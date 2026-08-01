#!/usr/bin/env python3
"""Independently validate persisted T03-P1-CAP-RATIO evidence."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p1_capacitance_ratio.json"


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


def same_value(left: float, right: float, *, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def close(
    left: float, right: float, *, rel_tol: float = 1e-10, abs_tol: float = 1e-15
) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T03-P1-CAP-RATIO primary grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def curve_for_ratio(rows: list[dict[str, Any]], ratio: float) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["capacitance_ratio"]), ratio)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def interpolate(xs: list[float], ys: list[float], target: float) -> float:
    for x_value, y_value in zip(xs, ys):
        if same_value(x_value, target):
            return y_value
    index = next(
        index for index in range(len(xs) - 1) if xs[index] < target < xs[index + 1]
    )
    return ys[index] + (
        (target - xs[index]) * (ys[index + 1] - ys[index])
        / (xs[index + 1] - xs[index])
    )


def extract_metric(
    baseline: dict[str, Any], config: dict[str, Any], curve: list[dict[str, Any]]
) -> dict[str, float]:
    width_cm = float(baseline["device"]["width_cm"])
    length_cm = float(baseline["device"]["channel_length_cm"])
    method = config["extraction_methods"]["constant_current_vth_proxy"]
    terminal_criterion = float(method["criterion_prefactor_a"]) * (width_cm / length_cm)
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
    gm_voltage = vth + float(config["extraction_methods"]["gm_proxy"]["evaluation_overdrive_v"])
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
    report_rows: list[dict[str, Any]], csv_rows: list[dict[str, str]], text_fields: set[str]
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
                float(report_row[field]), float(csv_value), rel_tol=1e-12, abs_tol=1e-300
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
    nearest = min(
        (row for row in rows if row["region"] == "channel"),
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
    t02_report = load_json(ROOT / config["dependencies"]["t02_c_report"])
    curve_rows, curve_fields = load_csv(ROOT / outputs["curve_csv"])
    metric_rows, metric_fields = load_csv(ROOT / outputs["metric_csv"])
    reference_rows, reference_fields = load_csv(ROOT / outputs["reference_comparison_csv"])
    state_summary_rows, state_summary_fields = load_csv(ROOT / outputs["state_summary_csv"])
    acceptance = config["acceptance"]
    ratios = [float(value) for value in acceptance["required_ratio_values"]]
    checks: list[dict[str, Any]] = []

    add_check(
        checks, "identity:e2_cap_ratio_report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T03-P1-CAP-RATIO"
        and report.get("parameter_group_id") == "P1"
        and report.get("evidence_level") == "E2",
        f"status={report.get('status')} case={report.get('case_id')}",
    )
    contract_checks = contract.get("checks", [])
    add_check(
        checks, "contract:static_gate_and_config_hash_match",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and len(contract_checks) == 20
        and all(item.get("status") == "PASS" for item in contract_checks)
        and not contract.get("failures")
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH),
        f"checks={len(contract_checks)} simulation={contract.get('simulation_status')}",
    )
    snapshot_valid = all(
        (ROOT / item["path"]).is_file() and item["sha256"] == sha256(ROOT / item["path"])
        for item in snapshot.get("inputs", {}).values()
    )
    add_check(
        checks, "inputs:snapshot_hashes_match",
        snapshot.get("case_id") == config["case_id"]
        and snapshot.get("stage") == config["stage"]
        and snapshot_valid
        and snapshot["inputs"]["t03_p1_cap_ratio_config"]["sha256"] == sha256(CONFIG_PATH)
        and report.get("input_snapshot") == outputs["config_snapshot"],
        f"inputs={len(snapshot.get('inputs', {}))}",
    )

    runs = solver_log.get("runs", [])
    records = [record for run in runs for record in run.get("solver_records", [])]
    solve_counts = [len(run.get("solver_records", [])) for run in runs]
    add_check(
        checks, "solver:five_fresh_devices_and_205_dc_solves_converged",
        [float(run["capacitance_ratio"]) for run in runs] == ratios
        and solve_counts == [41, 41, 41, 41, 41]
        and len(records) == 205
        and all(run.get("status") == "PASS" for run in runs)
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors")
        and float(solver_log["wall_seconds"]) <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"runs={len(runs)} solve_counts={solve_counts} records={len(records)} wall={solver_log.get('wall_seconds')}",
    )

    summaries = report.get("family_summaries", [])
    topology_counts = [
        (int(row["node_count_with_interface_duplicates"]), int(row["element_count"]))
        for row in summaries
    ]
    fixed_sum = float(config["ratio_encoding"]["fixed_relative_permittivity_sum"])
    encoding_valid = True
    for point, expected_ratio in zip(config["ratio_encoding"]["points"], ratios):
        top = float(point["top_relative_permittivity"])
        bottom = float(point["bottom_relative_permittivity"])
        encoding_valid = encoding_valid and all([
            close(point["ratio"], expected_ratio, rel_tol=1e-12),
            close(top / bottom, expected_ratio, rel_tol=float(acceptance["maximum_ratio_reconstruction_relative_error"])),
            close(top + bottom, fixed_sum, rel_tol=float(acceptance["maximum_fixed_sum_relative_error"])),
            close(point["top_coupling_fraction"], expected_ratio / (1.0 + expected_ratio), rel_tol=1e-12),
        ])
    add_check(
        checks, "topology:five_identical_fixed_geometry_devices_and_ratio_encoding_valid",
        len(summaries) == 5 and len(set(topology_counts)) == 1 and encoding_valid
        and all(
            sorted(row["regions"]) == sorted(acceptance["required_regions"])
            and sorted(row["contacts"]) == sorted(acceptance["required_contacts"])
            and sorted(row["interfaces"]) == sorted(acceptance["required_interfaces"])
            and int(row["forward_reported_point_count"]) == 31
            and int(row["reverse_reported_point_count"]) == 0
            and int(row["state_count"]) == 1
            and row == run["summary"]
            for row, run in zip(summaries, runs)
        ),
        f"topologies={topology_counts} encoding={encoding_valid}",
    )

    grid = primary_grid(config)
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_ratio(curve_rows, ratio)] == grid
        for ratio in ratios
    )
    curve_controls_valid = all(
        row["family_id"] == "top_primary"
        and row["primary_gate"] == "top_gate"
        and row["secondary_gate"] == "bottom_gate"
        and row["sweep_direction"] == "forward"
        and row["mesh_level"] == "interface_4x"
        and row["stage_id"] == "T03_P1_CAPACITANCE_RATIO"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        and same_value(float(row["vbg_v"]), 0.0)
        and same_value(float(row["vtg_v"]), float(row["primary_gate_v"]))
        and same_value(float(row["vds_v"]), 0.01)
        for row in curve_rows
    )
    curve_text_fields = {
        "family_id", "primary_gate", "secondary_gate", "sweep_direction",
        "mesh_level", "stage_id", "mode_id",
    }
    add_check(
        checks, "curves:155_persisted_points_match_report_grid_controls_and_encoding",
        len(curve_fields) == 28 and len(curve_rows) == 155 and grids_valid
        and curve_controls_valid
        and report_csv_rows_match(report["family_points"], curve_rows, curve_text_fields)
        and all(
            close(float(row["top_relative_permittivity"]) / float(row["bottom_relative_permittivity"]), float(row["capacitance_ratio"]), rel_tol=1e-12)
            and close(float(row["fixed_relative_permittivity_sum"]), fixed_sum, rel_tol=1e-12)
            for row in curve_rows
        ),
        f"rows={len(curve_rows)} fields={len(curve_fields)} grids={grids_valid}",
    )

    max_imbalance = max(float(row["relative_current_imbalance"]) for row in curve_rows)
    primary_monotonic = all(
        all(higher > lower for lower, higher in zip(currents, currents[1:]))
        for currents in (
            [abs(float(row["drain_current_a_per_cm"])) for row in curve_for_ratio(curve_rows, ratio)]
            for ratio in ratios
        )
    )
    zero_current = max(
        float(row["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"])
        for row in summaries
    )
    zero_potential = max(
        float(row["zero_equilibrium"]["maximum_absolute_potential_v"]) for row in summaries
    )
    add_check(
        checks, "current:direction_conservation_primary_ordering_and_zero_states_recomputed",
        all(
            float(row["drain_current_a_per_cm"]) > 0.0
            and float(row["source_current_a_per_cm"]) < 0.0
            and math.isfinite(float(row["drain_current_a_per_cm"]))
            and row["converged"].lower() == "true" for row in curve_rows
        )
        and max_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"])
        and primary_monotonic
        and zero_current <= float(acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"])
        and zero_potential <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"imbalance={max_imbalance:.6e} primary={primary_monotonic} zero_current={zero_current:.3e}",
    )

    recomputed = [
        {"capacitance_ratio": ratio, **extract_metric(baseline, config, curve_for_ratio(curve_rows, ratio))}
        for ratio in ratios
    ]
    reference_metric = recomputed[2]
    vth = [row["vth_proxy_v"] for row in recomputed]
    gm_values = [row["gm_proxy_s_per_cm"] for row in recomputed]
    delta_vth = [value - reference_metric["vth_proxy_v"] for value in vth]
    gm_relative = [value / reference_metric["gm_proxy_s_per_cm"] for value in gm_values]
    metric_valid = len(metric_rows) == 5 and len(metric_fields) == 22
    for expected, persisted, point in zip(recomputed, metric_rows, config["ratio_encoding"]["points"]):
        metric_valid = metric_valid and same_value(float(persisted["capacitance_ratio"]), expected["capacitance_ratio"])
        metric_valid = metric_valid and all(
            close(float(persisted[key]), value, rel_tol=1e-10, abs_tol=1e-300)
            for key, value in expected.items() if key != "capacitance_ratio"
        )
        metric_valid = metric_valid and all([
            close(float(persisted["delta_vth_proxy_v"]), delta_vth[recomputed.index(expected)]),
            close(float(persisted["gm_relative_to_symmetric"]), gm_relative[recomputed.index(expected)]),
            close(float(persisted["top_relative_permittivity"]), point["top_relative_permittivity"]),
            close(float(persisted["bottom_relative_permittivity"]), point["bottom_relative_permittivity"]),
            persisted["parameter_claim_status"] == "NUMERICAL_COUPLING_PROXY_NOT_PHYSICALLY_VALIDATED",
        ])
    metric_text_fields = {"family_id", "parameter_claim_status"}
    add_check(
        checks, "extraction:vth_delta_and_gm_recomputed_independently",
        metric_valid
        and report_csv_rows_match(report["capacitance_ratio_metrics"], metric_rows, metric_text_fields)
        and all(higher < lower for lower, higher in zip(vth, vth[1:]))
        and all(higher > lower for lower, higher in zip(gm_values, gm_values[1:]))
        and same_value(delta_vth[2], 0.0),
        f"VTH={vth} delta={delta_vth} gm={gm_values}",
    )

    current_reference = curve_for_ratio(curve_rows, 1.0)
    t02_reference = sorted(
        [
            row for row in t02_report["family_points"]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )
    reference_valid = len(reference_rows) == 31 and len(reference_fields) == 10
    maxima = {"current": 0.0, "potential": 0.0, "density": 0.0}
    for current_row, t02_row, persisted in zip(current_reference, t02_reference, reference_rows):
        current = abs(float(current_row["drain_current_a_per_cm"]))
        t02_current = abs(float(t02_row["drain_current_a_per_cm"]))
        density = float(current_row["center_channel_electron_density_cm3"])
        t02_density = float(t02_row["center_channel_electron_density_cm3"])
        expected = {
            "primary_gate_v": float(current_row["primary_gate_v"]),
            "t03_abs_drain_current_a_per_cm": current,
            "t02_c_abs_drain_current_a_per_cm": t02_current,
            "current_relative_difference": abs(current - t02_current) / max(current, t02_current, 1e-300),
            "t03_center_channel_potential_v": float(current_row["center_channel_potential_v"]),
            "t02_c_center_channel_potential_v": float(t02_row["center_channel_potential_v"]),
            "center_channel_potential_difference_v": abs(float(current_row["center_channel_potential_v"]) - float(t02_row["center_channel_potential_v"])),
            "t03_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": t02_density,
            "center_density_relative_difference": abs(density - t02_density) / max(density, t02_density, 1e-300),
        }
        maxima["current"] = max(maxima["current"], expected["current_relative_difference"])
        maxima["potential"] = max(maxima["potential"], expected["center_channel_potential_difference_v"])
        maxima["density"] = max(maxima["density"], expected["center_density_relative_difference"])
        reference_valid = reference_valid and all(
            close(float(persisted[key]), value, rel_tol=1e-12, abs_tol=1e-300)
            for key, value in expected.items()
        )
    current_reference_metric = extract_metric(baseline, config, current_reference)
    t02_reference_metric = extract_metric(baseline, config, t02_reference)
    vth_difference = abs(current_reference_metric["vth_proxy_v"] - t02_reference_metric["vth_proxy_v"])
    gm_difference = abs(current_reference_metric["gm_proxy_s_per_cm"] - t02_reference_metric["gm_proxy_s_per_cm"]) / max(
        abs(current_reference_metric["gm_proxy_s_per_cm"]), abs(t02_reference_metric["gm_proxy_s_per_cm"]), 1e-300
    )
    saved_reference = report["t02_c_symmetric_reference_reproduction"]
    add_check(
        checks, "regression:t02_c_symmetric_curve_and_extraction_recomputed",
        reference_valid
        and maxima["current"] <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and maxima["potential"] <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and maxima["density"] <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"])
        and vth_difference <= float(acceptance["maximum_t02_c_reference_vth_difference_v"])
        and gm_difference <= float(acceptance["maximum_t02_c_reference_gm_relative_difference"])
        and close(saved_reference["maximum_current_relative_difference"], maxima["current"])
        and close(saved_reference["vth_difference_v"], vth_difference)
        and close(saved_reference["gm_relative_difference"], gm_difference),
        f"current={maxima['current']:.3e} potential={maxima['potential']:.3e} density={maxima['density']:.3e}",
    )

    entries = state_manifest.get("entries", [])
    state_summary_by_id = {row["state_id"]: row for row in state_summary_rows}
    state_valid = all([
        state_manifest.get("entry_count") == 5, len(entries) == 5,
        len(state_summary_rows) == 5, len(state_summary_fields) == 31,
        report["state_outputs"] == entries,
        [entry["state_id"] for entry in entries] == acceptance["required_state_ids"],
    ])
    for entry in entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        node_rows, node_fields = load_csv(node_path)
        element_rows, element_fields = load_csv(element_path)
        center = nearest_channel_state(node_rows, baseline)
        ratio = float(entry["capacitance_ratio"])
        bias_row = next(
            row for row in curve_for_ratio(curve_rows, ratio)
            if same_value(float(row["primary_gate_v"]), float(entry["vtg_v"]))
        )
        potential_values = [float(row["potential_v"]) for row in node_rows]
        density_values = [float(row["electron_density_cm3"]) for row in node_rows if row["region"] == "channel"]
        current_values = [float(row["electron_current_density_magnitude_a_per_cm2"]) for row in element_rows]
        state_valid = state_valid and all([
            len(node_fields) == 17, len(element_fields) == 35,
            len(node_rows) == int(entry["node_row_count"]),
            len(density_values) == int(entry["channel_node_count"]),
            len(element_rows) == int(entry["channel_element_count"]),
            set(row["region"] for row in node_rows) == set(acceptance["required_regions"]),
            all(row["stage_id"] == "T03_P1_CAPACITANCE_RATIO" for row in node_rows),
            all(row["stage_id"] == "T03_P1_CAPACITANCE_RATIO" for row in element_rows),
            entry["node_csv_sha256"] == sha256(node_path),
            entry["element_csv_sha256"] == sha256(element_path),
            len(entry["vtk_files"]) == 6 and int(entry["vtk_file_count"]) == 6,
            all((ROOT / item["path"]).is_file() and item["sha256"] == sha256(ROOT / item["path"]) for item in entry["vtk_files"]),
            same_value(float(entry["vbg_v"]), 0.0), same_value(float(entry["vtg_v"]), 0.3),
            close(center["potential_v"], entry["center_channel_potential_v"]),
            close(center["electron_density_cm3"], entry["center_channel_electron_density_cm3"], abs_tol=1e-300),
            close(entry["absolute_drain_current_a_per_cm"], abs(float(bias_row["drain_current_a_per_cm"]))),
            close(entry["minimum_potential_v"], min(potential_values)),
            close(entry["maximum_potential_v"], max(potential_values)),
            close(entry["minimum_electron_density_cm3"], min(density_values)),
            close(entry["maximum_electron_density_cm3"], max(density_values)),
            close(entry["minimum_cell_current_density_magnitude_a_per_cm2"], min(current_values)),
            close(entry["median_cell_current_density_magnitude_a_per_cm2"], statistics.median(current_values)),
            close(entry["maximum_cell_current_density_magnitude_a_per_cm2"], max(current_values)),
            state_summary_by_id[entry["state_id"]]["node_csv"] == entry["node_csv"],
        ])
        state_valid = state_valid and all(
            close(
                float(row["electron_current_density_magnitude_a_per_cm2"]),
                math.hypot(float(row["electron_current_density_x_a_per_cm2"]), float(row["electron_current_density_y_a_per_cm2"])),
                rel_tol=1e-12, abs_tol=1e-300,
            ) for row in element_rows
        )
    ordered_entries = sorted(entries, key=lambda entry: float(entry["capacitance_ratio"]))
    state_currents = [float(entry["absolute_drain_current_a_per_cm"]) for entry in ordered_entries]
    state_potential = [float(entry["center_channel_potential_v"]) for entry in ordered_entries]
    state_density = [float(entry["center_channel_electron_density_cm3"]) for entry in ordered_entries]
    state_text_fields = {"state_id", "state_label", "source_family", "mesh_level", "stage_id", "node_csv", "element_csv"}
    add_check(
        checks, "states:five_node_element_and_30_vtk_outputs_recomputed",
        state_valid and sum(len(entry["vtk_files"]) for entry in entries) == 30
        and report_csv_rows_match(report["state_outputs"], state_summary_rows, state_text_fields)
        and all(higher > lower for lower, higher in zip(state_currents, state_currents[1:]))
        and all(higher > lower for lower, higher in zip(state_potential, state_potential[1:]))
        and all(higher > lower for lower, higher in zip(state_density, state_density[1:])),
        f"states={[entry['state_id'] for entry in entries]}",
    )

    artifact_valid = all(
        (ROOT / item["path"]).is_file() and item["sha256"] == sha256(ROOT / item["path"])
        for item in report["artifacts"].values()
    )
    figure_details: list[tuple[int, int, int]] = []
    figure_valid = len(report["figures"]) == 2
    for item in report["figures"]:
        path = ROOT / item["path"]
        width, height = png_dimensions(path)
        figure_details.append((width, height, path.stat().st_size))
        figure_valid = figure_valid and item["sha256"] == sha256(path) and width >= 1000 and height >= 600 and path.stat().st_size > 0
    add_check(
        checks, "outputs:artifact_hashes_and_png_dimensions_match",
        artifact_valid and figure_valid,
        f"artifacts={len(report['artifacts'])} figures={figure_details}",
    )
    add_check(
        checks, "scope:one_fixed_sum_p1_ratio_variable_and_p4_controls_remain_frozen",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "effective_top_to_bottom_gate_capacitance_ratio"
        and close(config["ratio_encoding"]["top_physical_thickness_nm"], 30.0)
        and close(config["ratio_encoding"]["bottom_physical_thickness_nm"], 30.0)
        and close(fixed_sum / 2.0, 6.8)
        and report["ratio_encoding"] == config["ratio_encoding"]
        and "fixed-sum differential coupling allocation" in report["p1_p4_variable_ownership"]["boundary"],
        report["p1_p4_variable_ownership"]["boundary"],
    )
    runner_checks = report.get("checks", {})
    completion = report.get("t03_p1_completion", {})
    prohibited = " ".join(report["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks, "runner:numerical_p1_completion_and_evidence_boundary_pass",
        len(runner_checks) == 16
        and all(item["status"] == "PASS" for item in runner_checks.values())
        and not report.get("failures")
        and completion.get("p1_bias_five_point_substage_complete") is True
        and completion.get("p1_capacitance_ratio_five_point_substage_complete") is True
        and completion.get("complete_p1_numerical_group") is True
        and completion.get("complete_t03_five_group_sensitivity") is False
        and completion.get("experimental_calibration_permitted") is False
        and completion.get("physical_capacitance_ratio_claim_permitted") is False
        and "physically extracted" in prohibited and "measured Al2O3" in prohibited
        and "complete T03" in prohibited and "numerical proxies" in report["limitations"][0],
        f"runner_checks={len(runner_checks)} p1_complete={completion.get('complete_p1_numerical_group')}",
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    check_report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"], "stage": config["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_simulation_runner": True,
        "checks": checks, "failures": failures,
        "recomputed_metrics": {
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "vth_proxy_v": vth, "delta_vth_proxy_v": delta_vth,
            "gm_proxy_s_per_cm": gm_values, "gm_relative_to_symmetric": gm_relative,
            "t02_c_reference": {
                "maximum_current_relative_difference": maxima["current"],
                "maximum_center_potential_difference_v": maxima["potential"],
                "maximum_center_density_relative_difference": maxima["density"],
                "vth_difference_v": vth_difference, "gm_relative_difference": gm_difference,
            },
            "state_absolute_drain_current_a_per_cm": state_currents,
            "state_center_channel_potential_v": state_potential,
            "state_center_channel_electron_density_cm3": state_density,
        },
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(json.dumps(check_report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"T03_P1_CAP_RATIO_SENSITIVITY_CHECK_{check_report['status']} checks={len(checks)} report={check_path}")
    for failure in failures:
        print(f"T03_P1_CAP_RATIO_SENSITIVITY_CHECK_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
