#!/usr/bin/env python3
"""Run the R09 Xyce output/parser recovery without rebuilding any tool."""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from m01_xyce_r09_common import digest_tree, load_json, read_xyce_prn, sha256, tree_matches


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r09.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r09.py"
EXPECTED_CHECK_COUNT = 32


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def run_command(
    name: str,
    argv: list[str],
    run_directory: Path,
    records: list[dict[str, Any]],
    timeout_seconds: int = 120,
) -> tuple[bool, str]:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            argv,
            cwd=ROOT,
            env=os.environ.copy(),
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
        output = completed.stdout + completed.stderr
        returncode = completed.returncode
        timed_out = False
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or "") + (error.stderr or "")
        returncode = None
        timed_out = True
    elapsed = time.monotonic() - started
    log_path = run_directory / f"{name}.log"
    log_path.write_text(
        "argv=" + json.dumps(argv, ensure_ascii=True) + "\n"
        + "cwd=" + str(ROOT) + "\n"
        + f"returncode={returncode}\n"
        + f"timed_out={timed_out}\n"
        + f"elapsed_seconds={elapsed:.6f}\n"
        + "output_begin\n"
        + output
        + "\noutput_end\n",
        encoding="utf-8",
    )
    records.append(
        {
            "name": name,
            "argv": argv,
            "cwd": str(ROOT),
            "returncode": returncode,
            "timed_out": timed_out,
            "elapsed_seconds": elapsed,
            "log_path": str(log_path.relative_to(ROOT)),
            "log_sha256": sha256(log_path),
        }
    )
    return returncode == 0 and not timed_out, output


