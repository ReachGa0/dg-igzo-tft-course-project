#!/usr/bin/env python3
"""Run the minimum T03-P2 bulk-trap equation smoke cases."""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402


core = t02_a.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_bulk_traps.json"
STAGE_ID = "T03-P2-BULK-TRAPS-EQUATION-SMOKE"
ELEMENTARY_CHARGE_C = 1.602176634e-19
MESH_LEVEL = "interface_4x"
ENABLED_REGIONS = t02_a.ENABLED_REGIONS
ENABLED_CONTACTS = t02_a.ENABLED_CONTACTS
ENABLED_INTERFACES = t02_a.ENABLED_INTERFACES

CASE_FIELDNAMES = [
    "case_id",
    "nta_cm3_ev",
    "nga_cm3_ev",
    "active_family",
    "solve_mode",
    "source_v",
    "drain_v",
    "vbg_v",
    "vtg_v",
    "mesh_level",
    "node_count_with_interface_duplicates",
    "element_count",
    "dc_solve_count",
    "all_dc_solves_converged",
    "source_current_a_per_cm",
    "drain_current_a_per_cm",
    "relative_current_imbalance",
    "center_channel_potential_v",
    "center_channel_electron_density_cm3",
    "center_tail_occupied_density_cm3",
    "center_deep_occupied_density_cm3",
    "center_occupied_bulk_traps_cm3",
    "center_occupied_bulk_traps_derivative",
    "center_physical_trap_charge_c_per_cm3",
    "center_poisson_trap_source_c_per_cm3",
    "minimum_occupied_bulk_traps_cm3",
    "maximum_occupied_bulk_traps_cm3",
    "minimum_occupied_bulk_traps_derivative",
    "maximum_occupied_bulk_traps_derivative",
    "wall_seconds",
]

INTEGRATION_FIELDNAMES = [
    "family",
    "electron_density_cm3",
    "gauss_legendre_integral_ev",
    "simpson_reference_integral_ev",
    "relative_error",
    "order",
]

STATE_FIELDNAMES = [
    "case_id",
    "nta_cm3_ev",
    "nga_cm3_ev",
    "active_family",
    "solve_mode",
    "source_v",
    "drain_v",
    "vbg_v",
    "vtg_v",
    "region",
    "x_cm",
    "y_cm",
    "x_um",
    "y_nm",
    "potential_v",
    "electron_density_cm3",
    "tail_occupied_density_cm3",
    "deep_occupied_density_cm3",
    "occupied_bulk_traps_cm3",
    "occupied_bulk_traps_derivative",
    "physical_trap_charge_c_per_cm3",
    "poisson_trap_source_c_per_cm3",
    "potential_node_charge_c_per_cm3",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=fieldnames,
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: float, right: float, *, rel_tol: float = 1e-10, abs_tol: float = 1e-15) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), 1e-300)


def add_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def gauss_legendre_nodes_weights(order: int) -> tuple[list[float], list[float]]:
    nodes = [0.0] * order
    weights = [0.0] * order
    midpoint = (order + 1) // 2
    for index in range(midpoint):
        root = math.cos(math.pi * (index + 0.75) / (order + 0.5))
        for _ in range(100):
            p0 = 1.0
            p1 = root
            for degree in range(2, order + 1):
                p0, p1 = p1, (
                    (2.0 * degree - 1.0) * root * p1 - (degree - 1.0) * p0
                ) / degree
            derivative = order * (root * p1 - p0) / (root * root - 1.0)
            updated = root - p1 / derivative
            if abs(updated - root) <= 2e-16:
                root = updated
                break
            root = updated
        else:
            raise RuntimeError("Gauss-Legendre root iteration did not converge")
        p0 = 1.0
        p1 = root
        for degree in range(2, order + 1):
            p0, p1 = p1, (
                (2.0 * degree - 1.0) * root * p1 - (degree - 1.0) * p0
            ) / degree
        derivative = order * (root * p1 - p0) / (root * root - 1.0)
        weight = 2.0 / ((1.0 - root * root) * derivative * derivative)
        nodes[index] = -root
        nodes[order - index - 1] = root
        weights[index] = weight
        weights[order - index - 1] = weight
    return nodes, weights


def energy_quadrature(config: dict[str, Any]) -> list[tuple[float, float]]:
    integration = config["energy_integration"]
    lower, upper = (float(value) for value in integration["domain_ev"])
    nodes, weights = gauss_legendre_nodes_weights(int(integration["order"]))
    midpoint = 0.5 * (lower + upper)
    half_width = 0.5 * (upper - lower)
    return [
        (midpoint + half_width * node, half_width * weight)
        for node, weight in zip(nodes, weights, strict=True)
    ]


def simpson_integral(function: Callable[[float], float], lower: float, upper: float, intervals: int) -> float:
    if intervals % 2:
        raise ValueError("Simpson intervals must be even")
    step = (upper - lower) / intervals
    odd_sum = math.fsum(function(lower + index * step) for index in range(1, intervals, 2))
    even_sum = math.fsum(function(lower + index * step) for index in range(2, intervals, 2))
    return step * (function(lower) + function(upper) + 4.0 * odd_sum + 2.0 * even_sum) / 3.0


def occupancy(epsilon_ev: float, electron_density_cm3: float, nc: float, thermal_ev: float) -> float:
    numerator = float(electron_density_cm3)
    denominator = numerator + nc * math.exp(-epsilon_ev / thermal_ev)
    return numerator / denominator


