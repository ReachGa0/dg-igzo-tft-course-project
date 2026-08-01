#!/usr/bin/env python3
"""Run the T03-P2-DIT-FORMAL bottom-interface transfer sensitivity."""

from __future__ import annotations

import copy
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
import run_t03_p2_dit_equation_smoke as dit_smoke  # noqa: E402


core = t02_c.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_dit_formal.json"
STAGE_ID = "T03_P2_DIT_FORMAL"
ELEMENTARY_CHARGE_C = 1.602176634e-19

CURVE_FIELDNAMES = ["dit_cm2_ev", "is_zero_control", *t02_c.FAMILY_FIELDNAMES]
METRIC_FIELDNAMES = [
    "dit_cm2_ev", "is_zero_control", "interface_trap_capacitance_f_per_cm2",
    "constant_current_criterion_terminal_a", "constant_current_criterion_a_per_cm",
    "vth_proxy_v", "delta_vth_proxy_v", "vth_bracket_lower_primary_gate_v",
    "vth_bracket_upper_primary_gate_v", "vth_bracket_lower_current_a_per_cm",
    "vth_bracket_upper_current_a_per_cm", "gm_evaluation_primary_gate_v",
    "gm_proxy_s_per_cm", "gm_proxy_terminal_s", "maximum_sampled_gm_s_per_cm",
    "maximum_sampled_gm_primary_gate_v", "ss_window_lower_current_a_per_cm",
    "ss_window_upper_current_a_per_cm", "ss_fit_sample_count", "ss_fit_slope_v_per_dec",
    "ss_fit_intercept_v", "ss_fit_r_squared", "ss_proxy_mv_per_dec",
    "ioff_evaluation_top_gate_v", "ioff_proxy_a_per_cm", "ioff_proxy_terminal_a",
    "parameter_claim_status",
]
REFERENCE_FIELDNAMES = [
    "primary_gate_v", "formal_abs_drain_current_a_per_cm",
    "t02_c_abs_drain_current_a_per_cm", "current_relative_difference",
    "formal_center_channel_potential_v", "t02_c_center_channel_potential_v",
    "center_channel_potential_difference_v", "formal_center_channel_electron_density_cm3",
    "t02_c_center_channel_electron_density_cm3", "center_density_relative_difference",
]
STATE_SUMMARY_FIELDNAMES = ["dit_cm2_ev", "is_zero_control", *t02_c.STATE_SUMMARY_FIELDNAMES]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float, *, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(abs(float(left)), abs(float(right)), 1e-300)


def add_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def curve_for_dit(rows: list[dict[str, Any]], dit_cm2_ev: float) -> list[dict[str, Any]]:
    return sorted(
        [row for row in rows if same_value(float(row["dit_cm2_ev"]), dit_cm2_ev)],
        key=lambda row: float(row["primary_gate_v"]),
    )


def metric_for(metrics: list[dict[str, Any]], dit_cm2_ev: float) -> dict[str, Any]:
    return next(row for row in metrics if same_value(float(row["dit_cm2_ev"]), dit_cm2_ev))


def voltage_at_current(curve: list[dict[str, Any]], target_current: float) -> float:
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    for voltage, current in zip(voltages, currents, strict=True):
        if math.isclose(current, target_current, rel_tol=1e-12, abs_tol=0.0):
            return voltage
    index = next(
        index
        for index in range(len(currents) - 1)
        if currents[index] < target_current < currents[index + 1]
    )
    lower_log = math.log10(currents[index])
    upper_log = math.log10(currents[index + 1])
    target_log = math.log10(target_current)
    return voltages[index] + (
        (target_log - lower_log)
        * (voltages[index + 1] - voltages[index])
        / (upper_log - lower_log)
    )


