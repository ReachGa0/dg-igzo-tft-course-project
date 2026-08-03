#!/usr/bin/env python3
"""Build the R06 generator toolchain and Xyce without formal device DC."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from m01_xyce_r06_common import digest_tree, load_json, sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r06.json"
EXPERIMENTS_PATH = ROOT / "config" / "experiments.json"
EXPECTED_CHECK_COUNT = 47
# formal_device_dc_invoked=false is the registered no-formal execution marker.
R06_STATIC_BOUNDARY_MARKER = "formal_device_dc_invoked=false"


def add_check(
    checks: list[dict[str, str]], name: str, passed: bool, detail: str
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def run_command(
    *,
    name: str,
    argv: list[str],
    run_directory: Path,
    environment: dict[str, str],
    records: list[dict[str, Any]],
    cwd: Path | None = None,
    timeout_seconds: int = 10800,
) -> tuple[bool, str]:
    log_path = run_directory / f"{name}.log"
    started = time.monotonic()
    returncode = -1
    timed_out = False
    try:
        result = subprocess.run(
            argv,
            cwd=cwd or ROOT,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
        returncode = result.returncode
        output = result.stdout + result.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        stdout = error.stdout.decode() if isinstance(error.stdout, bytes) else error.stdout
        stderr = error.stderr.decode() if isinstance(error.stderr, bytes) else error.stderr
        output = (stdout or "") + (stderr or "") + "\nCOMMAND_TIMEOUT\n"
    except OSError as error:
        output = f"COMMAND_OS_ERROR: {error}\n"
    elapsed = time.monotonic() - started
    with log_path.open("x", encoding="utf-8") as stream:
        stream.write("argv=" + json.dumps(argv) + "\n")
        stream.write(f"cwd={cwd or ROOT}\n")
        stream.write(f"returncode={returncode}\n")
        stream.write(f"timed_out={str(timed_out).lower()}\n")
        stream.write(f"elapsed_seconds={elapsed:.6f}\n")
        stream.write("output_begin\n")
        stream.write(output)
        if output and not output.endswith("\n"):
            stream.write("\n")
        stream.write("output_end\n")
    records.append(
        {
            "name": name,
            "argv": argv,
            "cwd": str(cwd or ROOT),
            "returncode": returncode,
            "timed_out": timed_out,
            "elapsed_seconds": elapsed,
            "log_path": str(log_path.relative_to(ROOT)),
            "log_sha256": sha256(log_path),
        }
    )
    return returncode == 0 and not timed_out, output


def read_xyce_csv(path: Path, column: str) -> float | None:
    if not path.is_file():
        return None
    with path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        return None
    normalized = {key.strip().upper(): key for key in rows[-1] if key is not None}
    key = normalized.get(column.upper())
    if key is None:
        return None
    try:
        return float(rows[-1][key])
    except (TypeError, ValueError):
        return None


def build_autotools_project(
    *,
    name: str,
    source_dir: Path,
    build_dir: Path,
    install_prefix: Path,
    configure_options: list[str],
    make_path: str,
    parallel_jobs: int,
    environment: dict[str, str],
    run_directory: Path,
    records: list[dict[str, Any]],
    enabled: bool,
) -> tuple[bool, bool, bool]:
    configure_ok = build_ok = install_ok = False
    if enabled:
        build_dir.mkdir(parents=True, exist_ok=False)
        configure_ok, _ = run_command(
            name=f"{name}_configure",
            argv=[
                str(source_dir / "configure"),
                f"--prefix={install_prefix}",
                *configure_options,
            ],
            run_directory=run_directory,
            environment=environment,
            records=records,
            cwd=build_dir,
        )
        if configure_ok:
            build_ok, _ = run_command(
                name=f"{name}_build",
                argv=[make_path, f"-j{parallel_jobs}"],
                run_directory=run_directory,
                environment=environment,
                records=records,
                cwd=build_dir,
            )
        if build_ok:
            install_ok, _ = run_command(
                name=f"{name}_install",
                argv=[make_path, "install"],
                run_directory=run_directory,
                environment=environment,
                records=records,
                cwd=build_dir,
            )
    return configure_ok, build_ok, install_ok


def run_preflight() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    experiments = load_json(EXPERIMENTS_PATH)
    m01 = next(item for item in experiments["experiments"] if item["id"] == "M01")
    machine = m01["xyce_build_preflight_r06"]
    outputs = config["outputs"]
    run_directory = ROOT / outputs["run_directory"]
    report_path = ROOT / outputs["preflight_report"]
    independent_report_path = ROOT / outputs["independent_check_report"]
    all_declared_paths = [
        ROOT / value for key, value in outputs.items() if key != "contract_report"
    ]
    preexisting = [path for path in all_declared_paths if path.exists()]
    if preexisting:
        raise RuntimeError(
            "Refusing to overwrite existing R06 outputs: "
            + ", ".join(str(path) for path in preexisting)
        )

    sources = config["source_provenance"]
    tools = config["toolchain"]
    build_dirs = {key: Path(value) for key, value in config["build_directories"].items()}
    generator_prefix = Path(tools["generator_install_prefix"])
    xyce_prefix = Path(sources["xyce"]["install_prefix"])
    new_external_roots = [*build_dirs.values(), generator_prefix, xyce_prefix]
    existing_new_roots = [path for path in new_external_roots if path.exists()]
    if existing_new_roots:
        raise RuntimeError(
            "Refusing to reuse R06 build/install roots: "
            + ", ".join(str(path) for path in existing_new_roots)
        )

    run_directory.mkdir(parents=True, exist_ok=False)
    preflight_log = ROOT / outputs["preflight_log"]
    with preflight_log.open("x", encoding="utf-8") as stream:
        stream.write("M01 Xyce build/tool preflight R06\n")
        stream.write("formal_device_dc_invoked=false\n")
        stream.write("formal_m01_numerical_run=false\n")
        stream.write("ngspice_invoked=false\n")
        stream.write("aimspice_invoked=false\n")
        stream.write("r05_suitesparse_trilinos_reused=true\n")
        stream.write("r05_partial_xyce_reused=false\n")

    checks: list[dict[str, str]] = []
    command_records: list[dict[str, Any]] = []
    formal_paths = [
        ROOT / value for value in config["formal_outputs_that_must_remain_absent"]
    ]

    add_check(
        checks,
        "identity:revision_6_xyce_build_preflight",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R06"
        and config.get("revision") == 6
        and config.get("status") == "preflight_planned"
        and machine.get("status") == "contract_ready"
        and machine.get("current_evidence") == "E3",
        f"stage={config.get('stage_id')} revision={config.get('revision')} machine={machine.get('status')}",
    )
    contract_report = ROOT / outputs["contract_report"]
    contract_json = load_json(contract_report) if contract_report.is_file() else {}
    add_check(
        checks,
        "binding:r06_static_contract_passed",
        contract_report.is_file()
        and contract_json.get("status") == "PASS"
        and contract_json.get("evidence_level") == "E3"
        and contract_json.get("summary", {}).get("passed")
        == machine.get("expected_contract_check_count")
        and machine.get("contract_check_completed") is True
        and machine.get("contract_status") == "PASS"
        and machine.get("artifact_hashes", {}).get("contract_report_sha256")
        == sha256(contract_report),
        f"contract={contract_report.is_file()} status={contract_json.get('status')}",
    )
    bound = config["bound_contract"]
    bound_config = ROOT / bound["path"]
    bound_report = ROOT / bound["report_path"]
    add_check(
        checks,
        "binding:open_source_recovery_contract",
        bound_config.is_file()
        and bound_report.is_file()
        and sha256(bound_config) == bound["sha256"]
        and sha256(bound_report) == bound["report_sha256"]
        and load_json(bound_report).get("status") == "PASS",
        "recovery config and E3 report remain hash-bound",
    )

    r05 = config["r05_failure_binding"]
    r05_paths = {
        "config": (r05["config_path"], r05["config_sha256"]),
        "contract": (r05["contract_report_path"], r05["contract_report_sha256"]),
        "preflight": (r05["preflight_report_path"], r05["preflight_report_sha256"]),
        "source_manifest": (r05["source_manifest_path"], r05["source_manifest_sha256"]),
        "build_manifest": (r05["build_manifest_path"], r05["build_manifest_sha256"]),
        "preflight_log": (r05["preflight_log_path"], r05["preflight_log_sha256"]),
        "trilinos_log": (r05["trilinos_build_log_path"], r05["trilinos_build_log_sha256"]),
        "xyce_log": (r05["xyce_build_log_path"], r05["xyce_build_log_sha256"]),
    }
    r05_hashes_ok = all(
        (ROOT / relative).is_file() and sha256(ROOT / relative) == expected
        for relative, expected in r05_paths.values()
    )
    add_check(
        checks,
        "binding:r05_artifacts_unchanged",
        r05["must_remain_unchanged"] is True
        and r05["bound_commit"] == "6779aab89e8e05aaea2645c50eed66cb5c6910bb"
        and r05_hashes_ok,
        f"artifacts={sum((ROOT / item[0]).is_file() for item in r05_paths.values())}/{len(r05_paths)}",
    )
    r05_report = load_json(ROOT / r05["preflight_report_path"])
    r05_build_manifest = load_json(ROOT / r05["build_manifest_path"])
    r05_xyce_log = (ROOT / r05["xyce_build_log_path"]).read_text(
        encoding="utf-8", errors="replace"
    )
    add_check(
        checks,
        "binding:r05_failed_gate_state",
        r05_report.get("status") == "FAIL"
        and r05_report.get("evidence_level") == "E0"
        and r05_report.get("summary", {}).get("passed") == r05["runner_checks_passed"] == 19
        and r05_report.get("summary", {}).get("failed") == r05["runner_checks_failed"] == 10
        and r05_report.get("summary", {}).get("controlled_bsource_self_test_invoked") is False
        and r05_report.get("summary", {}).get("device_syntax_only_invoked") is False
        and "cannot open: No such file or directory" in r05_xyce_log
        and "exec of /usr/bin/m4 failed" in r05_xyce_log
        and not (ROOT / "results/reports/m01_xyce_build_preflight_check_r05.json").exists(),
        "R05 remains 19/29 E0 with no independent check",
    )

    source_manifest: dict[str, Any] = {
        "archives": {},
        "sources": {},
        "r05_binding": {},
        "reused_dependencies": {},
    }
    xyce_archive = Path(sources["xyce"]["archive_path"])
    xyce_source = Path(sources["xyce"]["source_dir"])
    cmake_archive = Path(sources["cmake"]["archive_path"])
    cmake_binary = Path(sources["cmake"]["binary_path"])
    xyce_cmake_ok = (
        xyce_archive.is_file()
        and sha256(xyce_archive) == sources["xyce"]["archive_sha256"]
        and (xyce_source / sources["xyce"]["source_key_file"]).is_file()
        and cmake_archive.is_file()
        and sha256(cmake_archive) == sources["cmake"]["archive_sha256"]
        and cmake_binary.is_file()
    )
    source_manifest["archives"]["xyce"] = {
        "path": str(xyce_archive),
        "expected_sha256": sources["xyce"]["archive_sha256"],
        "actual_sha256": sha256(xyce_archive) if xyce_archive.is_file() else None,
    }
    source_manifest["archives"]["cmake"] = {
        "path": str(cmake_archive),
        "expected_sha256": sources["cmake"]["archive_sha256"],
        "actual_sha256": sha256(cmake_archive) if cmake_archive.is_file() else None,
    }
    source_manifest["sources"]["xyce"] = {
        "path": str(xyce_source),
        "key_file": sources["xyce"]["source_key_file"],
        "key_file_sha256": sha256(xyce_source / sources["xyce"]["source_key_file"])
        if (xyce_source / sources["xyce"]["source_key_file"]).is_file()
        else None,
    }
    add_check(
        checks,
        "sources:xyce_and_cmake_rehashed",
        xyce_cmake_ok,
        f"xyce={xyce_archive.is_file()} cmake={cmake_archive.is_file()}",
    )

    generator_archives_ok = []
    generator_sources_ok = []
    for key in ("m4", "bison", "flex"):
        item = sources[key]
        archive = Path(item["archive_path"])
        source_dir = Path(item["source_dir"])
        configure = source_dir / "configure"
        license_file = source_dir / item["license_file"]
        archive_hash = sha256(archive) if archive.is_file() else None
        archive_ok = archive_hash == item["archive_sha256"]
        source_ok = (
            configure.is_file()
            and sha256(configure) == item["configure_sha256"]
            and license_file.is_file()
            and sha256(license_file) == item["license_sha256"]
        )
        generator_archives_ok.append(archive_ok)
        generator_sources_ok.append(source_ok)
        source_manifest["archives"][key] = {
            "path": str(archive),
            "expected_sha256": item["archive_sha256"],
            "actual_sha256": archive_hash,
        }
        source_manifest["sources"][key] = {
            "path": str(source_dir),
            "configure_sha256": sha256(configure) if configure.is_file() else None,
            "license_file": item["license_file"],
            "license_sha256": sha256(license_file) if license_file.is_file() else None,
        }
    add_check(
        checks,
        "sources:generator_archives_rehashed",
        all(generator_archives_ok),
        f"archives={sum(generator_archives_ok)}/3",
    )
    add_check(
        checks,
        "sources:generator_trees_and_licenses",
        all(generator_sources_ok)
        and sources["m4"]["license"] == "GPL-3.0-or-later"
        and sources["bison"]["license"].startswith("GPL-3.0-or-later")
        and sources["flex"]["license"] == "BSD-2-Clause",
        f"sources={sum(generator_sources_ok)}/3",
    )
    scope = config["scope"]
    add_check(
        checks,
        "scope:serial_laptop_igzo_only",
        scope["active_material_scope"] == "IGZO only"
        and scope["laptop_target"] is True
        and scope["serial_build"] is True
        and scope["mpi_build"] is False
        and scope["fortran_build"] is False
        and scope["device_netlist_execution"] is False
        and scope["formal_m01_numerical_run"] is False
        and scope["circuit_or_downstream_permitted"] is False,
        json.dumps(scope, sort_keys=True),
    )
    add_check(
        checks,
        "outputs:formal_outputs_absent_before_build",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )

    reuse = config["dependency_reuse"]
    reuse_actual: dict[str, dict[str, int | str]] = {}
    for key in ("suitesparse", "trilinos"):
        prefix = Path(reuse[key]["install_prefix"])
        reuse_actual[key] = digest_tree(prefix) if prefix.is_dir() else {}
        source_manifest["reused_dependencies"][key] = {
            "path": str(prefix),
            "expected": {name: reuse[key][name] for name in reuse_actual[key]},
            "actual": reuse_actual[key],
        }
    reuse_ok = all(
        reuse_actual[key]
        and all(reuse_actual[key].get(name) == reuse[key].get(name) for name in reuse_actual[key])
        for key in ("suitesparse", "trilinos")
    )
    add_check(
        checks,
        "reuse:r05_dependency_tree_hashes",
        reuse_ok and reuse["dependency_rebuild_permitted"] is False,
        f"suitesparse={reuse_actual['suitesparse'].get('tree_sha256')} trilinos={reuse_actual['trilinos'].get('tree_sha256')}",
    )
    r05_commands = r05_build_manifest.get("commands", [])
    r05_command_map = {item.get("name"): item for item in r05_commands}
    add_check(
        checks,
        "reuse:r05_successful_install_command_audit",
        r05_command_map.get("suitesparse_build_install", {}).get("returncode") == 0
        and r05_command_map.get("trilinos_build_install", {}).get("returncode") == 0
        and r05_command_map.get("xyce_build_install", {}).get("returncode") == 2
        and r05_command_map.get("trilinos_build_install", {}).get("timed_out") is False
        and r05_command_map.get("xyce_build_install", {}).get("timed_out") is False,
        "R05 dependency installs passed and R05 Xyce build failed",
    )
    add_check(
        checks,
        "build:exclusive_new_r06_roots_absent",
        all(not path.exists() for path in new_external_roots)
        and len(new_external_roots) == len(set(new_external_roots))
        and config["build_plan"]["overwrite_build_directories"] is False,
        ", ".join(f"{path}={path.exists()}" for path in new_external_roots),
    )

    bootstrap_paths = {
        "cmake": Path(tools["cmake"]),
        "gcc": Path(tools["c_compiler"]),
        "g++": Path(tools["cxx_compiler"]),
        "make": Path(tools["make"]),
        "blas": Path(tools["blas_library_dir"]) / "libblas.so",
        "lapack": Path(tools["lapack_library_dir"]) / "liblapack.so",
    }
    bootstrap_hashes = tools["bootstrap_sha256"]
    bootstrap_ok = all(
        path.is_file() and sha256(path) == bootstrap_hashes[key]
        for key, path in bootstrap_paths.items()
    )
    add_check(
        checks,
        "toolchain:pinned_bootstrap_paths_and_hashes",
        bootstrap_ok and tools["max_parallel_jobs"] == 2,
        f"pinned={sum(path.is_file() for path in bootstrap_paths.values())}/{len(bootstrap_paths)}",
    )

    base_environment = os.environ.copy()
    base_environment["PATH"] = os.pathsep.join(
        [str(Path(tools["cmake"]).parent), base_environment.get("PATH", "")]
    )
    bootstrap_specs = {
        "cmake": ([tools["cmake"], "--version"], "cmake version 3.30.5"),
        "gcc": ([tools["c_compiler"], "--version"], "gcc"),
        "gxx": ([tools["cxx_compiler"], "--version"], "g++"),
        "make": ([tools["make"], "--version"], "GNU Make"),
    }
    bootstrap_probe_ok: list[bool] = []
    tool_probes: dict[str, str] = {}
    if bootstrap_ok:
        for name, (argv, token) in bootstrap_specs.items():
            passed, output = run_command(
                name=f"tool_probe_{name}",
                argv=argv,
                run_directory=run_directory,
                environment=base_environment,
                records=command_records,
                timeout_seconds=30,
            )
            bootstrap_probe_ok.append(passed and token in output)
            tool_probes[name] = output.strip()
    else:
        bootstrap_probe_ok = [False] * len(bootstrap_specs)
    add_check(
        checks,
        "toolchain:bootstrap_version_probes",
        all(bootstrap_probe_ok),
        f"passed={sum(bootstrap_probe_ok)}/{len(bootstrap_specs)}",
    )
    add_check(
        checks,
        "toolchain:no_mpi_fortran_or_proprietary_requirement",
        config["scope"]["mpi_build"] is False
        and config["scope"]["fortran_build"] is False
        and sources["xyce"]["proprietary_binary_accepted"] is False
        and config["no_execution_rules"]["runner_must_not_invoke_aimspice"] is True,
        "serial C/C++ open-source build only",
    )

    can_build_generators = all(item["status"] == "PASS" for item in checks)
    generator_environment = base_environment.copy()
    generator_environment["PATH"] = os.pathsep.join(
        [str(generator_prefix / "bin"), generator_environment.get("PATH", "")]
    )
    generator_environment["M4"] = tools["m4"]
    generator_environment["BISON_PKGDATADIR"] = tools["bison_pkgdatadir"]
    configure_options = config["build_plan"]["generator_configure_options"]

    m4_configure_ok, m4_build_ok, m4_install_command_ok = build_autotools_project(
        name="m4",
        source_dir=Path(sources["m4"]["source_dir"]),
        build_dir=build_dirs["m4_build"],
        install_prefix=generator_prefix,
        configure_options=configure_options,
        make_path=tools["make"],
        parallel_jobs=tools["max_parallel_jobs"],
        environment=base_environment,
        run_directory=run_directory,
        records=command_records,
        enabled=can_build_generators,
    )
    add_check(checks, "generator:m4_configure", m4_configure_ok, "GNU M4 1.4.19 configure")
    add_check(checks, "generator:m4_build", m4_build_ok, "GNU M4 two-job build")
    m4_install_ok = m4_install_command_ok and Path(tools["m4"]).is_file()
    add_check(checks, "generator:m4_install", m4_install_ok, f"binary={tools['m4']}")

    bison_configure_ok, bison_build_ok, bison_install_command_ok = build_autotools_project(
        name="bison",
        source_dir=Path(sources["bison"]["source_dir"]),
        build_dir=build_dirs["bison_build"],
        install_prefix=generator_prefix,
        configure_options=configure_options,
        make_path=tools["make"],
        parallel_jobs=tools["max_parallel_jobs"],
        environment=generator_environment,
        run_directory=run_directory,
        records=command_records,
        enabled=m4_install_ok,
    )
    add_check(checks, "generator:bison_configure", bison_configure_ok, "GNU Bison 3.8.2 configure")
    add_check(checks, "generator:bison_build", bison_build_ok, "GNU Bison two-job build")
    bison_install_ok = bison_install_command_ok and Path(tools["bison"]).is_file()
    add_check(checks, "generator:bison_install", bison_install_ok, f"binary={tools['bison']}")

    flex_configure_ok, flex_build_ok, flex_install_command_ok = build_autotools_project(
        name="flex",
        source_dir=Path(sources["flex"]["source_dir"]),
        build_dir=build_dirs["flex_build"],
        install_prefix=generator_prefix,
        configure_options=configure_options,
        make_path=tools["make"],
        parallel_jobs=tools["max_parallel_jobs"],
        environment=generator_environment,
        run_directory=run_directory,
        records=command_records,
        enabled=bison_install_ok,
    )
    add_check(checks, "generator:flex_configure", flex_configure_ok, "Flex 2.6.4 configure")
    add_check(checks, "generator:flex_build", flex_build_ok, "Flex two-job build")
    flex_install_ok = flex_install_command_ok and Path(tools["flex"]).is_file()
    add_check(checks, "generator:flex_install", flex_install_ok, f"binary={tools['flex']}")

    generator_probe_specs = {
        "m4": ([tools["m4"], "--version"], "m4 (GNU M4) 1.4.19"),
        "bison": ([tools["bison"], "--version"], "bison (GNU Bison) 3.8.2"),
        "flex": ([tools["flex"], "--version"], "flex 2.6.4"),
    }
    generator_probe_ok: list[bool] = []
    if m4_install_ok and bison_install_ok and flex_install_ok:
        for name, (argv, token) in generator_probe_specs.items():
            passed, output = run_command(
                name=f"generator_probe_{name}",
                argv=argv,
                run_directory=run_directory,
                environment=generator_environment,
                records=command_records,
                timeout_seconds=30,
            )
            generator_probe_ok.append(passed and token in output)
            tool_probes[name] = output.strip()
    else:
        generator_probe_ok = [False] * len(generator_probe_specs)
    add_check(
        checks,
        "generator:version_probes",
        all(generator_probe_ok),
        f"passed={sum(generator_probe_ok)}/{len(generator_probe_specs)}",
    )
    bison_data_dir = Path(tools["bison_pkgdatadir"])
    generator_data_ok = (
        (bison_data_dir / "m4sugar" / "m4sugar.m4").is_file()
        and (bison_data_dir / "skeletons" / "yacc.c").is_file()
        and (Path(tools["flex_include_dir"]) / "FlexLexer.h").is_file()
    )
    add_check(
        checks,
        "generator:data_and_include_paths",
        generator_data_ok,
        f"bison_data={bison_data_dir} flex_include={tools['flex_include_dir']}",
    )

    bison_input = ROOT / outputs["generator_bison_input"]
    bison_output = ROOT / outputs["generator_bison_output"]
    flex_input = ROOT / outputs["generator_flex_input"]
    flex_output = ROOT / outputs["generator_flex_output"]
    bison_text = """%{
int yylex(void);
void yyerror(const char *message) {(void)message;}
%}
%%
input: ;
%%
"""
    flex_text = """%option noyywrap
