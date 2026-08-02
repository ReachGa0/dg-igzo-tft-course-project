#!/usr/bin/env python3
"""Independently validate persisted M00 compact-model fit evidence."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "compact_m00_input_validation.json"
EXPECTED_CHECK_COUNT = 20
EXPECTED_RUNNER_CHECK_COUNT = 24
VTH_CRITERION_A_PER_CM = 1.0e-5
GM_OVERDRIVE_V = 0.2


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


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


def close(
    left: float, right: float, *, rel_tol: float = 1.0e-10,
    abs_tol: float = 1.0e-25,
) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


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


def classify_row(row: dict[str, str], spec: dict[str, Any]) -> str:
    filter_spec = spec["scoring_filter"]
    value = float(row[filter_spec["column"]])
    candidates = [float(item) for item in filter_spec["values"]]
    equal = any(
        math.isclose(value, candidate, rel_tol=0.0, abs_tol=1.0e-12)
        for candidate in candidates
    )
    if (filter_spec["operator"] == "equal" and equal) or (
        filter_spec["operator"] == "not_in" and not equal
    ):
        return "scored"
    if math.isclose(value, 0.0, rel_tol=0.0, abs_tol=1.0e-12):
        return "zero_vds_invariant"
    if math.isclose(value, 0.01, rel_tol=0.0, abs_tol=1.0e-12):
        return "repeated_low_vds_audit"
    raise ValueError(f"cannot classify {spec['curve_id']} row at {value}")


def normalize_source_row(
    row: dict[str, str], source_row_number: int, local_index: int,
    spec: dict[str, Any], source_path: str,
) -> dict[str, Any]:
    topology = spec["topology"]
    if topology == "single_bottom_gate":
        vbg_v = float(row["vgs_v"])
        vtg_v = 0.0
    else:
        vbg_v = float(row["vbg_v"])
        vtg_v = float(row["vtg_v"])
    vds_column = "external_vds_v" if "external_vds_v" in row else "vds_v"
    current_column = (
        "external_drain_current_a_per_cm"
        if "external_drain_current_a_per_cm" in row
        else "drain_current_a_per_cm"
    )
    vds_v = max(float(row[vds_column]), 0.0)
    primary_axis = (
        (vbg_v if topology == "single_bottom_gate" else float(row.get("primary_gate_v", row["vtg_v"])))
        if spec["kind"] == "transfer"
        else vds_v
    )
    role = classify_row(row, spec)
    canonical_row = {key: row[key] for key in sorted(row)}
    return {
        "row_uid": f"{spec['curve_id']}:{local_index:03d}",
        "curve_id": spec["curve_id"],
        "dataset_id": spec["dataset_id"],
        "split": spec["split"],
        "kind": spec["kind"],
        "topology": topology,
        "source_path": source_path,
        "source_row_number": source_row_number,
        "source_row_sha256": canonical_sha256(canonical_row),
        "selection_role": role,
        "optimizer_input": spec["split"] == "train" and role == "scored",
        "vbg_v": vbg_v,
        "vtg_v": vtg_v,
        "vds_v": vds_v,
        "primary_axis_v": primary_axis,
        "target_current_a_per_cm": abs(float(row[current_column])),
        "w_um": float(spec["w_um"]),
        "l_um": float(spec["l_um"]),
        "temperature_k": float(spec["temperature_k"]),
    }


def reconstruct_curves(
    config: dict[str, Any], registry: dict[str, dict[str, str]]
) -> list[tuple[dict[str, Any], list[dict[str, Any]]]]:
    curves: list[tuple[dict[str, Any], list[dict[str, Any]]]] = []
    for spec in config["scored_curves"]:
        registry_row = registry[spec["dataset_id"]]
        source_path = ROOT / registry_row["path"]
        selected: list[dict[str, Any]] = []
        with source_path.open("r", encoding="utf-8", newline="") as stream:
            reader = csv.DictReader(stream)
            for source_row_number, row in enumerate(reader, start=2):
                if row_matches(row, spec["selector"]):
                    selected.append(
                        normalize_source_row(
                            row, source_row_number, len(selected), spec,
                            registry_row["path"],
                        )
                    )
        if len(selected) != int(spec["point_count"]):
            raise ValueError(f"{spec['curve_id']} point count changed")
        if sum(row["selection_role"] == "scored" for row in selected) != int(
            spec["scored_point_count"]
        ):
            raise ValueError(f"{spec['curve_id']} scored count changed")
        curves.append((spec, selected))
    return curves


def softplus(value: float, scale: float) -> float:
    normalized = max(-60.0, min(60.0, value / scale))
    return scale * math.log1p(math.exp(normalized))


def evaluate_kernel(
    parameters: dict[str, float], point: dict[str, Any], config: dict[str, Any]
) -> float:
    vds = float(point["vds_v"])
    if point["topology"] == "symmetric_dual_gate":
        control = parameters["eta_dg"] * (
            float(point["vtg_v"]) + float(point["vbg_v"])
        )
        topology_threshold = parameters["vth_dual_v"]
    else:
        control = float(point["vbg_v"])
        topology_threshold = parameters["vth_single_v"]
    reference_length = float(config["reference_kernel"]["reference_length_um"])
    length = float(point["l_um"])
    threshold = topology_threshold + parameters["length_vth_slope_v"] * math.log(
        length / reference_length
    )
    source_charge = softplus(
        control - threshold, parameters["softplus_scale_v"]
    )
    drain_charge = softplus(
        control - threshold - parameters["drain_coupling"] * abs(vds),
        parameters["softplus_scale_v"],
    )
    magnitude = (
        10.0 ** parameters["log_beta"]
        * (reference_length / length) ** parameters["length_exponent"]
        * (
            source_charge ** parameters["transport_exponent"]
            - drain_charge ** parameters["transport_exponent"]
        )
        * (1.0 + parameters["lambda_per_v"] * abs(vds))
        + 10.0 ** parameters["log_gmin"] * abs(vds)
    )
    return math.copysign(magnitude, vds) if vds != 0.0 else 0.0


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
    gm = interpolate(gm_x, gm_y, vth + GM_OVERDRIVE_V)
    if gm is None:
        return None
    return {"vth_proxy_v": vth, "gm_proxy_a_per_cm_v": gm}


def is_nondecreasing(values: list[float]) -> bool:
    return all(
        right >= left - max(1.0e-30, 1.0e-12 * max(abs(left), abs(right)))
        for left, right in zip(values, values[1:])
    )


def recompute_metrics(
    curves: list[tuple[dict[str, Any], list[dict[str, Any]]]],
    parameters: dict[str, float], config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, dict[str, float]]]:
    floor = float(config["optimization_contract"]["current_floor_a_per_cm"])
    rows: list[dict[str, Any]] = []
    aggregate_inputs = {
        "train": {"linear": [], "log": []},
        "holdout": {"linear": [], "log": []},
    }
    for spec, curve in curves:
        scored = [point for point in curve if point["selection_role"] == "scored"]
        target = [float(point["target_current_a_per_cm"]) for point in scored]
        model = [evaluate_kernel(parameters, point, config) for point in scored]
        normalization = max(max(abs(value) for value in target), floor)
        linear = [
            (model_value - target_value) / normalization
            for model_value, target_value in zip(model, target, strict=True)
        ]
        logarithmic = [
            math.log10(max(abs(model_value), floor))
            - math.log10(max(abs(target_value), floor))
            for model_value, target_value in zip(model, target, strict=True)
        ]
        linear_nrmse = math.sqrt(sum(value * value for value in linear) / len(linear))
        log_rmse = math.sqrt(
            sum(value * value for value in logarithmic) / len(logarithmic)
        )
        aggregate_inputs[spec["split"]]["linear"].append(linear_nrmse)
        aggregate_inputs[spec["split"]]["log"].append(log_rmse)
        target_proxy = None
        model_proxy = None
        if spec["kind"] == "transfer":
            voltages = [float(point["primary_axis_v"]) for point in scored]
            target_proxy = extract_transfer_proxy(voltages, target)
            model_proxy = extract_transfer_proxy(voltages, model)
        vth_error = (
            abs(model_proxy["vth_proxy_v"] - target_proxy["vth_proxy_v"])
            if model_proxy is not None and target_proxy is not None
            else None
        )
        gm_error = (
            abs(
                model_proxy["gm_proxy_a_per_cm_v"]
                - target_proxy["gm_proxy_a_per_cm_v"]
            )
            / max(abs(target_proxy["gm_proxy_a_per_cm_v"]), 1.0e-300)
            if model_proxy is not None and target_proxy is not None
            else None
        )
        ordered_model = [
            evaluate_kernel(parameters, point, config)
            for point in sorted(curve, key=lambda item: float(item["primary_axis_v"]))
        ]
        rows.append(
            {
                "curve_id": spec["curve_id"],
                "linear_nrmse": linear_nrmse,
                "log_rmse_dec": log_rmse,
                "target_vth_proxy_v": None if target_proxy is None else target_proxy["vth_proxy_v"],
                "model_vth_proxy_v": None if model_proxy is None else model_proxy["vth_proxy_v"],
                "vth_absolute_error_v": vth_error,
                "target_gm_proxy_a_per_cm_v": None if target_proxy is None else target_proxy["gm_proxy_a_per_cm_v"],
                "model_gm_proxy_a_per_cm_v": None if model_proxy is None else model_proxy["gm_proxy_a_per_cm_v"],
                "gm_relative_error": gm_error,
                "monotonic": is_nondecreasing(ordered_model),
            }
        )
    aggregate = {
        split: {
            key: math.sqrt(sum(value * value for value in values) / len(values))
            for key, values in components.items()
        }
        for split, components in aggregate_inputs.items()
    }
    return rows, aggregate


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    direct = {
        name.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for name in node.names
    }
    from_imports = {
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    }
    return direct | from_imports


def check_fit(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    outputs = {key: ROOT / value for key, value in config["outputs"].items()}
    fit_report = load_json(outputs["fit_report"])
    contract_report = load_json(outputs["contract_report"])
    snapshot = load_json(outputs["input_snapshot"])
    optimizer = load_json(outputs["optimizer_log"])
    validity = load_json(outputs["validity_json"])
    mapping = load_json(outputs["aimspice_mapping"])
    manifest_rows, manifest_fields = load_csv(outputs["selected_rows_manifest"])
    prediction_rows, prediction_fields = load_csv(outputs["predictions_csv"])
    metric_rows, metric_fields = load_csv(outputs["curve_metrics_csv"])
    parameter_rows, parameter_fields = load_csv(outputs["parameter_table_csv"])
    registry_rows, _ = load_csv(ROOT / config["dataset_contract"]["registry"])
    registry = {row["dataset_id"]: row for row in registry_rows}
    curves = reconstruct_curves(config, registry)
    expected_points = [point for _, curve in curves for point in curve]
    expected_by_uid = {point["row_uid"]: point for point in expected_points}
    predictions_by_uid = {row["row_uid"]: row for row in prediction_rows}
    metrics_by_id = {row["curve_id"]: row for row in metric_rows}
    parameters = {row["name"]: float(row["value"]) for row in parameter_rows}
    recomputed_metrics, recomputed_aggregate = recompute_metrics(
        curves, parameters, config
    )
    recomputed_by_id = {row["curve_id"]: row for row in recomputed_metrics}
    checks: list[dict[str, Any]] = []

    runner_checks = fit_report.get("checks", [])
    add_check(
        checks,
        "runner:formal_e2_pass_and_all_gates",
        fit_report.get("status") == "PASS"
        and fit_report.get("fit_status") == "PASS"
        and fit_report.get("evidence_level") == "E2"
        and fit_report.get("formal_fit_run") is True
        and fit_report.get("formal_fit_run_ordinal") == 1
        and fit_report.get("independent_persisted_evidence_check_complete") is False
        and len(runner_checks) == EXPECTED_RUNNER_CHECK_COUNT
        and all(item.get("status") == "PASS" for item in runner_checks)
        and not fit_report.get("failures"),
        f"runner={sum(item.get('status') == 'PASS' for item in runner_checks)}/{len(runner_checks)}",
    )
    source_hashes_pass = (
        len(registry_rows) == 13
        and all(
            (ROOT / row["path"]).is_file()
            and sha256(ROOT / row["path"]) == row["sha256"]
            for row in registry_rows
        )
    )
    add_check(
        checks,
        "inputs:contract_config_registry_and_source_hashes",
        contract_report.get("status") == "PASS"
        and contract_report.get("config", {}).get("sha256") == sha256(config_path)
        and contract_report.get("registry", {}).get("sha256")
        == sha256(ROOT / config["dataset_contract"]["registry"])
        and source_hashes_pass,
        f"contract={contract_report.get('status')} sources={len(registry_rows)}",
    )
    runner_path = ROOT / "models" / "fit_m00_teaching_compact.py"
    checker_path = Path(__file__).resolve()
    add_check(
        checks,
        "snapshot:exact_runner_checker_and_machine_inputs",
        snapshot.get("runner", {}).get("sha256") == sha256(runner_path)
        and snapshot.get("independent_checker", {}).get("sha256") == sha256(checker_path)
        and snapshot.get("config", {}).get("sha256") == sha256(config_path)
        and snapshot.get("dataset_registry", {}).get("sha256")
        == sha256(ROOT / config["dataset_contract"]["registry"])
        and snapshot.get("holdout_target_rows_loaded_before_optimizer") is False
        and all(value is False for value in snapshot.get("simulator_execution", {}).values()),
        f"runner={snapshot.get('runner', {}).get('sha256')} checker={snapshot.get('independent_checker', {}).get('sha256')}",
    )
    train_points = [
        point
        for spec, curve in curves
        if spec["split"] == "train"
        for point in curve
        if point["selection_role"] == "scored"
    ]
    runner_source = runner_path.read_text(encoding="utf-8")
    add_check(
        checks,
        "optimizer:deterministic_training_only_and_holdout_late_load",
        optimizer.get("success") is True
        and optimizer.get("method") == "trf"
        and optimizer.get("random_seed_or_restart") == "none"
        and optimizer.get("objective_curve_count") == 9
        and optimizer.get("objective_scored_point_count") == 163
        and optimizer.get("objective_input_sha256") == canonical_sha256(train_points)
        and optimizer.get("holdout_curve_ids_in_objective") == []
        and optimizer.get("holdout_targets_loaded_before_optimizer_termination") is False
        and fit_report.get("holdout_evaluation", {}).get("loaded_after_optimizer_termination") is True
        and fit_report.get("holdout_evaluation", {}).get("used_to_change_parameters_or_thresholds") is False
        and runner_source.find("result = least_squares")
        < runner_source.find("holdout_curves ="),
        f"objective={optimizer.get('objective_curve_count')}/{optimizer.get('objective_scored_point_count')} nfev={optimizer.get('nfev')}",
    )
    manifest_exact = (
        len(manifest_rows) == len(expected_points) == 247
        and len({row["row_uid"] for row in manifest_rows}) == 247
        and all(
            row["row_uid"] in expected_by_uid
            and row["source_row_sha256"]
            == expected_by_uid[row["row_uid"]]["source_row_sha256"]
            and row["source_path"] == expected_by_uid[row["row_uid"]]["source_path"]
            and int(row["source_row_number"])
            == expected_by_uid[row["row_uid"]]["source_row_number"]
            and row["selection_role"]
            == expected_by_uid[row["row_uid"]]["selection_role"]
            and (row["optimizer_input"] == "True")
            == expected_by_uid[row["row_uid"]]["optimizer_input"]
            for row in manifest_rows
        )
    )
    add_check(
        checks,
        "selection:manifest_exactly_reconstructs_frozen_rows",
        manifest_exact,
        f"rows={len(manifest_rows)} fields={len(manifest_fields)}",
    )
    prediction_sources_pass = (
        len(prediction_rows) == 247
        and set(predictions_by_uid) == set(expected_by_uid)
        and all(
            close(
                float(predictions_by_uid[uid]["target_current_a_per_cm"]),
                float(point["target_current_a_per_cm"]),
                rel_tol=1.0e-13,
            )
            and predictions_by_uid[uid]["selection_role"] == point["selection_role"]
            and predictions_by_uid[uid]["split"] == point["split"]
            for uid, point in expected_by_uid.items()
        )
    )
    add_check(
        checks,
        "predictions:source_targets_and_roles_are_exact",
        prediction_sources_pass,
        f"rows={len(prediction_rows)} fields={len(prediction_fields)}",
    )
    contract_by_name = {
        item["name"]: item for item in config["parameter_contract"]
    }
    parameter_pass = (
        len(parameter_rows) == 11
        and set(parameters) == set(contract_by_name)
        and all(
            close(float(row["initial"]), float(contract_by_name[row["name"]]["initial"]))
            and close(float(row["lower"]), float(contract_by_name[row["name"]]["lower"]))
            and close(float(row["upper"]), float(contract_by_name[row["name"]]["upper"]))
            and float(row["lower"]) < float(row["value"]) < float(row["upper"])
            and float(row["normalized_bound_distance"]) > 0.0
            and "not a physical parameter" in row["provenance"]
            for row in parameter_rows
        )
        and validity.get("parameters") == parameters
    )
    add_check(
        checks,
        "parameters:frozen_bounds_values_and_nonphysical_provenance",
        parameter_pass,
        f"parameters={len(parameter_rows)} fields={len(parameter_fields)}",
    )
    kernel_differences = [
        abs(
            evaluate_kernel(parameters, point, config)
            - float(predictions_by_uid[uid]["model_current_a_per_cm"])
        )
        / max(
            abs(evaluate_kernel(parameters, point, config)),
            abs(float(predictions_by_uid[uid]["model_current_a_per_cm"])),
            1.0e-300,
        )
        for uid, point in expected_by_uid.items()
    ]
    add_check(
        checks,
        "kernel:independent_prediction_recalculation",
        max(kernel_differences) <= 1.0e-10,
        f"maximum_relative_difference={max(kernel_differences):.6e}",
    )
    floor = float(config["optimization_contract"]["current_floor_a_per_cm"])
    residual_pass = True
    maximum_residual_difference = 0.0
    for spec, curve in curves:
        scored = [point for point in curve if point["selection_role"] == "scored"]
        normalization = max(
            max(float(point["target_current_a_per_cm"]) for point in scored), floor
        )
        for point in curve:
            persisted = predictions_by_uid[point["row_uid"]]
            target = float(point["target_current_a_per_cm"])
            model = evaluate_kernel(parameters, point, config)
            expected_linear = (model - target) / normalization
            expected_log = math.log10(max(abs(model), floor)) - math.log10(
                max(abs(target), floor)
            )
            difference = max(
                abs(expected_linear - float(persisted["linear_normalized_residual"])),
                abs(expected_log - float(persisted["log_residual_dec"])),
            )
            maximum_residual_difference = max(maximum_residual_difference, difference)
            residual_pass = residual_pass and difference <= 1.0e-10
    add_check(
        checks,
        "residuals:independent_linear_and_log_recalculation",
        residual_pass,
        f"maximum_absolute_difference={maximum_residual_difference:.6e}",
    )
    metric_pass = len(metric_rows) == 13 and set(metrics_by_id) == set(recomputed_by_id)
    maximum_metric_difference = 0.0
    for curve_id, expected in recomputed_by_id.items():
        persisted = metrics_by_id[curve_id]
        for key in ("linear_nrmse", "log_rmse_dec"):
            difference = abs(float(persisted[key]) - float(expected[key]))
            maximum_metric_difference = max(maximum_metric_difference, difference)
            metric_pass = metric_pass and difference <= 1.0e-10
        metric_pass = metric_pass and (
            persisted["sampled_prediction_monotonic"] == str(expected["monotonic"])
        )
    add_check(
        checks,
        "metrics:independent_per_curve_recalculation",
        metric_pass,
        f"curves={len(metric_rows)} maximum_difference={maximum_metric_difference:.6e}",
    )
    aggregate_report = fit_report.get("aggregate_metrics", {})
    aggregate_pass = all(
        close(recomputed_aggregate[split][key], aggregate_report[split][key])
        and close(recomputed_aggregate[split][key], validity["aggregate_metrics"][split][key])
        for split in ("train", "holdout")
        for key in ("linear", "log")
    )
    add_check(
        checks,
        "metrics:equal_curve_training_and_holdout_aggregates",
        aggregate_pass,
        json.dumps(recomputed_aggregate, sort_keys=True),
    )
    holdout_transfer = [
        (spec, recomputed_by_id[spec["curve_id"]])
        for spec, _ in curves
        if spec["split"] == "holdout" and spec["kind"] == "transfer"
    ]
    proxy_pass = len(holdout_transfer) == 2
    for spec, expected in holdout_transfer:
        persisted = metrics_by_id[spec["curve_id"]]
        for key in (
            "target_vth_proxy_v", "model_vth_proxy_v", "vth_absolute_error_v",
            "target_gm_proxy_a_per_cm_v", "model_gm_proxy_a_per_cm_v",
            "gm_relative_error",
        ):
            proxy_pass = (
                proxy_pass
                and expected[key] is not None
                and close(float(persisted[key]), float(expected[key]))
            )
    add_check(
        checks,
        "metrics:holdout_vth_and_gm_proxies",
        proxy_pass,
        f"curves={[spec['curve_id'] for spec, _ in holdout_transfer]}",
    )
    role_counts = {
        role: sum(point["selection_role"] == role for point in expected_points)
        for role in ("scored", "zero_vds_invariant", "repeated_low_vds_audit")
    }
    add_check(
        checks,
        "counts:frozen_split_invariants_and_audits",
        sum(spec["split"] == "train" for spec, _ in curves) == 9
        and sum(spec["split"] == "holdout" for spec, _ in curves) == 4
        and sum(point["selection_role"] == "scored" and point["split"] == "train" for point in expected_points) == 163
        and sum(point["selection_role"] == "scored" and point["split"] == "holdout" for point in expected_points) == 70
        and role_counts == {"scored": 233, "zero_vds_invariant": 7, "repeated_low_vds_audit": 7},
        json.dumps(role_counts, sort_keys=True),
    )
    all_predictions = [evaluate_kernel(parameters, point, config) for point in expected_points]
    zero_predictions = [
        evaluate_kernel(parameters, point, config)
        for point in expected_points
        if point["selection_role"] == "zero_vds_invariant"
    ]
    monotonic_pass = all(row["monotonic"] for row in recomputed_metrics)
    add_check(
        checks,
        "invariants:finite_nonnegative_zero_vds_and_monotonic",
        all(math.isfinite(value) and value >= -1.0e-30 for value in all_predictions)
        and len(zero_predictions) == 7
        and max(abs(value) for value in zero_predictions)
        <= float(config["acceptance"]["maximum_zero_vds_abs_current_a_per_cm"])
        and monotonic_pass,
        f"maximum_zero={max(abs(value) for value in zero_predictions):.6e} monotonic={monotonic_pass}",
    )
    acceptance = config["acceptance"]
    train_metrics = [
        recomputed_by_id[spec["curve_id"]]
        for spec, _ in curves if spec["split"] == "train"
    ]
    holdout_metrics = [
        recomputed_by_id[spec["curve_id"]]
        for spec, _ in curves if spec["split"] == "holdout"
    ]
    acceptance_pass = (
        recomputed_aggregate["train"]["linear"] <= float(acceptance["maximum_training_aggregate_linear_nrmse"])
        and recomputed_aggregate["train"]["log"] <= float(acceptance["maximum_training_aggregate_log_rmse_dec"])
        and recomputed_aggregate["holdout"]["linear"] <= float(acceptance["maximum_holdout_aggregate_linear_nrmse"])
        and recomputed_aggregate["holdout"]["log"] <= float(acceptance["maximum_holdout_aggregate_log_rmse_dec"])
        and all(row["linear_nrmse"] <= float(acceptance["maximum_training_per_curve_linear_nrmse"]) and row["log_rmse_dec"] <= float(acceptance["maximum_training_per_curve_log_rmse_dec"]) for row in train_metrics)
        and all(row["linear_nrmse"] <= float(acceptance["maximum_holdout_per_curve_linear_nrmse"]) and row["log_rmse_dec"] <= float(acceptance["maximum_holdout_per_curve_log_rmse_dec"]) for row in holdout_metrics)
        and all(row["vth_absolute_error_v"] is not None and row["vth_absolute_error_v"] <= float(acceptance["maximum_holdout_vth_absolute_error_v"]) and row["gm_relative_error"] is not None and row["gm_relative_error"] <= float(acceptance["maximum_holdout_gm_relative_error"]) for _, row in holdout_transfer)
    )
    add_check(
        checks,
        "acceptance:all_prefrozen_numerical_thresholds",
        acceptance_pass,
        json.dumps(recomputed_aggregate, sort_keys=True),
    )
    artifact_entries = fit_report.get("artifacts", {})
    artifact_hash_pass = (
        len(artifact_entries) == 12
        and all(
            (ROOT / item["path"]).is_file()
            and sha256(ROOT / item["path"]) == item["sha256"]
            and (ROOT / item["path"]).stat().st_size == int(item["bytes"])
            for item in artifact_entries.values()
        )
    )
    add_check(
        checks,
        "artifacts:runner_hash_manifest_is_complete",
        artifact_hash_pass,
        f"artifacts={len(artifact_entries)}",
    )
    figure_paths = [outputs["fit_figure_png"], outputs["residual_figure_png"]]
    dimensions = [png_dimensions(path) for path in figure_paths]
    add_check(
        checks,
        "figures:two_nontrivial_pngs",
        all(width >= 1200 and height >= 700 for width, height in dimensions)
        and all(path.stat().st_size > 20_000 for path in figure_paths),
        f"dimensions={dimensions} bytes={[path.stat().st_size for path in figure_paths]}",
    )
    ngspice_text = outputs["ngspice_candidate"].read_text(encoding="ascii")
    aimspice_text = outputs["aimspice_candidate"].read_text(encoding="ascii")
    candidate_text = f"{ngspice_text}\n{aimspice_text}\n{json.dumps(mapping)}".lower()
    add_check(
        checks,
        "routes:igzo_only_candidates_are_explicitly_unexecuted_and_distinct",
        "m01_execution_required" in ngspice_text.lower()
        and "not native hspice level 61" in ngspice_text.lower()
        and "level=15" in aimspice_text.lower()
        and "tox=10n" in aimspice_text.lower()
        and "physical al2o3 thickness is 30 nm" in aimspice_text.lower()
        and mapping.get("equation_identity_with_reference_kernel") is False
        and mapping.get("aimspice_executed") is False
        and mapping.get("ngspice_executed") is False
        and "sno" not in candidate_text,
        f"mapping={mapping.get('status')}",
    )
    simulator_status = fit_report.get("simulator_status", {})
    add_check(
        checks,
        "validity:local_domain_provenance_and_no_simulator_claim",
        validity.get("validity_domain") == config["validity_domain"]
        and validity.get("vth_criterion_a_per_cm") == VTH_CRITERION_A_PER_CM
        and validity.get("gm_evaluation_overdrive_v") == GM_OVERDRIVE_V
        and simulator_status.get("reference_python_kernel") == "RUN"
        and simulator_status.get("tcad") == "NOT_RUN"
        and "NOT_EXECUTED" in simulator_status.get("ngspice", "")
        and "NOT_EXECUTED" in simulator_status.get("aimspice", "")
        and simulator_status.get("circuit") == "NOT_RUN"
        and fit_report.get("audit_and_exclusion_contract")
        == config["audit_and_exclusion_contract"],
        json.dumps(simulator_status, sort_keys=True),
    )
    checker_imports = imported_modules(checker_path)
    prohibited_claims = " ".join(fit_report.get("prohibited_claims", []))
    add_check(
        checks,
        "independence:standard_library_recalculation_and_evidence_boundary",
        checker_imports.isdisjoint(
            {"numpy", "scipy", "devsim", "subprocess", "fit_m00_teaching_compact"}
        )
        and "experimental fitting" in prohibited_claims
        and "independent external validation" in prohibited_claims
        and "circuit-ready" in prohibited_claims
        and fit_report.get("allowed_claim")
        == config["evidence_boundary"]["future_m00_pass_allowed_claim"],
        f"imports={sorted(checker_imports)}",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        add_check(
            checks,
            "checker:registered_check_count",
            False,
            f"expected={EXPECTED_CHECK_COUNT} actual_before_guard={len(checks)}",
        )
    failures = [item for item in checks if item["status"] == "FAIL"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": "M00",
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_fit_runner": True,
        "runner_imported": False,
        "scipy_imported": False,
        "numpy_imported": False,
        "checker": {
            "path": str(checker_path.relative_to(ROOT)),
            "sha256": sha256(checker_path),
        },
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "pass_count": sum(item["status"] == "PASS" for item in checks),
            "curve_count": len(curves),
            "training_curve_count": 9,
            "holdout_curve_count": 4,
            "training_scored_point_count": 163,
            "holdout_scored_point_count": 70,
            "persisted_prediction_count": len(prediction_rows),
            "parameter_count": len(parameter_rows),
            "aggregate_metrics": recomputed_aggregate,
            "maximum_kernel_relative_difference": max(kernel_differences),
            "maximum_residual_absolute_difference": maximum_residual_difference,
        },
        "m00_completion": {
            "status": "PASS" if not failures else "FAIL",
            "complete_m00_reference_kernel_fit": not failures,
            "m01_contract_permitted_after_documentation": not failures,
            "spice_execution_permitted_in_m00": False,
            "circuit_or_downstream_permitted": False,
        },
        "allowed_claim": config["evidence_boundary"]["future_m00_pass_allowed_claim"],
        "prohibited_claims": config["evidence_boundary"]["prohibited_claims"],
        "next_gate": "After documentation and commit, establish the M01 simulator cross-check contract; no simulator or circuit evidence is created by this check.",
    }
    return report


def main() -> int:
    config = load_json(CONFIG_PATH)
    report_path = ROOT / config["outputs"]["independent_check_report"]
    try:
        report = check_fit(CONFIG_PATH)
    except Exception as error:  # noqa: BLE001
        report = {
            "status": "FAIL",
            "case_id": config.get("case_id", "UNKNOWN"),
            "stage": "M00",
            "evidence_level": "E0",
            "independent_of_fit_runner": True,
            "checks": [],
            "failures": [
                {
                    "name": "checker:unhandled_exception",
                    "status": "FAIL",
                    "detail": f"{type(error).__name__}: {error}",
                }
            ],
        }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"M00_COMPACT_MODEL_FIT_CHECK_{report['status']} "
        f"checks={sum(item.get('status') == 'PASS' for item in report.get('checks', []))}/"
        f"{len(report.get('checks', []))} report={report_path}"
    )
    for failure in report.get("failures", []):
        print(
            f"M00_COMPACT_MODEL_FIT_CHECK_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
