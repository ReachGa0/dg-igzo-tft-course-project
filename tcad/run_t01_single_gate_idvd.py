#!/usr/bin/env python3
"""Run the T01-D-B sampled single-gate Id-Vd curve family."""

from __future__ import annotations

import argparse
import math
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t01_single_gate_mesh_refinement as mesh_stage  # noqa: E402


core = mesh_stage.core

BIAS_FIELDNAMES = [
    "mesh_role", "mesh_level", "curve_id", "stage_id", "vgs_v", "vds_v",
    "source_current_a_per_cm", "drain_current_a_per_cm", "source_current_terminal_a",
    "drain_current_terminal_a", "current_imbalance_a_per_cm",
    "relative_current_imbalance", "center_channel_potential_v",
    "center_channel_electron_density_cm3", "solve_seconds", "converged",
]
CURVE_METRIC_FIELDNAMES = [
    "mesh_role", "mesh_level", "curve_id", "vgs_v", "point_count",
    "zero_vds_abs_drain_current_a_per_cm", "endpoint_abs_drain_current_a_per_cm",
    "low_field_segment_conductance_s_per_cm", "high_field_segment_conductance_s_per_cm",
    "high_to_low_segment_conductance_ratio", "minimum_segment_conductance_s_per_cm",
    "maximum_segment_conductance_s_per_cm", "maximum_relative_current_drop",
    "monotonic_nondecreasing",
]
MESH_SUMMARY_FIELDNAMES = [
    "mesh_role", "mesh_level", "refinement_factor",
    "node_count_with_interface_duplicates", "element_count", "curve_count",
    "dc_solve_count", "reported_bias_point_count", "total_solve_seconds", "wall_seconds",
]
MESH_COMPARISON_FIELDNAMES = [
    "vgs_v", "vds_v", "production_abs_drain_current_a_per_cm",
    "reference_abs_drain_current_a_per_cm", "relative_current_difference",
    "log10_current_difference_decades", "production_center_channel_potential_v",
    "reference_center_channel_potential_v", "center_channel_potential_difference_v",
]
DA_REPRODUCTION_FIELDNAMES = [
    "mesh_level", "vgs_v", "vds_v", "t01_da_abs_drain_current_a_per_cm",
    "t01_db_abs_drain_current_a_per_cm", "relative_current_difference",
    "t01_da_center_channel_potential_v", "t01_db_center_channel_potential_v",
    "center_channel_potential_difference_v",
]


def same_value(left: float, right: float) -> bool:
    return math.isclose(left, right, rel_tol=0.0, abs_tol=1.0e-12)


def add_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def curve_id(mesh_level: str, vgs_v: float) -> str:
    token = f"{vgs_v:.3f}".replace("-", "m").replace(".", "p")
    return f"{mesh_level}_vgs_{token}"


def configured_curves(config: dict[str, Any]) -> list[dict[str, Any]]:
    protocol = config["bias_protocol"]
    mesh = config["mesh"]
    curves: list[dict[str, Any]] = []
    for role, level, key in (
        ("production", mesh["production_level"], "production_vgs_values_v"),
        ("reference", mesh["reference_level"], "reference_vgs_values_v"),
    ):
        for value in protocol[key]:
            vgs_v = float(value)
            curves.append({
                "mesh_role": role,
                "mesh_level": level,
                "vgs_v": vgs_v,
                "curve_id": curve_id(level, vgs_v),
            })
    return curves


def gate_path(config: dict[str, Any], target_vgs_v: float) -> list[float]:
    if target_vgs_v < 0.0:
        raise ValueError("T01-D-B only authorizes nonnegative VGS")
    values = [
        float(value)
        for value in config["bias_protocol"]["gate_preconditioning_ladder_v"]
        if float(value) <= target_vgs_v + 1.0e-12
    ]
    if target_vgs_v > 0.0 and not any(same_value(value, target_vgs_v) for value in values):
        values.append(target_vgs_v)
    return values


