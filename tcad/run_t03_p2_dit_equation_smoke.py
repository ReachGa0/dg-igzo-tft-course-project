#!/usr/bin/env python3
"""Run the T03-P2-DIT zero-limit and interface-equation smoke cases."""

from __future__ import annotations

import argparse
import copy
import csv
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402


core = t02_a.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_interface_trap.json"
INTERFACE = "bottom_oxide_channel"
ELEMENTARY_CHARGE_C = 1.602176634e-19

CASE_FIELDNAMES = [
    "case_id", "solve_mode", "interface_equation_active", "dit_cm2_ev",
    "interface_trap_capacitance_f_per_cm2", "source_v", "drain_v", "vbg_v",
    "vtg_v", "mesh_level", "node_count_with_interface_duplicates", "element_count",
    "dc_solve_count", "all_dc_solves_converged", "source_current_a_per_cm",
    "drain_current_a_per_cm", "relative_current_imbalance",
    "center_channel_potential_v", "center_channel_electron_density_cm3",
    "maximum_interface_potential_discontinuity_v", "center_interface_x_cm",
    "center_interface_potential_r0_v", "center_interface_potential_r1_v",
    "center_devsim_fluxterm_c_per_cm2", "center_physical_qit_c_per_cm2",
    "center_d_oxide_y_c_per_cm2", "center_d_channel_y_c_per_cm2",
    "center_displacement_jump_c_per_cm2", "center_gauss_absolute_error_c_per_cm2",
    "center_gauss_relative_error", "wall_seconds",
]

INTERFACE_FIELDNAMES = [
    "case_id", "solve_mode", "interface_equation_active", "dit_cm2_ev",
    "x_cm", "y_cm", "x_um", "y_nm", "potential_r0_v", "potential_r1_v",
    "potential_difference_v", "devsim_fluxterm_c_per_cm2",
    "physical_qit_c_per_cm2", "formula_fluxterm_c_per_cm2",
]

STATE_FIELDNAMES = [
    "case_id", "solve_mode", "interface_equation_active", "dit_cm2_ev",
    "source_v", "drain_v", "vbg_v", "vtg_v", "region", "x_cm", "y_cm",
    "x_um", "y_nm", "potential_v", "electron_density_cm3",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def same_value(left: float, right: float, *, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), 1e-300)


