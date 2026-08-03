#!/usr/bin/env python3
"""Check the M01 R02 open-source device DC contract without running a tool."""

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
CONFIG_PATH = ROOT / "config" / "m01_open_source_device_dc_r02.json"
CHECKER_PATH = Path(__file__).resolve()
COMMON_PATH = ROOT / "scripts" / "m01_open_source_device_dc_r02_common.py"
RUNNER_PATH = ROOT / "scripts" / "run_m01_open_source_device_dc_r02.py"
INDEPENDENT_PATH = ROOT / "scripts" / "check_m01_open_source_device_dc_r02.py"
EXPECTED_CHECK_COUNT = 40


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
    checks: list[dict[str, str]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def imports_module(tree: ast.AST, module: str) -> bool:
    return any(
        isinstance(node, ast.Import) and any(alias.name == module for alias in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == module
        for node in ast.walk(tree)
    )


def calls_subprocess(tree: ast.AST) -> int:
    return sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        for node in ast.walk(tree)
    )


def literal_assignment(tree: ast.AST, name: str) -> Any:
    for node in ast.walk(tree):
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            if any(isinstance(target, ast.Name) and target.id == name for target in targets):
                return ast.literal_eval(node.value)
    raise KeyError(name)


def check_contract() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    m01 = experiment_map["M01"]
    r01_machine = m01.get("open_source_device_dc_r01", {})
    machine = m01.get("open_source_device_dc_r02", {})
    checks: list[dict[str, str]] = []
    common_text = COMMON_PATH.read_text(encoding="ascii")
    runner_text = RUNNER_PATH.read_text(encoding="ascii")
    independent_text = INDEPENDENT_PATH.read_text(encoding="ascii")
    common_tree = ast.parse(common_text)
    runner_tree = ast.parse(runner_text)
    independent_tree = ast.parse(independent_text)

    # 1-4: identity, scope, machine state, and registered gates.
    add_check(
        checks,
        "identity:m01_open_source_device_dc_r02",
        config.get("project_id") == "DG-IGZO-TFT-PDK"
        and config.get("stage_id") == "M01"
        and config.get("contract_id") == "M01_OPEN_SOURCE_DEVICE_DC_R02"
        and config.get("revision") == 2
        and config.get("status") == "contract_planned"
        and config.get("evidence_level_before_static_check") == "E0"
        and config.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"contract={config.get('contract_id')} revision={config.get('revision')}",
    )
    scope = config["scope"]
    add_check(
        checks,
        "scope:igzo_device_only_laptop",
        project.get("tcad_track", {}).get("dimension") == "2D"
        and project.get("tcad_track", {}).get("laptop_target") is True
        and scope["active_material_scope"] == "IGZO only"
        and scope["polarity"] == "n-type"
        and scope["upstream_device_model"] == "2D frozen teaching TCAD"
        and scope["execution_scope"] == "compact-model device-only DC cross-check"
        and scope["laptop_target"] is True
        and scope["formal_device_dc"] is True,
        json.dumps(scope, sort_keys=True),
    )
    add_check(
        checks,
        "machine:implementation_before_static_check",
        m01.get("status") == "preflight_failed_tool_provenance"
        and m01.get("current_evidence") == "E0"
        and machine.get("status") == "contract_implemented"
        and machine.get("current_evidence") == "E0"
        and machine.get("contract_check_completed") is False
        and machine.get("formal_run_completed") is False
        and machine.get("runner_processes_invoked") == 0
        and machine.get("circuit_or_downstream_permitted") is False
        and r01_machine.get("status") == "contract_failed_static_checker"
        and r01_machine.get("contract_checks_passed") == 39
        and r01_machine.get("contract_checks_failed") == 1,
        f"root={m01.get('status')} machine={machine.get('status')}",
    )
    registered = config["registered_checks"]
    add_check(
        checks,
        "registry:40_30_24",
        registered == {"static_contract": 40, "runner": 30, "independent": 24}
        and machine.get("expected_contract_check_count") == 40
        and machine.get("expected_runner_check_count") == 30
        and machine.get("expected_independent_check_count") == 24,
        json.dumps(registered, sort_keys=True),
    )

    # 5-9: committed preflight and immutable historical contracts.
    binding = config["committed_preflight_binding"]
    r11_artifacts = [
        (binding["r11_config_path"], binding["r11_config_sha256"]),
        (binding["r11_contract_checker_path"], binding["r11_contract_checker_sha256"]),
        (binding["r11_contract_report_path"], binding["r11_contract_report_sha256"]),
        (binding["r11_runner_path"], binding["r11_runner_sha256"]),
        (binding["r11_runner_report_path"], binding["r11_runner_report_sha256"]),
        (binding["r11_independent_checker_path"], binding["r11_independent_checker_sha256"]),
        (binding["r11_independent_report_path"], binding["r11_independent_report_sha256"]),
        (binding["r11_common_path"], binding["r11_common_sha256"]),
    ]
    add_check(
        checks,
        "binding:r11_artifact_hashes",
        all((ROOT / path).is_file() and sha256(ROOT / path) == expected for path, expected in r11_artifacts)
        and binding["bound_commit"] == "010a51f30e87602e7935bd55e4ee35c38014e9ff",
        f"artifacts={len(r11_artifacts)}",
    )
    r11_static = load_json(ROOT / binding["r11_contract_report_path"])
    r11_runner = load_json(ROOT / binding["r11_runner_report_path"])
    r11_check = load_json(ROOT / binding["r11_independent_report_path"])
    r11_check_status = {
        item.get("name"): item.get("status") for item in r11_check.get("checks", [])
    }
    add_check(
        checks,
        "binding:r11_36_32_25_pass",
        r11_static.get("status") == "PASS"
        and r11_static.get("evidence_level") == "E3"
        and r11_static.get("summary", {}).get("passed") == 36
        and r11_runner.get("status") == "PASS"
        and r11_runner.get("evidence_level") == "E2"
        and r11_runner.get("summary", {}).get("passed") == 32
        and r11_check.get("status") == "PASS"
        and r11_check.get("evidence_level") == "E3"
        and r11_check.get("summary", {}).get("passed") == 25,
        "R11 static/runner/independent reports pass",
    )
    add_check(
        checks,
        "binding:r11_no_formal_or_independent_process",
        r11_runner.get("summary", {}).get("process_invocations") == 4
        and r11_runner.get("summary", {}).get("formal_device_dc_invoked") is False
        and r11_check.get("summary", {}).get("check_count") == 25
        and r11_check.get("summary", {}).get("passed") == 25
        and r11_check.get("summary", {}).get("failed") == 0
        and r11_check_status.get("independence:no_runner_or_process_import") == "PASS"
        and binding["formal_device_dc_invoked_by_r11"] is False
        and binding["must_remain_unchanged"] is True,
        "R11 zero-process evidence uses its persisted 25/25 schema and independence check",
    )
    historical = config["historical_contract_bindings"]
    historical_artifacts = [
        (historical["revision3_contract_path"], historical["revision3_contract_sha256"]),
        (historical["revision3_report_path"], historical["revision3_report_sha256"]),
        (historical["open_source_recovery_path"], historical["open_source_recovery_sha256"]),
        (historical["open_source_recovery_report_path"], historical["open_source_recovery_report_sha256"]),
        (
            historical["implementation_project_check_failure_path"],
            historical["implementation_project_check_failure_sha256"],
        ),
        (historical["r01_config_path"], historical["r01_config_sha256"]),
        (historical["r01_common_path"], historical["r01_common_sha256"]),
        (
            historical["r01_contract_checker_path"],
            historical["r01_contract_checker_sha256"],
        ),
        (historical["r01_runner_path"], historical["r01_runner_sha256"]),
        (
            historical["r01_independent_checker_path"],
            historical["r01_independent_checker_sha256"],
        ),
        (
            historical["r01_contract_failure_path"],
            historical["r01_contract_failure_sha256"],
        ),
        (
            historical["r02_implementation_project_check_failure_path"],
            historical["r02_implementation_project_check_failure_sha256"],
        ),
    ]
    add_check(
        checks,
        "binding:historical_contract_hashes",
        all((ROOT / path).is_file() and sha256(ROOT / path) == expected for path, expected in historical_artifacts),
        f"artifacts={len(historical_artifacts)}",
    )
    revision3_report = load_json(ROOT / historical["revision3_report_path"])
    recovery_report = load_json(ROOT / historical["open_source_recovery_report_path"])
    implementation_failure = load_json(
        ROOT / historical["implementation_project_check_failure_path"]
    )
    r01_failure = load_json(ROOT / historical["r01_contract_failure_path"])
    r02_implementation_failure = load_json(
        ROOT / historical["r02_implementation_project_check_failure_path"]
    )
    r01_failed_checks = [
        item.get("name")
        for item in r01_failure.get("checks", [])
        if item.get("status") == "FAIL"
    ]
    add_check(
        checks,
        "binding:historical_contract_statuses",
        revision3_report.get("status") == "PASS"
        and revision3_report.get("summary", {}).get("passed") == 32
        and recovery_report.get("status") == "PASS"
        and recovery_report.get("summary", {}).get("passed") == 30
        and implementation_failure.get("status") == "FAIL"
        and implementation_failure.get("failures") == 1
        and historical["implementation_project_check_failure_category"]
        == "prediction_table_order_assumption_in_project_checker"
        and historical["implementation_project_check_failure_count"] == 1
        and historical["r01_failure_bound_commit"]
        == "7d5f079ab369de0675e1b658c1f6ec3cfe4ef88c"
        and r01_failure.get("status") == "FAIL"
        and r01_failure.get("evidence_level") == "E0"
        and r01_failure.get("summary", {}).get("passed")
        == historical["r01_contract_failure_passed"]
        == 39
        and r01_failure.get("summary", {}).get("failed")
        == historical["r01_contract_failure_failed"]
        == 1
        and r01_failure.get("summary", {}).get("simulator_processes_invoked") == 0
        and r01_failure.get("summary", {}).get("device_netlists_created") == 0
        and r01_failure.get("summary", {}).get("numerical_outputs_created") == 0
        and r01_failed_checks == [historical["r01_failed_check"]]
        and historical["r01_failure_must_remain_unchanged"] is True
        and r02_implementation_failure.get("status") == "FAIL"
        and r02_implementation_failure.get("failures") == 1
        and historical["r02_implementation_project_check_failure_category"]
        == "contract_checker_audit_literal_misclassified_as_executable_old_schema_read"
        and historical["r02_implementation_project_check_failure_count"] == 1
        and historical["unauthorized_aimspice_excluded"] is True
        and historical["r10_and_earlier_failures_preserved"] is True,
        "revision-3/recovery remain E3 and R01 39/40 failure is immutable",
    )

    # 10-15: exact target selection and candidate bytes.
    target = config["target_contract"]
    manifest_path = ROOT / target["selection_manifest"]
    prediction_path = ROOT / target["prediction_table"]
    manifest_rows, manifest_fields = load_csv(manifest_path)
    prediction_rows, prediction_fields = load_csv(prediction_path)
    add_check(
        checks,
        "targets:files_and_hashes",
        manifest_path.is_file()
        and prediction_path.is_file()
        and sha256(manifest_path) == target["selection_manifest_sha256"]
        and sha256(prediction_path) == target["prediction_table_sha256"],
        f"rows={len(manifest_rows)}/{len(prediction_rows)}",
    )
    required_fields = {
        "row_uid", "curve_id", "dataset_id", "split", "kind", "topology",
        "selection_role", "optimizer_input", "vbg_v", "vtg_v", "vds_v",
        "primary_axis_v", "target_current_a_per_cm", "w_um", "l_um",
        "temperature_k",
    }
    add_check(
        checks,
        "targets:fields_and_row_count",
        required_fields.issubset(manifest_fields)
        and required_fields.union({"model_current_a_per_cm"}).issubset(prediction_fields)
        and len(manifest_rows) == len(prediction_rows) == target["row_count"] == 247,
        f"fields={len(manifest_fields)}/{len(prediction_fields)} rows={len(manifest_rows)}",
    )
    role_counts = Counter(row["selection_role"] for row in manifest_rows)
    add_check(
        checks,
        "targets:roles_and_scored_split",
        role_counts == {"scored": 233, "zero_vds_invariant": 7, "repeated_low_vds_audit": 7}
        and sum(row["selection_role"] == "scored" and row["split"] == "train" for row in manifest_rows) == 163
        and sum(row["selection_role"] == "scored" and row["split"] == "holdout" for row in manifest_rows) == 70,
        str(role_counts),
    )
    add_check(
        checks,
        "targets:curves_geometry_bias_temperature",
        len({row["curve_id"] for row in manifest_rows}) == target["curve_count"] == 13
        and len({row["curve_id"] for row in manifest_rows if row["split"] == "train"}) == 9
        and len({row["curve_id"] for row in manifest_rows if row["split"] == "holdout"}) == 4
        and all(
            math.isfinite(float(row[field]))
            for row in manifest_rows
            for field in ("vbg_v", "vtg_v", "vds_v", "primary_axis_v", "target_current_a_per_cm", "w_um", "l_um", "temperature_k")
        )
        and all(float(row["w_um"]) == 60.0 and float(row["l_um"]) in {8.0, 10.0, 12.0} and float(row["temperature_k"]) == 300.0 and 0.0 <= float(row["vds_v"]) <= 0.2 for row in manifest_rows),
        "13 curves, W=60 um, L=8/10/12 um, 300 K, VDS=0..0.2 V",
    )
    prediction_by_uid = {row["row_uid"]: row for row in prediction_rows}
    add_check(
        checks,
        "targets:manifest_prediction_alignment",
        len({row["row_uid"] for row in manifest_rows}) == len(manifest_rows)
        and len(prediction_by_uid) == len(prediction_rows)
        and {row["row_uid"] for row in manifest_rows} == set(prediction_by_uid)
        and all(
            row[field] == prediction_by_uid[row["row_uid"]][field]
            for row in manifest_rows
            for field in required_fields
        )
        and all(
            math.isfinite(float(row["model_current_a_per_cm"]))
            for row in prediction_rows
        )
        and target["route_tuning_permitted"] is False
        and target["holdout_tuning_permitted"] is False
        and target["external_current_substitution_permitted"] is False,
        "selection manifest fixes route order; prediction rows align by row_uid",
    )
    device = config["device_contract"]
    candidate_path = ROOT / device["candidate_path"]
    candidate_text = candidate_path.read_text(encoding="ascii")
    forbidden_candidate = re.compile(r"\b(?:sno|hzo|ferroelectric|ring_oscillator|full_adder|nand|nor|xor|tran|noise|monte)\b", re.IGNORECASE)
    add_check(
        checks,
        "candidate:hash_ascii_igzo_scope",
        candidate_path.is_file()
        and sha256(candidate_path) == device["candidate_sha256"]
        and candidate_text.isascii()
        and ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text
        and "M01_EXECUTION_REQUIRED" in candidate_text
        and forbidden_candidate.search(candidate_text) is None,
        sha256(candidate_path),
    )

    # 16-23: routes, binaries, argv, netlist, metrics, and resource budget.
    ng_route = config["routes"]["ngspice"]
    xy_route = config["routes"]["xyce"]
    ng_tool = Path(ng_route["tool_path"])
    add_check(
        checks,
        "tool:ngspice_fingerprint",
        ng_tool.is_file()
        and sha256(ng_tool) == ng_route["tool_sha256"]
        and ng_tool.stat().st_size == ng_route["tool_bytes"]
        and ng_route["version_token"] == "ngspice-42"
        and ng_route["one_process_only"] is True,
        f"bytes={ng_tool.stat().st_size if ng_tool.is_file() else None}",
    )
    xy_tool = Path(xy_route["tool_path"])
    add_check(
        checks,
        "tool:xyce_fingerprint_and_license",
        xy_tool.is_file()
        and sha256(xy_tool) == xy_route["tool_sha256"]
        and xy_tool.stat().st_size == xy_route["tool_bytes"]
        and xy_route["version_token"] == "7.10.0"
        and xy_route["license_token"] == "GNU General Public License"
        and xy_route["reused_r07_install"] is True
        and xy_route["one_process_only"] is True,
        f"bytes={xy_tool.stat().st_size if xy_tool.is_file() else None}",
    )
    add_check(
        checks,
        "routes:same_candidate_separate_identity",
        device["same_candidate_bytes_for_both_routes"] is True
        and device["equation_identity_claimed"] is False
        and ng_route["route_id"] == "ngspice_behavioral"
        and xy_route["route_id"] == "xyce_source_behavioral"
        and ng_route["raw_format"] == "ngspice_ascii_raw"
        and xy_route["raw_format"] == "Xyce_PRN_FIXED_COLUMNS",
        "same bytes, separate simulator routes, no equation-identity claim",
    )
    outputs = config["outputs"]
    expected_ng_argv = [ng_route["tool_path"], "-b", "-o", outputs["ngspice_log"], outputs["ngspice_netlist"]]
    expected_xy_argv = [xy_route["tool_path"], "-l", outputs["xyce_log"], "-o", "results/compact/m01_open_source_cross_check_r02/xyce_values", outputs["xyce_netlist"]]
    add_check(
        checks,
        "routes:exact_batch_argv_and_cwd",
        [item.format(tool=ng_route["tool_path"]) for item in ng_route["argv_template"]] == expected_ng_argv
        and [item.format(tool=xy_route["tool_path"]) for item in xy_route["argv_template"]] == expected_xy_argv
        and config["netlist_contract"]["runner_working_directory"] == "project_root",
        "one ngspice batch argv and one Xyce batch argv",
    )
    netlist = config["netlist_contract"]
    add_check(
        checks,
        "netlist:two_by_247_dc_contract",
        netlist["netlists"] == 2
        and netlist["devices_per_netlist"] == 247
        and netlist["analysis"] == ".DC VSWEEP 0 0 1"
        and netlist["dummy_sweep_source"] == "VSWEEP SWEEP 0 0"
        and netlist["candidate_include"] == '.include "spice/models/igzo_dg_behavioral_r02.inc"'
        and netlist["include_path_mode"] == "repository_relative_ascii"
        and netlist["netlist_encoding"] == "ascii"
        and netlist["external_include_permitted"] is False
        and netlist["circuit_instance_permitted"] is False,
        json.dumps(netlist, sort_keys=True),
    )
    add_check(
        checks,
        "netlist:output_extraction_methods",
        netlist["ngspice_output_method"] == ".save I(VDSnnn) plus one ASCII raw write"
        and netlist["xyce_output_method"] == ".PRINT DC FORMAT=NOINDEX PRECISION=17 I(VDSnnn)"
        and ng_route["raw_output"] == outputs["ngspice_raw_output"]
        and xy_route["raw_output"] == outputs["xyce_raw_output"]
        and all(token.lower() in {item.lower() for item in netlist["forbidden_case_insensitive_tokens"]} for token in ("sno", "hzo", "ferroelectric", ".tran")),
        "route-specific persisted raw formats are frozen",
    )
    extraction = config["extraction_contract"]
    add_check(
        checks,
        "extraction:formula_counts_and_diagnostic_policy",
        extraction["current_sign"] == "absolute voltage-source current"
        and extraction["width_normalization_cm"] == "W_um*1e-4"
        and extraction["current_floor_a_per_cm"] == 1e-20
        and extraction["raw_rows_per_route"] == 247
        and extraction["route_metric_rows"] == 30
        and extraction["route_difference_rows"] == 247
        and extraction["zero_vds_max_current_a_per_cm"] == 1e-18
        and extraction["route_to_target_thresholds_are_diagnostic_only"] is True
        and extraction["route_difference_threshold_is_not_a_pass_gate"] is True
        and extraction["finite_complete_outputs_are_required"] is True,
        json.dumps(extraction, sort_keys=True),
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "resource:exact_two_process_budget",
        budget == {
            "route_processes": 2,
            "ngspice_processes": 1,
            "xyce_processes": 1,
            "generated_device_netlists": 2,
            "parallel_route_execution": False,
            "laptop_target": True,
            "tcad_processes": 0,
            "aimspice_processes": 0,
            "circuit_processes": 0,
            "layout_processes": 0,
        },
        json.dumps(budget, sort_keys=True),
    )

    # 24-34: implementation source contracts.
    add_check(
        checks,
        "source:common_standard_library_core",
        COMMON_PATH.is_file()
        and common_text.isascii()
        and not imports_module(common_tree, "subprocess")
        and calls_subprocess(common_tree) == 0
        and all(marker in common_text for marker in ("generate_device_netlist", "parse_ngspice_ascii_raw", "parse_xyce_prn", "compute_metrics", "compute_route_differences", "render_plots")),
        f"sha256={sha256(COMMON_PATH)}",
    )
    runner_check_names = literal_assignment(runner_tree, "CHECK_NAMES")
    add_check(
        checks,
        "source:runner_registry",
        literal_assignment(runner_tree, "EXPECTED_CHECK_COUNT") == 30
        and isinstance(runner_check_names, list)
        and len(runner_check_names) == len(set(runner_check_names)) == 30,
        f"checks={len(runner_check_names)}",
    )
    add_check(
        checks,
        "source:runner_only_process_api",
        imports_module(runner_tree, "subprocess")
        and calls_subprocess(runner_tree) == 1
        and runner_text.count("process_invocations += 1") == 2
        and runner_text.count("_run_command(") == 3,
        f"subprocess_calls={calls_subprocess(runner_tree)} process_markers={runner_text.count('process_invocations += 1')}",
    )
    add_check(
        checks,
        "source:runner_exact_routes_and_order",
        runner_text.find('ng_route = config["routes"]["ngspice"]')
        < runner_text.find('xy_route = config["routes"]["xyce"]')
        and "formal_device_dc_invoked = True" in runner_text
        and '"aimspice_invoked": False' in runner_text
        and '"tcad_invoked": False' in runner_text
        and '"circuit_or_downstream_invoked": False' in runner_text
        and 'machine.get("status") == "contract_ready"' in runner_text
        and 'r11_check_status.get("independence:no_runner_or_process_import")'
        in runner_text
        and 'r11_check.get("processes_invoked")' not in runner_text
        and "execute the committed M01 open-source device DC revision-2 two-route runner"
        in runner_text,
        "ngspice first; Xyce second; excluded processes false",
    )
    add_check(
        checks,
        "source:runner_exclusive_failure_retention",
        "exist_ok=False" in runner_text
        and "runner refuses to overwrite" in runner_text
        and "except Exception as exc" in runner_text
        and "failure_category" in runner_text
        and "failure_detail" in runner_text
        and "Preserve and commit this formal-run failure" in runner_text,
        "exclusive outputs and structured failure report",
    )
    add_check(
        checks,
        "source:runner_two_netlist_generation",
        runner_text.count("generate_device_netlist(") == 2
        and '"ngspice"' in runner_text
        and '"xyce"' in runner_text
        and "encoding=\"ascii\"" in runner_text
        and "XDEV" in runner_text,
        "two deterministic ASCII netlists",
    )
    add_check(
        checks,
        "source:runner_parser_metrics_outputs",
        all(marker in runner_text for marker in ("parse_ngspice_ascii_raw", "parse_xyce_prn", "extract_route_rows", "compute_metrics", "compute_route_differences", "write_csv", "render_plots")),
        "raw parsing, extraction, metrics, difference and figures implemented",
    )
    add_check(
        checks,
        "source:independent_no_runner_or_process",
        INDEPENDENT_PATH.is_file()
        and independent_text.isascii()
        and "run_m01_open_source_device_dc_r02" in independent_text
        and not imports_module(independent_tree, "subprocess")
        and calls_subprocess(independent_tree) == 0
        and not any(isinstance(node, ast.ImportFrom) and node.module == "run_m01_open_source_device_dc_r02" for node in ast.walk(independent_tree))
        and 'machine.get("status") == "formal_run_passed"' in independent_text
        and 'r11_check_status.get("independence:no_runner_or_process_import")'
        in independent_text
        and 'r11_check.get("processes_invoked")' not in independent_text
        and "run the independent persisted-evidence checker for M01 open-source device DC revision-2"
        in independent_text,
        f"sha256={sha256(INDEPENDENT_PATH)}",
    )
    add_check(
        checks,
        "source:independent_registry",
        literal_assignment(independent_tree, "EXPECTED_CHECK_COUNT") == 24
        and independent_text.count("add_check(") - 1 == 24,
        f"registered={independent_text.count('add_check(') - 1}",
    )
    add_check(
        checks,
        "source:independent_recomputation_scope",
        all(marker in independent_text for marker in ("generate_device_netlist", "parse_ngspice_ascii_raw", "parse_xyce_prn", "extract_route_rows", "compute_metrics", "compute_route_differences", "csv_matches", "png_dimensions"))
        and "processes_invoked\": 0" in independent_text,
        "independent parser/table/metric/PNG/hash recomputation",
    )
    makefile_text = (ROOT / "Makefile").read_text(encoding="utf-8")
    add_check(
        checks,
        "make:three_gated_targets",
        "m01-open-source-device-dc-r02-contract-check:" in makefile_text
        and "scripts/check_m01_open_source_device_dc_r02_contract.py" in makefile_text
        and "m01-open-source-device-dc-r02:" in makefile_text
        and "scripts/run_m01_open_source_device_dc_r02.py" in makefile_text
        and "m01-open-source-device-dc-r02-check:" in makefile_text
        and "scripts/check_m01_open_source_device_dc_r02.py" in makefile_text,
        "contract, runner and independent targets registered",
    )

    # 35-40: output exclusivity, failure policy, boundary, and next gate.
    output_values = list(outputs.values())
    future_paths = [ROOT / value for value in output_values]
    add_check(
        checks,
        "outputs:unique_paths",
        len(output_values) == len(set(output_values))
        and outputs["run_directory"] == "results/compact/m01_open_source_cross_check_r02"
        and outputs["run_report"] == "results/reports/m01_open_source_cross_check_r02.json"
        and outputs["independent_check_report"] == "results/reports/m01_open_source_cross_check_r02_check.json",
        f"paths={len(output_values)} unique={len(set(output_values))}",
    )
    add_check(
        checks,
        "outputs:all_future_paths_absent",
        all(not path.exists() for path in future_paths),
        f"absent={sum(not path.exists() for path in future_paths)}/{len(future_paths)}",
    )
    failure = config["failure_retention"]
    add_check(
        checks,
        "failure:retention_and_no_relaxation",
        all(
            failure[key] is True
            for key in (
                "exclusive_outputs", "retain_failed_route_netlist", "retain_failed_route_log",
                "retain_partial_raw_output", "retain_partial_tables", "write_failure_report",
                "first_route_failure_stops_second_route", "independent_checker_runs_only_after_runner_pass_commit",
                "r11_and_historical_evidence_must_not_change",
            )
        )
        and failure["overwrite_existing_outputs"] is False
        and failure["threshold_relaxation_permitted"] is False,
        json.dumps(failure, sort_keys=True),
    )
    no_execution = config["no_execution_rules"]
    add_check(
        checks,
        "static:no_execution_rules",
        all(no_execution[key] is True for key in ("static_checker_must_not_import_runner", "static_checker_must_not_import_or_call_subprocess", "static_checker_must_not_create_device_netlist", "static_checker_must_not_create_numerical_output", "runner_requires_committed_static_pass", "independent_checker_must_not_import_runner", "independent_checker_must_not_import_or_call_subprocess"))
        and no_execution["r11_or_earlier_preflight_rerun_permitted"] is False
        and no_execution["aimspice_invocation_permitted"] is False
        and no_execution["circuit_or_downstream_permitted"] is False
        and not imports_module(ast.parse(CHECKER_PATH.read_text(encoding="ascii")), "subprocess"),
        json.dumps(no_execution, sort_keys=True),
    )
    boundary = config["evidence_boundary"]
    add_check(
        checks,
        "boundary:static_only_and_prohibited_claims",
        all(term in boundary for term in ("schema-only correction", "247 persisted target rows", "invokes no simulator", "AIM-Spice", "equation identity", "physical IGZO parameters", "experimental calibration", "C00 remain closed")),
        boundary,
    )
    next_gate = config["next_gate"]
    next_scope = project.get("tcad_track", {}).get("next_scope", "")
    add_check(
        checks,
        "boundary:next_gate_static_before_routes",
        "Commit and push this R02 schema-only implementation" in next_gate
        and "40-check static contract exactly once" in next_gate
        and "Do not execute either device route" in next_gate
        and next_scope.startswith("establish and commit M01 open-source device DC revision-2")
        and machine.get("next_gate") == next_gate,
        next_gate,
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"static registry mismatch expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    passed = sum(item["status"] == "PASS" for item in checks)
    failed = EXPECTED_CHECK_COUNT - passed
    return {
        "schema_version": "1.0",
        "project_id": config["project_id"],
        "stage_id": "M01",
        "contract_id": config["contract_id"],
        "status": "PASS" if failed == 0 else "FAIL",
        "evidence_level": "E3" if failed == 0 else "E0",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "contract_checker": {"path": str(CHECKER_PATH.relative_to(ROOT)), "sha256": sha256(CHECKER_PATH)},
        "common": {"path": str(COMMON_PATH.relative_to(ROOT)), "sha256": sha256(COMMON_PATH)},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "independent_checker": {"path": str(INDEPENDENT_PATH.relative_to(ROOT)), "sha256": sha256(INDEPENDENT_PATH)},
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": EXPECTED_CHECK_COUNT,
            "build_processes_invoked": 0,
            "simulator_processes_invoked": 0,
            "device_netlists_created": 0,
            "numerical_outputs_created": 0,
            "formal_device_dc_invoked": False,
            "aimspice_invoked": False,
            "tcad_invoked": False,
            "circuit_or_downstream_invoked": False,
        },
        "checks": checks,
        "future_outputs_absent_before_report": all(not path.exists() for path in future_paths),
        "evidence_boundary": boundary,
        "next_gate": (
            "Commit and push this 40/40 E3 static PASS before the one permitted two-route runner. Do not run the independent checker or C00."
            if failed == 0
            else "Preserve and commit this static contract failure. Do not execute either route or relax the contract."
        ),
    }


def main() -> int:
    config = load_json(CONFIG_PATH)
    report_path = ROOT / config["outputs"]["contract_report"]
    if report_path.exists():
        raise RuntimeError(f"static checker refuses to overwrite {report_path}")
    report = check_contract()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    summary = report["summary"]
    print(
        f"M01_OPEN_SOURCE_DEVICE_DC_R02_CONTRACT_{report['status']} "
        f"checks={summary['passed']}/{summary['total']} report={report_path}"
    )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
