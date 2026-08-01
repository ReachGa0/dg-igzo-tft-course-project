#!/usr/bin/env python3
"""Independently validate persisted T03-P4-L channel-length evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import statistics
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p4_channel_length.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_value(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def close(
    left: float, right: float, *, rel_tol: float = 1.0e-10,
    abs_tol: float = 1.0e-15,
) -> bool:
    return math.isclose(
        float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol
    )


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append({
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    })


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T03-P4-L primary grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def curve_for_length(
    rows: list[dict[str, str]], length_um: float
) -> list[dict[str, str]]:
    return sorted(
        [
            row for row in rows
            if same_value(float(row["channel_length_um"]), length_um)
        ],
        key=lambda row: float(row["vtg_v"]),
    )


def interpolate(xs: list[float], ys: list[float], target: float) -> float:
    for x_value, y_value in zip(xs, ys):
        if same_value(x_value, target):
            return y_value
    index = next(
        index for index in range(len(xs) - 1)
        if xs[index] < target < xs[index + 1]
    )
    return ys[index] + (
        (target - xs[index]) * (ys[index + 1] - ys[index])
        / (xs[index + 1] - xs[index])
    )


def regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    variance = sum((value - mean_x) ** 2 for value in xs)
    slope = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys)
    ) / variance
    intercept = mean_y - slope * mean_x
    residual = sum(
        (y_value - (slope * x_value + intercept)) ** 2
        for x_value, y_value in zip(xs, ys)
    )
    total = sum((value - mean_y) ** 2 for value in ys)
    return slope, intercept, 1.0 if total == 0.0 else 1.0 - residual / total


def relative_spread(values: list[float]) -> float:
    return (max(values) - min(values)) / max(
        max(abs(value) for value in values), 1.0e-300
    )


def extract_metric(
    baseline: dict[str, Any], config: dict[str, Any], length_um: float,
    rows: list[dict[str, str]],
) -> dict[str, float]:
    width_cm = float(baseline["device"]["width_cm"])
    length_cm = length_um * 1.0e-4
    prefactor = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "criterion_prefactor_a"
        ]
    )
    terminal_criterion = prefactor * width_cm / length_cm
    criterion = terminal_criterion / width_cm
    voltages = [float(row["vtg_v"]) for row in rows]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
    bracket = next(
        index for index in range(len(currents) - 1)
        if currents[index] <= criterion <= currents[index + 1]
    )
    lower_current = currents[bracket]
    upper_current = currents[bracket + 1]
    lower_voltage = voltages[bracket]
    upper_voltage = voltages[bracket + 1]
    vth = lower_voltage + (
        (math.log10(criterion) - math.log10(lower_current))
        * (upper_voltage - lower_voltage)
        / (math.log10(upper_current) - math.log10(lower_current))
    )
    gm_voltages = voltages[1:-1]
    gm_values = [
        (currents[index + 1] - currents[index - 1])
        / (voltages[index + 1] - voltages[index - 1])
        for index in range(1, len(rows) - 1)
    ]
    gm_voltage = vth + float(
        config["extraction_methods"]["gm_proxy"]["evaluation_overdrive_v"]
    )
    gm = interpolate(gm_voltages, gm_values, gm_voltage)
    peak_index = max(range(len(gm_values)), key=lambda index: gm_values[index])
    on_voltage = float(
        config["extraction_methods"]["on_state_current_proxy"][
            "primary_gate_v"
        ]
    )
    on_row = next(
        row for row in rows if same_value(float(row["vtg_v"]), on_voltage)
    )
    on_current = abs(float(on_row["drain_current_a_per_cm"]))
    return {
        "channel_length_cm": length_cm,
        "constant_current_criterion_terminal_a": terminal_criterion,
        "constant_current_criterion_a_per_cm": criterion,
        "vth_proxy_v": vth,
        "vth_bracket_lower_primary_gate_v": lower_voltage,
        "vth_bracket_upper_primary_gate_v": upper_voltage,
        "vth_bracket_lower_current_a_per_cm": lower_current,
        "vth_bracket_upper_current_a_per_cm": upper_current,
        "gm_evaluation_primary_gate_v": gm_voltage,
        "gm_proxy_s_per_cm": gm,
        "gm_proxy_terminal_s": gm * width_cm,
        "maximum_sampled_gm_s_per_cm": gm_values[peak_index],
        "maximum_sampled_gm_primary_gate_v": gm_voltages[peak_index],
        "on_state_primary_gate_v": on_voltage,
        "on_state_current_proxy_a_per_cm": on_current,
        "on_state_current_proxy_terminal_a": on_current * width_cm,
        "current_length_product_a": on_current * length_cm,
        "gm_length_product_s": gm * length_cm,
    }


def report_csv_rows_match(
    report_rows: list[dict[str, Any]], csv_rows: list[dict[str, str]],
    text_fields: set[str],
) -> bool:
    if len(report_rows) != len(csv_rows):
        return False
    for report_row, csv_row in zip(report_rows, csv_rows):
        for field, csv_value in csv_row.items():
            if field in text_fields:
                if str(report_row[field]) != csv_value:
                    return False
            elif field == "converged":
                if bool(report_row[field]) is not (csv_value.lower() == "true"):
                    return False
            elif not close(
                float(report_row[field]), float(csv_value), rel_tol=1.0e-12,
                abs_tol=1.0e-300,
            ):
                return False
    return True


def png_dimensions(path: Path) -> tuple[int, int]:
    data = path.read_bytes()[:24]
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        raise ValueError(f"not a PNG file: {path}")
    return struct.unpack(">II", data[16:24])


def nearest_channel_state(
    rows: list[dict[str, str]], baseline: dict[str, Any], length_cm: float
) -> dict[str, float]:
    target_x = length_cm / 2.0
    target_y = float(baseline["geometry"]["bottom_oxide_thickness_cm"]) + (
        float(baseline["geometry"]["channel_thickness_cm"]) / 2.0
    )
    channel_rows = [row for row in rows if row["region"] == "channel"]
    nearest = min(
        channel_rows,
        key=lambda row: (float(row["x_cm"]) - target_x) ** 2
        + (float(row["y_cm"]) - target_y) ** 2,
    )
    return {
        "potential_v": float(nearest["potential_v"]),
        "electron_density_cm3": float(nearest["electron_density_cm3"]),
    }


def archived_v1_valid(config: dict[str, Any]) -> tuple[bool, str]:
    remediation = config["remediation"]
    prior_config_path = ROOT / remediation["prior_config"]
    prior_contract_path = ROOT / remediation["prior_contract_report"]
    prior_report_path = ROOT / remediation["prior_run_report"]
    prior_run_dir = ROOT / remediation["prior_run_directory"]
    prior_config = load_json(prior_config_path)
    prior_contract = load_json(prior_contract_path)
    prior_report = load_json(prior_report_path)
    prior_snapshot = load_json(prior_run_dir / "input_snapshot.json")
    valid = all([
        prior_config.get("case_id") == remediation["prior_case_id"],
        prior_contract.get("contract_status") == "PASS",
        prior_contract.get("config", {}).get("sha256") == sha256(prior_config_path),
        prior_snapshot.get("inputs", {}).get("t03_config", {}).get("sha256")
        == sha256(prior_config_path),
        prior_report.get("status") == "FAIL",
        prior_report.get("failures") == remediation["prior_failed_checks"],
    ])
    table_paths = {
        "curve_csv": ROOT / "results/tables/tcad_t03_p4_l_transfer_curves_v1_failed.csv",
        "metric_csv": ROOT / "results/tables/tcad_t03_p4_l_metrics_v1_failed.csv",
        "reference_comparison_csv": ROOT / "results/tables/tcad_t03_p4_l_t02_c_reproduction_v1_failed.csv",
        "state_summary_csv": ROOT / "results/tables/tcad_t03_p4_l_state_summary_v1_failed.csv",
        "state_manifest": prior_run_dir / "state_manifest.json",
        "solver_log": prior_run_dir / "solver_log.json",
    }
    valid = valid and all(
        path.is_file()
        and prior_report["artifacts"][name]["sha256"] == sha256(path)
        for name, path in table_paths.items()
    )
    for entry in prior_report.get("state_outputs", []):
        node_path = prior_run_dir / Path(entry["node_csv"]).name
        element_path = prior_run_dir / Path(entry["element_csv"]).name
        valid = valid and all([
            node_path.is_file(),
            element_path.is_file(),
            entry["node_csv_sha256"] == sha256(node_path),
            entry["element_csv_sha256"] == sha256(element_path),
        ])
        for item in entry["vtk_files"]:
            vtk_path = prior_run_dir / Path(item["path"]).name
            valid = valid and vtk_path.is_file() and item["sha256"] == sha256(vtk_path)
    prior_figures = [
        ROOT / "report/assets/tcad_t03_p4_l_sensitivity_v1_failed.png",
        ROOT / "report/assets/tcad_t03_p4_l_state_maps_v1_failed.png",
    ]
    valid = valid and all(
        path.is_file() and item["sha256"] == sha256(path)
        for item, path in zip(prior_report.get("figures", []), prior_figures)
    )
    return valid, (
        f"case={prior_report.get('case_id')} status={prior_report.get('status')} "
        f"failures={prior_report.get('failures')}"
    )


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report = load_json(ROOT / outputs["report"])
    contract = load_json(ROOT / outputs["contract_report"])
    snapshot = load_json(ROOT / outputs["config_snapshot"])
    solver_log = load_json(ROOT / outputs["solver_log"])
    state_manifest = load_json(ROOT / outputs["state_manifest"])
    baseline = load_json(ROOT / config["dependencies"]["t01_baseline_config"])
    t02_c_report = load_json(ROOT / config["dependencies"]["t02_c_report"])
    curve_rows, curve_fields = load_csv(ROOT / outputs["curve_csv"])
    metric_rows, metric_fields = load_csv(ROOT / outputs["metric_csv"])
    reference_rows, reference_fields = load_csv(
        ROOT / outputs["reference_comparison_csv"]
    )
    state_summary_rows, state_summary_fields = load_csv(
        ROOT / outputs["state_summary_csv"]
    )
    acceptance = config["acceptance"]
    lengths = [float(value) for value in config["sensitivity"]["values_um"]]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:v2_report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T03-P4-L"
        and report.get("parameter_group_id") == "P4"
        and report.get("evidence_level") == "E2",
        f"status={report.get('status')} case={report.get('case_id')}",
    )

    contract_checks = contract.get("checks", [])
    add_check(
        checks,
        "contract:static_gate_and_config_hash_match",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and len(contract_checks) == 25
        and all(item.get("status") == "PASS" for item in contract_checks)
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH),
        f"checks={len(contract_checks)} simulation={contract.get('simulation_status')}",
    )

    snapshot_valid = all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in snapshot.get("inputs", {}).values()
    )
    add_check(
        checks,
        "inputs:snapshot_hashes_match",
        snapshot.get("case_id") == config["case_id"]
        and snapshot_valid
        and snapshot["inputs"]["t03_config"]["sha256"] == sha256(CONFIG_PATH),
        f"inputs={len(snapshot.get('inputs', {}))}",
    )

    prior_valid, prior_detail = archived_v1_valid(config)
    add_check(
        checks,
        "remediation:v1_failed_evidence_is_complete_and_immutable",
        prior_valid,
        prior_detail,
    )

    runs = solver_log.get("runs", [])
    solve_counts = [len(run.get("solver_records", [])) for run in runs]
    solver_records = [
        record for run in runs for record in run.get("solver_records", [])
    ]
    add_check(
        checks,
        "solver:three_fresh_devices_and_123_dc_solves_converged",
        [float(run["channel_length_um"]) for run in runs] == lengths
        and solve_counts == [41, 41, 41]
        and len(solver_records) == 123
        and all(run.get("status") == "PASS" for run in runs)
        and all(record.get("converged") is True for record in solver_records)
        and not solver_log.get("errors")
        and float(solver_log["wall_seconds"])
        <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"runs={len(runs)} solve_counts={solve_counts} records={len(solver_records)}",
    )

    summaries = report.get("topology_summaries", [])
    node_counts = [int(row["node_count_with_interface_duplicates"]) for row in summaries]
    element_counts = [int(row["element_count"]) for row in summaries]
    add_check(
        checks,
        "topology:one_variable_meshes_are_ordered_and_valid",
        [float(row["channel_length_um"]) for row in summaries] == lengths
        and all(
            row["regions"] == sorted(acceptance["required_regions"])
            and row["contacts"] == sorted(acceptance["required_contacts"])
            and row["interfaces"] == sorted(acceptance["required_interfaces"])
            and row["dc_solve_count"] == 41
            and row["reported_point_count"] == 31
            for row in summaries
        )
        and all(higher > lower for lower, higher in zip(node_counts, node_counts[1:]))
        and all(
            higher > lower for lower, higher in zip(element_counts, element_counts[1:])
        ),
        f"nodes={node_counts} elements={element_counts}",
    )

    grid = primary_grid(config)
    grids_valid = all(
        [float(row["vtg_v"]) for row in curve_for_length(curve_rows, length)]
        == grid
        for length in lengths
    )
    curve_text_fields = {
        "parameter_group_id", "changed_parameter", "mesh_level", "stage_id",
        "mode_id",
    }
    add_check(
        checks,
        "curves:93_persisted_points_match_report_and_grid",
        len(curve_fields) == 21
        and len(curve_rows) == 93
        and grids_valid
        and report_csv_rows_match(
            report["curve_points"], curve_rows, curve_text_fields
        ),
        f"rows={len(curve_rows)} fields={len(curve_fields)} grids={grids_valid}",
    )

    max_imbalance = max(
        float(row["relative_current_imbalance"]) for row in curve_rows
    )
    gate_monotonic = True
    max_drop = 0.0
    for length in lengths:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in curve_for_length(curve_rows, length)
        ]
        gate_monotonic = gate_monotonic and all(
            higher > lower for lower, higher in zip(currents, currents[1:])
        )
        max_drop = max(
            max_drop,
            max(
                max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
                for lower, higher in zip(currents, currents[1:])
            ),
        )
    add_check(
        checks,
        "current:direction_conservation_and_gate_order_recomputed",
        all(
            float(row["drain_current_a_per_cm"]) > 0.0
            and float(row["source_current_a_per_cm"]) < 0.0
            and math.isfinite(float(row["drain_current_a_per_cm"]))
            and row["converged"].lower() == "true"
            for row in curve_rows
        )
        and max_imbalance
        <= float(acceptance["maximum_relative_terminal_current_imbalance"])
        and gate_monotonic
        and max_drop <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"imbalance={max_imbalance:.6e} monotonic={gate_monotonic} drop={max_drop:.6e}",
    )

    recomputed = [
        extract_metric(
            baseline, config, length, curve_for_length(curve_rows, length)
        )
        for length in lengths
    ]
    length_cm = [row["channel_length_cm"] for row in recomputed]
    on_currents = [row["on_state_current_proxy_a_per_cm"] for row in recomputed]
    gm_values = [row["gm_proxy_s_per_cm"] for row in recomputed]
    slope, intercept, r_squared = regression(
        [math.log(value) for value in length_cm],
        [math.log(value) for value in on_currents],
    )
    shared = {
        "vth_range_v": max(row["vth_proxy_v"] for row in recomputed)
        - min(row["vth_proxy_v"] for row in recomputed),
        "current_length_product_relative_spread": relative_spread(
            [row["current_length_product_a"] for row in recomputed]
        ),
        "gm_length_product_relative_spread": relative_spread(
            [row["gm_length_product_s"] for row in recomputed]
        ),
        "log_current_vs_length_slope": slope,
        "log_current_vs_length_intercept": intercept,
        "log_current_vs_length_r_squared": r_squared,
    }
    metric_valid = len(metric_rows) == 3 and len(metric_fields) == 28
    for length, values in zip(lengths, recomputed):
        persisted = next(
            row for row in metric_rows
            if same_value(float(row["channel_length_um"]), length)
        )
        for key, value in {**values, **shared}.items():
            metric_valid = metric_valid and close(
                float(persisted[key]), value, rel_tol=1.0e-10,
                abs_tol=1.0e-300,
            )
        metric_valid = metric_valid and (
            persisted["parameter_claim_status"]
            == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
        )
    report_metric_match = report_csv_rows_match(
        report["sensitivity_metrics"],
        metric_rows,
        {"parameter_group_id", "changed_parameter", "parameter_claim_status"},
    )
    add_check(
        checks,
        "extraction:vth_gm_current_and_scaling_metrics_recomputed",
        metric_valid
        and report_metric_match
        and all(higher < lower for lower, higher in zip(on_currents, on_currents[1:]))
        and all(higher < lower for lower, higher in zip(gm_values, gm_values[1:])),
        f"VTH={[row['vth_proxy_v'] for row in recomputed]} I={on_currents} gm={gm_values}",
    )

    diagnostic_config = config["diagnostic_hypotheses"]["ideal_inverse_length"]
    diagnostic_checks = {
        "vth_range_within_2mv": shared["vth_range_v"]
        <= float(diagnostic_config["maximum_vth_range_v"]),
        "current_length_product_spread_within_2percent": shared[
            "current_length_product_relative_spread"
        ] <= float(
            diagnostic_config["maximum_current_length_product_relative_spread"]
        ),
        "gm_length_product_spread_within_2percent": shared[
            "gm_length_product_relative_spread"
        ] <= float(diagnostic_config["maximum_gm_length_product_relative_spread"]),
        "log_current_length_slope_near_minus_one": float(
            diagnostic_config["minimum_log_current_vs_length_slope"]
        ) <= slope <= float(
            diagnostic_config["maximum_log_current_vs_length_slope"]
        ) and r_squared >= float(
            diagnostic_config["minimum_log_current_vs_length_r_squared"]
        ),
    }
    saved_diagnostic = report["diagnostic_hypotheses"]["ideal_inverse_length"]
    add_check(
        checks,
        "diagnostic:ideal_inverse_length_remains_explicit_fail",
        not any(diagnostic_checks.values())
        and saved_diagnostic["status"] == "FAIL"
        and saved_diagnostic["completion_gate"] is False
        and saved_diagnostic["checks"] == diagnostic_checks
        and report["summary_metrics"]["diagnostic_hypotheses"][
            "ideal_inverse_length"
        ]["status"] == "FAIL",
        f"checks={diagnostic_checks} slope={slope:.9f} R2={r_squared:.9f}",
    )

    reference_curve = curve_for_length(curve_rows, 10.0)
    t02_curve = sorted(
        [
            row for row in t02_c_report["family_points"]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )
    reference_valid = len(reference_rows) == 31 and len(reference_fields) == 10
    max_reference_current = 0.0
    max_reference_potential = 0.0
    max_reference_density = 0.0
    for current_row, t02_row, persisted in zip(
        reference_curve, t02_curve, reference_rows
    ):
        current = abs(float(current_row["drain_current_a_per_cm"]))
        t02_current = abs(float(t02_row["drain_current_a_per_cm"]))
        current_difference = abs(current - t02_current) / max(
            current, t02_current, 1.0e-300
        )
        potential_difference = abs(
            float(current_row["center_channel_potential_v"])
            - float(t02_row["center_channel_potential_v"])
        )
        density = float(current_row["center_channel_electron_density_cm3"])
        t02_density = float(t02_row["center_channel_electron_density_cm3"])
        density_difference = abs(density - t02_density) / max(
            density, t02_density, 1.0e-300
        )
        max_reference_current = max(max_reference_current, current_difference)
        max_reference_potential = max(max_reference_potential, potential_difference)
        max_reference_density = max(max_reference_density, density_difference)
        expected = {
            "primary_gate_v": float(current_row["vtg_v"]),
            "t03_abs_drain_current_a_per_cm": current,
            "t02_c_abs_drain_current_a_per_cm": t02_current,
            "current_relative_difference": current_difference,
            "t03_center_channel_potential_v": float(
                current_row["center_channel_potential_v"]
            ),
            "t02_c_center_channel_potential_v": float(
                t02_row["center_channel_potential_v"]
            ),
            "center_channel_potential_difference_v": potential_difference,
            "t03_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": t02_density,
            "center_density_relative_difference": density_difference,
        }
        reference_valid = reference_valid and all(
            close(float(persisted[key]), value, rel_tol=1.0e-12, abs_tol=1.0e-300)
            for key, value in expected.items()
        )
    add_check(
        checks,
        "regression:t02_c_reference_curve_recomputed",
        reference_valid
        and max_reference_current
        <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and max_reference_potential
        <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and max_reference_density
        <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"])
        and report["t02_c_reference_reproduction"]["vth_difference_v"]
        <= float(acceptance["maximum_t02_c_reference_vth_difference_v"])
        and report["t02_c_reference_reproduction"]["gm_relative_difference"]
        <= float(acceptance["maximum_t02_c_reference_gm_relative_difference"]),
        f"current={max_reference_current:.3e} potential={max_reference_potential:.3e} density={max_reference_density:.3e}",
    )

    state_entries = state_manifest.get("entries", [])
    state_summary_by_id = {row["state_id"]: row for row in state_summary_rows}
    state_valid = (
        len(state_entries) == 3
        and len(state_summary_rows) == 3
        and len(state_summary_fields) == 28
        and report["state_outputs"] == state_entries
    )
    for entry in state_entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        node_rows, node_fields = load_csv(node_path)
        element_rows, element_fields = load_csv(element_path)
        length = float(entry["channel_length_um"])
        center = nearest_channel_state(
            node_rows, baseline, float(entry["channel_length_cm"])
        )
        bias_row = next(
            row for row in curve_for_length(curve_rows, length)
            if same_value(float(row["vtg_v"]), float(entry["vtg_v"]))
        )
        summary = state_summary_by_id[entry["state_id"]]
        state_valid = state_valid and all([
            len(node_fields) == 19,
            len(element_fields) == 38,
            len(node_rows) == int(entry["node_row_count"]),
            len(element_rows) == int(entry["channel_element_count"]),
            set(row["region"] for row in node_rows)
            == set(acceptance["required_regions"]),
            entry["node_csv_sha256"] == sha256(node_path),
            entry["element_csv_sha256"] == sha256(element_path),
            len(entry["vtk_files"]) == 6,
            int(entry["vtk_file_count"]) == 6,
            all(
                (ROOT / item["path"]).is_file()
                and item["sha256"] == sha256(ROOT / item["path"])
                for item in entry["vtk_files"]
            ),
            close(center["potential_v"], entry["center_channel_potential_v"]),
            close(
                center["electron_density_cm3"],
                entry["center_channel_electron_density_cm3"],
                abs_tol=1.0e-300,
            ),
            close(
                entry["absolute_drain_current_a_per_cm"],
                abs(float(bias_row["drain_current_a_per_cm"])),
            ),
            summary["node_csv"] == entry["node_csv"],
            summary["element_csv"] == entry["element_csv"],
        ])
        state_valid = state_valid and all(
            math.isfinite(float(row[field]))
            for row in element_rows
            for field in (
                "electron_current_density_x_a_per_cm2",
                "electron_current_density_y_a_per_cm2",
                "electron_current_density_magnitude_a_per_cm2",
            )
        )
    add_check(
        checks,
        "states:node_element_and_vtk_evidence_recomputed",
        state_valid
        and report_csv_rows_match(
            report["state_outputs"],
            state_summary_rows,
            {
                "state_id", "state_label", "parameter_group_id", "mesh_level",
                "stage_id", "node_csv", "element_csv",
            },
        ),
        f"states={[entry['state_id'] for entry in state_entries]}",
    )

    artifact_hashes_valid = all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in report["artifacts"].values()
    )
    figure_details: list[tuple[int, int, int]] = []
    figure_valid = len(report["figures"]) == 2
    for item in report["figures"]:
        path = ROOT / item["path"]
        width, height = png_dimensions(path)
        figure_details.append((width, height, path.stat().st_size))
        figure_valid = figure_valid and (
            item["sha256"] == sha256(path)
            and width >= 1000
            and height >= 600
            and path.stat().st_size > 0
        )
    add_check(
        checks,
        "outputs:artifact_hashes_and_png_dimensions_match",
        artifact_hashes_valid and figure_valid,
        f"artifacts={len(report['artifacts'])} figures={figure_details}",
    )

    runner_checks = report.get("checks", {})
    completion = report.get("t03_p4_l_completion", {})
    prohibited = " ".join(report["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks,
        "runner:one_group_gate_and_evidence_boundary_pass",
        len(runner_checks) == 16
        and all(item["status"] == "PASS" for item in runner_checks.values())
        and not report.get("failures")
        and completion.get("status") == "PASS"
        and completion.get("p4_channel_length_three_point_group_complete") is True
        and completion.get("complete_t03_five_group_sensitivity") is False
        and completion.get("another_t03_group_permitted_next") is True
        and completion.get("experimental_calibration_permitted") is False
        and completion.get("physical_short_channel_claim_permitted") is False
        and "scaling-law proof" in prohibited
        and "complete T03" in prohibited
        and "numerical proxies" in report["limitations"][0],
        f"runner_checks={len(runner_checks)} group_complete={completion.get('p4_channel_length_three_point_group_complete')}",
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    check_report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "checks": checks,
        "failures": failures,
        "recomputed_metrics": {
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_monotonic_relative_current_drop": max_drop,
            **shared,
            "on_state_current_proxy_a_per_cm": on_currents,
            "vth_proxy_v": [row["vth_proxy_v"] for row in recomputed],
            "gm_proxy_s_per_cm": gm_values,
            "ideal_inverse_length_diagnostic": {
                "status": "PASS" if all(diagnostic_checks.values()) else "FAIL",
                "completion_gate": False,
                "checks": diagnostic_checks,
            },
            "t02_c_reference": {
                "maximum_current_relative_difference": max_reference_current,
                "maximum_center_potential_difference_v": max_reference_potential,
                "maximum_center_density_relative_difference": max_reference_density,
            },
        },
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        json.dumps(check_report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T03_P4_L_SENSITIVITY_CHECK_{check_report['status']} "
        f"checks={len(checks)} report={check_path}"
    )
    for failure in failures:
        print(
            f"T03_P4_L_SENSITIVITY_CHECK_ERROR "
            f"{failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
