#!/usr/bin/env python3
"""Check the M01 simulator cross-check contract without invoking a simulator."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_simulator_cross_check_contract.json"
EXPECTED_CHECK_COUNT = 32


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
    checks.append(
        {
            "name": name,
            "status": "PASS" if passed else "FAIL",
            "detail": detail,
        }
    )


def finite_float(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def check_contract() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    m00_fit = load_json(ROOT / "results" / "reports" / "m00_compact_model_fit_r02.json")
    m00_check = load_json(
        ROOT / "results" / "reports" / "m00_compact_model_fit_check_r02.json"
    )
    manifest_path = ROOT / config["target_contract"]["selection_manifest"]
    prediction_path = ROOT / config["target_contract"]["prediction_table"]
    manifest_rows, manifest_fields = load_csv(manifest_path)
    prediction_rows, prediction_fields = load_csv(prediction_path)
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:m01_contract",
        config.get("stage_id") == "M01"
        and config.get("revision") == 3
        and config.get("status") == "contract_ready"
        and config.get("evidence_level") == "E3"
        and config.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    add_check(
        checks,
        "scope:2d_laptop_igzo_only",
        project.get("tcad_track", {}).get("dimension") == "2D"
        and project.get("tcad_track", {}).get("laptop_target") is True
        and config.get("device_contract", {}).get("material") == "IGZO"
        and config.get("device_contract", {}).get("polarity") == "n-type"
        and config.get("excluded_inputs_and_scope", {}).get("active_material_scope")
        == "IGZO only",
        json.dumps(config.get("device_contract", {}), sort_keys=True),
    )
    add_check(
        checks,
        "dependencies:m00_r02_two_level_pass_and_r01_preserved",
        experiment_map.get("M00", {}).get("status") == "verified"
        and experiment_map.get("M00", {}).get("current_evidence") == "E3"
        and config["depends_on"]["m00_r02_runner_passes"] == 24
        and config["depends_on"]["m00_r02_independent_passes"] == 20
        and config["depends_on"]["r01_failure_preserved"] is True
        and m00_fit.get("status") == "PASS"
        and m00_check.get("status") == "PASS",
        f"M00={experiment_map.get('M00', {}).get('status')} runner={m00_fit.get('status')} checker={m00_check.get('status')}",
    )
    add_check(
        checks,
        "machine_state:m01_is_still_unexecuted_before_contract_commit",
        (
            (
                experiment_map.get("M01", {}).get("status") == "planned"
                and experiment_map.get("M01", {}).get("current_evidence") == "E0"
            )
            or (
                experiment_map.get("M01", {}).get("status") == "contract_ready"
                and experiment_map.get("M01", {}).get("current_evidence") == "E3"
            )
        )
        and experiment_map.get("M01", {}).get("depends_on") == ["M00"],
        json.dumps(experiment_map.get("M01", {}), sort_keys=True),
    )

    add_check(
        checks,
        "targets:source_files_present",
        manifest_path.is_file() and prediction_path.is_file(),
        f"manifest={manifest_path.is_file()} predictions={prediction_path.is_file()}",
    )
    add_check(
        checks,
        "targets:frozen_sha256",
        sha256(manifest_path) == config["target_contract"]["selection_manifest_sha256"]
        and sha256(prediction_path) == config["target_contract"]["prediction_table_sha256"],
        f"manifest={sha256(manifest_path)} predictions={sha256(prediction_path)}",
    )
    required_manifest_fields = {
        "row_uid", "curve_id", "dataset_id", "split", "kind", "topology",
        "source_path", "source_row_number", "source_row_sha256", "selection_role",
        "optimizer_input", "vbg_v", "vtg_v", "vds_v", "primary_axis_v",
        "target_current_a_per_cm", "w_um", "l_um", "temperature_k",
    }
    required_prediction_fields = required_manifest_fields | {
        "model_current_a_per_cm", "current_error_a_per_cm", "linear_normalized_residual",
        "log_residual_dec",
    }
    add_check(
        checks,
        "targets:field_contract",
        required_manifest_fields.issubset(manifest_fields)
        and required_prediction_fields.issubset(prediction_fields),
        f"manifest_fields={len(manifest_fields)} prediction_fields={len(prediction_fields)}",
    )
    manifest_split = Counter(row.get("split") for row in manifest_rows)
    manifest_curves = {row.get("curve_id") for row in manifest_rows}
    add_check(
        checks,
        "targets:row_curve_and_split_counts",
        len(manifest_rows) == 247
        and len(prediction_rows) == 247
        and len(manifest_curves) == 13
        and manifest_split == Counter({"train": 173, "holdout": 74}),
        f"rows={len(manifest_rows)}/{len(prediction_rows)} curves={len(manifest_curves)} split={dict(manifest_split)}",
    )
    add_check(
        checks,
        "targets:all_rows_are_frozen_scored_inputs",
        all(
            row.get("selection_role") in {"scored", "zero_vds_invariant", "repeated_low_vds_audit"}
            and (row.get("optimizer_input") == "True")
            == (row.get("selection_role") == "scored" and row.get("split") == "train")
            for row in manifest_rows
        )
        and all(
            row.get("selection_role")
            in {"scored", "zero_vds_invariant", "repeated_low_vds_audit"}
            for row in prediction_rows
        )
        and sum(row.get("selection_role") == "scored" for row in manifest_rows) == 233
        and sum(row.get("selection_role") == "zero_vds_invariant" for row in manifest_rows) == 7
        and sum(row.get("selection_role") == "repeated_low_vds_audit" for row in manifest_rows) == 7,
        f"scored={sum(row.get('selection_role') == 'scored' for row in manifest_rows)} audits=14",
    )
    manifest_by_uid = {row["row_uid"]: row for row in manifest_rows}
    prediction_by_uid = {row["row_uid"]: row for row in prediction_rows}
    aligned = (
        set(manifest_by_uid) == set(prediction_by_uid)
        and all(
            manifest_by_uid[uid].get(key) == prediction_by_uid[uid].get(key)
            for uid in manifest_by_uid
            for key in required_manifest_fields
        )
    )
    add_check(
        checks,
        "targets:manifest_prediction_alignment",
        aligned,
        f"uids={len(manifest_by_uid)} aligned={aligned}",
    )
    numeric_fields = [
        "vbg_v", "vtg_v", "vds_v", "primary_axis_v", "target_current_a_per_cm",
        "w_um", "l_um", "temperature_k",
    ]
    add_check(
        checks,
        "targets:finite_numeric_rows",
        all(finite_float(row.get(field, "")) for row in manifest_rows for field in numeric_fields),
        f"numeric_rows={len(manifest_rows)}",
    )
    add_check(
        checks,
        "device:geometry_bias_and_temperature_frozen",
        all(
            math.isclose(float(row["w_um"]), 60.0)
            and float(row["l_um"]) in {8.0, 10.0, 12.0}
            and math.isclose(float(row["temperature_k"]), 300.0)
            and float(row["vds_v"]) >= 0.0
            for row in manifest_rows
        )
        and config["device_contract"]["source_potential_v"] == 0.0,
        "W=60 um L=8/10/12 um T=300 K source=0 V",
    )

    ng_route = config["routes"]["ngspice_behavioral"]
    aim_route = config["routes"]["aimspice_level15"]
    ng_path = ROOT / ng_route["candidate_path"]
    aim_path = ROOT / aim_route["candidate_path"]
    mapping_path = ROOT / aim_route["mapping_path"]
    add_check(
        checks,
        "routes:candidate_hashes",
        ng_path.is_file()
        and aim_path.is_file()
        and mapping_path.is_file()
        and sha256(ng_path) == ng_route["candidate_sha256"]
        and sha256(aim_path) == aim_route["candidate_sha256"]
        and sha256(mapping_path) == aim_route["mapping_sha256"],
        f"ng={ng_path.is_file()} aim={aim_path.is_file()} mapping={mapping_path.is_file()}",
    )
    mapping = load_json(mapping_path)
    add_check(
        checks,
        "routes:mapping_is_unexecuted_r02_candidate",
        mapping.get("mapping_id") == "IGZO_M00_TO_AIMSPICE_LEVEL15_R02"
        and mapping.get("status") == "CANDIDATE_ONLY_M01_EXECUTION_REQUIRED"
        and mapping.get("equation_identity_with_reference_kernel") is False
        and mapping.get("aimspice_executed") is False
        and mapping.get("ngspice_executed") is False,
        mapping.get("status", ""),
    )
    ng_text = ng_path.read_text(encoding="ascii")
    aim_text = aim_path.read_text(encoding="ascii")
    add_check(
        checks,
        "routes:ngspice_candidate_syntax_boundary",
        ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in ng_text
        and "M01_EXECUTION_REQUIRED" in ng_text
        and "not native HSPICE Level 61" in ng_text
        and "(10/LUM)" in ng_text,
        "behavioral subcircuit, pins, fixed length factor and non-Level-61 boundary found",
    )
    add_check(
        checks,
        "routes:aimspice_candidate_syntax_boundary",
        ".model IGZO_N_L15_R02 NMOS LEVEL=15" in aim_text
        and ".subckt IGZO_DG_LEVEL15_R02 D TG BG S" in aim_text
        and "TOX=10n" in aim_text
        and "physical al2o3 thickness is 30 nm" in aim_text.lower()
        and "M01_EXECUTION_REQUIRED" in aim_text,
        "Level-15 model, dual-gate wrapper and physical/effective TOX boundary found",
    )
    forbidden_pattern = re.compile(
        r"\b(?:sno|hzo|ferroelectric|ring_oscillator|full_adder|inverter|nand|nor|xor|tran|noise|monte)\b",
        re.IGNORECASE,
    )
    add_check(
        checks,
        "scope:candidates_contain_no_excluded_material_or_circuit_route",
        forbidden_pattern.search(ng_text) is None
        and forbidden_pattern.search(aim_text) is None
        and "deepseek_work" not in ng_text
        and "deepseek_work" not in aim_text
        and "AIMSPICE_improved" not in ng_text
        and "AIMSPICE_improved" not in aim_text,
        "candidate text is IGZO device-only and has no excluded route token",
    )
    add_check(
        checks,
        "routes:distinct_model_equations_and_port_mapping",
        ng_route["equation_identity_with_aimspice"] is False
        and aim_route["equation_identity_with_ngspice"] is False
        and ng_route["subcircuit"] == "IGZO_DG_BEHAVIORAL_R02"
        and aim_route["subcircuit"] == "IGZO_DG_LEVEL15_R02"
        and config["device_contract"]["port_mapping"]["source"] == "0 V reference",
        "routes are distinct and use the frozen D/TG/BG/S mapping",
    )

    tool_checks = []
    for route in (ng_route, aim_route):
        tool_path = Path(route["tool_path"])
        tool_checks.append(
            tool_path.is_file()
            and tool_path.stat().st_size == route["tool_bytes"]
            and sha256(tool_path) == route["tool_sha256"]
        )
    add_check(
        checks,
        "tools:fingerprints_recorded_without_execution",
        all(tool_checks),
        f"ngspice={tool_checks[0]} aimspice={tool_checks[1]}",
    )
    checker_imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.Import)
    } | {
        (node.module or "").split(".")[0]
        for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
        if isinstance(node, ast.ImportFrom)
    }
    add_check(
        checks,
        "implementation:checker_is_stdlib_and_no_simulator_invocation",
        checker_imports.isdisjoint({"numpy", "scipy", "subprocess", "devsim"})
        and config["syntax_and_preflight_contract"]["contract_check_must_not_invoke_simulator"] is True,
        f"imports={sorted(checker_imports)}",
    )
    add_check(
        checks,
        "metrics:formulas_split_and_route_difference_frozen",
        config["metric_contract"]["current_floor_a_per_cm"] == 1e-20
        and "Equal weight per complete scored curve" in config["metric_contract"]["aggregate_weighting"]
        and "route disagreement is a required diagnostic" in config["metric_contract"]["route_difference"]
        and "do not retune" in config["metric_contract"]["threshold_policy"],
        "linear/log formulas, split weighting and non-tunable route difference are explicit",
    )

    output_values = [
        value
        for key, value in config["outputs"].items()
        if key != "historical_failed_contract_reports"
    ]
    output_paths = [ROOT / value for value in output_values]
    planned_paths_absent = all(not path.exists() for path in output_paths)
    add_check(
        checks,
        "outputs:unique_exclusive_paths_absent_before_contract_report",
        len(output_values) == len(set(output_values))
        and planned_paths_absent
        and config["failure_retention"]["exclusive_outputs"] is True
        and config["failure_retention"]["overwrite_existing_outputs"] is False,
        f"paths={len(output_paths)} absent={planned_paths_absent}",
    )
    add_check(
        checks,
        "failure_retention:failed_routes_and_r02_outputs_preserved",
        config["failure_retention"]["retain_failed_route_logs"] is True
        and config["failure_retention"]["retain_partial_tables"] is True
        and config["failure_retention"]["r02_and_r01_outputs_must_not_change"] is True,
        json.dumps(config["failure_retention"], sort_keys=True),
    )
    historical_failure_paths = [
        ROOT / value for value in config["outputs"]["historical_failed_contract_reports"]
    ]
    historical_failures = []
    for historical_failure_path in historical_failure_paths:
        try:
            historical_failures.append(load_json(historical_failure_path))
        except (FileNotFoundError, json.JSONDecodeError):
            historical_failures.append({})
    add_check(
        checks,
        "failure_retention:prior_contract_failures_preserved",
        len(historical_failures) == 2
        and all(
            report.get("status") == "FAIL"
            and report.get("contract_status") == "FAIL"
            and report.get("evidence_level") == "E0"
            for report in historical_failures
        )
        and all(path != ROOT / config["outputs"]["contract_report"] for path in historical_failure_paths),
        f"historical_statuses={[report.get('status') for report in historical_failures]}",
    )
    excluded = config["excluded_inputs_and_scope"]
    add_check(
        checks,
        "scope:external_baselines_reference_only_and_sno_excluded",
        len(excluded["reference_only_roots"]) == 2
        and any("ngspice_results" in value for value in excluded["reference_only_roots"])
        and any("AIMSPICE_improved" in value for value in excluded["reference_only_roots"])
        and any("SnO" in value for value in excluded["excluded_assets"]),
        "external folders are reference-only and SnO is explicitly excluded",
    )
    add_check(
        checks,
        "budget:two_device_only_routes_laptop_bound",
        config["resource_budget"]["routes"] == 2
        and config["resource_budget"]["target_rows_per_route"] == 247
        and config["resource_budget"]["max_generated_device_netlists"] == 2
        and config["resource_budget"]["circuit_or_transient_runs"] is False
        and config["resource_budget"]["hzo_runs"] is False,
        json.dumps(config["resource_budget"], sort_keys=True),
    )
    add_check(
        checks,
        "machine_state:project_next_scope_is_m01_contract",
        project.get("tcad_track", {}).get("next_scope", "").startswith(
            "establish the M01 simulator cross-check contract"
        ),
        project.get("tcad_track", {}).get("next_scope", ""),
    )
    downstream_ids = ["C00", "C01", "C02", "C03", "L00", "V00", "V01", "PEX0", "FE0"]
    add_check(
        checks,
        "machine_state:downstream_remains_closed",
        all(experiment_map[item].get("status") in {"planned", "optional"} for item in downstream_ids),
        ",".join(f"{item}={experiment_map[item].get('status')}" for item in downstream_ids),
    )
    add_check(
        checks,
        "history:r01_failure_and_r02_artifacts_are_not_reinterpreted",
        experiment_map["M00"].get("formal_fit_evidence", {}).get("formal_fit_passed") is False
        and experiment_map["M00"].get("r02_execution_evidence", {}).get("formal_fit_passed") is True
        and config["evidence_boundary"]["contract_claim"].startswith("E3 static contract only"),
        "R01 remains FAIL while R02 remains the only M00 source for M01",
    )
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    add_check(
        checks,
        "implementation:make_contract_target_registered",
        "m01-simulator-cross-check-contract-check" in makefile
        and "scripts/check_m01_simulator_cross_check_contract.py" in makefile,
        "M01 static contract target is registered",
    )
    contract_report_path = ROOT / config["outputs"]["contract_report"]
    add_check(
        checks,
        "outputs:contract_report_is_separate_from_future_run_outputs",
        config["outputs"]["contract_report"] not in config["outputs"]["run_report"]
        and config["outputs"]["contract_report"] not in config["outputs"]["independent_check_report"]
        and not contract_report_path.exists(),
        str(contract_report_path.relative_to(ROOT)),
    )
    add_check(
        checks,
        "scope:candidates_have_no_external_paths_or_sno_text",
        all(
            token not in (ng_text + aim_text).lower()
            for token in ("sno", "hzo", "aimspice_improved", "deepseek_work", "data/raw/baseline")
        ),
        "candidate files contain no external or excluded-material path",
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
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "fit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "spice_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "circuit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "evidence_level": "E3" if not failures else "E0",
        "contract_id": "M01_SIMULATOR_CROSS_CHECK_R01",
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "target_rows": len(manifest_rows),
            "target_curves": len(manifest_curves),
            "routes": 2,
            "outputs_created_by_contract": False,
        },
        "config": {
            "path": str(CONFIG_PATH.relative_to(ROOT)),
            "sha256": sha256(CONFIG_PATH),
        },
        "checker": {
            "path": str(Path(__file__).relative_to(ROOT)),
            "sha256": sha256(Path(__file__)),
        },
        "next_gate": config["next_gate"],
        "failures": failures,
    }
    if contract_report_path.exists():
        raise RuntimeError(f"Refusing to overwrite existing contract report: {contract_report_path}")
    with contract_report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_SIMULATOR_CROSS_CHECK_CONTRACT_"
        f"{'PASS' if not failures else 'FAIL'} checks="
        f"{len(checks) - len(failures)}/{len(checks)} report={contract_report_path}"
    )
    return report


if __name__ == "__main__":
    result = check_contract()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
