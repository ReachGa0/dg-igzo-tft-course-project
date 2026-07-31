#!/usr/bin/env python3
"""Validate the frozen T02-C bidirectional dual-gate input contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t02_c_bidirectional.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1.0e-12, abs_tol=abs_tol)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def grid_values(spec: dict[str, Any]) -> list[float]:
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not close(start + intervals * step, stop):
        raise ValueError("T02-C primary-gate range is not an integral number of steps")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    input_paths = {
        "project": ROOT / "config/project.json",
        "s00_report": ROOT / dependency["s00_report"],
        "t01_baseline_config": ROOT / dependency["t01_baseline_config"],
        "t01_mesh_config": ROOT / dependency["t01_mesh_config"],
        "t01_extraction_config": ROOT / dependency["t01_extraction_config"],
        "t01_extraction_report": ROOT / dependency["t01_extraction_report"],
        "t01_extraction_check_report": ROOT / dependency["t01_extraction_check_report"],
        "t02_a_config": ROOT / dependency["t02_a_config"],
        "t02_a_report": ROOT / dependency["t02_a_report"],
        "t02_b_config": ROOT / dependency["t02_b_config"],
        "t02_b_contract_report": ROOT / dependency["t02_b_contract_report"],
        "t02_b_report": ROOT / dependency["t02_b_report"],
        "t02_b_check_report": ROOT / dependency["t02_b_check_report"],
    }
    loaded = {name: load_json(path) for name, path in input_paths.items()}
    project = loaded["project"]
    s00 = loaded["s00_report"]
    t01 = loaded["t01_baseline_config"]
    t01_extract_config = loaded["t01_extraction_config"]
    t01_extract_report = loaded["t01_extraction_report"]
    t01_extract_check = loaded["t01_extraction_check_report"]
    t02_a_config = loaded["t02_a_config"]
    t02_a_report = loaded["t02_a_report"]
    t02_b_config = loaded["t02_b_config"]
    t02_b_contract = loaded["t02_b_contract_report"]
    t02_b_report = loaded["t02_b_report"]
    t02_b_check = loaded["t02_b_check_report"]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t02_c_contract",
        config.get("schema_version") == 1
        and config.get("stage") == "T02-C"
        and config.get("case_id") == "IGZO_T02_DUAL_GATE_DD_C_BIDIRECTIONAL_V1"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )

    t01_completion = t01_extract_report.get("t01_completion", {})
    add_check(
        checks,
        "dependencies:t01_numerical_gate_closed",
        t01_extract_report.get("status") == dependency["required_t01_extraction_status"]
        and t01_extract_check.get("status") == dependency["required_t01_extraction_check_status"]
        and not t01_extract_check.get("failures")
        and t01_completion.get("complete_t01_numerical_stage_gate") == "PASS",
        f"run={t01_extract_report.get('status')} check={t01_extract_check.get('status')} completion={t01_completion}",
    )

    t02_b_completion = t02_b_report.get("t02_b_completion", {})
    add_check(
        checks,
        "dependencies:t02_b_gate_is_open",
        t02_a_report.get("status") == dependency["required_t02_a_status"]
        and t02_b_contract.get("contract_status") == dependency["required_t02_b_contract_status"]
        and t02_b_report.get("status") == dependency["required_t02_b_status"]
        and t02_b_check.get("status") == dependency["required_t02_b_check_status"]
        and not t02_b_check.get("failures")
        and t02_b_completion.get("t02_c_bidirectional_family_permitted_next")
        is dependency["require_t02_c_permitted_by_t02_b"]
        and t02_b_completion.get("t02_complete") is False,
        f"contract={t02_b_contract.get('contract_status')} run={t02_b_report.get('status')} check={t02_b_check.get('status')} next={t02_b_completion.get('t02_c_bidirectional_family_permitted_next')}",
    )

    add_check(
        checks,
        "dependencies:identities_and_hashes_match",
        t01_extract_report.get("case_id") == t01_extract_config.get("case_id")
        and t01_extract_check.get("case_id") == t01_extract_config.get("case_id")
        and t02_a_report.get("case_id") == t02_a_config.get("case_id")
        and t02_b_report.get("case_id") == t02_b_config.get("case_id")
        and t02_b_check.get("case_id") == t02_b_config.get("case_id")
        and t02_b_contract.get("config", {}).get("sha256") == sha256(input_paths["t02_b_config"]),
        f"t01={t01_extract_config.get('case_id')} t02a={t02_a_config.get('case_id')} t02b={t02_b_config.get('case_id')}",
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
        "2D n-IGZO" in config["scope"]["device"]
        and t01["device"]["material"] == "IGZO"
        and project["baseline_devices"]["IGZO_TFT"]["polarity"] == "n"
        and "SnO" not in serialized
        and project["tcad_track"]["dimension"] == "2D"
        and project["tcad_track"]["laptop_target"] is True,
        config["scope"]["device"],
    )

    enabled = t02_a_config["top_stack_contract"]["enabled_mode"]
    inheritance = config["inheritance"]
    add_check(
        checks,
        "topology:inherits_exact_symmetric_t02_a_stack",
        inheritance["require_exact_t02_a_enabled_topology"] is True
        and inheritance["required_mesh_level"] == t02_a_config["mesh"]["source_level"] == "interface_4x"
        and enabled["top_oxide_present"] is True
        and enabled["top_gate_present"] is True
        and enabled["top_oxide_material"] == "Al2O3"
        and close(enabled["top_oxide_thickness_nm"], 30.0)
        and close(enabled["top_oxide_relative_permittivity"], 6.8),
        json.dumps(enabled, sort_keys=True),
    )

    physics = t02_a_config["physics"]
    add_check(
        checks,
        "physics:frozen_electron_only_drift_diffusion",
        physics["active_equations"] == ["Poisson", "electron_continuity"]
        and physics["mobility_model"] == t01["physics"]["mobility_model"]
        and close(physics["temperature_k"], t01["physics"]["temperature_k"])
        and all(
            item in physics["inactive_models"]
            for item in ["bulk_traps", "contact_resistance_or_barrier", "ferroelectric_polarization"]
        ),
        json.dumps(physics, sort_keys=True),
    )

    protocol = config["bias_protocol"]
    acceptance = config["acceptance"]
    grid = grid_values(protocol["primary_gate_grid"])
    secondary = [float(value) for value in protocol["fixed_secondary_gate_values_v"]]
    families = protocol["families"]
    reverse = protocol["reverse_paths"]
    add_check(
        checks,
        "bias:frozen_low_vds_and_primary_grid",
        close(protocol["source_v"], 0.0)
        and close(protocol["drain_v"], 0.01)
        and protocol["low_vds_values_v"] == t02_b_config["bias_protocol"]["low_vds_values_v"]
        and grid[0] == -0.5
        and grid[-1] == 1.0
        and len(grid) == protocol["primary_gate_grid"]["point_count"] == 31,
        f"grid={grid[0]}:{protocol['primary_gate_grid']['step_v']}:{grid[-1]} points={len(grid)}",
    )

    add_check(
        checks,
        "bias:matched_top_and_bottom_primary_families",
        [item["family_id"] for item in families] == ["top_primary", "bottom_primary"]
        and families[0]["primary_gate"] == "top_gate"
        and families[0]["secondary_gate"] == "bottom_gate"
        and families[1]["primary_gate"] == "bottom_gate"
        and families[1]["secondary_gate"] == "top_gate"
        and all([float(value) for value in item["fixed_secondary_values_v"]] == secondary for item in families)
        and secondary == [-0.3, 0.0, 0.3],
        json.dumps(families, sort_keys=True),
    )

    add_check(
        checks,
        "bias:central_reverse_paths_only",
        reverse == [
            {"family_id": "top_primary", "fixed_secondary_v": 0.0},
            {"family_id": "bottom_primary", "fixed_secondary_v": 0.0},
        ]
        and "no hysteresis model is active" in config["extraction_methods"]["reverse_path_comparison"]["purpose"],
        json.dumps(reverse, sort_keys=True),
    )

    expected_forward_families = len(families) * len(secondary)
    expected_forward_points = expected_forward_families * len(grid)
    expected_reverse_points = len(reverse) * len(grid)
    expected_solves = 0
    for _family in families:
        for fixed_secondary in secondary:
            fixed_ramp_count = round(abs(fixed_secondary) / float(protocol["fixed_secondary_ramp_step_v"]))
            reverse_count = len(grid) - 1 if close(fixed_secondary, 0.0) else 0
            expected_solves += (
                2
                + len(protocol["low_vds_values_v"])
                + fixed_ramp_count
                + len(protocol["primary_negative_preconditioning_v"])
                + len(grid) - 1
                + reverse_count
            )
    add_check(
        checks,
        "acceptance:point_and_solve_counts_are_derived",
        expected_forward_families == acceptance["required_forward_family_count"] == 6
        and expected_forward_points == acceptance["required_forward_reported_point_count"] == 186
        and len(reverse) == acceptance["required_reverse_family_count"] == 2
        and expected_reverse_points == acceptance["required_reverse_reported_point_count"] == 62
        and expected_forward_points + expected_reverse_points == acceptance["required_total_reported_point_count"] == 248
        and expected_solves == acceptance["required_total_dc_solve_count"] == 318,
        f"forward={expected_forward_points} reverse={expected_reverse_points} solves={expected_solves}",
    )

    t01_vth = t01_extract_config["extraction_methods"]["constant_current_vth_proxy"]
    t02_vth = config["extraction_methods"]["constant_current_vth_proxy"]
    add_check(
        checks,
        "extraction:vth_criterion_exactly_reuses_t01",
        all(t02_vth[key] == t01_vth[key] for key in [
            "name",
            "criterion_formula",
            "criterion_prefactor_a",
            "expected_terminal_current_a",
            "expected_current_per_width_a_per_cm",
        ])
        and "primary-gate-voltage" in t02_vth["interpolation"],
        json.dumps(t02_vth, sort_keys=True),
    )

    extraction = config["extraction_methods"]
    add_check(
        checks,
        "extraction:limited_delta_vth_gm_and_coupling_are_predefined",
        close(extraction["delta_vth_proxy"]["reference_secondary_gate_v"], 0.0)
        and close(extraction["gm_proxy"]["evaluation_overdrive_v"], 0.2)
        and extraction["gm_proxy"]["reported_units"] == ["S/cm", "S terminal"]
        and extraction["coupling_slope_proxy"]["reported_unit"] == "V/V"
        and "ordinary_least_squares" in extraction["coupling_slope_proxy"]["name"],
        json.dumps(extraction, sort_keys=True),
    )

    add_check(
        checks,
        "acceptance:conservation_monotonicity_and_path_limits",
        0.0 < acceptance["maximum_relative_terminal_current_imbalance"] <= 1e-5
        and acceptance["require_positive_drain_and_negative_source_current"] is True
        and acceptance["require_strict_primary_gate_current_increase"] is True
        and acceptance["require_strict_secondary_gate_current_ordering"] is True
        and acceptance["maximum_monotonic_relative_current_drop"] <= 1e-6
        and acceptance["maximum_forward_reverse_relative_current_difference"] <= 1e-5
        and acceptance["maximum_forward_reverse_vth_difference_v"] <= 1e-3,
        json.dumps(acceptance, sort_keys=True),
    )

    add_check(
        checks,
        "acceptance:symmetry_and_coupling_limits",
        acceptance["maximum_reciprocal_top_bottom_relative_current_difference"] <= 1e-5
        and acceptance["maximum_reciprocal_top_bottom_center_potential_difference_v"] <= 1e-5
        and acceptance["maximum_reciprocal_top_bottom_center_density_relative_difference"] <= 1e-5
        and acceptance["maximum_reciprocal_top_bottom_vth_difference_v"] <= 1e-3
        and 0.0 < acceptance["minimum_absolute_coupling_slope_v_per_v"]
        < acceptance["maximum_absolute_coupling_slope_v_per_v"]
        and acceptance["minimum_coupling_fit_r_squared"] >= 0.99,
        json.dumps(acceptance, sort_keys=True),
    )

    state_points = protocol["state_points"]
    add_check(
        checks,
        "state:six_representative_reused_forward_states",
        [item["state_id"] for item in state_points] == acceptance["required_state_ids"]
        and len(state_points) == 6
        and all(item["source_family"] in acceptance["required_family_ids"] for item in state_points)
        and acceptance["required_vtk_file_count_per_state"] == 6,
        f"states={[item['state_id'] for item in state_points]}",
    )

    state_contract = config["state_output_contract"]
    add_check(
        checks,
        "state:potential_density_current_density_contract",
        state_contract["potential"]["unit"] == "V"
        and state_contract["electron_density"]["unit"] == "cm^-3"
        and state_contract["electron_current_density"]["unit"] == "A/cm^2"
        and "element_from_edge_model" in state_contract["electron_current_density"]["source_model"]
        and set(acceptance["required_state_fields"]) == {
            "potential_v",
            "electron_density_cm3",
            "electron_current_density_x_a_per_cm2",
            "electron_current_density_y_a_per_cm2",
            "electron_current_density_magnitude_a_per_cm2",
        },
        json.dumps(state_contract, sort_keys=True),
    )

    add_check(
        checks,
        "acceptance:exact_enabled_topology_contract",
        acceptance["required_regions"] == t02_a_config["acceptance"]["required_enabled_regions"]
        and acceptance["required_contacts"] == t02_a_config["acceptance"]["required_enabled_contacts"]
        and acceptance["required_interfaces"] == ["bottom_oxide_channel", "channel_top_oxide"]
        and acceptance["require_exact_t02_a_topology_count_match"] is True,
        f"regions={acceptance['required_regions']} contacts={acceptance['required_contacts']}",
    )

    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:separate_raw_processed_reports_and_two_figures",
        outputs["run_directory"].startswith("results/tcad/t02_dual_gate/")
        and outputs["family_csv"].startswith("results/tables/")
        and outputs["metric_csv"].startswith("results/tables/")
        and outputs["report"].startswith("results/reports/")
        and outputs["check_report"].startswith("results/reports/")
        and outputs["family_figure_png"].startswith("report/assets/")
        and outputs["state_figure_png"].startswith("report/assets/")
        and len(set(outputs.values())) == len(outputs),
        json.dumps(outputs, sort_keys=True),
    )

    boundary = config["evidence_boundary"]
    add_check(
        checks,
        "scope:evidence_boundary_requires_independent_pass",
        "frozen E2 teaching model" in boundary["allowed_claim"]
        and "independent persisted-evidence PASS" in boundary["next_gate"]
        and any("experimentally validated" in claim for claim in boundary["prohibited_claims"])
        and "T03 parameter scans" in config["scope"]["prohibited_work"],
        boundary["next_gate"],
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "contract_evidence_level": config["contract_evidence_level_after_check"] if not failures else "E0",
        "checks": checks,
        "failures": failures,
        "derived_counts": {
            "primary_gate_point_count": len(grid),
            "forward_family_count": expected_forward_families,
            "forward_reported_point_count": expected_forward_points,
            "reverse_family_count": len(reverse),
            "reverse_reported_point_count": expected_reverse_points,
            "total_reported_point_count": expected_forward_points + expected_reverse_points,
            "total_dc_solve_count": expected_solves,
        },
        "config": {"path": str(config_path.relative_to(ROOT)), "sha256": sha256(config_path)},
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in input_paths.items()
        },
        "outputs": config["outputs"],
        "evidence_boundary": boundary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    try:
        report = check_contract(config_path)
    except Exception as error:  # noqa: BLE001
        print(f"T02_C_CONTRACT_ERROR {error}", file=sys.stderr)
        return 1

    config = load_json(config_path)
    report_path = ROOT / config["outputs"]["contract_report"]
    if not args.check_only:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"T02_C_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(f"T02_C_CONTRACT_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
