#!/usr/bin/env python3
"""Run the frozen formal T03-P5 V_t-only temperature sensitivity."""

from __future__ import annotations

import copy
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t02_dual_gate_bidirectional as t02_c  # noqa: E402


core = t02_c.core
t02_a = t02_c.t02_a
CONFIG_PATH = ROOT / "config" / "tcad_t03_p5_temperature.json"
STAGE_ID = "T03_P5_TEMPERATURE"

CURVE_FIELDNAMES = [
    "parameter_group_id", "changed_parameter", "temperature_k",
    "thermal_voltage_v", *t02_c.FAMILY_FIELDNAMES,
]
METRIC_FIELDNAMES = [
    "parameter_group_id", "changed_parameter", "temperature_k",
    "thermal_voltage_v", "configured_mobility_cm2_vs",
    "constant_current_criterion_terminal_a",
    "constant_current_criterion_a_per_cm", "vth_proxy_v",
    "delta_vth_proxy_v", "vth_bracket_lower_primary_gate_v",
    "vth_bracket_upper_primary_gate_v",
    "vth_bracket_lower_current_a_per_cm",
    "vth_bracket_upper_current_a_per_cm",
    "gm_evaluation_primary_gate_v", "gm_proxy_s_per_cm",
    "gm_proxy_terminal_s", "maximum_sampled_gm_s_per_cm",
    "maximum_sampled_gm_primary_gate_v",
    "ss_window_lower_current_a_per_cm",
    "ss_window_upper_current_a_per_cm", "ss_fit_sample_count",
    "ss_fit_slope_v_per_dec", "ss_fit_intercept_v", "ss_fit_r_squared",
    "ss_proxy_mv_per_dec", "low_gate_evaluation_top_gate_v",
    "low_gate_current_proxy_a_per_cm", "low_gate_current_proxy_terminal_a",
    "high_gate_evaluation_top_gate_v", "high_gate_current_proxy_a_per_cm",
    "high_gate_current_proxy_terminal_a", "parameter_claim_status",
]
REFERENCE_FIELDNAMES = [
    "primary_gate_v", "p5_300k_abs_drain_current_a_per_cm",
    "t02_c_abs_drain_current_a_per_cm", "current_relative_difference",
    "p5_300k_center_channel_potential_v",
    "t02_c_center_channel_potential_v",
    "center_channel_potential_difference_v",
    "p5_300k_center_channel_electron_density_cm3",
    "t02_c_center_channel_electron_density_cm3",
    "center_density_relative_difference",
]
STATE_SUMMARY_FIELDNAMES = [
    "state_id", "state_label", "parameter_group_id", "temperature_k",
    "thermal_voltage_v", "source_family", "mesh_level", "stage_id",
    "vbg_v", "vtg_v", "vds_v", "absolute_drain_current_a_per_cm",
    "drain_current_terminal_a", "relative_current_imbalance",
    "center_channel_potential_v", "center_channel_electron_density_cm3",
    "node_row_count", "channel_node_count", "channel_element_count",
    "minimum_potential_v", "maximum_potential_v",
    "minimum_electron_density_cm3", "maximum_electron_density_cm3",
    "minimum_cell_current_density_magnitude_a_per_cm2",
    "median_cell_current_density_magnitude_a_per_cm2",
    "maximum_cell_current_density_magnitude_a_per_cm2", "node_csv",
    "element_csv", "vtk_file_count",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(
        abs(float(left)), abs(float(right)), 1.0e-300
    )


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def temperature_token(temperature_k: float) -> str:
    if not float(temperature_k).is_integer():
        raise ValueError("T03-P5 temperature token requires an integer kelvin value")
    return f"{int(temperature_k)}k"


def curve_for_temperature(
    rows: list[dict[str, Any]], temperature_k: float
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if same_value(float(row["temperature_k"]), temperature_k)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def metric_for_temperature(
    metrics: list[dict[str, Any]], temperature_k: float
) -> dict[str, Any]:
    return next(
        row
        for row in metrics
        if same_value(float(row["temperature_k"]), temperature_k)
    )


def voltage_at_current(curve: list[dict[str, Any]], target_current: float) -> float:
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    index = next(
        index
        for index in range(len(currents) - 1)
        if currents[index] < target_current < currents[index + 1]
    )
    lower_log = math.log10(currents[index])
    upper_log = math.log10(currents[index + 1])
    return voltages[index] + (
        (math.log10(target_current) - lower_log)
        * (voltages[index + 1] - voltages[index])
        / (upper_log - lower_log)
    )


def runtime_baseline(
    baseline: dict[str, Any], config: dict[str, Any], temperature_k: float
) -> dict[str, Any]:
    variant = copy.deepcopy(baseline)
    boltzmann = float(config["temperature_model_contract"]["boltzmann_ev_per_k"])
    variant["physics"]["temperature_k"] = temperature_k
    variant["physics"]["thermal_voltage_v"] = boltzmann * temperature_k
    return variant


def runtime_config(config: dict[str, Any], temperature_k: float) -> dict[str, Any]:
    variant = copy.deepcopy(config)
    token = temperature_token(temperature_k)
    variant["bias_protocol"]["state_points"] = [
        {
            "state_id": f"p5_temperature_{token}_on_proxy",
            "label": f"T={temperature_k:g} K on proxy",
            "source_family": "top_primary",
            "vbg_v": float(config["bias_protocol"]["fixed_secondary_gate_v"]),
            "vtg_v": float(config["bias_protocol"]["state_primary_gate_v"]),
        }
    ]
    return variant


def extract_metric(
    baseline: dict[str, Any], config: dict[str, Any], temperature_k: float,
    curve: list[dict[str, Any]],
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
    slope, intercept, r_squared = t02_c.t01_extract.linear_regression(
        log_currents, voltages
    )
    if len(log_currents) < int(ss_method["minimum_augmented_sample_count"]):
        raise RuntimeError(
            f"T={temperature_k:g} K has only {len(log_currents)} SS samples"
        )
    if not math.isfinite(slope) or slope <= 0.0:
        raise RuntimeError(f"T={temperature_k:g} K has invalid SS slope {slope}")

    low_v = float(
        config["extraction_methods"]["low_gate_current_proxy"][
            "evaluation_top_gate_v"
        ]
    )
    high_v = float(
        config["extraction_methods"]["high_gate_current_proxy"][
            "evaluation_top_gate_v"
        ]
    )
    low_current = abs(
        float(
            next(
                row
                for row in curve
                if same_value(float(row["primary_gate_v"]), low_v)
            )["drain_current_a_per_cm"]
        )
    )
    high_current = abs(
        float(
            next(
                row
                for row in curve
                if same_value(float(row["primary_gate_v"]), high_v)
            )["drain_current_a_per_cm"]
        )
    )
    width_cm = float(baseline["device"]["width_cm"])
    thermal_voltage = float(
        config["temperature_model_contract"]["boltzmann_ev_per_k"]
    ) * temperature_k
    return {
        "parameter_group_id": "P5",
        "changed_parameter": "lattice_temperature_k",
        "temperature_k": temperature_k,
        "thermal_voltage_v": thermal_voltage,
        "configured_mobility_cm2_vs": float(
            config["extraction_methods"]["configured_mobility_control"][
                "value_cm2_vs"
            ]
        ),
        **base,
        "delta_vth_proxy_v": math.nan,
        "ss_window_lower_current_a_per_cm": lower,
        "ss_window_upper_current_a_per_cm": upper,
        "ss_fit_sample_count": len(log_currents),
        "ss_fit_slope_v_per_dec": slope,
        "ss_fit_intercept_v": intercept,
        "ss_fit_r_squared": r_squared,
        "ss_proxy_mv_per_dec": 1000.0 * slope,
        "low_gate_evaluation_top_gate_v": low_v,
        "low_gate_current_proxy_a_per_cm": low_current,
        "low_gate_current_proxy_terminal_a": low_current * width_cm,
        "high_gate_evaluation_top_gate_v": high_v,
        "high_gate_current_proxy_a_per_cm": high_current,
        "high_gate_current_proxy_terminal_a": high_current * width_cm,
        "parameter_claim_status": "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
    }


def build_metrics(
    baseline: dict[str, Any], config: dict[str, Any], rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    temperatures = [float(value) for value in config["sensitivity"]["values_k"]]
    metrics = [
        extract_metric(
            baseline, config, temperature_k,
            curve_for_temperature(rows, temperature_k),
        )
        for temperature_k in temperatures
    ]
    reference_vth = float(
        metric_for_temperature(
            metrics, float(config["sensitivity"]["reference_value_k"])
        )["vth_proxy_v"]
    )
    for metric in metrics:
        metric["delta_vth_proxy_v"] = float(metric["vth_proxy_v"]) - reference_vth
    return metrics


def build_reference_comparison(
    config: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], t02_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    reference_temperature = float(config["sensitivity"]["reference_value_k"])
    current_curve = curve_for_temperature(rows, reference_temperature)
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
            "p5_300k_abs_drain_current_a_per_cm": current,
            "t02_c_abs_drain_current_a_per_cm": reference_current,
            "current_relative_difference": relative_difference(
                current, reference_current
            ),
            "p5_300k_center_channel_potential_v": float(
                row["center_channel_potential_v"]
            ),
            "t02_c_center_channel_potential_v": float(
                reference["center_channel_potential_v"]
            ),
            "center_channel_potential_difference_v": abs(
                float(row["center_channel_potential_v"])
                - float(reference["center_channel_potential_v"])
            ),
            "p5_300k_center_channel_electron_density_cm3": density,
            "t02_c_center_channel_electron_density_cm3": reference_density,
            "center_density_relative_difference": relative_difference(
                density, reference_density
            ),
        })
    current_metric = metric_for_temperature(metrics, reference_temperature)
    reference_metric = next(
        row
        for row in t02_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    return comparisons, {
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
        "gm_relative_difference": relative_difference(
            float(current_metric["gm_proxy_s_per_cm"]),
            float(reference_metric["gm_proxy_s_per_cm"]),
        ),
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
    config: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], path: Path,
) -> str:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    temperatures = [float(value) for value in config["sensitivity"]["values_k"]]
    colors = {250.0: "#2563a6", 300.0: "#555b63", 350.0: "#c45d25"}
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 8.0), constrained_layout=True)
    for temperature_k in temperatures:
        curve = curve_for_temperature(rows, temperature_k)
        axes[0][0].semilogy(
            [float(row["primary_gate_v"]) for row in curve],
            [abs(float(row["drain_current_a_per_cm"])) for row in curve],
            color=colors[temperature_k], linewidth=1.8,
            label=f"T={temperature_k:g} K",
        )
    axes[0][0].set_title("Top-gate transfer curves")
    axes[0][0].set_xlabel("Top-gate voltage (V)")
    axes[0][0].set_ylabel("Absolute drain current per width (A/cm)")
    axes[0][0].legend(fontsize=8)

    vth = [float(row["vth_proxy_v"]) for row in metrics]
    ss = [float(row["ss_proxy_mv_per_dec"]) for row in metrics]
    axes[0][1].plot(temperatures, vth, "o-", color="#2563a6", label="VTH")
    ss_axis = axes[0][1].twinx()
    ss_axis.plot(temperatures, ss, "s--", color="#287d59", label="SS")
    axes[0][1].set_title("Extracted numerical proxies")
    axes[0][1].set_xlabel("Temperature (K)")
    axes[0][1].set_ylabel("VTH proxy (V)")
    ss_axis.set_ylabel("SS proxy (mV/dec)")

    gm = [float(row["gm_proxy_s_per_cm"]) for row in metrics]
    high = [float(row["high_gate_current_proxy_a_per_cm"]) for row in metrics]
    axes[1][0].plot(temperatures, gm, "o-", color="#c45d25", label="gm")
    high_axis = axes[1][0].twinx()
    high_axis.plot(temperatures, high, "s--", color="#555b63", label="high-gate I")
    axes[1][0].set_title("High-gate and gm proxies")
    axes[1][0].set_xlabel("Temperature (K)")
    axes[1][0].set_ylabel("gm proxy (S/cm)")
    high_axis.set_ylabel("High-gate current proxy (A/cm)")
    axes[1][0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    high_axis.ticklabel_format(axis="y", style="sci", scilimits=(0, 0))

    thermal = [float(row["thermal_voltage_v"]) for row in metrics]
    low = [float(row["low_gate_current_proxy_a_per_cm"]) for row in metrics]
    axes[1][1].plot(temperatures, thermal, "o-", color="#287d59")
    low_axis = axes[1][1].twinx()
    low_axis.semilogy(temperatures, low, "s--", color="#a33a3a")
    axes[1][1].set_title("Explicit input and low-gate response")
    axes[1][1].set_xlabel("Temperature (K)")
    axes[1][1].set_ylabel("Thermal voltage (V)")
    low_axis.set_ylabel("Low-gate current proxy (A/cm)")
    for axis in axes.flat:
        axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle("T03-P5 IGZO V_t-only numerical temperature sensitivity", fontsize=12)
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

    ordered = sorted(state_entries, key=lambda row: float(row["temperature_k"]))
    potentials = [
        float(row["potential_v"]) for entry in ordered for row in entry["_node_rows"]
    ]
    log_density = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
        for entry in ordered for row in entry["_node_rows"]
        if row["region"] == "channel"
    ]
    log_current = [
        math.log10(
            max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1.0e-300)
        )
        for entry in ordered for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(log_density), max(log_density)),
        Normalize(min(log_current), max(log_current)),
    ]
    cmaps = ["viridis", "plasma", "magma"]
    figure, axes = plt.subplots(3, 3, figsize=(11.2, 8.2), constrained_layout=True)
    for row_index, entry in enumerate(ordered):
        nodes = entry["_node_rows"]
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        elements = entry["_element_rows"]
        axes[row_index][0].scatter(
            [float(row["x_um"]) for row in nodes],
            [float(row["y_nm"]) for row in nodes],
            c=[float(row["potential_v"]) for row in nodes],
            cmap=cmaps[0], norm=norms[0], s=5, linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes],
            [float(row["y_nm"]) for row in channel_nodes],
            c=[
                math.log10(max(float(row["electron_density_cm3"]), 1.0e-300))
                for row in channel_nodes
            ],
            cmap=cmaps[1], norm=norms[1], s=6, linewidths=0,
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
            cmap=cmaps[2], norm=norms[2], s=6, linewidths=0,
        )
        for column in range(3):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            line_color = "white" if column != 1 else "#555555"
            axis.axhline(30.0, color=line_color, linewidth=0.6)
            axis.axhline(54.0, color=line_color, linewidth=0.6)
            axis.set_ylabel(f"T={entry['temperature_k']:g} K\ny (nm)")
            if row_index == 2:
                axis.set_xlabel("x (um)")
    axes[0][0].set_title("Potential (V)")
    axes[0][1].set_title("log10 electron density (cm^-3)")
    axes[0][2].set_title("log10 |J| (A/cm^2)")
    for column, (norm, cmap) in enumerate(zip(norms, cmaps)):
        figure.colorbar(
            ScalarMappable(norm=norm, cmap=cmap), ax=axes[:, column],
            shrink=0.82, pad=0.02,
        )
    figure.suptitle(
        "T03-P5 states at VTG=1 V (vertical display scale expanded)", fontsize=12
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def public_state(entry: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in entry.items() if not key.startswith("_")}


def assess(
    config: dict[str, Any], contract: dict[str, Any], rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]], summaries: list[dict[str, Any]],
    states: list[dict[str, Any]], solver_records: list[dict[str, Any]],
    reference: dict[str, Any], wall_seconds: float,
    figure_hashes: tuple[str | None, str | None], caught_error: Exception | None,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    temperatures = [float(value) for value in acceptance["required_temperature_values_k"]]
    checks: dict[str, dict[str, Any]] = {}
    add_check(
        checks,
        "contract_passed_before_simulation",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"contract={contract.get('contract_status')} simulation={contract.get('simulation_status')}",
    )
    add_check(
        checks,
        "all_configured_dc_solves_converged",
        caught_error is None
        and len(solver_records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in solver_records),
        f"records={len(solver_records)} error={caught_error!r}",
    )
    topology_counts = [
        (
            int(summary["node_count_with_interface_duplicates"]),
            int(summary["element_count"]),
        )
        for summary in summaries
    ]
    topology_valid = (
        [float(summary["temperature_k"]) for summary in summaries] == temperatures
        and len(set(topology_counts)) == 1
        and all(
            summary["regions"] == sorted(acceptance["required_regions"])
            and summary["contacts"] == sorted(acceptance["required_contacts"])
            and summary["interfaces"] == sorted(acceptance["required_interfaces"])
            and int(summary["reported_point_count"]) == 31
            and int(summary["state_count"]) == 1
            for summary in summaries
        )
    )
    add_check(
        checks,
        "three_fresh_temperature_topologies_are_identical_and_valid",
        topology_valid,
        f"topologies={topology_counts}",
    )
    grid = t02_c.primary_grid(config)
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for_temperature(rows, value)]
        == grid
        for value in temperatures
    )
    add_check(
        checks,
        "exact_three_curve_grid_completed",
        len(rows) == int(acceptance["required_total_reported_point_count"])
        and grids_valid
        and all(row["stage_id"] == STAGE_ID for row in rows),
        f"rows={len(rows)} grids={grids_valid}",
    )
    max_imbalance = max(
        (float(row["relative_current_imbalance"]) for row in rows),
        default=math.inf,
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
        and max_imbalance
        <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"direction={direction_valid} max_imbalance={max_imbalance:.6e}",
    )
    maximum_drop = 0.0
    primary_monotonic = True
    for temperature_k in temperatures:
        currents = [
            abs(float(row["drain_current_a_per_cm"]))
            for row in curve_for_temperature(rows, temperature_k)
        ]
        primary_monotonic = primary_monotonic and all(
            higher > lower for lower, higher in zip(currents, currents[1:])
        )
        maximum_drop = max(
            maximum_drop,
            max(
                max(0.0, (lower - higher) / max(lower, higher, 1.0e-300))
                for lower, higher in zip(currents, currents[1:])
            ),
        )
    add_check(
        checks,
        "primary_gate_current_strictly_increases",
        primary_monotonic
        and maximum_drop
        <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"monotonic={primary_monotonic} maximum_drop={maximum_drop:.6e}",
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
        <= float(
            acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"]
        )
        and zero_potential
        <= float(acceptance["maximum_zero_equilibrium_absolute_potential_v"]),
        f"current={zero_current:.6e} potential={zero_potential:.6e}",
    )
    metrics_valid = len(metrics) == 3 and all(
        math.isfinite(float(metric["vth_proxy_v"]))
        and float(metric["vth_bracket_lower_primary_gate_v"])
        < float(metric["vth_bracket_upper_primary_gate_v"])
        and math.isfinite(float(metric["gm_proxy_s_per_cm"]))
        and float(metric["gm_proxy_s_per_cm"]) > 0.0
        and math.isfinite(float(metric["ss_proxy_mv_per_dec"]))
        and float(metric["ss_proxy_mv_per_dec"]) > 0.0
        and int(metric["ss_fit_sample_count"])
        >= int(acceptance["minimum_augmented_ss_sample_count"])
        and float(metric["ss_fit_r_squared"])
        >= float(acceptance["minimum_ss_fit_r_squared"])
        and float(metric["low_gate_current_proxy_a_per_cm"]) > 0.0
        and float(metric["high_gate_current_proxy_a_per_cm"]) > 0.0
        for metric in metrics
    )
    add_check(
        checks,
        "vth_gm_ss_and_sampled_current_proxies_are_valid",
        metrics_valid,
        f"metrics={len(metrics)}",
    )
    endpoint_response = math.nan
    if metrics_valid:
        low_metric = metric_for_temperature(metrics, 250.0)
        high_metric = metric_for_temperature(metrics, 350.0)
        endpoint_response = max(
            relative_difference(low_metric[key], high_metric[key])
            for key in (
                "vth_proxy_v", "gm_proxy_s_per_cm", "ss_proxy_mv_per_dec",
                "low_gate_current_proxy_a_per_cm",
                "high_gate_current_proxy_a_per_cm",
            )
        )
    add_check(
        checks,
        "temperature_endpoints_produce_resolved_numerical_response",
        math.isfinite(endpoint_response)
        and endpoint_response
        >= float(
            acceptance["minimum_250_to_350_maximum_metric_relative_response"]
        ),
        f"maximum_endpoint_metric_relative_response={endpoint_response}",
    )
    add_check(
        checks,
        "t02_c_300k_curve_and_extraction_reproduced",
        int(reference.get("point_count", -1)) == 31
        and float(reference.get("maximum_current_relative_difference", math.inf))
        <= float(acceptance["maximum_300k_t02_c_current_relative_difference"])
        and float(reference.get("maximum_center_potential_difference_v", math.inf))
        <= float(
            acceptance["maximum_300k_t02_c_center_potential_difference_v"]
        )
        and float(reference.get("maximum_center_density_relative_difference", math.inf))
        <= float(acceptance["maximum_300k_t02_c_center_density_relative_difference"])
        and float(reference.get("vth_difference_v", math.inf))
        <= float(acceptance["maximum_300k_t02_c_vth_difference_v"])
        and float(reference.get("gm_relative_difference", math.inf))
        <= float(acceptance["maximum_300k_t02_c_gm_relative_difference"]),
        json.dumps(reference, sort_keys=True),
    )
    state_ids = [entry["state_id"] for entry in states]
    vtk_count = sum(len(entry["vtk_files"]) for entry in states)
    add_check(
        checks,
        "three_complete_common_bias_states_written",
        state_ids == acceptance["required_state_ids"]
        and len(states) == int(acceptance["required_state_count"])
        and vtk_count == int(acceptance["required_vtk_file_count"]),
        f"states={state_ids} vtk={vtk_count}",
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
        wall_seconds <= float(config["resource_budget"]["maximum_wall_seconds"]),
        f"wall_seconds={wall_seconds} budget={config['resource_budget']['maximum_wall_seconds']}",
    )
    directional = {
        "completion_gate": False,
        "ss_proxy_strictly_increases_with_temperature": bool(metrics)
        and all(
            float(right["ss_proxy_mv_per_dec"])
            > float(left["ss_proxy_mv_per_dec"])
            for left, right in zip(metrics, metrics[1:])
        ),
        "reported_metric_values": {
            key: [float(metric[key]) for metric in metrics]
            for key in (
                "vth_proxy_v", "ss_proxy_mv_per_dec", "gm_proxy_s_per_cm",
                "low_gate_current_proxy_a_per_cm",
                "high_gate_current_proxy_a_per_cm",
            )
        } if metrics else {},
        "failure_rule": config["directional_hypotheses"]["failure_rule"],
    }
    add_check(
        checks,
        "directional_hypotheses_are_reported_without_gating",
        config["directional_hypotheses"]["completion_gate"] is False
        and directional["completion_gate"] is False,
        json.dumps(directional, sort_keys=True),
    )
    failures = [name for name, item in checks.items() if item["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "summary_metrics": {
            "device_count": len(summaries),
            "dc_solve_count": len(solver_records),
            "reported_point_count": len(rows),
            "state_count": len(states),
            "vtk_file_count": sum(len(entry["vtk_files"]) for entry in states),
            "maximum_relative_terminal_current_imbalance": max_imbalance,
            "maximum_endpoint_metric_relative_response": endpoint_response,
            "temperature_values_k": temperatures,
            "thermal_voltage_values_v": [
                float(metric["thermal_voltage_v"]) for metric in metrics
            ],
            "vth_proxy_v": [float(metric["vth_proxy_v"]) for metric in metrics],
            "ss_proxy_mv_per_dec": [
                float(metric["ss_proxy_mv_per_dec"]) for metric in metrics
            ],
            "gm_proxy_s_per_cm": [
                float(metric["gm_proxy_s_per_cm"]) for metric in metrics
            ],
            "low_gate_current_proxy_a_per_cm": [
                float(metric["low_gate_current_proxy_a_per_cm"])
                for metric in metrics
            ],
            "high_gate_current_proxy_a_per_cm": [
                float(metric["high_gate_current_proxy_a_per_cm"])
                for metric in metrics
            ],
        },
        "directional_hypotheses": directional,
    }


