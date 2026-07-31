#!/usr/bin/env python3
"""Independently validate persisted T01-C transfer artifacts."""

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
CONFIG_PATH = ROOT / "config" / "tcad_t01_c_transfer.json"
BASELINE_PATH = ROOT / "config" / "tcad_t01_baseline.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_artifacts() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    baseline = load_json(BASELINE_PATH)
    outputs = config["outputs"]
    report_path = ROOT / outputs["report"]
    report = load_json(report_path)
    t01_a_path = ROOT / config["dependency_reports"]["t01_a_contract"]
    t01_a_report = load_json(t01_a_path)
    t01_b_path = ROOT / config["dependency_reports"]["t01_b_smoke"]
    t01_b_report = load_json(t01_b_path)
    snapshot_path = ROOT / outputs["config_snapshot"]
    snapshot = load_json(snapshot_path)
    state_manifest_path = ROOT / outputs["state_manifest"]
    state_manifest = load_json(state_manifest_path)
    acceptance = config["acceptance"]
    expected_meshes = list(acceptance["required_mesh_levels"])
    expected_vgs = [float(value) for value in acceptance["required_vgs_values_v"]]
    fixed_vds = float(acceptance["fixed_vds_v"])
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == "T01-C"
        and report.get("baseline_case_id") == baseline["case_id"]
        and report.get("t01_b_case_id") == t01_b_report["case_id"],
        f"status={report.get('status')} stage={report.get('stage')}",
    )
    add_check(
        checks,
        "scope:authorized_stages",
        report.get("executed_bias_stage_ids") == [
            "T01_A_STAGE_0",
            "T01_A_STAGE_1",
            "T01_A_STAGE_2",
        ]
        and report.get("reported_bias_stage_id") == "T01_A_STAGE_2",
        str(report.get("executed_bias_stage_ids")),
    )
    reproduction = report.get("reproduction", {})
    add_check(
        checks,
        "reproduction:command_and_tool",
        reproduction.get("command") == "make t01-c-transfer"
        and reproduction.get("validation_command") == "make t01-c-check"
        and bool(reproduction.get("python_executable"))
        and bool(reproduction.get("devsim_version")),
        str(reproduction.get("command")),
    )
    add_check(
        checks,
        "inputs:hash_locked",
        snapshot.get("transfer_config_sha256") == sha256(CONFIG_PATH)
        and snapshot.get("baseline_config_sha256") == sha256(BASELINE_PATH)
        and snapshot.get("t01_a_report_sha256") == sha256(t01_a_path)
        and snapshot.get("t01_b_report_sha256") == sha256(t01_b_path),
        f"snapshot={snapshot_path.relative_to(ROOT)}",
    )
    add_check(
        checks,
        "dependencies:stage_gates",
        t01_a_report.get("contract_status") == config["input_contract"]["required_contract_status"]
        and t01_b_report.get("status") == config["dependency_reports"]["required_t01_b_status"],
        f"T01-A={t01_a_report.get('contract_status')} T01-B={t01_b_report.get('status')}",
    )

    idvg_path = ROOT / outputs["idvg_csv"]
    with idvg_path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_mesh = {
        mesh: [row for row in rows if row["mesh_level"] == mesh]
        for mesh in expected_meshes
    }
    add_check(
        checks,
        "bias:configured_grid",
        len(rows) == len(expected_meshes) * len(expected_vgs)
        and all(
            [float(row["vgs_v"]) for row in by_mesh[mesh]] == expected_vgs
            and all(same_value(float(row["vds_v"]), fixed_vds) for row in by_mesh[mesh])
            and all(row["stage_id"] == "T01_A_STAGE_2" for row in by_mesh[mesh])
            for mesh in expected_meshes
        ),
        f"rows={len(rows)} VGS={expected_vgs}",
    )
    current_floor = float(
        acceptance["minimum_numerically_nonzero_abs_drain_current_a_per_cm"]
    )
    currents = {
        mesh: [abs(float(row["drain_current_a_per_cm"])) for row in by_mesh[mesh]]
        for mesh in expected_meshes
    }
    signs = {
        math.copysign(1.0, float(row["drain_current_a_per_cm"]))
        for row in rows
        if abs(float(row["drain_current_a_per_cm"])) >= current_floor
    }
    add_check(
        checks,
        "current:finite_numerically_nonzero_directional",
        all(math.isfinite(value) and value >= current_floor for values in currents.values() for value in values)
        and signs == {1.0},
        f"floor={current_floor:.3e} signs={sorted(signs)}",
    )
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in rows)
    add_check(
        checks,
        "current:terminal_conservation",
        max_imbalance <= imbalance_limit,
        f"maximum={max_imbalance:.6e} limit={imbalance_limit:.6e}",
    )
    drop_limit = float(acceptance["maximum_monotonic_relative_current_drop"])
    add_check(
        checks,
        "current:monotonic_gate_control",
        all(
            next_value >= value * (1.0 - drop_limit)
            for values in currents.values()
            for value, next_value in zip(values, values[1:])
        ),
        f"maximum_relative_drop={drop_limit:.3e}",
    )
    modulation = {
        mesh: max(values) / max(min(values), 1.0e-300)
        for mesh, values in currents.items()
    }
    modulation_limit = float(acceptance["minimum_numerical_current_span_ratio"])
    add_check(
        checks,
        "current:modulation",
        all(value >= modulation_limit for value in modulation.values()),
        f"ratios={json.dumps(modulation, sort_keys=True)} limit={modulation_limit:.6e}",
    )
    anchor = {
        row["mesh_level"]: abs(float(row["drain_current_a_per_cm"]))
        for row in t01_b_report["bias_points"]
        if same_value(float(row["vgs_v"]), 0.0) and same_value(float(row["vds_v"]), fixed_vds)
    }
    reentry = {}
    for mesh in expected_meshes:
        current = next(
            abs(float(row["drain_current_a_per_cm"]))
            for row in by_mesh[mesh]
            if same_value(float(row["vgs_v"]), 0.0)
        )
        reentry[mesh] = abs(current - anchor[mesh]) / max(current, anchor[mesh], 1.0e-300)
    reentry_limit = float(acceptance["maximum_t01_b_reentry_relative_current_difference"])
    add_check(
        checks,
        "continuation:t01_b_reentry",
        all(value <= reentry_limit for value in reentry.values()),
        f"relative_differences={json.dumps(reentry, sort_keys=True)} limit={reentry_limit:.6e}",
    )

    mesh_path = ROOT / outputs["mesh_comparison_csv"]
    with mesh_path.open("r", encoding="utf-8", newline="") as stream:
        mesh_rows = list(csv.DictReader(stream))
    relative_floor = float(acceptance["mesh_relative_comparison_current_floor_a_per_cm"])
    relative_warning = float(
        acceptance["mesh_relative_current_difference_warning_threshold"]
    )
    log_limit = float(acceptance["maximum_log10_mesh_current_difference_decades"])
    resolved = [
        row
        for row in mesh_rows
        if max(
            float(row["coarse_abs_drain_current_a_per_cm"]),
            float(row["fine_abs_drain_current_a_per_cm"]),
        )
        >= relative_floor
    ]
    recomputed_mesh_values = []
    for row in mesh_rows:
        coarse = float(row["coarse_abs_drain_current_a_per_cm"])
        fine = float(row["fine_abs_drain_current_a_per_cm"])
        relative = abs(coarse - fine) / max(coarse, fine, 1.0e-300)
        log_delta = abs(math.log10(max(coarse, 1.0e-300)) - math.log10(max(fine, 1.0e-300)))
        recomputed_mesh_values.append((relative, log_delta))
    mesh_values_match = all(
        same_value(float(row["relative_current_difference"]), values[0])
        and same_value(float(row["log10_current_difference_decades"]), values[1])
        for row, values in zip(mesh_rows, recomputed_mesh_values, strict=True)
    )
    add_check(
        checks,
        "mesh:log_agreement_and_sensitivity_recorded",
        len(mesh_rows) == len(expected_vgs)
        and mesh_values_match
        and bool(resolved)
        and all(float(row["log10_current_difference_decades"]) <= log_limit for row in mesh_rows)
        and report.get("mesh_sensitivity", {}).get("status")
        == (
            "WARNING"
            if max(float(row["relative_current_difference"]) for row in resolved) > relative_warning
            else "WITHIN_WARNING_THRESHOLD"
        )
        and report.get("mesh_sensitivity", {}).get("quantitative_absolute_current_use_permitted") is False,
        (
            f"max_relative={max(float(row['relative_current_difference']) for row in resolved):.6e} "
            f"max_log_decades={max(float(row['log10_current_difference_decades']) for row in mesh_rows):.6e}"
        ),
    )

    state_entries = state_manifest.get("entries", [])
    expected_state_count = len(expected_meshes) * len(expected_vgs)
    required_vtk = [float(value) for value in acceptance["required_vtk_vgs_values_v"]]
    state_files_valid = all(
        (ROOT / entry["state_csv"]).is_file()
        and (ROOT / entry["state_csv"]).stat().st_size > 0
        and entry["state_csv_sha256"] == sha256(ROOT / entry["state_csv"])
        for entry in state_entries
    )
    vtk_entries = [entry for entry in state_entries if entry.get("vtk_base")]
    vtk_files_valid = all(
        (ROOT / f"{entry['vtk_base']}.vtm").is_file()
        for entry in vtk_entries
    )
    add_check(
        checks,
        "outputs:state_artifacts",
        len(state_entries) == expected_state_count
        and state_files_valid
        and len(vtk_entries) == len(expected_meshes) * len(required_vtk)
        and vtk_files_valid,
        f"state_files={len(state_entries)} selected_vtk={len(vtk_entries)}",
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
        "recomputed_numerical_current_span_ratio": modulation,
        "recomputed_t01_b_reentry_relative_current_difference": reentry,
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
        print(f"T01_C_TRANSFER_CHECK_ERROR {error}", file=sys.stderr)
        return 1
    if not args.check_only:
        check_report_path.parent.mkdir(parents=True, exist_ok=True)
        check_report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    label = "PASS" if report["status"] == "PASS" else "FAIL"
    print(
        f"T01_C_TRANSFER_CHECK_{label} checks={len(report['checks'])} "
        f"report={check_report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T01_C_TRANSFER_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
