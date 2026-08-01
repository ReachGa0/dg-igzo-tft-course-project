#!/usr/bin/env python3
"""Independently validate persisted T03-P2-DIT-FORMAL evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_dit_formal.json"


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


def close(
    left: float, right: float, *, rel_tol: float = 1e-10, abs_tol: float = 1e-14
) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def same_voltage(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def same_dit(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-6)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), 1e-300)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    count = round((stop - start) / step)
    if count < 1 or not same_voltage(start + count * step, stop):
        raise ValueError("formal primary-gate grid is not integral")
    return [round(start + index * step, 12) for index in range(count + 1)]


def curve_for_dit(rows: list[dict[str, str]], dit_cm2_ev: float) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if same_dit(float(row["dit_cm2_ev"]), dit_cm2_ev)],
        key=lambda row: float(row["primary_gate_v"]),
    )


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    if len(xs) != len(ys) or len(xs) < 2:
        raise ValueError("regression needs at least two paired samples")
    x_mean = sum(xs) / len(xs)
    y_mean = sum(ys) / len(ys)
    sxx = sum((value - x_mean) ** 2 for value in xs)
    if sxx <= 0.0:
        raise ValueError("regression x variance is zero")
    slope = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys, strict=True)) / sxx
    intercept = y_mean - slope * x_mean
    total = sum((value - y_mean) ** 2 for value in ys)
    residual = sum(
        (y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys, strict=True)
    )
    r_squared = 1.0 if total == 0.0 else 1.0 - residual / total
    return slope, intercept, r_squared


def interpolate(xs: list[float], ys: list[float], target: float) -> float:
    for x_value, y_value in zip(xs, ys, strict=True):
        if same_voltage(x_value, target):
            return y_value
    index = next(index for index in range(len(xs) - 1) if xs[index] < target < xs[index + 1])
    return ys[index] + (
        (target - xs[index]) * (ys[index + 1] - ys[index]) / (xs[index + 1] - xs[index])
    )


def voltage_at_current(curve: list[dict[str, str]], target: float) -> float:
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    for voltage, current in zip(voltages, currents, strict=True):
        if math.isclose(current, target, rel_tol=1e-12, abs_tol=0.0):
            return voltage
    index = next(
        index for index in range(len(currents) - 1)
        if currents[index] < target < currents[index + 1]
    )
    logs = [math.log10(currents[index]), math.log10(currents[index + 1])]
    return voltages[index] + (
        (math.log10(target) - logs[0])
        * (voltages[index + 1] - voltages[index])
        / (logs[1] - logs[0])
    )


def recompute_metric(
    baseline: dict[str, Any], config: dict[str, Any], curve: list[dict[str, str]], dit_cm2_ev: float
) -> dict[str, float | int]:
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    criterion = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "expected_current_per_width_a_per_cm"
        ]
    )
    terminal_criterion = float(
        config["extraction_methods"]["constant_current_vth_proxy"]["expected_terminal_current_a"]
    )
    bracket = next(
        index for index in range(len(currents) - 1)
        if currents[index] <= criterion <= currents[index + 1]
    )
    lower_log = math.log10(currents[bracket])
    upper_log = math.log10(currents[bracket + 1])
    vth = voltages[bracket] + (
        (math.log10(criterion) - lower_log)
        * (voltages[bracket + 1] - voltages[bracket])
        / (upper_log - lower_log)
    )
    gm_voltages = voltages[1:-1]
    gm_values = [
        (currents[index + 1] - currents[index - 1])
        / (voltages[index + 1] - voltages[index - 1])
        for index in range(1, len(curve) - 1)
    ]
    gm_v = vth + float(config["extraction_methods"]["gm_proxy"]["evaluation_overdrive_v"])
    gm = interpolate(gm_voltages, gm_values, gm_v)
    peak_index = max(range(len(gm_values)), key=lambda index: gm_values[index])

    ss = config["extraction_methods"]["ss_proxy"]
    ss_lower = float(ss["lower_current_a_per_cm"])
    ss_upper = float(ss["upper_current_a_per_cm"])
    samples = {
        round(math.log10(ss_lower), 14): voltage_at_current(curve, ss_lower),
        round(math.log10(ss_upper), 14): voltage_at_current(curve, ss_upper),
    }
    for voltage, current in zip(voltages, currents, strict=True):
        if ss_lower < current < ss_upper:
            samples[round(math.log10(current), 14)] = voltage
    ss_x = sorted(samples)
    ss_y = [samples[value] for value in ss_x]
    ss_slope, ss_intercept, ss_r_squared = linear_regression(ss_x, ss_y)
    ioff_v = float(config["extraction_methods"]["ioff_proxy"]["evaluation_top_gate_v"])
    ioff = next(
        current for voltage, current in zip(voltages, currents, strict=True)
        if same_voltage(voltage, ioff_v)
    )
    width_cm = float(baseline["device"]["width_cm"])
    return {
        "dit_cm2_ev": dit_cm2_ev,
        "interface_trap_capacitance_f_per_cm2": 1.602176634e-19 * dit_cm2_ev,
        "constant_current_criterion_terminal_a": terminal_criterion,
        "constant_current_criterion_a_per_cm": criterion,
        "vth_proxy_v": vth,
        "vth_bracket_lower_primary_gate_v": voltages[bracket],
        "vth_bracket_upper_primary_gate_v": voltages[bracket + 1],
        "vth_bracket_lower_current_a_per_cm": currents[bracket],
        "vth_bracket_upper_current_a_per_cm": currents[bracket + 1],
        "gm_evaluation_primary_gate_v": gm_v,
        "gm_proxy_s_per_cm": gm,
        "gm_proxy_terminal_s": gm * width_cm,
        "maximum_sampled_gm_s_per_cm": gm_values[peak_index],
        "maximum_sampled_gm_primary_gate_v": gm_voltages[peak_index],
        "ss_window_lower_current_a_per_cm": ss_lower,
        "ss_window_upper_current_a_per_cm": ss_upper,
        "ss_fit_sample_count": len(ss_x),
        "ss_fit_slope_v_per_dec": ss_slope,
        "ss_fit_intercept_v": ss_intercept,
        "ss_fit_r_squared": ss_r_squared,
        "ss_proxy_mv_per_dec": 1000.0 * ss_slope,
        "ioff_evaluation_top_gate_v": ioff_v,
        "ioff_proxy_a_per_cm": ioff,
        "ioff_proxy_terminal_a": ioff * width_cm,
    }


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    report_path = ROOT / outputs["report"]
    contract = load_json(contract_path)
    report = load_json(report_path)
    snapshot = load_json(ROOT / outputs["config_snapshot"])
    solver_log = load_json(ROOT / outputs["solver_log"])
    manifest = load_json(ROOT / outputs["state_manifest"])
    curve_rows, curve_fields = load_csv(ROOT / outputs["curve_csv"])
    metric_rows, metric_fields = load_csv(ROOT / outputs["metric_csv"])
    reference_rows, reference_fields = load_csv(ROOT / outputs["reference_comparison_csv"])
    state_rows, state_fields = load_csv(ROOT / outputs["state_summary_csv"])
    baseline = load_json(ROOT / config["dependencies"]["t01_baseline_config"])
    t02_report = load_json(ROOT / config["dependencies"]["t02_c_report"])
    checks: list[dict[str, Any]] = []
    values = [float(value) for value in config["sensitivity"]["execution_values_cm2_ev"]]
    acceptance = config["acceptance"]

    runner_checks = report.get("checks", {})
    add_check(
        checks, "identity:runner_report_is_passed_v2_e2",
        report.get("status") == "PASS"
        and report.get("case_id") == config.get("case_id") == "IGZO_T03_P2_DIT_FORMAL_V2"
        and report.get("stage") == config.get("stage") == "T03-P2-DIT-FORMAL"
        and report.get("evidence_level") == "E2"
        and len(runner_checks) == 14
        and all(item.get("status") == "PASS" for item in runner_checks.values())
        and not report.get("failures"),
        f"status={report.get('status')} checks={len(runner_checks)} failures={report.get('failures')}",
    )
    add_check(
        checks, "contract:current_v2_contract_passed_without_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and contract.get("case_id") == config.get("case_id")
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and len(contract.get("checks", [])) == 21
        and all(item.get("status") == "PASS" for item in contract.get("checks", [])),
        f"contract={contract.get('contract_status')} checks={len(contract.get('checks', []))}",
    )
    snapshot_inputs = snapshot.get("inputs", {})
    snapshot_valid = bool(snapshot_inputs) and all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in snapshot_inputs.values()
    )
    add_check(
        checks, "provenance:input_snapshot_paths_and_hashes_match",
        snapshot.get("case_id") == config.get("case_id")
        and snapshot.get("formal_contract") == config
        and snapshot_valid
        and report.get("input_snapshot") == outputs["config_snapshot"],
        f"inputs={len(snapshot_inputs)} valid={snapshot_valid}",
    )
    runs = solver_log.get("runs", [])
    records = [record for run in runs for record in run.get("solver_records", [])]
    add_check(
        checks, "solver:four_devices_164_dc_all_converged",
        [float(run["dit_cm2_ev"]) for run in runs] == values
        and [len(run.get("solver_records", [])) for run in runs] == [41, 41, 41, 41]
        and len(records) == 164
        and all(run.get("status") == "PASS" for run in runs)
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors")
        and float(solver_log.get("wall_seconds", math.inf))
        <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"runs={len(runs)} records={len(records)} wall={solver_log.get('wall_seconds')}",
    )
    summaries = report.get("family_summaries", [])
    topology_counts = [
        (int(row["node_count_with_interface_duplicates"]), int(row["element_count"]))
        for row in summaries
    ]
    add_check(
        checks, "topology:single_variable_devices_and_interface_equations_match",
        len(summaries) == 4
        and [float(row["dit_cm2_ev"]) for row in summaries] == values
        and len(set(topology_counts)) == 1
        and all(
            row["regions"] == sorted(acceptance["required_regions"])
            and row["contacts"] == sorted(acceptance["required_contacts"])
            and row["interfaces"] == sorted(acceptance["required_interfaces"])
            and row["bottom_interface_equations"]
            == sorted(acceptance["require_active_bottom_interface_equations"])
            and row["top_interface_equations"]
            == sorted(acceptance["require_inactive_top_interface_equations"])
            and int(row["forward_reported_point_count"]) == 31
            and int(row["state_count"]) == 1
            for row in summaries
        ),
        f"topologies={topology_counts}",
    )
    required_curve_fields = {
        "dit_cm2_ev", "is_zero_control", "family_id", "sweep_direction", "stage_id",
        "primary_gate_v", "fixed_secondary_gate_v", "vbg_v", "vtg_v", "vds_v",
        "source_current_a_per_cm", "drain_current_a_per_cm", "relative_current_imbalance",
        "center_channel_potential_v", "center_channel_electron_density_cm3", "converged",
    }
    grid = primary_grid(config)
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_dit(curve_rows, value)] == grid
        for value in values
    )
    one_variable = all(
        row["family_id"] == "top_primary"
        and row["sweep_direction"] == "forward"
        and row["stage_id"] == "T03_P2_DIT_FORMAL"
        and same_voltage(row["fixed_secondary_gate_v"], 0.0)
        and same_voltage(row["vbg_v"], 0.0)
        and same_voltage(row["vds_v"], 0.01)
        for row in curve_rows
    )
    add_check(
        checks, "curves:schemas_counts_grid_and_controls_are_exact",
        required_curve_fields <= set(curve_fields)
        and len(curve_rows) == 124 and grids_valid and one_variable
        and len(report.get("family_points", [])) == len(curve_rows),
        f"fields={len(curve_fields)} rows={len(curve_rows)} grids={grids_valid}",
    )
    maximum_imbalance = max(float(row["relative_current_imbalance"]) for row in curve_rows)
    current_valid = all(
        float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and row["converged"] == "True"
        for row in curve_rows
    )
    monotonic = all(
        all(higher > lower for lower, higher in zip(currents, currents[1:]))
        for currents in (
            [abs(float(row["drain_current_a_per_cm"])) for row in curve_for_dit(curve_rows, value)]
            for value in values
        )
    )
    add_check(
        checks, "curves:current_is_finite_conserved_and_monotonic",
        current_valid and monotonic
        and maximum_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"current={current_valid} monotonic={monotonic} imbalance={maximum_imbalance:.6e}",
    )

    recomputed = [
        recompute_metric(baseline, config, curve_for_dit(curve_rows, value), value)
        for value in values
    ]
    zero_vth = float(recomputed[0]["vth_proxy_v"])
    for metric in recomputed:
        metric["delta_vth_proxy_v"] = float(metric["vth_proxy_v"]) - zero_vth
    numeric_metric_fields = [
        "interface_trap_capacitance_f_per_cm2", "constant_current_criterion_terminal_a",
        "constant_current_criterion_a_per_cm", "vth_proxy_v", "delta_vth_proxy_v",
        "vth_bracket_lower_primary_gate_v", "vth_bracket_upper_primary_gate_v",
        "vth_bracket_lower_current_a_per_cm", "vth_bracket_upper_current_a_per_cm",
        "gm_evaluation_primary_gate_v", "gm_proxy_s_per_cm", "gm_proxy_terminal_s",
        "maximum_sampled_gm_s_per_cm", "maximum_sampled_gm_primary_gate_v",
        "ss_window_lower_current_a_per_cm", "ss_window_upper_current_a_per_cm",
        "ss_fit_slope_v_per_dec", "ss_fit_intercept_v", "ss_fit_r_squared",
        "ss_proxy_mv_per_dec", "ioff_evaluation_top_gate_v", "ioff_proxy_a_per_cm",
        "ioff_proxy_terminal_a",
    ]
    metrics_match = len(metric_rows) == len(recomputed) == 4
    for persisted, calculated, value in zip(metric_rows, recomputed, values, strict=True):
        metrics_match = metrics_match and same_dit(persisted["dit_cm2_ev"], value)
        metrics_match = metrics_match and int(persisted["ss_fit_sample_count"]) == int(
            calculated["ss_fit_sample_count"]
        )
        metrics_match = metrics_match and all(
            close(float(persisted[field]), float(calculated[field]))
            for field in numeric_metric_fields
        )
        metrics_match = metrics_match and persisted["parameter_claim_status"] == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
    add_check(
        checks, "metrics:vth_gm_ss_ioff_independently_recomputed",
        metrics_match and set(numeric_metric_fields) <= set(metric_fields),
        f"metrics={len(metric_rows)} fields={len(metric_fields)}",
    )
    ss_r2 = [float(row["ss_fit_r_squared"]) for row in metric_rows]
    ss_counts = [int(row["ss_fit_sample_count"]) for row in metric_rows]
    add_check(
        checks, "metrics:v2_fixed_one_decade_ss_window_is_well_conditioned",
        all(close(row["ss_window_lower_current_a_per_cm"], 1e-7) for row in metric_rows)
        and all(close(row["ss_window_upper_current_a_per_cm"], 1e-6) for row in metric_rows)
        and ss_counts == [4, 5, 6, 8]
        and all(value >= float(acceptance["minimum_ss_fit_r_squared"]) for value in ss_r2),
        f"samples={ss_counts} R2={ss_r2}",
    )
    vth_values = [float(row["vth_proxy_v"]) for row in metric_rows]
    ss_values = [float(row["ss_proxy_mv_per_dec"]) for row in metric_rows]
    ioff_values = [float(row["ioff_proxy_a_per_cm"]) for row in metric_rows]
    gm_values = [float(row["gm_proxy_s_per_cm"]) for row in metric_rows]
    directional = report.get("directional_diagnostics", {})
    add_check(
        checks, "diagnostics:directions_are_recomputed_and_not_completion_gates",
        all(higher > lower for lower, higher in zip(vth_values, vth_values[1:]))
        and all(higher > lower for lower, higher in zip(ss_values, ss_values[1:]))
        and all(higher > lower for lower, higher in zip(ioff_values, ioff_values[1:]))
        and all(higher < lower for lower, higher in zip(gm_values, gm_values[1:]))
        and directional.get("completion_gate") is False
        and directional.get("vth_proxy_strictly_increases_with_dit") is True
        and directional.get("ss_proxy_strictly_increases_with_dit") is True,
        f"VTH={vth_values} SS={ss_values} Ioff={ioff_values} gm={gm_values}",
    )

    zero_curve = curve_for_dit(curve_rows, 0.0)
    t02_curve = sorted(
        [
            row for row in t02_report["family_points"]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_voltage(row["fixed_secondary_gate_v"], 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )
    comparisons: list[dict[str, float]] = []
    for current, reference in zip(zero_curve, t02_curve, strict=True):
        comparisons.append({
            "primary_gate_v": float(current["primary_gate_v"]),
            "current_relative_difference": relative_difference(
                current["drain_current_a_per_cm"], reference["drain_current_a_per_cm"]
            ),
            "center_channel_potential_difference_v": abs(
                float(current["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
            "center_density_relative_difference": relative_difference(
                current["center_channel_electron_density_cm3"],
                reference["center_channel_electron_density_cm3"],
            ),
        })
    reference_csv_matches = len(reference_rows) == len(comparisons) == 31 and all(
        same_voltage(row["primary_gate_v"], calculated["primary_gate_v"])
        and close(row["current_relative_difference"], calculated["current_relative_difference"])
        and close(
            row["center_channel_potential_difference_v"],
            calculated["center_channel_potential_difference_v"],
        )
        and close(
            row["center_density_relative_difference"],
            calculated["center_density_relative_difference"],
        )
        for row, calculated in zip(reference_rows, comparisons, strict=True)
    )
    reference_summary = report.get("zero_dit_t02_c_reproduction", {})
    add_check(
        checks, "regression:zero_dit_t02_c_reproduction_is_independent_and_exact",
        reference_csv_matches
        and len(reference_fields) == 10
        and max(item["current_relative_difference"] for item in comparisons)
        <= float(acceptance["maximum_zero_dit_t02_c_current_relative_difference"])
        and max(item["center_channel_potential_difference_v"] for item in comparisons)
        <= float(acceptance["maximum_zero_dit_t02_c_center_potential_difference_v"])
        and max(item["center_density_relative_difference"] for item in comparisons)
        <= float(acceptance["maximum_zero_dit_t02_c_center_density_relative_difference"])
        and all(close(reference_summary[key], 0.0) for key in (
            "maximum_current_relative_difference", "maximum_center_potential_difference_v",
            "maximum_center_density_relative_difference", "vth_difference_v", "gm_relative_difference",
        )),
        json.dumps(reference_summary, sort_keys=True),
    )

    entries = manifest.get("entries", [])
    state_artifacts_valid = len(entries) == 4 and all(
        (ROOT / entry["node_csv"]).is_file()
        and entry["node_csv_sha256"] == sha256(ROOT / entry["node_csv"])
        and (ROOT / entry["element_csv"]).is_file()
        and entry["element_csv_sha256"] == sha256(ROOT / entry["element_csv"])
        and len(entry["vtk_files"]) == 6
        and all(
            (ROOT / item["path"]).is_file()
            and item["sha256"] == sha256(ROOT / item["path"])
            for item in entry["vtk_files"]
        )
        for entry in entries
    )
    add_check(
        checks, "states:manifest_csv_and_24_vtk_hashes_match",
        manifest.get("case_id") == config.get("case_id")
        and manifest.get("entry_count") == 4
        and [entry["state_id"] for entry in entries] == acceptance["required_state_ids"]
        and state_artifacts_valid
        and len(state_rows) == 4
        and {"dit_cm2_ev", "state_id", "vbg_v", "vtg_v", "stage_id"} <= set(state_fields),
        f"entries={len(entries)} vtk={sum(len(entry.get('vtk_files', [])) for entry in entries)}",
    )
    state_values = [float(row["dit_cm2_ev"]) for row in state_rows]
    state_currents = [float(row["absolute_drain_current_a_per_cm"]) for row in state_rows]
    state_response = relative_difference(state_currents[0], state_currents[-1])
    add_check(
        checks, "states:common_bias_controls_and_response_are_recomputed",
        state_values == values
        and all(same_voltage(row["vbg_v"], 0.0) and same_voltage(row["vtg_v"], 0.3) for row in state_rows)
        and all(row["stage_id"] == "T03_P2_DIT_FORMAL" for row in state_rows)
        and state_response >= float(acceptance["minimum_max_dit_common_state_current_relative_response"])
        and close(
            state_response,
            report["summary_metrics"]["maximum_dit_common_state_current_relative_response"],
        ),
        f"currents={state_currents} response={state_response:.6e}",
    )

    artifact_hashes_valid = all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in report.get("artifacts", {}).values()
    )
    figures = report.get("figures", [])
    figure_paths = [ROOT / item["path"] for item in figures]
    figure_hashes_valid = len(figures) == 2 and all(
        path.is_file() and item["sha256"] == sha256(path)
        for path, item in zip(figure_paths, figures, strict=True)
    )
    dimensions = [png_dimensions(path) for path in figure_paths] if figure_hashes_valid else []
    add_check(
        checks, "artifacts:report_hashes_and_two_nontrivial_pngs_match",
        len(report.get("artifacts", {})) == 7
        and artifact_hashes_valid and figure_hashes_valid
        and all(width >= 1600 and height >= 1000 for width, height in dimensions),
        f"artifacts={len(report.get('artifacts', {}))} dimensions={dimensions}",
    )

    prior = config["prior_failed_run"]
    name_failure_report = ROOT / "results/reports/tcad_t03_p2_dit_formal_v1_failed.json"
    name_failure_dir = ROOT / "results/tcad/t03_sensitivity/p2_dit_formal_v1_failed"
    v1_report = load_json(ROOT / prior["archive_report"])
    v1_solver = load_json(ROOT / config["dependencies"]["v1_solver_log"])
    name_failure = load_json(name_failure_report)
    add_check(
        checks, "history:device_name_and_ss_linearity_failures_remain_preserved",
        name_failure_dir.is_dir() and name_failure_report.is_file()
        and name_failure.get("status") == "FAIL"
        and "runner_completed_without_exception" in name_failure.get("failures", [])
        and v1_report.get("status") == "FAIL"
        and "vth_gm_ss_and_ioff_numerical_proxies_are_extractable" in v1_report.get("failures", [])
        and len(v1_solver.get("runs", [])) == 4
        and sum(len(run.get("solver_records", [])) for run in v1_solver.get("runs", [])) == 164
        and prior["v1_observed_ss_fit_r_squared"]
        == [0.9547013581224532, 0.9708165634170878, 0.985595897703967, 0.9944438232965194],
        prior["reason"],
    )
    completion = report.get("t03_p2_completion", {})
    prohibited = " ".join(config["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks, "boundary:interface_dit_complete_but_p2_and_t03_remain_partial",
        completion.get("status") == "PARTIAL"
        and completion.get("formal_three_point_dit_sensitivity_complete") is True
        and completion.get("interface_dit_substage_complete") is True
        and completion.get("bulk_tail_and_deep_traps_complete") is False
        and completion.get("complete_p2_trap_group") is False
        and completion.get("complete_t03_five_group_sensitivity") is False
        and completion.get("bulk_trap_contract_permitted_next") is True
        and completion.get("experimental_calibration_permitted") is False
        and "complete P2" in prohibited and "complete T03" in prohibited,
        json.dumps(completion, sort_keys=True),
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_simulation_runner": True,
        "checks": checks,
        "failures": failures,
        "recomputed_metrics": {
            "vth_proxy_v": vth_values,
            "ss_proxy_mv_per_dec": ss_values,
            "ioff_proxy_a_per_cm": ioff_values,
            "gm_proxy_s_per_cm": gm_values,
            "ss_fit_sample_count": ss_counts,
            "ss_fit_r_squared": ss_r2,
            "maximum_relative_terminal_current_imbalance": maximum_imbalance,
            "maximum_dit_common_state_current_relative_response": state_response,
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    output_path = ROOT / outputs["check_report"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"T03_P2_DIT_FORMAL_CHECK_{result['status']} checks={len(checks)} "
        f"metrics={len(metric_rows)} report={output_path}"
    )
    for failure in failures:
        print(f"T03_P2_DIT_FORMAL_CHECK_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
