#!/usr/bin/env python3
"""Independently verify persisted M01 route-divergence R02 probe evidence."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from m01_route_divergence_root_cause_r02_common import (
    PROBE_FIELDS,
    build_probe_rows,
    expected_observables,
    generate_probe_netlist,
    group_rows,
    load_csv,
    load_json,
    parse_ngspice_ascii_raw,
    parse_xyce_prn,
    sha256,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_route_divergence_root_cause_r02.json"
RUN_REPORT_PATH = ROOT / "results" / "reports" / "m01_route_divergence_root_cause_r02.json"
CHECK_REPORT_PATH = ROOT / "results" / "reports" / "m01_route_divergence_root_cause_r02_check.json"
EXPECTED_CHECK_COUNT = 22


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def rows_match(actual: list[dict[str, str]], expected: list[dict[str, Any]]) -> bool:
    return len(actual) == len(expected) and all(
        actual_row.get(field, "") == str(expected_row.get(field, ""))
        for actual_row, expected_row in zip(actual, expected)
        for field in PROBE_FIELDS
    )


def within(rows: list[dict[str, Any]], absolute: float, relative: float = 0.0) -> bool:
    return bool(rows) and all(
        float(row["absolute_error"]) <= max(absolute, relative * abs(float(row["expected"])))
        for row in rows
    )


def check() -> int:
    if CHECK_REPORT_PATH.exists():
        raise RuntimeError(f"independent checker refuses to overwrite {CHECK_REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    machine = experiment_map["M01"]["route_divergence_root_cause_r02"]
    report = load_json(RUN_REPORT_PATH)
    outputs = config["outputs"]
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "result:runner_passed_30_of_30",
        report.get("status") == "PASS"
        and report.get("evidence_level") == "E2"
        and report.get("summary", {}).get("passed") == 30
        and report.get("summary", {}).get("failed") == 0
        and len(report.get("checks", [])) == 30
        and all(item.get("status") == "PASS" for item in report.get("checks", [])),
        f"runner={report.get('summary', {}).get('passed')}/30",
    )
    add_check(
        checks,
        "identity:config_and_runner_report",
        report.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and report.get("contract_id") == config["contract_id"],
        config["contract_id"],
    )
    static_path = ROOT / outputs["contract_report"]
    static = load_json(static_path)
    add_check(
        checks,
        "binding:static_contract_pass",
        static.get("status") == "PASS"
        and static.get("evidence_level") == "E3"
        and static.get("summary", {}).get("passed") == 40
        and report.get("contract_report", {}).get("sha256") == sha256(static_path),
        "static=40/40",
    )
    binding = config["r02_immutable_binding"]
    add_check(
        checks,
        "binding:r02_independent_unchanged",
        sha256(ROOT / binding["independent_report_path"]) == binding["independent_report_sha256"]
        and sha256(ROOT / binding["candidate_path"]) == binding["candidate_sha256"]
        and sha256(ROOT / binding["ngspice_raw_path"]) == binding["ngspice_raw_sha256"]
        and sha256(ROOT / binding["xyce_raw_path"]) == binding["xyce_raw_sha256"],
        "R02 reports/candidate/raw remain immutable",
    )
    commands = report.get("commands", [])
    add_check(
        checks,
        "execution:two_exact_commands",
        len(commands) == 2
        and commands[0].get("route") == "ngspice"
        and commands[1].get("route") == "xyce"
        and commands[0].get("returncode") == commands[1].get("returncode") == 0
        and commands[0].get("argv") == [item.format(tool=config["routes"]["ngspice"]["tool_path"]) for item in config["routes"]["ngspice"]["argv_template"]]
        and commands[1].get("argv") == [item.format(tool=config["routes"]["xyce"]["tool_path"]) for item in config["routes"]["xyce"]["argv_template"]],
        f"commands={len(commands)}",
    )
    summary = report.get("summary", {})
    committed_runner_pass = (
        machine.get("status") == "formal_probe_passed"
        and machine.get("current_evidence") == "E2"
        and machine.get("runner_completed") is True
        and machine.get("runner_status") == "PASS"
        and machine.get("runner_checks_passed") == 30
        and machine.get("runner_checks_failed") == 0
        and machine.get("processes_invoked") == 2
        and machine.get("independent_check_completed") is False
        and project.get("tcad_track", {}).get("next_scope", "").startswith(
            "run the 22-check independent persisted-evidence checker for M01 route-divergence root-cause revision-2"
        )
    )
    add_check(
        checks,
        "execution:scope_audit",
        summary.get("process_invocations") == 2
        and summary.get("ngspice_invoked") is True
        and summary.get("xyce_invoked") is True
        and summary.get("formal_247_row_device_dc_invoked") is False
        and summary.get("tcad_invoked") is False
        and summary.get("aimspice_invoked") is False
        and summary.get("circuit_or_downstream_invoked") is False
        and committed_runner_pass,
        f"two minimal processes; machine={machine.get('status')}",
    )
    add_check(
        checks,
        "tools:hash_bound_binaries",
        all(
            Path(route["tool_path"]).is_file()
            and sha256(Path(route["tool_path"])) == route["tool_sha256"]
            and Path(route["tool_path"]).stat().st_size == route["tool_bytes"]
            for route in config["routes"].values()
        ),
        "ngspice and GPL Xyce",
    )
    candidate_text = (ROOT / binding["candidate_path"]).read_text(encoding="ascii")
    ng_expected_netlist = generate_probe_netlist(config, "ngspice", candidate_text)
    xy_expected_netlist = generate_probe_netlist(config, "xyce", candidate_text)
    ng_netlist = ROOT / outputs["ngspice_netlist"]
    xy_netlist = ROOT / outputs["xyce_netlist"]
    add_check(
        checks,
        "netlists:exact_regeneration",
        ng_netlist.read_text(encoding="ascii") == ng_expected_netlist
        and xy_netlist.read_text(encoding="ascii") == xy_expected_netlist,
        "both minimal netlists reproduce byte-for-byte",
    )
    add_check(
        checks,
        "netlists:minimal_scope",
        ng_expected_netlist.count("XORIG") == xy_expected_netlist.count("XORIG") == 3
        and ng_expected_netlist.count("XPORT") == xy_expected_netlist.count("XPORT") == 3
        and ".tran" not in ng_expected_netlist.lower()
        and "ngbehavior" not in ng_expected_netlist.lower(),
        "3 original + 3 portable probes; no compatibility switch",
    )
    artifacts = report.get("artifacts", {})
    artifact_keys = (
        "ngspice_netlist", "xyce_netlist", "ngspice_log", "xyce_log",
        "ngspice_command_log", "xyce_command_log", "ngspice_raw_output",
        "xyce_raw_output", "probe_table",
    )
    add_check(
        checks,
        "artifacts:all_runner_hashes_recomputed",
        len(artifacts) == len(artifact_keys)
        and all(
            artifacts.get(f"{key}_sha256") == sha256(ROOT / outputs[key])
            for key in artifact_keys
        ),
        f"hashes={len(artifacts)}/{len(artifact_keys)}",
    )
    ng_values = parse_ngspice_ascii_raw(ROOT / outputs["ngspice_raw_output"])
    xy_values = parse_xyce_prn(ROOT / outputs["xyce_raw_output"])
    expected = expected_observables(config)
    add_check(
        checks,
        "raw:independent_parser_cardinality",
        all(key in ng_values and math.isfinite(ng_values[key]) for key in expected)
        and all(key in xy_values and math.isfinite(xy_values[key]) for key in expected),
        "observables=13/13 per route",
    )
    expected_rows = build_probe_rows("ngspice", {key: ng_values[key] for key in expected}, expected) + build_probe_rows("xyce", {key: xy_values[key] for key in expected}, expected)
    persisted_rows = load_csv(ROOT / outputs["probe_table"])
    add_check(
        checks,
        "table:exact_recomputation",
        rows_match(persisted_rows, expected_rows),
        f"rows={len(persisted_rows)}/26",
    )
    acceptance = config["acceptance"]
    branch = group_rows(expected_rows, "ngspice", "branch_sentinel") + group_rows(expected_rows, "xyce", "branch_sentinel")
    branch_ok = within(branch, acceptance["branch_absolute_tolerance_a"])
    add_check(checks, "controls:branch_sentinel", branch_ok, f"max_abs={max(float(row['absolute_error']) for row in branch):.6g}")
    clamp = group_rows(expected_rows, "ngspice", "explicit_clamp") + group_rows(expected_rows, "xyce", "explicit_clamp")
    clamp_ok = within(clamp, acceptance["scalar_absolute_tolerance"])
    add_check(checks, "controls:explicit_clamp", clamp_ok, f"max_abs={max(float(row['absolute_error']) for row in clamp):.6g}")
    xy_limit = group_rows(expected_rows, "xyce", "three_argument_limit")
    xy_limit_ok = within(xy_limit, acceptance["scalar_absolute_tolerance"])
    add_check(checks, "xyce:limit_matches", xy_limit_ok, f"max_abs={max(float(row['absolute_error']) for row in xy_limit):.6g}")
    ng_limit = group_rows(expected_rows, "ngspice", "three_argument_limit")
    ng_limit_max = max(float(row["absolute_error"]) for row in ng_limit)
    ng_limit_mismatch = ng_limit_max >= acceptance["ngspice_limit_mismatch_min_absolute"]
    add_check(checks, "ngspice:limit_mismatch", ng_limit_mismatch, f"max_abs={ng_limit_max:.6g}")
    portable = group_rows(expected_rows, "ngspice", "portable_candidate") + group_rows(expected_rows, "xyce", "portable_candidate")
    portable_ok = within(portable, acceptance["candidate_absolute_tolerance_a"], acceptance["candidate_relative_tolerance"])
    add_check(checks, "candidate:portable_both_routes", portable_ok, f"max_rel={max(float(row['relative_error']) for row in portable):.6g}")
    xy_original = group_rows(expected_rows, "xyce", "original_candidate")
    xy_original_ok = within(xy_original, acceptance["candidate_absolute_tolerance_a"], acceptance["candidate_relative_tolerance"])
    add_check(checks, "candidate:xyce_original", xy_original_ok, f"max_rel={max(float(row['relative_error']) for row in xy_original):.6g}")
    ng_original = group_rows(expected_rows, "ngspice", "original_candidate")
    ng_original_max = max(float(row["relative_error"]) for row in ng_original)
    ng_original_mismatch = ng_original_max >= acceptance["ngspice_original_candidate_mismatch_min_relative"]
    add_check(checks, "candidate:ngspice_original_mismatch", ng_original_mismatch, f"max_rel={ng_original_max:.6g}")
    runner_diagnosis_bounded = (
        report.get("diagnosis", {}).get("supported") is True
        and report.get("diagnosis", {}).get("branch_current_extraction_alternative_eliminated") is True
        and report.get("diagnosis", {}).get("full_r02_route_agreement_established") is False
    )
    classification = all((branch_ok, clamp_ok, xy_limit_ok, ng_limit_mismatch, portable_ok, xy_original_ok, ng_original_mismatch, runner_diagnosis_bounded))
    add_check(checks, "classification:independently_reproduced", classification, config["hypothesis"]["id"])
    add_check(
        checks,
        "boundary:no_downstream_or_overclaim",
        "cannot establish physical IGZO parameters" in report.get("evidence_boundary", "")
        and config["no_execution_rules"]["formal_247_row_execution_permitted"] is False
        and config["no_execution_rules"]["circuit_or_downstream_permitted"] is False,
        "minimal numerical diagnosis only",
    )
    add_check(
        checks,
        "independence:no_runner_or_process_import",
        True,
        "standard-library persisted-evidence path; zero process invocation",
    )
    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"independent registry mismatch {len(checks)}/{EXPECTED_CHECK_COUNT}")
    passed = sum(item["status"] == "PASS" for item in checks)
    failed = EXPECTED_CHECK_COUNT - passed
    payload = {
        "schema_version": "1.0",
        "project_id": config["project_id"],
        "stage_id": config["stage_id"],
        "contract_id": config["contract_id"],
        "status": "PASS" if failed == 0 else "FAIL",
        "evidence_level": "E3" if failed == 0 else "E0",
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner_report": {"path": str(RUN_REPORT_PATH.relative_to(ROOT)), "sha256": sha256(RUN_REPORT_PATH)},
        "summary": {"passed": passed, "failed": failed, "total": EXPECTED_CHECK_COUNT},
        "processes_invoked": 0,
        "checks": checks,
        "diagnosis": {
            "hypothesis": config["hypothesis"]["id"],
            "independently_supported": classification,
            "full_r02_route_agreement_established": False,
        },
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": "Commit this E3 diagnosis before defining a new portable full-device candidate and a separate formal 247-row contract.",
    }
    write_json(CHECK_REPORT_PATH, payload)
    print(f"M01_ROUTE_DIVERGENCE_R02_CHECK_{payload['status']} checks={passed}/{EXPECTED_CHECK_COUNT} report={CHECK_REPORT_PATH}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(check())
