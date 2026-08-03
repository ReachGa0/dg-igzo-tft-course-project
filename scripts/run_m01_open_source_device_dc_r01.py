#!/usr/bin/env python3
"""Run the two formal open-source M01 device-only DC routes exactly once."""

from __future__ import annotations

import json
import math
import subprocess
import time
from pathlib import Path
from typing import Any

from m01_open_source_device_dc_r01_common import (
    DIFFERENCE_FIELDS,
    METRIC_FIELDS,
    RAW_FIELDS,
    compute_metrics,
    compute_route_differences,
    extract_route_rows,
    generate_device_netlist,
    load_csv,
    load_json,
    parse_ngspice_ascii_raw,
    parse_xyce_prn,
    render_plots,
    sha256,
    write_csv,
    write_json,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_open_source_device_dc_r01.json"
CONTRACT_CHECKER_PATH = ROOT / "scripts" / "check_m01_open_source_device_dc_r01_contract.py"
RUNNER_PATH = Path(__file__).resolve()
EXPECTED_CHECK_COUNT = 30

CHECK_NAMES = [
    "precondition:committed_static_contract_pass",
    "identity:config_and_runner_hashes",
    "binding:r11_complete_preflight",
    "targets:frozen_files_and_counts",
    "candidate:frozen_igzo_bytes",
    "tools:two_hash_bound_open_source_routes",
    "outputs:exclusive_absent_before_run",
    "resource:two_process_serial_budget",
    "targets:row_alignment_and_finite_inputs",
    "netlists:ascii_generation",
    "netlists:247_devices_per_route",
    "netlists:igzo_device_dc_scope",
    "ngspice:argv_exact",
    "ngspice:returncode_zero",
    "ngspice:raw_output_present",
    "ngspice:247_finite_currents",
    "ngspice:zero_vds_invariant",
    "xyce:argv_exact",
    "xyce:returncode_zero",
    "xyce:raw_output_present",
    "xyce:247_finite_currents",
    "xyce:zero_vds_invariant",
    "outputs:two_raw_csvs",
    "metrics:thirty_rows",
    "differences:247_rows",
    "figures:two_pngs",
    "artifacts:hash_manifest_complete",
    "execution:exactly_two_route_processes",
    "scope:no_aimspice_tcad_circuit_or_downstream",
    "result:formal_device_dc_complete_with_boundary",
]

ARTIFACT_KEYS = [
    "ngspice_netlist",
    "xyce_netlist",
    "ngspice_log",
    "xyce_log",
    "ngspice_command_log",
    "xyce_command_log",
    "ngspice_raw_output",
    "xyce_raw_output",
    "ngspice_raw_csv",
    "xyce_raw_csv",
    "route_metrics_csv",
    "route_difference_csv",
    "overlay_png",
    "route_difference_png",
]


class RouteFailure(RuntimeError):
    pass


def _new_checks() -> dict[str, dict[str, str]]:
    return {
        name: {"name": name, "status": "FAIL", "detail": "not reached"}
        for name in CHECK_NAMES
    }


def _set(
    checks: dict[str, dict[str, str]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {
        "name": name,
        "status": "PASS" if passed else "FAIL",
        "detail": detail,
    }


def _run_command(
    argv: list[str], command_log: Path, *, cwd: Path
) -> tuple[subprocess.CompletedProcess[str], float]:
    started = time.monotonic()
    completed = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    elapsed = time.monotonic() - started
    write_json(
        command_log,
        {
            "argv": argv,
            "cwd": str(cwd),
            "returncode": completed.returncode,
            "elapsed_seconds": elapsed,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        },
    )
    return completed, elapsed


def _future_output_paths(config: dict[str, Any]) -> list[Path]:
    outputs = config["outputs"]
    return [
        ROOT / value
        for key, value in outputs.items()
        if key not in {"contract_report", "run_directory"}
    ] + [ROOT / outputs["run_directory"]]


def run() -> int:
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    machine = experiment_map["M01"]["open_source_device_dc_r01"]
    outputs = config["outputs"]
    report_path = ROOT / outputs["run_report"]
    checks = _new_checks()
    command_records: list[dict[str, Any]] = []
    process_invocations = 0
    formal_device_dc_invoked = False
    started_wall = time.time()
    failure_category: str | None = None
    failure_detail: str | None = None
    artifacts: dict[str, str] = {}

    try:
        if len(CHECK_NAMES) != EXPECTED_CHECK_COUNT:
            raise RuntimeError(
                f"runner registry mismatch expected={EXPECTED_CHECK_COUNT} actual={len(CHECK_NAMES)}"
            )
        contract_report_path = ROOT / outputs["contract_report"]
        if not contract_report_path.is_file():
            raise RuntimeError("committed static contract report is absent")
        contract_report = load_json(contract_report_path)
        committed_static_pass = (
            contract_report.get("status") == "PASS"
            and contract_report.get("evidence_level") == "E3"
            and contract_report.get("summary", {}).get("passed") == 40
            and contract_report.get("summary", {}).get("failed") == 0
            and contract_report.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
            and contract_report.get("runner", {}).get("sha256") == sha256(RUNNER_PATH)
            and machine.get("status") == "contract_ready"
            and machine.get("current_evidence") == "E3"
            and machine.get("contract_check_completed") is True
            and machine.get("contract_status") == "PASS"
            and machine.get("contract_checks_passed") == 40
            and machine.get("contract_checks_failed") == 0
            and machine.get("formal_run_completed") is False
            and machine.get("runner_processes_invoked") == 0
            and outputs["contract_report"] in machine.get("result_paths", [])
            and project.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute the committed M01 open-source device DC R01 two-route runner"
            )
        )
        _set(
            checks,
            "precondition:committed_static_contract_pass",
            committed_static_pass,
            (
                f"report={contract_report.get('status')} "
                f"passed={contract_report.get('summary', {}).get('passed')} "
                f"machine={machine.get('status')}"
            ),
        )
        if not committed_static_pass:
            raise RouteFailure("committed static PASS machine gate failed")
        identity_ok = (
            contract_report.get("contract_checker", {}).get("sha256")
            == sha256(CONTRACT_CHECKER_PATH)
            and contract_report.get("contract_id") == config["contract_id"]
        )
        _set(
            checks,
            "identity:config_and_runner_hashes",
            identity_ok,
            f"contract={config['contract_id']}",
        )
        if not identity_ok:
            raise RouteFailure("static contract identity changed")

        binding = config["committed_preflight_binding"]
        bound_paths = [
            (binding["r11_config_path"], binding["r11_config_sha256"]),
            (binding["r11_contract_checker_path"], binding["r11_contract_checker_sha256"]),
            (binding["r11_contract_report_path"], binding["r11_contract_report_sha256"]),
            (binding["r11_runner_path"], binding["r11_runner_sha256"]),
            (binding["r11_runner_report_path"], binding["r11_runner_report_sha256"]),
            (binding["r11_independent_checker_path"], binding["r11_independent_checker_sha256"]),
            (binding["r11_independent_report_path"], binding["r11_independent_report_sha256"]),
            (binding["r11_common_path"], binding["r11_common_sha256"]),
        ]
        r11_report = load_json(ROOT / binding["r11_runner_report_path"])
        r11_check = load_json(ROOT / binding["r11_independent_report_path"])
        r11_ok = (
            all((ROOT / path).is_file() and sha256(ROOT / path) == expected for path, expected in bound_paths)
            and r11_report.get("status") == "PASS"
            and r11_report.get("summary", {}).get("passed") == 32
            and r11_check.get("status") == "PASS"
            and r11_check.get("summary", {}).get("passed") == 25
            and r11_check.get("processes_invoked") == 0
            and r11_report.get("summary", {}).get("formal_device_dc_invoked") is False
        )
        _set(checks, "binding:r11_complete_preflight", r11_ok, f"artifacts={len(bound_paths)}")
        if not r11_ok:
            raise RouteFailure("R11 binding changed")

        target = config["target_contract"]
        manifest_path = ROOT / target["selection_manifest"]
        prediction_path = ROOT / target["prediction_table"]
        manifest_rows, manifest_fields = load_csv(manifest_path)
        prediction_rows, prediction_fields = load_csv(prediction_path)
        targets_ok = (
            sha256(manifest_path) == target["selection_manifest_sha256"]
            and sha256(prediction_path) == target["prediction_table_sha256"]
            and len(manifest_rows) == len(prediction_rows) == 247
            and len({row["curve_id"] for row in manifest_rows}) == 13
        )
        _set(checks, "targets:frozen_files_and_counts", targets_ok, f"rows={len(manifest_rows)} curves={len({row.get('curve_id') for row in manifest_rows})}")
        if not targets_ok:
            raise RouteFailure("target binding changed")

        candidate_path = ROOT / config["device_contract"]["candidate_path"]
        candidate_text = candidate_path.read_text(encoding="ascii")
        candidate_ok = (
            sha256(candidate_path) == config["device_contract"]["candidate_sha256"]
            and ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text
            and "M01_EXECUTION_REQUIRED" in candidate_text
        )
        _set(checks, "candidate:frozen_igzo_bytes", candidate_ok, sha256(candidate_path))
        if not candidate_ok:
            raise RouteFailure("candidate binding changed")

        route_tools = [config["routes"]["ngspice"], config["routes"]["xyce"]]
        tools_ok = all(
            Path(route["tool_path"]).is_file()
            and sha256(Path(route["tool_path"])) == route["tool_sha256"]
            and Path(route["tool_path"]).stat().st_size == route["tool_bytes"]
            for route in route_tools
        )
        _set(checks, "tools:two_hash_bound_open_source_routes", tools_ok, "ngspice and GPL Xyce fingerprints")
        if not tools_ok:
            raise RouteFailure("tool fingerprint changed")

        future_paths = _future_output_paths(config)
        outputs_absent = all(not path.exists() for path in future_paths)
        _set(checks, "outputs:exclusive_absent_before_run", outputs_absent, f"checked={len(future_paths)}")
        if not outputs_absent:
            raise RouteFailure("formal output path already exists")
        budget = config["resource_budget"]
        budget_ok = (
            budget["route_processes"] == 2
            and budget["ngspice_processes"] == 1
            and budget["xyce_processes"] == 1
            and budget["generated_device_netlists"] == 2
            and budget["parallel_route_execution"] is False
        )
        _set(checks, "resource:two_process_serial_budget", budget_ok, json.dumps(budget, sort_keys=True))
        if not budget_ok:
            raise RouteFailure("resource budget changed")

        prediction_by_uid = {row["row_uid"]: row for row in prediction_rows}
        aligned = (
            len({row["row_uid"] for row in manifest_rows}) == len(manifest_rows)
            and len(prediction_by_uid) == len(prediction_rows)
            and {row["row_uid"] for row in manifest_rows} == set(prediction_by_uid)
            and all(
                row[field] == prediction_by_uid[row["row_uid"]][field]
                for row in manifest_rows
                for field in (
                    "curve_id", "dataset_id", "split", "kind", "topology",
                    "selection_role", "optimizer_input", "vbg_v", "vtg_v",
                    "vds_v", "primary_axis_v", "target_current_a_per_cm",
                    "w_um", "l_um", "temperature_k",
                )
            )
            and all(
                math.isfinite(float(row[field]))
                for row in manifest_rows
                for field in ("vbg_v", "vtg_v", "vds_v", "target_current_a_per_cm", "w_um", "l_um", "temperature_k")
            )
            and all(
                math.isfinite(float(row["model_current_a_per_cm"]))
                for row in prediction_rows
            )
            and all(float(row["w_um"]) == 60.0 and float(row["l_um"]) in {8.0, 10.0, 12.0} and float(row["temperature_k"]) == 300.0 for row in manifest_rows)
        )
        _set(checks, "targets:row_alignment_and_finite_inputs", aligned, f"manifest_fields={len(manifest_fields)} prediction_fields={len(prediction_fields)}")
        if not aligned:
            raise RouteFailure("target rows are not aligned")

        run_directory = ROOT / outputs["run_directory"]
        run_directory.mkdir(parents=True, exist_ok=False)
        include_line = config["netlist_contract"]["candidate_include"]
        ng_netlist_text = generate_device_netlist(
            manifest_rows,
            "ngspice",
            include_line,
            config["routes"]["ngspice"]["raw_output"],
        )
        xy_netlist_text = generate_device_netlist(
            manifest_rows,
            "xyce",
            include_line,
            config["routes"]["xyce"]["raw_output"],
        )
        ng_netlist = ROOT / outputs["ngspice_netlist"]
        xy_netlist = ROOT / outputs["xyce_netlist"]
        ng_netlist.write_text(ng_netlist_text, encoding="ascii", newline="\n")
        xy_netlist.write_text(xy_netlist_text, encoding="ascii", newline="\n")
        _set(checks, "netlists:ascii_generation", ng_netlist_text.isascii() and xy_netlist_text.isascii(), "two ASCII netlists")
        device_counts_ok = ng_netlist_text.count("XDEV") == xy_netlist_text.count("XDEV") == 247
        _set(checks, "netlists:247_devices_per_route", device_counts_ok, f"ng={ng_netlist_text.count('XDEV')} xyce={xy_netlist_text.count('XDEV')}")
        forbidden = [token.lower() for token in config["netlist_contract"]["forbidden_case_insensitive_tokens"]]
        scope_ok = all(token not in ng_netlist_text.lower() and token not in xy_netlist_text.lower() for token in forbidden) and ng_netlist_text.count(".DC VSWEEP 0 0 1") == 1 and xy_netlist_text.count(".DC VSWEEP 0 0 1") == 1
        _set(checks, "netlists:igzo_device_dc_scope", scope_ok, "IGZO-only .DC, no transient/circuit assets")
        if not all((device_counts_ok, scope_ok)):
            raise RouteFailure("generated netlist scope failed")

        ng_route = config["routes"]["ngspice"]
        ng_argv = [item.format(tool=ng_route["tool_path"]) for item in ng_route["argv_template"]]
        expected_ng_argv = [
            ng_route["tool_path"],
            "-b",
            "-o",
            outputs["ngspice_log"],
            outputs["ngspice_netlist"],
        ]
        ng_argv_ok = ng_argv == expected_ng_argv
        _set(checks, "ngspice:argv_exact", ng_argv_ok, json.dumps(ng_argv))
        if not ng_argv_ok:
            raise RouteFailure("ngspice argv differs from the frozen command")
        formal_device_dc_invoked = True
        process_invocations += 1
        ng_completed, ng_elapsed = _run_command(ng_argv, ROOT / outputs["ngspice_command_log"], cwd=ROOT)
        command_records.append({"route": "ngspice", "argv": ng_argv, "returncode": ng_completed.returncode, "elapsed_seconds": ng_elapsed})
        _set(checks, "ngspice:returncode_zero", ng_completed.returncode == 0, f"returncode={ng_completed.returncode}")
        if ng_completed.returncode != 0:
            raise RouteFailure("ngspice returned nonzero")
        ng_raw_path = ROOT / outputs["ngspice_raw_output"]
        _set(checks, "ngspice:raw_output_present", ng_raw_path.is_file() and ng_raw_path.stat().st_size > 0, str(ng_raw_path.relative_to(ROOT)))
        ng_currents = parse_ngspice_ascii_raw(ng_raw_path)
        ng_rows = extract_route_rows(manifest_rows, prediction_rows, "ngspice", ng_currents)
        ng_finite = len(ng_rows) == 247 and all(row["finite_current"] is True for row in ng_rows)
        _set(checks, "ngspice:247_finite_currents", ng_finite, f"rows={len(ng_rows)}")
        zero_limit = float(config["extraction_contract"]["zero_vds_max_current_a_per_cm"])
        ng_zero_max = max(float(row["current_a_per_cm"]) for row in ng_rows if float(row["vds_v"]) == 0.0)
        _set(checks, "ngspice:zero_vds_invariant", ng_zero_max <= zero_limit, f"max={ng_zero_max:.17g}")
        if not ng_finite or ng_zero_max > zero_limit:
            raise RouteFailure("ngspice extraction gate failed")

        xy_route = config["routes"]["xyce"]
        xy_argv = [item.format(tool=xy_route["tool_path"]) for item in xy_route["argv_template"]]
        expected_xy_argv = [
            xy_route["tool_path"],
            "-l",
            outputs["xyce_log"],
            "-o",
            "results/compact/m01_open_source_cross_check_r01/xyce_values",
            outputs["xyce_netlist"],
        ]
        xy_argv_ok = xy_argv == expected_xy_argv
        _set(checks, "xyce:argv_exact", xy_argv_ok, json.dumps(xy_argv))
        if not xy_argv_ok:
            raise RouteFailure("Xyce argv differs from the frozen command")
        process_invocations += 1
        xy_completed, xy_elapsed = _run_command(xy_argv, ROOT / outputs["xyce_command_log"], cwd=ROOT)
        command_records.append({"route": "xyce", "argv": xy_argv, "returncode": xy_completed.returncode, "elapsed_seconds": xy_elapsed})
        _set(checks, "xyce:returncode_zero", xy_completed.returncode == 0, f"returncode={xy_completed.returncode}")
        if xy_completed.returncode != 0:
            raise RouteFailure("Xyce returned nonzero")
        xy_raw_path = ROOT / outputs["xyce_raw_output"]
        _set(checks, "xyce:raw_output_present", xy_raw_path.is_file() and xy_raw_path.stat().st_size > 0, str(xy_raw_path.relative_to(ROOT)))
        xy_currents = parse_xyce_prn(xy_raw_path)
        xy_rows = extract_route_rows(manifest_rows, prediction_rows, "xyce", xy_currents)
        xy_finite = len(xy_rows) == 247 and all(row["finite_current"] is True for row in xy_rows)
        _set(checks, "xyce:247_finite_currents", xy_finite, f"rows={len(xy_rows)}")
        xy_zero_max = max(float(row["current_a_per_cm"]) for row in xy_rows if float(row["vds_v"]) == 0.0)
        _set(checks, "xyce:zero_vds_invariant", xy_zero_max <= zero_limit, f"max={xy_zero_max:.17g}")
        if not xy_finite or xy_zero_max > zero_limit:
            raise RouteFailure("Xyce extraction gate failed")

        ng_csv = ROOT / outputs["ngspice_raw_csv"]
        xy_csv = ROOT / outputs["xyce_raw_csv"]
        write_csv(ng_csv, ng_rows, RAW_FIELDS)
        write_csv(xy_csv, xy_rows, RAW_FIELDS)
        _set(checks, "outputs:two_raw_csvs", ng_csv.is_file() and xy_csv.is_file(), "247 rows per route")
        floor = float(config["extraction_contract"]["current_floor_a_per_cm"])
        metric_rows = compute_metrics(ng_rows, floor) + compute_metrics(xy_rows, floor)
        metrics_path = ROOT / outputs["route_metrics_csv"]
        write_csv(metrics_path, metric_rows, METRIC_FIELDS)
        metrics_ok = len(metric_rows) == 30 and all(
            math.isfinite(float(row[field]))
            for row in metric_rows
            for field in (
                "linear_nrmse",
                "log_rmse_dec",
                "max_abs_model_error_a_per_cm",
                "max_log_model_error_dec",
            )
        )
        _set(checks, "metrics:thirty_rows", metrics_ok, f"rows={len(metric_rows)} finite={metrics_ok}")
        difference_rows = compute_route_differences(ng_rows, xy_rows, floor)
        difference_path = ROOT / outputs["route_difference_csv"]
        write_csv(difference_path, difference_rows, DIFFERENCE_FIELDS)
        differences_ok = len(difference_rows) == 247 and all(
            math.isfinite(float(row["absolute_difference_a_per_cm"]))
            and math.isfinite(float(row["log_difference_dec"]))
            for row in difference_rows
        )
        _set(checks, "differences:247_rows", differences_ok, f"rows={len(difference_rows)} finite={differences_ok}")
        overlay_path = ROOT / outputs["overlay_png"]
        route_difference_path = ROOT / outputs["route_difference_png"]
        render_plots(ng_rows, xy_rows, difference_rows, overlay_path, route_difference_path, floor)
        figures_ok = all(path.is_file() and path.stat().st_size > 1000 for path in (overlay_path, route_difference_path))
        _set(checks, "figures:two_pngs", figures_ok, f"bytes={overlay_path.stat().st_size}/{route_difference_path.stat().st_size}")

        artifacts = {
            f"{key}_sha256": sha256(ROOT / outputs[key])
            for key in ARTIFACT_KEYS
            if (ROOT / outputs[key]).is_file()
        }
        _set(checks, "artifacts:hash_manifest_complete", len(artifacts) == len(ARTIFACT_KEYS), f"hashes={len(artifacts)}/{len(ARTIFACT_KEYS)}")
        process_ok = process_invocations == 2 and len(command_records) == 2 and all(item["returncode"] == 0 for item in command_records)
        _set(checks, "execution:exactly_two_route_processes", process_ok, f"processes={process_invocations}")
        scope_closed = config["resource_budget"]["aimspice_processes"] == 0 and config["resource_budget"]["tcad_processes"] == 0 and config["resource_budget"]["circuit_processes"] == 0 and config["resource_budget"]["layout_processes"] == 0
        _set(checks, "scope:no_aimspice_tcad_circuit_or_downstream", scope_closed, "only ngspice and Xyce device DC")
        final_ready = all(item["status"] == "PASS" for name, item in checks.items() if name != "result:formal_device_dc_complete_with_boundary")
        _set(checks, "result:formal_device_dc_complete_with_boundary", final_ready, "device-only numerical comparison; no physical/calibration/circuit claim")
    except Exception as exc:  # Evidence must survive every failure class.
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
        "stage_id": "M01",
        "contract_id": config.get("contract_id"),
        "status": status,
        "evidence_level": "E2" if status == "PASS" else "E0",
        "simulation_status": "FORMAL_DEVICE_DC_COMPLETE" if status == "PASS" else "FORMAL_DEVICE_DC_FAILED",
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "contract_report": {"path": outputs["contract_report"], "sha256": sha256(ROOT / outputs["contract_report"]) if (ROOT / outputs["contract_report"]).is_file() else None},
        "summary": {
            "passed": passed,
            "failed": failed,
            "total": EXPECTED_CHECK_COUNT,
            "process_invocations": process_invocations,
            "formal_device_dc_invoked": formal_device_dc_invoked,
            "ngspice_invoked": any(item.get("route") == "ngspice" for item in command_records),
            "xyce_invoked": any(item.get("route") == "xyce" for item in command_records),
            "aimspice_invoked": False,
            "tcad_invoked": False,
            "circuit_or_downstream_invoked": False,
            "elapsed_seconds": time.time() - started_wall,
        },
        "failure_category": failure_category,
        "failure_detail": failure_detail,
        "commands": command_records,
        "checks": ordered_checks,
        "artifacts": artifacts,
        "evidence_boundary": config.get("evidence_boundary"),
        "next_gate": (
            "Commit and push the E2 runner PASS, then run the 24-check independent persisted-evidence checker exactly once. C00 and downstream remain closed."
            if status == "PASS"
            else "Preserve and commit this formal-run failure. Do not run the independent PASS-only checker or relax the contract."
        ),
    }
    if report_path.exists():
        raise RuntimeError(f"runner refuses to overwrite {report_path}")
    write_json(report_path, report)
    print(
        f"M01_OPEN_SOURCE_DEVICE_DC_R01_{status} checks={passed}/{EXPECTED_CHECK_COUNT} "
        f"report={report_path}"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