def run_curve(
    baseline: dict[str, Any],
    config: dict[str, Any],
    mesh_config: dict[str, Any],
    curve: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    mesh_level = str(curve["mesh_level"])
    mesh_role = str(curve["mesh_role"])
    target_vgs = float(curve["vgs_v"])
    identifier = str(curve["curve_id"])
    runtime, _ = mesh_stage.build_runtime_baseline(baseline, mesh_config, mesh_level)
    device = f"t01_db_{identifier}"
    records: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    try:
        core.initialize_device(device, runtime, mesh_level)
        core.set_biases(device, source_v=0.0, drain_v=0.0, bottom_gate_v=0.0)
        records.append(core.solve_dc(
            device, runtime, f"{identifier}_poisson_zero_bias_initialization", coupled=False
        ))
        core.create_transport(device, runtime)
        records.append(core.solve_dc(
            device, runtime, f"{identifier}_T01_A_STAGE_0", coupled=True
        ))
        for vgs_v in gate_path(config, target_vgs):
            core.set_biases(device, source_v=0.0, drain_v=0.0, bottom_gate_v=vgs_v)
            records.append(core.solve_dc(
                device,
                runtime,
                f"{identifier}_VGS_PRECONDITION_{vgs_v:.6g}_V",
                coupled=True,
            ))

        rows: list[dict[str, Any]] = []
        for vds_v in [float(value) for value in config["bias_protocol"]["vds_values_v"]]:
            core.set_biases(
                device,
                source_v=float(config["bias_protocol"]["source_v"]),
                drain_v=vds_v,
                bottom_gate_v=target_vgs,
            )
            record = core.solve_dc(
                device,
                runtime,
                f"{identifier}_T01_A_STAGE_3_VDS_{vds_v:.6g}_V",
                coupled=True,
            )
            records.append(record)
            row = core.collect_bias_row(
                device,
                runtime,
                mesh_level=mesh_level,
                stage_id="T01_A_STAGE_3",
                vds_v=vds_v,
                vgs_v=target_vgs,
                solve_record=record,
            )
            rows.append({"mesh_role": mesh_role, "curve_id": identifier, **row})

        nodes, elements = core.node_and_element_counts(device)
        return rows, {
            **curve,
            "node_count_with_interface_duplicates": nodes,
            "element_count": elements,
            "dc_solve_count": len(records),
            "reported_bias_point_count": len(rows),
            "total_solve_seconds": sum(float(record["elapsed_seconds"]) for record in records),
            "wall_seconds": time.perf_counter() - wall_start,
            "solver_records": records,
        }
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def aggregate_mesh_summaries(
    config: dict[str, Any],
    mesh_config: dict[str, Any],
    curve_summaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for role, level in zip(
        config["acceptance"]["required_mesh_roles"],
        config["acceptance"]["required_mesh_levels"],
        strict=True,
    ):
        summaries = [row for row in curve_summaries if row["mesh_level"] == level]
        if not summaries:
            continue
        output.append({
            "mesh_role": role,
            "mesh_level": level,
            "refinement_factor": float(mesh_stage.level_map(mesh_config)[level]["refinement_factor"]),
            "node_count_with_interface_duplicates": int(summaries[0]["node_count_with_interface_duplicates"]),
            "element_count": int(summaries[0]["element_count"]),
            "curve_count": len(summaries),
            "dc_solve_count": sum(int(row["dc_solve_count"]) for row in summaries),
            "reported_bias_point_count": sum(int(row["reported_bias_point_count"]) for row in summaries),
            "total_solve_seconds": sum(float(row["total_solve_seconds"]) for row in summaries),
            "wall_seconds": sum(float(row["wall_seconds"]) for row in summaries),
        })
    return output


def rows_for_curve(rows: list[dict[str, Any]], mesh_level: str, vgs_v: float) -> list[dict[str, Any]]:
    return sorted(
        [row for row in rows if row["mesh_level"] == mesh_level and same_value(float(row["vgs_v"]), vgs_v)],
        key=lambda row: float(row["vds_v"]),
    )


def point(
    rows: list[dict[str, Any]], mesh_level: str, vgs_v: float, vds_v: float
) -> dict[str, Any]:
    return next(
        row for row in rows
        if row["mesh_level"] == mesh_level
        and same_value(float(row["vgs_v"]), vgs_v)
        and same_value(float(row["vds_v"]), vds_v)
    )


def build_curve_metrics(config: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for curve in configured_curves(config):
        curve_rows = rows_for_curve(rows, curve["mesh_level"], float(curve["vgs_v"]))
        voltages = [float(row["vds_v"]) for row in curve_rows]
        currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve_rows]
        segments = [
            (higher_i - lower_i) / (higher_v - lower_v)
            for lower_v, higher_v, lower_i, higher_i in zip(
                voltages, voltages[1:], currents, currents[1:]
            )
        ]
        drops = [
            max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
            for lower, higher in zip(currents, currents[1:])
        ]
        low = segments[0]
        high = segments[-1]
        metrics.append({
            **curve,
            "point_count": len(curve_rows),
            "zero_vds_abs_drain_current_a_per_cm": currents[0],
            "endpoint_abs_drain_current_a_per_cm": currents[-1],
            "low_field_segment_conductance_s_per_cm": low,
            "high_field_segment_conductance_s_per_cm": high,
            "high_to_low_segment_conductance_ratio": high / max(low, 1.0e-300),
            "minimum_segment_conductance_s_per_cm": min(segments),
            "maximum_segment_conductance_s_per_cm": max(segments),
            "maximum_relative_current_drop": max(drops, default=0.0),
            "monotonic_nondecreasing": all(segment >= 0.0 for segment in segments),
        })
    return metrics


def build_mesh_comparisons(config: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    production = config["mesh"]["production_level"]
    reference = config["mesh"]["reference_level"]
    output: list[dict[str, Any]] = []
    for vgs_v in [float(value) for value in config["bias_protocol"]["reference_vgs_values_v"]]:
        for vds_v in [float(value) for value in config["bias_protocol"]["vds_values_v"]]:
            lower = point(rows, production, vgs_v, vds_v)
            higher = point(rows, reference, vgs_v, vds_v)
            lower_current = abs(float(lower["drain_current_a_per_cm"]))
            higher_current = abs(float(higher["drain_current_a_per_cm"]))
            output.append({
                "vgs_v": vgs_v,
                "vds_v": vds_v,
                "production_abs_drain_current_a_per_cm": lower_current,
                "reference_abs_drain_current_a_per_cm": higher_current,
                "relative_current_difference": abs(lower_current - higher_current)
                / max(lower_current, higher_current, 1.0e-300),
                "log10_current_difference_decades": abs(
                    math.log10(max(lower_current, 1.0e-300))
                    - math.log10(max(higher_current, 1.0e-300))
                ),
                "production_center_channel_potential_v": float(lower["center_channel_potential_v"]),
                "reference_center_channel_potential_v": float(higher["center_channel_potential_v"]),
                "center_channel_potential_difference_v": abs(
                    float(lower["center_channel_potential_v"])
                    - float(higher["center_channel_potential_v"])
                ),
            })
    return output


def build_da_reproduction(
    config: dict[str, Any], rows: list[dict[str, Any]], da_report: dict[str, Any]
) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for mesh_level in config["acceptance"]["required_mesh_levels"]:
        for vgs_v in (0.5, 1.0):
            reference = next(
                row for row in da_report["bias_points"]
                if row["mesh_level"] == mesh_level
                and same_value(float(row["vgs_v"]), vgs_v)
                and same_value(float(row["vds_v"]), 0.01)
            )
            reproduced = point(rows, mesh_level, vgs_v, 0.01)
            reference_current = abs(float(reference["drain_current_a_per_cm"]))
            reproduced_current = abs(float(reproduced["drain_current_a_per_cm"]))
            output.append({
                "mesh_level": mesh_level,
                "vgs_v": vgs_v,
                "vds_v": 0.01,
                "t01_da_abs_drain_current_a_per_cm": reference_current,
                "t01_db_abs_drain_current_a_per_cm": reproduced_current,
                "relative_current_difference": abs(reference_current - reproduced_current)
                / max(reference_current, reproduced_current, 1.0e-300),
                "t01_da_center_channel_potential_v": float(reference["center_channel_potential_v"]),
                "t01_db_center_channel_potential_v": float(reproduced["center_channel_potential_v"]),
                "center_channel_potential_difference_v": abs(
                    float(reference["center_channel_potential_v"])
                    - float(reproduced["center_channel_potential_v"])
                ),
            })
    return output


def render_figure(config: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> str:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    colors = {0.0: "#3b6ea8", 0.3: "#2a8a68", 0.5: "#c47a1d", 1.0: "#a33b45"}
    figure, axis = plt.subplots(figsize=(7.2, 4.8), constrained_layout=True)
    for curve in configured_curves(config):
        curve_rows = rows_for_curve(rows, curve["mesh_level"], float(curve["vgs_v"]))
        axis.plot(
            [float(row["vds_v"]) for row in curve_rows],
            [abs(float(row["drain_current_a_per_cm"])) for row in curve_rows],
            color=colors[float(curve["vgs_v"])],
            linestyle="-" if curve["mesh_role"] == "production" else "--",
            marker="o" if curve["mesh_role"] == "production" else "x",
            linewidth=1.8,
            markersize=4.8,
            label=(
                f"VGS={float(curve['vgs_v']):g} V, 4x"
                if curve["mesh_role"] == "production"
                else f"VGS={float(curve['vgs_v']):g} V, 8x check"
            ),
        )
    axis.set_title("T01-D-B sampled single-gate IGZO Id-Vd")
    axis.set_xlabel("VDS (V)")
    axis.set_ylabel("Absolute drain current (A/cm)")
    axis.set_xlim(0.0, max(float(value) for value in config["bias_protocol"]["vds_values_v"]))
    axis.set_ylim(bottom=0.0)
    axis.grid(True, color="#d8dee3", linewidth=0.7)
    axis.legend(loc="best", fontsize=8, frameon=True)
    axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    curve_summaries: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    comparisons: list[dict[str, Any]],
    reproductions: list[dict[str, Any]],
    figure_path: Path,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    curves = configured_curves(config)
    vds_values = [float(value) for value in acceptance["required_vds_values_v"]]
    add_check(
        checks,
        "configured_independent_curve_grid_completed",
        len(rows) == int(acceptance["required_total_reported_bias_points"])
        and all(
            [float(row["vds_v"]) for row in rows_for_curve(rows, curve["mesh_level"], float(curve["vgs_v"]))]
            == vds_values
            for curve in curves
        )
        and all(row["stage_id"] == "T01_A_STAGE_3" for row in rows),
        f"curves={len(curves)} bias_points={len(rows)}",
    )
    records = [record for summary in curve_summaries for record in summary["solver_records"]]
    add_check(
        checks,
        "all_dc_solves_converged",
        len(records) == int(acceptance["required_total_dc_solve_count"])
        and all(record["converged"] is True for record in records),
        f"solver_records={len(records)}",
    )
    zero_limit = float(acceptance["maximum_zero_vds_abs_terminal_current_a_per_cm"])
    zero_rows = [row for row in rows if same_value(float(row["vds_v"]), 0.0)]
    max_zero_current = max(
        max(abs(float(row["source_current_a_per_cm"])), abs(float(row["drain_current_a_per_cm"])))
        for row in zero_rows
    )
    add_check(
        checks,
        "zero_vds_terminal_current",
        len(zero_rows) == len(curves) and max_zero_current <= zero_limit,
        f"maximum={max_zero_current:.6e} limit={zero_limit:.6e}",
    )
    nonzero_rows = [row for row in rows if float(row["vds_v"]) > 0.0]
    floor = float(acceptance["minimum_nonzero_vds_abs_drain_current_a_per_cm"])
    add_check(
        checks,
        "finite_resolved_directional_nonzero_vds_current",
        all(
            math.isfinite(float(row["drain_current_a_per_cm"]))
            and float(row["drain_current_a_per_cm"]) >= floor
            and float(row["source_current_a_per_cm"]) <= -floor
            for row in nonzero_rows
        ),
        f"points={len(nonzero_rows)} floor={floor:.3e}",
    )
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in nonzero_rows)
    add_check(
        checks,
        "terminal_current_conservation",
        max_imbalance <= imbalance_limit,
        f"maximum={max_imbalance:.6e} limit={imbalance_limit:.6e}",
    )
    drop_limit = float(acceptance["maximum_monotonic_relative_current_drop"])
    max_drop = max(float(metric["maximum_relative_current_drop"]) for metric in metrics)
    add_check(
        checks,
        "each_idvd_curve_monotonic_nondecreasing",
        len(metrics) == len(curves)
        and max_drop <= drop_limit
        and all(bool(metric["monotonic_nondecreasing"]) for metric in metrics),
        f"maximum_relative_drop={max_drop:.6e} limit={drop_limit:.6e}",
    )
    production_mesh = config["mesh"]["production_level"]
    production_vgs = [float(value) for value in acceptance["required_production_vgs_values_v"]]
    gate_drop_limit = float(acceptance["maximum_gate_order_relative_current_drop"])
    maximum_gate_drop = 0.0
    gate_order_valid = True
    for vds_v in vds_values[1:]:
        values = [
            abs(float(point(rows, production_mesh, vgs_v, vds_v)["drain_current_a_per_cm"]))
            for vgs_v in production_vgs
        ]
        for lower, higher in zip(values, values[1:]):
            relative_drop = max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
            maximum_gate_drop = max(maximum_gate_drop, relative_drop)
            gate_order_valid = gate_order_valid and relative_drop <= gate_drop_limit
    add_check(
        checks,
        "production_current_ordered_with_vgs",
        gate_order_valid,
        f"maximum_relative_drop={maximum_gate_drop:.6e} limit={gate_drop_limit:.6e}",
    )
    minimum_segment = min(float(metric["minimum_segment_conductance_s_per_cm"]) for metric in metrics)
    add_check(
        checks,
        "sampled_segment_conductance_nonnegative",
        minimum_segment >= 0.0,
        f"minimum_segment_conductance={minimum_segment:.6e} S/cm",
    )
    positive_comparisons = [row for row in comparisons if float(row["vds_v"]) > 0.0]
    max_current_difference = max(float(row["relative_current_difference"]) for row in positive_comparisons)
    max_potential_difference = max(float(row["center_channel_potential_difference_v"]) for row in comparisons)
    current_limit = float(acceptance["maximum_reference_relative_current_difference"])
    potential_limit = float(acceptance["maximum_reference_center_potential_difference_v"])
    add_check(
        checks,
        "selected_high_vgs_reference_mesh_agreement",
        len(comparisons) == len(acceptance["required_reference_vgs_values_v"]) * len(vds_values)
        and max_current_difference <= current_limit
        and max_potential_difference <= potential_limit,
        (
            f"max_current_relative={max_current_difference:.6e} limit={current_limit:.6e} "
            f"max_potential_v={max_potential_difference:.6e} limit={potential_limit:.6e}"
        ),
    )
    da_current_limit = float(acceptance["maximum_t01_da_anchor_relative_current_difference"])
    da_potential_limit = float(acceptance["maximum_t01_da_anchor_potential_difference_v"])
    max_da_current = max(float(row["relative_current_difference"]) for row in reproductions)
    max_da_potential = max(float(row["center_channel_potential_difference_v"]) for row in reproductions)
    add_check(
        checks,
        "t01_da_low_vds_anchor_reproduced",
        len(reproductions) == 4
        and max_da_current <= da_current_limit
        and max_da_potential <= da_potential_limit,
        (
            f"max_current_relative={max_da_current:.6e} limit={da_current_limit:.6e} "
            f"max_potential_v={max_da_potential:.6e} limit={da_potential_limit:.6e}"
        ),
    )
    add_check(
        checks,
        "report_figure_written",
        figure_path.is_file() and figure_path.stat().st_size > 0,
        f"path={figure_path.relative_to(ROOT)} bytes={figure_path.stat().st_size if figure_path.exists() else 0}",
    )
    failures = [name for name, result in checks.items() if result["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_zero_vds_abs_terminal_current_a_per_cm": max_zero_current,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "maximum_curve_relative_current_drop": max_drop,
        "maximum_gate_order_relative_current_drop": maximum_gate_drop,
        "minimum_segment_conductance_s_per_cm": minimum_segment,
        "maximum_reference_relative_current_difference": max_current_difference,
        "maximum_reference_center_potential_difference_v": max_potential_difference,
        "maximum_t01_da_anchor_relative_current_difference": max_da_current,
        "maximum_t01_da_anchor_potential_difference_v": max_da_potential,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=ROOT / "config" / "tcad_t01_d_idvd.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = core.load_json(config_path)
    baseline_path = ROOT / config["input_contract"]["path"]
    contract_report_path = ROOT / config["input_contract"]["report"]
    mesh_config_path = ROOT / config["dependency"]["mesh_config"]
    mesh_report_path = ROOT / config["dependency"]["mesh_report"]
    baseline = core.load_json(baseline_path)
    contract_report = core.load_json(contract_report_path)
    mesh_config = core.load_json(mesh_config_path)
    mesh_report = core.load_json(mesh_report_path)

    if baseline.get("case_id") != config["input_contract"]["case_id"]:
        raise RuntimeError("T01-A baseline case ID changed")
    if contract_report.get("contract_status") != config["input_contract"]["required_contract_status"]:
        raise RuntimeError("T01-A input contract is not PASS")
    dependency = config["dependency"]
    mesh_gate = mesh_report.get("mesh_convergence", {})
    if (
        mesh_report.get("case_id") != mesh_config.get("case_id")
        or mesh_report.get("stage") != dependency["required_stage"]
        or mesh_report.get("status") != dependency["required_status"]
        or mesh_gate.get("status") != dependency["required_mesh_convergence_status"]
        or mesh_gate.get("idvd_stage_permitted_next")
        is not dependency["require_idvd_stage_permitted_next"]
    ):
        raise RuntimeError("T01-D-A dependency gate is not open")

    stage3 = mesh_stage.stage_by_id(baseline, "T01_A_STAGE_3")
    protocol = config["bias_protocol"]
    if (
        stage3.get("name") != "output_curve_points"
        or [float(value) for value in stage3["vgs_values_v"]]
        != [float(value) for value in protocol["production_vgs_values_v"]]
        or [float(value) for value in stage3["vds_values_v"]]
        != [float(value) for value in protocol["vds_values_v"]]
    ):
        raise RuntimeError("T01-D-B bias grid no longer matches frozen T01-A Stage 3")
    required_meshes = config["acceptance"]["required_mesh_levels"]
    if required_meshes != [config["mesh"]["production_level"], config["mesh"]["reference_level"]]:
        raise RuntimeError("T01-D-B mesh roles and acceptance order differ")
    if not set(required_meshes) <= set(mesh_stage.level_map(mesh_config)):
        raise RuntimeError("T01-D-B mesh levels are absent from T01-D-A ladder")

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    bias_path = ROOT / outputs["bias_csv"]
    metric_path = ROOT / outputs["curve_metrics_csv"]
    summary_path = ROOT / outputs["mesh_summary_csv"]
    comparison_path = ROOT / outputs["mesh_comparison_csv"]
    reproduction_path = ROOT / outputs["t01_da_reproduction_csv"]
    figure_path = ROOT / outputs["figure_png"]
    report_path = ROOT / outputs["report"]

    snapshot = {
        "idvd_config_path": str(config_path.relative_to(ROOT)),
        "idvd_config_sha256": core.sha256(config_path),
        "baseline_config_path": str(baseline_path.relative_to(ROOT)),
        "baseline_config_sha256": core.sha256(baseline_path),
        "t01_a_contract_report_path": str(contract_report_path.relative_to(ROOT)),
        "t01_a_contract_report_sha256": core.sha256(contract_report_path),
        "mesh_config_path": str(mesh_config_path.relative_to(ROOT)),
        "mesh_config_sha256": core.sha256(mesh_config_path),
        "mesh_report_path": str(mesh_report_path.relative_to(ROOT)),
        "mesh_report_sha256": core.sha256(mesh_report_path),
        "baseline_case_id": baseline["case_id"],
        "mesh_case_id": mesh_report["case_id"],
        "idvd_case_id": config["case_id"],
        "baseline": baseline,
        "mesh_refinement": mesh_config,
        "idvd": config,
    }
    core.write_json(snapshot_path, snapshot)

    rows: list[dict[str, Any]] = []
    curve_summaries: list[dict[str, Any]] = []
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t01-d-idvd",
        "validation_command": "make t01-d-idvd-check",
        "curve_runs": [],
        "errors": [],
    }
    caught_error: Exception | None = None
    curves = configured_curves(config)
    for curve in curves:
        try:
            curve_rows, summary = run_curve(baseline, config, mesh_config, curve)
            rows.extend(curve_rows)
            curve_summaries.append(summary)
            solver_log["curve_runs"].append({
                "curve_id": curve["curve_id"],
                "mesh_role": curve["mesh_role"],
                "mesh_level": curve["mesh_level"],
                "vgs_v": curve["vgs_v"],
                "status": "PASS",
                "solver_records": summary["solver_records"],
            })
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"curve_id": curve["curve_id"], "error": repr(error)})
            solver_log["curve_runs"].append({**curve, "status": "FAIL"})
            break

    completed = len(curve_summaries) == len(curves)
    metrics = build_curve_metrics(config, rows) if completed else []
    mesh_summaries = aggregate_mesh_summaries(config, mesh_config, curve_summaries)
    comparisons = build_mesh_comparisons(config, rows) if completed else []
    reproductions = build_da_reproduction(config, rows, mesh_report) if completed else []
    figure_sha256: str | None = None
    if caught_error is None and completed:
        try:
            figure_sha256 = render_figure(config, rows, figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"curve_id": "figure", "error": repr(error)})

    core.write_csv(bias_path, rows, BIAS_FIELDNAMES)
    core.write_csv(metric_path, metrics, CURVE_METRIC_FIELDNAMES)
    core.write_csv(summary_path, mesh_summaries, MESH_SUMMARY_FIELDNAMES)
    core.write_csv(comparison_path, comparisons, MESH_COMPARISON_FIELDNAMES)
    core.write_csv(reproduction_path, reproductions, DA_REPRODUCTION_FIELDNAMES)
    core.write_json(solver_log_path, solver_log)

    if caught_error is None and completed:
        assessment = assess(
            config, rows, curve_summaries, metrics, comparisons, reproductions, figure_path
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {"stage_exception": {"status": "FAIL", "detail": repr(caught_error)}},
            "failures": ["stage_exception"],
        }
    passed = assessment["status"] == "PASS"
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": "2D single-bottom-gate n-IGZO electron-only drift-diffusion, sampled positive-gate Id-Vd family",
        "executed_bias_stage_ids": config["scope"]["executed_bias_stage_ids"],
        "reported_bias_stage_id": config["scope"]["reported_bias_stage_id"],
        "baseline_case_id": baseline["case_id"],
        "t01_da_case_id": mesh_report["case_id"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "command": "make t01-d-idvd",
            "validation_command": "make t01-d-idvd-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "mesh": mesh_summaries,
        "bias_points": rows,
        "curve_metrics": metrics,
        "mesh_comparison": comparisons,
        "t01_da_reproduction": reproductions,
        "figure": {"path": str(figure_path.relative_to(ROOT)), "sha256": figure_sha256},
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {
            key: value for key, value in assessment.items()
            if key not in {"status", "checks", "failures"}
        },
        "idvd_completion": {
            "status": "PASS" if passed else "FAIL",
            "production_mesh": config["mesh"]["production_level"],
            "reference_mesh": config["mesh"]["reference_level"],
            "production_curve_count": len(config["bias_protocol"]["production_vgs_values_v"]),
            "reference_curve_count": len(config["bias_protocol"]["reference_vgs_values_v"]),
            "sampled_bias_point_count": len(rows),
            "continuous_curve_validation_permitted": False,
            "experimental_quantitative_use_permitted": False,
            "t01_dc_stage_permitted_next": passed,
        },
        "limitations": [
            "Id-Vd evidence applies only to the configured 4x production points and selected 8x high-positive-gate checks.",
            "Five sampled VDS values do not prove continuous behavior or validate saturation physics.",
            "The model remains an E2 teaching baseline without traps, non-ideal contacts, or experimental calibration.",
            "T01-D-B does not produce state maps, VTH, SS, mobility, physical Ion/Ioff, dual-gate, compact-model, circuit, or layout evidence.",
        ],
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T01_D_IDVD_{report['status']} curves={len(curve_summaries)} "
        f"bias_points={len(rows)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T01_D_IDVD_ERROR {caught_error}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
