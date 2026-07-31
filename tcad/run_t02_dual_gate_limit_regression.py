#!/usr/bin/env python3
"""Run the T02-A disabled-top-stack limit regression and zero-bias topology smoke."""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t01_single_gate_mesh_refinement as mesh_stage  # noqa: E402


core = mesh_stage.core
DISABLED_REGIONS = ("bottom_oxide", "channel")
DISABLED_CONTACTS = ("source", "drain", "bottom_gate")
ENABLED_REGIONS = ("bottom_oxide", "channel", "top_oxide")
ENABLED_CONTACTS = ("source", "drain", "bottom_gate", "top_gate")
ENABLED_INTERFACES = ("bottom_oxide_channel", "channel_top_oxide")

DISABLED_FIELDNAMES = [
    "stage_id",
    "mode_id",
    "mesh_level",
    "vbg_v",
    "vtg_v",
    "vds_v",
    "source_current_a_per_cm",
    "drain_current_a_per_cm",
    "source_current_terminal_a",
    "drain_current_terminal_a",
    "current_imbalance_a_per_cm",
    "relative_current_imbalance",
    "center_channel_potential_v",
    "center_channel_electron_density_cm3",
    "t01_reference_abs_drain_current_a_per_cm",
    "t01_reference_center_channel_potential_v",
    "t01_reference_center_channel_electron_density_cm3",
    "relative_current_difference",
    "center_potential_difference_v",
    "center_density_relative_difference",
    "solve_seconds",
    "converged",
]

TOPOLOGY_FIELDNAMES = [
    "mode_id",
    "top_coupling_enabled",
    "mesh_level",
    "regions_json",
    "contacts_json",
    "interfaces_json",
    "node_count_with_interface_duplicates",
    "element_count",
    "dc_solve_count",
    "reported_bias_point_count",
    "maximum_absolute_terminal_current_a_per_cm",
    "maximum_absolute_potential_v",
    "state_csv",
    "vtk_file_count",
    "total_solve_seconds",
    "wall_seconds",
]

STATE_FIELDNAMES = [
    "mode_id",
    "source_v",
    "drain_v",
    "vbg_v",
    "vtg_v",
    "region",
    "x_cm",
    "y_cm",
    "x_um",
    "y_nm",
    "potential_v",
    "electron_density_cm3",
]


def same_value(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1.0e-12)


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def active_topology(device: str, active_regions: tuple[str, ...]) -> tuple[list[str], list[str], list[str]]:
    regions = sorted(
        region
        for region in core.devsim.get_region_list(device=device)
        if region in active_regions
    )
    contacts = sorted(core.devsim.get_contact_list(device=device))
    interfaces = sorted(core.devsim.get_interface_list(device=device))
    return regions, contacts, interfaces


def active_counts(device: str, regions: tuple[str, ...]) -> tuple[int, int]:
    node_count = sum(
        len(core.devsim.get_node_model_values(device=device, region=region, name="x"))
        for region in regions
    )
    element_count = sum(
        len(core.devsim.get_element_node_list(device=device, region=region))
        for region in regions
    )
    return node_count, element_count


def add_enabled_y_lines(
    mesh: str,
    runtime: dict[str, Any],
    config: dict[str, Any],
    mesh_spec: dict[str, Any],
) -> tuple[float, float, float]:
    geometry = runtime["geometry"]
    bottom_top = float(geometry["bottom_oxide_thickness_cm"])
    channel_top = bottom_top + float(geometry["channel_thickness_cm"])
    top_thickness = float(
        config["top_stack_contract"]["enabled_mode"]["top_oxide_thickness_cm"]
    )
    stack_top = channel_top + top_thickness
    refinement = mesh_spec["interface_refinement"]
    bottom_oxide_window = float(refinement["oxide_window_cm"])
    bottom_channel_window = float(refinement["channel_window_cm"])
    top_oxide_window = float(config["mesh"]["top_oxide_interface_window_cm"])
    top_channel_window = float(config["mesh"]["channel_top_interface_window_cm"])
    bulk_oxide_spacing = float(mesh_spec["oxide_y_spacing_cm"])
    bulk_channel_spacing = float(mesh_spec["channel_y_spacing_cm"])
    fine_oxide_spacing = float(refinement["oxide_spacing_cm"])
    fine_channel_spacing = float(refinement["channel_spacing_cm"])

    if bottom_channel_window + top_channel_window > channel_top - bottom_top:
        raise ValueError("bottom and top channel refinement windows overlap")
    segments = [
        (0.0, bottom_top - bottom_oxide_window, bulk_oxide_spacing),
        (bottom_top - bottom_oxide_window, bottom_top, fine_oxide_spacing),
        (bottom_top, bottom_top + bottom_channel_window, fine_channel_spacing),
    ]
    channel_bulk_start = bottom_top + bottom_channel_window
    channel_bulk_stop = channel_top - top_channel_window
    if channel_bulk_stop > channel_bulk_start:
        segments.append((channel_bulk_start, channel_bulk_stop, bulk_channel_spacing))
    segments.extend(
        [
            (channel_top - top_channel_window, channel_top, fine_channel_spacing),
            (channel_top, channel_top + top_oxide_window, fine_oxide_spacing),
            (channel_top + top_oxide_window, stack_top, bulk_oxide_spacing),
        ]
    )
    core.add_piecewise_axis_lines(mesh, "y", segments)
    return bottom_top, channel_top, stack_top


