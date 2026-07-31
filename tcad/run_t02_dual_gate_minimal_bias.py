#!/usr/bin/env python3
"""Run the T02-B minimal nonzero enabled top-gate bias family."""

from __future__ import annotations

import argparse
import copy
import json
import math
import os
import sys
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
TCAD_DIR = Path(__file__).resolve().parent
if str(TCAD_DIR) not in sys.path:
    sys.path.insert(0, str(TCAD_DIR))

import run_t02_dual_gate_limit_regression as t02_a  # noqa: E402


core = t02_a.core
ENABLED_REGIONS = t02_a.ENABLED_REGIONS
ENABLED_CONTACTS = t02_a.ENABLED_CONTACTS
ENABLED_INTERFACES = t02_a.ENABLED_INTERFACES

BIAS_FIELDNAMES = [
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
    "solve_seconds",
    "converged",
]

STATE_FIELDNAMES = [
    "state_id",
    "state_label",
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

STATE_SUMMARY_FIELDNAMES = [
    "state_id",
    "state_label",
    "vtg_v",
    "vbg_v",
    "vds_v",
    "source_current_a_per_cm",
    "drain_current_a_per_cm",
    "relative_current_imbalance",
    "center_channel_potential_v",
    "center_channel_electron_density_cm3",
    "node_row_count",
    "state_csv",
    "state_csv_sha256",
    "vtk_file_count",
]


def add_check(
    checks: dict[str, dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}


def same_value(left: float, right: float) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1.0e-12)


def contact_currents(device: str) -> tuple[float, float]:
    source = float(
        core.devsim.get_contact_current(
            device=device,
            contact="source",
            equation="ElectronContinuityEquation",
        )
    )
    drain = float(
        core.devsim.get_contact_current(
            device=device,
            contact="drain",
            equation="ElectronContinuityEquation",
        )
    )
    return source, drain


def maximum_state_potential(state_rows: list[dict[str, Any]]) -> float:
    return max(abs(float(row["potential_v"])) for row in state_rows)


def collect_bias_row(
    device: str,
    runtime: dict[str, Any],
    mesh_level: str,
    mode_id: str,
    vbg_v: float,
    vtg_v: float,
    vds_v: float,
    solve_record: dict[str, Any],
) -> dict[str, Any]:
    base = core.collect_bias_row(
        device,
        runtime,
        mesh_level=mesh_level,
        stage_id="T02_B_MINIMAL_TOP_GATE",
        vds_v=vds_v,
        vgs_v=vbg_v,
        solve_record=solve_record,
    )
    return {
        "stage_id": "T02_B_MINIMAL_TOP_GATE",
        "mode_id": mode_id,
        "mesh_level": mesh_level,
        "vbg_v": vbg_v,
        "vtg_v": vtg_v,
        "vds_v": vds_v,
        "source_current_a_per_cm": base["source_current_a_per_cm"],
        "drain_current_a_per_cm": base["drain_current_a_per_cm"],
        "source_current_terminal_a": base["source_current_terminal_a"],
        "drain_current_terminal_a": base["drain_current_terminal_a"],
        "current_imbalance_a_per_cm": base["current_imbalance_a_per_cm"],
        "relative_current_imbalance": base["relative_current_imbalance"],
        "center_channel_potential_v": base["center_channel_potential_v"],
        "center_channel_electron_density_cm3": base[
            "center_channel_electron_density_cm3"
        ],
        "solve_seconds": base["solve_seconds"],
        "converged": base["converged"],
    }


def write_endpoint_state(
    device: str,
    runtime: dict[str, Any],
    mode_id: str,
    state_id: str,
    state_label: str,
    bias: dict[str, float],
    run_dir: Path,
) -> dict[str, Any]:
    rows = t02_a.collect_enabled_state(device, mode_id, bias)
    enriched = [
        {
            "state_id": state_id,
            "state_label": state_label,
            **row,
        }
        for row in rows
    ]
    state_path = run_dir / f"t02_b_{state_id}_nodes.csv"
    core.write_csv(state_path, enriched, STATE_FIELDNAMES)
    vtk_base = run_dir / f"t02_b_{state_id}"
    core.devsim.write_devices(file=str(vtk_base), device=device, type="vtk")
    vtk_files: list[dict[str, str]] = []
    for path in sorted(run_dir.glob(f"{vtk_base.name}*")):
        if path == state_path:
            continue
        core.normalize_text_newline(path)
        vtk_files.append(
            {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
        )

    source_current, drain_current = contact_currents(device)
    magnitude = max(abs(source_current), abs(drain_current), 1.0e-300)
    center = core.nearest_channel_state(device, runtime)
    return {
        "state_id": state_id,
        "state_label": state_label,
        "bias": bias,
        "mode_id": mode_id,
        "regions": list(ENABLED_REGIONS),
        "contacts": list(ENABLED_CONTACTS),
        "interfaces": list(ENABLED_INTERFACES),
        "node_count_with_interface_duplicates": len(enriched),
        "state_csv": str(state_path.relative_to(ROOT)),
        "state_csv_sha256": core.sha256(state_path),
        "vtk_base": str(vtk_base.relative_to(ROOT)),
        "vtk_files": vtk_files,
        "vtk_file_count": len(vtk_files),
        "source_current_a_per_cm": source_current,
        "drain_current_a_per_cm": drain_current,
        "relative_current_imbalance": abs(source_current + drain_current) / magnitude,
        "center_channel_potential_v": center["center_channel_potential_v"],
        "center_channel_electron_density_cm3": center[
            "center_channel_electron_density_cm3"
        ],
        "maximum_absolute_potential_v": maximum_state_potential(enriched),
    }


def render_figure(config: dict[str, Any], rows: list[dict[str, Any]], path: Path) -> str:
    cache_root = ROOT / "results" / ".cache"
    mpl_cache = cache_root / "matplotlib"
    temp_dir = cache_root / "tmp"
    mpl_cache.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(mpl_cache))
    os.environ.setdefault("TMPDIR", str(temp_dir))
    import matplotlib  # noqa: PLC0415

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt  # noqa: PLC0415

    vtg = [float(row["vtg_v"]) for row in rows]
    current = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
    potential = [float(row["center_channel_potential_v"]) for row in rows]
    density = [float(row["center_channel_electron_density_cm3"]) for row in rows]
    figure, axes = plt.subplots(1, 3, figsize=(10.8, 3.5), constrained_layout=True)
    axes[0].plot(vtg, current, marker="o", color="#2b6ca3", linewidth=2.0)
    axes[0].set_xlabel("VTG (V)")
    axes[0].set_ylabel("|ID| (A/cm)")
    axes[0].ticklabel_format(axis="y", style="sci", scilimits=(0, 0))
    axes[0].set_title("Terminal current")
    axes[1].plot(vtg, potential, marker="o", color="#b36b27", linewidth=2.0)
    axes[1].set_xlabel("VTG (V)")
    axes[1].set_ylabel("Center potential (V)")
    axes[1].set_title("Channel potential")
    axes[2].plot(vtg, density, marker="o", color="#287d59", linewidth=2.0)
    axes[2].set_xlabel("VTG (V)")
    axes[2].set_ylabel("Electron density (cm$^{-3}$)")
    axes[2].set_yscale("log")
    axes[2].set_title("Center electron density")
    for axis in axes:
        axis.grid(True, color="#d8dee3", linewidth=0.7)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(path, dpi=180, facecolor="white")
    plt.close(figure)
    return core.sha256(path)


def assess(
    config: dict[str, Any],
    contract_report: dict[str, Any],
    t02_a_report: dict[str, Any],
    topology: dict[str, Any],
    zero_equilibrium: dict[str, Any],
    rows: list[dict[str, Any]],
    state_entries: list[dict[str, Any]],
    solver_records: list[dict[str, Any]],
    figure_path: Path,
) -> dict[str, Any]:
    acceptance = config["acceptance"]
    checks: dict[str, dict[str, Any]] = {}
    currents = [abs(float(row["drain_current_a_per_cm"])) for row in rows]
    potentials = [float(row["center_channel_potential_v"]) for row in rows]
    densities = [float(row["center_channel_electron_density_cm3"]) for row in rows]
    max_imbalance = max(float(row["relative_current_imbalance"]) for row in rows)
    t02_a_topology = next(
        item for item in t02_a_report["topology"] if item["top_coupling_enabled"]
    )

    add_check(
        checks,
        "t02_a_contract_and_gate_passed",
        contract_report.get("contract_status") == "PASS"
        and t02_a_report.get("status") == "PASS"
        and t02_a_report.get("t02_a_completion", {}).get(
            "t02_b_minimal_bias_family_permitted_next"
        ) is True,
        (
            f"contract={contract_report.get('contract_status')} "
            f"t02_a={t02_a_report.get('status')}"
        ),
    )
    add_check(
        checks,
        "all_configured_dc_solves_converged",
        len(solver_records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in solver_records),
        f"records={len(solver_records)} expected={acceptance['required_total_dc_solve_count']}",
    )
    add_check(
        checks,
        "enabled_topology_matches_t02_a",
        topology["regions"] == sorted(acceptance["required_regions"])
        and topology["contacts"] == sorted(acceptance["required_contacts"])
        and topology["interfaces"] == sorted(acceptance["required_interfaces"])
        and topology["node_count_with_interface_duplicates"]
        == t02_a_topology["node_count_with_interface_duplicates"]
        and topology["element_count"] == t02_a_topology["element_count"],
        f"nodes={topology['node_count_with_interface_duplicates']} elements={topology['element_count']}",
    )
    expected_vtg = [float(value) for value in acceptance["required_top_gate_values_v"]]
    add_check(
        checks,
        "minimal_top_gate_grid_completed",
        len(rows) == acceptance["required_reported_point_count"]
        and [float(row["vtg_v"]) for row in rows] == expected_vtg
        and all(same_value(float(row["vbg_v"]), 0.0) for row in rows)
        and all(same_value(float(row["vds_v"]), 0.01) for row in rows),
        f"rows={len(rows)} VTG={[row['vtg_v'] for row in rows]}",
    )
    add_check(
        checks,
        "current_conservation_sign_and_strict_increase",
        max_imbalance <= acceptance["maximum_relative_terminal_current_imbalance"]
        and all(float(row["drain_current_a_per_cm"]) > 0.0 for row in rows)
        and all(float(row["source_current_a_per_cm"]) < 0.0 for row in rows)
        and all(next_value > value for value, next_value in zip(currents, currents[1:])),
        f"max_imbalance={max_imbalance:.6e} currents={currents}",
    )
    add_check(
        checks,
        "internal_state_strictly_increases",
        all(next_value > value for value, next_value in zip(potentials, potentials[1:]))
        and all(next_value > value for value, next_value in zip(densities, densities[1:])),
        f"potentials={potentials} densities={densities}",
    )
    endpoint_current_ratio = currents[-1] / max(currents[0], 1.0e-300)
    endpoint_density_ratio = densities[-1] / max(densities[0], 1.0e-300)
    endpoint_potential_increase = potentials[-1] - potentials[0]
    add_check(
        checks,
        "endpoint_response_is_numerically_detectable",
        endpoint_current_ratio >= acceptance["minimum_endpoint_current_ratio"]
        and endpoint_density_ratio >= acceptance["minimum_endpoint_center_density_ratio"]
        and endpoint_potential_increase
        >= acceptance["minimum_endpoint_center_potential_increase_v"],
        (
            f"current_ratio={endpoint_current_ratio:.6g} "
            f"density_ratio={endpoint_density_ratio:.6g} "
            f"potential_delta={endpoint_potential_increase:.6e}"
        ),
    )
    add_check(
        checks,
        "zero_equilibrium_is_current_free_before_bias_ramp",
        zero_equilibrium["maximum_absolute_terminal_current_a_per_cm"]
        <= acceptance["maximum_zero_equilibrium_absolute_terminal_current_a_per_cm"]
        and zero_equilibrium["maximum_absolute_potential_v"]
        <= acceptance["maximum_zero_equilibrium_absolute_potential_v"],
        json.dumps(zero_equilibrium, sort_keys=True),
    )
    add_check(
        checks,
        "endpoint_states_and_vtk_are_persisted",
        [entry["state_id"] for entry in state_entries]
        == acceptance["required_state_ids"]
        and all(
            entry["vtk_file_count"] == acceptance["required_vtk_file_count_per_state"]
            and len(entry["vtk_files"]) == acceptance["required_vtk_file_count_per_state"]
            for entry in state_entries
        ),
        f"states={[entry['state_id'] for entry in state_entries]} vtk={[entry['vtk_file_count'] for entry in state_entries]}",
    )
    add_check(
        checks,
        "report_figure_written",
        figure_path.is_file() and figure_path.stat().st_size > 0,
        f"path={figure_path.relative_to(ROOT)} bytes={figure_path.stat().st_size if figure_path.exists() else 0}",
    )
    failures = [name for name, result in checks.items() if result["status"] == "FAIL"]
    return {
        "status": "PASS" if not failures else "FAIL",
        "checks": checks,
        "failures": failures,
        "maximum_relative_terminal_current_imbalance": max_imbalance,
        "endpoint_current_ratio": endpoint_current_ratio,
        "endpoint_center_potential_increase_v": endpoint_potential_increase,
        "endpoint_center_density_ratio": endpoint_density_ratio,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--config",
        type=Path,
        default=ROOT / "config" / "tcad_t02_b_minimal_bias.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = args.config.resolve()
    config = core.load_json(config_path)
    dependency = config["dependencies"]
    baseline_path = ROOT / dependency["t01_baseline_config"]
    mesh_config_path = ROOT / dependency["t01_mesh_config"]
    t02_a_config_path = ROOT / dependency["t02_a_config"]
    t02_a_report_path = ROOT / dependency["t02_a_report"]
    t02_a_check_path = ROOT / dependency["t02_a_check_report"]
    contract_report_path = ROOT / config["outputs"]["contract_report"]
    baseline = core.load_json(baseline_path)
    mesh_config = core.load_json(mesh_config_path)
    t02_a_config = core.load_json(t02_a_config_path)
    t02_a_report = core.load_json(t02_a_report_path)
    t02_a_check = core.load_json(t02_a_check_path)
    contract_report = core.load_json(contract_report_path)

    if contract_report.get("contract_status") != "PASS":
        raise RuntimeError("T02-B input contract is not PASS")
    if contract_report.get("config", {}).get("sha256") != core.sha256(config_path):
        raise RuntimeError("T02-B contract report does not match current config")
    if (
        t02_a_report.get("status") != dependency["required_t02_a_status"]
        or t02_a_check.get("status") != dependency["required_t02_a_check_status"]
        or t02_a_report.get("t02_a_completion", {}).get(
            "t02_b_minimal_bias_family_permitted_next"
        )
        is not dependency["require_t02_b_permitted_by_t02_a"]
    ):
        raise RuntimeError("T02-A gate is not open")

    outputs = config["outputs"]
    run_dir = ROOT / outputs["run_directory"]
    run_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = ROOT / outputs["config_snapshot"]
    solver_log_path = ROOT / outputs["solver_log"]
    state_manifest_path = ROOT / outputs["state_manifest"]
    bias_path = ROOT / outputs["bias_csv"]
    state_summary_path = ROOT / outputs["state_summary_csv"]
    figure_path = ROOT / outputs["figure_png"]
    report_path = ROOT / outputs["report"]

    input_paths = {
        "t02_b_config": config_path,
        "t02_b_contract_report": contract_report_path,
        "t01_baseline_config": baseline_path,
        "t01_mesh_config": mesh_config_path,
        "t02_a_config": t02_a_config_path,
        "t02_a_report": t02_a_report_path,
        "t02_a_check_report": t02_a_check_path,
    }
    snapshot = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "inputs": {
            name: {"path": str(path.relative_to(ROOT)), "sha256": core.sha256(path)}
            for name, path in input_paths.items()
        },
        "t02_b_contract": config,
        "t01_baseline": baseline,
        "t01_mesh_source": mesh_config,
        "t02_a_config": t02_a_config,
    }
    core.write_json(snapshot_path, snapshot)

    solver_log: dict[str, Any] = {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        "python_executable": sys.executable,
        "reproduction_command": "make t02-b-minimal",
        "validation_command": "make t02-b-minimal-check",
        "runs": [],
        "errors": [],
    }
    protocol = config["bias_protocol"]
    mesh_level = config["inheritance"]["required_mesh_level"]
    runtime, mesh_spec = t02_a.mesh_stage.build_runtime_baseline(
        baseline, mesh_config, mesh_level
    )
    runtime = copy.deepcopy(runtime)
    runtime["geometry"]["top_oxide_thickness_cm"] = float(
        t02_a_config["top_stack_contract"]["enabled_mode"][
            "top_oxide_thickness_cm"
        ]
    )
    device = "t02_b_enabled_minimal_bias"
    mode_id = t02_a_config["top_stack_contract"]["enabled_mode"]["mode_id"]
    solver_records: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    state_entries: list[dict[str, Any]] = []
    topology: dict[str, Any] = {}
    zero_equilibrium: dict[str, Any] = {}
    caught_error: Exception | None = None
    wall_start = time.perf_counter()
    try:
        t02_a.initialize_enabled_device(
            device, runtime, t02_a_config, mesh_level, mesh_spec
        )
        regions, contacts, interfaces = t02_a.active_topology(device, ENABLED_REGIONS)
        node_count, element_count = t02_a.active_counts(device, ENABLED_REGIONS)
        topology = {
            "mode_id": mode_id,
            "top_coupling_enabled": True,
            "mesh_level": mesh_level,
            "regions": regions,
            "contacts": contacts,
            "interfaces": interfaces,
            "node_count_with_interface_duplicates": node_count,
            "element_count": element_count,
        }
        t02_a.set_enabled_biases(
            device,
            source_v=0.0,
            drain_v=0.0,
            bottom_gate_v=0.0,
            top_gate_v=0.0,
        )
        solver_records.append(
            core.solve_dc(device, runtime, "T02_B_POISSON_ZERO_BIAS", coupled=False)
        )
        core.create_transport(device, runtime)
        solver_records.append(
            core.solve_dc(device, runtime, "T02_B_COUPLED_ZERO_BIAS", coupled=True)
        )
        zero_source, zero_drain = contact_currents(device)
        zero_state = t02_a.collect_enabled_state(
            device,
            mode_id,
            {
                "source_v": 0.0,
                "drain_v": 0.0,
                "bottom_gate_v": 0.0,
                "top_gate_v": 0.0,
            },
        )
        zero_equilibrium = {
            "source_current_a_per_cm": zero_source,
            "drain_current_a_per_cm": zero_drain,
            "maximum_absolute_terminal_current_a_per_cm": max(
                abs(zero_source), abs(zero_drain)
            ),
            "maximum_absolute_potential_v": maximum_state_potential(zero_state),
            "node_count": len(zero_state),
        }

        last_low_vds: dict[str, Any] | None = None
        for vds_v in [float(value) for value in protocol["low_vds_values_v"]]:
            t02_a.set_enabled_biases(
                device,
                source_v=float(protocol["source_v"]),
                drain_v=vds_v,
                bottom_gate_v=float(protocol["bottom_gate_v"]),
                top_gate_v=0.0,
            )
            last_low_vds = core.solve_dc(
                device,
                runtime,
                f"T02_B_LOW_VDS_{vds_v:.6g}_V",
                coupled=True,
            )
            solver_records.append(last_low_vds)
        if last_low_vds is None:
            raise RuntimeError("T02-B low-VDS ladder is empty")

        top_values = [float(value) for value in protocol["top_gate_values_v"]]
        for index, vtg_v in enumerate(top_values):
            if index == 0 and same_value(vtg_v, 0.0):
                solve_record = last_low_vds
            else:
                t02_a.set_enabled_biases(
                    device,
                    source_v=float(protocol["source_v"]),
                    drain_v=float(protocol["drain_v"]),
                    bottom_gate_v=float(protocol["bottom_gate_v"]),
                    top_gate_v=vtg_v,
                )
                solve_record = core.solve_dc(
                    device,
                    runtime,
                    f"T02_B_VTG_{vtg_v:.6g}_V",
                    coupled=True,
                )
                solver_records.append(solve_record)
            row = collect_bias_row(
                device,
                runtime,
                mesh_level,
                mode_id,
                float(protocol["bottom_gate_v"]),
                vtg_v,
                float(protocol["drain_v"]),
                solve_record,
            )
            rows.append(row)
            if any(same_value(vtg_v, value) for value in protocol["state_top_gate_values_v"]):
                state_id = (
                    "top_gate_zero_reference"
                    if same_value(vtg_v, 0.0)
                    else "top_gate_positive_endpoint"
                )
                state_label = (
                    "VTG=0 V reference at fixed VDS and VBG"
                    if same_value(vtg_v, 0.0)
                    else "VTG=0.3 V positive endpoint at fixed VDS and VBG"
                )
                state_entries.append(
                    write_endpoint_state(
                        device,
                        runtime,
                        mode_id,
                        state_id,
                        state_label,
                        {
                            "source_v": float(protocol["source_v"]),
                            "drain_v": float(protocol["drain_v"]),
                            "bottom_gate_v": float(protocol["bottom_gate_v"]),
                            "top_gate_v": vtg_v,
                        },
                        run_dir,
                    )
                )
    except Exception as error:  # noqa: BLE001
        caught_error = error
        solver_log["errors"].append({"error": repr(error)})
    finally:
        if device in core.devsim.get_device_list():
            core.devsim.delete_device(device=device)

    solver_log["runs"].append(
        {
            "mode_id": mode_id,
            "status": "PASS" if caught_error is None else "FAIL",
            "solver_records": solver_records,
        }
    )
    core.write_csv(bias_path, rows, BIAS_FIELDNAMES)
    state_summary_rows = [
        {
            "state_id": entry["state_id"],
            "state_label": entry["state_label"],
            "vtg_v": entry["bias"]["top_gate_v"],
            "vbg_v": entry["bias"]["bottom_gate_v"],
            "vds_v": entry["bias"]["drain_v"],
            "source_current_a_per_cm": entry["source_current_a_per_cm"],
            "drain_current_a_per_cm": entry["drain_current_a_per_cm"],
            "relative_current_imbalance": entry["relative_current_imbalance"],
            "center_channel_potential_v": entry["center_channel_potential_v"],
            "center_channel_electron_density_cm3": entry[
                "center_channel_electron_density_cm3"
            ],
            "node_row_count": entry["node_count_with_interface_duplicates"],
            "state_csv": entry["state_csv"],
            "state_csv_sha256": entry["state_csv_sha256"],
            "vtk_file_count": entry["vtk_file_count"],
        }
        for entry in state_entries
    ]
    core.write_csv(state_summary_path, state_summary_rows, STATE_SUMMARY_FIELDNAMES)
    core.write_json(state_manifest_path, {
        "case_id": config["case_id"],
        "stage": config["stage"],
        "entries": state_entries,
    })
    core.write_json(solver_log_path, solver_log)

    figure_sha256: str | None = None
    if caught_error is None and len(rows) == len(protocol["top_gate_values_v"]):
        try:
            figure_sha256 = render_figure(config, rows, figure_path)
        except Exception as error:  # noqa: BLE001
            caught_error = error
            solver_log["errors"].append({"error": repr(error)})
            core.write_json(solver_log_path, solver_log)

    if caught_error is None and len(rows) == len(protocol["top_gate_values_v"]):
        assessment = assess(
            config,
            contract_report,
            t02_a_report,
            topology,
            zero_equilibrium,
            rows,
            state_entries,
            solver_records,
            figure_path,
        )
    else:
        assessment = {
            "status": "FAIL",
            "checks": {"stage_exception": {"status": "FAIL", "detail": repr(caught_error)}},
            "failures": ["stage_exception"],
            "maximum_relative_terminal_current_imbalance": None,
            "endpoint_current_ratio": None,
            "endpoint_center_potential_increase_v": None,
            "endpoint_center_density_ratio": None,
        }
    passed = assessment["status"] == "PASS"
    report = {
        "status": assessment["status"],
        "case_id": config["case_id"],
        "stage": config["stage"],
        "evidence_level": "E2" if passed else "E0",
        "model_scope": "2D n-IGZO electron-only drift-diffusion teaching model with the frozen T02-A enabled symmetric top stack",
        "input_snapshot": str(snapshot_path.relative_to(ROOT)),
        "reproduction": {
            "contract_command": "make t02-b-contract-check",
            "command": "make t02-b-minimal",
            "validation_command": "make t02-b-minimal-check",
            "python_executable": sys.executable,
            "devsim_version": getattr(core.devsim, "__version__", "2.10.0"),
        },
        "topology": topology,
        "zero_equilibrium": zero_equilibrium,
        "bias_points": rows,
        "state_outputs": state_entries,
        "figure": {"path": str(figure_path.relative_to(ROOT)), "sha256": figure_sha256},
        "checks": assessment["checks"],
        "failures": assessment["failures"],
        "summary_metrics": {
            key: value
            for key, value in assessment.items()
            if key not in {"status", "checks", "failures"}
        },
        "t02_b_completion": {
            "status": "PASS" if passed else "FAIL",
            "minimal_nonzero_top_gate_family_completed": passed,
            "top_gate_response_direction_verified": passed,
            "t02_c_bidirectional_family_permitted_next": passed,
            "t02_complete": False,
            "delta_vth_verified": False,
            "gm_verified": False,
            "experimental_calibration_permitted": False,
        },
        "limitations": [
            "Only VTG=0/0.1/0.2/0.3 V was run at VDS=0.01 V and VBG=0 V on the frozen teaching model.",
            "The family is a one-direction minimal response check; negative or reverse top-gate sweeps remain unverified.",
            "No Delta VTH, gm, SS, mobility, capacitance ratio, coupling slope, experimental calibration, or physical Ion/Ioff claim is established.",
            "Traps, non-ideal contacts, recombination, ferroelectric polarization, and uncertainty remain absent.",
        ],
        "outputs": {key: value for key, value in outputs.items() if key != "check_report"},
        "evidence_boundary": config["evidence_boundary"],
    }
    core.write_json(report_path, report)
    print(
        f"T02_B_MINIMAL_{report['status']} points={len(rows)} "
        f"dc_solves={len(solver_records)} report={report_path}"
    )
    if caught_error is not None:
        print(f"T02_B_MINIMAL_ERROR {caught_error}", file=sys.stderr)
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
