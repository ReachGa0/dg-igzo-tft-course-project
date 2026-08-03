#!/usr/bin/env python3
"""Check the M01 open-source simulator recovery contract without simulation."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_open_source_recovery_contract_r01.json"
REPORT_PATH = ROOT / "results" / "reports" / "m01_open_source_recovery_contract_r01_e3.json"
EXPECTED_CHECK_COUNT = 30


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def finite(value: str) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def source_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports = {
        node.names[0].name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
    }
    imports.update(
        (node.module or "").split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
    )
    return imports


def check_contract() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:open_source_recovery_contract",
        config.get("stage_id") == "M01"
        and config.get("contract_id") == "M01_OPEN_SOURCE_RECOVERY_R01"
        and config.get("revision") == 1
        and config.get("status") == "contract_ready"
        and config.get("evidence_level") == "E3"
        and config.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    add_check(
        checks,
        "scope:igzo_2d_laptop_device_only",
        config.get("scope", {}).get("dimension") == "2D"
        and config.get("scope", {}).get("laptop_target") is True
        and config.get("scope", {}).get("active_material_scope") == "IGZO only"
        and config.get("scope", {}).get("device_only_dc") is True
        and config.get("device_contract", {}).get("material") == "IGZO"
        and config.get("device_contract", {}).get("polarity") == "n-type",
        json.dumps(config.get("scope", {}), sort_keys=True),
    )
    add_check(
        checks,
        "history:revision3_and_preflight_failure_bound",
        config["historical_bindings"]["revision3_contract"]["must_remain_unchanged"] is True
        and config["historical_bindings"]["revision3_contract"]["checks_passed"] == 32
        and config["historical_bindings"]["r01_preflight_failure"]["status"] == "FAIL"
        and config["historical_bindings"]["r01_preflight_failure"]["checks_passed"] == 11
        and config["historical_bindings"]["r01_preflight_failure"]["checks_total"] == 13
        and config["historical_bindings"]["r01_preflight_failure"]["aimspice_invoked"] is False
        and config["historical_bindings"]["r01_preflight_failure"]["numerical_outputs_created"] is False,
        "historical E3 contract and 11/13 E0 failure are explicit bindings",
    )
    add_check(
        checks,
        "history:files_and_hashes_preserved",
        all(
            (ROOT / item["path"]).is_file()
            and sha256(ROOT / item["path"]) == item["sha256"]
            for item in [config["historical_bindings"]["revision3_contract"],]
        )
        and (ROOT / config["historical_bindings"]["revision3_contract"]["report_path"]).is_file()
        and sha256(ROOT / config["historical_bindings"]["revision3_contract"]["report_path"])
        == config["historical_bindings"]["revision3_contract"]["report_sha256"]
        and (ROOT / config["historical_bindings"]["r01_preflight_failure"]["config_path"]).is_file()
        and sha256(ROOT / config["historical_bindings"]["r01_preflight_failure"]["config_path"])
        == config["historical_bindings"]["r01_preflight_failure"]["config_sha256"]
        and (ROOT / config["historical_bindings"]["r01_preflight_failure"]["report_path"]).is_file()
        and sha256(ROOT / config["historical_bindings"]["r01_preflight_failure"]["report_path"])
        == config["historical_bindings"]["r01_preflight_failure"]["report_sha256_actual"]
        and (ROOT / config["historical_bindings"]["r01_preflight_failure"]["log_path"]).is_file()
        and sha256(ROOT / config["historical_bindings"]["r01_preflight_failure"]["log_path"])
        == config["historical_bindings"]["r01_preflight_failure"]["log_sha256"]
        and load_json(ROOT / config["historical_paths_to_preserve"][-1]).get("status") == "FAIL",
        "historical configs, reports and raw log match frozen hashes",
    )

    manifest_path = ROOT / config["target_contract"]["selection_manifest"]
    prediction_path = ROOT / config["target_contract"]["prediction_table"]
    manifest_rows, manifest_fields = load_csv(manifest_path)
    prediction_rows, prediction_fields = load_csv(prediction_path)
    add_check(
        checks,
        "targets:files_and_hashes",
        manifest_path.is_file()
        and prediction_path.is_file()
        and sha256(manifest_path) == config["target_contract"]["selection_manifest_sha256"]
        and sha256(prediction_path) == config["target_contract"]["prediction_table_sha256"],
        f"manifest={len(manifest_rows)} predictions={len(prediction_rows)}",
    )
    required_fields = {
        "row_uid", "curve_id", "split", "selection_role", "optimizer_input",
        "vbg_v", "vtg_v", "vds_v", "primary_axis_v", "target_current_a_per_cm",
        "w_um", "l_um", "temperature_k",
    }
    add_check(
        checks,
        "targets:fields_counts_and_roles",
        required_fields.issubset(manifest_fields)
        and required_fields.union({"model_current_a_per_cm"}).issubset(prediction_fields)
        and len(manifest_rows) == 247
        and len(prediction_rows) == 247
        and len({row.get("curve_id") for row in manifest_rows}) == 13
        and sum(row.get("selection_role") == "scored" for row in manifest_rows) == 233
        and sum(row.get("selection_role") == "zero_vds_invariant" for row in manifest_rows) == 7
        and sum(row.get("selection_role") == "repeated_low_vds_audit" for row in manifest_rows) == 7,
        f"fields={len(manifest_fields)}/{len(prediction_fields)} roles={Counter(row.get('selection_role') for row in manifest_rows)}",
    )
    manifest_by_uid = {row["row_uid"]: row for row in manifest_rows}
    prediction_by_uid = {row["row_uid"]: row for row in prediction_rows}
    add_check(
        checks,
        "targets:alignment_finite_geometry",
        set(manifest_by_uid) == set(prediction_by_uid)
        and all(
            manifest_by_uid[uid].get(field) == prediction_by_uid[uid].get(field)
            for uid in manifest_by_uid
            for field in required_fields
        )
        and all(
            finite(row.get(field, ""))
            for row in manifest_rows
            for field in ("vbg_v", "vtg_v", "vds_v", "primary_axis_v", "target_current_a_per_cm", "w_um", "l_um", "temperature_k")
        )
        and all(
            float(row["w_um"]) == 60.0
            and float(row["l_um"]) in {8.0, 10.0, 12.0}
            and float(row["temperature_k"]) == 300.0
            and float(row["vds_v"]) >= 0.0
            for row in manifest_rows
        ),
        "247 target/prediction rows align and remain within frozen geometry",
    )
    ng_route = config["routes"]["ngspice_behavioral"]
    xyce_route = config["routes"]["xyce_source_behavioral"]
    candidate_path = ROOT / ng_route["candidate_path"]
    candidate_text = candidate_path.read_text(encoding="ascii") if candidate_path.is_file() else ""
    add_check(
        checks,
        "routes:two_active_routes_same_candidate_hash",
        config.get("active_routes") == ["ngspice_behavioral", "xyce_source_behavioral"]
        and ng_route["candidate_path"] == xyce_route["candidate_path"]
        and ng_route["candidate_sha256"] == xyce_route["candidate_sha256"]
        and candidate_path.is_file()
        and sha256(candidate_path) == ng_route["candidate_sha256"]
        and ng_route["equation_identity_with_xyce"] is False
        and xyce_route["equation_identity_with_ngspice"] is False,
        "ngspice and Xyce are separate routes over one frozen candidate text",
    )
    forbidden = re.compile(r"\b(?:sno|hzo|ferroelectric|ring_oscillator|full_adder|nand|nor|xor|tran|noise|monte)\b", re.IGNORECASE)
    add_check(
        checks,
        "routes:candidate_is_igzo_behavioral_only",
        ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text
        and "M01_EXECUTION_REQUIRED" in candidate_text
        and ".func M00_Q" in candidate_text
        and "BIDS D S I={" in candidate_text
        and forbidden.search(candidate_text) is None
        and all(token not in candidate_text.lower() for token in ("deepseek_work", "aimspice_improved")),
        "candidate has the frozen IGZO B-source kernel and no excluded route tokens",
    )
    add_check(
        checks,
        "tools:xyce_source_license_and_binary_policy",
        config["xyce_source_provenance"]["license"] == "GPL-3.0-or-later"
        and config["xyce_source_provenance"]["source_build_required"] is True
        and config["xyce_source_provenance"]["proprietary_binary_accepted"] is False
        and config["xyce_source_provenance"]["source_archive_sha256"] == "b5a883196f0a2b3972fd13c541cfecf04735bfabc7d124d7c7e17de707204f4e2"
        and xyce_route["binary_status_at_contract_stage"] == "NOT_BUILT_AT_CONTRACT_STAGE"
        and xyce_route["build_provenance_required_before_run"] is True,
        "pure GPL source build required; no proprietary binary admitted",
    )
    source_review = config["xyce_source_provenance"]["source_review"]
    add_check(
        checks,
        "tools:xyce_source_review_scope",
        source_review["status"] == "STATIC_SOURCE_REVIEW_ONLY"
        and source_review["execution_performed"] is False
        and set(source_review["reviewed_capabilities"]) >= {
            "limit(...) token and three-argument parser production",
            "sgn(...) token and parser production",
            ".func user-defined functions in official test netlists",
            "B-level 1 expression-based voltage or current source",
            "batch positional netlist syntax, -l log path and -o output basename",
        },
        "Xyce capability evidence is source review only",
    )
    add_check(
        checks,
        "batch:syntax_templates_and_self_test_gate",
        config["batch_contract"]["ngspice_argv_template"] == ["{ngspice_path}", "-b", "-o", "{ngspice_log_path}", "{ngspice_netlist_path}"]
        and config["batch_contract"]["xyce_argv_template"] == ["{xyce_path}", "-l", "{xyce_log_path}", "-o", "{xyce_output_basename}", "{xyce_netlist_path}"]
        and config["batch_contract"]["device_netlist_execution_before_self_test"] is False
        and len(config["batch_contract"]["required_preflight_self_tests"]) == 6,
        "both positional batch templates require a committed preflight self-test",
    )
    add_check(
        checks,
        "outputs:unique_future_paths_absent",
        len(set(config["outputs"].values())) == len(config["outputs"])
        and all(not (ROOT / path).exists() for path in config["outputs"].values())
        and config["failure_retention"]["exclusive_outputs"] is True
        and config["failure_retention"]["overwrite_existing_outputs"] is False,
        "contract report and all future run paths are exclusive and absent",
    )
    add_check(
        checks,
        "outputs:historical_paths_not_reused",
        not any(path in config["historical_paths_to_preserve"] for path in config["outputs"].values())
        and config["failure_retention"]["retain_failed_route_logs"] is True
        and config["failure_retention"]["retain_partial_tables"] is True
        and config["failure_retention"]["either_route_failure_stops_m01"] is True,
        "new output namespace is separate and failures remain retained",
    )
    add_check(
        checks,
        "budget:two_routes_no_downstream",
        config["resource_budget"] == {
            "routes": 2,
            "target_rows_per_route": 247,
            "max_generated_device_netlists": 2,
            "max_route_processes": 2,
            "laptop_target": True,
            "circuit_or_transient_runs": False,
            "hzo_runs": False,
            "sno_runs": False,
        }
        and config["no_execution_rules"]["circuit_or_downstream_permitted"] is False,
        json.dumps(config["resource_budget"], sort_keys=True),
    )
    add_check(
        checks,
        "scope:excluded_materials_and_external_reference_only",
        config["excluded_inputs_and_scope"]["active_material_scope"] == "IGZO only"
        and any("SnO" in item for item in config["excluded_inputs_and_scope"]["excluded_assets"])
        and any("HZO" in item for item in config["excluded_inputs_and_scope"]["excluded_assets"])
        and len(config["excluded_inputs_and_scope"]["reference_only_roots"]) == 2,
        "SnO/HZO/circuit and external baselines are excluded or reference-only",
    )
    add_check(
        checks,
        "implementation:checker_is_stdlib_no_invocation",
        source_imports(Path(__file__)).isdisjoint({"numpy", "scipy", "subprocess", "devsim"})
        and config["no_execution_rules"]["contract_checker_must_not_invoke_simulator"] is True
        and config["no_execution_rules"]["contract_checker_must_not_create_device_netlist"] is True,
        f"imports={sorted(source_imports(Path(__file__)))}",
    )
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    add_check(
        checks,
        "implementation:make_target_registered",
        "m01-open-source-recovery-contract-check" in makefile
        and "scripts/check_m01_open_source_recovery_contract.py" in makefile,
        "new static contract target is registered",
    )
    add_check(
        checks,
        "machine_state:experiment_and_project_boundary",
        experiment_map.get("M01", {}).get("status") == "preflight_failed_tool_provenance"
        and experiment_map.get("M01", {}).get("current_evidence") == "E0"
        and experiment_map.get("M01", {}).get("open_source_recovery_contract", {}).get("status") == "contract_ready"
        and experiment_map.get("M01", {}).get("open_source_recovery_contract", {}).get("evidence_level") == "E3"
        and experiment_map.get("M01", {}).get("open_source_recovery_contract", {}).get("simulation_run_by_contract_check") is False
        and project.get("tcad_track", {}).get("m01_open_source_recovery_contract_boundary", "").startswith("The E3 M01 open-source recovery contract")
        and project.get("tcad_track", {}).get("next_scope", "").startswith("implement and commit the pure-source Xyce build/tool preflight"),
        "M01 remains E0 while the new contract is E3 and preflight is next",
    )
    downstream_ids = ["C00", "C01", "C02", "C03", "L00", "V00", "V01", "PEX0", "FE0"]
    add_check(
        checks,
        "machine_state:downstream_closed",
        all(experiment_map.get(item, {}).get("status") in {"planned", "optional"} for item in downstream_ids),
        ",".join(f"{item}={experiment_map.get(item, {}).get('status')}" for item in downstream_ids),
    )
    add_check(
        checks,
        "evidence:boundary_not_overstated",
        "E3 static recovery contract only" in config["evidence_boundary"]
        and "not native AIM-Spice Level 15" in config["evidence_boundary"]
        and "physical calibration" in config["evidence_boundary"]
        and "M01 stays E0/FAIL" in config["evidence_boundary"]
        and "P3, P5, C00" in config["evidence_boundary"],
        "contract text keeps numerical, physical and downstream claims closed",
    )
    add_check(
        checks,
        "implementation:historical_failure_not_reinterpreted",
        experiment_map.get("M01", {}).get("preflight_execution_chain", {}).get("formal_preflight_status") == "FAIL"
        and experiment_map.get("M01", {}).get("preflight_execution_chain", {}).get("open_source_recovery_contract_established") is False,
        "old preflight record remains an immutable E0 failure snapshot",
    )
    add_check(
        checks,
        "next_gate:build_before_device_netlist",
        config["next_gate"].startswith("Implement and commit the pure-source Xyce build/tool preflight")
        and config["batch_contract"]["device_netlist_execution_before_self_test"] is False,
        config["next_gate"],
    )
    add_check(
        checks,
        "targets:split_counts_frozen",
        Counter(row.get("split") for row in manifest_rows) == Counter({"train": 173, "holdout": 74})
        and sum(row.get("split") == "train" and row.get("selection_role") == "scored" for row in manifest_rows) == 163
        and sum(row.get("split") == "holdout" and row.get("selection_role") == "scored" for row in manifest_rows) == 70,
        "train=173/163 scored and holdout=74/70 scored",
    )
    add_check(
        checks,
        "device:port_and_bias_mapping_frozen",
        config["device_contract"]["source_potential_v"] == 0.0
        and config["device_contract"]["port_mapping"]["drain"] == "VDS relative to source"
        and config["device_contract"]["port_mapping"]["bottom_gate"] == "VBG relative to source"
        and config["device_contract"]["port_mapping"]["top_gate"] == "VTG relative to source"
        and config["device_contract"]["port_mapping"]["reported_current"].startswith("absolute drain current"),
        "D/TG/BG/S mapping and |ID|/W reporting are frozen",
    )
    add_check(
        checks,
        "routes:required_candidate_and_tool_fingerprints",
        all(
            route.get("candidate_path") == "spice/models/igzo_dg_behavioral_r02.inc"
            and route.get("candidate_sha256") == ng_route.get("candidate_sha256")
            and route.get("tool_fingerprint_required_before_run") is True
            for route in (ng_route, xyce_route)
        )
        and bool(ng_route.get("tool_path"))
        and bool(xyce_route.get("tool_binary_path")),
        "both routes require a tool fingerprint and the same frozen candidate hash",
    )
    add_check(
        checks,
        "tools:official_source_urls_complete",
        all(
            config["xyce_source_provenance"].get(key, "").startswith("https://")
            for key in ("repository_url", "source_archive_url", "official_downloads_url", "official_build_docs_url", "official_reference_url")
        )
        and config["xyce_source_provenance"]["release_tag"] == "Release-7.10.0",
        "repository, archive, downloads, build and reference URLs are recorded",
    )
    add_check(
        checks,
        "metrics:route_comparison_and_threshold_policy",
        config["metric_contract"]["current_floor_a_per_cm"] == 1e-20
        and "Equal weight per complete scored curve" in config["metric_contract"]["aggregate_weighting"]
        and "not a tunable pass threshold" in config["metric_contract"]["route_difference"]
        and "Do not retune" in config["metric_contract"]["threshold_policy"],
        "linear/log metrics and non-tunable route disagreement are explicit",
    )
    old_numerical_paths = {
        "results/tables/m01_ngspice_r02_raw.csv",
        "results/tables/m01_aimspice_r02_raw.csv",
        "results/tables/m01_route_metrics_r02.csv",
        "results/tables/m01_route_difference_r02.csv",
        "results/compact/m01_simulator_cross_check_r01/ngspice.log",
        "results/compact/m01_simulator_cross_check_r01/aimspice.log",
        "report/assets/m01_simulator_cross_check_r02.png",
        "report/assets/m01_route_difference_r02.png",
        "results/reports/m01_simulator_cross_check_r02.json",
        "results/reports/m01_simulator_cross_check_r02_check.json",
    }
    add_check(
        checks,
        "history:old_numerical_outputs_remain_absent",
        all(not (ROOT / path).exists() for path in old_numerical_paths),
        f"absent={sum(not (ROOT / path).exists() for path in old_numerical_paths)}/{len(old_numerical_paths)}",
    )
    add_check(
        checks,
        "implementation:no_subprocess_or_simulator_code",
        source_imports(Path(__file__)).isdisjoint({"subprocess", "os"})
        and all(
            not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in {"run", "Popen", "system", "execve"}
            )
            for node in ast.walk(ast.parse(Path(__file__).read_text(encoding="utf-8")))
        ),
        "checker performs only file/config checks and no simulator invocation",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        add_check(checks, "checker:registered_check_count", False, f"expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")

    failures = [item for item in checks if item["status"] == "FAIL"]
    report = {
        "status": "PASS" if not failures else "FAIL",
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "fit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "spice_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "circuit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "evidence_level": "E3" if not failures else "E0",
        "contract_id": config["contract_id"],
        "checks": checks,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "target_rows": len(manifest_rows),
            "target_curves": len({row.get("curve_id") for row in manifest_rows}),
            "active_routes": config.get("active_routes", []),
            "outputs_created_by_contract": False,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256(Path(__file__))},
        "next_gate": config["next_gate"],
        "failures": failures,
    }
    dry_run = "--dry-run" in sys.argv[1:]
    if not dry_run:
        if REPORT_PATH.exists():
            raise RuntimeError(f"Refusing to overwrite existing contract report: {REPORT_PATH}")
        with REPORT_PATH.open("x", encoding="utf-8") as stream:
            json.dump(report, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
    print(
        f"M01_OPEN_SOURCE_RECOVERY_CONTRACT_"
        f"{'PASS' if not failures else 'FAIL'} checks="
        f"{len(checks) - len(failures)}/{len(checks)}"
        f"{' dry_run=true' if dry_run else ''}"
        f" report={REPORT_PATH}"
    )
    return report


if __name__ == "__main__":
    result = check_contract()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