def create_enabled_mesh(
    device: str,
    runtime: dict[str, Any],
    config: dict[str, Any],
    mesh_level: str,
    mesh_spec: dict[str, Any],
) -> None:
    geometry = runtime["geometry"]
    length = float(geometry["channel_length_cm"])
    ambient_thickness = min(
        float(mesh_spec["oxide_y_spacing_cm"]),
        float(geometry["bottom_oxide_thickness_cm"]) / 3.0,
    )
    mesh = f"{device}_mesh"
    core.devsim.create_2d_mesh(mesh=mesh)
    core.add_axis_lines(mesh, "x", -ambient_thickness, 0.0, ambient_thickness)
    core.add_axis_lines(mesh, "x", 0.0, length, float(mesh_spec["x_spacing_cm"]))
    core.add_axis_lines(
        mesh, "x", length, length + ambient_thickness, ambient_thickness
    )
    core.add_axis_lines(mesh, "y", -ambient_thickness, 0.0, ambient_thickness)
    bottom_top, channel_top, stack_top = add_enabled_y_lines(
        mesh, runtime, config, mesh_spec
    )
    core.add_axis_lines(
        mesh, "y", stack_top, stack_top + ambient_thickness, ambient_thickness
    )

    core.devsim.add_2d_region(
        mesh=mesh,
        material="Air",
        region="ambient",
        xl=-ambient_thickness,
        xh=length + ambient_thickness,
        yl=-ambient_thickness,
        yh=stack_top + ambient_thickness,
    )
    core.devsim.add_2d_region(
        mesh=mesh,
        material="Al2O3",
        region="bottom_oxide",
        xl=0.0,
        xh=length,
        yl=0.0,
        yh=bottom_top,
    )
    core.devsim.add_2d_region(
        mesh=mesh,
        material="IGZO",
        region="channel",
        xl=0.0,
        xh=length,
        yl=bottom_top,
        yh=channel_top,
    )
    core.devsim.add_2d_region(
        mesh=mesh,
        material="Al2O3",
        region="top_oxide",
        xl=0.0,
        xh=length,
        yl=channel_top,
        yh=stack_top,
    )
    bloat = 1.0e-10
    core.devsim.add_2d_contact(
        mesh=mesh,
        name="bottom_gate",
        region="bottom_oxide",
        material="metal",
        xl=0.0,
        xh=length,
        yl=0.0,
        yh=0.0,
        bloat=bloat,
    )
    core.devsim.add_2d_contact(
        mesh=mesh,
        name="top_gate",
        region="top_oxide",
        material="metal",
        xl=0.0,
        xh=length,
        yl=stack_top,
        yh=stack_top,
        bloat=bloat,
    )
    for contact, x in (("source", 0.0), ("drain", length)):
        core.devsim.add_2d_contact(
            mesh=mesh,
            name=contact,
            region="channel",
            material="metal",
            xl=x,
            xh=x,
            yl=bottom_top,
            yh=channel_top,
            bloat=bloat,
        )
    core.devsim.add_2d_interface(
        mesh=mesh,
        name="bottom_oxide_channel",
        region0="bottom_oxide",
        region1="channel",
    )
    core.devsim.add_2d_interface(
        mesh=mesh,
        name="channel_top_oxide",
        region0="channel",
        region1="top_oxide",
    )
    core.devsim.finalize_mesh(mesh=mesh)
    core.devsim.create_device(mesh=mesh, device=device)


