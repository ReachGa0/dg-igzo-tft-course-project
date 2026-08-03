#!/usr/bin/env python3
"""Build pure-source Xyce and run tool-only preflight self-tests."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r01.json"
EXPECTED_CHECK_COUNT = 29


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


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


def run_preflight() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    run_directory = ROOT / outputs["run_directory"]
    report_path = ROOT / outputs["preflight_report"]
    independent_report_path = ROOT / outputs["independent_check_report"]
    # The contract report is committed before execution; only run-scoped artifacts
    # must be exclusive and absent when this runner starts.
    all_declared_paths = [
        ROOT / value for key, value in outputs.items() if key != "contract_report"
    ]
    preexisting = [path for path in all_declared_paths if path.exists()]
    if preexisting:
        raise RuntimeError(
            "Refusing to overwrite existing Xyce build/preflight outputs: "
            + ", ".join(str(path) for path in preexisting)
        )
    run_directory.mkdir(parents=True, exist_ok=False)

    preflight_log = ROOT / outputs["preflight_log"]
    with preflight_log.open("x", encoding="utf-8") as stream:
        stream.write("M01 Xyce build/tool preflight R01\n")
        stream.write("formal_device_dc_invoked=false\n")
        stream.write("formal_m01_numerical_run=false\n")
        stream.write("ngspice_invoked=false\n")
        stream.write("aimspice_invoked=false\n")

    checks: list[dict[str, str]] = []
    command_records: list[dict[str, Any]] = []
    sources = config["source_provenance"]
    tools = config["toolchain"]
    build_dirs = {key: Path(value) for key, value in config["build_directories"].items()}
    install_prefixes = {
        key: Path(sources[key]["install_prefix"])
        for key in ("suitesparse", "trilinos", "xyce")
    }
    formal_paths = [ROOT / value for value in config["formal_outputs_that_must_remain_absent"]]

    add_check(
        checks,
        "identity:revision_1_xyce_build_preflight",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R01"
        and config.get("revision") == 1
        and config.get("status") == "preflight_planned",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
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
        f"config={bound_config.is_file()} report={bound_report.is_file()}",
    )

    archive_results = []
    source_results = []
    source_key_files = {
        "xyce": "INSTALL.md",
        "trilinos": "CMakeLists.txt",
        "suitesparse": "CMakeLists.txt",
    }
    source_manifest: dict[str, Any] = {"archives": {}, "sources": {}}
    for key, key_file in source_key_files.items():
        item = sources[key]
        archive = Path(item["archive_path"])
        source_dir = Path(item["source_dir"])
        actual_archive_hash = sha256(archive) if archive.is_file() else None
        archive_ok = actual_archive_hash == item["archive_sha256"]
        source_ok = source_dir.is_dir() and (source_dir / key_file).is_file()
        archive_results.append(archive_ok)
        source_results.append(source_ok)
        source_manifest["archives"][key] = {
            "path": str(archive),
            "expected_sha256": item["archive_sha256"],
            "actual_sha256": actual_archive_hash,
            "match": archive_ok,
        }
        source_manifest["sources"][key] = {
            "path": str(source_dir),
            "key_file": key_file,
            "key_file_sha256": sha256(source_dir / key_file) if source_ok else None,
        }
    cmake_archive = Path(sources["cmake"]["archive_path"])
    cmake_hash = sha256(cmake_archive) if cmake_archive.is_file() else None
    cmake_archive_ok = cmake_hash == sources["cmake"]["archive_sha256"]
    source_manifest["archives"]["cmake"] = {
        "path": str(cmake_archive),
        "expected_sha256": sources["cmake"]["archive_sha256"],
        "actual_sha256": cmake_hash,
        "match": cmake_archive_ok,
    }
    add_check(
        checks,
        "sources:archive_hashes",
        all(archive_results) and cmake_archive_ok,
        f"source_archives={sum(archive_results)}/3 cmake={cmake_archive_ok}",
    )
    add_check(
        checks,
        "sources:extracted_tree_key_files",
        all(source_results),
        f"key_files={sum(source_results)}/3",
    )

    tool_paths = {
        "cmake": Path(tools["cmake"]),
        "gcc": Path(tools["c_compiler"]),
        "g++": Path(tools["cxx_compiler"]),
        "make": Path(tools["make"]),
        "bison": Path(tools["bison"]),
        "flex": Path(tools["flex"]),
    }
    add_check(
        checks,
        "toolchain:pinned_paths_exist",
        all(path.is_file() for path in tool_paths.values()),
        ", ".join(f"{key}={path.is_file()}" for key, path in tool_paths.items()),
    )
    add_check(
        checks,
        "outputs:formal_outputs_absent_before_build",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    external_roots_absent = all(not path.exists() for path in [*build_dirs.values(), *install_prefixes.values()])
    add_check(
        checks,
        "build:exclusive_external_roots_absent",
        external_roots_absent and config["build_plan"]["overwrite_build_directories"] is False,
        ", ".join(f"{path}={path.exists()}" for path in [*build_dirs.values(), *install_prefixes.values()]),
    )

    environment = os.environ.copy()
    toolchain_bin = str(Path(tools["bison"]).parent)
    cmake_bin = str(Path(tools["cmake"]).parent)
    environment["PATH"] = os.pathsep.join([cmake_bin, toolchain_bin, environment.get("PATH", "")])
    library_paths = [
        str(Path(tools["bison"]).parents[1] / "lib" / "x86_64-linux-gnu"),
        str(install_prefixes["suitesparse"] / "lib"),
        str(install_prefixes["trilinos"] / "lib"),
        str(install_prefixes["xyce"] / "lib"),
    ]
    environment["LD_LIBRARY_PATH"] = os.pathsep.join(
        library_paths + [environment.get("LD_LIBRARY_PATH", "")]
    )

    probe_specs = {
        "cmake": ([str(tool_paths["cmake"]), "--version"], "cmake version 3.30.5"),
        "gcc": ([str(tool_paths["gcc"]), "--version"], "gcc"),
        "gxx": ([str(tool_paths["g++"]), "--version"], "g++"),
        "make": ([str(tool_paths["make"]), "--version"], "GNU Make"),
        "bison": ([str(tool_paths["bison"]), "--version"], "3.8.2"),
        "flex": ([str(tool_paths["flex"]), "--version"], "2.6.4"),
    }
    probe_passes = []
    probe_outputs: dict[str, str] = {}
    if all(path.is_file() for path in tool_paths.values()):
        for name, (argv, token) in probe_specs.items():
            passed, output = run_command(
                name=f"tool_probe_{name}",
                argv=argv,
                run_directory=run_directory,
                environment=environment,
                records=command_records,
                timeout_seconds=30,
            )
            probe_passes.append(passed and token in output)
            probe_outputs[name] = output.strip()
    else:
        probe_passes = [False] * len(probe_specs)
    add_check(
        checks,
        "toolchain:version_probes",
        all(probe_passes),
        f"passed={sum(probe_passes)}/{len(probe_specs)}",
    )
    add_check(
        checks,
        "toolchain:no_mpi_fortran_or_proprietary_requirement",
        config["scope"]["mpi_build"] is False
        and config["scope"]["fortran_build"] is False
        and sources["xyce"]["proprietary_binary_accepted"] is False
        and config["no_execution_rules"]["runner_must_not_invoke_aimspice"] is True,
        "serial C/C++ build only; proprietary binaries are excluded",
    )

    can_build = all(item["status"] == "PASS" for item in checks)
    cmake = str(tool_paths["cmake"])
    common_cmake = [
        f"-DCMAKE_C_COMPILER={tools['c_compiler']}",
        f"-DCMAKE_CXX_COMPILER={tools['cxx_compiler']}",
        "-DCMAKE_BUILD_TYPE=Release",
    ]
    suitesparse_configure = [
        cmake,
        "-S",
        sources["suitesparse"]["source_dir"],
        "-B",
        str(build_dirs["suitesparse_build"]),
        f"-DCMAKE_INSTALL_PREFIX={install_prefixes['suitesparse']}",
        "-DSUITESPARSE_ENABLE_PROJECTS=suitesparse_config;amd",
        "-DSUITESPARSE_USE_FORTRAN=OFF",
        "-DSUITESPARSE_USE_CUDA=OFF",
        *common_cmake,
    ]
    suitesparse_build = [
        cmake,
        "--build",
        str(build_dirs["suitesparse_build"]),
        "--parallel",
        str(tools["max_parallel_jobs"]),
        "--target",
        "install",
    ]
    suite_config_ok = suite_build_ok = False
    if can_build:
        suite_config_ok, _ = run_command(
            name="suitesparse_configure",
            argv=suitesparse_configure,
            run_directory=run_directory,
            environment=environment,
            records=command_records,
        )
        if suite_config_ok:
            suite_build_ok, _ = run_command(
                name="suitesparse_build_install",
                argv=suitesparse_build,
                run_directory=run_directory,
                environment=environment,
                records=command_records,
            )
    add_check(checks, "build:suitesparse_configure", suite_config_ok, "SuiteSparse AMD-only configure")
    suite_install_ok = (
        suite_build_ok
        and (install_prefixes["suitesparse"] / "include" / "suitesparse" / "amd.h").is_file()
        and any((install_prefixes["suitesparse"] / "lib").glob("libamd.so*"))
    )
    add_check(checks, "build:suitesparse_install", suite_install_ok, "AMD and SuiteSparse_config installed")

    trilinos_configure = [
        cmake,
        "-C",
        config["build_plan"]["trilinos_initial_cache"],
        "-S",
        sources["trilinos"]["source_dir"],
        "-B",
        str(build_dirs["trilinos_build"]),
        f"-DCMAKE_INSTALL_PREFIX={install_prefixes['trilinos']}",
        f"-DAMD_LIBRARY_DIRS={install_prefixes['suitesparse'] / 'lib'}",
        f"-DAMD_INCLUDE_DIRS={install_prefixes['suitesparse'] / 'include' / 'suitesparse'}",
        f"-DBLAS_LIBRARY_DIRS={tools['blas_library_dir']}",
        f"-DLAPACK_LIBRARY_DIRS={tools['lapack_library_dir']}",
        *config["build_plan"]["trilinos_cmake_options"],
        *common_cmake,
    ]
    trilinos_build = [
        cmake,
        "--build",
        str(build_dirs["trilinos_build"]),
        "--parallel",
        str(tools["max_parallel_jobs"]),
        "--target",
        "install",
    ]
    trilinos_config_ok = trilinos_build_ok = False
    if suite_install_ok:
        trilinos_config_ok, _ = run_command(
            name="trilinos_configure",
            argv=trilinos_configure,
            run_directory=run_directory,
            environment=environment,
            records=command_records,
        )
        if trilinos_config_ok:
            trilinos_build_ok, _ = run_command(
                name="trilinos_build_install",
                argv=trilinos_build,
                run_directory=run_directory,
                environment=environment,
                records=command_records,
            )
    add_check(checks, "build:trilinos_configure", trilinos_config_ok, "serial Trilinos 14.4 configure")
    trilinos_install_ok = trilinos_build_ok and (
        install_prefixes["trilinos"] / "lib" / "cmake" / "Trilinos" / "TrilinosConfig.cmake"
    ).is_file()
    add_check(checks, "build:trilinos_install", trilinos_install_ok, "TrilinosConfig.cmake installed")

    flex_include = Path(tools["flex"]).parents[1] / "include"
    prefix_path = f"{install_prefixes['trilinos']};{install_prefixes['suitesparse']}"
    xyce_configure = [
        cmake,
        "-S",
        sources["xyce"]["source_dir"],
        "-B",
        str(build_dirs["xyce_build"]),
        f"-DCMAKE_INSTALL_PREFIX={install_prefixes['xyce']}",
        f"-DCMAKE_PREFIX_PATH={prefix_path}",
        f"-DTrilinos_ROOT={install_prefixes['trilinos']}",
        f"-DAMD_LIBRARY_DIRS={install_prefixes['suitesparse'] / 'lib'}",
        f"-DAMD_INCLUDE_DIRS={install_prefixes['suitesparse'] / 'include' / 'suitesparse'}",
        f"-DFLEX_EXECUTABLE={tools['flex']}",
        f"-DFLEX_INCLUDE_DIR={flex_include}",
        f"-DBISON_EXECUTABLE={tools['bison']}",
        *config["build_plan"]["xyce_cmake_options"],
        *common_cmake,
    ]
    xyce_build = [
        cmake,
        "--build",
        str(build_dirs["xyce_build"]),
        "--parallel",
        str(tools["max_parallel_jobs"]),
        "--target",
        "install",
    ]
    xyce_config_ok = xyce_build_ok = False
    if trilinos_install_ok:
        xyce_config_ok, _ = run_command(
            name="xyce_configure",
            argv=xyce_configure,
            run_directory=run_directory,
            environment=environment,
            records=command_records,
        )
        if xyce_config_ok:
            xyce_build_ok, _ = run_command(
                name="xyce_build_install",
                argv=xyce_build,
                run_directory=run_directory,
                environment=environment,
                records=command_records,
            )
    add_check(checks, "build:xyce_configure", xyce_config_ok, "Xyce 7.10 configure")
    xyce_binary = install_prefixes["xyce"] / "bin" / "Xyce"
    xyce_install_ok = xyce_build_ok and xyce_binary.is_file()
    add_check(checks, "build:xyce_install", xyce_install_ok, f"binary={xyce_binary}")

    version_ok = license_ok = False
    version_output = license_output = ""
    if xyce_install_ok:
        version_ok, version_output = run_command(
            name="xyce_version",
            argv=[str(xyce_binary), "-v"],
            run_directory=run_directory,
            environment=environment,
            records=command_records,
            timeout_seconds=60,
        )
        license_ok, license_output = run_command(
            name="xyce_license",
            argv=[str(xyce_binary), "-license"],
            run_directory=run_directory,
            environment=environment,
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
    self_test_text = """* M01 controlled Xyce B-source scalar self-test; not a project device\nVctrl nin 0 1.0\nBtest nout 0 V={limit(V(nin),0,2)+sgn(V(nin))*0.25}\nVsense nout nload 0\nRload nload 0 1k\n.DC Vctrl 1 1 1\n.PRINT DC FORMAT=CSV V(nout) I(Vsense)\n.END\n"""
    self_test_scope_ok = all(
        token.lower() not in self_test_text.lower()
        for token in config["self_test"]["forbidden_tokens"]
    ) and ".DC" in self_test_text and "Btest" in self_test_text
    if xyce_install_ok and version_ok and license_ok:
        with self_test_netlist.open("x", encoding="ascii") as stream:
            stream.write(self_test_text)
    add_check(
        checks,
        "self_test:netlist_scope",
        xyce_install_ok and self_test_scope_ok and self_test_netlist.is_file(),
        "controlled scalar source only; no project candidate included",
    )
    self_test_run_ok = False
    if self_test_netlist.is_file():
        self_test_basename = str(self_test_output.with_suffix(""))
        self_test_run_ok, _ = run_command(
            name="xyce_bsource_self_test_command",
            argv=[
                str(xyce_binary),
                "-l",
                str(self_test_log),
                "-o",
                self_test_basename,
                str(self_test_netlist),
            ],
            run_directory=run_directory,
            environment=environment,
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
        with device_syntax_netlist.open("x", encoding="ascii") as stream:
            stream.write(device_syntax_text)
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
            environment=environment,
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
    invoked_programs = [Path(record["argv"][0]).name.lower() for record in command_records]
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
        and any(record["name"] == "xyce_bsource_self_test_command" for record in command_records)
        and any(record["name"] == "xyce_device_syntax_command" for record in command_records),
        f"commands={len(command_records)} ngspice=false aimspice=false formal_device_dc=false",
    )
    add_check(
        checks,
        "gate:m01_and_downstream_remain_closed",
        config["scope"]["circuit_or_downstream_permitted"] is False
        and config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True,
        "formal M01 requires persisted preflight plus independent check",
    )

    source_manifest_path = ROOT / outputs["source_manifest"]
    source_manifest["config"] = {
        "path": str(CONFIG_PATH.relative_to(ROOT)),
        "sha256": sha256(CONFIG_PATH),
    }
    source_manifest["tool_probes"] = probe_outputs
    source_manifest["binary"] = {
        "path": str(xyce_binary),
        "sha256": binary_hash,
        "bytes": xyce_binary.stat().st_size if xyce_binary.exists() else None,
        "version_output": version_output.strip(),
        "license_output_sha256": hashlib.sha256(license_output.encode("utf-8")).hexdigest()
        if license_output
        else None,
    }
    with source_manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(source_manifest, stream, indent=2, ensure_ascii=True)
        stream.write("\n")

    build_manifest_path = ROOT / outputs["build_manifest"]
    build_manifest = {
        "preflight_id": config["preflight_id"],
        "serial_build": True,
        "fortran_enabled": False,
        "mpi_enabled": False,
        "parallel_jobs": tools["max_parallel_jobs"],
        "commands": command_records,
        "install_prefixes": {key: str(value) for key, value in install_prefixes.items()},
        "build_directories": {key: str(value) for key, value in build_dirs.items()},
    }
    with build_manifest_path.open("x", encoding="utf-8") as stream:
        json.dump(build_manifest, stream, indent=2, ensure_ascii=True)
        stream.write("\n")

    add_check(
        checks,
        "artifacts:source_and_build_manifests",
        source_manifest_path.is_file()
        and build_manifest_path.is_file()
        and sha256(source_manifest_path)
        and sha256(build_manifest_path),
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
            f"Preflight check registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
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
        "build_status": "FAIL" if any(item["status"] == "FAIL" for item in checks if item["name"].startswith("build:")) else "PASS",
        "bsource_self_test_status": "PASS" if all(item["status"] == "PASS" for item in checks if item["name"].startswith("self_test:")) else "FAIL",
        "device_syntax_status": "PASS" if all(item["status"] == "PASS" for item in checks if item["name"].startswith("device_syntax:")) else "FAIL",
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
            "controlled_bsource_self_test_invoked": any(record["name"] == "xyce_bsource_self_test_command" for record in command_records),
            "device_syntax_only_invoked": any(record["name"] == "xyce_device_syntax_command" for record in command_records),
            "formal_device_dc_invoked": False,
            "formal_m01_outputs_created": False,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256(Path(__file__))},
        "preflight_log": {"path": str(preflight_log.relative_to(ROOT)), "sha256": sha256(preflight_log)},
        "source_manifest": {"path": str(source_manifest_path.relative_to(ROOT)), "sha256": sha256(source_manifest_path)},
        "build_manifest": {"path": str(build_manifest_path.relative_to(ROOT)), "sha256": sha256(build_manifest_path)},
        "xyce_binary": {"path": str(xyce_binary), "sha256": binary_hash, "bytes": xyce_binary.stat().st_size if xyce_binary.exists() else None},
        "observed_self_test_value_v": observed_v,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"] if not failures else "Retain this failed preflight and stop M01; diagnose without deleting or weakening the registered gate.",
    }
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_{report['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={report_path}"
    )
    return report


if __name__ == "__main__":
    result = run_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