def add_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def build_runtime(
    baseline: dict[str, Any], mesh_config: dict[str, Any], t02_config: dict[str, Any], mesh_level: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime, mesh_spec = t02_a.mesh_stage.build_runtime_baseline(
        baseline, mesh_config, mesh_level
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = float(
        t02_config["top_stack_contract"]["enabled_mode"]["top_oxide_thickness_cm"]
    )
    return runtime, mesh_spec


def install_interface_models(
    device: str, *, equation_active: bool, dit_cm2_ev: float, neutral_potential_v: float
) -> None:
    for name, equation in (
        ("InterfaceXCoordinate", "x@r0"),
        ("InterfaceYCoordinate", "y@r0"),
        ("InterfacePotentialR0", "Potential@r0"),
        ("InterfacePotentialR1", "Potential@r1"),
    ):
        core.devsim.interface_model(
            device=device, interface=INTERFACE, name=name, equation=equation
        )

    core.devsim.set_parameter(
        device=device, name="InterfaceTrapDensity", value=float(dit_cm2_ev)
    )
    core.devsim.set_parameter(
        device=device,
        name="InterfaceTrapNeutralPotential",
        value=float(neutral_potential_v),
    )
    core.devsim.set_parameter(
        device=device, name="InterfaceTrapElementaryCharge", value=ELEMENTARY_CHARGE_C
    )
    if equation_active:
        flux = (
            "InterfaceTrapElementaryCharge*InterfaceTrapDensity*"
            "(Potential@r1-InterfaceTrapNeutralPotential)"
        )
        models = (
            ("InterfaceTrapFluxTerm", flux),
            ("InterfaceTrapFluxTerm:Potential@r0", "0"),
            (
                "InterfaceTrapFluxTerm:Potential@r1",
                "InterfaceTrapElementaryCharge*InterfaceTrapDensity",
            ),
        )
        for name, equation in models:
            core.devsim.interface_model(
                device=device, interface=INTERFACE, name=name, equation=equation
            )
        core.devsim.interface_equation(
            device=device,
            interface=INTERFACE,
            name="InterfaceTrapChargeEquation",
            name0="PotentialEquation",
            name1="PotentialEquation",
            interface_model="InterfaceTrapFluxTerm",
            type="fluxterm",
        )
    else:
        core.devsim.interface_model(
            device=device,
            interface=INTERFACE,
            name="InterfaceTrapFluxTerm",
            # DEVSIM may still optimize this algebraic zero to an empty model;
            # the zero-D_it reader maps that documented limit to exact zeros.
            equation="0*Potential@r1",
        )


def collect_state_nodes(
    device: str,
    case: dict[str, Any],
    solve_mode: str,
    bias: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in t02_a.ENABLED_REGIONS:
        xs = core.devsim.get_node_model_values(device=device, region=region, name="x")
        ys = core.devsim.get_node_model_values(device=device, region=region, name="y")
        potentials = core.devsim.get_node_model_values(
            device=device, region=region, name="Potential"
        )
        electrons = (
            core.devsim.get_node_model_values(
                device=device, region=region, name="Electrons"
            )
            if region == "channel"
            else [None] * len(xs)
        )
        for x, y, potential, electron in zip(xs, ys, potentials, electrons, strict=True):
            rows.append(
                {
                    "case_id": case["case_id"],
                    "solve_mode": solve_mode,
                    "interface_equation_active": bool(case["interface_equation_active"]),
                    "dit_cm2_ev": float(case["dit_cm2_ev"]),
                    "source_v": float(bias["source_v"]),
                    "drain_v": float(bias["drain_v"]),
                    "vbg_v": float(bias["bottom_gate_v"]),
                    "vtg_v": float(bias["top_gate_v"]),
                    "region": region,
                    "x_cm": float(x),
                    "y_cm": float(y),
                    "x_um": float(x) * 1e4,
                    "y_nm": float(y) * 1e7,
                    "potential_v": float(potential),
                    "electron_density_cm3": "" if electron is None else float(electron),
                }
            )
    return rows


def collect_interface_samples(
    device: str, case: dict[str, Any], solve_mode: str, neutral_potential_v: float
) -> list[dict[str, Any]]:
    base_names = (
        "InterfaceXCoordinate",
        "InterfaceYCoordinate",
        "InterfacePotentialR0",
        "InterfacePotentialR1",
        "continuousPotential",
    )
    values = {
        name: core.devsim.get_interface_model_values(
            device=device, interface=INTERFACE, name=name
        )
        for name in base_names
    }
    length = len(values["InterfaceXCoordinate"])
    dit = float(case["dit_cm2_ev"])
    try:
        fluxterm = core.devsim.get_interface_model_values(
            device=device, interface=INTERFACE, name="InterfaceTrapFluxTerm"
        )
    except core.devsim.error:
        if dit != 0.0:
            raise
        fluxterm = [0.0] * length
    if len(fluxterm) != length:
        if dit != 0.0:
            raise RuntimeError(
                "T03-P2-DIT nonzero InterfaceTrapFluxTerm diagnostic has "
                f"{len(fluxterm)} values; expected {length}"
            )
        fluxterm = [0.0] * length
    values["InterfaceTrapFluxTerm"] = fluxterm
    values["InterfaceTrapPhysicalSheetCharge"] = [-float(value) for value in fluxterm]
    if any(len(item) != length for item in values.values()):
        raise RuntimeError("T03-P2-DIT interface diagnostics have inconsistent lengths")
    rows: list[dict[str, Any]] = []
    for index in range(length):
        x = float(values["InterfaceXCoordinate"][index])
        y = float(values["InterfaceYCoordinate"][index])
        p0 = float(values["InterfacePotentialR0"][index])
        p1 = float(values["InterfacePotentialR1"][index])
        flux = float(values["InterfaceTrapFluxTerm"][index])
        physical = float(values["InterfaceTrapPhysicalSheetCharge"][index])
        rows.append(
            {
                "case_id": case["case_id"],
                "solve_mode": solve_mode,
                "interface_equation_active": bool(case["interface_equation_active"]),
                "dit_cm2_ev": dit,
                "x_cm": x,
                "y_cm": y,
                "x_um": x * 1e4,
                "y_nm": y * 1e7,
                "potential_r0_v": p0,
                "potential_r1_v": p1,
                "potential_difference_v": float(values["continuousPotential"][index]),
                "devsim_fluxterm_c_per_cm2": flux,
                "physical_qit_c_per_cm2": physical,
                "formula_fluxterm_c_per_cm2": (
                    ELEMENTARY_CHARGE_C * dit * (p1 - neutral_potential_v)
                    if bool(case["interface_equation_active"])
                    else 0.0
                ),
            }
        )
    return rows


def center_channel_state(state_rows: list[dict[str, Any]], runtime: dict[str, Any]) -> dict[str, float]:
    target_x = float(runtime["geometry"]["channel_length_cm"]) / 2.0
    target_y = float(runtime["geometry"]["bottom_oxide_thickness_cm"]) + float(
        runtime["geometry"]["channel_thickness_cm"]
    ) / 2.0
    row = min(
        (item for item in state_rows if item["region"] == "channel"),
        key=lambda item: (float(item["x_cm"]) - target_x) ** 2
        + (float(item["y_cm"]) - target_y) ** 2,
    )
    return {
        "potential_v": float(row["potential_v"]),
        "electron_density_cm3": float(row["electron_density_cm3"]),
    }


def center_interface_diagnostics(
    state_rows: list[dict[str, Any]],
    interface_rows: list[dict[str, Any]],
    runtime: dict[str, Any],
) -> dict[str, float]:
    target_x = float(runtime["geometry"]["channel_length_cm"]) / 2.0
    interface_y = float(runtime["geometry"]["bottom_oxide_thickness_cm"])
    x_tolerance = 1e-14
    oxide = sorted(
        (
            (float(row["y_cm"]), float(row["potential_v"]))
            for row in state_rows
            if row["region"] == "bottom_oxide"
            and abs(float(row["x_cm"]) - target_x) <= x_tolerance
        ),
        key=lambda item: item[0],
    )
    channel = sorted(
        (
            (float(row["y_cm"]), float(row["potential_v"]))
            for row in state_rows
            if row["region"] == "channel"
            and abs(float(row["x_cm"]) - target_x) <= x_tolerance
        ),
        key=lambda item: item[0],
    )
    oxide_interface = max((item for item in oxide if item[0] <= interface_y + 1e-15), key=lambda item: item[0])
    oxide_below = max((item for item in oxide if item[0] < interface_y - 1e-15), key=lambda item: item[0])
    channel_interface = min((item for item in channel if item[0] >= interface_y - 1e-15), key=lambda item: item[0])
    channel_above = min((item for item in channel if item[0] > interface_y + 1e-15), key=lambda item: item[0])
    epsilon_oxide = core.EPSILON_0_F_PER_CM * float(
        runtime["materials"]["bottom_oxide"]["relative_permittivity"]
    )
    epsilon_channel = core.EPSILON_0_F_PER_CM * float(
        runtime["materials"]["channel"]["relative_permittivity"]
    )
    e_oxide = -(
        oxide_interface[1] - oxide_below[1]
    ) / (oxide_interface[0] - oxide_below[0])
    e_channel = -(
        channel_above[1] - channel_interface[1]
    ) / (channel_above[0] - channel_interface[0])
    d_oxide = epsilon_oxide * e_oxide
    d_channel = epsilon_channel * e_channel
    center_interface = min(
        interface_rows, key=lambda row: abs(float(row["x_cm"]) - target_x)
    )
    physical_qit = float(center_interface["physical_qit_c_per_cm2"])
    jump = d_channel - d_oxide
    absolute_error = abs(jump - physical_qit)
    return {
        "center_interface_x_cm": float(center_interface["x_cm"]),
        "center_interface_potential_r0_v": float(center_interface["potential_r0_v"]),
        "center_interface_potential_r1_v": float(center_interface["potential_r1_v"]),
        "center_devsim_fluxterm_c_per_cm2": float(center_interface["devsim_fluxterm_c_per_cm2"]),
        "center_physical_qit_c_per_cm2": physical_qit,
        "center_d_oxide_y_c_per_cm2": d_oxide,
        "center_d_channel_y_c_per_cm2": d_channel,
        "center_displacement_jump_c_per_cm2": jump,
        "center_gauss_absolute_error_c_per_cm2": absolute_error,
        "center_gauss_relative_error": absolute_error / max(abs(physical_qit), 1e-300),
    }


def final_case_summary(
    device: str,
    case: dict[str, Any],
    solve_mode: str,
    bias: dict[str, float],
    runtime: dict[str, Any],
    records: list[dict[str, Any]],
    state_rows: list[dict[str, Any]],
    interface_rows: list[dict[str, Any]],
    wall_seconds: float,
) -> dict[str, Any]:
    regions, contacts, interfaces = t02_a.active_topology(device, t02_a.ENABLED_REGIONS)
    node_count, element_count = t02_a.active_counts(device, t02_a.ENABLED_REGIONS)
    if regions != sorted(t02_a.ENABLED_REGIONS):
        raise RuntimeError(f"unexpected T03-P2-DIT regions: {regions}")
    center = center_channel_state(state_rows, runtime)
    interface_center = center_interface_diagnostics(state_rows, interface_rows, runtime)
    coupled = solve_mode == "coupled"
    if coupled:
        source_current = float(
            core.devsim.get_contact_current(
                device=device, contact="source", equation="ElectronContinuityEquation"
            )
        )
        drain_current = float(
            core.devsim.get_contact_current(
                device=device, contact="drain", equation="ElectronContinuityEquation"
            )
        )
        imbalance = abs(source_current + drain_current) / max(
            abs(source_current), abs(drain_current), 1e-300
        )
    else:
        source_current = ""
        drain_current = ""
        imbalance = ""
    return {
        "case_id": case["case_id"],
        "solve_mode": solve_mode,
        "interface_equation_active": bool(case["interface_equation_active"]),
        "dit_cm2_ev": float(case["dit_cm2_ev"]),
        "interface_trap_capacitance_f_per_cm2": ELEMENTARY_CHARGE_C
        * float(case["dit_cm2_ev"]),
        "source_v": float(bias["source_v"]),
        "drain_v": float(bias["drain_v"]),
        "vbg_v": float(bias["bottom_gate_v"]),
        "vtg_v": float(bias["top_gate_v"]),
        "mesh_level": "interface_4x",
        "node_count_with_interface_duplicates": node_count,
        "element_count": element_count,
        "dc_solve_count": len(records),
        "all_dc_solves_converged": all(bool(record["converged"]) for record in records),
        "source_current_a_per_cm": source_current,
        "drain_current_a_per_cm": drain_current,
        "relative_current_imbalance": imbalance,
        "center_channel_potential_v": center["potential_v"],
        "center_channel_electron_density_cm3": center["electron_density_cm3"],
        "maximum_interface_potential_discontinuity_v": max(
            abs(float(row["potential_difference_v"])) for row in interface_rows
        ),
        **interface_center,
        "wall_seconds": wall_seconds,
        "topology": {"regions": regions, "contacts": contacts, "interfaces": interfaces},
        "bottom_interface_equations": sorted(
            core.devsim.get_interface_equation_list(device=device, interface=INTERFACE)
        ),
        "top_interface_equations": sorted(
            core.devsim.get_interface_equation_list(
                device=device, interface="channel_top_oxide"
            )
        ),
        "interface_trap_equation_command": (
            core.devsim.get_interface_equation_command(
                device=device, interface=INTERFACE, name="InterfaceTrapChargeEquation"
            )
            if bool(case["interface_equation_active"])
            else None
        ),
    }


def run_electrostatic_case(
    case: dict[str, Any],
    bias: dict[str, float],
    neutral_potential_v: float,
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    runtime, mesh_spec = build_runtime(baseline, mesh_config, t02_config, "interface_4x")
    device = f"t03_p2_{case['case_id']}"
    records: list[dict[str, Any]] = []
    start = time.perf_counter()
    try:
        t02_a.initialize_enabled_device(device, runtime, t02_config, "interface_4x", mesh_spec)
        install_interface_models(
            device,
            equation_active=bool(case["interface_equation_active"]),
            dit_cm2_ev=float(case["dit_cm2_ev"]),
            neutral_potential_v=neutral_potential_v,
        )
        t02_a.set_enabled_biases(
            device,
            source_v=float(bias["source_v"]),
            drain_v=float(bias["drain_v"]),
            bottom_gate_v=float(bias["bottom_gate_v"]),
            top_gate_v=float(bias["top_gate_v"]),
        )
        records.append(
            core.solve_dc(device, runtime, f"{case['case_id']}_POISSON", coupled=False)
        )
        states = collect_state_nodes(device, case, "electrostatic", bias)
        samples = collect_interface_samples(
            device, case, "electrostatic", neutral_potential_v
        )
        summary = final_case_summary(
            device,
            case,
            "electrostatic",
            bias,
            runtime,
            records,
            states,
            samples,
            time.perf_counter() - start,
        )
        return summary, records, states, samples
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def run_coupled_case(
    case: dict[str, Any],
    protocol: dict[str, Any],
    neutral_potential_v: float,
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    runtime, mesh_spec = build_runtime(baseline, mesh_config, t02_config, "interface_4x")
    device = f"t03_p2_{case['case_id']}"
    records: list[dict[str, Any]] = []
    start = time.perf_counter()
    try:
        t02_a.initialize_enabled_device(device, runtime, t02_config, "interface_4x", mesh_spec)
        install_interface_models(
            device,
            equation_active=bool(case["interface_equation_active"]),
            dit_cm2_ev=float(case["dit_cm2_ev"]),
            neutral_potential_v=neutral_potential_v,
        )
        t02_a.set_enabled_biases(
            device, source_v=0.0, drain_v=0.0, bottom_gate_v=0.0, top_gate_v=0.0
        )
        records.append(
            core.solve_dc(device, runtime, f"{case['case_id']}_POISSON_ZERO", coupled=False)
        )
        core.create_transport(device, runtime)
        records.append(
            core.solve_dc(device, runtime, f"{case['case_id']}_COUPLED_ZERO", coupled=True)
        )
        for vds_v in (float(value) for value in protocol["low_vds_values_v"]):
            t02_a.set_enabled_biases(
                device,
                source_v=0.0,
                drain_v=vds_v,
                bottom_gate_v=0.0,
                top_gate_v=0.0,
            )
            records.append(
                core.solve_dc(
                    device,
                    runtime,
                    f"{case['case_id']}_VDS_{vds_v:.6g}",
                    coupled=True,
                )
            )
        drain_v = float(protocol["low_vds_values_v"][-1])
        for vtg_v in (float(value) for value in protocol["top_gate_values_v"]):
            t02_a.set_enabled_biases(
                device,
                source_v=0.0,
                drain_v=drain_v,
                bottom_gate_v=float(protocol["fixed_bottom_gate_v"]),
                top_gate_v=vtg_v,
            )
            records.append(
                core.solve_dc(
                    device,
                    runtime,
                    f"{case['case_id']}_VTG_{vtg_v:.6g}",
                    coupled=True,
                )
            )
        bias = {
            "source_v": 0.0,
            "drain_v": drain_v,
            "bottom_gate_v": float(protocol["fixed_bottom_gate_v"]),
            "top_gate_v": float(protocol["top_gate_values_v"][-1]),
        }
        states = collect_state_nodes(device, case, "coupled", bias)
        samples = collect_interface_samples(device, case, "coupled", neutral_potential_v)
        summary = final_case_summary(
            device,
            case,
            "coupled",
            bias,
            runtime,
            records,
            states,
            samples,
            time.perf_counter() - start,
        )
        return summary, records, states, samples
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def state_potential_map(rows: list[dict[str, Any]]) -> dict[tuple[str, float, float], float]:
    return {
        (str(row["region"]), round(float(row["x_cm"]), 18), round(float(row["y_cm"]), 18)): float(row["potential_v"])
        for row in rows
    }


def find_t02_reference(rows: list[dict[str, str]], spec: dict[str, Any]) -> dict[str, str]:
    return next(
        row
        for row in rows
        if row["family_id"] == spec["family_id"]
        and row["sweep_direction"] == spec["sweep_direction"]
        and same_value(row["fixed_secondary_gate_v"], spec["fixed_secondary_gate_v"])
        and same_value(row["primary_gate_v"], spec["primary_gate_v"])
        and same_value(row["vds_v"], spec["vds_v"])
    )


def assess(
    config: dict[str, Any],
    contract: dict[str, Any],
    case_summaries: list[dict[str, Any]],
    solver_runs: list[dict[str, Any]],
    states_by_case: dict[str, list[dict[str, Any]]],
    interface_rows: list[dict[str, Any]],
    t02_reference: dict[str, str],
    wall_seconds: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    acceptance = config["acceptance"]
    budget = config["resource_budget"]
    by_case = {row["case_id"]: row for row in case_summaries}
    checks: dict[str, dict[str, Any]] = {}
    add_check(
        checks,
        "contract_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("config", {}).get("sha256") == core.sha256(CONFIG_PATH),
        f"status={contract.get('contract_status')} hash={contract.get('config', {}).get('sha256')}",
    )
    all_records = [record for run in solver_runs for record in run["records"]]
    add_check(
        checks,
        "five_cases_and_17_dc_solves_completed",
        [row["case_id"] for row in case_summaries] == acceptance["required_case_ids"]
        and len(case_summaries) == budget["required_device_count"]
        and len(all_records) == budget["required_total_dc_solve_count"]
        and [row["dc_solve_count"] for row in case_summaries] == [1, 1, 1, 7, 7],
        f"cases={[row['case_id'] for row in case_summaries]} solves={len(all_records)}",
    )
    add_check(
        checks,
        "all_dc_solves_converged_within_laptop_budget",
        all(bool(record["converged"]) for record in all_records)
        and wall_seconds <= float(budget["maximum_wall_seconds"]),
        f"converged={sum(bool(record['converged']) for record in all_records)}/{len(all_records)} wall={wall_seconds:.6f}s",
    )
    topology_valid = all(
        row["topology"]["regions"] == sorted(acceptance["required_regions"])
        and row["topology"]["contacts"] == sorted(acceptance["required_contacts"])
        and row["topology"]["interfaces"] == sorted(acceptance["required_interfaces"])
        and row["node_count_with_interface_duplicates"] == 2419
        and row["element_count"] == 4480
        for row in case_summaries
    )
    equation_valid = all(
        row["bottom_interface_equations"]
        == (
            sorted(acceptance["required_active_interface_equations"])
            if row["interface_equation_active"]
            else acceptance["required_inactive_interface_equations"]
        )
        and row["top_interface_equations"] == acceptance["required_inactive_interface_equations"]
        for row in case_summaries
    )
    add_check(
        checks,
        "topology_and_interface_equation_lists_match_contract",
        topology_valid and equation_valid,
        f"topology={topology_valid} equations={[(row['case_id'], row['bottom_interface_equations']) for row in case_summaries]}",
    )

    reference_map = state_potential_map(states_by_case["electrostatic_reference_no_equation"])
    zero_map = state_potential_map(states_by_case["electrostatic_zero_dit_equation"])
    max_zero_difference = max(abs(reference_map[key] - zero_map[key]) for key in reference_map)
    add_check(
        checks,
        "zero_dit_equation_is_exact_electrostatic_limit",
        reference_map.keys() == zero_map.keys()
        and max_zero_difference
        <= float(acceptance["maximum_zero_dit_electrostatic_potential_difference_v"]),
        f"maximum_node_potential_difference={max_zero_difference:.6e} V",
    )
    max_continuity = max(
        float(row["maximum_interface_potential_discontinuity_v"])
        for row in case_summaries
    )
    add_check(
        checks,
        "interface_potential_continuity_retained",
        max_continuity
        <= float(acceptance["maximum_interface_potential_discontinuity_v"]),
        f"maximum_discontinuity={max_continuity:.6e} V",
    )
    formula_error = max(
        abs(
            float(row["devsim_fluxterm_c_per_cm2"])
            - float(row["formula_fluxterm_c_per_cm2"])
        )
        for row in interface_rows
    )
    sign_error = max(
        abs(
            float(row["physical_qit_c_per_cm2"])
            + float(row["devsim_fluxterm_c_per_cm2"])
        )
        for row in interface_rows
    )
    add_check(
        checks,
        "interface_flux_formula_and_physical_charge_sign_match",
        formula_error <= 1e-20 and sign_error <= 1e-20,
        f"formula_error={formula_error:.6e} sign_error={sign_error:.6e} C/cm2",
    )
    representative_es = by_case["electrostatic_representative_dit_equation"]
    add_check(
        checks,
        "center_gauss_jump_matches_physical_sheet_charge",
        float(representative_es["center_gauss_relative_error"])
        <= float(acceptance["maximum_center_gauss_relative_error"]),
        (
            f"jump={representative_es['center_displacement_jump_c_per_cm2']:.6e} "
            f"Qit={representative_es['center_physical_qit_c_per_cm2']:.6e} "
            f"relative_error={representative_es['center_gauss_relative_error']:.6e}"
        ),
    )
    reference_es = by_case["electrostatic_reference_no_equation"]
    potential_change = abs(
        float(representative_es["center_channel_potential_v"])
        - float(reference_es["center_channel_potential_v"])
    )
    add_check(
        checks,
        "representative_dit_creates_negative_sheet_charge_and_nonzero_response",
        float(representative_es["center_physical_qit_c_per_cm2"]) < 0.0
        and abs(float(representative_es["center_physical_qit_c_per_cm2"]))
        >= float(acceptance["minimum_representative_sheet_charge_magnitude_c_per_cm2"])
        and potential_change
        >= float(acceptance["minimum_representative_electrostatic_potential_change_v"]),
        f"Qit={representative_es['center_physical_qit_c_per_cm2']:.6e} C/cm2 potential_change={potential_change:.6e} V",
    )
    coupled_rows = [row for row in case_summaries if row["solve_mode"] == "coupled"]
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in coupled_rows)
    add_check(
        checks,
        "coupled_smoke_converged_with_terminal_conservation",
        all(row["all_dc_solves_converged"] for row in coupled_rows)
        and max_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"maximum_relative_imbalance={max_imbalance:.6e}",
    )
    zero_coupled = by_case["coupled_zero_dit_equation"]
    t02_drain = abs(float(t02_reference["drain_current_a_per_cm"]))
    zero_drain = abs(float(zero_coupled["drain_current_a_per_cm"]))
    t02_differences = {
        "current_relative": relative_difference(zero_drain, t02_drain),
        "center_potential_v": abs(
            float(zero_coupled["center_channel_potential_v"])
            - float(t02_reference["center_channel_potential_v"])
        ),
        "center_density_relative": relative_difference(
            float(zero_coupled["center_channel_electron_density_cm3"]),
            float(t02_reference["center_channel_electron_density_cm3"]),
        ),
    }
    add_check(
        checks,
        "zero_dit_coupled_case_reproduces_t02_c_reference",
        t02_differences["current_relative"]
        <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and t02_differences["center_potential_v"]
        <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and t02_differences["center_density_relative"]
        <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"]),
        json.dumps(t02_differences, sort_keys=True),
    )
    representative_coupled = by_case["coupled_representative_dit_equation"]
    current_ratio = abs(float(representative_coupled["drain_current_a_per_cm"])) / max(
        zero_drain, 1e-300
    )
    add_check(
        checks,
        "representative_dit_reduces_fixed_bias_coupled_current",
        current_ratio < 1.0,
        f"representative_to_zero_current_ratio={current_ratio:.6e}",
    )
    expected_state_rows = budget["required_device_count"] * 2419
    add_check(
        checks,
        "raw_state_and_interface_evidence_counts_complete",
        sum(len(rows) for rows in states_by_case.values()) == expected_state_rows
        and len(interface_rows) == budget["required_device_count"] * 39,
        f"state_rows={sum(len(rows) for rows in states_by_case.values())}/{expected_state_rows} interface_rows={len(interface_rows)}/{budget['required_device_count'] * 39}",
    )
    add_check(
        checks,
        "formal_scan_and_complete_p2_remain_closed",
        len(config["smoke_protocol"]["electrostatic_cases"]) == 3
        and len(config["smoke_protocol"]["coupled_cases"]) == 2
        and "formal three-point D_it transfer sensitivity" in config["scope"]["prohibited_work"]
        and "completed P2" in " ".join(config["evidence_boundary"]["prohibited_claims"]),
        config["evidence_boundary"]["next_gate"],
    )
    diagnostics = {
        "maximum_zero_dit_electrostatic_node_potential_difference_v": max_zero_difference,
        "maximum_interface_potential_discontinuity_v": max_continuity,
        "maximum_interface_flux_formula_error_c_per_cm2": formula_error,
        "maximum_interface_charge_sign_error_c_per_cm2": sign_error,
        "representative_center_gauss_relative_error": representative_es[
            "center_gauss_relative_error"
        ],
        "representative_center_physical_qit_c_per_cm2": representative_es[
            "center_physical_qit_c_per_cm2"
        ],
        "representative_center_potential_change_v": potential_change,
        "maximum_coupled_relative_current_imbalance": max_imbalance,
        "t02_c_zero_dit_reproduction": t02_differences,
        "representative_to_zero_dit_current_ratio": current_ratio,
    }
    return checks, diagnostics


def public_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in CASE_FIELDNAMES}


def report_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_summary(row),
        "bottom_interface_equations": row["bottom_interface_equations"],
        "top_interface_equations": row["top_interface_equations"],
        "interface_trap_equation_command": row["interface_trap_equation_command"],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = load_json(config_path)
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    if not contract_path.is_file():
        raise FileNotFoundError("run make t03-p2-dit-contract-check before the smoke")
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P2-DIT contract is not PASS")

    dependency = config["dependencies"]
    baseline = load_json(ROOT / dependency["t01_baseline_config"])
    mesh_config = load_json(ROOT / dependency["t01_mesh_config"])
    t02_config = load_json(ROOT / dependency["t02_a_config"])
    t02_rows = load_csv(ROOT / "results/tables/tcad_t02_c_bidirectional_families.csv")
    t02_reference = find_t02_reference(
        t02_rows, config["smoke_protocol"]["t02_c_reference"]
    )
    neutral = float(config["interface_trap_model"]["neutral_potential_v"])
    start = time.perf_counter()
    summaries: list[dict[str, Any]] = []
    solver_runs: list[dict[str, Any]] = []
    states_by_case: dict[str, list[dict[str, Any]]] = {}
    all_interface_rows: list[dict[str, Any]] = []

    electrostatic_bias = config["smoke_protocol"]["electrostatic_bias"]
    for case in config["smoke_protocol"]["electrostatic_cases"]:
        summary, records, states, samples = run_electrostatic_case(
            case, electrostatic_bias, neutral, baseline, mesh_config, t02_config
        )
        summaries.append(summary)
        solver_runs.append({"case_id": case["case_id"], "solve_mode": "electrostatic", "records": records})
        states_by_case[case["case_id"]] = states
        all_interface_rows.extend(samples)

    continuation = config["smoke_protocol"]["coupled_continuation"]
    for case in config["smoke_protocol"]["coupled_cases"]:
        summary, records, states, samples = run_coupled_case(
            case, continuation, neutral, baseline, mesh_config, t02_config
        )
        summaries.append(summary)
        solver_runs.append({"case_id": case["case_id"], "solve_mode": "coupled", "records": records})
        states_by_case[case["case_id"]] = states
        all_interface_rows.extend(samples)

    wall_seconds = time.perf_counter() - start
    checks, diagnostics = assess(
        config,
        contract,
        summaries,
        solver_runs,
        states_by_case,
        all_interface_rows,
        t02_reference,
        wall_seconds,
    )
    failures = [
        {"name": name, **value}
        for name, value in checks.items()
        if value["status"] == "FAIL"
    ]

    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_path = ROOT / outputs["solver_log"]
    case_path = ROOT / outputs["case_summary_csv"]
    interface_path = ROOT / outputs["interface_samples_csv"]
    state_path = ROOT / outputs["state_nodes_csv"]
    report_path = ROOT / outputs["report"]
    input_paths = {
        "t03_config": config_path,
        "contract_report": contract_path,
        "literature_table": ROOT / dependency["literature_table"],
        "t01_baseline_config": ROOT / dependency["t01_baseline_config"],
        "t01_mesh_config": ROOT / dependency["t01_mesh_config"],
        "t02_a_config": ROOT / dependency["t02_a_config"],
        "t02_c_family_csv": ROOT / "results/tables/tcad_t02_c_bidirectional_families.csv",
    }
    core.write_json(
        snapshot_path,
        {
            "case_id": config["case_id"],
            "stage": config["stage"],
            "inputs": {
                name: {
                    "path": str(path.relative_to(ROOT)),
                    "sha256": core.sha256(path),
                }
                for name, path in input_paths.items()
            },
            "formal_sensitivity_run": False,
        },
    )
    core.write_json(
        solver_path,
        {
            "case_id": config["case_id"],
            "stage": config["stage"],
            "runs": solver_runs,
            "total_dc_solve_count": sum(len(run["records"]) for run in solver_runs),
            "wall_seconds": wall_seconds,
        },
    )
    core.write_csv(case_path, [public_summary(row) for row in summaries], CASE_FIELDNAMES)
    core.write_csv(interface_path, all_interface_rows, INTERFACE_FIELDNAMES)
    ordered_states = [
        row
        for case_id in config["acceptance"]["required_case_ids"]
        for row in states_by_case[case_id]
    ]
    core.write_csv(state_path, ordered_states, STATE_FIELDNAMES)

    artifacts = {
        "config_snapshot": snapshot_path,
        "solver_log": solver_path,
        "case_summary_csv": case_path,
        "interface_samples_csv": interface_path,
        "state_nodes_csv": state_path,
    }
    report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if not failures else "E0",
        "contract_report": {
            "path": str(contract_path.relative_to(ROOT)),
            "sha256": core.sha256(contract_path),
            "status": contract.get("contract_status"),
        },
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "literature_input": config["literature_input"],
        "interface_trap_model": config["interface_trap_model"],
        "case_summaries": [report_summary(row) for row in summaries],
        "interface_equation_commands": {
            row["case_id"]: row["interface_trap_equation_command"]
            for row in summaries
            if row["interface_equation_active"]
        },
        "checks": checks,
        "failures": failures,
        "diagnostics": diagnostics,
        "resource_usage": {
            "device_count": len(summaries),
            "dc_solve_count": sum(len(run["records"]) for run in solver_runs),
            "state_node_row_count": len(ordered_states),
            "interface_sample_row_count": len(all_interface_rows),
            "wall_seconds": wall_seconds,
        },
        "artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in artifacts.items()
        },
        "t03_p2_completion": {
            "status": "PARTIAL" if not failures else "BLOCKED",
            "dit_literature_input_contract_passed": contract.get("contract_status") == "PASS",
            "dit_interface_equation_smoke_passed": not failures,
            "formal_three_point_dit_sensitivity_complete": False,
            "bulk_tail_and_deep_traps_complete": False,
            "complete_p2_trap_group": False,
            "complete_t03_five_group_sensitivity": False,
            "formal_three_point_dit_sensitivity_permitted_next": not failures,
            "experimental_calibration_permitted": False,
        },
        "formal_sensitivity_run": False,
        "evidence_boundary": config["evidence_boundary"],
        "limitations": config["interface_trap_model"]["limitations"],
    }
    core.write_json(report_path, report)
    print(
        f"T03_P2_DIT_EQUATION_SMOKE_{report['status']} checks={len(checks)} "
        f"dc_solves={report['resource_usage']['dc_solve_count']} "
        f"cases={len(summaries)} report={report_path}"
    )
    for failure in failures:
        print(
            f"T03_P2_DIT_EQUATION_SMOKE_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
