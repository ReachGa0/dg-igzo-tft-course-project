#!/usr/bin/env python3
"""Run the frozen T03-P4-L channel-length sensitivity."""

from __future__ import annotations

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
import run_t02_dual_gate_bidirectional as t02_c  # noqa: E402
import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402
import run_t02_dual_gate_minimal_bias as t02_b  # noqa: E402


core = t02_a.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p4_channel_length.json"
STAGE_ID = "T03_P4_L_CHANNEL_LENGTH"

CURVE_FIELDNAMES = [
    "parameter_group_id", "changed_parameter", "channel_length_um",
    "channel_length_cm", "sweep_index", "mesh_level", "stage_id", "mode_id",
    "vbg_v", "vtg_v", "vds_v", "source_current_a_per_cm",
    "drain_current_a_per_cm", "source_current_terminal_a",
    "drain_current_terminal_a", "current_imbalance_a_per_cm",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "solve_seconds", "converged",
]
METRIC_FIELDNAMES = [
    "parameter_group_id", "changed_parameter", "channel_length_um",
    "channel_length_cm", "constant_current_criterion_terminal_a",
    "constant_current_criterion_a_per_cm", "vth_proxy_v",
    "vth_bracket_lower_primary_gate_v", "vth_bracket_upper_primary_gate_v",
    "vth_bracket_lower_current_a_per_cm", "vth_bracket_upper_current_a_per_cm",
    "gm_evaluation_primary_gate_v", "gm_proxy_s_per_cm", "gm_proxy_terminal_s",
    "maximum_sampled_gm_s_per_cm", "maximum_sampled_gm_primary_gate_v",
    "on_state_primary_gate_v", "on_state_current_proxy_a_per_cm",
    "on_state_current_proxy_terminal_a", "current_length_product_a",
    "gm_length_product_s", "vth_range_v",
    "current_length_product_relative_spread",
    "gm_length_product_relative_spread", "log_current_vs_length_slope",
    "log_current_vs_length_intercept", "log_current_vs_length_r_squared",
    "parameter_claim_status",
]
REFERENCE_FIELDNAMES = [
    "primary_gate_v", "t03_abs_drain_current_a_per_cm",
    "t02_c_abs_drain_current_a_per_cm", "current_relative_difference",
    "t03_center_channel_potential_v", "t02_c_center_channel_potential_v",
    "center_channel_potential_difference_v",
    "t03_center_channel_electron_density_cm3",
    "t02_c_center_channel_electron_density_cm3",
    "center_density_relative_difference",
]
STATE_NODE_FIELDNAMES = [
    "state_id", "state_label", "parameter_group_id", "channel_length_um",
    "channel_length_cm", "mesh_level", "stage_id", "mode_id", "source_v",
    "drain_v", "vbg_v", "vtg_v", "region", "x_cm", "y_cm", "x_um",
    "y_nm", "potential_v", "electron_density_cm3",
]
STATE_ELEMENT_FIELDNAMES = [
    "state_id", "state_label", "parameter_group_id", "channel_length_um",
    "channel_length_cm", "mesh_level", "stage_id", "mode_id", "vbg_v",
    "vtg_v", "vds_v", "region", "element_index", "node0_index",
    "node1_index", "node2_index", "x0_cm", "y0_cm", "x1_cm", "y1_cm",
    "x2_cm", "y2_cm", "centroid_x_cm", "centroid_y_cm", "centroid_x_um",
    "centroid_y_nm", "electron_current_density_x_en0_a_per_cm2",
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
    "state_id", "state_label", "parameter_group_id", "channel_length_um",
    "channel_length_cm", "mesh_level", "stage_id", "vbg_v", "vtg_v",
    "vds_v", "absolute_drain_current_a_per_cm", "drain_current_terminal_a",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "node_row_count",
    "channel_node_count", "channel_element_count", "minimum_potential_v",
    "maximum_potential_v", "minimum_electron_density_cm3",
    "maximum_electron_density_cm3",
    "minimum_cell_current_density_magnitude_a_per_cm2",
    "median_cell_current_density_magnitude_a_per_cm2",
    "maximum_cell_current_density_magnitude_a_per_cm2", "node_csv",
    "element_csv", "vtk_file_count",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def length_token(length_um: float) -> str:
    return f"{length_um:.1f}".replace(".", "p")


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T03-P4-L primary grid is not integral")
    values = [round(start + index * step, 12) for index in range(intervals + 1)]
    if len(values) != int(spec["point_count"]):
        raise ValueError("T03-P4-L primary grid point count differs from contract")
    return values


def runtime_baseline(
    baseline: dict[str, Any], length_um: float
) -> dict[str, Any]:
    variant = copy.deepcopy(baseline)
    length_cm = length_um * 1.0e-4
    variant["device"]["channel_length_um"] = length_um
    variant["device"]["channel_length_cm"] = length_cm
    variant["geometry"]["channel_length_cm"] = length_cm
    return variant


def set_biases(
    device: str, *, source_v: float, drain_v: float, vbg_v: float, vtg_v: float
) -> None:
    t02_a.set_enabled_biases(
        device,
        source_v=source_v,
        drain_v=drain_v,
        bottom_gate_v=vbg_v,
        top_gate_v=vtg_v,
    )


def collect_curve_row(
    device: str,
    runtime: dict[str, Any],
    length_um: float,
    mesh_level: str,
    mode_id: str,
    sweep_index: int,
    vbg_v: float,
    vtg_v: float,
    vds_v: float,
    solve_record: dict[str, Any],
) -> dict[str, Any]:
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
        "parameter_group_id": "P4",
        "changed_parameter": "channel_length_um",
        "channel_length_um": length_um,
        "channel_length_cm": length_um * 1.0e-4,
        "sweep_index": sweep_index,
        "mesh_level": mesh_level,
        "stage_id": STAGE_ID,
        "mode_id": mode_id,
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


def write_state(
    device: str,
    runtime: dict[str, Any],
    length_um: float,
    mesh_level: str,
    mode_id: str,
    bias_row: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    length_cm = length_um * 1.0e-4
    token = length_token(length_um)
    state = {
        "state_id": f"length_{token}um_on_proxy",
        "label": f"L={length_um:g} um on proxy",
        "source_family": "top_primary",
        "vbg_v": float(bias_row["vbg_v"]),
        "vtg_v": float(bias_row["vtg_v"]),
        "vds_v": float(bias_row["vds_v"]),
    }
    bias = {
        "source_v": 0.0,
        "drain_v": state["vds_v"],
        "bottom_gate_v": state["vbg_v"],
        "top_gate_v": state["vtg_v"],
    }
    node_rows = [
        {
            "state_id": state["state_id"],
            "state_label": state["label"],
            "parameter_group_id": "P4",
            "channel_length_um": length_um,
            "channel_length_cm": length_cm,
            "mesh_level": mesh_level,
            "stage_id": STAGE_ID,
            **row,
        }
        for row in t02_a.collect_enabled_state(device, mode_id, bias)
    ]
    element_rows: list[dict[str, Any]] = []
    for source in t02_c.collect_current_elements(device, mesh_level, state):
        row = dict(source)
        row.pop("source_family", None)
        row.update({
            "parameter_group_id": "P4",
            "channel_length_um": length_um,
            "channel_length_cm": length_cm,
            "stage_id": STAGE_ID,
            "mode_id": mode_id,
        })
        element_rows.append(row)

    base = f"t03_p4_l_{token}um_on_proxy"
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
        "parameter_group_id": "P4",
        "channel_length_um": length_um,
        "channel_length_cm": length_cm,
        "mesh_level": mesh_level,
        "stage_id": STAGE_ID,
        "vbg_v": state["vbg_v"],
        "vtg_v": state["vtg_v"],
        "vds_v": state["vds_v"],
        "absolute_drain_current_a_per_cm": abs(
            float(bias_row["drain_current_a_per_cm"])
        ),
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
            "cell_center_reduction": "arithmetic mean of three element-node vectors",
            "local_unit": "A/cm^2",
        },
        "_node_rows": node_rows,
        "_element_rows": element_rows,
    }


