#!/usr/bin/env python3
"""Run the formal C00 R02 ngspice/Xyce inverter analyses exactly once."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from c00_active_load_inverter_r02_common import (
    DC_DIFFERENCE_FIELDS,
    DC_FIELDS,
    STATIC_METRIC_FIELDS,
    TRANSIENT_DIFFERENCE_FIELDS,
    TRANSIENT_FIELDS,
    TRANSIENT_METRIC_FIELDS,
    anchor_ids,
    compute_dc_differences,
    compute_static_metrics,
    compute_transient_differences,
    compute_transient_metrics,
    extract_dc_rows,
    extract_transient_rows,
    generate_dc_netlist,
    generate_transient_netlist,
    load_json,
    parse_ngspice_ascii_raw,
    parse_xyce_prn,
    render_plots,
    sha256,
    write_csv,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "c00_active_load_inverter_r02.json"
CONTRACT_CHECKER_PATH = ROOT / "scripts" / "check_c00_active_load_inverter_r02_contract.py"
COMMON_PATH = ROOT / "scripts" / "c00_active_load_inverter_r02_common.py"
RUNNER_PATH = Path(__file__).resolve()
EXPECTED_CHECK_COUNT = 36

CHECK_NAMES = [
    "precondition:committed_static_contract_pass",
    "identity:config_common_checker_runner",
    "git:head_and_origin_match_static_pass_commit",
    "machine:circuit_execution_gate_open",
    "model:frozen_portable_candidate",
    "tools:two_hash_bound_open_source_routes",
    "outputs:exclusive_absent_before_run",
    "resource:four_process_serial_budget",
    "netlists:four_ascii_generated",
    "netlists:registered_topology_and_case_counts",
    "netlists:no_forbidden_scope",
    "ngspice_dc:argv_exact",
    "ngspice_dc:returncode_zero",
    "ngspice_dc:raw_present",
    "ngspice_tran:argv_exact",
    "ngspice_tran:returncode_zero",
    "ngspice_tran:raw_present",
    "xyce_dc:argv_exact",
    "xyce_dc:returncode_zero",
    "xyce_dc:raw_present",
    "xyce_tran:argv_exact",
    "xyce_tran:returncode_zero",
    "xyce_tran:raw_present",
    "execution:exactly_four_serial_processes",
    "raw:four_native_tables_parse",
    "tables:two_complete_dc_routes",
    "tables:two_complete_transient_routes",
    "metrics:static_all_cases_and_power",
    "metrics:transient_all_cases_delay_and_power",
    "acceptance:both_routes_anchor_static_qualified",
    "acceptance:both_routes_anchor_transient_qualified",
    "differences:complete_aligned_tables",
    "differences:diagnostic_only_policy_preserved",
    "figures:vtc_and_transient_png",
    "artifacts:all_runner_hashes_persisted",
    "result:formal_c00_complete_with_boundary",
]

ARTIFACT_KEYS = [
    "ngspice_dc_netlist",
    "ngspice_dc_log",
    "ngspice_dc_command",
    "ngspice_dc_raw",
    "ngspice_tran_netlist",
    "ngspice_tran_log",
    "ngspice_tran_command",
    "ngspice_tran_raw",
    "xyce_dc_netlist",
    "xyce_dc_log",
    "xyce_dc_command",
    "xyce_dc_raw",
    "xyce_tran_netlist",
    "xyce_tran_log",
    "xyce_tran_command",
    "xyce_tran_raw",
    "ngspice_dc_csv",
    "xyce_dc_csv",
    "ngspice_tran_csv",
    "xyce_tran_csv",
    "static_metrics_csv",
    "transient_metrics_csv",
    "dc_route_difference_csv",
    "transient_route_difference_csv",
    "vtc_png",
    "transient_png",
]


class CircuitRunFailure(RuntimeError):
    pass


def _new_checks() -> dict[str, dict[str, str]]:
    return {
        name: {"name": name, "status": "FAIL", "detail": "not reached"}
        for name in CHECK_NAMES
    }


def _set(checks: dict[str, dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}


def _read_ref(name: str) -> str | None:
    git_dir = ROOT / ".git"
    head_path = git_dir / name
    if head_path.is_file():
        value = head_path.read_text(encoding="ascii").strip()
        if value.startswith("ref: "):
            target = git_dir / value[5:]
            return target.read_text(encoding="ascii").strip() if target.is_file() else None
        return value
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="ascii").splitlines():
            if line and not line.startswith(("#", "^")):
                commit, ref = line.split(" ", 1)
                if ref == name:
                    return commit
    return None


def _run_command(argv: list[str], command_path: Path) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.monotonic() - started
    write_json(
        command_path,
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


def _argv(config: dict[str, Any], route: str, analysis: str) -> list[str]:
    registered = config["routes"][route][f"{analysis}_argv"]
    return [item.format(tool=config["routes"][route]["tool_path"]) for item in registered]


def forbidden_tokens_absent(text: str, forbidden: list[str]) -> bool:
    identifiers = {
        token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    }
    return not identifiers.intersection(token.lower() for token in forbidden)


def run() -> int:
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    c00 = next(item for item in experiments["experiments"] if item["id"] == "C00")
    machine = c00.get("active_load_inverter_r02", {})
    outputs = config["outputs"]
    report_path = ROOT / outputs["run_report"]
    checks = _new_checks()
    commands: list[dict[str, Any]] = []
    process_invocations = 0
    formal_circuit_invoked = False
    failure_category: str | None = None
    failure_detail: str | None = None
    native_points: dict[str, int] = {}
    started_wall = time.time()

    try:
        static_report_path = ROOT / outputs["contract_report"]
        static_report = load_json(static_report_path)
        static_ok = (
            static_report.get("status") == "PASS"
            and static_report.get("evidence_level") == "E3"
            and static_report.get("summary") == {"passed": 50, "failed": 0, "total": 50}
            and static_report.get("simulator_processes_invoked") == 0
            and static_report.get("circuit_netlists_created") == 0
            and machine.get("contract_report_sha256") == sha256(static_report_path)
        )
        _set(checks, "precondition:committed_static_contract_pass", static_ok, f"sha256={sha256(static_report_path)}")
        if not static_ok:
            raise CircuitRunFailure("committed static contract precondition failed")

        identity_ok = (
            static_report["config"]["sha256"] == sha256(CONFIG_PATH)
            and static_report["checker"]["sha256"] == sha256(CONTRACT_CHECKER_PATH)
            and machine.get("config_sha256") == sha256(CONFIG_PATH)
            and machine.get("common_sha256") == sha256(COMMON_PATH)
            and machine.get("runner_sha256") == sha256(RUNNER_PATH)
        )
        _set(checks, "identity:config_common_checker_runner", identity_ok, f"config={sha256(CONFIG_PATH)} runner={sha256(RUNNER_PATH)}")
        if not identity_ok:
            raise CircuitRunFailure("source identity differs from the committed static gate")

        head = _read_ref("HEAD")
        origin = _read_ref("refs/remotes/origin/main")
        static_commit = machine.get("static_pass_commit")
        git_ok = head == origin == static_commit and isinstance(static_commit, str) and len(static_commit) == 40
        _set(checks, "git:head_and_origin_match_static_pass_commit", git_ok, f"head={head} origin={origin} registered={static_commit}")
        if not git_ok:
            raise CircuitRunFailure("static PASS state is not committed and synchronized")

        machine_ok = (
            c00.get("status") == "contract_ready"
            and c00.get("current_evidence") == "E3"
            and machine.get("status") == "contract_ready"
            and machine.get("contract_check_completed") is True
            and machine.get("contract_checks_passed") == 50
            and machine.get("contract_checks_failed") == 0
            and machine.get("circuit_execution_permitted") is True
            and machine.get("formal_run_completed") is False
            and machine.get("simulator_processes_invoked") == 0
            and project.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute the committed C00 active-load inverter revision-2 four-process runner"
            )
        )
        _set(checks, "machine:circuit_execution_gate_open", machine_ok, f"root={c00.get('status')} machine={machine.get('status')}")
        if not machine_ok:
            raise CircuitRunFailure("C00 execution gate is not open")

        model = config["upstream_model"]
        model_path = ROOT / model["candidate_path"]
        model_ok = model_path.is_file() and sha256(model_path) == model["candidate_sha256"] and model_path.stat().st_size == model["candidate_bytes"]
        _set(checks, "model:frozen_portable_candidate", model_ok, f"sha256={sha256(model_path)}")
        if not model_ok:
            raise CircuitRunFailure("portable model bytes changed")

        tools_ok = all(
            Path(route["tool_path"]).is_file()
            and sha256(Path(route["tool_path"])) == route["tool_sha256"]
            and Path(route["tool_path"]).stat().st_size == route["tool_bytes"]
            for route in config["routes"].values()
        )
        _set(checks, "tools:two_hash_bound_open_source_routes", tools_ok, "ngspice and GPL Xyce hashes match")
        if not tools_ok:
            raise CircuitRunFailure("tool fingerprint mismatch")

        future_paths = [ROOT / outputs[key] for key in ARTIFACT_KEYS] + [report_path, ROOT / outputs["independent_report"]]
        outputs_absent = not (ROOT / outputs["run_directory"]).exists() and all(not path.exists() for path in future_paths)
        _set(checks, "outputs:exclusive_absent_before_run", outputs_absent, f"absent={sum(not path.exists() for path in future_paths)}/{len(future_paths)}")
        if not outputs_absent:
            raise CircuitRunFailure("exclusive C00 output already exists")

        budget = config["resource_budget"]
        budget_ok = budget["max_serial_simulator_processes"] == 4 and budget["parallel_simulator_processes"] == 0 and budget["aimspice_processes"] == budget["tcad_processes"] == budget["layout_processes"] == budget["pex_processes"] == 0
        _set(checks, "resource:four_process_serial_budget", budget_ok, json.dumps(budget, sort_keys=True))
        if not budget_ok:
            raise CircuitRunFailure("resource budget differs from contract")

        run_directory = ROOT / outputs["run_directory"]
        run_directory.mkdir(parents=True, exist_ok=False)
        texts = {
            "ngspice_dc_netlist": generate_dc_netlist(config, "ngspice"),
            "ngspice_tran_netlist": generate_transient_netlist(config, "ngspice"),
            "xyce_dc_netlist": generate_dc_netlist(config, "xyce"),
            "xyce_tran_netlist": generate_transient_netlist(config, "xyce"),
        }
        for key, text in texts.items():
            (ROOT / outputs[key]).write_text(text, encoding="ascii", newline="\n")
        ascii_ok = all(text.isascii() for text in texts.values())
        _set(checks, "netlists:four_ascii_generated", ascii_ok, "four exclusive ASCII netlists")
        topology_ok = (
            texts["ngspice_dc_netlist"].count("XLD") == texts["xyce_dc_netlist"].count("XLD") == 18
            and texts["ngspice_dc_netlist"].count("XDR") == texts["xyce_dc_netlist"].count("XDR") == 18
            and texts["ngspice_tran_netlist"].count("XLD") == texts["xyce_tran_netlist"].count("XLD") == 36
            and texts["ngspice_tran_netlist"].count("XDR") == texts["xyce_tran_netlist"].count("XDR") == 36
            and texts["ngspice_tran_netlist"].count("CLOAD") == texts["xyce_tran_netlist"].count("CLOAD") == 36
        )
        _set(checks, "netlists:registered_topology_and_case_counts", topology_ok, "18 DC and 36 transient two-TFT cases per route")
        forbidden = config["netlist_contract"]["forbidden_case_insensitive_tokens"]
        scope_ok = all(forbidden_tokens_absent(text, forbidden) for text in texts.values())
        _set(checks, "netlists:no_forbidden_scope", scope_ok, f"forbidden={len(forbidden)} policy=ASCII identifier equality")
        if not all((ascii_ok, topology_ok, scope_ok)):
            raise CircuitRunFailure("generated netlist scope failed")

        sequence = [
            ("ngspice", "dc", "ngspice_dc:argv_exact", "ngspice_dc:returncode_zero", "ngspice_dc:raw_present"),
            ("ngspice", "transient", "ngspice_tran:argv_exact", "ngspice_tran:returncode_zero", "ngspice_tran:raw_present"),
            ("xyce", "dc", "xyce_dc:argv_exact", "xyce_dc:returncode_zero", "xyce_dc:raw_present"),
            ("xyce", "transient", "xyce_tran:argv_exact", "xyce_tran:returncode_zero", "xyce_tran:raw_present"),
        ]
        for route, analysis, argv_check, return_check, raw_check in sequence:
            short = "tran" if analysis == "transient" else "dc"
            argv = _argv(config, route, analysis)
            expected = [item.format(tool=config["routes"][route]["tool_path"]) for item in config["routes"][route][f"{analysis}_argv"]]
            argv_ok = argv == expected and argv[-1] == outputs[f"{route}_{short}_netlist"]
            _set(checks, argv_check, argv_ok, json.dumps(argv))
            if not argv_ok:
                raise CircuitRunFailure(f"{route} {analysis} argv differs from contract")
            formal_circuit_invoked = True
            process_invocations += 1
            completed, elapsed = _run_command(argv, ROOT / outputs[f"{route}_{short}_command"])
            commands.append({"route": route, "analysis": analysis, "argv": argv, "returncode": completed.returncode, "elapsed_seconds": elapsed})
            _set(checks, return_check, completed.returncode == 0, f"returncode={completed.returncode}")
            raw_path = ROOT / outputs[f"{route}_{short}_raw"]
            raw_ok = completed.returncode == 0 and raw_path.is_file() and raw_path.stat().st_size > 0
            _set(checks, raw_check, raw_ok, str(raw_path.relative_to(ROOT)))
            if not raw_ok:
                raise CircuitRunFailure(f"{route} {analysis} process/raw gate failed")

        process_ok = process_invocations == 4 and len(commands) == 4 and all(item["returncode"] == 0 for item in commands)
        _set(checks, "execution:exactly_four_serial_processes", process_ok, f"processes={process_invocations}")

        ng_dc_vectors = parse_ngspice_ascii_raw(ROOT / outputs["ngspice_dc_raw"])
        ng_tran_vectors = parse_ngspice_ascii_raw(ROOT / outputs["ngspice_tran_raw"])
        xy_dc_vectors = parse_xyce_prn(ROOT / outputs["xyce_dc_raw"])
        xy_tran_vectors = parse_xyce_prn(ROOT / outputs["xyce_tran_raw"])
        native_points = {
            "ngspice_dc": len(next(iter(ng_dc_vectors.values()))),
            "ngspice_transient": len(next(iter(ng_tran_vectors.values()))),
            "xyce_dc": len(next(iter(xy_dc_vectors.values()))),
            "xyce_transient": len(next(iter(xy_tran_vectors.values()))),
        }
        raw_ok = native_points["ngspice_dc"] >= 101 and native_points["xyce_dc"] >= 101 and native_points["ngspice_transient"] >= 601 and native_points["xyce_transient"] >= 601
        _set(checks, "raw:four_native_tables_parse", raw_ok, json.dumps(native_points, sort_keys=True))
        if not raw_ok:
            raise CircuitRunFailure("native raw point count failed")

        ng_dc_rows = extract_dc_rows(config, "ngspice", ng_dc_vectors)
        xy_dc_rows = extract_dc_rows(config, "xyce", xy_dc_vectors)
        ng_tran_rows = extract_transient_rows(config, "ngspice", ng_tran_vectors)
        xy_tran_rows = extract_transient_rows(config, "xyce", xy_tran_vectors)
        dc_expected = 18 * 101
        tran_expected = 36 * 601
        dc_ok = len(ng_dc_rows) == len(xy_dc_rows) == dc_expected and all(row["finite"] for row in ng_dc_rows + xy_dc_rows)
        tran_ok = len(ng_tran_rows) == len(xy_tran_rows) == tran_expected and all(row["finite"] for row in ng_tran_rows + xy_tran_rows)
        _set(checks, "tables:two_complete_dc_routes", dc_ok, f"rows={len(ng_dc_rows)}/{len(xy_dc_rows)}")
        _set(checks, "tables:two_complete_transient_routes", tran_ok, f"rows={len(ng_tran_rows)}/{len(xy_tran_rows)}")
        if not dc_ok or not tran_ok:
            raise CircuitRunFailure("normalized route table completeness failed")
        write_csv(ROOT / outputs["ngspice_dc_csv"], ng_dc_rows, DC_FIELDS)
        write_csv(ROOT / outputs["xyce_dc_csv"], xy_dc_rows, DC_FIELDS)
        write_csv(ROOT / outputs["ngspice_tran_csv"], ng_tran_rows, TRANSIENT_FIELDS)
        write_csv(ROOT / outputs["xyce_tran_csv"], xy_tran_rows, TRANSIENT_FIELDS)

        static_metrics = compute_static_metrics(ng_dc_rows + xy_dc_rows, config)
        transient_metrics = compute_transient_metrics(ng_tran_rows + xy_tran_rows, config)
        static_ok = len(static_metrics) == 36 and all(float(item["p_static_input_low_w"]) >= 0.0 and float(item["p_static_input_high_w"]) >= 0.0 for item in static_metrics)
        transient_ok = len(transient_metrics) == 72 and all(float(item["average_supply_power_w"]) >= 0.0 and float(item["cycle_energy_j"]) >= 0.0 for item in transient_metrics)
        _set(checks, "metrics:static_all_cases_and_power", static_ok, f"rows={len(static_metrics)}")
        _set(checks, "metrics:transient_all_cases_delay_and_power", transient_ok, f"rows={len(transient_metrics)}")
        write_csv(ROOT / outputs["static_metrics_csv"], static_metrics, STATIC_METRIC_FIELDS)
        write_csv(ROOT / outputs["transient_metrics_csv"], transient_metrics, TRANSIENT_METRIC_FIELDS)

        dc_anchor, transient_anchor = anchor_ids(config)
        static_anchor_rows = [item for item in static_metrics if item["case_id"] == dc_anchor]
        transient_anchor_rows = [item for item in transient_metrics if item["case_id"] == transient_anchor]
        static_anchor_ok = len(static_anchor_rows) == 2 and {item["route"] for item in static_anchor_rows} == {"ngspice", "xyce"} and all(item["qualified"] is True for item in static_anchor_rows)
        transient_anchor_ok = len(transient_anchor_rows) == 2 and {item["route"] for item in transient_anchor_rows} == {"ngspice", "xyce"} and all(item["qualified"] is True for item in transient_anchor_rows)
        _set(checks, "acceptance:both_routes_anchor_static_qualified", static_anchor_ok, json.dumps(static_anchor_rows, sort_keys=True))
        _set(checks, "acceptance:both_routes_anchor_transient_qualified", transient_anchor_ok, json.dumps(transient_anchor_rows, sort_keys=True))

        dc_differences = compute_dc_differences(ng_dc_rows, xy_dc_rows)
        transient_differences = compute_transient_differences(ng_tran_rows, xy_tran_rows)
        differences_ok = len(dc_differences) == dc_expected and len(transient_differences) == tran_expected
        _set(checks, "differences:complete_aligned_tables", differences_ok, f"rows={len(dc_differences)}/{len(transient_differences)}")
        diagnostic_ok = config["extraction_contract"]["route_difference_is_diagnostic_only"] is True and config["acceptance_contract"]["route_agreement_threshold_is_not_a_pass_gate"] is True
        _set(checks, "differences:diagnostic_only_policy_preserved", diagnostic_ok, "no route-difference acceptance threshold")
        write_csv(ROOT / outputs["dc_route_difference_csv"], dc_differences, DC_DIFFERENCE_FIELDS)
        write_csv(ROOT / outputs["transient_route_difference_csv"], transient_differences, TRANSIENT_DIFFERENCE_FIELDS)

        render_plots(config, ng_dc_rows + xy_dc_rows, ng_tran_rows + xy_tran_rows, ROOT / outputs["vtc_png"], ROOT / outputs["transient_png"])
        figures_ok = all((ROOT / outputs[key]).is_file() and (ROOT / outputs[key]).stat().st_size > 10000 for key in ("vtc_png", "transient_png"))
        _set(checks, "figures:vtc_and_transient_png", figures_ok, f"bytes={(ROOT / outputs['vtc_png']).stat().st_size}/{(ROOT / outputs['transient_png']).stat().st_size}")
        artifacts = {f"{key}_sha256": sha256(ROOT / outputs[key]) for key in ARTIFACT_KEYS if (ROOT / outputs[key]).is_file()}
        artifact_ok = len(artifacts) == len(ARTIFACT_KEYS)
        _set(checks, "artifacts:all_runner_hashes_persisted", artifact_ok, f"hashes={len(artifacts)}/{len(ARTIFACT_KEYS)}")
        final_ok = all(item["status"] == "PASS" for name, item in checks.items() if name != "result:formal_c00_complete_with_boundary")
        _set(checks, "result:formal_c00_complete_with_boundary", final_ok, "teaching-model C00 only; no physical/calibration/downstream claim")
    except Exception as exc:  # Every partial artifact remains in place.
        failure_category = type(exc).__name__
        failure_detail = str(exc)

    artifacts = {
        f"{key}_sha256": sha256(ROOT / outputs[key])
        for key in ARTIFACT_KEYS
        if (ROOT / outputs[key]).is_file()
    }
    ordered_checks = [checks[name] for name in CHECK_NAMES]
    passed = sum(item["status"] == "PASS" for item in ordered_checks)
    failed = EXPECTED_CHECK_COUNT - passed
    status = "PASS" if failed == 0 else "FAIL"
    report = {
        "schema_version": "1.0",
        "project_id": config.get("project_id"),
        "stage_id": "C00",
        "contract_id": config.get("contract_id"),
        "status": status,
        "evidence_level": "E2" if status == "PASS" else "E0",
        "simulation_status": "FORMAL_C00_COMPLETE" if status == "PASS" else "FORMAL_C00_FAILED",
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "contract_report": {"path": outputs["contract_report"], "sha256": sha256(ROOT / outputs["contract_report"])},
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": EXPECTED_CHECK_COUNT,
            "process_invocations": process_invocations,
            "formal_circuit_invoked": formal_circuit_invoked,
            "ngspice_processes": sum(item["route"] == "ngspice" for item in commands),
            "xyce_processes": sum(item["route"] == "xyce" for item in commands),
            "aimspice_processes": 0,
            "tcad_processes": 0,
            "layout_or_pex_processes": 0,
            "elapsed_seconds": time.time() - started_wall,
        },
        "native_points": native_points,
        "failure_category": failure_category,
        "failure_detail": failure_detail,
        "commands": commands,
        "checks": ordered_checks,
        "artifacts": artifacts,
        "evidence_boundary": config["evidence_boundary"]["future_runner_allowed_claim"],
        "next_gate": (
            "Commit and push this E2 runner PASS, then run the 29-check zero-process independent persisted-evidence checker exactly once."
            if status == "PASS"
            else "Preserve and commit this formal C00 failure. Do not run the PASS-only independent checker, change the anchor, or relax a threshold."
        ),
    }
    write_json(report_path, report)
    print(f"C00_ACTIVE_LOAD_INVERTER_R02_{status} checks={passed}/{EXPECTED_CHECK_COUNT} report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
