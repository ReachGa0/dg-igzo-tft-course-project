#!/usr/bin/env python3
"""Independently validate persisted T01-B low-bias smoke artifacts."""

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
SMOKE_CONFIG_PATH = ROOT / "config" / "tcad_t01_b_smoke.json"
BASELINE_CONFIG_PATH = ROOT / "config" / "tcad_t01_baseline.json"
REPORT_PATH = ROOT / "results" / "reports" / "tcad_t01_b_smoke.json"
CHECK_REPORT_PATH = ROOT / "results" / "reports" / "tcad_t01_b_smoke_check.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def float_value(row: dict[str, str], name: str) -> float:
    return float(row[name])


def check_artifacts() -> dict[str, Any]:
    smoke = load_json(SMOKE_CONFIG_PATH)
    baseline = load_json(BASELINE_CONFIG_PATH)
    report = load_json(REPORT_PATH)
    checks: list[dict[str, str]] = []
    acceptance = smoke["acceptance"]
    outputs = smoke["outputs"]
    expected_meshes = list(acceptance["required_mesh_levels"])
    expected_vds = [float(value) for value in acceptance["required_vds_values_v"]]

    add_check(
        checks,
        "identity:report",
        report.get("status") == "PASS"
        and report.get("case_id") == smoke["case_id"]
        and report.get("stage") == "T01-B"
        and report.get("baseline_case_id") == baseline["case_id"],
        f"status={report.get('status')} stage={report.get('stage')}",
    )
    add_check(
        checks,
        "scope:only_stage_0_and_1",
        report.get("executed_bias_stage_ids") == ["T01_A_STAGE_0", "T01_A_STAGE_1"],
        str(report.get("executed_bias_stage_ids")),
    )
    reproduction = report.get("reproduction", {})
    add_check(
        checks,
        "reproduction:command_and_tool",
        reproduction.get("command") == "make t01-b-smoke"
        and reproduction.get("validation_command") == "make t01-b-check"
        and bool(reproduction.get("python_executable"))
        and bool(reproduction.get("devsim_version")),
        str(reproduction.get("command")),
    )
    snapshot_path = ROOT / outputs["config_snapshot"]
    snapshot = load_json(snapshot_path)
    add_check(
        checks,
        "inputs:hash_locked",
        snapshot.get("baseline_config_sha256") == sha256(BASELINE_CONFIG_PATH)
        and snapshot.get("smoke_config_sha256") == sha256(SMOKE_CONFIG_PATH),
        f"snapshot={snapshot_path.relative_to(ROOT)}",
    )

    csv_path = ROOT / outputs["bias_points_csv"]
    with csv_path.open("r", encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    by_mesh = {
        mesh: sorted(
            [row for row in rows if row["mesh_level"] == mesh],
            key=lambda row: float_value(row, "vds_v"),
        )
        for mesh in expected_meshes
    }
    add_check(
        checks,
        "bias:configured_meshes",
        len(rows) == len(expected_meshes) * len(expected_vds)
        and all(len(by_mesh[mesh]) == len(expected_vds) for mesh in expected_meshes),
        f"rows={len(rows)} meshes={','.join(expected_meshes)}",
    )
    add_check(
        checks,
        "bias:low_vds_sequence",
        all(
            [float_value(row, "vds_v") for row in by_mesh[mesh]] == expected_vds
            and all(float_value(row, "vgs_v") == 0.0 for row in by_mesh[mesh])
            and all(row["stage_id"] == "T01_A_STAGE_1" for row in by_mesh[mesh])
            for mesh in expected_meshes
        ),
        f"expected_vds={expected_vds}",
    )
    zero_rows = [row for row in rows if float_value(row, "vds_v") == 0.0]
    zero_limit = float(acceptance["zero_bias_abs_terminal_current_a_per_cm_max"])
    add_check(
        checks,
        "current:zero_bias_small",
        len(zero_rows) == len(expected_meshes)
        and all(
            max(abs(float_value(row, "source_current_a_per_cm")), abs(float_value(row, "drain_current_a_per_cm")))
            <= zero_limit
            for row in zero_rows
        ),
        f"limit_a_per_cm={zero_limit:.3e}",
    )
    nonzero_rows = [row for row in rows if float_value(row, "vds_v") > 0.0]
    current_floor = float(acceptance["minimum_low_vds_abs_terminal_current_a_per_cm"])
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    signs = {
        math.copysign(1.0, float_value(row, "drain_current_a_per_cm"))
        for row in nonzero_rows
        if abs(float_value(row, "drain_current_a_per_cm")) >= current_floor
    }
    add_check(
        checks,
        "current:nonzero_conserved_directional",
        len(nonzero_rows) == len(expected_meshes) * (len(expected_vds) - 1)
        and all(abs(float_value(row, "drain_current_a_per_cm")) >= current_floor for row in nonzero_rows)
        and all(float_value(row, "relative_current_imbalance") <= imbalance_limit for row in nonzero_rows)
        and len(signs) == 1,
        f"floor={current_floor:.3e} imbalance_limit={imbalance_limit:.3e} signs={sorted(signs)}",
    )
    final_current = {}
    for mesh in expected_meshes:
        final = next(
            row for row in by_mesh[mesh] if math.isclose(float_value(row, "vds_v"), 0.01, abs_tol=1.0e-15)
        )
        final_current[mesh] = abs(float_value(final, "drain_current_a_per_cm"))
    mesh_delta = abs(final_current["fine"] - final_current["coarse"]) / max(
        final_current["fine"], final_current["coarse"], 1.0e-300
    )
    add_check(
        checks,
        "mesh:low_vds_current_smoke",
        mesh_delta <= float(acceptance["maximum_relative_mesh_current_difference_at_0p01v"]),
        f"relative_delta={mesh_delta:.6e}",
    )
    state_paths = [
        ROOT / summary["state_csv"]
        for summary in report.get("mesh", [])
        if summary.get("mesh_level") in expected_meshes
    ]
    add_check(
        checks,
        "outputs:state_files",
        len(state_paths) == len(expected_meshes)
        and all(path.is_file() and path.stat().st_size > 0 for path in state_paths),
        ", ".join(str(path.relative_to(ROOT)) for path in state_paths),
    )
    runner_checks = report.get("checks", {})
    add_check(
        checks,
        "runner:all_acceptance_checks_pass",
        bool(runner_checks) and all(result.get("status") == "PASS" for result in runner_checks.values()),
        f"checks={len(runner_checks)}",
    )
    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": smoke["case_id"],
        "stage": "T01-B",
        "checks": checks,
        "failures": failures,
        "recomputed_mesh_current_relative_difference_at_0p01v": mesh_delta,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = check_artifacts()
    except Exception as error:  # noqa: BLE001
        print(f"T01_B_SMOKE_CHECK_ERROR {error}", file=sys.stderr)
        return 1
    if not args.check_only:
        CHECK_REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHECK_REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    label = "PASS" if report["status"] == "PASS" else "FAIL"
    print(f"T01_B_SMOKE_CHECK_{label} checks={len(report['checks'])} report={CHECK_REPORT_PATH}")
    for failure in report["failures"]:
        print(f"T01_B_SMOKE_CHECK_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