def run_length(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_a_config: dict[str, Any],
    config: dict[str, Any],
    length_um: float,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    protocol = config["bias_protocol"]
    mesh_level = config["inheritance"]["required_mesh_level"]
    variant = runtime_baseline(baseline, length_um)
    runtime, mesh_spec = t02_a.mesh_stage.build_runtime_baseline(
        variant, mesh_config, mesh_level
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = float(
        t02_a_config["top_stack_contract"]["enabled_mode"][
            "top_oxide_thickness_cm"
        ]
    )
    mode_id = t02_a_config["top_stack_contract"]["enabled_mode"]["mode_id"]
    device = f"t03_p4_l_{length_token(length_um)}um"
    records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    state_entry: dict[str, Any] = {}
    wall_start = time.perf_counter()
    try:
        t02_a.initialize_enabled_device(
            device, runtime, t02_a_config, mesh_level, mesh_spec
        )
        regions, contacts, interfaces = t02_a.active_topology(
            device, t02_a.ENABLED_REGIONS
        )
        node_count, element_count = t02_a.active_counts(
            device, t02_a.ENABLED_REGIONS
        )
        set_biases(device, source_v=0.0, drain_v=0.0, vbg_v=0.0, vtg_v=0.0)
        records.append(
            core.solve_dc(
                device,
                runtime,
                f"T03_P4_L_{length_um:g}UM_POISSON_ZERO",
                coupled=False,
            )
        )
        core.create_transport(device, runtime)
        records.append(
            core.solve_dc(
                device,
                runtime,
                f"T03_P4_L_{length_um:g}UM_COUPLED_ZERO",
                coupled=True,
            )
        )
        core.devsim.element_from_edge_model(
            device=device, region="channel", edge_model="ElectronCurrent"
        )
        zero_source, zero_drain = t02_b.contact_currents(device)
        zero_rows = t02_a.collect_enabled_state(
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
            "maximum_absolute_terminal_current_a_per_cm": max(
                abs(zero_source), abs(zero_drain)
            ),
            "maximum_absolute_potential_v": t02_b.maximum_state_potential(zero_rows),
        }

        for vds_v in [float(value) for value in protocol["low_vds_values_v"]]:
            set_biases(
                device,
                source_v=float(protocol["source_v"]),
                drain_v=vds_v,
                vbg_v=0.0,
                vtg_v=0.0,
            )
            records.append(
                core.solve_dc(
                    device,
                    runtime,
                    f"T03_P4_L_{length_um:g}UM_LOW_VDS_{vds_v:.6g}",
                    coupled=True,
                )
            )

        precondition: dict[float, dict[str, Any]] = {}
        for vtg_v in [
            float(value) for value in protocol["primary_negative_preconditioning_v"]
        ]:
            set_biases(
                device,
                source_v=float(protocol["source_v"]),
                drain_v=float(protocol["drain_v"]),
                vbg_v=float(protocol["fixed_secondary_gate_v"]),
                vtg_v=vtg_v,
            )
            record = core.solve_dc(
                device,
                runtime,
                f"T03_P4_L_{length_um:g}UM_PRE_{vtg_v:.6g}",
                coupled=True,
            )
            records.append(record)
            precondition[round(vtg_v, 12)] = record

        for index, vtg_v in enumerate(primary_grid(config)):
            key = round(vtg_v, 12)
            if index == 0 and key in precondition:
                record = precondition[key]
            else:
                set_biases(
                    device,
                    source_v=float(protocol["source_v"]),
                    drain_v=float(protocol["drain_v"]),
                    vbg_v=float(protocol["fixed_secondary_gate_v"]),
                    vtg_v=vtg_v,
                )
                record = core.solve_dc(
                    device,
                    runtime,
                    f"T03_P4_L_{length_um:g}UM_FWD_{vtg_v:.6g}",
                    coupled=True,
                )
                records.append(record)
            row = collect_curve_row(
                device,
                runtime,
                length_um,
                mesh_level,
                mode_id,
                index,
                float(protocol["fixed_secondary_gate_v"]),
                vtg_v,
                float(protocol["drain_v"]),
                record,
            )
            rows.append(row)
            if same_value(vtg_v, float(protocol["state_primary_gate_v"])):
                state_entry = write_state(
                    device,
                    runtime,
                    length_um,
                    mesh_level,
                    mode_id,
                    row,
                    run_dir,
                )

        summary = {
            "parameter_group_id": "P4",
            "changed_parameter": "channel_length_um",
            "channel_length_um": length_um,
            "channel_length_cm": length_um * 1.0e-4,
            "mesh_level": mesh_level,
            "mode_id": mode_id,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(records),
            "reported_point_count": len(rows),
            "state_count": 1 if state_entry else 0,
            "zero_equilibrium": zero_equilibrium,
            "total_solve_seconds": sum(
                float(record["elapsed_seconds"]) for record in records
            ),
            "wall_seconds": time.perf_counter() - wall_start,
        }
        return rows, state_entry, summary, records
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def curve_for_length(
    rows: list[dict[str, Any]], length_um: float
) -> list[dict[str, Any]]:
    return sorted(
        [row for row in rows if same_value(float(row["channel_length_um"]), length_um)],
        key=lambda row: float(row["vtg_v"]),
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


def extract_metric(
    baseline: dict[str, Any], config: dict[str, Any], length_um: float,
    curve: list[dict[str, Any]],
) -> dict[str, Any]:
    length_cm = length_um * 1.0e-4
    width_cm = float(baseline["device"]["width_cm"])
    prefactor = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "criterion_prefactor_a"
        ]
    )
    terminal_criterion = prefactor * width_cm / length_cm
    criterion = terminal_criterion / width_cm
    voltages = [float(row["vtg_v"]) for row in curve]
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
        for index in range(1, len(curve) - 1)
    ]
    gm_voltage = vth + float(
        config["extraction_methods"]["gm_proxy"]["evaluation_overdrive_v"]
    )
    if not gm_voltages[0] <= gm_voltage <= gm_voltages[-1]:
        raise RuntimeError("T03-P4-L gm evaluation voltage is outside the grid")
    gm = interpolate(gm_voltages, gm_values, gm_voltage)
    peak = max(range(len(gm_values)), key=lambda index: gm_values[index])
    on_voltage = float(
        config["extraction_methods"]["on_state_current_proxy"]["primary_gate_v"]
    )
    on_row = next(row for row in curve if same_value(float(row["vtg_v"]), on_voltage))
    on_current = abs(float(on_row["drain_current_a_per_cm"]))
    return {
        "parameter_group_id": "P4",
        "changed_parameter": "channel_length_um",
        "channel_length_um": length_um,
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
        "maximum_sampled_gm_s_per_cm": gm_values[peak],
        "maximum_sampled_gm_primary_gate_v": gm_voltages[peak],
        "on_state_primary_gate_v": on_voltage,
        "on_state_current_proxy_a_per_cm": on_current,
        "on_state_current_proxy_terminal_a": on_current * width_cm,
        "current_length_product_a": on_current * length_cm,
        "gm_length_product_s": gm * length_cm,
        "parameter_claim_status": "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
    }


