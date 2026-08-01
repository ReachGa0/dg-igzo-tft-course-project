#!/usr/bin/env python3
"""Independently validate persisted T03-P2-DIT equation-smoke evidence."""

from __future__ import annotations

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


def close(left: float, right: float, *, rel_tol: float = 1e-10, abs_tol: float = 1e-15) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), 1e-300)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report_path = ROOT / outputs["report"]
    report = load_json(report_path)
    case_path = ROOT / outputs["case_summary_csv"]
    interface_path = ROOT / outputs["interface_samples_csv"]
    state_path = ROOT / outputs["state_nodes_csv"]
    solver_path = ROOT / outputs["solver_log"]
    snapshot_path = ROOT / outputs["config_snapshot"]
    case_rows, case_fields = load_csv(case_path)
    interface_rows, interface_fields = load_csv(interface_path)
    state_rows, state_fields = load_csv(state_path)
    solver_log = load_json(solver_path)
    snapshot = load_json(snapshot_path)
    checks: list[dict[str, Any]] = []
    expected_cases = config["acceptance"]["required_case_ids"]
    by_case = {row["case_id"]: row for row in case_rows}

    add_check(
        checks,
        "identity:report_and_config_match",
        report["case_id"] == config["case_id"]
        and report["stage"] == config["stage"]
        and report["parameter_group_id"] == "P2"
        and report["formal_sensitivity_run"] is False
        and report["contract_report"]["status"] == "PASS"
        and report["contract_report"]["sha256"] == sha256(ROOT / report["contract_report"]["path"]),
        f"case={report.get('case_id')} stage={report.get('stage')} formal_scan={report.get('formal_sensitivity_run')}",
    )
    add_check(
        checks,
        "inputs:snapshot_hashes_and_formal_scan_flag_match",
        snapshot["case_id"] == config["case_id"]
        and snapshot["formal_sensitivity_run"] is False
        and all(
            item["sha256"] == sha256(ROOT / item["path"])
            for item in snapshot["inputs"].values()
        ),
        f"inputs={len(snapshot['inputs'])}",
    )
    add_check(
        checks,
        "outputs:csv_headers_and_case_order_match_contract",
        case_fields == [
            "case_id", "solve_mode", "interface_equation_active", "dit_cm2_ev",
            "interface_trap_capacitance_f_per_cm2", "source_v", "drain_v", "vbg_v",
            "vtg_v", "mesh_level", "node_count_with_interface_duplicates", "element_count",
            "dc_solve_count", "all_dc_solves_converged", "source_current_a_per_cm",
            "drain_current_a_per_cm", "relative_current_imbalance",
            "center_channel_potential_v", "center_channel_electron_density_cm3",
            "maximum_interface_potential_discontinuity_v", "center_interface_x_cm",
            "center_interface_potential_r0_v", "center_interface_potential_r1_v",
            "center_devsim_fluxterm_c_per_cm2", "center_physical_qit_c_per_cm2",
            "center_d_oxide_y_c_per_cm2", "center_d_channel_y_c_per_cm2",
            "center_displacement_jump_c_per_cm2", "center_gauss_absolute_error_c_per_cm2",
            "center_gauss_relative_error", "wall_seconds",
        ]
        and interface_fields == [
            "case_id", "solve_mode", "interface_equation_active", "dit_cm2_ev",
            "x_cm", "y_cm", "x_um", "y_nm", "potential_r0_v", "potential_r1_v",
            "potential_difference_v", "devsim_fluxterm_c_per_cm2",
            "physical_qit_c_per_cm2", "formula_fluxterm_c_per_cm2",
        ]
        and state_fields == [
            "case_id", "solve_mode", "interface_equation_active", "dit_cm2_ev",
            "source_v", "drain_v", "vbg_v", "vtg_v", "region", "x_cm", "y_cm",
            "x_um", "y_nm", "potential_v", "electron_density_cm3",
        ]
        and [row["case_id"] for row in case_rows] == expected_cases,
        f"case_fields={len(case_fields)} interface_fields={len(interface_fields)} state_fields={len(state_fields)}",
    )
    add_check(
        checks,
        "counts:five_cases_17_solves_12095_raw_rows",
        len(case_rows) == 5
        and [int(row["dc_solve_count"]) for row in case_rows] == [1, 1, 1, 7, 7]
        and solver_log["total_dc_solve_count"] == 17
        and sum(len(item["records"]) for item in solver_log["runs"]) == 17
        and len(state_rows) == 5 * 2419
        and len(interface_rows) == 5 * 39,
        f"cases={len(case_rows)} solves={solver_log['total_dc_solve_count']} state_rows={len(state_rows)} interface_rows={len(interface_rows)}",
    )
    add_check(
        checks,
        "solver:all_persisted_records_converged",
        all(bool(record["converged"]) for run in solver_log["runs"] for record in run["records"])
        and all(row["all_dc_solves_converged"] == "True" for row in case_rows),
        f"records={sum(len(item['records']) for item in solver_log['runs'])}",
    )
    topology_valid = all(
        int(row["node_count_with_interface_duplicates"]) == 2419
        and int(row["element_count"]) == 4480
        and row["mesh_level"] == "interface_4x"
        for row in case_rows
    )
    add_check(
        checks,
        "topology:every_case_matches_enabled_t02_stack",
        topology_valid,
        f"nodes={sorted({row['node_count_with_interface_duplicates'] for row in case_rows})} elements={sorted({row['element_count'] for row in case_rows})}",
    )
    active_case = report["case_summaries"][2]
    inactive_case = report["case_summaries"][0]
    add_check(
        checks,
        "equation:active_case_has_fluxterm_and_inactive_case_does_not",
        "InterfaceTrapChargeEquation" in active_case["bottom_interface_equations"]
        and "PotentialEquation" in active_case["bottom_interface_equations"]
        and active_case["interface_trap_equation_command"]["type"] == "fluxterm"
        and inactive_case["bottom_interface_equations"] == ["PotentialEquation"]
        and active_case["top_interface_equations"] == ["PotentialEquation"]
        and inactive_case["top_interface_equations"] == ["PotentialEquation"],
        f"active={active_case['bottom_interface_equations']} inactive={inactive_case['bottom_interface_equations']}",
    )
    state_by_case: dict[str, list[dict[str, str]]] = {}
    for case_id in expected_cases:
        state_by_case[case_id] = [row for row in state_rows if row["case_id"] == case_id]
    ref_map = {
        (row["region"], row["x_cm"], row["y_cm"]): float(row["potential_v"])
        for row in state_by_case["electrostatic_reference_no_equation"]
    }
    zero_map = {
        (row["region"], row["x_cm"], row["y_cm"]): float(row["potential_v"])
        for row in state_by_case["electrostatic_zero_dit_equation"]
    }
    zero_diff = max(abs(ref_map[key] - zero_map[key]) for key in ref_map)
    add_check(
        checks,
        "zero_limit:reference_and_zero_dit_node_potentials_match",
        ref_map.keys() == zero_map.keys()
        and zero_diff <= float(config["acceptance"]["maximum_zero_dit_electrostatic_potential_difference_v"]),
        f"maximum_node_potential_difference={zero_diff:.6e} V",
    )
    interface_formula_error = 0.0
    interface_sign_error = 0.0
    max_continuity = 0.0
    for row in interface_rows:
        interface_formula_error = max(
            interface_formula_error,
            abs(
                float(row["devsim_fluxterm_c_per_cm2"])
                - float(row["formula_fluxterm_c_per_cm2"])
            ),
        )
        interface_sign_error = max(
            interface_sign_error,
            abs(
                float(row["physical_qit_c_per_cm2"])
                + float(row["devsim_fluxterm_c_per_cm2"])
            ),
        )
        max_continuity = max(max_continuity, abs(float(row["potential_difference_v"])))
    add_check(
        checks,
        "interface:formula_sign_and_continuity_persisted_values_match",
        interface_formula_error <= 1e-20
        and interface_sign_error <= 1e-20
        and max_continuity <= float(config["acceptance"]["maximum_interface_potential_discontinuity_v"]),
        f"formula={interface_formula_error:.6e} sign={interface_sign_error:.6e} continuity={max_continuity:.6e}",
    )
    representative = by_case["electrostatic_representative_dit_equation"]
    add_check(
        checks,
        "gauss:representative_case_matches_interface_displacement_jump",
        float(representative["center_gauss_relative_error"])
        <= float(config["acceptance"]["maximum_center_gauss_relative_error"])
        and float(representative["center_physical_qit_c_per_cm2"]) < 0.0,
        f"relative_error={representative['center_gauss_relative_error']} Qit={representative['center_physical_qit_c_per_cm2']}",
    )
    reference = by_case["electrostatic_reference_no_equation"]
    potential_change = abs(
        float(representative["center_channel_potential_v"])
        - float(reference["center_channel_potential_v"])
    )
    add_check(
        checks,
        "response:representative_dit_has_nonzero_electrostatic_effect",
        abs(float(representative["center_physical_qit_c_per_cm2"]))
        >= float(config["acceptance"]["minimum_representative_sheet_charge_magnitude_c_per_cm2"])
        and potential_change
        >= float(config["acceptance"]["minimum_representative_electrostatic_potential_change_v"]),
        f"Qit={representative['center_physical_qit_c_per_cm2']} potential_change={potential_change:.6e} V",
    )
    coupled_zero = by_case["coupled_zero_dit_equation"]
    t02_rows, _ = load_csv(ROOT / "results/tables/tcad_t02_c_bidirectional_families.csv")
    t02_ref = next(
        row
        for row in t02_rows
        if row["family_id"] == "top_primary"
        and row["sweep_direction"] == "forward"
        and close(row["fixed_secondary_gate_v"], 0.0)
        and close(row["primary_gate_v"], 0.1)
        and close(row["vds_v"], 0.01)
    )
    t02_current_relative = relative_difference(
        abs(float(coupled_zero["drain_current_a_per_cm"])),
        abs(float(t02_ref["drain_current_a_per_cm"])),
    )
    t02_potential_difference = abs(
        float(coupled_zero["center_channel_potential_v"])
        - float(t02_ref["center_channel_potential_v"])
    )
    t02_density_relative = relative_difference(
        float(coupled_zero["center_channel_electron_density_cm3"]),
        float(t02_ref["center_channel_electron_density_cm3"]),
    )
    add_check(
        checks,
        "regression:zero_dit_coupled_case_reproduces_t02_c_reference",
        t02_current_relative <= float(config["acceptance"]["maximum_t02_c_reference_current_relative_difference"])
        and t02_potential_difference <= float(config["acceptance"]["maximum_t02_c_reference_center_potential_difference_v"])
        and t02_density_relative <= float(config["acceptance"]["maximum_t02_c_reference_center_density_relative_difference"]),
        f"current={t02_current_relative:.6e} potential={t02_potential_difference:.6e} density={t02_density_relative:.6e}",
    )
    coupled_representative = by_case["coupled_representative_dit_equation"]
    current_ratio = abs(float(coupled_representative["drain_current_a_per_cm"])) / max(
        abs(float(coupled_zero["drain_current_a_per_cm"])), 1e-300
    )
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in case_rows if row["solve_mode"] == "coupled")
    add_check(
        checks,
        "coupled:conservation_and_representative_current_direction_match",
        max_imbalance <= float(config["acceptance"]["maximum_relative_terminal_current_imbalance"])
        and current_ratio < 1.0,
        f"maximum_imbalance={max_imbalance:.6e} representative_to_zero_ratio={current_ratio:.6e}",
    )
    artifact_paths = {
        "config_snapshot": snapshot_path,
        "solver_log": solver_path,
        "case_summary_csv": case_path,
        "interface_samples_csv": interface_path,
        "state_nodes_csv": state_path,
    }
    add_check(
        checks,
        "artifacts:all_reported_hashes_and_files_match",
        all(
            item["sha256"] == sha256(ROOT / item["path"])
            and (ROOT / item["path"]).is_file()
            for item in report["artifacts"].values()
        )
        and all(path.is_file() for path in artifact_paths.values())
        and report["resource_usage"]["dc_solve_count"] == 17,
        f"artifacts={len(report['artifacts'])} dc_solves={report['resource_usage']['dc_solve_count']}",
    )
    completion = report["t03_p2_completion"]
    add_check(
        checks,
        "boundary:smoke_does_not_close_formal_dit_or_p2",
        report["evidence_level"] == "E2"
        and completion["dit_interface_equation_smoke_passed"] is True
        and completion["formal_three_point_dit_sensitivity_complete"] is False
        and completion["complete_p2_trap_group"] is False
        and completion["complete_t03_five_group_sensitivity"] is False
        and report["formal_sensitivity_run"] is False,
        json.dumps(completion, sort_keys=True),
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    independent = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_simulation_runner": True,
        "checks": checks,
        "failures": failures,
        "recomputed_diagnostics": {
            "maximum_zero_dit_electrostatic_node_potential_difference_v": zero_diff,
            "maximum_interface_formula_error_c_per_cm2": interface_formula_error,
            "maximum_interface_sign_error_c_per_cm2": interface_sign_error,
            "maximum_interface_potential_discontinuity_v": max_continuity,
            "representative_center_gauss_relative_error": float(representative["center_gauss_relative_error"]),
            "representative_center_potential_change_v": potential_change,
            "t02_c_zero_dit_reproduction": {
                "current_relative": t02_current_relative,
                "center_potential_difference_v": t02_potential_difference,
                "center_density_relative": t02_density_relative,
            },
            "representative_to_zero_dit_current_ratio": current_ratio,
        },
        "artifact_hashes": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in artifact_paths.items()
        },
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(json.dumps(independent, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"T03_P2_DIT_EQUATION_SMOKE_CHECK_{independent['status']} checks={len(checks)} report={check_path}"
    )
    for failure in failures:
        print(
            f"T03_P2_DIT_EQUATION_SMOKE_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
