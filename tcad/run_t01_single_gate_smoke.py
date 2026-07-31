#!/usr/bin/env python3
"""Run the limited T01-B single-gate IGZO drift-diffusion smoke case."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DEVSIM_MATH_LIBS", "liblapack.so.3:libblas.so.3")

import devsim  # noqa: E402
from devsim.python_packages.model_create import (  # noqa: E402
    CreateContinuousInterfaceModel,
    CreateEdgeModel,
    CreateEdgeModelDerivatives,
    CreateNodeModel,
    CreateNodeModelDerivative,
    CreateSolution,
)
from devsim.python_packages.simple_dd import CreateBernoulli  # noqa: E402


EPSILON_0_F_PER_CM = 8.8541878128e-14
ELECTRON_CHARGE_C = 1.602176634e-19
ACTIVE_REGIONS = ("bottom_oxide", "channel")
CONTACTS = ("source", "drain", "bottom_gate")


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, default=str) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)


def normalize_text_newline(path: Path) -> None:
    content = path.read_bytes()
    normalized = content.rstrip(b"\n") + b"\n"
    if content != normalized:
        path.write_bytes(normalized)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_axis_lines(mesh: str, direction: str, start: float, stop: float, spacing: float) -> None:
    count = max(1, math.ceil((stop - start) / spacing))
    for index in range(count + 1):
        position = start + (stop - start) * index / count
        devsim.add_2d_mesh_line(mesh=mesh, dir=direction, pos=position, ps=spacing)


def create_mesh(device: str, baseline: dict[str, Any], mesh_level: str) -> None:
    geometry = baseline["geometry"]
    mesh_config = baseline["mesh"]["levels"][mesh_level]
    length = float(geometry["channel_length_cm"])
    oxide_top = float(geometry["bottom_oxide_thickness_cm"])
    channel_top = oxide_top + float(geometry["channel_thickness_cm"])
    ambient_thickness = min(
        float(mesh_config["oxide_y_spacing_cm"]),
        float(geometry["bottom_oxide_thickness_cm"]) / 3.0,
    )
    mesh = f"{device}_mesh"

    devsim.create_2d_mesh(mesh=mesh)
    add_axis_lines(mesh, "x", -ambient_thickness, 0.0, ambient_thickness)
    add_axis_lines(mesh, "x", 0.0, length, float(mesh_config["x_spacing_cm"]))
    add_axis_lines(mesh, "x", length, length + ambient_thickness, ambient_thickness)
    add_axis_lines(mesh, "y", -ambient_thickness, 0.0, ambient_thickness)
    add_axis_lines(mesh, "y", 0.0, oxide_top, float(mesh_config["oxide_y_spacing_cm"]))
    add_axis_lines(mesh, "y", oxide_top, channel_top, float(mesh_config["channel_y_spacing_cm"]))

    # DEVSIM attaches contacts at region interfaces. This buffer has no equations.
    devsim.add_2d_region(
        mesh=mesh,
        material="Air",
        region="ambient",
        xl=-ambient_thickness,
        xh=length + ambient_thickness,
        yl=-ambient_thickness,
        yh=channel_top,
    )
    devsim.add_2d_region(
        mesh=mesh,
        material="Al2O3",
        region="bottom_oxide",
        xl=0.0,
        xh=length,
        yl=0.0,
        yh=oxide_top,
    )
    devsim.add_2d_region(
        mesh=mesh,
        material="IGZO",
        region="channel",
        xl=0.0,
        xh=length,
        yl=oxide_top,
        yh=channel_top,
    )
    bloat = 1.0e-10
    devsim.add_2d_contact(
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
    for contact, x in (("source", 0.0), ("drain", length)):
        devsim.add_2d_contact(
            mesh=mesh,
            name=contact,
            region="channel",
            material="metal",
            xl=x,
            xh=x,
            yl=oxide_top,
            yh=channel_top,
            bloat=bloat,
        )
    devsim.add_2d_interface(
        mesh=mesh,
        name="bottom_oxide_channel",
        region0="bottom_oxide",
        region1="channel",
    )
    devsim.finalize_mesh(mesh=mesh)
    devsim.create_device(mesh=mesh, device=device)


def create_potential_equation(
    device: str,
    region: str,
    relative_permittivity: float,
    *,
    has_mobile_electrons: bool,
    donor_density_cm3: float | None = None,
) -> None:
    CreateSolution(device, region, "Potential")
    devsim.set_parameter(
        device=device,
        region=region,
        name="Permittivity",
        value=EPSILON_0_F_PER_CM * relative_permittivity,
    )
    devsim.set_parameter(
        device=device,
        region=region,
        name="ElectronCharge",
        value=ELECTRON_CHARGE_C,
    )
    field = "(Potential@n0-Potential@n1)*EdgeInverseLength"
    CreateEdgeModel(device, region, "ElectricField", field)
    CreateEdgeModelDerivatives(device, region, "ElectricField", field, "Potential")
    flux = "Permittivity*ElectricField"
    CreateEdgeModel(device, region, "PotentialEdgeFlux", flux)
    CreateEdgeModelDerivatives(device, region, "PotentialEdgeFlux", flux, "Potential")

    if not has_mobile_electrons:
        devsim.equation(
            device=device,
            region=region,
            name="PotentialEquation",
            variable_name="Potential",
            edge_model="PotentialEdgeFlux",
            variable_update="default",
        )
        return

    if donor_density_cm3 is None:
        raise ValueError("channel donor density is required")
    CreateSolution(device, region, "Electrons")
    CreateNodeModel(device, region, "NetDoping", f"{donor_density_cm3:.15e}")
    devsim.set_node_values(device=device, region=region, name="Electrons", init_from="NetDoping")
    charge = "ElectronCharge*(Electrons-NetDoping)"
    CreateNodeModel(device, region, "PotentialNodeCharge", charge)
    CreateNodeModelDerivative(device, region, "PotentialNodeCharge", charge, "Electrons")
    devsim.equation(
        device=device,
        region=region,
        name="PotentialEquation",
        variable_name="Potential",
        node_model="PotentialNodeCharge",
        edge_model="PotentialEdgeFlux",
        variable_update="log_damp",
    )


def create_potential_contact(device: str, contact: str) -> None:
    model = f"{contact}_potential_bc"
    expression = f"Potential-{contact}_bias"
    devsim.contact_node_model(device=device, contact=contact, name=model, equation=expression)
    devsim.contact_node_model(
        device=device,
        contact=contact,
        name=f"{model}:Potential",
        equation="1",
    )
    devsim.contact_equation(
        device=device,
        contact=contact,
        name="PotentialEquation",
        node_model=model,
        edge_charge_model="PotentialEdgeFlux",
    )


def create_transport(device: str, baseline: dict[str, Any]) -> None:
    channel = baseline["materials"]["channel"]
    contacts = baseline["contacts"]
    devsim.set_parameter(
        device=device,
        region="channel",
        name="V_t",
        value=float(baseline["physics"]["thermal_voltage_v"]),
    )
    devsim.set_parameter(
        device=device,
        region="channel",
        name="mu_n",
        value=float(channel["mobility_cm2_vs"]),
    )
    CreateBernoulli(device, "channel")
    current = (
        "ElectronCharge*mu_n*EdgeInverseLength*V_t*"
        "kahan3(Electrons@n1*Bern01, Electrons@n1*vdiff, -Electrons@n0*Bern01)"
    )
    CreateEdgeModel(device, "channel", "ElectronCurrent", current)
    for variable in ("Electrons", "Potential"):
        CreateEdgeModelDerivatives(device, "channel", "ElectronCurrent", current, variable)
    devsim.equation(
        device=device,
        region="channel",
        name="ElectronContinuityEquation",
        variable_name="Electrons",
        edge_model="ElectronCurrent",
        variable_update="positive",
    )
    for contact in ("source", "drain"):
        density = float(contacts[contact]["electron_density_cm3"])
        model = f"{contact}_electron_bc"
        expression = f"Electrons-{density:.15e}"
        devsim.contact_node_model(device=device, contact=contact, name=model, equation=expression)
        devsim.contact_node_model(
            device=device,
            contact=contact,
            name=f"{model}:Electrons",
            equation="1",
        )
        devsim.contact_equation(
            device=device,
            contact=contact,
            name="ElectronContinuityEquation",
            node_model=model,
            edge_current_model="ElectronCurrent",
        )


def initialize_device(device: str, baseline: dict[str, Any], mesh_level: str) -> None:
    create_mesh(device, baseline, mesh_level)
    materials = baseline["materials"]
    create_potential_equation(
        device,
        "bottom_oxide",
        float(materials["bottom_oxide"]["relative_permittivity"]),
        has_mobile_electrons=False,
    )
    create_potential_equation(
        device,
        "channel",
        float(materials["channel"]["relative_permittivity"]),
        has_mobile_electrons=True,
        donor_density_cm3=float(materials["channel"]["background_donor_density_cm3"]),
    )
    interface_model = CreateContinuousInterfaceModel(device, "bottom_oxide_channel", "Potential")
    devsim.interface_equation(
        device=device,
        interface="bottom_oxide_channel",
        name="PotentialEquation",
        interface_model=interface_model,
        type="continuous",
    )
    for contact in CONTACTS:
        create_potential_contact(device, contact)


def set_biases(device: str, *, source_v: float, drain_v: float, bottom_gate_v: float) -> None:
    for contact, value in (
        ("source", source_v),
        ("drain", drain_v),
        ("bottom_gate", bottom_gate_v),
    ):
        devsim.set_parameter(device=device, name=f"{contact}_bias", value=value)


def solve_dc(device: str, baseline: dict[str, Any], label: str, *, coupled: bool) -> dict[str, Any]:
    solver = baseline["solver"]
    absolute_error = float(
        solver["coupled_absolute_error"] if coupled else solver["poisson_absolute_error"]
    )
    start = time.perf_counter()
    info = devsim.solve(
        type=solver["type"],
        absolute_error=absolute_error,
        relative_error=float(solver["relative_error"]),
        maximum_iterations=int(solver["maximum_iterations"]),
        solver_type=solver["solver_type"],
        info=True,
    )
    elapsed = time.perf_counter() - start
    converged = isinstance(info, dict) and bool(info.get("converged", False))
    record = {
        "label": label,
        "absolute_error": absolute_error,
        "elapsed_seconds": elapsed,
        "converged": converged,
        "solver_info": info,
    }
    if not converged:
        raise RuntimeError(f"{label} did not converge: {json.dumps(info, default=str)}")
    return record


def nearest_channel_state(device: str, baseline: dict[str, Any]) -> dict[str, float]:
    geometry = baseline["geometry"]
    target_x = float(geometry["channel_length_cm"]) / 2.0
    target_y = float(geometry["bottom_oxide_thickness_cm"]) + float(geometry["channel_thickness_cm"]) / 2.0
    xs = devsim.get_node_model_values(device=device, region="channel", name="x")
    ys = devsim.get_node_model_values(device=device, region="channel", name="y")
    potentials = devsim.get_node_model_values(device=device, region="channel", name="Potential")
    electrons = devsim.get_node_model_values(device=device, region="channel", name="Electrons")
    index = min(range(len(xs)), key=lambda item: (xs[item] - target_x) ** 2 + (ys[item] - target_y) ** 2)
    return {
        "center_channel_potential_v": float(potentials[index]),
        "center_channel_electron_density_cm3": float(electrons[index]),
    }


def collect_bias_row(
    device: str,
    baseline: dict[str, Any],
    *,
    mesh_level: str,
    stage_id: str,
    vds_v: float,
    vgs_v: float,
    solve_record: dict[str, Any],
) -> dict[str, Any]:
    source_current = float(
        devsim.get_contact_current(
            device=device,
            contact="source",
            equation="ElectronContinuityEquation",
        )
    )
    drain_current = float(
        devsim.get_contact_current(
            device=device,
            contact="drain",
            equation="ElectronContinuityEquation",
        )
    )
    magnitude = max(abs(source_current), abs(drain_current), 1.0e-300)
    center = nearest_channel_state(device, baseline)
    width_cm = float(baseline["device"]["width_cm"])
    return {
        "mesh_level": mesh_level,
        "stage_id": stage_id,
        "vgs_v": vgs_v,
        "vds_v": vds_v,
        "source_current_a_per_cm": source_current,
        "drain_current_a_per_cm": drain_current,
        "source_current_terminal_a": source_current * width_cm,
        "drain_current_terminal_a": drain_current * width_cm,
        "current_imbalance_a_per_cm": source_current + drain_current,
        "relative_current_imbalance": abs(source_current + drain_current) / magnitude,
        "center_channel_potential_v": center["center_channel_potential_v"],
        "center_channel_electron_density_cm3": center["center_channel_electron_density_cm3"],
        "solve_seconds": float(solve_record["elapsed_seconds"]),
        "converged": bool(solve_record["converged"]),
    }


def collect_state_nodes(device: str, mesh_level: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for region in ACTIVE_REGIONS:
        xs = devsim.get_node_model_values(device=device, region=region, name="x")
        ys = devsim.get_node_model_values(device=device, region=region, name="y")
        potentials = devsim.get_node_model_values(device=device, region=region, name="Potential")
        electrons = (
            devsim.get_node_model_values(device=device, region=region, name="Electrons")
            if region == "channel"
            else [None] * len(xs)
        )
        for x, y, potential, electron in zip(xs, ys, potentials, electrons, strict=True):
            rows.append(
                {
                    "mesh_level": mesh_level,
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


def node_and_element_counts(device: str) -> tuple[int, int]:
    node_count = sum(
        len(devsim.get_node_model_values(device=device, region=region, name="x"))
        for region in ACTIVE_REGIONS
    )
    element_count = sum(
        len(devsim.get_element_node_list(device=device, region=region))
        for region in ACTIVE_REGIONS
    )
    return node_count, element_count


def run_mesh(
    baseline: dict[str, Any],
    smoke: dict[str, Any],
    mesh_level: str,
    run_dir: Path,
) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    device = f"t01_b_{mesh_level}"
    solver_records: list[dict[str, Any]] = []
    try:
        initialize_device(device, baseline, mesh_level)
        stage_zero = baseline["bias_protocol"]["stages"][0]
        stage_low_vds = baseline["bias_protocol"]["stages"][1]
        set_biases(
            device,
            source_v=float(stage_zero["source_v"]),
            drain_v=float(stage_zero["drain_v"]),
            bottom_gate_v=float(stage_zero["bottom_gate_v"]),
        )
        solver_records.append(
            solve_dc(device, baseline, "poisson_zero_bias_initialization", coupled=False)
        )
        create_transport(device, baseline)
        solver_records.append(solve_dc(device, baseline, "T01_A_STAGE_0", coupled=True))

        bias_rows: list[dict[str, Any]] = []
        vgs_v = float(stage_low_vds["vgs_v"])
        for vds_v in [float(value) for value in stage_low_vds["vds_values_v"]]:
            set_biases(device, source_v=0.0, drain_v=vds_v, bottom_gate_v=vgs_v)
            solve_record = solve_dc(
                device,
                baseline,
                f"T01_A_STAGE_1_VDS_{vds_v:.6g}_V",
                coupled=True,
            )
            solver_records.append(solve_record)
            bias_rows.append(
                collect_bias_row(
                    device,
                    baseline,
                    mesh_level=mesh_level,
                    stage_id="T01_A_STAGE_1",
                    vds_v=vds_v,
                    vgs_v=vgs_v,
                    solve_record=solve_record,
                )
            )

        state_rows = collect_state_nodes(device, mesh_level)
        state_path = run_dir / f"t01_b_{mesh_level}_final_nodes.csv"
        write_csv(
            state_path,
            state_rows,
            [
                "mesh_level",
                "region",
                "x_cm",
                "y_cm",
                "x_um",
                "y_nm",
                "potential_v",
                "electron_density_cm3",
            ],
        )
        vtk_base = run_dir / f"t01_b_{mesh_level}_final"
        devsim.write_devices(file=str(vtk_base), device=device, type="vtk")
        for vtk_path in run_dir.glob(f"{vtk_base.name}*"):
            normalize_text_newline(vtk_path)
        node_count, element_count = node_and_element_counts(device)
        summary = {
            "mesh_level": mesh_level,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
            "state_csv": str(state_path.relative_to(ROOT)),
            "vtk_base": str(vtk_base.relative_to(ROOT)),
            "solver_records": solver_records,
        }
        return bias_rows, summary, solver_records
    finally:
        if device in devsim.get_device_list():
            devsim.delete_device(device=device)


def boolean_check(checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def assess_smoke(
    baseline: dict[str, Any],
    smoke: dict[str, Any],
    bias_rows: list[dict[str, Any]],
    mesh_summaries: list[dict[str, Any]],
    run_dir: Path,
) -> dict[str, Any]:
    acceptance = smoke["acceptance"]
    expected_meshes = list(acceptance["required_mesh_levels"])
    expected_vds = [float(value) for value in acceptance["required_vds_values_v"]]
    checks: dict[str, dict[str, Any]] = {}
    by_mesh = {
        mesh: sorted(
            [row for row in bias_rows if row["mesh_level"] == mesh],
            key=lambda row: float(row["vds_v"]),
        )
        for mesh in expected_meshes
    }
    boolean_check(
        checks,
        "configured_meshes_completed",
        set(by_mesh) == set(expected_meshes) and len(mesh_summaries) == len(expected_meshes),
        f"meshes={','.join(summary['mesh_level'] for summary in mesh_summaries)}",
    )
    boolean_check(
        checks,
        "only_authorized_stages_executed",
        all(row["stage_id"] == "T01_A_STAGE_1" and float(row["vgs_v"]) == 0.0 for row in bias_rows),
        "T01-B records only the VGS=0 V low-VDS continuation after the internal zero-bias equilibrium solve",
    )
    boolean_check(
        checks,
        "required_vds_continuation",
        all([float(row["vds_v"]) for row in by_mesh[mesh]] == expected_vds for mesh in expected_meshes),
        f"VDS values={expected_vds}",
    )
    all_solver_records = [record for summary in mesh_summaries for record in summary["solver_records"]]
    boolean_check(
        checks,
        "all_dc_solves_converged",
        bool(all_solver_records) and all(bool(record["converged"]) for record in all_solver_records),
        f"solver_records={len(all_solver_records)}",
    )
    zero_rows = [row for row in bias_rows if float(row["vds_v"]) == 0.0]
    zero_limit = float(acceptance["zero_bias_abs_terminal_current_a_per_cm_max"])
    boolean_check(
        checks,
        "zero_bias_current_small",
        len(zero_rows) == len(expected_meshes)
        and all(
            max(abs(float(row["source_current_a_per_cm"])), abs(float(row["drain_current_a_per_cm"]))) <= zero_limit
            for row in zero_rows
        ),
        f"limit_a_per_cm={zero_limit:.3e}",
    )
    nonzero_rows = [row for row in bias_rows if float(row["vds_v"]) > 0.0]
    current_floor = float(acceptance["minimum_low_vds_abs_terminal_current_a_per_cm"])
    imbalance_limit = float(acceptance["maximum_relative_terminal_current_imbalance"])
    boolean_check(
        checks,
        "low_vds_current_resolved",
        len(nonzero_rows) == len(expected_meshes) * (len(expected_vds) - 1)
        and all(abs(float(row["drain_current_a_per_cm"])) >= current_floor for row in nonzero_rows),
        f"floor_a_per_cm={current_floor:.3e}",
    )
    boolean_check(
        checks,
        "terminal_current_conservation",
        all(float(row["relative_current_imbalance"]) <= imbalance_limit for row in nonzero_rows),
        f"limit={imbalance_limit:.3e}",
    )
    signs = {
        math.copysign(1.0, float(row["drain_current_a_per_cm"]))
        for row in nonzero_rows
        if abs(float(row["drain_current_a_per_cm"])) >= current_floor
    }
    boolean_check(
        checks,
        "low_vds_current_direction_consistent",
        len(signs) == 1,
        f"drain_current_signs={sorted(signs)}",
    )
    final_rows = {
        mesh: next(
            (row for row in by_mesh[mesh] if math.isclose(float(row["vds_v"]), 0.01, abs_tol=1.0e-15)),
            None,
        )
        for mesh in expected_meshes
    }
    coarse = final_rows.get("coarse")
    fine = final_rows.get("fine")
    if coarse is None or fine is None:
        mesh_delta = math.inf
    else:
        coarse_current = abs(float(coarse["drain_current_a_per_cm"]))
        fine_current = abs(float(fine["drain_current_a_per_cm"]))
        mesh_delta = abs(fine_current - coarse_current) / max(fine_current, coarse_current, 1.0e-300)
    mesh_limit = float(acceptance["maximum_relative_mesh_current_difference_at_0p01v"])
    boolean_check(
        checks,
        "low_vds_mesh_current_smoke",
        math.isfinite(mesh_delta) and mesh_delta <= mesh_limit,
        f"relative_delta={mesh_delta:.6e} limit={mesh_limit:.6e}",
    )
    expected_state_files = [ROOT / summary["state_csv"] for summary in mesh_summaries]
    boolean_check(
        checks,
        "state_outputs_present",
        all(path.is_file() and path.stat().st_size > 0 for path in expected_state_files),
        ", ".join(str(path.relative_to(ROOT)) for path in expected_state_files),
    )
    failures = [name for name, result in checks.items() if result["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "mesh_current_relative_difference_at_0p01v": mesh_delta,
        "baseline_case_id": baseline["case_id"],
        "run_directory": str(run_dir.relative_to(ROOT)),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_t01_b_smoke.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    smoke_path = args.config.resolve()
    smoke = load_json(smoke_path)
    baseline_path = ROOT / smoke["input_contract"]["path"]
    baseline = load_json(baseline_path)
    outputs = smoke["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    bias_csv_path = ROOT / outputs["bias_points_csv"]
    mesh_csv_path = ROOT / outputs["mesh_summary_csv"]
    report_path = ROOT / outputs["report"]
    snapshot = {
        "smoke_config_path": str(smoke_path.relative_to(ROOT)),
        "smoke_config_sha256": sha256(smoke_path),
        "baseline_config_path": str(baseline_path.relative_to(ROOT)),
        "baseline_config_sha256": sha256(baseline_path),
        "baseline_case_id": baseline["case_id"],
        "smoke_case_id": smoke["case_id"],
        "baseline": baseline,
        "smoke": smoke,
    }
    write_json(snapshot_path, snapshot)

    bias_rows: list[dict[str, Any]] = []
    mesh_summaries: list[dict[str, Any]] = []
    solver_log: dict[str, Any] = {
        "case_id": smoke["case_id"],
        "stage": smoke["stage"],
        "devsim_version": getattr(devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t01-b-smoke",
        "validation_command": "make t01-b-check",
        "mesh_runs": [],
        "errors": [],
    }
    caught_error: Exception | None = None
    for mesh_level in smoke["scope"]["mesh_levels"]:
        try:
            rows, summary, records = run_mesh(baseline, smoke, mesh_level, run_dir)
            bias_rows.extend(rows)
            mesh_summaries.append(summary)
            solver_log["mesh_runs"].append(
                {
                    "mesh_level": mesh_level,
                    "status": "PASS",
                    "solver_records": records,
                }
            )
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"mesh_level": mesh_level, "error": repr(error)})
            solver_log["mesh_runs"].append({"mesh_level": mesh_level, "status": "FAIL"})
            break

    bias_fieldnames = [
        "mesh_level",
        "stage_id",
        "vgs_v",
        "vds_v",
        "source_current_a_per_cm",
        "drain_current_a_per_cm",
        "source_current_terminal_a",
        "drain_current_terminal_a",
        "current_imbalance_a_per_cm",
        "relative_current_imbalance",
        "center_channel_potential_v",
        "center_channel_electron_density_cm3",
        "solve_seconds",
        "converged",
    ]
    write_csv(bias_csv_path, bias_rows, bias_fieldnames)
    mesh_rows = []
    for summary in mesh_summaries:
        final = next(
            (row for row in bias_rows if row["mesh_level"] == summary["mesh_level"] and math.isclose(float(row["vds_v"]), 0.01, abs_tol=1.0e-15)),
            None,
        )
        mesh_rows.append(
            {
                "mesh_level": summary["mesh_level"],
                "node_count_with_interface_duplicates": summary["node_count_with_interface_duplicates"],
                "element_count": summary["element_count"],
                "dc_solve_count": len(summary["solver_records"]),
                "final_drain_current_a_per_cm": "" if final is None else final["drain_current_a_per_cm"],
                "state_csv": summary["state_csv"],
                "vtk_base": summary["vtk_base"],
            }
        )
    write_csv(
        mesh_csv_path,
        mesh_rows,
        [
            "mesh_level",
            "node_count_with_interface_duplicates",
            "element_count",
            "dc_solve_count",
            "final_drain_current_a_per_cm",
            "state_csv",
            "vtk_base",
        ],
    )
    write_json(solver_log_path, solver_log)
    assessment = assess_smoke(baseline, smoke, bias_rows, mesh_summaries, run_dir)
    if caught_error is not None:
        assessment["status"] = "FAIL"
        assessment["failures"].append("simulation_exception")
        assessment["checks"]["simulation_exception"] = {
            "status": "FAIL",
            "detail": repr(caught_error),
        }
    report = {
        "status": assessment["status"],
        "case_id": smoke["case_id"],
        "stage": smoke["stage"],
        "evidence_level": "E2" if assessment["status"] == "PASS" else "E0",
        "model_scope": "2D single-bottom-gate n-IGZO, electron-only drift-diffusion low-bias smoke",
        "executed_bias_stage_ids": ["T01_A_STAGE_0", "T01_A_STAGE_1"],
        "baseline_case_id": baseline["case_id"],
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "command": "make t01-b-smoke",
            "validation_command": "make t01-b-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(devsim, "__version__", "2.10.0"),
        },
        "mesh": mesh_rows,
        "bias_points": bias_rows,
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "mesh_current_relative_difference_at_0p01v": assessment["mesh_current_relative_difference_at_0p01v"],
        "outputs": {
            "solver_log": str(solver_log_path.relative_to(ROOT)),
            "bias_points_csv": str(bias_csv_path.relative_to(ROOT)),
            "mesh_summary_csv": str(mesh_csv_path.relative_to(ROOT)),
            "run_directory": str(run_dir.relative_to(ROOT)),
        },
        "evidence_boundary": smoke["evidence_boundary"],
    }
    write_json(report_path, report)
    print(
        f"T01_B_SMOKE_{report['status']} "
        f"meshes={len(mesh_summaries)} bias_points={len(bias_rows)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T01_B_SMOKE_ERROR {caught_error}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
