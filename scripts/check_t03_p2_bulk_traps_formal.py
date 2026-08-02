#!/usr/bin/env python3
"""Independently validate persisted formal T03-P2 NTA/NGA evidence."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p2_bulk_traps_formal.json"
ELEMENTARY_CHARGE_C = 1.602176634e-19


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


def close(
    left: float,
    right: float,
    *,
    rel_tol: float = 1e-9,
    abs_tol: float = 1e-12,
) -> bool:
    return math.isclose(
        float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol
    )


def same_voltage(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-12)


def same_density(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-6)


def relative_difference(left: float, right: float) -> float:
    return abs(float(left) - float(right)) / max(
        abs(float(left)), abs(float(right)), 1e-300
    )


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def value_token(value: float) -> str:
    if same_density(value, 0.0):
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
                    "state_id": (
                        f"p2_bulk_{family_id.lower()}_{value_token(value)}_common_primary"
                    ),
                }
            )
    return cases


def primary_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    count = round((stop - start) / step)
    if count < 1 or not same_voltage(start + count * step, stop):
        raise ValueError("formal primary-gate grid is not integral")
    return [round(start + index * step, 12) for index in range(count + 1)]


def curve_for(
    rows: list[dict[str, str]], family_id: str, value_cm3_ev: float
) -> list[dict[str, str]]:
    return sorted(
        [
            row
            for row in rows
            if row["bulk_family_id"] == family_id
            and same_density(float(row["bulk_value_cm3_ev"]), value_cm3_ev)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )


def linear_regression(
    xs: list[float], ys: list[float]
) -> tuple[float, float, float]:
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    denominator = sum((value - mean_x) ** 2 for value in xs)
    slope = sum(
        (x_value - mean_x) * (y_value - mean_y)
        for x_value, y_value in zip(xs, ys, strict=True)
    ) / denominator
    intercept = mean_y - slope * mean_x
    residual = sum(
        (y_value - (slope * x_value + intercept)) ** 2
        for x_value, y_value in zip(xs, ys, strict=True)
    )
    total = sum((value - mean_y) ** 2 for value in ys)
    return slope, intercept, 1.0 - residual / total


def interpolate(xs: list[float], ys: list[float], target: float) -> float:
    for x_value, y_value in zip(xs, ys, strict=True):
        if same_voltage(x_value, target):
            return y_value
    index = next(
        index
        for index in range(len(xs) - 1)
        if xs[index] < target < xs[index + 1]
    )
    return ys[index] + (
        (target - xs[index])
        * (ys[index + 1] - ys[index])
        / (xs[index + 1] - xs[index])
    )


def voltage_at_current(curve: list[dict[str, str]], target: float) -> float:
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    for voltage, current in zip(voltages, currents, strict=True):
        if math.isclose(current, target, rel_tol=1e-12, abs_tol=0.0):
            return voltage
    index = next(
        index
        for index in range(len(currents) - 1)
        if currents[index] < target < currents[index + 1]
    )
    lower_log = math.log10(currents[index])
    upper_log = math.log10(currents[index + 1])
    return voltages[index] + (
        (math.log10(target) - lower_log)
        * (voltages[index + 1] - voltages[index])
        / (upper_log - lower_log)
    )


def recompute_metric(
    config: dict[str, Any], curve: list[dict[str, str]]
) -> dict[str, float | int]:
    method = config["extraction_methods"]["constant_current_vth_proxy"]
    gm_method = config["extraction_methods"]["gm_proxy"]
    criterion = float(method["expected_current_per_width_a_per_cm"])
    voltages = [float(row["primary_gate_v"]) for row in curve]
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in curve]
    bracket = next(
        index
        for index in range(len(currents) - 1)
        if currents[index] <= criterion <= currents[index + 1]
    )
    lower_log = math.log10(currents[bracket])
    upper_log = math.log10(currents[bracket + 1])
    vth = voltages[bracket] + (
        (math.log10(criterion) - lower_log)
        * (voltages[bracket + 1] - voltages[bracket])
        / (upper_log - lower_log)
    )
    gm_voltages = voltages[1:-1]
    gm_values = [
        (currents[index + 1] - currents[index - 1])
        / (voltages[index + 1] - voltages[index - 1])
        for index in range(1, len(curve) - 1)
    ]
    gm_voltage = vth + float(gm_method["evaluation_overdrive_v"])
    gm = interpolate(gm_voltages, gm_values, gm_voltage)

    ss_method = config["extraction_methods"]["ss_proxy"]
    ss_lower = float(ss_method["lower_current_a_per_cm"])
    ss_upper = float(ss_method["upper_current_a_per_cm"])
    samples: dict[float, float] = {
        round(math.log10(ss_lower), 14): voltage_at_current(curve, ss_lower),
        round(math.log10(ss_upper), 14): voltage_at_current(curve, ss_upper),
    }
    for row in curve:
        current = abs(float(row["drain_current_a_per_cm"]))
        if ss_lower < current < ss_upper:
            samples[round(math.log10(current), 14)] = float(row["primary_gate_v"])
    log_currents = sorted(samples)
    ss_voltages = [samples[value] for value in log_currents]
    ss_slope, ss_intercept, ss_r_squared = linear_regression(
        log_currents, ss_voltages
    )
    low_v = float(
        config["extraction_methods"]["low_gate_current_proxy"][
            "evaluation_top_gate_v"
        ]
    )
    low_current = abs(
        float(
            next(
                row
                for row in curve
                if same_voltage(float(row["primary_gate_v"]), low_v)
            )["drain_current_a_per_cm"]
        )
    )
    peak_index = max(range(len(gm_values)), key=lambda index: gm_values[index])
    return {
        "vth_proxy_v": vth,
        "vth_bracket_lower_primary_gate_v": voltages[bracket],
        "vth_bracket_upper_primary_gate_v": voltages[bracket + 1],
        "gm_evaluation_primary_gate_v": gm_voltage,
        "gm_proxy_s_per_cm": gm,
        "maximum_sampled_gm_s_per_cm": gm_values[peak_index],
        "maximum_sampled_gm_primary_gate_v": gm_voltages[peak_index],
        "ss_fit_sample_count": len(log_currents),
        "ss_fit_slope_v_per_dec": ss_slope,
        "ss_fit_intercept_v": ss_intercept,
        "ss_fit_r_squared": ss_r_squared,
        "ss_proxy_mv_per_dec": 1000.0 * ss_slope,
        "low_gate_evaluation_top_gate_v": low_v,
        "low_gate_current_proxy_a_per_cm": low_current,
    }


def gauss_legendre_nodes_weights(order: int) -> tuple[list[float], list[float]]:
    nodes = [0.0] * order
    weights = [0.0] * order
    for index in range((order + 1) // 2):
        root = math.cos(math.pi * (index + 0.75) / (order + 0.5))
        for _ in range(100):
            p0, p1 = 1.0, root
            for degree in range(2, order + 1):
                p0, p1 = p1, (
                    (2.0 * degree - 1.0) * root * p1
                    - (degree - 1.0) * p0
                ) / degree
            derivative = order * (root * p1 - p0) / (root * root - 1.0)
            updated = root - p1 / derivative
            if abs(updated - root) <= 2e-16:
                root = updated
                break
            root = updated
        else:
            raise RuntimeError("Gauss-Legendre root iteration did not converge")
        p0, p1 = 1.0, root
        for degree in range(2, order + 1):
            p0, p1 = p1, (
                (2.0 * degree - 1.0) * root * p1
                - (degree - 1.0) * p0
            ) / degree
        derivative = order * (root * p1 - p0) / (root * root - 1.0)
        weight = 2.0 / ((1.0 - root * root) * derivative * derivative)
        nodes[index] = -root
        nodes[order - index - 1] = root
        weights[index] = weight
        weights[order - index - 1] = weight
    return nodes, weights


def energy_quadrature(config: dict[str, Any]) -> list[tuple[float, float]]:
    lower, upper = (
        float(value) for value in config["energy_integration"]["domain_ev"]
    )
    nodes, weights = gauss_legendre_nodes_weights(
        int(config["energy_integration"]["order"])
    )
    midpoint = 0.5 * (lower + upper)
    half_width = 0.5 * (upper - lower)
    return [
        (midpoint + half_width * node, half_width * weight)
        for node, weight in zip(nodes, weights, strict=True)
    ]


def occupancy(
    epsilon_ev: float, electron_density_cm3: float, nc: float, thermal_ev: float
) -> float:
    return electron_density_cm3 / (
        electron_density_cm3 + nc * math.exp(-epsilon_ev / thermal_ev)
    )


def expected_node_values(
    config: dict[str, Any],
    nta: float,
    nga: float,
    electron_density_cm3: float,
    quadrature: list[tuple[float, float]],
    net_doping_cm3: float,
) -> dict[str, float]:
    model = config["bulk_trap_model"]
    nc = float(model["effective_conduction_dos_cm3"])
    thermal = float(model["boltzmann_ev_per_k"]) * float(
        model["temperature_k"]
    )
    tail_width = float(config["literature_input"]["tail"]["width_ev"])
    deep_width = float(config["literature_input"]["deep"]["width_ev"])
    deep_peak = float(
        config["literature_input"]["deep"]["peak_depth_below_ec_ev"]
    )
    tail_integral = math.fsum(
        weight
        * math.exp(-epsilon / tail_width)
        * occupancy(epsilon, electron_density_cm3, nc, thermal)
        for epsilon, weight in quadrature
    )
    deep_integral = math.fsum(
        weight
        * math.exp(-((epsilon - deep_peak) / deep_width) ** 2)
        * occupancy(epsilon, electron_density_cm3, nc, thermal)
        for epsilon, weight in quadrature
    )
    tail = nta * tail_integral
    deep = nga * deep_integral
    derivative_tail = 0.0
    derivative_deep = 0.0
    for epsilon, weight in quadrature:
        exponential = nc * math.exp(-epsilon / thermal)
        factor = exponential / ((electron_density_cm3 + exponential) ** 2)
        derivative_tail += weight * math.exp(-epsilon / tail_width) * factor
        derivative_deep += (
            weight
            * math.exp(-((epsilon - deep_peak) / deep_width) ** 2)
            * factor
        )
    total = tail + deep
    derivative = nta * derivative_tail + nga * derivative_deep
    return {
        "tail": tail,
        "deep": deep,
        "total": total,
        "derivative": derivative,
        "physical_charge": -ELEMENTARY_CHARGE_C * total,
        "poisson_source": ELEMENTARY_CHARGE_C * total,
        "potential_node_charge": ELEMENTARY_CHARGE_C
        * (electron_density_cm3 + total - net_doping_cm3),
    }


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    paths = {name: ROOT / value for name, value in outputs.items()}
    report = load_json(paths["report"])
    contract = load_json(paths["contract_report"])
    snapshot = load_json(paths["config_snapshot"])
    solver_log = load_json(paths["solver_log"])
    state_manifest = load_json(paths["state_manifest"])
    curve_rows, curve_fields = load_csv(paths["curve_csv"])
    metric_rows, metric_fields = load_csv(paths["metric_csv"])
    reference_rows, reference_fields = load_csv(paths["reference_comparison_csv"])
    zero_rows, zero_fields = load_csv(paths["zero_control_comparison_csv"])
    state_rows, state_fields = load_csv(paths["state_summary_csv"])
    bulk_input = load_json(ROOT / config["dependencies"]["bulk_input_config"])
    baseline = load_json(ROOT / config["dependencies"]["t01_baseline_config"])
    net_doping_cm3 = float(
        baseline["materials"]["channel"]["background_donor_density_cm3"]
    )
    cases = build_cases(config)
    checks: list[dict[str, Any]] = []

    report_checks = report.get("checks", {})
    add_check(
        checks,
        "identity:runner_report_contract_and_stage_are_passed",
        report.get("status") == "PASS"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == config["stage"]
        and report.get("evidence_level") == "E2"
        and report.get("formal_sensitivity_run") is True
        and report.get("independent_persisted_evidence_check_complete") is False
        and contract.get("contract_status") == "PASS"
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and len(report_checks) == 17
        and all(item.get("status") == "PASS" for item in report_checks.values())
        and not report.get("failures"),
        (
            f"report={report.get('status')} contract={contract.get('contract_status')} "
            f"runner_checks={len(report_checks)}"
        ),
    )
    add_check(
        checks,
        "inputs:snapshot_hashes_match_persisted_inputs",
        snapshot.get("case_id") == config["case_id"]
        and snapshot.get("stage") == config["stage"]
        and all(
            item["sha256"] == sha256(ROOT / item["path"])
            for item in snapshot.get("inputs", {}).values()
        ),
        f"inputs={len(snapshot.get('inputs', {}))}",
    )
    artifact_paths = {
        name: paths[name]
        for name in (
            "config_snapshot",
            "solver_log",
            "state_manifest",
            "curve_csv",
            "metric_csv",
            "reference_comparison_csv",
            "zero_control_comparison_csv",
            "state_summary_csv",
        )
    }
    artifacts_valid = all(
        path.is_file()
        and report["artifacts"][name]["path"] == str(path.relative_to(ROOT))
        and report["artifacts"][name]["sha256"] == sha256(path)
        for name, path in artifact_paths.items()
    )
    add_check(
        checks,
        "artifacts:runner_report_hashes_match_all_primary_outputs",
        artifacts_valid,
        f"artifacts={len(artifact_paths)}",
    )

    required_curve_fields = {
        "bulk_family_id",
        "bulk_value_cm3_ev",
        "nta_cm3_ev",
        "nga_cm3_ev",
        "is_zero_control",
        "inactive_family_id",
        "family_id",
        "sweep_direction",
        "stage_id",
        "primary_gate_v",
        "fixed_secondary_gate_v",
        "vbg_v",
        "vtg_v",
        "vds_v",
        "source_current_a_per_cm",
        "drain_current_a_per_cm",
        "relative_current_imbalance",
        "center_channel_potential_v",
        "center_channel_electron_density_cm3",
        "converged",
    }
    expected_grid = primary_grid(config)
    curve_contract_valid = (
        required_curve_fields <= set(curve_fields)
        and len(curve_rows)
        == int(config["acceptance"]["required_total_reported_point_count"])
        and all(
            [
                float(row["primary_gate_v"])
                for row in curve_for(
                    curve_rows, case["bulk_family_id"], case["bulk_value_cm3_ev"]
                )
            ]
            == expected_grid
            for case in cases
        )
        and all(
            row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and row["stage_id"] == "T03_P2_BULK_TRAPS_FORMAL"
            and same_voltage(float(row["fixed_secondary_gate_v"]), 0.0)
            and same_voltage(float(row["vbg_v"]), 0.0)
            and same_voltage(float(row["vds_v"]), 0.01)
            for row in curve_rows
        )
    )
    isolation_valid = all(
        (
            case["bulk_family_id"],
            case["bulk_value_cm3_ev"],
            case["nta_cm3_ev"],
            case["nga_cm3_ev"],
        )
        == (
            row["bulk_family_id"],
            float(row["bulk_value_cm3_ev"]),
            float(row["nta_cm3_ev"]),
            float(row["nga_cm3_ev"]),
        )
        for case in cases
        for row in curve_for(
            curve_rows, case["bulk_family_id"], case["bulk_value_cm3_ev"]
        )
    )
    add_check(
        checks,
        "curves:headers_exact_grid_bias_and_isolation_match_contract",
        curve_contract_valid and isolation_valid,
        (
            f"fields={len(curve_fields)} rows={len(curve_rows)} "
            f"grid={curve_contract_valid} isolation={isolation_valid}"
        ),
    )

    runs = solver_log.get("runs", [])
    records = [record for run in runs for record in run.get("solver_records", [])]
    solver_valid = (
        [run.get("case_id") for run in runs] == [case["case_id"] for case in cases]
        and [len(run.get("solver_records", [])) for run in runs]
        == [int(config["resource_budget"]["required_dc_solve_count_per_device"])]
        * 8
        and len(records)
        == int(config["acceptance"]["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in records)
        and not solver_log.get("errors")
        and float(solver_log.get("wall_seconds", math.inf))
        <= float(config["resource_budget"]["maximum_wall_seconds"])
    )
    add_check(
        checks,
        "solver:eight_fresh_runs_and_frozen_record_budget_converged",
        solver_valid,
        f"runs={len(runs)} records={len(records)} wall={solver_log.get('wall_seconds')}",
    )
    zero_current = max(
        float(
            run["summary"]["zero_equilibrium"][
                "maximum_absolute_terminal_current_a_per_cm"
            ]
        )
        for run in runs
    )
    zero_control_potentials = [
        float(run["summary"]["zero_equilibrium"]["maximum_absolute_potential_v"])
        for run in runs
        if same_density(float(run["bulk_value_cm3_ev"]), 0.0)
    ]
    nonzero_potentials = [
        float(run["summary"]["zero_equilibrium"]["maximum_absolute_potential_v"])
        for run in runs
        if not same_density(float(run["bulk_value_cm3_ev"]), 0.0)
    ]
    equilibrium_valid = (
        zero_current
        <= float(
            config["acceptance"][
                "maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"
            ]
        )
        and len(zero_control_potentials) == 2
        and max(zero_control_potentials)
        <= float(
            config["acceptance"][
                "maximum_zero_control_equilibrium_absolute_potential_v"
            ]
        )
        and len(nonzero_potentials) == 6
        and all(math.isfinite(value) and value >= 0.0 for value in nonzero_potentials)
    )
    add_check(
        checks,
        "solver:zero_bias_current_and_internal_potential_semantics_match_v2",
        equilibrium_valid,
        (
            f"current={zero_current:.6e} controls={zero_control_potentials} "
            f"nonzero={nonzero_potentials}"
        ),
    )
    maximum_imbalance = max(
        float(row["relative_current_imbalance"]) for row in curve_rows
    )
    transport_valid = all(
        row["converged"] == "True"
        and float(row["drain_current_a_per_cm"]) > 0.0
        and float(row["source_current_a_per_cm"]) < 0.0
        and math.isfinite(float(row["drain_current_a_per_cm"]))
        for row in curve_rows
    ) and maximum_imbalance <= float(
        config["acceptance"]["maximum_relative_terminal_current_imbalance"]
    )
    monotonic = all(
        all(higher > lower for lower, higher in zip(currents, currents[1:]))
        for currents in (
            [
                abs(float(row["drain_current_a_per_cm"]))
                for row in curve_for(
                    curve_rows, case["bulk_family_id"], case["bulk_value_cm3_ev"]
                )
            ]
            for case in cases
        )
    )
    add_check(
        checks,
        "transport:finite_directional_conserved_and_monotonic_curves",
        transport_valid and monotonic,
        f"imbalance={maximum_imbalance:.6e} monotonic={monotonic}",
    )

    required_metric_fields = {
        "bulk_family_id",
        "bulk_value_cm3_ev",
        "nta_cm3_ev",
        "nga_cm3_ev",
        "vth_proxy_v",
        "delta_vth_proxy_v",
        "gm_proxy_s_per_cm",
        "ss_fit_sample_count",
        "ss_fit_r_squared",
        "ss_proxy_mv_per_dec",
        "low_gate_current_proxy_a_per_cm",
    }
    metric_by_case = {
        (row["bulk_family_id"], float(row["bulk_value_cm3_ev"])): row
        for row in metric_rows
    }
    metric_recomputed = True
    max_metric_relative_error = 0.0
    for case in cases:
        key = (case["bulk_family_id"], case["bulk_value_cm3_ev"])
        persisted = metric_by_case[key]
        expected = recompute_metric(
            config,
            curve_for(curve_rows, case["bulk_family_id"], case["bulk_value_cm3_ev"]),
        )
        for field in (
            "vth_proxy_v",
            "vth_bracket_lower_primary_gate_v",
            "vth_bracket_upper_primary_gate_v",
            "gm_evaluation_primary_gate_v",
            "gm_proxy_s_per_cm",
            "maximum_sampled_gm_s_per_cm",
            "maximum_sampled_gm_primary_gate_v",
            "ss_fit_slope_v_per_dec",
            "ss_fit_intercept_v",
            "ss_fit_r_squared",
            "ss_proxy_mv_per_dec",
            "low_gate_evaluation_top_gate_v",
            "low_gate_current_proxy_a_per_cm",
        ):
            observed = float(persisted[field])
            expected_value = float(expected[field])
            max_metric_relative_error = max(
                max_metric_relative_error,
                relative_difference(observed, expected_value),
            )
            metric_recomputed = metric_recomputed and close(
                observed, expected_value, rel_tol=2e-10, abs_tol=1e-12
            )
        metric_recomputed = metric_recomputed and int(
            persisted["ss_fit_sample_count"]
        ) == int(expected["ss_fit_sample_count"])
        metric_recomputed = metric_recomputed and float(
            persisted["ss_fit_r_squared"]
        ) >= float(config["acceptance"]["minimum_ss_fit_r_squared"])
    delta_valid = True
    for family_id in ("NTA", "NGA"):
        reference_vth = float(metric_by_case[(family_id, 0.0)]["vth_proxy_v"])
        for case in [item for item in cases if item["bulk_family_id"] == family_id]:
            metric = metric_by_case[(family_id, case["bulk_value_cm3_ev"])]
            delta_valid = delta_valid and close(
                float(metric["delta_vth_proxy_v"]),
                float(metric["vth_proxy_v"]) - reference_vth,
                rel_tol=1e-10,
                abs_tol=1e-12,
            )
    report_metrics_valid = all(
        close(
            float(metric_by_case[(row["bulk_family_id"], float(row["bulk_value_cm3_ev"]))]["vth_proxy_v"]),
            float(row["vth_proxy_v"]),
            rel_tol=1e-12,
            abs_tol=1e-14,
        )
        for row in report["metrics"]
    )
    add_check(
        checks,
        "metrics:independent_vth_gm_ss_and_low_gate_extraction_matches",
        required_metric_fields <= set(metric_fields)
        and len(metric_rows) == 8
        and metric_recomputed
        and delta_valid
        and report_metrics_valid,
        (
            f"metrics={len(metric_rows)} max_relative_error={max_metric_relative_error:.6e} "
            f"delta={delta_valid} report={report_metrics_valid}"
        ),
    )

    t02_curve = sorted(
        [
            row
            for row in load_json(ROOT / config["dependencies"]["t02_c_report"])[
                "family_points"
            ]
            if row["family_id"] == "top_primary"
            and row["sweep_direction"] == "forward"
            and same_voltage(float(row["fixed_secondary_gate_v"]), 0.0)
        ],
        key=lambda row: float(row["primary_gate_v"]),
    )
    t02_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row for row in t02_curve
    }
    reference_recomputed: list[dict[str, Any]] = []
    reference_valid = len(reference_rows) == 62 and {
        "bulk_family_id",
        "primary_gate_v",
        "current_relative_difference",
        "center_channel_potential_difference_v",
        "center_density_relative_difference",
    } <= set(reference_fields)
    for family_id in ("NTA", "NGA"):
        family_rows = []
        for row in curve_for(curve_rows, family_id, 0.0):
            reference = t02_by_voltage.get(
                round(float(row["primary_gate_v"]), 12)
            )
            if reference is None:
                continue
            family_rows.append(
                {
                    "current": relative_difference(
                        abs(float(row["drain_current_a_per_cm"])),
                        abs(float(reference["drain_current_a_per_cm"])),
                    ),
                    "potential": abs(
                        float(row["center_channel_potential_v"])
                        - float(reference["center_channel_potential_v"])
                    ),
                    "density": relative_difference(
                        float(row["center_channel_electron_density_cm3"]),
                        float(reference["center_channel_electron_density_cm3"]),
                    ),
                }
            )
        summary = {
            "bulk_family_id": family_id,
            "maximum_current_relative_difference": max(
                item["current"] for item in family_rows
            ),
            "maximum_center_potential_difference_v": max(
                item["potential"] for item in family_rows
            ),
            "maximum_center_density_relative_difference": max(
                item["density"] for item in family_rows
            ),
        }
        reference_recomputed.append(summary)
        reference_valid = reference_valid and summary[
            "maximum_current_relative_difference"
        ] <= float(
            config["acceptance"][
                "maximum_each_zero_control_t02_c_current_relative_difference"
            ]
        )
        reference_valid = reference_valid and summary[
            "maximum_center_potential_difference_v"
        ] <= float(
            config["acceptance"][
                "maximum_each_zero_control_t02_c_center_potential_difference_v"
            ]
        )
        reference_valid = reference_valid and summary[
            "maximum_center_density_relative_difference"
        ] <= float(
            config["acceptance"][
                "maximum_each_zero_control_t02_c_center_density_relative_difference"
            ]
        )
    add_check(
        checks,
        "controls:both_zero_curves_independently_reproduce_t02_c",
        reference_valid,
        json.dumps(reference_recomputed, sort_keys=True),
    )

    nta_zero = curve_for(curve_rows, "NTA", 0.0)
    nga_zero_by_voltage = {
        round(float(row["primary_gate_v"]), 12): row
        for row in curve_for(curve_rows, "NGA", 0.0)
    }
    pairwise_current = max(
        relative_difference(
            abs(float(row["drain_current_a_per_cm"])),
            abs(
                float(
                    nga_zero_by_voltage[round(float(row["primary_gate_v"]), 12)][
                        "drain_current_a_per_cm"
                    ]
                )
            ),
        )
        for row in nta_zero
    )
    metric_differences = {
        field: relative_difference(
            metric_by_case[("NTA", 0.0)][field],
            metric_by_case[("NGA", 0.0)][field],
        )
        for field in (
            "vth_proxy_v",
            "gm_proxy_s_per_cm",
            "ss_proxy_mv_per_dec",
            "low_gate_current_proxy_a_per_cm",
        )
    }
    pairwise_valid = (
        len(zero_rows)
        == int(config["acceptance"]["required_primary_gate_point_count"])
        and {
            "primary_gate_v",
            "current_relative_difference",
            "center_channel_potential_difference_v",
            "center_density_relative_difference",
        }
        <= set(zero_fields)
        and pairwise_current
        <= float(
            config["acceptance"][
                "maximum_pairwise_zero_control_current_relative_difference"
            ]
        )
        and max(metric_differences.values())
        <= float(
            config["acceptance"][
                "maximum_pairwise_zero_control_metric_relative_difference"
            ]
        )
    )
    add_check(
        checks,
        "controls:two_fresh_zero_devices_match_each_other",
        pairwise_valid,
        json.dumps(
            {
                "maximum_current_relative_difference": pairwise_current,
                "metric_relative_differences": metric_differences,
            },
            sort_keys=True,
        ),
    )

    entries = state_manifest.get("entries", [])
    required_state_fields = {
        "bulk_family_id",
        "bulk_value_cm3_ev",
        "state_id",
        "node_csv",
        "element_csv",
        "bulk_node_csv",
        "vtk_file_count",
        "center_occupied_bulk_traps_cm3",
    }
    state_contract_valid = (
        state_manifest.get("entry_count") == 8
        and [entry.get("state_id") for entry in entries]
        == [case["state_id"] for case in cases]
        and len(state_rows) == 8
        and required_state_fields <= set(state_fields)
    )
    state_file_valid = True
    vtk_count = 0
    bulk_rows_by_state: dict[str, list[dict[str, str]]] = {}
    vtk_field_valid = True
    for entry in entries:
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        bulk_path = ROOT / entry["bulk_node_csv"]
        node_rows, node_header = load_csv(node_path)
        element_rows, element_header = load_csv(element_path)
        persisted_bulk_rows, bulk_header = load_csv(bulk_path)
        bulk_rows_by_state[str(entry["state_id"])] = persisted_bulk_rows
        state_file_valid = state_file_valid and (
            sha256(node_path) == entry["node_csv_sha256"]
            and sha256(element_path) == entry["element_csv_sha256"]
            and sha256(bulk_path) == entry["bulk_node_csv_sha256"]
            and len(node_rows) == 2419
            and len(element_rows) == int(entry["channel_element_count"])
            and int(entry["channel_element_count"]) == 2560
            and len(persisted_bulk_rows) == 2419
            and {"potential_v", "electron_density_cm3", "region"}
            <= set(node_header)
            and {
                "electron_current_density_magnitude_a_per_cm2",
                "region",
            }
            <= set(element_header)
            and {
                "occupied_bulk_traps_cm3",
                "occupied_bulk_traps_derivative",
                "physical_trap_charge_c_per_cm3",
                "poisson_trap_source_c_per_cm3",
                "potential_node_charge_c_per_cm3",
            }
            <= set(bulk_header)
        )
        vtk_count += len(entry["vtk_files"])
        vtk_contents: list[bytes] = []
        for item in entry["vtk_files"]:
            vtk_path = ROOT / item["path"]
            state_file_valid = state_file_valid and (
                vtk_path.is_file() and sha256(vtk_path) == item["sha256"]
            )
            vtk_contents.append(vtk_path.read_bytes())
        vtk_field_valid = vtk_field_valid and any(
            b"OccupiedBulkTraps" in content for content in vtk_contents
        )
        vtk_field_valid = vtk_field_valid and any(
            b"Potential" in content for content in vtk_contents
        )
        vtk_field_valid = vtk_field_valid and any(
            b"Electron" in content for content in vtk_contents
        )
    add_check(
        checks,
        "states:eight_manifests_csv_families_and_48_vtk_are_complete",
        state_contract_valid
        and state_file_valid
        and vtk_count == 48
        and vtk_field_valid,
        (
            f"entries={len(entries)} state_rows={len(state_rows)} vtk={vtk_count} "
            f"files={state_file_valid} fields={vtk_field_valid}"
        ),
    )

    quadrature = energy_quadrature(bulk_input)
    node_recomputed = True
    max_density_error = 0.0
    max_derivative_error = 0.0
    max_charge_error = 0.0
    for case in cases:
        for row in bulk_rows_by_state.get(case["state_id"], []):
            if row["region"] != "channel":
                continue
            expected = expected_node_values(
                bulk_input,
                case["nta_cm3_ev"],
                case["nga_cm3_ev"],
                float(row["electron_density_cm3"]),
                quadrature,
                net_doping_cm3,
            )
            for field, key in (
                ("tail_occupied_density_cm3", "tail"),
                ("deep_occupied_density_cm3", "deep"),
                ("occupied_bulk_traps_cm3", "total"),
                ("occupied_bulk_traps_derivative", "derivative"),
                ("physical_trap_charge_c_per_cm3", "physical_charge"),
                ("poisson_trap_source_c_per_cm3", "poisson_source"),
                ("potential_node_charge_c_per_cm3", "potential_node_charge"),
            ):
                observed = float(row[field])
                expected_value = expected[key]
                error = relative_difference(observed, expected_value)
                if field == "occupied_bulk_traps_derivative":
                    max_derivative_error = max(max_derivative_error, error)
                elif field == "potential_node_charge_c_per_cm3":
                    max_charge_error = max(max_charge_error, error)
                else:
                    max_density_error = max(max_density_error, error)
                node_recomputed = node_recomputed and close(
                    observed, expected_value, rel_tol=2e-8, abs_tol=1e-8
                )
    add_check(
        checks,
        "states:independent_96_point_occupancy_derivative_and_charge_recompute",
        node_recomputed,
        (
            f"max_density_error={max_density_error:.6e} "
            f"max_derivative_error={max_derivative_error:.6e} "
            f"max_charge_error={max_charge_error:.6e}"
        ),
    )

    state_summary_by_id = {row["state_id"]: row for row in state_rows}
    center_valid = True
    responses: dict[str, float] = {}
    for case in cases:
        entry = next(item for item in entries if item["state_id"] == case["state_id"])
        summary = state_summary_by_id[case["state_id"]]
        center_valid = center_valid and close(
            float(summary["center_occupied_bulk_traps_cm3"]),
            float(entry["center_occupied_bulk_traps_cm3"]),
            rel_tol=1e-12,
            abs_tol=1e-8,
        )
        if case["bulk_value_cm3_ev"] == 0.0:
            center_valid = center_valid and abs(
                float(entry["maximum_occupied_bulk_traps_cm3"])
            ) <= 1e-12
        else:
            center_valid = center_valid and float(
                entry["maximum_occupied_bulk_traps_cm3"]
            ) > 0.0
    entry_by_case = {
        (entry["bulk_family_id"], float(entry["bulk_value_cm3_ev"])): entry
        for entry in entries
    }
    for family in config["sensitivity_families"]:
        family_id = family["family_id"]
        maximum = max(float(value) for value in family["formal_values_cm3_ev"])
        responses[family_id] = relative_difference(
            entry_by_case[(family_id, 0.0)]["absolute_drain_current_a_per_cm"],
            entry_by_case[(family_id, maximum)]["absolute_drain_current_a_per_cm"],
        )
    response_valid = all(
        value
        >= float(
            config["acceptance"][
                "minimum_each_family_maximum_common_state_current_relative_response"
            ]
        )
        for value in responses.values()
    )
    add_check(
        checks,
        "states:center_summaries_zero_limits_and_family_responses_match",
        center_valid and response_valid,
        f"center={center_valid} responses={json.dumps(responses, sort_keys=True)}",
    )

    figure_valid = len(report.get("figures", [])) == 2
    figure_diagnostics = []
    for item in report.get("figures", []):
        path = ROOT / item["path"]
        dimensions = png_dimensions(path)
        figure_diagnostics.append(
            {"path": item["path"], "dimensions": dimensions, "sha256": sha256(path)}
        )
        figure_valid = figure_valid and (
            path.is_file()
            and item["sha256"] == sha256(path)
            and dimensions[0] >= 1200
            and dimensions[1] >= 900
        )
    add_check(
        checks,
        "figures:two_nontrivial_png_outputs_match_hashes",
        figure_valid,
        json.dumps(figure_diagnostics, sort_keys=True),
    )
    add_check(
        checks,
        "diagnostics:trend_directions_are_recorded_but_not_completion_gates",
        report["directional_diagnostics"]["completion_gate"] is False
        and set(report["directional_diagnostics"]["families"]) == {"NTA", "NGA"},
        json.dumps(
            {
                family: {
                    key: value
                    for key, value in diagnostics.items()
                    if key != "observed_metrics"
                }
                for family, diagnostics in report["directional_diagnostics"][
                    "families"
                ].items()
            },
            sort_keys=True,
        ),
    )
    completion = report["t03_p2_completion"]
    add_check(
        checks,
        "boundary:runner_alone_does_not_close_p2_or_later_stages",
        completion["bulk_formal_runner_passed"] is True
        and completion["bulk_formal_independent_check_passed"] is False
        and completion["complete_p2_trap_group"] is False
        and completion["complete_t03_five_group_sensitivity"] is False
        and completion["p3_or_p5_permitted_next"] is False
        and "numerical proxies"
        in report["evidence_boundary"][
            "allowed_claim_after_future_run_and_independent_check"
        ],
        report["evidence_boundary"][
            "allowed_claim_after_future_run_and_independent_check"
        ],
    )

    failures = [item for item in checks if item["status"] == "FAIL"]
    independent = {
        "status": "PASS" if not failures else "FAIL",
        "case_id": report["case_id"],
        "stage": report["stage"],
        "parameter_group_id": "P2",
        "evidence_level": "E3" if not failures else "E0",
        "independent_of_simulation_runner": True,
        "runner_imported": False,
        "devsim_imported": False,
        "checks": checks,
        "failures": failures,
        "recomputed_diagnostics": {
            "device_count": len(runs),
            "dc_solve_count": len(records),
            "curve_point_count": len(curve_rows),
            "metric_row_count": len(metric_rows),
            "state_count": len(entries),
            "vtk_file_count": vtk_count,
            "maximum_relative_terminal_current_imbalance": maximum_imbalance,
            "maximum_metric_relative_error": max_metric_relative_error,
            "maximum_node_density_relative_error": max_density_error,
            "maximum_derivative_relative_error": max_derivative_error,
            "maximum_potential_node_charge_relative_error": max_charge_error,
            "family_common_state_current_relative_responses": responses,
        },
        "t03_p2_completion": {
            "bulk_formal_runner_passed": report["status"] == "PASS",
            "bulk_formal_independent_check_passed": not failures,
            "complete_p2_trap_group": not failures,
            "complete_t03_five_group_sensitivity": False,
            "p3_or_p5_permitted_after_documentation": not failures,
            "experimental_calibration_permitted": False,
        },
        "evidence_boundary": {
            "allowed_claim": config["evidence_boundary"][
                "allowed_claim_after_future_run_and_independent_check"
            ],
            "prohibited_claims": config["evidence_boundary"]["prohibited_claims"],
            "next_gate": (
                "Document P2 completion and preserve its numerical-proxy boundary before "
                "opening exactly one of P3 or P5. M00, M01, SPICE, circuits, layout, PEX, "
                "and HZO remain closed."
            ),
        },
        "artifact_hashes": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in artifact_paths.items()
        },
    }
    paths["check_report"].parent.mkdir(parents=True, exist_ok=True)
    paths["check_report"].write_text(
        json.dumps(independent, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        f"T03_P2_BULK_TRAPS_FORMAL_CHECK_{independent['status']} "
        f"checks={len(checks)} devices={len(runs)} dc={len(records)} "
        f"points={len(curve_rows)} report={paths['check_report']}"
    )
    for failure in failures:
        print(
            f"T03_P2_BULK_TRAPS_FORMAL_CHECK_ERROR "
            f"{failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
