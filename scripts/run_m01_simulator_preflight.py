#!/usr/bin/env python3
"""Run the M01 tool/provenance preflight without invoking a device netlist."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_simulator_preflight_r01.json"
EXPECTED_CHECK_COUNT = 13


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_check(
    checks: list[dict[str, str]], name: str, passed: bool, detail: str
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def run_preflight() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    contract_path = ROOT / config["contract"]["path"]
    contract_report_path = ROOT / config["contract"]["report"]
    contract = load_json(contract_path)
    contract_report = load_json(contract_report_path)
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    output = config["outputs"]
    run_directory = ROOT / output["run_directory"]
    log_path = ROOT / output["preflight_log"]
    report_path = ROOT / output["preflight_report"]
    numerical_paths = [
        ROOT / value for value in config["numerical_outputs_that_must_remain_absent"]
    ]

    if run_directory.exists() or log_path.exists() or report_path.exists():
        raise RuntimeError(
            "Refusing to overwrite existing M01 preflight output: "
            f"run_directory={run_directory.exists()} log={log_path.exists()} "
            f"report={report_path.exists()}"
        )

    checks: list[dict[str, str]] = []
    add_check(
        checks,
        "identity:revision_1_preflight",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_SIMULATOR_PREFLIGHT_R01"
        and config.get("revision") == 1
        and config.get("status") == "preflight_planned",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    add_check(
        checks,
        "contract:committed_revision_3_pass_is_bound",
        config["bound_contract_commit"]
        == "49b93a456b490b56f7d431ee24e11b3a388c66b5"
        and sha256(contract_path) == config["contract"]["sha256"]
        and sha256(contract_report_path) == config["contract"]["report_sha256"]
        and contract.get("revision") == 3
        and contract_report.get("status") == "PASS"
        and contract_report.get("summary", {}).get("passed") == 32,
        f"contract_revision={contract.get('revision')} report={contract_report.get('status')}",
    )
    add_check(
        checks,
        "outputs:numerical_outputs_absent_before_preflight",
        all(not path.exists() for path in numerical_paths),
        f"absent={sum(not path.exists() for path in numerical_paths)}/{len(numerical_paths)}",
    )

    ng_route = config["routes"]["ngspice_behavioral"]
    ng_tool = Path(ng_route["tool_path"])
    add_check(
        checks,
        "ngspice:executable_fingerprint",
        ng_tool.is_file()
        and ng_tool.stat().st_size == ng_route["tool_bytes"]
        and sha256(ng_tool) == ng_route["tool_sha256"],
        f"exists={ng_tool.is_file()} bytes={ng_tool.stat().st_size if ng_tool.exists() else -1}",
    )
    ng_argv = ng_route["allowed_probe_argv"]
    add_check(
        checks,
        "ngspice:version_probe_has_no_netlist_argument",
        ng_argv == [str(ng_tool), "--version"]
        and config["preflight_rules"]["ngspice_version_probe_only"] is True,
        json.dumps(ng_argv),
    )
    ng_result = subprocess.run(
        ng_argv,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    ng_output = ng_result.stdout + ng_result.stderr
    add_check(
        checks,
        "ngspice:version_identified",
        ng_result.returncode == 0
        and ng_route["required_version_token"] in ng_output,
        f"returncode={ng_result.returncode} token={ng_route['required_version_token']}",
    )

    aim_route = config["routes"]["aimspice_level15"]
    aim_tool = Path(aim_route["tool_path"])
    add_check(
        checks,
        "aimspice:executable_fingerprint",
        aim_tool.is_file()
        and aim_tool.stat().st_size == aim_route["tool_bytes"]
        and sha256(aim_tool) == aim_route["tool_sha256"],
        f"exists={aim_tool.is_file()} bytes={aim_tool.stat().st_size if aim_tool.exists() else -1}",
    )
    license_provenance = aim_route["license_provenance"]
    add_check(
        checks,
        "aimspice:license_provenance_is_auditable",
        license_provenance["auditable_for_formal_project_evidence"] is True,
        license_provenance["status"],
    )
    add_check(
        checks,
        "aimspice:documented_reproducible_batch_cli",
        aim_route["documented_batch_cli_status"] == "ESTABLISHED",
        aim_route["documented_batch_cli_status"],
    )
    add_check(
        checks,
        "aimspice:not_invoked_by_formal_runner",
        aim_route["runner_must_not_invoke"] is True
        and config["preflight_rules"]["aimspice_process_invocation_by_runner"] is False,
        "static fingerprint only; no AIM-Spice subprocess call exists in this runner",
    )

    candidate_checks = []
    for route in (ng_route, aim_route):
        candidate_path = ROOT / route["candidate_path"]
        candidate_checks.append(
            candidate_path.is_file()
            and sha256(candidate_path) == route["candidate_sha256"]
            and "IGZO" in candidate_path.read_text(encoding="ascii")
            and "M01_EXECUTION_REQUIRED" in candidate_path.read_text(encoding="ascii")
        )
    add_check(
        checks,
        "candidates:frozen_igzo_only_files_unchanged",
        all(candidate_checks),
        f"ngspice={candidate_checks[0]} aimspice={candidate_checks[1]}",
    )
    add_check(
        checks,
        "execution:no_device_netlist_or_numerical_result",
        config["preflight_rules"]["device_netlist_invocation_permitted"] is False
        and config["preflight_rules"]["numerical_curve_generation_permitted"] is False
        and all(not path.exists() for path in numerical_paths),
        "only ngspice --version executed; no netlist was supplied",
    )
    downstream_ids = ["C00", "C01", "C02", "C03", "L00", "V00", "V01", "PEX0", "FE0"]
    add_check(
        checks,
        "gate:route_failure_stops_m01_and_downstream",
        config["preflight_rules"]["either_route_failure_stops_m01"] is True
        and config["preflight_rules"]["circuit_or_downstream_permitted"] is False
        and experiment_map["M01"].get("status") == "contract_ready"
        and all(
            experiment_map[item].get("status") in {"planned", "optional"}
            for item in downstream_ids
        ),
        "M01 was contract_ready before preflight; all downstream stages remain closed",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"Preflight check registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    failures = [item for item in checks if item["status"] == "FAIL"]
    run_directory.mkdir(parents=True, exist_ok=False)
    log_lines = [
        "M01 simulator preflight R01",
        "device_netlist_invoked=false",
        "numerical_curve_generated=false",
        "ngspice_argv=" + json.dumps(ng_argv),
        f"ngspice_returncode={ng_result.returncode}",
        "ngspice_output_begin",
        ng_output.rstrip(),
        "ngspice_output_end",
        "aimspice_runner_invoked=false",
        "aimspice_license_status=" + license_provenance["status"],
        "aimspice_batch_cli_status=" + aim_route["documented_batch_cli_status"],
        "formal_result=FAIL_STOP_M01",
    ]
    with log_path.open("x", encoding="utf-8") as stream:
        stream.write("\n".join(log_lines) + "\n")

    report = {
        "status": "FAIL" if failures else "PASS",
        "preflight_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E2",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "ngspice_preflight_status": (
            "PASS"
            if all(
                item["status"] == "PASS"
                for item in checks
                if item["name"].startswith("ngspice:")
            )
            else "FAIL"
        ),
        "aimspice_preflight_status": (
            "PASS"
            if all(
                item["status"] == "PASS"
                for item in checks
                if item["name"].startswith("aimspice:")
            )
            else "FAIL"
        ),
        "device_simulation_status": "NOT_RUN_BY_PREFLIGHT",
        "spice_numerical_status": "NOT_RUN_BY_PREFLIGHT",
        "circuit_status": "NOT_RUN_BY_PREFLIGHT",
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "simulator_processes_invoked_by_runner": 1,
            "simulator_process_invocations": [
                {
                    "tool": "ngspice",
                    "purpose": "version probe only",
                    "argv": ng_argv,
                    "returncode": ng_result.returncode,
                    "netlist_argument_supplied": False,
                }
            ],
            "aimspice_invoked_by_runner": False,
            "prior_aimspice_exploratory_probe": aim_route["prior_exploratory_probe"],
            "numerical_outputs_created": False,
        },
        "config": {
            "path": str(CONFIG_PATH.relative_to(ROOT)),
            "sha256": sha256(CONFIG_PATH),
        },
        "runner": {
            "path": str(Path(__file__).relative_to(ROOT)),
            "sha256": sha256(Path(__file__)),
        },
        "log": {
            "path": str(log_path.relative_to(ROOT)),
            "sha256": sha256(log_path),
        },
        "failure_boundary": config["failure_boundary"],
        "next_gate": config["next_gate_after_failure"],
    }
    with report_path.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_SIMULATOR_PREFLIGHT_{report['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} "
        f"report={report_path}"
    )
    return report


if __name__ == "__main__":
    result = run_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
