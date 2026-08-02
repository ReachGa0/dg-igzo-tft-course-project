#!/usr/bin/env python3
"""Run the formal isolated T03-P2 NTA/NGA transfer sensitivity."""

from __future__ import annotations

import copy
import json
import math
import os
import re
import shutil
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t02_dual_gate_bidirectional as t02_c  # noqa: E402
import run_t03_p2_bulk_traps_equation_smoke as bulk_smoke  # noqa: E402


core = t02_c.core
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_bulk_traps_formal.json"
STAGE_ID = "T03_P2_BULK_TRAPS_FORMAL"

CURVE_FIELDNAMES = [
    "bulk_family_id",
    "bulk_value_cm3_ev",
    "nta_cm3_ev",
    "nga_cm3_ev",
    "is_zero_control",
    "inactive_family_id",
    *t02_c.FAMILY_FIELDNAMES,
]
METRIC_FIELDNAMES = [
    "bulk_family_id",
    "bulk_value_cm3_ev",
    "nta_cm3_ev",
    "nga_cm3_ev",
    "is_zero_control",
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
    "maximum_sampled_gm_s_per_cm",
    "maximum_sampled_gm_primary_gate_v",
    "ss_window_lower_current_a_per_cm",
    "ss_window_upper_current_a_per_cm",
    "ss_fit_sample_count",
    "ss_fit_slope_v_per_dec",
    "ss_fit_intercept_v",
    "ss_fit_r_squared",
    "ss_proxy_mv_per_dec",
    "low_gate_evaluation_top_gate_v",
    "low_gate_current_proxy_a_per_cm",
    "low_gate_current_proxy_terminal_a",
    "parameter_claim_status",
]
REFERENCE_FIELDNAMES = [
    "bulk_family_id",
    "primary_gate_v",
    "formal_abs_drain_current_a_per_cm",
    "t02_c_abs_drain_current_a_per_cm",
    "current_relative_difference",
    "formal_center_channel_potential_v",
    "t02_c_center_channel_potential_v",
    "center_channel_potential_difference_v",
    "formal_center_channel_electron_density_cm3",
    "t02_c_center_channel_electron_density_cm3",
    "center_density_relative_difference",
]
ZERO_CONTROL_FIELDNAMES = [
    "primary_gate_v",
    "nta_zero_abs_drain_current_a_per_cm",
    "nga_zero_abs_drain_current_a_per_cm",
    "current_relative_difference",
    "nta_zero_center_channel_potential_v",
    "nga_zero_center_channel_potential_v",
    "center_channel_potential_difference_v",
    "nta_zero_center_channel_electron_density_cm3",
    "nga_zero_center_channel_electron_density_cm3",
    "center_density_relative_difference",
]
STATE_SUMMARY_FIELDNAMES = [
    "bulk_family_id",
    "bulk_value_cm3_ev",
    "nta_cm3_ev",
    "nga_cm3_ev",
    "is_zero_control",
    *t02_c.STATE_SUMMARY_FIELDNAMES,
    "bulk_node_row_count",
    "bulk_channel_node_count",
    "center_tail_occupied_density_cm3",
    "center_deep_occupied_density_cm3",
    "center_occupied_bulk_traps_cm3",
    "maximum_occupied_bulk_traps_cm3",
    "bulk_node_csv",
    "bulk_node_csv_sha256",
]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def same_value(left: float, right: float, *, abs_tol: float = 1e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(
        abs(float(left)), abs(float(right)), 1e-300
    )


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def value_token(value: float) -> str:
    if same_value(value, 0.0):
        return "zero"
    return f"{float(value):.0e}".replace("+", "")


def build_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for family in config["sensitivity_families"]:
        family_id = str(family["family_id"])
        for value in [float(item) for item in family["execution_values_cm3_ev"]]:
            cases.append(
                {
                    "case_id": f"{family_id.lower()}_{value_token(value)}",
                    "bulk_family_id": family_id,
                    "bulk_value_cm3_ev": value,
                    "nta_cm3_ev": value if family_id == "NTA" else 0.0,
                    "nga_cm3_ev": value if family_id == "NGA" else 0.0,
                    "active_family": "tail" if family_id == "NTA" else "deep",
                    "inactive_family_id": str(family["inactive_family"]),
                    "is_zero_control": same_value(value, 0.0),
                    "state_id": (
                        f"p2_bulk_{family_id.lower()}_{value_token(value)}_common_primary"
                    ),
                }
            )
    return cases


def curve_for(
    rows: list[dict[str, Any]], family_id: str, value_cm3_ev: float
) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in rows
            if row["bulk_family_id"] == family_id
            and same_value(float(row["bulk_value_cm3_ev"]), value_cm3_ev)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def metric_for(
    metrics: list[dict[str, Any]], family_id: str, value_cm3_ev: float
) -> dict[str, Any]:
    return next(
        row
        for row in metrics
        if row["bulk_family_id"] == family_id
        and same_value(float(row["bulk_value_cm3_ev"]), value_cm3_ev)
    )


def voltage_at_current(curve: list[dict[str, Any]], target_current: float) -> float:
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    for voltage, current in zip(voltages, currents, strict=True):
        if math.isclose(current, target_current, rel_tol=1e-12, abs_tol=0.0):
            return voltage
    brackets = [
        index
        for index in range(len(currents) - 1)
        if currents[index] < target_current < currents[index + 1]
    ]
    if not brackets:
        raise RuntimeError(
            f"target current {target_current:.6e} A/cm is not bracketed by "
            f"[{min(currents):.6e}, {max(currents):.6e}] A/cm"
        )
    index = brackets[0]
    lower_log = math.log10(currents[index])
    upper_log = math.log10(currents[index + 1])
    return voltages[index] + (
        (math.log10(target_current) - lower_log)
        * (voltages[index + 1] - voltages[index])
        / (upper_log - lower_log)
    )


def extract_metric(
    baseline: dict[str, Any],
    config: dict[str, Any],
    curve: list[dict[str, Any]],
    case: dict[str, Any],
) -> dict[str, Any]:
    criterion = float(
        config["extraction_methods"]["constant_current_vth_proxy"][
            "expected_current_per_width_a_per_cm"
        ]
    )
    curve_currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    try:
        base = t02_c.threshold_and_gm(baseline, config, curve)
    except (RuntimeError, StopIteration) as error:
        raise RuntimeError(
            f"{case['case_id']} VTH/gm extraction failed: criterion="
            f"{criterion:.6e} A/cm curve_range="
            f"[{min(curve_currents):.6e}, {max(curve_currents):.6e}] A/cm; {error}"
        ) from error
    ss_method = config["extraction_methods"]["ss_proxy"]
    lower = float(ss_method["lower_current_a_per_cm"])
    upper = float(ss_method["upper_current_a_per_cm"])
    try:
        samples: dict[float, float] = {
            round(math.log10(lower), 14): voltage_at_current(curve, lower),
            round(math.log10(upper), 14): voltage_at_current(curve, upper),
        }
    except RuntimeError as error:
        raise RuntimeError(f"{case['case_id']} SS extraction failed: {error}") from error
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
            f"{case['case_id']} has only {len(log_currents)} augmented SS samples"
        )
    if not math.isfinite(slope) or slope <= 0.0:
        raise RuntimeError(f"{case['case_id']} has invalid SS slope {slope}")

    low_method = config["extraction_methods"]["low_gate_current_proxy"]
    low_v = float(low_method["evaluation_top_gate_v"])
    low_row = next(
        row
        for row in curve
        if same_value(float(row["primary_gate_v"]), low_v)
    )
    low_current = abs(float(low_row["drain_current_a_per_cm"]))
    width_cm = float(baseline["device"]["width_cm"])
    return {
        "bulk_family_id": case["bulk_family_id"],
        "bulk_value_cm3_ev": case["bulk_value_cm3_ev"],
        "nta_cm3_ev": case["nta_cm3_ev"],
        "nga_cm3_ev": case["nga_cm3_ev"],
        "is_zero_control": case["is_zero_control"],
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
        "parameter_claim_status": "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED",
    }