%%
[ \\t\\n]+ ;
. ;
%%
"""
    generator_smoke_scope_ok = all(
        token not in (bison_text + flex_text).lower()
        for token in ("igzo", "sno", "hzo", "device", "circuit")
    )
    if all(generator_probe_ok) and generator_data_ok:
        bison_input.write_text(bison_text, encoding="ascii")
        flex_input.write_text(flex_text, encoding="ascii")
    add_check(
        checks,
        "generator:smoke_inputs_scope",
        generator_smoke_scope_ok and bison_input.is_file() and flex_input.is_file(),
        "minimal parser/scanner generation only",
    )
    bison_smoke_ok = False
    if bison_input.is_file():
        bison_smoke_ok, _ = run_command(
            name="generator_bison_smoke",
            argv=[tools["bison"], f"--output={bison_output}", str(bison_input)],
            run_directory=run_directory,
            environment=generator_environment,
            records=command_records,
            timeout_seconds=120,
        )
    add_check(
        checks,
        "generator:bison_generation_smoke",
        bison_smoke_ok and bison_output.is_file() and bison_output.stat().st_size > 0,
        f"return={bison_smoke_ok} output={bison_output.is_file()}",
    )
    flex_smoke_ok = False
    if flex_input.is_file():
        flex_smoke_ok, _ = run_command(
            name="generator_flex_smoke",
            argv=[tools["flex"], f"--outfile={flex_output}", str(flex_input)],
            run_directory=run_directory,
            environment=generator_environment,
            records=command_records,
            timeout_seconds=120,
        )
    add_check(
        checks,
        "generator:flex_generation_smoke",
        flex_smoke_ok and flex_output.is_file() and flex_output.stat().st_size > 0,
        f"return={flex_smoke_ok} output={flex_output.is_file()}",
    )

    reuse_after = {
        key: digest_tree(Path(reuse[key]["install_prefix"]))
        for key in ("suitesparse", "trilinos")
    }
    add_check(
        checks,
        "reuse:dependency_trees_unchanged_after_generator_build",
        reuse_after == reuse_actual,
        "R05 dependency prefixes remain byte-identical",
    )

    cmake = tools["cmake"]
    suitesparse_prefix = Path(reuse["suitesparse"]["install_prefix"])
    trilinos_prefix = Path(reuse["trilinos"]["install_prefix"])
    prefix_path = f"{trilinos_prefix};{suitesparse_prefix}"
    xyce_environment = generator_environment.copy()
    xyce_environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        [
            str(suitesparse_prefix / "lib"),
            str(trilinos_prefix / "lib"),
            str(xyce_prefix / "lib"),
            str(Path(tools["blas_library_dir"])),
            xyce_environment.get("LD_LIBRARY_PATH", ""),
        ]
    )
    xyce_configure_argv = [
        cmake,
        "-S",
        str(xyce_source),
        "-B",
        str(build_dirs["xyce_build"]),
        f"-DCMAKE_INSTALL_PREFIX={xyce_prefix}",
        f"-DCMAKE_PREFIX_PATH={prefix_path}",
        f"-DTrilinos_ROOT={trilinos_prefix}",
        f"-DAMD_LIBRARY_DIRS={suitesparse_prefix / 'lib'}",
        f"-DAMD_INCLUDE_DIRS={suitesparse_prefix / 'include' / 'suitesparse'}",
        f"-DFLEX_EXECUTABLE={tools['flex']}",
        f"-DFLEX_INCLUDE_DIR={tools['flex_include_dir']}",
        f"-DBISON_EXECUTABLE={tools['bison']}",
        *config["build_plan"]["xyce_cmake_options"],
        f"-DCMAKE_C_COMPILER={tools['c_compiler']}",
        f"-DCMAKE_CXX_COMPILER={tools['cxx_compiler']}",
        "-DCMAKE_BUILD_TYPE=Release",
    ]
    xyce_configure_ok = xyce_build_ok = False
    if bison_smoke_ok and flex_smoke_ok and reuse_after == reuse_actual:
        build_dirs["xyce_build"].mkdir(parents=True, exist_ok=False)
        xyce_configure_ok, _ = run_command(
            name="xyce_configure",
            argv=xyce_configure_argv,
            run_directory=run_directory,
            environment=xyce_environment,
            records=command_records,
        )
        if xyce_configure_ok:
            xyce_build_ok, _ = run_command(
                name="xyce_build_install",
                argv=[
                    cmake,
                    "--build",
                    str(build_dirs["xyce_build"]),
                    "--parallel",
                    str(tools["max_parallel_jobs"]),
                    "--target",
                    "install",
                ],
                run_directory=run_directory,
                environment=xyce_environment,
                records=command_records,
            )
    add_check(checks, "build:xyce_configure", xyce_configure_ok, "Xyce 7.10 R06 configure")
    xyce_binary = xyce_prefix / "bin" / "Xyce"
    xyce_install_ok = xyce_build_ok and xyce_binary.is_file()
    add_check(checks, "build:xyce_install", xyce_install_ok, f"binary={xyce_binary}")

    version_ok = license_ok = False
    version_output = license_output = ""
    if xyce_install_ok:
        version_ok, version_output = run_command(
            name="xyce_version",
            argv=[str(xyce_binary), "-v"],
            run_directory=run_directory,
            environment=xyce_environment,
            records=command_records,
            timeout_seconds=60,
        )
        license_ok, license_output = run_command(
            name="xyce_license",
            argv=[str(xyce_binary), "-license"],
            run_directory=run_directory,
            environment=xyce_environment,
            records=command_records,
            timeout_seconds=60,
        )
    add_check(
        checks,
        "binary:version_fingerprint",
        version_ok and "7.10" in version_output and "Xyce" in version_output,
        version_output.strip()[:240],
    )
    add_check(
        checks,
        "binary:license_fingerprint",
        license_ok and "GNU General Public License" in license_output,
        "GPL token present" if "GNU General Public License" in license_output else "GPL token absent",
    )
    binary_hash = sha256(xyce_binary) if xyce_binary.is_file() else None
    add_check(
        checks,
        "binary:installed_executable_hash",
        xyce_binary.is_file() and binary_hash is not None and xyce_binary.stat().st_size > 0,
        f"sha256={binary_hash} bytes={xyce_binary.stat().st_size if xyce_binary.exists() else -1}",
    )

    self_test_netlist = ROOT / outputs["bsource_self_test_netlist"]
    self_test_log = ROOT / outputs["bsource_self_test_log"]
    self_test_output = ROOT / outputs["bsource_self_test_output"]
    self_test_text = """* M01 controlled Xyce B-source scalar self-test; not a project device
