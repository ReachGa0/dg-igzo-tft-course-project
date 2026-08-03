#!/usr/bin/env python3
"""Check the C00 R02 inverter contract without creating a netlist or process."""

from __future__ import annotations

import ast
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from c00_active_load_inverter_r02_common import (
    anchor_ids,
    dc_cases,
    generate_dc_netlist,
    generate_transient_netlist,
    transient_cases,
)


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "c00_active_load_inverter_r02.json"
COMMON_PATH = ROOT / "scripts" / "c00_active_load_inverter_r02_common.py"
RUNNER_PATH = ROOT / "scripts" / "run_c00_active_load_inverter_r02.py"
INDEPENDENT_PATH = ROOT / "scripts" / "check_c00_active_load_inverter_r02.py"
CHECKER_PATH = Path(__file__).resolve()
EXPECTED_CHECK_COUNT = 50


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


def imports_module(tree: ast.AST, module: str) -> bool:
    return any(
        isinstance(node, ast.Import) and any(alias.name == module for alias in node.names)
        or isinstance(node, ast.ImportFrom) and node.module == module
        for node in ast.walk(tree)
    )


def subprocess_calls(tree: ast.AST) -> int:
    return sum(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        for node in ast.walk(tree)
    )


def forbidden_tokens_absent(text: str, forbidden: list[str]) -> bool:
    identifiers = {
        token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    }
    return not identifiers.intersection(token.lower() for token in forbidden)


def topology_lines_match(text: str) -> bool:
    load_lines = [line.split() for line in text.splitlines() if line.startswith("XLD")]
    driver_lines = [line.split() for line in text.splitlines() if line.startswith("XDR")]
    return bool(load_lines) and len(load_lines) == len(driver_lines) and all(
        len(parts) >= 8
        and parts[1].startswith("VD")
        and parts[2].startswith("VT")
        and parts[3] == parts[1]
        and parts[4].startswith("VO")
        for parts in load_lines
    ) and all(
        len(parts) >= 8
        and parts[1].startswith("VO")
        and parts[2].startswith("VI")
        and parts[3:5] == ["0", "0"]
        for parts in driver_lines
    )


