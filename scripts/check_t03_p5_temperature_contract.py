#!/usr/bin/env python3
"""Validate the formal T03-P5 temperature input contract without DEVSIM."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p5_temperature.json"


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


def close(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1.0e-12, abs_tol=abs_tol)


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append({
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    })


def primary_grid(spec: dict[str, Any]) -> list[float]:
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not close(start + intervals * step, stop):
        raise ValueError("T03-P5 primary-gate range is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    json_names = (
        "project_config", "experiments_config", "s00_report",
        "t01_baseline_config", "t01_mesh_config", "t02_a_config",
        "t02_c_config", "t02_c_report", "t02_c_check_report", "p4_report",
        "p4_check_report", "p1_bias_report", "p1_bias_check_report",
        "p1_cap_report", "p1_cap_check_report", "p2_bulk_report",
        "p2_bulk_check_report", "p3_report", "p3_check_report",
    )
    input_paths = {name: ROOT / dependency[name] for name in json_names}
    input_paths.update({
        name: ROOT / dependency[name]
        for name in (
            "t01_transport_runner", "source_table", "runner",
            "independent_checker",
        )
    })
    loaded = {name: load_json(input_paths[name]) for name in json_names}
    project = loaded["project_config"]
    experiments = loaded["experiments_config"]
    s00 = loaded["s00_report"]
    baseline = loaded["t01_baseline_config"]
    mesh = loaded["t01_mesh_config"]
    t02_a = loaded["t02_a_config"]
    t02_c = loaded["t02_c_config"]
    t02_report = loaded["t02_c_report"]
    t02_check = loaded["t02_c_check_report"]
    p3_report = loaded["p3_report"]
    p3_check = loaded["p3_check_report"]
    source_rows, source_fields = load_csv(input_paths["source_table"])
    transport_source = input_paths["t01_transport_runner"].read_text(encoding="utf-8")
    runner_source = input_paths["runner"].read_text(encoding="utf-8")
    checker_source = input_paths["independent_checker"].read_text(encoding="utf-8")
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p5_temperature_contract",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P5_TEMPERATURE_V1"
        and config.get("stage") == "T03-P5-TEMPERATURE"
        and config.get("parameter_group_id") == "P5"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')} group={config.get('parameter_group_id')}",
    )
    serialized = json.dumps(config, sort_keys=True)
    add_check(
        checks,
        "scope:2d_n_igzo_laptop_only",
        baseline["device"]["material"] == "IGZO"
        and baseline["device"]["polarity"] == "n"
        and project["tcad_track"]["dimension"] == "2D"
        and project["tcad_track"]["laptop_target"] is True
        and config["resource_budget"]["laptop_target"] is True
        and "SnO" not in serialized
        and "HZO" in serialized,
        config["scope"]["device"],
    )
    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status") == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted") is False,
        json.dumps(s00.get("g0_decision", {}), sort_keys=True),
    )
    t02_completion = t02_report.get("t02_c_completion", {})
    add_check(
        checks,
        "dependencies:t02_numerical_gate_is_complete",
        t02_report.get("status") == dependency["required_t02_c_status"]
        and t02_check.get("status") == dependency["required_t02_c_check_status"]
        and not t02_check.get("failures")
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"],
        f"run={t02_report.get('status')} check={t02_check.get('status')} completion={t02_completion.get('complete_t02_numerical_stage_gate')}",
    )
    completed_reports = [
        loaded[name]
        for name in (
            "p4_report", "p4_check_report", "p1_bias_report",
            "p1_bias_check_report", "p1_cap_report", "p1_cap_check_report",
            "p2_bulk_report", "p2_bulk_check_report", "p3_report",
            "p3_check_report",
        )
    ]
    t03_experiment = next(
        item for item in experiments["experiments"] if item["id"] == "T03"
    )
    add_check(
        checks,
        "dependencies:p1_p2_p3_p4_are_complete_before_p5",
        all(item.get("status") == "PASS" for item in completed_reports)
        and t03_experiment.get("completed_parameter_groups")
        == dependency["require_completed_parameter_groups_before_p5"]
        and t03_experiment.get("remaining_parameter_groups") == ["P5"]
        and t03_experiment.get("remaining_substages") == ["T03-P5"]
        and p3_report.get("t03_p3_completion", {}).get(
            "formal_runner_passed"
        ) is True
        and p3_report.get("t03_p3_completion", {}).get(
            "p5_or_downstream_permitted_next"
        ) is False
        and p3_check.get("t03_p3_completion", {}).get(
            "p5_permitted_after_documentation"
        ) is True,
        f"completed={t03_experiment.get('completed_parameter_groups')} remaining={t03_experiment.get('remaining_parameter_groups')}",
    )
    add_check(
        checks,
        "machine_state:contract_ready_and_only_formal_p5_run_is_next",
        t03_experiment.get("p5_temperature_contract_evidence", {}).get("status")
        == "input_contract_ready"
        and t03_experiment.get("p5_temperature_contract_evidence", {}).get(
            "simulation_status"
        ) == "NOT_RUN_BY_CONTRACT_CHECK"
        and project.get("tcad_track", {}).get("next_scope", "").startswith(
            "run exactly one formal isolated T03-P5"
        ),
        project.get("tcad_track", {}).get("next_scope", ""),
    )

    model = config["temperature_model_contract"]
    temperatures = [float(value) for value in config["sensitivity"]["values_k"]]
    thermal_values = [float(value) for value in config["sensitivity"]["thermal_voltage_values_v"]]
    computed = [float(model["boltzmann_ev_per_k"]) * value for value in temperatures]
    add_check(
        checks,
        "model:three_points_and_thermal_voltage_are_exact",
        temperatures == [250.0, 300.0, 350.0]
        and all(close(left, right, abs_tol=1.0e-15) for left, right in zip(thermal_values, computed))
        and close(computed[1], baseline["physics"]["thermal_voltage_v"], abs_tol=1.0e-15)
        and close(baseline["physics"]["temperature_k"], 300.0),
        f"temperatures={temperatures} thermal_voltage={thermal_values}",
    )
    add_check(
        checks,
        "model:only_vt_changes_and_all_empirical_temperature_laws_are_off",
        model["changed_devsim_parameter"] == "channel region parameter V_t"
        and model["poisson_charge_equation_changed"] is False
        and model["electron_contact_density_changed"] is False
        and model["mobility_changed"] is False
        and model["mobility_temperature_law_active"] is False
        and model["effective_density_of_states_changed"] is False
        and model["bandgap_or_affinity_changed"] is False
        and model["permittivity_changed"] is False
        and model["contact_model_changed"] is False
        and model["trap_model_active"] is False
        and model["self_heating_active"] is False,
        model["interpretation"],
    )
    current_expression = model["implemented_current_expression"]
    add_check(
        checks,
        "implementation:existing_sg_current_uses_runtime_vt",
        'name="V_t"' in transport_source
        and 'value=float(baseline["physics"]["thermal_voltage_v"])' in transport_source
        and all(token in transport_source for token in (
            "ElectronCharge*mu_n*EdgeInverseLength*V_t*",
            "Electrons@n1*Bern01", "Electrons@n1*vdiff",
            "-Electrons@n0*Bern01",
        ))
        and all(token in current_expression for token in (
            "ElectronCharge", "mu_n", "V_t", "Bern01", "vdiff"
        )),
        current_expression,
    )
    add_check(
        checks,
        "sources:nist_constant_and_project_boundaries_are_explicit",
        len(source_rows) == 4
        and source_fields == [
            "source_id", "parameter_or_rule", "value_or_range", "unit",
            "source_type", "evidence_level", "source_reference",
            "allowed_use", "prohibited_use",
        ]
        and {row["source_id"] for row in source_rows} == {
            "NIST_CODATA_2022_BOLTZMANN_EV_PER_K",
            "PROJECT_ARCHITECTURE_P5_POINTS", "T01_BASELINE_300K",
            "T01_SG_IMPLEMENTATION",
        }
        and next(
            row for row in source_rows
            if row["source_id"] == "NIST_CODATA_2022_BOLTZMANN_EV_PER_K"
        )["value_or_range"] == "8.617333262e-5",
        f"rows={len(source_rows)} ids={[row['source_id'] for row in source_rows]}",
    )

    scope = config["scope"]
    fixed = " ".join(scope["fixed_variables"])
    add_check(
        checks,
        "controls:geometry_bias_transport_contacts_and_traps_are_frozen",
        scope["changed_variable"] == "lattice_temperature_k"
        and scope["changed_variable_count"] == 1
        and all(token in fixed for token in (
            "60 um", "10 um", "24 nm", "30 nm", "6.8", "35.5",
            "1e16", "D_it = 0", "NTA, NGA, NTD and NGD = 0",
            "ideal zero-series-resistance",
        )),
        scope["changed_variable"],
    )
    protocol = config["bias_protocol"]
    t02_protocol = t02_c["bias_protocol"]
    grid = primary_grid(protocol["primary_gate_grid"])
    add_check(
        checks,
        "bias:exact_t02_c_top_primary_zero_secondary_grid",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and protocol["primary_gate"] == "top_gate"
        and protocol["secondary_gate"] == "bottom_gate"
        and close(protocol["fixed_secondary_gate_v"], 0.0)
        and grid == primary_grid(t02_protocol["primary_gate_grid"])
        and len(grid) == 31
        and protocol["primary_negative_preconditioning_v"]
        == t02_protocol["primary_negative_preconditioning_v"],
        f"points={len(grid)} range={grid[0]}..{grid[-1]} V",
    )
    extraction = config["extraction_methods"]
    t02_extraction = t02_c["extraction_methods"]
    add_check(
        checks,
        "extraction:vth_gm_ss_and_fixed_current_proxies_are_frozen",
        extraction["constant_current_vth_proxy"]["name"]
        == t02_extraction["constant_current_vth_proxy"]["name"]
        and close(
            extraction["constant_current_vth_proxy"]["expected_current_per_width_a_per_cm"],
            1e-5,
        )
        and extraction["gm_proxy"]["name"] == t02_extraction["gm_proxy"]["name"]
        and close(extraction["gm_proxy"]["evaluation_overdrive_v"], 0.2)
        and extraction["ss_proxy"]["name"] == "fixed_current_window_ols"
        and close(extraction["ss_proxy"]["lower_current_a_per_cm"], 1e-7)
        and close(extraction["ss_proxy"]["upper_current_a_per_cm"], 1e-6)
        and close(extraction["low_gate_current_proxy"]["evaluation_top_gate_v"], -0.5)
        and close(extraction["high_gate_current_proxy"]["evaluation_top_gate_v"], 1.0)
        and close(extraction["configured_mobility_control"]["value_cm2_vs"], 35.5)
        and extraction["configured_mobility_control"]["temperature_dependent"] is False
        and extraction["configured_mobility_control"]["extracted_mobility_claim_permitted"] is False,
        json.dumps(extraction, sort_keys=True),
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "execution:three_fresh_devices_93_points_and_123_dc_solves",
        budget["required_temperature_count"] == 3
        and budget["required_device_count"] == 3
        and budget["required_reported_point_count_per_device"] == 31
        and budget["required_total_reported_point_count"] == 93
        and budget["required_dc_solve_count_per_device"] == 41
        and budget["required_total_dc_solve_count"] == 123
        and budget["maximum_wall_seconds"] <= 300.0
        and budget["maximum_run_directory_bytes"] <= 75000000,
        json.dumps(budget, sort_keys=True),
    )
    state = config["state_output_contract"]
    add_check(
        checks,
        "states:three_common_on_proxy_states_and_18_vtk_are_required",
        close(state["common_primary_gate_v"], 1.0)
        and state["required_state_ids"] == config["acceptance"]["required_state_ids"]
        and state["required_state_count"] == 3
        and state["required_vtk_file_count_per_state"] == 6
        and state["required_total_vtk_file_count"] == 18
        and state["electron_current_density"]["unit"] == "A/cm^2",
        json.dumps(state, sort_keys=True),
    )
    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:counts_conservation_extraction_and_response_are_prefrozen",
        acceptance["required_temperature_values_k"] == temperatures
        and acceptance["required_thermal_voltage_values_v"] == thermal_values
        and acceptance["required_total_reported_point_count"] == 93
        and acceptance["required_total_dc_solve_count"] == 123
        and close(acceptance["maximum_relative_terminal_current_imbalance"], 1e-5)
        and close(acceptance["minimum_ss_fit_r_squared"], 0.98)
        and acceptance["minimum_augmented_ss_sample_count"] == 4
        and close(
            acceptance["minimum_250_to_350_maximum_metric_relative_response"],
            0.001,
        )
        and acceptance["require_all_dc_solves_converged"] is True
        and acceptance["require_directional_hypotheses_reported_without_gating"] is True,
        json.dumps(acceptance, sort_keys=True),
    )
    add_check(
        checks,
        "acceptance:300k_t02_c_full_regression_is_mandatory",
        config["inheritance"]["require_300k_t02_c_reproduction"] is True
        and acceptance["maximum_300k_t02_c_current_relative_difference"] <= 1e-6
        and acceptance["maximum_300k_t02_c_center_potential_difference_v"] <= 1e-7
        and acceptance["maximum_300k_t02_c_center_density_relative_difference"] <= 1e-6
        and acceptance["maximum_300k_t02_c_vth_difference_v"] <= 1e-4
        and acceptance["maximum_300k_t02_c_gm_relative_difference"] <= 1e-4,
        "31-point curve, center state, VTH and gm must reproduce T02-C at 300 K",
    )
    directional = config["directional_hypotheses"]
    add_check(
        checks,
        "diagnostics:temperature_direction_is_report_only",
        directional["completion_gate"] is False
        and "contrary or non-monotonic trend" in directional["failure_rule"]
        and len(directional["registered"]) == 2,
        directional["reason"],
    )
    retention = config["failure_retention"]
    add_check(
        checks,
        "failure:retention_and_no_overwrite_are_mandatory",
        retention["refuse_to_overwrite_existing_run_outputs"] is True
        and retention["preserve_every_failed_run"] is True
        and retention["never_delete_or_overwrite_failed_evidence"] is True
        and len(retention["required_failure_artifacts"]) == 6
        and "silently relax an acceptance threshold" in retention["prohibited_recovery"]
        and "drop a temperature point after seeing its result" in retention["prohibited_recovery"]
        and "add an empirical temperature law after seeing the result" in retention["prohibited_recovery"],
        retention["acceptance_change_rule"],
    )
    outputs = config["outputs"]
    output_values = list(outputs.values())
    run_output_names = [
        name for name in outputs if name not in {"contract_report", "check_report"}
    ]
    existing_run_outputs = [
        outputs[name] for name in run_output_names if (ROOT / outputs[name]).exists()
    ]
    add_check(
        checks,
        "outputs:unique_stage_paths_are_unrun",
        len(output_values) == len(set(output_values))
        and all("p5_temperature" in value for value in output_values)
        and not existing_run_outputs,
        f"outputs={len(output_values)} existing_run_outputs={existing_run_outputs}",
    )
    add_check(
        checks,
        "implementation:runner_and_independent_checker_are_frozen",
        "runtime_baseline" in runner_source
        and 'variant["physics"]["temperature_k"] = temperature_k' in runner_source
        and 'variant["physics"]["thermal_voltage_v"] = boltzmann * temperature_k' in runner_source
        and "ensure_fresh_outputs" in runner_source
        and "complete_t03_five_group_sensitivity\": False" in runner_source
        and "run_t03_p5_temperature" not in checker_source
        and "import devsim" not in checker_source
        and "runner_imported\": False" in checker_source
        and "devsim_imported\": False" in checker_source,
        f"runner={dependency['runner']} checker={dependency['independent_checker']}",
    )
    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:no_calibration_physical_parameter_or_downstream_claim",
        "without running DEVSIM" in boundary["contract_allowed_claim"]
        and "V_t-only" in boundary["future_run_allowed_claim"]
        and "experimental or calibrated" in prohibited
        and "physical VTH" in prohibited
        and "compact-model" in prohibited
        and "complete T03 before" in prohibited,
        boundary["contract_allowed_claim"],
    )
    prohibited_work = " ".join(scope["prohibited_work_before_contract_pass"])
    add_check(
        checks,
        "gate:no_p5_simulation_or_downstream_work_was_started",
        "formal P5 DEVSIM run" in prohibited_work
        and "M00" in prohibited_work
        and "SPICE" in prohibited_work
        and "layout" in prohibited_work
        and "HZO" in prohibited_work
        and not existing_run_outputs,
        prohibited_work,
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    report = {
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
            for name, path in input_paths.items()
        },
        "checks": checks,
        "failures": failures,
        "planned_run": {
            "changed_variable": scope["changed_variable"],
            "temperature_values_k": temperatures,
            "thermal_voltage_values_v": thermal_values,
            "devices": budget["required_device_count"],
            "reported_points": budget["required_total_reported_point_count"],
            "dc_solves": budget["required_total_dc_solve_count"],
            "states": state["required_state_count"],
            "vtk_files": state["required_total_vtk_file_count"],
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
        f"T03_P5_TEMPERATURE_CONTRACT_{report['status']} "
        f"checks={len(report['checks'])} simulation={report['simulation_status']} "
        f"report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P5_TEMPERATURE_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
