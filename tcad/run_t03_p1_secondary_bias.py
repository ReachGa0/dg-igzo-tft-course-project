#!/usr/bin/env python3
"""Run the frozen T03-P1-BIAS five-point secondary-gate sensitivity."""

from __future__ import annotations

import json
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

import run_t02_dual_gate_bidirectional as t02_c  # noqa: E402
import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402


core = t02_c.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p1_secondary_bias.json"
STAGE_ID = "T03_P1_SECONDARY_BIAS"
REFERENCE_FIELDNAMES = [
    "primary_gate_v",
    "t03_abs_drain_current_a_per_cm",
    "t02_c_abs_drain_current_a_per_cm",
    "current_relative_difference",
    "t03_center_channel_potential_v",
    "t02_c_center_channel_potential_v",
    "center_channel_potential_difference_v",
    "t03_center_channel_electron_density_cm3",
    "t02_c_center_channel_electron_density_cm3",
    "center_density_relative_difference",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1.0e-12)


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def curve_for_bias(
    rows: list[dict[str, Any]], secondary_v: float
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), secondary_v)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def metric_for(
    metrics: list[dict[str, Any]], secondary_v: float
) -> dict[str, Any]:
    return next(
        row
        for row in metrics
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), secondary_v)
    )


def build_reference_comparison(
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    t02_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, float | int]]:
    current_curve = curve_for_bias(rows, 0.0)
    reference_curve = sorted(
        [
            row
            for row in t02_report["family_points"]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )
    reference_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in reference_curve
    }
    comparisons: list[dict[str, Any]] = []
    for row in current_curve:
        voltage = float(row["primary_gate_v"])
        reference = reference_by_voltage[round(voltage, 12)]
        current = abs(float(row["drain_current_a_per_cm"]))
        reference_current = abs(float(reference["drain_current_a_per_cm"]))
        density = float(row["center_channel_electron_density_cm3"])
        reference_density = float(reference["center_channel_electron_density_cm3"])
        comparisons.append({
            "primary_gate_v": voltage,
            "t03_abs_drain_current_a_per_cm": current,
            "t02_c_abs_drain_current_a_per_cm": reference_current,
            "current_relative_difference": abs(current - reference_current)
            / max(current, reference_current, 1.0e-300),
            "t03_center_channel_potential_v": float(
                row["center_channel_potential_v"]
            ),
            "t02_c_center_channel_potential_v": float(
                reference["center_channel_potential_v"]
            ),
            "center_channel_potential_difference_v": abs(
                float(row["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
            "t03_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": reference_density,
            "center_density_relative_difference": abs(density - reference_density)
            / max(density, reference_density, 1.0e-300),
        })
    current_metric = metric_for(metrics, 0.0)
    reference_metric = next(
        row
        for row in t02_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    gm = float(current_metric["gm_proxy_s_per_cm"])
    reference_gm = float(reference_metric["gm_proxy_s_per_cm"])
    summary: dict[str, float | int] = {
        "point_count": len(comparisons),
        "maximum_current_relative_difference": max(
            float(row["current_relative_difference"]) for row in comparisons
        ),
        "maximum_center_potential_difference_v": max(
            float(row["center_channel_potential_difference_v"])
            for row in comparisons
        ),
        "maximum_center_density_relative_difference": max(
            float(row["center_density_relative_difference"])
            for row in comparisons
        ),
        "vth_difference_v": abs(
            float(current_metric["vth_proxy_v"])
            - float(reference_metric["vth_proxy_v"])
        ),
        "gm_relative_difference": abs(gm - reference_gm)
        / max(abs(gm), abs(reference_gm), 1.0e-300),
    }
    return comparisons, summary


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))


def render_sensitivity_figure(
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    path: Path,
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    values = [float(value) for value in config["sensitivity"]["values_v"]]
    colors = ["#2563a6", "#287d59", "#555b63", "#c45d25", "#a33a3a"]
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.0), constrained_layout=True)
    for secondary_v, color in zip(values, colors):
        curve = curve_for_bias(rows, secondary_v)
        axes[0][0].semilogy(
            [float(row["primary_gate_v"]) for row in curve],
            [abs(float(row["drain_current_a_per_cm"])) for row in curve],
            color=color,
            linewidth=1.7,
            label=f"VBG={secondary_v:+.1f} V",
        )
    axes[0][0].set_title("Top-primary transfer families")
    axes[0][0].set_xlabel("Top-gate voltage (V)")
    axes[0][0].set_ylabel("Absolute drain current per width (A/cm)")
    axes[0][0].legend(fontsize=7)

    vth = [float(metric_for(metrics, value)["vth_proxy_v"]) for value in values]
    slope = float(metrics[0]["coupling_slope_v_per_v"])
    intercept = float(metrics[0]["coupling_fit_intercept_v"])
    r_squared = float(metrics[0]["coupling_fit_r_squared"])
    axes[0][1].plot(values, vth, "o", color="#287d59", label="VTH proxy")
    axes[0][1].plot(
        values,
        [slope * value + intercept for value in values],
        "--",
        color="#555b63",
        label="five-point OLS",
    )
    axes[0][1].set_title(f"Coupling slope = {slope:.4f} V/V, R2={r_squared:.5f}")
    axes[0][1].set_xlabel("Fixed bottom-gate voltage (V)")
    axes[0][1].set_ylabel("Constant-current VTH proxy (V)")
    axes[0][1].legend(fontsize=8)

    delta_vth = [
        float(metric_for(metrics, value)["delta_vth_proxy_v"]) for value in values
    ]
    axes[1][0].plot(values, delta_vth, "o-", color="#2563a6", linewidth=1.8)
    axes[1][0].axhline(0.0, color="#72777d", linewidth=0.8)
    axes[1][0].set_title("Threshold-shift numerical proxy")
    axes[1][0].set_xlabel("Fixed bottom-gate voltage (V)")
    axes[1][0].set_ylabel("Delta VTH proxy (V)")

    gm = [float(metric_for(metrics, value)["gm_proxy_s_per_cm"]) for value in values]
    axes[1][1].plot(values, gm, "o-", color="#c45d25", linewidth=1.8)
    axes[1][1].set_title("gm proxy at VTH + 0.2 V")
    axes[1][1].set_xlabel("Fixed bottom-gate voltage (V)")
    axes[1][1].set_ylabel("gm proxy (S/cm)")
    axes[1][1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    for axis in axes.flat:
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle("T03-P1-BIAS IGZO secondary-gate numerical sensitivity", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def render_state_figure(state_entries: list[dict[str, Any]], path: Path) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415
    from matplotlib.cm import ScalarMappable  # noqa: PLC0415
    from matplotlib.colors import Normalize  # noqa: PLC0415

    ordered = sorted(state_entries, key=lambda row: float(row["vbg_v"]))
    potentials = [
        float(row["potential_v"]) for entry in ordered for row in entry["_node_rows"]
    ]
    log_density = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
        for entry in ordered
        for row in entry["_node_rows"]
        if row["region"] == "channel"
    ]
    log_current = [
        math.log10(
            max(
                float(row["electron_current_density_magnitude_a_per_cm2"]),
                1.0e-300,
            )
        )
        for entry in ordered
        for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(log_density), max(log_density)),
        Normalize(min(log_current), max(log_current)),
    ]
    cmaps = ["viridis", "plasma", "magma"]
    figure, axes = plt.subplots(5, 3, figsize=(11.2, 12.2), constrained_layout=True)
    for row_index, entry in enumerate(ordered):
        nodes = entry["_node_rows"]
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        elements = entry["_element_rows"]
        axes[row_index][0].scatter(
            [float(row["x_um"]) for row in nodes],
            [float(row["y_nm"]) for row in nodes],
            c=[float(row["potential_v"]) for row in nodes],
            cmap=cmaps[0],
            norm=norms[0],
            s=4,
            linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes],
            [float(row["y_nm"]) for row in channel_nodes],
            c=[
                math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
                for row in channel_nodes
            ],
            cmap=cmaps[1],
            norm=norms[1],
            s=5,
            linewidths=0,
        )
        axes[row_index][2].scatter(
            [float(row["centroid_x_um"]) for row in elements],
            [float(row["centroid_y_nm"]) for row in elements],
            c=[
                math.log10(
                    max(
                        float(row["electron_current_density_magnitude_a_per_cm2"]),
                        1.0e-300,
                    )
                )
                for row in elements
            ],
            cmap=cmaps[2],
            norm=norms[2],
            s=5,
            linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            line_color = "white" if column != 1 else "#555555"
            axis.axhline(30.0, color=line_color, linewidth=0.5)
            axis.axhline(54.0, color=line_color, linewidth=0.5)
            axis.set_ylabel(f"VBG={float(entry['vbg_v']):+.1f} V\ny (nm)")
        if row_index == len(ordered) - 1:
            for axis in axes[row_index]:
                axis.set_xlabel("x (um)")
    titles = ["Potential (V)", "log10 electron density (cm^-3)", "log10 |J| (A/cm^2)"]
    for column, title in enumerate(titles):
        axes[0][column].set_title(title)
        figure.colorbar(
            ScalarMappable(norm=norms[column], cmap=cmaps[column]),
            ax=axes[:, column],
            fraction=0.025,
            pad=0.02,
        )
    figure.suptitle(
        "T03-P1-BIAS states at VTG=0.3 V (vertical display scale expanded)",
        fontsize=12,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any],
    contract: dict[str, Any],
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    solver_log: dict[str, Any],
    reference: dict[str, Any],
    figure_hashes: tuple[str | None, str | None],
    caught_error: Exception | None,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    values = [float(value) for value in config["sensitivity"]["values_v"]]
    grid = t02_c.primary_grid(config)
    checks: dict[str, dict[str, Any]] = {}

    add_check(
        checks,
        "contract_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"contract={contract.get('contract_status')} simulation={contract.get('simulation_status')}",
    )
    records = [
        record
        for run in solver_log.get("runs", [])
        for record in run.get("solver_records", [])
    ]
    solve_counts = [
        len(run.get("solver_records", [])) for run in solver_log.get("runs", [])
    ]
    add_check(
        checks,
        "all_configured_dc_solves_converged",
        caught_error is None
        and len(records) == int(acceptance["required_total_dc_solve_count"])
        and solve_counts
        == config["resource_budget"]["required_dc_solve_counts_by_secondary_bias"]
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors"),
        f"records={len(records)} solve_counts={solve_counts} error={caught_error!r}",
    )

    topology_valid = len(summaries) == 5 and all(
        summary["regions"] == sorted(acceptance["required_regions"])
        and summary["contacts"] == sorted(acceptance["required_contacts"])
        and summary["interfaces"] == sorted(acceptance["required_interfaces"])
        and summary["forward_reported_point_count"] == len(grid)
        and summary["reverse_reported_point_count"] == 0
        and summary["state_count"] == 1
        for summary in summaries
    )
    topology_counts = [
        (
            int(summary["node_count_with_interface_duplicates"]),
            int(summary["element_count"]),
        )
        for summary in summaries
    ]
    add_check(
        checks,
        "five_fresh_topologies_are_identical_and_valid",
        topology_valid and len(set(topology_counts)) == 1,
        f"topologies={topology_counts}",
    )

    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_bias(rows, value)]
        == grid
        for value in values
    )
    add_check(
        checks,
        "exact_five_family_curve_grid_completed",
        len(rows) == int(acceptance["required_forward_reported_point_count"])
        and grids_valid
        and all(row["stage_id"] == STAGE_ID for row in rows),
        f"rows={len(rows)} grids={grids_valid}",
    )

    maximum_imbalance = max(
        (float(row["relative_current_imbalance"]) for row in rows), default=math.inf
    )
    direction_valid = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and row["converged"] is True
        for row in rows
    )
    add_check(
        checks,
        "finite_directional_and_conserved_terminal_current",
        direction_valid
        and maximum_imbalance
        <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"direction={direction_valid} max_imbalance={maximum_imbalance:.6e}",
    )

    primary_monotonic = True
    secondary_ordering = True
    for value in values:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in curve_for_bias(rows, value)
        ]
        primary_monotonic = primary_monotonic and all(
            higher > lower for lower, higher in zip(currents, currents[1:])
        )
    for primary_v in grid:
        currents = [
            abs(
                float(
                    next(
                        row
                        for row in curve_for_bias(rows, value)
                        if same_value(float(row["primary_gate_v"]), primary_v)
                    )["drain_current_a_per_cm"]
                )
            )
            for value in values
        ]
        secondary_ordering = secondary_ordering and all(
            higher > lower for lower, higher in zip(currents, currents[1:])
        )
    add_check(
        checks,
        "primary_and_secondary_current_ordering",
        primary_monotonic and secondary_ordering,
        f"primary={primary_monotonic} secondary={secondary_ordering}",
    )

    zero_current = max(
        (
            float(
                summary["zero_equilibrium"][
                    "maximum_absolute_terminal_current_a_per_cm"
                ]
            )
            for summary in summaries
        ),
        default=math.inf,
    )
    zero_potential = max(
        (
            float(summary["zero_equilibrium"]["maximum_absolute_potential_v"])
            for summary in summaries
        ),
        default=math.inf,
    )
    add_check(
        checks,
        "fresh_zero_equilibria_are_current_free",
        zero_current
        <= float(acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"])
        and zero_potential
        <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"current={zero_current:.6e} potential={zero_potential:.6e}",
    )

    metrics_valid = len(metrics) == 5 and all(
        math.isfinite(float(row["vth_proxy_v"]))
        and float(row["vth_bracket_lower_primary_gate_v"])
        < float(row["vth_bracket_upper_primary_gate_v"])
        and math.isfinite(float(row["gm_proxy_s_per_cm"]))
        and float(row["gm_proxy_s_per_cm"]) > 0.0
        for row in metrics
    )
    vth: list[float] = []
    delta_vth: list[float] = []
    gm_proxy: list[float] = []
    slope = math.nan
    r_squared = math.nan
    if metrics_valid:
        try:
            vth = [float(metric_for(metrics, value)["vth_proxy_v"]) for value in values]
            delta_vth = [
                float(metric_for(metrics, value)["delta_vth_proxy_v"])
                for value in values
            ]
            gm_proxy = [
                float(metric_for(metrics, value)["gm_proxy_s_per_cm"])
                for value in values
            ]
            slope = float(metrics[0]["coupling_slope_v_per_v"])
            r_squared = float(metrics[0]["coupling_fit_r_squared"])
        except (KeyError, StopIteration, TypeError, ValueError):
            metrics_valid = False
    add_check(
        checks,
        "vth_delta_gm_and_coupling_proxies_are_valid",
        metrics_valid
        and all(higher < lower for lower, higher in zip(vth, vth[1:]))
        and all(higher < lower for lower, higher in zip(delta_vth, delta_vth[1:]))
        and slope < 0.0
        and float(acceptance["minimum_absolute_coupling_slope_v_per_v"])
        <= abs(slope)
        <= float(acceptance["maximum_absolute_coupling_slope_v_per_v"])
        and r_squared >= float(acceptance["minimum_coupling_fit_r_squared"]),
        f"VTH={vth} delta={delta_vth} slope={slope:.6f} R2={r_squared:.6f}",
    )

    add_check(
        checks,
        "t02_c_zero_secondary_curve_reproduced",
        int(reference.get("point_count", -1)) == 31
        and float(reference.get("maximum_current_relative_difference", math.inf))
        <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and float(reference.get("maximum_center_potential_difference_v", math.inf))
        <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and float(reference.get("maximum_center_density_relative_difference", math.inf))
        <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"]),
        json.dumps(reference, sort_keys=True),
    )
    add_check(
        checks,
        "t02_c_zero_secondary_extraction_reproduced",
        float(reference.get("vth_difference_v", math.inf))
        <= float(acceptance["maximum_t02_c_reference_vth_difference_v"])
        and float(reference.get("gm_relative_difference", math.inf))
        <= float(acceptance["maximum_t02_c_reference_gm_relative_difference"]),
        f"VTH={reference.get('vth_difference_v')} gm={reference.get('gm_relative_difference')}",
    )

    ordered_states = sorted(state_entries, key=lambda entry: float(entry["vbg_v"]))
    state_currents = [
        float(entry["absolute_drain_current_a_per_cm"]) for entry in ordered_states
    ]
    state_potential = [
        float(entry["center_channel_potential_v"]) for entry in ordered_states
    ]
    state_density = [
        float(entry["center_channel_electron_density_cm3"]) for entry in ordered_states
    ]
    states_valid = (
        [entry["state_id"] for entry in state_entries]
        == acceptance["required_state_ids"]
        and len(state_entries) == int(acceptance["required_state_count"])
        and sum(len(entry["vtk_files"]) for entry in state_entries)
        == int(acceptance["required_vtk_file_count"])
        and all(higher > lower for lower, higher in zip(state_currents, state_currents[1:]))
        and all(higher > lower for lower, higher in zip(state_potential, state_potential[1:]))
        and all(higher > lower for lower, higher in zip(state_density, state_density[1:]))
    )
    add_check(
        checks,
        "five_complete_common_bias_states_written_and_ordered",
        states_valid,
        f"states={[entry['state_id'] for entry in state_entries]} I={state_currents}",
    )

    add_check(
        checks,
        "two_report_figures_written",
        all(value is not None for value in figure_hashes),
        f"sensitivity={figure_hashes[0]} states={figure_hashes[1]}",
    )
    add_check(
        checks,
        "laptop_wall_time_budget_met",
        float(solver_log.get("wall_seconds", math.inf))
        <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"wall_seconds={solver_log.get('wall_seconds')} budget={config['resource_budget']['maximum_wall_seconds']}",
    )
    prohibited = " ".join(config["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks,
        "evidence_boundary_remains_bias_only_partial_p1",
        "complete P1" in prohibited
        and "physical top-to-bottom capacitance ratio" in prohibited
        and "complete T03" in prohibited,
        config["evidence_boundary"]["allowed_claim"],
    )

    failures = [name for name, item in checks.items() if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "summary_metrics": {
            "dc_solve_count": len(records),
            "reported_point_count": len(rows),
            "state_count": len(state_entries),
            "maximum_relative_terminal_current_imbalance": maximum_imbalance,
            "fixed_secondary_gate_values_v": values,
            "vth_proxy_v": vth,
            "delta_vth_proxy_v": delta_vth,
            "gm_proxy_s_per_cm": gm_proxy,
            "coupling_slope_v_per_v": slope,
            "coupling_fit_r_squared": r_squared,
        },
    }


def main() -> int:
    config = load_json(CONFIG_PATH)
    dependency = config["dependencies"]
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P1-BIAS input contract is not PASS")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("T03-P1-BIAS contract report does not match current config")

    baseline_path = ROOT / dependency["t01_baseline_config"]
    mesh_path = ROOT / dependency["t01_mesh_config"]
    t02_a_path = ROOT / dependency["t02_a_config"]
    t02_c_report_path = ROOT / dependency["t02_c_report"]
    baseline = load_json(baseline_path)
    mesh = load_json(mesh_path)
    t02_a_config = load_json(t02_a_path)
    t02_c_report = load_json(t02_c_report_path)
    if t02_c_report.get("status") != dependency["required_t02_c_status"]:
        raise RuntimeError("T02-C dependency is not PASS")

    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    curve_path = ROOT / outputs["curve_csv"]
    metric_path = ROOT / outputs["metric_csv"]
    reference_path = ROOT / outputs["reference_comparison_csv"]
    state_summary_path = ROOT / outputs["state_summary_csv"]
    sensitivity_figure_path = ROOT / outputs["sensitivity_figure_png"]
    state_figure_path = ROOT / outputs["state_figure_png"]
    report_path = ROOT / outputs["report"]

    input_paths = {
        "t03_p1_config": CONFIG_PATH,
        "t03_p1_contract_report": contract_path,
        **{
            name: ROOT / dependency[name]
            for name in (
                "project_config",
                "experiments_config",
                "s00_report",
                "t01_baseline_config",
                "t01_mesh_config",
                "t02_a_config",
                "t02_a_report",
                "t02_c_config",
                "t02_c_contract_report",
                "t02_c_report",
                "t02_c_check_report",
                "t03_p4_config",
                "t03_p4_report",
                "t03_p4_check_report",
            )
        },
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in input_paths.items()
        },
        "t03_p1_contract": config,
        "t01_baseline": baseline,
        "t01_mesh_source": mesh,
        "t02_a_config": t02_a_config,
    }
    core.write_json(snapshot_path, snapshot)

    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t03-p1-bias-sensitivity",
        "validation_command": "make t03-p1-bias-sensitivity-check",
        "runs": [],
        "errors": [],
    }
    rows: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    original_stage_id = t02_c.STAGE_ID
    t02_c.STAGE_ID = STAGE_ID
    family = config["bias_protocol"]["families"][0]
    try:
        for secondary_v in [
            float(value) for value in family["fixed_secondary_values_v"]
        ]:
            forward, reverse, states, summary, records = t02_c.run_family(
                baseline,
                mesh,
                t02_a_config,
                config,
                family,
                secondary_v,
                run_dir,
            )
            if reverse:
                raise RuntimeError("T03-P1-BIAS unexpectedly produced a reverse path")
            rows.extend(forward)
            state_entries.extend(states)
            summaries.append(summary)
            solver_log["runs"].append({
                "family_id": "top_primary",
                "fixed_secondary_gate_v": secondary_v,
                "status": "PASS",
                "summary": summary,
                "solver_records": records,
            })
            core.write_json(solver_log_path, solver_log)
            print(
                f"T03_P1_BIAS_FAMILY_PASS secondary={secondary_v:+.1f} V "
                f"points={len(forward)} solves={len(records)}"
            )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        t02_c.STAGE_ID = original_stage_id

    order = {
        state_id: index
        for index, state_id in enumerate(config["acceptance"]["required_state_ids"])
    }
    state_entries.sort(key=lambda entry: order.get(str(entry["state_id"]), 999))
    metrics: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    reference_summary: dict[str, Any] = {}
    sensitivity_hash: str | None = None
    state_hash: str | None = None
    if caught_error is None:
        try:
            metrics = t02_c.build_metrics(baseline, config, rows)
            comparisons, reference_summary = build_reference_comparison(
                rows, metrics, t02_c_report
            )
            sensitivity_hash = render_sensitivity_figure(
                config, rows, metrics, sensitivity_figure_path
            )
            state_hash = render_state_figure(state_entries, state_figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(curve_path, rows, t02_c.FAMILY_FIELDNAMES)
    core.write_csv(metric_path, metrics, t02_c.METRIC_FIELDNAMES)
    core.write_csv(reference_path, comparisons, REFERENCE_FIELDNAMES)
    core.write_csv(
        state_summary_path,
        [
            {field: entry[field] for field in t02_c.STATE_SUMMARY_FIELDNAMES}
            for entry in state_entries
        ],
        t02_c.STATE_SUMMARY_FIELDNAMES,
    )
    manifest_entries = [
        {key: value for key, value in entry.items() if not key.startswith("_")}
        for entry in state_entries
    ]
    core.write_json(
        state_manifest_path,
        {
            "case_id": config["case_id"],
            "stage": config["stage"],
            "entry_count": len(manifest_entries),
            "entries": manifest_entries,
        },
    )
    solver_log["wall_seconds"] = time.perf_counter() - wall_start
    core.write_json(solver_log_path, solver_log)

    assessment = assess(
        config,
        contract,
        rows,
        metrics,
        summaries,
        state_entries,
        solver_log,
        reference_summary,
        (sensitivity_hash, state_hash),
        caught_error,
    )
    figures = []
    if sensitivity_hash is not None:
        figures.append({
            "path": str(sensitivity_figure_path.relative_to(ROOT)),
            "sha256": sensitivity_hash,
        })
    if state_hash is not None:
        figures.append({
            "path": str(state_figure_path.relative_to(ROOT)),
            "sha256": state_hash,
        })
    artifact_paths = {
        "config_snapshot": snapshot_path,
        "solver_log": solver_log_path,
        "state_manifest": state_manifest_path,
        "curve_csv": curve_path,
        "metric_csv": metric_path,
        "reference_comparison_csv": reference_path,
        "state_summary_csv": state_summary_path,
    }
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if assessment["status"] == "PASS" else "E0",
        "model_scope": config["scope"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "capacitance_ratio_control": config["capacitance_ratio_control"],
        "family_summaries": summaries,
        "family_points": rows,
        "coupling_metrics": metrics,
        "t02_c_reference_reproduction": reference_summary,
        "state_outputs": manifest_entries,
        "figures": figures,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": assessment["summary_metrics"],
        "t03_p1_bias_completion": {
            "status": assessment["status"],
            "p1_bias_five_point_substage_complete": assessment["status"] == "PASS",
            "complete_p1_bias_and_capacitance_group": False,
            "capacitance_ratio_substage_permitted_next": assessment["status"] == "PASS",
            "complete_t03_five_group_sensitivity": False,
            "experimental_calibration_permitted": False,
            "physical_capacitance_ratio_claim_permitted": False,
            "compact_model_calibrated": False,
        },
        "limitations": [
            "All VTH, Delta VTH, gm, coupling, current, potential, and density values are numerical proxies from the frozen E2 teaching model.",
            "Only fixed bottom-gate bias changes; the symmetric Ctop/Cbottom input proxy remains 1 and is not scanned or physically extracted.",
            "No experiment calibration, physical capacitance ratio, physical Ion, traps, contact nonideality, temperature dependence, compact model, circuit, layout, or HZO evidence is established.",
            "Passing this run completes only T03-P1-BIAS, not complete P1 or complete T03.",
        ],
        "artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in artifact_paths.items()
        },
        "outputs": {
            key: value for key, value in outputs.items() if key != "check_report"
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T03_P1_BIAS_SENSITIVITY_{report['status']} points={len(rows)} "
        f"dc_solves={assessment['summary_metrics']['dc_solve_count']} "
        f"states={len(state_entries)} report={report_path}"
    )
    for failure in assessment["failures"]:
        print(
            f"T03_P1_BIAS_SENSITIVITY_ERROR {failure}: "
            f"{assessment['checks'][failure]['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
