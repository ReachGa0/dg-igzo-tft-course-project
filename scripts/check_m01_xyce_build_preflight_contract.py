#!/usr/bin/env python3
"""Check the Xyce build/preflight contract without invoking any simulator."""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r01.json"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r01.json"
EXPECTED_CHECK_COUNT = 25


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
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:xyce_build_preflight_contract",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R01"
        and config.get("revision") == 1
        and config.get("status") == "preflight_planned"
        and config.get("evidence_level_before_run") == "E0",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    bound = config["bound_contract"]
    bound_config = ROOT / bound["path"]
    bound_report = ROOT / bound["report_path"]
    bound_config_ok = bound_config.is_file() and sha256(bound_config) == bound["sha256"]
    bound_report_ok = bound_report.is_file() and sha256(bound_report) == bound["report_sha256"]
    bound_json = load_json(bound_config) if bound_config.is_file() else {}
    bound_report_json = load_json(bound_report) if bound_report.is_file() else {}
    add_check(
        checks,
        "binding:recovery_contract_is_committed_e3",
        bound_config_ok
        and bound_report_ok
        and bound["bound_commit"] == "23b983c523e97c50f3b1fbd243f0481c6370cc30"
        and bound_json.get("contract_id") == "M01_OPEN_SOURCE_RECOVERY_R01"
        and bound_report_json.get("status") == "PASS"
        and bound_report_json.get("evidence_level") == "E3"
        and bound_report_json.get("summary", {}).get("passed") == 30,
        f"config_hash={bound_config_ok} report_hash={bound_report_ok}",
    )
    add_check(
        checks,
        "scope:serial_laptop_igzo_only",
        config["scope"]["active_material_scope"] == "IGZO only"
        and config["scope"]["laptop_target"] is True
        and config["scope"]["serial_build"] is True
        and config["scope"]["mpi_build"] is False
        and config["scope"]["fortran_build"] is False
        and config["scope"]["formal_m01_numerical_run"] is False
        and config["scope"]["circuit_or_downstream_permitted"] is False,
        json.dumps(config["scope"], sort_keys=True),
    )

    sources = config["source_provenance"]
    source_checks = []
    source_key_files = {
        "xyce": "INSTALL.md",
        "trilinos": "CMakeLists.txt",
        "suitesparse": "CMakeLists.txt",
    }
    for key, expected_file in source_key_files.items():
        item = sources[key]
        archive = Path(item["archive_path"])
        source_dir = Path(item["source_dir"])
        source_checks.append(
            archive.is_file()
            and sha256(archive) == item["archive_sha256"]
            and (source_dir / expected_file).is_file()
        )
    add_check(
        checks,
        "sources:official_archives_and_extracted_sources",
        all(source_checks),
        "xyce/trilinos/suitesparse=" + "/".join("PASS" if value else "FAIL" for value in source_checks),
    )
    cmake_source = sources["cmake"]
    cmake_archive = Path(cmake_source["archive_path"])
    cmake_binary = Path(cmake_source["binary_path"])
    add_check(
        checks,
        "sources:cmake_archive_and_binary",
        cmake_archive.is_file()
        and sha256(cmake_archive) == cmake_source["archive_sha256"]
        and cmake_binary.is_file(),
        f"archive={cmake_archive.is_file()} binary={cmake_binary.is_file()}",
    )
    add_check(
        checks,
        "sources:license_and_proprietary_policy",
        sources["xyce"]["license"] == "GPL-3.0-or-later"
        and sources["xyce"]["proprietary_binary_accepted"] is False
        and "proprietary" in config["evidence_boundary"].lower()
        and "AIM-Spice Level 15" in config["evidence_boundary"],
        "pure GPL source required; proprietary XyceNF and AIM-Spice are excluded",
    )
    add_check(
        checks,
        "sources:versions_meet_official_minimums",
        sources["xyce"]["release_tag"] == "Release-7.10.0"
        and sources["trilinos"]["minimum_version"] == "14.4"
        and sources["suitesparse"]["minimum_version"] == "7.8.3"
        and sources["cmake"]["release"] == "3.30.5",
        "Xyce 7.10.0, Trilinos 14.4, SuiteSparse 7.8.3 and CMake 3.30.5",
    )
    historical_hash = config["historical_hash_boundary"]
    historical_recovery = load_json(ROOT / historical_hash["historical_contract_path"])
    add_check(
        checks,
        "sources:historical_hash_transcription_is_preserved_and_corrected",
        historical_recovery["xyce_source_provenance"]["source_archive_sha256"]
        == historical_hash["historical_recorded_xyce_archive_sha256"]
        and sources["xyce"]["archive_sha256"]
        == historical_hash["actual_rehashed_xyce_archive_sha256"]
        and historical_hash["historical_contract_and_report_must_remain_unchanged"] is True
        and historical_hash["historical_recorded_xyce_archive_sha256"]
        != historical_hash["actual_rehashed_xyce_archive_sha256"],
        "old static string is retained; the new build input uses the independently rehashed archive",
    )

    candidate_path = ROOT / config["device_syntax_check"]["candidate_path"]
    candidate_text = candidate_path.read_text(encoding="ascii") if candidate_path.is_file() else ""
    forbidden = re.compile(
        r"\b(?:sno|hzo|ferroelectric|tran|noise|ring|adder|nand|nor|xor|circuit)\b",
        re.IGNORECASE,
    )
    add_check(
        checks,
        "candidate:frozen_igzo_hash_and_scope",
        candidate_path.is_file()
        and sha256(candidate_path) == config["device_syntax_check"]["candidate_sha256"]
        and ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text
        and "M01_EXECUTION_REQUIRED" in candidate_text
        and forbidden.search(candidate_text) is None,
        f"exists={candidate_path.is_file()} bytes={len(candidate_text)}",
    )
    add_check(
        checks,
        "candidate:device_parser_is_not_formal_run",
        config["device_syntax_check"]["enabled_after_self_test_only"] is True
        and config["device_syntax_check"]["netlist_is_formal_device_run"] is False
        and config["device_syntax_check"]["numerical_solution_must_not_be_requested"] is True
        and config["no_execution_rules"]["runner_must_not_invoke_formal_device_dc"] is True,
        "parser-only device syntax check follows scalar self-test",
    )

    tools = config["toolchain"]
    tool_paths = [Path(tools[key]) for key in ("cmake", "c_compiler", "cxx_compiler", "make", "bison", "flex")]
    add_check(
        checks,
        "toolchain:required_local_tools_are_pinned",
        all(path.is_file() for path in tool_paths)
        and tools["max_parallel_jobs"] == 2
        and tools["forbidden_required_commands"] == ["mpirun", "mpicxx", "gfortran"],
        "cmake/compiler/build/parser paths are explicit; MPI and Fortran are not required",
    )
    add_check(
        checks,
        "toolchain:serial_cmake_plan",
        config["build_plan"]["overwrite_build_directories"] is False
        and config["build_plan"]["configure_and_build_in_runner"] is True
        and config["build_plan"]["parallel_jobs"] == 2
        and "-DTrilinos_ENABLE_Fortran=OFF" in config["build_plan"]["trilinos_cmake_options"]
        and "-DTPL_ENABLE_MPI=OFF" in config["build_plan"]["trilinos_cmake_options"]
        and "-DXyce_ENABLE_TESTS=OFF" in config["build_plan"]["xyce_cmake_options"],
        "serial, Fortran-off, MPI-off, two-job build is frozen",
    )
    add_check(
        checks,
        "toolchain:official_xyce_trilinos_cache",
        Path(config["build_plan"]["trilinos_initial_cache"]).is_file()
        and "Trilinos_ENABLE_NOX" in Path(config["build_plan"]["trilinos_initial_cache"]).read_text(encoding="utf-8"),
        "Xyce-provided Trilinos cache is present",
    )
    build_dirs = [Path(value) for value in config["build_directories"].values()]
    install_prefixes = [
        Path(sources[key]["install_prefix"])
        for key in ("xyce", "trilinos", "suitesparse")
    ]
    add_check(
        checks,
        "build:external_unique_user_prefixes",
        len(build_dirs) == len(set(build_dirs))
        and len(install_prefixes) == len(set(install_prefixes))
        and all(str(path).startswith("/home/reachgao/.local/") for path in build_dirs + install_prefixes)
        and all(not str(path).startswith(str(ROOT)) for path in build_dirs + install_prefixes),
        "build and install roots are unique, user-owned and outside the repository",
    )
    add_check(
        checks,
        "sequence:source_build_before_self_test",
        config["preflight_sequence"][:6]
        == [
            "verify_archive_and_source_hashes",
            "verify_toolchain_versions_and_no_proprietary_binary",
            "configure_build_install_suitesparse_amd_only",
            "configure_build_install_serial_trilinos_fortran_off",
            "configure_build_install_serial_xyce",
            "fingerprint_xyce_binary_license_and_version",
        ]
        and config["preflight_sequence"][6]
        == "run_controlled_bsource_expression_self_test"
        and config["preflight_sequence"][7]
        == "run_xyce_syntax_only_on_generated_device_netlist_after_self_test",
        "build and binary fingerprint precede scalar self-test; parser check is last",
    )
    add_check(
        checks,
        "self_test:scalar_only_and_deterministic",
        config["self_test"]["netlist_is_device_netlist"] is False
        and config["self_test"]["dc_analysis_required"] is True
        and config["self_test"]["expected_value_v"] == 1.25
        and config["self_test"]["tolerance_v"] == 1e-9
        and "IGZO" in config["self_test"]["forbidden_tokens"]
        and config["self_test"]["must_not_create_formal_m01_tables"] is True,
        "one controlled B-source scalar check only",
    )
    add_check(
        checks,
        "no_execution:formal_routes_and_downstream_closed",
        config["no_execution_rules"]["runner_must_not_invoke_ngspice"] is True
        and config["no_execution_rules"]["runner_must_not_invoke_aimspice"] is True
        and config["no_execution_rules"]["controlled_bsource_self_test_is_not_formal_m01"] is True
        and config["no_execution_rules"]["circuit_or_downstream_permitted"] is False
        and all(
            experiment_map[item].get("status") in {"planned", "optional"}
            for item in ("C00", "C01", "C02", "C03", "L00", "V00", "V01", "PEX0", "FE0")
        ),
        "no ngspice/AIM-Spice/device route or downstream work is admitted",
    )
    formal_paths = [ROOT / value for value in config["formal_outputs_that_must_remain_absent"]]
    add_check(
        checks,
        "outputs:formal_outputs_absent",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    output_values = list(config["outputs"].values())
    add_check(
        checks,
        "outputs:exclusive_and_unique",
        len(output_values) == len(set(output_values))
        and config["failure_retention"]["exclusive_outputs"] is True
        and config["failure_retention"]["overwrite_existing_outputs"] is False
        and config["build_plan"]["overwrite_build_directories"] is False,
        "all runner artifacts are append-only and build directories are not cleaned",
    )
    add_check(
        checks,
        "outputs:historical_failure_retention",
        all((ROOT / path).is_file() for path in config["historical_paths_to_preserve"])
        and config["failure_retention"]["retain_build_logs"] is True
        and config["failure_retention"]["retain_failed_self_test_logs"] is True,
        "historical M01 failures and future failed logs are retained",
    )
    add_check(
        checks,
        "boundary:no_physical_or_experimental_claim",
        all(
            phrase in config["evidence_boundary"]
            for phrase in (
                "not a device simulation result",
                "not an IGZO equation",
                "physical parameter",
                "experimental calibration",
                "circuit result",
                "M01 remains E0",
            )
        ),
        "preflight evidence is explicitly tool-only",
    )
    add_check(
        checks,
        "project:next_scope_matches_preflight",
        project.get("tcad_track", {}).get("next_scope", "").startswith(
            "implement and commit the pure-source Xyce build/tool preflight"
        )
        and experiment_map["M01"].get("status") == "preflight_failed_tool_provenance",
        project.get("tcad_track", {}).get("next_scope", ""),
    )
    add_check(
        checks,
        "experiment:preflight_is_planned_before_execution",
        experiment_map["M01"].get("xyce_build_preflight", {}).get("status") == "preflight_planned"
        and experiment_map["M01"].get("xyce_build_preflight", {}).get("formal_run_completed") is False
        and experiment_map["M01"].get("xyce_build_preflight", {}).get("device_netlist_invoked") is False
        and experiment_map["M01"].get("xyce_build_preflight", {}).get("numerical_outputs_created") is False,
        "machine state records an unexecuted preflight chain",
    )
    add_check(
        checks,
        "runner:contract_is_no_subprocess_checker",
        source_imports(Path(__file__)).isdisjoint({"subprocess", "os"}),
        "contract checker has no process invocation path",
    )
    add_check(
        checks,
        "next_gate:formal_two_route_run_only_after_independent_check",
        config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True
        and "independent check" in config["next_gate"],
        config["next_gate"],
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"Contract check registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "contract_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E3",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "spice_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "circuit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "simulator_processes_invoked": 0,
            "device_netlist_created": False,
            "numerical_outputs_created": False,
        },
        "config": {
            "path": str(CONFIG_PATH.relative_to(ROOT)),
            "sha256": sha256(CONFIG_PATH),
        },
        "checker": {
            "path": str(Path(__file__).relative_to(ROOT)),
            "sha256": sha256(Path(__file__)),
        },
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"],
    }
    return result


def main() -> int:
    result = check_contract()
    if "--dry-run" not in sys.argv:
        if REPORT_PATH.exists():
            raise RuntimeError(f"Refusing to overwrite existing contract report: {REPORT_PATH}")
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        with REPORT_PATH.open("x", encoding="utf-8") as stream:
            json.dump(result, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_CONTRACT_{result['status']} "
        f"checks={result['summary']['passed']}/{result['summary']['check_count']} "
        f"report={REPORT_PATH}"
    )
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
