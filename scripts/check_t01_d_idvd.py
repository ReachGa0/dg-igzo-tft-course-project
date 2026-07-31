#!/usr/bin/env python3
"""Independently validate persisted T01-D-B Id-Vd artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t01_d_idvd.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def close_metric(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1.0e-11, abs_tol=1.0e-15)


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def stage_by_id(baseline: dict[str, Any], stage_id: str) -> dict[str, Any]:
    return next(stage for stage in baseline["bias_protocol"]["stages"] if stage["id"] == stage_id)


def curves(config: dict[str, Any]) -> list[tuple[str, str, float]]:
    return [
        *[
            ("production", config["mesh"]["production_level"], float(value))
            for value in config["acceptance"]["required_production_vgs_values_v"]
        ],
        *[
            ("reference", config["mesh"]["reference_level"], float(value))
            for value in config["acceptance"]["required_reference_vgs_values_v"]
        ],
    ]


def curve_rows(rows: list[dict[str, str]], mesh_level: str, vgs_v: float) -> list[dict[str, str]]:
    return sorted(
        [
            row for row in rows
            if row["mesh_level"] == mesh_level and same_value(float(row["vgs_v"]), vgs_v)
        ],
        key=lambda row: float(row["vds_v"]),
    )


def point(
    rows: list[dict[str, str]], mesh_level: str, vgs_v: float, vds_v: float
) -> dict[str, str]:
    return next(
        row for row in rows
        if row["mesh_level"] == mesh_level
        and same_value(float(row["vgs_v"]), vgs_v)
        and same_value(float(row["vds_v"]), vds_v)
    )


def check_artifacts() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    baseline_path = ROOT / config["input_contract"]["path"]
    contract_report_path = ROOT / config["input_contract"]["report"]
    da_config_path = ROOT / config["dependency"]["mesh_config"]
    da_report_path = ROOT / config["dependency"]["mesh_report"]
    baseline = load_json(baseline_path)
    contract_report = load_json(contract_report_path)
    da_config = load_json(da_config_path)
    da_report = load_json(da_report_path)
    outputs = config["outputs"]
    report = load_json(ROOT / outputs["report"])
    snapshot = load_json(ROOT / outputs["config_snapshot"])
    solver_log = load_json(ROOT / outputs["solver_log"])
    bias_rows = load_csv(ROOT / outputs["bias_csv"])
    metric_rows = load_csv(ROOT / outputs["curve_metrics_csv"])
    mesh_rows = load_csv(ROOT / outputs["mesh_summary_csv"])
    comparison_rows = load_csv(ROOT / outputs["mesh_comparison_csv"])
    reproduction_rows = load_csv(ROOT / outputs["t01_da_reproduction_csv"])
    acceptance = config["acceptance"]
    expected_curves = curves(config)
    expected_vds = [float(value) for value in acceptance["required_vds_values_v"]]
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T01-D-B"
        and report.get("evidence_level") == "E2"
        and report.get("baseline_case_id") == baseline["case_id"]
        and report.get("t01_da_case_id") == da_report["case_id"],
        f"status={report.get('status')} stage={report.get('stage')}",
    )
    reproduction = report.get("reproduction", {})
    add_check(
        checks,
        "scope:authorized_stage_and_reproduction",
        report.get("executed_bias_stage_ids") == ["T01_A_STAGE_0", "T01_A_STAGE_3"]
        and report.get("reported_bias_stage_id") == "T01_A_STAGE_3"
        and config["scope"]["changed_variable"]
        == "drain bias at each frozen positive VGS output-curve point"
        and any("T01-D-C" in item for item in config["scope"]["prohibited_work"])
        and reproduction.get("command") == "make t01-d-idvd"
        and reproduction.get("validation_command") == "make t01-d-idvd-check"
        and bool(reproduction.get("python_executable"))
        and bool(reproduction.get("devsim_version")),
        str(report.get("executed_bias_stage_ids")),
    )
    add_check(
        checks,
        "inputs:hash_locked",
        snapshot.get("idvd_config_sha256") == sha256(CONFIG_PATH)
        and snapshot.get("baseline_config_sha256") == sha256(baseline_path)
        and snapshot.get("t01_a_contract_report_sha256") == sha256(contract_report_path)
        and snapshot.get("mesh_config_sha256") == sha256(da_config_path)
        and snapshot.get("mesh_report_sha256") == sha256(da_report_path),
        str(report.get("input_snapshot")),
    )
    dependency = config["dependency"]
    da_gate = da_report.get("mesh_convergence", {})
    add_check(
        checks,
        "dependencies:stage_gates",
        contract_report.get("contract_status") == config["input_contract"]["required_contract_status"]
        and da_report.get("case_id") == da_config.get("case_id")
        and da_report.get("stage") == dependency["required_stage"]
        and da_report.get("status") == dependency["required_status"]
        and da_gate.get("status") == dependency["required_mesh_convergence_status"]
        and da_gate.get("idvd_stage_permitted_next") is True,
        f"T01-A={contract_report.get('contract_status')} T01-D-A={da_report.get('status')}",
    )

    stage3 = stage_by_id(baseline, "T01_A_STAGE_3")
    levels = {row["id"]: float(row["refinement_factor"]) for row in da_config["mesh_ladder"]["levels"]}
    required_meshes = list(acceptance["required_mesh_levels"])
    mesh_contract_valid = (
        stage3.get("name") == "output_curve_points"
        and [float(value) for value in stage3["vgs_values_v"]]
        == [float(value) for value in acceptance["required_production_vgs_values_v"]]
        and [float(value) for value in stage3["vds_values_v"]] == expected_vds
        and required_meshes == [config["mesh"]["production_level"], config["mesh"]["reference_level"]]
        and levels.get(required_meshes[0]) == 4.0
        and levels.get(required_meshes[1]) == 8.0
    )
    add_check(
        checks,
        "contract:frozen_stage3_and_da_meshes",
        mesh_contract_valid,
        f"VGS={stage3.get('vgs_values_v')} VDS={stage3.get('vds_values_v')} meshes={required_meshes}",
    )

    expected_curve_keys = [(role, level, vgs_v) for role, level, vgs_v in expected_curves]
    actual_curve_keys = [
        (run.get("mesh_role"), run.get("mesh_level"), float(run.get("vgs_v")))
        for run in solver_log.get("curve_runs", [])
    ]
    record_counts = [len(run.get("solver_records", [])) for run in solver_log.get("curve_runs", [])]
    expected_record_counts = [
        2
        + len([
            value for value in config["bias_protocol"]["gate_preconditioning_ladder_v"]
            if float(value) <= vgs_v + 1.0e-12
        ])
        + len(expected_vds)
        for _, _, vgs_v in expected_curves
    ]
    records = [
        record for run in solver_log.get("curve_runs", []) for record in run.get("solver_records", [])
    ]
    add_check(
        checks,
        "solver:fresh_curve_runs_and_convergence",
        actual_curve_keys == expected_curve_keys
        and record_counts == expected_record_counts
        and sum(record_counts) == int(acceptance["required_total_dc_solve_count"])
        and all(run.get("status") == "PASS" for run in solver_log.get("curve_runs", []))
        and not solver_log.get("errors")
        and all(record.get("converged") is True for record in records),
        f"curves={len(actual_curve_keys)} records={sum(record_counts)} counts={record_counts}",
    )

    grid_valid = len(bias_rows) == int(acceptance["required_total_reported_bias_points"])
    for role, level, vgs_v in expected_curves:
        rows = curve_rows(bias_rows, level, vgs_v)
        grid_valid = grid_valid and len(rows) == len(expected_vds)
        grid_valid = grid_valid and [float(row["vds_v"]) for row in rows] == expected_vds
        grid_valid = grid_valid and all(
            row["mesh_role"] == role and row["stage_id"] == "T01_A_STAGE_3" for row in rows
        )
    add_check(
        checks,
        "bias:configured_grid",
        grid_valid,
        f"curves={len(expected_curves)} rows={len(bias_rows)} VDS={expected_vds}",
    )

    zero_rows = [row for row in bias_rows if same_value(float(row["vds_v"]), 0.0)]
    max_zero = max(
        max(abs(float(row["source_current_a_per_cm"])), abs(float(row["drain_current_a_per_cm"])))
        for row in zero_rows
    )
    nonzero_rows = [row for row in bias_rows if float(row["vds_v"]) > 0.0]
    floor = float(acceptance["minimum_nonzero_vds_abs_drain_current_a_per_cm"])
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in nonzero_rows)
    numerical_current_valid = (
        len(zero_rows) == len(expected_curves)
        and max_zero <= float(acceptance["maximum_zero_vds_abs_terminal_current_a_per_cm"])
        and all(
            math.isfinite(float(row["drain_current_a_per_cm"]))
            and float(row["drain_current_a_per_cm"]) >= floor
            and float(row["source_current_a_per_cm"]) <= -floor
            for row in nonzero_rows
        )
        and max_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"])
    )
    add_check(
        checks,
        "current:zero_resolved_directional_and_conserved",
        numerical_current_valid,
        f"max_zero={max_zero:.6e} nonzero={len(nonzero_rows)} max_imbalance={max_imbalance:.6e}",
    )

    drop_limit = float(acceptance["maximum_monotonic_relative_current_drop"])
    maximum_drop = 0.0
    curve_order_valid = True
    for _, level, vgs_v in expected_curves:
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve_rows(bias_rows, level, vgs_v)]
        for lower, higher in zip(currents, currents[1:]):
            drop = max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
            maximum_drop = max(maximum_drop, drop)
            curve_order_valid = curve_order_valid and drop <= drop_limit
    gate_limit = float(acceptance["maximum_gate_order_relative_current_drop"])
    maximum_gate_drop = 0.0
    production = config["mesh"]["production_level"]
    production_vgs = [float(value) for value in acceptance["required_production_vgs_values_v"]]
    for vds_v in expected_vds[1:]:
        currents = [
            abs(float(point(bias_rows, production, vgs_v, vds_v)["drain_current_a_per_cm"]))
            for vgs_v in production_vgs
        ]
        for lower, higher in zip(currents, currents[1:]):
            drop = max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
            maximum_gate_drop = max(maximum_gate_drop, drop)
            curve_order_valid = curve_order_valid and drop <= gate_limit
    add_check(
        checks,
        "trend:idvd_and_gate_order",
        curve_order_valid,
        f"curve_drop={maximum_drop:.6e} gate_drop={maximum_gate_drop:.6e}",
    )

    metrics_valid = len(metric_rows) == len(expected_curves)
    minimum_segment = float("inf")
    for metric, (role, level, vgs_v) in zip(metric_rows, expected_curves, strict=True):
        rows = curve_rows(bias_rows, level, vgs_v)
        voltages = [float(row["vds_v"]) for row in rows]
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
        segments = [
            (higher_i - lower_i) / (higher_v - lower_v)
            for lower_v, higher_v, lower_i, higher_i in zip(
                voltages, voltages[1:], currents, currents[1:]
            )
        ]
        minimum_segment = min(minimum_segment, min(segments))
        metrics_valid = metrics_valid and metric["mesh_role"] == role and metric["mesh_level"] == level
        metrics_valid = metrics_valid and same_value(float(metric["vgs_v"]), vgs_v)
        metrics_valid = metrics_valid and int(metric["point_count"]) == len(expected_vds)
        metrics_valid = metrics_valid and close_metric(
            float(metric["zero_vds_abs_drain_current_a_per_cm"]), currents[0]
        )
        metrics_valid = metrics_valid and close_metric(
            float(metric["endpoint_abs_drain_current_a_per_cm"]), currents[-1]
        )
        metrics_valid = metrics_valid and close_metric(
            float(metric["low_field_segment_conductance_s_per_cm"]), segments[0]
        )
        metrics_valid = metrics_valid and close_metric(
            float(metric["high_field_segment_conductance_s_per_cm"]), segments[-1]
        )
        metrics_valid = metrics_valid and close_metric(
            float(metric["minimum_segment_conductance_s_per_cm"]), min(segments)
        )
        metrics_valid = metrics_valid and metric["monotonic_nondecreasing"] == "True"
    add_check(
        checks,
        "metrics:independently_recomputed",
        metrics_valid and minimum_segment >= 0.0,
        f"metrics={len(metric_rows)} minimum_segment={minimum_segment:.6e} S/cm",
    )

    expected_comparisons = len(acceptance["required_reference_vgs_values_v"]) * len(expected_vds)
    comparison_valid = len(comparison_rows) == expected_comparisons
    max_reference_current = 0.0
    max_reference_potential = 0.0
    reference_mesh = config["mesh"]["reference_level"]
    for row in comparison_rows:
        vgs_v = float(row["vgs_v"])
        vds_v = float(row["vds_v"])
        lower = point(bias_rows, production, vgs_v, vds_v)
        higher = point(bias_rows, reference_mesh, vgs_v, vds_v)
        lower_current = abs(float(lower["drain_current_a_per_cm"]))
        higher_current = abs(float(higher["drain_current_a_per_cm"]))
        relative = abs(lower_current - higher_current) / max(lower_current, higher_current, 1.0e-300)
        potential = abs(
            float(lower["center_channel_potential_v"])
            - float(higher["center_channel_potential_v"])
        )
        if vds_v > 0.0:
            max_reference_current = max(max_reference_current, relative)
        max_reference_potential = max(max_reference_potential, potential)
        comparison_valid = comparison_valid and close_metric(
            float(row["relative_current_difference"]), relative
        ) and close_metric(float(row["center_channel_potential_difference_v"]), potential)
    comparison_valid = comparison_valid and (
        max_reference_current <= float(acceptance["maximum_reference_relative_current_difference"])
        and max_reference_potential
        <= float(acceptance["maximum_reference_center_potential_difference_v"])
    )
    add_check(
        checks,
        "mesh:selected_reference_comparison_recomputed",
        comparison_valid,
        f"rows={len(comparison_rows)} max_current={max_reference_current:.6e} max_potential={max_reference_potential:.6e}",
    )

    da_valid = len(reproduction_rows) == 4
    max_da_current = 0.0
    max_da_potential = 0.0
    for row in reproduction_rows:
        level = row["mesh_level"]
        vgs_v = float(row["vgs_v"])
        da_point = next(
            item for item in da_report["bias_points"]
            if item["mesh_level"] == level
            and same_value(float(item["vgs_v"]), vgs_v)
            and same_value(float(item["vds_v"]), 0.01)
        )
        db_point = point(bias_rows, level, vgs_v, 0.01)
        da_current = abs(float(da_point["drain_current_a_per_cm"]))
        db_current = abs(float(db_point["drain_current_a_per_cm"]))
        relative = abs(da_current - db_current) / max(da_current, db_current, 1.0e-300)
        potential = abs(
            float(da_point["center_channel_potential_v"])
            - float(db_point["center_channel_potential_v"])
        )
        max_da_current = max(max_da_current, relative)
        max_da_potential = max(max_da_potential, potential)
        da_valid = da_valid and close_metric(float(row["relative_current_difference"]), relative)
        da_valid = da_valid and close_metric(
            float(row["center_channel_potential_difference_v"]), potential
        )
    da_valid = da_valid and (
        max_da_current <= float(acceptance["maximum_t01_da_anchor_relative_current_difference"])
        and max_da_potential <= float(acceptance["maximum_t01_da_anchor_potential_difference_v"])
    )
    add_check(
        checks,
        "regression:t01_da_anchors_recomputed",
        da_valid,
        f"rows={len(reproduction_rows)} max_current={max_da_current:.6e} max_potential={max_da_potential:.6e}",
    )

    expected_mesh_rows = [
        ("production", config["mesh"]["production_level"], 4.0, 4, 41, 20),
        ("reference", config["mesh"]["reference_level"], 8.0, 2, 24, 10),
    ]
    mesh_summary_valid = len(mesh_rows) == 2 and all(
        row["mesh_role"] == role
        and row["mesh_level"] == level
        and same_value(float(row["refinement_factor"]), factor)
        and int(row["curve_count"]) == curve_count
        and int(row["dc_solve_count"]) == solve_count
        and int(row["reported_bias_point_count"]) == point_count
        for row, (role, level, factor, curve_count, solve_count, point_count) in zip(
            mesh_rows, expected_mesh_rows, strict=True
        )
    )
    add_check(
        checks,
        "mesh:summary_counts",
        mesh_summary_valid,
        f"rows={len(mesh_rows)} nodes={[row.get('node_count_with_interface_duplicates') for row in mesh_rows]}",
    )

    report_bias = report.get("bias_points", [])
    report_metric = report.get("curve_metrics", [])
    persisted_match = len(report_bias) == len(bias_rows) and len(report_metric) == len(metric_rows)
    for json_row, csv_row in zip(report_bias, bias_rows):
        persisted_match = persisted_match and json_row["mesh_role"] == csv_row["mesh_role"]
        persisted_match = persisted_match and json_row["mesh_level"] == csv_row["mesh_level"]
        persisted_match = persisted_match and close_metric(
            float(json_row["drain_current_a_per_cm"]), float(csv_row["drain_current_a_per_cm"])
        )
    add_check(
        checks,
        "outputs:json_csv_consistency",
        persisted_match,
        f"report_bias={len(report_bias)} csv_bias={len(bias_rows)}",
    )

    figure = report.get("figure", {})
    figure_path = ROOT / outputs["figure_png"]
    output_paths = [
        ROOT / value for key, value in report.get("outputs", {}).items() if key != "run_directory"
    ]
    add_check(
        checks,
        "outputs:raw_tables_and_figure",
        all(path.is_file() and path.stat().st_size > 0 for path in output_paths)
        and (ROOT / outputs["run_directory"]).is_dir()
        and figure.get("path") == outputs["figure_png"]
        and figure.get("sha256") == sha256(figure_path),
        f"files={len(output_paths)} figure_bytes={figure_path.stat().st_size if figure_path.exists() else 0}",
    )
    completion = report.get("idvd_completion", {})
    runner_checks = report.get("checks", {})
    add_check(
        checks,
        "runner:acceptance_and_next_gate",
        bool(runner_checks)
        and all(result.get("status") == "PASS" for result in runner_checks.values())
        and completion.get("status") == "PASS"
        and completion.get("sampled_bias_point_count")
        == int(acceptance["required_total_reported_bias_points"])
        and completion.get("continuous_curve_validation_permitted") is False
        and completion.get("experimental_quantitative_use_permitted") is False
        and completion.get("t01_dc_stage_permitted_next") is True,
        f"runner_checks={len(runner_checks)} next={completion.get('t01_dc_stage_permitted_next')}",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "checks": checks,
        "failures": failures,
        "recomputed_maximum_zero_vds_abs_terminal_current_a_per_cm": max_zero,
        "recomputed_maximum_relative_terminal_current_imbalance": max_imbalance,
        "recomputed_maximum_curve_relative_current_drop": maximum_drop,
        "recomputed_maximum_gate_order_relative_current_drop": maximum_gate_drop,
        "recomputed_minimum_segment_conductance_s_per_cm": minimum_segment,
        "recomputed_maximum_reference_relative_current_difference": max_reference_current,
        "recomputed_maximum_reference_center_potential_difference_v": max_reference_potential,
        "recomputed_maximum_t01_da_anchor_relative_current_difference": max_da_current,
        "recomputed_maximum_t01_da_anchor_potential_difference_v": max_da_potential,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(CONFIG_PATH)
    check_report_path = ROOT / config["outputs"]["check_report"]
    try:
        report = check_artifacts()
    except Exception as error:  # noqa: BLE001
        print(f"T01_D_IDVD_CHECK_ERROR {error}", file=sys.stderr)
        return 1
    if not args.check_only:
        check_report_path.parent.mkdir(parents=True, exist_ok=True)
        check_report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    label = "PASS" if report["status"] == "PASS" else "FAIL"
    print(
        f"T01_D_IDVD_CHECK_{label} checks={len(report['checks'])} report={check_report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T01_D_IDVD_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
