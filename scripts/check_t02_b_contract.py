#!/usr/bin/env python3
"""Validate the T02-B minimal nonzero top-gate bias contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t02_b_minimal_bias.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(left: float, right: float, *, abs_tol: float = 1.0e-15) -> bool:
    return math.isclose(float(left), float(right), rel_tol=1.0e-12, abs_tol=abs_tol)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    project_path = ROOT / "config" / "project.json"
    s00_path = ROOT / dependency["s00_report"]
    t01_path = ROOT / dependency["t01_baseline_config"]
    mesh_path = ROOT / dependency["t01_mesh_config"]
    t02_a_config_path = ROOT / dependency["t02_a_config"]
    t02_a_contract_path = ROOT / dependency["t02_a_contract_report"]
    t02_a_report_path = ROOT / dependency["t02_a_report"]
    t02_a_check_path = ROOT / dependency["t02_a_check_report"]

    project = load_json(project_path)
    s00 = load_json(s00_path)
    t01 = load_json(t01_path)
    mesh = load_json(mesh_path)
    t02_a_config = load_json(t02_a_config_path)
    t02_a_contract = load_json(t02_a_contract_path)
    t02_a_report = load_json(t02_a_report_path)
    t02_a_check = load_json(t02_a_check_path)
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t02_b_contract",
        config.get("schema_version") == 1
        and config.get("stage") == "T02-B"
        and config.get("case_id") == "IGZO_T02_DUAL_GATE_DD_B_MINIMAL_V1"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )

    completion = t02_a_report.get("t02_a_completion", {})
    add_check(
        checks,
        "dependencies:t02_a_gate_is_open",
        t02_a_contract.get("contract_status")
        == dependency["required_t02_a_contract_status"]
        and t02_a_report.get("status") == dependency["required_t02_a_status"]
        and t02_a_check.get("status") == dependency["required_t02_a_check_status"]
        and not t02_a_check.get("failures")
        and completion.get("t02_b_minimal_bias_family_permitted_next")
        is dependency["require_t02_b_permitted_by_t02_a"]
        and completion.get("t02_complete") is False,
        (
            f"contract={t02_a_contract.get('contract_status')} "
            f"run={t02_a_report.get('status')} check={t02_a_check.get('status')} "
            f"next={completion.get('t02_b_minimal_bias_family_permitted_next')}"
        ),
    )

    add_check(
        checks,
        "dependencies:t02_a_identity_and_hashes_match",
        t02_a_report.get("case_id") == t02_a_config.get("case_id")
        and t02_a_check.get("case_id") == t02_a_config.get("case_id")
        and t02_a_contract.get("config", {}).get("sha256") == sha256(t02_a_config_path),
        f"case={t02_a_config.get('case_id')} config_sha256={sha256(t02_a_config_path)}",
    )

    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status") == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted") is False,
        json.dumps(s00.get("g0_decision", {}), sort_keys=True),
    )

    serialized = json.dumps(config, sort_keys=True)
    add_check(
        checks,
        "materials:igzo_only",
        "n-IGZO" in config["scope"]["device"]
        and t01["device"]["material"] == "IGZO"
        and project["baseline_devices"]["IGZO_TFT"]["polarity"] == "n"
        and "SnO" not in serialized,
        f"device={config['scope']['device']}",
    )

    enabled = t02_a_config["top_stack_contract"]["enabled_mode"]
    add_check(
        checks,
        "topology:inherits_t02_a_enabled_stack",
        config["inheritance"]["top_stack_source"].endswith(
            "top_stack_contract.enabled_mode"
        )
        and enabled["top_oxide_present"] is True
        and enabled["top_gate_present"] is True
        and enabled["top_oxide_material"] == "Al2O3"
        and close(enabled["top_oxide_thickness_nm"], 30.0)
        and close(enabled["top_oxide_relative_permittivity"], 6.8)
        and enabled["top_gate_boundary"] == "ideal_electrostatic_dirichlet",
        json.dumps(enabled, sort_keys=True),
    )

    t02_a_physics = t02_a_config["physics"]
    add_check(
        checks,
        "physics:frozen_teaching_transport",
        t02_a_physics["active_equations"] == ["Poisson", "electron_continuity"]
        and t02_a_physics["mobility_model"] == t01["physics"]["mobility_model"]
        and close(t02_a_physics["temperature_k"], t01["physics"]["temperature_k"])
        and "bulk_traps" in t02_a_physics["inactive_models"]
        and "contact_resistance_or_barrier" in t02_a_physics["inactive_models"]
        and "ferroelectric_polarization" in t02_a_physics["inactive_models"],
        json.dumps(t02_a_physics, sort_keys=True),
    )

    inheritance = config["inheritance"]
    mesh_levels = {item["id"] for item in mesh["mesh_ladder"]["levels"]}
    add_check(
        checks,
        "mesh:exact_t02_a_interface_4x",
        inheritance["required_mesh_level"] == t02_a_config["mesh"]["source_level"]
        == "interface_4x"
        and inheritance["required_mesh_level"] in mesh_levels
        and inheritance["require_exact_t02_a_enabled_topology"] is True,
        f"mesh={inheritance['required_mesh_level']} available={sorted(mesh_levels)}",
    )

    protocol = config["bias_protocol"]
    top_values = [float(value) for value in protocol["top_gate_values_v"]]
    state_values = [float(value) for value in protocol["state_top_gate_values_v"]]
    add_check(
        checks,
        "bias:only_top_gate_changes_at_reported_points",
        config["scope"]["changed_variable"] == "V_top_gate"
        and close(protocol["source_v"], 0.0)
        and close(protocol["drain_v"], 0.01)
        and close(protocol["bottom_gate_v"], 0.0)
        and "bottom-gate sweep" in config["scope"]["prohibited_work"],
        (
            f"VS={protocol['source_v']} VD={protocol['drain_v']} "
            f"VBG={protocol['bottom_gate_v']}"
        ),
    )
    add_check(
        checks,
        "bias:minimal_ordered_nonzero_vtg_family",
        top_values == [0.0, 0.1, 0.2, 0.3]
        and top_values == sorted(top_values)
        and len(set(top_values)) == len(top_values)
        and any(value > 0.0 for value in top_values)
        and all(value >= 0.0 for value in top_values),
        f"VTG={top_values}",
    )

    t01_low_vds = next(
        stage for stage in t01["bias_protocol"]["stages"] if stage["id"] == "T01_A_STAGE_1"
    )
    add_check(
        checks,
        "bias:initialization_reuses_low_vds_ladder",
        protocol["low_vds_values_v"] == t01_low_vds["vds_values_v"]
        and close(protocol["low_vds_values_v"][-1], protocol["drain_v"])
        and protocol["execution_order"][0] == "fresh T02-A enabled-top-stack device",
        json.dumps(protocol["low_vds_values_v"]),
    )

    acceptance = config["acceptance"]
    add_check(
        checks,
        "state:endpoints_only",
        state_values == [top_values[0], top_values[-1]]
        and acceptance["required_state_ids"]
        == ["top_gate_zero_reference", "top_gate_positive_endpoint"]
        and acceptance["required_vtk_file_count_per_state"] == 6,
        f"state_VTG={state_values} ids={acceptance['required_state_ids']}",
    )

    expected_solves = 2 + len(protocol["low_vds_values_v"]) + len(top_values) - 1
    add_check(
        checks,
        "acceptance:point_and_solve_counts_are_derived",
        top_values
        == [float(value) for value in acceptance["required_top_gate_values_v"]]
        and len(top_values) == acceptance["required_reported_point_count"]
        and expected_solves == acceptance["required_total_dc_solve_count"],
        f"points={len(top_values)} solves={expected_solves}",
    )

    add_check(
        checks,
        "acceptance:strict_direction_and_conservation",
        0.0 < acceptance["maximum_relative_terminal_current_imbalance"] <= 1.0e-5
        and acceptance["require_positive_drain_and_negative_source_current"] is True
        and acceptance["require_strict_current_increase_with_top_gate"] is True
        and acceptance["require_strict_center_potential_increase_with_top_gate"] is True
        and acceptance["require_strict_center_density_increase_with_top_gate"] is True
        and acceptance["minimum_endpoint_current_ratio"] > 1.0
        and acceptance["minimum_endpoint_center_potential_increase_v"] > 0.0
        and acceptance["minimum_endpoint_center_density_ratio"] > 1.0,
        json.dumps(acceptance, sort_keys=True),
    )

    add_check(
        checks,
        "acceptance:exact_enabled_topology_contract",
        acceptance["required_regions"]
        == t02_a_config["acceptance"]["required_enabled_regions"]
        and acceptance["required_contacts"]
        == t02_a_config["acceptance"]["required_enabled_contacts"]
        and acceptance["required_interfaces"]
        == ["bottom_oxide_channel", "channel_top_oxide"]
        and acceptance["require_t02_a_topology_count_match"] is True,
        (
            f"regions={acceptance['required_regions']} "
            f"contacts={acceptance['required_contacts']}"
        ),
    )

    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:separate_raw_processed_report_and_figure",
        outputs["run_directory"].startswith("results/tcad/t02_dual_gate/")
        and outputs["bias_csv"].startswith("results/tables/")
        and outputs["state_summary_csv"].startswith("results/tables/")
        and outputs["report"].startswith("results/reports/")
        and outputs["check_report"].startswith("results/reports/")
        and outputs["figure_png"].startswith("report/assets/")
        and len(set(outputs.values())) == len(outputs),
        json.dumps(outputs, sort_keys=True),
    )

    boundary = config["evidence_boundary"]
    add_check(
        checks,
        "scope:evidence_boundary_keeps_t02_incomplete",
        "T02 complete" in boundary["prohibited_claims"]
        and "Delta VTH, gm, SS, mobility, capacitance ratio, or coupling slope extracted"
        in boundary["prohibited_claims"]
        and "T02-C" in boundary["next_gate"]
        and "T03 parameter scans" in config["scope"]["prohibited_work"],
        boundary["next_gate"],
    )

    input_paths = {
        "project": project_path,
        "s00_report": s00_path,
        "t01_baseline_config": t01_path,
        "t01_mesh_config": mesh_path,
        "t02_a_config": t02_a_config_path,
        "t02_a_contract_report": t02_a_contract_path,
        "t02_a_report": t02_a_report_path,
        "t02_a_check_report": t02_a_check_path,
    }
    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
        "contract_evidence_level": (
            config["contract_evidence_level_after_check"] if not failures else "E0"
        ),
        "checks": checks,
        "failures": failures,
        "config": {
            "path": str(config_path.relative_to(ROOT)),
            "sha256": sha256(config_path),
        },
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": sha256(path)}
            for name, path in input_paths.items()
        },
        "outputs": outputs,
        "evidence_boundary": boundary,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=CONFIG_PATH)
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    try:
        report = check_contract(config_path)
    except Exception as error:  # noqa: BLE001
        print(f"T02_B_CONTRACT_ERROR {error}", file=sys.stderr)
        return 1

    config = load_json(config_path)
    report_path = ROOT / config["outputs"]["contract_report"]
    if not args.check_only:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=True) + "\n",
            encoding="utf-8",
        )
    print(
        f"T02_B_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T02_B_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
