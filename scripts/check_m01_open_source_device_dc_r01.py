#!/usr/bin/env python3
"""Independently recompute persisted M01 R01 two-route device DC evidence."""

from __future__ import annotations

import math
import struct
from pathlib import Path
from typing import Any

from m01_open_source_device_dc_r01_common import (
    DIFFERENCE_FIELDS,
    METRIC_FIELDS,
    RAW_FIELDS,
    compute_metrics,
    compute_route_differences,
    extract_route_rows,
    generate_device_netlist,
    load_csv,
    load_json,
    parse_ngspice_ascii_raw,
    parse_xyce_prn,
    sha256,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_open_source_device_dc_r01.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_open_source_device_dc_r01.py"
RUN_REPORT_PATH = ROOT / "results" / "reports" / "m01_open_source_cross_check_r01.json"
CHECK_REPORT_PATH = ROOT / "results" / "reports" / "m01_open_source_cross_check_r01_check.json"
EXPECTED_CHECK_COUNT = 24


def add_check(
    checks: list[dict[str, str]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def csv_matches(
    actual: list[dict[str, str]], expected: list[dict[str, Any]], fields: list[str]
) -> bool:
    if len(actual) != len(expected):
        return False
    return all(
        actual_row.get(field, "") == str(expected_row.get(field, ""))
        for actual_row, expected_row in zip(actual, expected)
        for field in fields
    )


def png_dimensions(path: Path) -> tuple[int, int] | None:
    if not path.is_file():
        return None
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def check() -> int:
    if CHECK_REPORT_PATH.exists():
        raise RuntimeError(f"independent checker refuses to overwrite {CHECK_REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    machine = experiment_map["M01"]["open_source_device_dc_r01"]
    report = load_json(RUN_REPORT_PATH)
    outputs = config["outputs"]
    checks: list[dict[str, str]] = []
    runner_checks = report.get("checks", [])

    add_check(
        checks,
        "result:runner_passed_30_of_30",
        report.get("status") == "PASS"
        and report.get("evidence_level") == "E2"
        and len(runner_checks) == 30
        and all(item.get("status") == "PASS" for item in runner_checks)
        and report.get("summary", {}).get("passed") == 30
        and report.get("summary", {}).get("failed") == 0,
        f"passed={report.get('summary', {}).get('passed')}/{len(runner_checks)} machine={machine.get('status')}",
    )
    add_check(
        checks,
        "identity:config_and_runner_hashes",
        report.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and report.get("runner", {}).get("sha256") == sha256(RUNNER_PATH)
        and report.get("contract_id") == config["contract_id"],
        f"contract={report.get('contract_id')}",
    )
    contract_report_path = ROOT / outputs["contract_report"]
    contract_report = load_json(contract_report_path)
    add_check(
        checks,
        "binding:static_contract_pass",
        contract_report.get("status") == "PASS"
        and contract_report.get("evidence_level") == "E3"
        and contract_report.get("summary", {}).get("passed") == 40
        and contract_report.get("summary", {}).get("failed") == 0
        and report.get("contract_report", {}).get("sha256") == sha256(contract_report_path),
        f"static={contract_report.get('summary', {}).get('passed')}/40",
    )
    binding = config["committed_preflight_binding"]
    bound_paths = [
        (binding["r11_config_path"], binding["r11_config_sha256"]),
        (binding["r11_contract_report_path"], binding["r11_contract_report_sha256"]),
        (binding["r11_runner_report_path"], binding["r11_runner_report_sha256"]),
        (binding["r11_independent_report_path"], binding["r11_independent_report_sha256"]),
    ]
    r11_check = load_json(ROOT / binding["r11_independent_report_path"])
    add_check(
        checks,
        "binding:r11_preflight_unchanged",
        all((ROOT / path).is_file() and sha256(ROOT / path) == expected for path, expected in bound_paths)
        and r11_check.get("status") == "PASS"
        and r11_check.get("summary", {}).get("passed") == 25
        and r11_check.get("processes_invoked") == 0,
        f"bound={len(bound_paths)}",
    )
    commands = report.get("commands", [])
    expected_ng = [
        config["routes"]["ngspice"]["tool_path"],
        "-b",
        "-o",
        outputs["ngspice_log"],
        outputs["ngspice_netlist"],
    ]
    expected_xy = [
        config["routes"]["xyce"]["tool_path"],
        "-l",
        outputs["xyce_log"],
        "-o",
        "results/compact/m01_open_source_cross_check_r01/xyce_values",
        outputs["xyce_netlist"],
    ]
    add_check(
        checks,
        "execution:two_exact_commands",
        len(commands) == 2
        and commands[0].get("route") == "ngspice"
        and commands[0].get("argv") == expected_ng
        and commands[0].get("returncode") == 0
        and commands[1].get("route") == "xyce"
        and commands[1].get("argv") == expected_xy
        and commands[1].get("returncode") == 0,
        f"commands={len(commands)}",
    )
    summary = report.get("summary", {})
    committed_runner_pass = (
        machine.get("status") == "formal_run_passed"
        and machine.get("current_evidence") == "E2"
        and machine.get("formal_run_completed") is True
        and machine.get("formal_run_status") == "PASS"
        and machine.get("runner_checks_passed") == 30
        and machine.get("runner_checks_failed") == 0
        and machine.get("runner_processes_invoked") == 2
        and machine.get("independent_check_completed") is False
        and project.get("tcad_track", {}).get("next_scope", "").startswith(
            "run the 24-check independent persisted-evidence checker for M01 open-source device DC R01"
        )
    )
    add_check(
        checks,
        "execution:process_and_scope_audit",
        summary.get("process_invocations") == 2
        and summary.get("formal_device_dc_invoked") is True
        and summary.get("ngspice_invoked") is True
        and summary.get("xyce_invoked") is True
        and summary.get("aimspice_invoked") is False
        and summary.get("tcad_invoked") is False
        and summary.get("circuit_or_downstream_invoked") is False
        and committed_runner_pass,
        (
            f"processes={summary.get('process_invocations')} "
            f"machine={machine.get('status')}"
        ),
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
    target = config["target_contract"]
    manifest_path = ROOT / target["selection_manifest"]
    prediction_path = ROOT / target["prediction_table"]
    manifest_rows, _ = load_csv(manifest_path)
    prediction_rows, _ = load_csv(prediction_path)
    prediction_by_uid = {row["row_uid"]: row for row in prediction_rows}
    add_check(
        checks,
        "targets:hashes_counts_and_order",
        sha256(manifest_path) == target["selection_manifest_sha256"]
        and sha256(prediction_path) == target["prediction_table_sha256"]
        and len(manifest_rows) == len(prediction_rows) == 247
        and len({row["row_uid"] for row in manifest_rows}) == len(manifest_rows)
        and len(prediction_by_uid) == len(prediction_rows)
        and {row["row_uid"] for row in manifest_rows} == set(prediction_by_uid)
        and all(
            row[field] == prediction_by_uid[row["row_uid"]][field]
            for row in manifest_rows
            for field in (
                "curve_id", "dataset_id", "split", "kind", "topology",
                "selection_role", "optimizer_input", "vbg_v", "vtg_v",
                "vds_v", "primary_axis_v", "target_current_a_per_cm",
                "w_um", "l_um", "temperature_k",
            )
        )
        and all(
            math.isfinite(float(row["model_current_a_per_cm"]))
            for row in prediction_rows
        )
        and len({row["curve_id"] for row in manifest_rows}) == 13,
        f"rows={len(manifest_rows)} prediction_uid_map={len(prediction_by_uid)}",
    )
    candidate_path = ROOT / config["device_contract"]["candidate_path"]
    add_check(
        checks,
        "candidate:igzo_hash_and_scope",
        sha256(candidate_path) == config["device_contract"]["candidate_sha256"]
        and candidate_path.read_text(encoding="ascii").count(".subckt IGZO_DG_BEHAVIORAL_R02") == 1
        and config["device_contract"]["same_candidate_bytes_for_both_routes"] is True
        and config["device_contract"]["equation_identity_claimed"] is False,
        sha256(candidate_path),
    )
    include_line = config["netlist_contract"]["candidate_include"]
    expected_ng_text = generate_device_netlist(manifest_rows, "ngspice", include_line, config["routes"]["ngspice"]["raw_output"])
    expected_xy_text = generate_device_netlist(manifest_rows, "xyce", include_line, config["routes"]["xyce"]["raw_output"])
    ng_netlist_path = ROOT / outputs["ngspice_netlist"]
    xy_netlist_path = ROOT / outputs["xyce_netlist"]
    actual_ng_text = ng_netlist_path.read_text(encoding="ascii")
    actual_xy_text = xy_netlist_path.read_text(encoding="ascii")
    add_check(
        checks,
        "netlists:exact_deterministic_regeneration",
        actual_ng_text == expected_ng_text and actual_xy_text == expected_xy_text,
        f"sha256={sha256(ng_netlist_path)}/{sha256(xy_netlist_path)}",
    )
    forbidden = [token.lower() for token in config["netlist_contract"]["forbidden_case_insensitive_tokens"]]
    add_check(
        checks,
        "netlists:device_dc_scope",
        actual_ng_text.count("XDEV") == actual_xy_text.count("XDEV") == 247
        and actual_ng_text.count(".DC VSWEEP 0 0 1") == 1
        and actual_xy_text.count(".DC VSWEEP 0 0 1") == 1
        and all(token not in actual_ng_text.lower() and token not in actual_xy_text.lower() for token in forbidden),
        "247 IGZO devices per route",
    )
    ng_raw_path = ROOT / outputs["ngspice_raw_output"]
    xy_raw_path = ROOT / outputs["xyce_raw_output"]
    artifacts = report.get("artifacts", {})
    add_check(
        checks,
        "raw:simulator_artifacts_hash_bound",
        ng_raw_path.is_file()
        and xy_raw_path.is_file()
        and artifacts.get("ngspice_raw_output_sha256") == sha256(ng_raw_path)
        and artifacts.get("xyce_raw_output_sha256") == sha256(xy_raw_path),
        f"bytes={ng_raw_path.stat().st_size}/{xy_raw_path.stat().st_size}",
    )
    ng_currents = parse_ngspice_ascii_raw(ng_raw_path)
    xy_currents = parse_xyce_prn(xy_raw_path)
    expected_ng_rows = extract_route_rows(manifest_rows, prediction_rows, "ngspice", ng_currents)
    expected_xy_rows = extract_route_rows(manifest_rows, prediction_rows, "xyce", xy_currents)
    add_check(
        checks,
        "raw:independent_parser_cardinality",
        len(expected_ng_rows) == len(expected_xy_rows) == 247
        and all(row["finite_current"] is True for row in expected_ng_rows + expected_xy_rows),
        f"rows={len(expected_ng_rows)}/{len(expected_xy_rows)}",
    )
    ng_csv_rows, ng_fields = load_csv(ROOT / outputs["ngspice_raw_csv"])
    xy_csv_rows, xy_fields = load_csv(ROOT / outputs["xyce_raw_csv"])
    add_check(
        checks,
        "tables:raw_schema_and_counts",
        ng_fields == xy_fields == RAW_FIELDS and len(ng_csv_rows) == len(xy_csv_rows) == 247,
        f"fields={len(ng_fields)} rows={len(ng_csv_rows)}/{len(xy_csv_rows)}",
    )
    add_check(
        checks,
        "tables:raw_exact_recomputation",
        csv_matches(ng_csv_rows, expected_ng_rows, RAW_FIELDS)
        and csv_matches(xy_csv_rows, expected_xy_rows, RAW_FIELDS),
        "both route tables reproduce raw simulator files",
    )
    zero_limit = float(config["extraction_contract"]["zero_vds_max_current_a_per_cm"])
    zero_rows = [row for row in expected_ng_rows + expected_xy_rows if float(row["vds_v"]) == 0.0]
    max_zero = max(float(row["current_a_per_cm"]) for row in zero_rows)
    add_check(
        checks,
        "extraction:zero_vds_invariants",
        len(zero_rows) == 14 and max_zero <= zero_limit,
        f"rows={len(zero_rows)} max={max_zero:.17g}",
    )
    floor = float(config["extraction_contract"]["current_floor_a_per_cm"])
    expected_metrics = compute_metrics(expected_ng_rows, floor) + compute_metrics(expected_xy_rows, floor)
    metric_rows, metric_fields = load_csv(ROOT / outputs["route_metrics_csv"])
    add_check(
        checks,
        "metrics:schema_and_count",
        metric_fields == METRIC_FIELDS and len(metric_rows) == 30,
        f"fields={len(metric_fields)} rows={len(metric_rows)}",
    )
    add_check(
        checks,
        "metrics:exact_recomputation",
        csv_matches(metric_rows, expected_metrics, METRIC_FIELDS),
        "26 curve and four equal-curve aggregate rows",
    )
    expected_differences = compute_route_differences(expected_ng_rows, expected_xy_rows, floor)
    difference_rows, difference_fields = load_csv(ROOT / outputs["route_difference_csv"])
    add_check(
        checks,
        "differences:schema_and_count",
        difference_fields == DIFFERENCE_FIELDS and len(difference_rows) == 247,
        f"fields={len(difference_fields)} rows={len(difference_rows)}",
    )
    add_check(
        checks,
        "differences:exact_recomputation",
        csv_matches(difference_rows, expected_differences, DIFFERENCE_FIELDS),
        "all route differences reproduce",
    )
    add_check(
        checks,
        "diagnostics:finite_and_not_a_tuned_gate",
        all(
            math.isfinite(float(row[field]))
            for row in metric_rows
            for field in ("linear_nrmse", "log_rmse_dec", "max_abs_model_error_a_per_cm", "max_log_model_error_dec")
        )
        and all(math.isfinite(float(row["log_difference_dec"])) for row in difference_rows)
        and config["extraction_contract"]["route_to_target_thresholds_are_diagnostic_only"] is True
        and config["extraction_contract"]["route_difference_threshold_is_not_a_pass_gate"] is True,
        "finite diagnostics retained without post-run tuning",
    )
    overlay_path = ROOT / outputs["overlay_png"]
    difference_png_path = ROOT / outputs["route_difference_png"]
    overlay_dimensions = png_dimensions(overlay_path)
    difference_dimensions = png_dimensions(difference_png_path)
    add_check(
        checks,
        "figures:png_hashes_and_dimensions",
        overlay_dimensions is not None
        and difference_dimensions is not None
        and min(overlay_dimensions) >= 1000
        and min(difference_dimensions) >= 1000
        and artifacts.get("overlay_png_sha256") == sha256(overlay_path)
        and artifacts.get("route_difference_png_sha256") == sha256(difference_png_path),
        f"dimensions={overlay_dimensions}/{difference_dimensions}",
    )
    artifact_keys = [
        "ngspice_netlist", "xyce_netlist", "ngspice_log", "xyce_log",
        "ngspice_command_log", "xyce_command_log", "ngspice_raw_output",
        "xyce_raw_output", "ngspice_raw_csv", "xyce_raw_csv",
        "route_metrics_csv", "route_difference_csv", "overlay_png",
        "route_difference_png",
    ]
    add_check(
        checks,
        "artifacts:all_runner_hashes_recomputed",
        len(artifacts) == len(artifact_keys)
        and all(
            (ROOT / outputs[key]).is_file()
            and artifacts.get(f"{key}_sha256") == sha256(ROOT / outputs[key])
            for key in artifact_keys
        ),
        f"hashes={len(artifacts)}/{len(artifact_keys)}",
    )
    add_check(
        checks,
        "boundary:no_downstream_or_overclaim",
        report.get("failure_category") is None
        and report.get("failure_detail") is None
        and config["scope"]["circuit_or_transient_permitted"] is False
        and config["scope"]["layout_or_pex_permitted"] is False
        and config["scope"]["hzo_or_sno_permitted"] is False
        and config["scope"]["experimental_calibration_claim_permitted"] is False
        and "C00 and downstream remain closed" in report.get("next_gate", ""),
        "device-only numerical evidence; no calibration/circuit/layout claim",
    )
    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"independent registry mismatch expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    passed = sum(item["status"] == "PASS" for item in checks)
    status = "PASS" if passed == EXPECTED_CHECK_COUNT else "FAIL"
    payload = {
        "schema_version": "1.0",
        "project_id": config["project_id"],
        "stage_id": "M01",
        "contract_id": config["contract_id"],
        "status": status,
        "evidence_level": "E3" if status == "PASS" else "E0",
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "runner_report": {"path": str(RUN_REPORT_PATH.relative_to(ROOT)), "sha256": sha256(RUN_REPORT_PATH)},
        "summary": {"passed": passed, "failed": EXPECTED_CHECK_COUNT - passed, "total": EXPECTED_CHECK_COUNT},
        "processes_invoked": 0,
        "checks": checks,
        "evidence_boundary": "E3 independently establishes persisted-evidence integrity for the two device-only open-source routes. It does not establish equation identity, physical parameters, experimental calibration, external validation, circuit readiness, layout, PEX or HZO evidence.",
        "next_gate": "Commit and push this E3 state before deciding whether M01 closes within the declared teaching-model boundary and whether C00 may open.",
    }
    write_json(CHECK_REPORT_PATH, payload)
    print(
        f"M01_OPEN_SOURCE_DEVICE_DC_R01_CHECK_{status} checks={passed}/{EXPECTED_CHECK_COUNT} "
        f"report={CHECK_REPORT_PATH}"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(check())
