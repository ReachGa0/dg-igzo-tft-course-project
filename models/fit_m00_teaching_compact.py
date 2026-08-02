#!/usr/bin/env python3
"""Run the single preregistered M00 teaching compact-model fit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import platform
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import __version__ as scipy_version
from scipy.optimize import least_squares


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "compact_m00_input_validation.json"
EXPECTED_RUNNER_CHECK_COUNT = 24
VTH_CRITERION_A_PER_CM = 1.0e-5
GM_OVERDRIVE_V = 0.2
MANIFEST_FIELDS = [
    "row_uid",
    "curve_id",
    "dataset_id",
    "split",
    "kind",
    "topology",
    "source_path",
    "source_row_number",
    "source_row_sha256",
    "selection_role",
    "optimizer_input",
    "vbg_v",
    "vtg_v",
    "vds_v",
    "primary_axis_v",
    "target_current_a_per_cm",
    "w_um",
    "l_um",
    "temperature_k",
]
PREDICTION_FIELDS = [
    *MANIFEST_FIELDS,
    "model_current_a_per_cm",
    "current_error_a_per_cm",
    "linear_normalized_residual",
    "log_residual_dec",
]
CURVE_METRIC_FIELDS = [
    "curve_id",
    "dataset_id",
    "split",
    "kind",
    "topology",
    "point_count",
    "scored_point_count",
    "linear_nrmse",
    "log_rmse_dec",
    "maximum_abs_current_error_a_per_cm",
    "maximum_target_current_a_per_cm",
    "target_vth_proxy_v",
    "model_vth_proxy_v",
    "vth_absolute_error_v",
    "target_gm_proxy_a_per_cm_v",
    "model_gm_proxy_a_per_cm_v",
    "gm_relative_error",
    "sampled_prediction_monotonic",
    "curve_acceptance_status",
]
PARAMETER_FIELDS = [
    "name",
    "value",
    "initial",
    "lower",
    "upper",
    "unit",
    "role",
    "distance_to_lower",
    "distance_to_upper",
    "normalized_bound_distance",
    "provenance",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_sha256(value: Any) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json_new(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2, ensure_ascii=True)
        stream.write("\n")


def write_csv_new(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("a", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writerows(rows)


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def same_selector_value(raw: str, expected: Any) -> bool:
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        try:
            return math.isclose(
                float(raw), float(expected), rel_tol=0.0, abs_tol=1.0e-12
            )
        except ValueError:
            return False
    if isinstance(expected, bool):
        return raw.strip().lower() == str(expected).lower()
    return raw == str(expected)


def row_matches(row: dict[str, str], selector: dict[str, Any]) -> bool:
    return all(
        key in row and same_selector_value(row[key], expected)
        for key, expected in selector.items()
    )


def scoring_role(row: dict[str, str], spec: dict[str, Any]) -> str:
    filter_spec = spec["scoring_filter"]
    column = filter_spec["column"]
    value = float(row[column])
    values = [float(item) for item in filter_spec["values"]]
    if filter_spec["operator"] == "equal":
        scored = any(math.isclose(value, item, abs_tol=1.0e-12) for item in values)
    elif filter_spec["operator"] == "not_in":
        scored = not any(
            math.isclose(value, item, abs_tol=1.0e-12) for item in values
        )
    else:
        raise ValueError(f"unsupported scoring operator: {filter_spec['operator']}")
    if scored:
        return "scored"
    if math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1.0e-12):
        return "zero_vds_invariant"
    if math.isclose(value, 0.01, rel_tol=0.0, abs_tol=1.0e-12):
        return "repeated_low_vds_audit"
    raise ValueError(f"unclassified unscored row for {spec['curve_id']}: {value}")


def normalize_source_row(
    row: dict[str, str],
    source_row_number: int,
    local_index: int,
    spec: dict[str, Any],
    registry_row: dict[str, str],
) -> dict[str, Any]:
    topology = spec["topology"]
    if topology == "single_bottom_gate":
        vbg_v = float(row["vgs_v"])
        vtg_v = 0.0
    elif topology == "symmetric_dual_gate":
        vbg_v = float(row["vbg_v"])
        vtg_v = float(row["vtg_v"])
    else:
        raise ValueError(f"unsupported topology: {topology}")
    vds_column = (
        "external_vds_v" if "external_vds_v" in row else "vds_v"
    )
    current_column = (
        "external_drain_current_a_per_cm"
        if "external_drain_current_a_per_cm" in row
        else "drain_current_a_per_cm"
    )
    vds_v = float(row[vds_column])
    if vds_v < -1.0e-12:
        raise ValueError("formal M00 source row has negative VDS")
    if spec["kind"] == "transfer":
        primary_axis_v = vbg_v if topology == "single_bottom_gate" else float(
            row.get("primary_gate_v", row["vtg_v"])
        )
    else:
        primary_axis_v = vds_v
    canonical_row = {key: row[key] for key in sorted(row)}
    return {
        "row_uid": f"{spec['curve_id']}:{local_index:03d}",
        "curve_id": spec["curve_id"],
        "dataset_id": spec["dataset_id"],
        "split": spec["split"],
        "kind": spec["kind"],
        "topology": topology,
        "source_path": registry_row["path"],
        "source_row_number": source_row_number,
        "source_row_sha256": canonical_sha256(canonical_row),
        "selection_role": scoring_role(row, spec),
        "optimizer_input": spec["split"] == "train"
        and scoring_role(row, spec) == "scored",
        "vbg_v": vbg_v,
        "vtg_v": vtg_v,
        "vds_v": max(vds_v, 0.0),
        "primary_axis_v": primary_axis_v,
        "target_current_a_per_cm": abs(float(row[current_column])),
        "w_um": float(spec["w_um"]),
        "l_um": float(spec["l_um"]),
        "temperature_k": float(spec["temperature_k"]),
    }


def load_curve(
    spec: dict[str, Any], registry: dict[str, dict[str, str]]
) -> list[dict[str, Any]]:
    registry_row = registry[spec["dataset_id"]]
    source_path = ROOT / registry_row["path"]
    selected: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        for source_row_number, row in enumerate(reader, start=2):
            if row_matches(row, spec["selector"]):
                selected.append(
                    normalize_source_row(
                        row, source_row_number, len(selected), spec, registry_row
                    )
                )
    scored_count = sum(row["selection_role"] == "scored" for row in selected)
    if len(selected) != int(spec["point_count"]):
        raise ValueError(
            f"{spec['curve_id']} selected {len(selected)} rows, "
            f"expected {spec['point_count']}"
        )
    if scored_count != int(spec["scored_point_count"]):
        raise ValueError(
            f"{spec['curve_id']} selected {scored_count} scored rows, "
            f"expected {spec['scored_point_count']}"
        )
    return selected


def parameter_dict(config: dict[str, Any], values: np.ndarray) -> dict[str, float]:
    return {
        item["name"]: float(value)
        for item, value in zip(config["parameter_contract"], values, strict=True)
    }


def softplus(values: np.ndarray, scale: float) -> np.ndarray:
    normalized = np.clip(values / scale, -60.0, 60.0)
    return scale * np.log1p(np.exp(normalized))


def evaluate_kernel(
    values: np.ndarray, points: list[dict[str, Any]], config: dict[str, Any]
) -> np.ndarray:
    parameters = parameter_dict(config, values)
    vbg = np.asarray([float(row["vbg_v"]) for row in points], dtype=float)
    vtg = np.asarray([float(row["vtg_v"]) for row in points], dtype=float)
    vds = np.asarray([float(row["vds_v"]) for row in points], dtype=float)
    lengths = np.asarray([float(row["l_um"]) for row in points], dtype=float)
    dual = np.asarray(
        [row["topology"] == "symmetric_dual_gate" for row in points], dtype=bool
    )
    control = np.where(
        dual, parameters["eta_dg"] * (vtg + vbg), vbg
    )
    topology_vth = np.where(
        dual, parameters["vth_dual_v"], parameters["vth_single_v"]
    )
    reference_length = float(config["reference_kernel"]["reference_length_um"])
    threshold = topology_vth + parameters["length_vth_slope_v"] * np.log(
        lengths / reference_length
    )
    source_charge = softplus(
        control - threshold, parameters["softplus_scale_v"]
    )
    drain_charge = softplus(
        control
        - threshold
        - parameters["drain_coupling"] * np.abs(vds),
        parameters["softplus_scale_v"],
    )
    current = (
        10.0 ** parameters["log_beta"]
        * (reference_length / lengths) ** parameters["length_exponent"]
        * (
            source_charge ** parameters["transport_exponent"]
            - drain_charge ** parameters["transport_exponent"]
        )
        * (1.0 + parameters["lambda_per_v"] * np.abs(vds))
        + 10.0 ** parameters["log_gmin"] * np.abs(vds)
    )
    return np.sign(vds) * current


def objective_residuals(
    values: np.ndarray,
    training_curves: list[list[dict[str, Any]]],
    config: dict[str, Any],
) -> np.ndarray:
    floor = float(config["optimization_contract"]["current_floor_a_per_cm"])
    blocks: list[np.ndarray] = []
    for curve in training_curves:
        scored = [row for row in curve if row["selection_role"] == "scored"]
        target = np.asarray(
            [float(row["target_current_a_per_cm"]) for row in scored], dtype=float
        )
        model = evaluate_kernel(values, scored, config)
        count = len(scored)
        linear = (model - target) / max(float(np.max(np.abs(target))), floor)
        logarithmic = np.log10(np.maximum(np.abs(model), floor)) - np.log10(
            np.maximum(np.abs(target), floor)
        )
        block_scale = math.sqrt(0.5 / count)
        blocks.extend((linear * block_scale, logarithmic * block_scale))
    return np.concatenate(blocks)


def interpolate(xs: list[float], ys: list[float], target: float) -> float | None:
    for x_value, y_value in zip(xs, ys, strict=True):
        if math.isclose(x_value, target, rel_tol=0.0, abs_tol=1.0e-12):
            return y_value
    for index in range(len(xs) - 1):
        if xs[index] < target < xs[index + 1]:
            return ys[index] + (
                (target - xs[index]) * (ys[index + 1] - ys[index])
                / (xs[index + 1] - xs[index])
            )
    return None


def extract_transfer_proxy(
    voltages: list[float], currents: list[float]
) -> dict[str, float] | None:
    ordered = sorted(zip(voltages, currents, strict=True))
    xs = [float(item[0]) for item in ordered]
    ys = [max(abs(float(item[1])), 1.0e-300) for item in ordered]
    bracket = next(
        (
            index
            for index in range(len(ys) - 1)
            if ys[index] <= VTH_CRITERION_A_PER_CM <= ys[index + 1]
        ),
        None,
    )
    if bracket is None:
        return None
    vth = xs[bracket] + (
        (math.log10(VTH_CRITERION_A_PER_CM) - math.log10(ys[bracket]))
        * (xs[bracket + 1] - xs[bracket])
        / (math.log10(ys[bracket + 1]) - math.log10(ys[bracket]))
    )
    gm_x = xs[1:-1]
    gm_y = [
        (ys[index + 1] - ys[index - 1]) / (xs[index + 1] - xs[index - 1])
        for index in range(1, len(xs) - 1)
    ]
    gm_voltage = vth + GM_OVERDRIVE_V
    gm = interpolate(gm_x, gm_y, gm_voltage)
    if gm is None:
        return None
    return {"vth_proxy_v": vth, "gm_proxy_a_per_cm_v": gm}


def is_nondecreasing(values: list[float]) -> bool:
    return all(
        right >= left - max(1.0e-30, 1.0e-12 * max(abs(left), abs(right)))
        for left, right in zip(values, values[1:])
    )


def manifest_row(point: dict[str, Any]) -> dict[str, Any]:
    return {field: point[field] for field in MANIFEST_FIELDS}


def prediction_and_metrics(
    curves: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    values: np.ndarray,
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, dict[str, float]]]:
    floor = float(config["optimization_contract"]["current_floor_a_per_cm"])
    acceptance = config["acceptance"]
    prediction_rows: list[dict[str, Any]] = []
    metric_rows: list[dict[str, Any]] = []
    aggregate_inputs: dict[str, dict[str, list[float]]] = {
        "train": {"linear": [], "log": []},
        "holdout": {"linear": [], "log": []},
    }
    for spec, curve in curves:
        model_all = evaluate_kernel(values, curve, config)
        scored_pairs = [
            (point, float(model))
            for point, model in zip(curve, model_all, strict=True)
            if point["selection_role"] == "scored"
        ]
        target = [float(point["target_current_a_per_cm"]) for point, _ in scored_pairs]
        model = [value for _, value in scored_pairs]
        normalization = max(max(abs(value) for value in target), floor)
        linear_residuals = [
            (model_value - target_value) / normalization
            for model_value, target_value in zip(model, target, strict=True)
        ]
        log_residuals = [
            math.log10(max(abs(model_value), floor))
            - math.log10(max(abs(target_value), floor))
            for model_value, target_value in zip(model, target, strict=True)
        ]
        linear_nrmse = math.sqrt(
            sum(value * value for value in linear_residuals) / len(linear_residuals)
        )
        log_rmse = math.sqrt(
            sum(value * value for value in log_residuals) / len(log_residuals)
        )
        split = spec["split"]
        aggregate_inputs[split]["linear"].append(linear_nrmse)
        aggregate_inputs[split]["log"].append(log_rmse)

        point_residuals = {
            point["row_uid"]: (
                (model_value - float(point["target_current_a_per_cm"]))
                / normalization,
                math.log10(max(abs(model_value), floor))
                - math.log10(
                    max(abs(float(point["target_current_a_per_cm"])), floor)
                ),
            )
            for point, model_value in zip(curve, model_all, strict=True)
        }
        for point, model_value in zip(curve, model_all, strict=True):
            linear_value, log_value = point_residuals[point["row_uid"]]
            prediction_rows.append(
                {
                    **manifest_row(point),
                    "model_current_a_per_cm": float(model_value),
                    "current_error_a_per_cm": float(model_value)
                    - float(point["target_current_a_per_cm"]),
                    "linear_normalized_residual": linear_value,
                    "log_residual_dec": log_value,
                }
            )

        ordered_prediction = [
            float(model_value)
            for _, model_value in sorted(
                zip(curve, model_all, strict=True),
                key=lambda pair: float(pair[0]["primary_axis_v"]),
            )
        ]
        monotonic = is_nondecreasing(ordered_prediction)
        target_proxy: dict[str, float] | None = None
        model_proxy: dict[str, float] | None = None
        if spec["kind"] == "transfer":
            target_proxy = extract_transfer_proxy(
                [float(point["primary_axis_v"]) for point, _ in scored_pairs], target
            )
            model_proxy = extract_transfer_proxy(
                [float(point["primary_axis_v"]) for point, _ in scored_pairs], model
            )
        vth_error = (
            abs(model_proxy["vth_proxy_v"] - target_proxy["vth_proxy_v"])
            if target_proxy is not None and model_proxy is not None
            else None
        )
        gm_error = (
            abs(
                model_proxy["gm_proxy_a_per_cm_v"]
                - target_proxy["gm_proxy_a_per_cm_v"]
            )
            / max(abs(target_proxy["gm_proxy_a_per_cm_v"]), 1.0e-300)
            if target_proxy is not None and model_proxy is not None
            else None
        )
        prefix = "training" if split == "train" else "holdout"
        curve_pass = (
            linear_nrmse
            <= float(acceptance[f"maximum_{prefix}_per_curve_linear_nrmse"])
            and log_rmse
            <= float(acceptance[f"maximum_{prefix}_per_curve_log_rmse_dec"])
            and monotonic
        )
        if split == "holdout" and spec["kind"] == "transfer":
            curve_pass = (
                curve_pass
                and vth_error is not None
                and gm_error is not None
                and vth_error
                <= float(acceptance["maximum_holdout_vth_absolute_error_v"])
                and gm_error
                <= float(acceptance["maximum_holdout_gm_relative_error"])
            )
        metric_rows.append(
            {
                "curve_id": spec["curve_id"],
                "dataset_id": spec["dataset_id"],
                "split": split,
                "kind": spec["kind"],
                "topology": spec["topology"],
                "point_count": len(curve),
                "scored_point_count": len(scored_pairs),
                "linear_nrmse": linear_nrmse,
                "log_rmse_dec": log_rmse,
                "maximum_abs_current_error_a_per_cm": max(
                    abs(model_value - target_value)
                    for model_value, target_value in zip(model, target, strict=True)
                ),
                "maximum_target_current_a_per_cm": max(abs(value) for value in target),
                "target_vth_proxy_v": ""
                if target_proxy is None
                else target_proxy["vth_proxy_v"],
                "model_vth_proxy_v": ""
                if model_proxy is None
                else model_proxy["vth_proxy_v"],
                "vth_absolute_error_v": "" if vth_error is None else vth_error,
                "target_gm_proxy_a_per_cm_v": ""
                if target_proxy is None
                else target_proxy["gm_proxy_a_per_cm_v"],
                "model_gm_proxy_a_per_cm_v": ""
                if model_proxy is None
                else model_proxy["gm_proxy_a_per_cm_v"],
                "gm_relative_error": "" if gm_error is None else gm_error,
                "sampled_prediction_monotonic": monotonic,
                "curve_acceptance_status": "PASS" if curve_pass else "FAIL",
            }
        )
    aggregate = {
        split: {
            key: math.sqrt(sum(value * value for value in values) / len(values))
            for key, values in components.items()
        }
        for split, components in aggregate_inputs.items()
    }
    return prediction_rows, metric_rows, aggregate


def parameter_rows(
    config: dict[str, Any], values: np.ndarray
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for contract, value in zip(config["parameter_contract"], values, strict=True):
        lower = float(contract["lower"])
        upper = float(contract["upper"])
        lower_distance = float(value) - lower
        upper_distance = upper - float(value)
        rows.append(
            {
                "name": contract["name"],
                "value": float(value),
                "initial": contract["initial"],
                "lower": lower,
                "upper": upper,
                "unit": contract["unit"],
                "role": contract["role"],
                "distance_to_lower": lower_distance,
                "distance_to_upper": upper_distance,
                "normalized_bound_distance": min(lower_distance, upper_distance)
                / (upper - lower),
                "provenance": "deterministic M00 teaching-surrogate fit; not a physical parameter",
            }
        )
    return rows


def prepare_matplotlib() -> None:
    cache_root = ROOT / ".cache"
    os.environ.setdefault("MPLCONFIGDIR", str(cache_root / "matplotlib"))
    os.environ.setdefault("XDG_CACHE_HOME", str(cache_root))


def generate_fit_figure(
    path: Path, predictions: list[dict[str, Any]], metric_rows: list[dict[str, Any]]
) -> None:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    curve_order = [row["curve_id"] for row in metric_rows]
    palette = plt.get_cmap("tab20")
    figure, axes = plt.subplots(1, 2, figsize=(12.0, 5.2), constrained_layout=True)
    for index, curve_id in enumerate(curve_order):
        rows = [row for row in predictions if row["curve_id"] == curve_id]
        scored = [row for row in rows if row["selection_role"] == "scored"]
        if not scored:
            continue
        split = scored[0]["split"]
        kind = scored[0]["kind"]
        axis = axes[0] if kind == "transfer" else axes[1]
        color = palette(index % 20)
        linestyle = "--" if split == "holdout" else "-"
        x_values = [float(row["primary_axis_v"]) for row in scored]
        target = [float(row["target_current_a_per_cm"]) for row in scored]
        model = [float(row["model_current_a_per_cm"]) for row in scored]
        label = curve_id.replace("train_", "T ").replace("holdout_", "H ")
        axis.plot(x_values, model, color=color, linestyle=linestyle, linewidth=1.5, label=label)
        axis.scatter(x_values, target, color=color, s=14, marker="o", facecolors="none", linewidths=0.8)
    axes[0].set_yscale("log")
    axes[0].set_ylim(bottom=1.0e-22)
    axes[0].set_xlabel("Gate voltage (V)")
    axes[0].set_ylabel("Drain current per width (A/cm)")
    axes[0].set_title("Transfer curves: target markers, model lines")
    axes[0].grid(True, which="both", alpha=0.25)
    axes[1].set_xlabel("Drain voltage (V)")
    axes[1].set_ylabel("Drain current per width (A/cm)")
    axes[1].set_title("Output curves: target markers, model lines")
    axes[1].grid(True, alpha=0.25)
    for axis in axes:
        axis.legend(fontsize=6.5, ncol=1, loc="best", frameon=False)
    figure.suptitle("M00 IGZO teaching surrogate fit (T=train, H=holdout)", fontsize=11)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)


def generate_residual_figure(
    path: Path, metric_rows: list[dict[str, Any]], config: dict[str, Any]
) -> None:
    prepare_matplotlib()
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    acceptance = config["acceptance"]
    labels = [row["curve_id"].replace("train_", "T:").replace("holdout_", "H:") for row in metric_rows]
    x_values = np.arange(len(metric_rows))
    colors = ["#277da1" if row["split"] == "train" else "#f8961e" for row in metric_rows]
    figure, axes = plt.subplots(2, 1, figsize=(12.0, 7.2), sharex=True, constrained_layout=True)
    axes[0].bar(x_values, [float(row["linear_nrmse"]) for row in metric_rows], color=colors, width=0.72)
    axes[1].bar(x_values, [float(row["log_rmse_dec"]) for row in metric_rows], color=colors, width=0.72)
    axes[0].axhline(float(acceptance["maximum_training_per_curve_linear_nrmse"]), color="#277da1", linestyle=":", linewidth=1.2)
    axes[0].axhline(float(acceptance["maximum_holdout_per_curve_linear_nrmse"]), color="#f8961e", linestyle=":", linewidth=1.2)
    axes[1].axhline(float(acceptance["maximum_training_per_curve_log_rmse_dec"]), color="#277da1", linestyle=":", linewidth=1.2)
    axes[1].axhline(float(acceptance["maximum_holdout_per_curve_log_rmse_dec"]), color="#f8961e", linestyle=":", linewidth=1.2)
    axes[0].set_ylabel("Linear NRMSE")
    axes[1].set_ylabel("Log RMSE (dec)")
    axes[1].set_xticks(x_values, labels, rotation=55, ha="right", fontsize=7)
    axes[0].set_title("Per-curve residual gates: blue training, orange holdout")
    for axis in axes:
        axis.grid(True, axis="y", alpha=0.25)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)


def generate_ngspice_candidate(path: Path, parameters: dict[str, float]) -> None:
    content = f"""* IGZO-only M00 behavioral translation candidate R01
