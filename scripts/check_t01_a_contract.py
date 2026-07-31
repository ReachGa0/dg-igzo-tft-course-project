#!/usr/bin/env python3
"""Validate the T01-A single-gate drift-diffusion input contract."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t01_baseline.json"
PROJECT_PATH = ROOT / "config" / "project.json"
S00_REPORT_PATH = ROOT / "results" / "reports" / "s00_data_audit.json"
REPORT_PATH = ROOT / "results" / "reports" / "tcad_t01_input_contract.json"


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def close(left: float, right: float, *, rel_tol: float = 1.0e-9, abs_tol: float = 1.0e-15) -> bool:
    return math.isclose(float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol)


def add_check(checks: list[dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def check_contract() -> dict[str, Any]:
    config = load_json(CONFIG_PATH)
    project = load_json(PROJECT_PATH)
    s00 = load_json(S00_REPORT_PATH)
    checks: list[dict[str, Any]] = []

    device = config["device"]
    geometry = config["geometry"]
    materials = config["materials"]
    channel = materials["channel"]
    oxide = materials["bottom_oxide"]
    physics = config["physics"]
    contacts = config["contacts"]
    stages = config["bias_protocol"]["stages"]
    project_device = project["baseline_devices"]["IGZO_TFT"]
    teaching = project["teaching_baseline"]
    tcad_baseline = load_json(ROOT / "config" / "tcad_baseline.json")

    units = config["coordinate_system"]
    add_check(
        checks,
        "units:physical_coordinate_system",
        units["coordinate_unit"] == "cm"
        and units["length_unit"] == "cm"
        and units["voltage_unit"] == "V"
        and units["temperature_unit"] == "K"
        and units["density_unit"] == "cm^-3"
        and units["mobility_unit"] == "cm^2/(V*s)"
        and units["current_density_2d_unit"] == "A/cm",
        json.dumps(units, sort_keys=True),
    )
    add_check(
        checks,
        "geometry:single_gate_scope",
        device["single_gate"] is True
        and device["active_gate"] == "bottom_gate"
        and device["top_gate_present"] is False
        and device["top_oxide_present"] is False
        and "top_oxide" not in geometry["regions"]
        and geometry["forbidden_contacts"] == ["top_gate"],
        f"regions={geometry['regions']} contacts={geometry['contacts']}",
    )
    add_check(
        checks,
        "geometry:unit_conversion",
        close(device["width_cm"], device["width_um"] * 1.0e-4)
        and close(device["channel_length_cm"], device["channel_length_um"] * 1.0e-4)
        and close(device["channel_thickness_cm"], device["channel_thickness_nm"] * 1.0e-7)
        and close(geometry["bottom_oxide_thickness_cm"], 30.0 * 1.0e-7)
        and close(geometry["channel_thickness_cm"], 24.0 * 1.0e-7),
        "um/nm values convert to cm without rounding loss",
    )
    add_check(
        checks,
        "geometry:project_baseline_match",
        close(device["width_um"], project_device["w_um"])
        and close(device["channel_length_um"], project_device["l_um"])
        and close(device["channel_thickness_nm"], project_device["active_thickness_nm"])
        and close(oxide["physical_thickness_nm"], project_device["physical_gate_dielectric_nm"]),
        "W/L/tch/physical tox match config/project.json",
    )
    add_check(
        checks,
        "materials:igzo_only",
        device["material"] == "IGZO"
        and device["polarity"] == "n"
        and channel["name"] == "IGZO"
        and "SnO" not in json.dumps(config),
        "active material is n-type IGZO and config contains no SnO",
    )
    add_check(
        checks,
        "materials:teaching_sources",
        close(channel["mobility_cm2_vs"], teaching["mobility_cm2_vs"])
        and close(channel["threshold_target_v"], teaching["vth_v"])
        and close(channel["relative_permittivity"], tcad_baseline["materials"]["channel"]["relative_permittivity"])
        and channel["source_types"]["background_donor_density_cm3"] == "assumed_initialization",
        "mobility/VTH/IGZO permittivity are traced; remaining closure values are explicit assumptions",
    )
    add_check(
        checks,
        "materials:physical_vs_effective_tox",
        config["spice_effective_parameters"]["spice_effective_tox_not_used_in_t01"] is True
        and config["spice_effective_parameters"]["use_status"] == "deferred_to_compact_model"
        and close(config["spice_effective_parameters"]["effective_tox_nm"], project_device["spice_effective_tox_nm"]),
        "30 nm physical oxide remains separate from 10 nm compact-model effective TOX",
    )
    equations = physics["equations"]
    add_check(
        checks,
        "physics:minimal_electron_transport",
        equations["poisson"] == "active"
        and equations["electron_continuity"] == "active"
        and equations["drift_diffusion"] == "electron_only"
        and equations["hole_continuity"] == "inactive"
        and equations["bulk_traps"] == "inactive"
        and equations["interface_traps"] == "inactive"
        and equations["ferroelectric_polarization"] == "inactive"
        and physics["discretization"] == "Scharfetter-Gummel edge flux",
        json.dumps(equations, sort_keys=True),
    )
    add_check(
        checks,
        "physics:temperature_and_mobility",
        close(physics["temperature_k"], 300.0)
        and close(physics["mobility_cm2_vs"], teaching["mobility_cm2_vs"])
        and physics["mobility_model"] == "constant_teaching_mobility"
        and physics["diffusion_model"] == "Einstein_relation",
        "300 K constant teaching mobility with Einstein diffusion",
    )
    add_check(
        checks,
        "contacts:ideal_ohmic_baseline",
        contacts["source"]["kind"] == "ohmic"
        and contacts["drain"]["kind"] == "ohmic"
        and close(contacts["source"]["series_resistance_ohm_cm"], 0.0)
        and close(contacts["drain"]["series_resistance_ohm_cm"], 0.0)
        and contacts["bottom_gate"]["kind"] == "electrostatic_dirichlet"
        and contacts["top_boundary"]["kind"] == "natural_zero_normal_flux",
        "source/drain are ideal ohmic; non-ideal contact resistance is deferred",
    )
    add_check(
        checks,
        "mesh:two_structured_levels",
        config["mesh"]["type"] == "structured_2d"
        and set(config["mesh"]["required_levels"]) == {"coarse", "fine"}
        and set(config["mesh"]["levels"]) == {"coarse", "fine"},
        "coarse and fine structured meshes are defined in cm",
    )
    add_check(
        checks,
        "solver:continuation_order",
        config["solver"]["initialization"] == "equilibrium_poisson_then_carrier"
        and config["solver"]["continuation"] == "use_previous_converged_solution"
        and config["solver"]["never_jump_directly_to_maximum_bias"] is True,
        "equilibrium -> low VDS -> stepped VGS/VDS continuation",
    )
    add_check(
        checks,
        "solver:residual_scales_explicit",
        close(config["solver"]["poisson_absolute_error"], 1.0e-12)
        and close(config["solver"]["coupled_absolute_error"], 1.0e10)
        and close(config["solver"]["relative_error"], 1.0e-10),
        "Poisson and carrier-continuity residual scales are separated for DEVSIM",
    )
    stage_ids = [stage["id"] for stage in stages]
    add_check(
        checks,
        "bias:staged_protocol",
        stage_ids == [
            "T01_A_STAGE_0",
            "T01_A_STAGE_1",
            "T01_A_STAGE_2",
            "T01_A_STAGE_3",
        ]
        and all(stage["execution_status"] == "planned" for stage in stages)
        and stages[1]["vds_values_v"][0] == 0.0
        and stages[1]["vds_values_v"] == sorted(stages[1]["vds_values_v"])
        and stages[3]["vds_values_v"] == sorted(stages[3]["vds_values_v"]),
        "four ordered stages are frozen but not executed",
    )
    add_check(
        checks,
        "mesh:spacing_consistent",
        all(
            float(level["x_spacing_cm"]) > 0.0
            and float(level["oxide_y_spacing_cm"]) > 0.0
            and float(level["channel_y_spacing_cm"]) > 0.0
            for level in config["mesh"]["levels"].values()
        )
        and config["mesh"]["levels"]["fine"]["x_spacing_cm"] < config["mesh"]["levels"]["coarse"]["x_spacing_cm"]
        and config["mesh"]["levels"]["fine"]["channel_y_spacing_cm"] < config["mesh"]["levels"]["coarse"]["channel_y_spacing_cm"],
        "fine mesh is strictly finer in x and channel y",
    )
    add_check(
        checks,
        "gate:source_audit",
        s00["g0_decision"]["status"] == "TEACHING_BASELINE_ONLY"
        and s00["g0_decision"]["t01_permitted"] is True
        and s00["g0_decision"]["quantitative_fitting_permitted"] is False,
        "T01 is permitted only as an E2 teaching-parameter simulation",
    )

    failures = [check for check in checks if check["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "case_id": config["case_id"],
        "stage": config["stage"],
        "contract_status": "PASS" if not failures else "FAIL",
        "simulation_status": config["execution_boundary"]["simulation_status"],
        "simulation_run": config["execution_boundary"]["simulation_run"],
        "evidence_level": config["evidence_level"],
        "contract_evidence_level": config["contract_evidence_level"],
        "checks": checks,
        "outputs": config["future_outputs"],
        "evidence_boundary": config["execution_boundary"],
        "failures": failures,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        report = check_contract()
    except Exception as error:  # noqa: BLE001
        print(f"T01_A_CONTRACT_ERROR {error}", file=sys.stderr)
        return 1

    if not args.check_only:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    label = "PASS" if report["status"] == "PASS" else "FAIL"
    print(
        f"T01_A_CONTRACT_{label} checks={len(report['checks'])} "
        f"simulation={report['simulation_status']} report={REPORT_PATH}"
    )
    if report["failures"]:
        for failure in report["failures"]:
            print(f"T01_A_CONTRACT_ERROR {failure['name']}: {failure['detail']}", file=sys.stderr)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