def extract_metric(
    baseline: dict[str, Any], config: dict[str, Any], curve: list[dict[str, Any]], dit_cm2_ev: float
) -> dict[str, Any]:
    base = t02_c.threshold_and_gm(baseline, config, curve)
    ss_method = config["extraction_methods"]["ss_proxy"]
    lower = float(ss_method["lower_current_a_per_cm"])
    upper = float(ss_method["upper_current_a_per_cm"])
    samples: dict[float, float] = {
        round(math.log10(lower), 14): voltage_at_current(curve, lower),
        round(math.log10(upper), 14): voltage_at_current(curve, upper),
    }
    for row in curve:
        current = abs(float(row["drain_current_a_per_cm"]))
        if lower < current < upper:
            samples[round(math.log10(current), 14)] = float(row["primary_gate_v"])
    log_currents = sorted(samples)
    voltages = [samples[value] for value in log_currents]
    slope, intercept, r_squared = t02_c.t01_extract.linear_regression(log_currents, voltages)
    if len(log_currents) < int(ss_method["minimum_augmented_sample_count"]):
        raise RuntimeError(f"D_it={dit_cm2_ev} has only {len(log_currents)} SS samples")
    if not math.isfinite(slope) or slope <= 0.0:
        raise RuntimeError(f"D_it={dit_cm2_ev} has invalid SS slope {slope}")

    ioff_v = float(config["extraction_methods"]["ioff_proxy"]["evaluation_top_gate_v"])
    ioff_row = next(row for row in curve if same_value(float(row["primary_gate_v"]), ioff_v))
    ioff = abs(float(ioff_row["drain_current_a_per_cm"]))
    width_cm = float(baseline["device"]["width_cm"])
    return {
        "dit_cm2_ev": dit_cm2_ev,
        "is_zero_control": same_value(dit_cm2_ev, 0.0),
        "interface_trap_capacitance_f_per_cm2": ELEMENTARY_CHARGE_C * dit_cm2_ev,
        **base,
        "delta_vth_proxy_v": math.nan,
        "ss_window_lower_current_a_per_cm": lower,
        "ss_window_upper_current_a_per_cm": upper,
        "ss_fit_sample_count": len(log_currents),
        "ss_fit_slope_v_per_dec": slope,
        "ss_fit_intercept_v": intercept,
        "ss_fit_r_squared": r_squared,
        "ss_proxy_mv_per_dec": 1000.0 * slope,
        "ioff_evaluation_top_gate_v": ioff_v,
        "ioff_proxy_a_per_cm": ioff,
        "ioff_proxy_terminal_a": ioff * width_cm,
        "parameter_claim_status": "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
    }


