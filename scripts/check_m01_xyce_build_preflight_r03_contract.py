#!/usr/bin/env python3
"""Check the revision-3 Xyce build/preflight contract without invoking a simulator."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r03.json"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r03.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r03.py"
CHECKER_PATH = ROOT / "scripts" / "check_m01_xyce_build_preflight_r03.py"
EXPECTED_CHECK_COUNT = 25


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract() -> dict[str, Any]:
    if REPORT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite existing contract report: {REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    m01 = next(item for item in experiments["experiments"] if item["id"] == "M01")
    r03 = m01["xyce_build_preflight_r03"]
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:revision_3_xyce_build_preflight",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R03"
        and config.get("revision") == 3
        and config.get("status") == "preflight_planned"
        and config.get("evidence_level_before_run") == "E0",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    bound = config["bound_contract"]
    bound_config = ROOT / bound["path"]
    bound_report = ROOT / bound["report_path"]
    bound_json = load_json(bound_config) if bound_config.is_file() else {}
    bound_report_json = load_json(bound_report) if bound_report.is_file() else {}
    add_check(
        checks,
        "binding:recovery_contract_e3_unchanged",
        bound_config.is_file()
        and bound_report.is_file()
        and sha256(bound_config) == bound["sha256"]
        and sha256(bound_report) == bound["report_sha256"]
        and bound["bound_commit"] == "23b983c523e97c50f3b1fbd243f0481c6370cc30"
        and bound_json.get("contract_id") == "M01_OPEN_SOURCE_RECOVERY_R01"
        and bound_report_json.get("status") == "PASS"
        and bound_report_json.get("evidence_level") == "E3"
        and bound_report_json.get("summary", {}).get("passed") == 30,
        "recovery contract and its E3 report are hash-bound",
    )
    r01 = config["r01_failure_binding"]
    r01_report = ROOT / r01["preflight_report"]
    r01_check = ROOT / r01["independent_check_report"]
    r01_report_json = load_json(r01_report) if r01_report.is_file() else {}
    r01_check_json = load_json(r01_check) if r01_check.is_file() else {}
    add_check(
        checks,
        "binding:r01_failed_gate_preserved",
        r01["must_remain_unchanged"] is True
        and r01_report.is_file()
        and r01_check.is_file()
        and sha256(r01_report) == r01["preflight_report_sha256"]
        and sha256(r01_check) == r01["independent_check_report_sha256"]
        and r01_report_json.get("status") == "FAIL"
        and r01_report_json.get("evidence_level") == "E0"
        and r01_report_json.get("summary", {}).get("passed") == 14
        and r01_check_json.get("status") == "FAIL"
        and r01_check_json.get("evidence_level") == "E0"
        and r01_check_json.get("summary", {}).get("passed") == 9,
        "R01 14/29 and 9/20 failure evidence is immutable",
    )
    r02_failure = config["r02_contract_failure_binding"]
    r02_contract_report = ROOT / r02_failure["contract_report"]
    r02_contract_json = load_json(r02_contract_report) if r02_contract_report.is_file() else {}
    add_check(
        checks,
        "binding:r02_contract_failure_preserved",
        r02_failure["must_remain_unchanged"] is True
        and r02_contract_report.is_file()
        and sha256(r02_contract_report) == r02_failure["contract_report_sha256"]
        and r02_contract_json.get("status") == "FAIL"
        and r02_contract_json.get("evidence_level") == "E0"
        and r02_contract_json.get("summary", {}).get("passed") == 22
        and r02_failure["contract_checks_passed"] == 22
        and r02_failure["contract_checks_failed"] == 3,
        "R02 22/25 contract failure is immutable",
    )
    scope = config["scope"]
    add_check(
        checks,
        "scope:serial_laptop_igzo_only",
        scope["active_material_scope"] == "IGZO only"
        and scope["laptop_target"] is True
        and scope["serial_build"] is True
        and scope["mpi_build"] is False
        and scope["fortran_build"] is False
        and scope["device_netlist_execution"] is False
        and scope["formal_m01_numerical_run"] is False
        and scope["circuit_or_downstream_permitted"] is False,
        json.dumps(scope, sort_keys=True),
    )
    sources = config["source_provenance"]
    source_key_files = {"xyce": "INSTALL.md", "trilinos": "CMakeLists.txt", "suitesparse": "CMakeLists.txt"}
    source_ok = []
    for key, key_file in source_key_files.items():
        item = sources[key]
        archive = Path(item["archive_path"])
        source_dir = Path(item["source_dir"])
        source_ok.append(
            archive.is_file()
            and sha256(archive) == item["archive_sha256"]
            and (source_dir / key_file).is_file()
        )
    cmake = sources["cmake"]
    cmake_archive = Path(cmake["archive_path"])
    add_check(
        checks,
        "sources:archives_and_sources_rehashed",
        all(source_ok)
        and cmake_archive.is_file()
        and sha256(cmake_archive) == cmake["archive_sha256"]
        and Path(cmake["binary_path"]).is_file(),
        f"source_trees={sum(source_ok)}/3 cmake={cmake_archive.is_file()}",
    )
    add_check(
        checks,
        "sources:license_versions_policy",
        sources["xyce"]["license"] == "GPL-3.0-or-later"
        and sources["xyce"]["proprietary_binary_accepted"] is False
        and sources["xyce"]["release_tag"] == "Release-7.10.0"
        and sources["trilinos"]["minimum_version"] == "14.4"
        and sources["suitesparse"]["minimum_version"] == "7.8.3"
        and sources["cmake"]["release"] == "3.30.5",
        "GPL source and pinned releases only",
    )
    historical = config["historical_hash_boundary"]
    add_check(
        checks,
        "sources:historical_hash_correction_is_explicit",
        historical["historical_contract_and_report_must_remain_unchanged"] is True
        and historical["historical_recorded_xyce_archive_sha256"]
        != historical["actual_rehashed_xyce_archive_sha256"]
        and sources["xyce"]["archive_sha256"] == historical["actual_rehashed_xyce_archive_sha256"],
        "old transcription retained; independent archive hash is the R03 input",
    )
    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    candidate_text = candidate.read_text(encoding="ascii") if candidate.is_file() else ""
    add_check(
        checks,
        "candidate:frozen_igzo_scope_and_hash",
        candidate.is_file()
        and sha256(candidate) == config["device_syntax_check"]["candidate_sha256"]
        and ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text
        and re.search(r"\b(?:sno|hzo|ferroelectric|tran|noise|circuit)\b", candidate_text, re.IGNORECASE) is None,
        f"exists={candidate.is_file()} bytes={len(candidate_text)}",
    )
    tools = config["toolchain"]
    tool_paths = [Path(tools[key]) for key in ("cmake", "c_compiler", "cxx_compiler", "make", "bison", "flex")]
    add_check(
        checks,
        "toolchain:pinned_local_tools",
        all(path.is_file() for path in tool_paths)
        and tools["max_parallel_jobs"] == 2
        and tools["forbidden_required_commands"] == ["mpirun", "mpicxx", "gfortran"],
        "C/C++/CMake/parser tools are explicit and serial",
    )
    blas = Path(tools["blas_library_dir"]) / "libblas.so"
    lapack = Path(tools["lapack_library_dir"]) / "liblapack.so"
    add_check(
        checks,
        "toolchain:explicit_blas_lapack_paths",
        blas.is_file()
        and lapack.is_file()
        and f"-DBLAS_LIBRARIES={blas}" in config["build_plan"]["suitesparse_cmake_options"]
        and f"-DLAPACK_LIBRARIES={lapack}" in config["build_plan"]["suitesparse_cmake_options"],
        f"blas={blas} lapack={lapack}",
    )
    build_dirs = [Path(value) for value in config["build_directories"].values()]
    prefixes = [Path(sources[key]["install_prefix"]) for key in ("xyce", "trilinos", "suitesparse")]
    add_check(
        checks,
        "build:unique_external_r03_roots",
        len(build_dirs) == len(set(build_dirs))
        and len(prefixes) == len(set(prefixes))
        and all(str(path).startswith("/home/reachgao/.local/") for path in build_dirs + prefixes)
        and all(not path.exists() for path in build_dirs + prefixes),
        "R03 roots are unique, external and absent before execution",
    )
    add_check(
        checks,
        "build:serial_cmake_options",
        config["build_plan"]["overwrite_build_directories"] is False
        and config["build_plan"]["parallel_jobs"] == 2
        and "-DTrilinos_ENABLE_Fortran=OFF" in config["build_plan"]["trilinos_cmake_options"]
        and "-DTPL_ENABLE_MPI=OFF" in config["build_plan"]["trilinos_cmake_options"]
        and "-DXyce_ENABLE_TESTS=OFF" in config["build_plan"]["xyce_cmake_options"],
        "Fortran-off, MPI-off, two-job build remains frozen",
    )
    add_check(
        checks,
        "sequence:build_before_self_test_before_parser",
        config["preflight_sequence"][2:8]
        == [
            "configure_build_install_suitesparse_amd_only",
            "configure_build_install_serial_trilinos_fortran_off",
            "configure_build_install_serial_xyce",
            "fingerprint_xyce_binary_license_and_version",
            "run_controlled_bsource_expression_self_test",
            "run_xyce_syntax_only_on_generated_device_netlist_after_self_test",
        ],
        "build and fingerprints precede scalar self-test and parser-only syntax",
    )
    self_test = config["self_test"]
    add_check(
        checks,
        "self_test:scalar_only_contract",
        self_test["netlist_is_device_netlist"] is False
        and self_test["dc_analysis_required"] is True
        and self_test["expected_value_v"] == 1.25
        and self_test["tolerance_v"] == 1e-9
        and self_test["must_not_create_formal_m01_tables"] is True,
        "one controlled 1.25 V B-source self-test only",
    )
    add_check(
        checks,
        "no_execution:formal_routes_and_downstream_closed",
        config["no_execution_rules"]["runner_must_not_invoke_ngspice"] is True
        and config["no_execution_rules"]["runner_must_not_invoke_aimspice"] is True
        and config["no_execution_rules"]["runner_must_not_invoke_formal_device_dc"] is True
        and config["no_execution_rules"]["circuit_or_downstream_permitted"] is False,
        "no simulator route or downstream work is admitted by the contract",
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
        "outputs:exclusive_unique_r03_namespace",
        len(output_values) == len(set(output_values))
        and config["failure_retention"]["exclusive_outputs"] is True
        and config["failure_retention"]["overwrite_existing_outputs"] is False
        and all("r03" in value for key, value in config["outputs"].items() if key != "contract_report"),
        "R03 run artifacts are unique and append-only",
    )
    boundary = config["evidence_boundary"]
    add_check(
        checks,
        "boundary:no_physical_or_simulation_claim",
        all(phrase in boundary for phrase in ("not a device simulation result", "not an IGZO equation", "physical parameter", "experimental calibration", "M01 remains E0")),
        "R03 evidence remains tool-only",
    )
    add_check(
        checks,
        "project:next_scope_is_r03",
        project["tcad_track"]["next_scope"].startswith("establish and commit M01 Xyce build/tool preflight revision-3")
        and m01["status"] == "preflight_failed_tool_provenance",
        project["tcad_track"]["next_scope"],
    )
    add_check(
        checks,
        "experiment:r03_is_planned_and_r01_failed",
        r03["status"] == "preflight_planned"
        and r03["revision"] == 3
        and r03["current_evidence"] == "E0"
        and r03["formal_run_completed"] is False
        and r03["device_netlist_invoked"] is False
        and m01["xyce_build_preflight"]["status"] == "preflight_failed_build"
        and m01["xyce_build_preflight"]["preflight_run_ordinal"] == 1,
        "R03 is unexecuted while R01 failure remains machine-recorded",
    )
    runner_source = RUNNER_PATH.read_text(encoding="utf-8") if RUNNER_PATH.is_file() else ""
    checker_source = CHECKER_PATH.read_text(encoding="utf-8") if CHECKER_PATH.is_file() else ""
    makefile_source = (ROOT / "Makefile").read_text(encoding="utf-8")
    add_check(
        checks,
        "runner:r03_wrapper_and_no_formal_execution",
        "m01_xyce_build_preflight_r01.py" in runner_source
        and "suitesparse_cmake_options" in runner_source
        and "EXPECTED_CHECK_COUNT = 29" in runner_source
        and "formal_device_dc_invoked=false" in runner_source,
        "R03 wraps the reviewed runner and injects only registered BLAS/LAPACK options",
    )
    add_check(
        checks,
        "checker:r03_independent_standard_library",
        "m01_xyce_build_preflight_r01.py" in checker_source
        and "EXPECTED_CHECK_COUNT = 20" in checker_source
        and "import subprocess" not in checker_source,
        "R03 independent checker has no simulator subprocess path",
    )
    add_check(
        checks,
        "make:r03_targets_registered",
        "m01-xyce-build-preflight-r03-contract-check:" in makefile_source
        and "m01-xyce-build-preflight-r03:" in makefile_source
        and "m01-xyce-build-preflight-r03-check:" in makefile_source,
        "contract, runner and independent-check targets are registered",
    )
    add_check(
        checks,
        "gate:formal_m01_requires_r03_independent_pass",
        config["no_execution_rules"]["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True
        and "independent check" in config["next_gate"]
        and "R01" in config["evidence_boundary"],
        config["next_gate"],
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"R03 contract registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")
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
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {"path": str(Path(__file__).relative_to(ROOT)), "sha256": sha256(Path(__file__))},
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"],
    }
    with REPORT_PATH.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(f"M01_XYCE_BUILD_PREFLIGHT_R03_CONTRACT_{result['status']} checks={len(checks) - len(failures)}/{len(checks)} report={REPORT_PATH}")
    return result


if __name__ == "__main__":
    result = check_contract()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
