#!/usr/bin/env python3
"""Validate the T03-P2-DIT source, equation, and smoke contract without simulation."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_interface_trap.json"


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


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    paths = {
        name: ROOT / value
        for name, value in dependency.items()
        if isinstance(value, str) and ("/" in value or value.endswith(".json"))
    }
    missing = [name for name, path in paths.items() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"missing T03-P2-DIT inputs: {missing}")

    project = load_json(paths["project_config"])
    experiments = load_json(paths["experiments_config"])
    s00 = load_json(paths["s00_report"])
    baseline = load_json(paths["t01_baseline_config"])
    t02_a = load_json(paths["t02_a_config"])
    t02_c = load_json(paths["t02_c_config"])
    t02_report = load_json(paths["t02_c_report"])
    t02_check = load_json(paths["t02_c_check_report"])
    p4_report = load_json(paths["t03_p4_report"])
    p4_check = load_json(paths["t03_p4_check_report"])
    p1_bias_report = load_json(paths["t03_p1_bias_report"])
    p1_bias_check = load_json(paths["t03_p1_bias_check_report"])
    p1_ratio_report = load_json(paths["t03_p1_cap_ratio_report"])
    p1_ratio_check = load_json(paths["t03_p1_cap_ratio_check_report"])
    literature = load_csv(paths["literature_table"])
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p2_dit_contract_smoke",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P2_DIT_CONTRACT_SMOKE_V1"
        and config.get("stage") == "T03-P2-DIT-CONTRACT-SMOKE"
        and config.get("parameter_group_id") == "P2"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')} group={config.get('parameter_group_id')}",
    )
    t02_completion = t02_report.get("t02_c_completion", {})
    add_check(
        checks,
        "dependencies:complete_t02_gate_passed",
        t02_report.get("status") == dependency["required_t02_c_status"]
        and t02_check.get("status") == dependency["required_t02_c_check_status"]
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"]
        and all(item.get("status") == "PASS" for item in t02_check.get("checks", []))
        and not t02_check.get("failures"),
        f"run={t02_report.get('status')} independent={t02_check.get('status')} completion={t02_completion.get('complete_t02_numerical_stage_gate')}",
    )
    p4_completion = p4_report.get("t03_p4_l_completion", {})
    add_check(
        checks,
        "dependencies:p4_group_passed",
        p4_report.get("status") == "PASS"
        and p4_check.get("status") == "PASS"
        and p4_completion.get("p4_channel_length_three_point_group_complete")
        is dependency["require_complete_p4_group"]
        and all(item.get("status") == "PASS" for item in p4_check.get("checks", [])),
        f"run={p4_report.get('status')} independent={p4_check.get('status')} complete={p4_completion.get('p4_channel_length_three_point_group_complete')}",
    )
    p1_bias_completion = p1_bias_report.get("t03_p1_bias_completion", {})
    p1_completion = p1_ratio_report.get("t03_p1_completion", {})
    add_check(
        checks,
        "dependencies:numerical_p1_group_passed",
        p1_bias_report.get("status") == "PASS"
        and p1_bias_check.get("status") == "PASS"
        and p1_bias_completion.get("p1_bias_five_point_substage_complete") is True
        and p1_ratio_report.get("status") == "PASS"
        and p1_ratio_check.get("status") == "PASS"
        and p1_completion.get("complete_p1_numerical_group")
        is dependency["require_complete_p1_numerical_group"]
        and all(item.get("status") == "PASS" for item in p1_ratio_check.get("checks", [])),
        f"bias={p1_bias_report.get('status')}/{p1_bias_check.get('status')} ratio={p1_ratio_report.get('status')}/{p1_ratio_check.get('status')} complete={p1_completion.get('complete_p1_numerical_group')}",
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
        "group:one_bottom_interface_dit_variable",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "bottom_interface_D_it_cm^-2_eV^-1"
        and "D_it" in p2["variables"]
        and config["scope"]["active_interface"] == "bottom_oxide_channel"
        and config["scope"]["inactive_interface"] == "channel_top_oxide",
        f"group={p2['id']} variable={config['scope']['changed_variable']}",
    )

    required_fields = {
        "source_id", "doi", "title", "year", "device_stack", "anneal_ambient",
        "anneal_temperature_c", "dit_cm2_ev", "ss_mv_dec", "source_url",
        "accessed_date", "evidence_level", "project_use", "limitations",
    }
    add_check(
        checks,
        "source:four_primary_literature_rows_and_schema",
        len(literature) == 4
        and all(required_fields <= set(row) for row in literature)
        and len({row["source_id"] for row in literature}) == 4
        and all(row["doi"] == config["literature_input"]["doi"] for row in literature)
        and all(row["title"] == config["literature_input"]["title"] for row in literature)
        and all(row["evidence_level"] == "E1" for row in literature),
        f"rows={len(literature)} ids={[row.get('source_id') for row in literature]}",
    )
    source_values = sorted(float(row["dit_cm2_ev"]) for row in literature)
    source_ss = sorted(float(row["ss_mv_dec"]) for row in literature)
    add_check(
        checks,
        "source:reported_dit_and_ss_values_match_article",
        source_values == sorted([8.43e11, 3.07e12, 4.98e12, 6.02e12])
        and source_ss == [75.0, 115.0, 150.0, 168.0]
        and all(close(row["gate_dielectric_thickness_nm"], 15.0) for row in literature)
        and all(close(row["igzo_thickness_nm"], 30.0) for row in literature),
        f"dit={source_values} ss={source_ss}",
    )
    lit = config["literature_input"]
    formal_values = [float(value) for value in lit["formal_sensitivity_values_cm2_ev"]]
    add_check(
        checks,
        "source:three_literature_points_plus_zero_control_frozen",
        formal_values == [8.43e11, 3.07e12, 6.02e12]
        and len(formal_values) == int(p2["minimum_points"])
        and set(formal_values) < set(source_values)
        and close(lit["regression_control_cm2_ev"], 0.0)
        and close(lit["smoke_value_cm2_ev"], 3.07e12),
        f"formal={formal_values} control={lit['regression_control_cm2_ev']} smoke={lit['smoke_value_cm2_ev']}",
    )
    add_check(
        checks,
        "source:e1_process_mismatch_is_explicit",
        lit["source_evidence_level"] == "E1"
        and "15 nm Al2O3" in lit["source_device_context"]
        and "dual gate" in lit["project_mismatch"]
        and "30 nm physical Al2O3" in lit["project_mismatch"]
        and "sensitivity range only" in lit["project_mismatch"],
        lit["project_mismatch"],
    )

    model = config["interface_trap_model"]
    add_check(
        checks,
        "model:bottom_interface_order_and_single_location",
        model["interface_region_order"] == {"region0": "bottom_oxide", "region1": "channel"}
        and config["scope"]["active_interface"] == "bottom_oxide_channel"
        and "top interface D_it = 0 cm^-2 eV^-1" in config["scope"]["fixed_variables"],
        json.dumps(model["interface_region_order"], sort_keys=True),
    )
    add_check(
        checks,
        "model:physical_charge_and_devsim_flux_sign_frozen",
        model["physical_sheet_charge_formula"] == "Q_it=-q*D_it*(Potential@r1-Psi_neutral)"
        and model["devsim_fluxterm_formula"] == "InterfaceTrapFluxTerm=q*D_it*(Potential@r1-Psi_neutral)=-Q_it"
        and model["devsim_fluxterm_derivative_r0"].endswith("=0")
        and model["devsim_fluxterm_derivative_r1"].endswith("=q*D_it")
        and "D_channel_y-D_oxide_y=Q_it" in model["physical_boundary_relation"],
        model["devsim_fluxterm_formula"],
    )
    add_check(
        checks,
        "model:continuous_plus_fluxterm_assembly_frozen",
        model["interface_equation_type"] == "fluxterm"
        and model["bulk_equation_name0"] == "PotentialEquation"
        and model["bulk_equation_name1"] == "PotentialEquation"
        and model["potential_continuity_equation_retained"] is True
        and model["software_reference"].startswith("https://devsim.net/"),
        f"type={model['interface_equation_type']} software={model['software_reference']}",
    )
    add_check(
        checks,
        "model:units_and_neutral_reference_are_explicit_assumptions",
        model["neutral_potential_v"] == 0.0
        and model["neutral_potential_source_type"] == "explicit_teaching_assumption"
        and "cm^-2 eV^-1" in model["unit_derivation"]
        and "C/cm^2" in model["unit_derivation"]
        and "F/cm^2" in model["unit_derivation"],
        model["unit_derivation"],
    )
    limitations = " ".join(model["limitations"])
    add_check(
        checks,
        "model:dynamic_bulk_and_double_interface_claims_blocked",
        "capture-emission" in limitations
        and "bulk tail/deep" in limitations
        and "both interfaces" in limitations
        and "not project measurements" in limitations,
        limitations,
    )

    smoke = config["smoke_protocol"]
    electrostatic = smoke["electrostatic_cases"]
    coupled = smoke["coupled_cases"]
    add_check(
        checks,
        "smoke:three_electrostatic_zero_limit_and_charge_cases",
        [item["case_id"] for item in electrostatic]
        == config["acceptance"]["required_case_ids"][:3]
        and [bool(item["interface_equation_active"]) for item in electrostatic] == [False, True, True]
        and [float(item["dit_cm2_ev"]) for item in electrostatic] == [0.0, 0.0, 3.07e12]
        and smoke["electrostatic_bias"] == {"source_v": 0.0, "drain_v": 0.0, "bottom_gate_v": 0.0, "top_gate_v": 0.1},
        json.dumps(electrostatic, sort_keys=True),
    )
    add_check(
        checks,
        "smoke:two_coupled_cases_and_minimal_continuation",
        [item["case_id"] for item in coupled] == config["acceptance"]["required_case_ids"][3:]
        and [float(item["dit_cm2_ev"]) for item in coupled] == [0.0, 3.07e12]
        and smoke["coupled_continuation"]["low_vds_values_v"] == [0.001, 0.005, 0.01]
        and smoke["coupled_continuation"]["top_gate_values_v"] == [0.05, 0.1]
        and smoke["coupled_bias"] == {"source_v": 0.0, "drain_v": 0.01, "bottom_gate_v": 0.0, "top_gate_v": 0.1},
        json.dumps(smoke["coupled_continuation"], sort_keys=True),
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "execution:five_devices_17_solves_laptop_budget",
        budget["required_device_count"] == 5
        and budget["required_electrostatic_case_count"] == 3
        and budget["required_coupled_case_count"] == 2
        and budget["required_electrostatic_dc_solve_count"] == 3
        and budget["required_coupled_dc_solve_count_per_case"] == 7
        and budget["required_total_dc_solve_count"] == 17
        and budget["maximum_wall_seconds"] <= 120.0
        and budget["laptop_target"] is True,
        json.dumps(budget, sort_keys=True),
    )
    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:zero_limit_continuity_gauss_and_coupled_gates_frozen",
        acceptance["maximum_zero_dit_electrostatic_potential_difference_v"] <= 1e-12
        and acceptance["maximum_interface_potential_discontinuity_v"] <= 1e-9
        and acceptance["maximum_center_gauss_relative_error"] <= 1e-5
        and acceptance["maximum_relative_terminal_current_imbalance"] <= 1e-5
        and acceptance["require_representative_physical_sheet_charge_negative"] is True
        and acceptance["require_representative_current_below_zero_dit"] is True
        and acceptance["require_all_dc_solves_converged"] is True,
        "zero-limit, potential continuity, Gauss closure, current conservation, and response direction are mandatory",
    )
    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:paths_are_unique_and_stage_scoped",
        len(outputs) == len(set(outputs.values()))
        and all("t03_p2_dit" in value or "p2_dit_equation_smoke" in value for value in outputs.values()),
        f"outputs={len(outputs)} unique={len(set(outputs.values()))}",
    )
    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:equation_smoke_does_not_complete_scan_or_p2",
        "sheet-charge equation" in boundary["allowed_claim"]
        and "completed D_it sensitivity" in prohibited
        and "completed P2" in prohibited
        and "bulk N_tail" in prohibited
        and "complete T03" in prohibited
        and "separate minimum three-point" in boundary["next_gate"],
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
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in paths.items()
        },
        "checks": checks,
        "failures": failures,
        "planned_smoke": {
            "case_ids": acceptance["required_case_ids"],
            "device_count": budget["required_device_count"],
            "dc_solve_count": budget["required_total_dc_solve_count"],
            "formal_sensitivity_run": False,
        },
        "planned_future_formal_values_cm2_ev": formal_values,
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
        f"T03_P2_DIT_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(f"T03_P2_DIT_CONTRACT_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