def check_contract() -> int:
    config = load_json(CONFIG_PATH)
    project = load_json(ROOT / "config" / "project.json")
    experiments = load_json(ROOT / "config" / "experiments.json")
    experiment_map = {item["id"]: item for item in experiments["experiments"]}
    c00 = experiment_map["C00"]
    machine = c00.get("active_load_inverter_r02", {})
    r01_machine = c00.get("active_load_inverter_r01", {})
    m01 = experiment_map["M01"]
    t02 = experiment_map["T02"]
    checks: list[dict[str, str]] = []

    common_text = COMMON_PATH.read_text(encoding="ascii")
    runner_text = RUNNER_PATH.read_text(encoding="ascii")
    independent_text = INDEPENDENT_PATH.read_text(encoding="ascii")
    checker_text = CHECKER_PATH.read_text(encoding="ascii")
    common_tree = ast.parse(common_text)
    runner_tree = ast.parse(runner_text)
    independent_tree = ast.parse(independent_text)
    checker_tree = ast.parse(checker_text)

    add_check(
        checks,
        "identity:c00_active_load_inverter_r02",
        config.get("project_id") == "DG-IGZO-TFT-PDK"
        and config.get("stage_id") == "C00"
        and config.get("contract_id") == "C00_ACTIVE_LOAD_INVERTER_R02"
        and config.get("revision") == 2
        and config.get("status") == "contract_planned"
        and config.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK",
        f"contract={config.get('contract_id')} revision={config.get('revision')}",
    )
    entry = config["entry_gate"]
    closure = m01.get("teaching_model_closure", {})
    add_check(
        checks,
        "entry:m01_committed_teaching_model_closure",
        m01.get("status") == "done_with_limitation"
        and m01.get("current_evidence") == "E3"
        and closure.get("decision") == "M01_TEACHING_MODEL_ONLY_PASS"
        and entry["source_decision"] == closure.get("decision")
        and entry["source_decision_basis_commit"] == closure.get("decision_basis_commit")
        and entry["source_closure_commit"] == "d03b06ea201fbc15ca98e84c129715ea7148edb3",
        f"decision={closure.get('decision')}",
    )
    add_check(
        checks,
        "entry:t02_bidirectional_e2",
        t02.get("status") == entry["t02_status"] == "bidirectional_verified"
        and t02.get("current_evidence") == entry["t02_evidence"] == "E2",
        f"status={t02.get('status')} evidence={t02.get('current_evidence')}",
    )
    binding = config["r01_failure_binding"]
    bound_files = (
        ("config_path", "config_sha256"),
        ("common_path", "common_sha256"),
        ("contract_checker_path", "contract_checker_sha256"),
        ("runner_path", "runner_sha256"),
        ("independent_checker_path", "independent_checker_sha256"),
        ("failure_report_path", "failure_report_sha256"),
    )
    r01_config_path = ROOT / binding["config_path"]
    r01_report_path = ROOT / binding["failure_report_path"]
    r01_config = load_json(r01_config_path)
    r01_report = load_json(r01_report_path)
    add_check(
        checks,
        "binding:r01_immutable_artifacts_and_failure",
        binding["implementation_commit"]
        == "4097b9d8e25f161da5e5ede3b3307bcbad11836b"
        and binding["failure_registration_commit"]
        == "60cdcbc305b45f37b3b54a494933f0a7b07c4017"
        and all(
            (ROOT / binding[path_key]).is_file()
            and sha256(ROOT / binding[path_key]) == binding[hash_key]
            for path_key, hash_key in bound_files
        )
        and binding["status"] == r01_report.get("status") == "FAIL"
        and binding["evidence_level"] == r01_report.get("evidence_level") == "E0"
        and r01_report.get("summary") == {"passed": 46, "failed": 2, "total": 48}
        and binding["checks_passed"] == r01_machine.get("contract_checks_passed") == 46
        and binding["checks_failed"] == r01_machine.get("contract_checks_failed") == 2
        and binding["primary_failed_check"] == r01_machine.get("failed_check")
        == "netlist:forbidden_scopes_absent"
        and binding["derived_failed_check"] == r01_machine.get("derived_failed_check")
        == "result:static_contract_ready"
        and binding["failure_category"] == r01_machine.get("failure_category")
        == "FORBIDDEN_TOKEN_SUBSTRING_COLLISION_NOR_IN_NORM"
        and binding["simulator_processes_invoked"]
        == r01_report.get("simulator_processes_invoked")
        == r01_machine.get("simulator_processes_invoked")
        == 0
        and binding["circuit_netlists_created"]
        == r01_report.get("circuit_netlists_created")
        == r01_machine.get("circuit_netlists_created")
        == 0
        and binding["must_remain_unchanged"] is True,
        f"report={binding['failure_report_sha256']} status={r01_report.get('status')} 46/48",
    )
    correction = config["correction_contract"]
    r01_topology = dict(r01_config["topology_contract"])
    r02_topology = dict(config["topology_contract"])
    r01_topology.pop("cell_name")
    r02_topology.pop("cell_name")
    unchanged_route_keys = {
        key: value
        for key, value in r01_config["routes"]["ngspice"].items()
        if key not in {"dc_argv", "transient_argv"}
    }
    current_route_keys = {
        key: value
        for key, value in config["routes"]["ngspice"].items()
        if key not in {"dc_argv", "transient_argv"}
    }
    unchanged_xyce_keys = {
        key: value
        for key, value in r01_config["routes"]["xyce"].items()
        if key not in {"dc_argv", "transient_argv"}
    }
    current_xyce_keys = {
        key: value
        for key, value in config["routes"]["xyce"].items()
        if key not in {"dc_argv", "transient_argv"}
    }
    r02_netlist_base = dict(config["netlist_contract"])
    r02_netlist_base.pop("forbidden_match_policy")
    add_check(
        checks,
        "correction:token_safe_only_inputs_and_thresholds_unchanged",
        correction
        == {
            "only_semantic_correction": "Match forbidden scope tokens as complete ASCII identifiers instead of arbitrary substrings.",
            "ascii_identifier_pattern": "[A-Za-z_][A-Za-z0-9_]*",
            "comparison": "case-insensitive exact token equality",
            "registered_collision": "R01 forbidden token 'nor' matched the valid DC identifier NORM",
            "topology_unchanged": True,
            "sweep_unchanged": True,
            "anchor_unchanged": True,
            "extraction_unchanged": True,
            "acceptance_thresholds_unchanged": True,
            "resource_budget_unchanged": True,
            "failure_retention_unchanged": True,
        }
        and config["entry_gate"] == r01_config["entry_gate"]
        and config["scope"] == r01_config["scope"]
        and config["upstream_model"] == r01_config["upstream_model"]
        and r02_topology == r01_topology
        and config["topology_contract"]["cell_name"] == "DG_IGZO_ACTIVE_LOAD_INV_R02"
        and config["sweep_contract"] == r01_config["sweep_contract"]
        and config["extraction_contract"] == r01_config["extraction_contract"]
        and config["acceptance_contract"] == r01_config["acceptance_contract"]
        and config["failure_retention"] == r01_config["failure_retention"]
        and config["resource_budget"] == r01_config["resource_budget"]
        and r02_netlist_base == r01_config["netlist_contract"]
        and unchanged_route_keys == current_route_keys
        and unchanged_xyce_keys == current_xyce_keys
        and config["netlist_contract"]["forbidden_match_policy"]
        == "case-insensitive exact equality over ASCII identifiers matching [A-Za-z_][A-Za-z0-9_]*",
        "R01 topology/sweep/extraction/thresholds/tools/budgets retained; matcher tokenized",
    )
    scope = config["scope"]
    add_check(
        checks,
        "scope:igzo_only_n_type_two_device_inverter",
        scope["active_material_scope"] == "IGZO only"
        and scope["polarity"] == "n-type only"
        and scope["circuit"] == "two-device dual-gate active-load ratioed inverter"
        and scope["formal_c00_circuit"] is True
        and scope["resistor_load_permitted"] is False,
        json.dumps(scope, sort_keys=True),
    )
    add_check(
        checks,
        "scope:no_sno_hzo_or_downstream",
        scope["sno_permitted"] is False
        and scope["hzo_or_ferroelectric_permitted"] is False
        and scope["c01_or_later_permitted"] is False
        and scope["layout_or_pex_permitted"] is False
        and scope["physical_parameter_claim_permitted"] is False
        and scope["experimental_calibration_claim_permitted"] is False,
        "SnO/HZO/C01/layout/PEX/calibration disabled",
    )

    topology = config["topology_contract"]
    add_check(
        checks,
        "topology:exact_two_tft_port_mapping",
        topology["device_count_per_case"] == 2
        and topology["driver"] == {
            "drain": "VOUT",
            "top_gate": "VIN",
            "bottom_gate": "0",
            "source": "0",
            "role": "input-controlled pull-down",
        }
        and topology["load"] == {
            "drain": "VDD",
            "top_gate": "V_TOP_LOAD",
            "bottom_gate": "VDD",
            "source": "VOUT",
            "role": "second-gate-programmed active pull-up",
        },
        "load D/TG/BG/S=VDD/V_TOP_LOAD/VDD/VOUT; driver=VOUT/VIN/0/0",
    )
    add_check(
        checks,
        "topology:frozen_geometry_and_ratio_rule",
        topology["driver_width_um"] == 60.0
        and topology["driver_length_um"] == 10.0
        and topology["load_length_um"] == 10.0
        and topology["load_width_rule"] == "driver_width_um * Wload_over_Wdriver"
        and topology["device_model_has_intrinsic_capacitance"] is False
        and topology["explicit_output_capacitance_required_for_transient"] is True,
        f"Wdriver={topology['driver_width_um']} L={topology['driver_length_um']}",
    )

    sweep = config["sweep_contract"]
    add_check(
        checks,
        "sweep:registered_p6_grids",
        sweep["vdd_v"] == [0.1, 0.2]
        and sweep["v_top_load_over_vdd"] == [0.5, 0.75, 1.0]
        and sweep["wload_over_wdriver"] == [0.125, 0.25, 0.5]
        and sweep["cload_f"] == [5e-13, 1e-12],
        "VDD=2, load-bias=3, ratio=3, Cload=2",
    )
    add_check(
        checks,
        "sweep:dc_grid_and_counts",
        sweep["dc_normalized_input_start"] == 0.0
        and sweep["dc_normalized_input_stop"] == 1.0
        and sweep["dc_normalized_input_step"] == 0.01
        and sweep["dc_points_per_case"] == 101
        and sweep["dc_case_count"] == 18
        and len(dc_cases(config)) == 18,
        f"cases={len(dc_cases(config))} points={sweep['dc_points_per_case']}",
    )
    add_check(
        checks,
        "sweep:transient_grid_and_counts",
        sweep["transient_case_count"] == 36
        and len(transient_cases(config)) == 36
        and sweep["transient_step_s"] == 5e-09
        and sweep["transient_stop_s"] == 3e-06
        and sweep["pulse_period_s"] == 1.5e-06,
        f"cases={len(transient_cases(config))} step={sweep['transient_step_s']}",
    )
    dc_anchor, transient_anchor = anchor_ids(config)
    add_check(
        checks,
        "sweep:anchor_preregistered_and_in_grid",
        dc_anchor in {item["case_id"] for item in dc_cases(config)}
        and transient_anchor in {item["case_id"] for item in transient_cases(config)}
        and "no post-run best-case substitution" in sweep["selection_policy"],
        f"anchor={dc_anchor}/{transient_anchor}",
    )
    add_check(
        checks,
        "sweep:registered_measurement_times",
        sweep["measured_rising_input_crossing_s"] == 1.755e-06
        and sweep["measured_falling_input_crossing_s"] == 2.465e-06
        and 1.5e-06 < sweep["pre_rising_sample_s"] < sweep["measured_rising_input_crossing_s"]
        and sweep["measured_rising_input_crossing_s"] < sweep["pre_falling_sample_s"]
        < sweep["measured_falling_input_crossing_s"],
        "second-cycle samples and crossings frozen",
    )

    extraction = config["extraction_contract"]
    add_check(
        checks,
        "extraction:static_metrics_complete",
        all(key in extraction for key in ("voh", "vol", "vm", "gain", "vil_vih", "nml", "nmh", "static_power")),
        "VOH/VOL/VM/gain/VIL/VIH/NML/NMH/static power",
    )
    add_check(
        checks,
        "extraction:transient_metrics_complete",
        all(key in extraction for key in ("tphl", "tplh", "dynamic_power"))
        and "second VIN 50%" in extraction["tphl"]
        and "second VIN 50%" in extraction["tplh"],
        "tPHL/tPLH and second-period power",
    )
    add_check(
        checks,
        "extraction:missing_values_never_imputed",
        "empty CSV field" in extraction["missing_metric_policy"]
        and "never impute" in extraction["missing_metric_policy"],
        extraction["missing_metric_policy"],
    )
    acceptance = config["acceptance_contract"]
    add_check(
        checks,
        "acceptance:anchor_logic_and_gain_thresholds",
        acceptance["anchor_voh_min_fraction_vdd"] == 0.55
        and acceptance["anchor_vol_max_fraction_vdd"] == 0.45
        and acceptance["anchor_vm_min_fraction_vdd"] == 0.2
        and acceptance["anchor_vm_max_fraction_vdd"] == 0.8
        and acceptance["anchor_gain_min_v_per_v"] == 1.0
        and acceptance["anchor_required_unit_gain_crossings"] == 2
        and acceptance["anchor_min_noise_margin_v"] == 0.0,
        "VOH/VOL/VM/gain/noise-margin thresholds frozen",
    )
    add_check(
        checks,
        "acceptance:anchor_transient_thresholds",
        acceptance["anchor_transient_high_min_fraction_vdd"] == 0.55
        and acceptance["anchor_transient_low_max_fraction_vdd"] == 0.45
        and acceptance["anchor_max_delay_s"] == 6.5e-07
        and acceptance["both_routes_must_qualify_anchor"] is True,
        "both routes require two output crossings and bounded delay",
    )
    add_check(
        checks,
        "acceptance:all_cases_and_power_reported",
        acceptance["all_raw_values_finite"] is True
        and acceptance["all_registered_cases_complete"] is True
        and acceptance["static_current_tradeoff_must_be_reported_for_all_dc_cases"] is True
        and acceptance["dynamic_power_must_be_reported_for_all_transient_cases"] is True,
        "all P6 cases retained",
    )
    add_check(
        checks,
        "acceptance:route_difference_diagnostic_only",
        extraction["route_difference_is_diagnostic_only"] is True
        and acceptance["route_agreement_threshold_is_not_a_pass_gate"] is True
        and acceptance["thresholds_must_not_be_relaxed_after_execution"] is True,
        "route differences reported without post-run tuning",
    )

    model = config["upstream_model"]
    model_path = ROOT / model["candidate_path"]
    model_text = model_path.read_text(encoding="ascii")
    add_check(
        checks,
        "model:portable_candidate_hash_bound",
        model_path.is_file()
        and sha256(model_path) == model["candidate_sha256"]
        and model_path.stat().st_size == model["candidate_bytes"],
        f"sha256={sha256(model_path)} bytes={model_path.stat().st_size}",
    )
    add_check(
        checks,
        "model:subcircuit_and_valid_domain",
        f".subckt {model['subcircuit']} D TG BG S" in model_text
        and model["port_order"] == ["D", "TG", "BG", "S"]
        and model["valid_vds_min_v"] == 0.0
        and model["valid_vds_max_v"] == max(sweep["vdd_v"]) == 0.2
        and model["temperature_k"] == 300.0,
        f"subckt={model['subcircuit']} VDS<=0.2 V",
    )
    add_check(
        checks,
        "model:no_equation_or_native_model_overclaim",
        model["equation_identity_claimed"] is False
        and model["native_level15_or_level61_claimed"] is False
        and "sno" not in model_text.lower()
        and "hzo" not in model_text.lower()
        and "ferroelectric" not in model_text.lower(),
        model["model_class"],
    )

    for route_name in ("ngspice", "xyce"):
        route = config["routes"][route_name]
        tool = Path(route["tool_path"])
        add_check(
            checks,
            f"tool:{route_name}_hash_and_size",
            tool.is_file()
            and sha256(tool) == route["tool_sha256"]
            and tool.stat().st_size == route["tool_bytes"],
            f"path={tool} sha256={sha256(tool)} bytes={tool.stat().st_size}",
        )
    add_check(
        checks,
        "tool:open_source_route_identity",
        config["routes"]["ngspice"]["version_token"] == "ngspice-42"
        and config["routes"]["xyce"]["version_token"] == "7.10.0"
        and config["routes"]["xyce"]["license_token"] == "GNU General Public License",
        "ngspice 42 and GPL Xyce 7.10.0",
    )
    outputs = config["outputs"]
    add_check(
        checks,
        "tool:four_exact_serial_argv",
        config["routes"]["ngspice"]["dc_argv"][-1] == outputs["ngspice_dc_netlist"]
        and config["routes"]["ngspice"]["transient_argv"][-1] == outputs["ngspice_tran_netlist"]
        and config["routes"]["xyce"]["dc_argv"][-1] == outputs["xyce_dc_netlist"]
        and config["routes"]["xyce"]["transient_argv"][-1] == outputs["xyce_tran_netlist"],
        "ngspice DC/TRAN then Xyce DC/TRAN",
    )
    budget = config["resource_budget"]
    add_check(
        checks,
        "resource:four_process_laptop_budget",
        budget == {
            "route_count": 2,
            "analyses_per_route": 2,
            "max_serial_simulator_processes": 4,
            "parallel_simulator_processes": 0,
            "ngspice_processes": 2,
            "xyce_processes": 2,
            "aimspice_processes": 0,
            "tcad_processes": 0,
            "layout_processes": 0,
            "pex_processes": 0,
            "laptop_target": True,
        },
        json.dumps(budget, sort_keys=True),
    )
    retention = config["failure_retention"]
    add_check(
        checks,
        "failure:exclusive_and_complete_retention",
        all(
            retention[key] is True
            for key in (
                "exclusive_outputs",
                "retain_failed_netlists",
                "retain_failed_logs",
                "retain_partial_raw_outputs",
                "retain_partial_tables",
                "failure_status_must_remain_visible",
                "no_threshold_relaxation",
                "m01_and_tcad_history_must_not_change",
            )
        )
        and retention["overwrite_existing_outputs"] is False,
        "exclusive outputs and immutable failures",
    )

    add_check(checks, "source:all_ascii_and_parseable", all(text.isascii() for text in (common_text, runner_text, independent_text, checker_text)), "four ASCII Python sources")
    add_check(checks, "source:common_has_no_subprocess", not imports_module(common_tree, "subprocess") and subprocess_calls(common_tree) == 0, "common is deterministic pure helper code")
    add_check(checks, "source:contract_checker_has_no_subprocess", not imports_module(checker_tree, "subprocess") and subprocess_calls(checker_tree) == 0, "static checker invokes zero processes")
    add_check(checks, "source:runner_owns_process_execution", imports_module(runner_tree, "subprocess") and subprocess_calls(runner_tree) == 1, f"subprocess_calls={subprocess_calls(runner_tree)}")
    add_check(checks, "source:independent_has_no_process_or_runner_import", not imports_module(independent_tree, "subprocess") and subprocess_calls(independent_tree) == 0 and not imports_module(independent_tree, "c00_active_load_inverter_r02_common") and not imports_module(independent_tree, "run_c00_active_load_inverter_r02"), "independent checker duplicates regeneration and extraction")

    ng_dc = generate_dc_netlist(config, "ngspice")
    xy_dc = generate_dc_netlist(config, "xyce")
    ng_tran = generate_transient_netlist(config, "ngspice")
    xy_tran = generate_transient_netlist(config, "xyce")
    add_check(checks, "netlist:four_ascii_in_memory_only", all(item.isascii() for item in (ng_dc, xy_dc, ng_tran, xy_tran)), "no netlist file written")
    add_check(checks, "netlist:dc_analysis_and_case_count", ng_dc.count(".DC VSWEEP") == xy_dc.count(".DC VSWEEP") == 1 and ng_dc.count("XLD") == ng_dc.count("XDR") == xy_dc.count("XLD") == xy_dc.count("XDR") == 18, "18 DC cases and 36 IGZO devices per route")
    add_check(checks, "netlist:transient_analysis_and_case_count", ng_tran.count(".TRAN ") == xy_tran.count(".TRAN ") == 1 and ng_tran.count("XLD") == ng_tran.count("XDR") == xy_tran.count("XLD") == xy_tran.count("XDR") == 36 and ng_tran.count("CLOAD") == xy_tran.count("CLOAD") == 36, "36 transient cases and 72 IGZO devices per route")
    add_check(checks, "netlist:exact_load_and_driver_connections", all(topology_lines_match(text) for text in (ng_dc, xy_dc, ng_tran, xy_tran)), "generated lines bind load to VD/VT/VD/VO and driver to VO/VI/0/0")
    forbidden = config["netlist_contract"]["forbidden_case_insensitive_tokens"]
    add_check(
        checks,
        "netlist:forbidden_scopes_absent_token_safe",
        all(forbidden_tokens_absent(text, forbidden) for text in (ng_dc, xy_dc, ng_tran, xy_tran)),
        f"forbidden={len(forbidden)} policy=ASCII identifier equality",
    )
    add_check(checks, "netlist:route_specific_output_contract", outputs["ngspice_dc_raw"] in ng_dc and outputs["ngspice_tran_raw"] in ng_tran and ".PRINT DC" in xy_dc and ".PRINT TRAN" in xy_tran and ".control" not in xy_dc + xy_tran, "ngspice ASCII raw and Xyce fixed-column PRN")

    output_values = list(outputs.values())
    add_check(checks, "outputs:unique_versioned_paths", len(output_values) == len(set(output_values)) and all("r02" in value or "c00_active_load_inverter_r02" in value for value in output_values), f"paths={len(output_values)}")
    add_check(checks, "outputs:owned_directories_only", all(value.startswith(("results/compact/c00_", "results/reports/c00_", "results/tables/c00_", "report/assets/c00_")) for value in output_values), "C00-owned result/report namespaces")
    future_keys = [key for key in outputs if key not in {"contract_report", "run_directory"}]
    add_check(checks, "outputs:no_future_artifact_before_static_check", all(not (ROOT / outputs[key]).exists() for key in future_keys) and not (ROOT / outputs["run_directory"]).exists(), f"absent={sum(not (ROOT / outputs[key]).exists() for key in future_keys)}/{len(future_keys)}")

    add_check(
        checks,
        "machine:implementation_state_before_static_check",
        c00.get("status") == "contract_implemented"
        and c00.get("current_evidence") == "E0"
        and machine.get("status") == "contract_implemented"
        and machine.get("current_evidence") == "E0"
        and machine.get("contract_check_completed") is False
        and machine.get("formal_run_completed") is False
        and machine.get("independent_check_completed") is False,
        f"root={c00.get('status')} machine={machine.get('status')}",
    )
    add_check(
        checks,
        "machine:registered_counts_and_no_execution",
        machine.get("expected_contract_check_count") == 50
        and machine.get("expected_runner_check_count") == 36
        and machine.get("expected_independent_check_count") == 29
        and machine.get("simulator_processes_invoked") == 0
        and machine.get("circuit_execution_permitted") is False
        and machine.get("downstream_permitted") is False,
        "50/36/29, zero processes",
    )
    add_check(
        checks,
        "project:next_scope_static_contract_only",
        project.get("tcad_track", {}).get("next_scope", "").startswith(
            "run the 50-check static contract for C00 active-load inverter revision-2"
        ),
        project.get("tcad_track", {}).get("next_scope", ""),
    )
    add_check(
        checks,
        "boundary:no_circuit_evidence_or_downstream_claim",
        entry["circuit_execution_permitted_before_committed_static_pass"] is False
        and entry["downstream_permitted"] is False
        and "No circuit netlist or numerical circuit result" in config["evidence_boundary"]["static_contract_allowed_claim"]
        and len(config["evidence_boundary"]["prohibited_claims"]) == 6,
        "static structure only; no circuit result",
    )
    add_check(
        checks,
        "registry:50_36_29",
        config["registered_checks"] == {"static_contract": 50, "runner": 36, "independent": 29},
        json.dumps(config["registered_checks"], sort_keys=True),
    )
    add_check(checks, "result:static_contract_ready", all(item["status"] == "PASS" for item in checks), f"pre_result_passed={sum(item['status'] == 'PASS' for item in checks)}")

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"static check registry mismatch expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")
    passed = sum(item["status"] == "PASS" for item in checks)
    status = "PASS" if passed == EXPECTED_CHECK_COUNT else "FAIL"
    report_path = ROOT / outputs["contract_report"]
    payload = {
        "schema_version": "1.0",
        "project_id": config["project_id"],
        "stage_id": "C00",
        "contract_id": config["contract_id"],
        "status": status,
        "evidence_level": "E3" if status == "PASS" else "E0",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "circuit_netlists_created": 0,
        "simulator_processes_invoked": 0,
        "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)},
        "checker": {"path": str(CHECKER_PATH.relative_to(ROOT)), "sha256": sha256(CHECKER_PATH)},
        "summary": {"passed": passed, "failed": EXPECTED_CHECK_COUNT - passed, "total": EXPECTED_CHECK_COUNT},
        "checks": checks,
        "evidence_boundary": config["evidence_boundary"]["static_contract_allowed_claim"],
        "next_gate": (
            "Commit and push this E3 static PASS, then execute the 36-check C00 runner exactly once with four serial simulator processes."
            if status == "PASS"
            else "Preserve and commit this static failure. Do not execute a circuit netlist or relax a threshold."
        ),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if report_path.exists():
        raise RuntimeError(f"contract checker refuses to overwrite {report_path}")
    report_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"C00_ACTIVE_LOAD_INVERTER_R02_CONTRACT_{status} checks={passed}/{EXPECTED_CHECK_COUNT} report={report_path}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(check_contract())
