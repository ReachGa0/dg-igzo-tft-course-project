#!/usr/bin/env python3
"""Run the frozen T02-C bidirectional dual-gate transfer families."""

from __future__ import annotations

import argparse
import copy
import json
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

import run_t01_single_gate_extraction as t01_extract  # noqa: E402
import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402
import run_t02_dual_gate_minimal_bias as t02_b  # noqa: E402


core = t02_a.core
ENABLED_REGIONS = t02_a.ENABLED_REGIONS
STAGE_ID = "T02_C_BIDIRECTIONAL"

FAMILY_FIELDNAMES = [
    "family_id", "primary_gate", "secondary_gate", "sweep_direction", "sweep_index",
    "mesh_level", "stage_id", "mode_id", "primary_gate_v", "fixed_secondary_gate_v",
    "vbg_v", "vtg_v", "vds_v", "source_current_a_per_cm",
    "drain_current_a_per_cm", "source_current_terminal_a", "drain_current_terminal_a",
    "current_imbalance_a_per_cm", "relative_current_imbalance",
    "center_channel_potential_v", "center_channel_electron_density_cm3",
    "solve_seconds", "converged",
]
METRIC_FIELDNAMES = [
    "family_id", "primary_gate", "secondary_gate", "fixed_secondary_gate_v",
    "constant_current_criterion_terminal_a", "constant_current_criterion_a_per_cm",
    "vth_proxy_v", "delta_vth_proxy_v", "vth_bracket_lower_primary_gate_v",
    "vth_bracket_upper_primary_gate_v", "vth_bracket_lower_current_a_per_cm",
    "vth_bracket_upper_current_a_per_cm", "gm_evaluation_primary_gate_v",
    "gm_proxy_s_per_cm", "gm_proxy_terminal_s", "maximum_sampled_gm_s_per_cm",
    "maximum_sampled_gm_primary_gate_v", "coupling_slope_v_per_v",
    "coupling_fit_intercept_v", "coupling_fit_r_squared", "parameter_claim_status",
]
REVERSE_FIELDNAMES = [
    "family_id", "primary_gate_v", "fixed_secondary_gate_v",
    "forward_abs_drain_current_a_per_cm", "reverse_abs_drain_current_a_per_cm",
    "relative_current_difference", "forward_center_channel_potential_v",
    "reverse_center_channel_potential_v", "center_channel_potential_difference_v",
    "forward_center_channel_electron_density_cm3",
    "reverse_center_channel_electron_density_cm3", "center_density_relative_difference",
]
RECIPROCAL_FIELDNAMES = [
    "fixed_secondary_gate_v", "primary_gate_v", "top_primary_vbg_v", "top_primary_vtg_v",
    "bottom_primary_vbg_v", "bottom_primary_vtg_v",
    "top_primary_abs_drain_current_a_per_cm", "bottom_primary_abs_drain_current_a_per_cm",
    "relative_current_difference", "top_primary_center_channel_potential_v",
    "bottom_primary_center_channel_potential_v", "center_channel_potential_difference_v",
    "top_primary_center_channel_electron_density_cm3",
    "bottom_primary_center_channel_electron_density_cm3", "center_density_relative_difference",
]
STATE_NODE_FIELDNAMES = [
    "state_id", "state_label", "source_family", "mesh_level", "stage_id", "mode_id",
    "source_v", "drain_v", "vbg_v", "vtg_v", "region", "x_cm", "y_cm", "x_um",
    "y_nm", "potential_v", "electron_density_cm3",
]
STATE_ELEMENT_FIELDNAMES = [
    "state_id", "state_label", "source_family", "mesh_level", "stage_id", "vbg_v",
    "vtg_v", "vds_v", "region", "element_index", "node0_index", "node1_index",
    "node2_index", "x0_cm", "y0_cm", "x1_cm", "y1_cm", "x2_cm", "y2_cm",
    "centroid_x_cm", "centroid_y_cm", "centroid_x_um", "centroid_y_nm",
    "electron_current_density_x_en0_a_per_cm2",
    "electron_current_density_x_en1_a_per_cm2",
    "electron_current_density_x_en2_a_per_cm2",
    "electron_current_density_y_en0_a_per_cm2",
    "electron_current_density_y_en1_a_per_cm2",
    "electron_current_density_y_en2_a_per_cm2",
    "electron_current_density_x_a_per_cm2", "electron_current_density_y_a_per_cm2",
    "electron_current_density_magnitude_a_per_cm2",
    "mean_element_node_current_density_magnitude_a_per_cm2",
    "maximum_element_node_current_density_magnitude_a_per_cm2", "projection_method",
]
STATE_SUMMARY_FIELDNAMES = [
    "state_id", "state_label", "source_family", "mesh_level", "stage_id", "vbg_v",
    "vtg_v", "vds_v", "absolute_drain_current_a_per_cm", "drain_current_terminal_a",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "node_row_count", "channel_node_count",
    "channel_element_count", "minimum_potential_v", "maximum_potential_v",
    "minimum_electron_density_cm3", "maximum_electron_density_cm3",
    "minimum_cell_current_density_magnitude_a_per_cm2",
    "median_cell_current_density_magnitude_a_per_cm2",
    "maximum_cell_current_density_magnitude_a_per_cm2", "node_csv", "element_csv",
    "vtk_file_count",
]


def same_value(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1.0e-12)


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def voltage_token(value: float) -> str:
    return f"{value:.3f}".replace("-", "m").replace(".", "p")


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T02-C primary-gate range is not integral")
    values = [round(start + index * step, 12) for index in range(intervals + 1)]
    if len(values) != int(spec["point_count"]):
        raise ValueError("T02-C primary-gate point count differs from the contract")
    return values


def family_biases(family_id: str, primary_v: float, secondary_v: float) -> tuple[float, float]:
    if family_id == "top_primary":
        return secondary_v, primary_v
    if family_id == "bottom_primary":
        return primary_v, secondary_v
    raise ValueError(f"unknown T02-C family {family_id}")


def set_family_biases(
    device: str,
    family_id: str,
    *,
    source_v: float,
    drain_v: float,
    primary_v: float,
    secondary_v: float,
) -> None:
    vbg_v, vtg_v = family_biases(family_id, primary_v, secondary_v)
    t02_a.set_enabled_biases(
        device,
        source_v=source_v,
        drain_v=drain_v,
        bottom_gate_v=vbg_v,
        top_gate_v=vtg_v,
    )


def collect_family_row(
    device: str,
    runtime: dict[str, Any],
    mesh_level: str,
    mode_id: str,
    family: dict[str, Any],
    direction: str,
    sweep_index: int,
    primary_v: float,
    secondary_v: float,
    vds_v: float,
    solve_record: dict[str, Any],
) -> dict[str, Any]:
    vbg_v, vtg_v = family_biases(str(family["family_id"]), primary_v, secondary_v)
    base = core.collect_bias_row(
        device,
        runtime,
        mesh_level=mesh_level,
        stage_id=STAGE_ID,
        vds_v=vds_v,
        vgs_v=vbg_v,
        solve_record=solve_record,
    )
    return {
        "family_id": family["family_id"],
        "primary_gate": family["primary_gate"],
        "secondary_gate": family["secondary_gate"],
        "sweep_direction": direction,
        "sweep_index": sweep_index,
        "mesh_level": mesh_level,
        "stage_id": STAGE_ID,
        "mode_id": mode_id,
        "primary_gate_v": primary_v,
        "fixed_secondary_gate_v": secondary_v,
        "vbg_v": vbg_v,
        "vtg_v": vtg_v,
        "vds_v": vds_v,
        "source_current_a_per_cm": base["source_current_a_per_cm"],
        "drain_current_a_per_cm": base["drain_current_a_per_cm"],
        "source_current_terminal_a": base["source_current_terminal_a"],
        "drain_current_terminal_a": base["drain_current_terminal_a"],
        "current_imbalance_a_per_cm": base["current_imbalance_a_per_cm"],
        "relative_current_imbalance": base["relative_current_imbalance"],
        "center_channel_potential_v": base["center_channel_potential_v"],
        "center_channel_electron_density_cm3": base[
            "center_channel_electron_density_cm3"
        ],
        "solve_seconds": base["solve_seconds"],
        "converged": base["converged"],
    }