Vctrl nin 0 1.0
Btest nout 0 V={limit(V(nin),0,2)+sgn(V(nin))*0.25}
Vsense nout nload 0
Rload nload 0 1k
.DC Vctrl 1 1 1
.PRINT DC FORMAT=CSV V(nout) I(Vsense)
.END
"""
    self_test_scope_ok = all(
        token.lower() not in self_test_text.lower()
        for token in config["self_test"]["forbidden_tokens"]
    ) and ".DC" in self_test_text and "Btest" in self_test_text
    if xyce_install_ok and version_ok and license_ok:
        self_test_netlist.write_text(self_test_text, encoding="ascii")
    add_check(
        checks,
        "self_test:netlist_scope",
        xyce_install_ok and self_test_scope_ok and self_test_netlist.is_file(),
        "controlled scalar source only; no project candidate included",
    )
    self_test_run_ok = False
    if self_test_netlist.is_file():
        self_test_run_ok, _ = run_command(
            name="xyce_bsource_self_test_command",
            argv=[
                str(xyce_binary),
                "-l",
                str(self_test_log),
                "-o",
                str(self_test_output.with_suffix("")),
                str(self_test_netlist),
            ],
            run_directory=run_directory,
            environment=xyce_environment,
            records=command_records,
            timeout_seconds=120,
        )
    add_check(
        checks,
        "self_test:xyce_process_pass",
        self_test_run_ok and self_test_log.is_file() and self_test_output.is_file(),
        f"return={self_test_run_ok} log={self_test_log.is_file()} output={self_test_output.is_file()}",
    )
    observed_v = read_xyce_csv(self_test_output, "V(NOUT)")
    expected_v = float(config["self_test"]["expected_value_v"])
    tolerance_v = float(config["self_test"]["tolerance_v"])
    add_check(
        checks,
        "self_test:deterministic_scalar_value",
        observed_v is not None and abs(observed_v - expected_v) <= tolerance_v,
        f"observed={observed_v} expected={expected_v} tolerance={tolerance_v}",
    )

    device_syntax_netlist = ROOT / outputs["device_syntax_netlist"]
    device_syntax_log = ROOT / outputs["device_syntax_log"]
    device_syntax_output = ROOT / outputs["device_syntax_output"]
    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    device_syntax_text = (
        "* M01 parser-only frozen IGZO candidate check; no numerical solve\n"
        f'.include "{candidate}"\n'
        "VDS D S 0.1\nVTG TG S 0.5\nVBG BG S 0\n"
        "XIGZO D TG BG S IGZO_DG_BEHAVIORAL_R02\n"
        ".DC VTG 0.5 0.5 1\n.PRINT DC FORMAT=CSV V(TG) I(VDS)\n.END\n"
    )
    syntax_scope_ok = (
        candidate.is_file()
        and sha256(candidate) == config["device_syntax_check"]["candidate_sha256"]
        and all(
            token.lower() not in device_syntax_text.lower()
            for token in config["device_syntax_check"]["forbidden_tokens"]
        )
        and ".TRAN" not in device_syntax_text.upper()
    )
    if observed_v is not None and abs(observed_v - expected_v) <= tolerance_v:
        device_syntax_netlist.write_text(device_syntax_text, encoding="ascii")
    add_check(
        checks,
        "device_syntax:netlist_scope_and_candidate_hash",
        syntax_scope_ok and device_syntax_netlist.is_file(),
        "frozen IGZO candidate only; parser-only gate",
    )
    device_syntax_ok = False
    if device_syntax_netlist.is_file():
        device_syntax_ok, _ = run_command(
            name="xyce_device_syntax_command",
            argv=[
                str(xyce_binary),
                "-syntax",
                "-l",
                str(device_syntax_log),
                "-o",
                str(device_syntax_output.with_suffix("")),
                str(device_syntax_netlist),
            ],
            run_directory=run_directory,
            environment=xyce_environment,
            records=command_records,
            timeout_seconds=120,
        )
    add_check(
        checks,
        "device_syntax:xyce_parser_pass",
        device_syntax_ok and device_syntax_log.is_file(),
        f"return={device_syntax_ok} log={device_syntax_log.is_file()}",
    )
    add_check(
        checks,
        "device_syntax:no_numerical_output",
        not device_syntax_output.exists(),
        f"numerical_output_exists={device_syntax_output.exists()}",
    )
    add_check(
        checks,
        "execution:no_formal_m01_outputs_after_preflight",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    invoked_programs = [
        Path(record["argv"][0]).name.lower() for record in command_records if record.get("argv")
    ]
    command_names = [record["name"] for record in command_records]
    formal_device_invocations = [
        record
        for record in command_records
        if record["name"] == "xyce_device_syntax_command" and "-syntax" not in record["argv"]
    ]
    add_check(
        checks,
        "execution:invocation_audit",
        "ngspice" not in invoked_programs
        and "aimspice" not in invoked_programs
        and not formal_device_invocations
        and not any(name.startswith("suitesparse_") or name.startswith("trilinos_") for name in command_names)
        and any(name == "generator_bison_smoke" for name in command_names)
        and any(name == "generator_flex_smoke" for name in command_names)
        and any(name == "xyce_bsource_self_test_command" for name in command_names)
        and any(name == "xyce_device_syntax_command" for name in command_names),
        f"commands={len(command_records)} dependency_rebuild=false formal_device_dc=false",
    )
    add_check(
        checks,
        "gate:m01_and_downstream_remain_closed",
        config["scope"]["circuit_or_downstream_permitted"] is False
        and config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True,
        "formal M01 requires persisted R06 preflight plus independent check",
    )

    for name, (relative, expected) in r05_paths.items():
        source_manifest["r05_binding"][name] = {
            "path": relative,
            "expected_sha256": expected,
            "actual_sha256": sha256(ROOT / relative),
        }
    source_manifest["config"] = {
        "path": str(CONFIG_PATH.relative_to(ROOT)),
        "sha256": sha256(CONFIG_PATH),
    }
    source_manifest["tool_probes"] = tool_probes
    source_manifest["generator_smoke"] = {
        "bison_input_sha256": sha256(bison_input) if bison_input.is_file() else None,
        "bison_output_sha256": sha256(bison_output) if bison_output.is_file() else None,
        "flex_input_sha256": sha256(flex_input) if flex_input.is_file() else None,
        "flex_output_sha256": sha256(flex_output) if flex_output.is_file() else None,
    }
    source_manifest["binary"] = {
        "path": str(xyce_binary),
        "sha256": binary_hash,
        "bytes": xyce_binary.stat().st_size if xyce_binary.exists() else None,
        "version_output": version_output.strip(),
        "license_output_sha256": hashlib.sha256(license_output.encode("utf-8")).hexdigest()
        if license_output
        else None,
    }
    source_manifest_path = ROOT / outputs["source_manifest"]
    with source_manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(source_manifest, stream, indent=2, ensure_ascii=True)
        stream.write("\n")

    build_manifest = {
        "preflight_id": config["preflight_id"],
        "serial_build": True,
        "fortran_enabled": False,
        "mpi_enabled": False,
        "parallel_jobs": tools["max_parallel_jobs"],
        "dependency_rebuild_permitted": False,
        "reused_dependency_prefixes": {
            key: reuse[key]["install_prefix"] for key in ("suitesparse", "trilinos")
        },
        "generator_install_prefix": str(generator_prefix),
        "xyce_install_prefix": str(xyce_prefix),
        "build_directories": {key: str(value) for key, value in build_dirs.items()},
        "environment_overrides": config["build_plan"]["environment_overrides"],
        "commands": command_records,
    }
    build_manifest_path = ROOT / outputs["build_manifest"]
    with build_manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(build_manifest, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    add_check(
        checks,
        "artifacts:source_and_build_manifests",
        source_manifest_path.is_file()
        and build_manifest_path.is_file()
        and bool(sha256(source_manifest_path))
        and bool(sha256(build_manifest_path)),
        f"sources={source_manifest_path} build={build_manifest_path}",
    )
    add_check(
        checks,
        "artifacts:preflight_log_and_exclusive_report",
        preflight_log.is_file()
        and not report_path.exists()
        and not independent_report_path.exists(),
        f"log={preflight_log.is_file()} report_preexisting={report_path.exists()}",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"R06 preflight registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    failures = [item for item in checks if item["status"] == "FAIL"]
    with preflight_log.open("a", encoding="utf-8") as stream:
        stream.write(f"checks_passed={len(checks) - len(failures)}/{len(checks)}\n")
        stream.write(f"preflight_status={'FAIL' if failures else 'PASS'}\n")
        stream.write("formal_device_dc_invoked=false\n")
        stream.write("formal_m01_numerical_run=false\n")

    report = {
        "status": "FAIL" if failures else "PASS",
        "preflight_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E2",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "build_status": "FAIL"
        if any(
            item["status"] == "FAIL"
            for item in checks
            if item["name"].startswith(("generator:", "build:", "binary:"))
        )
        else "PASS",
        "bsource_self_test_status": "PASS"
        if all(item["status"] == "PASS" for item in checks if item["name"].startswith("self_test:"))
        else "FAIL",
        "device_syntax_status": "PASS"
        if all(item["status"] == "PASS" for item in checks if item["name"].startswith("device_syntax:"))
        else "FAIL",
        "formal_device_simulation_status": "NOT_RUN_BY_PREFLIGHT",
        "formal_spice_numerical_status": "NOT_RUN_BY_PREFLIGHT",
        "circuit_status": "NOT_RUN_BY_PREFLIGHT",
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "process_invocations": len(command_records),
            "ngspice_invoked": False,
            "aimspice_invoked": False,
            "controlled_generator_smoke_invoked": any(
                record["name"] in {"generator_bison_smoke", "generator_flex_smoke"}
                for record in command_records
            ),
            "controlled_bsource_self_test_invoked": any(
                record["name"] == "xyce_bsource_self_test_command" for record in command_records
            ),
            "device_syntax_only_invoked": any(
                record["name"] == "xyce_device_syntax_command" for record in command_records
            ),
            "formal_device_dc_invoked": False,
            "formal_m01_outputs_created": False,
            "r05_dependency_rebuild_invoked": False,
            "r05_partial_xyce_reused": False,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {
            "path": str(Path(__file__).relative_to(ROOT)),
            "sha256": sha256(Path(__file__)),
        },
        "preflight_log": {
            "path": str(preflight_log.relative_to(ROOT)),
            "sha256": sha256(preflight_log),
        },
        "source_manifest": {
            "path": str(source_manifest_path.relative_to(ROOT)),
            "sha256": sha256(source_manifest_path),
        },
        "build_manifest": {
            "path": str(build_manifest_path.relative_to(ROOT)),
            "sha256": sha256(build_manifest_path),
        },
        "xyce_binary": {
            "path": str(xyce_binary),
            "sha256": binary_hash,
            "bytes": xyce_binary.stat().st_size if xyce_binary.exists() else None,
        },
        "observed_self_test_value_v": observed_v,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": "Run the R06 independent persisted-evidence check exactly once; formal M01 device DC and downstream stages remain closed until it passes."
        if not failures
        else "Retain this failed R06 preflight and stop M01; diagnose in a new revision without deleting evidence or weakening the registered gate.",
    }
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_R06_{report['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={report_path}"
    )
    return report


if __name__ == "__main__":
    result = run_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
