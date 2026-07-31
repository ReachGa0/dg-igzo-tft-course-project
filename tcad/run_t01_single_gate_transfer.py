#!/usr/bin/env python3
"""Run the T01-C single-gate IGZO low-VDS transfer continuation."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t01_single_gate_smoke as core  # noqa: E402


IDVG_FIELDNAMES = [
    "mesh_level",
    "stage_id",
    "vgs_v",
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
    "converged",
]

STATE_FIELDNAMES = [
    "mesh_level",
    "stage_id",
    "vgs_v",
    "vds_v",
    "region",
    "x_cm",
    "y_cm",
    "x_um",
    "y_nm",
    "potential_v",
    "electron_density_cm3",
]


def stage_by_id(baseline: dict[str, Any], stage_id: str) -> dict[str, Any]:
    return next(stage for stage in baseline["bias_protocol"]["stages"] if stage["id"] == stage_id)


def bias_slug(value: float) -> str:
    sign = "m" if value < 0.0 else "p"
    return sign + f"{abs(value):.3f}".replace(".", "p")


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def write_bias_state(
    device: str,
    mesh_level: str,
    vgs_v: float,
    vds_v: float,
    run_dir: Path,
    selected_vtk_values: list[float],
) -> dict[str, Any]:
    rows = core.collect_state_nodes(device, mesh_level)
    enriched_rows = [
        {
            "mesh_level": row["mesh_level"],
            "stage_id": "T01_A_STAGE_2",
            "vgs_v": vgs_v,
            "vds_v": vds_v,
            "region": row["region"],
            "x_cm": row["x_cm"],
            "y_cm": row["y_cm"],
            "x_um": row["x_um"],
            "y_nm": row["y_nm"],
            "potential_v": row["potential_v"],
            "electron_density_cm3": row["electron_density_cm3"],
        }
        for row in rows
    ]
    stem = f"t01_c_{mesh_level}_vgs_{bias_slug(vgs_v)}"
    state_path = run_dir / f"{stem}_nodes.csv"
    core.write_csv(state_path, enriched_rows, STATE_FIELDNAMES)

    vtk_base: str | None = None
    if any(same_value(vgs_v, selected) for selected in selected_vtk_values):
        vtk_path = run_dir / stem
        core.devsim.write_devices(file=str(vtk_path), device=device, type="vtk")
        for output_path in run_dir.glob(f"{vtk_path.name}*"):
            core.normalize_text_newline(output_path)
        vtk_base = str(vtk_path.relative_to(ROOT))

    return {
        "mesh_level": mesh_level,
        "vgs_v": vgs_v,
        "vds_v": vds_v,
        "node_count_with_interface_duplicates": len(enriched_rows),
        "state_csv": str(state_path.relative_to(ROOT)),
        "state_csv_sha256": core.sha256(state_path),
        "vtk_base": vtk_base,
    }


def run_mesh(
    baseline: dict[str, Any],
    transfer: dict[str, Any],
    mesh_level: str,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    device = f"t01_c_{mesh_level}"
    solver_records: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    try:
        core.initialize_device(device, baseline, mesh_level)
        stage_zero = stage_by_id(baseline, "T01_A_STAGE_0")
        stage_low_vds = stage_by_id(baseline, "T01_A_STAGE_1")
        core.set_biases(
            device,
            source_v=float(stage_zero["source_v"]),
            drain_v=float(stage_zero["drain_v"]),
            bottom_gate_v=float(stage_zero["bottom_gate_v"]),
        )
        solver_records.append(
            core.solve_dc(device, baseline, "poisson_zero_bias_initialization", coupled=False)
        )
        core.create_transport(device, baseline)
        solver_records.append(core.solve_dc(device, baseline, "T01_A_STAGE_0", coupled=True))

        for vds_v in [float(value) for value in stage_low_vds["vds_values_v"]]:
            core.set_biases(device, source_v=0.0, drain_v=vds_v, bottom_gate_v=0.0)
            solver_records.append(
                core.solve_dc(
                    device,
                    baseline,
                    f"T01_A_STAGE_1_VDS_{vds_v:.6g}_V",
                    coupled=True,
                )
            )

        continuation = transfer["continuation"]
        fixed_vds = float(continuation["vds_v"])
        precondition_records: dict[float, dict[str, Any]] = {}
        for vgs_v in [float(value) for value in continuation["negative_preconditioning_vgs_values_v"]]:
            core.set_biases(device, source_v=0.0, drain_v=fixed_vds, bottom_gate_v=vgs_v)
            record = core.solve_dc(
                device,
                baseline,
                f"T01_C_PRECONDITION_VGS_{vgs_v:.6g}_V",
                coupled=True,
            )
            solver_records.append(record)
            precondition_records[vgs_v] = record

        vgs_values = [float(value) for value in continuation["vgs_values_v"]]
        selected_vtk = [float(value) for value in continuation["selected_vtk_vgs_values_v"]]
        bias_rows: list[dict[str, Any]] = []
        for index, vgs_v in enumerate(vgs_values):
            if index == 0 and vgs_v in precondition_records:
                solve_record = precondition_records[vgs_v]
            else:
                core.set_biases(device, source_v=0.0, drain_v=fixed_vds, bottom_gate_v=vgs_v)
                solve_record = core.solve_dc(
                    device,
                    baseline,
                    f"T01_A_STAGE_2_VGS_{vgs_v:.6g}_V",
                    coupled=True,
                )
                solver_records.append(solve_record)
            bias_rows.append(
                core.collect_bias_row(
                    device,
                    baseline,
                    mesh_level=mesh_level,
                    stage_id="T01_A_STAGE_2",
                    vds_v=fixed_vds,
                    vgs_v=vgs_v,
                    solve_record=solve_record,
                )
            )
            state_entries.append(
                write_bias_state(
                    device,
                    mesh_level,
                    vgs_v,
                    fixed_vds,
                    run_dir,
                    selected_vtk,
                )
            )

        node_count, element_count = core.node_and_element_counts(device)
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in bias_rows]
        summary = {
            "mesh_level": mesh_level,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(solver_records),
            "reported_bias_point_count": len(bias_rows),
            "state_file_count": len(state_entries),
            "minimum_abs_drain_current_a_per_cm": min(currents),
            "maximum_abs_drain_current_a_per_cm": max(currents),
            "numerical_current_span_ratio": max(currents) / max(min(currents), 1.0e-300),
            "solver_records": solver_records,
        }
        return bias_rows, summary, solver_records, state_entries
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def build_mesh_comparison(
    bias_rows: list[dict[str, Any]], expected_vgs: list[float]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for vgs_v in expected_vgs:
        coarse = next(
            row for row in bias_rows if row["mesh_level"] == "coarse" and same_value(float(row["vgs_v"]), vgs_v)
        )
        fine = next(
            row for row in bias_rows if row["mesh_level"] == "fine" and same_value(float(row["vgs_v"]), vgs_v)
        )
        coarse_current = abs(float(coarse["drain_current_a_per_cm"]))
        fine_current = abs(float(fine["drain_current_a_per_cm"]))
        denominator = max(coarse_current, fine_current, 1.0e-300)
        log_difference = abs(
            math.log10(max(coarse_current, 1.0e-300))
            - math.log10(max(fine_current, 1.0e-300))
        )
        rows.append(
            {
                "vgs_v": vgs_v,
                "vds_v": float(coarse["vds_v"]),
                "coarse_abs_drain_current_a_per_cm": coarse_current,
                "fine_abs_drain_current_a_per_cm": fine_current,
                "relative_current_difference": abs(coarse_current - fine_current) / denominator,
                "log10_current_difference_decades": log_difference,
                "coarse_center_channel_potential_v": float(coarse["center_channel_potential_v"]),
                "fine_center_channel_potential_v": float(fine["center_channel_potential_v"]),
                "center_channel_potential_difference_v": abs(
                    float(coarse["center_channel_potential_v"])
                    - float(fine["center_channel_potential_v"])
                ),
            }
        )
    return rows


def t01_b_anchor_currents(report: dict[str, Any]) -> dict[str, float]:
    return {
        row["mesh_level"]: abs(float(row["drain_current_a_per_cm"]))
        for row in report["bias_points"]
        if same_value(float(row["vgs_v"]), 0.0) and same_value(float(row["vds_v"]), 0.01)
    }


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def assess_transfer(
    transfer: dict[str, Any],
    bias_rows: list[dict[str, Any]],
    mesh_summaries: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    mesh_rows: list[dict[str, Any]],
    t01_b_report: dict[str, Any],
) -> dict[str, Any]:
    acceptance = transfer["acceptance"]
    expected_meshes = list(acceptance["required_mesh_levels"])
    expected_vgs = [float(value) for value in acceptance["required_vgs_values_v"]]
    fixed_vds = float(acceptance["fixed_vds_v"])
    checks: dict[str, dict[str, Any]] = {}
    by_mesh = {
        mesh: [row for row in bias_rows if row["mesh_level"] == mesh]
        for mesh in expected_meshes
    }

    add_check(
        checks,
        "configured_meshes_completed",
        len(mesh_summaries) == len(expected_meshes)
        and {summary["mesh_level"] for summary in mesh_summaries} == set(expected_meshes),
        f"meshes={','.join(summary['mesh_level'] for summary in mesh_summaries)}",
    )
    add_check(
        checks,
        "required_transfer_bias_grid",
        all(
            [float(row["vgs_v"]) for row in by_mesh[mesh]] == expected_vgs
            and all(same_value(float(row["vds_v"]), fixed_vds) for row in by_mesh[mesh])
            and all(row["stage_id"] == "T01_A_STAGE_2" for row in by_mesh[mesh])
            for mesh in expected_meshes
        ),
        f"VGS={expected_vgs} VDS={fixed_vds}",
    )
    solver_records = [record for summary in mesh_summaries for record in summary["solver_records"]]
    add_check(
        checks,
        "all_dc_solves_converged",
        bool(solver_records) and all(bool(record["converged"]) for record in solver_records),
        f"solver_records={len(solver_records)}",
    )
    current_floor = float(
        acceptance["minimum_numerically_nonzero_abs_drain_current_a_per_cm"]
    )
    currents_by_mesh = {
        mesh: [abs(float(row["drain_current_a_per_cm"])) for row in by_mesh[mesh]]
        for mesh in expected_meshes
    }
    signs = {
        math.copysign(1.0, float(row["drain_current_a_per_cm"]))
        for row in bias_rows
        if abs(float(row["drain_current_a_per_cm"])) >= current_floor
    }
    add_check(
        checks,
        "finite_numerically_nonzero_directional_current",
        all(math.isfinite(value) and value >= current_floor for values in currents_by_mesh.values() for value in values)
        and signs == {1.0},
        f"floor={current_floor:.3e} signs={sorted(signs)}",
    )
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    add_check(
        checks,
        "terminal_current_conservation",
        all(float(row["relative_current_imbalance"]) <= imbalance_limit for row in bias_rows),
        f"maximum={max(float(row['relative_current_imbalance']) for row in bias_rows):.6e} limit={imbalance_limit:.6e}",
    )
    drop_limit = float(acceptance["maximum_monotonic_relative_current_drop"])
    monotonic = all(
        next_value >= current_value * (1.0 - drop_limit)
        for values in currents_by_mesh.values()
        for current_value, next_value in zip(values, values[1:])
    )
    add_check(
        checks,
        "drain_current_monotonic_with_vgs",
        monotonic,
        f"maximum_relative_drop={drop_limit:.3e}",
    )
    modulation = {
        mesh: max(values) / max(min(values), 1.0e-300)
        for mesh, values in currents_by_mesh.items()
    }
    modulation_limit = float(acceptance["minimum_numerical_current_span_ratio"])
    add_check(
        checks,
        "gate_numerical_current_span_resolved",
        all(value >= modulation_limit for value in modulation.values()),
        f"ratios={json.dumps(modulation, sort_keys=True)} limit={modulation_limit:.6e}",
    )
    anchor = t01_b_anchor_currents(t01_b_report)
    reentry = {}
    for mesh in expected_meshes:
        current = next(
            abs(float(row["drain_current_a_per_cm"]))
            for row in by_mesh[mesh]
            if same_value(float(row["vgs_v"]), 0.0)
        )
        reference = anchor[mesh]
        reentry[mesh] = abs(current - reference) / max(current, reference, 1.0e-300)
    reentry_limit = float(acceptance["maximum_t01_b_reentry_relative_current_difference"])
    add_check(
        checks,
        "t01_b_zero_gate_reentry",
        all(value <= reentry_limit for value in reentry.values()),
        f"relative_differences={json.dumps(reentry, sort_keys=True)} limit={reentry_limit:.6e}",
    )
    relative_floor = float(acceptance["mesh_relative_comparison_current_floor_a_per_cm"])
    relative_warning = float(
        acceptance["mesh_relative_current_difference_warning_threshold"]
    )
    log_limit = float(acceptance["maximum_log10_mesh_current_difference_decades"])
    resolved_mesh_rows = [
        row
        for row in mesh_rows
        if max(
            float(row["coarse_abs_drain_current_a_per_cm"]),
            float(row["fine_abs_drain_current_a_per_cm"]),
        )
        >= relative_floor
    ]
    add_check(
        checks,
        "mesh_transfer_log_agreement_and_sensitivity_recorded",
        bool(resolved_mesh_rows)
        and all(float(row["log10_current_difference_decades"]) <= log_limit for row in mesh_rows),
        (
            f"max_relative={max(float(row['relative_current_difference']) for row in resolved_mesh_rows):.6e} "
            f"warning={relative_warning:.6e} max_log_decades="
            f"{max(float(row['log10_current_difference_decades']) for row in mesh_rows):.6e} limit={log_limit:.6e}"
        ),
    )
    expected_state_count = len(expected_meshes) * len(expected_vgs)
    required_vtk = [float(value) for value in acceptance["required_vtk_vgs_values_v"]]
    state_paths = [ROOT / entry["state_csv"] for entry in state_entries]
    vtk_entries = [entry for entry in state_entries if entry["vtk_base"] is not None]
    add_check(
        checks,
        "state_outputs_present",
        len(state_entries) == expected_state_count
        and all(path.is_file() and path.stat().st_size > 0 for path in state_paths)
        and len(vtk_entries) == len(expected_meshes) * len(required_vtk),
        f"state_files={len(state_entries)} selected_vtk={len(vtk_entries)}",
    )
    failures = [name for name, result in checks.items() if result["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "numerical_current_span_ratio": modulation,
        "t01_b_reentry_relative_current_difference": reentry,
        "maximum_relative_mesh_current_difference": max(
            float(row["relative_current_difference"]) for row in resolved_mesh_rows
        ),
        "maximum_log10_mesh_current_difference_decades": max(
            float(row["log10_current_difference_decades"]) for row in mesh_rows
        ),
        "mesh_sensitivity": {
            "status": (
                "WARNING"
                if max(float(row["relative_current_difference"]) for row in resolved_mesh_rows)
                > relative_warning
                else "WITHIN_WARNING_THRESHOLD"
            ),
            "relative_current_difference_warning_threshold": relative_warning,
            "quantitative_absolute_current_use_permitted": False,
            "required_followup": "T01-D mesh refinement and full mesh metrics",
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_t01_c_transfer.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    transfer_path = args.config.resolve()
    transfer = core.load_json(transfer_path)
    baseline_path = ROOT / transfer["input_contract"]["path"]
    baseline = core.load_json(baseline_path)
    t01_a_path = ROOT / transfer["dependency_reports"]["t01_a_contract"]
    t01_a_report = core.load_json(t01_a_path)
    t01_b_path = ROOT / transfer["dependency_reports"]["t01_b_smoke"]
    t01_b_report = core.load_json(t01_b_path)
    if t01_a_report.get("contract_status") != transfer["input_contract"]["required_contract_status"]:
        raise RuntimeError("T01-A input contract is not PASS")
    if t01_b_report.get("status") != transfer["dependency_reports"]["required_t01_b_status"]:
        raise RuntimeError("T01-B dependency report is not PASS")
    frozen_vgs = [
        float(value) for value in stage_by_id(baseline, "T01_A_STAGE_2")["vgs_values_v"]
    ]
    configured_vgs = [float(value) for value in transfer["continuation"]["vgs_values_v"]]
    if configured_vgs != frozen_vgs:
        raise RuntimeError("T01-C VGS grid does not match the frozen T01-A contract")
    outputs = transfer["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    idvg_path = ROOT / outputs["idvg_csv"]
    mesh_path = ROOT / outputs["mesh_comparison_csv"]
    report_path = ROOT / outputs["report"]

    snapshot = {
        "transfer_config_path": str(transfer_path.relative_to(ROOT)),
        "transfer_config_sha256": core.sha256(transfer_path),
        "baseline_config_path": str(baseline_path.relative_to(ROOT)),
        "baseline_config_sha256": core.sha256(baseline_path),
        "t01_a_report_path": str(t01_a_path.relative_to(ROOT)),
        "t01_a_report_sha256": core.sha256(t01_a_path),
        "t01_b_report_path": str(t01_b_path.relative_to(ROOT)),
        "t01_b_report_sha256": core.sha256(t01_b_path),
        "baseline_case_id": baseline["case_id"],
        "transfer_case_id": transfer["case_id"],
        "baseline": baseline,
        "transfer": transfer,
    }
    core.write_json(snapshot_path, snapshot)

    bias_rows: list[dict[str, Any]] = []
    mesh_summaries: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    solver_log: dict[str, Any] = {
        "case_id": transfer["case_id"],
        "stage": transfer["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t01-c-transfer",
        "validation_command": "make t01-c-check",
        "mesh_runs": [],
        "errors": [],
    }
    caught_error: Exception | None = None
    for mesh_level in transfer["scope"]["mesh_levels"]:
        try:
            rows, summary, records, states = run_mesh(
                baseline, transfer, mesh_level, run_dir
            )
            bias_rows.extend(rows)
            mesh_summaries.append(summary)
            state_entries.extend(states)
            solver_log["mesh_runs"].append(
                {
                    "mesh_level": mesh_level,
                    "status": "PASS",
                    "solver_records": records,
                }
            )
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"mesh_level": mesh_level, "error": repr(error)})
            solver_log["mesh_runs"].append({"mesh_level": mesh_level, "status": "FAIL"})
            break

    core.write_csv(idvg_path, bias_rows, IDVG_FIELDNAMES)
    expected_vgs = [float(value) for value in transfer["acceptance"]["required_vgs_values_v"]]
    mesh_rows = build_mesh_comparison(bias_rows, expected_vgs) if len(mesh_summaries) == 2 else []
    core.write_csv(
        mesh_path,
        mesh_rows,
        [
            "vgs_v",
            "vds_v",
            "coarse_abs_drain_current_a_per_cm",
            "fine_abs_drain_current_a_per_cm",
            "relative_current_difference",
            "log10_current_difference_decades",
            "coarse_center_channel_potential_v",
            "fine_center_channel_potential_v",
            "center_channel_potential_difference_v",
        ],
    )
    state_manifest = {
        "case_id": transfer["case_id"],
        "stage": transfer["stage"],
        "entries": state_entries,
    }
    core.write_json(state_manifest_path, state_manifest)
    core.write_json(solver_log_path, solver_log)

    if caught_error is None and len(mesh_summaries) == 2:
        assessment = assess_transfer(
            transfer,
            bias_rows,
            mesh_summaries,
            state_entries,
            mesh_rows,
            t01_b_report,
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {
                "simulation_exception": {
                    "status": "FAIL",
                    "detail": repr(caught_error),
                }
            },
            "failures": ["simulation_exception"],
            "numerical_current_span_ratio": {},
            "t01_b_reentry_relative_current_difference": {},
            "maximum_relative_mesh_current_difference": None,
            "maximum_log10_mesh_current_difference_decades": None,
            "mesh_sensitivity": {
                "status": "NOT_EVALUATED",
                "quantitative_absolute_current_use_permitted": False,
                "required_followup": "T01-D mesh refinement and full mesh metrics",
            },
        }
    report = {
        "status": assessment["status"],
        "case_id": transfer["case_id"],
        "stage": transfer["stage"],
        "evidence_level": "E2" if assessment["status"] == "PASS" else "E0",
        "model_scope": "2D single-bottom-gate n-IGZO, electron-only drift-diffusion Id-Vg continuation at VDS=0.01 V",
        "executed_bias_stage_ids": transfer["scope"]["executed_bias_stage_ids"],
        "reported_bias_stage_id": transfer["scope"]["reported_bias_stage_id"],
        "baseline_case_id": baseline["case_id"],
        "t01_b_case_id": t01_b_report["case_id"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "command": "make t01-c-transfer",
            "validation_command": "make t01-c-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "mesh": [
            {key: value for key, value in summary.items() if key != "solver_records"}
            for summary in mesh_summaries
        ],
        "bias_points": bias_rows,
        "mesh_comparison": mesh_rows,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "numerical_current_span_ratio": assessment["numerical_current_span_ratio"],
        "t01_b_reentry_relative_current_difference": assessment[
            "t01_b_reentry_relative_current_difference"
        ],
        "maximum_relative_mesh_current_difference": assessment[
            "maximum_relative_mesh_current_difference"
        ],
        "maximum_log10_mesh_current_difference_decades": assessment[
            "maximum_log10_mesh_current_difference_decades"
        ],
        "mesh_sensitivity": assessment["mesh_sensitivity"],
        "limitations": [
            "The numerical current span is not a physical Ion/Ioff result.",
            "The coarse/fine absolute-current difference above VGS=0.1 V requires T01-D mesh refinement before quantitative use.",
        ],
        "outputs": {
            "solver_log": str(solver_log_path.relative_to(ROOT)),
            "state_manifest": str(state_manifest_path.relative_to(ROOT)),
            "idvg_csv": str(idvg_path.relative_to(ROOT)),
            "mesh_comparison_csv": str(mesh_path.relative_to(ROOT)),
            "run_directory": str(run_dir.relative_to(ROOT)),
        },
        "evidence_boundary": transfer["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T01_C_TRANSFER_{report['status']} meshes={len(mesh_summaries)} "
        f"bias_points={len(bias_rows)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T01_C_TRANSFER_ERROR {caught_error}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
