#!/usr/bin/env python3
"""Independently validate persisted T02-B minimal top-gate evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t02_b_minimal_bias.json"


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


def close_report_csv(report_row: dict[str, Any], csv_row: dict[str, str]) -> bool:
    numeric_fields = [
        "vbg_v",
        "vtg_v",
        "vds_v",
        "source_current_a_per_cm",
        "drain_current_a_per_cm",
        "source_current_terminal_a",
        "drain_current_terminal_a",
        "current_imbalance_a_per_cm",
        "relative_current_imbalance",
        "center_channel_potential_v",
        "center_channel_electron_density_cm3",
        "solve_seconds",
    ]
    return (
        report_row["stage_id"] == csv_row["stage_id"]
        and report_row["mode_id"] == csv_row["mode_id"]
        and report_row["mesh_level"] == csv_row["mesh_level"]
        and report_row["converged"] is True
        and csv_row["converged"].lower() == "true"
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


def nearest_channel_state(
    rows: list[dict[str, str]], geometry: dict[str, Any]
) -> dict[str, float]:
    channel_rows = [row for row in rows if row["region"] == "channel"]
    target_x = float(geometry["channel_length_cm"]) / 2.0
    target_y = float(geometry["bottom_oxide_thickness_cm"]) + float(
        geometry["channel_thickness_cm"]
    ) / 2.0
    row = min(
        channel_rows,
        key=lambda item: (float(item["x_cm"]) - target_x) ** 2
        + (float(item["y_cm"]) - target_y) ** 2,
    )
    return {
        "center_channel_potential_v": float(row["potential_v"]),
        "center_channel_electron_density_cm3": float(
            row["electron_density_cm3"]
        ),
    }


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
        bias_path = ROOT / outputs["bias_csv"]
        bias_csv = load_csv(bias_path)
        state_summary_path = ROOT / outputs["state_summary_csv"]
        state_summary_csv = load_csv(state_summary_path)
        t01_baseline = load_json(ROOT / config["dependencies"]["t01_baseline_config"])
        t02_a_config = load_json(ROOT / config["dependencies"]["t02_a_config"])
        t02_a_report = load_json(ROOT / config["dependencies"]["t02_a_report"])
        t02_a_check = load_json(ROOT / config["dependencies"]["t02_a_check_report"])
    except Exception as error:  # noqa: BLE001
        print(f"T02_B_MINIMAL_CHECK_ERROR {error}", file=sys.stderr)
        return 1

    acceptance = config["acceptance"]
    checks: list[dict[str, Any]] = []
    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T02-B"
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
        and len(contract_checks) == 17
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
        and snapshot.get("stage") == "T02-B"
        and len(snapshot_inputs) == 7
        and input_hashes_valid,
        f"snapshot={snapshot_path.relative_to(ROOT)} inputs={len(snapshot_inputs)}",
    )

    t02_a_completion = t02_a_report.get("t02_a_completion", {})
    add_check(
        checks,
        "dependencies:t02_a_evidence_is_still_pass",
        t02_a_report.get("status") == "PASS"
        and t02_a_check.get("status") == "PASS"
        and not t02_a_check.get("failures")
        and t02_a_completion.get("t02_b_minimal_bias_family_permitted_next") is True
        and t02_a_completion.get("t02_complete") is False,
        (
            f"T02_A={t02_a_report.get('status')} independent={t02_a_check.get('status')} "
            f"next={t02_a_completion.get('t02_b_minimal_bias_family_permitted_next')}"
        ),
    )

    runs = solver_log.get("runs", [])
    solver_records = [record for run in runs for record in run.get("solver_records", [])]
    labels = [record.get("label", "") for record in solver_records]
    add_check(
        checks,
        "solver:fresh_enabled_run_and_all_dc_converged",
        len(runs) == 1
        and len(solver_records) == acceptance["required_total_dc_solve_count"]
        and all(record.get("converged") is True for record in solver_records)
        and labels[0] == "T02_B_POISSON_ZERO_BIAS"
        and labels[1] == "T02_B_COUPLED_ZERO_BIAS"
        and labels[-3:] == [
            "T02_B_VTG_0.1_V",
            "T02_B_VTG_0.2_V",
            "T02_B_VTG_0.3_V",
        ]
        and not solver_log.get("errors"),
        f"runs={len(runs)} records={len(solver_records)} labels={labels}",
    )

    topology = report.get("topology", {})
    t02_a_enabled = next(
        item for item in t02_a_report.get("topology", []) if item["top_coupling_enabled"]
    )
    add_check(
        checks,
        "topology:exact_t02_a_enabled_domain",
        topology.get("regions") == sorted(acceptance["required_regions"])
        and topology.get("contacts") == sorted(acceptance["required_contacts"])
        and topology.get("interfaces") == sorted(acceptance["required_interfaces"])
        and topology.get("node_count_with_interface_duplicates")
        == t02_a_enabled.get("node_count_with_interface_duplicates")
        and topology.get("element_count") == t02_a_enabled.get("element_count"),
        f"nodes={topology.get('node_count_with_interface_duplicates')} elements={topology.get('element_count')}",
    )

    rows = report.get("bias_points", [])
    expected_vtg = [float(value) for value in acceptance["required_top_gate_values_v"]]
    add_check(
        checks,
        "bias:grid_and_csv_match",
        len(rows) == len(bias_csv) == acceptance["required_reported_point_count"]
        and [float(row["vtg_v"]) for row in rows] == expected_vtg
        and all(
            close_report_csv(report_row, csv_row)
            for report_row, csv_row in zip(rows, bias_csv, strict=True)
        ),
        f"rows={len(rows)} VTG={[row['vtg_v'] for row in rows]}",
    )

    currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
    potentials = [float(row["center_channel_potential_v"]) for row in rows]
    densities = [float(row["center_channel_electron_density_cm3"]) for row in rows]
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in rows)
    add_check(
        checks,
        "current:conservation_sign_and_strict_top_gate_control",
        all(math.isfinite(value) and value > 0.0 for value in currents)
        and all(float(row["source_current_a_per_cm"]) < 0.0 for row in rows)
        and all(float(row["drain_current_a_per_cm"]) > 0.0 for row in rows)
        and all(next_value > value for value, next_value in zip(currents, currents[1:]))
        and max_imbalance <= acceptance["maximum_relative_terminal_current_imbalance"],
        f"max_imbalance={max_imbalance:.6e} currents={currents}",
    )

    endpoint_current_ratio = currents[-1] / max(currents[0], 1.0e-300)
    endpoint_potential_increase = potentials[-1] - potentials[0]
    endpoint_density_ratio = densities[-1] / max(densities[0], 1.0e-300)
    add_check(
        checks,
        "state:internal_response_and_endpoint_thresholds",
        all(next_value > value for value, next_value in zip(potentials, potentials[1:]))
        and all(next_value > value for value, next_value in zip(densities, densities[1:]))
        and endpoint_current_ratio >= acceptance["minimum_endpoint_current_ratio"]
        and endpoint_potential_increase
        >= acceptance["minimum_endpoint_center_potential_increase_v"]
        and endpoint_density_ratio >= acceptance["minimum_endpoint_center_density_ratio"],
        (
            f"potential_delta={endpoint_potential_increase:.6e} "
            f"density_ratio={endpoint_density_ratio:.6g} "
            f"current_ratio={endpoint_current_ratio:.6g}"
        ),
    )

    zero_equilibrium = report.get("zero_equilibrium", {})
    add_check(
        checks,
        "equilibrium:zero_bias_is_current_free",
        zero_equilibrium.get("maximum_absolute_terminal_current_a_per_cm", math.inf)
        <= acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"]
        and zero_equilibrium.get("maximum_absolute_potential_v", math.inf)
        <= acceptance["maximum_zero_equilibrium_absolute_potential_v"]
        and zero_equilibrium.get("node_count")
        == topology.get("node_count_with_interface_duplicates"),
        json.dumps(zero_equilibrium, sort_keys=True),
    )

    state_entries = state_manifest.get("entries", [])
    state_summary_match = len(state_entries) == len(state_summary_csv) == 2
    state_hashes_valid = True
    state_rows_by_id: dict[str, list[dict[str, str]]] = {}
    for entry, summary_row in zip(state_entries, state_summary_csv, strict=False):
        state_path = ROOT / entry["state_csv"]
        state_rows = load_csv(state_path)
        state_rows_by_id[entry["state_id"]] = state_rows
        state_hashes_valid = state_hashes_valid and sha256(state_path) == entry["state_csv_sha256"]
        state_hashes_valid = state_hashes_valid and len(state_rows) == entry[
            "node_count_with_interface_duplicates"
        ]
        state_hashes_valid = state_hashes_valid and summary_row["state_id"] == entry["state_id"]
        state_hashes_valid = state_hashes_valid and math.isclose(
            float(summary_row["vtg_v"]), float(entry["bias"]["top_gate_v"])
        )
        for item in entry["vtk_files"]:
            path = ROOT / item["path"]
            state_hashes_valid = (
                state_hashes_valid
                and path.is_file()
                and path.stat().st_size > 0
                and sha256(path) == item["sha256"]
            )
    add_check(
        checks,
        "outputs:endpoint_state_and_vtk_hashes_match",
        state_summary_match
        and [entry["state_id"] for entry in state_entries]
        == acceptance["required_state_ids"]
        and state_hashes_valid
        and all(
            entry["vtk_file_count"] == acceptance["required_vtk_file_count_per_state"]
            for entry in state_entries
        ),
        f"states={[entry['state_id'] for entry in state_entries]}",
    )

    endpoint_state_match = True
    for entry in state_entries:
        state_rows = state_rows_by_id.get(entry["state_id"], [])
        center = nearest_channel_state(state_rows, t01_baseline["geometry"])
        matching_bias = next(
            row
            for row in rows
            if same_value(float(row["vtg_v"]), float(entry["bias"]["top_gate_v"]))
        )
        endpoint_state_match = endpoint_state_match and math.isclose(
            center["center_channel_potential_v"],
            float(entry["center_channel_potential_v"]),
            rel_tol=1.0e-13,
            abs_tol=1.0e-15,
        )
        endpoint_state_match = endpoint_state_match and math.isclose(
            center["center_channel_electron_density_cm3"],
            float(entry["center_channel_electron_density_cm3"]),
            rel_tol=1.0e-13,
            abs_tol=1.0e-300,
        )
        endpoint_state_match = endpoint_state_match and math.isclose(
            float(entry["center_channel_potential_v"]),
            float(matching_bias["center_channel_potential_v"]),
            rel_tol=1.0e-13,
            abs_tol=1.0e-15,
        )
        endpoint_state_match = endpoint_state_match and math.isclose(
            float(entry["center_channel_electron_density_cm3"]),
            float(matching_bias["center_channel_electron_density_cm3"]),
            rel_tol=1.0e-13,
            abs_tol=1.0e-300,
        )
    add_check(
        checks,
        "outputs:endpoint_internal_state_recomputed_from_nodes",
        endpoint_state_match,
        f"entries={len(state_entries)}",
    )

    figure = report.get("figure", {})
    figure_path = ROOT / figure.get("path", "")
    required_files = [
        report_path,
        contract_path,
        snapshot_path,
        solver_log_path,
        state_manifest_path,
        bias_path,
        state_summary_path,
        figure_path,
    ]
    add_check(
        checks,
        "outputs:reports_tables_and_figure_exist",
        all(path.is_file() and path.stat().st_size > 0 for path in required_files)
        and figure.get("sha256") == sha256(figure_path),
        f"files={len(required_files)} figure={figure_path}",
    )

    runner_checks = report.get("checks", {})
    completion = report.get("t02_b_completion", {})
    add_check(
        checks,
        "runner:stage_gate_and_boundary_pass",
        len(runner_checks) == 10
        and all(value["status"] == "PASS" for value in runner_checks.values())
        and completion.get("status") == "PASS"
        and completion.get("minimal_nonzero_top_gate_family_completed") is True
        and completion.get("top_gate_response_direction_verified") is True
        and completion.get("t02_c_bidirectional_family_permitted_next") is True
        and completion.get("t02_complete") is False
        and completion.get("delta_vth_verified") is False
        and completion.get("gm_verified") is False
        and "T02 complete" in report["evidence_boundary"]["prohibited_claims"],
        f"runner_checks={len(runner_checks)} next={completion.get('t02_c_bidirectional_family_permitted_next')} complete={completion.get('t02_complete')}",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    check_report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "checks": checks,
        "failures": failures,
        "recomputed_maximum_relative_terminal_current_imbalance": max_imbalance,
        "recomputed_endpoint_current_ratio": endpoint_current_ratio,
        "recomputed_endpoint_center_potential_increase_v": endpoint_potential_increase,
        "recomputed_endpoint_center_density_ratio": endpoint_density_ratio,
    }
    check_path = ROOT / outputs["check_report"]
    check_path.parent.mkdir(parents=True, exist_ok=True)
    check_path.write_text(
        json.dumps(check_report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T02_B_MINIMAL_CHECK_{check_report['status']} checks={len(checks)} report={check_path}"
    )
    for failure in failures:
        print(
            f"T02_B_MINIMAL_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
