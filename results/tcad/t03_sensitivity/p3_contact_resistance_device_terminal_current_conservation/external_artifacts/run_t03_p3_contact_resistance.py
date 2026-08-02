#!/usr/bin/env python3
"""Run the formal isolated T03-P3 symmetric contact-resistance sensitivity."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t02_dual_gate_bidirectional as t02_c  # noqa: E402


core = t02_c.core
t02_a = t02_c.t02_a
CONFIG_PATH = ROOT / "config" / "tcad_t03_p3_contact_resistance.json"
STAGE_ID = "T03_P3_CONTACT_RESISTANCE"

SOURCE_EXTERNAL_NODE = "p3_source_external"
SOURCE_INTERNAL_NODE = "p3_source_internal"
DRAIN_EXTERNAL_NODE = "p3_drain_external"
DRAIN_INTERNAL_NODE = "p3_drain_internal"
SOURCE_VOLTAGE_ELEMENT = "VP3SourceExternal"
DRAIN_VOLTAGE_ELEMENT = "VP3DrainExternal"
SOURCE_RESISTOR_ELEMENT = "RP3Source"
DRAIN_RESISTOR_ELEMENT = "RP3Drain"
TERMINAL_CHARGE_MODEL = "P3TerminalPotentialEdgeFlux"
TERMINAL_CURRENT_MODEL = "P3TerminalElectronCurrent"
CIRCUIT_ACTIVE = False

POINT_FIELDNAMES = [
    "point_uid",
    "parameter_group_id",
    "changed_parameter",
    "case_id",
    "r_pair_w_kohm_um",
    "r_pair_ohm",
    "r_source_ohm",
    "r_drain_ohm",
    "execution_mode",
    "circuit_coupled",
    "device_id",
    "curve_kind",
    "curve_id",
    "point_index",
    "mesh_level",
    "stage_id",
    "mode_id",
    "vbg_v",
    "vtg_v",
    "requested_external_source_v",
    "requested_external_vds_v",
    "external_source_v",
    "external_drain_v",
    "external_vds_v",
    "internal_source_v",
    "internal_drain_v",
    "internal_device_vds_v",
    "source_current_a_per_cm",
    "drain_current_a_per_cm",
    "source_current_terminal_a",
    "drain_current_terminal_a",
    "external_source_current_terminal_a",
    "external_drain_current_terminal_a",
    "external_source_current_a_per_cm",
    "external_drain_current_a_per_cm",
    "current_imbalance_a_per_cm",
    "relative_current_imbalance",
    "source_resistor_current_external_to_internal_a",
    "drain_resistor_current_external_to_internal_a",
    "source_voltage_source_current_a",
    "drain_voltage_source_current_a",
    "source_kcl_residual_a",
    "drain_kcl_residual_a",
    "source_kcl_relative_residual",
    "drain_kcl_relative_residual",
    "source_drop_v",
    "drain_drop_v",
    "total_resistor_drop_v",
    "circuit_ohms_law_residual_v",
    "circuit_ohms_law_relative_residual",
    "voltage_partition_residual_v",
    "total_resistor_power_w",
    "circuit_closure_applicable",
    "circuit_solution_list_json",
    "center_channel_potential_v",
    "center_channel_electron_density_cm3",
    "solve_seconds",
    "converged",
]

CIRCUIT_BALANCE_FIELDNAMES = [
    "point_uid",
    "case_id",
    "curve_kind",
    "curve_id",
    "vtg_v",
    "vbg_v",
    "external_vds_v",
    "r_pair_w_kohm_um",
    "r_pair_ohm",
    "circuit_coupled",
    "circuit_closure_applicable",
    "external_source_v",
    "internal_source_v",
    "internal_drain_v",
    "external_drain_v",
    "internal_device_vds_v",
    "source_current_terminal_a",
    "drain_current_terminal_a",
    "external_source_current_terminal_a",
    "external_drain_current_terminal_a",
    "source_resistor_current_external_to_internal_a",
    "drain_resistor_current_external_to_internal_a",
    "source_kcl_residual_a",
    "drain_kcl_residual_a",
    "source_kcl_relative_residual",
    "drain_kcl_relative_residual",
    "source_drop_v",
    "drain_drop_v",
    "total_resistor_drop_v",
    "circuit_ohms_law_residual_v",
    "circuit_ohms_law_relative_residual",
    "voltage_partition_residual_v",
    "total_resistor_power_w",
]

METRIC_FIELDNAMES = [
    "parameter_group_id",
    "case_id",
    "r_pair_w_kohm_um",
    "r_pair_ohm",
    "transfer_high_gate_current_proxy_a_per_cm",
    "transfer_high_gate_current_proxy_terminal_a",
    "transfer_high_gate_current_relative_reduction",
    "output_vtg_0p3_vds_0p2_current_a_per_cm",
    "output_vtg_0p5_vds_0p2_current_a_per_cm",
    "output_vtg_1p0_vds_0p2_current_a_per_cm",
    "output_vtg_0p3_vds_0p2_current_terminal_a",
    "output_vtg_0p5_vds_0p2_current_terminal_a",
    "output_vtg_1p0_vds_0p2_current_terminal_a",
    "linear_fit_point_count",
    "linear_fit_conductance_s",
    "linear_region_total_resistance_ohm",
    "linear_region_total_resistance_width_kohm_um",
    "added_total_resistance_width_kohm_um",
    "declared_pair_resistance_width_kohm_um",
    "added_resistance_relative_difference",
    "added_resistance_diagnostic_within_15_percent",
    "parameter_claim_status",
]

REFERENCE_FIELDNAMES = [
    "primary_gate_v",
    "p3_abs_external_drain_current_a_per_cm",
    "t02_c_abs_drain_current_a_per_cm",
    "current_relative_difference",
    "p3_center_channel_potential_v",
    "t02_c_center_channel_potential_v",
    "center_channel_potential_difference_v",
    "p3_center_channel_electron_density_cm3",
    "t02_c_center_channel_electron_density_cm3",
    "center_density_relative_difference",
]

STATE_NODE_FIELDNAMES = [
    "state_id",
    "state_label",
    "parameter_group_id",
    "case_id",
    "r_pair_w_kohm_um",
    "r_pair_ohm",
    "mesh_level",
    "stage_id",
    "mode_id",
    "external_source_v",
    "external_drain_v",
    "internal_source_v",
    "internal_drain_v",
    "vbg_v",
    "vtg_v",
    "region",
    "x_cm",
    "y_cm",
    "x_um",
    "y_nm",
    "potential_v",
    "electron_density_cm3",
]

STATE_ELEMENT_FIELDNAMES = [
    "state_id",
    "state_label",
    "parameter_group_id",
    "case_id",
    "r_pair_w_kohm_um",
    "r_pair_ohm",
    "mesh_level",
    "stage_id",
    "vbg_v",
    "vtg_v",
    "external_vds_v",
    "region",
    "element_index",
    "node0_index",
    "node1_index",
    "node2_index",
    "x0_cm",
    "y0_cm",
    "x1_cm",
    "y1_cm",
    "x2_cm",
    "y2_cm",
    "centroid_x_cm",
    "centroid_y_cm",
    "centroid_x_um",
    "centroid_y_nm",
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
    "state_id",
    "state_label",
    "parameter_group_id",
    "case_id",
    "r_pair_w_kohm_um",
    "r_pair_ohm",
    "mesh_level",
    "stage_id",
    "vbg_v",
    "vtg_v",
    "external_vds_v",
    "internal_source_v",
    "internal_drain_v",
    "internal_device_vds_v",
    "absolute_external_drain_current_a_per_cm",
    "absolute_external_drain_current_terminal_a",
    "relative_current_imbalance",
    "source_kcl_relative_residual",
    "drain_kcl_relative_residual",
    "circuit_ohms_law_relative_residual",
    "voltage_partition_residual_v",
    "center_channel_potential_v",
    "center_channel_electron_density_cm3",
    "node_row_count",
    "channel_node_count",
    "channel_element_count",
    "minimum_potential_v",
    "maximum_potential_v",
    "minimum_electron_density_cm3",
    "maximum_electron_density_cm3",
    "minimum_cell_current_density_magnitude_a_per_cm2",
    "median_cell_current_density_magnitude_a_per_cm2",
    "maximum_cell_current_density_magnitude_a_per_cm2",
    "node_csv",
    "element_csv",
    "vtk_file_count",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def relative_difference(left: float, right: float, *, floor: float = 1.0e-300) -> float:
    return abs(float(left) - float(right)) / max(
        abs(float(left)), abs(float(right)), floor
    )


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def value_token(value: float) -> str:
    return f"{float(value):.4g}".replace("-", "m").replace(".", "p")


def transfer_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["transfer"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T03-P3 transfer grid is not integral")
    values = [round(start + index * step, 12) for index in range(intervals + 1)]
    if len(values) != int(spec["point_count"]):
        raise ValueError("T03-P3 transfer point count differs from the contract")
    return values


def case_by_id(config: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(
        case for case in config["sensitivity"]["cases"] if case["case_id"] == case_id
    )


def runtime_for_device(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_a_config: dict[str, Any],
    mesh_level: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime, mesh_spec = t02_a.mesh_stage.build_runtime_baseline(
        baseline, mesh_config, mesh_level
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = float(
        t02_a_config["top_stack_contract"]["enabled_mode"][
            "top_oxide_thickness_cm"
        ]
    )
    return runtime, mesh_spec


def clear_circuit() -> None:
    global CIRCUIT_ACTIVE
    if CIRCUIT_ACTIVE:
        try:
            core.devsim.delete_circuit()
        except Exception as error:  # noqa: BLE001
            # DEVSIM 2.10.0 deletes both keepers but omits the Python empty
            # result. Accept only that known return-path defect after proving
            # that no circuit nodes survived the command.
            remaining = tuple(core.devsim.get_circuit_node_list())
            if remaining:
                raise RuntimeError(
                    f"DEVSIM circuit deletion failed; nodes remain: {remaining}"
                ) from error
        CIRCUIT_ACTIVE = False


def install_series_circuit(case: dict[str, Any]) -> None:
    global CIRCUIT_ACTIVE
    clear_circuit()
    core.devsim.circuit_element(
        name=SOURCE_VOLTAGE_ELEMENT,
        n1=SOURCE_EXTERNAL_NODE,
        n2=0,
        value=0.0,
        acreal=0.0,
        acimag=0.0,
    )
    core.devsim.circuit_element(
        name=DRAIN_VOLTAGE_ELEMENT,
        n1=DRAIN_EXTERNAL_NODE,
        n2=0,
        value=0.0,
        acreal=0.0,
        acimag=0.0,
    )
    core.devsim.circuit_element(
        name=SOURCE_RESISTOR_ELEMENT,
        n1=SOURCE_EXTERNAL_NODE,
        n2=SOURCE_INTERNAL_NODE,
        value=float(case["r_source_ohm"]),
    )
    core.devsim.circuit_element(
        name=DRAIN_RESISTOR_ELEMENT,
        n1=DRAIN_EXTERNAL_NODE,
        n2=DRAIN_INTERNAL_NODE,
        value=float(case["r_drain_ohm"]),
    )
    CIRCUIT_ACTIVE = True


def bind_potential_contacts_to_circuit(
    device: str, width_cm: float
) -> None:
    expression = f"{width_cm:.15e}*PotentialEdgeFlux"
    core.CreateEdgeModel(device, "channel", TERMINAL_CHARGE_MODEL, expression)
    core.CreateEdgeModelDerivatives(
        device, "channel", TERMINAL_CHARGE_MODEL, expression, "Potential"
    )
    for contact, circuit_node in (
        ("source", SOURCE_INTERNAL_NODE),
        ("drain", DRAIN_INTERNAL_NODE),
    ):
        core.devsim.delete_contact_equation(
            device=device, contact=contact, name="PotentialEquation"
        )
        model = f"{contact}_p3_circuit_potential_bc"
        core.devsim.contact_node_model(
            device=device,
            contact=contact,
            name=model,
            equation=f"Potential-{circuit_node}",
        )
        core.devsim.contact_node_model(
            device=device,
            contact=contact,
            name=f"{model}:Potential",
            equation="1",
        )
        core.devsim.contact_node_model(
            device=device,
            contact=contact,
            name=f"{model}:{circuit_node}",
            equation="-1",
        )
        core.devsim.contact_equation(
            device=device,
            contact=contact,
            name="PotentialEquation",
            node_model=model,
            edge_charge_model=TERMINAL_CHARGE_MODEL,
            circuit_node=circuit_node,
        )


def bind_transport_contacts_to_circuit(
    device: str, runtime: dict[str, Any]
) -> None:
    width_cm = float(runtime["device"]["width_cm"])
    expression = f"{width_cm:.15e}*ElectronCurrent"
    core.CreateEdgeModel(device, "channel", TERMINAL_CURRENT_MODEL, expression)
    for variable in ("Electrons", "Potential"):
        core.CreateEdgeModelDerivatives(
            device, "channel", TERMINAL_CURRENT_MODEL, expression, variable
        )
    for contact, circuit_node in (
        ("source", SOURCE_INTERNAL_NODE),
        ("drain", DRAIN_INTERNAL_NODE),
    ):
        core.devsim.delete_contact_equation(
            device=device,
            contact=contact,
            name="ElectronContinuityEquation",
        )
        core.devsim.contact_equation(
            device=device,
            contact=contact,
            name="ElectronContinuityEquation",
            node_model=f"{contact}_electron_bc",
            edge_current_model=TERMINAL_CURRENT_MODEL,
            circuit_node=circuit_node,
        )


def initialize_device(
    device: str,
    runtime: dict[str, Any],
    mesh_spec: dict[str, Any],
    t02_a_config: dict[str, Any],
    mesh_level: str,
    case: dict[str, Any],
) -> bool:
    circuit_coupled = float(case["r_pair_ohm"]) > 0.0
    if circuit_coupled:
        install_series_circuit(case)
    else:
        clear_circuit()
    t02_a.initialize_enabled_device(
        device, runtime, t02_a_config, mesh_level, mesh_spec
    )
    if circuit_coupled:
        bind_potential_contacts_to_circuit(
            device, float(runtime["device"]["width_cm"])
        )
    return circuit_coupled


def install_transport(
    device: str, runtime: dict[str, Any], circuit_coupled: bool
) -> None:
    core.create_transport(device, runtime)
    if circuit_coupled:
        bind_transport_contacts_to_circuit(device, runtime)
    core.devsim.element_from_edge_model(
        device=device, region="channel", edge_model="ElectronCurrent"
    )


def set_operating_bias(
    device: str,
    *,
    circuit_coupled: bool,
    source_v: float,
    drain_v: float,
    vbg_v: float,
    vtg_v: float,
) -> None:
    if circuit_coupled:
        for contact, value in (("source", source_v), ("drain", drain_v)):
            core.devsim.set_parameter(
                device=device, name=f"{contact}_bias", value=value
            )
        core.devsim.set_parameter(
            device=device, name="bottom_gate_bias", value=vbg_v
        )
        core.devsim.set_parameter(device=device, name="top_gate_bias", value=vtg_v)
        core.devsim.circuit_alter(name=SOURCE_VOLTAGE_ELEMENT, value=source_v)
        core.devsim.circuit_alter(name=DRAIN_VOLTAGE_ELEMENT, value=drain_v)
        return
    t02_a.set_enabled_biases(
        device,
        source_v=source_v,
        drain_v=drain_v,
        bottom_gate_v=vbg_v,
        top_gate_v=vtg_v,
    )


def tracked_solve(
    device: str,
    runtime: dict[str, Any],
    label: str,
    *,
    coupled: bool,
    metadata: dict[str, Any],
    solver_log: dict[str, Any],
    solver_log_path: Path,
) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        record = core.solve_dc(device, runtime, label, coupled=coupled)
    except Exception as error:  # noqa: BLE001
        record = {
            "label": label,
            "converged": False,
            "elapsed_seconds": time.perf_counter() - started,
            "error": repr(error),
            **metadata,
        }
        solver_log["solver_records"].append(record)
        core.write_json(solver_log_path, solver_log)
        raise
    record.update(metadata)
    solver_log["solver_records"].append(record)
    core.write_json(solver_log_path, solver_log)
    return record


def raw_contact_currents(device: str) -> tuple[float, float]:
    source = float(
        core.devsim.get_contact_current(
            device=device,
            contact="source",
            equation="ElectronContinuityEquation",
        )
    )
    drain = float(
        core.devsim.get_contact_current(
            device=device,
            contact="drain",
            equation="ElectronContinuityEquation",
        )
    )
    return source, drain


def branch_current(name: str) -> float:
    node = f"{name}.I"
    if node not in core.devsim.get_circuit_node_list():
        raise RuntimeError(f"missing DEVSIM circuit branch-current node {node}")
    return float(core.devsim.get_circuit_node_value(solution="dcop", node=node))


def collect_point(
    device: str,
    runtime: dict[str, Any],
    case: dict[str, Any],
    *,
    circuit_coupled: bool,
    device_id: str,
    curve_kind: str,
    curve_id: str,
    point_index: int,
    mesh_level: str,
    mode_id: str,
    source_v: float,
    drain_v: float,
    vbg_v: float,
    vtg_v: float,
    solve_record: dict[str, Any],
    acceptance: dict[str, Any],
) -> dict[str, Any]:
    raw_source, raw_drain = raw_contact_currents(device)
    width_cm = float(runtime["device"]["width_cm"])
    if circuit_coupled:
        source_terminal = raw_source
        drain_terminal = raw_drain
        source_per_cm = raw_source / width_cm
        drain_per_cm = raw_drain / width_cm
        solutions = sorted(core.devsim.get_circuit_solution_list())
        if "dcop" not in solutions:
            raise RuntimeError("DEVSIM circuit solution list does not contain dcop")
        source_external = float(
            core.devsim.get_circuit_node_value(
                solution="dcop", node=SOURCE_EXTERNAL_NODE
            )
        )
        source_internal = float(
            core.devsim.get_circuit_node_value(
                solution="dcop", node=SOURCE_INTERNAL_NODE
            )
        )
        drain_external = float(
            core.devsim.get_circuit_node_value(
                solution="dcop", node=DRAIN_EXTERNAL_NODE
            )
        )
        drain_internal = float(
            core.devsim.get_circuit_node_value(
                solution="dcop", node=DRAIN_INTERNAL_NODE
            )
        )
        source_resistor_current = (
            source_external - source_internal
        ) / float(case["r_source_ohm"])
        drain_resistor_current = (
            drain_external - drain_internal
        ) / float(case["r_drain_ohm"])
        source_voltage_current = branch_current(SOURCE_VOLTAGE_ELEMENT)
        drain_voltage_current = branch_current(DRAIN_VOLTAGE_ELEMENT)
        external_source_terminal = source_resistor_current
        external_drain_terminal = drain_resistor_current
        source_kcl = source_terminal - source_resistor_current
        drain_kcl = drain_terminal - drain_resistor_current
        floor = float(acceptance["circuit_relative_residual_floor_a"])
        source_kcl_relative = abs(source_kcl) / max(
            abs(source_terminal), abs(source_resistor_current), floor
        )
        drain_kcl_relative = abs(drain_kcl) / max(
            abs(drain_terminal), abs(drain_resistor_current), floor
        )
        source_drop = source_internal - source_external
        drain_drop = drain_external - drain_internal
        total_drop = source_drop + drain_drop
        expected_drop = abs(external_drain_terminal) * float(case["r_pair_ohm"])
        ohms_residual = total_drop - expected_drop
        ohms_relative = abs(ohms_residual) / max(
            abs(total_drop), abs(expected_drop), 1.0e-30
        )
        internal_vds = drain_internal - source_internal
        external_vds = drain_external - source_external
        partition_residual = external_vds - (
            source_drop + internal_vds + drain_drop
        )
        resistor_power = (
            source_resistor_current * source_resistor_current
            * float(case["r_source_ohm"])
            + drain_resistor_current * drain_resistor_current
            * float(case["r_drain_ohm"])
        )
        solution_json = json.dumps(solutions, sort_keys=True)
    else:
        source_per_cm = raw_source
        drain_per_cm = raw_drain
        source_terminal = raw_source * width_cm
        drain_terminal = raw_drain * width_cm
        source_external = source_v
        source_internal = source_v
        drain_external = drain_v
        drain_internal = drain_v
        source_resistor_current = 0.0
        drain_resistor_current = 0.0
        source_voltage_current = 0.0
        drain_voltage_current = 0.0
        external_source_terminal = source_terminal
        external_drain_terminal = drain_terminal
        source_kcl = 0.0
        drain_kcl = 0.0
        source_kcl_relative = 0.0
        drain_kcl_relative = 0.0
        source_drop = 0.0
        drain_drop = 0.0
        total_drop = 0.0
        ohms_residual = 0.0
        ohms_relative = 0.0
        internal_vds = drain_v - source_v
        external_vds = internal_vds
        partition_residual = 0.0
        resistor_power = 0.0
        solution_json = "[]"

    magnitude = max(abs(source_per_cm), abs(drain_per_cm), 1.0e-300)
    center = core.nearest_channel_state(device, runtime)
    closure_applicable = (
        circuit_coupled
        and external_vds > 0.0
        and vtg_v >= 0.3 - 1.0e-12
    )
    point_uid = f"{case['case_id']}:{curve_id}:{point_index:03d}"
    return {
        "point_uid": point_uid,
        "parameter_group_id": "P3",
        "changed_parameter": (
            "symmetric_total_source_drain_series_resistance_width_product"
        ),
        "case_id": case["case_id"],
        "r_pair_w_kohm_um": float(case["r_pair_w_kohm_um"]),
        "r_pair_ohm": float(case["r_pair_ohm"]),
        "r_source_ohm": float(case["r_source_ohm"]),
        "r_drain_ohm": float(case["r_drain_ohm"]),
        "execution_mode": case["execution_mode"],
        "circuit_coupled": circuit_coupled,
        "device_id": device_id,
        "curve_kind": curve_kind,
        "curve_id": curve_id,
        "point_index": point_index,
        "mesh_level": mesh_level,
        "stage_id": STAGE_ID,
        "mode_id": mode_id,
        "vbg_v": vbg_v,
        "vtg_v": vtg_v,
        "requested_external_source_v": source_v,
        "requested_external_vds_v": drain_v - source_v,
        "external_source_v": source_external,
        "external_drain_v": drain_external,
        "external_vds_v": external_vds,
        "internal_source_v": source_internal,
        "internal_drain_v": drain_internal,
        "internal_device_vds_v": internal_vds,
        "source_current_a_per_cm": source_per_cm,
        "drain_current_a_per_cm": drain_per_cm,
        "source_current_terminal_a": source_terminal,
        "drain_current_terminal_a": drain_terminal,
        "external_source_current_terminal_a": external_source_terminal,
        "external_drain_current_terminal_a": external_drain_terminal,
        "external_source_current_a_per_cm": external_source_terminal / width_cm,
        "external_drain_current_a_per_cm": external_drain_terminal / width_cm,
        "current_imbalance_a_per_cm": source_per_cm + drain_per_cm,
        "relative_current_imbalance": abs(source_per_cm + drain_per_cm) / magnitude,
        "source_resistor_current_external_to_internal_a": source_resistor_current,
        "drain_resistor_current_external_to_internal_a": drain_resistor_current,
        "source_voltage_source_current_a": source_voltage_current,
        "drain_voltage_source_current_a": drain_voltage_current,
        "source_kcl_residual_a": source_kcl,
        "drain_kcl_residual_a": drain_kcl,
        "source_kcl_relative_residual": source_kcl_relative,
        "drain_kcl_relative_residual": drain_kcl_relative,
        "source_drop_v": source_drop,
        "drain_drop_v": drain_drop,
        "total_resistor_drop_v": total_drop,
        "circuit_ohms_law_residual_v": ohms_residual,
        "circuit_ohms_law_relative_residual": ohms_relative,
        "voltage_partition_residual_v": partition_residual,
        "total_resistor_power_w": resistor_power,
        "circuit_closure_applicable": closure_applicable,
        "circuit_solution_list_json": solution_json,
        "center_channel_potential_v": center["center_channel_potential_v"],
        "center_channel_electron_density_cm3": center[
            "center_channel_electron_density_cm3"
        ],
        "solve_seconds": float(solve_record["elapsed_seconds"]),
        "converged": bool(solve_record["converged"]),
    }


def cleanup_device(device: str) -> None:
    if device in core.devsim.get_device_list():
        core.devsim.delete_device(device=device)
    clear_circuit()


def run_transfer_device(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_a_config: dict[str, Any],
    config: dict[str, Any],
    case: dict[str, Any],
    rows: list[dict[str, Any]],
    solver_log: dict[str, Any],
    solver_log_path: Path,
) -> dict[str, Any]:
    protocol = config["bias_protocol"]["transfer"]
    mesh_level = config["inheritance"]["required_mesh_level"]
    runtime, mesh_spec = runtime_for_device(
        baseline, mesh_config, t02_a_config, mesh_level
    )
    mode_id = t02_a_config["top_stack_contract"]["enabled_mode"]["mode_id"]
    device = f"t03_p3_contact_{case['case_id']}_transfer"
    record_start = len(solver_log["solver_records"])
    row_start = len(rows)
    started = time.perf_counter()
    circuit_coupled = False
    solver_log["current_device"] = {
        "device_id": device,
        "case_id": case["case_id"],
        "curve_kind": "transfer",
    }
    core.write_json(solver_log_path, solver_log)
    try:
        circuit_coupled = initialize_device(
            device, runtime, mesh_spec, t02_a_config, mesh_level, case
        )
        regions, contacts, interfaces = t02_a.active_topology(
            device, t02_a.ENABLED_REGIONS
        )
        node_count, element_count = t02_a.active_counts(
            device, t02_a.ENABLED_REGIONS
        )
        set_operating_bias(
            device,
            circuit_coupled=circuit_coupled,
            source_v=0.0,
            drain_v=0.0,
            vbg_v=0.0,
            vtg_v=0.0,
        )
        common = {
            "case_id": case["case_id"],
            "device_id": device,
            "curve_kind": "transfer",
            "circuit_coupled": circuit_coupled,
        }
        tracked_solve(
            device,
            runtime,
            f"{device}_POISSON_ZERO",
            coupled=False,
            metadata={**common, "solve_role": "poisson_zero"},
            solver_log=solver_log,
            solver_log_path=solver_log_path,
        )
        install_transport(device, runtime, circuit_coupled)
        equilibrium = tracked_solve(
            device,
            runtime,
            f"{device}_COUPLED_ZERO",
            coupled=True,
            metadata={**common, "solve_role": "coupled_zero"},
            solver_log=solver_log,
            solver_log_path=solver_log_path,
        )
        zero = collect_point(
            device,
            runtime,
            case,
            circuit_coupled=circuit_coupled,
            device_id=device,
            curve_kind="initialization",
            curve_id="transfer_zero_equilibrium",
            point_index=0,
            mesh_level=mesh_level,
            mode_id=mode_id,
            source_v=0.0,
            drain_v=0.0,
            vbg_v=0.0,
            vtg_v=0.0,
            solve_record=equilibrium,
            acceptance=config["acceptance"],
        )

        for vds_v in [
            float(value)
            for value in protocol["external_low_vds_values_v"]
            if float(value) > 0.0
        ]:
            set_operating_bias(
                device,
                circuit_coupled=circuit_coupled,
                source_v=0.0,
                drain_v=vds_v,
                vbg_v=0.0,
                vtg_v=0.0,
            )
            tracked_solve(
                device,
                runtime,
                f"{device}_LOW_VDS_{vds_v:.6g}",
                coupled=True,
                metadata={**common, "solve_role": "drain_continuation"},
                solver_log=solver_log,
                solver_log_path=solver_log_path,
            )

        drain_v = float(protocol["external_drain_v"])
        for vtg_v in [
            float(value) for value in protocol["primary_negative_preconditioning_v"]
        ]:
            set_operating_bias(
                device,
                circuit_coupled=circuit_coupled,
                source_v=0.0,
                drain_v=drain_v,
                vbg_v=0.0,
                vtg_v=vtg_v,
            )
            tracked_solve(
                device,
                runtime,
                f"{device}_PRE_{vtg_v:.6g}",
                coupled=True,
                metadata={**common, "solve_role": "gate_preconditioning"},
                solver_log=solver_log,
                solver_log_path=solver_log_path,
            )

        for index, vtg_v in enumerate(transfer_grid(config)):
            set_operating_bias(
                device,
                circuit_coupled=circuit_coupled,
                source_v=0.0,
                drain_v=drain_v,
                vbg_v=0.0,
                vtg_v=vtg_v,
            )
            record = tracked_solve(
                device,
                runtime,
                f"{device}_TRANSFER_{vtg_v:.6g}",
                coupled=True,
                metadata={**common, "solve_role": "reported_transfer"},
                solver_log=solver_log,
                solver_log_path=solver_log_path,
            )
            rows.append(
                collect_point(
                    device,
                    runtime,
                    case,
                    circuit_coupled=circuit_coupled,
                    device_id=device,
                    curve_kind="transfer",
                    curve_id=f"{case['case_id']}_transfer",
                    point_index=index,
                    mesh_level=mesh_level,
                    mode_id=mode_id,
                    source_v=0.0,
                    drain_v=drain_v,
                    vbg_v=0.0,
                    vtg_v=vtg_v,
                    solve_record=record,
                    acceptance=config["acceptance"],
                )
            )

        summary = {
            "device_id": device,
            "case_id": case["case_id"],
            "curve_kind": "transfer",
            "curve_id": f"{case['case_id']}_transfer",
            "target_top_gate_v": None,
            "circuit_coupled": circuit_coupled,
            "mesh_level": mesh_level,
            "mode_id": mode_id,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "circuit_nodes": sorted(core.devsim.get_circuit_node_list())
            if circuit_coupled
            else [],
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(solver_log["solver_records"]) - record_start,
            "reported_point_count": len(rows) - row_start,
            "zero_equilibrium_maximum_absolute_current_a_per_cm": max(
                abs(float(zero["source_current_a_per_cm"])),
                abs(float(zero["drain_current_a_per_cm"])),
            ),
            "wall_seconds": time.perf_counter() - started,
        }
        solver_log["runs"].append(summary)
        solver_log["current_device"] = None
        core.write_json(solver_log_path, solver_log)
        return summary
    finally:
        cleanup_device(device)


def run_output_device(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_a_config: dict[str, Any],
    config: dict[str, Any],
    case: dict[str, Any],
    target_vtg_v: float,
    rows: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    run_dir: Path,
    solver_log: dict[str, Any],
    solver_log_path: Path,
) -> dict[str, Any]:
    protocol = config["bias_protocol"]["output"]
    mesh_level = config["inheritance"]["required_mesh_level"]
    runtime, mesh_spec = runtime_for_device(
        baseline, mesh_config, t02_a_config, mesh_level
    )
    mode_id = t02_a_config["top_stack_contract"]["enabled_mode"]["mode_id"]
    target_token = value_token(target_vtg_v)
    device = f"t03_p3_contact_{case['case_id']}_output_vtg_{target_token}"
    curve_id = f"{case['case_id']}_output_vtg_{target_token}"
    record_start = len(solver_log["solver_records"])
    row_start = len(rows)
    started = time.perf_counter()
    circuit_coupled = False
    solver_log["current_device"] = {
        "device_id": device,
        "case_id": case["case_id"],
        "curve_kind": "output",
        "target_top_gate_v": target_vtg_v,
    }
    core.write_json(solver_log_path, solver_log)
    try:
        circuit_coupled = initialize_device(
            device, runtime, mesh_spec, t02_a_config, mesh_level, case
        )
        regions, contacts, interfaces = t02_a.active_topology(
            device, t02_a.ENABLED_REGIONS
        )
        node_count, element_count = t02_a.active_counts(
            device, t02_a.ENABLED_REGIONS
        )
        common = {
            "case_id": case["case_id"],
            "device_id": device,
            "curve_kind": "output",
            "target_top_gate_v": target_vtg_v,
            "circuit_coupled": circuit_coupled,
        }
        set_operating_bias(
            device,
            circuit_coupled=circuit_coupled,
            source_v=0.0,
            drain_v=0.0,
            vbg_v=0.0,
            vtg_v=0.0,
        )
        tracked_solve(
            device,
            runtime,
            f"{device}_POISSON_ZERO",
            coupled=False,
            metadata={**common, "solve_role": "poisson_zero"},
            solver_log=solver_log,
            solver_log_path=solver_log_path,
        )
        install_transport(device, runtime, circuit_coupled)
        equilibrium = tracked_solve(
            device,
            runtime,
            f"{device}_COUPLED_ZERO",
            coupled=True,
            metadata={**common, "solve_role": "coupled_zero"},
            solver_log=solver_log,
            solver_log_path=solver_log_path,
        )
        zero = collect_point(
            device,
            runtime,
            case,
            circuit_coupled=circuit_coupled,
            device_id=device,
            curve_kind="initialization",
            curve_id=f"{curve_id}_zero_equilibrium",
            point_index=0,
            mesh_level=mesh_level,
            mode_id=mode_id,
            source_v=0.0,
            drain_v=0.0,
            vbg_v=0.0,
            vtg_v=0.0,
            solve_record=equilibrium,
            acceptance=config["acceptance"],
        )

        for gate_v in [
            float(value)
            for value in protocol["gate_preconditioning_ladder_v"]
            if float(value) <= target_vtg_v + 1.0e-12
        ]:
            set_operating_bias(
                device,
                circuit_coupled=circuit_coupled,
                source_v=0.0,
                drain_v=0.0,
                vbg_v=0.0,
                vtg_v=gate_v,
            )
            tracked_solve(
                device,
                runtime,
                f"{device}_GATE_{gate_v:.6g}",
                coupled=True,
                metadata={**common, "solve_role": "output_gate_ramp"},
                solver_log=solver_log,
                solver_log_path=solver_log_path,
            )

        final_row: dict[str, Any] | None = None
        for index, vds_v in enumerate(
            [float(value) for value in protocol["external_drain_values_v"]]
        ):
            set_operating_bias(
                device,
                circuit_coupled=circuit_coupled,
                source_v=0.0,
                drain_v=vds_v,
                vbg_v=0.0,
                vtg_v=target_vtg_v,
            )
            record = tracked_solve(
                device,
                runtime,
                f"{device}_OUTPUT_{vds_v:.6g}",
                coupled=True,
                metadata={**common, "solve_role": "reported_output"},
                solver_log=solver_log,
                solver_log_path=solver_log_path,
            )
            final_row = collect_point(
                device,
                runtime,
                case,
                circuit_coupled=circuit_coupled,
                device_id=device,
                curve_kind="output",
                curve_id=curve_id,
                point_index=index,
                mesh_level=mesh_level,
                mode_id=mode_id,
                source_v=0.0,
                drain_v=vds_v,
                vbg_v=0.0,
                vtg_v=target_vtg_v,
                solve_record=record,
                acceptance=config["acceptance"],
            )
            rows.append(final_row)

        if same_value(target_vtg_v, 1.0):
            if final_row is None or not same_value(
                float(final_row["external_vds_v"]), 0.2, abs_tol=1.0e-9
            ):
                raise RuntimeError("T03-P3 state point is not VTG=1.0 V, VDS=0.2 V")
            state_entries.append(
                write_state(
                    device,
                    runtime,
                    case,
                    mesh_level,
                    mode_id,
                    final_row,
                    run_dir,
                )
            )

        summary = {
            "device_id": device,
            "case_id": case["case_id"],
            "curve_kind": "output",
            "curve_id": curve_id,
            "target_top_gate_v": target_vtg_v,
            "circuit_coupled": circuit_coupled,
            "mesh_level": mesh_level,
            "mode_id": mode_id,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "circuit_nodes": sorted(core.devsim.get_circuit_node_list())
            if circuit_coupled
            else [],
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(solver_log["solver_records"]) - record_start,
            "reported_point_count": len(rows) - row_start,
            "zero_equilibrium_maximum_absolute_current_a_per_cm": max(
                abs(float(zero["source_current_a_per_cm"])),
                abs(float(zero["drain_current_a_per_cm"])),
            ),
            "wall_seconds": time.perf_counter() - started,
        }
        solver_log["runs"].append(summary)
        solver_log["current_device"] = None
        core.write_json(solver_log_path, solver_log)
        return summary
    finally:
        cleanup_device(device)


def write_state(
    device: str,
    runtime: dict[str, Any],
    case: dict[str, Any],
    mesh_level: str,
    mode_id: str,
    bias_row: dict[str, Any],
    run_dir: Path,
) -> dict[str, Any]:
    state_id = f"contact_{case['case_id']}_output_vtg_1p0_vds_0p2"
    state_label = f"{case['case_id']} at VTG=1.0 V, external VDS=0.2 V"
    bias = {
        "source_v": float(bias_row["external_source_v"]),
        "drain_v": float(bias_row["external_drain_v"]),
        "bottom_gate_v": float(bias_row["vbg_v"]),
        "top_gate_v": float(bias_row["vtg_v"]),
    }
    node_rows = []
    for row in t02_a.collect_enabled_state(device, mode_id, bias):
        node_rows.append(
            {
                "state_id": state_id,
                "state_label": state_label,
                "parameter_group_id": "P3",
                "case_id": case["case_id"],
                "r_pair_w_kohm_um": float(case["r_pair_w_kohm_um"]),
                "r_pair_ohm": float(case["r_pair_ohm"]),
                "mesh_level": mesh_level,
                "stage_id": STAGE_ID,
                "mode_id": mode_id,
                "external_source_v": float(bias_row["external_source_v"]),
                "external_drain_v": float(bias_row["external_drain_v"]),
                "internal_source_v": float(bias_row["internal_source_v"]),
                "internal_drain_v": float(bias_row["internal_drain_v"]),
                "vbg_v": float(bias_row["vbg_v"]),
                "vtg_v": float(bias_row["vtg_v"]),
                "region": row["region"],
                "x_cm": row["x_cm"],
                "y_cm": row["y_cm"],
                "x_um": row["x_um"],
                "y_nm": row["y_nm"],
                "potential_v": row["potential_v"],
                "electron_density_cm3": row["electron_density_cm3"],
            }
        )

    state_spec = {
        "state_id": state_id,
        "label": state_label,
        "source_family": "top_primary",
        "vbg_v": float(bias_row["vbg_v"]),
        "vtg_v": float(bias_row["vtg_v"]),
        "vds_v": float(bias_row["external_vds_v"]),
    }
    element_rows = []
    for source in t02_c.collect_current_elements(device, mesh_level, state_spec):
        row = dict(source)
        row.pop("source_family", None)
        row.update(
            {
                "parameter_group_id": "P3",
                "case_id": case["case_id"],
                "r_pair_w_kohm_um": float(case["r_pair_w_kohm_um"]),
                "r_pair_ohm": float(case["r_pair_ohm"]),
                "stage_id": STAGE_ID,
                "external_vds_v": float(bias_row["external_vds_v"]),
            }
        )
        row.pop("vds_v", None)
        element_rows.append(row)

    base = f"t03_p3_contact_{case['case_id']}_output_vtg_1p0_vds_0p2"
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
        "state_id": state_id,
        "state_label": state_label,
        "parameter_group_id": "P3",
        "case_id": case["case_id"],
        "r_pair_w_kohm_um": float(case["r_pair_w_kohm_um"]),
        "r_pair_ohm": float(case["r_pair_ohm"]),
        "mesh_level": mesh_level,
        "stage_id": STAGE_ID,
        "vbg_v": float(bias_row["vbg_v"]),
        "vtg_v": float(bias_row["vtg_v"]),
        "external_vds_v": float(bias_row["external_vds_v"]),
        "internal_source_v": float(bias_row["internal_source_v"]),
        "internal_drain_v": float(bias_row["internal_drain_v"]),
        "internal_device_vds_v": float(bias_row["internal_device_vds_v"]),
        "absolute_external_drain_current_a_per_cm": abs(
            float(bias_row["external_drain_current_a_per_cm"])
        ),
        "absolute_external_drain_current_terminal_a": abs(
            float(bias_row["external_drain_current_terminal_a"])
        ),
        "relative_current_imbalance": float(bias_row["relative_current_imbalance"]),
        "source_kcl_relative_residual": float(
            bias_row["source_kcl_relative_residual"]
        ),
        "drain_kcl_relative_residual": float(
            bias_row["drain_kcl_relative_residual"]
        ),
        "circuit_ohms_law_relative_residual": float(
            bias_row["circuit_ohms_law_relative_residual"]
        ),
        "voltage_partition_residual_v": float(
            bias_row["voltage_partition_residual_v"]
        ),
        "center_channel_potential_v": float(
            bias_row["center_channel_potential_v"]
        ),
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
        "circuit_state": {
            field: bias_row[field]
            for field in (
                "external_source_v",
                "external_drain_v",
                "internal_source_v",
                "internal_drain_v",
                "source_resistor_current_external_to_internal_a",
                "drain_resistor_current_external_to_internal_a",
                "source_current_terminal_a",
                "drain_current_terminal_a",
                "source_kcl_residual_a",
                "drain_kcl_residual_a",
                "source_drop_v",
                "drain_drop_v",
                "total_resistor_drop_v",
                "total_resistor_power_w",
            )
        },
        "current_projection": {
            "source_edge_model": "ElectronCurrent",
            "api": "element_from_edge_model",
            "raw_values_per_triangle": 3,
            "cell_center_reduction": "arithmetic mean of en0/en1/en2 vectors",
            "local_unit": "A/cm^2",
        },
        "_node_rows": node_rows,
        "_element_rows": element_rows,
    }


def point_for(
    rows: list[dict[str, Any]],
    case_id: str,
    curve_kind: str,
    *,
    vtg_v: float,
    vds_v: float,
) -> dict[str, Any]:
    candidates = [
        row
        for row in rows
        if row["case_id"] == case_id
        and row["curve_kind"] == curve_kind
        and same_value(float(row["vtg_v"]), vtg_v)
        and same_value(float(row["external_vds_v"]), vds_v, abs_tol=1.0e-9)
    ]
    if len(candidates) != 1:
        raise RuntimeError(
            f"expected one {case_id} {curve_kind} point at VTG={vtg_v}, "
            f"VDS={vds_v}; found {len(candidates)}"
        )
    return candidates[0]


def build_metrics(
    config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    cases = config["sensitivity"]["cases"]
    ideal_case = case_by_id(config, "ideal_control")
    ideal_high = abs(
        float(
            point_for(
                rows,
                ideal_case["case_id"],
                "transfer",
                vtg_v=1.0,
                vds_v=0.01,
            )["external_drain_current_terminal_a"]
        )
    )
    fit_vds = [
        float(value)
        for value in config["extraction_methods"][
            "linear_region_total_resistance_width_proxy"
        ]["fit_external_vds_values_v"]
    ]
    width_um = float(config["sensitivity"]["width_um"])
    metrics: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case["case_id"])
        high = point_for(
            rows, case_id, "transfer", vtg_v=1.0, vds_v=0.01
        )
        fit_rows = [
            point_for(rows, case_id, "output", vtg_v=1.0, vds_v=value)
            for value in fit_vds
        ]
        currents = [
            abs(float(row["external_drain_current_terminal_a"])) for row in fit_rows
        ]
        conductance = sum(
            voltage * current for voltage, current in zip(fit_vds, currents, strict=True)
        ) / sum(voltage * voltage for voltage in fit_vds)
        if conductance <= 0.0:
            raise RuntimeError(f"nonpositive linear conductance for {case_id}")
        resistance = 1.0 / conductance
        resistance_width = resistance * width_um / 1000.0
        output_rows = {
            gate: point_for(rows, case_id, "output", vtg_v=gate, vds_v=0.2)
            for gate in (0.3, 0.5, 1.0)
        }
        metrics.append(
            {
                "parameter_group_id": "P3",
                "case_id": case_id,
                "r_pair_w_kohm_um": float(case["r_pair_w_kohm_um"]),
                "r_pair_ohm": float(case["r_pair_ohm"]),
                "transfer_high_gate_current_proxy_a_per_cm": abs(
                    float(high["external_drain_current_a_per_cm"])
                ),
                "transfer_high_gate_current_proxy_terminal_a": abs(
                    float(high["external_drain_current_terminal_a"])
                ),
                "transfer_high_gate_current_relative_reduction": (
                    ideal_high
                    - abs(float(high["external_drain_current_terminal_a"]))
                )
                / ideal_high,
                "output_vtg_0p3_vds_0p2_current_a_per_cm": abs(
                    float(output_rows[0.3]["external_drain_current_a_per_cm"])
                ),
                "output_vtg_0p5_vds_0p2_current_a_per_cm": abs(
                    float(output_rows[0.5]["external_drain_current_a_per_cm"])
                ),
                "output_vtg_1p0_vds_0p2_current_a_per_cm": abs(
                    float(output_rows[1.0]["external_drain_current_a_per_cm"])
                ),
                "output_vtg_0p3_vds_0p2_current_terminal_a": abs(
                    float(output_rows[0.3]["external_drain_current_terminal_a"])
                ),
                "output_vtg_0p5_vds_0p2_current_terminal_a": abs(
                    float(output_rows[0.5]["external_drain_current_terminal_a"])
                ),
                "output_vtg_1p0_vds_0p2_current_terminal_a": abs(
                    float(output_rows[1.0]["external_drain_current_terminal_a"])
                ),
                "linear_fit_point_count": len(fit_rows),
                "linear_fit_conductance_s": conductance,
                "linear_region_total_resistance_ohm": resistance,
                "linear_region_total_resistance_width_kohm_um": resistance_width,
                "added_total_resistance_width_kohm_um": 0.0,
                "declared_pair_resistance_width_kohm_um": float(
                    case["r_pair_w_kohm_um"]
                ),
                "added_resistance_relative_difference": 0.0,
                "added_resistance_diagnostic_within_15_percent": True,
                "parameter_claim_status": (
                    "NUMERICAL_LUMPED_SERIES_RESISTANCE_PROXY_NOT_MEASURED_OR_CALIBRATED"
                ),
            }
        )

    ideal_resistance_width = float(
        next(row for row in metrics if row["case_id"] == "ideal_control")[
            "linear_region_total_resistance_width_kohm_um"
        ]
    )
    diagnostic_limit = float(
        config["diagnostic_hypotheses"][
            "extracted_added_resistance_matches_declared_pair"
        ]["maximum_relative_difference"]
    )
    for row in metrics:
        added = (
            float(row["linear_region_total_resistance_width_kohm_um"])
            - ideal_resistance_width
        )
        declared = float(row["declared_pair_resistance_width_kohm_um"])
        difference = 0.0 if declared == 0.0 else abs(added - declared) / declared
        row["added_total_resistance_width_kohm_um"] = added
        row["added_resistance_relative_difference"] = difference
        row["added_resistance_diagnostic_within_15_percent"] = (
            difference <= diagnostic_limit
        )
    return metrics


def build_reference_comparison(
    rows: list[dict[str, Any]], t02_report: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ideal = sorted(
        [
            row
            for row in rows
            if row["case_id"] == "ideal_control"
            and row["curve_kind"] == "transfer"
        ],
        key=lambda row: float(row["vtg_v"]),
    )
    references = [
        row
        for row in t02_report["family_points"]
        if row["family_id"] == "top_primary"
        and row["sweep_direction"] == "forward"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    ]
    comparisons: list[dict[str, Any]] = []
    for row in ideal:
        gate = float(row["vtg_v"])
        reference = next(
            item
            for item in references
            if same_value(float(item["primary_gate_v"]), gate)
        )
        comparisons.append(
            {
                "primary_gate_v": gate,
                "p3_abs_external_drain_current_a_per_cm": abs(
                    float(row["external_drain_current_a_per_cm"])
                ),
                "t02_c_abs_drain_current_a_per_cm": abs(
                    float(reference["drain_current_a_per_cm"])
                ),
                "current_relative_difference": relative_difference(
                    abs(float(row["external_drain_current_a_per_cm"])),
                    abs(float(reference["drain_current_a_per_cm"])),
                ),
                "p3_center_channel_potential_v": float(
                    row["center_channel_potential_v"]
                ),
                "t02_c_center_channel_potential_v": float(
                    reference["center_channel_potential_v"]
                ),
                "center_channel_potential_difference_v": abs(
                    float(row["center_channel_potential_v"])
                    - float(reference["center_channel_potential_v"])
                ),
                "p3_center_channel_electron_density_cm3": float(
                    row["center_channel_electron_density_cm3"]
                ),
                "t02_c_center_channel_electron_density_cm3": float(
                    reference["center_channel_electron_density_cm3"]
                ),
                "center_density_relative_difference": relative_difference(
                    float(row["center_channel_electron_density_cm3"]),
                    float(reference["center_channel_electron_density_cm3"]),
                ),
            }
        )
    return comparisons, {
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
    }


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))
    os.environ.setdefault("TEMP", str(temp_dir))
    os.environ.setdefault("TMP", str(temp_dir))


def render_sensitivity_figure(
    config: dict[str, Any],
    transfer_rows: list[dict[str, Any]],
    output_rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    path: Path,
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    colors = {
        "ideal_control": "#4f5963",
        "literature_low_magnitude_proxy": "#287d59",
        "literature_high_magnitude_proxy": "#b65f2e",
    }
    labels = {
        case["case_id"]: f"RpairW={float(case['r_pair_w_kohm_um']):g} kOhm um"
        for case in config["sensitivity"]["cases"]
    }
    figure, axes = plt.subplots(2, 2, figsize=(11.0, 8.0), constrained_layout=True)
    for case in config["sensitivity"]["cases"]:
        case_id = str(case["case_id"])
        curve = sorted(
            [row for row in transfer_rows if row["case_id"] == case_id],
            key=lambda row: float(row["vtg_v"]),
        )
        axes[0][0].semilogy(
            [float(row["vtg_v"]) for row in curve],
            [abs(float(row["external_drain_current_a_per_cm"])) for row in curve],
            color=colors[case_id],
            linewidth=1.8,
            label=labels[case_id],
        )
        output_curve = sorted(
            [
                row
                for row in output_rows
                if row["case_id"] == case_id and same_value(float(row["vtg_v"]), 1.0)
            ],
            key=lambda row: float(row["external_vds_v"]),
        )
        axes[0][1].plot(
            [float(row["external_vds_v"]) for row in output_curve],
            [abs(float(row["external_drain_current_a_per_cm"])) for row in output_curve],
            color=colors[case_id],
            marker="o",
            markersize=3.5,
            linewidth=1.6,
            label=labels[case_id],
        )
    axes[0][0].set_title("Top-gate transfer at external VDS=0.01 V")
    axes[0][0].set_xlabel("Top-gate voltage (V)")
    axes[0][0].set_ylabel("Absolute external drain current per width (A/cm)")
    axes[0][0].legend(fontsize=8)
    axes[0][1].set_title("Output at VTG=1.0 V")
    axes[0][1].set_xlabel("External drain voltage (V)")
    axes[0][1].set_ylabel("Absolute external drain current per width (A/cm)")
    axes[0][1].legend(fontsize=8)

    x = [float(row["r_pair_w_kohm_um"]) for row in metrics]
    total = [
        float(row["linear_region_total_resistance_width_kohm_um"])
        for row in metrics
    ]
    axes[1][0].plot(x, total, "o-", color="#2563a6", linewidth=1.8)
    axes[1][0].set_title("External linear-region total resistance proxy")
    axes[1][0].set_xlabel("Declared RpairW proxy (kOhm um)")
    axes[1][0].set_ylabel("Extracted RtotalW proxy (kOhm um)")

    reductions = [
        100.0 * float(row["transfer_high_gate_current_relative_reduction"])
        for row in metrics
    ]
    axes[1][1].plot(x, reductions, "s-", color="#b65f2e", linewidth=1.8)
    axes[1][1].set_title("Sampled high-gate current response")
    axes[1][1].set_xlabel("Declared RpairW proxy (kOhm um)")
    axes[1][1].set_ylabel("Current reduction versus ideal (%)")
    for axis in axes.flat:
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle(
        "T03-P3 symmetric lumped contact-series-resistance numerical sensitivity",
        fontsize=12,
    )
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

    ordered = sorted(state_entries, key=lambda row: float(row["r_pair_w_kohm_um"]))
    potentials = [
        float(row["potential_v"]) for entry in ordered for row in entry["_node_rows"]
    ]
    densities = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
        for entry in ordered
        for row in entry["_node_rows"]
        if row["region"] == "channel"
    ]
    currents = [
        math.log10(
            max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1.0e-300)
        )
        for entry in ordered
        for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(densities), max(densities)),
        Normalize(min(currents), max(currents)),
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
            cmap=cmaps[0],
            norm=norms[0],
            s=5,
            linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes],
            [float(row["y_nm"]) for row in channel_nodes],
            c=[
                math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
                for row in channel_nodes
            ],
            cmap=cmaps[1],
            norm=norms[1],
            s=6,
            linewidths=0,
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
            cmap=cmaps[2],
            norm=norms[2],
            s=6,
            linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            line_color = "white" if column != 1 else "#555555"
            axis.axhline(30.0, color=line_color, linewidth=0.6)
            axis.axhline(54.0, color=line_color, linewidth=0.6)
            axis.set_ylabel(
                f"RpairW={float(entry['r_pair_w_kohm_um']):g} kOhm um\ny (nm)"
            )
            if row_index == 2:
                axis.set_xlabel("x (um)")
    axes[0][0].set_title("Potential (V)")
    axes[0][1].set_title("log10 electron density (cm^-3)")
    axes[0][2].set_title("log10 |J| (A/cm^2)")
    for column, (norm, cmap) in enumerate(zip(norms, cmaps, strict=True)):
        figure.colorbar(
            ScalarMappable(norm=norm, cmap=cmap),
            ax=axes[:, column],
            shrink=0.82,
            pad=0.02,
        )
    figure.suptitle(
        "T03-P3 VTG=1.0 V, external VDS=0.2 V numerical states",
        fontsize=12,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def public_state(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def circuit_balance_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {field: row[field] for field in CIRCUIT_BALANCE_FIELDNAMES} for row in rows
    ]


def persist_partial(
    config: dict[str, Any],
    paths: dict[str, Path],
    transfer_rows: list[dict[str, Any]],
    output_rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    reference_rows: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
) -> None:
    all_rows = [*transfer_rows, *output_rows]
    core.write_csv(paths["transfer_csv"], transfer_rows, POINT_FIELDNAMES)
    core.write_csv(paths["output_csv"], output_rows, POINT_FIELDNAMES)
    core.write_csv(paths["metric_csv"], metrics, METRIC_FIELDNAMES)
    core.write_csv(
        paths["circuit_balance_csv"],
        circuit_balance_rows(all_rows),
        CIRCUIT_BALANCE_FIELDNAMES,
    )
    core.write_csv(
        paths["reference_comparison_csv"], reference_rows, REFERENCE_FIELDNAMES
    )
    core.write_csv(
        paths["state_summary_csv"],
        [
            {field: entry.get(field, "") for field in STATE_SUMMARY_FIELDNAMES}
            for entry in state_entries
        ],
        STATE_SUMMARY_FIELDNAMES,
    )
    states = [public_state(entry) for entry in state_entries]
    core.write_json(
        paths["state_manifest"],
        {
            "case_id": config["case_id"],
            "stage": config["stage"],
            "entry_count": len(states),
            "entries": states,
        },
    )


def directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def assess(
    config: dict[str, Any],
    contract: dict[str, Any],
    transfer_rows: list[dict[str, Any]],
    output_rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    reference_summary: dict[str, Any],
    state_entries: list[dict[str, Any]],
    solver_log: dict[str, Any],
    figure_hashes: tuple[str | None, str | None],
    run_dir: Path,
    caught_error: Exception | None,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    all_rows = [*transfer_rows, *output_rows]
    records = solver_log["solver_records"]
    runs = solver_log["runs"]
    if caught_error is not None:
        add_check(checks, "stage_exception", False, repr(caught_error))
        return {
            "status": "FAIL",
            "checks": checks,
            "failures": ["stage_exception"],
            "summary_metrics": {
                "device_count": len(runs),
                "dc_solve_count": len(records),
                "reported_point_count": len(all_rows),
                "state_count": len(state_entries),
            },
        }

    required_cases = [str(value) for value in acceptance["required_case_ids"]]
    observed_cases = [str(row["case_id"]) for row in metrics]
    add_check(
        checks,
        "static_contract_is_current_and_passed",
        contract.get("contract_status") == "PASS"
        and contract.get("config", {}).get("sha256") == core.sha256(CONFIG_PATH),
        f"contract={contract.get('contract_status')} hash={contract.get('config', {}).get('sha256')}",
    )
    add_check(
        checks,
        "three_frozen_contact_cases_completed",
        observed_cases == required_cases
        and [float(row["r_pair_w_kohm_um"]) for row in metrics]
        == [float(value) for value in acceptance["required_r_pair_w_values_kohm_um"]],
        f"cases={observed_cases}",
    )
    expected_output_counts = {
        0.3: int(config["resource_budget"]["required_output_dc_solve_counts_per_gate"][0]),
        0.5: int(config["resource_budget"]["required_output_dc_solve_counts_per_gate"][1]),
        1.0: int(config["resource_budget"]["required_output_dc_solve_counts_per_gate"][2]),
    }
    solve_counts_valid = all(
        int(run["dc_solve_count"])
        == (
            int(config["resource_budget"]["required_transfer_dc_solve_count_per_case"])
            if run["curve_kind"] == "transfer"
            else expected_output_counts[float(run["target_top_gate_v"])]
        )
        for run in runs
    )
    add_check(
        checks,
        "device_and_dc_solve_budget_exact",
        len(runs) == int(acceptance["required_total_device_count"])
        and len(records) == int(acceptance["required_total_dc_solve_count"])
        and solve_counts_valid,
        f"devices={len(runs)} solves={len(records)} counts={[run['dc_solve_count'] for run in runs]}",
    )
    add_check(
        checks,
        "reported_point_counts_exact",
        len(transfer_rows) == int(acceptance["required_transfer_point_count"])
        and len(output_rows) == int(acceptance["required_output_point_count"])
        and len(all_rows) == int(acceptance["required_total_reported_point_count"]),
        f"transfer={len(transfer_rows)} output={len(output_rows)} total={len(all_rows)}",
    )
    add_check(
        checks,
        "all_dc_solves_converged",
        len(records) == int(acceptance["required_total_dc_solve_count"])
        and all(bool(record.get("converged")) for record in records),
        f"records={len(records)} failed={sum(not bool(record.get('converged')) for record in records)}",
    )
    required_regions = sorted(acceptance["required_regions"])
    required_contacts = sorted(acceptance["required_contacts"])
    required_interfaces = sorted(acceptance["required_interfaces"])
    topology_valid = all(
        sorted(run["regions"]) == required_regions
        and sorted(run["contacts"]) == required_contacts
        and sorted(run["interfaces"]) == required_interfaces
        for run in runs
    )
    circuit_count = sum(bool(run["circuit_coupled"]) for run in runs)
    circuit_nodes_valid = all(
        (not run["circuit_coupled"] and not run["circuit_nodes"])
        or (
            run["circuit_coupled"]
            and all(
                node in run["circuit_nodes"]
                for node in (
                    SOURCE_EXTERNAL_NODE,
                    SOURCE_INTERNAL_NODE,
                    DRAIN_EXTERNAL_NODE,
                    DRAIN_INTERNAL_NODE,
                    f"{SOURCE_VOLTAGE_ELEMENT}.I",
                    f"{DRAIN_VOLTAGE_ELEMENT}.I",
                )
            )
        )
        for run in runs
    )
    add_check(
        checks,
        "topology_and_circuit_execution_modes_exact",
        topology_valid
        and circuit_count
        == int(config["resource_budget"]["required_circuit_coupled_device_count"])
        and circuit_nodes_valid,
        f"topology={topology_valid} circuit_devices={circuit_count} nodes={circuit_nodes_valid}",
    )

    max_imbalance = max(float(row["relative_current_imbalance"]) for row in all_rows)
    add_check(
        checks,
        "device_terminal_current_conservation",
        max_imbalance
        <= float(acceptance["maximum_relative_device_terminal_current_imbalance"]),
        f"maximum_relative_imbalance={max_imbalance:.6e}",
    )
    zero_rows = [row for row in output_rows if same_value(float(row["external_vds_v"]), 0.0, abs_tol=1.0e-9)]
    max_zero = max(
        abs(float(row["external_drain_current_a_per_cm"])) for row in zero_rows
    )
    add_check(
        checks,
        "zero_external_vds_current_is_negligible",
        len(zero_rows) == 9
        and max_zero
        <= float(acceptance["maximum_zero_external_vds_absolute_current_a_per_cm"]),
        f"rows={len(zero_rows)} maximum={max_zero:.6e}",
    )
    resolved_rows = [
        row
        for row in all_rows
        if float(row["external_vds_v"]) > 0.0 and float(row["vtg_v"]) >= 0.3 - 1.0e-12
    ]
    minimum_resolved = min(
        abs(float(row["external_drain_current_a_per_cm"])) for row in resolved_rows
    )
    add_check(
        checks,
        "positive_bias_currents_are_resolved",
        minimum_resolved
        >= float(acceptance["minimum_resolved_positive_current_a_per_cm"]),
        f"minimum={minimum_resolved:.6e}",
    )

    closure_rows = [row for row in all_rows if bool(row["circuit_closure_applicable"])]
    max_kcl = max(
        max(
            float(row["source_kcl_relative_residual"]),
            float(row["drain_kcl_relative_residual"]),
        )
        for row in closure_rows
    )
    max_ohm = max(
        float(row["circuit_ohms_law_relative_residual"]) for row in closure_rows
    )
    max_partition = max(
        abs(float(row["voltage_partition_residual_v"])) for row in closure_rows
    )
    add_check(
        checks,
        "self_consistent_circuit_kcl_closes",
        bool(closure_rows)
        and max_kcl <= float(acceptance["maximum_circuit_kcl_relative_residual"]),
        f"rows={len(closure_rows)} maximum={max_kcl:.6e}",
    )
    add_check(
        checks,
        "series_resistor_ohms_law_closes",
        max_ohm
        <= float(acceptance["maximum_circuit_ohms_law_relative_residual"]),
        f"maximum={max_ohm:.6e}",
    )
    add_check(
        checks,
        "external_voltage_partition_closes",
        max_partition
        <= float(acceptance["maximum_circuit_voltage_partition_absolute_residual_v"]),
        f"maximum={max_partition:.6e} V",
    )
    rail_tolerance = float(
        acceptance["maximum_circuit_voltage_partition_absolute_residual_v"]
    )
    circuit_rows = [row for row in all_rows if bool(row["circuit_coupled"])]
    rails_valid = all(
        float(row["external_source_v"]) - rail_tolerance
        <= float(row["internal_source_v"])
        <= float(row["internal_drain_v"]) + rail_tolerance
        <= float(row["external_drain_v"]) + 2.0 * rail_tolerance
        for row in circuit_rows
    )
    add_check(
        checks,
        "internal_contact_nodes_remain_within_external_rails",
        rails_valid,
        f"rows={len(circuit_rows)} tolerance={rail_tolerance:.3e}",
    )
    min_power = min(float(row["total_resistor_power_w"]) for row in circuit_rows)
    add_check(
        checks,
        "resistor_power_is_nonnegative",
        min_power >= -1.0e-30,
        f"minimum={min_power:.6e} W",
    )

    transfer_monotonic = True
    maximum_transfer_drop = 0.0
    for case_id in required_cases:
        curve = sorted(
            [row for row in transfer_rows if row["case_id"] == case_id],
            key=lambda row: float(row["vtg_v"]),
        )
        currents = [
            abs(float(row["external_drain_current_a_per_cm"])) for row in curve
        ]
        transfer_monotonic = transfer_monotonic and all(
            right > left for left, right in zip(currents, currents[1:])
        )
        maximum_transfer_drop = max(
            maximum_transfer_drop,
            max(
                (left - right) / max(left, right, 1.0e-300)
                for left, right in zip(currents, currents[1:])
            ),
        )
    add_check(
        checks,
        "transfer_current_strictly_increases_with_top_gate",
        transfer_monotonic,
        f"maximum_relative_drop={maximum_transfer_drop:.6e}",
    )
    maximum_output_drop = 0.0
    for case_id in required_cases:
        for gate in (0.3, 0.5, 1.0):
            curve = sorted(
                [
                    row
                    for row in output_rows
                    if row["case_id"] == case_id
                    and same_value(float(row["vtg_v"]), gate)
                ],
                key=lambda row: float(row["external_vds_v"]),
            )
            currents = [
                abs(float(row["external_drain_current_a_per_cm"])) for row in curve
            ]
            maximum_output_drop = max(
                maximum_output_drop,
                max(
                    (left - right) / max(left, right, 1.0e-300)
                    for left, right in zip(currents, currents[1:])
                ),
            )
    add_check(
        checks,
        "output_current_is_nondecreasing_with_external_vds",
        maximum_output_drop
        <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"maximum_relative_drop={maximum_output_drop:.6e}",
    )

    selected_orderings: list[dict[str, Any]] = []
    ordering_valid = True
    for item in acceptance["required_current_ordering_biases"]["transfer"]:
        currents = [
            abs(
                float(
                    point_for(
                        transfer_rows,
                        case_id,
                        "transfer",
                        vtg_v=float(item["vtg_v"]),
                        vds_v=float(item["external_vds_v"]),
                    )["external_drain_current_terminal_a"]
                )
            )
            for case_id in required_cases
        ]
        passed = currents[0] > currents[1] > currents[2]
        ordering_valid = ordering_valid and passed
        selected_orderings.append({"kind": "transfer", "bias": item, "currents_a": currents, "passed": passed})
    for item in acceptance["required_current_ordering_biases"]["output"]:
        currents = [
            abs(
                float(
                    point_for(
                        output_rows,
                        case_id,
                        "output",
                        vtg_v=float(item["vtg_v"]),
                        vds_v=float(item["external_vds_v"]),
                    )["external_drain_current_terminal_a"]
                )
            )
            for case_id in required_cases
        ]
        passed = currents[0] > currents[1] > currents[2]
        ordering_valid = ordering_valid and passed
        selected_orderings.append({"kind": "output", "bias": item, "currents_a": currents, "passed": passed})
    add_check(
        checks,
        "selected_currents_strictly_decrease_with_pair_resistance",
        ordering_valid,
        json.dumps(selected_orderings, sort_keys=True),
    )
    resistance_widths = [
        float(row["linear_region_total_resistance_width_kohm_um"])
        for row in metrics
    ]
    add_check(
        checks,
        "linear_region_total_resistance_strictly_increases",
        resistance_widths[0] < resistance_widths[1] < resistance_widths[2],
        f"RtotalW={resistance_widths}",
    )
    high_reduction = float(metrics[-1]["transfer_high_gate_current_relative_reduction"])
    add_check(
        checks,
        "largest_pair_resistance_has_minimum_high_gate_response",
        high_reduction
        >= float(
            acceptance[
                "minimum_high_proxy_relative_current_reduction_at_largest_r_pair"
            ]
        ),
        f"relative_reduction={high_reduction:.6e}",
    )
    add_check(
        checks,
        "added_resistance_diagnostic_is_reported_but_not_gating",
        len(metrics) == 3
        and all("added_resistance_relative_difference" in row for row in metrics)
        and not bool(
            config["diagnostic_hypotheses"][
                "extracted_added_resistance_matches_declared_pair"
            ]["completion_gate"]
        ),
        json.dumps(
            {
                row["case_id"]: row["added_resistance_relative_difference"]
                for row in metrics
            },
            sort_keys=True,
        ),
    )
    add_check(
        checks,
        "ideal_control_reproduces_t02_c_transfer",
        int(reference_summary["point_count"]) == 31
        and float(reference_summary["maximum_current_relative_difference"])
        <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and float(reference_summary["maximum_center_potential_difference_v"])
        <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and float(reference_summary["maximum_center_density_relative_difference"])
        <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"]),
        json.dumps(reference_summary, sort_keys=True),
    )
    vtk_count = sum(int(entry["vtk_file_count"]) for entry in state_entries)
    states_valid = (
        len(state_entries) == int(acceptance["required_state_count"])
        and vtk_count == int(acceptance["required_vtk_file_count"])
        and all(
            int(entry["node_row_count"]) > 0
            and int(entry["channel_element_count"]) > 0
            and (ROOT / entry["node_csv"]).is_file()
            and (ROOT / entry["element_csv"]).is_file()
            for entry in state_entries
        )
    )
    add_check(
        checks,
        "three_complete_state_fields_written",
        states_valid,
        f"states={len(state_entries)} vtk={vtk_count}",
    )
    add_check(
        checks,
        "two_report_figures_written",
        all(value is not None for value in figure_hashes),
        f"sensitivity={figure_hashes[0]} states={figure_hashes[1]}",
    )
    wall_seconds = float(solver_log["wall_seconds"])
    run_bytes = directory_size(run_dir)
    add_check(
        checks,
        "laptop_resource_budget_met",
        wall_seconds <= float(config["resource_budget"]["maximum_wall_seconds"])
        and run_bytes <= int(config["resource_budget"]["maximum_run_directory_bytes"]),
        f"wall_seconds={wall_seconds:.6f} run_bytes={run_bytes}",
    )
    prohibited = config["evidence_boundary"]["prohibited_claims"]
    add_check(
        checks,
        "evidence_boundary_remains_numerical_and_partial",
        "controlled contact-series-resistance numerical sensitivity"
        in config["evidence_boundary"]["future_run_allowed_claim"]
        and any("TLM-extracted" in item for item in prohibited)
        and any("complete T03" in item for item in prohibited),
        config["evidence_boundary"]["future_run_allowed_claim"],
    )
    failures = [name for name, item in checks.items() if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "summary_metrics": {
            "device_count": len(runs),
            "circuit_coupled_device_count": circuit_count,
            "dc_solve_count": len(records),
            "transfer_point_count": len(transfer_rows),
            "output_point_count": len(output_rows),
            "reported_point_count": len(all_rows),
            "circuit_closure_point_count": len(closure_rows),
            "state_count": len(state_entries),
            "vtk_file_count": vtk_count,
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_circuit_kcl_relative_residual": max_kcl,
            "maximum_circuit_ohms_law_relative_residual": max_ohm,
            "maximum_circuit_voltage_partition_absolute_residual_v": max_partition,
            "minimum_resolved_positive_current_a_per_cm": minimum_resolved,
            "maximum_zero_external_vds_absolute_current_a_per_cm": max_zero,
            "maximum_output_monotonic_relative_drop": maximum_output_drop,
            "largest_pair_high_gate_current_relative_reduction": high_reduction,
            "linear_region_total_resistance_width_kohm_um": resistance_widths,
            "wall_seconds": wall_seconds,
            "run_directory_bytes": run_bytes,
        },
        "selected_current_orderings": selected_orderings,
    }


def archive_failed_run(
    config: dict[str, Any],
    run_dir: Path,
    paths: dict[str, Path],
    report: dict[str, Any],
) -> dict[str, Any]:
    failure_name = report["failures"][0] if report.get("failures") else "runner_exception"
    slug = re.sub(r"[^a-z0-9]+", "_", str(failure_name).lower()).strip("_")
    archive_dir = ROOT / config["failure_retention"][
        "failure_archive_directory_template"
    ].replace("<failure_slug>", slug)
    archive_report = ROOT / "results" / "reports" / f"tcad_t03_p3_contact_resistance_{slug}.json"
    if archive_dir.exists() or archive_report.exists():
        raise RuntimeError(
            f"refusing to overwrite existing P3 failed evidence: {archive_dir}"
        )
    shutil.copytree(run_dir, archive_dir)
    external_dir = archive_dir / "external_artifacts"
    external_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    candidates = {
        **paths,
        "runner_script": Path(__file__).resolve(),
        "formal_config": CONFIG_PATH,
    }
    for name, path in candidates.items():
        if name in {"contract_report", "check_report"} or not path.is_file():
            continue
        try:
            path.relative_to(run_dir)
        except ValueError:
            pass
        else:
            continue
        destination = external_dir / path.name
        shutil.copy2(path, destination)
        copied.append(
            {
                "name": name,
                "source": str(path.relative_to(ROOT)),
                "archive": str(destination.relative_to(ROOT)),
                "sha256": core.sha256(destination),
            }
        )
    archive_info = {
        "directory": str(archive_dir.relative_to(ROOT)),
        "report": str(archive_report.relative_to(ROOT)),
        "failed_gate": failure_name,
        "copied_external_artifacts": copied,
    }
    core.write_json(
        archive_dir / "failure_archive_manifest.json",
        {"status": "FAIL_PRESERVED", **archive_info},
    )
    report["failure_archive"] = archive_info
    core.write_json(paths["report"], report)
    core.write_json(archive_report, report)
    return archive_info


def input_paths(
    config: dict[str, Any], contract_path: Path
) -> dict[str, Path]:
    paths = {
        "p3_config": CONFIG_PATH,
        "p3_contract_report": contract_path,
        "runner_script": Path(__file__).resolve(),
    }
    mutable_machine_state = {"project_config", "experiments_config"}
    for name, value in config["dependencies"].items():
        if not isinstance(value, str):
            continue
        candidate = ROOT / value
        if candidate.is_file() and name not in mutable_machine_state:
            paths[name] = candidate
    return paths


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P3 input contract is not PASS")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("T03-P3 contract report does not match the current config")

    paths = {
        name: ROOT / value
        for name, value in outputs.items()
        if name != "run_directory"
    }
    run_dir = ROOT / outputs["run_directory"]
    if paths["report"].exists() or (run_dir.exists() and any(run_dir.iterdir())):
        raise RuntimeError(
            "refusing to overwrite an existing formal P3 run or report"
        )
    run_dir.mkdir(parents=True, exist_ok=True)

    dependencies = config["dependencies"]
    baseline_path = ROOT / dependencies["t01_baseline_config"]
    mesh_path = ROOT / dependencies["t01_mesh_config"]
    t02_a_path = ROOT / dependencies["t02_a_config"]
    t02_report_path = ROOT / dependencies["t02_c_report"]
    t02_check_path = ROOT / dependencies["t02_c_check_report"]
    baseline = load_json(baseline_path)
    mesh_config = load_json(mesh_path)
    t02_a_config = load_json(t02_a_path)
    t02_report = load_json(t02_report_path)
    t02_check = load_json(t02_check_path)
    if t02_report.get("status") != dependencies["required_t02_c_status"]:
        raise RuntimeError("T02-C runner dependency is not PASS")
    if t02_check.get("status") != dependencies["required_t02_c_check_status"]:
        raise RuntimeError("T02-C independent check dependency is not PASS")

    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "python_executable": sys.executable,
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "circuit_api": {
            "internal_nodes": [SOURCE_INTERNAL_NODE, DRAIN_INTERNAL_NODE],
            "external_nodes": [SOURCE_EXTERNAL_NODE, DRAIN_EXTERNAL_NODE],
            "voltage_elements": [SOURCE_VOLTAGE_ELEMENT, DRAIN_VOLTAGE_ELEMENT],
            "resistor_elements": [SOURCE_RESISTOR_ELEMENT, DRAIN_RESISTOR_ELEMENT],
            "terminal_current_scaling": (
                "2D contact edge current multiplied by frozen device width before "
                "integration into the external circuit"
            ),
        },
        "contract_recorded_machine_state": {
            name: contract["inputs"][name]
            for name in ("project_config", "experiments_config")
        },
        "inputs": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": core.sha256(path),
            }
            for name, path in input_paths(config, contract_path).items()
        },
    }
    core.write_json(paths["config_snapshot"], snapshot)
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "python_executable": sys.executable,
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "reproduction_command": "make t03-p3-contact-sensitivity",
        "validation_command": "make t03-p3-contact-sensitivity-check",
        "runs": [],
        "solver_records": [],
        "errors": [],
        "current_device": None,
    }
    core.write_json(paths["solver_log"], solver_log)

    transfer_rows: list[dict[str, Any]] = []
    output_rows: list[dict[str, Any]] = []
    metrics: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    reference_summary: dict[str, Any] = {}
    state_entries: list[dict[str, Any]] = []
    sensitivity_hash: str | None = None
    state_hash: str | None = None
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    try:
        for case in config["sensitivity"]["cases"]:
            summary = run_transfer_device(
                baseline,
                mesh_config,
                t02_a_config,
                config,
                case,
                transfer_rows,
                solver_log,
                paths["solver_log"],
            )
            persist_partial(
                config,
                paths,
                transfer_rows,
                output_rows,
                metrics,
                reference_rows,
                state_entries,
            )
            print(
                f"T03_P3_TRANSFER_DEVICE_PASS case={case['case_id']} "
                f"points={summary['reported_point_count']} solves={summary['dc_solve_count']}"
            )
            for target_vtg_v in [
                float(value)
                for value in config["bias_protocol"]["output"]["top_gate_values_v"]
            ]:
                summary = run_output_device(
                    baseline,
                    mesh_config,
                    t02_a_config,
                    config,
                    case,
                    target_vtg_v,
                    output_rows,
                    state_entries,
                    run_dir,
                    solver_log,
                    paths["solver_log"],
                )
                persist_partial(
                    config,
                    paths,
                    transfer_rows,
                    output_rows,
                    metrics,
                    reference_rows,
                    state_entries,
                )
                print(
                    f"T03_P3_OUTPUT_DEVICE_PASS case={case['case_id']} "
                    f"vtg={target_vtg_v:g} points={summary['reported_point_count']} "
                    f"solves={summary['dc_solve_count']}"
                )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        clear_circuit()

    if caught_error is None:
        try:
            metrics = build_metrics(config, [*transfer_rows, *output_rows])
            reference_rows, reference_summary = build_reference_comparison(
                transfer_rows, t02_report
            )
            sensitivity_hash = render_sensitivity_figure(
                config,
                transfer_rows,
                output_rows,
                metrics,
                paths["sensitivity_figure_png"],
            )
            state_hash = render_state_figure(
                state_entries, paths["state_figure_png"]
            )
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    if caught_error is None:
        solver_log["current_device"] = None
    solver_log["wall_seconds"] = time.perf_counter() - wall_start
    core.write_json(paths["solver_log"], solver_log)
    persist_partial(
        config,
        paths,
        transfer_rows,
        output_rows,
        metrics,
        reference_rows,
        state_entries,
    )
    assessment = assess(
        config,
        contract,
        transfer_rows,
        output_rows,
        metrics,
        reference_summary,
        state_entries,
        solver_log,
        (sensitivity_hash, state_hash),
        run_dir,
        caught_error,
    )
    artifact_keys = (
        "config_snapshot",
        "solver_log",
        "state_manifest",
        "transfer_csv",
        "output_csv",
        "metric_csv",
        "circuit_balance_csv",
        "reference_comparison_csv",
        "state_summary_csv",
    )
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if assessment["status"] == "PASS" else "E0",
        "model_scope": config["scope"],
        "input_snapshot": str(paths["config_snapshot"].relative_to(ROOT)),
        "contact_model_contract": config["contact_model_contract"],
        "sensitivity_cases": config["sensitivity"]["cases"],
        "device_summaries": solver_log["runs"],
        "transfer_points": transfer_rows,
        "output_points": output_rows,
        "metrics": metrics,
        "t02_c_ideal_transfer_reproduction": reference_summary,
        "diagnostic_hypotheses": {
            "extracted_added_resistance_matches_declared_pair": {
                "completion_gate": False,
                "rows": [
                    {
                        "case_id": row["case_id"],
                        "declared_pair_resistance_width_kohm_um": row[
                            "declared_pair_resistance_width_kohm_um"
                        ],
                        "added_total_resistance_width_kohm_um": row[
                            "added_total_resistance_width_kohm_um"
                        ],
                        "relative_difference": row[
                            "added_resistance_relative_difference"
                        ],
                        "within_15_percent": row[
                            "added_resistance_diagnostic_within_15_percent"
                        ],
                    }
                    for row in metrics
                ],
            }
        },
        "state_outputs": [public_state(entry) for entry in state_entries],
        "figures": [
            {
                "path": str(paths["sensitivity_figure_png"].relative_to(ROOT)),
                "sha256": sensitivity_hash,
            },
            {
                "path": str(paths["state_figure_png"].relative_to(ROOT)),
                "sha256": state_hash,
            },
        ]
        if sensitivity_hash is not None and state_hash is not None
        else [],
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": assessment["summary_metrics"],
        "selected_current_orderings": assessment.get(
            "selected_current_orderings", []
        ),
        "artifacts": {
            key: {
                "path": str(paths[key].relative_to(ROOT)),
                "sha256": core.sha256(paths[key]),
            }
            for key in artifact_keys
        },
        "reproduction": {
            "contract_command": "make t03-p3-contact-contract-check",
            "command": "make t03-p3-contact-sensitivity",
            "validation_command": "make t03-p3-contact-sensitivity-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "formal_sensitivity_run": assessment["status"] == "PASS",
        "independent_persisted_evidence_check_complete": False,
        "t03_p3_completion": {
            "status": "PARTIAL" if assessment["status"] == "PASS" else "BLOCKED",
            "input_contract_passed": True,
            "formal_runner_passed": assessment["status"] == "PASS",
            "independent_check_passed": False,
            "complete_p3_contact_group": False,
            "complete_t03_five_group_sensitivity": False,
            "p5_or_downstream_permitted_next": False,
            "experimental_calibration_permitted": False,
        },
        "limitations": [
            "The two nonzero resistance-width values are E1 literature magnitude anchors mapped to a project-defined symmetric total-pair teaching proxy; they are not project TLM measurements or fitted parameters.",
            "The external resistors are self-consistently coupled to the frozen 2D electron-only drift-diffusion device, but the contact region, barrier, injection, current crowding and contact metal are not spatially or physically modeled.",
            "All current and resistance quantities are numerical proxies from an uncalibrated quasi-static teaching model, not physical Ion, mobility, contact resistance or experimental accuracy.",
            "Runner PASS alone is E2; P3 remains incomplete until the independent persisted-evidence checker passes at E3.",
            "P5, complete T03, compact models, SPICE, circuit cells, layout, PEX and HZO remain closed.",
        ],
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(paths["report"], report)
    if report["status"] == "FAIL":
        archive_failed_run(config, run_dir, paths, report)
    print(
        f"T03_P3_CONTACT_RESISTANCE_{report['status']} "
        f"devices={assessment['summary_metrics']['device_count']} "
        f"dc={assessment['summary_metrics']['dc_solve_count']} "
        f"points={assessment['summary_metrics']['reported_point_count']} "
        f"wall={solver_log['wall_seconds']:.3f}s report={paths['report']}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P3_CONTACT_RESISTANCE_ERROR {failure}: "
            f"{report['checks'][failure]['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
