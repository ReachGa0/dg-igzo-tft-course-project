#!/usr/bin/env python3
"""Validate the formal isolated NTA/NGA transfer contract without DEVSIM."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_bulk_traps_formal.json"


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
    intervals = round((stop - start) / step)
    if intervals < 1 or not close(start + intervals * step, stop):
        raise ValueError("formal primary-gate grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dep = config["dependencies"]
    input_names = (
        "project_config",
        "experiments_config",
        "s00_report",
        "t01_baseline_config",
        "t02_c_config",
        "t02_c_report",
        "t02_c_check_report",
        "dit_formal_config",
        "bulk_input_config",
        "bulk_input_contract_report",
        "bulk_smoke_report",
        "bulk_smoke_check_report",
        "literature_table",
        "v1_formal_config",
        "v1_formal_contract_report",
        "v1_formal_report",
        "v1_failure_archive_manifest",
        "v1_config_snapshot",
        "v1_runner_script",
        "v1_curve_csv",
    )
    paths = {name: ROOT / dep[name] for name in input_names}
    loaded = {
        name: (
            load_csv(path)
            if name in {"literature_table", "v1_curve_csv"}
            else (
                {"path": str(path.relative_to(ROOT))}
                if name == "v1_runner_script"
                else load_json(path)
            )
        )
        for name, path in paths.items()
    }
    project = loaded["project_config"]
    experiments = loaded["experiments_config"]
    s00 = loaded["s00_report"]
    baseline = loaded["t01_baseline_config"]
    t02_config = loaded["t02_c_config"]
    t02_report = loaded["t02_c_report"]
    t02_check = loaded["t02_c_check_report"]
    dit_formal = loaded["dit_formal_config"]
    bulk_input = loaded["bulk_input_config"]
    bulk_contract = loaded["bulk_input_contract_report"]
    smoke_report = loaded["bulk_smoke_report"]
    smoke_check = loaded["bulk_smoke_check_report"]
    literature = loaded["literature_table"]
    v1_config = loaded["v1_formal_config"]
    v1_contract = loaded["v1_formal_contract_report"]
    v1_report = loaded["v1_formal_report"]
    v1_archive = loaded["v1_failure_archive_manifest"]
    v1_snapshot = loaded["v1_config_snapshot"]
    v1_curve = loaded["v1_curve_csv"]
    t03 = next(item for item in experiments["experiments"] if item["id"] == "T03")
    p2 = next(item for item in experiments["parameter_groups"] if item["id"] == "P2")
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t03_p2_bulk_traps_formal_v2",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_T03_P2_BULK_TRAPS_FORMAL_V2"
        and config.get("revision") == 2
        and config.get("stage") == "T03-P2-BULK-TRAPS-FORMAL"
        and config.get("parameter_group_id") == "P2"
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
    add_check(
        checks,
        "dependencies:g0_and_complete_t02_gate_are_preserved",
        s00.get("status") == "PASS"
        and s00.get("g0_decision", {}).get("status")
        == dep["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted")
        is False
        and t02_report.get("status") == dep["required_t02_c_status"]
        and t02_check.get("status") == dep["required_t02_c_check_status"]
        and t02_report.get("t02_c_completion", {}).get(
            "complete_t02_numerical_stage_gate"
        )
        == "PASS",
        (
            f"g0={s00.get('g0_decision', {}).get('status')} "
            f"t02={t02_report.get('status')} independent={t02_check.get('status')}"
        ),
    )
    add_check(
        checks,
        "dependencies:bulk_input_contract_passed_without_simulation",
        bulk_input.get("case_id") == "IGZO_T03_P2_BULK_TRAPS_CONTRACT_V1"
        and bulk_contract.get("contract_status")
        == dep["required_bulk_input_contract_status"]
        and bulk_contract.get("simulation_status")
        == "NOT_RUN_BY_CONTRACT_CHECK"
        and bulk_contract.get("evidence_level") == "E3"
        and len(bulk_contract.get("checks", [])) == 30
        and all(
            item.get("status") == "PASS"
            for item in bulk_contract.get("checks", [])
        )
        and not bulk_contract.get("failures")
        and bulk_contract.get("config", {}).get("sha256")
        == sha256(paths["bulk_input_config"]),
        (
            f"status={bulk_contract.get('contract_status')} "
            f"checks={len(bulk_contract.get('checks', []))}"
        ),
    )
    smoke_completion = smoke_report.get("t03_p2_completion", {})
    add_check(
        checks,
        "dependencies:bulk_equation_smoke_e2_and_independent_e3_passed",
        smoke_report.get("status") == dep["required_bulk_smoke_status"]
        and smoke_report.get("evidence_level") == "E2"
        and smoke_report.get("case_id")
        == "IGZO_T03_P2_BULK_TRAPS_EQUATION_SMOKE_V1"
        and smoke_report.get("formal_sensitivity_run") is False
        and smoke_check.get("status") == dep["required_bulk_smoke_check_status"]
        and smoke_check.get("evidence_level") == "E3"
        and smoke_check.get("independent_of_simulation_runner") is True
        and len(smoke_check.get("checks", [])) == 16
        and all(
            item.get("status") == "PASS" for item in smoke_check.get("checks", [])
        )
        and not smoke_report.get("failures")
        and not smoke_check.get("failures")
        and smoke_completion.get("formal_bulk_sensitivity_permitted_next")
        is dep["require_formal_bulk_sensitivity_permitted_next"]
        and smoke_completion.get("complete_p2_trap_group") is False,
        (
            f"runner={smoke_report.get('status')}/{smoke_report.get('evidence_level')} "
            f"independent={smoke_check.get('status')}/{smoke_check.get('evidence_level')}"
        ),
    )
    v1_high_rows = [
        row
        for row in v1_curve
        if row.get("bulk_family_id") == "NTA"
        and close(float(row.get("bulk_value_cm3_ev", "nan")), 5e19)
    ]
    v1_other_curves: dict[tuple[str, float], list[dict[str, str]]] = {}
    for row in v1_curve:
        key = (row.get("bulk_family_id", ""), float(row["bulk_value_cm3_ev"]))
        v1_other_curves.setdefault(key, []).append(row)
    v1_maximum_nonzero_potential = max(
        float(item["zero_equilibrium"]["maximum_absolute_potential_v"])
        for item in v1_report.get("family_summaries", [])
        if not item.get("is_zero_control")
    )
    prior = config["prior_failed_run"]
    add_check(
        checks,
        "failure:v1_bracket_and_zero_bias_gate_failure_is_preserved",
        v1_config.get("case_id") == "IGZO_T03_P2_BULK_TRAPS_FORMAL_V1"
        and v1_config.get("revision") == 1
        and v1_contract.get("contract_status") == "PASS"
        and v1_contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and v1_contract.get("config", {}).get("sha256")
        == sha256(paths["v1_formal_config"])
        and v1_snapshot.get("inputs", {}).get("runner_script", {}).get("sha256")
        == sha256(paths["v1_runner_script"])
        and v1_report.get("status") == "FAIL"
        and v1_report.get("evidence_level") == "E0"
        and v1_report.get("formal_sensitivity_run") is False
        and v1_report.get("summary_metrics", {}).get("device_count") == 8
        and v1_report.get("summary_metrics", {}).get("dc_solve_count") == 328
        and v1_report.get("summary_metrics", {}).get("reported_point_count") == 248
        and len(v1_curve) == 248
        and len(v1_high_rows) == 31
        and close(
            max(abs(float(row["drain_current_a_per_cm"])) for row in v1_high_rows),
            prior["v1_high_nta_maximum_current_a_per_cm"],
        )
        and prior["v1_high_nta_maximum_current_a_per_cm"]
        < prior["unchanged_constant_current_criterion_a_per_cm"]
        and all(
            max(abs(float(row["drain_current_a_per_cm"])) for row in rows)
            >= prior["unchanged_constant_current_criterion_a_per_cm"]
            for key, rows in v1_other_curves.items()
            if key != ("NTA", 5e19)
        )
        and close(
            v1_maximum_nonzero_potential,
            prior[
                "v1_maximum_nonzero_trap_zero_equilibrium_internal_potential_v"
            ],
        )
        and v1_archive.get("status") == "FAIL_PRESERVED"
        and v1_archive.get("failed_gate")
        == "runner_completed_without_exception"
        and v1_report.get("failure_archive", {}).get("directory")
        == prior["archive_directory"]
        and prior["status"] == "FAIL_PRESERVED"
        and prior["user_approved_recovery"] is True,
        (
            f"v1_rows={len(v1_curve)} high_nta_max="
            f"{prior['v1_high_nta_maximum_current_a_per_cm']:.6e} "
            f"criterion={prior['unchanged_constant_current_criterion_a_per_cm']:.6e} "
            f"zero_bias_potential={v1_maximum_nonzero_potential:.6e}"
        ),
    )
    machine_evidence = t03.get("p2_bulk_formal_contract_evidence", {})
    add_check(
        checks,
        "gate:machine_state_is_formal_contract_ready_and_p2_partial",
        t03.get("status") == "partial_verified"
        and t03.get("completed_parameter_groups") == ["P1", "P4"]
        and t03.get("partially_completed_parameter_groups") == ["P2"]
        and t03.get("remaining_parameter_groups") == ["P2", "P3", "P5"]
        and t03.get("remaining_substages")
        == [
            "T03-P2-BULK-TRAPS formal isolated NTA/NGA transfer sensitivity",
            "T03-P3",
            "T03-P5",
        ]
        and machine_evidence
        == {
            "status": "input_contract_ready_v2",
            "revision": 2,
            "contract_evidence": "E3",
            "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
            "v1_failure_preserved": True,
            "formal_sensitivity_completed": False,
        }
        and "run the V2 formal isolated NTA/NGA transfer sensitivity"
        in project.get("tcad_track", {}).get("next_scope", ""),
        (
            f"t03={t03.get('status')} partial={t03.get('partially_completed_parameter_groups')} "
            f"contract={machine_evidence}"
        ),
    )
    scope = config["scope"]
    fixed = " ".join(scope["fixed_variables"])
    add_check(
        checks,
        "scope:2d_igzo_single_family_isolation_and_closed_later_work",
        "2D n-IGZO" in scope["device"]
        and scope["one_active_family_per_device"] is True
        and "NGA = 0" in fixed
        and "NTA = 0" in fixed
        and "bottom and top interface D_it = 0" in fixed
        and "NTD and NGD = 0 and deferred" in fixed
        and len(scope["prohibited_work_before_contract_pass"]) == 5
        and any(
            "P3, P5" in item
            for item in scope["prohibited_work_before_contract_pass"]
        ),
        "NTA/NGA isolated; DIT/NTD/NGD zero; later tracks closed",
    )
    families = config["sensitivity_families"]
    family_map = {item["family_id"]: item for item in families}
    tail = bulk_input["literature_input"]["tail"]
    deep = bulk_input["literature_input"]["deep"]
    add_check(
        checks,
        "points:exact_two_families_three_formal_points_and_two_controls",
        [item["family_id"] for item in families] == ["NTA", "NGA"]
        and family_map["NTA"]["execution_values_cm3_ev"]
        == [0.0, 1e18, 5e18, 5e19]
        and family_map["NGA"]["execution_values_cm3_ev"]
        == [0.0, 1e16, 5e16, 5e17]
        and family_map["NTA"]["formal_values_cm3_ev"]
        == tail["formal_sensitivity_values_cm3_ev"]
        and family_map["NGA"]["formal_values_cm3_ev"]
        == deep["formal_sensitivity_values_cm3_ev"]
        and all(close(item["zero_control_cm3_ev"], 0.0) for item in families)
        and int(p2["minimum_points"]) == 3,
        json.dumps(
            {
                item["family_id"]: item["execution_values_cm3_ev"]
                for item in families
            },
            sort_keys=True,
        ),
    )
    add_check(
        checks,
        "points:width_peak_units_and_inactive_families_are_exact",
        family_map["NTA"]["inactive_family"] == "NGA"
        and close(family_map["NTA"]["inactive_family_value_cm3_ev"], 0.0)
        and close(family_map["NTA"]["width_ev"], tail["width_ev"])
        and family_map["NTA"]["peak_depth_below_ec_ev"] is None
        and family_map["NGA"]["inactive_family"] == "NTA"
        and close(family_map["NGA"]["inactive_family_value_cm3_ev"], 0.0)
        and close(family_map["NGA"]["width_ev"], deep["width_ev"])
        and close(
            family_map["NGA"]["peak_depth_below_ec_ev"],
            deep["peak_depth_below_ec_ev"],
        )
        and all(item["unit"] == "cm^-3 eV^-1" for item in families),
        "NTA WTA=0.08 eV; NGA WGA=0.2 eV and EGA=0.5 eV below Ec",
    )
    source_symbols = {row.get("parameter_symbol") for row in literature}
    add_check(
        checks,
        "source:two_e1_rows_and_device_mismatch_remain_explicit",
        len(literature) == 2
        and source_symbols == {"NTA", "NGA"}
        and all(row.get("evidence_level") == "E1" for row in literature)
        and all(
            row.get("doi") == bulk_input["literature_input"]["doi"]
            for row in literature
        )
        and "symmetric dual gate"
        in bulk_input["literature_input"]["project_mismatch"]
        and "caption says donor-like"
        in next(row for row in literature if row["parameter_symbol"] == "NGA")[
            "limitations"
        ],
        f"rows={len(literature)} symbols={sorted(source_symbols)}",
    )
    model = config["bulk_trap_model_inheritance"]
    source_model = bulk_input["bulk_trap_model"]
    source_integration = bulk_input["energy_integration"]
    add_check(
        checks,
        "model:equations_energy_grid_and_analytic_jacobian_are_unchanged",
        model["model_kind"] == source_model["model_kind"]
        and model["energy_variable"] == source_model["energy_variable"]
        and model["energy_domain_ev"] == source_model["energy_domain_ev"]
        and model["integration_method"] == source_integration["method"]
        and model["integration_order"] == source_integration["order"] == 96
        and model["electron_occupancy_formula"]
        == source_model["electron_occupancy_formula"]
        and model["physical_trapped_charge_density_formula"]
        == source_model["physical_trapped_charge_density_formula"]
        and model["poisson_insertion"] == source_model["poisson_insertion"]
        and model["analytic_electrons_jacobian_required"] is True
        and model["zero_density_limit_must_exactly_restore_t02_c"] is True,
        f"model={model['model_kind']} integration={model['integration_order']}",
    )
    protocol = config["bias_protocol"]
    source_protocol = bulk_input["bias_protocol"]
    t02_protocol = t02_config["bias_protocol"]
    add_check(
        checks,
        "bias:t02_c_prefix_and_v2_common_high_gate_extension_are_exact",
        close(protocol["source_v"], t02_protocol["source_v"])
        and close(protocol["drain_v"], t02_protocol["drain_v"])
        and protocol["low_vds_values_v"] == t02_protocol["low_vds_values_v"]
        and protocol["primary_negative_preconditioning_v"]
        == t02_protocol["primary_negative_preconditioning_v"]
        and primary_grid(protocol["primary_gate_grid"])[
            : len(primary_grid(t02_protocol["primary_gate_grid"]))
        ]
        == primary_grid(t02_protocol["primary_gate_grid"])
        == primary_grid(source_protocol["primary_gate_grid"])
        and len(primary_grid(protocol["primary_gate_grid"])) == 45
        and close(protocol["primary_gate_grid"]["stop_v"], 1.7)
        and protocol["primary_gate_grid"]["point_count"] == 45
        and protocol["primary_gate"] == "top_gate"
        and protocol["secondary_gate"] == "bottom_gate"
        and close(protocol["fixed_secondary_gate_v"], 0.0)
        and protocol["reverse_paths"] == [],
        (
            f"VDS={protocol['drain_v']} grid={primary_grid(protocol['primary_gate_grid'])[0]}"
            f":{primary_grid(protocol['primary_gate_grid'])[-1]}"
        ),
    )
    extraction = config["extraction_methods"]
    dit_extraction = dit_formal["extraction_methods"]
    add_check(
        checks,
        "extraction:vth_gm_ss_and_low_gate_current_are_pre_registered",
        extraction["constant_current_vth_proxy"]
        == dit_extraction["constant_current_vth_proxy"]
        and extraction["gm_proxy"] == dit_extraction["gm_proxy"]
        and extraction["ss_proxy"] == dit_extraction["ss_proxy"]
        and extraction["low_gate_current_proxy"]["name"]
        == dit_extraction["ioff_proxy"]["name"]
        and close(
            extraction["low_gate_current_proxy"]["evaluation_top_gate_v"],
            dit_extraction["ioff_proxy"]["evaluation_top_gate_v"],
        )
        and extraction["low_gate_current_proxy"]["physical_ioff_claim_permitted"]
        is False
        and "same family"
        in extraction["delta_vth_proxy"]["reference_rule"],
        "VTH=1e-5 A/cm; gm at VTH+0.2 V; SS=1e-7..1e-6 A/cm; low gate=-0.5 V",
    )
    directional = config["directional_hypotheses"]
    add_check(
        checks,
        "hypotheses:directions_are_registered_diagnostics_not_completion_gates",
        directional["completion_gate"] is False
        and len(directional["registered"]) == 2
        and "contrary or non-monotonic trend is retained"
        in directional["failure_rule"]
        and "diagnostic rather than a completion gate" in directional["reason"],
        directional["failure_rule"],
    )
    state = config["state_output_contract"]
    add_check(
        checks,
        "outputs:eight_common_states_include_potential_density_traps_and_current",
        close(state["common_primary_gate_v"], 0.3)
        and state["required_state_count_per_family"] == 4
        and state["required_total_state_count"] == 8
        and state["required_vtk_file_count_per_state"] == 6
        and state["required_total_vtk_file_count"] == 48
        and state["potential"]["unit"] == "V"
        and state["electron_density"]["unit"] == "cm^-3"
        and state["occupied_bulk_trap_density"]["unit"] == "cm^-3"
        and state["electron_current_density"]["unit"] == "A/cm^2",
        "states=8 VTK=48 fields=potential/electrons/occupied traps/current density",
    )
    retention = config["failure_retention"]
    add_check(
        checks,
        "failure:failed_runs_are_archived_without_threshold_relaxation",
        retention["preserve_every_failed_run"] is True
        and retention["never_delete_or_overwrite_failed_evidence"] is True
        and "<failure_slug>" in retention["archive_directory_pattern"]
        and "<failure_slug>" in retention["archive_report_pattern"]
        and len(retention["required_failure_artifacts"]) == 6
        and "new config revision" in retention["acceptance_change_rule"]
        and "complete rerun" in retention["acceptance_change_rule"]
        and set(retention["prohibited_recovery"])
        == {
            "delete failed evidence",
            "silently relax an acceptance threshold",
            "drop a literature point after seeing its result",
            "reuse a partially solved device as a replacement control",
        },
        retention["acceptance_change_rule"],
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "resource:eight_devices_360_points_440_dc_fit_laptop_budget",
        budget["required_family_count"] == 2
        and budget["required_device_count_per_family"] == 4
        and budget["required_total_device_count"] == 8
        and budget["required_formal_device_count"] == 6
        and budget["required_control_device_count"] == 2
        and budget["required_reported_point_count_per_device"] == 45
        and budget["required_total_reported_point_count"] == 360
        and budget["required_dc_solve_count_per_device"] == 55
        and budget["required_total_dc_solve_count"] == 440
        and budget["maximum_wall_seconds"] <= 600.0
        and budget["laptop_target"] is True,
        json.dumps(budget, sort_keys=True),
    )
    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:counts_isolation_convergence_and_independent_check_are_frozen",
        acceptance["required_family_order"] == ["NTA", "NGA"]
        and acceptance["required_nta_values_cm3_ev"]
        == family_map["NTA"]["execution_values_cm3_ev"]
        and acceptance["required_nga_values_cm3_ev"]
        == family_map["NGA"]["execution_values_cm3_ev"]
        and acceptance["required_formal_points_per_family"] == 3
        and acceptance["required_control_points_per_family"] == 1
        and acceptance["required_primary_gate_point_count"] == 45
        and acceptance["required_total_reported_point_count"] == 360
        and acceptance["required_total_dc_solve_count"] == 440
        and acceptance["require_all_dc_solves_converged"] is True
        and acceptance["require_exact_isolation_for_every_device"] is True
        and acceptance["require_both_interface_dit_zero"] is True
        and acceptance["require_independent_persisted_evidence_check"] is True,
        "families=2 formal=6 controls=2 points=360 solves=440 independent=required",
    )
    add_check(
        checks,
        "acceptance:numerical_tolerances_are_not_weaker_than_upstream_contract",
        acceptance["maximum_relative_terminal_current_imbalance"]
        <= bulk_input["acceptance"][
            "maximum_future_relative_terminal_current_imbalance"
        ]
        and acceptance[
            "maximum_each_zero_control_t02_c_current_relative_difference"
        ]
        <= bulk_input["acceptance"][
            "maximum_future_zero_control_t02_c_current_relative_difference"
        ]
        and acceptance["minimum_ss_fit_r_squared"]
        == dit_formal["acceptance"]["minimum_ss_fit_r_squared"]
        and acceptance["minimum_augmented_ss_sample_count"]
        == extraction["ss_proxy"]["minimum_augmented_sample_count"]
        and acceptance[
            "minimum_each_family_maximum_common_state_current_relative_response"
        ]
        >= bulk_input["acceptance"][
            "minimum_future_nonzero_common_state_relative_response"
        ]
        and acceptance["require_vth_bracket_for_every_device"] is True
        and acceptance["require_positive_finite_gm"] is True
        and acceptance["require_positive_finite_ss"] is True
        and acceptance["require_finite_positive_low_gate_current"] is True
        and acceptance[
            "maximum_zero_control_equilibrium_absolute_potential_v"
        ]
        == v1_config["acceptance"][
            "maximum_zero_equilibrium_absolute_potential_v"
        ]
        and acceptance[
            "maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"
        ]
        == v1_config["acceptance"][
            "maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"
        ]
        and acceptance[
            "require_all_nonzero_trap_equilibrium_internal_potentials_finite"
        ]
        is True
        and acceptance[
            "require_near_zero_internal_potential_only_for_zero_controls"
        ]
        is True,
        (
            f"imbalance={acceptance['maximum_relative_terminal_current_imbalance']} "
            f"R2={acceptance['minimum_ss_fit_r_squared']}"
        ),
    )
    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:fourteen_unique_stage_scoped_paths_are_frozen",
        len(outputs) == 14
        and len(set(outputs.values())) == 14
        and all(
            "t03_p2_bulk_traps_formal" in value
            or "p2_bulk_traps_formal" in value
            for value in outputs.values()
        )
        and all("v2" in value for value in outputs.values())
        and outputs["contract_report"]
        == "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v2.json",
        f"outputs={len(outputs)} unique={len(set(outputs.values()))}",
    )
    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:contract_is_not_formal_simulation_or_physical_validation",
        "statically checked without running DEVSIM"
        in boundary["allowed_claim_after_contract_pass"]
        and "numerical proxies"
        in boundary["allowed_claim_after_future_run_and_independent_check"]
        and "before both the runner and independent" in prohibited
        and "measured, extracted, fitted, calibrated" in prohibited
        and "Only this V2 formal contract PASS permits"
        in boundary["next_gate"]
        and "P3, P5, M00, M01" in boundary["next_gate"],
        boundary["allowed_claim_after_contract_pass"],
    )
    add_check(
        checks,
        "contract:no_simulation_is_run_by_this_checker",
        config.get("status") == "planned"
        and config.get("evidence_level_before_run") == "E0"
        and machine_evidence.get("simulation_status")
        == "NOT_RUN_BY_CONTRACT_CHECK"
        and machine_evidence.get("formal_sensitivity_completed") is False,
        "simulation=NOT_RUN_BY_CONTRACT_CHECK formal_sensitivity_completed=false",
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
        "planned_formal_sensitivity": {
            "families": {
                item["family_id"]: item["execution_values_cm3_ev"]
                for item in families
            },
            "device_count": budget["required_total_device_count"],
            "reported_point_count": budget["required_total_reported_point_count"],
            "dc_solve_count": budget["required_total_dc_solve_count"],
            "state_count": state["required_total_state_count"],
            "formal_sensitivity_run": False,
        },
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
        f"T03_P2_BULK_TRAPS_FORMAL_CONTRACT_{report['status']} "
        f"checks={len(report['checks'])} simulation={report['simulation_status']} "
        f"devices={report['planned_formal_sensitivity']['device_count']} "
        f"dc={report['planned_formal_sensitivity']['dc_solve_count']} "
        f"report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P2_BULK_TRAPS_FORMAL_CONTRACT_ERROR "
            f"{failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
