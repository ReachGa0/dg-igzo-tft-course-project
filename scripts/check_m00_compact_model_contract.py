#!/usr/bin/env python3
"""Validate the formal M00 input and validation contract without fitting or SPICE."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "compact_m00_input_validation.json"
EXPECTED_CHECK_COUNT = 25


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


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append({
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    })


def equivalent(actual: str, expected: Any) -> bool:
    if isinstance(expected, bool):
        return actual.lower() == str(expected).lower()
    if isinstance(expected, (int, float)):
        try:
            return math.isclose(
                float(actual), float(expected), rel_tol=1.0e-12, abs_tol=1.0e-15
            )
        except ValueError:
            return False
    return actual == str(expected)


def select_rows(
    rows: list[dict[str, str]], selector: dict[str, Any]
) -> list[tuple[int, dict[str, str]]]:
    return [
        (index, row)
        for index, row in enumerate(rows)
        if all(key in row and equivalent(row[key], value) for key, value in selector.items())
    ]


def score_rows(
    selected: list[tuple[int, dict[str, str]]], spec: dict[str, Any]
) -> list[tuple[int, dict[str, str]]]:
    rule = spec["scoring_filter"]
    column = rule["column"]
    values = rule["values"]
    operator = rule["operator"]
    if operator == "equal":
        return [item for item in selected if any(equivalent(item[1][column], v) for v in values)]
    if operator == "not_in":
        return [item for item in selected if not any(equivalent(item[1][column], v) for v in values)]
    raise ValueError(f"unsupported scoring operator: {operator}")


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependencies = config["dependencies"]
    project_path = ROOT / dependencies["project_config"]
    experiments_path = ROOT / dependencies["experiments_config"]
    s00_path = ROOT / dependencies["s00_report"]
    registry_path = ROOT / dependencies["dataset_registry"]
    checker_path = ROOT / dependencies["contract_checker"]
    project = load_json(project_path)
    experiments = load_json(experiments_path)
    s00 = load_json(s00_path)
    registry_rows, registry_fields = load_csv(registry_path)
    registry = {row["dataset_id"]: row for row in registry_rows}
    dataset_rows: dict[str, list[dict[str, str]]] = {}
    dataset_fields: dict[str, list[str]] = {}
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:m00_contract",
        config.get("schema_version") == 1
        and config.get("case_id") == "IGZO_M00_TEACHING_COMPACT_INPUT_VALIDATION_V1"
        and config.get("stage") == "M00"
        and config.get("status") == "planned"
        and config.get("contract_evidence_level_after_check") == "E3",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )
    serialized = json.dumps(config, sort_keys=True) + registry_path.read_text(encoding="utf-8")
    add_check(
        checks,
        "scope:2d_n_igzo_laptop_only",
        project.get("tcad_track", {}).get("dimension") == "2D"
        and project.get("tcad_track", {}).get("laptop_target") is True
        and config["scope"]["laptop_target"] is True
        and project.get("baseline_devices", {}).get("IGZO_TFT", {}).get("polarity") == "n"
        and "n-IGZO" in config["scope"]["device"]
        and "SnO" not in serialized,
        config["scope"]["device"],
    )
    g0 = s00.get("g0_decision", {})
    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        g0.get("status") == dependencies["required_g0_status"]
        and g0.get("quantitative_fitting_permitted") is False
        and "experimental fit" in g0.get("prohibited_claim", "").lower(),
        json.dumps(g0, sort_keys=True),
    )

    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    t03 = experiment_map["T03"]
    add_check(
        checks,
        "dependencies:t01_t02_t03_numerical_gates_complete",
        experiment_map["T01"].get("status") == dependencies["required_t01_status"]
        and experiment_map["T02"].get("status") == dependencies["required_t02_status"]
        and t03.get("status") == dependencies["required_t03_status"]
        and t03.get("completed_parameter_groups") == dependencies["required_t03_groups"]
        and t03.get("remaining_parameter_groups") == []
        and t03.get("remaining_substages") == [],
        (
            f"T01={experiment_map['T01'].get('status')} "
            f"T02={experiment_map['T02'].get('status')} "
            f"T03={t03.get('status')} groups={t03.get('completed_parameter_groups')}"
        ),
    )

    expected_fields = [
        "dataset_id", "path", "sha256", "row_count", "source_report",
        "independent_check", "evidence_level", "eligibility", "formal_role",
        "allowed_use", "prohibited_use",
    ]
    expected_ids = {
        "T01_D_B_IDVD", "T01_D_C_IDVG", "T02_C_DG_TRANSFER",
        "T03_P4_LENGTH_TRANSFER", "T03_P1_BIAS_TRANSFER",
        "T03_P1_CAP_RATIO_TRANSFER", "T03_P2_DIT_TRANSFER",
        "T03_P2_BULK_V3_TRANSFER", "T03_P3_V2_TRANSFER",
        "T03_P3_V2_OUTPUT", "T03_P5_TEMPERATURE_TRANSFER",
        "EXTERNAL_NGSPICE_TRANSFER", "EXTERNAL_NGSPICE_OUTPUT",
    }
    add_check(
        checks,
        "registry:schema_and_unique_ids",
        registry_fields == expected_fields
        and len(registry_rows) == 13
        and len(registry) == len(registry_rows)
        and set(registry) == expected_ids,
        f"rows={len(registry_rows)} ids={sorted(registry)}",
    )

    valid_bytes = True
    registry_details: list[dict[str, Any]] = []
    for dataset_id, record in registry.items():
        path = ROOT / record["path"]
        rows, fields = load_csv(path)
        dataset_rows[dataset_id] = rows
        dataset_fields[dataset_id] = fields
        current_hash = sha256(path)
        valid = current_hash == record["sha256"] and len(rows) == int(record["row_count"])
        valid_bytes = valid_bytes and valid
        registry_details.append({
            "dataset_id": dataset_id,
            "path": record["path"],
            "sha256": current_hash,
            "row_count": len(rows),
        })
    add_check(
        checks,
        "registry:bytes_hashes_and_row_counts_frozen",
        valid_bytes,
        f"datasets={len(registry_details)} rows={sum(item['row_count'] for item in registry_details)}",
    )

    evidence_valid = True
    for record in registry_rows:
        source_report = load_json(ROOT / record["source_report"])
        evidence_valid = evidence_valid and source_report.get("status") == "PASS"
        if record["independent_check"]:
            independent = load_json(ROOT / record["independent_check"])
            evidence_valid = (
                evidence_valid
                and independent.get("status") == "PASS"
                and not independent.get("failures")
            )
    add_check(
        checks,
        "registry:project_numerical_sources_have_passed_independent_checks",
        evidence_valid
        and all(
            record["evidence_level"] == "E3"
            for record in registry_rows
            if record["dataset_id"].startswith(("T01", "T02", "T03"))
        ),
        "all project numerical registry rows trace to PASS runner and independent reports",
    )

    formal_ids = set(config["dataset_contract"]["formal_fit_dataset_ids"])
    forbidden_ids = set(config["dataset_contract"]["forbidden_fit_dataset_ids"])
    add_check(
        checks,
        "registry:fit_diagnostic_excluded_and_reference_roles_are_disjoint",
        formal_ids == {
            dataset_id for dataset_id, record in registry.items()
            if record["eligibility"] == "formal_fit_source"
        }
        and forbidden_ids == set(registry) - formal_ids
        and formal_ids.isdisjoint(forbidden_ids)
        and all(registry[item]["evidence_level"] == "E3" for item in formal_ids)
        and all(not item.startswith("EXTERNAL") for item in formal_ids),
        f"formal={sorted(formal_ids)} forbidden={sorted(forbidden_ids)}",
    )

    selected_ids: dict[str, set[tuple[str, int]]] = {"train": set(), "holdout": set()}
    split_counts: Counter[str] = Counter()
    point_counts: Counter[str] = Counter()
    selector_valid = True
    selected_curve_details: list[dict[str, Any]] = []
    for curve in config["scored_curves"]:
        dataset_id = curve["dataset_id"]
        selected = select_rows(dataset_rows[dataset_id], curve["selector"])
        scored = score_rows(selected, curve)
        split = curve["split"]
        curve_ids = {(dataset_id, index) for index, _ in scored}
        selector_valid = (
            selector_valid
            and dataset_id in formal_ids
            and len(selected) == curve["point_count"]
            and len(scored) == curve["scored_point_count"]
            and selected_ids[split].isdisjoint(curve_ids)
        )
        selected_ids[split].update(curve_ids)
        split_counts[split] += 1
        point_counts[split] += len(scored)
        selected_curve_details.append({
            "curve_id": curve["curve_id"],
            "dataset_id": dataset_id,
            "split": split,
            "selected_points": len(selected),
            "scored_points": len(scored),
        })
    add_check(
        checks,
        "split:selectors_resolve_exact_counts_without_overlap",
        selector_valid and selected_ids["train"].isdisjoint(selected_ids["holdout"]),
        f"curves={dict(split_counts)} scored_points={dict(point_counts)}",
    )

    summary = config["split_summary"]
    add_check(
        checks,
        "split:nine_train_four_holdout_and_233_scored_points",
        split_counts == Counter({"train": 9, "holdout": 4})
        and point_counts == Counter({"train": 163, "holdout": 70})
        and summary["training_curve_count"] == 9
        and summary["holdout_curve_count"] == 4
        and summary["training_scored_point_count"] == 163
        and summary["holdout_scored_point_count"] == 70,
        json.dumps(summary, sort_keys=True),
    )
    add_check(
        checks,
        "split:whole_condition_holdout_is_prefrozen",
        all(curve["curve_id"].startswith(curve["split"] + "_") for curve in config["scored_curves"])
        and all(curve["split"] in {"train", "holdout"} for curve in config["scored_curves"])
        and {curve["kind"] for curve in config["scored_curves"] if curve["split"] == "holdout"}
        == {"transfer", "output"}
        and {curve["topology"] for curve in config["scored_curves"] if curve["split"] == "holdout"}
        == {"single_bottom_gate", "symmetric_dual_gate"},
        "holdout contains complete single/dual transfer/output bias or geometry conditions",
    )

    t01_output_rows = dataset_rows["T01_D_B_IDVD"]
    p3_output_rows = dataset_rows["T03_P3_V2_OUTPUT"]
    zero_ids = {
        ("T01_D_B_IDVD", index)
        for index, row in enumerate(t01_output_rows)
        if row["mesh_level"] == "interface_4x" and equivalent(row["vds_v"], 0.0)
    } | {
        ("T03_P3_V2_OUTPUT", index)
        for index, row in enumerate(p3_output_rows)
        if row["case_id"] == "ideal_control" and equivalent(row["external_vds_v"], 0.0)
    }
    repeated_ids = {
        ("T01_D_B_IDVD", index)
        for index, row in enumerate(t01_output_rows)
        if row["mesh_level"] == "interface_4x" and equivalent(row["vds_v"], 0.01)
    } | {
        ("T03_P3_V2_OUTPUT", index)
        for index, row in enumerate(p3_output_rows)
        if row["case_id"] == "ideal_control" and equivalent(row["external_vds_v"], 0.01)
    }
    add_check(
        checks,
        "split:zero_vds_and_repeated_low_vds_rows_are_separate_audits",
        len(zero_ids) == summary["zero_vds_invariant_point_count"] == 7
        and len(repeated_ids) == summary["repeated_low_vds_audit_point_count"] == 7
        and zero_ids.isdisjoint(selected_ids["train"] | selected_ids["holdout"])
        and repeated_ids.isdisjoint(selected_ids["train"] | selected_ids["holdout"]),
        f"zero_vds={len(zero_ids)} repeated_vds_0p01={len(repeated_ids)}",
    )

    audit_contract = config["audit_and_exclusion_contract"]
    audit_valid = True
    for item in audit_contract["numerical_reproduction_sets"]:
        count = len(select_rows(dataset_rows[item["dataset_id"]], item["selector"]))
        audit_valid = audit_valid and count == item["row_count"]
    for key in ("report_only_challenges", "excluded_physics_variants"):
        for item in audit_contract[key]:
            audit_valid = (
                audit_valid
                and len(dataset_rows[item["dataset_id"]]) == item["row_count"]
                and item["dataset_id"] in forbidden_ids
            )
    add_check(
        checks,
        "datasets:reproduction_challenge_and_physics_exclusions_are_counted",
        audit_valid
        and len(audit_contract["numerical_reproduction_sets"]) == 5
        and len(audit_contract["report_only_challenges"]) == 4
        and len(audit_contract["excluded_physics_variants"]) == 2,
        "audits=5 challenges=4 excluded_physics=2",
    )

    kernel = config["reference_kernel"]
    kernel_text = " ".join(str(value) for value in kernel.values())
    add_check(
        checks,
        "kernel:smooth_charge_difference_dual_gate_and_width_conversion_frozen",
        kernel["kernel_id"] == "IGZO_DG_TEACHING_KERNEL_R01"
        and "Q(x,s)" in kernel["softplus"]
        and "eta_dg * (VTG + VBG)" in kernel["dual_gate_control"]
        and "ln(L/Lref)" in kernel["length_threshold"]
        and all(token in kernel_text for token in ("log_beta", "k_d", "gamma", "lambda", "log_gmin"))
        and kernel["reference_length_um"] == 10.0
        and kernel["physical_parameter_claim_permitted"] is False,
        kernel["current_per_width"],
    )

    parameters = config["parameter_contract"]
    parameter_names = [item["name"] for item in parameters]
    add_check(
        checks,
        "parameters:eleven_unique_bounded_coefficients_with_initial_values",
        len(parameters) == 11
        and len(set(parameter_names)) == len(parameter_names)
        and set(parameter_names) == {
            "log_beta", "vth_single_v", "vth_dual_v", "eta_dg",
            "softplus_scale_v", "transport_exponent", "drain_coupling",
            "lambda_per_v", "log_gmin", "length_exponent",
            "length_vth_slope_v",
        }
        and all(item["lower"] < item["initial"] < item["upper"] for item in parameters),
        f"parameters={parameter_names}",
    )

    optimizer = config["optimization_contract"]
    add_check(
        checks,
        "optimization:deterministic_training_only_equal_curve_objective",
        optimizer["backend"] == "scipy.optimize.least_squares"
        and optimizer["method"] == "trf"
        and optimizer["loss"] == "linear"
        and optimizer["random_seed_or_restart"] == "none"
        and optimizer["training_only"] is True
        and optimizer["holdout_access_during_fit"] is False
        and math.isclose(optimizer["current_floor_a_per_cm"], 1.0e-20)
        and optimizer["max_nfev"] == 20000
        and optimizer["maximum_wall_seconds"] <= 120.0
        and optimizer["tcad_or_spice_execution"] is False
        and "equal total squared weight" in optimizer["per_curve_weighting"],
        json.dumps(optimizer, sort_keys=True),
    )

    metrics = config["metric_contract"]
    add_check(
        checks,
        "metrics:linear_log_vth_gm_invariants_and_bounds_reported_separately",
        len(metrics["report_separately"]) == 9
        and any("linear NRMSE" in item for item in metrics["report_separately"])
        and any("logarithmic RMSE" in item for item in metrics["report_separately"])
        and any("VTH" in item for item in metrics["report_separately"])
        and any("gm" in item for item in metrics["report_separately"])
        and any("blended score" in item for item in metrics["forbidden_reporting"])
        and any("experimental accuracy" in item for item in metrics["forbidden_reporting"]),
        f"reported={len(metrics['report_separately'])} forbidden={len(metrics['forbidden_reporting'])}",
    )

    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:train_holdout_thresholds_and_invariants_prefrozen",
        acceptance["required_training_curve_count"] == 9
        and acceptance["required_holdout_curve_count"] == 4
        and acceptance["required_training_scored_point_count"] == 163
        and acceptance["required_holdout_scored_point_count"] == 70
        and acceptance["required_zero_vds_invariant_point_count"] == 7
        and acceptance["maximum_training_aggregate_linear_nrmse"] == 0.15
        and acceptance["maximum_training_aggregate_log_rmse_dec"] == 0.45
        and acceptance["maximum_holdout_aggregate_linear_nrmse"] == 0.20
        and acceptance["maximum_holdout_aggregate_log_rmse_dec"] == 0.60
        and acceptance["maximum_zero_vds_abs_current_a_per_cm"] == 1.0e-18
        and all(
            acceptance[key] is True
            for key in (
                "require_all_predictions_finite",
                "require_nonnegative_current_for_nonnegative_vds",
                "require_sampled_transfer_and_output_monotonicity",
                "require_all_parameters_strictly_inside_bounds",
                "require_training_and_holdout_metrics_reported_separately",
                "require_multiple_vds_in_training_and_holdout",
                "require_parameter_provenance_and_validity_domain",
            )
        ),
        json.dumps(acceptance, sort_keys=True),
    )

    routes = config["model_routes"]
    add_check(
        checks,
        "routes:reference_ngspice_and_aimspice_boundaries_are_distinct",
        routes["reference_python"]["simulator_execution"] is False
        and "execution deferred to M01" in routes["ngspice_behavioral"]["role"]
        and routes["ngspice_behavioral"]["native_level61_claim_permitted"] is False
        and "NMOS LEVEL=15" in routes["aimspice_level15"]["role"]
        and routes["aimspice_level15"]["physical_tox_nm"] == 30.0
        and routes["aimspice_level15"]["effective_model_tox_nm"] == 10.0
        and routes["aimspice_level15"]["equation_identity_with_ngspice"] is False
        and "M01" in routes["m01_gate"],
        routes["m01_gate"],
    )

    validity = config["validity_domain"]
    add_check(
        checks,
        "validity:nominal_300k_ideal_contact_dc_domain_is_explicit",
        validity["material"] == "n-type IGZO only"
        and validity["temperature_k"] == [300.0, 300.0]
        and validity["contact"] == "ideal ohmic nominal only"
        and validity["traps"] == "none in nominal model"
        and validity["vds_v"] == [0.0, 0.2]
        and validity["channel_length_um"] == [8.0, 12.0]
        and validity["analysis_type"] == "DC only"
        and len(validity["excluded"]) == 5
        and "teaching assumption" in validity["width_scaling"],
        json.dumps(validity, sort_keys=True),
    )

    retention = config["failure_retention"]
    add_check(
        checks,
        "failure:immutable_failed_fit_and_no_threshold_relaxation",
        retention["refuse_to_overwrite_existing_run_outputs"] is True
        and retention["preserve_every_failed_fit"] is True
        and len(retention["required_failure_artifacts"]) == 6
        and len(retention["prohibited_recovery"]) == 6
        and any("holdout" in item for item in retention["prohibited_recovery"])
        and any("threshold" in item for item in retention["prohibited_recovery"])
        and any("overwrite" in item for item in retention["prohibited_recovery"])
        and "new revision" in retention["acceptance_change_rule"],
        retention["acceptance_change_rule"],
    )

    outputs = config["outputs"]
    output_values = list(outputs.values())
    future_outputs = [
        value for name, value in outputs.items() if name != "contract_report"
    ]
    existing_future_outputs = [
        value for value in future_outputs if (ROOT / value).exists()
    ]
    add_check(
        checks,
        "outputs:unique_m00_paths_and_no_fit_artifacts_exist",
        len(output_values) == len(set(output_values))
        and all("m00" in value or "igzo_dg" in value or "igzo_level15" in value for value in output_values)
        and not existing_future_outputs,
        f"outputs={len(output_values)} existing_future={existing_future_outputs}",
    )

    imported_modules = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(ast.parse(checker_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.Import)
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(ast.parse(checker_path.read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
    }
    add_check(
        checks,
        "implementation:contract_checker_is_standard_library_static_only",
        imported_modules.isdisjoint({"numpy", "scipy", "subprocess", "devsim"})
        and checker_path.resolve() == Path(__file__).resolve(),
        f"imports={sorted(imported_modules)}",
    )

    boundary = config["evidence_boundary"]
    prohibited = " ".join(boundary["prohibited_claims"])
    add_check(
        checks,
        "boundary:no_fit_simulator_physical_or_circuit_claim",
        "without fitting a model" in boundary["contract_allowed_claim"]
        and "condition-held-out numerical errors" in boundary["future_m00_pass_allowed_claim"]
        and "experimental fitting" in prohibited
        and "independent external validation" in prohibited
        and "AIM-Spice or ngspice validation before M01" in prohibited
        and "circuit-ready" in prohibited
        and "only one formal M00" in boundary["next_gate"],
        boundary["contract_allowed_claim"],
    )

    m00 = experiment_map["M00"]
    m00_contract = m00.get("contract_evidence", {})
    downstream_ids = ["M01", "C00", "C01", "C02", "C03", "L00", "V00", "V01", "PEX0", "FE0"]
    add_check(
        checks,
        "machine_state:contract_ready_only_one_m00_fit_is_next",
        m00.get("status") == "in_progress"
        and m00.get("current_evidence") == "E0"
        and m00.get("depends_on") == ["S00", "T01", "T02", "T03"]
        and m00_contract.get("status") == "input_validation_contract_ready"
        and m00_contract.get("contract_evidence") == "E3"
        and m00_contract.get("contract_checks_passed") == EXPECTED_CHECK_COUNT
        and m00_contract.get("fit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
        and m00_contract.get("formal_fit_completed") is False
        and project.get("tcad_track", {}).get("next_scope", "").startswith(
            "run exactly one formal M00 teaching compact-model fit"
        )
        and all(experiment_map[item].get("status") in {"planned", "optional"} for item in downstream_ids),
        project.get("tcad_track", {}).get("next_scope", ""),
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
        "contract_status": "PASS" if not failures else "FAIL",
        "fit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "tcad_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "spice_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "circuit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E3" if not failures else "E0",
        "config": {
            "path": str(config_path.relative_to(ROOT)),
            "sha256": sha256(config_path),
        },
        "contract_checker": {
            "path": str(checker_path.relative_to(ROOT)),
            "sha256": sha256(checker_path),
        },
        "machine_inputs": {
            "project_config": {
                "path": str(project_path.relative_to(ROOT)),
                "sha256": sha256(project_path),
            },
            "experiments_config": {
                "path": str(experiments_path.relative_to(ROOT)),
                "sha256": sha256(experiments_path),
            },
            "s00_report": {
                "path": str(s00_path.relative_to(ROOT)),
                "sha256": sha256(s00_path),
            },
        },
        "registry": {
            "path": str(registry_path.relative_to(ROOT)),
            "sha256": sha256(registry_path),
            "dataset_count": len(registry_rows),
            "datasets": registry_details,
        },
        "checks": checks,
        "failures": failures,
        "planned_fit": {
            "kernel_id": config["reference_kernel"]["kernel_id"],
            "parameter_count": len(parameters),
            "training_curves": split_counts["train"],
            "holdout_curves": split_counts["holdout"],
            "training_scored_points": point_counts["train"],
            "holdout_scored_points": point_counts["holdout"],
            "zero_vds_invariant_points": len(zero_ids),
            "selected_curves": selected_curve_details,
        },
        "evidence_boundary": boundary,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    args = parser.parse_args()
    config_path = args.config.resolve()
    report = check_contract(config_path)
    config = load_json(config_path)
    report_path = ROOT / config["outputs"]["contract_report"]
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"M00_COMPACT_MODEL_CONTRACT_{report['status']} "
        f"checks={len(report['checks'])} fit={report['fit_status']} "
        f"spice={report['spice_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"M00_COMPACT_MODEL_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