* M01_EXECUTION_REQUIRED: not executed or simulator-validated in M00.
* This is not native HSPICE Level 61 and is not a physical parameter card.
* Formal fitted domain: VDS=0..0.2 V, L=8..12 um, 300 K, ideal contacts.
.subckt IGZO_DG_BEHAVIORAL_R01 D TG BG S params: WUM=60 LUM=10
.param M00_LOGBETA={parameters['log_beta']:.16g}
.param M00_VTHDG={parameters['vth_dual_v']:.16g}
.param M00_ETA={parameters['eta_dg']:.16g}
.param M00_SOFT={parameters['softplus_scale_v']:.16g}
.param M00_GAMMA={parameters['transport_exponent']:.16g}
.param M00_KD={parameters['drain_coupling']:.16g}
.param M00_LAMBDA={parameters['lambda_per_v']:.16g}
.param M00_LOGGMIN={parameters['log_gmin']:.16g}
.param M00_PL={parameters['length_exponent']:.16g}
.param M00_KVTHL={parameters['length_vth_slope_v']:.16g}
.func M00_Q(x,s) {{s*ln(1+exp(limit(x/s,-60,60)))}}
BIDS D S I={{sgn(V(D,S))*WUM*1e-4*(pow(10,M00_LOGBETA)*pow(10/LUM,M00_PL)*(pow(M00_Q(M00_ETA*(V(TG,S)+V(BG,S))-M00_VTHDG-M00_KVTHL*ln(LUM/10),M00_SOFT),M00_GAMMA)-pow(M00_Q(M00_ETA*(V(TG,S)+V(BG,S))-M00_VTHDG-M00_KVTHL*ln(LUM/10)-M00_KD*abs(V(D,S)),M00_SOFT),M00_GAMMA))*(1+M00_LAMBDA*abs(V(D,S)))+pow(10,M00_LOGGMIN)*abs(V(D,S)))}}
.ends IGZO_DG_BEHAVIORAL_R01
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="ascii") as stream:
        stream.write(content)


