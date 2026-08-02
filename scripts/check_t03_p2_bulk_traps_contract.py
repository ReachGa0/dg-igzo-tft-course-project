#!/usr/bin/env python3
"""Validate the T03-P2 bulk-trap input contract without running DEVSIM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_bulk_traps.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(
    left: float,
    right: float,
    *,
    rel_tol: float = 1e-12,
    abs_tol: float = 1e-15,
) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def primary_grid(spec: dict[str, Any]) -> list[float]:
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    count = round((stop - start) / step)
    if count < 1 or not close(start + count * step, stop):
        raise ValueError("primary gate grid is not integral")
    return [round(start + index * step, 12) for index in range(count + 1)]


def gauss_legendre_nodes_weights(order: int) -> tuple[list[float], list[float]]:
    """Compute Legendre nodes/weights with the standard-library Newton method."""
    nodes = [0.0] * order
    weights = [0.0] * order
    half = (order + 1) // 2
    for index in range(half):
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


def gauss_integral(
    function: Callable[[float], float], lower: float, upper: float, order: int
) -> float:
    nodes, weights = gauss_legendre_nodes_weights(order)
    midpoint = 0.5 * (lower + upper)
    half_width = 0.5 * (upper - lower)
    return half_width * math.fsum(
        weight * function(midpoint + half_width * node)
        for node, weight in zip(nodes, weights, strict=True)
    )


def simpson_integral(
    function: Callable[[float], float], lower: float, upper: float, intervals: int
) -> float:
    if intervals % 2:
        raise ValueError("Simpson intervals must be even")
    step = (upper - lower) / intervals
    odd_sum = math.fsum(
        function(lower + index * step) for index in range(1, intervals, 2)
    )
    even_sum = math.fsum(
        function(lower + index * step) for index in range(2, intervals, 2)
    )
    return step * (
        function(lower) + function(upper) + 4.0 * odd_sum + 2.0 * even_sum
    ) / 3.0


def occupancy(epsilon_ev: float, density_cm3: float, model: dict[str, Any]) -> float:
    nc = float(model["effective_conduction_dos_cm3"])
    thermal_ev = float(model["boltzmann_ev_per_k"]) * float(model["temperature_k"])
    ratio = (nc / density_cm3) * math.exp(-epsilon_ev / thermal_ev)
    return 1.0 / (1.0 + ratio)


def integration_diagnostics(config: dict[str, Any]) -> list[dict[str, float | str]]:
    model = config["bulk_trap_model"]
    integration = config["energy_integration"]
    lower, upper = (float(value) for value in integration["domain_ev"])
    order = int(integration["order"])
    intervals = 32768
    tail_width = float(config["literature_input"]["tail"]["width_ev"])
    deep_width = float(config["literature_input"]["deep"]["width_ev"])
    deep_peak = float(
        config["literature_input"]["deep"]["peak_depth_below_ec_ev"]
    )
    profiles: dict[str, Callable[[float], float]] = {
        "tail": lambda energy: math.exp(-energy / tail_width),
        "deep": lambda energy: math.exp(-((energy - deep_peak) / deep_width) ** 2),
    }
    rows: list[dict[str, float | str]] = []
    for family, profile in profiles.items():
        for density in integration["probe_electron_densities_cm3"]:
            electron_density = float(density)
            integrand = lambda energy, profile=profile, electron_density=electron_density: (  # noqa: E731
                profile(energy) * occupancy(energy, electron_density, model)
            )
            candidate = gauss_integral(integrand, lower, upper, order)
            reference = simpson_integral(integrand, lower, upper, intervals)
            relative_error = abs(candidate - reference) / max(abs(reference), 1e-300)
            rows.append(
                {
                    "family": family,
                    "electron_density_cm3": electron_density,
                    "gauss_legendre_integral_ev": candidate,
                    "simpson_reference_integral_ev": reference,
                    "relative_error": relative_error,
                }
            )
    return rows


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    input_names = (
        "project_config",
        "experiments_config",
        "s00_report",
        "t01_baseline_config",
        "t02_a_config",
        "t02_c_config",
        "t02_c_report",
        "t02_c_check_report",
        "dit_formal_config",
        "dit_formal_report",
        "dit_formal_check_report",
        "literature_table",
    )
    paths = {name: ROOT / dependency[name] for name in input_names}
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing T03-P2 bulk-trap inputs: {missing}")

    project = load_json(paths["project_config"])
    experiments = load_json(paths["experiments_config"])
    s00 = load_json(paths["s00_report"])
    baseline = load_json(paths["t01_baseline_config"])
    t02_a = load_json(paths["t02_a_config"])
    t02_c = load_json(paths["t02_c_config"])
    t02_report = load_json(paths["t02_c_report"])
    t02_check = load_json(paths["t02_c_check_report"])
    dit_config = load_json(paths["dit_formal_config"])
    dit_report = load_json(paths["dit_formal_report"])
    dit_check = load_json(paths["dit_formal_check_report"])
    literature = load_csv(paths["literature_table"])
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p2_bulk_traps_contract_v1",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P2_BULK_TRAPS_CONTRACT_V1"
        and config.get("stage") == "T03-P2-BULK-TRAPS-CONTRACT"
        and config.get("parameter_group_id") == "P2"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )
    t02_completion = t02_report.get("t02_c_completion", {})
    add_check(
        checks,
        "dependencies:complete_t02_numerical_gate_passed",
        t02_report.get("status") == dependency["required_t02_c_status"]
        and t02_check.get("status") == dependency["required_t02_c_check_status"]
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"]
        and all(item.get("status") == "PASS" for item in t02_check.get("checks", [])),
        f"run={t02_report.get('status')} independent={t02_check.get('status')} gate={t02_completion.get('complete_t02_numerical_stage_gate')}",
    )
    dit_completion = dit_report.get("t03_p2_completion", {})
    add_check(
        checks,
        "dependencies:interface_dit_substage_passed_and_p2_partial",
        dit_report.get("status") == dependency["required_dit_formal_status"]
        and dit_check.get("status") == dependency["required_dit_formal_check_status"]
        and dit_check.get("independent_of_simulation_runner") is True
        and dit_completion.get("interface_dit_substage_complete")
        is dependency["require_interface_dit_substage_complete"]
        and (dit_completion.get("status") == "PARTIAL")
        is dependency["require_p2_still_partial"]
        and dit_completion.get("bulk_trap_contract_permitted_next") is True
        and dit_completion.get("bulk_tail_and_deep_traps_complete") is False,
        f"dit={dit_report.get('status')} independent={dit_check.get('status')} completion={dit_completion}",
    )
    add_check(
        checks,
        "dependencies:identities_and_hashes_match",
        dit_report.get("case_id") == dit_config.get("case_id")
        and dit_check.get("case_id") == dit_config.get("case_id")
        and t02_report.get("case_id") == t02_c.get("case_id"),
        f"t02={t02_c.get('case_id')} dit={dit_config.get('case_id')}",
    )
    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status") == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted") is False,
        json.dumps(s00.get("g0_decision", {}), sort_keys=True),
    )
    serialized = json.dumps(config, sort_keys=True)
    add_check(
        checks,
        "scope:igzo_2d_laptop_teaching_model_only",
        baseline["device"]["material"] == "IGZO"
        and project["baseline_devices"]["IGZO_TFT"]["polarity"] == "n"
        and project["tcad_track"]["dimension"] == "2D"
        and project["tcad_track"]["laptop_target"] is True
        and "SnO" not in serialized,
        config["scope"]["device"],
    )
    p2 = next(item for item in experiments["parameter_groups"] if item["id"] == "P2")
    add_check(
        checks,
        "group:p2_contains_tail_deep_and_dit",
        set(p2["variables"]) == {"N_tail", "N_deep", "D_it"}
        and int(p2["minimum_points"]) == 3,
        json.dumps(p2, sort_keys=True),
    )
    scope = config["scope"]
    add_check(
        checks,
        "scope:acceptor_tail_and_deep_only_with_donor_states_deferred",
        scope["included_states"]
        == [
            "acceptor-like conduction-band exponential tail NTA",
            "acceptor-like Gaussian deep state NGA",
        ]
        and scope["deferred_states"]
        == ["donor-like valence-band tail NTD", "donor-like Gaussian states NGD"],
        f"included={scope['included_states']} deferred={scope['deferred_states']}",
    )
    add_check(
        checks,
        "scope:one_bulk_family_only_and_interface_dit_zero",
        scope["one_active_family_per_future_scan"] is True
        and "bottom and top interface D_it = 0" in " ".join(scope["fixed_variables"])
        and "inactive bulk family peak density = 0" in " ".join(scope["fixed_variables"]),
        "one NTA/NGA family active; both interface D_it values fixed to zero",
    )
    required_fields = {
        "source_id",
        "doi",
        "title",
        "parameter_family",
        "parameter_symbol",
        "state_type",
        "distribution",
        "normalized_equation",
        "reported_scan_values_cm3_ev",
        "width_ev",
        "source_location",
        "evidence_level",
        "limitations",
    }
    add_check(
        checks,
        "source:two_primary_literature_rows_and_schema",
        len(literature) == 2
        and all(required_fields <= set(row) for row in literature)
        and len({row["source_id"] for row in literature}) == 2
        and all(row["doi"] == config["literature_input"]["doi"] for row in literature)
        and all(row["evidence_level"] == "E1" for row in literature),
        f"rows={len(literature)} ids={[row.get('source_id') for row in literature]}",
    )
    source_by_symbol = {row["parameter_symbol"]: row for row in literature}
    add_check(
        checks,
        "source:paper_device_and_project_mismatch_are_explicit",
        all(close(row["channel_length_um"], 10.0) for row in literature)
        and all(close(row["drain_bias_v"], 40.0) for row in literature)
        and all(row["gate_dielectric_context"] == "100 nm SiO2" for row in literature)
        and "symmetric dual gate" in config["literature_input"]["project_mismatch"]
        and "0.01 V drain bias" in config["literature_input"]["project_mismatch"],
        config["literature_input"]["project_mismatch"],
    )
    add_check(
        checks,
        "source:paper_nomenclature_conflict_is_preserved",
        source_by_symbol["NGA"]["state_type"] == "acceptor_like"
        and "caption says donor-like" in source_by_symbol["NGA"]["limitations"]
        and "equation/table" in config["literature_input"]["nomenclature_resolution"],
        config["literature_input"]["nomenclature_resolution"],
    )
    tail = config["literature_input"]["tail"]
    deep = config["literature_input"]["deep"]
    add_check(
        checks,
        "source:exact_tail_points_width_and_zero_control",
        tail["reported_values_cm3_ev"] == [1e18, 5e18, 1e19, 5e19]
        and tail["formal_sensitivity_values_cm3_ev"] == [1e18, 5e18, 5e19]
        and close(tail["regression_control_cm3_ev"], 0.0)
        and close(tail["width_ev"], 0.08)
        and source_by_symbol["NTA"]["reported_scan_values_cm3_ev"]
        == "1e18;5e18;1e19;5e19",
        json.dumps(tail, sort_keys=True),
    )
    add_check(
        checks,
        "source:exact_deep_points_width_peak_and_zero_control",
        deep["reported_values_cm3_ev"] == [1e16, 5e16, 1e17, 5e17]
        and deep["formal_sensitivity_values_cm3_ev"] == [1e16, 5e16, 5e17]
        and close(deep["regression_control_cm3_ev"], 0.0)
        and close(deep["width_ev"], 0.2)
        and close(deep["peak_depth_below_ec_ev"], 0.5)
        and source_by_symbol["NGA"]["reported_scan_values_cm3_ev"]
        == "1e16;5e16;1e17;5e17",
        json.dumps(deep, sort_keys=True),
    )
    model = config["bulk_trap_model"]
    add_check(
        checks,
        "model:energy_reference_and_dos_equations_are_frozen",
        model["energy_variable"] == "epsilon=Ec-E"
        and model["energy_domain_ev"] == [0.0, 3.0]
        and model["tail_dos_formula"] == "g_TA(epsilon)=NTA*exp(-epsilon/WTA)"
        and model["deep_dos_formula"]
        == "g_GA(epsilon)=NGA*exp(-((epsilon-EGA)/WGA)^2)"
        and model["dos_unit"] == "cm^-3 eV^-1",
        f"tail={model['tail_dos_formula']} deep={model['deep_dos_formula']}",
    )
    add_check(
        checks,
        "model:quasi_static_occupancy_and_units_are_closed",
        model["electron_occupancy_formula"]
        == "f_t(epsilon,n)=1/(1+(Nc/n)*exp(-epsilon/(k_B*T)))"
        and close(model["effective_conduction_dos_cm3"], 1e19)
        and close(model["temperature_k"], 300.0)
        and close(model["boltzmann_ev_per_k"], 8.617333262145e-5)
        and "C/cm^3" in model["charge_unit_derivation"],
        model["charge_unit_derivation"],
    )
    add_check(
        checks,
        "model:occupied_density_charge_sign_and_jacobian_are_explicit",
        model["physical_trapped_charge_density_formula"]
        == "rho_trap=-q*(n_TA+n_GA)"
        and model["devsim_poisson_node_source_formula"]
        == "PotentialNodeTrapCharge=-rho_trap=q*(n_TA+n_GA)"
        and model["occupancy_derivative_formula"] == "d_f_t/d_n=f_t*(1-f_t)/n"
        and "d_PotentialNodeTrapCharge/d_Electrons" in model["devsim_node_source_derivative_formula"]
        and model["poisson_insertion"]
        == "PotentialNodeCharge=q*(Electrons+OccupiedBulkTraps-NetDoping)",
        model["devsim_poisson_node_source_formula"],
    )
    add_check(
        checks,
        "model:zero_density_limit_exactly_restores_t02_c_charge",
        "NTA=NGA=0" in model["zero_density_limit"]
        and "exactly restores" in model["zero_density_limit"]
        and baseline["physics"]["equations"]["poisson"] == "active"
        and baseline["physics"]["equations"]["bulk_traps"] == "inactive",
        model["zero_density_limit"],
    )
    limitations = " ".join(model["limitations"])
    add_check(
        checks,
        "model:quasi_static_and_material_limitations_are_explicit",
        "teaching assumptions" in limitations
        and "no capture cross section or time constant" in limitations
        and "NTD and NGD are deferred" in limitations
        and "rather than project measurements" in limitations,
        limitations,
    )
    integration = config["energy_integration"]
    diagnostics = integration_diagnostics(config)
    maximum_error = max(float(row["relative_error"]) for row in diagnostics)
    add_check(
        checks,
        "integration:fixed_96_point_gauss_legendre_contract",
        integration["method"] == "fixed_order_gauss_legendre"
        and integration["order"] == 96
        and integration["domain_ev"] == [0.0, 3.0]
        and integration["reference_method_for_checker"]
        == "composite_simpson_32768_subintervals"
        and integration["probe_electron_densities_cm3"] == [1e12, 1e16, 1e20],
        json.dumps(integration, sort_keys=True),
    )
    add_check(
        checks,
        "integration:independent_reference_error_below_gate",
        len(diagnostics) == 6
        and maximum_error <= float(integration["maximum_relative_error_vs_reference"])
        and all(float(row["gauss_legendre_integral_ev"]) > 0 for row in diagnostics),
        f"cases={len(diagnostics)} max_relative_error={maximum_error:.6e}",
    )
    protocol = config["bias_protocol"]
    t02_protocol = t02_c["bias_protocol"]
    add_check(
        checks,
        "bias:exact_t02_c_top_primary_forward_grid",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and protocol["primary_negative_preconditioning_v"]
        == t02_protocol["primary_negative_preconditioning_v"]
        and primary_grid(protocol["primary_gate_grid"])
        == primary_grid(t02_protocol["primary_gate_grid"])
        and len(primary_grid(protocol["primary_gate_grid"])) == 31
        and protocol["primary_gate"] == "top_gate"
        and protocol["secondary_gate"] == "bottom_gate"
        and close(protocol["fixed_secondary_gate_v"], 0.0)
        and protocol["reverse_paths"] == [],
        f"grid={primary_grid(protocol['primary_gate_grid'])[0]}:{primary_grid(protocol['primary_gate_grid'])[-1]} points=31",
    )
    future = config["future_sensitivity"]
    add_check(
        checks,
        "future:isolated_three_points_plus_zero_controls",
        future["execution_order"]
        == [
            "tail scan with NGA=0 and both interface D_it values zero",
            "deep scan with NTA=0 and both interface D_it values zero",
        ]
        and future["tail_execution_values_cm3_ev"] == [0.0, 1e18, 5e18, 5e19]
        and future["deep_execution_values_cm3_ev"] == [0.0, 1e16, 5e16, 5e17]
        and future["formal_point_count_per_family"] == int(p2["minimum_points"])
        and future["control_point_count_per_family"] == 1,
        f"tail={future['tail_execution_values_cm3_ev']} deep={future['deep_execution_values_cm3_ev']}",
    )
    add_check(
        checks,
        "future:directional_hypotheses_registered_but_not_gates",
        future["directional_hypotheses_are_completion_gates"] is False
        and len(future["registered_hypotheses"]) == 2
        and "convergence" in future["reason_hypotheses_not_gates"],
        future["reason_hypotheses_not_gates"],
    )
    smoke = config["next_equation_smoke"]
    budget = smoke["resource_budget"]
    add_check(
        checks,
        "next_gate:minimum_three_case_equation_smoke_and_laptop_budget",
        smoke["case_id"] == "IGZO_T03_P2_BULK_TRAPS_EQUATION_SMOKE_V1"
        and smoke["stage"] == "T03-P2-BULK-TRAPS-EQUATION-SMOKE"
        and smoke["evidence_level_before_run"] == "E0"
        and smoke["permitted_only_after_contract_pass"] is True
        and [item["case_id"] for item in smoke["cases"]]
        == ["bulk_zero_control", "bulk_tail_reference", "bulk_deep_reference"]
        and budget["required_device_count"] == 3
        and budget["required_dc_solve_count_per_device"] == 7
        and budget["required_total_dc_solve_count"] == 21
        and budget["maximum_wall_seconds"] <= 180.0
        and budget["laptop_target"] is True,
        json.dumps(budget, sort_keys=True),
    )
    add_check(
        checks,
        "next_gate:integration_zero_limit_sign_convergence_and_response_checks",
        len(smoke["required_checks"]) == 6
        and any("reference integration" in item for item in smoke["required_checks"])
        and any("restores T02-C" in item for item in smoke["required_checks"])
        and any("opposite sign" in item for item in smoke["required_checks"])
        and any("current is conserved" in item for item in smoke["required_checks"])
        and any("nonzero persisted response" in item for item in smoke["required_checks"]),
        "; ".join(smoke["required_checks"]),
    )
    protocol = smoke["protocol"]
    add_check(
        checks,
        "next_gate:seven_solve_protocol_and_t02_c_anchor_are_frozen",
        close(protocol["source_v"], 0.0)
        and close(protocol["drain_v"], 0.01)
        and protocol["low_vds_values_v"] == [0.001, 0.005, 0.01]
        and close(protocol["fixed_bottom_gate_v"], 0.0)
        and protocol["top_gate_values_v"] == [0.05, 0.1]
        and protocol["final_common_state"]
        == {
            "source_v": 0.0,
            "drain_v": 0.01,
            "bottom_gate_v": 0.0,
            "top_gate_v": 0.1,
        }
        and protocol["t02_c_reference"]
        == {
            "family_id": "top_primary",
            "sweep_direction": "forward",
            "fixed_secondary_gate_v": 0.0,
            "primary_gate_v": 0.1,
            "vds_v": 0.01,
        }
        and "three-case DEVSIM equation smoke"
        in smoke["evidence_boundary"]["allowed_claim_after_run_and_independent_check"]
        and "formal NTA or NGA transfer sensitivity has completed"
        in smoke["evidence_boundary"]["prohibited_claims"]
        and "Only a passed equation smoke plus its independent"
        in smoke["evidence_boundary"]["next_gate"],
        json.dumps(protocol, sort_keys=True),
    )
    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:static_and_future_evidence_gates_are_frozen",
        acceptance["required_source_row_count"] == 2
        and acceptance["required_formal_points_per_family"] == 3
        and acceptance["required_control_points_per_family"] == 1
        and acceptance["require_exact_literature_points"] is True
        and acceptance["require_one_active_family_per_scan"] is True
        and acceptance["require_interface_dit_zero_during_bulk_scans"] is True
        and acceptance["require_zero_density_t02_c_regression"] is True
        and acceptance["require_analytic_electrons_derivative"] is True
        and acceptance["require_independent_persisted_evidence_check_after_future_run"]
        is True,
        json.dumps(acceptance, sort_keys=True),
    )
    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:paths_are_unique_and_stage_scoped",
        len(outputs) == len(set(outputs.values()))
        and all(
            "t03_p2_bulk_traps" in value or "p2_bulk_traps_equation_smoke" in value
            for value in outputs.values()
        ),
        f"outputs={len(outputs)} unique={len(set(outputs.values()))}",
    )
    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:contract_is_not_simulation_or_completed_p2",
        "statically checked" in boundary["allowed_claim"]
        and "DEVSIM simulation" in prohibited
        and "P2 or T03 has completed" in prohibited
        and "measured, extracted, fitted, or calibrated" in prohibited
        and "Only this contract PASS permits" in boundary["next_gate"],
        boundary["allowed_claim"],
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E3" if not failures else "E0",
        "config": {
            "path": str(config_path.relative_to(ROOT)),
            "sha256": sha256(config_path),
        },
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "checks": checks,
        "failures": failures,
        "integration_diagnostics": diagnostics,
        "maximum_integration_relative_error": maximum_error,
        "planned_future_sensitivity": {
            "tail_execution_values_cm3_ev": future["tail_execution_values_cm3_ev"],
            "deep_execution_values_cm3_ev": future["deep_execution_values_cm3_ev"],
            "formal_scan_run": False,
        },
        "planned_next_equation_smoke": {
            "case_ids": [item["case_id"] for item in smoke["cases"]],
            "device_count": budget["required_device_count"],
            "dc_solve_count": budget["required_total_dc_solve_count"],
            "simulation_run": False,
        },
        "evidence_boundary": boundary,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    config_path = args.config.resolve()
    report = check_contract(config_path)
    config = load_json(config_path)
    report_path = ROOT / config["outputs"]["contract_report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"T03_P2_BULK_TRAPS_CONTRACT_{report['status']} "
        f"checks={len(report['checks'])} simulation={report['simulation_status']} "
        f"max_integration_relative_error={report['maximum_integration_relative_error']:.6e} "
        f"report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P2_BULK_TRAPS_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