def build_metrics(
    baseline: dict[str, Any],
    config: dict[str, Any],
    rows: list[dict[str, Any]],
    cases: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    metrics = [
        extract_metric(
            baseline,
            config,
            curve_for(rows, case["bulk_family_id"], case["bulk_value_cm3_ev"]),
            case,
        )
        for case in cases
    ]
    for family_id in config["acceptance"]["required_family_order"]:
        reference_vth = float(metric_for(metrics, family_id, 0.0)["vth_proxy_v"])
        for metric in metrics:
            if metric["bulk_family_id"] == family_id:
                metric["delta_vth_proxy_v"] = (
                    float(metric["vth_proxy_v"]) - reference_vth
                )
    return metrics


def t02_reference_curve(t02_report: dict[str, Any]) -> list[dict[str, Any]]:
    return sorted(
        [
            row
            for row in t02_report["family_points"]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def build_reference_comparisons(
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    t02_report: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    reference_curve = t02_reference_curve(t02_report)
    reference_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in reference_curve
    }
    reference_metric = next(
        row
        for row in t02_report["coupling_metrics"]
        if row["family_id"] == "top_primary"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    )
    comparisons: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for family_id in ("NTA", "NGA"):
        current_curve = curve_for(rows, family_id, 0.0)
        family_rows: list[dict[str, Any]] = []
        for row in current_curve:
            voltage = float(row["primary_gate_v"])
            reference = reference_by_voltage.get(round(voltage, 12))
            if reference is None:
                continue
            current = abs(float(row["drain_current_a_per_cm"]))
            reference_current = abs(float(reference["drain_current_a_per_cm"]))
            density = float(row["center_channel_electron_density_cm3"])
            reference_density = float(reference["center_channel_electron_density_cm3"])
            family_rows.append(
                {
                    "bulk_family_id": family_id,
                    "primary_gate_v": voltage,
                    "formal_abs_drain_current_a_per_cm": current,
                    "t02_c_abs_drain_current_a_per_cm": reference_current,
                    "current_relative_difference": relative_difference(
                        current, reference_current
                    ),
                    "formal_center_channel_potential_v": float(
                        row["center_channel_potential_v"]
                    ),
                    "t02_c_center_channel_potential_v": float(
                        reference["center_channel_potential_v"]
                    ),
                    "center_channel_potential_difference_v": abs(
                        float(row["center_channel_potential_v"])
                        - float(reference["center_channel_potential_v"])
                    ),
                    "formal_center_channel_electron_density_cm3": density,
                    "t02_c_center_channel_electron_density_cm3": reference_density,
                    "center_density_relative_difference": relative_difference(
                        density, reference_density
                    ),
                }
            )
        metric = metric_for(metrics, family_id, 0.0)
        summaries.append(
            {
                "bulk_family_id": family_id,
                "point_count": len(family_rows),
                "maximum_current_relative_difference": max(
                    float(row["current_relative_difference"]) for row in family_rows
                ),
                "maximum_center_potential_difference_v": max(
                    float(row["center_channel_potential_difference_v"])
                    for row in family_rows
                ),
                "maximum_center_density_relative_difference": max(
                    float(row["center_density_relative_difference"])
                    for row in family_rows
                ),
                "vth_difference_v": abs(
                    float(metric["vth_proxy_v"])
                    - float(reference_metric["vth_proxy_v"])
                ),
                "gm_relative_difference": relative_difference(
                    metric["gm_proxy_s_per_cm"],
                    reference_metric["gm_proxy_s_per_cm"],
                ),
            }
        )
        comparisons.extend(family_rows)
    return comparisons, summaries


def build_zero_control_comparisons(
    rows: list[dict[str, Any]], metrics: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    nta_curve = curve_for(rows, "NTA", 0.0)
    nga_curve = curve_for(rows, "NGA", 0.0)
    nga_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in nga_curve
    }
    comparisons: list[dict[str, Any]] = []
    for nta_row in nta_curve:
        voltage = float(nta_row["primary_gate_v"])
        nga_row = nga_by_voltage[round(voltage, 12)]
        nta_current = abs(float(nta_row["drain_current_a_per_cm"]))
        nga_current = abs(float(nga_row["drain_current_a_per_cm"]))
        nta_density = float(nta_row["center_channel_electron_density_cm3"])
        nga_density = float(nga_row["center_channel_electron_density_cm3"])
        comparisons.append(
            {
                "primary_gate_v": voltage,
                "nta_zero_abs_drain_current_a_per_cm": nta_current,
                "nga_zero_abs_drain_current_a_per_cm": nga_current,
                "current_relative_difference": relative_difference(
                    nta_current, nga_current
                ),
                "nta_zero_center_channel_potential_v": float(
                    nta_row["center_channel_potential_v"]
                ),
                "nga_zero_center_channel_potential_v": float(
                    nga_row["center_channel_potential_v"]
                ),
                "center_channel_potential_difference_v": abs(
                    float(nta_row["center_channel_potential_v"])
                    - float(nga_row["center_channel_potential_v"])
                ),
                "nta_zero_center_channel_electron_density_cm3": nta_density,
                "nga_zero_center_channel_electron_density_cm3": nga_density,
                "center_density_relative_difference": relative_difference(
                    nta_density, nga_density
                ),
            }
        )
    nta_metric = metric_for(metrics, "NTA", 0.0)
    nga_metric = metric_for(metrics, "NGA", 0.0)
    metric_differences = {
        key: relative_difference(nta_metric[key], nga_metric[key])
        for key in (
            "vth_proxy_v",
            "gm_proxy_s_per_cm",
            "ss_proxy_mv_per_dec",
            "low_gate_current_proxy_a_per_cm",
        )
    }
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
        "metric_relative_differences": metric_differences,
        "maximum_metric_relative_difference": max(metric_differences.values()),
    }


def build_run_config(
    formal_config: dict[str, Any],
    t02_config: dict[str, Any],
    case: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    run_config = copy.deepcopy(t02_config)
    run_config["extraction_methods"] = copy.deepcopy(
        formal_config["extraction_methods"]
    )
    formal_protocol = formal_config["bias_protocol"]
    protocol = run_config["bias_protocol"]
    for key in (
        "source_v",
        "drain_v",
        "low_vds_values_v",
        "primary_gate_grid",
        "primary_negative_preconditioning_v",
        "reverse_paths",
    ):
        protocol[key] = copy.deepcopy(formal_protocol[key])
    protocol["fixed_secondary_gate_values_v"] = [
        float(formal_protocol["fixed_secondary_gate_v"])
    ]
    family = next(
        copy.deepcopy(item)
        for item in t02_config["bias_protocol"]["families"]
        if item["family_id"] == "top_primary"
    )
    family["fixed_secondary_values_v"] = [
        float(formal_protocol["fixed_secondary_gate_v"])
    ]
    protocol["families"] = [family]
    protocol["reverse_paths"] = []
    state = {
        "state_id": case["state_id"],
        "label": (
            f"{case['bulk_family_id']} {value_token(case['bulk_value_cm3_ev'])} "
            "common-primary state"
        ),
        "source_family": "top_primary",
        "vbg_v": float(formal_protocol["fixed_secondary_gate_v"]),
        "vtg_v": float(formal_protocol["common_state_primary_gate_v"]),
    }
    protocol["state_points"] = [state]
    return run_config, family


def persist_bulk_state(
    device: str,
    runtime: dict[str, Any],
    state: dict[str, Any],
    entry: dict[str, Any],
    run_dir: Path,
    case: dict[str, Any],
) -> None:
    bias = {
        "source_v": 0.0,
        "drain_v": float(state["vds_v"]),
        "bottom_gate_v": float(state["vbg_v"]),
        "top_gate_v": float(state["vtg_v"]),
    }
    bulk_rows = bulk_smoke.collect_state_nodes(device, case, bias)
    path = run_dir / f"t03_p2_bulk_{state['state_id']}_bulk_nodes.csv"
    bulk_smoke.write_csv(path, bulk_rows, bulk_smoke.STATE_FIELDNAMES)
    channel_rows = [row for row in bulk_rows if row["region"] == "channel"]
    center = bulk_smoke.center_state(bulk_rows, runtime)
    entry.update(
        {
            "bulk_family_id": case["bulk_family_id"],
            "bulk_value_cm3_ev": case["bulk_value_cm3_ev"],
            "nta_cm3_ev": case["nta_cm3_ev"],
            "nga_cm3_ev": case["nga_cm3_ev"],
            "is_zero_control": case["is_zero_control"],
            "bulk_node_row_count": len(bulk_rows),
            "bulk_channel_node_count": len(channel_rows),
            "center_tail_occupied_density_cm3": float(
                center["tail_occupied_density_cm3"]
            ),
            "center_deep_occupied_density_cm3": float(
                center["deep_occupied_density_cm3"]
            ),
            "center_occupied_bulk_traps_cm3": float(
                center["occupied_bulk_traps_cm3"]
            ),
            "maximum_occupied_bulk_traps_cm3": max(
                float(row["occupied_bulk_traps_cm3"]) for row in channel_rows
            ),
            "bulk_node_csv": str(path.relative_to(ROOT)),
            "bulk_node_csv_sha256": core.sha256(path),
            "_bulk_node_rows": bulk_rows,
        }
    )


def prepare_matplotlib() -> None:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))
    os.environ.setdefault("TEMP", str(temp_dir))
    os.environ.setdefault("TMP", str(temp_dir))


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

    figure, axes = plt.subplots(
        2, 3, figsize=(13.0, 8.2), constrained_layout=True, squeeze=False
    )
    colors = ["#2b6f9f", "#2f855a", "#b35c31", "#8a4f87"]
    for row_index, family in enumerate(config["sensitivity_families"]):
        family_id = str(family["family_id"])
        values = [float(value) for value in family["execution_values_cm3_ev"]]
        labels = [value_token(value) for value in values]
        positions = list(range(len(values)))
        for color, value, label in zip(colors, values, labels, strict=True):
            curve = curve_for(rows, family_id, value)
            axes[row_index][0].semilogy(
                [float(row["primary_gate_v"]) for row in curve],
                [abs(float(row["drain_current_a_per_cm"])) for row in curve],
                color=color,
                linewidth=1.6,
                label=label,
            )
        axes[row_index][0].set_title(f"{family_id} isolated transfer curves")
        axes[row_index][0].set_xlabel("Top-gate voltage (V)")
        axes[row_index][0].set_ylabel("Absolute drain current per width (A/cm)")
        axes[row_index][0].legend(fontsize=8, title=f"{family_id} (cm^-3 eV^-1)")

        family_metrics = [metric_for(metrics, family_id, value) for value in values]
        vth_axis = axes[row_index][1]
        ss_axis = vth_axis.twinx()
        vth_axis.plot(
            positions,
            [float(item["vth_proxy_v"]) for item in family_metrics],
            "o-",
            color="#2563a6",
            label="VTH",
        )
        ss_axis.plot(
            positions,
            [float(item["ss_proxy_mv_per_dec"]) for item in family_metrics],
            "s--",
            color="#287d59",
            label="SS",
        )
        vth_axis.set_title(f"{family_id} VTH and SS proxies")
        vth_axis.set_ylabel("VTH proxy (V)", color="#2563a6")
        ss_axis.set_ylabel("SS proxy (mV/dec)", color="#287d59")

        low_axis = axes[row_index][2]
        gm_axis = low_axis.twinx()
        low_axis.semilogy(
            positions,
            [
                float(item["low_gate_current_proxy_a_per_cm"])
                for item in family_metrics
            ],
            "o-",
            color="#a33a3a",
            label="low-gate current",
        )
        gm_axis.plot(
            positions,
            [float(item["gm_proxy_s_per_cm"]) for item in family_metrics],
            "s--",
            color="#c45d25",
            label="gm",
        )
        low_axis.set_title(f"{family_id} current and gm proxies")
        low_axis.set_ylabel("Low-gate current proxy (A/cm)", color="#a33a3a")
        gm_axis.set_ylabel("gm proxy (S/cm)", color="#c45d25")
        for axis in (vth_axis, low_axis):
            axis.set_xticks(positions, labels)
            axis.set_xlabel(f"{family_id} (cm^-3 eV^-1)")
        for axis in axes[row_index]:
            axis.grid(True, which="both", color="#d8dee3", linewidth=0.6)
    figure.suptitle(
        "T03-P2-BULK-TRAPS-FORMAL isolated IGZO sensitivity", fontsize=13
    )
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

    potentials = [
        float(row["potential_v"])
        for entry in state_entries
        for row in entry["_node_rows"]
    ]
    log_electrons = [
        math.log10(max(float(row["electron_density_cm3"]), 1.0))
        for entry in state_entries
        for row in entry["_node_rows"]
        if row["region"] == "channel"
    ]
    log_traps = [
        math.log10(max(float(row["occupied_bulk_traps_cm3"]), 1.0))
        for entry in state_entries
        for row in entry["_bulk_node_rows"]
        if row["region"] == "channel"
    ]
    log_currents = [
        math.log10(
            max(float(row["electron_current_density_magnitude_a_per_cm2"]), 1e-300)
        )
        for entry in state_entries
        for row in entry["_element_rows"]
    ]
    norms = [
        Normalize(min(potentials), max(potentials)),
        Normalize(min(log_electrons), max(log_electrons)),
        Normalize(min(log_traps), max(log_traps)),
        Normalize(min(log_currents), max(log_currents)),
    ]
    cmaps = ["viridis", "plasma", "cividis", "magma"]
    figure, axes = plt.subplots(
        len(state_entries),
        4,
        figsize=(14.0, 18.0),
        constrained_layout=True,
        squeeze=False,
    )
    for row_index, entry in enumerate(state_entries):
        nodes = entry["_node_rows"]
        channel_nodes = [row for row in nodes if row["region"] == "channel"]
        bulk_nodes = [
            row for row in entry["_bulk_node_rows"] if row["region"] == "channel"
        ]
        elements = entry["_element_rows"]
        axes[row_index][0].scatter(
            [float(row["x_um"]) for row in nodes],
            [float(row["y_nm"]) for row in nodes],
            c=[float(row["potential_v"]) for row in nodes],
            cmap=cmaps[0],
            norm=norms[0],
            s=3,
            linewidths=0,
        )
        axes[row_index][1].scatter(
            [float(row["x_um"]) for row in channel_nodes],
            [float(row["y_nm"]) for row in channel_nodes],
            c=[
                math.log10(max(float(row["electron_density_cm3"]), 1.0))
                for row in channel_nodes
            ],
            cmap=cmaps[1],
            norm=norms[1],
            s=4,
            linewidths=0,
        )
        axes[row_index][2].scatter(
            [float(row["x_um"]) for row in bulk_nodes],
            [float(row["y_nm"]) for row in bulk_nodes],
            c=[
                math.log10(max(float(row["occupied_bulk_traps_cm3"]), 1.0))
                for row in bulk_nodes
            ],
            cmap=cmaps[2],
            norm=norms[2],
            s=4,
            linewidths=0,
        )
        axes[row_index][3].scatter(
            [float(row["centroid_x_um"]) for row in elements],
            [float(row["centroid_y_nm"]) for row in elements],
            c=[
                math.log10(
                    max(
                        float(row["electron_current_density_magnitude_a_per_cm2"]),
                        1e-300,
                    )
                )
                for row in elements
            ],
            cmap=cmaps[3],
            norm=norms[3],
            s=4,
            linewidths=0,
        )
        label = (
            f"{entry['bulk_family_id']}={value_token(entry['bulk_value_cm3_ev'])}"
        )
        for column in range(4):
            axis = axes[row_index][column]
            axis.set_xlim(0.0, 10.0)
            axis.set_ylim(-2.0, 86.0)
            axis.axhline(30.0, color="#eeeeee", linewidth=0.5)
            axis.axhline(54.0, color="#eeeeee", linewidth=0.5)
            axis.set_ylabel(f"{label}\ny (nm)")
        if row_index == len(state_entries) - 1:
            for axis in axes[row_index]:
                axis.set_xlabel("x (um)")
    titles = [
        "Potential (V)",
        "log10 electron density (cm^-3)",
        "log10 occupied bulk traps (cm^-3)",
        "log10 |J| (A/cm^2)",
    ]
    for column, title in enumerate(titles):
        axes[0][column].set_title(title)
        figure.colorbar(
            ScalarMappable(norm=norms[column], cmap=cmaps[column]),
            ax=axes[:, column],
            fraction=0.02,
            pad=0.01,
        )
    figure.suptitle(
        "T03-P2-BULK-TRAPS-FORMAL states at VTG=0.3 V", fontsize=13
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any],
    contract: dict[str, Any],
    cases: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    metrics: list[dict[str, Any]],
    summaries: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    solver_log: dict[str, Any],
    references: list[dict[str, Any]],
    zero_control: dict[str, Any],
    figure_hashes: tuple[str | None, str | None],
    caught_error: Exception | None,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    add_check(
        checks,
        "contract_is_passed_and_current",
        contract.get("contract_status") == "PASS"
        and contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and contract.get("config", {}).get("sha256") == core.sha256(CONFIG_PATH),
        f"status={contract.get('contract_status')} simulation={contract.get('simulation_status')}",
    )
    add_check(
        checks,
        "runner_completed_without_exception",
        caught_error is None,
        repr(caught_error),
    )
    runs = solver_log.get("runs", [])
    records = [record for run in runs for record in run.get("solver_records", [])]
    expected_case_ids = [case["case_id"] for case in cases]
    add_check(
        checks,
        "eight_fresh_devices_and_frozen_dc_budget_converged",
        [run.get("case_id") for run in runs] == expected_case_ids
        and len(runs) == 8
        and [len(run.get("solver_records", [])) for run in runs]
        == [int(config["resource_budget"]["required_dc_solve_count_per_device"])]
        * 8
        and len(records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors"),
        f"runs={len(runs)} records={len(records)} errors={solver_log.get('errors')}",
    )
    expected_isolation = [
        (
            case["bulk_family_id"],
            case["bulk_value_cm3_ev"],
            case["nta_cm3_ev"],
            case["nga_cm3_ev"],
        )
        for case in cases
    ]
    actual_isolation = [
        (
            item.get("bulk_family_id"),
            item.get("bulk_value_cm3_ev"),
            item.get("nta_cm3_ev"),
            item.get("nga_cm3_ev"),
        )
        for item in summaries
    ]
    interfaces_valid = all(
        item.get("bottom_interface_equations") == ["PotentialEquation"]
        and item.get("top_interface_equations") == ["PotentialEquation"]
        for item in summaries
    )
    add_check(
        checks,
        "exact_family_isolation_and_zero_interface_dit_are_preserved",
        actual_isolation == expected_isolation and interfaces_valid,
        f"isolation={actual_isolation} interfaces={interfaces_valid}",
    )
    required_models = {
        "BulkTrapTailOccupiedDensity",
        "BulkTrapDeepOccupiedDensity",
        "OccupiedBulkTraps",
        "OccupiedBulkTrapsDerivative",
        "PhysicalBulkTrapCharge",
        "PotentialNodeTrapCharge",
        "PotentialNodeCharge",
        "PotentialNodeCharge:Electrons",
    }
    topology_valid = all(
        item.get("regions") == sorted(bulk_smoke.ENABLED_REGIONS)
        and item.get("contacts") == sorted(bulk_smoke.ENABLED_CONTACTS)
        and item.get("interfaces") == sorted(bulk_smoke.ENABLED_INTERFACES)
        and int(item.get("node_count_with_interface_duplicates", -1)) == 2419
        and int(item.get("element_count", -1)) == 4480
        and required_models <= set(item.get("channel_node_models", []))
        and item.get("channel_equations")
        == ["ElectronContinuityEquation", "PotentialEquation"]
        for item in summaries
    )
    add_check(
        checks,
        "topology_and_bulk_models_match_the_frozen_teaching_stack",
        len(summaries) == 8 and topology_valid,
        f"summaries={len(summaries)} topology={topology_valid}",
    )
    expected_grid = t02_c.primary_grid(
        {
            "bias_protocol": config["bias_protocol"],
        }
    )
    grids_valid = all(
        [float(row["primary_gate_v"]) for row in curve_for(rows, case["bulk_family_id"], case["bulk_value_cm3_ev"])]
        == expected_grid
        for case in cases
    )
    add_check(
        checks,
        "exact_eight_curve_frozen_point_grid_completed",
        len(rows) == int(acceptance["required_total_reported_point_count"])
        and grids_valid
        and all(row.get("stage_id") == STAGE_ID for row in rows),
        f"rows={len(rows)} grids={grids_valid}",
    )
    maximum_imbalance = max(
        (float(row["relative_current_imbalance"]) for row in rows),
        default=math.inf,
    )
    currents_valid = all(
        math.isfinite(float(row["drain_current_a_per_cm"]))
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and row["converged"] is True
        for row in rows
    )
    add_check(
        checks,
        "finite_directional_and_conserved_terminal_current",
        currents_valid
        and maximum_imbalance
        <= float(acceptance["maximum_relative_terminal_current_imbalance"]),
        f"direction={currents_valid} max_imbalance={maximum_imbalance:.6e}",
    )
    monotonic = all(
        all(higher > lower for lower, higher in zip(currents, currents[1:]))
        for currents in (
            [
                abs(float(row["drain_current_a_per_cm"]))
                for row in curve_for(
                    rows, case["bulk_family_id"], case["bulk_value_cm3_ev"]
                )
            ]
            for case in cases
        )
    )
    add_check(
        checks,
        "each_primary_gate_curve_is_strictly_increasing",
        monotonic,
        f"monotonic={monotonic}",
    )
    zero_current = max(
        (
            float(item["zero_equilibrium"]["maximum_absolute_terminal_current_a_per_cm"])
            for item in summaries
        ),
        default=math.inf,
    )
    zero_control_potential = max(
        (
            float(item["zero_equilibrium"]["maximum_absolute_potential_v"])
            for item in summaries
            if item.get("is_zero_control")
        ),
        default=math.inf,
    )
    nonzero_potentials = [
        float(item["zero_equilibrium"]["maximum_absolute_potential_v"])
        for item in summaries
        if not item.get("is_zero_control")
    ]
    nonzero_potentials_finite = len(nonzero_potentials) == 6 and all(
        math.isfinite(value) and value >= 0.0 for value in nonzero_potentials
    )
    add_check(
        checks,
        "fresh_zero_equilibria_are_current_free_and_zero_controls_restore_zero_potential",
        zero_current
        <= float(
            acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"]
        )
        and zero_control_potential
        <= float(
            acceptance["maximum_zero_control_equilibrium_absolute_potential_v"]
        )
        and nonzero_potentials_finite,
        (
            f"current={zero_current:.6e} zero_control_potential="
            f"{zero_control_potential:.6e} nonzero_potentials="
            f"{nonzero_potentials}"
        ),
    )
    metrics_valid = len(metrics) == 8 and all(
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
        and math.isfinite(float(metric["low_gate_current_proxy_a_per_cm"]))
        and float(metric["low_gate_current_proxy_a_per_cm"]) > 0.0
        for metric in metrics
    )
    add_check(
        checks,
        "vth_gm_ss_and_low_gate_current_proxies_are_extractable",
        metrics_valid,
        f"metrics={len(metrics)} ss_R2={[item.get('ss_fit_r_squared') for item in metrics]}",
    )
    reference_valid = len(references) == 2 and all(
        int(item.get("point_count", -1)) == 31
        and float(item.get("maximum_current_relative_difference", math.inf))
        <= float(
            acceptance["maximum_each_zero_control_t02_c_current_relative_difference"]
        )
        and float(item.get("maximum_center_potential_difference_v", math.inf))
        <= float(
            acceptance["maximum_each_zero_control_t02_c_center_potential_difference_v"]
        )
        and float(item.get("maximum_center_density_relative_difference", math.inf))
        <= float(
            acceptance["maximum_each_zero_control_t02_c_center_density_relative_difference"]
        )
        and float(item.get("vth_difference_v", math.inf))
        <= float(acceptance["maximum_each_zero_control_t02_c_vth_difference_v"])
        and float(item.get("gm_relative_difference", math.inf))
        <= float(acceptance["maximum_each_zero_control_t02_c_gm_relative_difference"])
        for item in references
    )
    add_check(
        checks,
        "both_zero_controls_reproduce_t02_c",
        reference_valid,
        json.dumps(references, sort_keys=True),
    )
    pairwise_valid = (
        int(zero_control.get("point_count", -1))
        == int(acceptance["required_primary_gate_point_count"])
        and float(zero_control.get("maximum_current_relative_difference", math.inf))
        <= float(acceptance["maximum_pairwise_zero_control_current_relative_difference"])
        and float(zero_control.get("maximum_metric_relative_difference", math.inf))
        <= float(acceptance["maximum_pairwise_zero_control_metric_relative_difference"])
    )
    add_check(
        checks,
        "two_independently_executed_zero_controls_match",
        pairwise_valid,
        json.dumps(zero_control, sort_keys=True),
    )
    expected_state_ids = [case["state_id"] for case in cases]
    states_valid = (
        [entry.get("state_id") for entry in state_entries] == expected_state_ids
        and len(state_entries) == 8
        and sum(int(entry.get("vtk_file_count", 0)) for entry in state_entries) == 48
        and all(int(entry.get("bulk_node_row_count", 0)) == 2419 for entry in state_entries)
        and all(int(entry.get("bulk_channel_node_count", 0)) > 0 for entry in state_entries)
        and all(entry.get("bulk_node_csv_sha256") for entry in state_entries)
    )
    zero_traps_valid = all(
        abs(float(entry["maximum_occupied_bulk_traps_cm3"])) <= 1e-12
        for entry in state_entries
        if entry["is_zero_control"]
    )
    nonzero_traps_valid = all(
        float(entry["maximum_occupied_bulk_traps_cm3"]) > 0.0
        for entry in state_entries
        if not entry["is_zero_control"]
    )
    add_check(
        checks,
        "eight_states_persist_potential_electrons_traps_current_and_vtk",
        states_valid and zero_traps_valid and nonzero_traps_valid,
        (
            f"states={[entry.get('state_id') for entry in state_entries]} "
            f"vtk={sum(int(entry.get('vtk_file_count', 0)) for entry in state_entries)} "
            f"zero={zero_traps_valid} nonzero={nonzero_traps_valid}"
        ),
    )
    state_by_case = {
        (entry["bulk_family_id"], float(entry["bulk_value_cm3_ev"])): entry
        for entry in state_entries
    }
    family_responses: dict[str, float] = {}
    for family in config["sensitivity_families"]:
        family_id = str(family["family_id"])
        maximum_value = max(float(value) for value in family["formal_values_cm3_ev"])
        if (family_id, 0.0) in state_by_case and (family_id, maximum_value) in state_by_case:
            family_responses[family_id] = relative_difference(
                state_by_case[(family_id, 0.0)]["absolute_drain_current_a_per_cm"],
                state_by_case[(family_id, maximum_value)]["absolute_drain_current_a_per_cm"],
            )
    response_valid = len(family_responses) == 2 and all(
        value
        >= float(
            acceptance["minimum_each_family_maximum_common_state_current_relative_response"]
        )
        for value in family_responses.values()
    )
    add_check(
        checks,
        "both_families_show_nonzero_common_state_response",
        response_valid,
        json.dumps(family_responses, sort_keys=True),
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
        f"wall={solver_log.get('wall_seconds')} budget={config['resource_budget']['maximum_wall_seconds']}",
    )
    prohibited_claims = config["evidence_boundary"]["prohibited_claims"]
    add_check(
        checks,
        "evidence_boundary_remains_numerical_and_partial_until_independent_check",
        "numerical proxies"
        in config["evidence_boundary"]["allowed_claim_after_future_run_and_independent_check"]
        and any("P2, T03" in item for item in prohibited_claims)
        and any(
            "physically or experimentally validated" in item
            for item in prohibited_claims
        ),
        config["evidence_boundary"]["allowed_claim_after_future_run_and_independent_check"],
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
            "vtk_file_count": sum(
                int(entry.get("vtk_file_count", 0)) for entry in state_entries
            ),
            "maximum_relative_terminal_current_imbalance": maximum_imbalance,
            "family_common_state_current_relative_responses": family_responses,
        },
    }


def archive_failed_run(
    config: dict[str, Any],
    run_dir: Path,
    paths: dict[str, Path],
    report: dict[str, Any],
) -> dict[str, Any]:
    failure_name = (
        report["failures"][0]
        if report.get("failures")
        else "runner_exception"
    )
    slug = re.sub(r"[^a-z0-9]+", "_", str(failure_name).lower()).strip("_")
    revision = str(config["revision"])
    archive_dir = ROOT / config["failure_retention"]["archive_directory_pattern"].replace(
        "<revision>", revision
    ).replace("<failure_slug>", slug)
    archive_report = ROOT / config["failure_retention"]["archive_report_pattern"].replace(
        "<revision>", revision
    ).replace("<failure_slug>", slug)
    if archive_dir.exists() or archive_report.exists():
        raise RuntimeError(
            f"refusing to overwrite existing failed evidence: {archive_dir}"
        )
    shutil.copytree(run_dir, archive_dir)
    external_dir = archive_dir / "external_artifacts"
    external_dir.mkdir(parents=True, exist_ok=True)
    copied: list[dict[str, Any]] = []
    for name, path in paths.items():
        if name in {"contract_report", "report"} or not path.is_file():
            continue
        destination = external_dir / path.name
        shutil.copy2(path, destination)
        copied.append(
            {
                "name": name,
                "source": str(path.relative_to(ROOT)),
                "archive": str(destination.relative_to(ROOT)),
                "sha256": core.sha256(destination),
            }
        )
    archive_info = {
        "directory": str(archive_dir.relative_to(ROOT)),
        "report": str(archive_report.relative_to(ROOT)),
        "failed_gate": failure_name,
        "copied_external_artifacts": copied,
    }
    core.write_json(
        archive_dir / "failure_archive_manifest.json",
        {"status": "FAIL_PRESERVED", **archive_info},
    )
    report["failure_archive"] = archive_info
    core.write_json(paths["report"], report)
    core.write_json(archive_report, report)
    return archive_info


def main() -> int:
    config = load_json(CONFIG_PATH)
    dependencies = config["dependencies"]
    outputs = config["outputs"]
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("contract_status") != "PASS":
        raise RuntimeError("T03-P2-BULK-TRAPS-FORMAL input contract is not PASS")
    if contract.get("config", {}).get("sha256") != core.sha256(CONFIG_PATH):
        raise RuntimeError("formal contract report does not match the current config")

    paths = {
        name: ROOT / value
        for name, value in outputs.items()
        if name != "run_directory"
    }
    if paths["report"].is_file():
        existing_report = load_json(paths["report"])
        if existing_report.get("status") == "FAIL":
            raise RuntimeError(
                "refusing to overwrite failed formal evidence; create a new config revision"
            )

    baseline_path = ROOT / dependencies["t01_baseline_config"]
    t02_config_path = ROOT / dependencies["t02_c_config"]
    t02_report_path = ROOT / dependencies["t02_c_report"]
    bulk_input_path = ROOT / dependencies["bulk_input_config"]
    baseline = load_json(baseline_path)
    t02_config = load_json(t02_config_path)
    t02_report = load_json(t02_report_path)
    bulk_input = load_json(bulk_input_path)
    mesh_path = ROOT / t02_config["dependencies"]["t01_mesh_config"]
    t02_a_path = ROOT / t02_config["dependencies"]["t02_a_config"]
    mesh_config = load_json(mesh_path)
    t02_a_config = load_json(t02_a_path)
    if t02_report.get("status") != dependencies["required_t02_c_status"]:
        raise RuntimeError("T02-C dependency is not PASS")

    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    input_paths = {
        "formal_config": CONFIG_PATH,
        "formal_contract_report": contract_path,
        "runner_script": Path(__file__).resolve(),
        "t01_baseline_config": baseline_path,
        "t01_mesh_config": mesh_path,
        "t02_a_config": t02_a_path,
        "t02_c_config": t02_config_path,
        "t02_c_report": t02_report_path,
        "bulk_input_config": bulk_input_path,
        **{
            name: ROOT / dependencies[name]
            for name in (
                "project_config",
                "experiments_config",
                "s00_report",
                "t02_c_check_report",
                "dit_formal_config",
                "bulk_input_contract_report",
                "bulk_smoke_report",
                "bulk_smoke_check_report",
                "literature_table",
                "v1_formal_config",
                "v1_formal_contract_report",
                "v1_formal_report",
                "v1_failure_archive_manifest",
                "v1_config_snapshot",
                "v1_runner_script",
                "v1_curve_csv",
            )
        },
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "inputs": {
            name: {
                "path": str(path.relative_to(ROOT)),
                "sha256": core.sha256(path),
            }
            for name, path in input_paths.items()
        },
        "formal_contract": config,
        "bulk_equation_source": bulk_input,
    }
    core.write_json(paths["config_snapshot"], snapshot)

    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t03-p2-bulk-traps-formal",
        "validation_command": "make t03-p2-bulk-traps-formal-check",
        "runs": [],
        "errors": [],
    }
    cases = build_cases(config)
    rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    original_stage_id = t02_c.STAGE_ID
    t02_c.STAGE_ID = STAGE_ID
    try:
        for case in cases:
            run_config, family = build_run_config(config, t02_config, case)
            extension: dict[str, Any] = {}

            def install(device: str, _runtime: dict[str, Any]) -> None:
                extension["model_metadata"] = bulk_smoke.install_bulk_trap_models(
                    device, case, bulk_input
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
                extension["channel_node_models"] = sorted(
                    core.devsim.get_node_model_list(device=device, region="channel")
                )
                extension["channel_equations"] = sorted(
                    core.devsim.get_equation_list(device=device, region="channel")
                )

            def persist(
                device: str,
                runtime: dict[str, Any],
                state: dict[str, Any],
                _row: dict[str, Any],
                entry: dict[str, Any],
                state_run_dir: Path,
            ) -> None:
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
                extension["channel_node_models"] = sorted(
                    core.devsim.get_node_model_list(device=device, region="channel")
                )
                extension["channel_equations"] = sorted(
                    core.devsim.get_equation_list(device=device, region="channel")
                )
                persist_bulk_state(
                    device, runtime, state, entry, state_run_dir, case
                )

            forward, reverse, states, summary, records = t02_c.run_family(
                baseline,
                mesh_config,
                t02_a_config,
                run_config,
                family,
                0.0,
                run_dir,
                post_initialize_hook=install,
                device_token=case["state_id"],
                post_state_hook=persist,
            )
            if reverse:
                raise RuntimeError(
                    f"{case['case_id']} unexpectedly produced a reverse path"
                )
            rows.extend(
                {
                    "bulk_family_id": case["bulk_family_id"],
                    "bulk_value_cm3_ev": case["bulk_value_cm3_ev"],
                    "nta_cm3_ev": case["nta_cm3_ev"],
                    "nga_cm3_ev": case["nga_cm3_ev"],
                    "is_zero_control": case["is_zero_control"],
                    "inactive_family_id": case["inactive_family_id"],
                    **row,
                }
                for row in forward
            )
            state_entries.extend(states)
            summary = {
                "case_id": case["case_id"],
                "bulk_family_id": case["bulk_family_id"],
                "bulk_value_cm3_ev": case["bulk_value_cm3_ev"],
                "nta_cm3_ev": case["nta_cm3_ev"],
                "nga_cm3_ev": case["nga_cm3_ev"],
                "is_zero_control": case["is_zero_control"],
                **summary,
                **extension,
            }
            summaries.append(summary)
            solver_log["runs"].append(
                {
                    "case_id": case["case_id"],
                    "bulk_family_id": case["bulk_family_id"],
                    "bulk_value_cm3_ev": case["bulk_value_cm3_ev"],
                    "nta_cm3_ev": case["nta_cm3_ev"],
                    "nga_cm3_ev": case["nga_cm3_ev"],
                    "status": "PASS",
                    "summary": summary,
                    "solver_records": records,
                }
            )
            core.write_json(paths["solver_log"], solver_log)
            print(
                f"T03_P2_BULK_TRAPS_FORMAL_DEVICE_PASS "
                f"family={case['bulk_family_id']} value={case['bulk_value_cm3_ev']:.6e} "
                f"points={len(forward)} solves={len(records)}"
            )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        t02_c.STAGE_ID = original_stage_id

    state_order = {
        case["state_id"]: index for index, case in enumerate(cases)
    }
    state_entries.sort(key=lambda entry: state_order.get(str(entry["state_id"]), 999))
    metrics: list[dict[str, Any]] = []
    reference_rows: list[dict[str, Any]] = []
    reference_summaries: list[dict[str, Any]] = []
    zero_rows: list[dict[str, Any]] = []
    zero_summary: dict[str, Any] = {}
    sensitivity_hash: str | None = None
    state_hash: str | None = None
    if caught_error is None:
        try:
            metrics = build_metrics(baseline, config, rows, cases)
            reference_rows, reference_summaries = build_reference_comparisons(
                rows, metrics, t02_report
            )
            zero_rows, zero_summary = build_zero_control_comparisons(rows, metrics)
            sensitivity_hash = render_sensitivity_figure(
                config, rows, metrics, paths["sensitivity_figure_png"]
            )
            state_hash = render_state_figure(
                state_entries, paths["state_figure_png"]
            )
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})

    core.write_csv(paths["curve_csv"], rows, CURVE_FIELDNAMES)
    core.write_csv(paths["metric_csv"], metrics, METRIC_FIELDNAMES)
    core.write_csv(
        paths["reference_comparison_csv"], reference_rows, REFERENCE_FIELDNAMES
    )
    core.write_csv(
        paths["zero_control_comparison_csv"], zero_rows, ZERO_CONTROL_FIELDNAMES
    )
    core.write_csv(
        paths["state_summary_csv"],
        [
            {field: entry.get(field, "") for field in STATE_SUMMARY_FIELDNAMES}
            for entry in state_entries
        ],
        STATE_SUMMARY_FIELDNAMES,
    )
    manifest_entries = [
        {key: value for key, value in entry.items() if not key.startswith("_")}
        for entry in state_entries
    ]
    core.write_json(
        paths["state_manifest"],
        {
            "case_id": config["case_id"],
            "stage": config["stage"],
            "entry_count": len(manifest_entries),
            "entries": manifest_entries,
        },
    )
    solver_log["wall_seconds"] = time.perf_counter() - wall_start
    core.write_json(paths["solver_log"], solver_log)

    assessment = assess(
        config,
        contract,
        cases,
        rows,
        metrics,
        summaries,
        state_entries,
        solver_log,
        reference_summaries,
        zero_summary,
        (sensitivity_hash, state_hash),
        caught_error,
    )
    directional: dict[str, Any] = {"completion_gate": False, "families": {}}
    for family in config["sensitivity_families"]:
        family_id = str(family["family_id"])
        family_metrics = [
            metric_for(metrics, family_id, float(value))
            for value in family["execution_values_cm3_ev"]
        ] if metrics else []
        directional["families"][family_id] = {
            "vth_proxy_strictly_increases": bool(family_metrics)
            and all(
                float(right["vth_proxy_v"]) > float(left["vth_proxy_v"])
                for left, right in zip(family_metrics, family_metrics[1:])
            ),
            "ss_proxy_strictly_increases": bool(family_metrics)
            and all(
                float(right["ss_proxy_mv_per_dec"])
                > float(left["ss_proxy_mv_per_dec"])
                for left, right in zip(family_metrics, family_metrics[1:])
            ),
            "gm_proxy_strictly_decreases": bool(family_metrics)
            and all(
                float(right["gm_proxy_s_per_cm"])
                < float(left["gm_proxy_s_per_cm"])
                for left, right in zip(family_metrics, family_metrics[1:])
            ),
            "observed_metrics": family_metrics,
        }
    artifact_keys = (
        "config_snapshot",
        "solver_log",
        "state_manifest",
        "curve_csv",
        "metric_csv",
        "reference_comparison_csv",
        "zero_control_comparison_csv",
        "state_summary_csv",
    )
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": config["parameter_group_id"],
        "evidence_level": "E2" if assessment["status"] == "PASS" else "E0",
        "model_scope": config["scope"],
        "input_snapshot": str(paths["config_snapshot"].relative_to(ROOT)),
        "sensitivity_families": config["sensitivity_families"],
        "family_summaries": summaries,
        "family_points": rows,
        "metrics": metrics,
        "zero_control_t02_c_reproduction": reference_summaries,
        "pairwise_zero_control_reproduction": zero_summary,
        "directional_diagnostics": directional,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": assessment["summary_metrics"],
        "artifacts": {
            key: {
                "path": str(paths[key].relative_to(ROOT)),
                "sha256": core.sha256(paths[key]),
            }
            for key in artifact_keys
        },
        "figures": [
            {
                "path": str(paths["sensitivity_figure_png"].relative_to(ROOT)),
                "sha256": sensitivity_hash,
            },
            {
                "path": str(paths["state_figure_png"].relative_to(ROOT)),
                "sha256": state_hash,
            },
        ]
        if sensitivity_hash is not None and state_hash is not None
        else [],
        "formal_sensitivity_run": assessment["status"] == "PASS",
        "independent_persisted_evidence_check_complete": False,
        "t03_p2_completion": {
            "status": "PARTIAL" if assessment["status"] == "PASS" else "BLOCKED",
            "interface_dit_substage_complete": True,
            "bulk_equation_smoke_passed": True,
            "bulk_formal_contract_passed": True,
            "bulk_formal_runner_passed": assessment["status"] == "PASS",
            "bulk_formal_independent_check_passed": False,
            "complete_p2_trap_group": False,
            "complete_t03_five_group_sensitivity": False,
            "p3_or_p5_permitted_next": False,
            "experimental_calibration_permitted": False,
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(paths["report"], report)
    if report["status"] == "FAIL":
        archive_failed_run(config, run_dir, paths, report)
    print(
        f"T03_P2_BULK_TRAPS_FORMAL_{report['status']} "
        f"devices={assessment['summary_metrics']['device_count']} "
        f"dc={assessment['summary_metrics']['dc_solve_count']} "
        f"points={assessment['summary_metrics']['reported_point_count']} "
        f"wall={solver_log['wall_seconds']:.3f}s report={paths['report']}"
    )
    for failure in report["failures"]:
        print(
            f"T03_P2_BULK_TRAPS_FORMAL_ERROR {failure}: "
            f"{report['checks'][failure]['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
