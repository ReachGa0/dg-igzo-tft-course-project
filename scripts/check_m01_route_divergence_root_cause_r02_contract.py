#!/usr/bin/env python3
"""Static contract checker for the M01 route-divergence R02 probe."""

from __future__ import annotations

import math
import re
from pathlib import Path

from m01_route_divergence_root_cause_r02_common import (
    analytical_source_current,
    expected_observables,
    generate_probe_netlist,
    load_csv,
    load_json,
    portable_candidate_text,
    sha256,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_route_divergence_root_cause_r02.json"
COMMON_PATH = ROOT / "scripts" / "m01_route_divergence_root_cause_r02_common.py"
CHECKER_PATH = ROOT / "scripts" / "check_m01_route_divergence_root_cause_r02_contract.py"
RUNNER_PATH = ROOT / "scripts" / "run_m01_route_divergence_root_cause_r02.py"
INDEPENDENT_PATH = ROOT / "scripts" / "check_m01_route_divergence_root_cause_r02.py"
EXPECTED_CHECK_COUNT = 40


def add_check(
    checks: list[dict[str, str]], name: str, passed: bool, detail: str
) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report_path = ROOT / outputs["contract_report"]
    if report_path.exists():
        raise RuntimeError(f"static checker refuses to overwrite {report_path}")

    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    machine = experiment_map["M01"].get("route_divergence_root_cause_r02", {})
    checks: list[dict[str, str]] = []
    binding = config["r02_immutable_binding"]
    r01_binding = config["r01_static_failure_binding"]
    r01_report_path = ROOT / r01_binding["static_report_path"]
    r01_report = load_json(r01_report_path)
    r01_machine = experiment_map["M01"]["route_divergence_root_cause_r01"]
    candidate_path = ROOT / binding["candidate_path"]
    candidate_text = candidate_path.read_text(encoding="ascii")

    add_check(
        checks,
        "identity:config",
        config.get("project_id") == "DG-IGZO-TFT-PDK"
        and config.get("stage_id") == "M01"
        and config.get("contract_id") == "M01_ROUTE_DIVERGENCE_ROOT_CAUSE_R02"
        and config.get("revision") == 2
        and config.get("status") == "contract_planned",
        f"contract={config.get('contract_id')}",
    )
    scope = config["scope"]
    add_check(
        checks,
        "scope:igzo_only_minimal",
        scope["active_material_scope"] == "IGZO only"
        and scope["laptop_target"] is True
        and scope["formal_247_row_device_dc_permitted"] is False
        and scope["circuit_or_transient_permitted"] is False
        and scope["layout_or_pex_permitted"] is False
        and scope["hzo_or_sno_permitted"] is False,
        scope["execution_scope"],
    )
    r02_source_pairs = [
        (binding["config_path"], binding["config_sha256"]),
        (binding["common_path"], binding["common_sha256"]),
        (binding["contract_checker_path"], binding["contract_checker_sha256"]),
        (binding["runner_path"], binding["runner_sha256"]),
        (binding["independent_checker_path"], binding["independent_checker_sha256"]),
        (binding["candidate_path"], binding["candidate_sha256"]),
    ]
    r01_source_pairs = [
        (r01_binding["config_path"], r01_binding["config_sha256"]),
        (r01_binding["common_path"], r01_binding["common_sha256"]),
        (r01_binding["contract_checker_path"], r01_binding["contract_checker_sha256"]),
        (r01_binding["runner_path"], r01_binding["runner_sha256"]),
        (r01_binding["independent_checker_path"], r01_binding["independent_checker_sha256"]),
    ]
    add_check(
        checks,
        "binding:r02_and_r01_failure_sources",
        binding["bound_commit"] == "6e61c5de59e1f47bac5a0d20d0dc5a2182f58a89"
        and binding["must_remain_unchanged"] is True
        and all((ROOT / path).is_file() and sha256(ROOT / path) == digest for path, digest in r02_source_pairs)
        and r01_binding["bound_commit"] == "203acaae20a46ca824f63ac3b29357870acd3452"
        and r01_binding["must_remain_unchanged"] is True
        and all((ROOT / path).is_file() and sha256(ROOT / path) == digest for path, digest in r01_source_pairs)
        and sha256(r01_report_path) == r01_binding["static_report_sha256"]
        and r01_report.get("status") == "FAIL"
        and r01_report.get("evidence_level") == "E0"
        and r01_report.get("summary", {}).get("passed") == 38
        and r01_report.get("summary", {}).get("failed") == 2
        and r01_report.get("summary", {}).get("simulator_processes_invoked") == 0
        and r01_machine.get("status") == "contract_failed_static_checker"
        and r01_machine.get("contract_failure", {}).get("sha256") == r01_binding["static_report_sha256"],
        f"r02={len(r02_source_pairs)} r01={len(r01_source_pairs)} commit={r01_binding['bound_commit'][:7]}",
    )
    report_pairs = [
        (binding["static_report_path"], binding["static_report_sha256"]),
        (binding["runner_report_path"], binding["runner_report_sha256"]),
        (binding["independent_report_path"], binding["independent_report_sha256"]),
    ]
    r02_static = load_json(ROOT / binding["static_report_path"])
    r02_run = load_json(ROOT / binding["runner_report_path"])
    r02_check = load_json(ROOT / binding["independent_report_path"])
    add_check(
        checks,
        "binding:r02_reports",
        all((ROOT / path).is_file() and sha256(ROOT / path) == digest for path, digest in report_pairs)
        and r02_static.get("status") == "PASS"
        and r02_static.get("summary", {}).get("passed") == 40
        and r02_run.get("status") == "PASS"
        and r02_run.get("summary", {}).get("passed") == 30
        and r02_check.get("status") == "PASS"
        and r02_check.get("summary", {}).get("passed") == 24
        and r02_check.get("processes_invoked") == 0,
        "R02=40/30/24",
    )
    r02_machine = experiment_map["M01"]["open_source_device_dc_r02"]
    add_check(
        checks,
        "binding:r02_machine_verified",
        r02_machine.get("status") == "verified"
        and r02_machine.get("current_evidence") == "E3"
        and r02_machine.get("independent_check_completed") is True
        and r02_machine.get("independent_report_sha256") == binding["independent_report_sha256"]
        and r02_machine.get("circuit_or_downstream_permitted") is False,
        f"machine={r02_machine.get('status')}/{r02_machine.get('current_evidence')}",
    )
    r02_config = load_json(ROOT / binding["config_path"])
    artifacts = r02_run.get("artifacts", {})
    diagnostic_binding = config["r02_diagnostic_evidence_binding"]
    diagnostic_pairs = [
        (diagnostic_binding["ngspice_raw_csv_path"], diagnostic_binding["ngspice_raw_csv_sha256"]),
        (diagnostic_binding["xyce_raw_csv_path"], diagnostic_binding["xyce_raw_csv_sha256"]),
        (diagnostic_binding["route_difference_csv_path"], diagnostic_binding["route_difference_csv_sha256"]),
    ]
    artifact_binding_ok = len(artifacts) == 14 and all(
        key.endswith("_sha256")
        and (ROOT / r02_config["outputs"][key.removesuffix("_sha256")]).is_file()
        and sha256(ROOT / r02_config["outputs"][key.removesuffix("_sha256")]) == digest
        for key, digest in artifacts.items()
    )
    add_check(
        checks,
        "binding:r02_artifact_hashes",
        artifact_binding_ok
        and all((ROOT / path).is_file() and sha256(ROOT / path) == digest for path, digest in diagnostic_pairs)
        and all(artifacts.get(key) == diagnostic_binding[key] for key in diagnostic_binding["runner_artifact_keys"])
        and diagnostic_binding["schema_correction_only"] is True
        and diagnostic_binding["independent_recomputation_checks_passed"] == 24,
        f"artifacts={len(artifacts)}/14 diagnostics={len(diagnostic_pairs)}/3",
    )
    observed = config["observed_r02_diagnostics"]
    add_check(
        checks,
        "observation:candidate_limit_token",
        candidate_text.count(observed["candidate_limit_expression"]) == 1
        and sha256(candidate_path) == binding["candidate_sha256"],
        observed["candidate_limit_expression"],
    )
    ng_log_path = ROOT / binding["ngspice_log_path"]
    add_check(
        checks,
        "observation:ngspice_no_compatibility",
        sha256(ng_log_path) == binding["ngspice_log_sha256"]
        and observed["ngspice_log_compatibility_token"]
        in ng_log_path.read_text(encoding="ascii"),
        observed["ngspice_log_compatibility_token"],
    )
    ng_rows = load_csv(ROOT / diagnostic_binding["ngspice_raw_csv_path"])
    xy_rows = load_csv(ROOT / diagnostic_binding["xyce_raw_csv_path"])
    difference_rows = load_csv(ROOT / diagnostic_binding["route_difference_csv_path"])
    row_count = diagnostic_binding["row_count_per_table"]
    diagnostic_rows_ok = (
        len(ng_rows) == len(xy_rows) == len(difference_rows) == row_count
        and all(row.get("route") == "ngspice" and row.get("finite_current") == "True" for row in ng_rows)
        and all(row.get("route") == "xyce" and row.get("finite_current") == "True" for row in xy_rows)
    )
    recomputed = {
        "ngspice_current_max_a_per_cm": max(float(row["current_a_per_cm"]) for row in ng_rows),
        "xyce_current_max_a_per_cm": max(float(row["current_a_per_cm"]) for row in xy_rows),
        "maximum_absolute_difference_a_per_cm": max(float(row["absolute_difference_a_per_cm"]) for row in difference_rows),
        "maximum_log_difference_dec": max(float(row["log_difference_dec"]) for row in difference_rows),
    }
    add_check(
        checks,
        "observation:r02_divergence_values",
        diagnostic_rows_ok
        and observed["route_agreement_claimed"] is False
        and observed["root_cause_confirmed_before_probe"] is False
        and all(
            math.isclose(recomputed[key], observed[key], rel_tol=0.0, abs_tol=0.0)
            for key in recomputed
        ),
        f"rows={len(ng_rows)}/{len(xy_rows)}/{len(difference_rows)} max_log={recomputed['maximum_log_difference_dec']:.6g}",
    )
    docs = config["documentation_and_source_bindings"]
    add_check(
        checks,
        "documentation:official_primary_urls",
        docs["ngspice_42_manual_url"].startswith("https://ngspice.sourceforge.io/")
        and docs["ngspice_bug_505_url"].startswith("https://sourceforge.net/p/ngspice/")
        and docs["xyce_reference_url"].startswith("https://xyce.sandia.gov/")
        and docs["documentation_is_context_not_executed_evidence"] is True,
        "ngspice and Sandia primary references registered",
    )
    add_check(
        checks,
        "documentation:ngspice_signatures",
        docs["ngspice_limit_builtin_signature"] == "limit(nom, avar)"
        and docs["ngspice_pspice_injected_definition"]
        == ".func limit(x, a, b) { min(max(x, a), b) }",
        "default two-argument vs compatibility-injected clamp",
    )
    xy_source = Path(docs["xyce_source_path"])
    xy_test = Path(docs["xyce_unit_test_path"])
    add_check(
        checks,
        "source:xyce_hashes",
        xy_source.is_file()
        and xy_test.is_file()
        and sha256(xy_source) == docs["xyce_source_sha256"]
        and sha256(xy_test) == docs["xyce_unit_test_sha256"],
        "Xyce 7.10 expression source and unit test",
    )
    xy_source_text = xy_source.read_text(encoding="utf-8")
    xy_test_text = xy_test.read_text(encoding="utf-8")
    add_check(
        checks,
        "source:xyce_limit_semantics",
        "x limited to range y to z" in xy_source_text
        and "class limitOp" in xy_source_text
        and "return std::real(yFixed);" in xy_source_text
        and "return std::real(zFixed);" in xy_source_text
        and "Double_Ast_limit_Test" in xy_test_text,
        docs["xyce_three_argument_semantics"],
    )
    hypothesis = config["hypothesis"]
    add_check(
        checks,
        "hypothesis:pre_run_unconfirmed",
        hypothesis["id"] == "THREE_ARGUMENT_LIMIT_SEMANTICS_MISMATCH"
        and observed["root_cause_confirmed_before_probe"] is False
        and hypothesis["hypothesis_requires_numerical_probe"] is True,
        "hypothesis requires numerical probe",
    )
    add_check(
        checks,
        "hypothesis:portable_replacement",
        hypothesis["portable_probe_replacement"] == "min(max(x/s,-60),60)"
        and hypothesis["candidate_file_modification_permitted"] is False
        and hypothesis["r02_reexecution_permitted"] is False
        and hypothesis["hypothesis_requires_numerical_probe"] is True,
        hypothesis["portable_probe_replacement"],
    )
    probe = config["probe_contract"]
    add_check(
        checks,
        "probe:expression_points",
        probe["expression_inputs"] == [-75.0, 0.25, 75.0]
        and probe["expected_clamp_outputs"] == [-60.0, 0.25, 60.0]
        and probe["clamp_lower"] == -60.0
        and probe["clamp_upper"] == 60.0,
        "three lower/interior/upper points",
    )
    add_check(
        checks,
        "probe:branch_sentinel",
        probe["branch_sentinel_voltage_v"] == 1.0
        and probe["branch_sentinel_resistance_ohm"] == 1000.0
        and probe["expected_branch_source_current_a"] == -0.001,
        "1 V / 1 kOhm branch-current sentinel",
    )
    points = probe["candidate_probe_points"]
    add_check(
        checks,
        "probe:candidate_points",
        len(points) == 3
        and [item["probe_id"] for item in points]
        == ["P0_MID_TRANSFER", "P1_OUTPUT", "P2_DUAL_ON"]
        and all(item["w_um"] == 60.0 and item["l_um"] == 10.0 for item in points),
        "three representative in-domain points",
    )
    analytic = [analytical_source_current(point, probe["candidate_parameters"]) for point in points]
    add_check(
        checks,
        "probe:analytic_expectations",
        all(math.isclose(value, point["expected_source_current_a"], rel_tol=1e-15, abs_tol=1e-20) for value, point in zip(analytic, points)),
        "/".join(format(value, ".6g") for value in analytic),
    )
    expected = expected_observables(config)
    add_check(
        checks,
        "probe:observable_counts",
        probe["observable_count_per_route"] == 13
        and probe["result_row_count"] == 26
        and len(expected) == 13,
        f"observables={len(expected)} rows={probe['result_row_count']}",
    )
    portable = portable_candidate_text(candidate_text)
    portable_round_trip = (
        portable.replace("min(max(x/s,-60),60)", "limit(x/s,-60,60)")
        .replace("RCA_Q", "M00_Q")
        .replace("BPORT", "BIDS")
        .replace("IGZO_DG_PORTABLE_PROBE_R02", "IGZO_DG_BEHAVIORAL_R02")
    )
    add_check(
        checks,
        "probe:portable_diff_only",
        observed["candidate_limit_expression"] not in portable
        and hypothesis["portable_probe_replacement"] in portable
        and "IGZO_DG_PORTABLE_PROBE_R02" in portable
        and "IGZO_DG_BEHAVIORAL_R02" not in portable
        and portable_round_trip == candidate_text
        and candidate_text == candidate_path.read_text(encoding="ascii"),
        "diagnostic copy changes only identifiers and clamp token",
    )
    add_check(
        checks,
        "tools:hashes",
        all(
            Path(route["tool_path"]).is_file()
            and sha256(Path(route["tool_path"])) == route["tool_sha256"]
            and Path(route["tool_path"]).stat().st_size == route["tool_bytes"]
            for route in config["routes"].values()
        ),
        "same hash-bound ngspice/Xyce binaries as R02",
    )
    route_outputs = config["outputs"]
    expected_ng = [
        config["routes"]["ngspice"]["tool_path"], "-b", "-o",
        route_outputs["ngspice_log"], route_outputs["ngspice_netlist"],
    ]
    expected_xy = [
        config["routes"]["xyce"]["tool_path"], "-l", route_outputs["xyce_log"],
        "-o", "results/compact/m01_route_divergence_root_cause_r02/xyce_probe",
        route_outputs["xyce_netlist"],
    ]
    add_check(
        checks,
        "routes:argv_exact",
        [item.format(tool=config["routes"]["ngspice"]["tool_path"]) for item in config["routes"]["ngspice"]["argv_template"]] == expected_ng
        and [item.format(tool=config["routes"]["xyce"]["tool_path"]) for item in config["routes"]["xyce"]["argv_template"]] == expected_xy,
        "one exact argv per route",
    )
    ng_text = generate_probe_netlist(config, "ngspice", candidate_text)
    xy_text = generate_probe_netlist(config, "xyce", candidate_text)
    add_check(
        checks,
        "netlists:in_memory_ascii",
        ng_text.isascii() and xy_text.isascii() and probe["netlist_encoding"] == "ascii",
        f"bytes={len(ng_text.encode('ascii'))}/{len(xy_text.encode('ascii'))}",
    )
    add_check(
        checks,
        "netlists:two_six_device_scope",
        probe["netlists"] == 2
        and ng_text.count("XORIG") == xy_text.count("XORIG") == 3
        and ng_text.count("XPORT") == xy_text.count("XPORT") == 3
        and ng_text.count(probe["analysis"]) == xy_text.count(probe["analysis"]) == 1,
        "3 original + 3 portable instances per route",
    )
    add_check(
        checks,
        "netlists:registered_observables",
        all(token in ng_text and token in xy_text for token in ("V(LO_LIMIT)", "V(HI_CLAMP)", "I(VSENSE)", "I(VORIG2)", "I(VPORT2)")),
        "13 observables per route",
    )
    add_check(
        checks,
        "netlists:no_compatibility_switch",
        "ngbehavior" not in ng_text.lower()
        and "ngbehavior" not in xy_text.lower()
        and ".option ps" not in ng_text.lower()
        and ".option ps" not in xy_text.lower(),
        "default tool semantics are observed, not changed",
    )
    acceptance = config["acceptance"]
    add_check(
        checks,
        "acceptance:tolerances",
        acceptance["scalar_absolute_tolerance"] == 1e-10
        and acceptance["branch_absolute_tolerance_a"] == 1e-12
        and acceptance["candidate_absolute_tolerance_a"] == 1e-15
        and acceptance["candidate_relative_tolerance"] == 1e-8,
        "pre-registered absolute and relative tolerances",
    )
    add_check(
        checks,
        "acceptance:classification",
        acceptance["ngspice_limit_mismatch_min_absolute"] == 1.0
        and acceptance["ngspice_original_candidate_mismatch_min_relative"] == 0.1
        and acceptance["branch_sentinel_must_pass_both_routes"] is True
        and acceptance["portable_candidate_must_pass_both_routes"] is True
        and acceptance["threshold_relaxation_after_run_permitted"] is False,
        "branch extraction separated from expression semantics",
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "resource:two_serial_processes",
        budget == {
            "route_processes": 2, "ngspice_processes": 1, "xyce_processes": 1,
            "parallel_route_execution": False, "tcad_processes": 0,
            "aimspice_processes": 0, "circuit_processes": 0, "layout_processes": 0,
        },
        "two serial simulator processes maximum",
    )
    output_paths = [ROOT / path for path in outputs.values()]
    add_check(
        checks,
        "outputs:exclusive_absent",
        all(not path.exists() for path in output_paths),
        f"absent={sum(not path.exists() for path in output_paths)}/{len(output_paths)}",
    )
    retention = config["failure_retention"]
    required_true_retention = {
        key for key in retention if key != "overwrite_existing_outputs"
    }
    add_check(
        checks,
        "failure:retention",
        all(retention[key] is True for key in required_true_retention)
        and retention["overwrite_existing_outputs"] is False
        and retention["exclusive_outputs"] is True,
        "all partial/failure evidence retained without overwrite",
    )
    static_source = CHECKER_PATH.read_text(encoding="ascii")
    common_source = COMMON_PATH.read_text(encoding="ascii")
    runner_source = RUNNER_PATH.read_text(encoding="ascii")
    independent_source = INDEPENDENT_PATH.read_text(encoding="ascii")
    add_check(
        checks,
        "noexec:static_source",
        re.search(r"^(?:import|from)\s+subprocess\b", static_source, re.MULTILINE) is None
        and re.search(
            r"^(?:import|from)\s+run_m01_route_divergence_root_cause_r02\b",
            static_source,
            re.MULTILINE,
        ) is None
        and re.search(r"^(?:import|from)\s+subprocess\b", common_source, re.MULTILINE) is None,
        "static checker/common contain no process path",
    )
    add_check(
        checks,
        "noexec:runner_gate",
        "FORMAL_ROOT_CAUSE_PROBE" in runner_source
        and "contract_ready" in runner_source
        and "subprocess.run" in runner_source
        and "formal_247_row_execution_permitted" in runner_source,
        "future runner has committed-static and scope gates",
    )
    add_check(
        checks,
        "independence:source",
        re.search(r"^(?:import|from)\s+subprocess\b", independent_source, re.MULTILINE) is None
        and re.search(
            r"^(?:import|from)\s+run_m01_route_divergence_root_cause_r02\b",
            independent_source,
            re.MULTILINE,
        ) is None
        and "EXPECTED_CHECK_COUNT = 22" in independent_source,
        "future independent checker cannot invoke runner/process",
    )
    add_check(
        checks,
        "checks:registry",
        config["registered_checks"] == {"static_contract": 40, "runner": 30, "independent": 22},
        "40/30/22",
    )
    makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
    add_check(
        checks,
        "make:targets",
        all(
            f"{target}:" in makefile
            for target in (
                "m01-route-divergence-r02-contract-check",
                "m01-route-divergence-r02",
                "m01-route-divergence-r02-check",
            )
        ),
        "three staged Make targets registered",
    )
    source_paths = [
        "config/m01_route_divergence_root_cause_r02.json",
        "scripts/m01_route_divergence_root_cause_r02_common.py",
        "scripts/check_m01_route_divergence_root_cause_r02_contract.py",
        "scripts/run_m01_route_divergence_root_cause_r02.py",
        "scripts/check_m01_route_divergence_root_cause_r02.py",
    ]
    add_check(
        checks,
        "machine:planned_state",
        machine.get("status") == "contract_implemented"
        and machine.get("current_evidence") == "E0"
        and machine.get("contract_check_completed") is False
        and machine.get("runner_completed") is False
        and machine.get("independent_check_completed") is False
        and machine.get("processes_invoked") == 0
        and machine.get("result_paths") == source_paths
        and machine.get("r01_static_failure_sha256") == r01_binding["static_report_sha256"]
        and machine.get("schema_correction_only") is True
        and project.get("tcad_track", {}).get("next_scope", "").startswith(
            "establish and commit M01 route-divergence root-cause revision-2 schema-only contract implementation"
        ),
        f"machine={machine.get('status')}/{machine.get('current_evidence')}",
    )
    add_check(
        checks,
        "boundary:no_overclaim",
        "cannot establish physical IGZO parameters" in config["evidence_boundary"]
        and "full 247-row route agreement" in config["evidence_boundary"]
        and config["no_execution_rules"]["r02_reexecution_permitted"] is False
        and config["no_execution_rules"]["circuit_or_downstream_permitted"] is False,
        "root-cause evidence only; M01/C00 remain closed",
    )
    source_hashes = config["source_hashes"]
    hashes_ok = (
        source_hashes["common_sha256"] == sha256(COMMON_PATH)
        and source_hashes["contract_checker_sha256"] == sha256(CHECKER_PATH)
        and source_hashes["runner_sha256"] == sha256(RUNNER_PATH)
        and source_hashes["independent_checker_sha256"] == sha256(INDEPENDENT_PATH)
    )
    prior_ok = len(checks) == EXPECTED_CHECK_COUNT - 1 and all(item["status"] == "PASS" for item in checks)
    add_check(
        checks,
        "result:static_ready",
        prior_ok and hashes_ok,
        f"prior={len(checks)}/{EXPECTED_CHECK_COUNT - 1} source_hashes={hashes_ok}",
    )
    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"static registry mismatch {len(checks)}/{EXPECTED_CHECK_COUNT}")

    passed = sum(item["status"] == "PASS" for item in checks)
    failed = EXPECTED_CHECK_COUNT - passed
    payload = {
        "schema_version": "1.0",
        "project_id": config["project_id"],
        "stage_id": config["stage_id"],
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
            "simulator_processes_invoked": 0,
            "netlists_created": 0,
            "numerical_outputs_created": 0,
        },
        "checks": checks,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": (
            "Commit and push this static PASS before the one permitted two-process minimal root-cause probe."
            if failed == 0
            else "Preserve this R02 static failure unchanged; do not run the probe or relax any gate."
        ),
    }
    write_json(report_path, payload)
    print(f"M01_ROUTE_DIVERGENCE_R02_CONTRACT_{payload['status']} checks={passed}/{EXPECTED_CHECK_COUNT} report={report_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(check())
