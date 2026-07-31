#!/usr/bin/env python3
"""Validate the T02-A dual-gate input and disabled-limit contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t02_a_dual_gate_contract.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def close(
    left: float,
    right: float,
    *,
    rel_tol: float = 1.0e-12,
    abs_tol: float = 1.0e-15,
) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def stage_by_id(config: dict[str, Any], stage_id: str) -> dict[str, Any]:
    return next(stage for stage in config["bias_protocol"]["stages"] if stage["id"] == stage_id)


def check_contract(config_path: Path) -> dict[str, Any]:
    config = load_json(config_path)
    dependency = config["dependencies"]
    project_path = ROOT / "config" / "project.json"
    project = load_json(project_path)
    s00_path = ROOT / dependency["s00_report"]
    t00_path = ROOT / dependency["t00_config"]
    t01_path = ROOT / dependency["t01_baseline_config"]
    t01_contract_path = ROOT / dependency["t01_contract_report"]
    mesh_path = ROOT / dependency["t01_mesh_config"]
    extraction_config_path = ROOT / dependency["t01_extraction_config"]
    extraction_report_path = ROOT / dependency["t01_extraction_report"]
    extraction_check_path = ROOT / dependency["t01_extraction_check_report"]

    s00 = load_json(s00_path)
    t00 = load_json(t00_path)
    t01 = load_json(t01_path)
    t01_contract = load_json(t01_contract_path)
    mesh = load_json(mesh_path)
    extraction_config = load_json(extraction_config_path)
    extraction_report = load_json(extraction_report_path)
    extraction_check = load_json(extraction_check_path)
    checks: list[dict[str, Any]] = []

    add_check(
        checks,
        "identity:t02_a_contract",
        config.get("schema_version") == 1
        and config.get("stage") == "T02-A"
        and config.get("case_id") == "IGZO_T02_DUAL_GATE_DD_A_LIMIT_V1"
        and config.get("status") == "planned",
        f"case={config.get('case_id')} stage={config.get('stage')}",
    )

    completion = extraction_report.get("t01_completion", {})
    add_check(
        checks,
        "dependencies:t01_complete_and_independently_checked",
        t01_contract.get("contract_status") == dependency["required_t01_contract_status"]
        and extraction_report.get("status") == dependency["required_t01_extraction_status"]
        and extraction_report.get("case_id") == extraction_config.get("case_id")
        and completion.get("complete_t01_numerical_stage_gate")
        == dependency["required_t01_complete_gate"]
        and completion.get("t02_stage_permitted_next")
        is dependency["require_t02_stage_permitted_next"]
        and extraction_check.get("status")
        == dependency["required_t01_extraction_check_status"]
        and not extraction_check.get("failures"),
        (
            f"T01 contract={t01_contract.get('contract_status')} "
            f"D-C={extraction_report.get('status')} independent={extraction_check.get('status')} "
            f"next={completion.get('t02_stage_permitted_next')}"
        ),
    )

    add_check(
        checks,
        "gate:g0_remains_teaching_only",
        s00.get("g0_decision", {}).get("status") == dependency["required_g0_status"]
        and s00.get("g0_decision", {}).get("quantitative_fitting_permitted") is False,
        json.dumps(s00.get("g0_decision", {}), sort_keys=True),
    )

    units = config["coordinate_system"]
    t01_units = t01["coordinate_system"]
    add_check(
        checks,
        "units:inherit_t01_centimeter_transport_convention",
        units["coordinate_unit"] == t01_units["coordinate_unit"] == "cm"
        and units["voltage_unit"] == t01_units["voltage_unit"] == "V"
        and units["density_unit"] == t01_units["density_unit"] == "cm^-3"
        and units["mobility_unit"] == t01_units["mobility_unit"] == "cm^2/(V*s)"
        and units["terminal_current_2d_unit"] == "A/cm",
        json.dumps(units, sort_keys=True),
    )

    serialized = json.dumps(config, sort_keys=True)
    add_check(
        checks,
        "materials:igzo_only",
        "n-IGZO" in config["scope"]["device"]
        and t01["device"]["material"] == "IGZO"
        and t01["device"]["polarity"] == "n"
        and "SnO" not in serialized,
        f"device={config['scope']['device']}",
    )

    top = config["top_stack_contract"]["enabled_mode"]
    t00_top = t00["materials"]["top_oxide"]
    project_device = project["baseline_devices"]["IGZO_TFT"]
    add_check(
        checks,
        "top_stack:symmetric_teaching_geometry_and_source",
        top["top_oxide_present"] is True
        and top["top_gate_present"] is True
        and top["top_oxide_material"] == "Al2O3"
        and close(top["top_oxide_thickness_nm"], project_device["physical_gate_dielectric_nm"])
        and close(top["top_oxide_thickness_cm"], top["top_oxide_thickness_nm"] * 1.0e-7)
        and close(top["top_oxide_relative_permittivity"], t00_top["relative_permittivity"])
        and top["top_gate_boundary"] == "ideal_electrostatic_dirichlet"
        and top["top_gate_work_function_offset_model"] == "none"
        and top["fabrication_status"]
        == "not present in the stated fabricated single-bottom-gate process",
        (
            f"tox={top['top_oxide_thickness_nm']} nm er={top['top_oxide_relative_permittivity']} "
            f"source={top['source_type']}"
        ),
    )

    disabled = config["top_stack_contract"]["disabled_mode"]
    add_check(
        checks,
        "limit:disabled_means_exact_t01_topology",
        disabled["top_oxide_present"] is False
        and disabled["top_gate_present"] is False
        and disabled["channel_top_boundary"] == "natural_zero_normal_flux"
        and disabled["required_reference"] == extraction_report.get("case_id")
        and "omit the complete top stack" in disabled["implementation"],
        json.dumps(disabled, sort_keys=True),
    )
    add_check(
        checks,
        "limit:zero_volt_top_gate_is_not_disabled",
        config["top_stack_contract"]["zero_bias_is_not_disabled"] is True
        and "not the disabled limit" in config["top_stack_contract"]["boundary_note"],
        config["top_stack_contract"]["boundary_note"],
    )

    physics = config["physics"]
    equations = t01["physics"]["equations"]
    add_check(
        checks,
        "physics:only_top_electrostatic_stack_changes",
        physics["active_equations"] == ["Poisson", "electron_continuity"]
        and physics["transport"] == "electron-only Scharfetter-Gummel drift-diffusion"
        and physics["mobility_model"] == t01["physics"]["mobility_model"]
        and close(physics["temperature_k"], t01["physics"]["temperature_k"])
        and equations["bulk_traps"] == "inactive"
        and equations["interface_traps"] == "inactive"
        and equations["ferroelectric_polarization"] == "inactive"
        and "contact_resistance_or_barrier" in physics["inactive_models"],
        json.dumps(physics, sort_keys=True),
    )

    mesh_contract = config["mesh"]
    level = next(
        item for item in mesh["mesh_ladder"]["levels"] if item["id"] == mesh_contract["source_level"]
    )
    add_check(
        checks,
        "mesh:inherits_t01_interface_4x_and_mirrors_top_interface",
        mesh_contract["source_stage"] == "T01-D-A"
        and mesh_contract["source_level"] == extraction_config["mesh"]["production_level"]
        and close(mesh_contract["refinement_factor"], level["refinement_factor"])
        and close(
            mesh_contract["top_oxide_interface_window_cm"],
            mesh["mesh_ladder"]["oxide_interface_window_cm"],
        )
        and close(
            mesh_contract["channel_top_interface_window_cm"],
            mesh["mesh_ladder"]["channel_interface_window_cm"],
        )
        and 2.0 * float(mesh_contract["channel_top_interface_window_cm"])
        <= float(t01["geometry"]["channel_thickness_cm"]),
        f"source={mesh_contract['source_level']} factor={level['refinement_factor']}",
    )

    disabled_bias = config["bias_protocol"]["disabled_regression"]
    enabled_bias = config["bias_protocol"]["enabled_zero_bias_smoke"]
    t01_low_vds = stage_by_id(t01, "T01_A_STAGE_1")
    configured_vbg = [float(value) for value in disabled_bias["bottom_gate_continuation_v"]]
    reference_vbg = {
        float(row["vgs_v"])
        for row in extraction_report["bias_points"]
        if row["mesh_level"] == mesh_contract["source_level"]
    }
    add_check(
        checks,
        "bias:ordered_disabled_regression_with_t01_reference_points",
        disabled_bias["low_vds_values_v"] == t01_low_vds["vds_values_v"]
        and close(disabled_bias["vds_v"], t01_low_vds["vds_values_v"][-1])
        and configured_vbg == sorted(configured_vbg)
        and configured_vbg[0] == 0.0
        and set(configured_vbg) <= reference_vbg,
        f"VBG={configured_vbg} VDS={disabled_bias['vds_v']}",
    )
    add_check(
        checks,
        "bias:enabled_case_is_zero_bias_topology_smoke_only",
        all(close(value, 0.0) for key, value in enabled_bias.items() if key.endswith("_v"))
        and config["scope"]["executed_cases"][-1]
        == "enabled-topology all-zero-bias equilibrium smoke"
        and "nonzero enabled-top-gate bias family" in config["scope"]["prohibited_work"],
        json.dumps(enabled_bias, sort_keys=True),
    )

    acceptance = config["acceptance"]
    expected_disabled_solves = 2 + len(disabled_bias["low_vds_values_v"]) + len(configured_vbg) - 1
    add_check(
        checks,
        "acceptance:solve_and_point_counts_are_derived",
        configured_vbg == [float(value) for value in acceptance["required_disabled_bottom_gate_values_v"]]
        and len(configured_vbg) == acceptance["required_disabled_reported_point_count"]
        and expected_disabled_solves == acceptance["required_disabled_dc_solve_count"]
        and acceptance["required_enabled_zero_bias_dc_solve_count"] == 2
        and expected_disabled_solves + 2 == acceptance["required_total_dc_solve_count"],
        (
            f"disabled={expected_disabled_solves} enabled=2 "
            f"total={expected_disabled_solves + 2}"
        ),
    )
    add_check(
        checks,
        "acceptance:strict_regression_and_conservation_limits",
        0.0 < acceptance["maximum_disabled_t01_relative_current_difference"] <= 1.0e-8
        and 0.0 < acceptance["maximum_disabled_t01_center_potential_difference_v"] <= 1.0e-10
        and 0.0 < acceptance["maximum_disabled_t01_center_density_relative_difference"] <= 1.0e-8
        and 0.0 < acceptance["maximum_relative_terminal_current_imbalance"] <= 1.0e-5
        and acceptance["require_all_dc_solves_converged"] is True,
        json.dumps(acceptance, sort_keys=True),
    )

    outputs = config["outputs"]
    add_check(
        checks,
        "outputs:separate_raw_processed_and_reports",
        outputs["run_directory"].startswith("results/tcad/t02_dual_gate/")
        and outputs["disabled_regression_csv"].startswith("results/tables/")
        and outputs["topology_summary_csv"].startswith("results/tables/")
        and outputs["report"].startswith("results/reports/")
        and outputs["check_report"].startswith("results/reports/")
        and len(set(outputs.values())) == len(outputs),
        json.dumps(outputs, sort_keys=True),
    )

    boundary = config["evidence_boundary"]
    add_check(
        checks,
        "scope:evidence_boundary_blocks_dual_gate_claims",
        "T02 complete" in boundary["prohibited_claims"]
        and "nonzero dual-gate current or threshold coupling verified"
        in boundary["prohibited_claims"]
        and "T02-B" in boundary["next_gate"]
        and "T03 parameter scans" in config["scope"]["prohibited_work"],
        boundary["next_gate"],
    )

    input_paths = {
        "project": project_path,
        "s00_report": s00_path,
        "t00_config": t00_path,
        "t01_baseline_config": t01_path,
        "t01_contract_report": t01_contract_path,
        "t01_mesh_config": mesh_path,
        "t01_extraction_config": extraction_config_path,
        "t01_extraction_report": extraction_report_path,
        "t01_extraction_check_report": extraction_check_path,
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
        print(f"T02_A_CONTRACT_ERROR {error}", file=sys.stderr)
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
        f"T02_A_CONTRACT_{report['status']} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={report_path}"
    )
    for failure in report["failures"]:
        print(
            f"T02_A_CONTRACT_ERROR {failure['name']}: {failure['detail']}",
            file=sys.stderr,
        )
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
