#!/usr/bin/env python3
"""Independently validate persisted T01-D-C extraction and state artifacts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t01_d_extraction.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def csv_headers(path: Path) -> list[str]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(next(csv.reader(stream)))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def close_metric(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1.0e-10, abs_tol=1.0e-15)


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def stage_by_id(baseline: dict[str, Any], stage_id: str) -> dict[str, Any]:
    return next(stage for stage in baseline["bias_protocol"]["stages"] if stage["id"] == stage_id)


def extraction_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["extraction_grid"]
    start = float(spec["dense_start_v"])
    stop = float(spec["dense_stop_v"])
    step = float(spec["dense_step_v"])
    intervals = round((stop - start) / step)
    if not same_value(start + intervals * step, stop):
        raise ValueError("configured dense VGS grid is not integral")
    dense = [round(start + index * step, 12) for index in range(intervals + 1)]
    anchors = [round(float(value), 12) for value in spec["outer_anchor_values_v"]]
    return sorted(set(dense + anchors))


def rows_for_mesh(rows: list[dict[str, str]], mesh_level: str) -> list[dict[str, str]]:
    return sorted(
        [row for row in rows if row["mesh_level"] == mesh_level],
        key=lambda row: float(row["vgs_v"]),
    )


def point(rows: list[dict[str, str]], mesh_level: str, vgs_v: float) -> dict[str, str]:
    return next(
        row for row in rows
        if row["mesh_level"] == mesh_level and same_value(float(row["vgs_v"]), vgs_v)
    )


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    variance = sum((value - mean_x) ** 2 for value in xs)
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance
    intercept = mean_y - slope * mean_x
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - mean_y) ** 2 for y in ys)
    return slope, intercept, 1.0 if total == 0.0 else 1.0 - residual / total


def recompute_parameter_metric(
    baseline: dict[str, Any],
    config: dict[str, Any],
    transfer_rows: list[dict[str, str]],
    mesh_level: str,
) -> dict[str, float | int]:
    methods = config["extraction_methods"]
    vth_method = methods["constant_current_vth_proxy"]
    ss_method = methods["subthreshold_swing_proxy"]
    mobility_method = methods["field_effect_mobility_proxy"]
    rows = rows_for_mesh(transfer_rows, mesh_level)
    voltages = [float(row["vgs_v"]) for row in rows]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
    criterion = float(vth_method["expected_current_per_width_a_per_cm"])
    index = next(
        item for item in range(len(currents) - 1)
        if currents[item] <= criterion <= currents[item + 1]
    )
    log_lower = math.log10(currents[index])
    log_upper = math.log10(currents[index + 1])
    vth = voltages[index] + (
        (math.log10(criterion) - log_lower)
        * (voltages[index + 1] - voltages[index])
        / (log_upper - log_lower)
    )
    ss_rows = [
        row for row in rows
        if float(ss_method["minimum_abs_drain_current_a_per_cm"])
        <= abs(float(row["drain_current_a_per_cm"]))
        <= float(ss_method["maximum_abs_drain_current_a_per_cm"])
    ]
    ss_x = [float(row["vgs_v"]) for row in ss_rows]
    ss_y = [math.log10(abs(float(row["drain_current_a_per_cm"]))) for row in ss_rows]
    slope, intercept, r_squared = linear_regression(ss_x, ss_y)

    lower_vgs = float(mobility_method["vgs_lower_v"])
    upper_vgs = float(mobility_method["vgs_upper_v"])
    lower_current = abs(float(point(transfer_rows, mesh_level, lower_vgs)["drain_current_a_per_cm"]))
    upper_current = abs(float(point(transfer_rows, mesh_level, upper_vgs)["drain_current_a_per_cm"]))
    gm = (upper_current - lower_current) / (upper_vgs - lower_vgs)
    oxide = baseline["materials"]["bottom_oxide"]
    cox = (
        float(mobility_method["epsilon0_f_per_cm"])
        * float(oxide["relative_permittivity"])
        / float(oxide["physical_thickness_cm"])
    )
    mobility = (
        float(baseline["device"]["channel_length_cm"])
        * gm
        / (cox * float(config["bias_protocol"]["vds_v"]))
    )
    sampled_gm = [
        (
            voltages[item],
            (currents[item + 1] - currents[item - 1])
            / (voltages[item + 1] - voltages[item - 1]),
        )
        for item in range(1, len(rows) - 1)
    ]
    maximum_gm_vgs, maximum_gm = max(sampled_gm, key=lambda item: item[1])
    minimum_current = min(currents)
    maximum_current = max(currents)
    span = maximum_current / minimum_current
    return {
        "vth_proxy_v": vth,
        "vth_bracket_lower_vgs_v": voltages[index],
        "vth_bracket_upper_vgs_v": voltages[index + 1],
        "vth_bracket_lower_current_a_per_cm": currents[index],
        "vth_bracket_upper_current_a_per_cm": currents[index + 1],
        "ss_proxy_mv_per_dec": 1000.0 / slope,
        "ss_fit_point_count": len(ss_rows),
        "ss_fit_r_squared": r_squared,
        "ss_fit_slope_dec_per_v": slope,
        "ss_fit_intercept": intercept,
        "ss_fit_vgs_min_v": min(ss_x),
        "ss_fit_vgs_max_v": max(ss_x),
        "physical_oxide_capacitance_f_per_cm2": cox,
        "gm_at_mobility_point_s_per_cm": gm,
        "mobility_proxy_cm2_vs": mobility,
        "maximum_sampled_gm_s_per_cm": maximum_gm,
        "maximum_sampled_gm_vgs_v": maximum_gm_vgs,
        "minimum_abs_drain_current_a_per_cm": minimum_current,
        "maximum_abs_drain_current_a_per_cm": maximum_current,
        "numerical_current_span_ratio": span,
        "numerical_current_span_decades": math.log10(span),
    }


def check_artifacts() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    baseline_path = ROOT / config["input_contract"]["path"]
    contract_report_path = ROOT / config["input_contract"]["report"]
    dependency = config["dependencies"]
    mesh_config_path = ROOT / dependency["mesh_config"]
    mesh_report_path = ROOT / dependency["mesh_report"]
    db_config_path = ROOT / dependency["idvd_config"]
    db_report_path = ROOT / dependency["idvd_report"]
    baseline = load_json(baseline_path)
    contract_report = load_json(contract_report_path)
    mesh_config = load_json(mesh_config_path)
    mesh_report = load_json(mesh_report_path)
    db_config = load_json(db_config_path)
    db_report = load_json(db_report_path)
    outputs = config["outputs"]
    report = load_json(ROOT / outputs["report"])
    snapshot = load_json(ROOT / outputs["config_snapshot"])
    solver_log = load_json(ROOT / outputs["solver_log"])
    state_manifest = load_json(ROOT / outputs["state_manifest"])
    transfer_rows = load_csv(ROOT / outputs["transfer_csv"])
    mesh_rows = load_csv(ROOT / outputs["mesh_summary_csv"])
    comparison_rows = load_csv(ROOT / outputs["mesh_comparison_csv"])
    parameter_rows = load_csv(ROOT / outputs["parameter_metrics_csv"])
    state_summary_rows = load_csv(ROOT / outputs["state_summary_csv"])
    reproduction_rows = load_csv(ROOT / outputs["t01_db_reproduction_csv"])
    acceptance = config["acceptance"]
    required_meshes = list(acceptance["required_mesh_levels"])
    required_roles = list(acceptance["required_mesh_roles"])
    grid = extraction_grid(config)
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T01-D-C"
        and report.get("evidence_level") == "E2"
        and report.get("baseline_case_id") == baseline["case_id"]
        and report.get("t01_da_case_id") == mesh_report["case_id"]
        and report.get("t01_db_case_id") == db_report["case_id"],
        f"status={report.get('status')} stage={report.get('stage')}",
    )
    reproduction = report.get("reproduction", {})
    add_check(
        checks,
        "scope:authorized_stage_and_reproduction",
        report.get("executed_bias_stage_ids")
        == ["T01_A_STAGE_0", "T01_A_STAGE_1", "T01_DC_EXTRACTION"]
        and report.get("reported_bias_stage_id") == "T01_DC_EXTRACTION"
        and reproduction.get("command") == "make t01-d-extract"
        and reproduction.get("validation_command") == "make t01-d-extract-check"
        and bool(reproduction.get("python_executable"))
        and bool(reproduction.get("devsim_version"))
        and any("T02" in item for item in config["scope"]["prohibited_work"]),
        str(report.get("executed_bias_stage_ids")),
    )
    add_check(
        checks,
        "inputs:hash_locked",
        snapshot.get("extraction_config_sha256") == sha256(CONFIG_PATH)
        and snapshot.get("baseline_config_sha256") == sha256(baseline_path)
        and snapshot.get("t01_a_contract_report_sha256") == sha256(contract_report_path)
        and snapshot.get("mesh_config_sha256") == sha256(mesh_config_path)
        and snapshot.get("mesh_report_sha256") == sha256(mesh_report_path)
        and snapshot.get("idvd_config_sha256") == sha256(db_config_path)
        and snapshot.get("idvd_report_sha256") == sha256(db_report_path),
        str(report.get("input_snapshot")),
    )
    add_check(
        checks,
        "dependencies:prior_stage_gates",
        contract_report.get("contract_status") == "PASS"
        and mesh_report.get("stage") == dependency["required_mesh_stage"]
        and mesh_report.get("status") == dependency["required_mesh_status"]
        and mesh_report.get("mesh_convergence", {}).get("status")
        == dependency["required_mesh_convergence_status"]
        and db_report.get("stage") == dependency["required_idvd_stage"]
        and db_report.get("status") == dependency["required_idvd_status"]
        and db_report.get("idvd_completion", {}).get("t01_dc_stage_permitted_next") is True,
        f"T01-A={contract_report.get('contract_status')} T01-D-A={mesh_report.get('status')} T01-D-B={db_report.get('status')}",
    )

    stage1 = stage_by_id(baseline, "T01_A_STAGE_1")
    stage2 = stage_by_id(baseline, "T01_A_STAGE_2")
    levels = {
        row["id"]: float(row["refinement_factor"])
        for row in mesh_config["mesh_ladder"]["levels"]
    }
    width = float(baseline["device"]["width_cm"])
    length = float(baseline["device"]["channel_length_cm"])
    vth_method = config["extraction_methods"]["constant_current_vth_proxy"]
    contract_valid = (
        [float(value) for value in stage1["vds_values_v"]]
        == [float(value) for value in config["bias_protocol"]["low_vds_values_v"]]
        and same_value(float(stage2["vds_v"]), float(config["bias_protocol"]["vds_v"]))
        and min(grid) >= min(float(value) for value in stage2["vgs_values_v"])
        and max(grid) <= max(float(value) for value in stage2["vgs_values_v"])
        and set(float(value) for value in stage2["vgs_values_v"]) <= set(grid)
        and required_meshes
        == [config["mesh"]["production_level"], config["mesh"]["reference_level"]]
        and levels.get(required_meshes[0]) == 4.0
        and levels.get(required_meshes[1]) == 8.0
        and len(grid) == int(acceptance["required_reported_bias_points_per_mesh"])
        and same_value(
            float(vth_method["criterion_prefactor_a"]) * width / length,
            float(vth_method["expected_terminal_current_a"]),
        )
        and same_value(
            float(vth_method["expected_terminal_current_a"]) / width,
            float(vth_method["expected_current_per_width_a_per_cm"]),
        )
    )
    add_check(
        checks,
        "contract:frozen_bounds_meshes_and_methods",
        contract_valid,
        f"grid={len(grid)} VGS=[{grid[0]},{grid[-1]}] meshes={required_meshes}",
    )

    expected_records_per_mesh = (
        2
        + len(config["bias_protocol"]["low_vds_values_v"])
        + len(config["bias_protocol"]["negative_gate_preconditioning_v"])
        + len(grid)
        - 1
    )
    mesh_runs = solver_log.get("mesh_runs", [])
    record_counts = [len(run.get("solver_records", [])) for run in mesh_runs]
    records = [record for run in mesh_runs for record in run.get("solver_records", [])]
    add_check(
        checks,
        "solver:fresh_mesh_runs_and_convergence",
        [(run.get("mesh_role"), run.get("mesh_level")) for run in mesh_runs]
        == list(zip(required_roles, required_meshes))
        and record_counts == [expected_records_per_mesh] * len(required_meshes)
        and sum(record_counts) == int(acceptance["required_total_dc_solve_count"])
        and all(run.get("status") == "PASS" for run in mesh_runs)
        and not solver_log.get("errors")
        and all(record.get("converged") is True for record in records),
        f"runs={len(mesh_runs)} records={record_counts} total={sum(record_counts)}",
    )

    grid_valid = len(transfer_rows) == int(acceptance["required_total_reported_bias_points"])
    for role, level in zip(required_roles, required_meshes, strict=True):
        rows = rows_for_mesh(transfer_rows, level)
        grid_valid = grid_valid and len(rows) == len(grid)
        grid_valid = grid_valid and [float(row["vgs_v"]) for row in rows] == grid
        grid_valid = grid_valid and all(
            row["mesh_role"] == role
            and row["stage_id"] == "T01_DC_EXTRACTION"
            and same_value(float(row["vds_v"]), float(config["bias_protocol"]["vds_v"]))
            for row in rows
        )
    add_check(
        checks,
        "bias:configured_grid",
        grid_valid,
        f"rows={len(transfer_rows)} points_per_mesh={len(grid)}",
    )

    max_imbalance = max(float(row["relative_current_imbalance"]) for row in transfer_rows)
    max_drop = 0.0
    current_valid = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and math.isfinite(float(row["source_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        for row in transfer_rows
    )
    for level in required_meshes:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in rows_for_mesh(transfer_rows, level)
        ]
        for lower, higher in zip(currents, currents[1:]):
            max_drop = max(max_drop, max(0.0, (lower - higher) / max(lower, higher, 1e-300)))
    current_valid = (
        current_valid
        and max_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"])
        and max_drop <= float(acceptance["maximum_monotonic_relative_current_drop"])
    )
    add_check(
        checks,
        "current:direction_conservation_and_monotonicity",
        current_valid,
        f"max_imbalance={max_imbalance:.6e} max_drop={max_drop:.6e}",
    )

    dependency_mesh = {
        row["mesh_level"]: (
            int(row["node_count_with_interface_duplicates"]), int(row["element_count"])
        )
        for row in mesh_report["mesh"] if row["mesh_level"] in required_meshes
    }
    mesh_valid = len(mesh_rows) == len(required_meshes)
    for role, level, row in zip(required_roles, required_meshes, mesh_rows, strict=True):
        mesh_valid = mesh_valid and row["mesh_role"] == role and row["mesh_level"] == level
        mesh_valid = mesh_valid and same_value(float(row["refinement_factor"]), levels[level])
        mesh_valid = mesh_valid and (
            int(row["node_count_with_interface_duplicates"]), int(row["element_count"])
        ) == dependency_mesh[level]
        mesh_valid = mesh_valid and int(row["dc_solve_count"]) == expected_records_per_mesh
        mesh_valid = mesh_valid and int(row["reported_bias_point_count"]) == len(grid)
    add_check(
        checks,
        "mesh:summary_matches_t01_da",
        mesh_valid,
        f"rows={len(mesh_rows)} counts={dependency_mesh}",
    )

    parameter_valid = len(parameter_rows) == len(required_meshes)
    recomputed: dict[str, dict[str, float | int]] = {}
    metric_keys = [
        "vth_proxy_v", "vth_bracket_lower_vgs_v", "vth_bracket_upper_vgs_v",
        "vth_bracket_lower_current_a_per_cm", "vth_bracket_upper_current_a_per_cm",
        "ss_proxy_mv_per_dec", "ss_fit_r_squared", "ss_fit_slope_dec_per_v",
        "ss_fit_intercept", "ss_fit_vgs_min_v", "ss_fit_vgs_max_v",
        "physical_oxide_capacitance_f_per_cm2", "gm_at_mobility_point_s_per_cm",
        "mobility_proxy_cm2_vs", "maximum_sampled_gm_s_per_cm",
        "maximum_sampled_gm_vgs_v", "minimum_abs_drain_current_a_per_cm",
        "maximum_abs_drain_current_a_per_cm", "numerical_current_span_ratio",
        "numerical_current_span_decades",
    ]
    for role, level, row in zip(required_roles, required_meshes, parameter_rows, strict=True):
        values = recompute_parameter_metric(baseline, config, transfer_rows, level)
        recomputed[level] = values
        parameter_valid = parameter_valid and row["mesh_role"] == role and row["mesh_level"] == level
        parameter_valid = parameter_valid and all(
            close_metric(float(row[key]), float(values[key])) for key in metric_keys
        )
        parameter_valid = parameter_valid and int(row["ss_fit_point_count"]) == int(
            values["ss_fit_point_count"]
        )
        parameter_valid = parameter_valid and int(row["ss_fit_point_count"]) >= int(
            acceptance["minimum_ss_fit_point_count"]
        )
        parameter_valid = parameter_valid and float(row["ss_fit_r_squared"]) >= float(
            acceptance["minimum_ss_fit_r_squared"]
        )
        parameter_valid = parameter_valid and row["parameter_claim_status"] == (
            "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
        )
    add_check(
        checks,
        "parameters:independently_recomputed_numerical_proxies",
        parameter_valid,
        "; ".join(
            f"{level}:VTH={float(recomputed[level]['vth_proxy_v']):.6g},"
            f"SS={float(recomputed[level]['ss_proxy_mv_per_dec']):.6g},"
            f"mu={float(recomputed[level]['mobility_proxy_cm2_vs']):.6g}"
            for level in required_meshes
        ),
    )
    production_metric = recomputed[required_meshes[0]]
    reference_metric = recomputed[required_meshes[1]]
    vth_difference = abs(
        float(production_metric["vth_proxy_v"]) - float(reference_metric["vth_proxy_v"])
    )
    ss_difference = abs(
        float(production_metric["ss_proxy_mv_per_dec"])
        - float(reference_metric["ss_proxy_mv_per_dec"])
    ) / max(
        float(production_metric["ss_proxy_mv_per_dec"]),
        float(reference_metric["ss_proxy_mv_per_dec"]),
    )
    mobility_difference = abs(
        float(production_metric["mobility_proxy_cm2_vs"])
        - float(reference_metric["mobility_proxy_cm2_vs"])
    ) / max(
        float(production_metric["mobility_proxy_cm2_vs"]),
        float(reference_metric["mobility_proxy_cm2_vs"]),
    )
    add_check(
        checks,
        "parameters:mesh_agreement",
        vth_difference <= float(acceptance["maximum_vth_proxy_mesh_difference_v"])
        and ss_difference <= float(acceptance["maximum_ss_proxy_mesh_relative_difference"])
        and mobility_difference <= float(acceptance["maximum_mobility_proxy_mesh_relative_difference"]),
        f"dVTH={vth_difference:.6e} dSS_rel={ss_difference:.6e} dmu_rel={mobility_difference:.6e}",
    )

    comparison_valid = len(comparison_rows) == len(grid)
    production_level, reference_level = required_meshes
    for row, vgs_v in zip(comparison_rows, grid, strict=True):
        lower = point(transfer_rows, production_level, vgs_v)
        higher = point(transfer_rows, reference_level, vgs_v)
        lower_current = abs(float(lower["drain_current_a_per_cm"]))
        higher_current = abs(float(higher["drain_current_a_per_cm"]))
        relative = abs(lower_current - higher_current) / max(lower_current, higher_current, 1e-300)
        log_difference = abs(math.log10(lower_current) - math.log10(higher_current))
        potential = abs(
            float(lower["center_channel_potential_v"])
            - float(higher["center_channel_potential_v"])
        )
        comparison_valid = comparison_valid and same_value(float(row["vgs_v"]), vgs_v)
        comparison_valid = comparison_valid and close_metric(
            float(row["relative_current_difference"]), relative
        )
        comparison_valid = comparison_valid and close_metric(
            float(row["log10_current_difference_decades"]), log_difference
        )
        comparison_valid = comparison_valid and close_metric(
            float(row["center_channel_potential_difference_v"]), potential
        )
    add_check(
        checks,
        "mesh:pointwise_comparison_recomputed",
        comparison_valid,
        f"rows={len(comparison_rows)}",
    )

    expected_reproductions = len(required_meshes) * len(
        acceptance["required_t01_db_anchor_vgs_values_v"]
    )
    reproduction_valid = len(reproduction_rows) == expected_reproductions
    max_anchor_current = 0.0
    max_anchor_potential = 0.0
    for row in reproduction_rows:
        level = row["mesh_level"]
        vgs_v = float(row["vgs_v"])
        old = next(
            item for item in db_report["bias_points"]
            if item["mesh_level"] == level
            and same_value(float(item["vgs_v"]), vgs_v)
            and same_value(float(item["vds_v"]), float(config["bias_protocol"]["vds_v"]))
        )
        new = point(transfer_rows, level, vgs_v)
        old_current = abs(float(old["drain_current_a_per_cm"]))
        new_current = abs(float(new["drain_current_a_per_cm"]))
        relative = abs(old_current - new_current) / max(old_current, new_current, 1e-300)
        potential = abs(
            float(old["center_channel_potential_v"])
            - float(new["center_channel_potential_v"])
        )
        max_anchor_current = max(max_anchor_current, relative)
        max_anchor_potential = max(max_anchor_potential, potential)
        reproduction_valid = reproduction_valid and close_metric(
            float(row["relative_current_difference"]), relative
        )
        reproduction_valid = reproduction_valid and close_metric(
            float(row["center_channel_potential_difference_v"]), potential
        )
    reproduction_valid = (
        reproduction_valid
        and max_anchor_current <= float(acceptance["maximum_t01_db_anchor_relative_current_difference"])
        and max_anchor_potential <= float(acceptance["maximum_t01_db_anchor_potential_difference_v"])
    )
    add_check(
        checks,
        "regression:t01_db_anchors_recomputed",
        reproduction_valid,
        f"rows={len(reproduction_rows)} max_current={max_anchor_current:.6e} max_potential={max_anchor_potential:.6e}",
    )

    state_entries = state_manifest.get("entries", [])
    state_valid = (
        state_manifest.get("case_id") == config["case_id"]
        and state_manifest.get("stage") == "T01-D-C"
        and [entry.get("state_id") for entry in state_entries]
        == list(acceptance["required_state_ids"])
        and len(state_summary_rows) == len(state_entries)
    )
    state_currents: list[float] = []
    state_densities: list[float] = []
    expected_node_headers = {
        "state_id", "state_label", "mesh_level", "stage_id", "vgs_v", "vds_v",
        "region", "x_cm", "y_cm", "x_um", "y_nm", "potential_v",
        "electron_density_cm3",
    }
    expected_element_headers = {
        "state_id", "state_label", "mesh_level", "stage_id", "vgs_v", "vds_v",
        "electron_current_density_x_en0_a_per_cm2",
        "electron_current_density_x_en1_a_per_cm2",
        "electron_current_density_x_en2_a_per_cm2",
        "electron_current_density_y_en0_a_per_cm2",
        "electron_current_density_y_en1_a_per_cm2",
        "electron_current_density_y_en2_a_per_cm2",
        "electron_current_density_x_a_per_cm2",
        "electron_current_density_y_a_per_cm2",
        "electron_current_density_magnitude_a_per_cm2",
    }
    for entry, summary in zip(state_entries, state_summary_rows, strict=True):
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        nodes = load_csv(node_path)
        elements = load_csv(element_path)
        state_valid = state_valid and expected_node_headers <= set(csv_headers(node_path))
        state_valid = state_valid and expected_element_headers <= set(csv_headers(element_path))
        state_valid = state_valid and sha256(node_path) == entry["node_csv_sha256"]
        state_valid = state_valid and sha256(element_path) == entry["element_csv_sha256"]
        state_valid = state_valid and len(nodes) == int(entry["node_row_count"])
        state_valid = state_valid and len(elements) == int(entry["channel_element_count"])
        state_valid = state_valid and {row["region"] for row in nodes} == {"bottom_oxide", "channel"}
        state_valid = state_valid and all(
            row["state_id"] == entry["state_id"]
            and row["mesh_level"] == config["mesh"]["production_level"]
            and row["stage_id"] == "T01_DC_EXTRACTION"
            and math.isfinite(float(row["potential_v"]))
            for row in nodes
        )
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        state_valid = state_valid and all(
            math.isfinite(float(row["electron_density_cm3"]))
            and float(row["electron_density_cm3"]) > 0.0
            for row in channel_nodes
        )
        for element in elements:
            jx_values = [
                float(element[f"electron_current_density_x_en{index}_a_per_cm2"])
                for index in range(3)
            ]
            jy_values = [
                float(element[f"electron_current_density_y_en{index}_a_per_cm2"])
                for index in range(3)
            ]
            jx = float(element["electron_current_density_x_a_per_cm2"])
            jy = float(element["electron_current_density_y_a_per_cm2"])
            magnitude = float(element["electron_current_density_magnitude_a_per_cm2"])
            centroid_x = statistics.fmean(float(element[f"x{index}_cm"]) for index in range(3))
            centroid_y = statistics.fmean(float(element[f"y{index}_cm"]) for index in range(3))
            state_valid = state_valid and all(math.isfinite(value) for value in jx_values + jy_values)
            state_valid = state_valid and close_metric(jx, statistics.fmean(jx_values))
            state_valid = state_valid and close_metric(jy, statistics.fmean(jy_values))
            state_valid = state_valid and close_metric(magnitude, math.hypot(jx, jy))
            state_valid = state_valid and close_metric(float(element["centroid_x_cm"]), centroid_x)
            state_valid = state_valid and close_metric(float(element["centroid_y_cm"]), centroid_y)
            state_valid = state_valid and element["projection_method"].startswith(
                "DEVSIM element_from_edge_model"
            )
        state_valid = state_valid and len(entry.get("vtk_files", [])) >= 3
        state_valid = state_valid and all(
            (ROOT / item["path"]).is_file() and sha256(ROOT / item["path"]) == item["sha256"]
            for item in entry.get("vtk_files", [])
        )
        state_valid = state_valid and entry.get("current_projection", {}).get("local_unit") == "A/cm^2"
        state_valid = state_valid and summary["state_id"] == entry["state_id"]
        state_valid = state_valid and int(summary["node_row_count"]) == len(nodes)
        state_valid = state_valid and int(summary["channel_element_count"]) == len(elements)
        state_currents.append(float(entry["absolute_drain_current_a_per_cm"]))
        state_densities.append(float(entry["center_channel_electron_density_cm3"]))
    state_valid = state_valid and all(
        higher > lower for lower, higher in zip(state_currents, state_currents[1:])
    )
    state_valid = state_valid and all(
        higher > lower for lower, higher in zip(state_densities, state_densities[1:])
    )
    add_check(
        checks,
        "states:potential_density_current_vectors_and_ordering",
        state_valid,
        f"states={[entry.get('state_id') for entry in state_entries]} currents={state_currents}",
    )

    report_bias = report.get("bias_points", [])
    report_parameters = report.get("parameter_proxies", [])
    report_states = report.get("state_outputs", [])
    persisted_match = (
        len(report_bias) == len(transfer_rows)
        and len(report_parameters) == len(parameter_rows)
        and len(report_states) == len(state_entries)
    )
    for json_row, csv_row in zip(report_bias, transfer_rows):
        persisted_match = persisted_match and json_row["mesh_level"] == csv_row["mesh_level"]
        persisted_match = persisted_match and close_metric(
            float(json_row["drain_current_a_per_cm"]), float(csv_row["drain_current_a_per_cm"])
        )
    add_check(
        checks,
        "outputs:json_csv_consistency",
        persisted_match,
        f"report_bias={len(report_bias)} csv_bias={len(transfer_rows)}",
    )

    figures = report.get("figures", {})
    extraction_figure = ROOT / outputs["extraction_figure_png"]
    state_figure = ROOT / outputs["state_figure_png"]
    output_paths = [
        ROOT / value for key, value in report.get("outputs", {}).items()
        if key != "run_directory"
    ]
    output_valid = (
        all(path.is_file() and path.stat().st_size > 0 for path in output_paths)
        and (ROOT / outputs["run_directory"]).is_dir()
        and figures.get("extraction", {}).get("path") == outputs["extraction_figure_png"]
        and figures.get("extraction", {}).get("sha256") == sha256(extraction_figure)
        and figures.get("states", {}).get("path") == outputs["state_figure_png"]
        and figures.get("states", {}).get("sha256") == sha256(state_figure)
    )
    add_check(
        checks,
        "outputs:raw_tables_states_and_figures",
        output_valid,
        f"files={len(output_paths)} figure_bytes={[extraction_figure.stat().st_size, state_figure.stat().st_size]}",
    )

    completion = report.get("t01_completion", {})
    runner_checks = report.get("checks", {})
    requirements = completion.get("requirements", {})
    boundary_valid = (
        config["evidence_boundary"].get("allowed_parameter_label")
        == "numerical proxy extracted from the frozen teaching model"
        and any("Ion/Ioff" in item for item in config["evidence_boundary"]["prohibited_claims"])
        and all("physical Ion/Ioff" not in str(row) for row in parameter_rows)
        and report.get("teaching_target_diagnostic_only", {}).get(
            "acceptance_depends_on_target_match"
        ) is False
    )
    add_check(
        checks,
        "runner:complete_t01_gate_and_evidence_boundary",
        bool(runner_checks)
        and all(result.get("status") == "PASS" for result in runner_checks.values())
        and completion.get("status") == "PASS"
        and completion.get("complete_t01_numerical_stage_gate") == "PASS"
        and set(requirements.values()) == {"PASS"}
        and completion.get("t02_stage_permitted_next") is True
        and completion.get("experimental_calibration_permitted") is False
        and completion.get("physical_parameter_validation_permitted") is False
        and completion.get("physical_ion_ioff_claim_permitted") is False
        and completion.get("compact_model_calibrated") is False
        and boundary_valid,
        f"runner_checks={len(runner_checks)} complete={completion.get('status')} next={completion.get('t02_stage_permitted_next')}",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "checks": checks,
        "failures": failures,
        "recomputed_maximum_relative_terminal_current_imbalance": max_imbalance,
        "recomputed_maximum_monotonic_relative_current_drop": max_drop,
        "recomputed_vth_proxy_mesh_difference_v": vth_difference,
        "recomputed_ss_proxy_mesh_relative_difference": ss_difference,
        "recomputed_mobility_proxy_mesh_relative_difference": mobility_difference,
        "recomputed_maximum_t01_db_anchor_relative_current_difference": max_anchor_current,
        "recomputed_maximum_t01_db_anchor_potential_difference_v": max_anchor_potential,
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
        print(f"T01_D_EXTRACTION_CHECK_ERROR {error}", file=sys.stderr)
        return 1
    if not args.check_only:
        check_report_path.parent.mkdir(parents=True, exist_ok=True)
        check_report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
        )
    label = "PASS" if report["status"] == "PASS" else "FAIL"
    print(
        f"T01_D_EXTRACTION_CHECK_{label} checks={len(report['checks'])} "
        f"report={check_report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T01_D_EXTRACTION_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
