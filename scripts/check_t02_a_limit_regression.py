#!/usr/bin/env python3
"""Independently validate persisted T02-A limit-regression evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t02_a_dual_gate_contract.json"


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


def same_value(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1.0e-12)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def find_reference(
    report: dict[str, Any], mesh_level: str, vbg_v: float, vds_v: float
) -> dict[str, Any]:
    return next(
        row
        for row in report["bias_points"]
        if row["mesh_level"] == mesh_level
        and same_value(float(row["vgs_v"]), vbg_v)
        and same_value(float(row["vds_v"]), vds_v)
    )


def close_report_csv(report_row: dict[str, Any], csv_row: dict[str, str]) -> bool:
    numeric_fields = [
        "vbg_v",
        "vds_v",
        "source_current_a_per_cm",
        "drain_current_a_per_cm",
        "relative_current_imbalance",
        "center_channel_potential_v",
        "center_channel_electron_density_cm3",
        "relative_current_difference",
        "center_potential_difference_v",
        "center_density_relative_difference",
    ]
    return (
        report_row["stage_id"] == csv_row["stage_id"]
        and report_row["mode_id"] == csv_row["mode_id"]
        and report_row["mesh_level"] == csv_row["mesh_level"]
        and csv_row["vtg_v"] == ""
        and all(
            math.isclose(
                float(report_row[field]),
                float(csv_row[field]),
                rel_tol=1.0e-13,
                abs_tol=1.0e-300,
            )
            for field in numeric_fields
        )
    )


def main() -> int:
    try:
        config = load_json(CONFIG_PATH)
        outputs = config["outputs"]
        report_path = ROOT / outputs["report"]
        report = load_json(report_path)
        contract_path = ROOT / outputs["contract_report"]
        contract = load_json(contract_path)
        snapshot_path = ROOT / outputs["config_snapshot"]
        snapshot = load_json(snapshot_path)
        solver_log_path = ROOT / outputs["solver_log"]
        solver_log = load_json(solver_log_path)
        state_manifest_path = ROOT / outputs["state_manifest"]
        state_manifest = load_json(state_manifest_path)
        disabled_csv_path = ROOT / outputs["disabled_regression_csv"]
        disabled_csv = load_csv(disabled_csv_path)
        topology_csv_path = ROOT / outputs["topology_summary_csv"]
        topology_csv = load_csv(topology_csv_path)
        t01_report_path = ROOT / config["dependencies"]["t01_extraction_report"]
        t01_report = load_json(t01_report_path)
        t01_check_path = ROOT / config["dependencies"]["t01_extraction_check_report"]
        t01_check = load_json(t01_check_path)
    except Exception as error:  # noqa: BLE001
        print(f"T02_A_LIMIT_REGRESSION_CHECK_ERROR {error}", file=sys.stderr)
        return 1

    acceptance = config["acceptance"]
    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config.get("case_id")
        and report.get("stage") == config.get("stage") == "T02-A"
        and report.get("evidence_level") == "E2",
        f"status={report.get('status')} case={report.get('case_id')} stage={report.get('stage')}",
    )

    contract_checks = contract.get("checks", [])
    add_check(
        checks,
        "contract:static_gate_passed_before_simulation",
        contract.get("status") == "PASS"
        and contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and len(contract_checks) == 16
        and all(check["status"] == "PASS" for check in contract_checks)
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH),
        f"checks={len(contract_checks)} simulation={contract.get('simulation_status')}",
    )

    snapshot_inputs = snapshot.get("inputs", {})
    input_hashes_valid = bool(snapshot_inputs)
    for entry in snapshot_inputs.values():
        path = ROOT / entry["path"]
        input_hashes_valid = (
            input_hashes_valid
            and path.is_file()
            and sha256(path) == entry["sha256"]
        )
    add_check(
        checks,
        "inputs:snapshot_hashes_match",
        snapshot.get("case_id") == config["case_id"]
        and snapshot.get("stage") == "T02-A"
        and len(snapshot_inputs) == 6
        and input_hashes_valid,
        f"snapshot={snapshot_path.relative_to(ROOT)} inputs={len(snapshot_inputs)}",
    )

    add_check(
        checks,
        "dependencies:complete_t01_evidence_is_still_pass",
        t01_report.get("status") == "PASS"
        and t01_report.get("t01_completion", {}).get("complete_t01_numerical_stage_gate")
        == "PASS"
        and t01_report.get("t01_completion", {}).get("t02_stage_permitted_next") is True
        and t01_check.get("status") == "PASS"
        and not t01_check.get("failures"),
        (
            f"T01={t01_report.get('status')} independent={t01_check.get('status')} "
            f"next={t01_report.get('t01_completion', {}).get('t02_stage_permitted_next')}"
        ),
    )

    runs = solver_log.get("runs", [])
    solver_records = [record for run in runs for record in run.get("solver_records", [])]
    run_counts = [len(run.get("solver_records", [])) for run in runs]
    labels = [record.get("label", "") for record in solver_records]
    add_check(
        checks,
        "solver:two_fresh_runs_and_all_dc_converged",
        len(runs) == 2
        and run_counts
        == [
            acceptance["required_disabled_dc_solve_count"],
            acceptance["required_enabled_zero_bias_dc_solve_count"],
        ]
        and len(solver_records) == acceptance["required_total_dc_solve_count"]
        and all(record.get("converged") is True for record in solver_records)
        and labels[0] == "T02_A_DISABLED_POISSON_ZERO_BIAS"
        and labels[-2:] == [
            "T02_A_ENABLED_POISSON_ZERO_BIAS",
            "T02_A_ENABLED_COUPLED_ZERO_BIAS",
        ]
        and not solver_log.get("errors"),
        f"runs={len(runs)} counts={run_counts} records={len(solver_records)}",
    )

    topology_report = report.get("topology", [])
    topology_by_enabled = {
        bool(row["top_coupling_enabled"]): row for row in topology_report
    }
    disabled_topology = topology_by_enabled.get(False)
    enabled_topology = topology_by_enabled.get(True)
    parsed_topology_csv: dict[bool, dict[str, Any]] = {}
    for row in topology_csv:
        enabled = row["top_coupling_enabled"].lower() == "true"
        parsed_topology_csv[enabled] = {
            "mode_id": row["mode_id"],
            "regions": json.loads(row["regions_json"]),
            "contacts": json.loads(row["contacts_json"]),
            "interfaces": json.loads(row["interfaces_json"]),
            "nodes": int(row["node_count_with_interface_duplicates"]),
            "elements": int(row["element_count"]),
            "solves": int(row["dc_solve_count"]),
        }
    add_check(
        checks,
        "topology:disabled_and_enabled_domains_are_distinct",
        len(topology_report) == len(topology_csv) == 2
        and disabled_topology is not None
        and enabled_topology is not None
        and disabled_topology["regions"] == sorted(acceptance["required_disabled_regions"])
        and disabled_topology["contacts"] == sorted(acceptance["required_disabled_contacts"])
        and disabled_topology["interfaces"] == ["bottom_oxide_channel"]
        and enabled_topology["regions"] == sorted(acceptance["required_enabled_regions"])
        and enabled_topology["contacts"] == sorted(acceptance["required_enabled_contacts"])
        and enabled_topology["interfaces"]
        == sorted(["bottom_oxide_channel", "channel_top_oxide"])
        and int(enabled_topology["node_count_with_interface_duplicates"])
        > int(disabled_topology["node_count_with_interface_duplicates"]),
        (
            f"disabled_nodes={disabled_topology.get('node_count_with_interface_duplicates') if disabled_topology else None} "
            f"enabled_nodes={enabled_topology.get('node_count_with_interface_duplicates') if enabled_topology else None}"
        ),
    )
    add_check(
        checks,
        "outputs:topology_csv_matches_json",
        set(parsed_topology_csv) == {False, True}
        and all(
            parsed_topology_csv[enabled]["mode_id"] == topology_by_enabled[enabled]["mode_id"]
            and parsed_topology_csv[enabled]["regions"] == topology_by_enabled[enabled]["regions"]
            and parsed_topology_csv[enabled]["contacts"] == topology_by_enabled[enabled]["contacts"]
            and parsed_topology_csv[enabled]["interfaces"] == topology_by_enabled[enabled]["interfaces"]
            and parsed_topology_csv[enabled]["nodes"]
            == int(topology_by_enabled[enabled]["node_count_with_interface_duplicates"])
            and parsed_topology_csv[enabled]["elements"]
            == int(topology_by_enabled[enabled]["element_count"])
            and parsed_topology_csv[enabled]["solves"]
            == int(topology_by_enabled[enabled]["dc_solve_count"])
            for enabled in (False, True)
        ),
        f"rows={len(topology_csv)}",
    )

    disabled_rows = report.get("disabled_regression_points", [])
    expected_vbg = [
        float(value) for value in acceptance["required_disabled_bottom_gate_values_v"]
    ]
    add_check(
        checks,
        "bias:disabled_regression_grid_and_csv",
        len(disabled_rows) == len(disabled_csv) == acceptance["required_disabled_reported_point_count"]
        and [float(row["vbg_v"]) for row in disabled_rows] == expected_vbg
        and all(row["vtg_v"] is None for row in disabled_rows)
        and all(
            close_report_csv(report_row, csv_row)
            for report_row, csv_row in zip(disabled_rows, disabled_csv, strict=True)
        ),
        f"rows={len(disabled_rows)} VBG={[row['vbg_v'] for row in disabled_rows]}",
    )

    currents = [abs(float(row["drain_current_a_per_cm"])) for row in disabled_rows]
    max_imbalance = max(
        float(row["relative_current_imbalance"]) for row in disabled_rows
    )
    add_check(
        checks,
        "current:disabled_limit_is_conserved_and_monotonic",
        all(math.isfinite(value) and value > 0.0 for value in currents)
        and all(next_value >= value for value, next_value in zip(currents, currents[1:]))
        and max_imbalance <= acceptance["maximum_relative_terminal_current_imbalance"],
        f"max_imbalance={max_imbalance:.6e} currents={currents}",
    )

    recomputed_current_differences: list[float] = []
    recomputed_potential_differences: list[float] = []
    recomputed_density_differences: list[float] = []
    reference_match = True
    for row in disabled_rows:
        reference = find_reference(
            t01_report,
            row["mesh_level"],
            float(row["vbg_v"]),
            float(row["vds_v"]),
        )
        current = abs(float(row["drain_current_a_per_cm"]))
        reference_current = abs(float(reference["drain_current_a_per_cm"]))
        current_difference = abs(current - reference_current) / max(
            current, reference_current, 1.0e-300
        )
        potential_difference = abs(
            float(row["center_channel_potential_v"])
            - float(reference["center_channel_potential_v"])
        )
        density = float(row["center_channel_electron_density_cm3"])
        reference_density = float(reference["center_channel_electron_density_cm3"])
        density_difference = abs(density - reference_density) / max(
            abs(density), abs(reference_density), 1.0e-300
        )
        recomputed_current_differences.append(current_difference)
        recomputed_potential_differences.append(potential_difference)
        recomputed_density_differences.append(density_difference)
        reference_match = reference_match and all(
            math.isclose(left, right, rel_tol=1.0e-13, abs_tol=1.0e-300)
            for left, right in (
                (current_difference, float(row["relative_current_difference"])),
                (potential_difference, float(row["center_potential_difference_v"])),
                (density_difference, float(row["center_density_relative_difference"])),
                (
                    reference_current,
                    float(row["t01_reference_abs_drain_current_a_per_cm"]),
                ),
            )
        )
    max_current_difference = max(recomputed_current_differences)
    max_potential_difference = max(recomputed_potential_differences)
    max_density_difference = max(recomputed_density_differences)
    add_check(
        checks,
        "regression:t01_terminal_and_internal_state_recomputed",
        reference_match
        and max_current_difference
        <= acceptance["maximum_disabled_t01_relative_current_difference"]
        and max_potential_difference
        <= acceptance["maximum_disabled_t01_center_potential_difference_v"]
        and max_density_difference
        <= acceptance["maximum_disabled_t01_center_density_relative_difference"],
        (
            f"max_current_rel={max_current_difference:.6e} "
            f"max_potential_v={max_potential_difference:.6e} "
            f"max_density_rel={max_density_difference:.6e}"
        ),
    )

    entries = state_manifest.get("entries", [])
    state_entry = entries[0] if len(entries) == 1 else None
    state_rows: list[dict[str, str]] = []
    state_hashes_valid = False
    if state_entry is not None:
        state_path = ROOT / state_entry["state_csv"]
        state_rows = load_csv(state_path)
        state_hashes_valid = sha256(state_path) == state_entry["state_csv_sha256"]
        for item in state_entry["vtk_files"]:
            path = ROOT / item["path"]
            state_hashes_valid = (
                state_hashes_valid
                and path.is_file()
                and path.stat().st_size > 0
                and sha256(path) == item["sha256"]
            )
    state_regions = sorted({row["region"] for row in state_rows})
    potentials = [abs(float(row["potential_v"])) for row in state_rows]
    channel_densities = [
        float(row["electron_density_cm3"])
        for row in state_rows
        if row["region"] == "channel"
    ]
    add_check(
        checks,
        "state:enabled_zero_bias_nodes_and_vtk_are_hash_locked",
        state_entry is not None
        and state_hashes_valid
        and state_regions == sorted(acceptance["required_enabled_regions"])
        and len(state_rows) == state_entry["node_count_with_interface_duplicates"]
        and len(state_rows) == int(enabled_topology["node_count_with_interface_duplicates"])
        and bool(state_entry["vtk_files"]),
        f"rows={len(state_rows)} regions={state_regions} vtk={len(state_entry['vtk_files']) if state_entry else 0}",
    )
    max_enabled_current = (
        max(
            abs(float(state_entry["source_current_a_per_cm"])),
            abs(float(state_entry["drain_current_a_per_cm"])),
        )
        if state_entry
        else math.inf
    )
    max_enabled_potential = max(potentials, default=math.inf)
    add_check(
        checks,
        "state:enabled_zero_bias_equilibrium_recomputed",
        bool(channel_densities)
        and all(math.isfinite(value) and value > 0.0 for value in channel_densities)
        and max_enabled_current
        <= acceptance["maximum_enabled_zero_bias_absolute_terminal_current_a_per_cm"]
        and max_enabled_potential
        <= acceptance["maximum_enabled_zero_bias_absolute_potential_v"],
        (
            f"max_current={max_enabled_current:.6e} max_potential={max_enabled_potential:.6e} "
            f"channel_nodes={len(channel_densities)}"
        ),
    )

    required_files = [
        report_path,
        contract_path,
        snapshot_path,
        solver_log_path,
        state_manifest_path,
        disabled_csv_path,
        topology_csv_path,
    ]
    add_check(
        checks,
        "outputs:required_evidence_files_exist",
        all(path.is_file() and path.stat().st_size > 0 for path in required_files),
        f"files={len(required_files)}",
    )

    runner_checks = report.get("checks", {})
    completion = report.get("t02_a_completion", {})
    add_check(
        checks,
        "runner:stage_gate_and_evidence_boundary",
        len(runner_checks) == 10
        and all(value["status"] == "PASS" for value in runner_checks.values())
        and completion.get("status") == "PASS"
        and completion.get("disabled_top_stack_returns_t01") is True
        and completion.get("enabled_zero_bias_topology_smoke") is True
        and completion.get("t02_b_minimal_bias_family_permitted_next") is True
        and completion.get("t02_complete") is False
        and completion.get("nonzero_dual_gate_coupling_verified") is False
        and "T02 complete" in report["evidence_boundary"]["prohibited_claims"],
        (
            f"runner_checks={len(runner_checks)} next="
            f"{completion.get('t02_b_minimal_bias_family_permitted_next')} "
            f"complete={completion.get('t02_complete')}"
        ),
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    check_report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "checks": checks,
        "failures": failures,
        "recomputed_maximum_relative_terminal_current_imbalance": max_imbalance,
        "recomputed_maximum_disabled_t01_relative_current_difference": max_current_difference,
        "recomputed_maximum_disabled_t01_center_potential_difference_v": max_potential_difference,
        "recomputed_maximum_disabled_t01_center_density_relative_difference": max_density_difference,
        "recomputed_enabled_zero_bias_maximum_absolute_terminal_current_a_per_cm": max_enabled_current,
        "recomputed_enabled_zero_bias_maximum_absolute_potential_v": max_enabled_potential,
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        json.dumps(check_report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T02_A_LIMIT_REGRESSION_CHECK_{check_report['status']} "
        f"checks={len(checks)} report={check_path}"
    )
    for failure in failures:
        print(
            f"T02_A_LIMIT_REGRESSION_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
