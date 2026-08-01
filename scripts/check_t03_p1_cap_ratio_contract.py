#!/usr/bin/env python3
"""Validate the T03-P1-CAP-RATIO input contract without running DEVSIM."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p1_capacitance_ratio.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not close(start + intervals * step, stop):
        raise ValueError("primary-gate grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    input_names = (
        "project_config", "experiments_config", "s00_report", "t01_baseline_config",
        "t01_mesh_config", "t02_a_config", "t02_c_config", "t02_c_report",
        "t02_c_check_report", "t03_p4_config", "t03_p4_report",
        "t03_p4_check_report", "t03_p1_bias_config", "t03_p1_bias_report",
        "t03_p1_bias_check_report",
    )
    paths = {name: ROOT / dependency[name] for name in input_names}
    loaded = {name: load_json(path) for name, path in paths.items()}
    project = loaded["project_config"]
    experiments = loaded["experiments_config"]
    s00 = loaded["s00_report"]
    baseline = loaded["t01_baseline_config"]
    mesh = loaded["t01_mesh_config"]
    t02_a = loaded["t02_a_config"]
    t02_c_config = loaded["t02_c_config"]
    t02_c_report = loaded["t02_c_report"]
    t02_c_check = loaded["t02_c_check_report"]
    p4_report = loaded["t03_p4_report"]
    p4_check = loaded["t03_p4_check_report"]
    bias_config = loaded["t03_p1_bias_config"]
    bias_report = loaded["t03_p1_bias_report"]
    bias_check = loaded["t03_p1_bias_check_report"]
    checks: list[dict[str, Any]] = []

    add_check(
        checks, "identity:t03_p1_cap_ratio_contract",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P1_CAP_RATIO_V1"
        and config.get("stage") == "T03-P1-CAP-RATIO"
        and config.get("parameter_group_id") == "P1"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')} group={config.get('parameter_group_id')}",
    )
    add_check(
        checks, "dependencies:complete_t02_gate_passed",
        t02_c_report.get("status") == dependency["required_t02_c_status"]
        and t02_c_check.get("status") == dependency["required_t02_c_check_status"]
        and t02_c_report.get("t02_c_completion", {}).get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"]
        and len(t02_c_check.get("checks", [])) == 17
        and not t02_c_check.get("failures"),
        f"run={t02_c_report.get('status')} independent={t02_c_check.get('status')}",
    )
    add_check(
        checks, "dependencies:p4_milestone_passed",
        p4_report.get("status") == dependency["required_t03_p4_status"]
        and p4_check.get("status") == dependency["required_t03_p4_check_status"]
        and p4_report.get("t03_p4_l_completion", {}).get("p4_channel_length_three_point_group_complete")
        is dependency["require_t03_p4_group_complete"]
        and len(p4_check.get("checks", [])) == 14
        and not p4_check.get("failures"),
        f"run={p4_report.get('status')} independent={p4_check.get('status')}",
    )
    bias_completion = bias_report.get("t03_p1_bias_completion", {})
    add_check(
        checks, "dependencies:p1_bias_substage_passed_and_opens_ratio_contract",
        bias_report.get("case_id") == bias_config.get("case_id")
        and bias_report.get("status") == dependency["required_t03_p1_bias_status"]
        and bias_check.get("status") == dependency["required_t03_p1_bias_check_status"]
        and bias_completion.get("p1_bias_five_point_substage_complete")
        is dependency["require_t03_p1_bias_substage_complete"]
        and bias_completion.get("capacitance_ratio_substage_permitted_next")
        is dependency["require_capacitance_ratio_substage_permitted"]
        and len(bias_check.get("checks", [])) == 14
        and not bias_check.get("failures"),
        f"run={bias_report.get('status')} independent={bias_check.get('status')} completion={bias_completion}",
    )
    add_check(
        checks, "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status") == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted") is False,
        json.dumps(s00.get("g0_decision", {}), sort_keys=True),
    )
    serialized = json.dumps(config, sort_keys=True)
    add_check(
        checks, "scope:igzo_2d_laptop_teaching_model_only",
        baseline["device"]["material"] == "IGZO"
        and project["baseline_devices"]["IGZO_TFT"]["polarity"] == "n"
        and project["tcad_track"]["dimension"] == "2D"
        and project["tcad_track"]["laptop_target"] is True
        and "SnO" not in serialized,
        config["scope"]["device"],
    )

    p1 = next(item for item in experiments["parameter_groups"] if item["id"] == "P1")
    p4 = next(item for item in experiments["parameter_groups"] if item["id"] == "P4")
    ratios = [float(value) for value in config["capacitance_ratio_sensitivity"]["values"]]
    add_check(
        checks, "group:one_p1_ratio_variable",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"] == "effective_top_to_bottom_gate_capacitance_ratio"
        and "C_top/C_bottom" in p1["variables"]
        and config["parameter_group_id"] == p1["id"],
        f"group={p1['id']} variable={config['scope']['changed_variable']}",
    )
    add_check(
        checks, "scan:five_ordered_dimensionless_ratios_include_symmetric_reference",
        ratios == [0.5, 0.75, 1.0, 1.5, 2.0]
        and close(config["capacitance_ratio_sensitivity"]["reference_value"], 1.0)
        and len(ratios) >= int(p1["minimum_points"]),
        f"ratios={ratios}",
    )

    encoding = config["ratio_encoding"]
    points = encoding["points"]
    fixed_sum = float(encoding["fixed_relative_permittivity_sum"])
    formulas_valid = len(points) == len(ratios)
    reconstructed: list[float] = []
    sums: list[float] = []
    fractions: list[float] = []
    for expected_ratio, point in zip(ratios, points):
        top = float(point["top_relative_permittivity"])
        bottom = float(point["bottom_relative_permittivity"])
        reconstructed.append(top / bottom)
        sums.append(top + bottom)
        fractions.append(top / (top + bottom))
        formulas_valid = formulas_valid and close(point["ratio"], expected_ratio)
        formulas_valid = formulas_valid and close(top, fixed_sum * expected_ratio / (1.0 + expected_ratio))
        formulas_valid = formulas_valid and close(bottom, fixed_sum / (1.0 + expected_ratio))
        formulas_valid = formulas_valid and close(point["top_coupling_fraction"], expected_ratio / (1.0 + expected_ratio))
    add_check(
        checks, "encoding:ratio_reconstruction_and_fixed_sum_are_exact",
        formulas_valid
        and all(close(value, expected) for value, expected in zip(reconstructed, ratios))
        and all(close(value, fixed_sum) for value in sums),
        f"reconstructed={reconstructed} sums={sums}",
    )
    add_check(
        checks, "ownership:p1_differential_allocation_is_separate_from_p4_common_mode",
        "epsilon_r" in p4["variables"]
        and "physical_dielectric_thickness" in p4["variables"]
        and close(encoding["top_physical_thickness_nm"], 30.0)
        and close(encoding["bottom_physical_thickness_nm"], 30.0)
        and close(fixed_sum / 2.0, 6.8)
        and "fixed-sum differential coupling allocation" in config["p1_p4_variable_ownership"]["boundary"]
        and "do not assert" in config["p1_p4_variable_ownership"]["encoding_note"],
        config["p1_p4_variable_ownership"]["boundary"],
    )

    enabled = t02_a["top_stack_contract"]["enabled_mode"]
    add_check(
        checks, "controls:geometry_transport_contact_temperature_and_common_mode_are_frozen",
        close(baseline["device"]["channel_length_um"], 10.0)
        and close(baseline["device"]["width_um"], 60.0)
        and close(baseline["device"]["channel_thickness_nm"], 24.0)
        and close(enabled["top_oxide_thickness_nm"], 30.0)
        and close(baseline["materials"]["bottom_oxide"]["physical_thickness_nm"], 30.0)
        and bias_config["inheritance"]["required_mesh_level"] == "interface_4x"
        and mesh["mesh_ladder"]["fixed_x_spacing_cm"] == 2.5e-5,
        "L=10 um W=60 um tch=24 nm ttop=tbottom=30 nm mean epsilon=6.8 interface_4x",
    )

    protocol = config["bias_protocol"]
    t02_protocol = t02_c_config["bias_protocol"]
    grid = primary_grid(config)
    t02_grid = primary_grid(t02_c_config)
    family = protocol["families"][0]
    add_check(
        checks, "bias:exact_t02_c_top_primary_zero_bottom_grid",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and protocol["primary_negative_preconditioning_v"] == t02_protocol["primary_negative_preconditioning_v"]
        and grid == t02_grid and len(grid) == 31
        and family == {"family_id": "top_primary", "primary_gate": "top_gate", "secondary_gate": "bottom_gate", "fixed_secondary_values_v": [0.0]}
        and protocol["reverse_paths"] == [],
        f"points={len(grid)} family={family}",
    )
    extraction = config["extraction_methods"]
    t02_extraction = t02_c_config["extraction_methods"]
    add_check(
        checks, "extraction:vth_and_gm_inherit_t02_c_while_delta_uses_ratio_one",
        extraction["constant_current_vth_proxy"] == t02_extraction["constant_current_vth_proxy"]
        and extraction["gm_proxy"]["name"] == t02_extraction["gm_proxy"]["name"]
        and close(extraction["gm_proxy"]["evaluation_overdrive_v"], t02_extraction["gm_proxy"]["evaluation_overdrive_v"])
        and close(extraction["delta_vth_proxy"]["reference_ratio"], 1.0),
        json.dumps(extraction, sort_keys=True),
    )

    budget = config["resource_budget"]
    add_check(
        checks, "execution:five_fresh_devices_155_points_and_205_solves",
        budget["required_device_count"] == 5
        and budget["required_forward_family_count"] == 5
        and budget["required_reported_point_count_per_family"] == 31
        and budget["required_total_reported_point_count"] == 155
        and budget["required_dc_solve_count_per_ratio"] == 41
        and budget["required_total_dc_solve_count"] == 205
        and budget["maximum_wall_seconds"] <= 420.0,
        json.dumps(budget, sort_keys=True),
    )
    states = protocol["state_points"]
    add_check(
        checks, "states:one_common_positive_top_gate_state_per_ratio",
        len(states) == len(ratios) == config["state_output_contract"]["required_state_count"]
        and [float(item["ratio"]) for item in states] == ratios
        and all(close(item["vbg_v"], 0.0) and close(item["vtg_v"], 0.3) for item in states)
        and config["state_output_contract"]["required_vtk_file_count_per_state"] == 6,
        f"states={[item['state_id'] for item in states]}",
    )
    acceptance = config["acceptance"]
    add_check(
        checks, "acceptance:counts_topology_conservation_and_direction_are_frozen",
        acceptance["required_ratio_values"] == ratios
        and acceptance["required_forward_reported_point_count"] == 155
        and acceptance["required_total_dc_solve_count"] == 205
        and close(acceptance["maximum_relative_terminal_current_imbalance"], 1e-5)
        and acceptance["required_regions"] == ["bottom_oxide", "channel", "top_oxide"]
        and acceptance["required_contacts"] == ["source", "drain", "bottom_gate", "top_gate"]
        and acceptance["required_interfaces"] == ["bottom_oxide_channel", "channel_top_oxide"]
        and acceptance["require_positive_drain_and_negative_source_current"] is True
        and acceptance["require_strict_primary_gate_current_increase"] is True,
        "counts, topology, terminal conservation, and current direction are mandatory",
    )
    add_check(
        checks, "acceptance:ratio_trends_and_symmetric_reference_are_prefrozen",
        acceptance["require_vth_strictly_decreases_with_ratio"] is True
        and acceptance["require_gm_strictly_increases_with_ratio"] is True
        and acceptance["require_common_bias_state_current_potential_density_ordering"] is True
        and config["inheritance"]["require_t02_c_symmetric_reference_reproduction"] is True
        and acceptance["maximum_t02_c_reference_current_relative_difference"] <= 1e-6
        and acceptance["maximum_t02_c_reference_vth_difference_v"] <= 1e-4,
        "VTH decreases, gm/common-state response increases, and ratio=1 reproduces T02-C",
    )
    add_check(
        checks, "outputs:paths_are_unique_and_stage_scoped",
        len(config["outputs"]) == len(set(config["outputs"].values()))
        and all("t03_p1_cap_ratio" in value or "p1_capacitance_ratio" in value for value in config["outputs"].values()),
        f"outputs={len(config['outputs'])} unique={len(set(config['outputs'].values()))}",
    )
    prohibited = " ".join(config["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks, "boundary:numerical_ratio_proxy_not_physical_or_complete_t03",
        "fixed-total-coupling allocation-ratio sensitivity" in config["evidence_boundary"]["allowed_claim"]
        and "physically extracted" in prohibited
        and "measured Al2O3" in prohibited
        and "complete T03" in prohibited,
        config["evidence_boundary"]["allowed_claim"],
    )
    add_check(
        checks, "scope:no_other_t03_group_or_domain_work",
        "any P2, P3, P4, or P5 run" in config["scope"]["prohibited_work"]
        and "compact-model, SPICE, circuit, layout, or HZO work" in config["scope"]["prohibited_work"],
        json.dumps(config["scope"]["prohibited_work"]),
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "config": {"path": str(config_path.relative_to(ROOT)), "sha256": sha256(config_path)},
        "inputs": {name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)} for name, path in paths.items()},
        "checks": checks,
        "failures": failures,
        "planned_run": {
            "changed_variable": config["scope"]["changed_variable"],
            "ratios": ratios,
            "reported_points": budget["required_total_reported_point_count"],
            "dc_solves": budget["required_total_dc_solve_count"],
            "states": config["state_output_contract"]["required_state_count"],
        },
        "evidence_boundary": config["evidence_boundary"],
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
        f"T03_P1_CAP_RATIO_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(f"T03_P1_CAP_RATIO_CONTRACT_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
