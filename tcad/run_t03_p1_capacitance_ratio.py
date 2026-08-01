#!/usr/bin/env python3
"""Run the frozen T03-P1-CAP-RATIO fixed-total-coupling sensitivity."""

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
import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402


core = t02_c.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p1_capacitance_ratio.json"
STAGE_ID = "T03_P1_CAPACITANCE_RATIO"
RATIO_FIELDS = [
    "capacitance_ratio",
    "top_relative_permittivity",
    "bottom_relative_permittivity",
    "fixed_relative_permittivity_sum",
    "top_coupling_fraction",
]
CURVE_FIELDNAMES = RATIO_FIELDS + t02_c.FAMILY_FIELDNAMES
METRIC_FIELDNAMES = RATIO_FIELDS + [
    "family_id",
    "fixed_bottom_gate_v",
    "constant_current_criterion_terminal_a",
    "constant_current_criterion_a_per_cm",
    "vth_proxy_v",
    "delta_vth_proxy_v",
    "vth_bracket_lower_primary_gate_v",
    "vth_bracket_upper_primary_gate_v",
    "vth_bracket_lower_current_a_per_cm",
    "vth_bracket_upper_current_a_per_cm",
    "gm_evaluation_primary_gate_v",
    "gm_proxy_s_per_cm",
    "gm_proxy_terminal_s",
    "gm_relative_to_symmetric",
    "maximum_sampled_gm_s_per_cm",
    "maximum_sampled_gm_primary_gate_v",
    "parameter_claim_status",
]
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
STATE_SUMMARY_FIELDNAMES = RATIO_FIELDS + t02_c.STATE_SUMMARY_FIELDNAMES


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float, *, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def add_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def point_fields(point: dict[str, Any]) -> dict[str, float]:
    top = float(point["top_relative_permittivity"])
    bottom = float(point["bottom_relative_permittivity"])
    return {
        "capacitance_ratio": float(point["ratio"]),
        "top_relative_permittivity": top,
        "bottom_relative_permittivity": bottom,
        "fixed_relative_permittivity_sum": top + bottom,
        "top_coupling_fraction": float(point["top_coupling_fraction"]),
    }


def curve_for_ratio(rows: list[dict[str, Any]], ratio: float) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["capacitance_ratio"]), ratio)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def metric_for(metrics: list[dict[str, Any]], ratio: float) -> dict[str, Any]:
    return next(row for row in metrics if same_value(float(row["capacitance_ratio"]), ratio))