def integration_samples(config: dict[str, Any]) -> list[dict[str, Any]]:
    integration = config["energy_integration"]
    lower, upper = (float(value) for value in integration["domain_ev"])
    order = int(integration["order"])
    quadrature = energy_quadrature(config)
    nc = float(config["bulk_trap_model"]["effective_conduction_dos_cm3"])
    thermal = float(config["bulk_trap_model"]["boltzmann_ev_per_k"]) * float(
        config["bulk_trap_model"]["temperature_k"]
    )
    tail_width = float(config["literature_input"]["tail"]["width_ev"])
    deep_width = float(config["literature_input"]["deep"]["width_ev"])
    deep_peak = float(config["literature_input"]["deep"]["peak_depth_below_ec_ev"])
    profiles: dict[str, Callable[[float], float]] = {
        "tail": lambda epsilon: math.exp(-epsilon / tail_width),
        "deep": lambda epsilon: math.exp(-((epsilon - deep_peak) / deep_width) ** 2),
    }
    rows: list[dict[str, Any]] = []
    for family, profile in profiles.items():
        for density in integration["probe_electron_densities_cm3"]:
            electron_density = float(density)
            integrand = lambda epsilon, profile=profile, electron_density=electron_density: profile(
                epsilon
            ) * occupancy(epsilon, electron_density, nc, thermal)
            gauss = math.fsum(weight * integrand(epsilon) for epsilon, weight in quadrature)
            reference = simpson_integral(integrand, lower, upper, 32768)
            rows.append(
                {
                    "family": family,
                    "electron_density_cm3": electron_density,
                    "gauss_legendre_integral_ev": gauss,
                    "simpson_reference_integral_ev": reference,
                    "relative_error": abs(gauss - reference) / max(abs(reference), 1e-300),
                    "order": order,
                }
            )
    return rows