def collect_current_elements(
    device: str, mesh_level: str, state: dict[str, Any]
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
        raise RuntimeError("T02-C current projection needs three values per triangle")

    rows: list[dict[str, Any]] = []
    for index, node_indexes_raw in enumerate(elements):
        if len(node_indexes_raw) != 3:
            raise RuntimeError("T02-C current export requires triangular 2D elements")
        node_indexes = tuple(int(value) for value in node_indexes_raw)
        x_coordinates = [float(xs[value]) for value in node_indexes]
        y_coordinates = [float(ys[value]) for value in node_indexes]
        jx = [float(value) for value in jx_values[3 * index : 3 * index + 3]]
        jy = [float(value) for value in jy_values[3 * index : 3 * index + 3]]
        jx_center = sum(jx) / 3.0
        jy_center = sum(jy) / 3.0
        node_magnitudes = [math.hypot(x, y) for x, y in zip(jx, jy)]
        centroid_x = sum(x_coordinates) / 3.0
        centroid_y = sum(y_coordinates) / 3.0
        rows.append({
            "state_id": state["state_id"],
            "state_label": state["label"],
            "source_family": state["source_family"],
            "mesh_level": mesh_level,
            "stage_id": STAGE_ID,
            "vbg_v": float(state["vbg_v"]),
            "vtg_v": float(state["vtg_v"]),
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
            "electron_current_density_magnitude_a_per_cm2": math.hypot(
                jx_center, jy_center
            ),
            "mean_element_node_current_density_magnitude_a_per_cm2": (
                sum(node_magnitudes) / 3.0
            ),
            "maximum_element_node_current_density_magnitude_a_per_cm2": max(
                node_magnitudes
            ),
            "projection_method": (
                "DEVSIM element_from_edge_model; arithmetic mean of en0/en1/en2"
            ),
        })
    return rows


def write_state(
    device: str,
    runtime: dict[str, Any],
    mesh_level: str,
    mode_id: str,
    state: dict[str, Any],
    bias_row: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    bias = {
        "source_v": 0.0,
        "drain_v": float(state["vds_v"]),
        "bottom_gate_v": float(state["vbg_v"]),
        "top_gate_v": float(state["vtg_v"]),
    }
    node_rows = [
        {
            "state_id": state["state_id"],
            "state_label": state["label"],
            "source_family": state["source_family"],
            "mesh_level": mesh_level,
            "stage_id": STAGE_ID,
            **row,
        }
        for row in t02_a.collect_enabled_state(device, mode_id, bias)
    ]
    element_rows = collect_current_elements(device, mesh_level, state)
    base = f"t02_c_{state['state_id']}"
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
        "source_family": state["source_family"],
        "mesh_level": mesh_level,
        "stage_id": STAGE_ID,
        "vbg_v": float(state["vbg_v"]),
        "vtg_v": float(state["vtg_v"]),
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
        "median_cell_current_density_magnitude_a_per_cm2": statistics.median(
            current_values
        ),
        "maximum_cell_current_density_magnitude_a_per_cm2": max(current_values),
        "node_csv": str(node_path.relative_to(ROOT)),
        "element_csv": str(element_path.relative_to(ROOT)),
        "vtk_file_count": len(vtk_paths),
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


def fixed_secondary_ramp(target_v: float, step_v: float) -> list[float]:
    if same_value(target_v, 0.0):
        return []
    count = round(abs(target_v) / step_v)
    if count < 1 or not same_value(count * step_v, abs(target_v)):
        raise ValueError("fixed secondary voltage is not integral in the ramp step")
    sign = 1.0 if target_v > 0.0 else -1.0
    return [round(sign * step_v * index, 12) for index in range(1, count + 1)]


def run_family(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_a_config: dict[str, Any],
    config: dict[str, Any],
    family: dict[str, Any],
    fixed_secondary_v: float,
    run_dir: Path,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    list[dict[str, Any]],
]:
    protocol = config["bias_protocol"]
    mesh_level = config["inheritance"]["required_mesh_level"]
    runtime, mesh_spec = t02_a.mesh_stage.build_runtime_baseline(
        baseline, mesh_config, mesh_level
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = float(
        t02_a_config["top_stack_contract"]["enabled_mode"]["top_oxide_thickness_cm"]
    )
    family_id = str(family["family_id"])
    device = f"t02_c_{family_id}_{voltage_token(fixed_secondary_v)}"
    mode_id = t02_a_config["top_stack_contract"]["enabled_mode"]["mode_id"]
    records: list[dict[str, Any]] = []
    forward_rows: list[dict[str, Any]] = []
    reverse_rows: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    try:
        t02_a.initialize_enabled_device(
            device, runtime, t02_a_config, mesh_level, mesh_spec
        )
        regions, contacts, interfaces = t02_a.active_topology(device, ENABLED_REGIONS)
        node_count, element_count = t02_a.active_counts(device, ENABLED_REGIONS)
        set_family_biases(
            device,
            family_id,
            source_v=0.0,
            drain_v=0.0,
            primary_v=0.0,
            secondary_v=0.0,
        )
        records.append(
            core.solve_dc(
                device,
                runtime,
                f"T02_C_{family_id}_SEC_{fixed_secondary_v:.3f}_POISSON_ZERO",
                coupled=False,
            )
        )
        core.create_transport(device, runtime)
        records.append(
            core.solve_dc(
                device,
                runtime,
                f"T02_C_{family_id}_SEC_{fixed_secondary_v:.3f}_COUPLED_ZERO",
                coupled=True,
            )
        )
        core.devsim.element_from_edge_model(
            device=device, region="channel", edge_model="ElectronCurrent"
        )
        zero_source, zero_drain = t02_b.contact_currents(device)
        zero_state = t02_a.collect_enabled_state(
            device,
            mode_id,
            {
                "source_v": 0.0,
                "drain_v": 0.0,
                "bottom_gate_v": 0.0,
                "top_gate_v": 0.0,
            },
        )
        zero_equilibrium = {
            "source_current_a_per_cm": zero_source,
            "drain_current_a_per_cm": zero_drain,
            "maximum_absolute_terminal_current_a_per_cm": max(
                abs(zero_source), abs(zero_drain)
            ),
            "maximum_absolute_potential_v": t02_b.maximum_state_potential(zero_state),
            "node_count": len(zero_state),
        }

        for vds_v in [float(value) for value in protocol["low_vds_values_v"]]:
            set_family_biases(
                device,
                family_id,
                source_v=float(protocol["source_v"]),
                drain_v=vds_v,
                primary_v=0.0,
                secondary_v=0.0,
            )
            records.append(
                core.solve_dc(
                    device,
                    runtime,
                    f"T02_C_{family_id}_SEC_{fixed_secondary_v:.3f}_LOW_VDS_{vds_v:.6g}",
                    coupled=True,
                )
            )

        for secondary_v in fixed_secondary_ramp(
            fixed_secondary_v, float(protocol["fixed_secondary_ramp_step_v"])
        ):
            set_family_biases(
                device,
                family_id,
                source_v=float(protocol["source_v"]),
                drain_v=float(protocol["drain_v"]),
                primary_v=0.0,
                secondary_v=secondary_v,
            )
            records.append(
                core.solve_dc(
                    device,
                    runtime,
                    f"T02_C_{family_id}_SECONDARY_{secondary_v:.6g}",
                    coupled=True,
                )
            )

        precondition_records: dict[float, dict[str, Any]] = {}
        for primary_v in [
            float(value) for value in protocol["primary_negative_preconditioning_v"]
        ]:
            set_family_biases(
                device,
                family_id,
                source_v=float(protocol["source_v"]),
                drain_v=float(protocol["drain_v"]),
                primary_v=primary_v,
                secondary_v=fixed_secondary_v,
            )
            record = core.solve_dc(
                device,
                runtime,
                f"T02_C_{family_id}_SEC_{fixed_secondary_v:.3f}_PRE_{primary_v:.6g}",
                coupled=True,
            )
            records.append(record)
            precondition_records[round(primary_v, 12)] = record

        state_lookup = {
            (
                str(state["source_family"]),
                round(float(state["vbg_v"]), 12),
                round(float(state["vtg_v"]), 12),
            ): {**state, "vds_v": float(protocol["drain_v"])}
            for state in protocol["state_points"]
        }
        grid = primary_grid(config)
        last_forward_record: dict[str, Any] | None = None
        for index, primary_v in enumerate(grid):
            key = round(primary_v, 12)
            if index == 0 and key in precondition_records:
                solve_record = precondition_records[key]
            else:
                set_family_biases(
                    device,
                    family_id,
                    source_v=float(protocol["source_v"]),
                    drain_v=float(protocol["drain_v"]),
                    primary_v=primary_v,
                    secondary_v=fixed_secondary_v,
                )
                solve_record = core.solve_dc(
                    device,
                    runtime,
                    f"T02_C_{family_id}_SEC_{fixed_secondary_v:.3f}_FWD_{primary_v:.6g}",
                    coupled=True,
                )
                records.append(solve_record)
            last_forward_record = solve_record
            row = collect_family_row(
                device,
                runtime,
                mesh_level,
                mode_id,
                family,
                "forward",
                index,
                primary_v,
                fixed_secondary_v,
                float(protocol["drain_v"]),
                solve_record,
            )
            forward_rows.append(row)
            vbg_v, vtg_v = family_biases(family_id, primary_v, fixed_secondary_v)
            state = state_lookup.get(
                (family_id, round(vbg_v, 12), round(vtg_v, 12))
            )
            if state is not None:
                state_entries.append(
                    write_state(
                        device,
                        runtime,
                        mesh_level,
                        mode_id,
                        state,
                        row,
                        run_dir,
                    )
                )

        reverse_enabled = any(
            item["family_id"] == family_id
            and same_value(float(item["fixed_secondary_v"]), fixed_secondary_v)
            for item in protocol["reverse_paths"]
        )
        if reverse_enabled:
            if last_forward_record is None:
                raise RuntimeError("T02-C reverse path has no forward endpoint")
            for index, primary_v in enumerate(reversed(grid)):
                if index == 0:
                    solve_record = last_forward_record
                else:
                    set_family_biases(
                        device,
                        family_id,
                        source_v=float(protocol["source_v"]),
                        drain_v=float(protocol["drain_v"]),
                        primary_v=primary_v,
                        secondary_v=fixed_secondary_v,
                    )
                    solve_record = core.solve_dc(
                        device,
                        runtime,
                        f"T02_C_{family_id}_SEC_{fixed_secondary_v:.3f}_REV_{primary_v:.6g}",
                        coupled=True,
                    )
                    records.append(solve_record)
                reverse_rows.append(
                    collect_family_row(
                        device,
                        runtime,
                        mesh_level,
                        mode_id,
                        family,
                        "reverse",
                        index,
                        primary_v,
                        fixed_secondary_v,
                        float(protocol["drain_v"]),
                        solve_record,
                    )
                )

        summary = {
            "family_id": family_id,
            "primary_gate": family["primary_gate"],
            "secondary_gate": family["secondary_gate"],
            "fixed_secondary_gate_v": fixed_secondary_v,
            "mesh_level": mesh_level,
            "mode_id": mode_id,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(records),
            "forward_reported_point_count": len(forward_rows),
            "reverse_reported_point_count": len(reverse_rows),
            "state_count": len(state_entries),
            "zero_equilibrium": zero_equilibrium,
            "total_solve_seconds": sum(float(record["elapsed_seconds"]) for record in records),
            "wall_seconds": time.perf_counter() - wall_start,
        }
        return forward_rows, reverse_rows, state_entries, summary, records
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def rows_for_curve(
    rows: list[dict[str, Any]], family_id: str, secondary_v: float, direction: str
) -> list[dict[str, Any]]:
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
        index
        for index in range(len(xs) - 1)
        if xs[index] < target < xs[index + 1]
    )
    return ys[index] + (
        (target - xs[index])
        * (ys[index + 1] - ys[index])
        / (xs[index + 1] - xs[index])
    )


def threshold_and_gm(
    baseline: dict[str, Any], config: dict[str, Any], curve: list[dict[str, Any]]
) -> dict[str, Any]:
    method = config["extraction_methods"]["constant_current_vth_proxy"]
    gm_method = config["extraction_methods"]["gm_proxy"]
    criterion = float(method["expected_current_per_width_a_per_cm"])
    terminal_criterion = float(method["expected_terminal_current_a"])
    width_cm = float(baseline["device"]["width_cm"])
    if not same_value(terminal_criterion / width_cm, criterion):
        raise RuntimeError("T02-C terminal and per-width threshold criteria differ")
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    bracket_index = next(
        index
        for index in range(len(currents) - 1)
        if currents[index] <= criterion <= currents[index + 1]
    )
    lower_current = currents[bracket_index]
    upper_current = currents[bracket_index + 1]
    lower_voltage = voltages[bracket_index]
    upper_voltage = voltages[bracket_index + 1]
    log_lower = math.log10(max(lower_current, 1.0e-300))
    log_upper = math.log10(max(upper_current, 1.0e-300))
    vth = lower_voltage + (
        (math.log10(criterion) - log_lower)
        * (upper_voltage - lower_voltage)
        / (log_upper - log_lower)
    )
    gm_voltages: list[float] = []
    gm_values: list[float] = []
    for index in range(1, len(curve) - 1):
        gm_voltages.append(voltages[index])
        gm_values.append(
            (currents[index + 1] - currents[index - 1])
            / (voltages[index + 1] - voltages[index - 1])
        )
    gm_evaluation_voltage = vth + float(gm_method["evaluation_overdrive_v"])
    if not gm_voltages[0] <= gm_evaluation_voltage <= gm_voltages[-1]:
        raise RuntimeError(
            f"T02-C gm evaluation voltage {gm_evaluation_voltage} is outside the central-difference grid"
        )
    gm = interpolate(gm_voltages, gm_values, gm_evaluation_voltage)
    peak_index = max(range(len(gm_values)), key=lambda index: gm_values[index])
    return {
        "constant_current_criterion_terminal_a": terminal_criterion,
        "constant_current_criterion_a_per_cm": criterion,
        "vth_proxy_v": vth,
        "vth_bracket_lower_primary_gate_v": lower_voltage,
        "vth_bracket_upper_primary_gate_v": upper_voltage,
        "vth_bracket_lower_current_a_per_cm": lower_current,
        "vth_bracket_upper_current_a_per_cm": upper_current,
        "gm_evaluation_primary_gate_v": gm_evaluation_voltage,
        "gm_proxy_s_per_cm": gm,
        "gm_proxy_terminal_s": gm * width_cm,
        "maximum_sampled_gm_s_per_cm": gm_values[peak_index],
        "maximum_sampled_gm_primary_gate_v": gm_voltages[peak_index],
    }


def build_metrics(
    baseline: dict[str, Any], config: dict[str, Any], forward_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for family in config["bias_protocol"]["families"]:
        family_id = str(family["family_id"])
        family_metrics: list[dict[str, Any]] = []
        for secondary_v in [float(value) for value in family["fixed_secondary_values_v"]]:
            curve = rows_for_curve(forward_rows, family_id, secondary_v, "forward")
            values = threshold_and_gm(baseline, config, curve)
            family_metrics.append({
                "family_id": family_id,
                "primary_gate": family["primary_gate"],
                "secondary_gate": family["secondary_gate"],
                "fixed_secondary_gate_v": secondary_v,
                **values,
            })
        reference_vth = float(
            next(
                row["vth_proxy_v"]
                for row in family_metrics
                if same_value(float(row["fixed_secondary_gate_v"]), 0.0)
            )
        )
        secondary_values = [float(row["fixed_secondary_gate_v"]) for row in family_metrics]
        vth_values = [float(row["vth_proxy_v"]) for row in family_metrics]
        slope, intercept, r_squared = t01_extract.linear_regression(
            secondary_values, vth_values
        )
        for row in family_metrics:
            row["delta_vth_proxy_v"] = float(row["vth_proxy_v"]) - reference_vth
            row["coupling_slope_v_per_v"] = slope
            row["coupling_fit_intercept_v"] = intercept
            row["coupling_fit_r_squared"] = r_squared
            row["parameter_claim_status"] = "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
        metrics.extend(family_metrics)
    return metrics


def metric_for(
    metrics: list[dict[str, Any]], family_id: str, secondary_v: float
) -> dict[str, Any]:
    return next(
        row
        for row in metrics
        if row["family_id"] == family_id
        and same_value(float(row["fixed_secondary_gate_v"]), secondary_v)
    )


def build_reverse_comparisons(
    baseline: dict[str, Any],
    config: dict[str, Any],
    forward_rows: list[dict[str, Any]],
    reverse_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    comparisons: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for path in config["bias_protocol"]["reverse_paths"]:
        family_id = str(path["family_id"])
        secondary_v = float(path["fixed_secondary_v"])
        forward = rows_for_curve(forward_rows, family_id, secondary_v, "forward")
        reverse = rows_for_curve(reverse_rows, family_id, secondary_v, "reverse")
        reverse_by_voltage = {
            round(float(row["primary_gate_v"]), 12): row for row in reverse
        }
        family_rows: list[dict[str, Any]] = []
        for forward_row in forward:
            primary_v = float(forward_row["primary_gate_v"])
            reverse_row = reverse_by_voltage[round(primary_v, 12)]
            forward_current = abs(float(forward_row["drain_current_a_per_cm"]))
            reverse_current = abs(float(reverse_row["drain_current_a_per_cm"]))
            forward_density = float(forward_row["center_channel_electron_density_cm3"])
            reverse_density = float(reverse_row["center_channel_electron_density_cm3"])
            family_rows.append({
                "family_id": family_id,
                "primary_gate_v": primary_v,
                "fixed_secondary_gate_v": secondary_v,
                "forward_abs_drain_current_a_per_cm": forward_current,
                "reverse_abs_drain_current_a_per_cm": reverse_current,
                "relative_current_difference": abs(forward_current - reverse_current)
                / max(forward_current, reverse_current, 1.0e-300),
                "forward_center_channel_potential_v": float(
                    forward_row["center_channel_potential_v"]
                ),
                "reverse_center_channel_potential_v": float(
                    reverse_row["center_channel_potential_v"]
                ),
                "center_channel_potential_difference_v": abs(
                    float(forward_row["center_channel_potential_v"])
                    - float(reverse_row["center_channel_potential_v"])
                ),
                "forward_center_channel_electron_density_cm3": forward_density,
                "reverse_center_channel_electron_density_cm3": reverse_density,
                "center_density_relative_difference": abs(forward_density - reverse_density)
                / max(forward_density, reverse_density, 1.0e-300),
            })
        forward_metric = threshold_and_gm(baseline, config, forward)
        reverse_metric = threshold_and_gm(baseline, config, reverse)
        summaries.append({
            "family_id": family_id,
            "fixed_secondary_gate_v": secondary_v,
            "point_count": len(family_rows),
            "maximum_relative_current_difference": max(
                float(row["relative_current_difference"]) for row in family_rows
            ),
            "maximum_center_channel_potential_difference_v": max(
                float(row["center_channel_potential_difference_v"]) for row in family_rows
            ),
            "maximum_center_density_relative_difference": max(
                float(row["center_density_relative_difference"]) for row in family_rows
            ),
            "forward_vth_proxy_v": forward_metric["vth_proxy_v"],
            "reverse_vth_proxy_v": reverse_metric["vth_proxy_v"],
            "absolute_vth_difference_v": abs(
                float(forward_metric["vth_proxy_v"])
                - float(reverse_metric["vth_proxy_v"])
            ),
        })
        comparisons.extend(family_rows)
    return comparisons, summaries


def build_reciprocal_comparisons(
    config: dict[str, Any],
    forward_rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    comparisons: list[dict[str, Any]] = []
    metric_pairs: list[dict[str, Any]] = []
    for secondary_v in [
        float(value) for value in config["bias_protocol"]["fixed_secondary_gate_values_v"]
    ]:
        top_rows = rows_for_curve(forward_rows, "top_primary", secondary_v, "forward")
        bottom_rows = rows_for_curve(
            forward_rows, "bottom_primary", secondary_v, "forward"
        )
        bottom_by_voltage = {
            round(float(row["primary_gate_v"]), 12): row for row in bottom_rows
        }
        for top_row in top_rows:
            primary_v = float(top_row["primary_gate_v"])
            bottom_row = bottom_by_voltage[round(primary_v, 12)]
            top_current = abs(float(top_row["drain_current_a_per_cm"]))
            bottom_current = abs(float(bottom_row["drain_current_a_per_cm"]))
            top_density = float(top_row["center_channel_electron_density_cm3"])
            bottom_density = float(bottom_row["center_channel_electron_density_cm3"])
            comparisons.append({
                "fixed_secondary_gate_v": secondary_v,
                "primary_gate_v": primary_v,
                "top_primary_vbg_v": float(top_row["vbg_v"]),
                "top_primary_vtg_v": float(top_row["vtg_v"]),
                "bottom_primary_vbg_v": float(bottom_row["vbg_v"]),
                "bottom_primary_vtg_v": float(bottom_row["vtg_v"]),
                "top_primary_abs_drain_current_a_per_cm": top_current,
                "bottom_primary_abs_drain_current_a_per_cm": bottom_current,
                "relative_current_difference": abs(top_current - bottom_current)
                / max(top_current, bottom_current, 1.0e-300),
                "top_primary_center_channel_potential_v": float(
                    top_row["center_channel_potential_v"]
                ),
                "bottom_primary_center_channel_potential_v": float(
                    bottom_row["center_channel_potential_v"]
                ),
                "center_channel_potential_difference_v": abs(
                    float(top_row["center_channel_potential_v"])
                    - float(bottom_row["center_channel_potential_v"])
                ),
                "top_primary_center_channel_electron_density_cm3": top_density,
                "bottom_primary_center_channel_electron_density_cm3": bottom_density,
                "center_density_relative_difference": abs(top_density - bottom_density)
                / max(top_density, bottom_density, 1.0e-300),
            })
        top_metric = metric_for(metrics, "top_primary", secondary_v)
        bottom_metric = metric_for(metrics, "bottom_primary", secondary_v)
        top_gm = float(top_metric["gm_proxy_s_per_cm"])
        bottom_gm = float(bottom_metric["gm_proxy_s_per_cm"])
        metric_pairs.append({
            "fixed_secondary_gate_v": secondary_v,
            "top_primary_vth_proxy_v": float(top_metric["vth_proxy_v"]),
            "bottom_primary_vth_proxy_v": float(bottom_metric["vth_proxy_v"]),
            "absolute_vth_difference_v": abs(
                float(top_metric["vth_proxy_v"])
                - float(bottom_metric["vth_proxy_v"])
            ),
            "top_primary_gm_proxy_s_per_cm": top_gm,
            "bottom_primary_gm_proxy_s_per_cm": bottom_gm,
            "gm_relative_difference": abs(top_gm - bottom_gm)
            / max(abs(top_gm), abs(bottom_gm), 1.0e-300),
        })
    return comparisons, {
        "point_count": len(comparisons),
        "maximum_relative_current_difference": max(
            float(row["relative_current_difference"]) for row in comparisons
        ),
        "maximum_center_channel_potential_difference_v": max(
            float(row["center_channel_potential_difference_v"]) for row in comparisons
        ),
        "maximum_center_density_relative_difference": max(
            float(row["center_density_relative_difference"]) for row in comparisons
        ),
        "metric_pairs": metric_pairs,
        "maximum_absolute_vth_difference_v": max(
            float(row["absolute_vth_difference_v"]) for row in metric_pairs
        ),
        "maximum_gm_relative_difference": max(
            float(row["gm_relative_difference"]) for row in metric_pairs
        ),
    }


def build_t02_b_reproduction(
    config: dict[str, Any],
    forward_rows: list[dict[str, Any]],
    t02_b_report: dict[str, Any],
) -> list[dict[str, Any]]:
    central = rows_for_curve(forward_rows, "top_primary", 0.0, "forward")
    current_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in central
    }
    reference_by_voltage = {
        round(float(row["vtg_v"]), 12): row for row in t02_b_report["bias_points"]
    }
    rows: list[dict[str, Any]] = []
    for vtg_v in [
        float(value) for value in config["acceptance"]["required_t02_b_anchor_vtg_values_v"]
    ]:
        reproduced = current_by_voltage[round(vtg_v, 12)]
        reference = reference_by_voltage[round(vtg_v, 12)]
        reproduced_current = abs(float(reproduced["drain_current_a_per_cm"]))
        reference_current = abs(float(reference["drain_current_a_per_cm"]))
        rows.append({
            "vtg_v": vtg_v,
            "vbg_v": 0.0,
            "vds_v": float(reproduced["vds_v"]),
            "t02_b_abs_drain_current_a_per_cm": reference_current,
            "t02_c_abs_drain_current_a_per_cm": reproduced_current,
            "relative_current_difference": abs(reference_current - reproduced_current)
            / max(reference_current, reproduced_current, 1.0e-300),
            "t02_b_center_channel_potential_v": float(
                reference["center_channel_potential_v"]
            ),
            "t02_c_center_channel_potential_v": float(
                reproduced["center_channel_potential_v"]
            ),
            "center_channel_potential_difference_v": abs(
                float(reference["center_channel_potential_v"])
                - float(reproduced["center_channel_potential_v"])
            ),
        })
    return rows


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))


def render_family_figure(
    config: dict[str, Any],
    forward_rows: list[dict[str, Any]],
    reverse_rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    path: Path,
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.0), constrained_layout=True)
    colors = {-0.3: "#2563a6", 0.0: "#555b63", 0.3: "#c45d25"}
    labels = {-0.3: "secondary = -0.3 V", 0.0: "secondary = 0 V", 0.3: "secondary = +0.3 V"}
    for axis, family_id, title in (
        (axes[0][0], "top_primary", "Top-gate-primary transfer families"),
        (axes[0][1], "bottom_primary", "Bottom-gate-primary transfer families"),
    ):
        for secondary_v in (-0.3, 0.0, 0.3):
            rows = rows_for_curve(forward_rows, family_id, secondary_v, "forward")
            axis.semilogy(
                [float(row["primary_gate_v"]) for row in rows],
                [abs(float(row["drain_current_a_per_cm"])) for row in rows],
                color=colors[secondary_v],
                linewidth=1.8,
                label=labels[secondary_v],
            )
        reverse = rows_for_curve(reverse_rows, family_id, 0.0, "reverse")
        axis.semilogy(
            [float(row["primary_gate_v"]) for row in reverse],
            [abs(float(row["drain_current_a_per_cm"])) for row in reverse],
            "--",
            color="#111111",
            linewidth=1.0,
            label="secondary = 0 V reverse",
        )
        axis.axhline(
            float(
                config["extraction_methods"]["constant_current_vth_proxy"][
                    "expected_current_per_width_a_per_cm"
                ]
            ),
            color="#72777d",
            linestyle=":",
            linewidth=1.0,
        )
        axis.set_title(title)
        axis.set_xlabel("Primary gate voltage (V)")
        axis.set_ylabel("Absolute drain current per width (A/cm)")
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
        axis.legend(fontsize=7, loc="best")

    for family_id, color, marker, label in (
        ("top_primary", "#2563a6", "o", "top primary"),
        ("bottom_primary", "#c45d25", "s", "bottom primary"),
    ):
        rows = [row for row in metrics if row["family_id"] == family_id]
        secondary = [float(row["fixed_secondary_gate_v"]) for row in rows]
        delta_vth = [float(row["delta_vth_proxy_v"]) for row in rows]
        gm = [float(row["gm_proxy_s_per_cm"]) for row in rows]
        axes[1][0].plot(
            secondary, delta_vth, marker=marker, color=color, linewidth=1.8, label=label
        )
        axes[1][1].plot(
            secondary, gm, marker=marker, color=color, linewidth=1.8, label=label
        )
    axes[1][0].axhline(0.0, color="#72777d", linewidth=0.8)
    axes[1][0].set_title("Constant-current threshold shift proxy")
    axes[1][0].set_xlabel("Fixed secondary gate voltage (V)")
    axes[1][0].set_ylabel("Delta VTH proxy (V)")
    axes[1][1].set_title("gm proxy at VTH + 0.2 V")
    axes[1][1].set_xlabel("Fixed secondary gate voltage (V)")
    axes[1][1].set_ylabel("gm proxy (S/cm)")
    for axis in axes[1]:
        axis.grid(True, color="#d8dee3", linewidth=0.6)
        axis.legend(fontsize=8, loc="best")
    figure.suptitle("T02-C dual-gate IGZO numerical families and limited proxies", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def render_state_figure(
    state_entries: list[dict[str, Any]], path: Path
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.cm import ScalarMappable  # noqa: PLC0415
    from matplotlib.colors import Normalize  # noqa: PLC0415

    selected_ids = [
        "dual_negative_off_proxy",
        "top_threshold_region_proxy",
        "dual_positive_on_proxy",
    ]
    ordered = [
        next(entry for entry in state_entries if entry["state_id"] == state_id)
        for state_id in selected_ids
    ]
    potentials = [
        float(row["potential_v"]) for entry in ordered for row in entry["_node_rows"]
    ]
    log_density = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
        for entry in ordered
        for row in entry["_node_rows"]
        if row["region"] == "channel"
    ]
    log_current = [
        math.log10(
            max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1.0e-300)
        )
        for entry in ordered
        for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(log_density), max(log_density)),
        Normalize(min(log_current), max(log_current)),
    ]
    cmaps = ["viridis", "plasma", "magma"]
    figure, axes = plt.subplots(3, 3, figsize=(11.2, 8.2), constrained_layout=True)
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
                    max(
                        float(row["electron_current_density_magnitude_a_per_cm2"]),
                        1.0e-300,
                    )
                )
                for row in elements
            ],
            cmap=cmaps[2], norm=norms[2], s=6, linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            line_color = "white" if column != 1 else "#555555"
            axis.axhline(30.0, color=line_color, linewidth=0.6)
            axis.axhline(54.0, color=line_color, linewidth=0.6)
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
        "T02-C representative dual-gate states (vertical display scale expanded)",
        fontsize=12,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any],
    contract_report: dict[str, Any],
    t02_a_report: dict[str, Any],
    t02_b_report: dict[str, Any],
    forward_rows: list[dict[str, Any]],
    reverse_rows: list[dict[str, Any]],
    family_summaries: list[dict[str, Any]],
    solver_records: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    reverse_summaries: list[dict[str, Any]],
    reciprocal_summary: dict[str, Any],
    t02_b_reproduction: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    family_figure: Path,
    state_figure: Path,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    all_rows = forward_rows + reverse_rows
    grid = primary_grid(config)
    secondary_values = [
        float(value) for value in acceptance["required_fixed_secondary_gate_values_v"]
    ]

    add_check(
        checks,
        "prior_contract_and_t02_b_gate_passed",
        contract_report.get("contract_status") == "PASS"
        and contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and t02_b_report.get("status") == "PASS"
        and t02_b_report.get("t02_b_completion", {}).get(
            "t02_c_bidirectional_family_permitted_next"
        ) is True
        and t02_b_report.get("t02_b_completion", {}).get("t02_complete") is False,
        (
            f"contract={contract_report.get('contract_status')} "
            f"T02-B={t02_b_report.get('status')}"
        ),
    )

    add_check(
        checks,
        "all_configured_dc_solves_converged",
        len(solver_records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in solver_records),
        f"records={len(solver_records)} expected={acceptance['required_total_dc_solve_count']}",
    )

    t02_a_topology = next(
        item for item in t02_a_report["topology"] if item["top_coupling_enabled"]
    )
    topology_valid = all(
        summary["regions"] == sorted(acceptance["required_regions"])
        and summary["contacts"] == sorted(acceptance["required_contacts"])
        and summary["interfaces"] == sorted(acceptance["required_interfaces"])
        and summary["node_count_with_interface_duplicates"]
        == t02_a_topology["node_count_with_interface_duplicates"]
        and summary["element_count"] == t02_a_topology["element_count"]
        for summary in family_summaries
    )
    add_check(
        checks,
        "all_families_match_exact_t02_a_topology",
        len(family_summaries) == int(acceptance["required_forward_family_count"])
        and topology_valid,
        (
            f"families={len(family_summaries)} nodes="
            f"{[summary['node_count_with_interface_duplicates'] for summary in family_summaries]}"
        ),
    )

    forward_grid_valid = True
    for family_id in acceptance["required_family_ids"]:
        for secondary_v in secondary_values:
            curve = rows_for_curve(forward_rows, family_id, secondary_v, "forward")
            forward_grid_valid = forward_grid_valid and (
                [float(row["primary_gate_v"]) for row in curve] == grid
            )
    reverse_grid_valid = all(
        [float(row["primary_gate_v"]) for row in rows_for_curve(
            reverse_rows, str(path["family_id"]), float(path["fixed_secondary_v"]), "reverse"
        )] == grid
        for path in config["bias_protocol"]["reverse_paths"]
    )
    add_check(
        checks,
        "bidirectional_family_grids_completed",
        len(forward_rows) == int(acceptance["required_forward_reported_point_count"])
        and len(reverse_rows) == int(acceptance["required_reverse_reported_point_count"])
        and len(all_rows) == int(acceptance["required_total_reported_point_count"])
        and forward_grid_valid
        and reverse_grid_valid,
        f"forward={len(forward_rows)} reverse={len(reverse_rows)} total={len(all_rows)}",
    )

    max_imbalance = max(float(row["relative_current_imbalance"]) for row in all_rows)
    directional = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and math.isfinite(float(row["source_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        for row in all_rows
    )
    add_check(
        checks,
        "finite_directional_and_conserved_terminal_current",
        directional
        and max_imbalance
        <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"points={len(all_rows)} maximum_relative_imbalance={max_imbalance:.6e}",
    )

    maximum_drop = 0.0
    strictly_monotonic = True
    for family_id in acceptance["required_family_ids"]:
        for secondary_v in secondary_values:
            currents = [
                abs(float(row["drain_current_a_per_cm"]))
                for row in rows_for_curve(forward_rows, family_id, secondary_v, "forward")
            ]
            for lower, higher in zip(currents, currents[1:]):
                maximum_drop = max(
                    maximum_drop,
                    max(0.0, (lower - higher) / max(lower, higher, 1.0e-300)),
                )
                strictly_monotonic = strictly_monotonic and higher > lower
    add_check(
        checks,
        "primary_gate_current_strictly_increases",
        strictly_monotonic
        and maximum_drop <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"maximum_relative_drop={maximum_drop:.6e}",
    )

    secondary_ordering = True
    for family_id in acceptance["required_family_ids"]:
        curves = {
            secondary_v: {
                round(float(row["primary_gate_v"]), 12): abs(
                    float(row["drain_current_a_per_cm"])
                )
                for row in rows_for_curve(forward_rows, family_id, secondary_v, "forward")
            }
            for secondary_v in secondary_values
        }
        for primary_v in grid:
            values = [curves[value][round(primary_v, 12)] for value in secondary_values]
            secondary_ordering = secondary_ordering and all(
                higher > lower for lower, higher in zip(values, values[1:])
            )
    add_check(
        checks,
        "fixed_secondary_gate_current_ordering",
        secondary_ordering,
        f"secondary_values={secondary_values} primary_points={len(grid)}",
    )

    finite_metrics = len(metrics) == int(acceptance["required_forward_family_count"])
    finite_metrics = finite_metrics and all(
        math.isfinite(float(row[key]))
        for row in metrics
        for key in (
            "vth_proxy_v",
            "delta_vth_proxy_v",
            "gm_proxy_s_per_cm",
            "gm_proxy_terminal_s",
            "coupling_slope_v_per_v",
            "coupling_fit_r_squared",
        )
    )
    vth_and_coupling_valid = True
    for family_id in acceptance["required_family_ids"]:
        family_metrics = [row for row in metrics if row["family_id"] == family_id]
        vth_values = [float(row["vth_proxy_v"]) for row in family_metrics]
        deltas = [float(row["delta_vth_proxy_v"]) for row in family_metrics]
        slope = float(family_metrics[0]["coupling_slope_v_per_v"])
        r_squared = float(family_metrics[0]["coupling_fit_r_squared"])
        vth_and_coupling_valid = vth_and_coupling_valid and (
            all(higher < lower for lower, higher in zip(vth_values, vth_values[1:]))
            and deltas[0] > 0.0
            and same_value(deltas[1], 0.0)
            and deltas[2] < 0.0
            and slope < 0.0
            and float(acceptance["minimum_absolute_coupling_slope_v_per_v"])
            <= abs(slope)
            <= float(acceptance["maximum_absolute_coupling_slope_v_per_v"])
            and r_squared >= float(acceptance["minimum_coupling_fit_r_squared"])
        )
    add_check(
        checks,
        "vth_delta_vth_and_coupling_proxies_valid",
        finite_metrics and vth_and_coupling_valid,
        "; ".join(
            f"{row['family_id']} sec={float(row['fixed_secondary_gate_v']):+.1f} "
            f"VTH={float(row['vth_proxy_v']):.6g} dVTH={float(row['delta_vth_proxy_v']):+.6g}"
            for row in metrics
        ),
    )

    gm_valid = all(
        float(row["gm_proxy_s_per_cm"]) > 0.0
        and float(row["gm_proxy_terminal_s"]) > 0.0
        and row["parameter_claim_status"] == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
        for row in metrics
    )
    add_check(
        checks,
        "positive_finite_gm_proxies",
        gm_valid,
        "; ".join(
            f"{row['family_id']} sec={float(row['fixed_secondary_gate_v']):+.1f} "
            f"gm={float(row['gm_proxy_s_per_cm']):.6e} S/cm"
            for row in metrics
        ),
    )

    max_reverse_current = max(
        float(row["maximum_relative_current_difference"]) for row in reverse_summaries
    )
    max_reverse_vth = max(
        float(row["absolute_vth_difference_v"]) for row in reverse_summaries
    )
    add_check(
        checks,
        "central_forward_reverse_paths_agree",
        len(reverse_summaries) == int(acceptance["required_reverse_family_count"])
        and max_reverse_current
        <= float(acceptance["maximum_forward_reverse_relative_current_difference"])
        and max_reverse_vth
        <= float(acceptance["maximum_forward_reverse_vth_difference_v"]),
        f"max_current_relative={max_reverse_current:.6e} max_dVTH={max_reverse_vth:.6e} V",
    )

    add_check(
        checks,
        "reciprocal_top_bottom_symmetry_agrees",
        reciprocal_summary["point_count"]
        == len(grid) * len(secondary_values)
        and reciprocal_summary["maximum_relative_current_difference"]
        <= float(acceptance["maximum_reciprocal_top_bottom_relative_current_difference"])
        and reciprocal_summary["maximum_center_channel_potential_difference_v"]
        <= float(
            acceptance["maximum_reciprocal_top_bottom_center_potential_difference_v"]
        )
        and reciprocal_summary["maximum_center_density_relative_difference"]
        <= float(
            acceptance["maximum_reciprocal_top_bottom_center_density_relative_difference"]
        )
        and reciprocal_summary["maximum_absolute_vth_difference_v"]
        <= float(acceptance["maximum_reciprocal_top_bottom_vth_difference_v"])
        and reciprocal_summary["maximum_gm_relative_difference"]
        <= float(acceptance["maximum_reciprocal_top_bottom_gm_relative_difference"]),
        json.dumps(reciprocal_summary, sort_keys=True),
    )

    max_anchor_current = max(
        float(row["relative_current_difference"]) for row in t02_b_reproduction
    )
    max_anchor_potential = max(
        float(row["center_channel_potential_difference_v"])
        for row in t02_b_reproduction
    )
    add_check(
        checks,
        "t02_b_minimal_family_anchors_reproduced",
        len(t02_b_reproduction)
        == len(acceptance["required_t02_b_anchor_vtg_values_v"])
        and max_anchor_current
        <= float(acceptance["maximum_t02_b_anchor_relative_current_difference"])
        and max_anchor_potential
        <= float(acceptance["maximum_t02_b_anchor_potential_difference_v"]),
        f"max_current_relative={max_anchor_current:.6e} max_potential={max_anchor_potential:.6e} V",
    )

    max_zero_current = max(
        float(summary["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"])
        for summary in family_summaries
    )
    max_zero_potential = max(
        float(summary["zero_equilibrium"]["maximum_absolute_potential_v"])
        for summary in family_summaries
    )
    add_check(
        checks,
        "fresh_family_zero_equilibria_are_current_free",
        max_zero_current
        <= float(acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"])
        and max_zero_potential
        <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"max_current={max_zero_current:.6e} A/cm max_potential={max_zero_potential:.6e} V",
    )

    state_files_valid = True
    for entry in state_entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        state_files_valid = state_files_valid and node_path.is_file() and element_path.is_file()
        state_files_valid = state_files_valid and entry["node_csv_sha256"] == core.sha256(node_path)
        state_files_valid = state_files_valid and entry["element_csv_sha256"] == core.sha256(element_path)
        state_files_valid = state_files_valid and int(entry["channel_element_count"]) > 0
        state_files_valid = state_files_valid and int(entry["vtk_file_count"]) == int(
            acceptance["required_vtk_file_count_per_state"]
        )
        state_files_valid = state_files_valid and all(
            (ROOT / item["path"]).is_file()
            and item["sha256"] == core.sha256(ROOT / item["path"])
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
    ] if len(state_by_id) == len(acceptance["required_state_ids"]) else []
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
    ] if len(state_by_id) == len(acceptance["required_state_ids"]) else []
    state_ordering = bool(current_groups) and all(
        higher > lower for lower, higher in zip(current_groups, current_groups[1:])
    ) and all(
        higher > lower for lower, higher in zip(density_groups, density_groups[1:])
    )
    add_check(
        checks,
        "six_representative_state_fields_and_ordering",
        [entry["state_id"] for entry in state_entries] == acceptance["required_state_ids"]
        and state_files_valid
        and state_ordering,
        f"states={[entry['state_id'] for entry in state_entries]} currents={current_groups} densities={density_groups}",
    )

    figure_bytes = [
        path.stat().st_size if path.is_file() else 0
        for path in (family_figure, state_figure)
    ]
    add_check(
        checks,
        "two_report_figures_written",
        all(value > 0 for value in figure_bytes),
        f"bytes={figure_bytes}",
    )

    failures = [name for name, result in checks.items() if result["status"] == "FAIL"]
    coupling = {
        family_id: {
            "slope_v_per_v": float(metric_for(metrics, family_id, 0.0)["coupling_slope_v_per_v"]),
            "r_squared": float(metric_for(metrics, family_id, 0.0)["coupling_fit_r_squared"]),
        }
        for family_id in acceptance["required_family_ids"]
    }
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "maximum_monotonic_relative_current_drop": maximum_drop,
        "maximum_forward_reverse_relative_current_difference": max_reverse_current,
        "maximum_forward_reverse_vth_difference_v": max_reverse_vth,
        "maximum_reciprocal_top_bottom_relative_current_difference": reciprocal_summary[
            "maximum_relative_current_difference"
        ],
        "maximum_reciprocal_top_bottom_vth_difference_v": reciprocal_summary[
            "maximum_absolute_vth_difference_v"
        ],
        "maximum_reciprocal_top_bottom_gm_relative_difference": reciprocal_summary[
            "maximum_gm_relative_difference"
        ],
        "maximum_t02_b_anchor_relative_current_difference": max_anchor_current,
        "maximum_t02_b_anchor_potential_difference_v": max_anchor_potential,
        "maximum_zero_equilibrium_absolute_terminal_current_a_per_cm": max_zero_current,
        "maximum_zero_equilibrium_absolute_potential_v": max_zero_potential,
        "coupling_proxies": coupling,
    }


def public_state_entry(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_t02_c_bidirectional.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = core.load_json(config_path)
    dependency = config["dependencies"]
    baseline_path = ROOT / dependency["t01_baseline_config"]
    mesh_config_path = ROOT / dependency["t01_mesh_config"]
    t02_a_config_path = ROOT / dependency["t02_a_config"]
    t02_a_report_path = ROOT / dependency["t02_a_report"]
    t02_b_config_path = ROOT / dependency["t02_b_config"]
    t02_b_report_path = ROOT / dependency["t02_b_report"]
    t02_b_check_path = ROOT / dependency["t02_b_check_report"]
    contract_report_path = ROOT / config["outputs"]["contract_report"]
    baseline = core.load_json(baseline_path)
    mesh_config = core.load_json(mesh_config_path)
    t02_a_config = core.load_json(t02_a_config_path)
    t02_a_report = core.load_json(t02_a_report_path)
    t02_b_report = core.load_json(t02_b_report_path)
    t02_b_check = core.load_json(t02_b_check_path)
    contract_report = core.load_json(contract_report_path)

    if contract_report.get("contract_status") != "PASS":
        raise RuntimeError("T02-C input contract is not PASS")
    if contract_report.get("config", {}).get("sha256") != core.sha256(config_path):
        raise RuntimeError("T02-C contract report does not match the current config")
    if (
        t02_b_report.get("status") != dependency["required_t02_b_status"]
        or t02_b_check.get("status") != dependency["required_t02_b_check_status"]
        or t02_b_report.get("t02_b_completion", {}).get(
            "t02_c_bidirectional_family_permitted_next"
        )
        is not dependency["require_t02_c_permitted_by_t02_b"]
    ):
        raise RuntimeError("T02-B gate is not open")

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    family_path = ROOT / outputs["family_csv"]
    metric_path = ROOT / outputs["metric_csv"]
    reverse_path = ROOT / outputs["reverse_comparison_csv"]
    reciprocal_path = ROOT / outputs["reciprocal_comparison_csv"]
    state_summary_path = ROOT / outputs["state_summary_csv"]
    family_figure_path = ROOT / outputs["family_figure_png"]
    state_figure_path = ROOT / outputs["state_figure_png"]
    report_path = ROOT / outputs["report"]

    input_paths = {
        "t02_c_config": config_path,
        "t02_c_contract_report": contract_report_path,
        "t01_baseline_config": baseline_path,
        "t01_mesh_config": mesh_config_path,
        "t02_a_config": t02_a_config_path,
        "t02_a_report": t02_a_report_path,
        "t02_b_config": t02_b_config_path,
        "t02_b_report": t02_b_report_path,
        "t02_b_check_report": t02_b_check_path,
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in input_paths.items()
        },
        "t02_c_contract": config,
        "t01_baseline": baseline,
        "t01_mesh_source": mesh_config,
        "t02_a_config": t02_a_config,
    }
    core.write_json(snapshot_path, snapshot)

    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t02-c-bidirectional",
        "validation_command": "make t02-c-bidirectional-check",
        "runs": [],
        "errors": [],
    }
    forward_rows: list[dict[str, Any]] = []
    reverse_rows: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    family_summaries: list[dict[str, Any]] = []
    solver_records: list[dict[str, Any]] = []
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    try:
        for family in config["bias_protocol"]["families"]:
            for fixed_secondary_v in [
                float(value) for value in family["fixed_secondary_values_v"]
            ]:
                family_forward, family_reverse, family_states, summary, records = run_family(
                    baseline,
                    mesh_config,
                    t02_a_config,
                    config,
                    family,
                    fixed_secondary_v,
                    run_dir,
                )
                forward_rows.extend(family_forward)
                reverse_rows.extend(family_reverse)
                state_entries.extend(family_states)
                family_summaries.append(summary)
                solver_records.extend(records)
                solver_log["runs"].append({
                    "family_id": family["family_id"],
                    "fixed_secondary_gate_v": fixed_secondary_v,
                    "status": "PASS",
                    "summary": summary,
                    "solver_records": records,
                })
                core.write_json(solver_log_path, solver_log)
                print(
                    f"T02_C_FAMILY_PASS family={family['family_id']} "
                    f"secondary={fixed_secondary_v:+.1f} V solves={len(records)}"
                )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})

    state_order = {
        state_id: index
        for index, state_id in enumerate(config["acceptance"]["required_state_ids"])
    }
    state_entries.sort(key=lambda entry: state_order.get(str(entry["state_id"]), 999))
    all_family_rows = forward_rows + reverse_rows
    metrics: list[dict[str, Any]] = []
    reverse_comparisons: list[dict[str, Any]] = []
    reverse_summaries: list[dict[str, Any]] = []
    reciprocal_comparisons: list[dict[str, Any]] = []
    reciprocal_summary: dict[str, Any] = {}
    t02_b_reproduction: list[dict[str, Any]] = []
    family_figure_sha256: str | None = None
    state_figure_sha256: str | None = None
    if caught_error is None:
        try:
            metrics = build_metrics(baseline, config, forward_rows)
            reverse_comparisons, reverse_summaries = build_reverse_comparisons(
                baseline, config, forward_rows, reverse_rows
            )
            reciprocal_comparisons, reciprocal_summary = build_reciprocal_comparisons(
                config, forward_rows, metrics
            )
            t02_b_reproduction = build_t02_b_reproduction(
                config, forward_rows, t02_b_report
            )
            family_figure_sha256 = render_family_figure(
                config, forward_rows, reverse_rows, metrics, family_figure_path
            )
            state_figure_sha256 = render_state_figure(state_entries, state_figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(family_path, all_family_rows, FAMILY_FIELDNAMES)
    core.write_csv(metric_path, metrics, METRIC_FIELDNAMES)
    core.write_csv(reverse_path, reverse_comparisons, REVERSE_FIELDNAMES)
    core.write_csv(reciprocal_path, reciprocal_comparisons, RECIPROCAL_FIELDNAMES)
    core.write_csv(
        state_summary_path,
        [
            {field: entry[field] for field in STATE_SUMMARY_FIELDNAMES}
            for entry in state_entries
        ],
        STATE_SUMMARY_FIELDNAMES,
    )
    public_states = [public_state_entry(entry) for entry in state_entries]
    core.write_json(
        state_manifest_path,
        {"case_id": config["case_id"], "stage": config["stage"], "entries": public_states},
    )
    solver_log["wall_seconds"] = time.perf_counter() - wall_start
    core.write_json(solver_log_path, solver_log)

    if caught_error is None:
        assessment = assess(
            config,
            contract_report,
            t02_a_report,
            t02_b_report,
            forward_rows,
            reverse_rows,
            family_summaries,
            solver_records,
            metrics,
            reverse_summaries,
            reciprocal_summary,
            t02_b_reproduction,
            state_entries,
            family_figure_path,
            state_figure_path,
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {
                "stage_exception": {"status": "FAIL", "detail": repr(caught_error)}
            },
            "failures": ["stage_exception"],
        }
    passed = assessment["status"] == "PASS"
    artifact_paths = {
        "family_csv": family_path,
        "metric_csv": metric_path,
        "reverse_comparison_csv": reverse_path,
        "reciprocal_comparison_csv": reciprocal_path,
        "state_summary_csv": state_summary_path,
        "state_manifest": state_manifest_path,
        "solver_log": solver_log_path,
    }
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": (
            "2D n-IGZO electron-only drift-diffusion teaching model with the frozen "
            "T02-A enabled symmetric top stack"
        ),
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "contract_command": "make t02-c-contract-check",
            "command": "make t02-c-bidirectional",
            "validation_command": "make t02-c-bidirectional-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "family_summaries": family_summaries,
        "family_points": all_family_rows,
        "coupling_metrics": metrics,
        "reverse_path_summaries": reverse_summaries,
        "reciprocal_symmetry_summary": reciprocal_summary,
        "t02_b_reproduction": t02_b_reproduction,
        "state_outputs": public_states,
        "figures": [
            {
                "path": str(family_figure_path.relative_to(ROOT)),
                "sha256": family_figure_sha256,
            },
            {
                "path": str(state_figure_path.relative_to(ROOT)),
                "sha256": state_figure_sha256,
            },
        ],
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {
            key: value
            for key, value in assessment.items()
            if key not in {"status", "checks", "failures"}
        },
        "t02_c_completion": {
            "status": "PASS" if passed else "FAIL",
            "bidirectional_gate_families_completed": passed,
            "negative_primary_gate_paths_verified": passed,
            "reverse_path_numerical_independence_verified": passed,
            "delta_vth_numerical_proxy_verified": passed,
            "gm_numerical_proxy_verified": passed,
            "representative_internal_states_verified": passed,
            "complete_t02_numerical_stage_gate": "PASS" if passed else "FAIL",
            "t02_complete": passed,
            "t03_controlled_sensitivity_permitted_next": passed,
            "experimental_calibration_permitted": False,
            "physical_parameter_validation_permitted": False,
            "compact_model_calibrated": False,
        },
        "limitations": [
            "All VTH, Delta VTH, gm, and coupling values are numerical proxies from the frozen E2 teaching model, not experimental fits.",
            "The central forward/reverse agreement is a numerical path-independence check with no hysteresis or ferroelectric model active.",
            "The symmetric top/bottom agreement follows the deliberately symmetric 30 nm Al2O3 teaching stack and is not a fabricated-device validation.",
            "Traps, non-ideal contacts, recombination, ferroelectric polarization, temperature dependence, and uncertainty remain absent.",
            "No compact-model or circuit-ready parameter set is established by T02-C.",
        ],
        "artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in artifact_paths.items()
        },
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T02_C_BIDIRECTIONAL_{report['status']} points={len(all_family_rows)} "
        f"dc_solves={len(solver_records)} states={len(state_entries)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T02_C_BIDIRECTIONAL_ERROR {caught_error}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
