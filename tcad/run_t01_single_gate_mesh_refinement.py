#!/usr/bin/env python3
"""Run T01-D-A interface-normal mesh refinement at low VDS."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t01_single_gate_smoke as core  # noqa: E402


BIAS_FIELDNAMES = [
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

MESH_SUMMARY_FIELDNAMES = [
    "mesh_level",
    "refinement_factor",
    "x_spacing_cm",
    "bulk_oxide_y_spacing_cm",
    "bulk_channel_y_spacing_cm",
    "oxide_interface_window_cm",
    "channel_interface_window_cm",
    "oxide_interface_spacing_cm",
    "channel_interface_spacing_cm",
    "node_count_with_interface_duplicates",
    "element_count",
    "dc_solve_count",
    "reported_bias_point_count",
    "total_solve_seconds",
    "wall_seconds",
]

COMPARISON_FIELDNAMES = [
    "lower_refinement_mesh",
    "higher_refinement_mesh",
    "lower_refinement_factor",
    "higher_refinement_factor",
    "vgs_v",
    "vds_v",
    "lower_abs_drain_current_a_per_cm",
    "higher_abs_drain_current_a_per_cm",
    "relative_current_difference",
    "log10_current_difference_decades",
    "lower_center_channel_potential_v",
    "higher_center_channel_potential_v",
    "center_channel_potential_difference_v",
]

REPRODUCTION_FIELDNAMES = [
    "vgs_v",
    "vds_v",
    "t01_c_fine_abs_drain_current_a_per_cm",
    "t01_d_fine_1x_abs_drain_current_a_per_cm",
    "relative_current_difference",
    "t01_c_fine_center_channel_potential_v",
    "t01_d_fine_1x_center_channel_potential_v",
    "center_channel_potential_difference_v",
]


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def stage_by_id(baseline: dict[str, Any], stage_id: str) -> dict[str, Any]:
    return next(stage for stage in baseline["bias_protocol"]["stages"] if stage["id"] == stage_id)


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def level_map(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {level["id"]: level for level in config["mesh_ladder"]["levels"]}


def build_runtime_baseline(
    baseline: dict[str, Any], config: dict[str, Any], mesh_level: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    ladder = config["mesh_ladder"]
    level = level_map(config)[mesh_level]
    factor = float(level["refinement_factor"])
    mesh_spec = {
        "x_spacing_cm": float(ladder["fixed_x_spacing_cm"]),
        "oxide_y_spacing_cm": float(ladder["fixed_bulk_oxide_y_spacing_cm"]),
        "channel_y_spacing_cm": float(ladder["fixed_bulk_channel_y_spacing_cm"]),
        "interface_refinement": {
            "oxide_window_cm": float(ladder["oxide_interface_window_cm"]),
            "channel_window_cm": float(ladder["channel_interface_window_cm"]),
            "oxide_spacing_cm": float(ladder["fixed_bulk_oxide_y_spacing_cm"]) / factor,
            "channel_spacing_cm": float(ladder["fixed_bulk_channel_y_spacing_cm"]) / factor,
        },
    }
    runtime = copy.deepcopy(baseline)
    runtime["mesh"]["levels"][mesh_level] = mesh_spec
    return runtime, mesh_spec


def write_accumulation_state(
    device: str,
    mesh_level: str,
    vgs_v: float,
    vds_v: float,
    run_dir: Path,
) -> dict[str, Any]:
    rows = core.collect_state_nodes(device, mesh_level)
    enriched = [
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
    stem = f"t01_d_mesh_{mesh_level}_vgs_1p000"
    state_path = run_dir / f"{stem}_nodes.csv"
    core.write_csv(state_path, enriched, STATE_FIELDNAMES)
    vtk_base = run_dir / stem
    core.devsim.write_devices(file=str(vtk_base), device=device, type="vtk")
    vtk_files: list[dict[str, str]] = []
    for output_path in sorted(run_dir.glob(f"{vtk_base.name}*")):
        if output_path == state_path:
            continue
        core.normalize_text_newline(output_path)
        vtk_files.append(
            {
                "path": str(output_path.relative_to(ROOT)),
                "sha256": core.sha256(output_path),
            }
        )
    return {
        "mesh_level": mesh_level,
        "vgs_v": vgs_v,
        "vds_v": vds_v,
        "node_count_with_interface_duplicates": len(enriched),
        "state_csv": str(state_path.relative_to(ROOT)),
        "state_csv_sha256": core.sha256(state_path),
        "vtk_base": str(vtk_base.relative_to(ROOT)),
        "vtk_files": vtk_files,
    }


def run_mesh(
    baseline: dict[str, Any],
    config: dict[str, Any],
    mesh_level: str,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    runtime, mesh_spec = build_runtime_baseline(baseline, config, mesh_level)
    factor = float(level_map(config)[mesh_level]["refinement_factor"])
    device = f"t01_d_mesh_{mesh_level}"
    solver_records: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    try:
        core.initialize_device(device, runtime, mesh_level)
        stage_zero = stage_by_id(runtime, "T01_A_STAGE_0")
        stage_low_vds = stage_by_id(runtime, "T01_A_STAGE_1")
        core.set_biases(
            device,
            source_v=float(stage_zero["source_v"]),
            drain_v=float(stage_zero["drain_v"]),
            bottom_gate_v=float(stage_zero["bottom_gate_v"]),
        )
        solver_records.append(
            core.solve_dc(device, runtime, "poisson_zero_bias_initialization", coupled=False)
        )
        core.create_transport(device, runtime)
        solver_records.append(core.solve_dc(device, runtime, "T01_A_STAGE_0", coupled=True))

        last_low_vds_record: dict[str, Any] | None = None
        for vds_v in [float(value) for value in stage_low_vds["vds_values_v"]]:
            core.set_biases(device, source_v=0.0, drain_v=vds_v, bottom_gate_v=0.0)
            last_low_vds_record = core.solve_dc(
                device,
                runtime,
                f"T01_A_STAGE_1_VDS_{vds_v:.6g}_V",
                coupled=True,
            )
            solver_records.append(last_low_vds_record)
        if last_low_vds_record is None:
            raise RuntimeError("T01-A low-VDS continuation is empty")

        continuation = config["continuation"]
        fixed_vds = float(continuation["vds_v"])
        bias_rows: list[dict[str, Any]] = []
        state_vgs_values = [float(value) for value in continuation["state_output_vgs_values_v"]]
        for index, vgs_v in enumerate(float(value) for value in continuation["vgs_values_v"]):
            if index == 0 and same_value(vgs_v, 0.0):
                solve_record = last_low_vds_record
            else:
                core.set_biases(device, source_v=0.0, drain_v=fixed_vds, bottom_gate_v=vgs_v)
                solve_record = core.solve_dc(
                    device,
                    runtime,
                    f"T01_DA_MESH_VGS_{vgs_v:.6g}_V",
                    coupled=True,
                )
                solver_records.append(solve_record)
            bias_rows.append(
                core.collect_bias_row(
                    device,
                    runtime,
                    mesh_level=mesh_level,
                    stage_id="T01_A_STAGE_2",
                    vds_v=fixed_vds,
                    vgs_v=vgs_v,
                    solve_record=solve_record,
                )
            )
            if any(same_value(vgs_v, selected) for selected in state_vgs_values):
                state_entries.append(
                    write_accumulation_state(device, mesh_level, vgs_v, fixed_vds, run_dir)
                )

        node_count, element_count = core.node_and_element_counts(device)
        refinement = mesh_spec["interface_refinement"]
        summary = {
            "mesh_level": mesh_level,
            "refinement_factor": factor,
            "x_spacing_cm": mesh_spec["x_spacing_cm"],
            "bulk_oxide_y_spacing_cm": mesh_spec["oxide_y_spacing_cm"],
            "bulk_channel_y_spacing_cm": mesh_spec["channel_y_spacing_cm"],
            "oxide_interface_window_cm": refinement["oxide_window_cm"],
            "channel_interface_window_cm": refinement["channel_window_cm"],
            "oxide_interface_spacing_cm": refinement["oxide_spacing_cm"],
            "channel_interface_spacing_cm": refinement["channel_spacing_cm"],
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(solver_records),
            "reported_bias_point_count": len(bias_rows),
            "total_solve_seconds": sum(float(record["elapsed_seconds"]) for record in solver_records),
            "wall_seconds": time.perf_counter() - wall_start,
            "solver_records": solver_records,
        }
        return bias_rows, summary, solver_records, state_entries
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def row_lookup(
    rows: list[dict[str, Any]], mesh_level: str, vgs_v: float
) -> dict[str, Any]:
    return next(
        row
        for row in rows
        if row["mesh_level"] == mesh_level and same_value(float(row["vgs_v"]), vgs_v)
    )


def build_mesh_comparisons(
    config: dict[str, Any], bias_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    levels = config["mesh_ladder"]["levels"]
    vgs_values = [float(value) for value in config["continuation"]["vgs_values_v"]]
    comparisons: list[dict[str, Any]] = []
    for lower_level, higher_level in zip(levels, levels[1:]):
        lower_id = lower_level["id"]
        higher_id = higher_level["id"]
        for vgs_v in vgs_values:
            lower = row_lookup(bias_rows, lower_id, vgs_v)
            higher = row_lookup(bias_rows, higher_id, vgs_v)
            lower_current = abs(float(lower["drain_current_a_per_cm"]))
            higher_current = abs(float(higher["drain_current_a_per_cm"]))
            comparisons.append(
                {
                    "lower_refinement_mesh": lower_id,
                    "higher_refinement_mesh": higher_id,
                    "lower_refinement_factor": float(lower_level["refinement_factor"]),
                    "higher_refinement_factor": float(higher_level["refinement_factor"]),
                    "vgs_v": vgs_v,
                    "vds_v": float(lower["vds_v"]),
                    "lower_abs_drain_current_a_per_cm": lower_current,
                    "higher_abs_drain_current_a_per_cm": higher_current,
                    "relative_current_difference": abs(lower_current - higher_current)
                    / max(lower_current, higher_current, 1.0e-300),
                    "log10_current_difference_decades": abs(
                        math.log10(max(lower_current, 1.0e-300))
                        - math.log10(max(higher_current, 1.0e-300))
                    ),
                    "lower_center_channel_potential_v": float(
                        lower["center_channel_potential_v"]
                    ),
                    "higher_center_channel_potential_v": float(
                        higher["center_channel_potential_v"]
                    ),
                    "center_channel_potential_difference_v": abs(
                        float(lower["center_channel_potential_v"])
                        - float(higher["center_channel_potential_v"])
                    ),
                }
            )
    return comparisons


def build_t01_c_reproduction(
    config: dict[str, Any],
    bias_rows: list[dict[str, Any]],
    t01_c_report: dict[str, Any],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for vgs_v in [
        float(value) for value in config["continuation"]["t01_c_reproduction_vgs_values_v"]
    ]:
        reference = next(
            row
            for row in t01_c_report["bias_points"]
            if row["mesh_level"] == "fine" and same_value(float(row["vgs_v"]), vgs_v)
        )
        reproduced = row_lookup(bias_rows, "fine_1x", vgs_v)
        reference_current = abs(float(reference["drain_current_a_per_cm"]))
        reproduced_current = abs(float(reproduced["drain_current_a_per_cm"]))
        output.append(
            {
                "vgs_v": vgs_v,
                "vds_v": float(reproduced["vds_v"]),
                "t01_c_fine_abs_drain_current_a_per_cm": reference_current,
                "t01_d_fine_1x_abs_drain_current_a_per_cm": reproduced_current,
                "relative_current_difference": abs(reference_current - reproduced_current)
                / max(reference_current, reproduced_current, 1.0e-300),
                "t01_c_fine_center_channel_potential_v": float(
                    reference["center_channel_potential_v"]
                ),
                "t01_d_fine_1x_center_channel_potential_v": float(
                    reproduced["center_channel_potential_v"]
                ),
                "center_channel_potential_difference_v": abs(
                    float(reference["center_channel_potential_v"])
                    - float(reproduced["center_channel_potential_v"])
                ),
            }
        )
    return output


def assess_mesh_refinement(
    config: dict[str, Any],
    bias_rows: list[dict[str, Any]],
    mesh_summaries: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    reproduction_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    expected_meshes = list(acceptance["required_mesh_levels"])
    expected_factors = [float(value) for value in acceptance["required_refinement_factors"]]
    expected_vgs = [float(value) for value in acceptance["required_vgs_values_v"]]
    fixed_vds = float(acceptance["fixed_vds_v"])
    checks: dict[str, dict[str, Any]] = {}
    summaries = {summary["mesh_level"]: summary for summary in mesh_summaries}

    add_check(
        checks,
        "configured_mesh_ladder_completed",
        [summary["mesh_level"] for summary in mesh_summaries] == expected_meshes
        and [float(summary["refinement_factor"]) for summary in mesh_summaries]
        == expected_factors,
        f"meshes={','.join(summary['mesh_level'] for summary in mesh_summaries)}",
    )
    solver_records = [record for summary in mesh_summaries for record in summary["solver_records"]]
    add_check(
        checks,
        "all_dc_solves_converged",
        bool(solver_records) and all(bool(record["converged"]) for record in solver_records),
        f"solver_records={len(solver_records)}",
    )
    by_mesh = {
        mesh: [row for row in bias_rows if row["mesh_level"] == mesh]
        for mesh in expected_meshes
    }
    add_check(
        checks,
        "required_positive_vgs_grid",
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
    add_check(
        checks,
        "finite_numerically_nonzero_directional_current",
        all(math.isfinite(value) and value >= floor for values in currents.values() for value in values)
        and signs == {1.0},
        f"floor={floor:.3e} signs={sorted(signs)}",
    )
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in bias_rows)
    add_check(
        checks,
        "terminal_current_conservation",
        max_imbalance <= imbalance_limit,
        f"maximum={max_imbalance:.6e} limit={imbalance_limit:.6e}",
    )
    drop_limit = float(acceptance["maximum_monotonic_relative_current_drop"])
    add_check(
        checks,
        "drain_current_monotonic_with_vgs",
        all(
            next_value >= value * (1.0 - drop_limit)
            for values in currents.values()
            for value, next_value in zip(values, values[1:])
        ),
        f"maximum_relative_drop={drop_limit:.3e}",
    )
    node_counts = [int(summaries[mesh]["node_count_with_interface_duplicates"]) for mesh in expected_meshes]
    add_check(
        checks,
        "active_node_count_strictly_increases",
        all(higher > lower for lower, higher in zip(node_counts, node_counts[1:])),
        f"node_counts={node_counts}",
    )
    current_reproduction_limit = float(
        acceptance["maximum_t01_c_fine_reproduction_relative_current_difference"]
    )
    potential_reproduction_limit = float(
        acceptance["maximum_t01_c_fine_reproduction_potential_difference_v"]
    )
    add_check(
        checks,
        "fine_1x_reproduces_t01_c_fine",
        bool(reproduction_rows)
        and all(
            float(row["relative_current_difference"]) <= current_reproduction_limit
            and float(row["center_channel_potential_difference_v"])
            <= potential_reproduction_limit
            for row in reproduction_rows
        ),
        (
            f"max_current_relative={max(float(row['relative_current_difference']) for row in reproduction_rows):.6e} "
            f"max_potential_v={max(float(row['center_channel_potential_difference_v']) for row in reproduction_rows):.6e}"
        ),
    )
    convergence_pair = config["mesh_ladder"]["convergence_pair"]
    target_vgs = [
        float(value) for value in config["continuation"]["mesh_convergence_vgs_values_v"]
    ]
    convergence_rows = [
        row
        for row in comparisons
        if row["lower_refinement_mesh"] == convergence_pair[0]
        and row["higher_refinement_mesh"] == convergence_pair[1]
        and any(same_value(float(row["vgs_v"]), target) for target in target_vgs)
    ]
    current_limit = float(acceptance["maximum_finest_pair_relative_current_difference"])
    potential_limit = float(
        acceptance["maximum_finest_pair_center_potential_difference_v"]
    )
    max_current_difference = max(
        float(row["relative_current_difference"]) for row in convergence_rows
    )
    max_potential_difference = max(
        float(row["center_channel_potential_difference_v"]) for row in convergence_rows
    )
    add_check(
        checks,
        "finest_pair_low_vds_positive_bias_mesh_convergence",
        len(convergence_rows) == len(target_vgs)
        and max_current_difference <= current_limit
        and max_potential_difference <= potential_limit,
        (
            f"pair={convergence_pair} targets={target_vgs} "
            f"max_current_relative={max_current_difference:.6e} limit={current_limit:.6e} "
            f"max_potential_v={max_potential_difference:.6e} limit={potential_limit:.6e}"
        ),
    )
    state_paths = [ROOT / entry["state_csv"] for entry in state_entries]
    vtk_files = [item for entry in state_entries for item in entry["vtk_files"]]
    add_check(
        checks,
        "accumulation_state_outputs_present",
        len(state_entries) == len(expected_meshes)
        and {entry["mesh_level"] for entry in state_entries} == set(expected_meshes)
        and all(path.is_file() and path.stat().st_size > 0 for path in state_paths)
        and len(vtk_files) >= len(expected_meshes),
        f"state_csv={len(state_entries)} vtk_files={len(vtk_files)}",
    )
    failures = [name for name, value in checks.items() if value["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "convergence_pair": convergence_pair,
        "convergence_target_vgs_values_v": target_vgs,
        "maximum_finest_pair_relative_current_difference": max_current_difference,
        "maximum_finest_pair_center_potential_difference_v": max_potential_difference,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_t01_d_mesh_refinement.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = core.load_json(config_path)
    baseline_path = ROOT / config["input_contract"]["path"]
    baseline = core.load_json(baseline_path)
    dependencies = config["dependency_reports"]
    t01_a_path = ROOT / dependencies["t01_a_contract"]
    t01_b_path = ROOT / dependencies["t01_b_smoke"]
    t01_c_path = ROOT / dependencies["t01_c_transfer"]
    t01_a_report = core.load_json(t01_a_path)
    t01_b_report = core.load_json(t01_b_path)
    t01_c_report = core.load_json(t01_c_path)
    if t01_a_report.get("contract_status") != config["input_contract"]["required_contract_status"]:
        raise RuntimeError("T01-A input contract is not PASS")
    if t01_b_report.get("status") != dependencies["required_t01_b_status"]:
        raise RuntimeError("T01-B dependency report is not PASS")
    if t01_c_report.get("status") != dependencies["required_t01_c_status"]:
        raise RuntimeError("T01-C dependency report is not PASS")
    if t01_c_report.get("mesh_sensitivity", {}).get("status") != dependencies[
        "required_t01_c_mesh_status"
    ]:
        raise RuntimeError("T01-C mesh warning required for T01-D-A was not found")
    if t01_c_report.get("mesh_sensitivity", {}).get(
        "quantitative_absolute_current_use_permitted"
    ) is not False:
        raise RuntimeError("T01-C evidence boundary is inconsistent")
    if baseline.get("case_id") != config["input_contract"]["case_id"]:
        raise RuntimeError("T01-A baseline case ID changed")

    ladder = config["mesh_ladder"]
    baseline_mesh = baseline["mesh"]["levels"][ladder["baseline_level"]]
    fixed_mesh_values = (
        float(ladder["fixed_x_spacing_cm"]),
        float(ladder["fixed_bulk_oxide_y_spacing_cm"]),
        float(ladder["fixed_bulk_channel_y_spacing_cm"]),
    )
    baseline_mesh_values = (
        float(baseline_mesh["x_spacing_cm"]),
        float(baseline_mesh["oxide_y_spacing_cm"]),
        float(baseline_mesh["channel_y_spacing_cm"]),
    )
    if fixed_mesh_values != baseline_mesh_values:
        raise RuntimeError("T01-D-A fixed mesh values do not reproduce the T01-C fine mesh")
    mesh_levels = [level["id"] for level in ladder["levels"]]
    if mesh_levels != config["acceptance"]["required_mesh_levels"]:
        raise RuntimeError("configured and accepted mesh-level orders differ")

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    bias_path = ROOT / outputs["bias_csv"]
    summary_path = ROOT / outputs["mesh_summary_csv"]
    comparison_path = ROOT / outputs["mesh_comparison_csv"]
    reproduction_path = ROOT / outputs["t01_c_reproduction_csv"]
    report_path = ROOT / outputs["report"]

    snapshot = {
        "mesh_config_path": str(config_path.relative_to(ROOT)),
        "mesh_config_sha256": core.sha256(config_path),
        "baseline_config_path": str(baseline_path.relative_to(ROOT)),
        "baseline_config_sha256": core.sha256(baseline_path),
        "t01_a_report_path": str(t01_a_path.relative_to(ROOT)),
        "t01_a_report_sha256": core.sha256(t01_a_path),
        "t01_b_report_path": str(t01_b_path.relative_to(ROOT)),
        "t01_b_report_sha256": core.sha256(t01_b_path),
        "t01_c_report_path": str(t01_c_path.relative_to(ROOT)),
        "t01_c_report_sha256": core.sha256(t01_c_path),
        "baseline_case_id": baseline["case_id"],
        "mesh_case_id": config["case_id"],
        "baseline": baseline,
        "mesh_refinement": config,
    }
    core.write_json(snapshot_path, snapshot)

    bias_rows: list[dict[str, Any]] = []
    mesh_summaries: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t01-d-mesh",
        "validation_command": "make t01-d-mesh-check",
        "mesh_runs": [],
        "errors": [],
    }
    caught_error: Exception | None = None
    for mesh_level in mesh_levels:
        try:
            rows, summary, records, states = run_mesh(
                baseline, config, mesh_level, run_dir
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

    core.write_csv(bias_path, bias_rows, BIAS_FIELDNAMES)
    core.write_csv(
        summary_path,
        [{key: value for key, value in summary.items() if key != "solver_records"} for summary in mesh_summaries],
        MESH_SUMMARY_FIELDNAMES,
    )
    completed = len(mesh_summaries) == len(mesh_levels)
    comparisons = build_mesh_comparisons(config, bias_rows) if completed else []
    reproduction_rows = (
        build_t01_c_reproduction(config, bias_rows, t01_c_report) if completed else []
    )
    core.write_csv(comparison_path, comparisons, COMPARISON_FIELDNAMES)
    core.write_csv(reproduction_path, reproduction_rows, REPRODUCTION_FIELDNAMES)
    state_manifest = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "entries": state_entries,
    }
    core.write_json(state_manifest_path, state_manifest)
    core.write_json(solver_log_path, solver_log)

    if caught_error is None and completed:
        assessment = assess_mesh_refinement(
            config,
            bias_rows,
            mesh_summaries,
            state_entries,
            comparisons,
            reproduction_rows,
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
            "maximum_relative_terminal_current_imbalance": None,
            "convergence_pair": ladder["convergence_pair"],
            "convergence_target_vgs_values_v": config["continuation"][
                "mesh_convergence_vgs_values_v"
            ],
            "maximum_finest_pair_relative_current_difference": None,
            "maximum_finest_pair_center_potential_difference_v": None,
        }
    passed = assessment["status"] == "PASS"
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": "2D single-bottom-gate n-IGZO electron-only drift-diffusion, low-VDS positive-gate interface-normal mesh refinement",
        "executed_bias_stage_ids": config["scope"]["executed_bias_stage_ids"],
        "reported_bias_stage_id": config["scope"]["reported_bias_stage_id"],
        "baseline_case_id": baseline["case_id"],
        "t01_c_case_id": t01_c_report["case_id"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "command": "make t01-d-mesh",
            "validation_command": "make t01-d-mesh-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "mesh": [
            {key: value for key, value in summary.items() if key != "solver_records"}
            for summary in mesh_summaries
        ],
        "bias_points": bias_rows,
        "mesh_comparison": comparisons,
        "t01_c_fine_reproduction": reproduction_rows,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "maximum_relative_terminal_current_imbalance": assessment[
            "maximum_relative_terminal_current_imbalance"
        ],
        "mesh_convergence": {
            "status": "PASS" if passed else "FAIL",
            "pair": assessment["convergence_pair"],
            "target_vgs_values_v": assessment["convergence_target_vgs_values_v"],
            "maximum_relative_current_difference": assessment[
                "maximum_finest_pair_relative_current_difference"
            ],
            "maximum_center_channel_potential_difference_v": assessment[
                "maximum_finest_pair_center_potential_difference_v"
            ],
            "numerical_low_vds_positive_bias_absolute_current_converged": passed,
            "experimental_quantitative_use_permitted": False,
            "idvd_stage_permitted_next": passed,
        },
        "limitations": [
            "Mesh convergence applies only to VDS=0.01 V and the configured VGS=0.5/1.0 V target points.",
            "The model remains an E2 teaching baseline without traps, non-ideal contacts, or experimental calibration.",
            "T01-D-A does not produce Id-Vd, VTH, SS, mobility, physical Ion/Ioff, dual-gate, compact-model, circuit, or layout evidence.",
        ],
        "outputs": {
            key: value
            for key, value in outputs.items()
            if key != "check_report"
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T01_D_MESH_{report['status']} meshes={len(mesh_summaries)} "
        f"bias_points={len(bias_rows)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T01_D_MESH_ERROR {caught_error}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
