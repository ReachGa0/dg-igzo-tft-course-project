#!/usr/bin/env python3
"""Validate the frozen T03-P4-L channel-length sensitivity contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p4_channel_length.json"


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


def primary_grid(spec: dict[str, Any]) -> list[float]:
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not close(start + intervals * step, stop):
        raise ValueError("T03-P4-L primary-gate range is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    input_paths = {
        name: ROOT / dependency[name]
        for name in (
            "project_config",
            "experiments_config",
            "s00_report",
            "t01_baseline_config",
            "t01_mesh_config",
            "t02_a_config",
            "t02_a_report",
            "t02_c_config",
            "t02_c_contract_report",
            "t02_c_report",
            "t02_c_check_report",
        )
    }
    loaded = {name: load_json(path) for name, path in input_paths.items()}
    project = loaded["project_config"]
    experiments = loaded["experiments_config"]
    s00 = loaded["s00_report"]
    baseline = loaded["t01_baseline_config"]
    mesh = loaded["t01_mesh_config"]
    t02_a = loaded["t02_a_config"]
    t02_a_report = loaded["t02_a_report"]
    t02_c_config = loaded["t02_c_config"]
    t02_c_contract = loaded["t02_c_contract_report"]
    t02_c_report = loaded["t02_c_report"]
    t02_c_check = loaded["t02_c_check_report"]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p4_l_contract",
        config.get("schema_version") == 2
        and config.get("case_id") == "IGZO_T03_P4_CHANNEL_LENGTH_V2"
        and config.get("stage") == "T03-P4-L"
        and config.get("parameter_group_id") == "P4"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')} group={config.get('parameter_group_id')}",
    )

    remediation = config["remediation"]
    prior_paths = {
        "config": ROOT / remediation["prior_config"],
        "contract": ROOT / remediation["prior_contract_report"],
        "report": ROOT / remediation["prior_run_report"],
        "run_directory": ROOT / remediation["prior_run_directory"],
    }
    prior_config = load_json(prior_paths["config"])
    prior_contract = load_json(prior_paths["contract"])
    prior_report = load_json(prior_paths["report"])
    prior_snapshot = load_json(prior_paths["run_directory"] / "input_snapshot.json")
    add_check(
        checks,
        "remediation:v1_failure_is_preserved",
        remediation["protocol_version"] == 2
        and remediation["prior_case_id"] == "IGZO_T03_P4_CHANNEL_LENGTH_V1"
        and remediation["prior_status"] == "FAIL"
        and prior_config.get("case_id") == remediation["prior_case_id"]
        and prior_contract.get("case_id") == remediation["prior_case_id"]
        and prior_contract.get("contract_status") == "PASS"
        and prior_contract.get("config", {}).get("sha256")
        == sha256(prior_paths["config"])
        and prior_report.get("case_id") == remediation["prior_case_id"]
        and prior_report.get("status") == "FAIL"
        and prior_report.get("failures") == remediation["prior_failed_checks"]
        and prior_snapshot.get("inputs", {}).get("t03_config", {}).get("sha256")
        == sha256(prior_paths["config"])
        and prior_paths["run_directory"].is_dir()
        and (prior_paths["run_directory"] / "solver_log.json").is_file()
        and (prior_paths["run_directory"] / "state_manifest.json").is_file(),
        f"prior_status={prior_report.get('status')} failures={prior_report.get('failures')}",
    )

    unchanged_sections = (
        "dependencies",
        "sensitivity",
        "inheritance",
        "bias_protocol",
        "state_output_contract",
        "resource_budget",
        "outputs",
    )
    add_check(
        checks,
        "remediation:simulation_protocol_is_unchanged_from_v1",
        all(config[section] == prior_config[section] for section in unchanged_sections)
        and config["scope"]["changed_variable"]
        == prior_config["scope"]["changed_variable"]
        and config["scope"]["fixed_variables"]
        == prior_config["scope"]["fixed_variables"]
        and config["extraction_methods"]["constant_current_vth_proxy"]
        == prior_config["extraction_methods"]["constant_current_vth_proxy"]
        and config["extraction_methods"]["gm_proxy"]
        == prior_config["extraction_methods"]["gm_proxy"]
        and config["extraction_methods"]["on_state_current_proxy"]
        == prior_config["extraction_methods"]["on_state_current_proxy"]
        and all(
            config["extraction_methods"]["length_scaling"][key]
            == prior_config["extraction_methods"]["length_scaling"][key]
            for key in (
                "current_product",
                "gm_product",
                "log_slope",
                "relative_spread_definition",
            )
        ),
        "V2 changes acceptance semantics and audit metadata, not simulation inputs or extraction formulas",
    )

    t02_completion = t02_c_report.get("t02_c_completion", {})
    t02_checks = t02_c_check.get("checks", [])
    add_check(
        checks,
        "dependencies:complete_t02_gate_passed",
        t02_c_contract.get("contract_status") == "PASS"
        and t02_c_report.get("status") == dependency["required_t02_c_status"]
        and t02_c_check.get("status") == dependency["required_t02_c_check_status"]
        and len(t02_checks) == 17
        and all(item.get("status") == "PASS" for item in t02_checks)
        and not t02_c_check.get("failures")
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"]
        and t02_completion.get("t03_controlled_sensitivity_permitted_next")
        is dependency["require_t03_permitted_by_t02_c"],
        f"contract={t02_c_contract.get('contract_status')} run={t02_c_report.get('status')} independent={t02_c_check.get('status')} next={t02_completion.get('t03_controlled_sensitivity_permitted_next')}",
    )

    add_check(
        checks,
        "dependencies:identities_and_hashes_match",
        t02_c_contract.get("config", {}).get("sha256") == sha256(input_paths["t02_c_config"])
        and t02_c_report.get("case_id") == t02_c_config.get("case_id")
        and t02_c_check.get("case_id") == t02_c_config.get("case_id")
        and t02_a_report.get("case_id") == t02_a.get("case_id"),
        f"t02a={t02_a.get('case_id')} t02c={t02_c_config.get('case_id')}",
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

    p4 = next(item for item in experiments["parameter_groups"] if item["id"] == "P4")
    sensitivity = config["sensitivity"]
    lengths = [float(value) for value in sensitivity["values_um"]]
    add_check(
        checks,
        "group:one_p4_channel_length_variable",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "channel_length_um"
        and sensitivity["parameter_name"] == "channel_length"
        and "L" in p4["variables"]
        and config["parameter_group_id"] == p4["id"],
        f"group={p4['id']} variable={sensitivity['parameter_name']}",
    )

    add_check(
        checks,
        "scan:three_ordered_lengths_include_reference",
        lengths == [8.0, 10.0, 12.0]
        and close(sensitivity["reference_value_um"], baseline["device"]["channel_length_um"])
        and float(sensitivity["reference_value_um"]) in lengths
        and len(lengths) >= int(p4["minimum_points"]),
        f"lengths={lengths} reference={sensitivity['reference_value_um']}",
    )

    add_check(
        checks,
        "controls:geometry_except_length_is_frozen",
        close(baseline["device"]["width_um"], 60.0)
        and close(baseline["device"]["channel_thickness_nm"], 24.0)
        and close(baseline["materials"]["bottom_oxide"]["physical_thickness_nm"], 30.0)
        and close(t02_a["top_stack_contract"]["enabled_mode"]["top_oxide_thickness_nm"], 30.0)
        and close(baseline["materials"]["bottom_oxide"]["relative_permittivity"], 6.8)
        and close(t02_a["top_stack_contract"]["enabled_mode"]["top_oxide_relative_permittivity"], 6.8),
        "W=60 um tch=24 nm top/bottom Al2O3=30 nm k=6.8",
    )

    enabled = t02_a["top_stack_contract"]["enabled_mode"]
    add_check(
        checks,
        "topology:inherits_t02_a_enabled_stack",
        config["inheritance"]["required_mesh_level"] == "interface_4x"
        and config["inheritance"]["require_exact_t02_a_y_stack"] is True
        and enabled["top_oxide_present"] is True
        and enabled["top_gate_present"] is True
        and mesh["mesh_ladder"]["fixed_x_spacing_cm"] == 2.5e-5,
        json.dumps(enabled, sort_keys=True),
    )

    physics = t02_a["physics"]
    add_check(
        checks,
        "physics:frozen_electron_only_transport",
        physics["active_equations"] == ["Poisson", "electron_continuity"]
        and physics["mobility_model"] == baseline["physics"]["mobility_model"]
        and close(physics["temperature_k"], 300.0)
        and all(
            item in physics["inactive_models"]
            for item in ("bulk_traps", "contact_resistance_or_barrier", "ferroelectric_polarization")
        ),
        json.dumps(physics, sort_keys=True),
    )

    protocol = config["bias_protocol"]
    t02_protocol = t02_c_config["bias_protocol"]
    grid = primary_grid(protocol["primary_gate_grid"])
    t02_grid = primary_grid(t02_protocol["primary_gate_grid"])
    add_check(
        checks,
        "bias:exact_t02_c_zero_secondary_top_primary_grid",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and protocol["primary_gate"] == "top_gate"
        and protocol["secondary_gate"] == "bottom_gate"
        and close(protocol["fixed_secondary_gate_v"], 0.0)
        and grid == t02_grid
        and len(grid) == 31,
        f"points={len(grid)} range={grid[0]}..{grid[-1]} V",
    )

    add_check(
        checks,
        "bias:preconditioning_and_state_are_frozen",
        protocol["primary_negative_preconditioning_v"]
        == t02_protocol["primary_negative_preconditioning_v"]
        and close(protocol["state_primary_gate_v"], 1.0),
        f"pre={protocol['primary_negative_preconditioning_v']} state={protocol['state_primary_gate_v']} V",
    )

    extraction = config["extraction_methods"]
    t02_extraction = t02_c_config["extraction_methods"]
    add_check(
        checks,
        "extraction:vth_and_gm_methods_inherit_t02_c",
        extraction["constant_current_vth_proxy"]["name"]
        == t02_extraction["constant_current_vth_proxy"]["name"]
        and close(extraction["constant_current_vth_proxy"]["criterion_prefactor_a"], 1e-8)
        and extraction["gm_proxy"]["name"] == t02_extraction["gm_proxy"]["name"]
        and close(
            extraction["gm_proxy"]["evaluation_overdrive_v"],
            t02_extraction["gm_proxy"]["evaluation_overdrive_v"],
        ),
        json.dumps(extraction, sort_keys=True),
    )

    criteria = [1e-8 / (value * 1e-4) for value in lengths]
    add_check(
        checks,
        "extraction:w_over_l_criterion_is_dynamic",
        all(value > 0.0 for value in criteria)
        and close(criteria[1], t02_extraction["constant_current_vth_proxy"]["expected_current_per_width_a_per_cm"]),
        f"criteria_A_per_cm={criteria}",
    )

    budget = config["resource_budget"]
    add_check(
        checks,
        "execution:three_fresh_devices_and_123_dc_solves",
        budget["required_device_count"] == 3
        and budget["required_reported_point_count_per_device"] == 31
        and budget["required_total_reported_point_count"] == 93
        and budget["required_dc_solve_count_per_device"] == 41
        and budget["required_total_dc_solve_count"] == 123
        and budget["maximum_wall_seconds"] <= 300.0,
        json.dumps(budget, sort_keys=True),
    )

    state = config["state_output_contract"]
    add_check(
        checks,
        "states:one_complete_on_proxy_per_length",
        state["required_state_count"] == 3
        and state["required_vtk_file_count_per_state"] == 6
        and state["electron_current_density"]["unit"] == "A/cm^2"
        and close(protocol["state_primary_gate_v"], extraction["on_state_current_proxy"]["primary_gate_v"]),
        json.dumps(state, sort_keys=True),
    )

    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:counts_and_conservation_are_frozen",
        acceptance["required_channel_lengths_um"] == lengths
        and acceptance["required_reported_point_count"] == 93
        and acceptance["required_total_dc_solve_count"] == 123
        and close(acceptance["maximum_relative_terminal_current_imbalance"], 1e-5)
        and acceptance["require_all_dc_solves_converged"] is True,
        json.dumps(acceptance, sort_keys=True),
    )

    add_check(
        checks,
        "acceptance:t02_c_reference_regression_is_mandatory",
        config["inheritance"]["require_t02_c_reference_length_reproduction"] is True
        and acceptance["maximum_t02_c_reference_current_relative_difference"] <= 1e-6
        and acceptance["maximum_t02_c_reference_vth_difference_v"] <= 1e-4
        and acceptance["maximum_t02_c_reference_gm_relative_difference"] <= 1e-4,
        "10 um full curve, center state, VTH, and gm must reproduce T02-C",
    )

    add_check(
        checks,
        "acceptance:controlled_sensitivity_gates_are_prefrozen",
        acceptance["require_finite_vth_with_in_grid_brackets"] is True
        and acceptance["require_positive_finite_gm"] is True
        and acceptance["require_strict_on_current_decrease_with_length"] is True
        and acceptance["require_strict_gm_decrease_with_length"] is True
        and acceptance["require_ideal_inverse_length_diagnostic_reported"] is True
        and acceptance["require_prior_v1_failure_preserved"] is True
        and extraction["length_scaling"]["relative_spread_definition"]
        == "(max(values) - min(values)) / max(abs(values))",
        "finite bracketed VTH, positive gm, directional I/gm response, mandatory diagnostic reporting",
    )

    diagnostic = config["diagnostic_hypotheses"]["ideal_inverse_length"]
    add_check(
        checks,
        "diagnostic:failed_v1_ideal_scaling_gate_is_report_only",
        diagnostic["completion_gate"] is False
        and diagnostic["required_reporting"] is True
        and close(diagnostic["maximum_vth_range_v"], 0.002)
        and close(diagnostic["maximum_current_length_product_relative_spread"], 0.02)
        and close(diagnostic["maximum_gm_length_product_relative_spread"], 0.02)
        and close(diagnostic["minimum_log_current_vs_length_slope"], -1.05)
        and close(diagnostic["maximum_log_current_vs_length_slope"], -0.95)
        and close(diagnostic["minimum_log_current_vs_length_r_squared"], 0.999),
        "V1 thresholds are retained verbatim as a non-gating falsifiable diagnostic",
    )

    outputs = list(config["outputs"].values())
    add_check(
        checks,
        "outputs:paths_are_unique_and_stage_scoped",
        len(outputs) == len(set(outputs))
        and all("t03" in value or "p4_channel_length" in value for value in outputs)
        and config["outputs"]["contract_report"].endswith(".json")
        and config["outputs"]["sensitivity_figure_png"].endswith(".png"),
        f"outputs={len(outputs)} unique={len(set(outputs))}",
    )

    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:no_experimental_short_channel_or_complete_t03_claim",
        "local channel-length sensitivity" in boundary["allowed_claim"]
        and "physical Ion" in prohibited
        and "short-channel-effect" in prohibited
        and "complete T03" in prohibited
        and "trap" in prohibited
        and "circuit" in prohibited,
        boundary["allowed_claim"],
    )

    add_check(
        checks,
        "scope:no_other_t03_group_or_domain_work",
        all(token not in config["scope"]["changed_variable"] for token in ("trap", "contact", "temperature", "mobility"))
        and "any second T03 parameter group" in config["scope"]["prohibited_work"]
        and "complete T03 five-group sensitivity" in boundary["prohibited_claims"],
        config["scope"]["changed_variable"],
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "config": {
            "path": str(config_path.relative_to(ROOT)),
            "sha256": sha256(config_path),
        },
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in input_paths.items()
        },
        "checks": checks,
        "failures": failures,
        "planned_run": {
            "changed_variable": config["scope"]["changed_variable"],
            "values_um": lengths,
            "reported_points": budget["required_total_reported_point_count"],
            "dc_solves": budget["required_total_dc_solve_count"],
            "states": state["required_state_count"],
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    return report


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
        f"T03_P4_L_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P4_L_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