def generate_aimspice_candidate(path: Path, parameters: dict[str, float]) -> None:
    content = f"""* IGZO-only AIM-Spice LEVEL=15 candidate R01
* M01_EXECUTION_REQUIRED: syntax and curves are not executed in M00.
* Native LEVEL=15 is not equation-identical to the M00 reference kernel.
* Physical Al2O3 thickness is 30 nm; TOX=10n is an effective model value.
.model IGZO_N_L15_R01 NMOS LEVEL=15 VTO={parameters['vth_dual_v']:.16g} TOX=10n EPSI=6.8 MUBAND=3.55e-3 RD=0 RS=0 LAMBDA={parameters['lambda_per_v']:.16g} VFB=0 ALPHASAT=0.6 KASAT=0.006 DEF0=0.6 DELTA=5 EL=0.35 EMU=0.06 GAMMA=0.4 IOL=1e-14 GMIN=1e23 SIGMA0=1e-14 V0=0.12 VAA=7.5e3 VDSL=7 VGSL=7 VMIN=0.3 TNOM=27
.subckt IGZO_DG_LEVEL15_R01 D TG BG S params: W=60u L=10u
EGEFF GEFF S VALUE={{{parameters['eta_dg']:.16g}*(V(TG,S)+V(BG,S))}}
MCORE D GEFF S S IGZO_N_L15_R01 W={{W}} L={{L}}
.ends IGZO_DG_LEVEL15_R01
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="ascii") as stream:
        stream.write(content)


def preflight(
    config: dict[str, Any], config_path: Path
) -> tuple[dict[str, Any], list[dict[str, str]], dict[str, dict[str, str]]]:
    outputs = config["outputs"]
    future_paths = [ROOT / value for key, value in outputs.items() if key != "contract_report"]
    run_directory = ROOT / outputs["run_directory"]
    existing = [str(path.relative_to(ROOT)) for path in future_paths if path.exists()]
    if run_directory.exists() and str(run_directory.relative_to(ROOT)) not in existing:
        existing.append(str(run_directory.relative_to(ROOT)))
    if existing:
        raise FileExistsError(f"formal M00 outputs already exist: {existing}")
    contract_path = ROOT / outputs["contract_report"]
    contract = load_json(contract_path)
    if contract.get("status") != "PASS" or contract.get("fit_status") != "NOT_RUN_BY_CONTRACT_CHECK":
        raise ValueError("M00 static contract is not a clean PASS")
    if contract.get("config", {}).get("sha256") != sha256(config_path):
        raise ValueError("M00 config changed after the static contract")
    registry_path = ROOT / config["dataset_contract"]["registry"]
    if contract.get("registry", {}).get("sha256") != sha256(registry_path):
        raise ValueError("M00 dataset registry changed after the static contract")
    with registry_path.open("r", encoding="utf-8", newline="") as stream:
        registry_rows = list(csv.DictReader(stream))
    registry = {row["dataset_id"]: row for row in registry_rows}
    for row in registry_rows:
        source = ROOT / row["path"]
        if sha256(source) != row["sha256"]:
            raise ValueError(f"registered source hash mismatch: {row['dataset_id']}")
    return contract, registry_rows, registry


def artifact_entry(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256(path),
        "bytes": path.stat().st_size,
    }


def run_formal_fit(config_path: Path) -> dict[str, Any]:
    start_utc = utc_now()
    wall_start = time.perf_counter()
    config = load_json(config_path)
    contract, registry_rows, registry = preflight(config, config_path)
    outputs = {key: ROOT / value for key, value in config["outputs"].items()}
    run_directory = outputs["run_directory"]
    run_directory.mkdir(parents=True, exist_ok=False)

    train_specs = [item for item in config["scored_curves"] if item["split"] == "train"]
    holdout_specs = [item for item in config["scored_curves"] if item["split"] == "holdout"]
    train_load_utc = utc_now()
    train_curves = [(spec, load_curve(spec, registry)) for spec in train_specs]
    train_scored = [
        row
        for _, curve in train_curves
        for row in curve
        if row["selection_role"] == "scored"
    ]

    snapshot = {
        "case_id": config["case_id"],
        "stage": "M00",
        "formal_run_revision": 1,
        "formal_run_ordinal": 1,
        "start_utc": start_utc,
        "training_rows_loaded_utc": train_load_utc,
        "holdout_target_rows_loaded_before_optimizer": False,
        "command": "make m00-compact-model-fit",
        "config": artifact_entry(config_path),
        "contract_report": artifact_entry(outputs["contract_report"]),
        "dataset_registry": artifact_entry(ROOT / config["dataset_contract"]["registry"]),
        "runner": artifact_entry(Path(__file__).resolve()),
        "independent_checker": artifact_entry(ROOT / "scripts" / "check_m00_compact_model_fit.py"),
        "project_config": artifact_entry(ROOT / "config" / "project.json"),
        "experiments_config": artifact_entry(ROOT / "config" / "experiments.json"),
        "registered_sources": [
            {
                "dataset_id": row["dataset_id"],
                "path": row["path"],
                "sha256": row["sha256"],
                "row_count": int(row["row_count"]),
            }
            for row in registry_rows
        ],
        "optimizer_input": {
            "curve_ids": [spec["curve_id"] for spec in train_specs],
            "curve_count": len(train_specs),
            "scored_point_count": len(train_scored),
            "canonical_sha256": canonical_sha256(train_scored),
        },
        "locked_holdout": {
            "curve_ids": [spec["curve_id"] for spec in holdout_specs],
            "curve_count": len(holdout_specs),
            "planned_scored_point_count": sum(int(spec["scored_point_count"]) for spec in holdout_specs),
            "targets_loaded_before_optimizer": False,
        },
        "parameter_contract": config["parameter_contract"],
        "optimization_contract": config["optimization_contract"],
        "acceptance": config["acceptance"],
        "python": sys.version,
        "platform": platform.platform(),
        "numpy_version": np.__version__,
        "scipy_version": scipy_version,
        "simulator_execution": {
            "tcad": False,
            "ngspice": False,
            "aimspice": False,
            "circuit": False,
        },
    }
    write_json_new(outputs["input_snapshot"], snapshot)
    write_csv_new(
        outputs["selected_rows_manifest"],
        MANIFEST_FIELDS,
        [manifest_row(row) for _, curve in train_curves for row in curve],
    )

    parameters = config["parameter_contract"]
    initial = np.asarray([float(item["initial"]) for item in parameters])
    lower = np.asarray([float(item["lower"]) for item in parameters])
    upper = np.asarray([float(item["upper"]) for item in parameters])
    optimizer_input = [curve for _, curve in train_curves]
    initial_residual = objective_residuals(initial, optimizer_input, config)
    optimize_start_utc = utc_now()
    optimize_wall_start = time.perf_counter()
    result = least_squares(
        objective_residuals,
        initial,
        args=(optimizer_input, config),
        jac="2-point",
        bounds=(lower, upper),
        method="trf",
        loss="linear",
        xtol=float(config["optimization_contract"]["xtol"]),
        ftol=float(config["optimization_contract"]["ftol"]),
        gtol=float(config["optimization_contract"]["gtol"]),
        max_nfev=int(config["optimization_contract"]["max_nfev"]),
    )
    optimize_seconds = time.perf_counter() - optimize_wall_start
    optimize_end_utc = utc_now()
    fitted_values = np.asarray(result.x, dtype=float)
    optimizer_log = {
        "case_id": config["case_id"],
        "backend": "scipy.optimize.least_squares",
        "scipy_version": scipy_version,
        "method": "trf",
        "jacobian": "2-point finite difference",
        "loss": "linear",
        "start_utc": optimize_start_utc,
        "end_utc": optimize_end_utc,
        "wall_seconds": optimize_seconds,
        "success": bool(result.success),
        "status_code": int(result.status),
        "message": str(result.message),
        "nfev": int(result.nfev),
        "njev": None if result.njev is None else int(result.njev),
        "initial_cost": 0.5 * float(np.dot(initial_residual, initial_residual)),
        "final_cost": float(result.cost),
        "optimality": float(result.optimality),
        "active_mask": [int(item) for item in result.active_mask],
        "initial_vector": [float(item) for item in initial],
        "fitted_vector": [float(item) for item in fitted_values],
        "objective_curve_ids": [spec["curve_id"] for spec in train_specs],
        "objective_curve_count": len(train_specs),
        "objective_scored_point_count": len(train_scored),
        "objective_residual_count": int(result.fun.size),
        "objective_input_sha256": canonical_sha256(train_scored),
        "holdout_curve_ids_in_objective": [],
        "holdout_targets_loaded_before_optimizer_termination": False,
        "random_seed_or_restart": "none",
        "tcad_or_spice_execution": False,
    }
    write_json_new(outputs["optimizer_log"], optimizer_log)

    holdout_load_utc = utc_now()
    holdout_curves = [(spec, load_curve(spec, registry)) for spec in holdout_specs]
    append_csv(
        outputs["selected_rows_manifest"],
        MANIFEST_FIELDS,
        [manifest_row(row) for _, curve in holdout_curves for row in curve],
    )
    curve_map = {spec["curve_id"]: (spec, curve) for spec, curve in [*train_curves, *holdout_curves]}
    ordered_curves = [curve_map[spec["curve_id"]] for spec in config["scored_curves"]]
    predictions, curve_metrics, aggregate = prediction_and_metrics(
        ordered_curves, fitted_values, config
    )
    params = parameter_dict(config, fitted_values)
    params_rows = parameter_rows(config, fitted_values)

    write_csv_new(outputs["predictions_csv"], PREDICTION_FIELDS, predictions)
    write_csv_new(outputs["curve_metrics_csv"], CURVE_METRIC_FIELDS, curve_metrics)
    write_csv_new(outputs["parameter_table_csv"], PARAMETER_FIELDS, params_rows)

    holdout_transfer = [
        row for row in curve_metrics if row["split"] == "holdout" and row["kind"] == "transfer"
    ]
    validity = {
        "model_id": config["reference_kernel"]["kernel_id"],
        "status": "M00_REFERENCE_KERNEL_RUNNER_EVIDENCE",
        "evidence_level": "E2 if the formal fit report passes; independent E3 check stored separately",
        "kernel": config["reference_kernel"],
        "parameters": params,
        "parameter_contract": config["parameter_contract"],
        "validity_domain": config["validity_domain"],
        "split_summary": config["split_summary"],
        "aggregate_metrics": aggregate,
        "vth_criterion_a_per_cm": VTH_CRITERION_A_PER_CM,
        "gm_evaluation_overdrive_v": GM_OVERDRIVE_V,
        "source_config": artifact_entry(config_path),
        "source_registry": artifact_entry(ROOT / config["dataset_contract"]["registry"]),
        "simulator_status": {
            "reference_python": "RUN_BY_M00",
            "ngspice": "CANDIDATE_ONLY_NOT_EXECUTED",
            "aimspice": "CANDIDATE_ONLY_NOT_EXECUTED",
            "tcad": "NOT_RUN",
            "circuit": "NOT_RUN",
        },
        "prohibited_claims": config["evidence_boundary"]["prohibited_claims"],
    }
    write_json_new(outputs["validity_json"], validity)
    generate_fit_figure(outputs["fit_figure_png"], predictions, curve_metrics)
    generate_residual_figure(outputs["residual_figure_png"], curve_metrics, config)

    acceptance = config["acceptance"]
    checks: list[dict[str, Any]] = []
    all_points = [row for _, curve in ordered_curves for row in curve]
    zero_predictions = [
        row for row in predictions if row["selection_role"] == "zero_vds_invariant"
    ]
    add_check(checks, "input:committed_static_contract_and_registered_hashes", contract["status"] == "PASS" and len(registry_rows) == 13, f"contract={contract['status']} registry={len(registry_rows)}")
    add_check(checks, "optimizer:training_only_holdout_isolation", optimizer_log["objective_curve_count"] == 9 and optimizer_log["objective_scored_point_count"] == 163 and not optimizer_log["holdout_curve_ids_in_objective"] and holdout_load_utc >= optimize_end_utc, f"train={optimizer_log['objective_curve_count']}/163 holdout_loaded={holdout_load_utc}")
    add_check(checks, "optimizer:deterministic_termination_success", bool(result.success), f"status={result.status} nfev={result.nfev} cost={result.cost:.9e}")
    add_check(checks, "optimizer:wall_time_budget", optimize_seconds <= float(config["optimization_contract"]["maximum_wall_seconds"]), f"seconds={optimize_seconds:.6f}")
    add_check(checks, "split:required_curves_and_scored_points", sum(spec["split"] == "train" for spec, _ in ordered_curves) == 9 and sum(spec["split"] == "holdout" for spec, _ in ordered_curves) == 4 and sum(row["selection_role"] == "scored" and row["split"] == "train" for row in all_points) == 163 and sum(row["selection_role"] == "scored" and row["split"] == "holdout" for row in all_points) == 70, f"curves=9/4 points=163/70")
    add_check(checks, "predictions:all_finite", all(math.isfinite(float(row["model_current_a_per_cm"])) for row in predictions), f"rows={len(predictions)}")
    add_check(checks, "predictions:nonnegative_for_nonnegative_vds", all(float(row["model_current_a_per_cm"]) >= -1.0e-30 for row in predictions if float(row["vds_v"]) >= 0.0), "formal VDS domain is nonnegative")
    max_zero = max(abs(float(row["model_current_a_per_cm"])) for row in zero_predictions)
    add_check(checks, "predictions:zero_vds_invariants", len(zero_predictions) == 7 and max_zero <= float(acceptance["maximum_zero_vds_abs_current_a_per_cm"]), f"count={len(zero_predictions)} maximum={max_zero:.6e}")
    add_check(checks, "predictions:sampled_transfer_and_output_monotonicity", all(row["sampled_prediction_monotonic"] in {True, "True"} for row in curve_metrics), f"curves={len(curve_metrics)}")
    min_bound_distance = min(float(row["normalized_bound_distance"]) for row in params_rows)
    add_check(checks, "parameters:all_strictly_inside_frozen_bounds", all(float(row["lower"]) < float(row["value"]) < float(row["upper"]) for row in params_rows), f"minimum_normalized_distance={min_bound_distance:.6e}")
    add_check(checks, "metrics:training_aggregate_linear", aggregate["train"]["linear"] <= float(acceptance["maximum_training_aggregate_linear_nrmse"]), f"value={aggregate['train']['linear']:.9e} limit={acceptance['maximum_training_aggregate_linear_nrmse']}")
    add_check(checks, "metrics:training_aggregate_log", aggregate["train"]["log"] <= float(acceptance["maximum_training_aggregate_log_rmse_dec"]), f"value={aggregate['train']['log']:.9e} limit={acceptance['maximum_training_aggregate_log_rmse_dec']}")
    add_check(checks, "metrics:holdout_aggregate_linear", aggregate["holdout"]["linear"] <= float(acceptance["maximum_holdout_aggregate_linear_nrmse"]), f"value={aggregate['holdout']['linear']:.9e} limit={acceptance['maximum_holdout_aggregate_linear_nrmse']}")
    add_check(checks, "metrics:holdout_aggregate_log", aggregate["holdout"]["log"] <= float(acceptance["maximum_holdout_aggregate_log_rmse_dec"]), f"value={aggregate['holdout']['log']:.9e} limit={acceptance['maximum_holdout_aggregate_log_rmse_dec']}")
    train_metric_rows = [row for row in curve_metrics if row["split"] == "train"]
    holdout_metric_rows = [row for row in curve_metrics if row["split"] == "holdout"]
    add_check(checks, "metrics:training_per_curve_linear_and_log", all(float(row["linear_nrmse"]) <= float(acceptance["maximum_training_per_curve_linear_nrmse"]) and float(row["log_rmse_dec"]) <= float(acceptance["maximum_training_per_curve_log_rmse_dec"]) for row in train_metric_rows), f"maximum={max(float(row['linear_nrmse']) for row in train_metric_rows):.6e}/{max(float(row['log_rmse_dec']) for row in train_metric_rows):.6e}")
    add_check(checks, "metrics:holdout_per_curve_linear_and_log", all(float(row["linear_nrmse"]) <= float(acceptance["maximum_holdout_per_curve_linear_nrmse"]) and float(row["log_rmse_dec"]) <= float(acceptance["maximum_holdout_per_curve_log_rmse_dec"]) for row in holdout_metric_rows), f"maximum={max(float(row['linear_nrmse']) for row in holdout_metric_rows):.6e}/{max(float(row['log_rmse_dec']) for row in holdout_metric_rows):.6e}")
    add_check(checks, "metrics:holdout_transfer_vth", len(holdout_transfer) == 2 and all(row["vth_absolute_error_v"] != "" and float(row["vth_absolute_error_v"]) <= float(acceptance["maximum_holdout_vth_absolute_error_v"]) for row in holdout_transfer), f"errors={[row['vth_absolute_error_v'] for row in holdout_transfer]}")
    add_check(checks, "metrics:holdout_transfer_gm", len(holdout_transfer) == 2 and all(row["gm_relative_error"] != "" and float(row["gm_relative_error"]) <= float(acceptance["maximum_holdout_gm_relative_error"]) for row in holdout_transfer), f"errors={[row['gm_relative_error'] for row in holdout_transfer]}")
    train_vds = {round(float(row["vds_v"]), 12) for row in predictions if row["split"] == "train" and row["selection_role"] == "scored"}
    holdout_vds = {round(float(row["vds_v"]), 12) for row in predictions if row["split"] == "holdout" and row["selection_role"] == "scored"}
    add_check(checks, "coverage:multiple_vds_in_training_and_holdout", len(train_vds) > 1 and len(holdout_vds) > 1, f"train={sorted(train_vds)} holdout={sorted(holdout_vds)}")
    add_check(checks, "reporting:separate_metrics_provenance_and_validity", len(curve_metrics) == 13 and len(params_rows) == 11 and validity["validity_domain"] == config["validity_domain"] and aggregate.keys() == {"train", "holdout"}, "curve metrics, parameter provenance and local domain persisted")
    add_check(checks, "audit:unscored_zero_and_low_vds_rows_retained", sum(row["selection_role"] == "zero_vds_invariant" for row in predictions) == 7 and sum(row["selection_role"] == "repeated_low_vds_audit" for row in predictions) == 7, "zero=7 repeated_low_vds=7")
    add_check(checks, "boundary:no_tcad_spice_or_circuit_execution", all(value is False for value in snapshot["simulator_execution"].values()) and optimizer_log["tcad_or_spice_execution"] is False, "reference Python kernel only")

    base_pass = all(item["status"] == "PASS" for item in checks)
    if base_pass:
        generate_ngspice_candidate(outputs["ngspice_candidate"], params)
        generate_aimspice_candidate(outputs["aimspice_candidate"], params)
        mapping = {
            "mapping_id": "IGZO_M00_TO_AIMSPICE_LEVEL15_R01",
            "status": "CANDIDATE_ONLY_M01_EXECUTION_REQUIRED",
            "reference_kernel_parameters": params,
            "direct_candidate_mapping": {
                "VTO": {"source": "vth_dual_v", "value": params["vth_dual_v"]},
                "LAMBDA": {"source": "lambda_per_v", "value": params["lambda_per_v"]},
                "dual_gate_control_weight": {"source": "eta_dg", "value": params["eta_dg"]},
            },
            "fixed_teaching_inputs": {
                "TOX_effective_nm": 10.0,
                "physical_Al2O3_nm": 30.0,
                "EPSI": 6.8,
                "MUBAND_m2_per_v_s": 3.55e-3,
            },
            "not_directly_mapped": [
                "log_beta",
                "vth_single_v",
                "softplus_scale_v",
                "transport_exponent",
                "drain_coupling",
                "log_gmin",
                "length_exponent",
                "length_vth_slope_v",
            ],
            "equation_identity_with_reference_kernel": False,
            "aimspice_executed": False,
            "ngspice_executed": False,
            "allowed_claim": "Unexecuted Level 15 mapping candidate for M01 only.",
        }
        write_json_new(outputs["aimspice_mapping"], mapping)
    candidate_paths = [
        outputs["ngspice_candidate"],
        outputs["aimspice_candidate"],
        outputs["aimspice_mapping"],
    ]
    add_check(checks, "routes:unexecuted_candidates_generated_only_after_numerical_pass", base_pass and all(path.is_file() for path in candidate_paths), f"base_pass={base_pass} candidates={sum(path.is_file() for path in candidate_paths)}/3")
    required_persisted = [
        outputs["input_snapshot"],
        outputs["selected_rows_manifest"],
        outputs["optimizer_log"],
        outputs["predictions_csv"],
        outputs["curve_metrics_csv"],
        outputs["parameter_table_csv"],
        outputs["validity_json"],
        outputs["fit_figure_png"],
        outputs["residual_figure_png"],
        *candidate_paths,
    ]
    add_check(checks, "artifacts:required_outputs_persisted_without_overwrite", all(path.is_file() and path.stat().st_size > 0 for path in required_persisted), f"files={sum(path.is_file() for path in required_persisted)}/{len(required_persisted)}")
    if len(checks) != EXPECTED_RUNNER_CHECK_COUNT:
        add_check(checks, "runner:registered_check_count", False, f"expected={EXPECTED_RUNNER_CHECK_COUNT} actual_before_guard={len(checks)}")

    failures = [item for item in checks if item["status"] == "FAIL"]
    artifact_paths = [path for path in required_persisted if path.is_file()]
    artifacts = {
        path.name: artifact_entry(path)
        for path in artifact_paths
    }
    report = {
        "status": "PASS" if not failures else "FAIL",
        "fit_status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": "M00",
        "evidence_level": "E2" if not failures else "E0",
        "formal_fit_run": True,
        "formal_fit_run_ordinal": 1,
        "independent_persisted_evidence_check_complete": False,
        "start_utc": start_utc,
        "end_utc": utc_now(),
        "wall_seconds": time.perf_counter() - wall_start,
        "optimizer": optimizer_log,
        "holdout_evaluation": {
            "loaded_after_optimizer_termination": holdout_load_utc >= optimize_end_utc,
            "load_utc": holdout_load_utc,
            "curve_ids": [spec["curve_id"] for spec in holdout_specs],
            "scored_point_count": sum(int(spec["scored_point_count"]) for spec in holdout_specs),
            "used_to_change_parameters_or_thresholds": False,
        },
        "split_summary": config["split_summary"],
        "aggregate_metrics": aggregate,
        "holdout_transfer_proxies": [
            {key: row[key] for key in (
                "curve_id", "target_vth_proxy_v", "model_vth_proxy_v", "vth_absolute_error_v",
                "target_gm_proxy_a_per_cm_v", "model_gm_proxy_a_per_cm_v", "gm_relative_error",
            )}
            for row in holdout_transfer
        ],
        "parameters": params,
        "minimum_normalized_parameter_bound_distance": min_bound_distance,
        "checks": checks,
        "failures": failures,
        "artifacts": artifacts,
        "simulator_status": {
            "reference_python_kernel": "RUN",
            "tcad": "NOT_RUN",
            "ngspice": "CANDIDATE_GENERATED_NOT_EXECUTED" if base_pass else "NOT_RUN",
            "aimspice": "CANDIDATE_GENERATED_NOT_EXECUTED" if base_pass else "NOT_RUN",
            "circuit": "NOT_RUN",
        },
        "audit_and_exclusion_contract": config["audit_and_exclusion_contract"],
        "validity_domain": config["validity_domain"],
        "allowed_claim": config["evidence_boundary"]["future_m00_pass_allowed_claim"],
        "prohibited_claims": config["evidence_boundary"]["prohibited_claims"],
        "next_gate": "Run the independent persisted-evidence checker only if this report passes; M01 and downstream remain closed.",
    }
    write_json_new(outputs["fit_report"], report)
    return report


def self_test() -> int:
    config = {
        "reference_kernel": {"reference_length_um": 10.0},
        "parameter_contract": [
            {"name": name}
            for name in (
                "log_beta", "vth_single_v", "vth_dual_v", "eta_dg",
                "softplus_scale_v", "transport_exponent", "drain_coupling",
                "lambda_per_v", "log_gmin", "length_exponent",
                "length_vth_slope_v",
            )
        ],
        "optimization_contract": {"current_floor_a_per_cm": 1.0e-20},
    }
    values = np.asarray([-3.0, 0.2, 0.15, 0.5, 0.026, 2.0, 1.0, 0.1, -18.0, 0.62, -0.03])
    base = {
        "vbg_v": 0.0, "vtg_v": 0.5, "l_um": 10.0,
        "topology": "symmetric_dual_gate", "target_current_a_per_cm": 1.0,
        "selection_role": "scored",
    }
    output_points = [{**base, "vds_v": value} for value in (0.0, 0.01, 0.05, 0.1, 0.2)]
    output = evaluate_kernel(values, output_points, config)
    transfer_points = [{**base, "vtg_v": value, "vds_v": 0.01} for value in (-0.5, 0.0, 0.5, 1.0)]
    transfer = evaluate_kernel(values, transfer_points, config)
    scipy_probe = least_squares(lambda value: value - np.asarray([1.0, 2.0]), np.zeros(2), method="trf")
    passed = (
        output[0] == 0.0
        and np.all(np.isfinite(output))
        and np.all(output >= 0.0)
        and is_nondecreasing([float(item) for item in output])
        and is_nondecreasing([float(item) for item in transfer])
        and scipy_probe.success
        and np.allclose(scipy_probe.x, [1.0, 2.0])
    )
    print(f"M00_COMPACT_MODEL_SYNTHETIC_SELF_TEST_{'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()
    if args.self_test:
        return self_test()
    try:
        report = run_formal_fit(args.config.resolve())
    except Exception as error:  # noqa: BLE001
        print(f"M00_COMPACT_MODEL_FIT_ERROR {type(error).__name__}: {error}", file=sys.stderr)
        return 1
    print(
        f"M00_COMPACT_MODEL_FIT_{report['status']} "
        f"checks={sum(item['status'] == 'PASS' for item in report['checks'])}/"
        f"{len(report['checks'])} train_linear={report['aggregate_metrics']['train']['linear']:.6e} "
        f"train_log={report['aggregate_metrics']['train']['log']:.6e} "
        f"holdout_linear={report['aggregate_metrics']['holdout']['linear']:.6e} "
        f"holdout_log={report['aggregate_metrics']['holdout']['log']:.6e}"
    )
    for failure in report["failures"]:
        print(f"M00_COMPACT_MODEL_FIT_GATE_FAIL {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
