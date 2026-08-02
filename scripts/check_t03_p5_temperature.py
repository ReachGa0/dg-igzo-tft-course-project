#!/usr/bin/env python3
"""Independently validate persisted T03-P5 temperature evidence."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p5_temperature.json"


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


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(
        abs(float(left)), abs(float(right)), 1.0e-300
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
        raise ValueError("T03-P5 primary grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def curve_for_temperature(
    rows: list[dict[str, str]], temperature_k: float
) -> list[dict[str, str]]:
    return sorted(
        [
            row
            for row in rows
            if same_value(float(row["temperature_k"]), temperature_k)
        ],
        key=lambda row: float(row["primary_gate_v"]),
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


def voltage_at_current(rows: list[dict[str, str]], target_current: float) -> float:
    voltages = [float(row["primary_gate_v"]) for row in rows]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
    index = next(
        index for index in range(len(currents) - 1)
        if currents[index] < target_current < currents[index + 1]
    )
    return voltages[index] + (
        (math.log10(target_current) - math.log10(currents[index]))
        * (voltages[index + 1] - voltages[index])
        / (math.log10(currents[index + 1]) - math.log10(currents[index]))
    )


def extract_metric(
    baseline: dict[str, Any], config: dict[str, Any], temperature_k: float,
    rows: list[dict[str, str]],
) -> dict[str, float]:
    width_cm = float(baseline["device"]["width_cm"])
    criterion = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "expected_current_per_width_a_per_cm"
        ]
    )
    terminal_criterion = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "expected_terminal_current_a"
        ]
    )
    voltages = [float(row["primary_gate_v"]) for row in rows]
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
    peak = max(range(len(gm_values)), key=lambda index: gm_values[index])

    ss_method = config["extraction_methods"]["ss_proxy"]
    ss_lower = float(ss_method["lower_current_a_per_cm"])
    ss_upper = float(ss_method["upper_current_a_per_cm"])
    samples: dict[float, float] = {
        round(math.log10(ss_lower), 14): voltage_at_current(rows, ss_lower),
        round(math.log10(ss_upper), 14): voltage_at_current(rows, ss_upper),
    }
    for row in rows:
        current = abs(float(row["drain_current_a_per_cm"]))
        if ss_lower < current < ss_upper:
            samples[round(math.log10(current), 14)] = float(row["primary_gate_v"])
    log_currents = sorted(samples)
    ss_voltages = [samples[value] for value in log_currents]
    ss_slope, ss_intercept, ss_r_squared = regression(log_currents, ss_voltages)

    low_v = float(
        config["extraction_methods"]["low_gate_current_proxy"][
            "evaluation_top_gate_v"
        ]
    )
    high_v = float(
        config["extraction_methods"]["high_gate_current_proxy"][
            "evaluation_top_gate_v"
        ]
    )
    low_current = abs(
        float(
            next(
                row for row in rows
                if same_value(float(row["primary_gate_v"]), low_v)
            )["drain_current_a_per_cm"]
        )
    )
    high_current = abs(
        float(
            next(
                row for row in rows
                if same_value(float(row["primary_gate_v"]), high_v)
            )["drain_current_a_per_cm"]
        )
    )
    thermal_voltage = float(
        config["temperature_model_contract"]["boltzmann_ev_per_k"]
    ) * temperature_k
    return {
        "thermal_voltage_v": thermal_voltage,
        "configured_mobility_cm2_vs": float(
            config["extraction_methods"]["configured_mobility_control"][
                "value_cm2_vs"
            ]
        ),
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
        "maximum_sampled_gm_s_per_cm": gm_values[peak],
        "maximum_sampled_gm_primary_gate_v": gm_voltages[peak],
        "ss_window_lower_current_a_per_cm": ss_lower,
        "ss_window_upper_current_a_per_cm": ss_upper,
        "ss_fit_sample_count": float(len(log_currents)),
        "ss_fit_slope_v_per_dec": ss_slope,
        "ss_fit_intercept_v": ss_intercept,
        "ss_fit_r_squared": ss_r_squared,
        "ss_proxy_mv_per_dec": 1000.0 * ss_slope,
        "low_gate_evaluation_top_gate_v": low_v,
        "low_gate_current_proxy_a_per_cm": low_current,
        "low_gate_current_proxy_terminal_a": low_current * width_cm,
        "high_gate_evaluation_top_gate_v": high_v,
        "high_gate_current_proxy_a_per_cm": high_current,
        "high_gate_current_proxy_terminal_a": high_current * width_cm,
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
    baseline = load_json(ROOT / config["dependencies"]["t01_baseline_config"])
    t02_report = load_json(ROOT / config["dependencies"]["t02_c_report"])
    contract = load_json(ROOT / outputs["contract_report"])
    report = load_json(ROOT / outputs["report"])
    snapshot = load_json(ROOT / outputs["config_snapshot"])
    solver_log = load_json(ROOT / outputs["solver_log"])
    state_manifest = load_json(ROOT / outputs["state_manifest"])
    curve_rows, curve_fields = load_csv(ROOT / outputs["curve_csv"])
    metric_rows, metric_fields = load_csv(ROOT / outputs["metric_csv"])
    reference_rows, reference_fields = load_csv(
        ROOT / outputs["reference_comparison_csv"]
    )
    state_summary_rows, state_summary_fields = load_csv(
        ROOT / outputs["state_summary_csv"]
    )
    acceptance = config["acceptance"]
    temperatures = [float(value) for value in acceptance["required_temperature_values_k"]]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "contract_and_runner:pass_chain_is_valid",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and report.get("status") == "PASS"
        and report.get("evidence_level") == "E2"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == config["stage"]
        and not report.get("failures"),
        f"contract={contract.get('contract_status')} runner={report.get('status')}",
    )
    immutable_inputs = {
        name: item
        for name, item in snapshot.get("inputs", {}).items()
        if name not in {"project_config", "experiments_config"}
    }
    add_check(
        checks,
        "inputs:immutable_snapshot_hashes_match",
        snapshot.get("case_id") == config["case_id"]
        and snapshot.get("stage") == config["stage"]
        and len(snapshot.get("inputs", {})) == 25
        and len(immutable_inputs) == 23
        and all(
            (ROOT / item["path"]).is_file()
            and item["sha256"] == sha256(ROOT / item["path"])
            for item in immutable_inputs.values()
        )
        and snapshot["inputs"]["t03_p5_config"]["sha256"] == sha256(CONFIG_PATH),
        f"inputs={len(snapshot.get('inputs', {}))} immutable={len(immutable_inputs)}",
    )
    runs = solver_log.get("runs", [])
    records = [record for run in runs for record in run.get("solver_records", [])]
    add_check(
        checks,
        "solver:three_fresh_devices_and_123_dc_solves_converged",
        [float(run["temperature_k"]) for run in runs] == temperatures
        and [len(run.get("solver_records", [])) for run in runs] == [41, 41, 41]
        and len(records) == 123
        and all(run.get("status") == "PASS" for run in runs)
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors")
        and float(solver_log["wall_seconds"])
        <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"runs={len(runs)} records={len(records)} wall={solver_log.get('wall_seconds')}",
    )
    thermal_values = [
        float(config["temperature_model_contract"]["boltzmann_ev_per_k"]) * value
        for value in temperatures
    ]
    summaries = report.get("topology_summaries", [])
    topology_counts = [
        (
            int(summary["node_count_with_interface_duplicates"]),
            int(summary["element_count"]),
        )
        for summary in summaries
    ]
    add_check(
        checks,
        "model_and_topology:only_temperature_and_vt_change",
        len(summaries) == 3
        and len(set(topology_counts)) == 1
        and all(
            close(summary["temperature_k"], temperature)
            and close(summary["thermal_voltage_v"], thermal)
            and summary["regions"] == sorted(acceptance["required_regions"])
            and summary["contacts"] == sorted(acceptance["required_contacts"])
            and summary["interfaces"] == sorted(acceptance["required_interfaces"])
            and int(summary["reported_point_count"]) == 31
            and int(summary["state_count"]) == 1
            for summary, temperature, thermal in zip(
                summaries, temperatures, thermal_values
            )
        )
        and report["temperature_model_contract"]["mobility_changed"] is False
        and report["temperature_model_contract"]["trap_model_active"] is False,
        f"topologies={topology_counts} thermal_voltage={thermal_values}",
    )
    grid = primary_grid(config)
    curve_text_fields = {
        "parameter_group_id", "changed_parameter", "family_id", "primary_gate",
        "secondary_gate", "sweep_direction", "mesh_level", "stage_id", "mode_id",
    }
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_temperature(curve_rows, value)]
        == grid
        for value in temperatures
    )
    controls_valid = all(
        row["parameter_group_id"] == "P5"
        and row["changed_parameter"] == "lattice_temperature_k"
        and row["family_id"] == "top_primary"
        and row["primary_gate"] == "top_gate"
        and row["secondary_gate"] == "bottom_gate"
        and row["sweep_direction"] == "forward"
        and row["mesh_level"] == "interface_4x"
        and row["stage_id"] == "T03_P5_TEMPERATURE"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        and same_value(float(row["vbg_v"]), 0.0)
        and same_value(float(row["vtg_v"]), float(row["primary_gate_v"]))
        and same_value(float(row["vds_v"]), 0.01)
        and close(
            float(row["thermal_voltage_v"]),
            float(config["temperature_model_contract"]["boltzmann_ev_per_k"])
            * float(row["temperature_k"]),
        )
        for row in curve_rows
    )
    add_check(
        checks,
        "curves:93_persisted_points_match_report_grid_and_controls",
        len(curve_fields) == 27
        and len(curve_rows) == 93
        and grids_valid
        and controls_valid
        and report_csv_rows_match(
            report["curve_points"], curve_rows, curve_text_fields
        ),
        f"rows={len(curve_rows)} fields={len(curve_fields)} grids={grids_valid}",
    )
    max_imbalance = max(
        float(row["relative_current_imbalance"]) for row in curve_rows
    )
    maximum_drop = 0.0
    primary_monotonic = True
    for temperature in temperatures:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in curve_for_temperature(curve_rows, temperature)
        ]
        primary_monotonic = primary_monotonic and all(
            upper > lower for lower, upper in zip(currents, currents[1:])
        )
        maximum_drop = max(
            maximum_drop,
            max(
                max(0.0, (lower - upper) / max(lower, upper, 1.0e-300))
                for lower, upper in zip(currents, currents[1:])
            ),
        )
    add_check(
        checks,
        "current:direction_conservation_and_gate_ordering_recomputed",
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
        and maximum_drop
        <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"imbalance={max_imbalance:.6e} monotonic={primary_monotonic}",
    )
    zero_current = max(
        float(summary["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"])
        for summary in summaries
    )
    zero_potential = max(
        float(summary["zero_equilibrium"]["maximum_absolute_potential_v"])
        for summary in summaries
    )
    add_check(
        checks,
        "initialization:three_zero_equilibria_are_current_free",
        zero_current
        <= float(acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"])
        and zero_potential
        <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"current={zero_current:.6e} potential={zero_potential:.6e}",
    )

    recomputed = [
        {
            "temperature_k": temperature,
            **extract_metric(
                baseline, config, temperature,
                curve_for_temperature(curve_rows, temperature),
            ),
        }
        for temperature in temperatures
    ]
    reference_vth = next(
        row["vth_proxy_v"] for row in recomputed
        if same_value(row["temperature_k"], 300.0)
    )
    for row in recomputed:
        row["delta_vth_proxy_v"] = row["vth_proxy_v"] - reference_vth
    metric_valid = len(metric_rows) == 3 and len(metric_fields) == 32
    for expected in recomputed:
        persisted = next(
            row for row in metric_rows
            if same_value(float(row["temperature_k"]), expected["temperature_k"])
        )
        metric_valid = metric_valid and all(
            close(
                float(persisted[key]), value, rel_tol=1.0e-10,
                abs_tol=1.0e-300,
            )
            for key, value in expected.items()
        )
        metric_valid = metric_valid and all([
            persisted["parameter_group_id"] == "P5",
            persisted["changed_parameter"] == "lattice_temperature_k",
            persisted["parameter_claim_status"]
            == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
        ])
    metric_text_fields = {
        "parameter_group_id", "changed_parameter", "parameter_claim_status",
    }
    endpoint_response = max(
        relative_difference(recomputed[0][key], recomputed[2][key])
        for key in (
            "vth_proxy_v", "gm_proxy_s_per_cm", "ss_proxy_mv_per_dec",
            "low_gate_current_proxy_a_per_cm",
            "high_gate_current_proxy_a_per_cm",
        )
    )
    add_check(
        checks,
        "extraction:vth_gm_ss_currents_and_endpoint_response_recomputed",
        metric_valid
        and report_csv_rows_match(
            report["sensitivity_metrics"], metric_rows, metric_text_fields
        )
        and all(
            row["gm_proxy_s_per_cm"] > 0.0
            and row["ss_proxy_mv_per_dec"] > 0.0
            and row["ss_fit_r_squared"] >= float(acceptance["minimum_ss_fit_r_squared"])
            and row["ss_fit_sample_count"]
            >= float(acceptance["minimum_augmented_ss_sample_count"])
            for row in recomputed
        )
        and endpoint_response
        >= float(acceptance["minimum_250_to_350_maximum_metric_relative_response"]),
        f"endpoint_response={endpoint_response:.6e} metrics={recomputed}",
    )

    current_reference = curve_for_temperature(curve_rows, 300.0)
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
    max_current_difference = 0.0
    max_potential_difference = 0.0
    max_density_difference = 0.0
    for current, reference, persisted in zip(
        current_reference, t02_reference, reference_rows
    ):
        current_value = abs(float(current["drain_current_a_per_cm"]))
        reference_value = abs(float(reference["drain_current_a_per_cm"]))
        density = float(current["center_channel_electron_density_cm3"])
        reference_density = float(reference["center_channel_electron_density_cm3"])
        expected = {
            "primary_gate_v": float(current["primary_gate_v"]),
            "p5_300k_abs_drain_current_a_per_cm": current_value,
            "t02_c_abs_drain_current_a_per_cm": reference_value,
            "current_relative_difference": relative_difference(
                current_value, reference_value
            ),
            "p5_300k_center_channel_potential_v": float(
                current["center_channel_potential_v"]
            ),
            "t02_c_center_channel_potential_v": float(
                reference["center_channel_potential_v"]
            ),
            "center_channel_potential_difference_v": abs(
                float(current["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
            "p5_300k_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": reference_density,
            "center_density_relative_difference": relative_difference(
                density, reference_density
            ),
        }
        reference_valid = reference_valid and all(
            close(float(persisted[key]), value, rel_tol=1.0e-12, abs_tol=1.0e-300)
            for key, value in expected.items()
        )
        max_current_difference = max(
            max_current_difference, expected["current_relative_difference"]
        )
        max_potential_difference = max(
            max_potential_difference,
            expected["center_channel_potential_difference_v"],
        )
        max_density_difference = max(
            max_density_difference, expected["center_density_relative_difference"]
        )
    recomputed_300 = recomputed[1]
    t02_metric = next(
        row for row in t02_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    vth_difference = abs(
        recomputed_300["vth_proxy_v"] - float(t02_metric["vth_proxy_v"])
    )
    gm_difference = relative_difference(
        recomputed_300["gm_proxy_s_per_cm"], float(t02_metric["gm_proxy_s_per_cm"])
    )
    saved_reference = report["t02_c_300k_reference_reproduction"]
    add_check(
        checks,
        "regression:t02_c_300k_curve_state_and_extraction_recomputed",
        reference_valid
        and max_current_difference
        <= float(acceptance["maximum_300k_t02_c_current_relative_difference"])
        and max_potential_difference
        <= float(acceptance["maximum_300k_t02_c_center_potential_difference_v"])
        and max_density_difference
        <= float(acceptance["maximum_300k_t02_c_center_density_relative_difference"])
        and vth_difference <= float(acceptance["maximum_300k_t02_c_vth_difference_v"])
        and gm_difference <= float(acceptance["maximum_300k_t02_c_gm_relative_difference"])
        and close(saved_reference["maximum_current_relative_difference"], max_current_difference)
        and close(saved_reference["maximum_center_potential_difference_v"], max_potential_difference)
        and close(saved_reference["maximum_center_density_relative_difference"], max_density_difference)
        and close(saved_reference["vth_difference_v"], vth_difference)
        and close(saved_reference["gm_relative_difference"], gm_difference),
        f"current={max_current_difference:.3e} potential={max_potential_difference:.3e} density={max_density_difference:.3e}",
    )

    entries = state_manifest.get("entries", [])
    summary_by_id = {row["state_id"]: row for row in state_summary_rows}
    states_valid = all([
        state_manifest.get("entry_count") == 3,
        len(entries) == 3,
        len(state_summary_rows) == 3,
        len(state_summary_fields) == 29,
        report["state_outputs"] == entries,
        [entry["state_id"] for entry in entries] == acceptance["required_state_ids"],
    ])
    for entry in entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        node_rows, node_fields = load_csv(node_path)
        element_rows, element_fields = load_csv(element_path)
        center = nearest_channel_state(node_rows, baseline)
        temperature = float(entry["temperature_k"])
        bias_row = next(
            row for row in curve_for_temperature(curve_rows, temperature)
            if same_value(float(row["primary_gate_v"]), float(entry["vtg_v"]))
        )
        summary = summary_by_id[entry["state_id"]]
        potential_values = [float(row["potential_v"]) for row in node_rows]
        density_values = [
            float(row["electron_density_cm3"])
            for row in node_rows if row["region"] == "channel"
        ]
        current_values = [
            float(row["electron_current_density_magnitude_a_per_cm2"])
            for row in element_rows
        ]
        states_valid = states_valid and all([
            len(node_fields) == 17,
            len(element_fields) == 35,
            len(node_rows) == int(entry["node_row_count"]),
            len(density_values) == int(entry["channel_node_count"]),
            len(element_rows) == int(entry["channel_element_count"]),
            set(row["region"] for row in node_rows)
            == set(acceptance["required_regions"]),
            all(row["stage_id"] == "T03_P5_TEMPERATURE" for row in node_rows),
            all(row["stage_id"] == "T03_P5_TEMPERATURE" for row in element_rows),
            entry["node_csv_sha256"] == sha256(node_path),
            entry["element_csv_sha256"] == sha256(element_path),
            len(entry["vtk_files"]) == 6,
            int(entry["vtk_file_count"]) == 6,
            all(
                (ROOT / item["path"]).is_file()
                and item["sha256"] == sha256(ROOT / item["path"])
                for item in entry["vtk_files"]
            ),
            same_value(float(entry["vbg_v"]), 0.0),
            same_value(float(entry["vtg_v"]), 1.0),
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
    state_text_fields = {
        "state_id", "state_label", "parameter_group_id", "source_family",
        "mesh_level", "stage_id", "node_csv", "element_csv",
    }
    add_check(
        checks,
        "states:three_node_element_and_18_vtk_outputs_recomputed",
        states_valid
        and sum(len(entry["vtk_files"]) for entry in entries) == 18
        and report_csv_rows_match(
            report["state_outputs"], state_summary_rows, state_text_fields
        ),
        f"states={[entry['state_id'] for entry in entries]}",
    )

    artifact_hashes_valid = all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in report["artifacts"].values()
    )
    figure_details: list[tuple[int, int, int]] = []
    figures_valid = len(report["figures"]) == 2
    for item in report["figures"]:
        path = ROOT / item["path"]
        width, height = png_dimensions(path)
        figure_details.append((width, height, path.stat().st_size))
        figures_valid = figures_valid and all([
            item["sha256"] == sha256(path),
            width >= 1000,
            height >= 900,
            path.stat().st_size >= 50000,
        ])
    add_check(
        checks,
        "artifacts:hashes_and_two_nontrivial_pngs_are_valid",
        artifact_hashes_valid and figures_valid,
        f"artifacts={len(report['artifacts'])} figures={figure_details}",
    )
    directional = report.get("directional_hypotheses", {})
    add_check(
        checks,
        "diagnostics:directions_are_reported_without_becoming_gates",
        directional.get("completion_gate") is False
        and len(directional.get("reported_metric_values", {})) == 5
        and "contrary or non-monotonic trend" in directional.get("failure_rule", ""),
        json.dumps(directional, sort_keys=True),
    )
    runner_checks = report.get("checks", {})
    add_check(
        checks,
        "runner:all_prefrozen_acceptance_gates_passed",
        len(runner_checks) == 14
        and all(item.get("status") == "PASS" for item in runner_checks.values())
        and not report.get("failures"),
        f"runner_checks={sum(item.get('status') == 'PASS' for item in runner_checks.values())}/{len(runner_checks)}",
    )
    run_dir = ROOT / outputs["run_directory"]
    run_bytes = sum(path.stat().st_size for path in run_dir.rglob("*") if path.is_file())
    add_check(
        checks,
        "resources:laptop_output_budget_is_met",
        run_bytes <= int(config["resource_budget"]["maximum_run_directory_bytes"]),
        f"run_directory_bytes={run_bytes}",
    )
    boundary = report.get("evidence_boundary", {})
    prohibited = " ".join(boundary.get("prohibited_claims", []))
    add_check(
        checks,
        "boundary:vt_only_teaching_scope_and_downstream_limits_are_preserved",
        "V_t-only" in boundary.get("future_run_allowed_claim", "")
        and "experimental or calibrated" in prohibited
        and "physical VTH" in prohibited
        and "compact-model" in prohibited
        and report.get("t03_p5_completion", {}).get(
            "complete_t03_five_group_sensitivity"
        ) is False
        and report.get("t03_p5_completion", {}).get(
            "m00_or_downstream_permitted"
        ) is False,
        boundary.get("future_run_allowed_claim", ""),
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    status = "PASS" if not failures else "FAIL"
    check_report = {
        "status": status,
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E3" if status == "PASS" else "E0",
        "independent_of_simulation_runner": True,
        "runner_imported": False,
        "devsim_imported": False,
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "pass_count": sum(item["status"] == "PASS" for item in checks),
            "device_count": len(runs),
            "dc_solve_count": len(records),
            "reported_point_count": len(curve_rows),
            "state_count": len(entries),
            "vtk_file_count": sum(len(entry["vtk_files"]) for entry in entries),
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_endpoint_metric_relative_response": endpoint_response,
            "run_directory_bytes": run_bytes,
        },
        "t03_p5_completion": {
            "status": status,
            "complete_p5_temperature_group": status == "PASS",
            "complete_t03_five_group_sensitivity": status == "PASS",
            "m00_contract_permitted_after_documentation": status == "PASS",
            "compact_model_simulation_permitted_before_m00_contract": False,
            "spice_circuit_layout_pex_or_hzo_permitted": False,
        },
        "allowed_claim": (
            "The frozen 2D n-IGZO teaching model has an independently reproducible "
            "three-point V_t-only temperature sensitivity and all five numerical "
            "T03 groups are complete."
            if status == "PASS"
            else "No T03-P5 or complete-T03 claim is permitted."
        ),
        "prohibited_claims": config["evidence_boundary"]["prohibited_claims"],
    }
    output_path = ROOT / outputs["check_report"]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(check_report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T03_P5_TEMPERATURE_CHECK_{status} "
        f"checks={check_report['summary']['pass_count']}/{len(checks)} "
        f"report={output_path}"
    )
    for failure in failures:
        print(
            f"T03_P5_TEMPERATURE_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
