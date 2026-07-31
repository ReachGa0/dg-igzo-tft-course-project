#!/usr/bin/env python3
"""Independently validate persisted T01-D-A mesh-refinement artifacts."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t01_d_mesh_refinement.json"


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
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def close_metric(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=1.0e-12, abs_tol=1.0e-15)


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def bias_row(
    rows: list[dict[str, str]], mesh_level: str, vgs_v: float
) -> dict[str, str]:
    return next(
        row
        for row in rows
        if row["mesh_level"] == mesh_level and same_value(float(row["vgs_v"]), vgs_v)
    )


def check_artifacts() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    baseline_path = ROOT / config["input_contract"]["path"]
    baseline = load_json(baseline_path)
    dependencies = config["dependency_reports"]
    t01_a_path = ROOT / dependencies["t01_a_contract"]
    t01_b_path = ROOT / dependencies["t01_b_smoke"]
    t01_c_path = ROOT / dependencies["t01_c_transfer"]
    t01_a_report = load_json(t01_a_path)
    t01_b_report = load_json(t01_b_path)
    t01_c_report = load_json(t01_c_path)
    outputs = config["outputs"]
    report_path = ROOT / outputs["report"]
    report = load_json(report_path)
    snapshot_path = ROOT / outputs["config_snapshot"]
    snapshot = load_json(snapshot_path)
    solver_log = load_json(ROOT / outputs["solver_log"])
    state_manifest = load_json(ROOT / outputs["state_manifest"])
    bias_rows = load_csv(ROOT / outputs["bias_csv"])
    mesh_rows = load_csv(ROOT / outputs["mesh_summary_csv"])
    comparison_rows = load_csv(ROOT / outputs["mesh_comparison_csv"])
    reproduction_rows = load_csv(ROOT / outputs["t01_c_reproduction_csv"])
    acceptance = config["acceptance"]
    expected_meshes = list(acceptance["required_mesh_levels"])
    expected_factors = [float(value) for value in acceptance["required_refinement_factors"]]
    expected_vgs = [float(value) for value in acceptance["required_vgs_values_v"]]
    fixed_vds = float(acceptance["fixed_vds_v"])
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T01-D-A"
        and report.get("evidence_level") == "E2"
        and report.get("baseline_case_id") == baseline["case_id"]
        and report.get("t01_c_case_id") == t01_c_report["case_id"],
        f"status={report.get('status')} stage={report.get('stage')}",
    )
    add_check(
        checks,
        "scope:mesh_only",
        report.get("executed_bias_stage_ids")
        == ["T01_A_STAGE_0", "T01_A_STAGE_1", "T01_A_STAGE_2"]
        and report.get("reported_bias_stage_id") == "T01_A_STAGE_2"
        and config["scope"]["changed_variable"]
        == "bottom-oxide/channel interface-normal mesh spacing only"
        and "full Id-Vd family" in config["scope"]["prohibited_work"],
        str(report.get("executed_bias_stage_ids")),
    )
    reproduction = report.get("reproduction", {})
    add_check(
        checks,
        "reproduction:command_and_tool",
        reproduction.get("command") == "make t01-d-mesh"
        and reproduction.get("validation_command") == "make t01-d-mesh-check"
        and bool(reproduction.get("python_executable"))
        and bool(reproduction.get("devsim_version")),
        str(reproduction.get("command")),
    )
    add_check(
        checks,
        "inputs:hash_locked",
        snapshot.get("mesh_config_sha256") == sha256(CONFIG_PATH)
        and snapshot.get("baseline_config_sha256") == sha256(baseline_path)
        and snapshot.get("t01_a_report_sha256") == sha256(t01_a_path)
        and snapshot.get("t01_b_report_sha256") == sha256(t01_b_path)
        and snapshot.get("t01_c_report_sha256") == sha256(t01_c_path),
        f"snapshot={snapshot_path.relative_to(ROOT)}",
    )
    t01_c_mesh = t01_c_report.get("mesh_sensitivity", {})
    add_check(
        checks,
        "dependencies:stage_gates",
        t01_a_report.get("contract_status") == config["input_contract"]["required_contract_status"]
        and t01_b_report.get("status") == dependencies["required_t01_b_status"]
        and t01_c_report.get("status") == dependencies["required_t01_c_status"]
        and t01_c_mesh.get("status") == dependencies["required_t01_c_mesh_status"]
        and t01_c_mesh.get("quantitative_absolute_current_use_permitted") is False,
        (
            f"T01-A={t01_a_report.get('contract_status')} "
            f"T01-B={t01_b_report.get('status')} T01-C={t01_c_report.get('status')} "
            f"mesh={t01_c_mesh.get('status')}"
        ),
    )

    ladder = config["mesh_ladder"]
    baseline_fine = baseline["mesh"]["levels"][ladder["baseline_level"]]
    mesh_ids = [row["mesh_level"] for row in mesh_rows]
    factors = [float(row["refinement_factor"]) for row in mesh_rows]
    mesh_formulas_valid = len(mesh_rows) == len(expected_meshes) and all(
        same_value(float(row["x_spacing_cm"]), float(baseline_fine["x_spacing_cm"]))
        and same_value(
            float(row["bulk_oxide_y_spacing_cm"]),
            float(baseline_fine["oxide_y_spacing_cm"]),
        )
        and same_value(
            float(row["bulk_channel_y_spacing_cm"]),
            float(baseline_fine["channel_y_spacing_cm"]),
        )
        and same_value(
            float(row["oxide_interface_spacing_cm"]),
            float(baseline_fine["oxide_y_spacing_cm"]) / factor,
        )
        and same_value(
            float(row["channel_interface_spacing_cm"]),
            float(baseline_fine["channel_y_spacing_cm"]) / factor,
        )
        and same_value(
            float(row["oxide_interface_window_cm"]),
            float(ladder["oxide_interface_window_cm"]),
        )
        and same_value(
            float(row["channel_interface_window_cm"]),
            float(ladder["channel_interface_window_cm"]),
        )
        for row, factor in zip(mesh_rows, expected_factors, strict=True)
    )
    node_counts = [int(row["node_count_with_interface_duplicates"]) for row in mesh_rows]
    add_check(
        checks,
        "mesh:configured_ladder_and_only_y_interface_changed",
        mesh_ids == expected_meshes
        and factors == expected_factors
        and mesh_formulas_valid
        and all(higher > lower for lower, higher in zip(node_counts, node_counts[1:])),
        f"meshes={mesh_ids} factors={factors} nodes={node_counts}",
    )

    by_mesh = {
        mesh: [row for row in bias_rows if row["mesh_level"] == mesh]
        for mesh in expected_meshes
    }
    add_check(
        checks,
        "bias:configured_grid",
        len(bias_rows) == len(expected_meshes) * len(expected_vgs)
        and all(
            [float(row["vgs_v"]) for row in by_mesh[mesh]] == expected_vgs
            and all(same_value(float(row["vds_v"]), fixed_vds) for row in by_mesh[mesh])
            and all(row["stage_id"] == "T01_A_STAGE_2" for row in by_mesh[mesh])
            for mesh in expected_meshes
        ),
        f"rows={len(bias_rows)} VGS={expected_vgs}",
    )
    floor = float(acceptance["minimum_numerically_nonzero_abs_drain_current_a_per_cm"])
    currents = {
        mesh: [abs(float(row["drain_current_a_per_cm"])) for row in by_mesh[mesh]]
        for mesh in expected_meshes
    }
    signs = {
        math.copysign(1.0, float(row["drain_current_a_per_cm"]))
        for row in bias_rows
        if abs(float(row["drain_current_a_per_cm"])) >= floor
    }
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in bias_rows)
    drop_limit = float(acceptance["maximum_monotonic_relative_current_drop"])
    add_check(
        checks,
        "current:resolved_conserved_monotonic",
        all(math.isfinite(value) and value >= floor for values in currents.values() for value in values)
        and signs == {1.0}
        and max_imbalance <= imbalance_limit
        and all(
            next_value >= value * (1.0 - drop_limit)
            for values in currents.values()
            for value, next_value in zip(values, values[1:])
        ),
        f"floor={floor:.3e} signs={sorted(signs)} max_imbalance={max_imbalance:.6e}",
    )

    expected_pairs = list(zip(expected_meshes, expected_meshes[1:]))
    recomputed_comparisons: list[tuple[float, float, float]] = []
    expected_order: list[tuple[str, str, float]] = []
    for lower_mesh, higher_mesh in expected_pairs:
        for vgs_v in expected_vgs:
            lower = bias_row(bias_rows, lower_mesh, vgs_v)
            higher = bias_row(bias_rows, higher_mesh, vgs_v)
            lower_current = abs(float(lower["drain_current_a_per_cm"]))
            higher_current = abs(float(higher["drain_current_a_per_cm"]))
            recomputed_comparisons.append(
                (
                    abs(lower_current - higher_current)
                    / max(lower_current, higher_current, 1.0e-300),
                    abs(
                        math.log10(max(lower_current, 1.0e-300))
                        - math.log10(max(higher_current, 1.0e-300))
                    ),
                    abs(
                        float(lower["center_channel_potential_v"])
                        - float(higher["center_channel_potential_v"])
                    ),
                )
            )
            expected_order.append((lower_mesh, higher_mesh, vgs_v))
    comparison_values_valid = len(comparison_rows) == len(recomputed_comparisons) and all(
        row["lower_refinement_mesh"] == identity[0]
        and row["higher_refinement_mesh"] == identity[1]
        and same_value(float(row["vgs_v"]), identity[2])
        and close_metric(float(row["relative_current_difference"]), values[0])
        and close_metric(float(row["log10_current_difference_decades"]), values[1])
        and close_metric(float(row["center_channel_potential_difference_v"]), values[2])
        for row, identity, values in zip(
            comparison_rows, expected_order, recomputed_comparisons, strict=True
        )
    )
    add_check(
        checks,
        "mesh:adjacent_comparisons_recomputed",
        comparison_values_valid,
        f"rows={len(comparison_rows)} expected={len(recomputed_comparisons)}",
    )

    convergence_pair = ladder["convergence_pair"]
    target_vgs = [
        float(value) for value in config["continuation"]["mesh_convergence_vgs_values_v"]
    ]
    finest_rows = [
        row
        for row in comparison_rows
        if row["lower_refinement_mesh"] == convergence_pair[0]
        and row["higher_refinement_mesh"] == convergence_pair[1]
        and any(same_value(float(row["vgs_v"]), target) for target in target_vgs)
    ]
    max_current_difference = max(float(row["relative_current_difference"]) for row in finest_rows)
    max_potential_difference = max(
        float(row["center_channel_potential_difference_v"]) for row in finest_rows
    )
    current_limit = float(acceptance["maximum_finest_pair_relative_current_difference"])
    potential_limit = float(
        acceptance["maximum_finest_pair_center_potential_difference_v"]
    )
    mesh_convergence = report.get("mesh_convergence", {})
    add_check(
        checks,
        "mesh:finest_pair_gate",
        len(finest_rows) == len(target_vgs)
        and max_current_difference <= current_limit
        and max_potential_difference <= potential_limit
        and close_metric(
            float(mesh_convergence.get("maximum_relative_current_difference")),
            max_current_difference,
        )
        and close_metric(
            float(mesh_convergence.get("maximum_center_channel_potential_difference_v")),
            max_potential_difference,
        )
        and mesh_convergence.get("status") == "PASS"
        and mesh_convergence.get("numerical_low_vds_positive_bias_absolute_current_converged")
        is True
        and mesh_convergence.get("experimental_quantitative_use_permitted") is False
        and mesh_convergence.get("idvd_stage_permitted_next") is True,
        (
            f"pair={convergence_pair} max_current_relative={max_current_difference:.6e} "
            f"limit={current_limit:.6e} max_potential_v={max_potential_difference:.6e}"
        ),
    )

    reproduction_vgs = [
        float(value) for value in config["continuation"]["t01_c_reproduction_vgs_values_v"]
    ]
    recomputed_reproduction: list[tuple[float, float]] = []
    for vgs_v in reproduction_vgs:
        reference = next(
            row
            for row in t01_c_report["bias_points"]
            if row["mesh_level"] == "fine" and same_value(float(row["vgs_v"]), vgs_v)
        )
        reproduced = bias_row(bias_rows, "fine_1x", vgs_v)
        reference_current = abs(float(reference["drain_current_a_per_cm"]))
        reproduced_current = abs(float(reproduced["drain_current_a_per_cm"]))
        recomputed_reproduction.append(
            (
                abs(reference_current - reproduced_current)
                / max(reference_current, reproduced_current, 1.0e-300),
                abs(
                    float(reference["center_channel_potential_v"])
                    - float(reproduced["center_channel_potential_v"])
                ),
            )
        )
    current_reproduction_limit = float(
        acceptance["maximum_t01_c_fine_reproduction_relative_current_difference"]
    )
    potential_reproduction_limit = float(
        acceptance["maximum_t01_c_fine_reproduction_potential_difference_v"]
    )
    reproduction_valid = len(reproduction_rows) == len(recomputed_reproduction) and all(
        same_value(float(row["vgs_v"]), vgs_v)
        and close_metric(float(row["relative_current_difference"]), values[0])
        and close_metric(float(row["center_channel_potential_difference_v"]), values[1])
        and values[0] <= current_reproduction_limit
        and values[1] <= potential_reproduction_limit
        for row, vgs_v, values in zip(
            reproduction_rows, reproduction_vgs, recomputed_reproduction, strict=True
        )
    )
    add_check(
        checks,
        "continuation:fine_1x_reproduces_t01_c",
        reproduction_valid,
        (
            f"max_current_relative={max(value[0] for value in recomputed_reproduction):.6e} "
            f"max_potential_v={max(value[1] for value in recomputed_reproduction):.6e}"
        ),
    )

    mesh_runs = solver_log.get("mesh_runs", [])
    all_solver_records = [record for run in mesh_runs for record in run.get("solver_records", [])]
    add_check(
        checks,
        "solver:all_records_converged",
        [run.get("mesh_level") for run in mesh_runs] == expected_meshes
        and all(run.get("status") == "PASS" for run in mesh_runs)
        and not solver_log.get("errors")
        and bool(all_solver_records)
        and all(record.get("converged") is True for record in all_solver_records),
        f"mesh_runs={len(mesh_runs)} solver_records={len(all_solver_records)}",
    )
    state_entries = state_manifest.get("entries", [])
    state_files_valid = all(
        (ROOT / entry["state_csv"]).is_file()
        and (ROOT / entry["state_csv"]).stat().st_size > 0
        and entry["state_csv_sha256"] == sha256(ROOT / entry["state_csv"])
        for entry in state_entries
    )
    vtk_files = [item for entry in state_entries for item in entry.get("vtk_files", [])]
    vtk_files_valid = all(
        (ROOT / item["path"]).is_file()
        and (ROOT / item["path"]).stat().st_size > 0
        and item["sha256"] == sha256(ROOT / item["path"])
        for item in vtk_files
    )
    required_state_vgs = float(acceptance["require_state_file_per_mesh_at_vgs_v"])
    add_check(
        checks,
        "outputs:state_artifacts",
        len(state_entries) == len(expected_meshes)
        and [entry["mesh_level"] for entry in state_entries] == expected_meshes
        and all(same_value(float(entry["vgs_v"]), required_state_vgs) for entry in state_entries)
        and state_files_valid
        and len(vtk_files) >= len(expected_meshes)
        and vtk_files_valid,
        f"state_files={len(state_entries)} vtk_files={len(vtk_files)}",
    )
    runner_checks = report.get("checks", {})
    add_check(
        checks,
        "runner:all_acceptance_checks_pass",
        bool(runner_checks)
        and all(result.get("status") == "PASS" for result in runner_checks.values()),
        f"checks={len(runner_checks)}",
    )
    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "checks": checks,
        "failures": failures,
        "recomputed_maximum_relative_terminal_current_imbalance": max_imbalance,
        "recomputed_maximum_finest_pair_relative_current_difference": max_current_difference,
        "recomputed_maximum_finest_pair_center_potential_difference_v": max_potential_difference,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config = load_json(CONFIG_PATH)
    check_report_path = ROOT / config["outputs"]["check_report"]
    try:
        report = check_artifacts()
    except Exception as error:  # noqa: BLE001
        print(f"T01_D_MESH_CHECK_ERROR {error}", file=sys.stderr)
        return 1
    if not args.check_only:
        check_report_path.parent.mkdir(parents=True, exist_ok=True)
        check_report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    label = "PASS" if report["status"] == "PASS" else "FAIL"
    print(
        f"T01_D_MESH_CHECK_{label} checks={len(report['checks'])} "
        f"report={check_report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T01_D_MESH_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
