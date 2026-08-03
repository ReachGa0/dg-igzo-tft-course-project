#!/usr/bin/env python3
"""Check the R08 Xyce output/parser contract without running any process."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from m01_xyce_r08_common import digest_tree, load_json, read_xyce_prn, sha256, tree_matches


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r08.json"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r08.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r08.py"
CHECKER_PATH = ROOT / "scripts" / "check_m01_xyce_build_preflight_r08.py"
COMMON_PATH = ROOT / "scripts" / "m01_xyce_r08_common.py"
EXPECTED_CHECK_COUNT = 36


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract() -> dict[str, Any]:
    if REPORT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite existing R08 contract report: {REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    m01 = next(item for item in experiments["experiments"] if item["id"] == "M01")
    machine = m01.get("xyce_build_preflight_r08", {})
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:revision_8_xyce_parser_recovery",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R08"
        and config.get("revision") == 8
        and config.get("status") == "preflight_planned"
        and config.get("evidence_level_before_run") == "E0",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    add_check(
        checks,
        "identity:machine_contract_planned",
        machine.get("status") == "contract_planned"
        and machine.get("revision") == 8
        and machine.get("current_evidence") == "E0"
        and machine.get("contract_check_completed") is False
        and machine.get("result_paths") == []
        and machine.get("artifact_hashes") == {},
        json.dumps(machine, sort_keys=True),
    )

    r07 = config["r07_failure_binding"]
    r07_report_path = ROOT / r07["preflight_report_path"]
    r07_report = load_json(r07_report_path)
    r07_artifact_bindings = [
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
    add_check(
        checks,
        "binding:r07_failure_report",
        r07["bound_commit"] == "9a7375ef30ae90adf5214b3c7421a5f7a8cab726"
        and r07_report.get("status") == "FAIL"
        and r07_report.get("evidence_level") == "E0"
        and r07_report.get("preflight_status") == "FAIL"
        and r07_report.get("build_status") == "PASS"
        and len(r07_report.get("checks", [])) == 47
        and sum(item.get("status") == "PASS" for item in r07_report.get("checks", [])) == 42
        and sha256(r07_report_path) == r07["preflight_report_sha256"],
        "immutable R07 42/47 E0 runner failure",
    )
    add_check(
        checks,
        "binding:r07_artifacts_hash_bound",
        r07["must_remain_unchanged"] is True
        and all(
            (ROOT / path).is_file() and sha256(ROOT / path) == expected
            for path, expected in r07_artifact_bindings
        ),
        f"artifacts={sum((ROOT / path).is_file() for path, _ in r07_artifact_bindings)}/{len(r07_artifact_bindings)}",
    )
    r07_output = ROOT / r07["self_test_output_path"]
    add_check(
        checks,
        "binding:r07_prn_failure_observation",
        r07_output.suffix == ".prn"
        and read_xyce_prn(r07_output, "V(NOUT)") == 1.25
        and r07_report.get("summary", {}).get("device_syntax_only_invoked") is False
        and r07_report.get("summary", {}).get("formal_device_dc_invoked") is False,
        "R07 retained fixed-column .prn observation and stopped before syntax",
    )

    generator_prefix = Path(r07["generator_prefix"])
    xyce_prefix = Path(r07["xyce_prefix"])
    add_check(
        checks,
        "binding:r07_generator_tree",
        tree_matches(generator_prefix, r07["generator_prefix_tree"]),
        digest_tree(generator_prefix).get("tree_sha256") if generator_prefix.is_dir() else "absent",
    )
    add_check(
        checks,
        "binding:r07_xyce_tree",
        tree_matches(xyce_prefix, r07["xyce_prefix_tree"]),
        digest_tree(xyce_prefix).get("tree_sha256") if xyce_prefix.is_dir() else "absent",
    )

    scope = config["scope"]
    add_check(
        checks,
        "scope:igzo_2d_laptop_tool_only",
        scope.get("active_material_scope") == "IGZO only"
        and scope.get("dimension", "").startswith("2D")
        and scope.get("laptop_target") is True
        and scope.get("device_netlist_execution") is False
        and scope.get("formal_m01_numerical_run") is False
        and scope.get("circuit_or_downstream_permitted") is False,
        json.dumps(scope, sort_keys=True),
    )
    reuse = config["reuse_policy"]
    tools = config["toolchain"]
    add_check(
        checks,
        "reuse:no_build_or_dependency_rebuild",
        reuse.get("reuse_complete_r07_generator_prefix") is True
        and reuse.get("reuse_complete_r07_xyce_prefix") is True
        and reuse.get("reuse_r07_binary_only_after_hash_check") is True
        and reuse.get("rebuild_generator_or_xyce") is False
        and reuse.get("reuse_r07_build_directory") is False
        and reuse.get("reuse_r07_output_directory") is False
        and reuse.get("reuse_r07_failure_report") is False
        and tools.get("build_commands_permitted") is False
        and tools.get("generator_commands_permitted") is False
        and tools.get("dependency_commands_permitted") is False,
        "only complete hash-bound R07 installs may be reused",
    )
    add_check(
        checks,
        "reuse:allowlist_and_namespace_denylist",
        reuse.get("allowed_prefixes") == [r07["generator_prefix"], r07["xyce_prefix"]]
        and reuse.get("new_output_namespace_required") is True
        and all("r07" in value or "r08" in value for value in reuse.get("forbidden_reused_paths", []))
        and "results/compact/m01_xyce_build_preflight_r08" in reuse.get("forbidden_reused_paths", []),
        json.dumps(reuse.get("forbidden_reused_paths", []), sort_keys=True),
    )

    xyce_binary = Path(tools["xyce_binary"])
    add_check(
        checks,
        "toolchain:binary_hash_and_command_allowlist",
        xyce_binary.is_file()
        and sha256(xyce_binary) == r07["xyce_binary_sha256"]
        and tools.get("required_commands") == [
            "Xyce -v",
            "Xyce -license",
            "Xyce scalar B-source",
            "Xyce -syntax",
        ]
        and tools.get("max_processes") == 4,
        f"binary={xyce_binary.is_file()} sha256={sha256(xyce_binary) if xyce_binary.is_file() else None}",
    )
    self_test = config["self_test"]
    add_check(
        checks,
        "self_test:fixed_column_prn_contract",
        self_test.get("output_format") == "Xyce_PRN_FIXED_COLUMNS"
        and self_test.get("output_suffix") == ".prn"
        and self_test.get("expected_column") == "V(NOUT)"
        and self_test.get("expected_value_v") == 1.25
        and self_test.get("tolerance_v") == 1e-9,
        json.dumps(self_test, sort_keys=True),
    )
    add_check(
        checks,
        "self_test:scope_forbids_project_and_downstream_tokens",
        {"igzo", "sno", "hzo", "ferroelectric", "tran", "noise", "circuit", "ring", "adder"}
        <= {token.lower() for token in self_test.get("forbidden_tokens", [])},
        json.dumps(self_test.get("forbidden_tokens", []), sort_keys=True),
    )

    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    candidate_text = candidate.read_text(encoding="ascii") if candidate.is_file() else ""
    candidate_contract = config["device_syntax_check"]
    add_check(
        checks,
        "candidate:frozen_igzo_hash_and_subckt",
        candidate.is_file()
        and sha256(candidate) == candidate_contract["candidate_sha256"]
        and ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text,
        f"exists={candidate.is_file()} bytes={len(candidate_text)}",
    )
    add_check(
        checks,
        "candidate:no_forbidden_numerical_or_material_scope",
        re.search(r"\b(?:sno|hzo|ferroelectric|tran|noise|ring|adder|full_adder)\b", candidate_text, re.IGNORECASE)
        is None
        and candidate_contract.get("enabled_after_self_test_only") is True
        and candidate_contract.get("netlist_is_formal_device_run") is False
        and candidate_contract.get("numerical_solution_must_not_be_requested") is True
        and candidate_contract.get("argv_suffix") == ["-syntax"],
        "IGZO candidate is parser-only and excludes downstream/material tokens",
    )

    outputs = config["outputs"]
    output_values = list(outputs.values())
    future_outputs = [ROOT / value for key, value in outputs.items() if key != "contract_report"]
    add_check(
        checks,
        "paths:exclusive_r08_outputs_absent",
        len(output_values) == len(set(output_values))
        and not REPORT_PATH.exists()
        and all(not path.exists() for path in future_outputs)
        and str(ROOT / outputs["run_directory"]).endswith("m01_xyce_build_preflight_r08"),
        f"future_absent={sum(not path.exists() for path in future_outputs)}/{len(future_outputs)}",
    )
    formal_paths = [ROOT / value for value in config["formal_outputs_that_must_remain_absent"]]
    add_check(
        checks,
        "paths:formal_m01_outputs_absent",
        all(not path.exists() for path in formal_paths),
        f"formal_absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    add_check(
        checks,
        "retention:r07_and_failure_logs_preserved",
        config["failure_retention"]["exclusive_outputs"] is True
        and config["failure_retention"]["overwrite_existing_outputs"] is False
        and config["failure_retention"]["retain_r07_failure"] is True
        and config["failure_retention"]["retain_failed_self_test_logs"] is True
        and config["failure_retention"]["retain_failed_syntax_logs"] is True,
        json.dumps(config["failure_retention"], sort_keys=True),
    )
    rules = config["no_execution_rules"]
    add_check(
        checks,
        "boundary:no_simulator_or_formal_execution",
        rules["reuse_only_hash_bound_r07_prefixes"] is True
        and rules["runner_must_not_build"] is True
        and rules["runner_must_not_invoke_ngspice"] is True
        and rules["runner_must_not_invoke_aimspice"] is True
        and rules["runner_must_not_invoke_formal_device_dc"] is True
        and rules["controlled_bsource_self_test_is_not_formal_m01"] is True
        and rules["device_syntax_check_must_follow_bsource_self_test"] is True
        and rules["circuit_or_downstream_permitted"] is False,
        json.dumps(rules, sort_keys=True),
    )
    add_check(
        checks,
        "boundary:evidence_and_next_gate",
        "not an IGZO equation" in config["evidence_boundary"]
        and "experimental calibration" in config["evidence_boundary"]
        and "36-check static contract" in config["next_gate"]
        and "independent" in config["next_gate"],
        config["next_gate"],
    )

    runner_source = RUNNER_PATH.read_text(encoding="utf-8")
    checker_source = CHECKER_PATH.read_text(encoding="utf-8")
    common_source = COMMON_PATH.read_text(encoding="utf-8")
    add_check(
        checks,
        "source:runner_registry_and_process_boundary",
        "EXPECTED_CHECK_COUNT = 32" in runner_source
        and "import subprocess" in runner_source
        and "subprocess.run" in runner_source
        and "build_invoked=false" in runner_source,
        "runner has an explicit four-command execution registry; build remains config-disabled",
    )
    add_check(
        checks,
        "source:runner_prn_parser_and_new_namespace",
        "read_xyce_prn" in runner_source
        and "bsource_self_test_output" in runner_source
        and "device_syntax" in runner_source
        and "m01_xyce_build_preflight_r07" not in runner_source,
        "runner parses fixed-column .prn and writes only R08 paths",
    )
    add_check(
        checks,
        "source:runner_forbidden_route_invocations",
        "ngspice" in runner_source
        and "aimspice" in runner_source
        and "formal_device_dc_invoked" in runner_source
        and "build_invoked=false" in runner_source,
        "forbidden routes are represented as asserted no-execution markers",
    )
    add_check(
        checks,
        "source:independent_checker_registry",
        "EXPECTED_CHECK_COUNT = 25" in checker_source
        and "EXPECTED_RUNNER_CHECK_COUNT = 32" in checker_source
        and "run_m01_xyce_build_preflight_r08.py" in checker_source,
        "independent checker binds the runner report without importing the runner",
    )
    add_check(
        checks,
        "source:independent_checker_no_process_import",
        "import subprocess" not in checker_source
        and "subprocess." not in checker_source
        and re.search(
            r"^(?:from\s+run_m01_xyce_build_preflight_r08\s+import|import\s+run_m01_xyce_build_preflight_r08\b)",
            checker_source,
            re.MULTILINE,
        )
        is None,
        "checker is standard-library persisted-evidence only",
    )
    add_check(
        checks,
        "source:common_parser_isolated",
        "def read_xyce_prn" in common_source
        and "def digest_tree" in common_source
        and "import subprocess" not in common_source,
        "common helper provides fixed-column parsing and tree hashing only",
    )
    add_check(
        checks,
        "source:makefile_r08_targets",
        "m01-xyce-build-preflight-r08-contract-check:" in (ROOT / "Makefile").read_text(encoding="utf-8")
        and "m01-xyce-build-preflight-r08:" in (ROOT / "Makefile").read_text(encoding="utf-8")
        and "m01-xyce-build-preflight-r08-check:" in (ROOT / "Makefile").read_text(encoding="utf-8"),
        "contract, runner and independent-check targets are registered",
    )
    add_check(
        checks,
        "project:next_scope_r08_contract",
        project.get("tcad_track", {}).get("next_scope", "").startswith(
            "establish and commit M01 Xyce build/tool preflight revision-8 output/parser recovery contract"
        )
        and "do not rerun R07" in project.get("tcad_track", {}).get("next_scope", ""),
        project.get("tcad_track", {}).get("next_scope", ""),
    )
    add_check(
        checks,
        "project:evidence_boundary_r08",
        "m01_xyce_build_preflight_r08_contract_boundary" in project.get("tcad_track", {})
        and "not a built simulator" in project["tcad_track"]["m01_xyce_build_preflight_r08_contract_boundary"],
        "project boundary records R08 as tool/output contract only",
    )
    add_check(
        checks,
        "registry:static_report_is_only_future_artifact",
        machine.get("contract_report_path") == "results/reports/m01_xyce_build_preflight_contract_r08.json"
        and machine.get("expected_contract_check_count") == EXPECTED_CHECK_COUNT
        and machine.get("expected_runner_check_count") == 32
        and machine.get("expected_independent_check_count") == 25,
        "experiment registry freezes 36/32/25 before execution",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"R08 contract registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")
    failures = [item for item in checks if item["status"] == "FAIL"]
    report = {
        "status": "FAIL" if failures else "PASS",
        "contract_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E3",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "build_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "build_processes_invoked": 0,
            "simulator_processes_invoked": 0,
            "device_netlist_created": False,
            "numerical_outputs_created": False,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256(Path(__file__))},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"],
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_R08_CONTRACT_{report['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={REPORT_PATH}"
    )
    return report


if __name__ == "__main__":
    result = check_contract()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
