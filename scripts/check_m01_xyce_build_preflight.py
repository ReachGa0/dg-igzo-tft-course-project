#!/usr/bin/env python3
"""Independently check persisted M01 Xyce build/preflight evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r01.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight.py"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_r01.json"
CHECK_REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_check_r01.json"
EXPECTED_CHECK_COUNT = 20
EXPECTED_RUNNER_CHECK_COUNT = 29


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
        raise RuntimeError(f"Refusing to overwrite existing independent report: {CHECK_REPORT_PATH}")
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
    add_check(
        checks,
        "result:tool_only_boundary",
        report.get("formal_device_simulation_status") == "NOT_RUN_BY_PREFLIGHT"
        and report.get("formal_spice_numerical_status") == "NOT_RUN_BY_PREFLIGHT"
        and report.get("circuit_status") == "NOT_RUN_BY_PREFLIGHT"
        and report.get("summary", {}).get("ngspice_invoked") is False
        and report.get("summary", {}).get("aimspice_invoked") is False
        and report.get("summary", {}).get("formal_device_dc_invoked") is False
        and report.get("summary", {}).get("formal_m01_outputs_created") is False,
        "preflight is build, scalar self-test and parser-only syntax evidence",
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
    source_hashes_ok = all(
        item.get("match") is True
        and Path(item["path"]).is_file()
        and sha256(Path(item["path"])) == item["expected_sha256"] == item["actual_sha256"]
        for item in source_manifest["archives"].values()
    )
    add_check(
        checks,
        "sources:all_archives_rehashed",
        source_hashes_ok and len(source_manifest["archives"]) == 4,
        f"archives={len(source_manifest['archives'])}",
    )
    add_check(
        checks,
        "sources:extracted_key_files_rehashed",
        all(
            Path(item["path"]).is_dir()
            and (Path(item["path"]) / item["key_file"]).is_file()
            and sha256(Path(item["path"]) / item["key_file"]) == item["key_file_sha256"]
            for item in source_manifest["sources"].values()
        ),
        "Xyce, Trilinos and SuiteSparse source key files match",
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
        "build:serial_fortran_off_mpi_off",
        build_manifest.get("serial_build") is True
        and build_manifest.get("fortran_enabled") is False
        and build_manifest.get("mpi_enabled") is False
        and build_manifest.get("parallel_jobs") == 2,
        "serial two-job source build is persisted",
    )
    required_commands = {
        "suitesparse_configure",
        "suitesparse_build_install",
        "trilinos_configure",
        "trilinos_build_install",
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
        if item.get("name") in {"trilinos_configure", "xyce_configure"}
    )
    add_check(
        checks,
        "build:registered_options_preserved",
        "-DTrilinos_ENABLE_Fortran=OFF" in configure_text
        and "-DTPL_ENABLE_MPI=OFF" in configure_text
        and config["build_plan"]["trilinos_initial_cache"] in configure_text
        and config["toolchain"]["bison"] in configure_text
        and config["toolchain"]["flex"] in configure_text,
        "Fortran-off, MPI-off, official cache and parser tools are in persisted argv",
    )
    invoked_programs = [Path(item["argv"][0]).name.lower() for item in commands if item.get("argv")]
    syntax_commands = [item for item in commands if item.get("name") == "xyce_device_syntax_command"]
    add_check(
        checks,
        "execution:no_disqualified_or_formal_route",
        "ngspice" not in invoked_programs
        and "aimspice" not in invoked_programs
        and len(syntax_commands) == 1
        and "-syntax" in syntax_commands[0]["argv"],
        "only Xyce scalar self-test and parser-only device syntax were invoked",
    )
    self_test_netlist = ROOT / outputs["bsource_self_test_netlist"]
    self_test_text = self_test_netlist.read_text(encoding="ascii") if self_test_netlist.is_file() else ""
    add_check(
        checks,
        "self_test:netlist_scope",
        self_test_netlist.is_file()
        and "Btest" in self_test_text
        and ".DC" in self_test_text
        and all(token.lower() not in self_test_text.lower() for token in config["self_test"]["forbidden_tokens"]),
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
    formal_paths = [ROOT / value for value in config["formal_outputs_that_must_remain_absent"]]
    add_check(
        checks,
        "outputs:formal_m01_outputs_absent",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    preflight_log_text = preflight_log.read_text(encoding="utf-8") if preflight_log.is_file() else ""
    add_check(
        checks,
        "boundary:raw_log_records_no_formal_execution",
        "formal_device_dc_invoked=false" in preflight_log_text
        and "formal_m01_numerical_run=false" in preflight_log_text
        and "ngspice_invoked=false" in preflight_log_text
        and "aimspice_invoked=false" in preflight_log_text,
        "raw preflight log retains the execution boundary",
    )
    add_check(
        checks,
        "boundary:no_physical_calibration_or_circuit_claim",
        all(
            phrase in report.get("evidence_boundary", "")
            for phrase in ("not a device simulation result", "physical parameter", "experimental calibration", "circuit result")
        ),
        "tool preflight remains separate from device and circuit evidence",
    )
    add_check(
        checks,
        "gate:formal_m01_requires_independent_pass",
        config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True
        and report.get("next_gate", "").startswith("After this preflight"),
        report.get("next_gate", ""),
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"Independent check registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
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
        "checker": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256(Path(__file__))},
        "runner_report": {"path": str(REPORT_PATH.relative_to(ROOT)), "sha256": sha256(REPORT_PATH)},
        "xyce_binary": report["xyce_binary"],
        "observed_self_test_value_v": observed_v,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"] if not failures else "Stop M01 and retain the failed independent check without altering the registered threshold.",
    }
    with CHECK_REPORT_PATH.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_CHECK_{result['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={CHECK_REPORT_PATH}"
    )
    return result


if __name__ == "__main__":
    result = check_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