def initialize_enabled_device(
    device: str,
    runtime: dict[str, Any],
    config: dict[str, Any],
    mesh_level: str,
    mesh_spec: dict[str, Any],
) -> None:
    create_enabled_mesh(device, runtime, config, mesh_level, mesh_spec)
    materials = runtime["materials"]
    core.create_potential_equation(
        device,
        "bottom_oxide",
        float(materials["bottom_oxide"]["relative_permittivity"]),
        has_mobile_electrons=False,
    )
    core.create_potential_equation(
        device,
        "channel",
        float(materials["channel"]["relative_permittivity"]),
        has_mobile_electrons=True,
        donor_density_cm3=float(materials["channel"]["background_donor_density_cm3"]),
    )
    core.create_potential_equation(
        device,
        "top_oxide",
        float(config["top_stack_contract"]["enabled_mode"]["top_oxide_relative_permittivity"]),
        has_mobile_electrons=False,
    )
    for interface in ENABLED_INTERFACES:
        model = core.CreateContinuousInterfaceModel(device, interface, "Potential")
        core.devsim.interface_equation(
            device=device,
            interface=interface,
            name="PotentialEquation",
            interface_model=model,
            type="continuous",
        )
    for contact in ENABLED_CONTACTS:
        core.create_potential_contact(device, contact)


def set_enabled_biases(
    device: str,
    *,
    source_v: float,
    drain_v: float,
    bottom_gate_v: float,
    top_gate_v: float,
) -> None:
    for contact, value in (
        ("source", source_v),
        ("drain", drain_v),
        ("bottom_gate", bottom_gate_v),
        ("top_gate", top_gate_v),
    ):
        core.devsim.set_parameter(device=device, name=f"{contact}_bias", value=value)


def find_t01_reference(
    report: dict[str, Any], mesh_level: str, vbg_v: float, vds_v: float
) -> dict[str, Any]:
    return next(
        row
        for row in report["bias_points"]
        if row["mesh_level"] == mesh_level
        and same_value(float(row["vgs_v"]), vbg_v)
        and same_value(float(row["vds_v"]), vds_v)
    )