def build_metrics(
    baseline: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    metrics: list[dict[str, Any]] = []
    for point in config["ratio_encoding"]["points"]:
        ratio = float(point["ratio"])
        extracted = t02_c.threshold_and_gm(baseline, config, curve_for_ratio(rows, ratio))
        metrics.append({
            **point_fields(point),
            "family_id": "top_primary",
            "fixed_bottom_gate_v": float(config["acceptance"]["required_fixed_bottom_gate_v"]),
            **extracted,
        })
    reference = metric_for(metrics, float(config["capacitance_ratio_sensitivity"]["reference_value"]))
    reference_vth = float(reference["vth_proxy_v"])
    reference_gm = float(reference["gm_proxy_s_per_cm"])
    for row in metrics:
        row["delta_vth_proxy_v"] = float(row["vth_proxy_v"]) - reference_vth
        row["gm_relative_to_symmetric"] = float(row["gm_proxy_s_per_cm"]) / reference_gm
        row["parameter_claim_status"] = "NUMERICAL_COUPLING_PROXY_NOT_PHYSICALLY_VALIDATED"
    return metrics


def build_reference_comparison(
    rows: list[dict[str, Any]], metrics: list[dict[str, Any]], t02_report: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, float | int]]:
    current_curve = curve_for_ratio(rows, 1.0)
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
            / max(current, reference_current, 1e-300),
            "t03_center_channel_potential_v": float(row["center_channel_potential_v"]),
            "t02_c_center_channel_potential_v": float(reference["center_channel_potential_v"]),
            "center_channel_potential_difference_v": abs(
                float(row["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
            "t03_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": reference_density,
            "center_density_relative_difference": abs(density - reference_density)
            / max(density, reference_density, 1e-300),
        })
    current_metric = metric_for(metrics, 1.0)
    reference_metric = next(
        row
        for row in t02_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    gm = float(current_metric["gm_proxy_s_per_cm"])
    reference_gm = float(reference_metric["gm_proxy_s_per_cm"])
    return comparisons, {
        "point_count": len(comparisons),
        "maximum_current_relative_difference": max(
            float(row["current_relative_difference"]) for row in comparisons
        ),
        "maximum_center_potential_difference_v": max(
            float(row["center_channel_potential_difference_v"]) for row in comparisons
        ),
        "maximum_center_density_relative_difference": max(
            float(row["center_density_relative_difference"]) for row in comparisons
        ),
        "vth_difference_v": abs(
            float(current_metric["vth_proxy_v"]) - float(reference_metric["vth_proxy_v"])
        ),
        "gm_relative_difference": abs(gm - reference_gm)
        / max(abs(gm), abs(reference_gm), 1e-300),
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

    ratios = [float(value) for value in config["capacitance_ratio_sensitivity"]["values"]]
    colors = ["#2563a6", "#287d59", "#555b63", "#c45d25", "#a33a3a"]
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.0), constrained_layout=True)
    for ratio, color in zip(ratios, colors):
        curve = curve_for_ratio(rows, ratio)
        axes[0][0].semilogy(
            [float(row["primary_gate_v"]) for row in curve],
            [abs(float(row["drain_current_a_per_cm"])) for row in curve],
            color=color,
            linewidth=1.7,
            label=f"Ctop/Cbottom={ratio:g}",
        )
    axes[0][0].set_title("Top-primary transfer families")
    axes[0][0].set_xlabel("Top-gate voltage (V)")
    axes[0][0].set_ylabel("Absolute drain current per width (A/cm)")
    axes[0][0].legend(fontsize=7)

    vth = [float(metric_for(metrics, ratio)["vth_proxy_v"]) for ratio in ratios]
    delta = [float(metric_for(metrics, ratio)["delta_vth_proxy_v"]) for ratio in ratios]
    axes[0][1].plot(ratios, vth, "o-", color="#287d59", linewidth=1.8, label="VTH")
    axes[0][1].plot(ratios, delta, "s--", color="#2563a6", linewidth=1.4, label="Delta VTH")
    axes[0][1].axhline(0.0, color="#72777d", linewidth=0.8)
    axes[0][1].set_title("Threshold numerical proxies")
    axes[0][1].set_xlabel("Effective Ctop/Cbottom input ratio")
    axes[0][1].set_ylabel("Voltage proxy (V)")
    axes[0][1].legend(fontsize=8)

    gm = [float(metric_for(metrics, ratio)["gm_proxy_s_per_cm"]) for ratio in ratios]
    axes[1][0].plot(ratios, gm, "o-", color="#c45d25", linewidth=1.8)
    axes[1][0].set_title("gm proxy at VTH + 0.2 V")
    axes[1][0].set_xlabel("Effective Ctop/Cbottom input ratio")
    axes[1][0].set_ylabel("gm proxy (S/cm)")
    axes[1][0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    top = [float(metric_for(metrics, ratio)["top_relative_permittivity"]) for ratio in ratios]
    bottom = [float(metric_for(metrics, ratio)["bottom_relative_permittivity"]) for ratio in ratios]
    total = [left + right for left, right in zip(top, bottom)]
    axes[1][1].plot(ratios, top, "o-", color="#a33a3a", label="top coefficient")
    axes[1][1].plot(ratios, bottom, "s-", color="#2563a6", label="bottom coefficient")
    axes[1][1].plot(ratios, total, "^-", color="#555b63", label="fixed sum")
    axes[1][1].set_title("Controlled fixed-sum encoding")
    axes[1][1].set_xlabel("Effective Ctop/Cbottom input ratio")
    axes[1][1].set_ylabel("Effective relative-permittivity coefficient")
    axes[1][1].legend(fontsize=8)
    for axis in axes.flat:
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle("T03-P1-CAP-RATIO IGZO fixed-total-coupling sensitivity", fontsize=12)
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

    ordered = sorted(state_entries, key=lambda row: float(row["capacitance_ratio"]))
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
    figure, axes = plt.subplots(5, 3, figsize=(11.2, 12.2), constrained_layout=True)
    for row_index, entry in enumerate(ordered):
        nodes = entry["_node_rows"]
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        elements = entry["_element_rows"]
        axes[row_index][0].scatter(
            [float(row["x_um"]) for row in nodes], [float(row["y_nm"]) for row in nodes],
            c=[float(row["potential_v"]) for row in nodes], cmap=cmaps[0], norm=norms[0],
            s=4, linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes],
            [float(row["y_nm"]) for row in channel_nodes],
            c=[math.log10(max(float(row["electron_density_cm3"]), 1e-300)) for row in channel_nodes],
            cmap=cmaps[1], norm=norms[1], s=5, linewidths=0,
        )
        axes[row_index][2].scatter(
            [float(row["centroid_x_um"]) for row in elements],
            [float(row["centroid_y_nm"]) for row in elements],
            c=[math.log10(max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1e-300)) for row in elements],
            cmap=cmaps[2], norm=norms[2], s=5, linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            axis.axhline(30.0, color="white" if column != 1 else "#555555", linewidth=0.5)
            axis.axhline(54.0, color="white" if column != 1 else "#555555", linewidth=0.5)
            axis.set_ylabel(f"ratio={float(entry['capacitance_ratio']):g}\ny (nm)")
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
    figure.suptitle(
        "T03-P1-CAP-RATIO states at VBG=0 V, VTG=0.3 V (vertical scale expanded)",
        fontsize=12,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any], contract: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], summaries: list[dict[str, Any]],
    state_entries: list[dict[str, Any]], records: list[dict[str, Any]],
    solver_log: dict[str, Any], reference: dict[str, Any],
    figure_hashes: tuple[str | None, str | None], caught_error: Exception | None,
) -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    acceptance = config["acceptance"]
    ratios = [float(value) for value in acceptance["required_ratio_values"]]
    add_check(
        checks, "input_contract_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and not contract.get("failures"),
        f"contract={contract.get('contract_status')} simulation={contract.get('simulation_status')}",
    )
    add_check(checks, "runner_completed_without_exception", caught_error is None, "none" if caught_error is None else repr(caught_error))
    add_check(
        checks, "all_205_dc_solves_converged",
        len(records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in records),
        f"solves={len(records)} expected={acceptance['required_total_dc_solve_count']}",
    )
    topology_counts = [
        (int(summary["node_count_with_interface_duplicates"]), int(summary["element_count"]))
        for summary in summaries
    ]
    topology_valid = all(
        sorted(summary["regions"]) == sorted(acceptance["required_regions"])
        and sorted(summary["contacts"]) == sorted(acceptance["required_contacts"])
        and sorted(summary["interfaces"]) == sorted(acceptance["required_interfaces"])
        and int(summary["state_count"]) == 1
        for summary in summaries
    )
    add_check(
        checks, "five_fresh_topologies_are_identical_and_valid",
        len(summaries) == 5 and topology_valid and len(set(topology_counts)) == 1,
        f"topologies={topology_counts}",
    )
    fixed_sum = float(config["ratio_encoding"]["fixed_relative_permittivity_sum"])
    encoding_valid = True
    for row in rows:
        ratio = float(row["capacitance_ratio"])
        top = float(row["top_relative_permittivity"])
        bottom = float(row["bottom_relative_permittivity"])
        encoding_valid = encoding_valid and math.isclose(
            top / bottom, ratio, rel_tol=float(acceptance["maximum_ratio_reconstruction_relative_error"]), abs_tol=1e-15
        )
        encoding_valid = encoding_valid and math.isclose(
            top + bottom, fixed_sum, rel_tol=float(acceptance["maximum_fixed_sum_relative_error"]), abs_tol=1e-15
        )
    add_check(checks, "ratio_encoding_reconstructs_with_fixed_sum", encoding_valid and len(rows) == 155, f"rows={len(rows)} fixed_sum={fixed_sum}")
    grid = t02_c.primary_grid(config)
    grid_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_ratio(rows, ratio)] == grid
        for ratio in ratios
    )
    add_check(
        checks, "exact_five_family_curve_grid_completed",
        len(rows) == int(acceptance["required_forward_reported_point_count"])
        and grid_valid and all(row["stage_id"] == STAGE_ID for row in rows),
        f"rows={len(rows)} grids={grid_valid}",
    )
    maximum_imbalance = max((float(row["relative_current_imbalance"]) for row in rows), default=math.inf)
    direction_valid = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and row["converged"] is True for row in rows
    )
    add_check(
        checks, "finite_directional_and_conserved_terminal_current",
        direction_valid and maximum_imbalance <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"direction={direction_valid} max_imbalance={maximum_imbalance:.6e}",
    )
    primary_monotonic = all(
        all(higher > lower for lower, higher in zip(currents, currents[1:]))
        for currents in (
            [abs(float(row["drain_current_a_per_cm"])) for row in curve_for_ratio(rows, ratio)]
            for ratio in ratios
        )
    )
    add_check(checks, "all_primary_transfer_curves_strictly_increase", primary_monotonic, f"ratios={ratios}")
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
    metrics_valid = len(metrics) == 5 and all(
        math.isfinite(float(row["vth_proxy_v"]))
        and float(row["vth_bracket_lower_primary_gate_v"]) < float(row["vth_bracket_upper_primary_gate_v"])
        and math.isfinite(float(row["gm_proxy_s_per_cm"]))
        and float(row["gm_proxy_s_per_cm"]) > 0.0 for row in metrics
    )
    vth = [float(metric_for(metrics, ratio)["vth_proxy_v"]) for ratio in ratios] if metrics_valid else []
    gm = [float(metric_for(metrics, ratio)["gm_proxy_s_per_cm"]) for ratio in ratios] if metrics_valid else []
    delta = [float(metric_for(metrics, ratio)["delta_vth_proxy_v"]) for ratio in ratios] if metrics_valid else []
    add_check(
        checks, "vth_delta_and_gm_ratio_trends_are_valid",
        metrics_valid
        and all(higher < lower for lower, higher in zip(vth, vth[1:]))
        and all(higher > lower for lower, higher in zip(gm, gm[1:]))
        and same_value(delta[2], 0.0),
        f"VTH={vth} delta={delta} gm={gm}",
    )
    add_check(
        checks, "t02_c_symmetric_curve_reproduced",
        int(reference.get("point_count", -1)) == 31
        and float(reference.get("maximum_current_relative_difference", math.inf)) <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and float(reference.get("maximum_center_potential_difference_v", math.inf)) <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and float(reference.get("maximum_center_density_relative_difference", math.inf)) <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"]),
        json.dumps(reference, sort_keys=True),
    )
    add_check(
        checks, "t02_c_symmetric_extraction_reproduced",
        float(reference.get("vth_difference_v", math.inf)) <= float(acceptance["maximum_t02_c_reference_vth_difference_v"])
        and float(reference.get("gm_relative_difference", math.inf)) <= float(acceptance["maximum_t02_c_reference_gm_relative_difference"]),
        f"VTH={reference.get('vth_difference_v')} gm={reference.get('gm_relative_difference')}",
    )
    ordered_states = sorted(state_entries, key=lambda entry: float(entry["capacitance_ratio"]))
    state_currents = [float(entry["absolute_drain_current_a_per_cm"]) for entry in ordered_states]
    state_potential = [float(entry["center_channel_potential_v"]) for entry in ordered_states]
    state_density = [float(entry["center_channel_electron_density_cm3"]) for entry in ordered_states]
    states_valid = (
        [entry["state_id"] for entry in state_entries] == acceptance["required_state_ids"]
        and len(state_entries) == int(acceptance["required_state_count"])
        and sum(len(entry["vtk_files"]) for entry in state_entries) == int(acceptance["required_vtk_file_count"])
        and all(higher > lower for lower, higher in zip(state_currents, state_currents[1:]))
        and all(higher > lower for lower, higher in zip(state_potential, state_potential[1:]))
        and all(higher > lower for lower, higher in zip(state_density, state_density[1:]))
    )
    add_check(checks, "five_complete_common_bias_states_written_and_ordered", states_valid, f"states={[entry['state_id'] for entry in state_entries]} I={state_currents}")
    add_check(checks, "two_report_figures_written", all(value is not None for value in figure_hashes), f"sensitivity={figure_hashes[0]} states={figure_hashes[1]}")
    add_check(
        checks, "laptop_wall_time_budget_met",
        float(solver_log.get("wall_seconds", math.inf)) <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"wall_seconds={solver_log.get('wall_seconds')} budget={config['resource_budget']['maximum_wall_seconds']}",
    )
    prohibited = " ".join(config["evidence_boundary"]["prohibited_claims"])
    add_check(
        checks, "evidence_boundary_is_numerical_p1_only",
        "physically extracted" in prohibited and "measured Al2O3" in prohibited and "complete T03" in prohibited,
        config["evidence_boundary"]["allowed_claim"],
    )
    failures = [name for name, item in checks.items() if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "summary_metrics": {
            "dc_solve_count": len(records), "reported_point_count": len(rows),
            "state_count": len(state_entries),
            "maximum_relative_terminal_current_imbalance": maximum_imbalance,
            "capacitance_ratio_values": ratios, "vth_proxy_v": vth,
            "delta_vth_proxy_v": delta, "gm_proxy_s_per_cm": gm,
        },
    }