def build_metrics(
    baseline: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    values = [float(value) for value in config["sensitivity"]["execution_values_cm2_ev"]]
    metrics = [extract_metric(baseline, config, curve_for_dit(rows, value), value) for value in values]
    reference_vth = float(metric_for(metrics, 0.0)["vth_proxy_v"])
    for metric in metrics:
        metric["delta_vth_proxy_v"] = float(metric["vth_proxy_v"]) - reference_vth
    return metrics


def build_reference_comparison(
    rows: list[dict[str, Any]], metrics: list[dict[str, Any]], t02_report: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, float | int]]:
    current_curve = curve_for_dit(rows, 0.0)
    reference_curve = sorted(
        [
            row for row in t02_report["family_points"]
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
            "formal_abs_drain_current_a_per_cm": current,
            "t02_c_abs_drain_current_a_per_cm": reference_current,
            "current_relative_difference": relative_difference(current, reference_current),
            "formal_center_channel_potential_v": float(row["center_channel_potential_v"]),
            "t02_c_center_channel_potential_v": float(reference["center_channel_potential_v"]),
            "center_channel_potential_difference_v": abs(
                float(row["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
            "formal_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": reference_density,
            "center_density_relative_difference": relative_difference(density, reference_density),
        })
    current_metric = metric_for(metrics, 0.0)
    reference_metric = next(
        row for row in t02_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    return comparisons, {
        "point_count": len(comparisons),
        "maximum_current_relative_difference": max(float(row["current_relative_difference"]) for row in comparisons),
        "maximum_center_potential_difference_v": max(float(row["center_channel_potential_difference_v"]) for row in comparisons),
        "maximum_center_density_relative_difference": max(float(row["center_density_relative_difference"]) for row in comparisons),
        "vth_difference_v": abs(float(current_metric["vth_proxy_v"]) - float(reference_metric["vth_proxy_v"])),
        "gm_relative_difference": relative_difference(current_metric["gm_proxy_s_per_cm"], reference_metric["gm_proxy_s_per_cm"]),
    }


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))


def render_sensitivity_figure(
    config: dict[str, Any], rows: list[dict[str, Any]], metrics: list[dict[str, Any]], path: Path
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    values = [float(value) for value in config["sensitivity"]["execution_values_cm2_ev"]]
    scaled = [value / 1e12 for value in values]
    colors = ["#555b63", "#287d59", "#c45d25", "#a33a3a"]
    figure, axes = plt.subplots(2, 3, figsize=(13.2, 7.8), constrained_layout=True)
    for value, color in zip(values, colors, strict=True):
        curve = curve_for_dit(rows, value)
        label = "zero control" if same_value(value, 0.0) else f"{value / 1e12:.3g}e12"
        axes[0][0].semilogy(
            [float(row["primary_gate_v"]) for row in curve],
            [abs(float(row["drain_current_a_per_cm"])) for row in curve],
            color=color, linewidth=1.7, label=label,
        )
    axes[0][0].set_title("Top-primary transfer families")
    axes[0][0].set_xlabel("Top-gate voltage (V)")
    axes[0][0].set_ylabel("Absolute drain current per width (A/cm)")
    axes[0][0].legend(fontsize=7, title="D_it (cm^-2 eV^-1)", title_fontsize=7)

    vth = [float(metric_for(metrics, value)["vth_proxy_v"]) for value in values]
    ss = [float(metric_for(metrics, value)["ss_proxy_mv_per_dec"]) for value in values]
    ioff = [float(metric_for(metrics, value)["ioff_proxy_a_per_cm"]) for value in values]
    gm = [float(metric_for(metrics, value)["gm_proxy_s_per_cm"]) for value in values]
    axes[0][1].plot(scaled, vth, "o-", color="#2563a6", linewidth=1.8)
    axes[0][1].set_title("Constant-current VTH proxy")
    axes[0][1].set_ylabel("VTH proxy (V)")
    axes[0][2].plot(scaled, ss, "o-", color="#287d59", linewidth=1.8)
    axes[0][2].set_title("Fixed-current-window SS proxy")
    axes[0][2].set_ylabel("SS proxy (mV/dec)")
    axes[1][0].semilogy(scaled, ioff, "o-", color="#a33a3a", linewidth=1.8)
    axes[1][0].set_title("Low-gate current proxy at VTG=-0.5 V")
    axes[1][0].set_ylabel("Current proxy (A/cm)")
    axes[1][1].plot(scaled, gm, "o-", color="#c45d25", linewidth=1.8)
    axes[1][1].set_title("gm proxy at VTH + 0.2 V")
    axes[1][1].set_ylabel("gm proxy (S/cm)")
    axes[1][1].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axes[1][2].axis("off")
    axes[1][2].text(
        0.03, 0.95,
        "Numerical teaching-model sensitivity\n"
        "Bottom interface only\n"
        "Psi_neutral = 0 V assumption\n"
        "No bulk traps or calibration",
        va="top", ha="left", fontsize=10, linespacing=1.5,
    )
    for axis in (axes[0][1], axes[0][2], axes[1][0], axes[1][1]):
        axis.set_xlabel("D_it (10^12 cm^-2 eV^-1)")
    for axis in axes.flat[:5]:
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle("T03-P2-DIT-FORMAL IGZO interface sensitivity", fontsize=12)
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

    ordered = sorted(state_entries, key=lambda row: float(row["dit_cm2_ev"]))
    potentials = [float(row["potential_v"]) for entry in ordered for row in entry["_node_rows"]]
    log_density = [
        math.log10(max(float(row["electron_density_cm3"]), 1e-300))
        for entry in ordered for row in entry["_node_rows"] if row["region"] == "channel"
    ]
    log_current = [
        math.log10(max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1e-300))
        for entry in ordered for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(log_density), max(log_density)),
        Normalize(min(log_current), max(log_current)),
    ]
    cmaps = ["viridis", "plasma", "magma"]
    figure, axes = plt.subplots(len(ordered), 3, figsize=(11.2, 10.3), constrained_layout=True, squeeze=False)
    for row_index, entry in enumerate(ordered):
        nodes = entry["_node_rows"]
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        elements = entry["_element_rows"]
        axes[row_index][0].scatter(
            [float(row["x_um"]) for row in nodes], [float(row["y_nm"]) for row in nodes],
            c=[float(row["potential_v"]) for row in nodes], cmap=cmaps[0], norm=norms[0], s=4, linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes], [float(row["y_nm"]) for row in channel_nodes],
            c=[math.log10(max(float(row["electron_density_cm3"]), 1e-300)) for row in channel_nodes],
            cmap=cmaps[1], norm=norms[1], s=5, linewidths=0,
        )
        axes[row_index][2].scatter(
            [float(row["centroid_x_um"]) for row in elements], [float(row["centroid_y_nm"]) for row in elements],
            c=[math.log10(max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1e-300)) for row in elements],
            cmap=cmaps[2], norm=norms[2], s=5, linewidths=0,
        )
        label = "0 control" if same_value(entry["dit_cm2_ev"], 0.0) else f"{float(entry['dit_cm2_ev']) / 1e12:.3g}e12"
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            line_color = "white" if column != 1 else "#555555"
            axis.axhline(30.0, color=line_color, linewidth=0.5)
            axis.axhline(54.0, color=line_color, linewidth=0.5)
            axis.set_ylabel(f"D_it={label}\ny (nm)")
        if row_index == len(ordered) - 1:
            for axis in axes[row_index]:
                axis.set_xlabel("x (um)")
    titles = ["Potential (V)", "log10 electron density (cm^-3)", "log10 |J| (A/cm^2)"]
    for column, title in enumerate(titles):
        axes[0][column].set_title(title)
        figure.colorbar(
            ScalarMappable(norm=norms[column], cmap=cmaps[column]),
            ax=axes[:, column], fraction=0.025, pad=0.02,
        )
    figure.suptitle("T03-P2-DIT-FORMAL states at VTG=0.3 V (vertical scale expanded)", fontsize=12)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any], contract: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], summaries: list[dict[str, Any]],
    state_entries: list[dict[str, Any]], solver_log: dict[str, Any],
    reference: dict[str, Any], figure_hashes: tuple[str | None, str | None],
    caught_error: Exception | None,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    values = [float(value) for value in config["sensitivity"]["execution_values_cm2_ev"]]
    checks: dict[str, dict[str, Any]] = {}
    add_check(
        checks, "contract_is_passed_and_current",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and contract.get("config", {}).get("sha256") == core.sha256(CONFIG_PATH),
        f"status={contract.get('contract_status')} simulation={contract.get('simulation_status')}",
    )
    add_check(checks, "runner_completed_without_exception", caught_error is None, repr(caught_error))
    runs = solver_log.get("runs", [])
    records = [record for run in runs for record in run.get("solver_records", [])]
    add_check(
        checks, "four_fresh_devices_and_164_dc_solves_converged",
        [float(run["dit_cm2_ev"]) for run in runs] == values
        and [len(run.get("solver_records", [])) for run in runs] == [41, 41, 41, 41]
        and len(records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors"),
        f"runs={len(runs)} records={len(records)} errors={solver_log.get('errors')}",
    )
    topology_counts = [
        (int(summary["node_count_with_interface_duplicates"]), int(summary["element_count"]))
        for summary in summaries
    ]
    equation_valid = all(
        summary["bottom_interface_equations"] == sorted(acceptance["require_active_bottom_interface_equations"])
        and summary["top_interface_equations"] == sorted(acceptance["require_inactive_top_interface_equations"])
        for summary in summaries
    )
    add_check(
        checks, "identical_topology_and_active_bottom_interface_equation",
        len(summaries) == 4 and len(set(topology_counts)) == 1 and equation_valid
        and all(
            summary["regions"] == sorted(acceptance["required_regions"])
            and summary["contacts"] == sorted(acceptance["required_contacts"])
            and summary["interfaces"] == sorted(acceptance["required_interfaces"])
            for summary in summaries
        ),
        f"topologies={topology_counts} equations={equation_valid}",
    )
    expected_grid = t02_c.primary_grid(config)
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_dit(rows, value)] == expected_grid
        for value in values
    )
    add_check(
        checks, "exact_four_curve_124_point_grid_completed",
        len(rows) == int(acceptance["required_total_reported_point_count"])
        and grids_valid
        and all(row["stage_id"] == STAGE_ID for row in rows),
        f"rows={len(rows)} grids={grids_valid}",
    )
    maximum_imbalance = max((float(row["relative_current_imbalance"]) for row in rows), default=math.inf)
    direction_valid = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and row["converged"] is True
        for row in rows
    )
    add_check(
        checks, "finite_directional_and_conserved_terminal_current",
        direction_valid and maximum_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"direction={direction_valid} max_imbalance={maximum_imbalance:.6e}",
    )
    monotonic = all(
        all(higher > lower for lower, higher in zip(currents, currents[1:]))
        for currents in (
            [abs(float(row["drain_current_a_per_cm"])) for row in curve_for_dit(rows, value)]
            for value in values
        )
    )
    add_check(checks, "each_primary_gate_curve_is_strictly_increasing", monotonic, f"monotonic={monotonic}")
    zero_current = max(
        (float(summary["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"]) for summary in summaries),
        default=math.inf,
    )
    zero_potential = max(
        (float(summary["zero_equilibrium"]["maximum_absolute_potential_v"]) for summary in summaries),
        default=math.inf,
    )
    add_check(
        checks, "fresh_zero_equilibria_are_current_free",
        zero_current <= float(acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"])
        and zero_potential <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"current={zero_current:.6e} potential={zero_potential:.6e}",
    )
    metrics_valid = len(metrics) == 4 and all(
        math.isfinite(float(metric["vth_proxy_v"]))
        and float(metric["vth_bracket_lower_primary_gate_v"]) < float(metric["vth_bracket_upper_primary_gate_v"])
        and math.isfinite(float(metric["gm_proxy_s_per_cm"])) and float(metric["gm_proxy_s_per_cm"]) > 0.0
        and math.isfinite(float(metric["ss_proxy_mv_per_dec"])) and float(metric["ss_proxy_mv_per_dec"]) > 0.0
        and int(metric["ss_fit_sample_count"]) >= int(config["extraction_methods"]["ss_proxy"]["minimum_augmented_sample_count"])
        and float(metric["ss_fit_r_squared"]) >= float(acceptance["minimum_ss_fit_r_squared"])
        and math.isfinite(float(metric["ioff_proxy_a_per_cm"])) and float(metric["ioff_proxy_a_per_cm"]) > 0.0
        for metric in metrics
    )
    add_check(
        checks, "vth_gm_ss_and_ioff_numerical_proxies_are_extractable",
        metrics_valid,
        f"metrics={len(metrics)} ss_R2={[metric.get('ss_fit_r_squared') for metric in metrics]}",
    )
    add_check(
        checks, "zero_dit_curve_and_extraction_reproduce_t02_c",
        int(reference.get("point_count", -1)) == 31
        and float(reference.get("maximum_current_relative_difference", math.inf)) <= float(acceptance["maximum_zero_dit_t02_c_current_relative_difference"])
        and float(reference.get("maximum_center_potential_difference_v", math.inf)) <= float(acceptance["maximum_zero_dit_t02_c_center_potential_difference_v"])
        and float(reference.get("maximum_center_density_relative_difference", math.inf)) <= float(acceptance["maximum_zero_dit_t02_c_center_density_relative_difference"])
        and float(reference.get("vth_difference_v", math.inf)) <= float(acceptance["maximum_zero_dit_t02_c_vth_difference_v"])
        and float(reference.get("gm_relative_difference", math.inf)) <= float(acceptance["maximum_zero_dit_t02_c_gm_relative_difference"]),
        json.dumps(reference, sort_keys=True),
    )
    ordered_states = sorted(state_entries, key=lambda entry: float(entry["dit_cm2_ev"]))
    response = math.inf
    if len(ordered_states) == 4:
        response = relative_difference(
            ordered_states[0]["absolute_drain_current_a_per_cm"],
            ordered_states[-1]["absolute_drain_current_a_per_cm"],
        )
    states_valid = (
        [entry["state_id"] for entry in state_entries] == acceptance["required_state_ids"]
        and len(state_entries) == int(acceptance["required_state_count"])
        and sum(len(entry["vtk_files"]) for entry in state_entries) == int(acceptance["required_vtk_file_count"])
    )
    add_check(
        checks, "four_complete_common_bias_states_show_nonzero_response",
        states_valid and response >= float(acceptance["minimum_max_dit_common_state_current_relative_response"]),
        f"states={[entry.get('state_id') for entry in state_entries]} response={response:.6e}",
    )
    add_check(
        checks, "two_report_figures_written",
        all(value is not None for value in figure_hashes),
        f"sensitivity={figure_hashes[0]} states={figure_hashes[1]}",
    )
    add_check(
        checks, "laptop_wall_time_budget_met",
        float(solver_log.get("wall_seconds", math.inf)) <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"wall={solver_log.get('wall_seconds')} budget={config['resource_budget']['maximum_wall_seconds']}",
    )
    prohibited = " ".join(config["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks, "evidence_boundary_remains_interface_only_partial_p2",
        "numerical proxies" in config["evidence_boundary"]["allowed_claim"]
        and "complete P2" in prohibited and "complete T03" in prohibited,
        config["evidence_boundary"]["allowed_claim"],
    )
    failures = [name for name, item in checks.items() if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "summary_metrics": {
            "device_count": len(runs),
            "dc_solve_count": len(records),
            "reported_point_count": len(rows),
            "state_count": len(state_entries),
            "maximum_relative_terminal_current_imbalance": maximum_imbalance,
            "maximum_dit_common_state_current_relative_response": response,
        },
    }


def main() -> int:
    config = load_json(CONFIG_PATH)
    dep = config["dependencies"]
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P2-DIT-FORMAL input contract is not PASS")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("T03-P2-DIT-FORMAL contract report does not match current config")

    baseline_path = ROOT / dep["t01_baseline_config"]
    mesh_path = ROOT / dep["t01_mesh_config"]
    t02_a_path = ROOT / dep["t02_a_config"]
    t02_report_path = ROOT / dep["t02_c_report"]
    baseline = load_json(baseline_path)
    mesh = load_json(mesh_path)
    t02_a_config = load_json(t02_a_path)
    t02_report = load_json(t02_report_path)
    if t02_report.get("status") != dep["required_t02_c_status"]:
        raise RuntimeError("T02-C dependency is not PASS")

    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    paths = {name: ROOT / value for name, value in outputs.items() if name != "run_directory"}
    input_paths = {
        "t03_p2_dit_formal_config": CONFIG_PATH,
        "t03_p2_dit_formal_contract_report": contract_path,
        **{
            name: ROOT / dep[name]
            for name in (
                "project_config", "experiments_config", "s00_report", "t01_baseline_config",
                "t01_mesh_config", "t02_a_config", "t02_c_config", "t02_c_contract_report",
                "t02_c_report", "t02_c_check_report", "dit_smoke_config",
                "dit_smoke_contract_report", "dit_smoke_report", "dit_smoke_check_report",
                "literature_table",
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
        "formal_contract": config,
        "t01_baseline": baseline,
        "t01_mesh_source": mesh,
        "t02_a_config": t02_a_config,
    }
    core.write_json(paths["config_snapshot"], snapshot)

    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t03-p2-dit-formal",
        "validation_command": "make t03-p2-dit-formal-check",
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
    values = [float(value) for value in config["sensitivity"]["execution_values_cm2_ev"]]
    try:
        for dit_cm2_ev in values:
            run_config = copy.deepcopy(config)
            state = next(
                item for item in config["bias_protocol"]["state_points"]
                if same_value(float(item["dit_cm2_ev"]), dit_cm2_ev)
            )
            run_config["bias_protocol"]["state_points"] = [
                {key: value for key, value in state.items() if key != "dit_cm2_ev"}
            ]
            extension: dict[str, Any] = {}

            def install(device: str, _runtime: dict[str, Any]) -> None:
                dit_smoke.install_interface_models(
                    device,
                    equation_active=True,
                    dit_cm2_ev=dit_cm2_ev,
                    neutral_potential_v=float(config["interface_trap_model"]["neutral_potential_v"]),
                )
                extension["bottom_interface_equations"] = sorted(
                    core.devsim.get_interface_equation_list(
                        device=device, interface="bottom_oxide_channel"
                    )
                )
                extension["top_interface_equations"] = sorted(
                    core.devsim.get_interface_equation_list(
                        device=device, interface="channel_top_oxide"
                    )
                )
                extension["interface_trap_equation_command"] = core.devsim.get_interface_equation_command(
                    device=device,
                    interface="bottom_oxide_channel",
                    name="InterfaceTrapChargeEquation",
                )

            forward, reverse, states, summary, records = t02_c.run_family(
                baseline, mesh, t02_a_config, run_config, family, 0.0, run_dir,
                post_initialize_hook=install,
                device_token=str(state["state_id"]),
            )
            if reverse:
                raise RuntimeError("T03-P2-DIT-FORMAL unexpectedly produced a reverse path")
            control = same_value(dit_cm2_ev, 0.0)
            rows.extend({"dit_cm2_ev": dit_cm2_ev, "is_zero_control": control, **row} for row in forward)
            for entry in states:
                entry["dit_cm2_ev"] = dit_cm2_ev
                entry["is_zero_control"] = control
                state_entries.append(entry)
            summary = {
                "dit_cm2_ev": dit_cm2_ev,
                "is_zero_control": control,
                **summary,
                **extension,
            }
            summaries.append(summary)
            solver_log["runs"].append({
                "dit_cm2_ev": dit_cm2_ev,
                "is_zero_control": control,
                "status": "PASS",
                "summary": summary,
                "solver_records": records,
            })
            core.write_json(paths["solver_log"], solver_log)
            print(
                f"T03_P2_DIT_FORMAL_DEVICE_PASS dit={dit_cm2_ev:.6e} "
                f"points={len(forward)} solves={len(records)}"
            )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        t02_c.STAGE_ID = original_stage_id

    order = {state_id: index for index, state_id in enumerate(config["acceptance"]["required_state_ids"])}
    state_entries.sort(key=lambda entry: order.get(str(entry["state_id"]), 999))
    metrics: list[dict[str, Any]] = []
    comparisons: list[dict[str, Any]] = []
    reference_summary: dict[str, Any] = {}
    sensitivity_hash: str | None = None
    state_hash: str | None = None
    if caught_error is None:
        try:
            metrics = build_metrics(baseline, config, rows)
            comparisons, reference_summary = build_reference_comparison(rows, metrics, t02_report)
            sensitivity_hash = render_sensitivity_figure(config, rows, metrics, paths["sensitivity_figure_png"])
            state_hash = render_state_figure(state_entries, paths["state_figure_png"])
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(paths["curve_csv"], rows, CURVE_FIELDNAMES)
    core.write_csv(paths["metric_csv"], metrics, METRIC_FIELDNAMES)
    core.write_csv(paths["reference_comparison_csv"], comparisons, REFERENCE_FIELDNAMES)
    core.write_csv(
        paths["state_summary_csv"],
        [{field: entry[field] for field in STATE_SUMMARY_FIELDNAMES} for entry in state_entries],
        STATE_SUMMARY_FIELDNAMES,
    )
    manifest_entries = [
        {key: value for key, value in entry.items() if not key.startswith("_")}
        for entry in state_entries
    ]
    core.write_json(
        paths["state_manifest"],
        {"case_id": config["case_id"], "stage": config["stage"], "entry_count": len(manifest_entries), "entries": manifest_entries},
    )
    solver_log["wall_seconds"] = time.perf_counter() - wall_start
    core.write_json(paths["solver_log"], solver_log)

    assessment = assess(
        config, contract, rows, metrics, summaries, state_entries, solver_log,
        reference_summary, (sensitivity_hash, state_hash), caught_error,
    )
    metric_values = {
        key: [float(metric[key]) for metric in metrics]
        for key in ("vth_proxy_v", "delta_vth_proxy_v", "ss_proxy_mv_per_dec", "ioff_proxy_a_per_cm", "gm_proxy_s_per_cm")
    } if metrics else {}
    directional = {
        "completion_gate": False,
        "vth_proxy_strictly_increases_with_dit": bool(metrics) and all(
            float(right["vth_proxy_v"]) > float(left["vth_proxy_v"])
            for left, right in zip(metrics, metrics[1:])
        ),
        "ss_proxy_strictly_increases_with_dit": bool(metrics) and all(
            float(right["ss_proxy_mv_per_dec"]) > float(left["ss_proxy_mv_per_dec"])
            for left, right in zip(metrics, metrics[1:])
        ),
        "ioff_proxy_values_a_per_cm": [float(metric["ioff_proxy_a_per_cm"]) for metric in metrics],
        "interpretation": "Recorded diagnostics are not completion gates; contrary trends remain reportable results.",
    }
    artifact_keys = (
        "config_snapshot", "solver_log", "state_manifest", "curve_csv",
        "metric_csv", "reference_comparison_csv", "state_summary_csv",
    )
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if assessment["status"] == "PASS" else "E0",
        "model_scope": config["scope"],
        "input_snapshot": str(paths["config_snapshot"].relative_to(ROOT)),
        "formal_values_cm2_ev": config["sensitivity"]["formal_values_cm2_ev"],
        "zero_regression_control_cm2_ev": config["sensitivity"]["zero_regression_control_cm2_ev"],
        "family_summaries": summaries,
        "family_points": rows,
        "metrics": metrics,
        "zero_dit_t02_c_reproduction": reference_summary,
        "directional_diagnostics": directional,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {**assessment["summary_metrics"], **metric_values},
        "artifacts": {
            key: {"path": str(paths[key].relative_to(ROOT)), "sha256": core.sha256(paths[key])}
            for key in artifact_keys
        },
        "figures": [
            {"path": str(paths["sensitivity_figure_png"].relative_to(ROOT)), "sha256": sensitivity_hash},
            {"path": str(paths["state_figure_png"].relative_to(ROOT)), "sha256": state_hash},
        ] if sensitivity_hash is not None and state_hash is not None else [],
        "t03_p2_completion": {
            "status": "PARTIAL" if assessment["status"] == "PASS" else "BLOCKED",
            "dit_literature_input_contract_passed": True,
            "dit_interface_equation_smoke_passed": True,
            "formal_three_point_dit_sensitivity_complete": assessment["status"] == "PASS",
            "interface_dit_substage_complete": assessment["status"] == "PASS",
            "bulk_tail_and_deep_traps_complete": False,
            "complete_p2_trap_group": False,
            "complete_t03_five_group_sensitivity": False,
            "bulk_trap_contract_permitted_next": assessment["status"] == "PASS",
            "experimental_calibration_permitted": False,
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(paths["report"], report)
    print(
        f"T03_P2_DIT_FORMAL_{report['status']} devices={len(solver_log['runs'])} "
        f"dc={assessment['summary_metrics']['dc_solve_count']} points={len(rows)} "
        f"wall={solver_log['wall_seconds']:.3f}s report={paths['report']}"
    )
    for failure in report["failures"]:
        print(f"T03_P2_DIT_FORMAL_ERROR {failure}: {report['checks'][failure]['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