def run_disabled_limit(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    t01_report: dict[str, Any],
    config: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    mesh_level = config["mesh"]["source_level"]
    runtime, _ = mesh_stage.build_runtime_baseline(baseline, mesh_config, mesh_level)
    device = "t02_a_disabled_exact_t01_limit"
    solver_records: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    try:
        core.initialize_device(device, runtime, mesh_level)
        regions, contacts, interfaces = active_topology(device, DISABLED_REGIONS)
        zero = mesh_stage.stage_by_id(runtime, "T01_A_STAGE_0")
        protocol = config["bias_protocol"]["disabled_regression"]
        core.set_biases(
            device,
            source_v=float(zero["source_v"]),
            drain_v=float(zero["drain_v"]),
            bottom_gate_v=float(zero["bottom_gate_v"]),
        )
        solver_records.append(
            core.solve_dc(
                device,
                runtime,
                "T02_A_DISABLED_POISSON_ZERO_BIAS",
                coupled=False,
            )
        )
        core.create_transport(device, runtime)
        solver_records.append(
            core.solve_dc(
                device,
                runtime,
                "T02_A_DISABLED_COUPLED_ZERO_BIAS",
                coupled=True,
            )
        )

        last_low_vds: dict[str, Any] | None = None
        for vds_v in [float(value) for value in protocol["low_vds_values_v"]]:
            core.set_biases(
                device,
                source_v=float(config["bias_protocol"]["source_v"]),
                drain_v=vds_v,
                bottom_gate_v=0.0,
            )
            last_low_vds = core.solve_dc(
                device,
                runtime,
                f"T02_A_DISABLED_LOW_VDS_{vds_v:.6g}_V",
                coupled=True,
            )
            solver_records.append(last_low_vds)
        if last_low_vds is None:
            raise RuntimeError("disabled-limit low-VDS ladder is empty")

        fixed_vds = float(protocol["vds_v"])
        rows: list[dict[str, Any]] = []
        for index, vbg_v in enumerate(
            float(value) for value in protocol["bottom_gate_continuation_v"]
        ):
            if index == 0 and same_value(vbg_v, 0.0):
                solve_record = last_low_vds
            else:
                core.set_biases(
                    device,
                    source_v=float(config["bias_protocol"]["source_v"]),
                    drain_v=fixed_vds,
                    bottom_gate_v=vbg_v,
                )
                solve_record = core.solve_dc(
                    device,
                    runtime,
                    f"T02_A_DISABLED_VBG_{vbg_v:.6g}_V",
                    coupled=True,
                )
                solver_records.append(solve_record)
            row = core.collect_bias_row(
                device,
                runtime,
                mesh_level=mesh_level,
                stage_id="T02_A_DISABLED_LIMIT",
                vds_v=fixed_vds,
                vgs_v=vbg_v,
                solve_record=solve_record,
            )
            reference = find_t01_reference(t01_report, mesh_level, vbg_v, fixed_vds)
            current = abs(float(row["drain_current_a_per_cm"]))
            reference_current = abs(float(reference["drain_current_a_per_cm"]))
            density = float(row["center_channel_electron_density_cm3"])
            reference_density = float(reference["center_channel_electron_density_cm3"])
            rows.append(
                {
                    "stage_id": "T02_A_DISABLED_LIMIT",
                    "mode_id": config["top_stack_contract"]["disabled_mode"]["mode_id"],
                    "mesh_level": mesh_level,
                    "vbg_v": vbg_v,
                    "vtg_v": None,
                    "vds_v": fixed_vds,
                    "source_current_a_per_cm": row["source_current_a_per_cm"],
                    "drain_current_a_per_cm": row["drain_current_a_per_cm"],
                    "source_current_terminal_a": row["source_current_terminal_a"],
                    "drain_current_terminal_a": row["drain_current_terminal_a"],
                    "current_imbalance_a_per_cm": row["current_imbalance_a_per_cm"],
                    "relative_current_imbalance": row["relative_current_imbalance"],
                    "center_channel_potential_v": row["center_channel_potential_v"],
                    "center_channel_electron_density_cm3": density,
                    "t01_reference_abs_drain_current_a_per_cm": reference_current,
                    "t01_reference_center_channel_potential_v": reference[
                        "center_channel_potential_v"
                    ],
                    "t01_reference_center_channel_electron_density_cm3": reference_density,
                    "relative_current_difference": abs(current - reference_current)
                    / max(current, reference_current, 1.0e-300),
                    "center_potential_difference_v": abs(
                        float(row["center_channel_potential_v"])
                        - float(reference["center_channel_potential_v"])
                    ),
                    "center_density_relative_difference": abs(density - reference_density)
                    / max(abs(density), abs(reference_density), 1.0e-300),
                    "solve_seconds": solve_record["elapsed_seconds"],
                    "converged": solve_record["converged"],
                }
            )

        node_count, element_count = active_counts(device, DISABLED_REGIONS)
        summary = {
            "mode_id": config["top_stack_contract"]["disabled_mode"]["mode_id"],
            "top_coupling_enabled": False,
            "mesh_level": mesh_level,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(solver_records),
            "reported_bias_point_count": len(rows),
            "maximum_absolute_terminal_current_a_per_cm": max(
                max(abs(float(row["source_current_a_per_cm"])), abs(float(row["drain_current_a_per_cm"])))
                for row in rows
            ),
            "maximum_absolute_potential_v": max(
                abs(float(row["center_channel_potential_v"])) for row in rows
            ),
            "state_csv": "",
            "vtk_file_count": 0,
            "total_solve_seconds": sum(float(record["elapsed_seconds"]) for record in solver_records),
            "wall_seconds": time.perf_counter() - wall_start,
        }
        return rows, summary, solver_records
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def collect_enabled_state(
    device: str, mode_id: str, bias: dict[str, Any]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in ENABLED_REGIONS:
        xs = core.devsim.get_node_model_values(device=device, region=region, name="x")
        ys = core.devsim.get_node_model_values(device=device, region=region, name="y")
        potentials = core.devsim.get_node_model_values(
            device=device, region=region, name="Potential"
        )
        electrons = (
            core.devsim.get_node_model_values(
                device=device, region=region, name="Electrons"
            )
            if region == "channel"
            else [None] * len(xs)
        )
        for x, y, potential, electron in zip(xs, ys, potentials, electrons, strict=True):
            rows.append(
                {
                    "mode_id": mode_id,
                    "source_v": bias["source_v"],
                    "drain_v": bias["drain_v"],
                    "vbg_v": bias["bottom_gate_v"],
                    "vtg_v": bias["top_gate_v"],
                    "region": region,
                    "x_cm": float(x),
                    "y_cm": float(y),
                    "x_um": float(x) * 1.0e4,
                    "y_nm": float(y) * 1.0e7,
                    "potential_v": float(potential),
                    "electron_density_cm3": "" if electron is None else float(electron),
                }
            )
    return rows


def run_enabled_zero_bias(
    baseline: dict[str, Any],
    mesh_config: dict[str, Any],
    config: dict[str, Any],
    run_dir: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    mesh_level = config["mesh"]["source_level"]
    runtime, mesh_spec = mesh_stage.build_runtime_baseline(
        baseline, mesh_config, mesh_level
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = config[
        "top_stack_contract"
    ]["enabled_mode"]["top_oxide_thickness_cm"]
    device = "t02_a_enabled_zero_bias"
    solver_records: list[dict[str, Any]] = []
    wall_start = time.perf_counter()
    try:
        initialize_enabled_device(device, runtime, config, mesh_level, mesh_spec)
        regions, contacts, interfaces = active_topology(device, ENABLED_REGIONS)
        bias = config["bias_protocol"]["enabled_zero_bias_smoke"]
        set_enabled_biases(
            device,
            source_v=float(bias["source_v"]),
            drain_v=float(bias["drain_v"]),
            bottom_gate_v=float(bias["bottom_gate_v"]),
            top_gate_v=float(bias["top_gate_v"]),
        )
        solver_records.append(
            core.solve_dc(
                device,
                runtime,
                "T02_A_ENABLED_POISSON_ZERO_BIAS",
                coupled=False,
            )
        )
        core.create_transport(device, runtime)
        solver_records.append(
            core.solve_dc(
                device,
                runtime,
                "T02_A_ENABLED_COUPLED_ZERO_BIAS",
                coupled=True,
            )
        )

        source_current = float(
            core.devsim.get_contact_current(
                device=device,
                contact="source",
                equation="ElectronContinuityEquation",
            )
        )
        drain_current = float(
            core.devsim.get_contact_current(
                device=device,
                contact="drain",
                equation="ElectronContinuityEquation",
            )
        )
        mode_id = config["top_stack_contract"]["enabled_mode"]["mode_id"]
        state_rows = collect_enabled_state(device, mode_id, bias)
        state_path = run_dir / "t02_a_enabled_zero_bias_nodes.csv"
        core.write_csv(state_path, state_rows, STATE_FIELDNAMES)
        vtk_base = run_dir / "t02_a_enabled_zero_bias"
        core.devsim.write_devices(file=str(vtk_base), device=device, type="vtk")
        vtk_files: list[dict[str, str]] = []
        for path in sorted(run_dir.glob(f"{vtk_base.name}*")):
            if path == state_path:
                continue
            core.normalize_text_newline(path)
            vtk_files.append(
                {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            )

        node_count, element_count = active_counts(device, ENABLED_REGIONS)
        max_potential = max(abs(float(row["potential_v"])) for row in state_rows)
        summary = {
            "mode_id": mode_id,
            "top_coupling_enabled": True,
            "mesh_level": mesh_level,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "dc_solve_count": len(solver_records),
            "reported_bias_point_count": 1,
            "maximum_absolute_terminal_current_a_per_cm": max(
                abs(source_current), abs(drain_current)
            ),
            "maximum_absolute_potential_v": max_potential,
            "state_csv": str(state_path.relative_to(ROOT)),
            "vtk_file_count": len(vtk_files),
            "total_solve_seconds": sum(float(record["elapsed_seconds"]) for record in solver_records),
            "wall_seconds": time.perf_counter() - wall_start,
        }
        state_entry = {
            "mode_id": mode_id,
            "bias": {
                "source_v": float(bias["source_v"]),
                "drain_v": float(bias["drain_v"]),
                "bottom_gate_v": float(bias["bottom_gate_v"]),
                "top_gate_v": float(bias["top_gate_v"]),
            },
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "node_count_with_interface_duplicates": len(state_rows),
            "state_csv": str(state_path.relative_to(ROOT)),
            "state_csv_sha256": core.sha256(state_path),
            "vtk_base": str(vtk_base.relative_to(ROOT)),
            "vtk_files": vtk_files,
            "source_current_a_per_cm": source_current,
            "drain_current_a_per_cm": drain_current,
            "maximum_absolute_potential_v": max_potential,
        }
        return summary, solver_records, state_entry
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)


def topology_csv_row(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode_id": summary["mode_id"],
        "top_coupling_enabled": summary["top_coupling_enabled"],
        "mesh_level": summary["mesh_level"],
        "regions_json": json.dumps(summary["regions"], separators=(",", ":")),
        "contacts_json": json.dumps(summary["contacts"], separators=(",", ":")),
        "interfaces_json": json.dumps(summary["interfaces"], separators=(",", ":")),
        "node_count_with_interface_duplicates": summary[
            "node_count_with_interface_duplicates"
        ],
        "element_count": summary["element_count"],
        "dc_solve_count": summary["dc_solve_count"],
        "reported_bias_point_count": summary["reported_bias_point_count"],
        "maximum_absolute_terminal_current_a_per_cm": summary[
            "maximum_absolute_terminal_current_a_per_cm"
        ],
        "maximum_absolute_potential_v": summary["maximum_absolute_potential_v"],
        "state_csv": summary["state_csv"],
        "vtk_file_count": summary["vtk_file_count"],
        "total_solve_seconds": summary["total_solve_seconds"],
        "wall_seconds": summary["wall_seconds"],
    }


def assess(
    config: dict[str, Any],
    contract_report: dict[str, Any],
    t01_report: dict[str, Any],
    disabled_rows: list[dict[str, Any]],
    topology: list[dict[str, Any]],
    solver_log: dict[str, Any],
    state_entry: dict[str, Any] | None,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    disabled = next((row for row in topology if not row["top_coupling_enabled"]), None)
    enabled = next((row for row in topology if row["top_coupling_enabled"]), None)
    solver_records = [
        record
        for run in solver_log["runs"]
        for record in run.get("solver_records", [])
    ]

    add_check(
        checks,
        "t02_a_contract_and_t01_gate_passed",
        contract_report.get("contract_status") == "PASS"
        and t01_report.get("status") == "PASS"
        and t01_report.get("t01_completion", {}).get("t02_stage_permitted_next") is True,
        (
            f"contract={contract_report.get('contract_status')} "
            f"t01={t01_report.get('status')} next="
            f"{t01_report.get('t01_completion', {}).get('t02_stage_permitted_next')}"
        ),
    )
    add_check(
        checks,
        "all_configured_dc_solves_converged",
        len(solver_records) == int(acceptance["required_total_dc_solve_count"])
        and all(bool(record["converged"]) for record in solver_records),
        f"records={len(solver_records)} expected={acceptance['required_total_dc_solve_count']}",
    )
    add_check(
        checks,
        "disabled_limit_uses_exact_t01_topology",
        disabled is not None
        and disabled["regions"] == sorted(acceptance["required_disabled_regions"])
        and disabled["contacts"] == sorted(acceptance["required_disabled_contacts"])
        and disabled["interfaces"] == ["bottom_oxide_channel"]
        and disabled["dc_solve_count"] == acceptance["required_disabled_dc_solve_count"],
        f"topology={disabled}",
    )
    add_check(
        checks,
        "enabled_zero_bias_topology_contains_top_stack",
        enabled is not None
        and enabled["regions"] == sorted(acceptance["required_enabled_regions"])
        and enabled["contacts"] == sorted(acceptance["required_enabled_contacts"])
        and enabled["interfaces"] == sorted(ENABLED_INTERFACES)
        and enabled["dc_solve_count"] == acceptance["required_enabled_zero_bias_dc_solve_count"]
        and disabled is not None
        and enabled["node_count_with_interface_duplicates"]
        > disabled["node_count_with_interface_duplicates"],
        f"topology={enabled}",
    )
    expected_vbg = [
        float(value) for value in acceptance["required_disabled_bottom_gate_values_v"]
    ]
    add_check(
        checks,
        "disabled_regression_grid_completed",
        len(disabled_rows) == acceptance["required_disabled_reported_point_count"]
        and [float(row["vbg_v"]) for row in disabled_rows] == expected_vbg
        and all(row["vtg_v"] is None for row in disabled_rows),
        f"rows={len(disabled_rows)} VBG={[row['vbg_v'] for row in disabled_rows]}",
    )
    max_imbalance = max(
        float(row["relative_current_imbalance"]) for row in disabled_rows
    )
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in disabled_rows]
    add_check(
        checks,
        "disabled_current_conservation_and_monotonicity",
        max_imbalance <= acceptance["maximum_relative_terminal_current_imbalance"]
        and all(next_value >= value for value, next_value in zip(currents, currents[1:])),
        f"max_imbalance={max_imbalance:.6e} currents={currents}",
    )
    max_current_difference = max(
        float(row["relative_current_difference"]) for row in disabled_rows
    )
    max_potential_difference = max(
        float(row["center_potential_difference_v"]) for row in disabled_rows
    )
    max_density_difference = max(
        float(row["center_density_relative_difference"]) for row in disabled_rows
    )
    add_check(
        checks,
        "disabled_limit_reproduces_t01_terminal_and_internal_state",
        max_current_difference
        <= acceptance["maximum_disabled_t01_relative_current_difference"]
        and max_potential_difference
        <= acceptance["maximum_disabled_t01_center_potential_difference_v"]
        and max_density_difference
        <= acceptance["maximum_disabled_t01_center_density_relative_difference"],
        (
            f"max_current_rel={max_current_difference:.6e} "
            f"max_potential_v={max_potential_difference:.6e} "
            f"max_density_rel={max_density_difference:.6e}"
        ),
    )
    add_check(
        checks,
        "enabled_zero_bias_equilibrium_is_finite_and_current_free",
        enabled is not None
        and math.isfinite(float(enabled["maximum_absolute_terminal_current_a_per_cm"]))
        and enabled["maximum_absolute_terminal_current_a_per_cm"]
        <= acceptance["maximum_enabled_zero_bias_absolute_terminal_current_a_per_cm"]
        and enabled["maximum_absolute_potential_v"]
        <= acceptance["maximum_enabled_zero_bias_absolute_potential_v"],
        (
            f"max_current={enabled['maximum_absolute_terminal_current_a_per_cm'] if enabled else None} "
            f"max_potential={enabled['maximum_absolute_potential_v'] if enabled else None}"
        ),
    )
    state_path = ROOT / state_entry["state_csv"] if state_entry else None
    vtk_files = state_entry["vtk_files"] if state_entry else []
    add_check(
        checks,
        "enabled_zero_bias_state_and_vtk_are_persisted",
        state_entry is not None
        and state_path is not None
        and state_path.is_file()
        and state_path.stat().st_size > 0
        and state_entry["regions"] == sorted(acceptance["required_enabled_regions"])
        and bool(vtk_files)
        and all((ROOT / item["path"]).is_file() for item in vtk_files),
        f"state={state_path} vtk_files={len(vtk_files)}",
    )
    add_check(
        checks,
        "evidence_boundary_keeps_t02_incomplete",
        "T02 complete" in config["evidence_boundary"]["prohibited_claims"]
        and "T02-B" in config["evidence_boundary"]["next_gate"],
        config["evidence_boundary"]["next_gate"],
    )
    failures = [name for name, value in checks.items() if value["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "maximum_disabled_t01_relative_current_difference": max_current_difference,
        "maximum_disabled_t01_center_potential_difference_v": max_potential_difference,
        "maximum_disabled_t01_center_density_relative_difference": max_density_difference,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_t02_a_dual_gate_contract.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = core.load_json(config_path)
    dependency = config["dependencies"]
    baseline_path = ROOT / dependency["t01_baseline_config"]
    mesh_config_path = ROOT / dependency["t01_mesh_config"]
    t01_report_path = ROOT / dependency["t01_extraction_report"]
    t01_check_path = ROOT / dependency["t01_extraction_check_report"]
    contract_report_path = ROOT / config["outputs"]["contract_report"]
    baseline = core.load_json(baseline_path)
    mesh_config = core.load_json(mesh_config_path)
    t01_report = core.load_json(t01_report_path)
    t01_check = core.load_json(t01_check_path)
    contract_report = core.load_json(contract_report_path)

    if contract_report.get("contract_status") != "PASS":
        raise RuntimeError("T02-A input contract is not PASS")
    if contract_report.get("config", {}).get("sha256") != core.sha256(config_path):
        raise RuntimeError("T02-A contract report does not match the current config")
    if (
        t01_report.get("status") != dependency["required_t01_extraction_status"]
        or t01_check.get("status") != dependency["required_t01_extraction_check_status"]
        or t01_report.get("t01_completion", {}).get("complete_t01_numerical_stage_gate")
        != dependency["required_t01_complete_gate"]
        or t01_report.get("t01_completion", {}).get("t02_stage_permitted_next")
        is not dependency["require_t02_stage_permitted_next"]
    ):
        raise RuntimeError("complete T01 dependency gate is not open")

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    disabled_csv_path = ROOT / outputs["disabled_regression_csv"]
    topology_csv_path = ROOT / outputs["topology_summary_csv"]
    report_path = ROOT / outputs["report"]

    input_paths = {
        "t02_a_config": config_path,
        "t02_a_contract_report": contract_report_path,
        "t01_baseline_config": baseline_path,
        "t01_mesh_config": mesh_config_path,
        "t01_extraction_report": t01_report_path,
        "t01_extraction_check_report": t01_check_path,
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in input_paths.items()
        },
        "t02_a_contract": config,
        "t01_baseline": baseline,
        "t01_mesh_source": mesh_config,
    }
    core.write_json(snapshot_path, snapshot)

    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t02-a-regression",
        "validation_command": "make t02-a-regression-check",
        "runs": [],
        "errors": [],
    }
    disabled_rows: list[dict[str, Any]] = []
    topology: list[dict[str, Any]] = []
    state_entry: dict[str, Any] | None = None
    caught_error: Exception | None = None
    try:
        disabled_rows, disabled_summary, disabled_records = run_disabled_limit(
            baseline, mesh_config, t01_report, config
        )
        topology.append(disabled_summary)
        solver_log["runs"].append(
            {
                "mode_id": disabled_summary["mode_id"],
                "status": "PASS",
                "solver_records": disabled_records,
            }
        )
        enabled_summary, enabled_records, state_entry = run_enabled_zero_bias(
            baseline, mesh_config, config, run_dir
        )
        topology.append(enabled_summary)
        solver_log["runs"].append(
            {
                "mode_id": enabled_summary["mode_id"],
                "status": "PASS",
                "solver_records": enabled_records,
            }
        )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
        solver_log["runs"].append({"mode_id": "incomplete", "status": "FAIL"})

    core.write_csv(disabled_csv_path, disabled_rows, DISABLED_FIELDNAMES)
    core.write_csv(
        topology_csv_path,
        [topology_csv_row(summary) for summary in topology],
        TOPOLOGY_FIELDNAMES,
    )
    state_manifest = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "entries": [] if state_entry is None else [state_entry],
    }
    core.write_json(state_manifest_path, state_manifest)
    core.write_json(solver_log_path, solver_log)

    if caught_error is None and len(topology) == 2 and state_entry is not None:
        assessment = assess(
            config,
            contract_report,
            t01_report,
            disabled_rows,
            topology,
            solver_log,
            state_entry,
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {
                "simulation_exception": {
                    "status": "FAIL",
                    "detail": repr(caught_error),
                }
            },
            "failures": ["simulation_exception"],
            "maximum_relative_terminal_current_imbalance": None,
            "maximum_disabled_t01_relative_current_difference": None,
            "maximum_disabled_t01_center_potential_difference_v": None,
            "maximum_disabled_t01_center_density_relative_difference": None,
        }
    passed = assessment["status"] == "PASS"
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": (
            "2D n-IGZO electron-only drift-diffusion teaching model; exact-T01 "
            "disabled-top-stack regression plus enabled-topology all-zero-bias smoke"
        ),
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "contract_command": "make t02-a-contract-check",
            "command": "make t02-a-regression",
            "validation_command": "make t02-a-regression-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "disabled_regression_points": disabled_rows,
        "topology": topology,
        "state_outputs": state_manifest["entries"],
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {
            key: value
            for key, value in assessment.items()
            if key not in {"status", "checks", "failures"}
        },
        "t02_a_completion": {
            "status": "PASS" if passed else "FAIL",
            "input_contract_frozen": passed,
            "disabled_top_stack_returns_t01": passed,
            "enabled_zero_bias_topology_smoke": passed,
            "t02_b_minimal_bias_family_permitted_next": passed,
            "t02_complete": False,
            "nonzero_dual_gate_coupling_verified": False,
            "experimental_calibration_permitted": False,
        },
        "limitations": [
            "The disabled limit omits the entire top stack and restores the exact T01 natural top boundary; VTG=0 V on an enabled top stack is not equivalent to disabling coupling.",
            "The enabled top stack is exercised only at all-zero-bias equilibrium in T02-A, so no nonzero dual-gate current, Delta VTH, gm, or coupling slope is established.",
            "The symmetric 30 nm Al2O3 top dielectric is a teaching extension from T00 and is not documented as part of the stated fabricated baseline.",
            "Traps, non-ideal contacts, recombination, ferroelectric polarization, experimental calibration, and uncertainty remain absent.",
        ],
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T02_A_LIMIT_REGRESSION_{report['status']} "
        f"disabled_points={len(disabled_rows)} dc_solves="
        f"{sum(len(run.get('solver_records', [])) for run in solver_log['runs'])} "
        f"report={report_path}"
    )
    if caught_error is not None:
        print(f"T02_A_LIMIT_REGRESSION_ERROR {caught_error}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
