#!/usr/bin/env python3
"""Validate the frozen T03-P3 contact-resistance contract without DEVSIM."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p3_contact_resistance.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path, *, encoding: str = "utf-8") -> list[dict[str, str]]:
    with path.open("r", encoding=encoding, newline="") as stream:
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
    intervals = round((stop - start) / step)
    if intervals < 1 or not close(start + intervals * step, stop):
        raise ValueError("T03-P3 primary-gate grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def gate_path(ladder: list[float], target: float) -> list[float]:
    values = [value for value in ladder if value <= target + 1e-12]
    if target > 0.0 and not any(close(value, target) for value in values):
        values.append(target)
    return values


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
        "t02_c_config",
        "t02_c_report",
        "t02_c_check_report",
        "p4_report",
        "p4_check_report",
        "p1_cap_report",
        "p1_cap_check_report",
        "p2_dit_report",
        "p2_dit_check_report",
        "p2_bulk_config",
        "p2_bulk_report",
        "p2_bulk_check_report",
        "literature_table",
        "senior_manifest",
    )
    paths = {name: ROOT / dependency[name] for name in input_names}
    loaded: dict[str, Any] = {}
    for name, path in paths.items():
        if name == "literature_table":
            loaded[name] = load_csv(path)
        elif name == "senior_manifest":
            loaded[name] = load_csv(path, encoding="utf-8-sig")
        else:
            loaded[name] = load_json(path)

    project = loaded["project_config"]
    experiments = loaded["experiments_config"]
    s00 = loaded["s00_report"]
    baseline = loaded["t01_baseline_config"]
    mesh = loaded["t01_mesh_config"]
    t02_a = loaded["t02_a_config"]
    t02_c_config = loaded["t02_c_config"]
    t02_c_report = loaded["t02_c_report"]
    t02_c_check = loaded["t02_c_check_report"]
    p4_report = loaded["p4_report"]
    p4_check = loaded["p4_check_report"]
    p1_report = loaded["p1_cap_report"]
    p1_check = loaded["p1_cap_check_report"]
    dit_report = loaded["p2_dit_report"]
    dit_check = loaded["p2_dit_check_report"]
    bulk_config = loaded["p2_bulk_config"]
    bulk_report = loaded["p2_bulk_report"]
    bulk_check = loaded["p2_bulk_check_report"]
    literature = loaded["literature_table"]
    senior_manifest = loaded["senior_manifest"]
    t03 = next(item for item in experiments["experiments"] if item["id"] == "T03")
    p3 = next(item for item in experiments["parameter_groups"] if item["id"] == "P3")
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p3_contact_resistance_v1",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P3_CONTACT_RESISTANCE_V1"
        and config.get("stage") == "T03-P3-CONTACT-RESISTANCE"
        and config.get("parameter_group_id") == "P3"
        and config.get("status") == "planned"
        and config.get("evidence_level_before_run") == "E0"
        and config.get("contract_evidence_level_after_check") == "E3",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )
    add_check(
        checks,
        "dependencies:all_declared_inputs_exist",
        all(path.is_file() for path in paths.values()),
        "; ".join(f"{name}={path.relative_to(ROOT)}" for name, path in paths.items()),
    )

    t02_completion = t02_c_report.get("t02_c_completion", {})
    add_check(
        checks,
        "dependencies:g0_and_complete_t02_gate_passed",
        s00.get("g0_decision", {}).get("status") == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted") is False
        and t02_c_report.get("status") == dependency["required_t02_c_status"]
        and t02_c_check.get("status") == dependency["required_t02_c_check_status"]
        and len(t02_c_check.get("checks", [])) == 17
        and all(item.get("status") == "PASS" for item in t02_c_check["checks"])
        and not t02_c_check.get("failures")
        and t02_completion.get("complete_t02_numerical_stage_gate")
        == dependency["require_complete_t02_numerical_gate"],
        (
            f"g0={s00.get('g0_decision', {}).get('status')} "
            f"t02={t02_c_report.get('status')}/{t02_c_check.get('status')}"
        ),
    )

    p4_completion = p4_report.get("t03_p4_l_completion", {})
    p1_completion = p1_report.get("t03_p1_completion", {})
    dit_completion = dit_report.get("t03_p2_completion", {})
    bulk_completion = bulk_check.get("t03_p2_completion", {})
    add_check(
        checks,
        "dependencies:prior_t03_groups_passed_in_sequence",
        p4_report.get("status") == "PASS"
        and p4_report.get("evidence_level") == "E2"
        and p4_check.get("status") == "PASS"
        and p4_check.get("evidence_level") == "E3"
        and len(p4_check.get("checks", [])) == 14
        and p4_completion.get("p4_channel_length_three_point_group_complete")
        is dependency["require_p4_complete"]
        and p1_report.get("status") == "PASS"
        and p1_report.get("evidence_level") == "E2"
        and p1_check.get("status") == "PASS"
        and p1_check.get("evidence_level") == "E3"
        and len(p1_check.get("checks", [])) == 13
        and p1_completion.get("complete_p1_numerical_group")
        is dependency["require_p1_complete"]
        and dit_report.get("status") == "PASS"
        and dit_check.get("status") == "PASS"
        and dit_completion.get("interface_dit_substage_complete") is True
        and bulk_config.get("case_id") == "IGZO_T03_P2_BULK_TRAPS_FORMAL_V3"
        and bulk_report.get("status") == "PASS"
        and bulk_report.get("evidence_level") == "E2"
        and bulk_check.get("status") == "PASS"
        and bulk_check.get("evidence_level") == "E3"
        and bulk_check.get("independent_of_simulation_runner") is True
        and len(bulk_check.get("checks", [])) == 16
        and bulk_completion.get("complete_p2_trap_group")
        is dependency["require_p2_complete"]
        and bulk_completion.get("p3_or_p5_permitted_after_documentation")
        is dependency["require_p3_permitted_by_p2_check"],
        (
            f"p4={p4_report.get('status')}/{p4_check.get('status')} "
            f"p1={p1_report.get('status')}/{p1_check.get('status')} "
            f"p2={bulk_report.get('status')}/{bulk_check.get('status')}"
        ),
    )
    add_check(
        checks,
        "dependencies:machine_state_keeps_only_p3_and_p5_open",
        t03.get("completed_parameter_groups") == ["P1", "P2", "P4"]
        and t03.get("partially_completed_parameter_groups") == []
        and t03.get("remaining_parameter_groups") == ["P3", "P5"]
        and t03.get("remaining_substages") == ["T03-P3", "T03-P5"],
        (
            f"complete={t03.get('completed_parameter_groups')} "
            f"remaining={t03.get('remaining_substages')}"
        ),
    )

    serialized = json.dumps(config, sort_keys=True)
    add_check(
        checks,
        "scope:igzo_2d_laptop_teaching_model_only",
        baseline["device"]["material"] == "IGZO"
        and project["baseline_devices"]["IGZO_TFT"]["polarity"] == "n"
        and project["tcad_track"]["dimension"] == "2D"
        and project["tcad_track"]["laptop_target"] is True
        and config["resource_budget"]["laptop_target"] is True
        and "SnO" not in serialized,
        config["scope"]["device"],
    )

    sensitivity = config["sensitivity"]
    values = [float(value) for value in sensitivity["values_kohm_um"]]
    add_check(
        checks,
        "group:one_symmetric_p3_resistance_variable",
        config["scope"]["changed_variable_count"] == 1
        and config["scope"]["changed_variable"]
        == "symmetric_total_source_drain_series_resistance_width_product"
        and sensitivity["parameter_name"] == config["scope"]["changed_variable"]
        and {"R_source", "R_drain"} <= set(p3["variables"])
        and config["parameter_group_id"] == p3["id"]
        and close(sensitivity["source_fraction"], 0.5)
        and close(sensitivity["drain_fraction"], 0.5)
        and close(
            sensitivity["source_fraction"] + sensitivity["drain_fraction"], 1.0
        ),
        f"group={p3['id']} variable={sensitivity['parameter_name']}",
    )
    add_check(
        checks,
        "scan:three_ordered_points_and_explicit_ohm_conversion",
        values == [0.0, 0.5, 4.5]
        and close(sensitivity["reference_value_kohm_um"], 0.0)
        and len(values) >= int(p3["minimum_points"])
        and close(sensitivity["width_um"], 60.0)
        and [item["case_id"] for item in sensitivity["cases"]]
        == [
            "ideal_control",
            "literature_low_magnitude_proxy",
            "literature_high_magnitude_proxy",
        ]
        and all(
            close(
                item["r_pair_ohm"],
                float(item["r_pair_w_kohm_um"]) * 1000.0
                / float(sensitivity["width_um"]),
            )
            and close(item["r_source_ohm"], 0.5 * float(item["r_pair_ohm"]))
            and close(item["r_drain_ohm"], 0.5 * float(item["r_pair_ohm"]))
            for item in sensitivity["cases"]
        ),
        f"values={values} pair_ohm={[item['r_pair_ohm'] for item in sensitivity['cases']]}",
    )

    source_by_metal = {row["contact_metal"]: row for row in literature}
    mapping = config["literature_mapping"]
    add_check(
        checks,
        "literature:two_primary_e1_tlm_anchors_are_frozen",
        len(literature) == 2
        and set(source_by_metal) == {"Ni", "Ti"}
        and all(row["doi"] == mapping["doi"] for row in literature)
        and all(row["evidence_level"] == "E1" for row in literature)
        and all(row["extraction_method"] == "transfer-length method" for row in literature)
        and all(row["reported_condition"] == "VGS-VTH=2.5 V" for row in literature)
        and close(source_by_metal["Ni"]["reported_rc_kohm_um"], 0.5)
        and close(source_by_metal["Ti"]["reported_rc_kohm_um"], 4.5)
        and mapping["reported_magnitude_anchors_kohm_um"] == {"Ni": 0.5, "Ti": 4.5},
        f"rows={len(literature)} metals={sorted(source_by_metal)}",
    )
    manifest_matches = [
        row
        for row in senior_manifest
        if row.get("sha256")
        == "96cf85563f3940cb3a70092f31ae5ede3a8b250a9be63d0aa67ad505e55baa96"
        and row.get("relative_path", "").endswith(
            "First_Demonstration_of_Dual-Gate_IGZO_2T0C_DRAM_with_Novel_Read_Operation_One_Bit_Line_in_Single_Cell_ION1500_A_mVDS1V_and_Retention_Timegt300s.pdf"
        )
    ]
    live_source = Path(manifest_matches[0]["source_path"]) if manifest_matches else Path()
    add_check(
        checks,
        "literature:manifest_identity_and_live_hash_match",
        len(manifest_matches) == 1
        and live_source.is_file()
        and sha256(live_source) == manifest_matches[0]["sha256"]
        and all(
            row["source_manifest_path"] == "references/senior_work_manifest.csv"
            and row["source_file_sha256"] == manifest_matches[0]["sha256"]
            for row in literature
        ),
        (
            f"manifest_rows={len(manifest_matches)} "
            f"source={live_source if manifest_matches else 'missing'}"
        ),
    )
    add_check(
        checks,
        "literature:magnitudes_are_not_inherited_as_project_metal_parameters",
        mapping["source_rc_convention_inherited"] is False
        and mapping["project_case_labels_do_not_name_metals"] is True
        and mapping["mapping_is_measurement_or_calibration"] is False
        and "total source-plus-drain" in mapping["project_mapping"]
        and all(
            token not in item["case_id"].lower().split("_")
            for item in sensitivity["cases"]
            for token in ("ni", "ti")
        ),
        mapping["project_mapping"],
    )

    enabled = t02_a["top_stack_contract"]["enabled_mode"]
    add_check(
        checks,
        "controls:geometry_transport_traps_and_temperature_are_frozen",
        close(baseline["device"]["channel_length_um"], 10.0)
        and close(baseline["device"]["width_um"], 60.0)
        and close(baseline["device"]["channel_thickness_nm"], 24.0)
        and close(baseline["materials"]["bottom_oxide"]["physical_thickness_nm"], 30.0)
        and close(enabled["top_oxide_thickness_nm"], 30.0)
        and close(baseline["materials"]["bottom_oxide"]["relative_permittivity"], 6.8)
        and close(enabled["top_oxide_relative_permittivity"], 6.8)
        and close(t02_a["physics"]["temperature_k"], 300.0)
        and t02_a["physics"]["mobility_model"]
        == baseline["physics"]["mobility_model"]
        and config["inheritance"]["traps_inherited_from_completed_p2"] is False,
        "L=10 um W=60 um tch=24 nm dual 30 nm Al2O3 k=6.8 T=300 K; traps zero",
    )
    add_check(
        checks,
        "topology:inherits_enabled_t02_stack_and_interface_4x_mesh",
        config["inheritance"]["required_mesh_level"] == "interface_4x"
        and config["inheritance"]["require_exact_t02_a_enabled_topology"] is True
        and enabled["top_oxide_present"] is True
        and enabled["top_gate_present"] is True
        and mesh["mesh_ladder"]["fixed_x_spacing_cm"] == 2.5e-5
        and t02_a["physics"]["active_equations"] == ["Poisson", "electron_continuity"],
        json.dumps(enabled, sort_keys=True),
    )

    model = config["contact_model_contract"]
    api_text = " ".join(model["required_devsim_api"])
    add_check(
        checks,
        "model:self_consistent_device_circuit_series_resistance_is_frozen",
        model["model_kind"]
        == "self_consistent_symmetric_lumped_series_resistance_proxy"
        and "contact_equation" in api_text
        and "circuit_element" in api_text
        and "circuit_alter" in api_text
        and "get_circuit_node_value" in api_text
        and "delete_circuit" in api_text
        and model["poisson_and_electron_contact_equations_both_coupled_to_internal_nodes"]
        is True
        and model["manual_outer_voltage_drop_iteration_permitted"] is False
        and model["postprocessed_current_derating_permitted"] is False,
        model["model_kind"],
    )
    add_check(
        checks,
        "model:ideal_zero_control_and_nonzero_circuit_paths_are_distinct",
        sensitivity["cases"][0]["execution_mode"] == "direct_ideal_ohmic_contacts"
        and all(
            item["execution_mode"] == "self_consistent_device_circuit_coupling"
            for item in sensitivity["cases"][1:]
        )
        and "no zero-valued circuit resistor" in model["zero_control_rule"]
        and model["gate_contacts_remain_direct_dirichlet"] is True,
        model["zero_control_rule"],
    )
    add_check(
        checks,
        "model:no_barrier_injection_or_contact_region_claim_is_implemented",
        model["barrier_height_ev"] is None
        and model["thermionic_emission_active"] is False
        and model["tunneling_active"] is False
        and model["contact_region_mesh_or_material_changed"] is False
        and "barrier-height or work-function scan"
        in config["scope"]["prohibited_work_before_contract_pass"],
        "lumped resistance only; barrier/thermionic/tunneling/contact-region changes inactive",
    )

    protocol = config["bias_protocol"]
    transfer = protocol["transfer"]
    output = protocol["output"]
    t02_protocol = t02_c_config["bias_protocol"]
    grid = primary_grid(transfer["primary_gate_grid"])
    t02_grid = primary_grid(t02_protocol["primary_gate_grid"])
    add_check(
        checks,
        "bias:transfer_exactly_inherits_t02_c_zero_secondary_family",
        close(protocol["external_source_v"], t02_protocol["source_v"])
        and close(transfer["external_drain_v"], t02_protocol["drain_v"])
        and transfer["external_low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and transfer["primary_gate"] == "top_gate"
        and transfer["secondary_gate"] == "bottom_gate"
        and close(transfer["fixed_secondary_gate_v"], 0.0)
        and transfer["primary_negative_preconditioning_v"]
        == t02_protocol["primary_negative_preconditioning_v"]
        and grid == t02_grid
        and len(grid) == 31,
        f"points={len(grid)} range={grid[0]}..{grid[-1]} V",
    )
    output_gate_values = [float(value) for value in output["top_gate_values_v"]]
    output_vds_values = [float(value) for value in output["external_drain_values_v"]]
    gate_ladder = [float(value) for value in output["gate_preconditioning_ladder_v"]]
    add_check(
        checks,
        "bias:three_output_curves_and_low_field_fit_points_are_frozen",
        output_gate_values == [0.3, 0.5, 1.0]
        and output_vds_values == [0.0, 0.001, 0.005, 0.01, 0.05, 0.1, 0.2]
        and gate_ladder == [0.1, 0.2, 0.3, 0.5, 0.75, 1.0]
        and output["fresh_device_per_gate_curve"] is True
        and config["extraction_methods"]["linear_region_total_resistance_width_proxy"][
            "fit_external_vds_values_v"
        ]
        == [0.001, 0.005, 0.01],
        f"VTG={output_gate_values} VDS={output_vds_values}",
    )

    transfer_solves = (
        2
        + len(transfer["external_low_vds_values_v"]) - 1
        + len(transfer["primary_negative_preconditioning_v"])
        + len(grid)
    )
    output_solves = [
        2 + len(gate_path(gate_ladder, target)) + len(output_vds_values)
        for target in output_gate_values
    ]
    budget = config["resource_budget"]
    add_check(
        checks,
        "execution:twelve_fresh_devices_156_points_and_243_solves",
        transfer_solves == 41
        and output_solves == [12, 13, 15]
        and budget["required_contact_case_count"] == 3
        and budget["required_transfer_device_count"] == 3
        and budget["required_output_device_count"] == 9
        and budget["required_total_device_count"] == 12
        and budget["required_circuit_coupled_device_count"] == 8
        and budget["required_transfer_point_count_per_case"] == len(grid) == 31
        and budget["required_output_point_count_per_case"]
        == len(output_gate_values) * len(output_vds_values)
        == 21
        and budget["required_total_reported_point_count"] == 156
        and budget["required_transfer_dc_solve_count_per_case"] == transfer_solves
        and budget["required_output_dc_solve_counts_per_gate"] == output_solves
        and budget["required_total_dc_solve_count"] == 243
        and budget["maximum_wall_seconds"] <= 600.0,
        f"transfer={transfer_solves} output={output_solves} total=243",
    )

    extraction = config["extraction_methods"]
    linear = extraction["linear_region_total_resistance_width_proxy"]
    add_check(
        checks,
        "extraction:external_current_and_linear_resistance_proxy_are_prefrozen",
        "not physical Ion" in extraction["transfer_high_gate_current_proxy"]["label"]
        and "not physical Ion" in extraction["output_current_proxies"]["label"]
        and "constrained through the origin" in linear["fit"]
        and "sum(VDS_ext*abs(ID_ext))" in linear["conductance_formula"]
        and "R_total_ohm = 1/G_fit" in linear["resistance_formula"]
        and "W_um / 1000" in linear["width_product_formula"]
        and "ideal_control" in linear["added_resistance_formula"],
        linear["label"],
    )
    circuit = extraction["circuit_closure"]
    add_check(
        checks,
        "extraction:kcl_ohms_law_voltage_partition_and_power_are_prefrozen",
        "R_pair_ohm" in circuit["ohms_law"]
        and "external_VDS" in circuit["voltage_partition"]
        and "V_drain_internal - V_source_internal"
        in circuit["internal_device_vds_v"]
        and "abs(I_external)^2" in circuit["power_w"]
        and {
            "source and drain KCL residual",
            "source, drain and total resistor voltage drop",
            "total resistor power",
        }
        <= set(model["stored_circuit_quantities"]),
        json.dumps(circuit, sort_keys=True),
    )

    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:counts_conservation_and_circuit_closure_are_frozen",
        acceptance["required_r_pair_w_values_kohm_um"] == values
        and acceptance["required_transfer_point_count"] == 93
        and acceptance["required_output_point_count"] == 63
        and acceptance["required_total_reported_point_count"] == 156
        and acceptance["required_total_dc_solve_count"] == 243
        and acceptance["required_total_device_count"] == 12
        and close(acceptance["maximum_relative_device_terminal_current_imbalance"], 1e-5)
        and acceptance["maximum_circuit_kcl_relative_residual"] <= 1e-6
        and acceptance["maximum_circuit_ohms_law_relative_residual"] <= 1e-8
        and acceptance["maximum_circuit_voltage_partition_absolute_residual_v"] <= 1e-9
        and acceptance["require_all_dc_solves_converged"] is True,
        "device conservation plus circuit KCL/Ohm-law/voltage-partition gates",
    )
    ordering = acceptance["required_current_ordering_biases"]
    add_check(
        checks,
        "acceptance:direction_and_minimum_response_gates_are_prefrozen",
        acceptance["require_strict_transfer_current_increase_with_top_gate"] is True
        and acceptance["require_output_current_nondecreasing_with_external_vds"] is True
        and acceptance["require_strict_current_decrease_with_r_pair_at_selected_biases"]
        is True
        and acceptance["require_strict_linear_region_total_resistance_increase_with_r_pair"]
        is True
        and acceptance["minimum_high_proxy_relative_current_reduction_at_largest_r_pair"]
        == 0.001
        and ordering["transfer"] == [{"vtg_v": 1.0, "external_vds_v": 0.01}]
        and len(ordering["output"]) == 8,
        f"selected_ordering_points={1 + len(ordering['output'])}",
    )
    add_check(
        checks,
        "acceptance:ideal_control_must_reproduce_t02_c",
        config["inheritance"]["require_t02_c_zero_resistance_transfer_reproduction"]
        is True
        and acceptance["require_t02_c_ideal_transfer_reproduction"] is True
        and acceptance["maximum_t02_c_reference_current_relative_difference"] <= 1e-6
        and acceptance["maximum_t02_c_reference_center_potential_difference_v"] <= 1e-7
        and acceptance["maximum_t02_c_reference_center_density_relative_difference"] <= 1e-6,
        "31-point transfer current plus center potential/density regression",
    )

    diagnostic = config["diagnostic_hypotheses"][
        "extracted_added_resistance_matches_declared_pair"
    ]
    add_check(
        checks,
        "diagnostic:added_resistance_match_is_required_report_not_completion_gate",
        diagnostic["completion_gate"] is False
        and diagnostic["required_reporting"] is True
        and close(diagnostic["maximum_relative_difference"], 0.15)
        and acceptance["require_added_resistance_diagnostic_reported"] is True,
        diagnostic["reason_non_gating"],
    )
    state = config["state_output_contract"]
    add_check(
        checks,
        "states:one_complete_high_output_state_per_contact_case",
        state["bias"] == "VTG=1.0 V, VBG=0 V, external VDS=0.2 V"
        and state["circuit_state_required"] is True
        and state["required_state_count"] == 3
        and state["required_vtk_file_count_per_state"] == 6
        and acceptance["required_state_count"] == 3
        and acceptance["required_vtk_file_count"] == 18,
        json.dumps(state, sort_keys=True),
    )

    retention = config["failure_retention"]
    add_check(
        checks,
        "failure:partial_outputs_and_thresholds_must_be_preserved",
        retention["runner_pass_required_before_independent_check"] is True
        and retention["failure_archive_manifest_required"] is True
        and retention["archive_before_any_recovery_run"] is True
        and retention["delete_or_overwrite_failed_evidence_permitted"] is False
        and retention["relax_preregistered_thresholds_after_failure_permitted"] is False
        and retention["recovery_requires_new_contract_revision"] is True
        and retention["failure_does_not_complete_p3_or_t03"] is True,
        retention["on_exception_or_failed_gate"],
    )
    implementation = config["implementation_contract"]
    add_check(
        checks,
        "execution:runner_then_independent_checker_order_is_frozen",
        implementation["future_runner"] == "tcad/run_t03_p3_contact_resistance.py"
        and implementation["future_independent_checker"]
        == "scripts/check_t03_p3_contact_resistance.py"
        and implementation["independent_checker_must_not_import_runner_or_devsim"]
        is True
        and implementation["formal_run_permitted_only_after_contract_pass"] is True
        and retention["runner_pass_required_before_independent_check"] is True,
        f"runner={implementation['future_runner']} checker={implementation['future_independent_checker']}",
    )
    output_paths = list(config["outputs"].values())
    add_check(
        checks,
        "outputs:paths_are_unique_and_stage_scoped",
        len(output_paths) == len(set(output_paths))
        and all("t03_p3" in value or "p3_contact_resistance" in value for value in output_paths)
        and config["outputs"]["contract_report"].endswith(".json")
        and config["outputs"]["transfer_csv"].endswith(".csv")
        and config["outputs"]["output_csv"].endswith(".csv")
        and config["outputs"]["sensitivity_figure_png"].endswith(".png")
        and config["outputs"]["check_report"].endswith(".json"),
        f"outputs={len(output_paths)} unique={len(set(output_paths))}",
    )

    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:contract_is_static_and_physical_contact_claims_remain_closed",
        "without running DEVSIM" in boundary["contract_allowed_claim"]
        and "runner E2 plus independent persisted-evidence E3 PASS"
        in boundary["future_run_allowed_claim"]
        and "TLM-extracted" in prohibited
        and "Ti-versus-Ni" in prohibited
        and "Schottky barrier" in prohibited
        and "physical Ion" in prohibited
        and "complete P3 before runner" in prohibited
        and "complete T03" in prohibited
        and "P5" in prohibited
        and "circuit-cell" in prohibited,
        boundary["contract_allowed_claim"],
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": config["contract_evidence_level_after_check"],
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
        "planned_run": {
            "changed_variable": config["scope"]["changed_variable"],
            "values_kohm_um": values,
            "devices": budget["required_total_device_count"],
            "reported_points": budget["required_total_reported_point_count"],
            "dc_solves": budget["required_total_dc_solve_count"],
            "states": state["required_state_count"],
            "vtk_files": acceptance["required_vtk_file_count"],
        },
        "source_boundary": config["literature_mapping"],
        "failure_retention": retention,
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
        f"T03_P3_CONTACT_CONTRACT_{report['status']} "
        f"checks={len(report['checks'])} simulation={report['simulation_status']} "
        f"report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P3_CONTACT_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