def relative_spread(values: list[float]) -> float:
    return (max(values) - min(values)) / max(
        max(abs(value) for value in values), 1.0e-300
    )


def build_metrics(
    baseline: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    metrics = [
        extract_metric(baseline, config, length, curve_for_length(rows, length))
        for length in [float(value) for value in config["sensitivity"]["values_um"]]
    ]
    lengths_cm = [float(row["channel_length_cm"]) for row in metrics]
    currents = [float(row["on_state_current_proxy_a_per_cm"]) for row in metrics]
    slope, intercept, r_squared = t01_extract.linear_regression(
        [math.log(value) for value in lengths_cm],
        [math.log(value) for value in currents],
    )
    vth_range = max(float(row["vth_proxy_v"]) for row in metrics) - min(
        float(row["vth_proxy_v"]) for row in metrics
    )
    current_spread = relative_spread(
        [float(row["current_length_product_a"]) for row in metrics]
    )
    gm_spread = relative_spread(
        [float(row["gm_length_product_s"]) for row in metrics]
    )
    for row in metrics:
        row.update({
            "vth_range_v": vth_range,
            "current_length_product_relative_spread": current_spread,
            "gm_length_product_relative_spread": gm_spread,
            "log_current_vs_length_slope": slope,
            "log_current_vs_length_intercept": intercept,
            "log_current_vs_length_r_squared": r_squared,
        })
    return metrics


def build_reference_comparison(
    config: dict[str, Any], rows: list[dict[str, Any]],
    t02_c_report: dict[str, Any], metrics: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reference_length = float(config["sensitivity"]["reference_value_um"])
    t03_curve = curve_for_length(rows, reference_length)
    t02_curve = sorted(
        [
            row
            for row in t02_c_report["family_points"]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )
    t02_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in t02_curve
    }
    comparisons: list[dict[str, Any]] = []
    for t03_row in t03_curve:
        voltage = float(t03_row["vtg_v"])
        t02_row = t02_by_voltage[round(voltage, 12)]
        t03_current = abs(float(t03_row["drain_current_a_per_cm"]))
        t02_current = abs(float(t02_row["drain_current_a_per_cm"]))
        t03_density = float(t03_row["center_channel_electron_density_cm3"])
        t02_density = float(t02_row["center_channel_electron_density_cm3"])
        comparisons.append({
            "primary_gate_v": voltage,
            "t03_abs_drain_current_a_per_cm": t03_current,
            "t02_c_abs_drain_current_a_per_cm": t02_current,
            "current_relative_difference": abs(t03_current - t02_current)
            / max(t03_current, t02_current, 1.0e-300),
            "t03_center_channel_potential_v": float(
                t03_row["center_channel_potential_v"]
            ),
            "t02_c_center_channel_potential_v": float(
                t02_row["center_channel_potential_v"]
            ),
            "center_channel_potential_difference_v": abs(
                float(t03_row["center_channel_potential_v"])
                - float(t02_row["center_channel_potential_v"])
            ),
            "t03_center_channel_electron_density_cm3": t03_density,
            "t02_c_center_channel_electron_density_cm3": t02_density,
            "center_density_relative_difference": abs(t03_density - t02_density)
            / max(t03_density, t02_density, 1.0e-300),
        })
    t03_metric = next(
        row for row in metrics if same_value(float(row["channel_length_um"]), reference_length)
    )
    t02_metric = next(
        row
        for row in t02_c_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    summary = {
        "point_count": len(comparisons),
        "maximum_current_relative_difference": max(
            float(row["current_relative_difference"]) for row in comparisons
        ),
        "maximum_center_potential_difference_v": max(
            float(row["center_channel_potential_difference_v"])
            for row in comparisons
        ),
        "maximum_center_density_relative_difference": max(
            float(row["center_density_relative_difference"]) for row in comparisons
        ),
        "vth_difference_v": abs(
            float(t03_metric["vth_proxy_v"]) - float(t02_metric["vth_proxy_v"])
        ),
        "gm_relative_difference": abs(
            float(t03_metric["gm_proxy_s_per_cm"])
            - float(t02_metric["gm_proxy_s_per_cm"])
        )
        / max(
            abs(float(t03_metric["gm_proxy_s_per_cm"])),
            abs(float(t02_metric["gm_proxy_s_per_cm"])),
            1.0e-300,
        ),
    }
    return comparisons, summary


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))


def render_sensitivity_figure(
    config: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], path: Path,
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    colors = {8.0: "#2563a6", 10.0: "#555b63", 12.0: "#c45d25"}
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.0), constrained_layout=True)
    for length in [float(value) for value in config["sensitivity"]["values_um"]]:
        curve = curve_for_length(rows, length)
        axes[0][0].semilogy(
            [float(row["vtg_v"]) for row in curve],
            [abs(float(row["drain_current_a_per_cm"])) for row in curve],
            color=colors[length], linewidth=1.8, label=f"L={length:g} um",
        )
    axes[0][0].set_title("Top-gate transfer curves")
    axes[0][0].set_xlabel("Top-gate voltage (V)")
    axes[0][0].set_ylabel("Absolute drain current per width (A/cm)")
    axes[0][0].legend(fontsize=8)

    lengths = [float(row["channel_length_um"]) for row in metrics]
    vth = [float(row["vth_proxy_v"]) for row in metrics]
    axes[0][1].plot(lengths, vth, "o-", color="#287d59", linewidth=1.8)
    axes[0][1].set_title(f"VTH proxy range = {metrics[0]['vth_range_v'] * 1e3:.3f} mV")
    axes[0][1].set_xlabel("Channel length (um)")
    axes[0][1].set_ylabel("Constant-current VTH proxy (V)")

    currents = [float(row["on_state_current_proxy_a_per_cm"]) for row in metrics]
    current_reference = currents[1] * lengths[1]
    axes[1][0].plot(lengths, currents, "o-", color="#2563a6", linewidth=1.8, label="sampled proxy")
    axes[1][0].plot(
        lengths, [current_reference / value for value in lengths], "--",
        color="#555b63", linewidth=1.2, label="1/L guide",
    )
    axes[1][0].set_title(
        f"Current log-slope = {metrics[0]['log_current_vs_length_slope']:.4f}"
    )
    axes[1][0].set_xlabel("Channel length (um)")
    axes[1][0].set_ylabel("|ID| at VTG=1 V (A/cm)")
    axes[1][0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axes[1][0].legend(fontsize=8)

    gm = [float(row["gm_proxy_s_per_cm"]) for row in metrics]
    gm_reference = gm[1] * lengths[1]
    axes[1][1].plot(lengths, gm, "o-", color="#c45d25", linewidth=1.8, label="gm proxy")
    axes[1][1].plot(
        lengths, [gm_reference / value for value in lengths], "--",
        color="#555b63", linewidth=1.2, label="1/L guide",
    )
    axes[1][1].set_title(
        f"gm*L spread = {metrics[0]['gm_length_product_relative_spread'] * 100:.3f}%"
    )
    axes[1][1].set_xlabel("Channel length (um)")
    axes[1][1].set_ylabel("gm proxy (S/cm)")
    axes[1][1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axes[1][1].legend(fontsize=8)
    for axis in axes.flat:
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle("T03-P4-L IGZO channel-length numerical sensitivity", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def render_state_figure(state_entries: list[dict[str, Any]], path: Path) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.cm import ScalarMappable  # noqa: PLC0415
    from matplotlib.colors import Normalize  # noqa: PLC0415

    ordered = sorted(state_entries, key=lambda row: float(row["channel_length_um"]))
    potentials = [
        float(row["potential_v"]) for entry in ordered for row in entry["_node_rows"]
    ]
    log_density = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
        for entry in ordered for row in entry["_node_rows"] if row["region"] == "channel"
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
            c=[math.log10(max(float(row["electron_density_cm3"]), 1.0e-300)) for row in channel_nodes],
            cmap=cmaps[1], norm=norms[1], s=6, linewidths=0,
        )
        axes[row_index][2].scatter(
            [float(row["centroid_x_um"]) for row in elements],
            [float(row["centroid_y_nm"]) for row in elements],
            c=[math.log10(max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1.0e-300)) for row in elements],
            cmap=cmaps[2], norm=norms[2], s=6, linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, float(entry["channel_length_um"]))
            axis.set_ylim(-2.0, 86.0)
            line_color = "white" if column != 1 else "#555555"
            axis.axhline(30.0, color=line_color, linewidth=0.6)
            axis.axhline(54.0, color=line_color, linewidth=0.6)
            axis.set_ylabel(f"L={entry['channel_length_um']:g} um\ny (nm)")
            if row_index == 2:
                axis.set_xlabel("x (um)")
    axes[0][0].set_title("Potential (V)")
    axes[0][1].set_title("log10 electron density (cm^-3)")
    axes[0][2].set_title("log10 |J| (A/cm^2)")
    for column, (norm, cmap) in enumerate(zip(norms, cmaps)):
        figure.colorbar(
            ScalarMappable(norm=norm, cmap=cmap), ax=axes[:, column],
            shrink=0.82, pad=0.02,
        )
    figure.suptitle(
        "T03-P4-L on-state proxies (vertical display scale expanded)", fontsize=12
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def public_state(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def assess(
    config: dict[str, Any], contract: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], summaries: list[dict[str, Any]],
    states: list[dict[str, Any]], solver_records: list[dict[str, Any]],
    reference: dict[str, Any], wall_seconds: float,
    sensitivity_figure: Path, state_figure: Path,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    lengths = [float(value) for value in acceptance["required_channel_lengths_um"]]
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in rows)
    max_drop = 0.0
    for length in lengths:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in curve_for_length(rows, length)
        ]
        max_drop = max(
            max_drop,
            max(
                (lower - upper) / max(lower, upper, 1.0e-300)
                for lower, upper in zip(currents, currents[1:])
            ),
        )
    node_counts = [int(row["node_count_with_interface_duplicates"]) for row in summaries]
    element_counts = [int(row["element_count"]) for row in summaries]
    metric0 = metrics[0]
    vtk_count = sum(len(entry["vtk_files"]) for entry in states)
    on_currents = [float(row["on_state_current_proxy_a_per_cm"]) for row in metrics]
    gm_values = [float(row["gm_proxy_s_per_cm"]) for row in metrics]
    diagnostic_gate = config["diagnostic_hypotheses"]["ideal_inverse_length"]
    diagnostic_checks = {
        "vth_range_within_2mv": (
            float(metric0["vth_range_v"])
            <= float(diagnostic_gate["maximum_vth_range_v"])
        ),
        "current_length_product_spread_within_2percent": (
            float(metric0["current_length_product_relative_spread"])
            <= float(diagnostic_gate["maximum_current_length_product_relative_spread"])
        ),
        "gm_length_product_spread_within_2percent": (
            float(metric0["gm_length_product_relative_spread"])
            <= float(diagnostic_gate["maximum_gm_length_product_relative_spread"])
        ),
        "log_current_length_slope_near_minus_one": (
            float(diagnostic_gate["minimum_log_current_vs_length_slope"])
            <= float(metric0["log_current_vs_length_slope"])
            <= float(diagnostic_gate["maximum_log_current_vs_length_slope"])
            and float(metric0["log_current_vs_length_r_squared"])
            >= float(diagnostic_gate["minimum_log_current_vs_length_r_squared"])
        ),
    }
    diagnostic_passed = all(diagnostic_checks.values())
    ideal_diagnostic = {
        "status": "PASS" if diagnostic_passed else "FAIL",
        "completion_gate": False,
        "checks": diagnostic_checks,
        "observed": {
            "vth_range_v": float(metric0["vth_range_v"]),
            "current_length_product_relative_spread": float(
                metric0["current_length_product_relative_spread"]
            ),
            "gm_length_product_relative_spread": float(
                metric0["gm_length_product_relative_spread"]
            ),
            "log_current_vs_length_slope": float(
                metric0["log_current_vs_length_slope"]
            ),
            "log_current_vs_length_r_squared": float(
                metric0["log_current_vs_length_r_squared"]
            ),
        },
        "interpretation": diagnostic_gate["interpretation"],
    }

    add_check(
        checks, "contract_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"contract={contract.get('contract_status')} simulation={contract.get('simulation_status')}",
    )
    add_check(
        checks, "all_configured_dc_solves_converged",
        len(solver_records) == acceptance["required_total_dc_solve_count"]
        and all(record.get("converged") is True for record in solver_records),
        f"records={len(solver_records)} expected={acceptance['required_total_dc_solve_count']}",
    )
    add_check(
        checks, "three_length_topologies_are_ordered_and_valid",
        [float(row["channel_length_um"]) for row in summaries] == lengths
        and all(row["regions"] == sorted(acceptance["required_regions"]) for row in summaries)
        and all(row["contacts"] == sorted(acceptance["required_contacts"]) for row in summaries)
        and all(row["interfaces"] == sorted(acceptance["required_interfaces"]) for row in summaries)
        and all(higher > lower for lower, higher in zip(node_counts, node_counts[1:]))
        and all(higher > lower for lower, higher in zip(element_counts, element_counts[1:])),
        f"nodes={node_counts} elements={element_counts}",
    )
    add_check(
        checks, "exact_curve_grid_completed",
        len(rows) == acceptance["required_reported_point_count"]
        and all(len(curve_for_length(rows, length)) == acceptance["required_primary_gate_point_count"] for length in lengths),
        f"points={len(rows)} curves={[len(curve_for_length(rows, value)) for value in lengths]}",
    )
    add_check(
        checks, "finite_directional_and_conserved_terminal_current",
        max_imbalance <= acceptance["maximum_relative_terminal_current_imbalance"]
        and all(float(row["drain_current_a_per_cm"]) > 0.0 for row in rows)
        and all(float(row["source_current_a_per_cm"]) < 0.0 for row in rows)
        and all(math.isfinite(float(row["drain_current_a_per_cm"])) for row in rows),
        f"maximum_relative_imbalance={max_imbalance:.6e}",
    )
    add_check(
        checks, "primary_gate_current_strictly_increases",
        max_drop <= acceptance["maximum_monotonic_relative_current_drop"]
        and all(
            all(higher > lower for lower, higher in zip(
                [abs(float(row["drain_current_a_per_cm"])) for row in curve_for_length(rows, length)],
                [abs(float(row["drain_current_a_per_cm"])) for row in curve_for_length(rows, length)][1:],
            ))
            for length in lengths
        ),
        f"maximum_relative_drop={max_drop:.6e}",
    )
    add_check(
        checks, "fresh_zero_equilibria_are_current_free",
        max(float(row["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"]) for row in summaries)
        <= acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"]
        and max(float(row["zero_equilibrium"]["maximum_absolute_potential_v"]) for row in summaries)
        <= acceptance["maximum_zero_equilibrium_absolute_potential_v"],
        f"equilibria={[row['zero_equilibrium'] for row in summaries]}",
    )
    add_check(
        checks, "vth_and_gm_numerical_proxies_are_valid",
        len(metrics) == 3
        and all(math.isfinite(float(row["vth_proxy_v"])) for row in metrics)
        and all(float(row["gm_proxy_s_per_cm"]) > 0.0 for row in metrics)
        and all(
            float(row["vth_bracket_lower_current_a_per_cm"])
            <= float(row["constant_current_criterion_a_per_cm"])
            <= float(row["vth_bracket_upper_current_a_per_cm"])
            and float(row["vth_bracket_lower_primary_gate_v"])
            <= float(row["vth_proxy_v"])
            <= float(row["vth_bracket_upper_primary_gate_v"])
            for row in metrics
        ),
        f"VTH={[row['vth_proxy_v'] for row in metrics]} gm={[row['gm_proxy_s_per_cm'] for row in metrics]}",
    )
    add_check(
        checks, "length_response_is_strict_and_directional",
        all(higher < lower for lower, higher in zip(on_currents, on_currents[1:]))
        and all(higher < lower for lower, higher in zip(gm_values, gm_values[1:])),
        f"on_currents={on_currents} gm={gm_values}",
    )
    add_check(
        checks, "ideal_inverse_length_diagnostic_is_reported_not_reclassified",
        diagnostic_gate["completion_gate"] is False
        and diagnostic_gate["required_reporting"] is True
        and ideal_diagnostic["status"] in {"PASS", "FAIL"}
        and config["remediation"]["prior_status"] == "FAIL",
        f"diagnostic={ideal_diagnostic['status']} completion_gate={ideal_diagnostic['completion_gate']}",
    )
    add_check(
        checks, "t02_c_reference_curve_reproduced",
        reference["point_count"] == 31
        and reference["maximum_current_relative_difference"]
        <= acceptance["maximum_t02_c_reference_current_relative_difference"]
        and reference["maximum_center_potential_difference_v"]
        <= acceptance["maximum_t02_c_reference_center_potential_difference_v"]
        and reference["maximum_center_density_relative_difference"]
        <= acceptance["maximum_t02_c_reference_center_density_relative_difference"],
        json.dumps(reference, sort_keys=True),
    )
    add_check(
        checks, "t02_c_reference_extraction_reproduced",
        reference["vth_difference_v"]
        <= acceptance["maximum_t02_c_reference_vth_difference_v"]
        and reference["gm_relative_difference"]
        <= acceptance["maximum_t02_c_reference_gm_relative_difference"],
        f"dVTH={reference['vth_difference_v']:.6e} gm_rel={reference['gm_relative_difference']:.6e}",
    )
    add_check(
        checks, "three_complete_state_fields_written",
        len(states) == acceptance["required_state_count"]
        and vtk_count == acceptance["required_vtk_file_count"]
        and all(entry["node_row_count"] > 0 and entry["channel_element_count"] > 0 for entry in states)
        and all(Path(ROOT / entry["node_csv"]).is_file() and Path(ROOT / entry["element_csv"]).is_file() for entry in states),
        f"states={len(states)} vtk={vtk_count} nodes={[entry['node_row_count'] for entry in states]}",
    )
    add_check(
        checks, "two_report_figures_written",
        sensitivity_figure.is_file() and sensitivity_figure.stat().st_size > 0
        and state_figure.is_file() and state_figure.stat().st_size > 0,
        f"bytes={[sensitivity_figure.stat().st_size, state_figure.stat().st_size]}",
    )
    add_check(
        checks, "laptop_wall_time_budget_met",
        wall_seconds <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"wall_seconds={wall_seconds:.6f}",
    )
    add_check(
        checks, "evidence_boundary_remains_one_local_p4_l_group",
        all(row["parameter_claim_status"] == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED" for row in metrics)
        and "complete T03 five-group sensitivity" in config["evidence_boundary"]["prohibited_claims"],
        config["evidence_boundary"]["allowed_claim"],
    )

    failures = [name for name, item in checks.items() if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "maximum_monotonic_relative_current_drop": max_drop,
        "vth_range_v": float(metric0["vth_range_v"]),
        "current_length_product_relative_spread": float(metric0["current_length_product_relative_spread"]),
        "gm_length_product_relative_spread": float(metric0["gm_length_product_relative_spread"]),
        "log_current_vs_length_slope": float(metric0["log_current_vs_length_slope"]),
        "log_current_vs_length_r_squared": float(metric0["log_current_vs_length_r_squared"]),
        "reference_reproduction": reference,
        "diagnostic_hypotheses": {"ideal_inverse_length": ideal_diagnostic},
        "wall_seconds": wall_seconds,
    }


def main() -> int:
    config = load_json(CONFIG_PATH)
    dependencies = config["dependencies"]
    contract_path = ROOT / config["outputs"]["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P4-L contract must pass before simulation")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("T03-P4-L config changed after contract check")

    baseline_path = ROOT / dependencies["t01_baseline_config"]
    mesh_path = ROOT / dependencies["t01_mesh_config"]
    t02_a_config_path = ROOT / dependencies["t02_a_config"]
    t02_a_report_path = ROOT / dependencies["t02_a_report"]
    t02_c_config_path = ROOT / dependencies["t02_c_config"]
    t02_c_report_path = ROOT / dependencies["t02_c_report"]
    t02_c_check_path = ROOT / dependencies["t02_c_check_report"]
    baseline = load_json(baseline_path)
    mesh_config = load_json(mesh_path)
    t02_a_config = load_json(t02_a_config_path)
    t02_c_report = load_json(t02_c_report_path)

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    curve_path = ROOT / outputs["curve_csv"]
    metric_path = ROOT / outputs["metric_csv"]
    reference_path = ROOT / outputs["reference_comparison_csv"]
    state_summary_path = ROOT / outputs["state_summary_csv"]
    sensitivity_figure_path = ROOT / outputs["sensitivity_figure_png"]
    state_figure_path = ROOT / outputs["state_figure_png"]
    report_path = ROOT / outputs["report"]

    input_paths = {
        "t03_config": CONFIG_PATH,
        "t03_contract_report": contract_path,
        "t01_baseline_config": baseline_path,
        "t01_mesh_config": mesh_path,
        "t02_a_config": t02_a_config_path,
        "t02_a_report": t02_a_report_path,
        "t02_c_config": t02_c_config_path,
        "t02_c_report": t02_c_report_path,
        "t02_c_check_report": t02_c_check_path,
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in input_paths.items()
        },
    }
    core.write_json(snapshot_path, snapshot)
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "python_executable": sys.executable,
        "reproduction_command": "make t03-p4-l-sensitivity",
        "validation_command": "make t03-p4-l-sensitivity-check",
        "runs": [],
        "errors": [],
    }
    all_rows: list[dict[str, Any]] = []
    all_states: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    solver_records: list[dict[str, Any]] = []
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    try:
        for length_um in [float(value) for value in config["sensitivity"]["values_um"]]:
            rows, state, summary, records = run_length(
                baseline, mesh_config, t02_a_config, config, length_um, run_dir
            )
            all_rows.extend(rows)
            all_states.append(state)
            summaries.append(summary)
            solver_records.extend(records)
            solver_log["runs"].append({
                "channel_length_um": length_um,
                "status": "PASS",
                "summary": summary,
                "solver_records": records,
            })
            core.write_json(solver_log_path, solver_log)
            print(
                f"T03_P4_L_DEVICE_PASS length={length_um:g} um "
                f"points={len(rows)} solves={len(records)}"
            )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})

    metrics: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    reference_summary: dict[str, Any] = {}
    sensitivity_figure_sha256: str | None = None
    state_figure_sha256: str | None = None
    if caught_error is None:
        try:
            metrics = build_metrics(baseline, config, all_rows)
            reference_rows, reference_summary = build_reference_comparison(
                config, all_rows, t02_c_report, metrics
            )
            sensitivity_figure_sha256 = render_sensitivity_figure(
                config, all_rows, metrics, sensitivity_figure_path
            )
            state_figure_sha256 = render_state_figure(all_states, state_figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(curve_path, all_rows, CURVE_FIELDNAMES)
    core.write_csv(metric_path, metrics, METRIC_FIELDNAMES)
    core.write_csv(reference_path, reference_rows, REFERENCE_FIELDNAMES)
    core.write_csv(
        state_summary_path,
        [
            {field: entry[field] for field in STATE_SUMMARY_FIELDNAMES}
            for entry in all_states if entry
        ],
        STATE_SUMMARY_FIELDNAMES,
    )
    public_states = [public_state(entry) for entry in all_states if entry]
    core.write_json(
        state_manifest_path,
        {"case_id": config["case_id"], "stage": config["stage"], "entries": public_states},
    )
    wall_seconds = time.perf_counter() - wall_start
    solver_log["wall_seconds"] = wall_seconds
    core.write_json(solver_log_path, solver_log)

    if caught_error is None:
        assessment = assess(
            config, contract, all_rows, metrics, summaries, all_states,
            solver_records, reference_summary, wall_seconds,
            sensitivity_figure_path, state_figure_path,
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {"stage_exception": {"status": "FAIL", "detail": repr(caught_error)}},
            "failures": ["stage_exception"],
        }
    passed = assessment["status"] == "PASS"
    artifact_paths = {
        "curve_csv": curve_path,
        "metric_csv": metric_path,
        "reference_comparison_csv": reference_path,
        "state_summary_csv": state_summary_path,
        "state_manifest": state_manifest_path,
        "solver_log": solver_log_path,
    }
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": "2D n-IGZO frozen teaching model; channel length is the only changed variable",
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "contract_command": "make t03-p4-l-contract-check",
            "command": "make t03-p4-l-sensitivity",
            "validation_command": "make t03-p4-l-sensitivity-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "topology_summaries": summaries,
        "curve_points": all_rows,
        "sensitivity_metrics": metrics,
        "t02_c_reference_reproduction": reference_summary,
        "diagnostic_hypotheses": assessment.get("diagnostic_hypotheses", {}),
        "remediation": config["remediation"],
        "state_outputs": public_states,
        "figures": [
            {"path": str(sensitivity_figure_path.relative_to(ROOT)), "sha256": sensitivity_figure_sha256},
            {"path": str(state_figure_path.relative_to(ROOT)), "sha256": state_figure_sha256},
        ],
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {
            key: value
            for key, value in assessment.items()
            if key not in {"status", "checks", "failures"}
        },
        "t03_p4_l_completion": {
            "status": "PASS" if passed else "FAIL",
            "p4_channel_length_three_point_group_complete": passed,
            "complete_t03_five_group_sensitivity": False,
            "another_t03_group_permitted_next": passed,
            "experimental_calibration_permitted": False,
            "physical_short_channel_claim_permitted": False,
            "compact_model_calibrated": False,
        },
        "limitations": [
            "All currents, VTH, gm, and scaling quantities are numerical proxies from the frozen E2 teaching model.",
            "Only L=8/10/12 um at VDS=0.01 V and one top-primary zero-secondary transfer family are covered.",
            "The V1 ideal inverse-length hypothesis is reported separately and remains FAIL when its frozen diagnostic thresholds are not met; it is not proof of a physical scaling law or short-channel behavior.",
            "No experimental distribution, traps, non-ideal contacts, temperature dependence, dielectric variation, uncertainty, compact model, or circuit is validated.",
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
        f"T03_P4_L_SENSITIVITY_{report['status']} points={len(all_rows)} "
        f"dc_solves={len(solver_records)} states={len(public_states)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T03_P4_L_SENSITIVITY_ERROR {caught_error}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
