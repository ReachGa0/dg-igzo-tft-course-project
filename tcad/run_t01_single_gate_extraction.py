#!/usr/bin/env python3
"""Run T01-D-C state export and limited numerical-proxy extraction."""

from __future__ import annotations

import argparse
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t01_single_gate_mesh_refinement as mesh_stage  # noqa: E402


core = mesh_stage.core

TRANSFER_FIELDNAMES = [
    "mesh_role", "mesh_level", "stage_id", "vgs_v", "vds_v",
    "source_current_a_per_cm", "drain_current_a_per_cm", "source_current_terminal_a",
    "drain_current_terminal_a", "current_imbalance_a_per_cm",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "solve_seconds", "converged",
]
MESH_SUMMARY_FIELDNAMES = [
    "mesh_role", "mesh_level", "refinement_factor",
    "node_count_with_interface_duplicates", "element_count", "dc_solve_count",
    "reported_bias_point_count", "total_solve_seconds", "wall_seconds",
]
MESH_COMPARISON_FIELDNAMES = [
    "vgs_v", "vds_v", "production_abs_drain_current_a_per_cm",
    "reference_abs_drain_current_a_per_cm", "relative_current_difference",
    "log10_current_difference_decades", "production_center_channel_potential_v",
    "reference_center_channel_potential_v", "center_channel_potential_difference_v",
]
PARAMETER_FIELDNAMES = [
    "mesh_role", "mesh_level", "constant_current_criterion_terminal_a",
    "constant_current_criterion_a_per_cm", "vth_proxy_v", "vth_bracket_lower_vgs_v",
    "vth_bracket_upper_vgs_v", "vth_bracket_lower_current_a_per_cm",
    "vth_bracket_upper_current_a_per_cm", "ss_proxy_mv_per_dec",
    "ss_fit_point_count", "ss_fit_r_squared", "ss_fit_slope_dec_per_v",
    "ss_fit_intercept", "ss_fit_vgs_min_v", "ss_fit_vgs_max_v",
    "ss_window_min_current_a_per_cm", "ss_window_max_current_a_per_cm",
    "physical_oxide_capacitance_f_per_cm2", "mobility_gm_lower_vgs_v",
    "mobility_gm_upper_vgs_v", "gm_at_mobility_point_s_per_cm",
    "mobility_proxy_cm2_vs", "configured_transport_mobility_cm2_vs",
    "mobility_proxy_to_configured_ratio", "maximum_sampled_gm_s_per_cm",
    "maximum_sampled_gm_vgs_v", "minimum_abs_drain_current_a_per_cm",
    "maximum_abs_drain_current_a_per_cm", "numerical_current_span_ratio",
    "numerical_current_span_decades", "parameter_claim_status",
]
STATE_NODE_FIELDNAMES = [
    "state_id", "state_label", "mesh_level", "stage_id", "vgs_v", "vds_v",
    "region", "x_cm", "y_cm", "x_um", "y_nm", "potential_v",
    "electron_density_cm3",
]
STATE_ELEMENT_FIELDNAMES = [
    "state_id", "state_label", "mesh_level", "stage_id", "vgs_v", "vds_v",
    "region", "element_index", "node0_index", "node1_index", "node2_index",
    "x0_cm", "y0_cm", "x1_cm", "y1_cm", "x2_cm", "y2_cm",
    "centroid_x_cm", "centroid_y_cm", "centroid_x_um", "centroid_y_nm",
    "electron_current_density_x_en0_a_per_cm2",
    "electron_current_density_x_en1_a_per_cm2",
    "electron_current_density_x_en2_a_per_cm2",
    "electron_current_density_y_en0_a_per_cm2",
    "electron_current_density_y_en1_a_per_cm2",
    "electron_current_density_y_en2_a_per_cm2",
    "electron_current_density_x_a_per_cm2",
    "electron_current_density_y_a_per_cm2",
    "electron_current_density_magnitude_a_per_cm2",
    "mean_element_node_current_density_magnitude_a_per_cm2",
    "maximum_element_node_current_density_magnitude_a_per_cm2",
    "projection_method",
]
STATE_SUMMARY_FIELDNAMES = [
    "state_id", "state_label", "mesh_level", "stage_id", "vgs_v", "vds_v",
    "absolute_drain_current_a_per_cm", "drain_current_terminal_a",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "node_row_count", "channel_node_count",
    "channel_element_count", "minimum_potential_v", "maximum_potential_v",
    "minimum_electron_density_cm3", "maximum_electron_density_cm3",
    "minimum_cell_current_density_magnitude_a_per_cm2",
    "median_cell_current_density_magnitude_a_per_cm2",
    "maximum_cell_current_density_magnitude_a_per_cm2", "node_csv", "element_csv",
]
DB_REPRODUCTION_FIELDNAMES = [
    "mesh_level", "vgs_v", "vds_v", "t01_db_abs_drain_current_a_per_cm",
    "t01_dc_abs_drain_current_a_per_cm", "relative_current_difference",
    "t01_db_center_channel_potential_v", "t01_dc_center_channel_potential_v",
    "center_channel_potential_difference_v",
]


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def add_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def extraction_vgs_values(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["extraction_grid"]
    start = float(spec["dense_start_v"])
    stop = float(spec["dense_stop_v"])
    step = float(spec["dense_step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T01-D-C dense VGS range is not an integral number of steps")
    dense = [round(start + index * step, 12) for index in range(intervals + 1)]
    anchors = [round(float(value), 12) for value in spec["outer_anchor_values_v"]]
    return sorted(set(dense + anchors))


def point(rows: list[dict[str, Any]], mesh_level: str, vgs_v: float) -> dict[str, Any]:
    return next(
        row for row in rows
        if row["mesh_level"] == mesh_level and same_value(float(row["vgs_v"]), vgs_v)
    )


def rows_for_mesh(rows: list[dict[str, Any]], mesh_level: str) -> list[dict[str, Any]]:
    return sorted(
        [row for row in rows if row["mesh_level"] == mesh_level],
        key=lambda row: float(row["vgs_v"]),
    )


def state_token(state_id: str, vgs_v: float) -> str:
    voltage = f"{vgs_v:.3f}".replace("-", "m").replace(".", "p")
    return f"{state_id}_vgs_{voltage}"


def collect_current_elements(
    device: str,
    mesh_level: str,
    state: dict[str, Any],
) -> list[dict[str, Any]]:
    region = "channel"
    elements = core.devsim.get_element_node_list(device=device, region=region)
    xs = core.devsim.get_node_model_values(device=device, region=region, name="x")
    ys = core.devsim.get_node_model_values(device=device, region=region, name="y")
    jx_values = core.devsim.get_element_model_values(
        device=device, region=region, name="ElectronCurrent_x"
    )
    jy_values = core.devsim.get_element_model_values(
        device=device, region=region, name="ElectronCurrent_y"
    )
    if len(jx_values) != 3 * len(elements) or len(jy_values) != 3 * len(elements):
        raise RuntimeError(
            "DEVSIM element current projection does not contain three values per triangle"
        )

    rows: list[dict[str, Any]] = []
    for index, node_indexes in enumerate(elements):
        if len(node_indexes) != 3:
            raise RuntimeError("T01-D-C current export requires triangular 2D elements")
        node_indexes = tuple(int(value) for value in node_indexes)
        x_coordinates = [float(xs[value]) for value in node_indexes]
        y_coordinates = [float(ys[value]) for value in node_indexes]
        jx = [float(value) for value in jx_values[3 * index : 3 * index + 3]]
        jy = [float(value) for value in jy_values[3 * index : 3 * index + 3]]
        jx_center = sum(jx) / 3.0
        jy_center = sum(jy) / 3.0
        node_magnitudes = [math.hypot(x_value, y_value) for x_value, y_value in zip(jx, jy)]
        centroid_x = sum(x_coordinates) / 3.0
        centroid_y = sum(y_coordinates) / 3.0
        rows.append({
            "state_id": state["state_id"],
            "state_label": state["label"],
            "mesh_level": mesh_level,
            "stage_id": "T01_DC_EXTRACTION",
            "vgs_v": float(state["vgs_v"]),
            "vds_v": float(state["vds_v"]),
            "region": region,
            "element_index": index,
            "node0_index": node_indexes[0],
            "node1_index": node_indexes[1],
            "node2_index": node_indexes[2],
            "x0_cm": x_coordinates[0],
            "y0_cm": y_coordinates[0],
            "x1_cm": x_coordinates[1],
            "y1_cm": y_coordinates[1],
            "x2_cm": x_coordinates[2],
            "y2_cm": y_coordinates[2],
            "centroid_x_cm": centroid_x,
            "centroid_y_cm": centroid_y,
            "centroid_x_um": centroid_x * 1.0e4,
            "centroid_y_nm": centroid_y * 1.0e7,
            "electron_current_density_x_en0_a_per_cm2": jx[0],
            "electron_current_density_x_en1_a_per_cm2": jx[1],
            "electron_current_density_x_en2_a_per_cm2": jx[2],
            "electron_current_density_y_en0_a_per_cm2": jy[0],
            "electron_current_density_y_en1_a_per_cm2": jy[1],
            "electron_current_density_y_en2_a_per_cm2": jy[2],
            "electron_current_density_x_a_per_cm2": jx_center,
            "electron_current_density_y_a_per_cm2": jy_center,
            "electron_current_density_magnitude_a_per_cm2": math.hypot(jx_center, jy_center),
            "mean_element_node_current_density_magnitude_a_per_cm2": sum(node_magnitudes) / 3.0,
            "maximum_element_node_current_density_magnitude_a_per_cm2": max(node_magnitudes),
            "projection_method": "DEVSIM element_from_edge_model; arithmetic mean of en0/en1/en2",
        })
    return rows


def write_state(
    device: str,
    mesh_level: str,
    state: dict[str, Any],
    bias_row: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    node_rows = [
        {
            "state_id": state["state_id"],
            "state_label": state["label"],
            "stage_id": "T01_DC_EXTRACTION",
            "vgs_v": float(state["vgs_v"]),
            "vds_v": float(state["vds_v"]),
            **row,
        }
        for row in core.collect_state_nodes(device, mesh_level)
    ]
    element_rows = collect_current_elements(device, mesh_level, state)
    token = state_token(str(state["state_id"]), float(state["vgs_v"]))
    base = f"t01_dc_{mesh_level}_{token}"
    node_path = run_dir / f"{base}_nodes.csv"
    element_path = run_dir / f"{base}_current_elements.csv"
    core.write_csv(node_path, node_rows, STATE_NODE_FIELDNAMES)
    core.write_csv(element_path, element_rows, STATE_ELEMENT_FIELDNAMES)

    vtk_base = run_dir / base
    core.devsim.write_devices(file=str(vtk_base), device=device, type="vtk")
    vtk_paths = sorted(run_dir.glob(f"{base}*"))
    vtk_paths = [path for path in vtk_paths if path not in {node_path, element_path}]
    for path in vtk_paths:
        core.normalize_text_newline(path)

    channel_nodes = [row for row in node_rows if row["region"] == "channel"]
    electron_values = [float(row["electron_density_cm3"]) for row in channel_nodes]
    potential_values = [float(row["potential_v"]) for row in node_rows]
    current_values = [
        float(row["electron_current_density_magnitude_a_per_cm2"])
        for row in element_rows
    ]
    summary = {
        "state_id": state["state_id"],
        "state_label": state["label"],
        "mesh_level": mesh_level,
        "stage_id": "T01_DC_EXTRACTION",
        "vgs_v": float(state["vgs_v"]),
        "vds_v": float(state["vds_v"]),
        "absolute_drain_current_a_per_cm": abs(float(bias_row["drain_current_a_per_cm"])),
        "drain_current_terminal_a": abs(float(bias_row["drain_current_terminal_a"])),
        "relative_current_imbalance": float(bias_row["relative_current_imbalance"]),
        "center_channel_potential_v": float(bias_row["center_channel_potential_v"]),
        "center_channel_electron_density_cm3": float(
            bias_row["center_channel_electron_density_cm3"]
        ),
        "node_row_count": len(node_rows),
        "channel_node_count": len(channel_nodes),
        "channel_element_count": len(element_rows),
        "minimum_potential_v": min(potential_values),
        "maximum_potential_v": max(potential_values),
        "minimum_electron_density_cm3": min(electron_values),
        "maximum_electron_density_cm3": max(electron_values),
        "minimum_cell_current_density_magnitude_a_per_cm2": min(current_values),
        "median_cell_current_density_magnitude_a_per_cm2": statistics.median(current_values),
        "maximum_cell_current_density_magnitude_a_per_cm2": max(current_values),
        "node_csv": str(node_path.relative_to(ROOT)),
        "element_csv": str(element_path.relative_to(ROOT)),
    }
    return {
        **summary,
        "node_csv_sha256": core.sha256(node_path),
        "element_csv_sha256": core.sha256(element_path),
        "vtk_files": [
            {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for path in vtk_paths
        ],
        "current_projection": {
            "source_edge_model": "ElectronCurrent",
            "api": "element_from_edge_model",
            "raw_values_per_triangle": 3,
            "cell_center_reduction": "arithmetic mean of the three element-node vectors",
            "local_unit": "A/cm^2",
        },
        "_node_rows": node_rows,
        "_element_rows": element_rows,
    }


def run_mesh(
    baseline: dict[str, Any],
    config: dict[str, Any],
    mesh_config: dict[str, Any],
    mesh_role: str,
    mesh_level: str,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    runtime, _ = mesh_stage.build_runtime_baseline(baseline, mesh_config, mesh_level)
    device = f"t01_dc_{mesh_level}"
    records: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    protocol = config["bias_protocol"]
    fixed_vds = float(protocol["vds_v"])
    try:
        core.initialize_device(device, runtime, mesh_level)
        core.set_biases(device, source_v=0.0, drain_v=0.0, bottom_gate_v=0.0)
        records.append(core.solve_dc(
            device, runtime, f"{mesh_level}_poisson_zero_bias_initialization", coupled=False
        ))
        core.create_transport(device, runtime)
        records.append(core.solve_dc(
            device, runtime, f"{mesh_level}_T01_A_STAGE_0", coupled=True
        ))
        core.devsim.element_from_edge_model(
            device=device, region="channel", edge_model="ElectronCurrent"
        )

        for vds_v in [float(value) for value in protocol["low_vds_values_v"]]:
            core.set_biases(device, source_v=0.0, drain_v=vds_v, bottom_gate_v=0.0)
            records.append(core.solve_dc(
                device,
                runtime,
                f"{mesh_level}_T01_A_STAGE_1_VDS_{vds_v:.6g}_V",
                coupled=True,
            ))

        precondition_records: dict[float, dict[str, Any]] = {}
        for vgs_v in [float(value) for value in protocol["negative_gate_preconditioning_v"]]:
            core.set_biases(device, source_v=0.0, drain_v=fixed_vds, bottom_gate_v=vgs_v)
            record = core.solve_dc(
                device,
                runtime,
                f"{mesh_level}_T01_DC_PRECONDITION_VGS_{vgs_v:.6g}_V",
                coupled=True,
            )
            records.append(record)
            precondition_records[round(vgs_v, 12)] = record

        state_points = {
            round(float(state["vgs_v"]), 12): state for state in protocol["state_points"]
        }
        rows: list[dict[str, Any]] = []
        for index, vgs_v in enumerate(extraction_vgs_values(config)):
            if index == 0 and round(vgs_v, 12) in precondition_records:
                solve_record = precondition_records[round(vgs_v, 12)]
            else:
                core.set_biases(
                    device, source_v=0.0, drain_v=fixed_vds, bottom_gate_v=vgs_v
                )
                solve_record = core.solve_dc(
                    device,
                    runtime,
                    f"{mesh_level}_T01_DC_EXTRACTION_VGS_{vgs_v:.6g}_V",
                    coupled=True,
                )
                records.append(solve_record)
            row = {
                "mesh_role": mesh_role,
                **core.collect_bias_row(
                    device,
                    runtime,
                    mesh_level=mesh_level,
                    stage_id="T01_DC_EXTRACTION",
                    vds_v=fixed_vds,
                    vgs_v=vgs_v,
                    solve_record=solve_record,
                ),
            }
            rows.append(row)
            key = round(vgs_v, 12)
            if mesh_role == "production" and key in state_points:
                state_entries.append(
                    write_state(device, mesh_level, state_points[key], row, run_dir)
                )

        node_count, element_count = core.node_and_element_counts(device)
        summary = {
            "mesh_role": mesh_role,
            "mesh_level": mesh_level,
            "refinement_factor": float(
                mesh_stage.level_map(mesh_config)[mesh_level]["refinement_factor"]
            ),
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(records),
            "reported_bias_point_count": len(rows),
            "total_solve_seconds": sum(float(record["elapsed_seconds"]) for record in records),
            "wall_seconds": time.perf_counter() - wall_start,
            "solver_records": records,
        }
        return rows, summary, state_entries
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def linear_regression(xs: list[float], ys: list[float]) -> tuple[float, float, float]:
    mean_x = statistics.fmean(xs)
    mean_y = statistics.fmean(ys)
    variance = sum((value - mean_x) ** 2 for value in xs)
    if variance <= 0.0:
        raise ValueError("regression VGS variance must be positive")
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance
    intercept = mean_y - slope * mean_x
    residual = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(xs, ys))
    total = sum((y - mean_y) ** 2 for y in ys)
    r_squared = 1.0 if total == 0.0 else 1.0 - residual / total
    return slope, intercept, r_squared


def build_parameter_metrics(
    baseline: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    methods = config["extraction_methods"]
    vth_method = methods["constant_current_vth_proxy"]
    ss_method = methods["subthreshold_swing_proxy"]
    mobility_method = methods["field_effect_mobility_proxy"]
    criterion = float(vth_method["expected_current_per_width_a_per_cm"])
    terminal_criterion = float(vth_method["expected_terminal_current_a"])
    width = float(baseline["device"]["width_cm"])
    length = float(baseline["device"]["channel_length_cm"])
    vds = float(config["bias_protocol"]["vds_v"])
    oxide = baseline["materials"]["bottom_oxide"]
    cox = (
        float(mobility_method["epsilon0_f_per_cm"])
        * float(oxide["relative_permittivity"])
        / float(oxide["physical_thickness_cm"])
    )
    if not same_value(terminal_criterion / width, criterion):
        raise RuntimeError("constant-current criterion terminal and per-width values differ")

    metrics: list[dict[str, Any]] = []
    for role, level in zip(
        config["acceptance"]["required_mesh_roles"],
        config["acceptance"]["required_mesh_levels"],
        strict=True,
    ):
        mesh_rows = rows_for_mesh(rows, level)
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in mesh_rows]
        voltages = [float(row["vgs_v"]) for row in mesh_rows]
        bracket_index = next(
            index for index in range(len(currents) - 1)
            if currents[index] <= criterion <= currents[index + 1]
        )
        lower_current = currents[bracket_index]
        upper_current = currents[bracket_index + 1]
        lower_voltage = voltages[bracket_index]
        upper_voltage = voltages[bracket_index + 1]
        log_lower = math.log10(max(lower_current, 1.0e-300))
        log_upper = math.log10(max(upper_current, 1.0e-300))
        vth_proxy = lower_voltage + (
            (math.log10(criterion) - log_lower)
            * (upper_voltage - lower_voltage)
            / (log_upper - log_lower)
        )

        ss_rows = [
            row for row in mesh_rows
            if float(ss_method["minimum_abs_drain_current_a_per_cm"])
            <= abs(float(row["drain_current_a_per_cm"]))
            <= float(ss_method["maximum_abs_drain_current_a_per_cm"])
        ]
        ss_x = [float(row["vgs_v"]) for row in ss_rows]
        ss_y = [math.log10(abs(float(row["drain_current_a_per_cm"]))) for row in ss_rows]
        slope, intercept, r_squared = linear_regression(ss_x, ss_y)
        ss_proxy = 1000.0 / slope

        gm_lower_vgs = float(mobility_method["vgs_lower_v"])
        gm_upper_vgs = float(mobility_method["vgs_upper_v"])
        gm_lower = abs(float(point(rows, level, gm_lower_vgs)["drain_current_a_per_cm"]))
        gm_upper = abs(float(point(rows, level, gm_upper_vgs)["drain_current_a_per_cm"]))
        gm = (gm_upper - gm_lower) / (gm_upper_vgs - gm_lower_vgs)
        mobility_proxy = length * gm / (cox * vds)

        sampled_gm: list[tuple[float, float]] = []
        for index in range(1, len(mesh_rows) - 1):
            sampled_gm.append((
                voltages[index],
                (currents[index + 1] - currents[index - 1])
                / (voltages[index + 1] - voltages[index - 1]),
            ))
        max_gm_vgs, max_gm = max(sampled_gm, key=lambda item: item[1])
        minimum_current = min(currents)
        maximum_current = max(currents)
        span_ratio = maximum_current / max(minimum_current, 1.0e-300)
        configured_mobility = float(baseline["physics"]["mobility_cm2_vs"])
        metrics.append({
            "mesh_role": role,
            "mesh_level": level,
            "constant_current_criterion_terminal_a": terminal_criterion,
            "constant_current_criterion_a_per_cm": criterion,
            "vth_proxy_v": vth_proxy,
            "vth_bracket_lower_vgs_v": lower_voltage,
            "vth_bracket_upper_vgs_v": upper_voltage,
            "vth_bracket_lower_current_a_per_cm": lower_current,
            "vth_bracket_upper_current_a_per_cm": upper_current,
            "ss_proxy_mv_per_dec": ss_proxy,
            "ss_fit_point_count": len(ss_rows),
            "ss_fit_r_squared": r_squared,
            "ss_fit_slope_dec_per_v": slope,
            "ss_fit_intercept": intercept,
            "ss_fit_vgs_min_v": min(ss_x),
            "ss_fit_vgs_max_v": max(ss_x),
            "ss_window_min_current_a_per_cm": float(
                ss_method["minimum_abs_drain_current_a_per_cm"]
            ),
            "ss_window_max_current_a_per_cm": float(
                ss_method["maximum_abs_drain_current_a_per_cm"]
            ),
            "physical_oxide_capacitance_f_per_cm2": cox,
            "mobility_gm_lower_vgs_v": gm_lower_vgs,
            "mobility_gm_upper_vgs_v": gm_upper_vgs,
            "gm_at_mobility_point_s_per_cm": gm,
            "mobility_proxy_cm2_vs": mobility_proxy,
            "configured_transport_mobility_cm2_vs": configured_mobility,
            "mobility_proxy_to_configured_ratio": mobility_proxy / configured_mobility,
            "maximum_sampled_gm_s_per_cm": max_gm,
            "maximum_sampled_gm_vgs_v": max_gm_vgs,
            "minimum_abs_drain_current_a_per_cm": minimum_current,
            "maximum_abs_drain_current_a_per_cm": maximum_current,
            "numerical_current_span_ratio": span_ratio,
            "numerical_current_span_decades": math.log10(span_ratio),
            "parameter_claim_status": "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
        })
    return metrics


def build_mesh_comparisons(
    config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    production = config["mesh"]["production_level"]
    reference = config["mesh"]["reference_level"]
    output: list[dict[str, Any]] = []
    for vgs_v in extraction_vgs_values(config):
        lower = point(rows, production, vgs_v)
        higher = point(rows, reference, vgs_v)
        lower_current = abs(float(lower["drain_current_a_per_cm"]))
        higher_current = abs(float(higher["drain_current_a_per_cm"]))
        output.append({
            "vgs_v": vgs_v,
            "vds_v": float(config["bias_protocol"]["vds_v"]),
            "production_abs_drain_current_a_per_cm": lower_current,
            "reference_abs_drain_current_a_per_cm": higher_current,
            "relative_current_difference": abs(lower_current - higher_current)
            / max(lower_current, higher_current, 1.0e-300),
            "log10_current_difference_decades": abs(
                math.log10(max(lower_current, 1.0e-300))
                - math.log10(max(higher_current, 1.0e-300))
            ),
            "production_center_channel_potential_v": float(lower["center_channel_potential_v"]),
            "reference_center_channel_potential_v": float(higher["center_channel_potential_v"]),
            "center_channel_potential_difference_v": abs(
                float(lower["center_channel_potential_v"])
                - float(higher["center_channel_potential_v"])
            ),
        })
    return output


def build_db_reproduction(
    config: dict[str, Any], rows: list[dict[str, Any]], db_report: dict[str, Any]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for level in config["acceptance"]["required_mesh_levels"]:
        for vgs_v in [
            float(value)
            for value in config["acceptance"]["required_t01_db_anchor_vgs_values_v"]
        ]:
            reference = next(
                row for row in db_report["bias_points"]
                if row["mesh_level"] == level
                and same_value(float(row["vgs_v"]), vgs_v)
                and same_value(float(row["vds_v"]), float(config["bias_protocol"]["vds_v"]))
            )
            reproduced = point(rows, level, vgs_v)
            reference_current = abs(float(reference["drain_current_a_per_cm"]))
            reproduced_current = abs(float(reproduced["drain_current_a_per_cm"]))
            output.append({
                "mesh_level": level,
                "vgs_v": vgs_v,
                "vds_v": float(config["bias_protocol"]["vds_v"]),
                "t01_db_abs_drain_current_a_per_cm": reference_current,
                "t01_dc_abs_drain_current_a_per_cm": reproduced_current,
                "relative_current_difference": abs(reference_current - reproduced_current)
                / max(reference_current, reproduced_current, 1.0e-300),
                "t01_db_center_channel_potential_v": float(
                    reference["center_channel_potential_v"]
                ),
                "t01_dc_center_channel_potential_v": float(
                    reproduced["center_channel_potential_v"]
                ),
                "center_channel_potential_difference_v": abs(
                    float(reference["center_channel_potential_v"])
                    - float(reproduced["center_channel_potential_v"])
                ),
            })
    return output


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))


def render_extraction_figure(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    path: Path,
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    figure, (current_axis, gm_axis) = plt.subplots(
        1, 2, figsize=(10.6, 4.6), constrained_layout=True
    )
    colors = {"production": "#2563a6", "reference": "#c45d25"}
    styles = {"production": "-", "reference": "--"}
    for metric in metrics:
        role = str(metric["mesh_role"])
        level = str(metric["mesh_level"])
        mesh_rows = rows_for_mesh(rows, level)
        voltages = [float(row["vgs_v"]) for row in mesh_rows]
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in mesh_rows]
        label = "interface 4x" if role == "production" else "interface 8x check"
        current_axis.semilogy(
            voltages, currents, styles[role], color=colors[role], linewidth=1.8, label=label
        )
        current_axis.axvline(
            float(metric["vth_proxy_v"]), color=colors[role], linestyle=":", linewidth=1.2
        )
        fit_x = [float(metric["ss_fit_vgs_min_v"]), float(metric["ss_fit_vgs_max_v"])]
        fit_y = [
            10.0 ** (
                float(metric["ss_fit_slope_dec_per_v"]) * value
                + float(metric["ss_fit_intercept"])
            )
            for value in fit_x
        ]
        current_axis.semilogy(fit_x, fit_y, color=colors[role], linewidth=3.2, alpha=0.35)

        gm_values: list[float] = []
        gm_vgs: list[float] = []
        for index in range(1, len(mesh_rows) - 1):
            gm_vgs.append(voltages[index])
            gm_values.append(
                (currents[index + 1] - currents[index - 1])
                / (voltages[index + 1] - voltages[index - 1])
            )
        gm_axis.plot(
            gm_vgs, gm_values, styles[role], color=colors[role], linewidth=1.8, label=label
        )
        gm_axis.scatter(
            [float(config["extraction_methods"]["field_effect_mobility_proxy"]["vgs_center_v"])],
            [float(metric["gm_at_mobility_point_s_per_cm"])],
            color=colors[role], s=28, zorder=3,
        )

    criterion = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "expected_current_per_width_a_per_cm"
        ]
    )
    current_axis.axhline(
        criterion, color="#555555", linestyle="-.", linewidth=1.0,
        label="constant-current criterion",
    )
    current_axis.set_title("Low-VDS transfer and proxy extraction")
    current_axis.set_xlabel("VGS (V)")
    current_axis.set_ylabel("Absolute drain current per width (A/cm)")
    current_axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    current_axis.legend(fontsize=8, loc="best")
    gm_axis.set_title("Sampled transconductance")
    gm_axis.set_xlabel("VGS (V)")
    gm_axis.set_ylabel("d|Id/W| / dVGS (S/cm)")
    gm_axis.grid(True, color="#d8dee3", linewidth=0.6)
    gm_axis.legend(fontsize=8, loc="best")
    figure.suptitle("T01-D-C single-gate IGZO numerical proxies", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def render_state_figure(
    config: dict[str, Any], state_entries: list[dict[str, Any]], path: Path
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.colors import Normalize  # noqa: PLC0415
    from matplotlib.cm import ScalarMappable  # noqa: PLC0415

    ordered = [
        next(entry for entry in state_entries if entry["state_id"] == state_id)
        for state_id in config["acceptance"]["required_state_ids"]
    ]
    potentials = [
        float(row["potential_v"])
        for entry in ordered for row in entry["_node_rows"]
    ]
    log_density = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
        for entry in ordered for row in entry["_node_rows"]
        if row["region"] == "channel"
    ]
    log_current = [
        math.log10(max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1.0e-300))
        for entry in ordered for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(log_density), max(log_density)),
        Normalize(min(log_current), max(log_current)),
    ]
    cmaps = ["viridis", "plasma", "magma"]
    figure, axes = plt.subplots(3, 3, figsize=(11.2, 8.0), constrained_layout=True)
    for row_index, entry in enumerate(ordered):
        nodes = entry["_node_rows"]
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        elements = entry["_element_rows"]
        axes[row_index][0].scatter(
            [float(row["x_um"]) for row in nodes],
            [float(row["y_nm"]) for row in nodes],
            c=[float(row["potential_v"]) for row in nodes],
            cmap=cmaps[0], norm=norms[0], s=5, linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes],
            [float(row["y_nm"]) for row in channel_nodes],
            c=[
                math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
                for row in channel_nodes
            ],
            cmap=cmaps[1], norm=norms[1], s=6, linewidths=0,
        )
        axes[row_index][2].scatter(
            [float(row["centroid_x_um"]) for row in elements],
            [float(row["centroid_y_nm"]) for row in elements],
            c=[
                math.log10(
                    max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1.0e-300)
                )
                for row in elements
            ],
            cmap=cmaps[2], norm=norms[2], s=6, linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-1.0, 55.0)
            axis.axhline(30.0, color="white" if column != 1 else "#555555", linewidth=0.6)
            axis.set_ylabel(f"{entry['state_label']}\ny (nm)")
            if row_index == 2:
                axis.set_xlabel("x (um)")
    axes[0][0].set_title("Potential (V)")
    axes[0][1].set_title("log10 electron density (cm^-3)")
    axes[0][2].set_title("log10 |J| (A/cm^2)")
    for column, (norm, cmap) in enumerate(zip(norms, cmaps)):
        figure.colorbar(
            ScalarMappable(norm=norm, cmap=cmap), ax=axes[:, column], shrink=0.82, pad=0.02
        )
    figure.suptitle(
        "T01-D-C representative internal states (vertical display scale expanded)", fontsize=12
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    baseline: dict[str, Any],
    config: dict[str, Any],
    mesh_report: dict[str, Any],
    db_report: dict[str, Any],
    rows: list[dict[str, Any]],
    mesh_summaries: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    reproductions: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    extraction_figure: Path,
    state_figure: Path,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    expected_grid = extraction_vgs_values(config)
    expected_meshes = list(acceptance["required_mesh_levels"])
    by_mesh = {level: rows_for_mesh(rows, level) for level in expected_meshes}
    add_check(
        checks,
        "configured_low_vds_extraction_grid_completed",
        len(rows) == int(acceptance["required_total_reported_bias_points"])
        and all(
            [float(row["vgs_v"]) for row in by_mesh[level]] == expected_grid
            and all(row["stage_id"] == "T01_DC_EXTRACTION" for row in by_mesh[level])
            and all(same_value(float(row["vds_v"]), float(config["bias_protocol"]["vds_v"])) for row in by_mesh[level])
            for level in expected_meshes
        ),
        f"meshes={len(expected_meshes)} points_per_mesh={len(expected_grid)} total={len(rows)}",
    )
    solver_records = [
        record for summary in mesh_summaries for record in summary["solver_records"]
    ]
    add_check(
        checks,
        "all_dc_solves_converged",
        len(solver_records) == int(acceptance["required_total_dc_solve_count"])
        and all(record["converged"] is True for record in solver_records),
        f"solver_records={len(solver_records)}",
    )
    finite_directional = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and math.isfinite(float(row["source_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        for row in rows
    )
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in rows)
    add_check(
        checks,
        "finite_directional_and_conserved_terminal_current",
        finite_directional
        and max_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"points={len(rows)} maximum_relative_imbalance={max_imbalance:.6e}",
    )
    max_drop = 0.0
    monotonic = True
    for level in expected_meshes:
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in by_mesh[level]]
        for lower, higher in zip(currents, currents[1:]):
            drop = max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
            max_drop = max(max_drop, drop)
            monotonic = monotonic and drop <= float(
                acceptance["maximum_monotonic_relative_current_drop"]
            )
    add_check(
        checks,
        "drain_current_monotonic_with_vgs",
        monotonic,
        f"maximum_relative_drop={max_drop:.6e}",
    )
    dependency_counts = {
        row["mesh_level"]: (
            int(row["node_count_with_interface_duplicates"]), int(row["element_count"])
        )
        for row in mesh_report["mesh"]
        if row["mesh_level"] in expected_meshes
    }
    summary_counts = {
        row["mesh_level"]: (
            int(row["node_count_with_interface_duplicates"]), int(row["element_count"])
        )
        for row in mesh_summaries
    }
    add_check(
        checks,
        "production_and_reference_mesh_metrics_reported",
        [row["mesh_level"] for row in mesh_summaries] == expected_meshes
        and summary_counts == dependency_counts,
        f"counts={summary_counts}",
    )
    proxies_finite = all(
        math.isfinite(float(row[key])) and float(row[key]) > 0.0
        for row in metrics
        for key in ("vth_proxy_v", "ss_proxy_mv_per_dec", "mobility_proxy_cm2_vs")
    )
    fits_valid = all(
        int(row["ss_fit_point_count"]) >= int(acceptance["minimum_ss_fit_point_count"])
        and float(row["ss_fit_r_squared"]) >= float(acceptance["minimum_ss_fit_r_squared"])
        and row["parameter_claim_status"] == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
        for row in metrics
    )
    add_check(
        checks,
        "limited_numerical_proxies_are_finite_and_auditable",
        len(metrics) == len(expected_meshes) and proxies_finite and fits_valid,
        "metrics=" + "; ".join(
            f"{row['mesh_level']}: VTH={float(row['vth_proxy_v']):.6g} V, "
            f"SS={float(row['ss_proxy_mv_per_dec']):.6g} mV/dec, "
            f"mu={float(row['mobility_proxy_cm2_vs']):.6g} cm2/Vs, "
            f"nfit={row['ss_fit_point_count']}, R2={float(row['ss_fit_r_squared']):.6g}"
            for row in metrics
        ),
    )
    production_metric, reference_metric = metrics
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
        "numerical_proxy_mesh_agreement",
        vth_difference <= float(acceptance["maximum_vth_proxy_mesh_difference_v"])
        and ss_difference <= float(acceptance["maximum_ss_proxy_mesh_relative_difference"])
        and mobility_difference <= float(
            acceptance["maximum_mobility_proxy_mesh_relative_difference"]
        ),
        f"dVTH={vth_difference:.6e} V dSS_rel={ss_difference:.6e} dmu_rel={mobility_difference:.6e}",
    )
    max_anchor_current = max(float(row["relative_current_difference"]) for row in reproductions)
    max_anchor_potential = max(
        float(row["center_channel_potential_difference_v"]) for row in reproductions
    )
    add_check(
        checks,
        "t01_db_low_vds_anchors_reproduced",
        len(reproductions)
        == len(expected_meshes) * len(acceptance["required_t01_db_anchor_vgs_values_v"])
        and max_anchor_current
        <= float(acceptance["maximum_t01_db_anchor_relative_current_difference"])
        and max_anchor_potential
        <= float(acceptance["maximum_t01_db_anchor_potential_difference_v"]),
        f"max_current_relative={max_anchor_current:.6e} max_potential_v={max_anchor_potential:.6e}",
    )
    required_states = list(acceptance["required_state_ids"])
    state_files_valid = True
    for entry in state_entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        state_files_valid = state_files_valid and node_path.is_file() and element_path.is_file()
        state_files_valid = state_files_valid and entry["node_csv_sha256"] == core.sha256(node_path)
        state_files_valid = state_files_valid and entry["element_csv_sha256"] == core.sha256(element_path)
        state_files_valid = state_files_valid and int(entry["channel_element_count"]) > 0
        state_files_valid = state_files_valid and len(entry["vtk_files"]) >= 3
        state_files_valid = state_files_valid and all(
            (ROOT / item["path"]).is_file() and item["sha256"] == core.sha256(ROOT / item["path"])
            for item in entry["vtk_files"]
        )
        state_files_valid = state_files_valid and all(
            math.isfinite(float(row[field]))
            for row in entry["_element_rows"]
            for field in (
                "electron_current_density_x_a_per_cm2",
                "electron_current_density_y_a_per_cm2",
                "electron_current_density_magnitude_a_per_cm2",
            )
        )
    add_check(
        checks,
        "three_state_potential_density_and_current_density_outputs",
        [entry["state_id"] for entry in state_entries] == required_states and state_files_valid,
        f"states={[entry['state_id'] for entry in state_entries]} vtk_files={sum(len(entry['vtk_files']) for entry in state_entries)}",
    )
    state_currents = [float(entry["absolute_drain_current_a_per_cm"]) for entry in state_entries]
    state_densities = [
        float(entry["center_channel_electron_density_cm3"]) for entry in state_entries
    ]
    add_check(
        checks,
        "representative_state_ordering",
        all(higher > lower for lower, higher in zip(state_currents, state_currents[1:]))
        and all(higher > lower for lower, higher in zip(state_densities, state_densities[1:])),
        f"currents={state_currents} center_densities={state_densities}",
    )
    figure_bytes = [
        path.stat().st_size if path.is_file() else 0 for path in (extraction_figure, state_figure)
    ]
    add_check(
        checks,
        "report_figures_written",
        all(value > 0 for value in figure_bytes),
        f"bytes={figure_bytes}",
    )
    prerequisites_pass = (
        mesh_report.get("status") == "PASS"
        and mesh_report.get("mesh_convergence", {}).get("status") == "PASS"
        and db_report.get("status") == "PASS"
        and db_report.get("idvd_completion", {}).get("t01_dc_stage_permitted_next") is True
    )
    add_check(
        checks,
        "prior_t01_stage_gates_passed",
        prerequisites_pass,
        f"T01-D-A={mesh_report.get('status')} T01-D-B={db_report.get('status')}",
    )
    failures = [name for name, result in checks.items() if result["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "maximum_monotonic_relative_current_drop": max_drop,
        "vth_proxy_mesh_difference_v": vth_difference,
        "ss_proxy_mesh_relative_difference": ss_difference,
        "mobility_proxy_mesh_relative_difference": mobility_difference,
        "maximum_t01_db_anchor_relative_current_difference": max_anchor_current,
        "maximum_t01_db_anchor_potential_difference_v": max_anchor_potential,
        "production_vth_proxy_minus_teaching_target_v": float(
            production_metric["vth_proxy_v"]
        ) - float(baseline["materials"]["channel"]["threshold_target_v"]),
    }


def public_state_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config", type=Path, default=ROOT / "config" / "tcad_t01_d_extraction.json"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = core.load_json(config_path)
    baseline_path = ROOT / config["input_contract"]["path"]
    contract_report_path = ROOT / config["input_contract"]["report"]
    dependency = config["dependencies"]
    mesh_config_path = ROOT / dependency["mesh_config"]
    mesh_report_path = ROOT / dependency["mesh_report"]
    db_config_path = ROOT / dependency["idvd_config"]
    db_report_path = ROOT / dependency["idvd_report"]
    baseline = core.load_json(baseline_path)
    contract_report = core.load_json(contract_report_path)
    mesh_config = core.load_json(mesh_config_path)
    mesh_report = core.load_json(mesh_report_path)
    db_config = core.load_json(db_config_path)
    db_report = core.load_json(db_report_path)

    if baseline.get("case_id") != config["input_contract"]["case_id"]:
        raise RuntimeError("T01-A baseline case ID changed")
    if contract_report.get("contract_status") != config["input_contract"]["required_contract_status"]:
        raise RuntimeError("T01-A input contract is not PASS")
    if (
        mesh_report.get("case_id") != mesh_config.get("case_id")
        or mesh_report.get("stage") != dependency["required_mesh_stage"]
        or mesh_report.get("status") != dependency["required_mesh_status"]
        or mesh_report.get("mesh_convergence", {}).get("status")
        != dependency["required_mesh_convergence_status"]
    ):
        raise RuntimeError("T01-D-A dependency gate is not open")
    if (
        db_report.get("case_id") != db_config.get("case_id")
        or db_report.get("stage") != dependency["required_idvd_stage"]
        or db_report.get("status") != dependency["required_idvd_status"]
        or db_report.get("idvd_completion", {}).get("t01_dc_stage_permitted_next")
        is not dependency["require_t01_dc_stage_permitted_next"]
    ):
        raise RuntimeError("T01-D-B dependency gate is not open")

    stage1 = mesh_stage.stage_by_id(baseline, "T01_A_STAGE_1")
    stage2 = mesh_stage.stage_by_id(baseline, "T01_A_STAGE_2")
    protocol = config["bias_protocol"]
    grid = extraction_vgs_values(config)
    if (
        [float(value) for value in stage1["vds_values_v"]]
        != [float(value) for value in protocol["low_vds_values_v"]]
        or not same_value(float(stage2["vds_v"]), float(protocol["vds_v"]))
        or min(grid) < min(float(value) for value in stage2["vgs_values_v"])
        or max(grid) > max(float(value) for value in stage2["vgs_values_v"])
        or not set(float(value) for value in stage2["vgs_values_v"]) <= set(grid)
    ):
        raise RuntimeError("T01-D-C grid is inconsistent with frozen T01-A low-VDS bounds")
    required_meshes = config["acceptance"]["required_mesh_levels"]
    if required_meshes != [config["mesh"]["production_level"], config["mesh"]["reference_level"]]:
        raise RuntimeError("T01-D-C mesh role order differs from acceptance")
    if not set(required_meshes) <= set(mesh_stage.level_map(mesh_config)):
        raise RuntimeError("T01-D-C mesh levels are absent from T01-D-A")
    if len(grid) != int(config["acceptance"]["required_reported_bias_points_per_mesh"]):
        raise RuntimeError("T01-D-C configured grid count differs from acceptance")
    expected_solves_per_mesh = (
        2
        + len(protocol["low_vds_values_v"])
        + len(protocol["negative_gate_preconditioning_v"])
        + len(grid)
        - 1
    )
    if expected_solves_per_mesh * len(required_meshes) != int(
        config["acceptance"]["required_total_dc_solve_count"]
    ):
        raise RuntimeError("T01-D-C configured solve count differs from acceptance")
    state_vgs = [float(state["vgs_v"]) for state in protocol["state_points"]]
    if not all(any(same_value(value, grid_value) for grid_value in grid) for value in state_vgs):
        raise RuntimeError("T01-D-C state points must belong to the extraction grid")

    width = float(baseline["device"]["width_cm"])
    length = float(baseline["device"]["channel_length_cm"])
    vth_method = config["extraction_methods"]["constant_current_vth_proxy"]
    derived_terminal_criterion = float(vth_method["criterion_prefactor_a"]) * width / length
    if not same_value(derived_terminal_criterion, float(vth_method["expected_terminal_current_a"])):
        raise RuntimeError("T01-D-C constant-current criterion no longer matches W/L")

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    transfer_path = ROOT / outputs["transfer_csv"]
    mesh_summary_path = ROOT / outputs["mesh_summary_csv"]
    comparison_path = ROOT / outputs["mesh_comparison_csv"]
    parameter_path = ROOT / outputs["parameter_metrics_csv"]
    state_summary_path = ROOT / outputs["state_summary_csv"]
    reproduction_path = ROOT / outputs["t01_db_reproduction_csv"]
    extraction_figure_path = ROOT / outputs["extraction_figure_png"]
    state_figure_path = ROOT / outputs["state_figure_png"]
    report_path = ROOT / outputs["report"]

    snapshot = {
        "extraction_config_path": str(config_path.relative_to(ROOT)),
        "extraction_config_sha256": core.sha256(config_path),
        "baseline_config_path": str(baseline_path.relative_to(ROOT)),
        "baseline_config_sha256": core.sha256(baseline_path),
        "t01_a_contract_report_path": str(contract_report_path.relative_to(ROOT)),
        "t01_a_contract_report_sha256": core.sha256(contract_report_path),
        "mesh_config_path": str(mesh_config_path.relative_to(ROOT)),
        "mesh_config_sha256": core.sha256(mesh_config_path),
        "mesh_report_path": str(mesh_report_path.relative_to(ROOT)),
        "mesh_report_sha256": core.sha256(mesh_report_path),
        "idvd_config_path": str(db_config_path.relative_to(ROOT)),
        "idvd_config_sha256": core.sha256(db_config_path),
        "idvd_report_path": str(db_report_path.relative_to(ROOT)),
        "idvd_report_sha256": core.sha256(db_report_path),
        "baseline_case_id": baseline["case_id"],
        "mesh_case_id": mesh_report["case_id"],
        "idvd_case_id": db_report["case_id"],
        "extraction_case_id": config["case_id"],
        "baseline": baseline,
        "mesh_refinement": mesh_config,
        "idvd": db_config,
        "extraction": config,
    }
    core.write_json(snapshot_path, snapshot)

    rows: list[dict[str, Any]] = []
    mesh_summaries: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t01-d-extract",
        "validation_command": "make t01-d-extract-check",
        "mesh_runs": [],
        "errors": [],
    }
    caught_error: Exception | None = None
    for role, level in zip(
        config["acceptance"]["required_mesh_roles"], required_meshes, strict=True
    ):
        try:
            mesh_rows, summary, states = run_mesh(
                baseline, config, mesh_config, role, level, run_dir
            )
            rows.extend(mesh_rows)
            mesh_summaries.append(summary)
            state_entries.extend(states)
            solver_log["mesh_runs"].append({
                "mesh_role": role,
                "mesh_level": level,
                "status": "PASS",
                "solver_records": summary["solver_records"],
            })
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"mesh_level": level, "error": repr(error)})
            solver_log["mesh_runs"].append({
                "mesh_role": role, "mesh_level": level, "status": "FAIL"
            })
            break

    completed = len(mesh_summaries) == len(required_meshes)
    metrics = build_parameter_metrics(baseline, config, rows) if completed else []
    comparisons = build_mesh_comparisons(config, rows) if completed else []
    reproductions = build_db_reproduction(config, rows, db_report) if completed else []
    extraction_figure_sha256: str | None = None
    state_figure_sha256: str | None = None
    if caught_error is None and completed:
        try:
            extraction_figure_sha256 = render_extraction_figure(
                config, rows, metrics, extraction_figure_path
            )
            state_figure_sha256 = render_state_figure(
                config, state_entries, state_figure_path
            )
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"mesh_level": "figures", "error": repr(error)})

    core.write_csv(transfer_path, rows, TRANSFER_FIELDNAMES)
    core.write_csv(
        mesh_summary_path,
        [{key: value for key, value in row.items() if key != "solver_records"} for row in mesh_summaries],
        MESH_SUMMARY_FIELDNAMES,
    )
    core.write_csv(comparison_path, comparisons, MESH_COMPARISON_FIELDNAMES)
    core.write_csv(parameter_path, metrics, PARAMETER_FIELDNAMES)
    core.write_csv(
        state_summary_path,
        [
            {key: entry[key] for key in STATE_SUMMARY_FIELDNAMES}
            for entry in state_entries
        ],
        STATE_SUMMARY_FIELDNAMES,
    )
    core.write_csv(reproduction_path, reproductions, DB_REPRODUCTION_FIELDNAMES)
    core.write_json(state_manifest_path, {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "entries": [public_state_entry(entry) for entry in state_entries],
    })
    core.write_json(solver_log_path, solver_log)

    if caught_error is None and completed:
        assessment = assess(
            baseline,
            config,
            mesh_report,
            db_report,
            rows,
            mesh_summaries,
            metrics,
            comparisons,
            reproductions,
            state_entries,
            extraction_figure_path,
            state_figure_path,
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {"stage_exception": {"status": "FAIL", "detail": repr(caught_error)}},
            "failures": ["stage_exception"],
        }
    passed = assessment["status"] == "PASS"
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": "2D single-bottom-gate n-IGZO electron-only drift-diffusion teaching model",
        "executed_bias_stage_ids": config["scope"]["executed_bias_stage_ids"],
        "reported_bias_stage_id": config["scope"]["reported_bias_stage_id"],
        "baseline_case_id": baseline["case_id"],
        "t01_da_case_id": mesh_report["case_id"],
        "t01_db_case_id": db_report["case_id"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "command": "make t01-d-extract",
            "validation_command": "make t01-d-extract-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "mesh": [
            {key: value for key, value in row.items() if key != "solver_records"}
            for row in mesh_summaries
        ],
        "bias_points": rows,
        "parameter_proxies": metrics,
        "mesh_comparison": comparisons,
        "t01_db_reproduction": reproductions,
        "state_outputs": [public_state_entry(entry) for entry in state_entries],
        "figures": {
            "extraction": {
                "path": str(extraction_figure_path.relative_to(ROOT)),
                "sha256": extraction_figure_sha256,
            },
            "states": {
                "path": str(state_figure_path.relative_to(ROOT)),
                "sha256": state_figure_sha256,
            },
        },
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {
            key: value for key, value in assessment.items()
            if key not in {"status", "checks", "failures"}
        },
        "t01_completion": {
            "status": "PASS" if passed else "FAIL",
            "complete_t01_numerical_stage_gate": "PASS" if passed else "FAIL",
            "requirements": {
                "complete_low_vds_bias_sweep": assessment["checks"].get(
                    "configured_low_vds_extraction_grid_completed", {"status": "FAIL"}
                )["status"],
                "terminal_current_conservation": assessment["checks"].get(
                    "finite_directional_and_conserved_terminal_current", {"status": "FAIL"}
                )["status"],
                "mesh_metrics_and_proxy_comparison": assessment["checks"].get(
                    "numerical_proxy_mesh_agreement", {"status": "FAIL"}
                )["status"],
                "potential_electron_density_current_density_states": assessment["checks"].get(
                    "three_state_potential_density_and_current_density_outputs", {"status": "FAIL"}
                )["status"],
            },
            "t02_stage_permitted_next": passed,
            "experimental_calibration_permitted": False,
            "physical_parameter_validation_permitted": False,
            "physical_ion_ioff_claim_permitted": False,
            "compact_model_calibrated": False,
        },
        "teaching_target_diagnostic_only": {
            "configured_threshold_target_v": float(
                baseline["materials"]["channel"]["threshold_target_v"]
            ),
            "acceptance_depends_on_target_match": False,
        },
        "limitations": [
            "VTH, SS, gm, mobility, and current span are numerical proxies of the frozen teaching model, not experimentally validated device parameters.",
            "The numerical current span must not be labelled physical Ion/Ioff because traps, leakage mechanisms, non-ideal contacts, and measurement floor are absent.",
            "The physical-oxide field-effect mobility proxy uses a fixed low-VDS finite difference and is not required to equal the configured constant transport mobility.",
            "State maps cover three configured low-VDS points on interface_4x; the vertical display scale is expanded and local current density is distinct from terminal current per width.",
            "T01 completion opens T02 only as an E2 teaching-model stage; experimental calibration, compact-model validation, SPICE, and layout remain separate later gates.",
        ],
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T01_D_EXTRACTION_{report['status']} meshes={len(mesh_summaries)} "
        f"bias_points={len(rows)} states={len(state_entries)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T01_D_EXTRACTION_ERROR {caught_error}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
