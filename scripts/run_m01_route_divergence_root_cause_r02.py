#!/usr/bin/env python3
"""Run the bounded M01 route-divergence R02 root-cause probe."""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

from m01_route_divergence_root_cause_r02_common import (
    build_probe_rows,
    expected_observables,
    generate_probe_netlist,
    group_rows,
    load_json,
    parse_ngspice_ascii_raw,
    parse_xyce_prn,
    sha256,
    write_csv,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_route_divergence_root_cause_r02.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_route_divergence_root_cause_r02.py"
CONTRACT_REPORT_PATH = ROOT / "results" / "reports" / "m01_route_divergence_root_cause_contract_r02.json"
EXPECTED_CHECK_COUNT = 30
FORMAL_ROOT_CAUSE_PROBE_R02 = True

CHECK_NAMES = [
    "prerequisite:committed_static_pass",
    "binding:r02_immutable",
    "tools:hash_bound_routes",
    "outputs:exclusive_absent_before_run",
    "resource:two_process_serial_budget",
    "netlists:ascii_generation",
    "netlists:minimal_scope",
    "netlists:registered_observables",
    "ngspice:argv_exact",
    "ngspice:returncode_zero",
    "ngspice:raw_output_present",
    "ngspice:thirteen_finite_observables",
    "xyce:argv_exact",
    "xyce:returncode_zero",
    "xyce:raw_output_present",
    "xyce:thirteen_finite_observables",
    "controls:branch_sentinel_both_routes",
    "controls:explicit_clamp_both_routes",
    "xyce:three_argument_limit_matches_clamp",
    "ngspice:three_argument_limit_mismatch_observed",
    "candidate:portable_probe_both_routes",
    "xyce:original_candidate_matches_analytic",
    "ngspice:original_candidate_mismatch_observed",
    "classification:branch_extraction_alternative_eliminated",
    "classification:limit_semantics_hypothesis_supported",
    "outputs:twenty_six_probe_rows",
    "artifacts:hash_manifest_complete",
    "execution:exactly_two_route_processes",
    "scope:no_formal_tcad_circuit_or_downstream",
    "result:root_cause_probe_complete_with_boundary",
]


class ProbeFailure(RuntimeError):
    pass


def _set(checks: dict[str, dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _run_command(argv: list[str], command_log: Path) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.time()
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.time() - started
    write_json(
        command_log,
        {
            "argv": argv,
            "cwd": str(ROOT),
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )
    return completed, elapsed


def _within(rows: list[dict[str, Any]], absolute: float, relative: float = 0.0) -> bool:
    return bool(rows) and all(
        float(row["absolute_error"])
        <= max(absolute, relative * abs(float(row["expected"])))
        for row in rows
    )


def run() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report_path = ROOT / outputs["run_report"]
    if report_path.exists():
        raise RuntimeError(f"runner refuses to overwrite {report_path}")
    checks: dict[str, dict[str, str]] = {}
    commands: list[dict[str, Any]] = []
    process_invocations = 0
    failure_category: str | None = None
    failure_detail: str | None = None
    started_wall = time.time()
    probe_rows: list[dict[str, Any]] = []

    try:
        project = load_json(ROOT / "config" / "project.json")
        experiments = load_json(ROOT / "config" / "experiments.json")
        experiment_map = {item["id"]: item for item in experiments["experiments"]}
        machine = experiment_map["M01"]["route_divergence_root_cause_r02"]
        static_report = load_json(CONTRACT_REPORT_PATH)
        committed_static_pass = (
            static_report.get("status") == "PASS"
            and static_report.get("evidence_level") == "E3"
            and static_report.get("summary", {}).get("passed") == 40
            and static_report.get("summary", {}).get("failed") == 0
            and static_report.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
            and static_report.get("runner", {}).get("sha256") == sha256(RUNNER_PATH)
            and machine.get("status") == "contract_ready"
            and machine.get("current_evidence") == "E3"
            and machine.get("contract_check_completed") is True
            and machine.get("contract_status") == "PASS"
            and machine.get("runner_completed") is False
            and project.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute the committed M01 route-divergence root-cause revision-2 probe"
            )
        )
        _set(checks, CHECK_NAMES[0], committed_static_pass, f"machine={machine.get('status')}")
        if not committed_static_pass:
            raise ProbeFailure("committed static PASS gate is not open")

        binding = config["r02_immutable_binding"]
        bound_pairs = [
            (binding["config_path"], binding["config_sha256"]),
            (binding["common_path"], binding["common_sha256"]),
            (binding["runner_path"], binding["runner_sha256"]),
            (binding["independent_report_path"], binding["independent_report_sha256"]),
            (binding["candidate_path"], binding["candidate_sha256"]),
            (binding["ngspice_raw_path"], binding["ngspice_raw_sha256"]),
            (binding["xyce_raw_path"], binding["xyce_raw_sha256"]),
        ]
        binding_ok = all(
            (ROOT / path).is_file() and sha256(ROOT / path) == digest
            for path, digest in bound_pairs
        )
        _set(checks, CHECK_NAMES[1], binding_ok, f"bound={len(bound_pairs)}")
        if not binding_ok:
            raise ProbeFailure("R02 immutable binding changed")

        tools_ok = all(
            Path(route["tool_path"]).is_file()
            and sha256(Path(route["tool_path"])) == route["tool_sha256"]
            and Path(route["tool_path"]).stat().st_size == route["tool_bytes"]
            for route in config["routes"].values()
        )
        _set(checks, CHECK_NAMES[2], tools_ok, "ngspice and GPL Xyce")
        if not tools_ok:
            raise ProbeFailure("tool fingerprint changed")

        future_keys = [key for key in outputs if key != "contract_report"]
        outputs_absent = all(not (ROOT / outputs[key]).exists() for key in future_keys)
        _set(checks, CHECK_NAMES[3], outputs_absent, f"absent={sum(not (ROOT / outputs[key]).exists() for key in future_keys)}/{len(future_keys)}")
        if not outputs_absent:
            raise ProbeFailure("future output already exists")
        budget = config["resource_budget"]
        budget_ok = (
            budget["route_processes"] == 2
            and budget["ngspice_processes"] == 1
            and budget["xyce_processes"] == 1
            and budget["parallel_route_execution"] is False
            and all(budget[key] == 0 for key in ("tcad_processes", "aimspice_processes", "circuit_processes", "layout_processes"))
            and config["scope"]["formal_247_row_device_dc_permitted"] is False
        )
        _set(checks, CHECK_NAMES[4], budget_ok, json.dumps(budget, sort_keys=True))
        if not budget_ok:
            raise ProbeFailure("resource/scope budget changed")

        candidate_path = ROOT / binding["candidate_path"]
        candidate_text = candidate_path.read_text(encoding="ascii")
        ng_text = generate_probe_netlist(config, "ngspice", candidate_text)
        xy_text = generate_probe_netlist(config, "xyce", candidate_text)
        run_directory = ROOT / outputs["run_directory"]
        run_directory.mkdir(parents=True, exist_ok=False)
        ng_netlist = ROOT / outputs["ngspice_netlist"]
        xy_netlist = ROOT / outputs["xyce_netlist"]
        ng_netlist.write_text(ng_text, encoding="ascii", newline="\n")
        xy_netlist.write_text(xy_text, encoding="ascii", newline="\n")
        _set(checks, CHECK_NAMES[5], ng_text.isascii() and xy_text.isascii(), "two ASCII netlists")
        scope_ok = (
            ng_text.count("XORIG") == xy_text.count("XORIG") == 3
            and ng_text.count("XPORT") == xy_text.count("XPORT") == 3
            and ".tran" not in ng_text.lower()
            and ".tran" not in xy_text.lower()
            and all(token not in ng_text.lower() and token not in xy_text.lower() for token in ("sno", "hzo", "ring_oscillator", "full_adder"))
        )
        _set(checks, CHECK_NAMES[6], scope_ok, "3 original + 3 portable device probes per route")
        observable_tokens = ("V(LO_LIMIT)", "V(LO_CLAMP)", "V(HI_LIMIT)", "V(HI_CLAMP)", "I(VSENSE)", "I(VORIG2)", "I(VPORT2)")
        observables_ok = all(token in ng_text and token in xy_text for token in observable_tokens)
        _set(checks, CHECK_NAMES[7], observables_ok, "13 registered observables")
        if not all((scope_ok, observables_ok)):
            raise ProbeFailure("generated probe netlist scope failed")

        ng_route = config["routes"]["ngspice"]
        ng_argv = [item.format(tool=ng_route["tool_path"]) for item in ng_route["argv_template"]]
        expected_ng_argv = [ng_route["tool_path"], "-b", "-o", outputs["ngspice_log"], outputs["ngspice_netlist"]]
        ng_argv_ok = ng_argv == expected_ng_argv
        _set(checks, CHECK_NAMES[8], ng_argv_ok, json.dumps(ng_argv))
        if not ng_argv_ok:
            raise ProbeFailure("ngspice argv changed")
        process_invocations += 1
        ng_completed, ng_elapsed = _run_command(ng_argv, ROOT / outputs["ngspice_command_log"])
        commands.append({"route": "ngspice", "argv": ng_argv, "returncode": ng_completed.returncode, "elapsed_seconds": ng_elapsed})
        _set(checks, CHECK_NAMES[9], ng_completed.returncode == 0, f"returncode={ng_completed.returncode}")
        if ng_completed.returncode != 0:
            raise ProbeFailure("ngspice returned nonzero")
        ng_raw = ROOT / outputs["ngspice_raw_output"]
        ng_raw_ok = ng_raw.is_file() and ng_raw.stat().st_size > 0
        _set(checks, CHECK_NAMES[10], ng_raw_ok, str(ng_raw.relative_to(ROOT)))
        if not ng_raw_ok:
            raise ProbeFailure("ngspice raw output missing")
        expected = expected_observables(config)
        ng_values = parse_ngspice_ascii_raw(ng_raw)
        ng_subset = {key: ng_values[key] for key in expected if key in ng_values}
        ng_finite = len(ng_subset) == 13 and all(math.isfinite(value) for value in ng_subset.values())
        _set(checks, CHECK_NAMES[11], ng_finite, f"observables={len(ng_subset)}/13")
        if not ng_finite:
            raise ProbeFailure("ngspice observables incomplete")
        ng_rows = build_probe_rows("ngspice", ng_subset, expected)

        xy_route = config["routes"]["xyce"]
        xy_argv = [item.format(tool=xy_route["tool_path"]) for item in xy_route["argv_template"]]
        expected_xy_argv = [
            xy_route["tool_path"], "-l", outputs["xyce_log"], "-o",
            "results/compact/m01_route_divergence_root_cause_r02/xyce_probe",
            outputs["xyce_netlist"],
        ]
        xy_argv_ok = xy_argv == expected_xy_argv
        _set(checks, CHECK_NAMES[12], xy_argv_ok, json.dumps(xy_argv))
        if not xy_argv_ok:
            raise ProbeFailure("Xyce argv changed")
        process_invocations += 1
        xy_completed, xy_elapsed = _run_command(xy_argv, ROOT / outputs["xyce_command_log"])
        commands.append({"route": "xyce", "argv": xy_argv, "returncode": xy_completed.returncode, "elapsed_seconds": xy_elapsed})
        _set(checks, CHECK_NAMES[13], xy_completed.returncode == 0, f"returncode={xy_completed.returncode}")
        if xy_completed.returncode != 0:
            raise ProbeFailure("Xyce returned nonzero")
        xy_raw = ROOT / outputs["xyce_raw_output"]
        xy_raw_ok = xy_raw.is_file() and xy_raw.stat().st_size > 0
        _set(checks, CHECK_NAMES[14], xy_raw_ok, str(xy_raw.relative_to(ROOT)))
        if not xy_raw_ok:
            raise ProbeFailure("Xyce raw output missing")
        xy_values = parse_xyce_prn(xy_raw)
        xy_subset = {key: xy_values[key] for key in expected if key in xy_values}
        xy_finite = len(xy_subset) == 13 and all(math.isfinite(value) for value in xy_subset.values())
        _set(checks, CHECK_NAMES[15], xy_finite, f"observables={len(xy_subset)}/13")
        if not xy_finite:
            raise ProbeFailure("Xyce observables incomplete")
        xy_rows = build_probe_rows("xyce", xy_subset, expected)
        probe_rows = ng_rows + xy_rows

        acceptance = config["acceptance"]
        branch_rows = group_rows(probe_rows, "ngspice", "branch_sentinel") + group_rows(probe_rows, "xyce", "branch_sentinel")
        branch_ok = _within(branch_rows, acceptance["branch_absolute_tolerance_a"])
        _set(checks, CHECK_NAMES[16], branch_ok, f"max_abs={max(float(row['absolute_error']) for row in branch_rows):.6g}")
        clamp_rows = group_rows(probe_rows, "ngspice", "explicit_clamp") + group_rows(probe_rows, "xyce", "explicit_clamp")
        clamp_ok = _within(clamp_rows, acceptance["scalar_absolute_tolerance"])
        _set(checks, CHECK_NAMES[17], clamp_ok, f"max_abs={max(float(row['absolute_error']) for row in clamp_rows):.6g}")
        xy_limit_rows = group_rows(probe_rows, "xyce", "three_argument_limit")
        xy_limit_ok = _within(xy_limit_rows, acceptance["scalar_absolute_tolerance"])
        _set(checks, CHECK_NAMES[18], xy_limit_ok, f"max_abs={max(float(row['absolute_error']) for row in xy_limit_rows):.6g}")
        ng_limit_rows = group_rows(probe_rows, "ngspice", "three_argument_limit")
        ng_limit_max = max(float(row["absolute_error"]) for row in ng_limit_rows)
        ng_limit_mismatch = ng_limit_max >= acceptance["ngspice_limit_mismatch_min_absolute"]
        _set(checks, CHECK_NAMES[19], ng_limit_mismatch, f"max_abs={ng_limit_max:.6g}")
        portable_rows = group_rows(probe_rows, "ngspice", "portable_candidate") + group_rows(probe_rows, "xyce", "portable_candidate")
        portable_ok = _within(portable_rows, acceptance["candidate_absolute_tolerance_a"], acceptance["candidate_relative_tolerance"])
        _set(checks, CHECK_NAMES[20], portable_ok, f"max_rel={max(float(row['relative_error']) for row in portable_rows):.6g}")
        xy_original_rows = group_rows(probe_rows, "xyce", "original_candidate")
        xy_original_ok = _within(xy_original_rows, acceptance["candidate_absolute_tolerance_a"], acceptance["candidate_relative_tolerance"])
        _set(checks, CHECK_NAMES[21], xy_original_ok, f"max_rel={max(float(row['relative_error']) for row in xy_original_rows):.6g}")
        ng_original_rows = group_rows(probe_rows, "ngspice", "original_candidate")
        ng_original_max = max(float(row["relative_error"]) for row in ng_original_rows)
        ng_original_mismatch = ng_original_max >= acceptance["ngspice_original_candidate_mismatch_min_relative"]
        _set(checks, CHECK_NAMES[22], ng_original_mismatch, f"max_rel={ng_original_max:.6g}")
        branch_alternative_eliminated = branch_ok and clamp_ok
        _set(checks, CHECK_NAMES[23], branch_alternative_eliminated, "known branch and explicit clamp agree in both tools")
        hypothesis_supported = all((branch_ok, clamp_ok, xy_limit_ok, ng_limit_mismatch, portable_ok, xy_original_ok, ng_original_mismatch))
        _set(checks, CHECK_NAMES[24], hypothesis_supported, "only unqualified limit/original ngspice path diverges")
        if not hypothesis_supported:
            raise ProbeFailure("pre-registered root-cause classification was not satisfied")

        table_path = ROOT / outputs["probe_table"]
        write_csv(table_path, probe_rows)
        table_ok = table_path.is_file() and len(probe_rows) == config["probe_contract"]["result_row_count"] == 26
        _set(checks, CHECK_NAMES[25], table_ok, f"rows={len(probe_rows)}/26")
        artifact_keys = (
            "ngspice_netlist", "xyce_netlist", "ngspice_log", "xyce_log",
            "ngspice_command_log", "xyce_command_log", "ngspice_raw_output",
            "xyce_raw_output", "probe_table",
        )
        artifacts = {
            f"{key}_sha256": sha256(ROOT / outputs[key])
            for key in artifact_keys
            if (ROOT / outputs[key]).is_file()
        }
        artifacts_ok = len(artifacts) == len(artifact_keys)
        _set(checks, CHECK_NAMES[26], artifacts_ok, f"hashes={len(artifacts)}/{len(artifact_keys)}")
        process_ok = process_invocations == 2 and len(commands) == 2 and all(item["returncode"] == 0 for item in commands)
        _set(checks, CHECK_NAMES[27], process_ok, f"processes={process_invocations}")
        noexec = config["no_execution_rules"]
        scope_closed = (
            noexec["formal_247_row_execution_permitted"] is False
            and noexec["r02_reexecution_permitted"] is False
            and noexec["circuit_or_downstream_permitted"] is False
            and budget["tcad_processes"] == budget["aimspice_processes"] == budget["circuit_processes"] == budget["layout_processes"] == 0
        )
        _set(checks, CHECK_NAMES[28], scope_closed, "minimal probe only; all downstream closed")
        final_ready = all(checks.get(name, {}).get("status") == "PASS" for name in CHECK_NAMES[:-1])
        _set(checks, CHECK_NAMES[29], final_ready, "numerical root-cause evidence only")
    except Exception as exc:  # Preserve every partial output and failure class.
        failure_category = type(exc).__name__
        failure_detail = str(exc)

    for name in CHECK_NAMES:
        if name not in checks:
            _set(checks, name, False, "not reached after earlier failure")
    ordered_checks = [checks[name] for name in CHECK_NAMES]
    passed = sum(item["status"] == "PASS" for item in ordered_checks)
    failed = EXPECTED_CHECK_COUNT - passed
    artifacts = {
        f"{key}_sha256": sha256(ROOT / outputs[key])
        for key in (
            "ngspice_netlist", "xyce_netlist", "ngspice_log", "xyce_log",
            "ngspice_command_log", "xyce_command_log", "ngspice_raw_output",
            "xyce_raw_output", "probe_table",
        )
        if (ROOT / outputs[key]).is_file()
    }
    payload = {
        "schema_version": "1.0",
        "project_id": config["project_id"],
        "stage_id": config["stage_id"],
        "contract_id": config["contract_id"],
        "status": "PASS" if failed == 0 else "FAIL",
        "evidence_level": "E2" if failed == 0 else "E0",
        "simulation_status": "MINIMAL_ROOT_CAUSE_PROBE_COMPLETE" if failed == 0 else "MINIMAL_ROOT_CAUSE_PROBE_FAILED",
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "contract_report": {"path": str(CONTRACT_REPORT_PATH.relative_to(ROOT)), "sha256": sha256(CONTRACT_REPORT_PATH) if CONTRACT_REPORT_PATH.is_file() else None},
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": EXPECTED_CHECK_COUNT,
            "process_invocations": process_invocations,
            "ngspice_invoked": any(item.get("route") == "ngspice" for item in commands),
            "xyce_invoked": any(item.get("route") == "xyce" for item in commands),
            "formal_247_row_device_dc_invoked": False,
            "tcad_invoked": False,
            "aimspice_invoked": False,
            "circuit_or_downstream_invoked": False,
            "elapsed_seconds": time.time() - started_wall,
        },
        "failure_category": failure_category,
        "failure_detail": failure_detail,
        "commands": commands,
        "checks": ordered_checks,
        "artifacts": artifacts,
        "diagnosis": {
            "hypothesis": config["hypothesis"]["id"],
            "supported": checks[CHECK_NAMES[24]]["status"] == "PASS",
            "branch_current_extraction_alternative_eliminated": checks[CHECK_NAMES[23]]["status"] == "PASS",
            "full_r02_route_agreement_established": False,
        },
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": "Commit and push this E2 probe result before the 22-check independent persisted-evidence review." if failed == 0 else "Preserve this failure unchanged; do not rerun or relax thresholds. Establish a new revision only after classifying the failed gate.",
    }
    write_json(report_path, payload)
    print(f"M01_ROUTE_DIVERGENCE_R02_RUNNER_{payload['status']} checks={passed}/{EXPECTED_CHECK_COUNT} report={report_path}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run())
