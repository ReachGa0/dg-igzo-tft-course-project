#!/usr/bin/env python3
"""Validate the T03-P1-BIAS input contract without running DEVSIM."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p1_secondary_bias.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


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
        raise ValueError("T03-P1-BIAS primary-gate range is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def expected_solve_counts(config: dict[str, Any]) -> list[int]:
    protocol = config["bias_protocol"]
    values = [float(value) for value in config["sensitivity"]["values_v"]]
    ramp_step = float(protocol["fixed_secondary_ramp_step_v"])
    fixed_count = (
        2
        + len(protocol["low_vds_values_v"])
        + len(protocol["primary_negative_preconditioning_v"])
        + int(protocol["primary_gate_grid"]["point_count"])
        - 1
    )
    counts: list[int] = []
    for value in values:
        ramp_count = round(abs(value) / ramp_step)
        if not close(ramp_count * ramp_step, abs(value)):
            raise ValueError(f"secondary bias {value} is not integral in ramp step")
        counts.append(fixed_count + ramp_count)
    return counts


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    input_names = (
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
        "t03_p4_config",
        "t03_p4_report",
        "t03_p4_check_report",
    )
    input_paths = {name: ROOT / dependency[name] for name in input_names}
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
    p4_config = loaded["t03_p4_config"]
    p4_report = loaded["t03_p4_report"]
    p4_check = loaded["t03_p4_check_report"]
    p4_snapshot = load_json(ROOT / p4_report["input_snapshot"])
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p1_bias_contract",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P1_SECONDARY_BIAS_V1"
        and config.get("stage") == "T03-P1-BIAS"
        and config.get("parameter_group_id") == "P1"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')} group={config.get('parameter_group_id')}",
    )

    t02_completion = t02_c_report.get("t02_c_completion", {})
    t02_checks = t02_c_check.get("checks", [])
    add_check(
        checks,
        "dependencies:complete_t02_gate_passed",
        t02_c_contract.get("contract_status") == "PASS"
        and t02_c_contract.get("config", {}).get("sha256")
        == sha256(input_paths["t02_c_config"])
        and t02_c_report.get("status") == dependency["required_t02_c_status"]
        and t02_c_check.get("status") == dependency["required_t02_c_check_status"]
        and len(t02_checks) == 17
        and all(item.get("status") == "PASS" for item in t02_checks)
        and not t02_c_check.get("failures")
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"],
        f"contract={t02_c_contract.get('contract_status')} run={t02_c_report.get('status')} independent={t02_c_check.get('status')}",
    )

    p4_completion = p4_report.get("t03_p4_l_completion", {})
    add_check(
        checks,
        "dependencies:prior_t03_p4_milestone_passed",
        p4_config.get("case_id") == p4_report.get("case_id")
        and p4_report.get("status") == dependency["required_t03_p4_status"]
        and p4_check.get("status") == dependency["required_t03_p4_check_status"]
        and p4_check.get("case_id") == p4_config.get("case_id")
        and len(p4_check.get("checks", [])) == 14
        and all(item.get("status") == "PASS" for item in p4_check["checks"])
        and p4_completion.get("p4_channel_length_three_point_group_complete")
        is dependency["require_t03_p4_group_complete"],
        f"p4_run={p4_report.get('status')} p4_check={p4_check.get('status')} complete={p4_completion.get('p4_channel_length_three_point_group_complete')}",
    )

    add_check(
        checks,
        "dependencies:identities_and_hashes_match",
        t02_c_report.get("case_id") == t02_c_config.get("case_id")
        and t02_c_check.get("case_id") == t02_c_config.get("case_id")
        and t02_a_report.get("case_id") == t02_a.get("case_id")
        and p4_snapshot.get("inputs", {}).get("t03_config", {}).get("sha256")
        == sha256(input_paths["t03_p4_config"]),
        f"t02a={t02_a.get('case_id')} t02c={t02_c_config.get('case_id')} p4={p4_config.get('case_id')}",
    )

    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status")
        == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted")
        is False,
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

    p1 = next(item for item in experiments["parameter_groups"] if item["id"] == "P1")
    values = [float(value) for value in config["sensitivity"]["values_v"]]
    add_check(
        checks,
        "group:one_p1_secondary_bias_variable",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "fixed_bottom_gate_bias_v"
        and config["sensitivity"]["parameter_name"] == "fixed_bottom_gate_bias"
        and "V_bottom_gate" in p1["variables"]
        and config["parameter_group_id"] == p1["id"],
        f"group={p1['id']} variable={config['sensitivity']['parameter_name']}",
    )

    add_check(
        checks,
        "scan:five_ordered_biases_include_zero_reference",
        values == [-0.4, -0.2, 0.0, 0.2, 0.4]
        and close(config["sensitivity"]["reference_value_v"], 0.0)
        and len(values) >= int(p1["minimum_points"]),
        f"values={values} reference={config['sensitivity']['reference_value_v']}",
    )

    ratio = config["capacitance_ratio_control"]
    bottom_material = baseline["materials"]["bottom_oxide"]
    enabled = t02_a["top_stack_contract"]["enabled_mode"]
    derived_ratio = (
        float(ratio["top_relative_permittivity"])
        / float(ratio["top_physical_thickness_nm"])
    ) / (
        float(ratio["bottom_relative_permittivity"])
        / float(ratio["bottom_physical_thickness_nm"])
    )
    add_check(
        checks,
        "controls:symmetric_capacitance_ratio_is_fixed_not_scanned",
        close(ratio["top_relative_permittivity"], enabled["top_oxide_relative_permittivity"])
        and close(ratio["bottom_relative_permittivity"], bottom_material["relative_permittivity"])
        and close(ratio["top_physical_thickness_nm"], enabled["top_oxide_thickness_nm"])
        and close(ratio["bottom_physical_thickness_nm"], bottom_material["physical_thickness_nm"])
        and close(derived_ratio, ratio["fixed_top_to_bottom_ratio"])
        and close(derived_ratio, 1.0)
        and ratio["status"] == "controlled_not_scanned",
        f"derived_Ctop_over_Cbottom={derived_ratio}",
    )

    add_check(
        checks,
        "controls:geometry_transport_contact_and_temperature_are_frozen",
        close(baseline["device"]["channel_length_um"], 10.0)
        and close(baseline["device"]["width_um"], 60.0)
        and close(baseline["device"]["channel_thickness_nm"], 24.0)
        and close(t02_a["physics"]["temperature_k"], 300.0)
        and t02_a["physics"]["mobility_model"]
        == baseline["physics"]["mobility_model"]
        and all(
            item in t02_a["physics"]["inactive_models"]
            for item in (
                "bulk_traps",
                "interface_traps",
                "contact_resistance_or_barrier",
                "ferroelectric_polarization",
            )
        ),
        "L=10 um W=60 um tch=24 nm T=300 K; traps/contact barrier/FE inactive",
    )

    add_check(
        checks,
        "topology:inherits_t02_a_enabled_stack_and_mesh",
        config["inheritance"]["required_mesh_level"] == "interface_4x"
        and config["inheritance"]["require_exact_t02_a_enabled_topology"] is True
        and enabled["top_oxide_present"] is True
        and enabled["top_gate_present"] is True
        and mesh["mesh_ladder"]["fixed_x_spacing_cm"] == 2.5e-5,
        json.dumps(enabled, sort_keys=True),
    )

    protocol = config["bias_protocol"]
    t02_protocol = t02_c_config["bias_protocol"]
    grid = primary_grid(protocol["primary_gate_grid"])
    t02_grid = primary_grid(t02_protocol["primary_gate_grid"])
    family = protocol["families"][0]
    add_check(
        checks,
        "bias:exact_t02_c_top_primary_grid_and_initialization",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and close(
            protocol["fixed_secondary_ramp_step_v"],
            t02_protocol["fixed_secondary_ramp_step_v"],
        )
        and protocol["primary_negative_preconditioning_v"]
        == t02_protocol["primary_negative_preconditioning_v"]
        and grid == t02_grid
        and len(grid) == 31
        and family["family_id"] == "top_primary"
        and family["primary_gate"] == "top_gate"
        and family["secondary_gate"] == "bottom_gate"
        and [float(value) for value in family["fixed_secondary_values_v"]]
        == values
        and protocol["reverse_paths"] == [],
        f"points={len(grid)} secondary={values}",
    )

    extraction = config["extraction_methods"]
    t02_extraction = t02_c_config["extraction_methods"]
    add_check(
        checks,
        "extraction:vth_delta_gm_and_coupling_methods_inherit_t02_c",
        extraction["constant_current_vth_proxy"]
        == t02_extraction["constant_current_vth_proxy"]
        and extraction["delta_vth_proxy"]
        == t02_extraction["delta_vth_proxy"]
        and extraction["gm_proxy"] == t02_extraction["gm_proxy"]
        and extraction["coupling_slope_proxy"]
        == {
            **t02_extraction["coupling_slope_proxy"],
            "definition": "five-point OLS slope of constant-current VTH versus fixed bottom-gate voltage",
        },
        json.dumps(extraction, sort_keys=True),
    )

    counts = expected_solve_counts(config)
    budget = config["resource_budget"]
    add_check(
        checks,
        "execution:five_fresh_devices_155_points_and_217_solves",
        counts == [45, 43, 41, 43, 45]
        and budget["required_device_count"] == 5
        and budget["required_forward_family_count"] == 5
        and budget["required_reported_point_count_per_family"] == 31
        and budget["required_total_reported_point_count"] == 155
        and budget["required_dc_solve_counts_by_secondary_bias"] == counts
        and budget["required_total_dc_solve_count"] == sum(counts) == 217
        and budget["maximum_wall_seconds"] <= 420.0,
        f"solve_counts={counts} total={sum(counts)}",
    )

    states = protocol["state_points"]
    state_contract = config["state_output_contract"]
    add_check(
        checks,
        "states:one_common_primary_state_per_secondary_bias",
        len(states) == len(values) == state_contract["required_state_count"] == 5
        and [float(item["vbg_v"]) for item in states] == values
        and all(
            item["source_family"] == "top_primary"
            and close(item["vtg_v"], protocol["common_state_primary_gate_v"])
            for item in states
        )
        and close(
            state_contract["common_primary_gate_v"],
            protocol["common_state_primary_gate_v"],
        )
        and state_contract["required_vtk_file_count_per_state"] == 6,
        f"states={[item['state_id'] for item in states]}",
    )

    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:counts_topology_and_conservation_are_frozen",
        acceptance["required_fixed_secondary_gate_values_v"] == values
        and acceptance["required_primary_gate_point_count"] == 31
        and acceptance["required_forward_family_count"] == 5
        and acceptance["required_forward_reported_point_count"] == 155
        and acceptance["required_total_dc_solve_count"] == 217
        and close(acceptance["maximum_relative_terminal_current_imbalance"], 1e-5)
        and acceptance["required_regions"]
        == ["bottom_oxide", "channel", "top_oxide"]
        and acceptance["required_contacts"]
        == ["source", "drain", "bottom_gate", "top_gate"]
        and acceptance["required_interfaces"]
        == ["bottom_oxide_channel", "channel_top_oxide"],
        json.dumps(acceptance, sort_keys=True),
    )

    add_check(
        checks,
        "acceptance:direction_and_extraction_gates_are_prefrozen",
        acceptance["require_positive_drain_and_negative_source_current"] is True
        and acceptance["require_strict_primary_gate_current_increase"] is True
        and acceptance["require_strict_secondary_gate_current_ordering"] is True
        and acceptance["require_vth_bracket_for_every_family"] is True
        and acceptance["require_delta_vth_strictly_decreases_with_secondary_bias"]
        is True
        and acceptance["require_positive_finite_gm"] is True
        and acceptance["require_common_bias_state_current_potential_density_ordering"]
        is True,
        "directional current, bracketed VTH, positive gm, and common-state ordering are mandatory",
    )

    t02_acceptance = t02_c_config["acceptance"]
    add_check(
        checks,
        "acceptance:coupling_fit_thresholds_inherit_t02_c",
        close(
            acceptance["minimum_absolute_coupling_slope_v_per_v"],
            t02_acceptance["minimum_absolute_coupling_slope_v_per_v"],
        )
        and close(
            acceptance["maximum_absolute_coupling_slope_v_per_v"],
            t02_acceptance["maximum_absolute_coupling_slope_v_per_v"],
        )
        and close(
            acceptance["minimum_coupling_fit_r_squared"],
            t02_acceptance["minimum_coupling_fit_r_squared"],
        ),
        f"abs_slope={acceptance['minimum_absolute_coupling_slope_v_per_v']}..{acceptance['maximum_absolute_coupling_slope_v_per_v']} R2>={acceptance['minimum_coupling_fit_r_squared']}",
    )

    add_check(
        checks,
        "acceptance:t02_c_zero_secondary_reference_is_mandatory",
        config["inheritance"]["require_t02_c_zero_secondary_reproduction"] is True
        and close(acceptance["required_reference_secondary_gate_v"], 0.0)
        and acceptance["maximum_t02_c_reference_current_relative_difference"] <= 1e-6
        and acceptance["maximum_t02_c_reference_vth_difference_v"] <= 1e-4
        and acceptance["maximum_t02_c_reference_gm_relative_difference"] <= 1e-4,
        "the full 31-point zero-secondary curve, center state, VTH, and gm must reproduce T02-C",
    )

    add_check(
        checks,
        "outputs:paths_are_unique_and_stage_scoped",
        len(config["outputs"]) == len(set(config["outputs"].values()))
        and all(
            "t03_p1" in value or "p1_secondary_bias" in value
            for value in config["outputs"].values()
        )
        and config["outputs"]["contract_report"].endswith(".json")
        and config["outputs"]["sensitivity_figure_png"].endswith(".png"),
        f"outputs={len(config['outputs'])} unique={len(set(config['outputs'].values()))}",
    )

    prohibited = " ".join(config["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks,
        "boundary:bias_only_not_capacitance_experiment_or_complete_p1",
        "five-point fixed-bottom-gate-bias sensitivity"
        in config["evidence_boundary"]["allowed_claim"]
        and "physical top-to-bottom capacitance ratio" in prohibited
        and "complete P1" in prohibited
        and "complete T03" in prohibited
        and "experimental" in prohibited,
        config["evidence_boundary"]["allowed_claim"],
    )

    add_check(
        checks,
        "scope:no_other_t03_group_or_domain_work",
        "top-to-bottom gate-capacitance-ratio variation"
        in config["scope"]["prohibited_work"]
        and "any P2, P3, P4, or P5 run" in config["scope"]["prohibited_work"]
        and all(
            token not in config["scope"]["changed_variable"]
            for token in ("trap", "contact", "length", "temperature", "mobility")
        ),
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
            "values_v": values,
            "reported_points": budget["required_total_reported_point_count"],
            "dc_solves": budget["required_total_dc_solve_count"],
            "states": state_contract["required_state_count"],
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
        f"T03_P1_BIAS_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P1_BIAS_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
