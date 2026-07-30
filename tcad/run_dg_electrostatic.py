#!/usr/bin/env python3
"""Run a laptop-scale 2D dual-gate electrostatic DEVSIM benchmark."""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import time
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("DEVSIM_MATH_LIBS", "liblapack.so.3:libblas.so.3")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / "results" / ".cache" / "matplotlib"))

import devsim  # noqa: E402
from devsim.python_packages.model_create import CreateContinuousInterfaceModel  # noqa: E402


REGIONS = ("bottom_oxide", "channel", "top_oxide")
INTERFACES = ("bottom_oxide_channel", "channel_top_oxide")
CONTACTS = ("source", "drain", "bottom_gate", "top_gate")


def load_config(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add_axis_lines(
    *, mesh: str, direction: str, start: float, stop: float, spacing: float
) -> None:
    count = max(1, math.ceil((stop - start) / spacing))
    for index in range(count + 1):
        position = start + (stop - start) * index / count
        devsim.add_2d_mesh_line(mesh=mesh, dir=direction, pos=position, ps=spacing)


def create_mesh(device: str, config: dict[str, Any], mesh_level: str) -> None:
    geometry = config["geometry"]
    mesh_config = config["mesh_levels"][mesh_level]
    length = geometry["channel_length_um"]
    bottom_interface = geometry["bottom_oxide_thickness_um"]
    top_interface = bottom_interface + geometry["channel_thickness_um"]
    top = top_interface + geometry["top_oxide_thickness_um"]
    ambient_thickness = min(
        mesh_config["oxide_y_spacing_um"],
        geometry["bottom_oxide_thickness_um"] / 3,
    )

    mesh = f"{device}_mesh"
    devsim.create_2d_mesh(mesh=mesh)
    add_axis_lines(
        mesh=mesh,
        direction="x",
        start=0.0,
        stop=length,
        spacing=mesh_config["x_spacing_um"],
    )
    add_axis_lines(
        mesh=mesh,
        direction="y",
        start=-ambient_thickness,
        stop=0.0,
        spacing=ambient_thickness,
    )
    add_axis_lines(
        mesh=mesh,
        direction="y",
        start=0.0,
        stop=bottom_interface,
        spacing=mesh_config["oxide_y_spacing_um"],
    )
    add_axis_lines(
        mesh=mesh,
        direction="y",
        start=bottom_interface,
        stop=top_interface,
        spacing=mesh_config["channel_y_spacing_um"],
    )
    add_axis_lines(
        mesh=mesh,
        direction="y",
        start=top_interface,
        stop=top,
        spacing=mesh_config["oxide_y_spacing_um"],
    )
    add_axis_lines(
        mesh=mesh,
        direction="y",
        start=top,
        stop=top + ambient_thickness,
        spacing=ambient_thickness,
    )

    devsim.add_2d_region(
        mesh=mesh,
        material="Air",
        region="ambient",
        xl=0.0,
        xh=length,
        yl=-ambient_thickness,
        yh=top + ambient_thickness,
    )

    devsim.add_2d_region(
        mesh=mesh,
        material="Al2O3",
        region="bottom_oxide",
        xl=0.0,
        xh=length,
        yl=0.0,
        yh=bottom_interface,
    )
    devsim.add_2d_region(
        mesh=mesh,
        material="IGZO",
        region="channel",
        xl=0.0,
        xh=length,
        yl=bottom_interface,
        yh=top_interface,
    )
    devsim.add_2d_region(
        mesh=mesh,
        material="Al2O3",
        region="top_oxide",
        xl=0.0,
        xh=length,
        yl=top_interface,
        yh=top,
    )

    devsim.add_2d_contact(
        mesh=mesh,
        name="bottom_gate",
        region="bottom_oxide",
        material="metal",
        yl=0.0,
        yh=0.0,
        bloat=1e-9,
    )
    devsim.add_2d_contact(
        mesh=mesh,
        name="top_gate",
        region="top_oxide",
        material="metal",
        yl=top,
        yh=top,
        bloat=1e-9,
    )
    devsim.add_2d_contact(
        mesh=mesh,
        name="source",
        region="channel",
        material="metal",
        xl=0.0,
        xh=0.0,
        yl=bottom_interface,
        yh=top_interface,
    )
    devsim.add_2d_contact(
        mesh=mesh,
        name="drain",
        region="channel",
        material="metal",
        xl=length,
        xh=length,
        yl=bottom_interface,
        yh=top_interface,
    )
    devsim.add_2d_interface(
        mesh=mesh,
        name="bottom_oxide_channel",
        region0="bottom_oxide",
        region1="channel",
    )
    devsim.add_2d_interface(
        mesh=mesh,
        name="channel_top_oxide",
        region0="channel",
        region1="top_oxide",
    )
    devsim.finalize_mesh(mesh=mesh)
    devsim.create_device(mesh=mesh, device=device)


def create_region_equation(device: str, region: str, relative_permittivity: float) -> None:
    devsim.set_parameter(
        device=device,
        region=region,
        name="Permittivity",
        value=relative_permittivity,
    )
    devsim.node_solution(device=device, region=region, name="Potential")
    devsim.edge_from_node_model(device=device, region=region, node_model="Potential")
    devsim.edge_model(
        device=device,
        region=region,
        name="ElectricField",
        equation="(Potential@n0-Potential@n1)*EdgeInverseLength",
    )
    devsim.edge_model(
        device=device,
        region=region,
        name="ElectricField:Potential@n0",
        equation="EdgeInverseLength",
    )
    devsim.edge_model(
        device=device,
        region=region,
        name="ElectricField:Potential@n1",
        equation="-EdgeInverseLength",
    )
    devsim.edge_model(
        device=device,
        region=region,
        name="PotentialEdgeFlux",
        equation="Permittivity*ElectricField",
    )
    devsim.edge_model(
        device=device,
        region=region,
        name="PotentialEdgeFlux:Potential@n0",
        equation="Permittivity*EdgeInverseLength",
    )
    devsim.edge_model(
        device=device,
        region=region,
        name="PotentialEdgeFlux:Potential@n1",
        equation="-Permittivity*EdgeInverseLength",
    )
    devsim.equation(
        device=device,
        region=region,
        name="PotentialEquation",
        variable_name="Potential",
        edge_model="PotentialEdgeFlux",
        variable_update="default",
    )


def create_contact_equation(device: str, contact: str) -> None:
    model = f"{contact}_potential_bc"
    devsim.contact_node_model(
        device=device,
        contact=contact,
        name=model,
        equation=f"Potential-{contact}_bias",
    )
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


def initialize_device(device: str, config: dict[str, Any], mesh_level: str) -> None:
    create_mesh(device, config, mesh_level)
    materials = config["materials"]
    create_region_equation(
        device, "bottom_oxide", materials["bottom_oxide"]["relative_permittivity"]
    )
    create_region_equation(device, "channel", materials["channel"]["relative_permittivity"])
    create_region_equation(
        device, "top_oxide", materials["top_oxide"]["relative_permittivity"]
    )
    for interface in INTERFACES:
        model = CreateContinuousInterfaceModel(device, interface, "Potential")
        devsim.interface_equation(
            device=device,
            interface=interface,
            name="PotentialEquation",
            interface_model=model,
            type="continuous",
        )
    for contact in CONTACTS:
        create_contact_equation(device, contact)


def set_biases(device: str, **biases: float) -> None:
    for name, value in biases.items():
        devsim.set_parameter(device=device, name=f"{name}_bias", value=value)


def solve_device(device: str, config: dict[str, Any]) -> float:
    solver = config["solver"]
    start = time.perf_counter()
    devsim.solve(
        type=solver["type"],
        absolute_error=solver["absolute_error"],
        relative_error=solver["relative_error"],
        maximum_iterations=solver["maximum_iterations"],
        solver_type=solver["solver_type"],
    )
    return time.perf_counter() - start


def region_nodes(device: str, region: str) -> list[dict[str, float | str]]:
    xs = devsim.get_node_model_values(device=device, region=region, name="x")
    ys = devsim.get_node_model_values(device=device, region=region, name="y")
    potentials = devsim.get_node_model_values(
        device=device, region=region, name="Potential"
    )
    return [
        {"region": region, "x_um": x, "y_um": y, "potential_v": potential}
        for x, y, potential in zip(xs, ys, potentials, strict=True)
    ]


def all_nodes(device: str) -> list[dict[str, float | str]]:
    nodes: list[dict[str, float | str]] = []
    for region in REGIONS:
        nodes.extend(region_nodes(device, region))
    return nodes


def center_channel_potential(device: str, config: dict[str, Any]) -> float:
    geometry = config["geometry"]
    target_x = geometry["channel_length_um"] / 2
    target_y = (
        geometry["bottom_oxide_thickness_um"]
        + geometry["channel_thickness_um"] / 2
    )
    nodes = region_nodes(device, "channel")
    nearest = min(
        nodes,
        key=lambda row: (float(row["x_um"]) - target_x) ** 2
        + (float(row["y_um"]) - target_y) ** 2,
    )
    return float(nearest["potential_v"])


def linear_slope(xs: list[float], ys: list[float]) -> float:
    mean_x = sum(xs) / len(xs)
    mean_y = sum(ys) / len(ys)
    numerator = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys, strict=True))
    denominator = sum((x - mean_x) ** 2 for x in xs)
    return numerator / denominator


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def plot_potential(path: Path, nodes: list[dict[str, Any]], config: dict[str, Any]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as tri

    grouped: dict[tuple[float, float], list[float]] = defaultdict(list)
    for row in nodes:
        key = (round(float(row["x_um"]), 12), round(float(row["y_um"]), 12))
        grouped[key].append(float(row["potential_v"]))
    xs = [key[0] for key in grouped]
    ys_nm = [key[1] * 1000 for key in grouped]
    values = [sum(grouped[key]) / len(grouped[key]) for key in grouped]
    triangulation = tri.Triangulation(xs, ys_nm)

    geometry = config["geometry"]
    bottom_interface_nm = geometry["bottom_oxide_thickness_um"] * 1000
    top_interface_nm = (
        geometry["bottom_oxide_thickness_um"] + geometry["channel_thickness_um"]
    ) * 1000

    figure, axis = plt.subplots(figsize=(9.2, 3.4), constrained_layout=True)
    contour = axis.tricontourf(triangulation, values, levels=32, cmap="viridis")
    axis.axhline(bottom_interface_nm, color="white", linewidth=0.8)
    axis.axhline(top_interface_nm, color="white", linewidth=0.8)
    axis.set_xlabel("x (um)")
    axis.set_ylabel("vertical position (nm)")
    axis.set_title("2D dual-gate electrostatic potential")
    figure.colorbar(contour, ax=axis, label="Potential (V)")
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def plot_coupling(path: Path, rows: list[dict[str, Any]]) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    figure, axis = plt.subplots(figsize=(6.8, 4.2), constrained_layout=True)
    for sweep, marker in (("top_gate", "o"), ("bottom_gate", "s")):
        selected = [row for row in rows if row["sweep"] == sweep]
        axis.plot(
            [row["gate_voltage_v"] for row in selected],
            [row["center_channel_potential_v"] for row in selected],
            marker=marker,
            label=sweep.replace("_", " "),
        )
    axis.set_xlabel("swept gate voltage (V)")
    axis.set_ylabel("center-channel potential (V)")
    axis.set_title("Dual-gate electrostatic coupling")
    axis.grid(True, alpha=0.25)
    axis.legend()
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180)
    plt.close(figure)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_baseline.json",
    )
    args = parser.parse_args()
    config = load_config(args.config)

    run_dir = ROOT / "results" / "tcad" / "dg_electrostatic"
    table_dir = ROOT / "results" / "tables"
    figure_dir = ROOT / "results" / "figures"
    report_path = ROOT / "results" / "reports" / "tcad_dg_electrostatic.json"
    for directory in (run_dir, table_dir, figure_dir, report_path.parent):
        directory.mkdir(parents=True, exist_ok=True)

    baseline_biases = {
        "source": config["bias"]["source_v"],
        "drain": config["bias"]["drain_v"],
        "bottom_gate": config["bias"]["bottom_gate_v"],
        "top_gate": config["bias"]["top_gate_v"],
    }
    mesh_rows: list[dict[str, Any]] = []
    devices: dict[str, str] = {}
    for mesh_level in config["mesh_levels"]:
        device = f"dg_igzo_{mesh_level}"
        devices[mesh_level] = device
        initialize_device(device, config, mesh_level)
        set_biases(device, **baseline_biases)
        elapsed = solve_device(device, config)
        node_count = sum(
            len(devsim.get_node_model_values(device=device, region=region, name="x"))
            for region in REGIONS
        )
        element_count = sum(
            len(devsim.get_element_node_list(device=device, region=region))
            for region in REGIONS
        )
        mesh_rows.append(
            {
                "mesh_level": mesh_level,
                "node_count_with_interface_duplicates": node_count,
                "element_count": element_count,
                "center_channel_potential_v": center_channel_potential(device, config),
                "solve_seconds": elapsed,
            }
        )
        devsim.write_devices(file=str(run_dir / device), device=device, type="vtk")

    fine_device = devices["fine"]
    devsim.delete_device(device=devices["coarse"])
    sweep_values = [float(value) for value in config["bias"]["coupling_sweep_v"]]
    coupling_rows: list[dict[str, Any]] = []
    for sweep in ("top_gate", "bottom_gate"):
        for gate_voltage in sweep_values:
            biases = {
                "source": config["bias"]["source_v"],
                "drain": config["bias"]["drain_v"],
                "bottom_gate": 0.0,
                "top_gate": 0.0,
            }
            biases[sweep] = gate_voltage
            set_biases(fine_device, **biases)
            elapsed = solve_device(fine_device, config)
            coupling_rows.append(
                {
                    "sweep": sweep,
                    "gate_voltage_v": gate_voltage,
                    "fixed_other_gate_v": 0.0,
                    "source_v": biases["source"],
                    "drain_v": biases["drain"],
                    "center_channel_potential_v": center_channel_potential(
                        fine_device, config
                    ),
                    "solve_seconds": elapsed,
                }
            )

    set_biases(fine_device, **baseline_biases)
    solve_device(fine_device, config)
    potential_nodes = all_nodes(fine_device)
    for row in potential_nodes:
        row["mesh_level"] = "fine"
        row["top_gate_v"] = baseline_biases["top_gate"]
        row["bottom_gate_v"] = baseline_biases["bottom_gate"]

    mesh_csv = table_dir / "tcad_dg_mesh_comparison.csv"
    coupling_csv = table_dir / "tcad_dg_coupling.csv"
    potential_csv = table_dir / "tcad_dg_potential_nodes.csv"
    potential_figure = figure_dir / "tcad_dg_potential.png"
    coupling_figure = figure_dir / "tcad_dg_coupling.png"
    write_csv(mesh_csv, mesh_rows)
    write_csv(coupling_csv, coupling_rows)
    write_csv(potential_csv, potential_nodes)
    plot_potential(potential_figure, potential_nodes, config)
    plot_coupling(coupling_figure, coupling_rows)

    mesh_values = {row["mesh_level"]: row for row in mesh_rows}
    mesh_difference = abs(
        mesh_values["fine"]["center_channel_potential_v"]
        - mesh_values["coarse"]["center_channel_potential_v"]
    )
    top_rows = [row for row in coupling_rows if row["sweep"] == "top_gate"]
    bottom_rows = [row for row in coupling_rows if row["sweep"] == "bottom_gate"]
    top_coupling = linear_slope(
        [row["gate_voltage_v"] for row in top_rows],
        [row["center_channel_potential_v"] for row in top_rows],
    )
    bottom_coupling = linear_slope(
        [row["gate_voltage_v"] for row in bottom_rows],
        [row["center_channel_potential_v"] for row in bottom_rows],
    )
    acceptance = config["acceptance"]
    checks = {
        "mesh_difference": mesh_difference
        <= acceptance["maximum_center_potential_mesh_difference_v"],
        "top_coupling_range": acceptance["minimum_top_gate_coupling_v_per_v"]
        <= top_coupling
        <= acceptance["maximum_top_gate_coupling_v_per_v"],
        "finite_outputs": all(
            math.isfinite(float(row["potential_v"])) for row in potential_nodes
        ),
    }
    status = "PASS" if all(checks.values()) else "FAIL"
    report = {
        "status": status,
        "case_id": config["case_id"],
        "model_scope": "2D electrostatic Poisson/Laplace benchmark",
        "mesh": mesh_rows,
        "mesh_center_potential_difference_v": mesh_difference,
        "top_gate_coupling_v_per_v": top_coupling,
        "bottom_gate_coupling_v_per_v": bottom_coupling,
        "checks": checks,
        "outputs": {
            "mesh_csv": str(mesh_csv.relative_to(ROOT)),
            "coupling_csv": str(coupling_csv.relative_to(ROOT)),
            "potential_csv": str(potential_csv.relative_to(ROOT)),
            "potential_figure": str(potential_figure.relative_to(ROOT)),
            "coupling_figure": str(coupling_figure.relative_to(ROOT)),
            "vtk_directory": str(run_dir.relative_to(ROOT)),
        },
        "evidence_boundary": config["evidence_boundary"],
    }
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        f"TCAD_DG_ELECTROSTATIC_{status} "
        f"mesh_delta={mesh_difference:.6g}V "
        f"alpha_top={top_coupling:.6g} "
        f"alpha_bottom={bottom_coupling:.6g} "
        f"report={report_path}"
    )
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
