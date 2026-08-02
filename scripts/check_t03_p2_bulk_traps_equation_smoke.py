#!/usr/bin/env python3
"""Independently validate persisted T03-P2 bulk-trap equation-smoke evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any, Callable


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_bulk_traps.json"
ELEMENTARY_CHARGE_C = 1.602176634e-19
CASE_FIELDS = [
    "case_id", "nta_cm3_ev", "nga_cm3_ev", "active_family", "solve_mode",
    "source_v", "drain_v", "vbg_v", "vtg_v", "mesh_level",
    "node_count_with_interface_duplicates", "element_count", "dc_solve_count",
    "all_dc_solves_converged", "source_current_a_per_cm", "drain_current_a_per_cm",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "center_tail_occupied_density_cm3",
    "center_deep_occupied_density_cm3", "center_occupied_bulk_traps_cm3",
    "center_occupied_bulk_traps_derivative", "center_physical_trap_charge_c_per_cm3",
    "center_poisson_trap_source_c_per_cm3", "minimum_occupied_bulk_traps_cm3",
    "maximum_occupied_bulk_traps_cm3", "minimum_occupied_bulk_traps_derivative",
    "maximum_occupied_bulk_traps_derivative", "wall_seconds",
]
INTEGRATION_FIELDS = [
    "family", "electron_density_cm3", "gauss_legendre_integral_ev",
    "simpson_reference_integral_ev", "relative_error", "order",
]
STATE_FIELDS = [
    "case_id", "nta_cm3_ev", "nga_cm3_ev", "active_family", "solve_mode",
    "source_v", "drain_v", "vbg_v", "vtg_v", "region", "x_cm", "y_cm",
    "x_um", "y_nm", "potential_v", "electron_density_cm3",
    "tail_occupied_density_cm3", "deep_occupied_density_cm3",
    "occupied_bulk_traps_cm3", "occupied_bulk_traps_derivative",
    "physical_trap_charge_c_per_cm3", "poisson_trap_source_c_per_cm3",
    "potential_node_charge_c_per_cm3",
]


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


def close(left: float, right: float, *, rel_tol: float = 1e-9, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), 1e-300)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def gauss_legendre_nodes_weights(order: int) -> tuple[list[float], list[float]]:
    nodes = [0.0] * order
    weights = [0.0] * order
    for index in range((order + 1) // 2):
        root = math.cos(math.pi * (index + 0.75) / (order + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, root
            for degree in range(2, order + 1):
                p0, p1 = p1, ((2.0 * degree - 1.0) * root * p1 - (degree - 1.0) * p0) / degree
            derivative = order * (root * p1 - p0) / (root * root - 1.0)
            updated = root - p1 / derivative
            if abs(updated - root) <= 2e-16:
                root = updated
                break
            root = updated
        else:
            raise RuntimeError("Gauss-Legendre root iteration did not converge")
        p0, p1 = 1.0, root
        for degree in range(2, order + 1):
            p0, p1 = p1, ((2.0 * degree - 1.0) * root * p1 - (degree - 1.0) * p0) / degree
        derivative = order * (root * p1 - p0) / (root * root - 1.0)
        weight = 2.0 / ((1.0 - root * root) * derivative * derivative)
        nodes[index] = -root
        nodes[order - index - 1] = root
        weights[index] = weight
        weights[order - index - 1] = weight
    return nodes, weights


def energy_quadrature(config: dict[str, Any]) -> list[tuple[float, float]]:
    lower, upper = (float(value) for value in config["energy_integration"]["domain_ev"])
    nodes, weights = gauss_legendre_nodes_weights(int(config["energy_integration"]["order"]))
    midpoint = 0.5 * (lower + upper)
    half_width = 0.5 * (upper - lower)
    return [(midpoint + half_width * node, half_width * weight) for node, weight in zip(nodes, weights, strict=True)]


def simpson_integral(function: Callable[[float], float], lower: float, upper: float, intervals: int) -> float:
    step = (upper - lower) / intervals
    odd_sum = math.fsum(function(lower + index * step) for index in range(1, intervals, 2))
    even_sum = math.fsum(function(lower + index * step) for index in range(2, intervals, 2))
    return step * (function(lower) + function(upper) + 4.0 * odd_sum + 2.0 * even_sum) / 3.0


def occupancy(epsilon_ev: float, electron_density_cm3: float, nc: float, thermal_ev: float) -> float:
    return electron_density_cm3 / (electron_density_cm3 + nc * math.exp(-epsilon_ev / thermal_ev))


def expected_integrals(config: dict[str, Any], electron_density_cm3: float) -> dict[str, tuple[float, float]]:
    model = config["bulk_trap_model"]
    integration = config["energy_integration"]
    lower, upper = (float(value) for value in integration["domain_ev"])
    nc = float(model["effective_conduction_dos_cm3"])
    thermal = float(model["boltzmann_ev_per_k"]) * float(model["temperature_k"])
    tail_width = float(config["literature_input"]["tail"]["width_ev"])
    deep_width = float(config["literature_input"]["deep"]["width_ev"])
    deep_peak = float(config["literature_input"]["deep"]["peak_depth_below_ec_ev"])
    quadrature = energy_quadrature(config)
    profiles = {
        "tail": lambda epsilon: math.exp(-epsilon / tail_width),
        "deep": lambda epsilon: math.exp(-((epsilon - deep_peak) / deep_width) ** 2),
    }
    result: dict[str, tuple[float, float]] = {}
    for family, profile in profiles.items():
        integrand = lambda epsilon, profile=profile: profile(epsilon) * occupancy(
            epsilon, float(electron_density_cm3), nc, thermal
        )
        gauss = math.fsum(weight * integrand(epsilon) for epsilon, weight in quadrature)
        reference = simpson_integral(integrand, lower, upper, 32768)
        result[family] = (gauss, reference)
    return result


def expected_node_values(
    config: dict[str, Any],
    case: dict[str, str],
    electron_density_cm3: float,
    quadrature: list[tuple[float, float]],
) -> dict[str, float]:
    nta = float(case["nta_cm3_ev"])
    nga = float(case["nga_cm3_ev"])
    model = config["bulk_trap_model"]
    nc = float(model["effective_conduction_dos_cm3"])
    thermal = float(model["boltzmann_ev_per_k"]) * float(model["temperature_k"])
    tail_width = float(config["literature_input"]["tail"]["width_ev"])
    deep_width = float(config["literature_input"]["deep"]["width_ev"])
    deep_peak = float(config["literature_input"]["deep"]["peak_depth_below_ec_ev"])
    tail_integral = math.fsum(
        weight * math.exp(-epsilon / tail_width) * occupancy(epsilon, electron_density_cm3, nc, thermal)
        for epsilon, weight in quadrature
    )
    deep_integral = math.fsum(
        weight * math.exp(-((epsilon - deep_peak) / deep_width) ** 2)
        * occupancy(epsilon, electron_density_cm3, nc, thermal)
        for epsilon, weight in quadrature
    )
    tail = nta * tail_integral
    deep = nga * deep_integral
    total = tail + deep
    derivative_tail = 0.0
    derivative_deep = 0.0
    for epsilon, weight in quadrature:
        exponential = nc * math.exp(-epsilon / thermal)
        derivative_factor = exponential / ((electron_density_cm3 + exponential) ** 2)
        derivative_tail += weight * math.exp(-epsilon / tail_width) * derivative_factor
        derivative_deep += weight * math.exp(-((epsilon - deep_peak) / deep_width) ** 2) * derivative_factor
    derivative = nta * derivative_tail + nga * derivative_deep
    charge = -ELEMENTARY_CHARGE_C * total
    source = ELEMENTARY_CHARGE_C * total
    net_doping = 1.0e16
    node_charge = ELEMENTARY_CHARGE_C * (electron_density_cm3 + total - net_doping)
    return {
        "tail": tail,
        "deep": deep,
        "total": total,
        "derivative": derivative,
        "physical_charge": charge,
        "poisson_source": source,
        "potential_node_charge": node_charge,
    }


def center_row(rows: list[dict[str, str]]) -> dict[str, str]:
    target_x = 0.0005
    target_y = 3.0e-6 + 1.2e-6
    return min(
        (row for row in rows if row["region"] == "channel"),
        key=lambda row: (float(row["x_cm"]) - target_x) ** 2 + (float(row["y_cm"]) - target_y) ** 2,
    )


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report = load_json(ROOT / outputs["future_report"])
    contract = load_json(ROOT / outputs["contract_report"])
    case_rows, case_fields = load_csv(ROOT / outputs["future_case_summary_csv"])
    integration_rows, integration_fields = load_csv(ROOT / outputs["future_integration_samples_csv"])
    state_rows, state_fields = load_csv(ROOT / outputs["future_state_nodes_csv"])
    solver_log = load_json(ROOT / outputs["future_solver_log"])
    snapshot = load_json(ROOT / outputs["future_config_snapshot"])
    checks: list[dict[str, Any]] = []
    expected_cases = [item["case_id"] for item in config["next_equation_smoke"]["cases"]]
    quadrature = energy_quadrature(config)
    by_case = {row["case_id"]: row for row in case_rows}
    states_by_case = {case_id: [row for row in state_rows if row["case_id"] == case_id] for case_id in expected_cases}

    add_check(
        checks,
        "identity:report_config_contract_and_stage_match",
        report["case_id"] == config["next_equation_smoke"]["case_id"]
        and report["stage"] == config["next_equation_smoke"]["stage"]
        and report["stage"] == "T03-P2-BULK-TRAPS-EQUATION-SMOKE"
        and report["formal_sensitivity_run"] is False
        and report["contract_report"]["status"] == "PASS"
        and report["contract_report"]["sha256"] == sha256(ROOT / report["contract_report"]["path"])
        and contract["contract_status"] == "PASS",
        f"case={report.get('case_id')} stage={report.get('stage')} contract={contract.get('contract_status')}",
    )
    add_check(
        checks,
        "inputs:snapshot_hashes_match",
        snapshot["case_id"] == report["case_id"]
        and snapshot["stage"] == report["stage"]
        and snapshot["formal_sensitivity_run"] is False
        and all(item["sha256"] == sha256(ROOT / item["path"]) for item in snapshot["inputs"].values()),
        f"inputs={len(snapshot.get('inputs', {}))}",
    )
    add_check(
        checks,
        "outputs:headers_case_order_and_counts_match_contract",
        case_fields == CASE_FIELDS
        and integration_fields == INTEGRATION_FIELDS
        and state_fields == STATE_FIELDS
        and [row["case_id"] for row in case_rows] == expected_cases
        and len(case_rows) == 3
        and len(integration_rows) == 6
        and len(state_rows) == 3 * 2419,
        f"cases={len(case_rows)} integration_rows={len(integration_rows)} state_rows={len(state_rows)}",
    )
    add_check(
        checks,
        "solver:21_records_and_all_cases_converged",
        solver_log["total_dc_solve_count"] == 21
        and sum(len(item["records"]) for item in solver_log["runs"]) == 21
        and all(bool(record["converged"]) for item in solver_log["runs"] for record in item["records"])
        and all(row["all_dc_solves_converged"] == "True" and int(row["dc_solve_count"]) == 7 for row in case_rows),
        f"solves={solver_log.get('total_dc_solve_count')} runs={len(solver_log.get('runs', []))}",
    )
    add_check(
        checks,
        "scope:isolated_nta_nga_and_zero_interface_dit",
        [(float(row["nta_cm3_ev"]), float(row["nga_cm3_ev"])) for row in case_rows]
        == [(0.0, 0.0), (5e18, 0.0), (0.0, 5e16)]
        and all(row["bottom_interface_equations"] == ["PotentialEquation"] and row["top_interface_equations"] == ["PotentialEquation"] for row in report["case_summaries"]),
        str([(row["nta_cm3_ev"], row["nga_cm3_ev"]) for row in case_rows]),
    )
    topology_valid = all(
        row["node_count_with_interface_duplicates"] == "2419"
        and row["element_count"] == "4480"
        and row["mesh_level"] == "interface_4x"
        for row in case_rows
    )
    model_valid = all(
        {"BulkTrapTailOccupiedDensity", "BulkTrapDeepOccupiedDensity", "OccupiedBulkTraps", "OccupiedBulkTrapsDerivative", "PhysicalBulkTrapCharge", "PotentialNodeTrapCharge", "PotentialNodeCharge", "PotentialNodeCharge:Electrons"}
        <= set(summary["channel_node_models"])
        and summary["channel_equations"] == ["ElectronContinuityEquation", "PotentialEquation"]
        for summary in report["case_summaries"]
    )
    add_check(checks, "topology_and_bulk_models_match_enabled_t02_stack", topology_valid and model_valid, f"topology={topology_valid} models={model_valid}")

    integration_recomputed = []
    integration_valid = True
    for row in integration_rows:
        expected = expected_integrals(config, float(row["electron_density_cm3"]))[row["family"]]
        integration_recomputed.append({"family": row["family"], "electron_density_cm3": float(row["electron_density_cm3"]), "gauss": expected[0], "simpson": expected[1]})
        integration_valid = integration_valid and int(row["order"]) == 96
        integration_valid = integration_valid and close(float(row["gauss_legendre_integral_ev"]), expected[0], rel_tol=1e-11, abs_tol=1e-14)
        integration_valid = integration_valid and close(float(row["simpson_reference_integral_ev"]), expected[1], rel_tol=1e-11, abs_tol=1e-14)
        integration_valid = integration_valid and float(row["relative_error"]) <= float(config["energy_integration"]["maximum_relative_error_vs_reference"])
    add_check(checks, "integration:independent_96_point_recomputation_matches_persisted_samples", integration_valid, json.dumps(integration_recomputed, sort_keys=True))

    node_recomputed = True
    max_node_error = 0.0
    max_derivative_error = 0.0
    max_charge_error = 0.0
    for case_id in expected_cases:
        case = by_case[case_id]
        for row in states_by_case[case_id]:
            if row["region"] != "channel":
                continue
            electron_density = float(row["electron_density_cm3"])
            expected = expected_node_values(config, case, electron_density, quadrature)
            for field, key in (
                ("tail_occupied_density_cm3", "tail"),
                ("deep_occupied_density_cm3", "deep"),
                ("occupied_bulk_traps_cm3", "total"),
                ("occupied_bulk_traps_derivative", "derivative"),
                ("physical_trap_charge_c_per_cm3", "physical_charge"),
                ("poisson_trap_source_c_per_cm3", "poisson_source"),
                ("potential_node_charge_c_per_cm3", "potential_node_charge"),
            ):
                observed = float(row[field])
                expected_value = expected[key]
                error = relative_difference(observed, expected_value)
                if field == "occupied_bulk_traps_derivative":
                    max_derivative_error = max(max_derivative_error, error)
                elif field == "potential_node_charge_c_per_cm3":
                    max_charge_error = max(max_charge_error, error)
                else:
                    max_node_error = max(max_node_error, error)
                if not close(observed, expected_value, rel_tol=2e-8, abs_tol=1e-8):
                    node_recomputed = False
    add_check(checks, "nodes:independent_energy_integral_charge_and_derivative_recompute", node_recomputed, f"max_density_relative_error={max_node_error:.6e} max_derivative_relative_error={max_derivative_error:.6e} max_charge_relative_error={max_charge_error:.6e}")
    all_channel = [row for rows in states_by_case.values() for row in rows if row["region"] == "channel"]
    finite_signs = all(
        math.isfinite(float(row["electron_density_cm3"]))
        and math.isfinite(float(row["occupied_bulk_traps_cm3"]))
        and math.isfinite(float(row["occupied_bulk_traps_derivative"]))
        and float(row["electron_density_cm3"]) > 0.0
        and float(row["occupied_bulk_traps_cm3"]) >= -1e-8
        and float(row["occupied_bulk_traps_derivative"]) >= -1e-12
        and float(row["physical_trap_charge_c_per_cm3"]) <= 1e-8
        and float(row["poisson_trap_source_c_per_cm3"]) >= -1e-8
        for row in all_channel
    )
    add_check(checks, "nodes:finite_nonnegative_occupancy_and_opposite_charge_sign", finite_signs, f"channel_rows={len(all_channel)}")

    zero_state = states_by_case[expected_cases[0]]
    zero_models = all(
        abs(float(row["tail_occupied_density_cm3"])) <= 1e-8
        and abs(float(row["deep_occupied_density_cm3"])) <= 1e-8
        and abs(float(row["occupied_bulk_traps_cm3"])) <= 1e-8
        and abs(float(row["occupied_bulk_traps_derivative"])) <= 1e-12
        for row in zero_state
        if row["region"] == "channel"
    )
    add_check(checks, "zero_limit:all_trap_node_models_are_zero", zero_models, "zero control channel diagnostics")
    zero_summary = by_case[expected_cases[0]]
    t02_rows, _ = load_csv(ROOT / "results/tables/tcad_t02_c_bidirectional_families.csv")
    reference_spec = config["next_equation_smoke"]["protocol"]["t02_c_reference"]
    t02_reference = next(
        row for row in t02_rows
        if row["family_id"] == reference_spec["family_id"]
        and row["sweep_direction"] == reference_spec["sweep_direction"]
        and close(float(row["fixed_secondary_gate_v"]), reference_spec["fixed_secondary_gate_v"])
        and close(float(row["primary_gate_v"]), reference_spec["primary_gate_v"])
        and close(float(row["vds_v"]), reference_spec["vds_v"])
    )
    t02_differences = {
        "current_relative": relative_difference(abs(float(zero_summary["drain_current_a_per_cm"])), abs(float(t02_reference["drain_current_a_per_cm"]))),
        "center_potential_v": abs(float(zero_summary["center_channel_potential_v"]) - float(t02_reference["center_channel_potential_v"])),
        "center_density_relative": relative_difference(float(zero_summary["center_channel_electron_density_cm3"]), float(t02_reference["center_channel_electron_density_cm3"])),
    }
    add_check(checks, "zero_limit:T02_C_common_bias_current_and_state_regression", t02_differences["current_relative"] <= 1e-6 and t02_differences["center_potential_v"] <= 1e-7 and t02_differences["center_density_relative"] <= 1e-6, json.dumps(t02_differences, sort_keys=True))
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in case_rows)
    add_check(checks, "transport:all_cases_terminal_current_conservation", max_imbalance <= 1e-5, f"maximum_relative_imbalance={max_imbalance:.6e}")
    responses = []
    for case_id in expected_cases[1:]:
        case_summary = by_case[case_id]
        responses.append({
            "case_id": case_id,
            "current_relative": relative_difference(abs(float(case_summary["drain_current_a_per_cm"])), abs(float(zero_summary["drain_current_a_per_cm"]))),
            "density_relative": relative_difference(float(case_summary["center_channel_electron_density_cm3"]), float(zero_summary["center_channel_electron_density_cm3"])),
        })
    add_check(checks, "response:tail_and_deep_cases_have_nonzero_persisted_response", all(max(item["current_relative"], item["density_relative"]) >= 1e-6 for item in responses), json.dumps(responses, sort_keys=True))
    center_consistency = all(
        close(float(summary["center_channel_potential_v"]), float(center_row(states_by_case[summary["case_id"]])["potential_v"]), rel_tol=1e-9, abs_tol=1e-12)
        and close(float(summary["center_occupied_bulk_traps_cm3"]), float(center_row(states_by_case[summary["case_id"]])["occupied_bulk_traps_cm3"]), rel_tol=1e-9, abs_tol=1e-8)
        for summary in report["case_summaries"]
    )
    add_check(checks, "outputs:case_summaries_match_persisted_center_states", center_consistency, "summary/state center rows")
    artifacts = {
        "config_snapshot": ROOT / outputs["future_config_snapshot"],
        "solver_log": ROOT / outputs["future_solver_log"],
        "case_summary_csv": ROOT / outputs["future_case_summary_csv"],
        "integration_samples_csv": ROOT / outputs["future_integration_samples_csv"],
        "state_nodes_csv": ROOT / outputs["future_state_nodes_csv"],
    }
    artifacts_valid = all(
        path.is_file()
        and report["artifacts"][name]["sha256"] == sha256(path)
        and report["artifacts"][name]["path"] == str(path.relative_to(ROOT))
        for name, path in artifacts.items()
    )
    add_check(checks, "artifacts:all_hashes_and_paths_match_report", artifacts_valid, f"artifacts={len(artifacts)}")
    boundary = report["evidence_boundary"]
    add_check(checks, "boundary:formal_bulk_scan_and_complete_p2_remain_closed", report["t03_p2_completion"]["bulk_tail_and_deep_traps_complete"] is False and report["t03_p2_completion"]["formal_bulk_sensitivity_complete"] is False and "formal NTA or NGA transfer sensitivity has completed" in boundary["prohibited_claims"], boundary["next_gate"])

    failures = [item for item in checks if item["status"] == "FAIL"]
    independent = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": report["case_id"],
        "stage": report["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_simulation_runner": True,
        "checks": checks,
        "failures": failures,
        "recomputed_diagnostics": {
            "t02_c_zero_control_reproduction": t02_differences,
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_node_density_relative_error": max_node_error,
            "maximum_derivative_relative_error": max_derivative_error,
            "maximum_potential_node_charge_relative_error": max_charge_error,
            "nonzero_responses": responses,
        },
        "artifact_hashes": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for name, path in artifacts.items()
        },
    }
    check_path = ROOT / outputs["future_check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(json.dumps(independent, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(f"T03_P2_BULK_TRAPS_EQUATION_SMOKE_CHECK_{independent['status']} checks={len(checks)} report={check_path}")
    for failure in failures:
        print(f"T03_P2_BULK_TRAPS_EQUATION_SMOKE_CHECK_ERROR {failure['name']}: {failure['detail']}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
