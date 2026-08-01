#!/usr/bin/env python3
"""Independently validate persisted T03-P1-BIAS evidence."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p1_secondary_bias.json"


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
    left: float,
    right: float,
    *,
    rel_tol: float = 1.0e-10,
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
        raise ValueError("T03-P1-BIAS primary grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def curve_for_bias(
    rows: list[dict[str, Any]], secondary_v: float
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), secondary_v)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def interpolate(xs: list[float], ys: list[float], target: float) -> float:
    for x_value, y_value in zip(xs, ys):
        if same_value(x_value, target):
            return y_value
    index = next(
        index
        for index in range(len(xs) - 1)
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


def extract_metric(
    baseline: dict[str, Any],
    config: dict[str, Any],
    curve: list[dict[str, Any]],
) -> dict[str, float]:
    width_cm = float(baseline["device"]["width_cm"])
    length_cm = float(baseline["device"]["channel_length_cm"])
    method = config["extraction_methods"]["constant_current_vth_proxy"]
    terminal_criterion = float(method["criterion_prefactor_a"]) * (
        width_cm / length_cm
    )
    criterion = terminal_criterion / width_cm
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    bracket = next(
        index
        for index in range(len(currents) - 1)
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
        for index in range(1, len(curve) - 1)
    ]
    gm_voltage = vth + float(
        config["extraction_methods"]["gm_proxy"]["evaluation_overdrive_v"]
    )
    gm = interpolate(gm_voltages, gm_values, gm_voltage)
    peak_index = max(range(len(gm_values)), key=lambda index: gm_values[index])
    return {
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
    }


def report_csv_rows_match(
    report_rows: list[dict[str, Any]],
    csv_rows: list[dict[str, str]],
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
                float(report_row[field]),
                float(csv_value),
                rel_tol=1.0e-12,
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
    rows: list[dict[str, str]], baseline: dict[str, Any]
) -> dict[str, float]:
    target_x = float(baseline["geometry"]["channel_length_cm"]) / 2.0
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
    values = [float(value) for value in config["sensitivity"]["values_v"]]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:e2_bias_only_report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T03-P1-BIAS"
        and report.get("parameter_group_id") == "P1"
        and report.get("evidence_level") == "E2",
        f"status={report.get('status')} case={report.get('case_id')}",
    )

    contract_checks = contract.get("checks", [])
    add_check(
        checks,
        "contract:static_gate_and_config_hash_match",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and len(contract_checks) == 22
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
        and snapshot.get("stage") == config["stage"]
        and snapshot_valid
        and snapshot["inputs"]["t03_p1_config"]["sha256"] == sha256(CONFIG_PATH)
        and report.get("input_snapshot") == outputs["config_snapshot"],
        f"inputs={len(snapshot.get('inputs', {}))}",
    )

    runs = solver_log.get("runs", [])
    solve_counts = [len(run.get("solver_records", [])) for run in runs]
    solver_records = [
        record for run in runs for record in run.get("solver_records", [])
    ]
    add_check(
        checks,
        "solver:five_fresh_devices_and_217_dc_solves_converged",
        [float(run["fixed_secondary_gate_v"]) for run in runs] == values
        and solve_counts
        == config["resource_budget"][
            "required_dc_solve_counts_by_secondary_bias"
        ]
        and len(solver_records) == 217
        and all(run.get("status") == "PASS" for run in runs)
        and all(record.get("converged") is True for record in solver_records)
        and not solver_log.get("errors")
        and float(solver_log["wall_seconds"])
        <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"runs={len(runs)} solve_counts={solve_counts} records={len(solver_records)}",
    )

    summaries = report.get("family_summaries", [])
    topology_counts = [
        (
            int(row["node_count_with_interface_duplicates"]),
            int(row["element_count"]),
        )
        for row in summaries
    ]
    add_check(
        checks,
        "topology:five_identical_one_variable_devices_are_valid",
        [float(row["fixed_secondary_gate_v"]) for row in summaries] == values
        and len(set(topology_counts)) == 1
        and all(
            row["regions"] == sorted(acceptance["required_regions"])
            and row["contacts"] == sorted(acceptance["required_contacts"])
            and row["interfaces"] == sorted(acceptance["required_interfaces"])
            and int(row["forward_reported_point_count"]) == 31
            and int(row["reverse_reported_point_count"]) == 0
            and int(row["state_count"]) == 1
            and row == run["summary"]
            for row, run in zip(summaries, runs)
        ),
        f"topologies={topology_counts}",
    )

    grid = primary_grid(config)
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_bias(curve_rows, value)]
        == grid
        for value in values
    )
    curve_controls_valid = all(
        row["family_id"] == "top_primary"
        and row["primary_gate"] == "top_gate"
        and row["secondary_gate"] == "bottom_gate"
        and row["sweep_direction"] == "forward"
        and row["mesh_level"] == "interface_4x"
        and row["stage_id"] == "T03_P1_SECONDARY_BIAS"
        and same_value(float(row["vbg_v"]), float(row["fixed_secondary_gate_v"]))
        and same_value(float(row["vtg_v"]), float(row["primary_gate_v"]))
        and same_value(float(row["vds_v"]), 0.01)
        for row in curve_rows
    )
    curve_text_fields = {
        "family_id",
        "primary_gate",
        "secondary_gate",
        "sweep_direction",
        "mesh_level",
        "stage_id",
        "mode_id",
    }
    add_check(
        checks,
        "curves:155_persisted_points_match_report_grid_and_controls",
        len(curve_fields) == 23
        and len(curve_rows) == 155
        and grids_valid
        and curve_controls_valid
        and report_csv_rows_match(
            report["family_points"], curve_rows, curve_text_fields
        ),
        f"rows={len(curve_rows)} fields={len(curve_fields)} grids={grids_valid}",
    )

    max_imbalance = max(
        float(row["relative_current_imbalance"]) for row in curve_rows
    )
    primary_monotonic = True
    secondary_ordering = True
    max_drop = 0.0
    for value in values:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in curve_for_bias(curve_rows, value)
        ]
        primary_monotonic = primary_monotonic and all(
            higher > lower for lower, higher in zip(currents, currents[1:])
        )
        max_drop = max(
            max_drop,
            max(
                max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
                for lower, higher in zip(currents, currents[1:])
            ),
        )
    for primary_v in grid:
        currents = [
            abs(
                float(
                    next(
                        row
                        for row in curve_for_bias(curve_rows, value)
                        if same_value(float(row["primary_gate_v"]), primary_v)
                    )["drain_current_a_per_cm"]
                )
            )
            for value in values
        ]
        secondary_ordering = secondary_ordering and all(
            higher > lower for lower, higher in zip(currents, currents[1:])
        )
    add_check(
        checks,
        "current:direction_conservation_and_two_axis_ordering_recomputed",
        all(
            float(row["drain_current_a_per_cm"]) > 0.0
            and float(row["source_current_a_per_cm"]) < 0.0
            and math.isfinite(float(row["drain_current_a_per_cm"]))
            and row["converged"].lower() == "true"
            for row in curve_rows
        )
        and max_imbalance
        <= float(acceptance["maximum_relative_terminal_current_imbalance"])
        and primary_monotonic
        and secondary_ordering
        and max_drop <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"imbalance={max_imbalance:.6e} primary={primary_monotonic} secondary={secondary_ordering}",
    )

    zero_current = max(
        float(row["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"])
        for row in summaries
    )
    zero_potential = max(
        float(row["zero_equilibrium"]["maximum_absolute_potential_v"])
        for row in summaries
    )
    add_check(
        checks,
        "initialization:five_zero_equilibria_recomputed_from_logs",
        zero_current
        <= float(
            acceptance[
                "maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"
            ]
        )
        and zero_potential
        <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"current={zero_current:.6e} potential={zero_potential:.6e}",
    )

    recomputed = [
        {
            "fixed_secondary_gate_v": value,
            **extract_metric(baseline, config, curve_for_bias(curve_rows, value)),
        }
        for value in values
    ]
    vth = [row["vth_proxy_v"] for row in recomputed]
    slope, intercept, r_squared = regression(values, vth)
    reference_vth = next(
        row["vth_proxy_v"]
        for row in recomputed
        if same_value(row["fixed_secondary_gate_v"], 0.0)
    )
    for row in recomputed:
        row["delta_vth_proxy_v"] = row["vth_proxy_v"] - reference_vth
        row["coupling_slope_v_per_v"] = slope
        row["coupling_fit_intercept_v"] = intercept
        row["coupling_fit_r_squared"] = r_squared
    metric_valid = len(metric_rows) == 5 and len(metric_fields) == 21
    for value, expected in zip(values, recomputed):
        persisted = next(
            row
            for row in metric_rows
            if same_value(float(row["fixed_secondary_gate_v"]), value)
        )
        metric_valid = metric_valid and all(
            close(
                float(persisted[key]),
                expected_value,
                rel_tol=1.0e-10,
                abs_tol=1.0e-300,
            )
            for key, expected_value in expected.items()
        )
        metric_valid = metric_valid and all([
            persisted["family_id"] == "top_primary",
            persisted["primary_gate"] == "top_gate",
            persisted["secondary_gate"] == "bottom_gate",
            persisted["parameter_claim_status"]
            == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
        ])
    metric_text_fields = {
        "family_id",
        "primary_gate",
        "secondary_gate",
        "parameter_claim_status",
    }
    delta_vth = [row["delta_vth_proxy_v"] for row in recomputed]
    gm_values = [row["gm_proxy_s_per_cm"] for row in recomputed]
    add_check(
        checks,
        "extraction:vth_delta_gm_and_five_point_ols_recomputed",
        metric_valid
        and report_csv_rows_match(
            report["coupling_metrics"], metric_rows, metric_text_fields
        )
        and all(higher < lower for lower, higher in zip(vth, vth[1:]))
        and all(higher < lower for lower, higher in zip(delta_vth, delta_vth[1:]))
        and all(value > 0.0 and math.isfinite(value) for value in gm_values)
        and slope < 0.0
        and float(acceptance["minimum_absolute_coupling_slope_v_per_v"])
        <= abs(slope)
        <= float(acceptance["maximum_absolute_coupling_slope_v_per_v"])
        and r_squared >= float(acceptance["minimum_coupling_fit_r_squared"]),
        f"VTH={vth} slope={slope:.9f} R2={r_squared:.9f}",
    )

    current_reference = curve_for_bias(curve_rows, 0.0)
    t02_reference = sorted(
        [
            row
            for row in t02_c_report["family_points"]
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
        current_reference, t02_reference, reference_rows
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
            "primary_gate_v": float(current_row["primary_gate_v"]),
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
            close(
                float(persisted[key]),
                expected_value,
                rel_tol=1.0e-12,
                abs_tol=1.0e-300,
            )
            for key, expected_value in expected.items()
        )
    current_reference_metric = extract_metric(baseline, config, current_reference)
    t02_reference_metric = extract_metric(baseline, config, t02_reference)
    reference_vth_difference = abs(
        current_reference_metric["vth_proxy_v"]
        - t02_reference_metric["vth_proxy_v"]
    )
    reference_gm_difference = abs(
        current_reference_metric["gm_proxy_s_per_cm"]
        - t02_reference_metric["gm_proxy_s_per_cm"]
    ) / max(
        abs(current_reference_metric["gm_proxy_s_per_cm"]),
        abs(t02_reference_metric["gm_proxy_s_per_cm"]),
        1.0e-300,
    )
    saved_reference = report["t02_c_reference_reproduction"]
    add_check(
        checks,
        "regression:t02_c_zero_secondary_curve_and_extraction_recomputed",
        reference_valid
        and max_reference_current
        <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and max_reference_potential
        <= float(
            acceptance["maximum_t02_c_reference_center_potential_difference_v"]
        )
        and max_reference_density
        <= float(
            acceptance["maximum_t02_c_reference_center_density_relative_difference"]
        )
        and reference_vth_difference
        <= float(acceptance["maximum_t02_c_reference_vth_difference_v"])
        and reference_gm_difference
        <= float(acceptance["maximum_t02_c_reference_gm_relative_difference"])
        and close(saved_reference["maximum_current_relative_difference"], max_reference_current)
        and close(saved_reference["maximum_center_potential_difference_v"], max_reference_potential)
        and close(saved_reference["maximum_center_density_relative_difference"], max_reference_density)
        and close(saved_reference["vth_difference_v"], reference_vth_difference)
        and close(saved_reference["gm_relative_difference"], reference_gm_difference),
        f"current={max_reference_current:.3e} potential={max_reference_potential:.3e} density={max_reference_density:.3e}",
    )

    state_entries = state_manifest.get("entries", [])
    state_summary_by_id = {row["state_id"]: row for row in state_summary_rows}
    state_valid = all([
        state_manifest.get("entry_count") == 5,
        len(state_entries) == 5,
        len(state_summary_rows) == 5,
        len(state_summary_fields) == 26,
        report["state_outputs"] == state_entries,
        [entry["state_id"] for entry in state_entries]
        == acceptance["required_state_ids"],
    ])
    for entry in state_entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        node_rows, node_fields = load_csv(node_path)
        element_rows, element_fields = load_csv(element_path)
        center = nearest_channel_state(node_rows, baseline)
        bias_row = next(
            row
            for row in curve_for_bias(curve_rows, float(entry["vbg_v"]))
            if same_value(float(row["primary_gate_v"]), float(entry["vtg_v"]))
        )
        summary = state_summary_by_id[entry["state_id"]]
        potential_values = [float(row["potential_v"]) for row in node_rows]
        density_values = [
            float(row["electron_density_cm3"])
            for row in node_rows
            if row["region"] == "channel"
        ]
        current_values = [
            float(row["electron_current_density_magnitude_a_per_cm2"])
            for row in element_rows
        ]
        state_valid = state_valid and all([
            len(node_fields) == 17,
            len(element_fields) == 35,
            len(node_rows) == int(entry["node_row_count"]),
            len(density_values) == int(entry["channel_node_count"]),
            len(element_rows) == int(entry["channel_element_count"]),
            set(row["region"] for row in node_rows)
            == set(acceptance["required_regions"]),
            all(row["stage_id"] == "T03_P1_SECONDARY_BIAS" for row in node_rows),
            all(row["stage_id"] == "T03_P1_SECONDARY_BIAS" for row in element_rows),
            entry["node_csv_sha256"] == sha256(node_path),
            entry["element_csv_sha256"] == sha256(element_path),
            len(entry["vtk_files"]) == 6,
            int(entry["vtk_file_count"]) == 6,
            all(
                (ROOT / item["path"]).is_file()
                and item["sha256"] == sha256(ROOT / item["path"])
                for item in entry["vtk_files"]
            ),
            same_value(float(entry["vtg_v"]), 0.3),
            same_value(float(entry["vds_v"]), 0.01),
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
            close(entry["minimum_potential_v"], min(potential_values)),
            close(entry["maximum_potential_v"], max(potential_values)),
            close(entry["minimum_electron_density_cm3"], min(density_values)),
            close(entry["maximum_electron_density_cm3"], max(density_values)),
            close(
                entry["minimum_cell_current_density_magnitude_a_per_cm2"],
                min(current_values),
            ),
            close(
                entry["median_cell_current_density_magnitude_a_per_cm2"],
                statistics.median(current_values),
            ),
            close(
                entry["maximum_cell_current_density_magnitude_a_per_cm2"],
                max(current_values),
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
    ordered_states = sorted(state_entries, key=lambda entry: float(entry["vbg_v"]))
    state_currents = [
        float(entry["absolute_drain_current_a_per_cm"]) for entry in ordered_states
    ]
    state_potential = [
        float(entry["center_channel_potential_v"]) for entry in ordered_states
    ]
    state_density = [
        float(entry["center_channel_electron_density_cm3"])
        for entry in ordered_states
    ]
    state_text_fields = {
        "state_id",
        "state_label",
        "source_family",
        "mesh_level",
        "stage_id",
        "node_csv",
        "element_csv",
    }
    add_check(
        checks,
        "states:five_node_element_and_30_vtk_outputs_recomputed",
        state_valid
        and sum(len(entry["vtk_files"]) for entry in state_entries) == 30
        and report_csv_rows_match(
            report["state_outputs"], state_summary_rows, state_text_fields
        )
        and all(higher > lower for lower, higher in zip(state_currents, state_currents[1:]))
        and all(higher > lower for lower, higher in zip(state_potential, state_potential[1:]))
        and all(higher > lower for lower, higher in zip(state_density, state_density[1:])),
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
        figure_valid = figure_valid and all([
            item["sha256"] == sha256(path),
            width >= 1000,
            height >= 600,
            path.stat().st_size > 0,
        ])
    add_check(
        checks,
        "outputs:artifact_hashes_and_png_dimensions_match",
        artifact_hashes_valid and figure_valid,
        f"artifacts={len(report['artifacts'])} figures={figure_details}",
    )

    ratio = config["capacitance_ratio_control"]
    computed_ratio = (
        float(ratio["top_relative_permittivity"])
        / float(ratio["top_physical_thickness_nm"])
    ) / (
        float(ratio["bottom_relative_permittivity"])
        / float(ratio["bottom_physical_thickness_nm"])
    )
    add_check(
        checks,
        "scope:one_bias_variable_and_fixed_ratio_control_remain_frozen",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "fixed_bottom_gate_bias_v"
        and ratio["status"] == "controlled_not_scanned"
        and same_value(computed_ratio, 1.0)
        and same_value(ratio["fixed_top_to_bottom_ratio"], 1.0)
        and report["capacitance_ratio_control"] == ratio,
        f"changed={config['scope']['changed_variable']} ratio={computed_ratio}",
    )

    runner_checks = report.get("checks", {})
    completion = report.get("t03_p1_bias_completion", {})
    prohibited = " ".join(report["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks,
        "runner:partial_p1_gate_and_evidence_boundary_pass",
        len(runner_checks) == 14
        and all(item["status"] == "PASS" for item in runner_checks.values())
        and not report.get("failures")
        and completion.get("status") == "PASS"
        and completion.get("p1_bias_five_point_substage_complete") is True
        and completion.get("complete_p1_bias_and_capacitance_group") is False
        and completion.get("capacitance_ratio_substage_permitted_next") is True
        and completion.get("complete_t03_five_group_sensitivity") is False
        and completion.get("experimental_calibration_permitted") is False
        and completion.get("physical_capacitance_ratio_claim_permitted") is False
        and "complete P1" in prohibited
        and "complete T03" in prohibited
        and "physical top-to-bottom capacitance ratio" in prohibited
        and "numerical proxies" in report["limitations"][0],
        f"runner_checks={len(runner_checks)} bias_complete={completion.get('p1_bias_five_point_substage_complete')}",
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    check_report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_simulation_runner": True,
        "checks": checks,
        "failures": failures,
        "recomputed_metrics": {
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_monotonic_relative_current_drop": max_drop,
            "vth_proxy_v": vth,
            "delta_vth_proxy_v": delta_vth,
            "gm_proxy_s_per_cm": gm_values,
            "coupling_slope_v_per_v": slope,
            "coupling_fit_intercept_v": intercept,
            "coupling_fit_r_squared": r_squared,
            "t02_c_reference": {
                "maximum_current_relative_difference": max_reference_current,
                "maximum_center_potential_difference_v": max_reference_potential,
                "maximum_center_density_relative_difference": max_reference_density,
                "vth_difference_v": reference_vth_difference,
                "gm_relative_difference": reference_gm_difference,
            },
            "state_absolute_drain_current_a_per_cm": state_currents,
            "state_center_channel_potential_v": state_potential,
            "state_center_channel_electron_density_cm3": state_density,
        },
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        json.dumps(check_report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T03_P1_BIAS_SENSITIVITY_CHECK_{check_report['status']} "
        f"checks={len(checks)} report={check_path}"
    )
    for failure in failures:
        print(
            f"T03_P1_BIAS_SENSITIVITY_CHECK_ERROR "
            f"{failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
