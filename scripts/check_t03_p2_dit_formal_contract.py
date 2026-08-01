#!/usr/bin/env python3
"""Validate the T03-P2-DIT-FORMAL input contract without running DEVSIM."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_dit_formal.json"


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


def close(left: float, right: float, *, rel_tol: float = 1e-12, abs_tol: float = 1e-15) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def grid(spec: dict[str, Any]) -> list[float]:
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    count = round((stop - start) / step)
    if count < 1 or not close(start + count * step, stop):
        raise ValueError("formal primary-gate grid is not integral")
    return [round(start + index * step, 12) for index in range(count + 1)]


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dep = config["dependencies"]
    input_names = (
        "project_config", "experiments_config", "s00_report", "t01_baseline_config",
        "t01_mesh_config", "t02_a_config", "t02_c_config", "t02_c_contract_report",
        "t02_c_report", "t02_c_check_report", "dit_smoke_config",
        "dit_smoke_contract_report", "dit_smoke_report", "dit_smoke_check_report",
        "literature_table", "v1_formal_contract_report", "v1_formal_report",
        "v1_solver_log",
    )
    paths = {name: ROOT / dep[name] for name in input_names}
    loaded = {
        name: (load_csv(path) if name == "literature_table" else load_json(path))
        for name, path in paths.items()
    }
    project = loaded["project_config"]
    experiments = loaded["experiments_config"]
    s00 = loaded["s00_report"]
    baseline = loaded["t01_baseline_config"]
    mesh = loaded["t01_mesh_config"]
    t02_a = loaded["t02_a_config"]
    t02_c = loaded["t02_c_config"]
    t02_contract = loaded["t02_c_contract_report"]
    t02_report = loaded["t02_c_report"]
    t02_check = loaded["t02_c_check_report"]
    smoke_config = loaded["dit_smoke_config"]
    smoke_contract = loaded["dit_smoke_contract_report"]
    smoke_report = loaded["dit_smoke_report"]
    smoke_check = loaded["dit_smoke_check_report"]
    literature = loaded["literature_table"]
    v1_contract = loaded["v1_formal_contract_report"]
    v1_report = loaded["v1_formal_report"]
    v1_solver_log = loaded["v1_solver_log"]
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p2_dit_formal_contract",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P2_DIT_FORMAL_V2"
        and config.get("revision") == 2
        and config.get("stage") == "T03-P2-DIT-FORMAL"
        and config.get("parameter_group_id") == "P2"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )
    t02_completion = t02_report.get("t02_c_completion", {})
    add_check(
        checks,
        "dependencies:complete_t02_gate_passed",
        t02_contract.get("contract_status") == "PASS"
        and t02_report.get("status") == dep["required_t02_c_status"]
        and t02_check.get("status") == dep["required_t02_c_check_status"]
        and all(item.get("status") == "PASS" for item in t02_check.get("checks", []))
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dep["require_complete_t02_numerical_gate"],
        f"contract={t02_contract.get('contract_status')} run={t02_report.get('status')} check={t02_check.get('status')}",
    )
    smoke_completion = smoke_report.get("t03_p2_completion", {})
    add_check(
        checks,
        "dependencies:dit_equation_smoke_and_independent_check_passed",
        smoke_contract.get("contract_status") == "PASS"
        and smoke_contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and smoke_report.get("status") == dep["required_dit_smoke_status"]
        and smoke_check.get("status") == dep["required_dit_smoke_check_status"]
        and smoke_check.get("independent_of_simulation_runner") is True
        and all(item.get("status") == "PASS" for item in smoke_check.get("checks", []))
        and smoke_completion.get("formal_three_point_dit_sensitivity_permitted_next")
        is dep["require_formal_scan_permitted_by_smoke"],
        f"smoke={smoke_report.get('status')} check={smoke_check.get('status')} permitted={smoke_completion.get('formal_three_point_dit_sensitivity_permitted_next')}",
    )
    add_check(
        checks,
        "dependencies:identities_and_hashes_match",
        smoke_report.get("case_id") == smoke_config.get("case_id")
        and smoke_check.get("case_id") == smoke_config.get("case_id")
        and smoke_contract.get("config", {}).get("sha256") == sha256(paths["dit_smoke_config"])
        and t02_report.get("case_id") == t02_c.get("case_id")
        and t02_contract.get("config", {}).get("sha256") == sha256(paths["t02_c_config"]),
        f"t02={t02_c.get('case_id')} smoke={smoke_config.get('case_id')}",
    )
    prior = config["prior_failed_run"]
    add_check(
        checks,
        "history:v1_wide_window_failure_is_preserved_before_v2",
        prior["case_id"] == "IGZO_T03_P2_DIT_FORMAL_V1"
        and prior["status"] == "FAIL_PRESERVED"
        and prior["failed_gate"] == "minimum_ss_fit_r_squared"
        and prior["v1_window_a_per_cm"] == [1e-7, 1e-5]
        and prior["v1_observed_ss_fit_r_squared"]
        == [0.9547013581224532, 0.9708165634170878, 0.985595897703967, 0.9944438232965194]
        and "remains 0.98" in prior["unchanged_acceptance"]
        and v1_contract.get("contract_status") == "PASS"
        and v1_contract.get("case_id") == "IGZO_T03_P2_DIT_FORMAL_V1"
        and v1_report.get("status") == "FAIL"
        and v1_report.get("case_id") == "IGZO_T03_P2_DIT_FORMAL_V1"
        and "vth_gm_ss_and_ioff_numerical_proxies_are_extractable" in v1_report.get("failures", [])
        and len(v1_solver_log.get("runs", [])) == 4
        and sum(len(run.get("solver_records", [])) for run in v1_solver_log.get("runs", [])) == 164,
        prior["reason"],
    )
    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status") == dep["required_g0_status"]
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
        "group:one_bottom_interface_dit_variable",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "bottom_interface_D_it_cm^-2_eV^-1"
        and config["sensitivity"]["parameter_name"] == "bottom_interface_D_it"
        and "D_it" in p2["variables"]
        and config["scope"]["active_interface"] == "bottom_oxide_channel"
        and config["scope"]["inactive_interface"] == "channel_top_oxide",
        f"group={p2['id']} variable={config['sensitivity']['parameter_name']}",
    )
    source_values = sorted(float(row["dit_cm2_ev"]) for row in literature)
    sensitivity = config["sensitivity"]
    formal_values = [float(value) for value in sensitivity["formal_values_cm2_ev"]]
    execution_values = [float(value) for value in sensitivity["execution_values_cm2_ev"]]
    add_check(
        checks,
        "source:three_exact_literature_points_plus_zero_control",
        source_values == sorted([8.43e11, 3.07e12, 4.98e12, 6.02e12])
        and formal_values == [8.43e11, 3.07e12, 6.02e12]
        and execution_values == [0.0, *formal_values]
        and len(formal_values) == int(p2["minimum_points"])
        and sensitivity["formal_point_count"] == 3
        and sensitivity["control_point_count"] == 1,
        f"formal={formal_values} execution={execution_values}",
    )
    model = config["interface_trap_model"]
    smoke_model = smoke_config["interface_trap_model"]
    shared_model_keys = (
        "model_kind", "interface_region_order", "physical_sheet_charge_formula",
        "devsim_fluxterm_formula", "devsim_fluxterm_derivative_r0",
        "devsim_fluxterm_derivative_r1", "interface_equation_type",
        "bulk_equation_name0", "bulk_equation_name1",
        "potential_continuity_equation_retained", "neutral_potential_v",
        "neutral_potential_source_type",
    )
    add_check(
        checks,
        "model:exact_passed_smoke_equation_is_reused",
        all(model[key] == smoke_model[key] for key in shared_model_keys)
        and close(model["top_interface_dit_cm2_ev"], 0.0),
        model["devsim_fluxterm_formula"],
    )
    limitations = " ".join(model["limitations"])
    add_check(
        checks,
        "model:linearized_single_interface_limitations_are_explicit",
        "linearized" in limitations
        and "Only the bottom interface" in limitations
        and "bulk tail/deep" in limitations
        and "numerical proxies" in limitations,
        limitations,
    )
    enabled = t02_a["top_stack_contract"]["enabled_mode"]
    add_check(
        checks,
        "controls:geometry_transport_contact_temperature_and_top_interface_frozen",
        close(baseline["device"]["channel_length_um"], 10.0)
        and close(baseline["device"]["width_um"], 60.0)
        and close(baseline["device"]["channel_thickness_nm"], 24.0)
        and close(enabled["top_oxide_thickness_nm"], 30.0)
        and config["inheritance"]["required_mesh_level"] == "interface_4x"
        and "top interface D_it = 0 cm^-2 eV^-1" in config["scope"]["fixed_variables"],
        "L=10 um W=60 um tch=24 nm tox=30/30 nm mesh=interface_4x top_Dit=0",
    )
    protocol = config["bias_protocol"]
    t02_protocol = t02_c["bias_protocol"]
    primary_grid = grid(protocol["primary_gate_grid"])
    add_check(
        checks,
        "bias:exact_t02_c_top_primary_forward_grid",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and protocol["primary_negative_preconditioning_v"] == t02_protocol["primary_negative_preconditioning_v"]
        and primary_grid == grid(t02_protocol["primary_gate_grid"])
        and len(primary_grid) == 31
        and protocol["families"] == [{"family_id": "top_primary", "primary_gate": "top_gate", "secondary_gate": "bottom_gate", "fixed_secondary_values_v": [0.0]}]
        and protocol["reverse_paths"] == [],
        f"grid={primary_grid[0]}:{primary_grid[-1]} points={len(primary_grid)}",
    )
    extraction = config["extraction_methods"]
    t02_extraction = t02_c["extraction_methods"]
    add_check(
        checks,
        "extraction:vth_and_gm_methods_inherit_t02_c",
        extraction["constant_current_vth_proxy"] == t02_extraction["constant_current_vth_proxy"]
        and extraction["gm_proxy"] == t02_extraction["gm_proxy"]
        and close(extraction["delta_vth_proxy"]["reference_dit_cm2_ev"], 0.0),
        json.dumps({key: extraction[key] for key in ("constant_current_vth_proxy", "gm_proxy")}, sort_keys=True),
    )
    ss = extraction["ss_proxy"]
    ioff = extraction["ioff_proxy"]
    add_check(
        checks,
        "extraction:ss_and_ioff_are_fixed_before_run",
        ss["name"] == "fixed_current_window_ols"
        and close(ss["lower_current_a_per_cm"], 1e-7)
        and close(ss["upper_current_a_per_cm"], 1e-6)
        and ss["minimum_augmented_sample_count"] == 4
        and ioff["name"] == "fixed_lowest_gate_voltage_current"
        and close(ioff["evaluation_top_gate_v"], -0.5),
        json.dumps({"ss": ss, "ioff": ioff}, sort_keys=True),
    )
    hypotheses = config["directional_hypotheses"]
    add_check(
        checks,
        "hypotheses:directions_registered_but_not_completion_gate",
        hypotheses["completion_gate"] is False
        and hypotheses["vth_proxy_expected_to_increase_with_dit"] is True
        and hypotheses["ss_proxy_expected_to_increase_with_dit"] is True
        and hypotheses["ioff_proxy_direction_pre_registered"] is False,
        hypotheses["reason"],
    )
    states = protocol["state_points"]
    add_check(
        checks,
        "states:one_common_bias_state_per_execution_value",
        [float(item["dit_cm2_ev"]) for item in states] == execution_values
        and len(states) == config["state_output_contract"]["required_state_count"] == 4
        and all(close(item["vbg_v"], 0.0) and close(item["vtg_v"], 0.3) for item in states)
        and [item["state_id"] for item in states] == config["acceptance"]["required_state_ids"],
        f"states={[item['state_id'] for item in states]}",
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "execution:four_devices_124_points_164_solves_laptop_budget",
        budget["required_device_count"] == 4
        and budget["required_formal_device_count"] == 3
        and budget["required_control_device_count"] == 1
        and budget["required_reported_point_count_per_device"] == 31
        and budget["required_total_reported_point_count"] == 124
        and budget["required_dc_solve_count_per_device"] == 41
        and budget["required_total_dc_solve_count"] == 164
        and budget["maximum_wall_seconds"] <= 300.0
        and budget["laptop_target"] is True,
        json.dumps(budget, sort_keys=True),
    )
    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:numerics_reproduction_extraction_and_response_are_frozen",
        [float(value) for value in acceptance["required_dit_values_cm2_ev"]] == execution_values
        and acceptance["required_total_reported_point_count"] == 124
        and acceptance["required_total_dc_solve_count"] == 164
        and acceptance["maximum_relative_terminal_current_imbalance"] <= 1e-5
        and acceptance["maximum_zero_dit_t02_c_current_relative_difference"] <= 1e-6
        and acceptance["minimum_ss_fit_r_squared"] >= 0.98
        and acceptance["minimum_max_dit_common_state_current_relative_response"] > 0.0
        and acceptance["require_all_dc_solves_converged"] is True,
        "convergence, conservation, T02-C reproduction, extractability, and nonzero response are mandatory",
    )
    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:paths_are_unique_and_formal_stage_scoped",
        len(outputs) == len(set(outputs.values()))
        and all("t03_p2_dit_formal" in value or "p2_dit_formal" in value for value in outputs.values()),
        f"outputs={len(outputs)} unique={len(set(outputs.values()))}",
    )
    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:formal_interface_scan_does_not_complete_p2_or_t03",
        "numerical proxies" in boundary["allowed_claim"]
        and "complete P2" in prohibited
        and "complete T03" in prohibited
        and "T03-P2-BULK-TRAPS" in boundary["next_gate"],
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
        "config": {"path": str(config_path.relative_to(ROOT)), "sha256": sha256(config_path)},
        "inputs": {name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for name, path in paths.items()},
        "checks": checks,
        "failures": failures,
        "planned_run": {
            "execution_values_cm2_ev": execution_values,
            "formal_values_cm2_ev": formal_values,
            "device_count": budget["required_device_count"],
            "reported_point_count": budget["required_total_reported_point_count"],
            "dc_solve_count": budget["required_total_dc_solve_count"],
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
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"T03_P2_DIT_FORMAL_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(f"T03_P2_DIT_FORMAL_CONTRACT_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
