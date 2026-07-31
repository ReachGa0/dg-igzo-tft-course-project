#!/usr/bin/env python3
"""Independently validate persisted T02-C bidirectional dual-gate evidence."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t02_c_bidirectional.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        return rows, list(reader.fieldnames or [])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_value(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def close(left: float, right: float, *, rel_tol: float = 1.0e-10, abs_tol: float = 1.0e-15) -> bool:
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
        raise ValueError("T02-C primary grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def curve(
    rows: list[dict[str, str]], family_id: str, secondary_v: float, direction: str
) -> list[dict[str, str]]:
    return sorted(
        [
            row
            for row in rows
            if row["family_id"] == family_id
            and row["sweep_direction"] == direction
            and same_value(float(row["fixed_secondary_gate_v"]), secondary_v)
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
        (target - xs[index])
        * (ys[index + 1] - ys[index])
        / (xs[index + 1] - xs[index])
    )


def threshold_and_gm(
    baseline: dict[str, Any], config: dict[str, Any], rows: list[dict[str, str]]
) -> dict[str, float]:
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
    width_cm = float(baseline["device"]["width_cm"])
    if not same_value(terminal_criterion / width_cm, criterion):
        raise ValueError("T02-C threshold criteria disagree")
    voltages = [float(row["primary_gate_v"]) for row in rows]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
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
        (math.log10(criterion) - math.log10(max(lower_current, 1.0e-300)))
        * (upper_voltage - lower_voltage)
        / (
            math.log10(max(upper_current, 1.0e-300))
            - math.log10(max(lower_current, 1.0e-300))
        )
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
    return {
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


def regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    variance = sum((value - mean_x) ** 2 for value in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance
    intercept = mean_y - slope * mean_x
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - mean_y) ** 2 for y in ys)
    return slope, intercept, 1.0 if total == 0.0 else 1.0 - residual / total


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
            elif not close(float(report_row[field]), float(csv_value), rel_tol=1.0e-12):
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
    channel = [row for row in rows if row["region"] == "channel"]
    nearest = min(
        channel,
        key=lambda row: (float(row["x_cm"]) - target_x) ** 2
        + (float(row["y_cm"]) - target_y) ** 2,
    )
    return {
        "potential_v": float(nearest["potential_v"]),
        "electron_density_cm3": float(nearest["electron_density_cm3"]),
    }


def find_forward_bias(
    family_rows: list[dict[str, str]], entry: dict[str, Any]
) -> dict[str, str]:
    return next(
        row
        for row in family_rows
        if row["sweep_direction"] == "forward"
        and row["family_id"] == entry["source_family"]
        and same_value(float(row["vbg_v"]), float(entry["vbg_v"]))
        and same_value(float(row["vtg_v"]), float(entry["vtg_v"]))
    )


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report_path = ROOT / outputs["report"]
    contract_path = ROOT / outputs["contract_report"]
    family_path = ROOT / outputs["family_csv"]
    metric_path = ROOT / outputs["metric_csv"]
    reverse_path = ROOT / outputs["reverse_comparison_csv"]
    reciprocal_path = ROOT / outputs["reciprocal_comparison_csv"]
    state_summary_path = ROOT / outputs["state_summary_csv"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    solver_log_path = ROOT / outputs["solver_log"]
    baseline_path = ROOT / config["dependencies"]["t01_baseline_config"]
    t02_a_report_path = ROOT / config["dependencies"]["t02_a_report"]
    t02_b_report_path = ROOT / config["dependencies"]["t02_b_report"]
    t02_b_check_path = ROOT / config["dependencies"]["t02_b_check_report"]

    report = load_json(report_path)
    contract = load_json(contract_path)
    baseline = load_json(baseline_path)
    t02_a_report = load_json(t02_a_report_path)
    t02_b_report = load_json(t02_b_report_path)
    t02_b_check = load_json(t02_b_check_path)
    solver_log = load_json(solver_log_path)
    state_manifest = load_json(state_manifest_path)
    family_rows, family_fields = load_csv(family_path)
    metric_rows, metric_fields = load_csv(metric_path)
    reverse_rows, reverse_fields = load_csv(reverse_path)
    reciprocal_rows, reciprocal_fields = load_csv(reciprocal_path)
    state_summary_rows, state_summary_fields = load_csv(state_summary_path)
    acceptance = config["acceptance"]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T02-C"
        and report.get("evidence_level") == "E2",
        f"status={report.get('status')} case={report.get('case_id')} stage={report.get('stage')}",
    )

    contract_checks = contract.get("checks", [])
    add_check(
        checks,
        "contract:static_gate_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and len(contract_checks) == 21
        and all(check.get("status") == "PASS" for check in contract_checks)
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH),
        f"checks={len(contract_checks)} simulation={contract.get('simulation_status')}",
    )

    snapshot_path = ROOT / report["input_snapshot"]
    snapshot = load_json(snapshot_path)
    snapshot_inputs_valid = all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in snapshot["inputs"].values()
    )
    add_check(
        checks,
        "inputs:snapshot_hashes_match",
        snapshot.get("case_id") == config["case_id"]
        and snapshot_inputs_valid
        and snapshot["inputs"]["t02_c_config"]["sha256"] == sha256(CONFIG_PATH),
        f"snapshot={report['input_snapshot']} inputs={len(snapshot.get('inputs', {}))}",
    )

    add_check(
        checks,
        "dependencies:t02_a_and_t02_b_evidence_remains_pass",
        t02_a_report.get("status") == "PASS"
        and t02_b_report.get("status") == "PASS"
        and t02_b_check.get("status") == "PASS"
        and not t02_b_check.get("failures")
        and t02_b_report.get("t02_b_completion", {}).get(
            "t02_c_bidirectional_family_permitted_next"
        ) is True,
        f"T02-A={t02_a_report.get('status')} T02-B={t02_b_report.get('status')} independent={t02_b_check.get('status')}",
    )

    runs = solver_log.get("runs", [])
    solver_records = [record for run in runs for record in run.get("solver_records", [])]
    solve_counts = [len(run.get("solver_records", [])) for run in runs]
    add_check(
        checks,
        "solver:six_fresh_families_and_all_dc_converged",
        len(runs) == int(acceptance["required_forward_family_count"])
        and solve_counts == [44, 71, 44, 44, 71, 44]
        and len(solver_records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in solver_records)
        and not solver_log.get("errors"),
        f"runs={len(runs)} counts={solve_counts} records={len(solver_records)}",
    )

    enabled_topology = next(
        item for item in t02_a_report["topology"] if item["top_coupling_enabled"]
    )
    family_summaries = report.get("family_summaries", [])
    topology_valid = all(
        summary["regions"] == sorted(acceptance["required_regions"])
        and summary["contacts"] == sorted(acceptance["required_contacts"])
        and summary["interfaces"] == sorted(acceptance["required_interfaces"])
        and summary["node_count_with_interface_duplicates"]
        == enabled_topology["node_count_with_interface_duplicates"]
        and summary["element_count"] == enabled_topology["element_count"]
        for summary in family_summaries
    )
    add_check(
        checks,
        "topology:all_families_match_t02_a_enabled_domain",
        len(family_summaries) == 6 and topology_valid,
        f"families={len(family_summaries)} nodes={enabled_topology['node_count_with_interface_duplicates']} elements={enabled_topology['element_count']}",
    )

    text_fields = {
        "family_id", "primary_gate", "secondary_gate", "sweep_direction",
        "mesh_level", "stage_id", "mode_id",
    }
    grid = primary_grid(config)
    secondary_values = [
        float(value) for value in acceptance["required_fixed_secondary_gate_values_v"]
    ]
    forward_count = sum(row["sweep_direction"] == "forward" for row in family_rows)
    reverse_count = sum(row["sweep_direction"] == "reverse" for row in family_rows)
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve(family_rows, family, secondary, "forward")]
        == grid
        for family in acceptance["required_family_ids"]
        for secondary in secondary_values
    ) and all(
        [float(row["primary_gate_v"]) for row in curve(family_rows, family, 0.0, "reverse")]
        == grid
        for family in acceptance["required_family_ids"]
    )
    add_check(
        checks,
        "bias:persisted_family_grid_and_report_match",
        len(family_fields) == 23
        and len(family_rows) == int(acceptance["required_total_reported_point_count"])
        and forward_count == int(acceptance["required_forward_reported_point_count"])
        and reverse_count == int(acceptance["required_reverse_reported_point_count"])
        and grids_valid
        and report_csv_rows_match(report["family_points"], family_rows, text_fields),
        f"rows={len(family_rows)} forward={forward_count} reverse={reverse_count} fields={len(family_fields)}",
    )

    max_imbalance = max(float(row["relative_current_imbalance"]) for row in family_rows)
    directional = all(
        float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and row["converged"].lower() == "true"
        for row in family_rows
    )
    add_check(
        checks,
        "current:finite_directional_and_conserved",
        directional
        and max_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"])
        and close(
            max_imbalance,
            report["summary_metrics"]["maximum_relative_terminal_current_imbalance"],
            rel_tol=1.0e-12,
        ),
        f"maximum_relative_imbalance={max_imbalance:.6e}",
    )

    max_drop = 0.0
    strict_primary = True
    strict_secondary = True
    for family in acceptance["required_family_ids"]:
        curve_maps: dict[float, dict[float, float]] = {}
        for secondary in secondary_values:
            rows = curve(family_rows, family, secondary, "forward")
            currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
            curve_maps[secondary] = {
                float(row["primary_gate_v"]): current for row, current in zip(rows, currents)
            }
            for lower, higher in zip(currents, currents[1:]):
                strict_primary = strict_primary and higher > lower
                max_drop = max(
                    max_drop,
                    max(0.0, (lower - higher) / max(lower, higher, 1.0e-300)),
                )
        for primary in grid:
            values = [curve_maps[value][primary] for value in secondary_values]
            strict_secondary = strict_secondary and all(
                higher > lower for lower, higher in zip(values, values[1:])
            )
    add_check(
        checks,
        "current:primary_and_secondary_ordering_recomputed",
        strict_primary
        and strict_secondary
        and max_drop <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"primary={strict_primary} secondary={strict_secondary} max_drop={max_drop:.6e}",
    )

    recomputed_metrics: list[dict[str, Any]] = []
    metric_csv_valid = len(metric_rows) == 6 and len(metric_fields) == 21
    for family in acceptance["required_family_ids"]:
        family_metrics: list[dict[str, Any]] = []
        for secondary in secondary_values:
            values = threshold_and_gm(
                baseline, config, curve(family_rows, family, secondary, "forward")
            )
            family_metrics.append({
                "family_id": family,
                "fixed_secondary_gate_v": secondary,
                **values,
            })
        reference_vth = float(family_metrics[1]["vth_proxy_v"])
        vth_values = [float(row["vth_proxy_v"]) for row in family_metrics]
        slope, intercept, r_squared = regression(secondary_values, vth_values)
        for row in family_metrics:
            row["delta_vth_proxy_v"] = float(row["vth_proxy_v"]) - reference_vth
            row["coupling_slope_v_per_v"] = slope
            row["coupling_fit_intercept_v"] = intercept
            row["coupling_fit_r_squared"] = r_squared
            persisted = next(
                item
                for item in metric_rows
                if item["family_id"] == family
                and same_value(float(item["fixed_secondary_gate_v"]), float(row["fixed_secondary_gate_v"]))
            )
            for key, value in row.items():
                if key not in {"family_id", "fixed_secondary_gate_v"}:
                    metric_csv_valid = metric_csv_valid and close(
                        float(persisted[key]), float(value), rel_tol=1.0e-10
                    )
            metric_csv_valid = metric_csv_valid and (
                persisted["parameter_claim_status"]
                == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
            )
        recomputed_metrics.extend(family_metrics)
    metric_contract_valid = all(
        row["gm_proxy_s_per_cm"] > 0.0 for row in recomputed_metrics
    ) and all(
        family_rows_recomputed[0]["delta_vth_proxy_v"] > 0.0
        and same_value(family_rows_recomputed[1]["delta_vth_proxy_v"], 0.0)
        and family_rows_recomputed[2]["delta_vth_proxy_v"] < 0.0
        and family_rows_recomputed[0]["coupling_slope_v_per_v"] < 0.0
        and float(acceptance["minimum_absolute_coupling_slope_v_per_v"])
        <= abs(float(family_rows_recomputed[0]["coupling_slope_v_per_v"]))
        <= float(acceptance["maximum_absolute_coupling_slope_v_per_v"])
        and float(family_rows_recomputed[0]["coupling_fit_r_squared"])
        >= float(acceptance["minimum_coupling_fit_r_squared"])
        for family_rows_recomputed in (
            [row for row in recomputed_metrics if row["family_id"] == family]
            for family in acceptance["required_family_ids"]
        )
    )
    report_metric_match = report_csv_rows_match(
        report["coupling_metrics"],
        metric_rows,
        {"family_id", "primary_gate", "secondary_gate", "parameter_claim_status"},
    )
    add_check(
        checks,
        "extraction:vth_delta_vth_gm_and_coupling_recomputed",
        metric_csv_valid and metric_contract_valid and report_metric_match,
        "; ".join(
            f"{row['family_id']} sec={float(row['fixed_secondary_gate_v']):+.1f} "
            f"VTH={float(row['vth_proxy_v']):.6g} gm={float(row['gm_proxy_s_per_cm']):.6e}"
            for row in recomputed_metrics
        ),
    )

    reverse_csv_valid = len(reverse_rows) == 62 and len(reverse_fields) == 12
    reverse_max_current = 0.0
    reverse_max_vth = 0.0
    reverse_summary_by_family = {
        row["family_id"]: row for row in report["reverse_path_summaries"]
    }
    for family in acceptance["required_family_ids"]:
        forward = curve(family_rows, family, 0.0, "forward")
        backward = curve(family_rows, family, 0.0, "reverse")
        persisted = {
            round(float(row["primary_gate_v"]), 12): row
            for row in reverse_rows
            if row["family_id"] == family
        }
        for forward_row, reverse_row in zip(forward, backward):
            voltage = round(float(forward_row["primary_gate_v"]), 12)
            saved = persisted[voltage]
            forward_current = abs(float(forward_row["drain_current_a_per_cm"]))
            reverse_current = abs(float(reverse_row["drain_current_a_per_cm"]))
            difference = abs(forward_current - reverse_current) / max(
                forward_current, reverse_current, 1.0e-300
            )
            reverse_max_current = max(reverse_max_current, difference)
            reverse_csv_valid = reverse_csv_valid and close(
                float(saved["relative_current_difference"]), difference, rel_tol=1.0e-10
            )
        forward_vth = threshold_and_gm(baseline, config, forward)["vth_proxy_v"]
        reverse_vth = threshold_and_gm(baseline, config, backward)["vth_proxy_v"]
        vth_difference = abs(forward_vth - reverse_vth)
        reverse_max_vth = max(reverse_max_vth, vth_difference)
        reverse_csv_valid = reverse_csv_valid and close(
            reverse_summary_by_family[family]["absolute_vth_difference_v"],
            vth_difference,
            rel_tol=1.0e-10,
        )
    add_check(
        checks,
        "path:forward_reverse_agreement_recomputed",
        reverse_csv_valid
        and reverse_max_current
        <= float(acceptance["maximum_forward_reverse_relative_current_difference"])
        and reverse_max_vth <= float(acceptance["maximum_forward_reverse_vth_difference_v"]),
        f"rows={len(reverse_rows)} max_current_relative={reverse_max_current:.6e} max_dVTH={reverse_max_vth:.6e} V",
    )

    reciprocal_csv_valid = len(reciprocal_rows) == 93 and len(reciprocal_fields) == 15
    reciprocal_max_current = 0.0
    reciprocal_max_potential = 0.0
    reciprocal_max_density = 0.0
    for secondary in secondary_values:
        top = curve(family_rows, "top_primary", secondary, "forward")
        bottom = curve(family_rows, "bottom_primary", secondary, "forward")
        persisted = {
            round(float(row["primary_gate_v"]), 12): row
            for row in reciprocal_rows
            if same_value(float(row["fixed_secondary_gate_v"]), secondary)
        }
        for top_row, bottom_row in zip(top, bottom):
            voltage = round(float(top_row["primary_gate_v"]), 12)
            saved = persisted[voltage]
            top_current = abs(float(top_row["drain_current_a_per_cm"]))
            bottom_current = abs(float(bottom_row["drain_current_a_per_cm"]))
            current_difference = abs(top_current - bottom_current) / max(
                top_current, bottom_current, 1.0e-300
            )
            potential_difference = abs(
                float(top_row["center_channel_potential_v"])
                - float(bottom_row["center_channel_potential_v"])
            )
            top_density = float(top_row["center_channel_electron_density_cm3"])
            bottom_density = float(bottom_row["center_channel_electron_density_cm3"])
            density_difference = abs(top_density - bottom_density) / max(
                top_density, bottom_density, 1.0e-300
            )
            reciprocal_max_current = max(reciprocal_max_current, current_difference)
            reciprocal_max_potential = max(reciprocal_max_potential, potential_difference)
            reciprocal_max_density = max(reciprocal_max_density, density_difference)
            reciprocal_csv_valid = reciprocal_csv_valid and all([
                close(saved["relative_current_difference"], current_difference, rel_tol=1.0e-10),
                close(saved["center_channel_potential_difference_v"], potential_difference, rel_tol=1.0e-10),
                close(saved["center_density_relative_difference"], density_difference, rel_tol=1.0e-10),
            ])
    reciprocal_vth = max(
        abs(
            next(row for row in recomputed_metrics if row["family_id"] == "top_primary" and same_value(row["fixed_secondary_gate_v"], secondary))["vth_proxy_v"]
            - next(row for row in recomputed_metrics if row["family_id"] == "bottom_primary" and same_value(row["fixed_secondary_gate_v"], secondary))["vth_proxy_v"]
        )
        for secondary in secondary_values
    )
    reciprocal_gm = max(
        abs(
            next(row for row in recomputed_metrics if row["family_id"] == "top_primary" and same_value(row["fixed_secondary_gate_v"], secondary))["gm_proxy_s_per_cm"]
            - next(row for row in recomputed_metrics if row["family_id"] == "bottom_primary" and same_value(row["fixed_secondary_gate_v"], secondary))["gm_proxy_s_per_cm"]
        )
        / max(
            abs(next(row for row in recomputed_metrics if row["family_id"] == "top_primary" and same_value(row["fixed_secondary_gate_v"], secondary))["gm_proxy_s_per_cm"]),
            abs(next(row for row in recomputed_metrics if row["family_id"] == "bottom_primary" and same_value(row["fixed_secondary_gate_v"], secondary))["gm_proxy_s_per_cm"]),
            1.0e-300,
        )
        for secondary in secondary_values
    )
    add_check(
        checks,
        "symmetry:top_bottom_reciprocity_recomputed",
        reciprocal_csv_valid
        and reciprocal_max_current
        <= float(acceptance["maximum_reciprocal_top_bottom_relative_current_difference"])
        and reciprocal_max_potential
        <= float(acceptance["maximum_reciprocal_top_bottom_center_potential_difference_v"])
        and reciprocal_max_density
        <= float(acceptance["maximum_reciprocal_top_bottom_center_density_relative_difference"])
        and reciprocal_vth
        <= float(acceptance["maximum_reciprocal_top_bottom_vth_difference_v"])
        and reciprocal_gm
        <= float(acceptance["maximum_reciprocal_top_bottom_gm_relative_difference"]),
        f"rows={len(reciprocal_rows)} current={reciprocal_max_current:.6e} potential={reciprocal_max_potential:.6e} density={reciprocal_max_density:.6e} dVTH={reciprocal_vth:.6e} dgm={reciprocal_gm:.6e}",
    )

    central_top = curve(family_rows, "top_primary", 0.0, "forward")
    central_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in central_top
    }
    reference_by_voltage = {
        round(float(row["vtg_v"]), 12): row for row in t02_b_report["bias_points"]
    }
    anchor_current = 0.0
    anchor_potential = 0.0
    for voltage in [float(value) for value in acceptance["required_t02_b_anchor_vtg_values_v"]]:
        reproduced = central_by_voltage[round(voltage, 12)]
        reference = reference_by_voltage[round(voltage, 12)]
        reproduced_current = abs(float(reproduced["drain_current_a_per_cm"]))
        reference_current = abs(float(reference["drain_current_a_per_cm"]))
        anchor_current = max(
            anchor_current,
            abs(reproduced_current - reference_current)
            / max(reproduced_current, reference_current, 1.0e-300),
        )
        anchor_potential = max(
            anchor_potential,
            abs(
                float(reproduced["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
        )
    add_check(
        checks,
        "regression:t02_b_four_anchors_reproduced",
        anchor_current <= float(acceptance["maximum_t02_b_anchor_relative_current_difference"])
        and anchor_potential <= float(acceptance["maximum_t02_b_anchor_potential_difference_v"]),
        f"max_current_relative={anchor_current:.6e} max_potential={anchor_potential:.6e} V",
    )

    state_entries = state_manifest.get("entries", [])
    state_summary_by_id = {row["state_id"]: row for row in state_summary_rows}
    required_element_fields = set(acceptance["required_state_fields"])
    state_files_valid = len(state_entries) == 6 and len(state_summary_rows) == 6
    state_curve_match = True
    for entry in state_entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        node_rows, node_fields = load_csv(node_path)
        element_rows, element_fields = load_csv(element_path)
        center = nearest_channel_state(node_rows, baseline)
        matching_bias = find_forward_bias(family_rows, entry)
        saved_summary = state_summary_by_id[entry["state_id"]]
        state_files_valid = state_files_valid and all([
            node_path.is_file(),
            element_path.is_file(),
            entry["node_csv_sha256"] == sha256(node_path),
            entry["element_csv_sha256"] == sha256(element_path),
            len(node_rows) == int(entry["node_row_count"]),
            len(element_rows) == int(entry["channel_element_count"]),
            set(row["region"] for row in node_rows) == set(acceptance["required_regions"]),
            required_element_fields.issubset(set(node_fields) | set(element_fields)),
            int(entry["vtk_file_count"]) == int(acceptance["required_vtk_file_count_per_state"]),
            len(entry["vtk_files"]) == int(acceptance["required_vtk_file_count_per_state"]),
            all((ROOT / item["path"]).is_file() and item["sha256"] == sha256(ROOT / item["path"]) for item in entry["vtk_files"]),
            close(center["potential_v"], entry["center_channel_potential_v"], rel_tol=1.0e-12),
            close(center["electron_density_cm3"], entry["center_channel_electron_density_cm3"], rel_tol=1.0e-12, abs_tol=1.0e-300),
            saved_summary["state_id"] == entry["state_id"],
            int(saved_summary["vtk_file_count"]) == int(entry["vtk_file_count"]),
        ])
        state_curve_match = state_curve_match and all([
            close(entry["absolute_drain_current_a_per_cm"], abs(float(matching_bias["drain_current_a_per_cm"])), rel_tol=1.0e-12),
            close(entry["center_channel_potential_v"], matching_bias["center_channel_potential_v"], rel_tol=1.0e-12),
            close(entry["center_channel_electron_density_cm3"], matching_bias["center_channel_electron_density_cm3"], rel_tol=1.0e-12, abs_tol=1.0e-300),
        ])
        state_files_valid = state_files_valid and all(
            math.isfinite(float(row[field]))
            for row in element_rows
            for field in required_element_fields
            if field in element_fields
        )
    add_check(
        checks,
        "state:six_node_element_vtk_outputs_recomputed",
        [entry["state_id"] for entry in state_entries] == acceptance["required_state_ids"]
        and len(state_summary_fields) == 26
        and state_files_valid
        and state_curve_match,
        f"states={[entry['state_id'] for entry in state_entries]} summaries={len(state_summary_rows)}",
    )

    state_by_id = {entry["state_id"]: entry for entry in state_entries}
    current_groups = [
        float(state_by_id["dual_negative_off_proxy"]["absolute_drain_current_a_per_cm"]),
        statistics.fmean([
            float(state_by_id["top_positive_bottom_negative_asymmetry"]["absolute_drain_current_a_per_cm"]),
            float(state_by_id["bottom_positive_top_negative_asymmetry"]["absolute_drain_current_a_per_cm"]),
        ]),
        statistics.fmean([
            float(state_by_id["top_threshold_region_proxy"]["absolute_drain_current_a_per_cm"]),
            float(state_by_id["bottom_threshold_region_proxy"]["absolute_drain_current_a_per_cm"]),
        ]),
        float(state_by_id["dual_positive_on_proxy"]["absolute_drain_current_a_per_cm"]),
    ]
    density_groups = [
        float(state_by_id["dual_negative_off_proxy"]["center_channel_electron_density_cm3"]),
        statistics.fmean([
            float(state_by_id["top_positive_bottom_negative_asymmetry"]["center_channel_electron_density_cm3"]),
            float(state_by_id["bottom_positive_top_negative_asymmetry"]["center_channel_electron_density_cm3"]),
        ]),
        statistics.fmean([
            float(state_by_id["top_threshold_region_proxy"]["center_channel_electron_density_cm3"]),
            float(state_by_id["bottom_threshold_region_proxy"]["center_channel_electron_density_cm3"]),
        ]),
        float(state_by_id["dual_positive_on_proxy"]["center_channel_electron_density_cm3"]),
    ]
    add_check(
        checks,
        "state:representative_current_and_density_ordering",
        all(higher > lower for lower, higher in zip(current_groups, current_groups[1:]))
        and all(higher > lower for lower, higher in zip(density_groups, density_groups[1:])),
        f"currents={current_groups} densities={density_groups}",
    )

    artifact_hashes_valid = all(
        (ROOT / item["path"]).is_file()
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in report["artifacts"].values()
    )
    figure_valid = True
    figure_details: list[tuple[int, int, int]] = []
    for figure in report["figures"]:
        path = ROOT / figure["path"]
        width, height = png_dimensions(path)
        figure_details.append((width, height, path.stat().st_size))
        figure_valid = figure_valid and (
            figure["sha256"] == sha256(path)
            and width >= 1000
            and height >= 600
            and path.stat().st_size > 0
        )
    add_check(
        checks,
        "outputs:artifact_hashes_and_png_dimensions_match",
        artifact_hashes_valid and figure_valid and len(report["figures"]) == 2,
        f"artifacts={len(report['artifacts'])} figures={figure_details}",
    )

    runner_checks = report.get("checks", {})
    completion = report.get("t02_c_completion", {})
    add_check(
        checks,
        "runner:t02_gate_and_evidence_boundary_pass",
        len(runner_checks) == 15
        and all(value["status"] == "PASS" for value in runner_checks.values())
        and completion.get("status") == "PASS"
        and completion.get("complete_t02_numerical_stage_gate") == "PASS"
        and completion.get("t02_complete") is True
        and completion.get("t03_controlled_sensitivity_permitted_next") is True
        and completion.get("experimental_calibration_permitted") is False
        and completion.get("physical_parameter_validation_permitted") is False
        and "numerical proxies" in report["limitations"][0]
        and any(
            "experimentally validated" in claim
            for claim in report["evidence_boundary"]["prohibited_claims"]
        ),
        f"runner_checks={len(runner_checks)} complete={completion.get('t02_complete')} next={completion.get('t03_controlled_sensitivity_permitted_next')}",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    check_report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "checks": checks,
        "failures": failures,
        "recomputed_metrics": {
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_monotonic_relative_current_drop": max_drop,
            "maximum_forward_reverse_relative_current_difference": reverse_max_current,
            "maximum_forward_reverse_vth_difference_v": reverse_max_vth,
            "maximum_reciprocal_top_bottom_relative_current_difference": reciprocal_max_current,
            "maximum_reciprocal_top_bottom_center_potential_difference_v": reciprocal_max_potential,
            "maximum_reciprocal_top_bottom_center_density_relative_difference": reciprocal_max_density,
            "maximum_reciprocal_top_bottom_vth_difference_v": reciprocal_vth,
            "maximum_reciprocal_top_bottom_gm_relative_difference": reciprocal_gm,
            "maximum_t02_b_anchor_relative_current_difference": anchor_current,
            "maximum_t02_b_anchor_potential_difference_v": anchor_potential,
            "coupling_metrics": recomputed_metrics,
        },
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        json.dumps(check_report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T02_C_BIDIRECTIONAL_CHECK_{check_report['status']} "
        f"checks={len(checks)} report={check_path}"
    )
    for failure in failures:
        print(
            f"T02_C_BIDIRECTIONAL_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