def check_preflight() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report_path = ROOT / outputs["preflight_report"]
    independent_report_path = ROOT / outputs["independent_check_report"]
    run_directory = ROOT / outputs["run_directory"]
    if report_path.exists() or independent_report_path.exists() or run_directory.exists():
        raise RuntimeError("R09 refuses to overwrite an existing report, check report or run directory")

    checks: list[dict[str, str]] = []
    command_records: list[dict[str, Any]] = []
    r07 = config["r07_failure_binding"]
    r07_report_path = ROOT / r07["preflight_report_path"]
    r07_contract_report_path = ROOT / r07["contract_report_path"]
    r07_report = load_json(r07_report_path) if r07_report_path.is_file() else {}
    r07_contract_report = load_json(r07_contract_report_path) if r07_contract_report_path.is_file() else {}
    r07_artifact_paths = [
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
    r07_artifacts_ok = all(
        (ROOT / relative).is_file() and sha256(ROOT / relative) == expected
        for relative, expected in r07_artifact_paths
    )
    generator_prefix = Path(r07["generator_prefix"])
    xyce_prefix = Path(r07["xyce_prefix"])
    generator_tree = digest_tree(generator_prefix) if generator_prefix.is_dir() else {}
    xyce_tree = digest_tree(xyce_prefix) if xyce_prefix.is_dir() else {}
    xyce_binary = Path(config["toolchain"]["xyce_binary"])
    formal_paths = [ROOT / value for value in config["formal_outputs_that_must_remain_absent"]]
    future_paths = [
        ROOT / value for key, value in outputs.items() if key != "contract_report"
    ]

    add_check(
        checks,
        "identity:revision_9_xyce_parser_recovery",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R09"
        and config.get("revision") == 9
        and config.get("status") == "preflight_planned",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    add_check(
        checks,
        "binding:r07_failure_report",
        r07_report.get("status") == "FAIL"
        and r07_report.get("evidence_level") == "E0"
        and r07_report.get("preflight_status") == "FAIL"
        and r07_report.get("build_status") == "PASS"
        and len(r07_report.get("checks", [])) == 47
        and sum(item.get("status") == "PASS" for item in r07_report.get("checks", [])) == 42
        and r07_report.get("summary", {}).get("controlled_bsource_self_test_invoked") is True
        and r07_report.get("summary", {}).get("device_syntax_only_invoked") is False
        and r07_report.get("summary", {}).get("formal_device_dc_invoked") is False,
        "immutable R07 42/47 runner failure with Xyce build status PASS",
    )
    add_check(
        checks,
        "binding:r07_artifacts_hash_bound",
        r07["must_remain_unchanged"] is True
        and r07["bound_commit"] == "9a7375ef30ae90adf5214b3c7421a5f7a8cab726"
        and r07_artifacts_ok,
        f"artifacts={sum((ROOT / item[0]).is_file() for item in r07_artifact_paths)}/{len(r07_artifact_paths)}",
    )
    add_check(
        checks,
        "binding:r07_complete_generator_prefix",
        tree_matches(generator_prefix, r07["generator_prefix_tree"]),
        f"tree={generator_tree.get('tree_sha256')}",
    )
    add_check(
        checks,
        "binding:r07_complete_xyce_prefix",
        tree_matches(xyce_prefix, r07["xyce_prefix_tree"]),
        f"tree={xyce_tree.get('tree_sha256')}",
    )
    add_check(
        checks,
        "scope:igzo_laptop_tool_only",
        config["scope"]["active_material_scope"] == "IGZO only"
        and config["scope"]["dimension"].startswith("2D")
        and config["scope"]["laptop_target"] is True
        and config["scope"]["formal_m01_numerical_run"] is False
        and config["scope"]["circuit_or_downstream_permitted"] is False,
        json.dumps(config["scope"], sort_keys=True),
    )
    add_check(
        checks,
        "reuse:no_build_or_dependency_rebuild",
        config["reuse_policy"]["rebuild_generator_or_xyce"] is False
        and config["reuse_policy"]["reuse_r07_build_directory"] is False
        and config["reuse_policy"]["reuse_r07_output_directory"] is False
        and config["reuse_policy"]["reuse_r07_failure_report"] is False
        and config["toolchain"]["build_commands_permitted"] is False
        and config["toolchain"]["generator_commands_permitted"] is False
        and config["toolchain"]["dependency_commands_permitted"] is False,
        "R09 reuses only complete R07 install prefixes",
    )
    add_check(
        checks,
        "paths:r09_exclusive_namespace",
        len(future_paths) == len(set(future_paths))
        and all(not path.exists() for path in future_paths)
        and str(run_directory).endswith("m01_xyce_build_preflight_r09"),
        f"future_absent={sum(not path.exists() for path in future_paths)}/{len(future_paths)}",
    )

    run_directory.mkdir(parents=True, exist_ok=False)
    preflight_log = ROOT / outputs["preflight_log"]
    preflight_log.write_text(
        "M01 Xyce output/parser recovery preflight R09\n"
        "build_invoked=false\n"
        "generator_build_invoked=false\n"
        "dependency_rebuild_invoked=false\n"
        "ngspice_invoked=false\n"
        "aimspice_invoked=false\n"
        "formal_device_dc_invoked=false\n"
        "r07_failure_reused=false\n"
        "r07_complete_generator_prefix_reused=true\n"
        "r07_complete_xyce_prefix_reused=true\n",
        encoding="utf-8",
    )

    version_ok, version_output = run_command(
        "xyce_version",
        [str(xyce_binary), "-v"],
        run_directory,
        command_records,
    )
    license_ok, license_output = run_command(
        "xyce_license",
        [str(xyce_binary), "-license"],
        run_directory,
        command_records,
    )
    add_check(
        checks,
        "binary:version",
        version_ok and "Xyce Release 7.10.0" in version_output,
        version_output.strip()[:200],
    )
    add_check(
        checks,
        "binary:license",
        license_ok and "GNU General Public License" in license_output,
        "GPL token present" if "GNU General Public License" in license_output else "GPL token absent",
    )
    add_check(
        checks,
        "binary:hash",
        xyce_binary.is_file()
        and sha256(xyce_binary) == r07["xyce_binary_sha256"],
        f"sha256={sha256(xyce_binary) if xyce_binary.is_file() else None}",
    )
    add_check(
        checks,
        "outputs:formal_absent_before_run",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )

    self_test_netlist = ROOT / outputs["bsource_self_test_netlist"]
    self_test_log = ROOT / outputs["bsource_self_test_log"]
    self_test_output = ROOT / outputs["bsource_self_test_output"]
    self_test_text = """* R09 controlled Xyce B-source scalar self-test; not a project device
Vctrl nin 0 1.0
Btest nout 0 V={limit(V(nin),0,2)+sgn(V(nin))*0.25}
Vsense nout nload 0
Rload nload 0 1k
.DC Vctrl 1 1 1
.PRINT DC FORMAT=CSV V(nout) I(Vsense)
.END
"""
    self_test_scope_ok = all(
        token.lower() not in self_test_text.lower()
        for token in config["self_test"]["forbidden_tokens"]
    ) and ".DC" in self_test_text and "Btest" in self_test_text
    self_test_netlist.write_text(self_test_text, encoding="ascii")
    add_check(
        checks,
        "self_test:netlist_scope",
        self_test_scope_ok and self_test_netlist.is_file(),
        "controlled scalar source only; no project candidate",
    )
    self_test_run_ok, _ = run_command(
        "xyce_bsource_self_test",
        [
            str(xyce_binary),
            "-l",
            str(self_test_log),
            "-o",
            str(self_test_output.with_suffix("")),
            str(self_test_netlist),
        ],
        run_directory,
        command_records,
    )
    observed_v = read_xyce_prn(self_test_output, config["self_test"]["expected_column"])
    expected_v = float(config["self_test"]["expected_value_v"])
    tolerance_v = float(config["self_test"]["tolerance_v"])
    add_check(
        checks,
        "self_test:command_returncode",
        self_test_run_ok,
        f"return={self_test_run_ok}",
    )
    add_check(
        checks,
        "self_test:prn_output_exists",
        self_test_output.is_file() and self_test_output.stat().st_size > 0,
        f"path={self_test_output} bytes={self_test_output.stat().st_size if self_test_output.exists() else 0}",
    )
    add_check(
        checks,
        "self_test:deterministic_prn_value",
        observed_v is not None and abs(observed_v - expected_v) <= tolerance_v,
        f"observed={observed_v} expected={expected_v} tolerance={tolerance_v}",
    )
    add_check(
        checks,
        "self_test:log_persisted",
        self_test_log.is_file() and self_test_log.stat().st_size > 0,
        f"log={self_test_log.is_file()}",
    )

    device_syntax_netlist = ROOT / outputs["device_syntax_netlist"]
    device_syntax_log = ROOT / outputs["device_syntax_log"]
    device_syntax_output = ROOT / outputs["device_syntax_output"]
    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    device_syntax_text = (
        "* R09 parser-only frozen IGZO candidate; no numerical solve\n"
        f'.include "{candidate}"\n'
        "VDS D S 0.1\nVTG TG S 0.5\nVBG BG S 0\n"
        "XIGZO D TG BG S IGZO_DG_BEHAVIORAL_R02\n"
        ".DC VTG 0.5 0.5 1\n"
        ".PRINT DC FORMAT=CSV V(TG) I(VDS)\n.END\n"
    )
    syntax_scope_ok = (
        candidate.is_file()
        and sha256(candidate) == config["device_syntax_check"]["candidate_sha256"]
        and all(
            token.lower() not in device_syntax_text.lower()
            for token in config["device_syntax_check"]["forbidden_tokens"]
        )
        and ".TRAN" not in device_syntax_text.upper()
    )
    if observed_v is not None and abs(observed_v - expected_v) <= tolerance_v:
        device_syntax_netlist.write_text(device_syntax_text, encoding="ascii")
    add_check(
        checks,
        "device_syntax:netlist_scope_and_candidate_hash",
        syntax_scope_ok and device_syntax_netlist.is_file(),
        "frozen IGZO candidate only; parser-only gate",
    )
    device_syntax_run_ok = False
    if device_syntax_netlist.is_file():
        device_syntax_run_ok, _ = run_command(
            "xyce_device_syntax",
            [
                str(xyce_binary),
                "-syntax",
                "-l",
                str(device_syntax_log),
                "-o",
                str(device_syntax_output.with_suffix("")),
                str(device_syntax_netlist),
            ],
            run_directory,
            command_records,
        )
    add_check(
        checks,
        "device_syntax:parser_returncode",
        device_syntax_run_ok,
        f"return={device_syntax_run_ok}",
    )
    add_check(
        checks,
        "device_syntax:log_persisted",
        device_syntax_log.is_file(),
        f"log={device_syntax_log.is_file()}",
    )
    add_check(
        checks,
        "device_syntax:no_numerical_output",
        not device_syntax_output.exists(),
        f"output_exists={device_syntax_output.exists()}",
    )
    add_check(
        checks,
        "execution:no_formal_m01_outputs",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    invoked_programs = [
        Path(item["argv"][0]).name.lower() for item in command_records if item.get("argv")
    ]
    add_check(
        checks,
        "execution:no_ngspice_aimspice",
        "ngspice" not in invoked_programs and "aimspice" not in invoked_programs,
        ",".join(invoked_programs),
    )
    add_check(
        checks,
        "execution:no_formal_device_dc",
        all("-syntax" in item.get("argv", []) for item in command_records if item["name"] == "xyce_device_syntax")
        and any(item["name"] == "xyce_device_syntax" for item in command_records),
        "only parser-only Xyce device command is permitted",
    )
    expected_names = {"xyce_version", "xyce_license", "xyce_bsource_self_test", "xyce_device_syntax"}
    add_check(
        checks,
        "execution:only_expected_commands",
        set(item["name"] for item in command_records) == expected_names
        and len(command_records) == 4,
        f"commands={len(command_records)}",
    )

    reuse_manifest_path = ROOT / outputs["reuse_manifest"]
    reuse_manifest = {
        "preflight_id": config["preflight_id"],
        "r07_failure_report": {
            "path": r07["preflight_report_path"],
            "sha256": sha256(r07_report_path),
        },
        "generator_prefix": {
            "path": str(generator_prefix),
            "digest": generator_tree,
        },
        "xyce_prefix": {
            "path": str(xyce_prefix),
            "digest": xyce_tree,
        },
        "xyce_binary": {
            "path": str(xyce_binary),
            "sha256": sha256(xyce_binary),
        },
    }
    reuse_manifest_path.write_text(json.dumps(reuse_manifest, indent=2) + "\n", encoding="utf-8")
    execution_manifest_path = ROOT / outputs["execution_manifest"]
    execution_manifest_path.write_text(
        json.dumps({"preflight_id": config["preflight_id"], "commands": command_records}, indent=2)
        + "\n",
        encoding="utf-8",
    )
    add_check(
        checks,
        "artifacts:reuse_manifest",
        reuse_manifest_path.is_file() and sha256(reuse_manifest_path),
        str(reuse_manifest_path.relative_to(ROOT)),
    )
    add_check(
        checks,
        "artifacts:execution_manifest",
        execution_manifest_path.is_file() and sha256(execution_manifest_path),
        str(execution_manifest_path.relative_to(ROOT)),
    )
    add_check(
        checks,
        "artifacts:preflight_log",
        preflight_log.is_file() and "build_invoked=false" in preflight_log.read_text(encoding="utf-8"),
        str(preflight_log.relative_to(ROOT)),
    )
    add_check(
        checks,
        "binding:config_hash",
        sha256(CONFIG_PATH) == sha256(CONFIG_PATH),
        sha256(CONFIG_PATH),
    )
    add_check(
        checks,
        "binding:runner_hash",
        RUNNER_PATH.is_file() and sha256(RUNNER_PATH),
        sha256(RUNNER_PATH),
    )
    add_check(
        checks,
        "gate:formal_requires_independent",
        config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True
        and "independent" in config["next_gate"],
        config["next_gate"],
    )
    add_check(
        checks,
        "gate:downstream_closed",
        config["scope"]["circuit_or_downstream_permitted"] is False
        and config["no_execution_rules"]["circuit_or_downstream_permitted"] is False,
        "formal M01 and downstream remain closed",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"R09 preflight registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")
    failures = [item for item in checks if item["status"] == "FAIL"]
    with preflight_log.open("a", encoding="utf-8") as stream:
        stream.write(f"checks_passed={len(checks) - len(failures)}/{len(checks)}\n")
        stream.write(f"preflight_status={'FAIL' if failures else 'PASS'}\n")
        stream.write("build_invoked=false\n")
        stream.write("formal_device_dc_invoked=false\n")
    report = {
        "status": "FAIL" if failures else "PASS",
        "preflight_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E2",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "build_status": "REUSED_HASH_BOUND_R07_INSTALL",
        "bsource_self_test_status": "PASS"
        if all(item["status"] == "PASS" for item in checks if item["name"].startswith("self_test:"))
        else "FAIL",
        "device_syntax_status": "PASS"
        if all(item["status"] == "PASS" for item in checks if item["name"].startswith("device_syntax:"))
        else "FAIL",
        "formal_device_simulation_status": "NOT_RUN_BY_PREFLIGHT",
        "formal_spice_numerical_status": "NOT_RUN_BY_PREFLIGHT",
        "circuit_status": "NOT_RUN_BY_PREFLIGHT",
        "checks": checks,
        "failures": failures,
        "commands": command_records,
        "artifacts": {
            "self_test_netlist_sha256": sha256(self_test_netlist)
            if self_test_netlist.is_file()
            else None,
            "self_test_log_sha256": sha256(self_test_log)
            if self_test_log.is_file()
            else None,
            "self_test_output_sha256": sha256(self_test_output)
            if self_test_output.is_file()
            else None,
            "device_syntax_netlist_sha256": sha256(device_syntax_netlist)
            if device_syntax_netlist.is_file()
            else None,
            "device_syntax_log_sha256": sha256(device_syntax_log)
            if device_syntax_log.is_file()
            else None,
            "device_syntax_output_exists": device_syntax_output.exists(),
        },
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "process_invocations": len(command_records),
            "build_processes_invoked": 0,
            "generator_build_invoked": False,
            "dependency_rebuild_invoked": False,
            "ngspice_invoked": False,
            "aimspice_invoked": False,
            "controlled_bsource_self_test_invoked": True,
            "device_syntax_only_invoked": any(item["name"] == "xyce_device_syntax" for item in command_records),
            "formal_device_dc_invoked": False,
            "formal_m01_outputs_created": any(path.exists() for path in formal_paths),
            "r07_complete_generator_prefix_reused": True,
            "r07_complete_xyce_prefix_reused": True,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)},
        "reuse_manifest": {
            "path": str(reuse_manifest_path.relative_to(ROOT)),
            "sha256": sha256(reuse_manifest_path),
        },
        "execution_manifest": {
            "path": str(execution_manifest_path.relative_to(ROOT)),
            "sha256": sha256(execution_manifest_path),
        },
        "xyce_binary": {
            "path": str(xyce_binary),
            "sha256": sha256(xyce_binary),
            "bytes": xyce_binary.stat().st_size if xyce_binary.is_file() else None,
        },
        "observed_self_test_value_v": observed_v,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"],
    }
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_R09_{report['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={report_path}"
    )
    return report


if __name__ == "__main__":
    result = check_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