def build_runtime(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime, mesh_spec = t02_a.mesh_stage.build_runtime_baseline(
        baseline, mesh_config, MESH_LEVEL
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = float(
        t02_config["top_stack_contract"]["enabled_mode"]["top_oxide_thickness_cm"]
    )
    return runtime, mesh_spec


def format_constant(value: float) -> str:
    return f"{float(value):.17e}"


def sum_expression(terms: list[str]) -> str:
    if not terms:
        return "0"
    return "+".join(f"({term})" for term in terms)


def chunked(values: list[str], size: int) -> list[list[str]]:
    return [values[index : index + size] for index in range(0, len(values), size)]


def install_bulk_trap_models(
    device: str,
    case: dict[str, Any],
    config: dict[str, Any],
) -> dict[str, Any]:
    model = config["bulk_trap_model"]
    integration = config["energy_integration"]
    nta = float(case["nta_cm3_ev"])
    nga = float(case["nga_cm3_ev"])
    nc = float(model["effective_conduction_dos_cm3"])
    thermal = float(model["boltzmann_ev_per_k"]) * float(model["temperature_k"])
    tail_width = float(config["literature_input"]["tail"]["width_ev"])
    deep_width = float(config["literature_input"]["deep"]["width_ev"])
    deep_peak = float(config["literature_input"]["deep"]["peak_depth_below_ec_ev"])
    quadrature = energy_quadrature(config)

    core.devsim.set_parameter(
        device=device, region="channel", name="BulkTrapNTA", value=nta
    )
    core.devsim.set_parameter(
        device=device, region="channel", name="BulkTrapNGA", value=nga
    )
    core.devsim.set_parameter(
        device=device, region="channel", name="BulkTrapNc", value=nc
    )
    core.devsim.set_parameter(
        device=device, region="channel", name="BulkTrapThermalEnergy", value=thermal
    )

    tail_integral_terms: list[str] = []
    deep_integral_terms: list[str] = []
    tail_derivative_terms: list[str] = []
    deep_derivative_terms: list[str] = []
    occupancy_models: list[str] = []
    for index, (epsilon, weight) in enumerate(quadrature):
        epsilon_text = format_constant(epsilon)
        weight_text = format_constant(weight)
        tail_profile = format_constant(math.exp(-epsilon / tail_width))
        deep_profile = format_constant(math.exp(-((epsilon - deep_peak) / deep_width) ** 2))
        exponential = format_constant(nc * math.exp(-epsilon / thermal))
        occupancy_name = f"BulkTrapOccupancy_{index:03d}"
        occupancy_expression = f"Electrons/(Electrons+{exponential})"
        core.CreateNodeModel(
            device,
            "channel",
            occupancy_name,
            occupancy_expression,
        )
        occupancy_models.append(occupancy_name)
        tail_integral_terms.append(f"{weight_text}*{tail_profile}*{occupancy_name}")
        deep_integral_terms.append(f"{weight_text}*{deep_profile}*{occupancy_name}")
        derivative_factor = f"{exponential}/((Electrons+{exponential})*(Electrons+{exponential}))"
        tail_derivative_terms.append(f"{weight_text}*{tail_profile}*{derivative_factor}")
        deep_derivative_terms.append(f"{weight_text}*{deep_profile}*{derivative_factor}")

    # Chunk the 96-point sums to keep each DEVSIM expression comfortably small.
    tail_chunks = []
    deep_chunks = []
    tail_derivative_chunks = []
    deep_derivative_chunks = []
    for index, terms in enumerate(chunked(tail_integral_terms, 12)):
        name = f"BulkTrapTailIntegralPart_{index:02d}"
        core.CreateNodeModel(device, "channel", name, sum_expression(terms))
        tail_chunks.append(name)
    for index, terms in enumerate(chunked(deep_integral_terms, 12)):
        name = f"BulkTrapDeepIntegralPart_{index:02d}"
        core.CreateNodeModel(device, "channel", name, sum_expression(terms))
        deep_chunks.append(name)
    for index, terms in enumerate(chunked(tail_derivative_terms, 12)):
        name = f"BulkTrapTailDerivativePart_{index:02d}"
        core.CreateNodeModel(device, "channel", name, sum_expression(terms))
        tail_derivative_chunks.append(name)
    for index, terms in enumerate(chunked(deep_derivative_terms, 12)):
        name = f"BulkTrapDeepDerivativePart_{index:02d}"
        core.CreateNodeModel(device, "channel", name, sum_expression(terms))
        deep_derivative_chunks.append(name)

    tail_integral_expression = sum_expression(tail_chunks)
    deep_integral_expression = sum_expression(deep_chunks)
    tail_derivative_expression = sum_expression(tail_derivative_chunks)
    deep_derivative_expression = sum_expression(deep_derivative_chunks)
    if nta == 0.0 and nga == 0.0:
        tail_density_expression = "0"
        deep_density_expression = "0"
        occupied_expression = "0"
        derivative_expression = "0"
        potential_charge_expression = "ElectronCharge*(Electrons-NetDoping)"
        potential_charge_derivative = "ElectronCharge"
        exact_zero_branch = True
    else:
        tail_density_expression = f"BulkTrapNTA*({tail_integral_expression})"
        deep_density_expression = f"BulkTrapNGA*({deep_integral_expression})"
        occupied_expression = "BulkTrapTailOccupiedDensity+BulkTrapDeepOccupiedDensity"
        derivative_expression = (
            f"BulkTrapNTA*({tail_derivative_expression})+"
            f"BulkTrapNGA*({deep_derivative_expression})"
        )
        potential_charge_expression = (
            "ElectronCharge*(Electrons+OccupiedBulkTraps-NetDoping)"
        )
        potential_charge_derivative = (
            "ElectronCharge*(1+OccupiedBulkTrapsDerivative)"
        )
        exact_zero_branch = False

    core.CreateNodeModel(
        device, "channel", "BulkTrapTailOccupiedDensity", tail_density_expression
    )
    core.CreateNodeModel(
        device, "channel", "BulkTrapDeepOccupiedDensity", deep_density_expression
    )
    core.CreateNodeModel(device, "channel", "OccupiedBulkTraps", occupied_expression)
    core.CreateNodeModel(
        device, "channel", "OccupiedBulkTrapsDerivative", derivative_expression
    )
    core.CreateNodeModel(
        device,
        "channel",
        "PotentialNodeTrapCharge",
        "ElectronCharge*OccupiedBulkTraps",
    )
    core.CreateNodeModel(
        device,
        "channel",
        "PotentialNodeTrapCharge:Electrons",
        "ElectronCharge*OccupiedBulkTrapsDerivative",
    )
    core.CreateNodeModel(
        device,
        "channel",
        "PhysicalBulkTrapCharge",
        "-ElectronCharge*OccupiedBulkTraps",
    )
    core.CreateNodeModel(
        device,
        "channel",
        "PhysicalBulkTrapCharge:Electrons",
        "-ElectronCharge*OccupiedBulkTrapsDerivative",
    )
    core.CreateNodeModel(
        device, "channel", "PotentialNodeCharge", potential_charge_expression
    )
    core.CreateNodeModel(
        device,
        "channel",
        "PotentialNodeCharge:Electrons",
        potential_charge_derivative,
    )
    return {
        "quadrature_order": int(integration["order"]),
        "quadrature_term_count": len(quadrature),
        "quadrature_chunk_size": 12,
        "occupancy_model_count": len(occupancy_models),
        "occupancy_models": occupancy_models,
        "exact_zero_branch": exact_zero_branch,
        "tail_density_expression": tail_density_expression,
        "deep_density_expression": deep_density_expression,
        "occupied_density_expression": occupied_expression,
        "occupied_density_derivative_expression": derivative_expression,
        "potential_node_charge_expression": potential_charge_expression,
        "potential_node_charge_derivative_expression": potential_charge_derivative,
        "inactive_interface_dit_cm2_ev": 0.0,
        "interface_equations_are_continuous_only": True,
    }


def model_values(device: str, region: str, name: str, count: int) -> list[float]:
    try:
        values = [float(value) for value in core.devsim.get_node_model_values(device=device, region=region, name=name)]
    except core.devsim.error:
        values = []
    if len(values) == count:
        return values
    if len(values) == 0:
        return [0.0] * count
    raise RuntimeError(
        f"node model {name} returned {len(values)} values; expected {count}"
    )


def collect_state_nodes(
    device: str,
    case: dict[str, Any],
    bias: dict[str, float],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in ENABLED_REGIONS:
        xs = core.devsim.get_node_model_values(device=device, region=region, name="x")
        ys = core.devsim.get_node_model_values(device=device, region=region, name="y")
        potentials = core.devsim.get_node_model_values(device=device, region=region, name="Potential")
        count = len(xs)
        electrons = (
            model_values(device, region, "Electrons", count)
            if region == "channel"
            else [None] * count
        )
        tail = (
            model_values(device, region, "BulkTrapTailOccupiedDensity", count)
            if region == "channel"
            else [None] * count
        )
        deep = (
            model_values(device, region, "BulkTrapDeepOccupiedDensity", count)
            if region == "channel"
            else [None] * count
        )
        occupied = (
            model_values(device, region, "OccupiedBulkTraps", count)
            if region == "channel"
            else [None] * count
        )
        derivative = (
            model_values(device, region, "OccupiedBulkTrapsDerivative", count)
            if region == "channel"
            else [None] * count
        )
        physical = (
            model_values(device, region, "PhysicalBulkTrapCharge", count)
            if region == "channel"
            else [None] * count
        )
        source = (
            model_values(device, region, "PotentialNodeTrapCharge", count)
            if region == "channel"
            else [None] * count
        )
        node_charge = (
            model_values(device, region, "PotentialNodeCharge", count)
            if region == "channel"
            else [None] * count
        )
        for values in zip(
            xs,
            ys,
            potentials,
            electrons,
            tail,
            deep,
            occupied,
            derivative,
            physical,
            source,
            node_charge,
            strict=True,
        ):
            x, y, potential, electron, tail_value, deep_value, occupied_value, derivative_value, physical_value, source_value, node_charge_value = values
            rows.append(
                {
                    "case_id": case["case_id"],
                    "nta_cm3_ev": float(case["nta_cm3_ev"]),
                    "nga_cm3_ev": float(case["nga_cm3_ev"]),
                    "active_family": case["active_family"],
                    "solve_mode": "coupled_final",
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
                    "electron_density_cm3": "" if electron is None else electron,
                    "tail_occupied_density_cm3": "" if tail_value is None else tail_value,
                    "deep_occupied_density_cm3": "" if deep_value is None else deep_value,
                    "occupied_bulk_traps_cm3": "" if occupied_value is None else occupied_value,
                    "occupied_bulk_traps_derivative": "" if derivative_value is None else derivative_value,
                    "physical_trap_charge_c_per_cm3": "" if physical_value is None else physical_value,
                    "poisson_trap_source_c_per_cm3": "" if source_value is None else source_value,
                    "potential_node_charge_c_per_cm3": "" if node_charge_value is None else node_charge_value,
                }
            )
    return rows


def center_state(rows: list[dict[str, Any]], runtime: dict[str, Any]) -> dict[str, Any]:
    target_x = float(runtime["geometry"]["channel_length_cm"]) / 2.0
    target_y = float(runtime["geometry"]["bottom_oxide_thickness_cm"]) + float(
        runtime["geometry"]["channel_thickness_cm"]
    ) / 2.0
    return min(
        (row for row in rows if row["region"] == "channel"),
        key=lambda row: (float(row["x_cm"]) - target_x) ** 2
        + (float(row["y_cm"]) - target_y) ** 2,
    )


def run_case(
    case: dict[str, Any],
    config: dict[str, Any],
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t02_config: dict[str, Any],
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    runtime, mesh_spec = build_runtime(baseline, mesh_config, t02_config)
    device = f"t03_p2_bulk_{case['case_id']}"
    protocol = config["next_equation_smoke"]["protocol"]
    records: list[dict[str, Any]] = []
    start = time.perf_counter()
    try:
        t02_a.initialize_enabled_device(device, runtime, t02_config, MESH_LEVEL, mesh_spec)
        model_metadata = install_bulk_trap_models(device, case, config)
        t02_a.set_enabled_biases(device, source_v=0.0, drain_v=0.0, bottom_gate_v=0.0, top_gate_v=0.0)
        records.append(core.solve_dc(device, runtime, f"{case['case_id']}_POISSON_ZERO", coupled=False))
        core.create_transport(device, runtime)
        records.append(core.solve_dc(device, runtime, f"{case['case_id']}_COUPLED_ZERO", coupled=True))
        for vds_v in protocol["low_vds_values_v"]:
            t02_a.set_enabled_biases(
                device,
                source_v=float(protocol["source_v"]),
                drain_v=float(vds_v),
                bottom_gate_v=float(protocol["fixed_bottom_gate_v"]),
                top_gate_v=0.0,
            )
            records.append(
                core.solve_dc(device, runtime, f"{case['case_id']}_VDS_{float(vds_v):.6g}", coupled=True)
            )
        for vtg_v in protocol["top_gate_values_v"]:
            t02_a.set_enabled_biases(
                device,
                source_v=float(protocol["source_v"]),
                drain_v=float(protocol["drain_v"]),
                bottom_gate_v=float(protocol["fixed_bottom_gate_v"]),
                top_gate_v=float(vtg_v),
            )
            records.append(
                core.solve_dc(device, runtime, f"{case['case_id']}_VTG_{float(vtg_v):.6g}", coupled=True)
            )
        final_bias = protocol["final_common_state"]
        states = collect_state_nodes(device, case, final_bias)
        channel_states = [row for row in states if row["region"] == "channel"]
        center = center_state(states, runtime)
        source_current = float(
            core.devsim.get_contact_current(device=device, contact="source", equation="ElectronContinuityEquation")
        )
        drain_current = float(
            core.devsim.get_contact_current(device=device, contact="drain", equation="ElectronContinuityEquation")
        )
        imbalance = abs(source_current + drain_current) / max(abs(source_current), abs(drain_current), 1e-300)
        node_count, element_count = t02_a.active_counts(device, ENABLED_REGIONS)
        regions, contacts, interfaces = t02_a.active_topology(device, ENABLED_REGIONS)
        channel_models = sorted(core.devsim.get_node_model_list(device=device, region="channel"))
        model_names = {
            "tail_density": "BulkTrapTailOccupiedDensity",
            "deep_density": "BulkTrapDeepOccupiedDensity",
            "occupied_density": "OccupiedBulkTraps",
            "occupied_derivative": "OccupiedBulkTrapsDerivative",
            "physical_charge": "PhysicalBulkTrapCharge",
            "poisson_source": "PotentialNodeTrapCharge",
            "potential_node_charge": "PotentialNodeCharge",
        }
        summary = {
            "case_id": case["case_id"],
            "nta_cm3_ev": float(case["nta_cm3_ev"]),
            "nga_cm3_ev": float(case["nga_cm3_ev"]),
            "active_family": case["active_family"],
            "solve_mode": "coupled",
            "source_v": float(final_bias["source_v"]),
            "drain_v": float(final_bias["drain_v"]),
            "vbg_v": float(final_bias["bottom_gate_v"]),
            "vtg_v": float(final_bias["top_gate_v"]),
            "mesh_level": MESH_LEVEL,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(records),
            "all_dc_solves_converged": all(bool(record["converged"]) for record in records),
            "source_current_a_per_cm": source_current,
            "drain_current_a_per_cm": drain_current,
            "relative_current_imbalance": imbalance,
            "center_channel_potential_v": float(center["potential_v"]),
            "center_channel_electron_density_cm3": float(center["electron_density_cm3"]),
            "center_tail_occupied_density_cm3": float(center["tail_occupied_density_cm3"]),
            "center_deep_occupied_density_cm3": float(center["deep_occupied_density_cm3"]),
            "center_occupied_bulk_traps_cm3": float(center["occupied_bulk_traps_cm3"]),
            "center_occupied_bulk_traps_derivative": float(center["occupied_bulk_traps_derivative"]),
            "center_physical_trap_charge_c_per_cm3": float(center["physical_trap_charge_c_per_cm3"]),
            "center_poisson_trap_source_c_per_cm3": float(center["poisson_trap_source_c_per_cm3"]),
            "minimum_occupied_bulk_traps_cm3": min(float(row["occupied_bulk_traps_cm3"]) for row in channel_states),
            "maximum_occupied_bulk_traps_cm3": max(float(row["occupied_bulk_traps_cm3"]) for row in channel_states),
            "minimum_occupied_bulk_traps_derivative": min(float(row["occupied_bulk_traps_derivative"]) for row in channel_states),
            "maximum_occupied_bulk_traps_derivative": max(float(row["occupied_bulk_traps_derivative"]) for row in channel_states),
            "wall_seconds": time.perf_counter() - start,
            "topology": {"regions": regions, "contacts": contacts, "interfaces": interfaces},
            "bottom_interface_equations": sorted(core.devsim.get_interface_equation_list(device=device, interface="bottom_oxide_channel")),
            "top_interface_equations": sorted(core.devsim.get_interface_equation_list(device=device, interface="channel_top_oxide")),
            "channel_equations": sorted(core.devsim.get_equation_list(device=device, region="channel")),
            "channel_node_models": channel_models,
            "required_node_models": model_names,
            "model_metadata": model_metadata,
            "physical_trap_charge_formula": "-ElectronCharge*OccupiedBulkTraps",
            "poisson_trap_source_formula": "ElectronCharge*OccupiedBulkTraps",
            "potential_node_charge_formula": model_metadata["potential_node_charge_expression"],
            "potential_node_charge_derivative_formula": model_metadata["potential_node_charge_derivative_expression"],
        }
        return summary, records, states
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def find_t02_reference(rows: list[dict[str, str]], spec: dict[str, Any]) -> dict[str, str]:
    return next(
        row
        for row in rows
        if row["family_id"] == spec["family_id"]
        and row["sweep_direction"] == spec["sweep_direction"]
        and close(float(row["fixed_secondary_gate_v"]), spec["fixed_secondary_gate_v"])
        and close(float(row["primary_gate_v"]), spec["primary_gate_v"])
        and close(float(row["vds_v"]), spec["vds_v"])
    )


def channel_map(rows: list[dict[str, Any]], field: str) -> dict[tuple[float, float], float]:
    return {
        (round(float(row["x_cm"]), 18), round(float(row["y_cm"]), 18)): float(row[field])
        for row in rows
        if row["region"] == "channel"
    }


def assess(
    config: dict[str, Any],
    contract: dict[str, Any],
    summaries: list[dict[str, Any]],
    solver_runs: list[dict[str, Any]],
    states_by_case: dict[str, list[dict[str, Any]]],
    integration_rows: list[dict[str, Any]],
    t02_reference: dict[str, str],
    config_path: Path,
    wall_seconds: float,
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    smoke = config["next_equation_smoke"]
    acceptance = config["acceptance"]
    budget = smoke["resource_budget"]
    expected_cases = [item["case_id"] for item in smoke["cases"]]
    by_case = {row["case_id"]: row for row in summaries}
    checks: dict[str, dict[str, Any]] = {}
    add_check(
        checks,
        "contract_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("config", {}).get("sha256") == sha256(config_path),
        f"status={contract.get('contract_status')} config_hash_matches={contract.get('config', {}).get('sha256') == sha256(config_path)}",
    )
    all_records = [record for run in solver_runs for record in run["records"]]
    add_check(
        checks,
        "three_cases_and_21_dc_solves_completed",
        [row["case_id"] for row in summaries] == expected_cases
        and len(summaries) == budget["required_device_count"]
        and len(all_records) == budget["required_total_dc_solve_count"]
        and [row["dc_solve_count"] for row in summaries]
        == [budget["required_dc_solve_count_per_device"]] * budget["required_device_count"],
        f"cases={[row['case_id'] for row in summaries]} solves={len(all_records)}",
    )
    add_check(
        checks,
        "all_dc_solves_converged_within_laptop_budget",
        all(bool(record["converged"]) for record in all_records)
        and wall_seconds <= float(budget["maximum_wall_seconds"]),
        f"converged={sum(bool(record['converged']) for record in all_records)}/{len(all_records)} wall={wall_seconds:.6f}s",
    )
    add_check(
        checks,
        "isolated_families_and_interface_dit_zero_are_preserved",
        [(row["nta_cm3_ev"], row["nga_cm3_ev"]) for row in summaries]
        == [(0.0, 0.0), (5e18, 0.0), (0.0, 5e16)]
        and all(
            row["bottom_interface_equations"] == ["PotentialEquation"]
            and row["top_interface_equations"] == ["PotentialEquation"]
            for row in summaries
        ),
        f"families={[(row['nta_cm3_ev'], row['nga_cm3_ev']) for row in summaries]}",
    )
    topology_valid = all(
        row["topology"]["regions"] == sorted(ENABLED_REGIONS)
        and row["topology"]["contacts"] == sorted(ENABLED_CONTACTS)
        and row["topology"]["interfaces"] == sorted(ENABLED_INTERFACES)
        and row["node_count_with_interface_duplicates"] == 2419
        and row["element_count"] == 4480
        for row in summaries
    )
    add_check(checks, "topology_matches_t02_a_enabled_stack", topology_valid, str([row["topology"] for row in summaries]))
    required_model_names = {
        "BulkTrapTailOccupiedDensity",
        "BulkTrapDeepOccupiedDensity",
        "OccupiedBulkTraps",
        "OccupiedBulkTrapsDerivative",
        "PhysicalBulkTrapCharge",
        "PotentialNodeTrapCharge",
        "PotentialNodeCharge",
        "PotentialNodeCharge:Electrons",
    }
    model_valid = all(
        required_model_names <= set(row["channel_node_models"])
        and row["channel_equations"]
        == ["ElectronContinuityEquation", "PotentialEquation"]
        for row in summaries
    )
    add_check(checks, "bulk_node_models_and_channel_equations_are_installed", model_valid, str([(row["case_id"], row["channel_equations"]) for row in summaries]))
    integration_limit = float(config["energy_integration"]["maximum_relative_error_vs_reference"])
    integration_valid = len(integration_rows) == 6 and all(
        math.isfinite(float(row["gauss_legendre_integral_ev"]))
        and math.isfinite(float(row["simpson_reference_integral_ev"]))
        and float(row["relative_error"]) <= integration_limit
        for row in integration_rows
    )
    add_check(checks, "quadrature_samples_pass_independent_reference_gate", integration_valid, f"rows={len(integration_rows)} max_error={max(float(row['relative_error']) for row in integration_rows):.6e}")
    channel_rows = [row for rows in states_by_case.values() for row in rows if row["region"] == "channel"]
    finite_nonnegative = all(
        math.isfinite(float(row["electron_density_cm3"]))
        and math.isfinite(float(row["occupied_bulk_traps_cm3"]))
        and math.isfinite(float(row["occupied_bulk_traps_derivative"]))
        and float(row["electron_density_cm3"]) > 0.0
        and float(row["occupied_bulk_traps_cm3"]) >= -1e-12
        and float(row["occupied_bulk_traps_derivative"]) >= -1e-12
        for row in channel_rows
    )
    add_check(checks, "occupied_density_and_analytic_derivative_are_finite_nonnegative", finite_nonnegative, f"channel_rows={len(channel_rows)}")
    charge_sign = all(
        float(row["physical_trap_charge_c_per_cm3"]) <= 1e-12
        and float(row["poisson_trap_source_c_per_cm3"]) >= -1e-12
        and abs(float(row["physical_trap_charge_c_per_cm3"]) + float(row["poisson_trap_source_c_per_cm3"])) <= 1e-10 * max(abs(float(row["poisson_trap_source_c_per_cm3"])), 1.0)
        for row in channel_rows
    )
    add_check(checks, "physical_trap_charge_and_poisson_source_have_opposite_sign", charge_sign, "physical Qtrap <= 0 and Poisson node source >= 0")
    zero_rows = states_by_case[expected_cases[0]]
    zero_channel = [row for row in zero_rows if row["region"] == "channel"]
    zero_exact = all(
        abs(float(row["tail_occupied_density_cm3"])) <= 1e-12
        and abs(float(row["deep_occupied_density_cm3"])) <= 1e-12
        and abs(float(row["occupied_bulk_traps_cm3"])) <= 1e-12
        and abs(float(row["occupied_bulk_traps_derivative"])) <= 1e-12
        and abs(float(row["physical_trap_charge_c_per_cm3"])) <= 1e-12
        and abs(float(row["poisson_trap_source_c_per_cm3"])) <= 1e-12
        for row in zero_channel
    )
    add_check(checks, "zero_density_has_exact_zero_trap_models", zero_exact, f"zero_channel_rows={len(zero_channel)}")
    zero_summary = by_case[expected_cases[0]]
    t02_current = abs(float(t02_reference["drain_current_a_per_cm"]))
    zero_current = abs(float(zero_summary["drain_current_a_per_cm"]))
    t02_differences = {
        "current_relative": relative_difference(zero_current, t02_current),
        "center_potential_v": abs(float(zero_summary["center_channel_potential_v"]) - float(t02_reference["center_channel_potential_v"])),
        "center_density_relative": relative_difference(float(zero_summary["center_channel_electron_density_cm3"]), float(t02_reference["center_channel_electron_density_cm3"])),
    }
    add_check(
        checks,
        "zero_density_reproduces_t02_c_common_bias_reference",
        t02_differences["current_relative"] <= float(acceptance["maximum_future_zero_control_t02_c_current_relative_difference"])
        and t02_differences["center_potential_v"] <= 1e-7
        and t02_differences["center_density_relative"] <= 1e-6,
        json.dumps(t02_differences, sort_keys=True),
    )
    coupled_rows = [row for row in summaries if row["solve_mode"] == "coupled"]
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in coupled_rows)
    add_check(
        checks,
        "coupled_terminal_current_is_conserved",
        max_imbalance <= float(acceptance["maximum_future_relative_terminal_current_imbalance"]),
        f"maximum_relative_imbalance={max_imbalance:.6e}",
    )
    response_rows = []
    for case_id in expected_cases[1:]:
        current_response = relative_difference(abs(float(by_case[case_id]["drain_current_a_per_cm"])), zero_current)
        density_response = relative_difference(float(by_case[case_id]["center_channel_electron_density_cm3"]), float(zero_summary["center_channel_electron_density_cm3"]))
        response_rows.append({"case_id": case_id, "current_relative": current_response, "density_relative": density_response})
    response_valid = all(
        max(item["current_relative"], item["density_relative"]) >= float(acceptance["minimum_future_nonzero_common_state_relative_response"])
        for item in response_rows
    )
    add_check(checks, "tail_and_deep_cases_have_nonzero_common_state_response", response_valid, json.dumps(response_rows, sort_keys=True))
    add_check(
        checks,
        "persisted_state_and_solver_evidence_counts_match_contract",
        len(states_by_case) == 3
        and all(len(rows) == 2419 for rows in states_by_case.values())
        and len(integration_rows) == 6,
        f"state_rows={sum(len(rows) for rows in states_by_case.values())} integration_rows={len(integration_rows)}",
    )
    add_check(
        checks,
        "formal_bulk_scan_and_complete_p2_remain_closed",
        config["next_equation_smoke"]["evidence_boundary"]["next_gate"].startswith("Only a passed equation smoke")
        and "formal NTA or NGA transfer sensitivity has completed" in config["next_equation_smoke"]["evidence_boundary"]["prohibited_claims"],
        config["next_equation_smoke"]["evidence_boundary"]["next_gate"],
    )
    diagnostics = {
        "t02_c_zero_control_reproduction": t02_differences,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "maximum_integration_relative_error": max(float(row["relative_error"]) for row in integration_rows),
        "nonzero_response": response_rows,
        "state_node_row_count": sum(len(rows) for rows in states_by_case.values()),
        "channel_node_row_count": len(channel_rows),
    }
    return checks, diagnostics


def public_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {key: row[key] for key in CASE_FIELDNAMES}


def report_summary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        **public_summary(row),
        "topology": row["topology"],
        "bottom_interface_equations": row["bottom_interface_equations"],
        "top_interface_equations": row["top_interface_equations"],
        "channel_equations": row["channel_equations"],
        "channel_node_models": row["channel_node_models"],
        "required_node_models": row["required_node_models"],
        "model_metadata": row["model_metadata"],
        "physical_trap_charge_formula": row["physical_trap_charge_formula"],
        "poisson_trap_source_formula": row["poisson_trap_source_formula"],
        "potential_node_charge_formula": row["potential_node_charge_formula"],
        "potential_node_charge_derivative_formula": row["potential_node_charge_derivative_formula"],
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
        raise FileNotFoundError("run make t03-p2-bulk-traps-contract-check before the smoke")
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P2-BULK-TRAPS contract is not PASS")
    if contract.get("config", {}).get("sha256") != sha256(config_path):
        raise RuntimeError("T03-P2-BULK-TRAPS contract hash does not match the current config")

    dependencies = config["dependencies"]
    baseline = load_json(ROOT / dependencies["t01_baseline_config"])
    mesh_config = load_json(ROOT / "config/tcad_t01_d_mesh_refinement.json")
    t02_config = load_json(ROOT / dependencies["t02_a_config"])
    t02_rows = load_csv(ROOT / "results/tables/tcad_t02_c_bidirectional_families.csv")
    t02_reference = find_t02_reference(t02_rows, config["next_equation_smoke"]["protocol"]["t02_c_reference"])
    cases = []
    for item in config["next_equation_smoke"]["cases"]:
        case = dict(item)
        case["active_family"] = "none" if float(case["nta_cm3_ev"]) == 0.0 and float(case["nga_cm3_ev"]) == 0.0 else ("tail" if float(case["nta_cm3_ev"]) > 0.0 else "deep")
        cases.append(case)

    start = time.perf_counter()
    summaries: list[dict[str, Any]] = []
    solver_runs: list[dict[str, Any]] = []
    states_by_case: dict[str, list[dict[str, Any]]] = {}
    for case in cases:
        summary, records, states = run_case(case, config, baseline, mesh_config, t02_config)
        summaries.append(summary)
        solver_runs.append({"case_id": case["case_id"], "records": records})
        states_by_case[case["case_id"]] = states
    wall_seconds = time.perf_counter() - start
    integration_rows = integration_samples(config)
    checks, diagnostics = assess(
        config,
        contract,
        summaries,
        solver_runs,
        states_by_case,
        integration_rows,
        t02_reference,
        config_path,
        wall_seconds,
    )
    failures = [{"name": name, **value} for name, value in checks.items() if value["status"] == "FAIL"]

    run_dir = ROOT / outputs["future_run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["future_config_snapshot"]
    solver_path = ROOT / outputs["future_solver_log"]
    case_path = ROOT / outputs["future_case_summary_csv"]
    integration_path = ROOT / outputs["future_integration_samples_csv"]
    state_path = ROOT / outputs["future_state_nodes_csv"]
    report_path = ROOT / outputs["future_report"]
    input_paths = {
        "bulk_contract_config": config_path,
        "bulk_contract_report": contract_path,
        "literature_table": ROOT / dependencies["literature_table"],
        "t01_baseline_config": ROOT / dependencies["t01_baseline_config"],
        "t01_mesh_config": ROOT / "config/tcad_t01_d_mesh_refinement.json",
        "t02_a_config": ROOT / dependencies["t02_a_config"],
        "t02_c_family_csv": ROOT / "results/tables/tcad_t02_c_bidirectional_families.csv",
        "runner_script": Path(__file__).resolve(),
    }
    write_json(
        snapshot_path,
        {
            "case_id": config["next_equation_smoke"]["case_id"],
            "stage": STAGE_ID,
            "formal_sensitivity_run": False,
            "inputs": {
                name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
                for name, path in input_paths.items()
            },
        },
    )
    write_json(
        solver_path,
        {
            "case_id": config["next_equation_smoke"]["case_id"],
            "stage": STAGE_ID,
            "runs": solver_runs,
            "total_dc_solve_count": sum(len(run["records"]) for run in solver_runs),
            "wall_seconds": wall_seconds,
        },
    )
    write_csv(case_path, [public_summary(row) for row in summaries], CASE_FIELDNAMES)
    write_csv(integration_path, integration_rows, INTEGRATION_FIELDNAMES)
    ordered_states = [row for case in cases for row in states_by_case[case["case_id"]]]
    write_csv(state_path, ordered_states, STATE_FIELDNAMES)
    artifacts = {
        "config_snapshot": snapshot_path,
        "solver_log": solver_path,
        "case_summary_csv": case_path,
        "integration_samples_csv": integration_path,
        "state_nodes_csv": state_path,
    }
    smoke_boundary = config["next_equation_smoke"]["evidence_boundary"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["next_equation_smoke"]["case_id"],
        "stage": STAGE_ID,
        "parameter_group_id": "P2",
        "evidence_level": "E2" if not failures else "E0",
        "contract_report": {
            "path": str(contract_path.relative_to(ROOT)),
            "sha256": sha256(contract_path),
            "status": contract.get("contract_status"),
        },
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "literature_input": config["literature_input"],
        "bulk_trap_model": config["bulk_trap_model"],
        "equation_smoke_protocol": config["next_equation_smoke"]["protocol"],
        "case_summaries": [report_summary(row) for row in summaries],
        "integration_samples": integration_rows,
        "checks": checks,
        "failures": failures,
        "diagnostics": diagnostics,
        "resource_usage": {
            "device_count": len(summaries),
            "dc_solve_count": sum(len(run["records"]) for run in solver_runs),
            "state_node_row_count": len(ordered_states),
            "integration_sample_row_count": len(integration_rows),
            "wall_seconds": wall_seconds,
        },
        "artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in artifacts.items()
        },
        "t03_p2_completion": {
            "status": "PARTIAL" if not failures else "BLOCKED",
            "bulk_trap_equation_smoke_passed": not failures,
            "bulk_tail_and_deep_traps_complete": False,
            "formal_bulk_sensitivity_complete": False,
            "complete_p2_trap_group": False,
            "complete_t03_five_group_sensitivity": False,
            "formal_bulk_sensitivity_permitted_next": not failures,
            "experimental_calibration_permitted": False,
        },
        "formal_sensitivity_run": False,
        "evidence_boundary": smoke_boundary,
        "limitations": config["bulk_trap_model"]["limitations"],
    }
    write_json(report_path, report)
    print(
        f"T03_P2_BULK_TRAPS_EQUATION_SMOKE_{report['status']} "
        f"checks={len(checks)} dc_solves={report['resource_usage']['dc_solve_count']} "
        f"cases={len(summaries)} wall_seconds={wall_seconds:.3f} report={report_path}"
    )
    for failure in failures:
        print(
            f"T03_P2_BULK_TRAPS_EQUATION_SMOKE_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
