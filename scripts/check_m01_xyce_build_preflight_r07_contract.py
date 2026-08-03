#!/usr/bin/env python3
"""Check the R07 Xyce recovery contract without build or simulator execution."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from m01_xyce_r07_common import digest_tree, load_json, sha256


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r07.json"
REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r07.json"
RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r07.py"
CHECKER_PATH = ROOT / "scripts" / "check_m01_xyce_build_preflight_r07.py"
COMMON_PATH = ROOT / "scripts" / "m01_xyce_r07_common.py"
EXPECTED_CHECK_COUNT = 39


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract() -> dict[str, Any]:
    if REPORT_PATH.exists():
        raise RuntimeError(f"Refusing to overwrite existing R07 contract report: {REPORT_PATH}")
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    m01 = next(item for item in experiments["experiments"] if item["id"] == "M01")
    machine = m01["xyce_build_preflight_r07"]
    checks: list[dict[str, str]] = []

    add_check(
        checks,
        "identity:revision_7_xyce_build_preflight",
        config.get("stage_id") == "M01"
        and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R07"
        and config.get("revision") == 7
        and config.get("status") == "preflight_planned"
        and config.get("evidence_level_before_run") == "E0",
        f"stage={config.get('stage_id')} revision={config.get('revision')}",
    )
    bound = config["bound_contract"]
    bound_config = ROOT / bound["path"]
    bound_report = ROOT / bound["report_path"]
    bound_report_json = load_json(bound_report) if bound_report.is_file() else {}
    add_check(
        checks,
        "binding:recovery_contract_e3_unchanged",
        bound_config.is_file()
        and bound_report.is_file()
        and sha256(bound_config) == bound["sha256"]
        and sha256(bound_report) == bound["report_sha256"]
        and bound["bound_commit"] == "23b983c523e97c50f3b1fbd243f0481c6370cc30"
        and bound_report_json.get("status") == "PASS"
        and bound_report_json.get("evidence_level") == "E3"
        and bound_report_json.get("summary", {}).get("passed") == 30,
        "open-source recovery contract and E3 report are hash-bound",
    )

    r05 = config["r05_failure_binding"]
    r05_bindings = [
        (r05["config_path"], r05["config_sha256"]),
        (r05["contract_report_path"], r05["contract_report_sha256"]),
        (r05["preflight_report_path"], r05["preflight_report_sha256"]),
        (r05["source_manifest_path"], r05["source_manifest_sha256"]),
        (r05["build_manifest_path"], r05["build_manifest_sha256"]),
        (r05["preflight_log_path"], r05["preflight_log_sha256"]),
        (r05["trilinos_build_log_path"], r05["trilinos_build_log_sha256"]),
        (r05["xyce_build_log_path"], r05["xyce_build_log_sha256"]),
    ]
    add_check(
        checks,
        "binding:r05_artifacts_hash_bound",
        r05["must_remain_unchanged"] is True
        and r05["bound_commit"] == "6779aab89e8e05aaea2645c50eed66cb5c6910bb"
        and all(
            (ROOT / relative).is_file() and sha256(ROOT / relative) == expected
            for relative, expected in r05_bindings
        ),
        f"artifacts={sum((ROOT / item[0]).is_file() for item in r05_bindings)}/{len(r05_bindings)}",
    )
    r05_contract = load_json(ROOT / r05["contract_report_path"])
    r05_report = load_json(ROOT / r05["preflight_report_path"])
    add_check(
        checks,
        "binding:r05_contract_and_runner_states",
        r05_contract.get("status") == "PASS"
        and r05_contract.get("evidence_level") == "E3"
        and r05_contract.get("summary", {}).get("passed") == 27
        and r05_report.get("status") == "FAIL"
        and r05_report.get("evidence_level") == "E0"
        and r05_report.get("summary", {}).get("passed") == r05["runner_checks_passed"] == 19
        and r05_report.get("summary", {}).get("failed") == r05["runner_checks_failed"] == 10
        and r05_report.get("summary", {}).get("controlled_bsource_self_test_invoked") is False
        and r05_report.get("summary", {}).get("device_syntax_only_invoked") is False
        and r05["independent_check_run"] is False
        and not (ROOT / "results/reports/m01_xyce_build_preflight_check_r05.json").exists(),
        "R05 contract passed, runner failed 19/29 and independent check did not run",
    )
    r05_xyce_log = (ROOT / r05["xyce_build_log_path"]).read_text(
        encoding="utf-8", errors="replace"
    )
    add_check(
        checks,
        "binding:r05_generator_failure_root_cause",
        "cannot open: No such file or directory" in r05_xyce_log
        and "exec of /usr/bin/m4 failed" in r05_xyce_log
        and r05_report.get("summary", {}).get("ngspice_invoked") is False
        and r05_report.get("summary", {}).get("aimspice_invoked") is False
        and r05_report.get("summary", {}).get("formal_device_dc_invoked") is False,
        "R05 failed at missing M4/Bison data before Xyce compilation",
    )
    r06 = config["r06_contract_failure_binding"]
    r06_bindings = [
        (r06["config_path"], r06["config_sha256"]),
        (r06["contract_checker_path"], r06["contract_checker_sha256"]),
        (r06["contract_report_path"], r06["contract_report_sha256"]),
        (
            r06["implementation_project_check_failure_path"],
            r06["implementation_project_check_failure_sha256"],
        ),
        (
            r06["failure_state_project_check_failure_path"],
            r06["failure_state_project_check_failure_sha256"],
        ),
    ]
    add_check(
        checks,
        "binding:r06_failure_artifacts_hash_bound",
        r06["must_remain_unchanged"] is True
        and r06["bound_commit"] == "2cbcbf2b253016e7b1ebee68eab683e82918eea7"
        and all(
            (ROOT / relative).is_file() and sha256(ROOT / relative) == expected
            for relative, expected in r06_bindings
        ),
        f"artifacts={sum((ROOT / item[0]).is_file() for item in r06_bindings)}/{len(r06_bindings)}",
    )
    r06_report = load_json(ROOT / r06["contract_report_path"])
    r06_checker_source = (ROOT / r06["contract_checker_path"]).read_text(
        encoding="utf-8"
    )
    r06_independent_source = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r06.py"
    ).read_text(encoding="utf-8")
    add_check(
        checks,
        "binding:r06_checker_failure_state_and_root_cause",
        r06_report.get("status") == "FAIL"
        and r06_report.get("evidence_level") == "E0"
        and r06_report.get("summary", {}).get("passed")
        == r06["contract_checks_passed"]
        == 36
        and r06_report.get("summary", {}).get("failed")
        == r06["contract_checks_failed"]
        == 1
        and [item.get("name") for item in r06_report.get("failures", [])]
        == [r06["failed_check_name"]]
        and r06_report.get("summary", {}).get("build_processes_invoked")
        == r06["build_processes_invoked"]
        == 0
        and r06_report.get("summary", {}).get("simulator_processes_invoked")
        == r06["simulator_processes_invoked"]
        == 0
        and r06_report.get("summary", {}).get("device_netlist_created")
        is r06["device_netlist_created"]
        is False
        and r06_report.get("summary", {}).get("numerical_outputs_created")
        is r06["numerical_outputs_created"]
        is False
        and "run_m01_xyce_build_preflight_r06.py" in r06_independent_source
        and '"run_m01_xyce_build_preflight_r06" not in checker_source'
        in r06_checker_source,
        "R06 failed only because its checker prohibited the required runner-path literal",
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
    xyce_archive = Path(sources["xyce"]["archive_path"])
    xyce_source = Path(sources["xyce"]["source_dir"])
    cmake_archive = Path(sources["cmake"]["archive_path"])
    add_check(
        checks,
        "sources:xyce_and_cmake_rehashed",
        xyce_archive.is_file()
        and sha256(xyce_archive) == sources["xyce"]["archive_sha256"]
        and (xyce_source / sources["xyce"]["source_key_file"]).is_file()
        and cmake_archive.is_file()
        and sha256(cmake_archive) == sources["cmake"]["archive_sha256"]
        and Path(sources["cmake"]["binary_path"]).is_file(),
        "Xyce source and CMake binary archive remain pinned",
    )
    generator_archive_ok: list[bool] = []
    generator_source_ok: list[bool] = []
    for key in ("m4", "bison", "flex"):
        item = sources[key]
        archive = Path(item["archive_path"])
        source_dir = Path(item["source_dir"])
        generator_archive_ok.append(
            archive.is_file() and sha256(archive) == item["archive_sha256"]
        )
        generator_source_ok.append(
            (source_dir / "configure").is_file()
            and sha256(source_dir / "configure") == item["configure_sha256"]
            and (source_dir / item["license_file"]).is_file()
            and sha256(source_dir / item["license_file"]) == item["license_sha256"]
        )
    add_check(
        checks,
        "sources:generator_archives_rehashed",
        all(generator_archive_ok),
        f"archives={sum(generator_archive_ok)}/3",
    )
    add_check(
        checks,
        "sources:generator_trees_and_license_files",
        all(generator_source_ok),
        f"sources={sum(generator_source_ok)}/3",
    )
    add_check(
        checks,
        "sources:generator_versions_licenses_and_official_urls",
        sources["m4"]["release"] == "1.4.19"
        and sources["m4"]["archive_url"].startswith("https://ftp.gnu.org/gnu/m4/")
        and sources["m4"]["license"] == "GPL-3.0-or-later"
        and sources["bison"]["release"] == "3.8.2"
        and sources["bison"]["archive_url"].startswith("https://ftp.gnu.org/gnu/bison/")
        and sources["bison"]["license"].startswith("GPL-3.0-or-later")
        and sources["flex"]["release_tag"] == "v2.6.4"
        and sources["flex"]["archive_url"].startswith("https://github.com/westes/flex/")
        and sources["flex"]["license"] == "BSD-2-Clause",
        "GNU and westes release sources only",
    )
    candidate = ROOT / config["device_syntax_check"]["candidate_path"]
    candidate_text = candidate.read_text(encoding="ascii") if candidate.is_file() else ""
    add_check(
        checks,
        "candidate:frozen_igzo_scope_and_hash",
        candidate.is_file()
        and sha256(candidate) == config["device_syntax_check"]["candidate_sha256"]
        and ".subckt IGZO_DG_BEHAVIORAL_R02 D TG BG S" in candidate_text
        and re.search(
            r"\b(?:sno|hzo|ferroelectric|tran|noise|circuit)\b",
            candidate_text,
            re.IGNORECASE,
        )
        is None,
        f"exists={candidate.is_file()} bytes={len(candidate_text)}",
    )

    tools = config["toolchain"]
    bootstrap_paths = {
        "cmake": Path(tools["cmake"]),
        "gcc": Path(tools["c_compiler"]),
        "g++": Path(tools["cxx_compiler"]),
        "make": Path(tools["make"]),
        "blas": Path(tools["blas_library_dir"]) / "libblas.so",
        "lapack": Path(tools["lapack_library_dir"]) / "liblapack.so",
    }
    add_check(
        checks,
        "toolchain:bootstrap_paths_and_hashes",
        all(
            path.is_file() and sha256(path) == tools["bootstrap_sha256"][key]
            for key, path in bootstrap_paths.items()
        )
        and tools["max_parallel_jobs"] == 2
        and tools["forbidden_required_commands"] == ["mpirun", "mpicxx", "gfortran"],
        f"bootstrap={sum(path.is_file() for path in bootstrap_paths.values())}/{len(bootstrap_paths)}",
    )
    generator_prefix = Path(tools["generator_install_prefix"])
    planned_generator_paths = [
        Path(tools["m4"]),
        Path(tools["bison"]),
        Path(tools["bison_pkgdatadir"]),
        Path(tools["flex"]),
        Path(tools["flex_include_dir"]),
    ]
    add_check(
        checks,
        "toolchain:source_built_generator_paths_are_future",
        tools["source_built_commands"] == ["m4", "bison", "flex"]
        and not generator_prefix.exists()
        and all(not path.exists() for path in planned_generator_paths),
        "R07 generator prefix is absent before execution",
    )

    reuse = config["dependency_reuse"]
    reuse_actual: dict[str, dict[str, int | str]] = {}
    for key in ("suitesparse", "trilinos"):
        prefix = Path(reuse[key]["install_prefix"])
        reuse_actual[key] = digest_tree(prefix) if prefix.is_dir() else {}
    add_check(
        checks,
        "reuse:r05_dependency_tree_hashes",
        all(
            reuse_actual[key]
            and all(
                reuse_actual[key].get(field) == reuse[key].get(field)
                for field in reuse_actual[key]
            )
            for key in ("suitesparse", "trilinos")
        ),
        f"suitesparse={reuse_actual['suitesparse'].get('tree_sha256')} trilinos={reuse_actual['trilinos'].get('tree_sha256')}",
    )
    add_check(
        checks,
        "reuse:allowlist_and_partial_xyce_denylist",
        reuse["dependency_rebuild_permitted"] is False
        and reuse["allowed_reused_prefixes"]
        == [reuse["suitesparse"]["install_prefix"], reuse["trilinos"]["install_prefix"]]
        and "/home/reachgao/.local/build/xyce-7.10.0-r05"
        in reuse["forbidden_reused_paths"]
        and "/home/reachgao/.local/xyce-7.10-pure-r05"
        in reuse["forbidden_reused_paths"]
        and "/home/reachgao/.local/build/xyce-7.10.0-r06"
        in reuse["forbidden_reused_paths"]
        and "/home/reachgao/.local/xyce-7.10-pure-r06"
        in reuse["forbidden_reused_paths"]
        and reuse["suitesparse"]["install_prefix"].endswith("-r05")
        and reuse["trilinos"]["install_prefix"].endswith("-r05"),
        "only complete R05 SuiteSparse and Trilinos prefixes are reusable; R05/R06 Xyce roots are denied",
    )
    r05_build_manifest = load_json(ROOT / r05["build_manifest_path"])
    r05_command_map = {
        item.get("name"): item for item in r05_build_manifest.get("commands", [])
    }
    add_check(
        checks,
        "reuse:r05_install_command_audit",
        r05_command_map.get("suitesparse_build_install", {}).get("returncode") == 0
        and r05_command_map.get("trilinos_build_install", {}).get("returncode") == 0
        and r05_command_map.get("xyce_build_install", {}).get("returncode") == 2
        and r05_command_map.get("trilinos_build_install", {}).get("elapsed_seconds", 0)
        > 1000,
        "R05 dependency installs passed before the Xyce generator failure",
    )

    build_dirs = [Path(value) for value in config["build_directories"].values()]
    xyce_prefix = Path(sources["xyce"]["install_prefix"])
    new_roots = [*build_dirs, generator_prefix, xyce_prefix]
    add_check(
        checks,
        "build:unique_external_r07_roots_absent",
        len(new_roots) == len(set(new_roots))
        and all(str(path).startswith("/home/reachgao/.local/") for path in new_roots)
        and all("r07" in str(path) for path in new_roots)
        and all(not path.exists() for path in new_roots),
        "all R07 build and install roots are unique and absent",
    )
    add_check(
        checks,
        "build:r07_roots_are_isolated_from_r05_r06_xyce",
        str(xyce_prefix) != "/home/reachgao/.local/xyce-7.10-pure-r05"
        and str(Path(config["build_directories"]["xyce_build"]))
        != "/home/reachgao/.local/build/xyce-7.10.0-r05"
        and str(xyce_prefix) != "/home/reachgao/.local/xyce-7.10-pure-r06"
        and str(Path(config["build_directories"]["xyce_build"]))
        != "/home/reachgao/.local/build/xyce-7.10.0-r06"
        and all(str(path) not in reuse["forbidden_reused_paths"] for path in new_roots),
        "R05 partial and unused R06 Xyce roots are never reused",
    )
    plan = config["build_plan"]
    add_check(
        checks,
        "build:generator_order_and_environment",
        plan["generator_build_order"] == ["m4", "bison", "flex"]
        and plan["generator_configure_options"] == ["--disable-dependency-tracking"]
        and plan["environment_overrides"]["M4"] == tools["m4"]
        and plan["environment_overrides"]["BISON_PKGDATADIR"]
        == tools["bison_pkgdatadir"],
        "M4 precedes Bison and Flex with explicit runtime data paths",
    )
    add_check(
        checks,
        "build:no_dependency_rebuild_and_two_job_budget",
        plan["reuse_suitesparse_and_trilinos_without_rebuild"] is True
        and plan["suitesparse_or_trilinos_commands_permitted"] is False
        and plan["parallel_jobs"] == 2
        and plan["overwrite_build_directories"] is False,
        "R05 dependencies are immutable and no more than two jobs are used",
    )
    add_check(
        checks,
        "build:xyce_serial_options_and_reused_prefixes",
        "-DTrilinos_ENABLE_Fortran=OFF" in plan["xyce_cmake_options"]
        and "-DTPL_ENABLE_MPI=OFF" in plan["xyce_cmake_options"]
        and "-DXyce_ENABLE_TESTS=OFF" in plan["xyce_cmake_options"]
        and tools["bison"].endswith("/m01-generator-toolchain-r07/bin/bison")
        and tools["flex"].endswith("/m01-generator-toolchain-r07/bin/flex"),
        "serial Xyce configure uses the R07 generator prefix",
    )
    add_check(
        checks,
        "sequence:recovery_before_xyce_before_self_test",
        config["preflight_sequence"][3:12]
        == [
            "configure_build_install_m4",
            "configure_build_install_bison_with_local_m4",
            "configure_build_install_flex_with_local_m4_and_bison",
            "fingerprint_generator_versions_and_data_paths",
            "run_controlled_bison_and_flex_generation_smoke",
            "configure_build_install_serial_xyce_using_reused_dependencies",
            "fingerprint_xyce_binary_license_and_version",
            "run_controlled_bsource_expression_self_test",
            "run_xyce_syntax_only_on_generated_device_netlist_after_self_test",
        ],
        "generator smoke and Xyce fingerprints precede parser-only IGZO syntax",
    )
    generator_smoke_paths = [
        ROOT / config["outputs"][key]
        for key in (
            "generator_bison_input",
            "generator_bison_output",
            "generator_flex_input",
            "generator_flex_output",
        )
    ]
    add_check(
        checks,
        "generator:smoke_paths_registered_and_future",
        len(generator_smoke_paths) == len(set(generator_smoke_paths))
        and all("m01_xyce_build_preflight_r07" in str(path) for path in generator_smoke_paths)
        and all(not path.exists() for path in generator_smoke_paths),
        "minimal Bison/Flex smoke inputs and generated C outputs are future R07 artifacts",
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
        "controlled 1.25 V B-source self-test only",
    )
    rules = config["no_execution_rules"]
    add_check(
        checks,
        "no_execution:formal_routes_and_downstream_closed",
        rules["runner_must_not_invoke_ngspice"] is True
        and rules["runner_must_not_invoke_aimspice"] is True
        and rules["runner_must_not_invoke_formal_device_dc"] is True
        and rules["circuit_or_downstream_permitted"] is False,
        "no formal simulator route or downstream work is admitted",
    )
    formal_paths = [
        ROOT / value for value in config["formal_outputs_that_must_remain_absent"]
    ]
    add_check(
        checks,
        "outputs:formal_outputs_absent",
        all(not path.exists() for path in formal_paths),
        f"absent={sum(not path.exists() for path in formal_paths)}/{len(formal_paths)}",
    )
    output_values = list(config["outputs"].values())
    future_outputs = [
        ROOT / value for key, value in config["outputs"].items() if key != "contract_report"
    ]
    add_check(
        checks,
        "outputs:exclusive_unique_r07_namespace",
        len(output_values) == len(set(output_values))
        and config["failure_retention"]["exclusive_outputs"] is True
        and config["failure_retention"]["overwrite_existing_outputs"] is False
        and all("r07" in value for value in output_values)
        and all(not path.exists() for path in future_outputs),
        "R07 artifacts are unique, future and append-only",
    )
    retention = config["failure_retention"]
    add_check(
        checks,
        "outputs:failure_retention_and_no_threshold_relaxation",
        retention["retain_build_logs"] is True
        and retention["retain_failed_self_test_logs"] is True
        and retention["retain_failed_syntax_logs"] is True
        and retention["retain_partial_build_manifest"] is True
        and retention["formal_m01_outputs_must_remain_absent"] is True
        and retention["either_self_test_or_syntax_failure_stops_m01"] is True,
        "failed logs and partial manifests are retained",
    )
    boundary = config["evidence_boundary"]
    add_check(
        checks,
        "boundary:no_physical_or_simulation_claim",
        all(
            phrase in boundary
            for phrase in (
                "not a device simulation result",
                "not an IGZO equation",
                "physical parameter",
                "experimental calibration",
                "M01 remains E0",
            )
        ),
        "R07 evidence remains tool-only",
    )
    add_check(
        checks,
        "boundary:unaudited_aimspice_is_excluded",
        "AIM-Spice executable is excluded" in boundary
        and "lawful license provenance is absent" in boundary
        and sources["xyce"]["proprietary_binary_accepted"] is False,
        "only open-source simulator routes remain eligible",
    )
    add_check(
        checks,
        "project:next_scope_is_r07_contract",
        project["tcad_track"]["next_scope"].startswith(
            "establish and commit M01 Xyce build/tool preflight revision-7"
        )
        and m01["status"] == "preflight_failed_tool_provenance",
        project["tcad_track"]["next_scope"],
    )
    add_check(
        checks,
        "experiment:r07_is_planned_and_prior_failures_preserved",
        machine["status"] == "contract_planned"
        and machine["revision"] == 7
        and machine["current_evidence"] == "E0"
        and machine["formal_run_completed"] is False
        and machine["preflight_run_completed"] is False
        and machine["contract_check_completed"] is False
        and machine["device_netlist_invoked"] is False
        and machine["expected_contract_check_count"] == EXPECTED_CHECK_COUNT
        and machine["expected_runner_check_count"] == 47
        and machine["expected_independent_check_count"] == 25
        and machine["r05_failure_preserved"] is True
        and machine["r06_contract_failure_preserved"] is True
        and machine["r06_contract_report_sha256"] == sha256(ROOT / r06["contract_report_path"])
        and m01["xyce_build_preflight_r05"]["status"] == "preflight_failed_build"
        and m01["xyce_build_preflight_r05"]["runner_checks_passed"] == 19
        and m01["xyce_build_preflight_r06"]["status"] == "contract_failed_checker"
        and m01["xyce_build_preflight_r06"]["contract_checks_passed"] == 36,
        "R07 is unexecuted while the R05 and R06 failures remain machine-recorded",
    )

    runner_source = RUNNER_PATH.read_text(encoding="utf-8") if RUNNER_PATH.is_file() else ""
    checker_source = CHECKER_PATH.read_text(encoding="utf-8") if CHECKER_PATH.is_file() else ""
    common_source = COMMON_PATH.read_text(encoding="utf-8") if COMMON_PATH.is_file() else ""
    add_check(
        checks,
        "runner:r07_dedicated_recovery_and_no_formal_execution",
        "EXPECTED_CHECK_COUNT = 47" in runner_source
        and "build_autotools_project" in runner_source
        and 'name="m4"' in runner_source
        and 'name="bison"' in runner_source
        and 'name="flex"' in runner_source
        and "generator_bison_smoke" in runner_source
        and "generator_flex_smoke" in runner_source
        and "r05_partial_xyce_reused=false" in runner_source
        and "r06_xyce_or_outputs_reused=false" in runner_source
        and "formal_device_dc_invoked=false" in runner_source
        and "run_m01_xyce_build_preflight.py" not in runner_source,
        "R07 has a dedicated generator recovery runner and no formal device path",
    )
    add_check(
        checks,
        "checker:r07_independent_standard_library",
        "EXPECTED_CHECK_COUNT = 25" in checker_source
        and "EXPECTED_RUNNER_CHECK_COUNT = 47" in checker_source
        and "import subprocess" not in checker_source
        and "subprocess." not in checker_source
        and "run_m01_xyce_build_preflight_r07.py" in checker_source
        and re.search(
            r"^(?:from\s+run_m01_xyce_build_preflight_r07\s+import|import\s+run_m01_xyce_build_preflight_r07\b)",
            checker_source,
            re.MULTILINE,
        )
        is None
        and "def digest_tree" in common_source
        and "import subprocess" not in common_source,
        "independent checker may hash-bind the runner path but cannot import it or execute a process",
    )
    makefile_source = (ROOT / "Makefile").read_text(encoding="utf-8")
    add_check(
        checks,
        "make:r07_targets_registered",
        "m01-xyce-build-preflight-r07-contract-check:" in makefile_source
        and "m01-xyce-build-preflight-r07:" in makefile_source
        and "m01-xyce-build-preflight-r07-check:" in makefile_source,
        "contract, runner and independent-check targets are registered",
    )
    add_check(
        checks,
        "gate:formal_m01_requires_r07_independent_pass",
        rules["formal_m01_run_requires_this_preflight_report_and_independent_check"] is True
        and "independent persisted-evidence check" in config["next_gate"]
        and "formal M01 device DC" in config["next_gate"]
        and "R05" in boundary
        and "R06" in boundary,
        config["next_gate"],
    )
    historical_paths = [ROOT / value for value in config["historical_paths_to_preserve"]]
    add_check(
        checks,
        "history:registered_failure_artifacts_present",
        all(path.exists() for path in historical_paths)
        and len(historical_paths) == len(set(historical_paths)),
        f"present={sum(path.exists() for path in historical_paths)}/{len(historical_paths)}",
    )

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(
            f"R07 contract registry mismatch: expected={EXPECTED_CHECK_COUNT} actual={len(checks)}"
        )
    failures = [item for item in checks if item["status"] == "FAIL"]
    result = {
        "status": "FAIL" if failures else "PASS",
        "contract_status": "FAIL" if failures else "PASS",
        "evidence_level": "E0" if failures else "E3",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "spice_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "circuit_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "build_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "stage_id": "M01",
        "preflight_id": config["preflight_id"],
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "passed": len(checks) - len(failures),
            "failed": len(failures),
            "simulator_processes_invoked": 0,
            "build_processes_invoked": 0,
            "device_netlist_created": False,
            "numerical_outputs_created": False,
        },
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {
            "path": str(Path(__file__).relative_to(ROOT)),
            "sha256": sha256(Path(__file__)),
        },
        "reuse_tree_hashes": reuse_actual,
        "evidence_boundary": config["evidence_boundary"],
        "next_gate": config["next_gate"],
    }
    with REPORT_PATH.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=True)
        stream.write("\n")
    print(
        f"M01_XYCE_BUILD_PREFLIGHT_R07_CONTRACT_{result['status']} "
        f"checks={len(checks) - len(failures)}/{len(checks)} report={REPORT_PATH}"
    )
    return result


if __name__ == "__main__":
    result = check_contract()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
