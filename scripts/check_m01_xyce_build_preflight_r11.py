#!/usr/bin/env python3
"""Independently check persisted R11 Xyce output/parser evidence."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from m01_xyce_r11_common import digest_tree, load_json, read_xyce_prn, sha256, tree_matches


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r11.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r11.py"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_r11.json"
CHECK_REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_check_r11.json"
EXPECTED_CHECK_COUNT = 25
EXPECTED_RUNNER_CHECK_COUNT = 32


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_preflight() -> dict[str, Any]:
    if CHECK_REPORT_PATH.exists():
        raise RuntimeError(f"R11 refuses to overwrite {CHECK_REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    report = load_json(REPORT_PATH)
    outputs = config["outputs"]
    checks: list[dict[str, str]] = []
    runner_checks = report.get("checks", [])
    r07 = config["r07_failure_binding"]
    r07_report_path = ROOT / r07["preflight_report_path"]
    r07_report = load_json(r07_report_path)
    r07_artifacts = [
        (r07["config_path"], r07["config_sha256"]),
        (r07["contract_checker_path"], r07["contract_checker_sha256"]),
        (r07["contract_report_path"], r07["contract_report_sha256"]),
        (r07["runner_path"], r07["runner_sha256"]),
        (r07["independent_checker_path"], r07["independent_checker_sha256"]),
        (r07["preflight_report_path"], r07["preflight_report_sha256"]),
        (r07["preflight_log_path"], r07["preflight_log_sha256"]),
        (r07["source_manifest_path"], r07["source_manifest_sha256"]),
        (r07["build_manifest_path"], r07["build_manifest_sha256"]),
        (r07["self_test_output_path"], r07["self_test_output_sha256"]),
        (r07["xyce_build_log_path"], r07["xyce_build_log_sha256"]),
    ]
    r10 = config["r10_failure_binding"]
    r10_static_report_path = ROOT / r10["static_contract_report_path"]
    r10_failure_report_path = ROOT / r10["runner_failure_report_path"]
    r10_static_report = load_json(r10_static_report_path)
    r10_failure_report = load_json(r10_failure_report_path)
    r10_artifacts = [
        (r10["config_path"], r10["config_sha256"]),
        (r10["common_hash_helper_path"], r10["common_hash_helper_sha256"]),
        (r10["contract_checker_path"], r10["contract_checker_sha256"]),
        (r10["runner_path"], r10["runner_sha256"]),
        (r10["independent_checker_path"], r10["independent_checker_sha256"]),
        (r10["static_contract_report_path"], r10["static_contract_report_sha256"]),
        (r10["runner_failure_report_path"], r10["runner_failure_report_sha256"]),
        (r10["runner_failure_log_path"], r10["runner_failure_log_sha256"]),
    ]
    r10_partial_directory = ROOT / r10["partial_run_directory"]
    r10_summary = r10_failure_report.get("summary", {})
    add_check(
        checks,
        "result:runner_passed_all_registered_checks",
        report.get("status") == "PASS"
        and report.get("preflight_status") == "PASS"
        and report.get("evidence_level") == "E2"
        and len(runner_checks) == EXPECTED_RUNNER_CHECK_COUNT
        and all(item.get("status") == "PASS" for item in runner_checks),
        f"passed={sum(item.get('status') == 'PASS' for item in runner_checks)}/{len(runner_checks)}",
    )
    summary = report.get("summary", {})
    add_check(
        checks,
        "result:reuse_tool_only",
        report.get("build_status") == "REUSED_HASH_BOUND_R07_INSTALL"
        and summary.get("build_processes_invoked") == 0
        and summary.get("generator_build_invoked") is False
        and summary.get("dependency_rebuild_invoked") is False
        and summary.get("r07_complete_generator_prefix_reused") is True
        and summary.get("r07_complete_xyce_prefix_reused") is True
        and summary.get("formal_device_dc_invoked") is False,
        "R11 reuses complete R07 installs and executes only tool/parser commands",
    )
    add_check(
        checks,
        "identity:config_runner_hash",
        report.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and report.get("runner", {}).get("sha256") == sha256(RUNNER_PATH)
        and report.get("preflight_id") == config["preflight_id"],
        "R11 report binds current config, runner and preflight id",
    )
    add_check(
        checks,
        "binding:historical_failures",
        r07_report.get("status") == "FAIL"
        and r07_report.get("evidence_level") == "E0"
        and len(r07_report.get("checks", [])) == 47
        and sum(item.get("status") == "PASS" for item in r07_report.get("checks", [])) == 42
        and sha256(r07_report_path) == r07["preflight_report_sha256"]
        and r10_static_report.get("status") == "PASS"
        and r10_static_report.get("evidence_level") == "E3"
        and r10_static_report.get("summary", {}).get("passed") == 36
        and r10_static_report.get("summary", {}).get("failed") == 0
        and r10_failure_report.get("status") == "FAIL"
        and r10_failure_report.get("evidence_level") == "E0"
        and r10_failure_report.get("failure_category")
        == "runner_unicode_path_ascii_encoding"
        and r10_summary.get("process_invocations") == 3
        and r10_summary.get("controlled_bsource_self_test_invoked") is True
        and r10_summary.get("device_syntax_only_invoked") is False
        and r10_summary.get("formal_device_dc_invoked") is False
        and r10_failure_report.get("commands_completed", [{}])[-1].get(
            "observed_self_test_value_v"
        )
        == 1.25,
        "immutable R07 and R10 failures remain hash-bound",
    )
    add_check(
        checks,
        "binding:historical_artifacts",
        all(
            (ROOT / path).is_file() and sha256(ROOT / path) == expected
            for path, expected in r07_artifacts + r10_artifacts
        )
        and r10["bound_commit"] == "63be6a45e583b61027b18614cec4f83ce93848ad"
        and r10["runner_rerun"] is False
        and r10["independent_checker_run"] is False
        and tree_matches(r10_partial_directory, r10["partial_run_tree"]),
        f"artifacts={sum((ROOT / path).is_file() for path, _ in r07_artifacts + r10_artifacts)}/{len(r07_artifacts + r10_artifacts)}",
    )
    add_check(
        checks,
        "identity:revision_11_contract",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R11"
        and config.get("revision") == 11
        and config.get("status") == "preflight_planned"
        and config.get("evidence_level_before_run") == "E0",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    generator_prefix = Path(r07["generator_prefix"])
    xyce_prefix = Path(r07["xyce_prefix"])
    add_check(
        checks,
        "binding:generator_tree",
        tree_matches(generator_prefix, r07["generator_prefix_tree"]),
        digest_tree(generator_prefix).get("tree_sha256") if generator_prefix.is_dir() else "absent",
    )
    add_check(
        checks,
        "binding:xyce_tree",
        tree_matches(xyce_prefix, r07["xyce_prefix_tree"]),
        digest_tree(xyce_prefix).get("tree_sha256") if xyce_prefix.is_dir() else "absent",
    )
    xyce_binary = Path(config["toolchain"]["xyce_binary"])
    reuse_manifest = ROOT / outputs["reuse_manifest"]
    add_check(
        checks,
        "binary:hash_version",
        xyce_binary.is_file()
        and sha256(xyce_binary) == r07["xyce_binary_sha256"]
        and report.get("xyce_binary", {}).get("sha256") == sha256(xyce_binary)
        and "7.10.0" in json.dumps(report.get("checks", [])),
        f"sha256={sha256(xyce_binary) if xyce_binary.is_file() else None}",
    )
    run_directory = ROOT / outputs["run_directory"]
    self_test_netlist = ROOT / outputs["bsource_self_test_netlist"]
    self_test_output = ROOT / outputs["bsource_self_test_output"]
    self_test_log = ROOT / outputs["bsource_self_test_log"]
    add_check(
        checks,
        "self_test:netlist_scope",
        self_test_netlist.is_file()
        and "Btest" in self_test_netlist.read_text(encoding="ascii")
        and all(
            token.lower() not in self_test_netlist.read_text(encoding="ascii").lower()
            for token in config["self_test"]["forbidden_tokens"]
        ),
        "controlled scalar source only",
    )
    observed_v = read_xyce_prn(self_test_output, config["self_test"]["expected_column"])
    expected_v = float(config["self_test"]["expected_value_v"])
    add_check(
        checks,
        "self_test:prn_value",
        self_test_output.is_file()
        and sha256(self_test_output) == report.get("artifacts", {}).get("self_test_output_sha256")
        and observed_v is not None
        and abs(observed_v - expected_v) <= float(config["self_test"]["tolerance_v"]),
        f"observed={observed_v} expected={expected_v}",
    )
    add_check(
        checks,
        "self_test:prn_artifact",
        self_test_output.is_file()
        and self_test_output.suffix == ".prn"
        and "V(NOUT)" in self_test_output.read_text(encoding="utf-8"),
        str(self_test_output.relative_to(ROOT)),
    )
    add_check(
        checks,
        "self_test:logs",
        self_test_log.is_file()
        and (run_directory / "xyce_bsource_self_test.log").is_file(),
        "Xyce log and command wrapper log persisted",
    )
    device_netlist = ROOT / outputs["device_syntax_netlist"]
    device_log = ROOT / outputs["device_syntax_log"]
    device_output = ROOT / outputs["device_syntax_output"]
    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    device_text = device_netlist.read_text(encoding="ascii") if device_netlist.is_file() else ""
    add_check(
        checks,
        "device_syntax:netlist_scope",
        device_netlist.is_file()
        and candidate.is_file()
        and sha256(candidate) == config["device_syntax_check"]["candidate_sha256"]
        and "IGZO_DG_BEHAVIORAL_R02" in device_text
        and len(device_text.splitlines()) > 1
        and device_text.splitlines()[1]
        == f'.include "{config["device_syntax_check"]["include_path"]}"'
        and config["device_syntax_check"]["include_path_mode"]
        == "repository_relative_ascii"
        and config["device_syntax_check"]["include_path"].isascii()
        and not Path(config["device_syntax_check"]["include_path"]).is_absolute()
        and config["device_syntax_check"]["runner_working_directory"] == "project_root"
        and config["device_syntax_check"]["netlist_encoding"] == "ascii"
        and config["device_syntax_check"]["absolute_project_path_forbidden"] is True
        and str(ROOT) not in device_text
        and ".TRAN" not in device_text.upper(),
        "frozen IGZO candidate parser input uses a repository-relative ASCII include",
    )
    add_check(
        checks,
        "device_syntax:parser_pass",
        report.get("device_syntax_status") == "PASS"
        and device_log.is_file()
        and any(item.get("name") == "xyce_device_syntax" and item.get("returncode") == 0 for item in report.get("commands", [])),
        "Xyce -syntax parser-only command passed",
    )
    add_check(
        checks,
        "device_syntax:no_numerical_output",
        not device_output.exists(),
        f"output_exists={device_output.exists()}",
    )
    command_records = report.get("commands", [])
    add_check(
        checks,
        "execution:only_commands",
        len(command_records) == 4
        and {item.get("name") for item in command_records}
        == {"xyce_version", "xyce_license", "xyce_bsource_self_test", "xyce_device_syntax"},
        f"commands={len(command_records)}",
    )
    formal_paths = [ROOT / value for value in config["formal_outputs_that_must_remain_absent"]]
    add_check(
        checks,
        "execution:no_formal",
        all(not path.exists() for path in formal_paths)
        and summary.get("formal_m01_outputs_created") is False,
        f"formal_absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    add_check(
        checks,
        "execution:no_ngspice",
        summary.get("ngspice_invoked") is False
        and summary.get("aimspice_invoked") is False
        and all("ngspice" not in str(item.get("argv", [])).lower() for item in command_records)
        and all("aimspice" not in str(item.get("argv", [])).lower() for item in command_records),
        "only the bound Xyce binary was invoked",
    )
    execution_manifest = ROOT / outputs["execution_manifest"]
    add_check(
        checks,
        "manifests:reuse_and_execution",
        reuse_manifest.is_file()
        and execution_manifest.is_file()
        and report.get("reuse_manifest", {}).get("sha256") == sha256(reuse_manifest)
        and report.get("execution_manifest", {}).get("sha256") == sha256(execution_manifest),
        "reuse and command manifests match report hashes",
    )
    preflight_log = ROOT / outputs["preflight_log"]
    add_check(
        checks,
        "manifests:preflight_log",
        preflight_log.is_file()
        and "build_invoked=false" in preflight_log.read_text(encoding="utf-8")
        and "formal_device_dc_invoked=false" in preflight_log.read_text(encoding="utf-8")
        and "r10_failure_preserved=true" in preflight_log.read_text(encoding="utf-8")
        and "r10_runner_rerun=false" in preflight_log.read_text(encoding="utf-8")
        and "parser_include_path_mode=repository_relative_ascii"
        in preflight_log.read_text(encoding="utf-8"),
        "R11 no-build and path-safe boundaries persisted",
    )
    add_check(
        checks,
        "config:igzo_candidate_binding",
        config["scope"]["active_material_scope"] == "IGZO only"
        and config["device_syntax_check"]["candidate_sha256"] == sha256(candidate),
        "IGZO-only candidate hash",
    )
    checker_source = (ROOT / "scripts" / "check_m01_xyce_build_preflight_r11.py").read_text(encoding="utf-8")
    common_source = (ROOT / "scripts" / "m01_xyce_r11_common.py").read_text(encoding="utf-8")
    process_import = "import " + "sub" + "process"
    process_call = "sub" + "process."
    add_check(
        checks,
        "independence:no_runner_or_process_import",
        process_import not in checker_source
        and process_call not in checker_source
        and "run_m01_xyce_build_preflight_r11.py" in checker_source
        and process_import not in common_source,
        "independent checker only reads persisted evidence",
    )
    add_check(
        checks,
        "boundary:formal_requires_independent",
        config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True
        and config["no_execution_rules"]["r10_runner_must_not_be_rerun"] is True
        and "independent" in config["next_gate"],
        config["next_gate"],
    )
    add_check(
        checks,
        "registry:output_suffix_prn",
        config["self_test"]["output_suffix"] == ".prn"
        and "read_xyce_prn" in common_source
        and "bsource_self_test_output" in (ROOT / "scripts" / "run_m01_xyce_build_preflight_r11.py").read_text(encoding="utf-8"),
        "R11 binds Xyce fixed-column .prn parsing",
    )
    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"R11 independent registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")
    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E3",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "checks": checks,
        "failures": failures,
        "summary": {"check_count": len(checks), "passed": len(checks) - len(failures), "failed": len(failures)},
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256(Path(__file__))},
        "runner_report": {"path": str(REPORT_PATH.relative_to(ROOT)), "sha256": sha256(REPORT_PATH)},
        "observed_self_test_value_v": observed_v,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": "Formal M01 remains closed; this report is tool/parser evidence only.",
    }
    CHECK_REPORT_PATH.write_text(json.dumps(result, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_R11_CHECK_{result['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={CHECK_REPORT_PATH}"
    )
    return result


if __name__ == "__main__":
    result = check_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