def ensure_fresh_outputs(config: dict[str, Any]) -> None:
    outputs = config["outputs"]
    protected = [
        ROOT / path
        for name, path in outputs.items()
        if name not in {"contract_report", "check_report"}
    ]
    existing = [path for path in protected if path.exists()]
    if existing:
        joined = ", ".join(str(path.relative_to(ROOT)) for path in existing)
        raise RuntimeError(
            "T03-P5 refuses to overwrite existing run evidence: " + joined
        )


def main() -> int:
    config = load_json(CONFIG_PATH)
    dependencies = config["dependencies"]
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P5 input contract must pass before simulation")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("T03-P5 config changed after contract check")
    ensure_fresh_outputs(config)

    baseline_path = ROOT / dependencies["t01_baseline_config"]
    mesh_path = ROOT / dependencies["t01_mesh_config"]
    t02_a_path = ROOT / dependencies["t02_a_config"]
    t02_c_report_path = ROOT / dependencies["t02_c_report"]
    baseline = load_json(baseline_path)
    mesh = load_json(mesh_path)
    t02_a_config = load_json(t02_a_path)
    t02_c_report = load_json(t02_c_report_path)

    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=False)
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
        "t03_p5_config": CONFIG_PATH,
        "t03_p5_contract_report": contract_path,
        **{
            name: ROOT / dependencies[name]
            for name in (
                "project_config", "experiments_config", "s00_report",
                "t01_baseline_config", "t01_mesh_config", "t01_transport_runner",
                "t02_a_config", "t02_c_config", "t02_c_report",
                "t02_c_check_report", "p4_report", "p4_check_report",
                "p1_bias_report", "p1_bias_check_report", "p1_cap_report",
                "p1_cap_check_report", "p2_bulk_report", "p2_bulk_check_report",
                "p3_report", "p3_check_report", "source_table", "runner",
                "independent_checker",
            )
        },
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in input_paths.items()
        },
        "temperature_model_contract": config["temperature_model_contract"],
    }
    core.write_json(snapshot_path, snapshot)
    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t03-p5-temperature-sensitivity",
        "validation_command": "make t03-p5-temperature-sensitivity-check",
        "runs": [],
        "errors": [],
    }
    all_rows: list[dict[str, Any]] = []
    all_states: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    solver_records: list[dict[str, Any]] = []
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    original_stage_id = t02_c.STAGE_ID
    t02_c.STAGE_ID = STAGE_ID
    family = config["bias_protocol"]["families"][0]
    try:
        for temperature_k in [
            float(value) for value in config["sensitivity"]["values_k"]
        ]:
            variant_baseline = runtime_baseline(baseline, config, temperature_k)
            variant_config = runtime_config(config, temperature_k)
            thermal_voltage = float(
                variant_baseline["physics"]["thermal_voltage_v"]
            )
            forward, reverse, states, summary, records = t02_c.run_family(
                variant_baseline,
                mesh,
                t02_a_config,
                variant_config,
                family,
                0.0,
                run_dir,
                device_token=f"p5_temperature_{temperature_token(temperature_k)}",
            )
            if reverse:
                raise RuntimeError("T03-P5 unexpectedly produced a reverse path")
            for row in forward:
                row.update({
                    "parameter_group_id": "P5",
                    "changed_parameter": "lattice_temperature_k",
                    "temperature_k": temperature_k,
                    "thermal_voltage_v": thermal_voltage,
                })
            for state in states:
                state.update({
                    "parameter_group_id": "P5",
                    "temperature_k": temperature_k,
                    "thermal_voltage_v": thermal_voltage,
                })
            summary.update({
                "parameter_group_id": "P5",
                "changed_parameter": "lattice_temperature_k",
                "temperature_k": temperature_k,
                "thermal_voltage_v": thermal_voltage,
                "reported_point_count": len(forward),
            })
            all_rows.extend(forward)
            all_states.extend(states)
            summaries.append(summary)
            solver_records.extend(records)
            solver_log["runs"].append({
                "temperature_k": temperature_k,
                "thermal_voltage_v": thermal_voltage,
                "status": "PASS",
                "summary": summary,
                "solver_records": records,
            })
            core.write_json(solver_log_path, solver_log)
            print(
                f"T03_P5_DEVICE_PASS temperature={temperature_k:g} K "
                f"points={len(forward)} solves={len(records)}"
            )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        t02_c.STAGE_ID = original_stage_id

    all_states.sort(key=lambda entry: float(entry["temperature_k"]))
    metrics: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    reference_summary: dict[str, Any] = {}
    sensitivity_hash: str | None = None
    state_hash: str | None = None
    if caught_error is None:
        try:
            metrics = build_metrics(baseline, config, all_rows)
            reference_rows, reference_summary = build_reference_comparison(
                config, all_rows, metrics, t02_c_report
            )
            sensitivity_hash = render_sensitivity_figure(
                config, all_rows, metrics, sensitivity_figure_path
            )
            state_hash = render_state_figure(all_states, state_figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(curve_path, all_rows, CURVE_FIELDNAMES)
    core.write_csv(metric_path, metrics, METRIC_FIELDNAMES)
    core.write_csv(reference_path, reference_rows, REFERENCE_FIELDNAMES)
    core.write_csv(
        state_summary_path,
        [
            {field: entry[field] for field in STATE_SUMMARY_FIELDNAMES}
            for entry in all_states
        ],
        STATE_SUMMARY_FIELDNAMES,
    )
    public_states = [public_state(entry) for entry in all_states]
    core.write_json(
        state_manifest_path,
        {
            "case_id": config["case_id"],
            "stage": config["stage"],
            "entry_count": len(public_states),
            "entries": public_states,
        },
    )
    wall_seconds = time.perf_counter() - wall_start
    solver_log["wall_seconds"] = wall_seconds
    core.write_json(solver_log_path, solver_log)

    assessment = assess(
        config, contract, all_rows, metrics, summaries, all_states,
        solver_records, reference_summary, wall_seconds,
        (sensitivity_hash, state_hash), caught_error,
    )
    passed = assessment["status"] == "PASS"
    artifact_paths = {
        "config_snapshot": snapshot_path,
        "solver_log": solver_log_path,
        "state_manifest": state_manifest_path,
        "curve_csv": curve_path,
        "metric_csv": metric_path,
        "reference_comparison_csv": reference_path,
        "state_summary_csv": state_summary_path,
    }
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
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": config["scope"],
        "temperature_model_contract": config["temperature_model_contract"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "contract_command": "make t03-p5-temperature-contract-check",
            "command": "make t03-p5-temperature-sensitivity",
            "validation_command": "make t03-p5-temperature-sensitivity-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "topology_summaries": summaries,
        "curve_points": all_rows,
        "sensitivity_metrics": metrics,
        "t02_c_300k_reference_reproduction": reference_summary,
        "directional_hypotheses": assessment["directional_hypotheses"],
        "state_outputs": public_states,
        "figures": figures,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": assessment["summary_metrics"],
        "t03_p5_completion": {
            "status": "RUNNER_PASS_INDEPENDENT_CHECK_REQUIRED" if passed else "FAIL",
            "p5_temperature_three_point_runner_complete": passed,
            "independent_persisted_evidence_check_permitted": passed,
            "complete_p5_temperature_group": False,
            "complete_t03_five_group_sensitivity": False,
            "m00_or_downstream_permitted": False,
        },
        "limitations": [
            "Only V_t in the existing Scharfetter-Gummel electron-current expression changes with temperature.",
            "Mobility, density of states, band parameters, permittivities, contacts and traps remain fixed teaching inputs.",
            "VTH, SS, gm and sampled currents are numerical proxies, not measured or calibrated IGZO temperature parameters.",
            "No self-heating, thermal boundary equation, transient thermal response, reliability, compact model or circuit is validated.",
        ],
        "artifacts": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in artifact_paths.items()
        },
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "failure_retention": config["failure_retention"],
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T03_P5_TEMPERATURE_{report['status']} points={len(all_rows)} "
        f"dc_solves={len(solver_records)} states={len(public_states)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T03_P5_TEMPERATURE_ERROR {caught_error}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
