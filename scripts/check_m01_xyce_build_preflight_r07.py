#!/usr/bin/env python3
"""Independently check persisted R07 Xyce build/preflight evidence."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from m01_xyce_r07_common import digest_tree, load_json, sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r07.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r07.py"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_r07.json"
CHECK_REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_check_r07.json"
EXPECTED_CHECK_COUNT = 25
EXPECTED_RUNNER_CHECK_COUNT = 47
# EXPECTED_CHECK_COUNT = 25 is the registered no-simulator independent-check marker.
R07_INDEPENDENT_CHECK_COUNT = 25


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


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


def check_preflight() -> dict[str, Any]:
    if CHECK_REPORT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite existing R07 independent report: {CHECK_REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    report = load_json(REPORT_PATH)
    outputs = config["outputs"]
    checks: list[dict[str, str]] = []
    runner_checks = report.get("checks", [])

    add_check(
        checks,
        "result:runner_passed_all_registered_checks",
        report.get("status") == "PASS"
        and report.get("preflight_status") == "PASS"
        and report.get("evidence_level") == "E2"
        and len(runner_checks) == EXPECTED_RUNNER_CHECK_COUNT
        and all(item.get("status") == "PASS" for item in runner_checks),
        f"passed={sum(item.get('status') == 'PASS' for item in runner_checks)}/{len(runner_checks)}",
    )
    summary = report.get("summary", {})
    add_check(
        checks,
        "result:tool_only_boundary",
        report.get("formal_device_simulation_status") == "NOT_RUN_BY_PREFLIGHT"
        and report.get("formal_spice_numerical_status") == "NOT_RUN_BY_PREFLIGHT"
        and report.get("circuit_status") == "NOT_RUN_BY_PREFLIGHT"
        and summary.get("ngspice_invoked") is False
        and summary.get("aimspice_invoked") is False
        and summary.get("formal_device_dc_invoked") is False
        and summary.get("formal_m01_outputs_created") is False
        and summary.get("r05_dependency_rebuild_invoked") is False
        and summary.get("r05_partial_xyce_reused") is False
        and summary.get("r06_xyce_or_outputs_reused") is False,
        "R07 is generator build, Xyce build, scalar self-test and parser-only evidence",
    )
    add_check(
        checks,
        "identity:config_and_runner_hashes",
        report.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and report.get("runner", {}).get("sha256") == sha256(RUNNER_PATH)
        and report.get("preflight_id") == config["preflight_id"],
        f"config={report.get('config', {}).get('sha256')} runner={report.get('runner', {}).get('sha256')}",
    )
    preflight_log = ROOT / report["preflight_log"]["path"]
    source_manifest_path = ROOT / report["source_manifest"]["path"]
    build_manifest_path = ROOT / report["build_manifest"]["path"]
    add_check(
        checks,
        "artifacts:registered_hashes",
        preflight_log.is_file()
        and source_manifest_path.is_file()
        and build_manifest_path.is_file()
        and sha256(preflight_log) == report["preflight_log"]["sha256"]
        and sha256(source_manifest_path) == report["source_manifest"]["sha256"]
        and sha256(build_manifest_path) == report["build_manifest"]["sha256"],
        "preflight log and both manifests match the runner report",
    )
    source_manifest = load_json(source_manifest_path)
    archive_hashes_ok = all(
        item.get("actual_sha256") == item.get("expected_sha256")
        and Path(item["path"]).is_file()
        and sha256(Path(item["path"])) == item["expected_sha256"]
        for item in source_manifest["archives"].values()
    )
    add_check(
        checks,
        "sources:all_archives_rehashed",
        archive_hashes_ok and len(source_manifest["archives"]) == 5,
        f"archives={len(source_manifest['archives'])}",
    )
    sources = config["source_provenance"]
    extracted_ok = True
    for key in ("m4", "bison", "flex"):
        item = source_manifest["sources"][key]
        source_dir = Path(item["path"])
        extracted_ok = extracted_ok and (
            source_dir.is_dir()
            and sha256(source_dir / "configure") == sources[key]["configure_sha256"]
            and item["configure_sha256"] == sources[key]["configure_sha256"]
            and sha256(source_dir / sources[key]["license_file"])
            == sources[key]["license_sha256"]
            and item["license_sha256"] == sources[key]["license_sha256"]
        )
    xyce_source_item = source_manifest["sources"]["xyce"]
    xyce_key = Path(xyce_source_item["path"]) / xyce_source_item["key_file"]
    add_check(
        checks,
        "sources:extracted_key_files_and_licenses",
        extracted_ok
        and xyce_key.is_file()
        and sha256(xyce_key) == xyce_source_item["key_file_sha256"],
        "Xyce key file and all generator configure/license files match",
    )
    r05_binding_ok = all(
        (ROOT / item["path"]).is_file()
        and item["actual_sha256"] == item["expected_sha256"]
        and sha256(ROOT / item["path"]) == item["expected_sha256"]
        for item in source_manifest["r05_binding"].values()
    )
    add_check(
        checks,
        "binding:r05_artifacts_unchanged",
        r05_binding_ok and len(source_manifest["r05_binding"]) == 8,
        f"artifacts={len(source_manifest['r05_binding'])}",
    )
    reuse = config["dependency_reuse"]
    reuse_ok = True
    for key in ("suitesparse", "trilinos"):
        actual = digest_tree(Path(reuse[key]["install_prefix"]))
        persisted = source_manifest["reused_dependencies"][key]
        reuse_ok = reuse_ok and all(actual.get(field) == reuse[key].get(field) for field in actual)
        reuse_ok = reuse_ok and persisted["actual"] == actual
    add_check(
        checks,
        "reuse:dependency_tree_hashes",
        reuse_ok and reuse["dependency_rebuild_permitted"] is False,
        "R05 SuiteSparse and Trilinos trees remain byte-identical",
    )
    xyce_binary = Path(report["xyce_binary"]["path"])
    add_check(
        checks,
        "binary:hash_size_version_license",
        xyce_binary.is_file()
        and sha256(xyce_binary) == report["xyce_binary"]["sha256"]
        and xyce_binary.stat().st_size == report["xyce_binary"]["bytes"]
        and "7.10" in source_manifest["binary"]["version_output"]
        and source_manifest["binary"]["license_output_sha256"] is not None,
        f"sha256={report['xyce_binary']['sha256']} bytes={report['xyce_binary']['bytes']}",
    )
    build_manifest = load_json(build_manifest_path)
    commands = build_manifest.get("commands", [])
    command_names = [item.get("name") for item in commands]
    add_check(
        checks,
        "build:serial_and_no_dependency_rebuild",
        build_manifest.get("serial_build") is True
        and build_manifest.get("fortran_enabled") is False
        and build_manifest.get("mpi_enabled") is False
        and build_manifest.get("parallel_jobs") == 2
        and build_manifest.get("dependency_rebuild_permitted") is False,
        "serial two-job source build reused immutable dependencies",
    )
    required_commands = {
        "m4_configure",
        "m4_build",
        "m4_install",
        "bison_configure",
        "bison_build",
        "bison_install",
        "flex_configure",
        "flex_build",
        "flex_install",
        "generator_probe_m4",
        "generator_probe_bison",
        "generator_probe_flex",
        "generator_bison_smoke",
        "generator_flex_smoke",
        "xyce_configure",
        "xyce_build_install",
        "xyce_version",
        "xyce_license",
        "xyce_bsource_self_test_command",
        "xyce_device_syntax_command",
    }
    add_check(
        checks,
        "build:required_commands_passed",
        required_commands.issubset(command_names)
        and all(
            item.get("returncode") == 0 and item.get("timed_out") is False
            for item in commands
            if item.get("name") in required_commands
        ),
        f"required={len(required_commands.intersection(command_names))}/{len(required_commands)}",
    )
    configure_text = "\n".join(
        " ".join(item.get("argv", []))
        for item in commands
        if item.get("name") in {"m4_configure", "bison_configure", "flex_configure", "xyce_configure"}
    )
    add_check(
        checks,
        "build:registered_options_and_reused_prefixes",
        "--disable-dependency-tracking" in configure_text
        and "-DTrilinos_ENABLE_Fortran=OFF" in configure_text
        and "-DTPL_ENABLE_MPI=OFF" in configure_text
        and config["toolchain"]["bison"] in configure_text
        and config["toolchain"]["flex"] in configure_text
        and reuse["suitesparse"]["install_prefix"] in configure_text
        and reuse["trilinos"]["install_prefix"] in configure_text
        and not any(
            name.startswith("suitesparse_") or name.startswith("trilinos_")
            for name in command_names
            if isinstance(name, str)
        ),
        "R07 configures only generators and Xyce against reused dependency prefixes",
    )
    tools = config["toolchain"]
    add_check(
        checks,
        "generator:versions_and_data_paths",
        "m4 (GNU M4) 1.4.19" in source_manifest["tool_probes"]["m4"]
        and "bison (GNU Bison) 3.8.2" in source_manifest["tool_probes"]["bison"]
        and "flex 2.6.4" in source_manifest["tool_probes"]["flex"]
        and (Path(tools["bison_pkgdatadir"]) / "m4sugar" / "m4sugar.m4").is_file()
        and (Path(tools["bison_pkgdatadir"]) / "skeletons" / "yacc.c").is_file()
        and (Path(tools["flex_include_dir"]) / "FlexLexer.h").is_file(),
        "source-built generators and runtime data are present",
    )
    bison_input = ROOT / outputs["generator_bison_input"]
    bison_output = ROOT / outputs["generator_bison_output"]
    flex_input = ROOT / outputs["generator_flex_input"]
    flex_output = ROOT / outputs["generator_flex_output"]
    smoke = source_manifest["generator_smoke"]
    add_check(
        checks,
        "generator:persisted_generation_smoke",
        all(path.is_file() and path.stat().st_size > 0 for path in (bison_input, bison_output, flex_input, flex_output))
        and sha256(bison_input) == smoke["bison_input_sha256"]
        and sha256(bison_output) == smoke["bison_output_sha256"]
        and sha256(flex_input) == smoke["flex_input_sha256"]
        and sha256(flex_output) == smoke["flex_output_sha256"],
        "minimal Bison and Flex inputs and generated C sources match",
    )
    invoked_programs = [
        Path(item["argv"][0]).name.lower() for item in commands if item.get("argv")
    ]
    syntax_commands = [
        item for item in commands if item.get("name") == "xyce_device_syntax_command"
    ]
    add_check(
        checks,
        "execution:no_disqualified_or_formal_route",
        "ngspice" not in invoked_programs
        and "aimspice" not in invoked_programs
        and len(syntax_commands) == 1
        and "-syntax" in syntax_commands[0]["argv"]
        and not any(
            item.get("name", "").startswith(("suitesparse_", "trilinos_"))
            for item in commands
        ),
        "only generator tools, Xyce tool probes, scalar self-test and parser-only syntax ran",
    )
    self_test_netlist = ROOT / outputs["bsource_self_test_netlist"]
    self_test_text = (
        self_test_netlist.read_text(encoding="ascii") if self_test_netlist.is_file() else ""
    )
    add_check(
        checks,
        "self_test:netlist_scope",
        self_test_netlist.is_file()
        and "Btest" in self_test_text
        and ".DC" in self_test_text
        and all(
            token.lower() not in self_test_text.lower()
            for token in config["self_test"]["forbidden_tokens"]
        ),
        "controlled scalar B-source netlist contains no project-device token",
    )
    self_test_output = ROOT / outputs["bsource_self_test_output"]
    observed_v = read_xyce_csv(self_test_output, "V(NOUT)")
    expected_v = float(config["self_test"]["expected_value_v"])
    tolerance_v = float(config["self_test"]["tolerance_v"])
    add_check(
        checks,
        "self_test:persisted_value",
        observed_v is not None and abs(observed_v - expected_v) <= tolerance_v,
        f"observed={observed_v} expected={expected_v} tolerance={tolerance_v}",
    )
    add_check(
        checks,
        "self_test:registered_log_and_output",
        (ROOT / outputs["bsource_self_test_log"]).is_file()
        and self_test_output.is_file()
        and report.get("observed_self_test_value_v") == observed_v,
        "Xyce log, CSV and runner observation are consistent",
    )
    device_netlist = ROOT / outputs["device_syntax_netlist"]
    device_text = device_netlist.read_text(encoding="ascii") if device_netlist.is_file() else ""
    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    add_check(
        checks,
        "device_syntax:frozen_candidate_and_scope",
        device_netlist.is_file()
        and candidate.is_file()
        and sha256(candidate) == config["device_syntax_check"]["candidate_sha256"]
        and str(candidate) in device_text
        and "IGZO_DG_BEHAVIORAL_R02" in device_text
        and ".TRAN" not in device_text.upper()
        and all(
            token.lower() not in device_text.lower()
            for token in config["device_syntax_check"]["forbidden_tokens"]
        ),
        "parser input binds the frozen IGZO candidate only",
    )
    add_check(
        checks,
        "device_syntax:log_without_numerical_output",
        (ROOT / outputs["device_syntax_log"]).is_file()
        and not (ROOT / outputs["device_syntax_output"]).exists(),
        "-syntax log exists and no DC CSV was created",
    )
    formal_paths = [
        ROOT / value for value in config["formal_outputs_that_must_remain_absent"]
    ]
    add_check(
        checks,
        "outputs:formal_m01_outputs_absent",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    preflight_log_text = (
        preflight_log.read_text(encoding="utf-8") if preflight_log.is_file() else ""
    )
    add_check(
        checks,
        "boundary:raw_log_records_no_formal_execution",
        "formal_device_dc_invoked=false" in preflight_log_text
        and "formal_m01_numerical_run=false" in preflight_log_text
        and "ngspice_invoked=false" in preflight_log_text
        and "aimspice_invoked=false" in preflight_log_text
        and "r05_suitesparse_trilinos_reused=true" in preflight_log_text
        and "r05_partial_xyce_reused=false" in preflight_log_text
        and "r06_xyce_or_outputs_reused=false" in preflight_log_text,
        "raw preflight log retains the execution and reuse boundary",
    )
    add_check(
        checks,
        "boundary:no_physical_calibration_or_circuit_claim",
        all(
            phrase in report.get("evidence_boundary", "")
            for phrase in (
                "not a device simulation result",
                "physical parameter",
                "experimental calibration",
                "circuit result",
            )
        ),
        "tool preflight remains separate from device and circuit evidence",
    )
    add_check(
        checks,
        "gate:formal_m01_requires_independent_pass",
        config["no_execution_rules"][
            "formal_m01_run_requires_this_preflight_report_and_independent_check"
        ]
        is True
        and report.get("next_gate", "").startswith(
            "Run the R07 independent persisted-evidence check exactly once"
        ),
        report.get("next_gate", ""),
    )
    r05_report_path = ROOT / config["r05_failure_binding"]["preflight_report_path"]
    add_check(
        checks,
        "history:r05_failure_and_partial_build_remain_separate",
        r05_report_path.is_file()
        and sha256(r05_report_path)
        == config["r05_failure_binding"]["preflight_report_sha256"]
        and build_manifest["xyce_install_prefix"]
        != "/home/reachgao/.local/xyce-7.10-pure-r05"
        and build_manifest["build_directories"]["xyce_build"]
        != "/home/reachgao/.local/build/xyce-7.10.0-r05"
        and build_manifest["xyce_install_prefix"]
        != "/home/reachgao/.local/xyce-7.10-pure-r06"
        and build_manifest["build_directories"]["xyce_build"]
        != "/home/reachgao/.local/build/xyce-7.10.0-r06",
        "R05/R06 failures are immutable and R07 Xyce uses new roots",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"R07 independent registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "check_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E3",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "simulation_status": "NOT_RUN_BY_INDEPENDENT_CHECK",
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "simulator_processes_invoked": 0,
            "formal_device_dc_invoked": False,
            "formal_m01_outputs_created": False,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {
            "path": str(Path(__file__).relative_to(ROOT)),
            "sha256": sha256(Path(__file__)),
        },
        "runner_report": {
            "path": str(REPORT_PATH.relative_to(ROOT)),
            "sha256": sha256(REPORT_PATH),
        },
        "xyce_binary": report["xyce_binary"],
        "observed_self_test_value_v": observed_v,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": "Establish the formal two-open-source-route M01 device-only DC execution contract; do not run it until that contract is committed."
        if not failures
        else "Stop M01 and retain the failed R07 independent check without altering the registered gate.",
    }
    with CHECK_REPORT_PATH.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_R07_CHECK_{result['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={CHECK_REPORT_PATH}"
    )
    return result


if __name__ == "__main__":
    result = check_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