def main() -> int:
    config = load_json(CONFIG_PATH)
    dependency = config["dependencies"]
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P1-CAP-RATIO input contract is not PASS")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("T03-P1-CAP-RATIO contract report does not match current config")

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
        "t03_p1_cap_ratio_config": CONFIG_PATH,
        "t03_p1_cap_ratio_contract_report": contract_path,
        **{
            name: ROOT / dependency[name]
            for name in (
                "project_config", "experiments_config", "s00_report", "t01_baseline_config",
                "t01_mesh_config", "t02_a_config", "t02_c_config", "t02_c_report",
                "t02_c_check_report", "t03_p4_config", "t03_p4_report",
                "t03_p4_check_report", "t03_p1_bias_config", "t03_p1_bias_report",
                "t03_p1_bias_check_report",
            )
        },
    }
    snapshot = {
        "case_id": config["case_id"], "stage": config["stage"],
        "inputs": {name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)} for name, path in input_paths.items()},
        "t03_p1_cap_ratio_contract": config,
        "t01_baseline": baseline, "t01_mesh_source": mesh, "t02_a_config": t02_a_config,
    }
    core.write_json(snapshot_path, snapshot)
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"], "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t03-p1-cap-ratio-sensitivity",
        "validation_command": "make t03-p1-cap-ratio-sensitivity-check",
        "runs": [], "errors": [],
    }
    rows: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    records_all: list[dict[str, Any]] = []
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    original_stage_id = t02_c.STAGE_ID
    original_voltage_token = t02_c.voltage_token
    t02_c.STAGE_ID = STAGE_ID
    family = config["bias_protocol"]["families"][0]
    try:
        for point in config["ratio_encoding"]["points"]:
            ratio = float(point["ratio"])
            fields = point_fields(point)
            ratio_token = f"ratio_{ratio:.2f}".replace(".", "p")
            t02_c.voltage_token = (
                lambda value, suffix=ratio_token: (
                    f"{original_voltage_token(value)}_{suffix}"
                )
            )
            ratio_baseline = copy.deepcopy(baseline)
            ratio_baseline["materials"]["bottom_oxide"]["relative_permittivity"] = fields["bottom_relative_permittivity"]
            ratio_t02_a = copy.deepcopy(t02_a_config)
            ratio_t02_a["top_stack_contract"]["enabled_mode"]["top_oxide_relative_permittivity"] = fields["top_relative_permittivity"]
            ratio_config = copy.deepcopy(config)
            ratio_config["bias_protocol"]["state_points"] = [
                {key: value for key, value in state.items() if key != "ratio"}
                for state in config["bias_protocol"]["state_points"]
                if same_value(float(state["ratio"]), ratio)
            ]
            forward, reverse, states, summary, records = t02_c.run_family(
                ratio_baseline, mesh, ratio_t02_a, ratio_config, family, 0.0, run_dir
            )
            if reverse:
                raise RuntimeError("T03-P1-CAP-RATIO unexpectedly produced a reverse path")
            for row in forward:
                row.update(fields)
            for state in states:
                state.update(fields)
            summary.update(fields)
            rows.extend(forward)
            state_entries.extend(states)
            summaries.append(summary)
            records_all.extend(records)
            solver_log["runs"].append({
                "capacitance_ratio": ratio, **fields, "status": "PASS",
                "summary": summary, "solver_records": records,
            })
            core.write_json(solver_log_path, solver_log)
            print(f"T03_P1_CAP_RATIO_FAMILY_PASS ratio={ratio:g} points={len(forward)} solves={len(records)}")
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        t02_c.STAGE_ID = original_stage_id
        t02_c.voltage_token = original_voltage_token

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
            comparisons, reference_summary = build_reference_comparison(rows, metrics, t02_c_report)
            sensitivity_hash = render_sensitivity_figure(config, rows, metrics, sensitivity_figure_path)
            state_hash = render_state_figure(state_entries, state_figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(curve_path, rows, CURVE_FIELDNAMES)
    core.write_csv(metric_path, metrics, METRIC_FIELDNAMES)
    core.write_csv(reference_path, comparisons, REFERENCE_FIELDNAMES)
    core.write_csv(
        state_summary_path,
        [{field: entry[field] for field in STATE_SUMMARY_FIELDNAMES} for entry in state_entries],
        STATE_SUMMARY_FIELDNAMES,
    )
    manifest_entries = [
        {key: value for key, value in entry.items() if not key.startswith("_")}
        for entry in state_entries
    ]
    core.write_json(state_manifest_path, {
        "case_id": config["case_id"], "stage": config["stage"],
        "entry_count": len(manifest_entries), "entries": manifest_entries,
    })
    solver_log["wall_seconds"] = time.perf_counter() - wall_start
    core.write_json(solver_log_path, solver_log)
    assessment = assess(
        config, contract, rows, metrics, summaries, state_entries, records_all,
        solver_log, reference_summary, (sensitivity_hash, state_hash), caught_error,
    )
    figures = []
    if sensitivity_hash is not None:
        figures.append({"path": str(sensitivity_figure_path.relative_to(ROOT)), "sha256": sensitivity_hash})
    if state_hash is not None:
        figures.append({"path": str(state_figure_path.relative_to(ROOT)), "sha256": state_hash})
    artifact_paths = {
        "config_snapshot": snapshot_path, "solver_log": solver_log_path,
        "state_manifest": state_manifest_path, "curve_csv": curve_path,
        "metric_csv": metric_path, "reference_comparison_csv": reference_path,
        "state_summary_csv": state_summary_path,
    }
    passed = assessment["status"] == "PASS"
    report = {
        "status": assessment["status"], "case_id": config["case_id"],
        "stage": config["stage"], "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if passed else "E0", "model_scope": config["scope"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "ratio_encoding": config["ratio_encoding"], "p1_p4_variable_ownership": config["p1_p4_variable_ownership"],
        "family_summaries": summaries, "family_points": rows,
        "capacitance_ratio_metrics": metrics,
        "t02_c_symmetric_reference_reproduction": reference_summary,
        "state_outputs": manifest_entries, "figures": figures,
        "checks": assessment["checks"], "failures": assessment["failures"],
        "summary_metrics": assessment["summary_metrics"],
        "t03_p1_completion": {
            "status": assessment["status"],
            "p1_bias_five_point_substage_complete": True,
            "p1_capacitance_ratio_five_point_substage_complete": passed,
            "complete_p1_numerical_group": passed,
            "complete_t03_five_group_sensitivity": False,
            "one_of_p2_p3_p5_permitted_next": passed,
            "experimental_calibration_permitted": False,
            "physical_capacitance_ratio_claim_permitted": False,
            "compact_model_calibrated": False,
        },
        "limitations": [
            "All VTH, Delta VTH, gm, current, potential, and density values are numerical proxies from the frozen E2 teaching model.",
            "The paired dielectric-region values encode a fixed-sum electrostatic allocation ratio and are not measured Al2O3 material properties or a fabricated asymmetric stack.",
            "Passing this run may complete only numerical P1 together with P1-BIAS; P2, P3, P5, complete T03, experiment calibration, compact models, circuits, layouts, and HZO remain incomplete.",
        ],
        "artifacts": {name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)} for name, path in artifact_paths.items()},
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T03_P1_CAP_RATIO_SENSITIVITY_{report['status']} points={len(rows)} "
        f"dc_solves={len(records_all)} states={len(state_entries)} report={report_path}"
    )
    for failure in assessment["failures"]:
        print(f"T03_P1_CAP_RATIO_SENSITIVITY_ERROR {failure}: {assessment['checks'][failure]['detail']}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
