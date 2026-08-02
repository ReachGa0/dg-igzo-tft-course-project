#!/usr/bin/env python3
"""Independently validate persisted formal T03-P3 V2 contact evidence."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import struct
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "tcad_t03_p3_contact_resistance.json"
CHECKER_PATH = Path(__file__).resolve()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_csv(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader), list(reader.fieldnames or [])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def same_value(left: float, right: float, *, abs_tol: float = 1.0e-12) -> bool:
    return math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=abs_tol)


def close(
    left: float,
    right: float,
    *,
    rel_tol: float = 1.0e-10,
    abs_tol: float = 1.0e-15,
) -> bool:
    return math.isclose(
        float(left), float(right), rel_tol=rel_tol, abs_tol=abs_tol
    )


def relative_difference(left: float, right: float, *, floor: float = 1.0e-300) -> float:
    return abs(float(left) - float(right)) / max(
        abs(float(left)), abs(float(right)), floor
    )


def as_bool(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"not a persisted Python boolean: {value!r}")


def add_check(
    checks: list[dict[str, Any]], name: str, passed: bool, detail: str
) -> None:
    checks.append(
        {"name": name, "status": "PASS" if passed else "FAIL", "detail": detail}
    )


def transfer_grid(config: dict[str, Any]) -> list[float]:
    spec = config["bias_protocol"]["transfer"]["primary_gate_grid"]
    start = float(spec["start_v"])
    stop = float(spec["stop_v"])
    step = float(spec["step_v"])
    intervals = round((stop - start) / step)
    if intervals < 1 or not same_value(start + intervals * step, stop):
        raise ValueError("T03-P3 transfer grid is not integral")
    return [round(start + index * step, 12) for index in range(intervals + 1)]


def case_ids(config: dict[str, Any]) -> list[str]:
    return [str(case["case_id"]) for case in config["sensitivity"]["cases"]]


def case_for(config: dict[str, Any], case_id: str) -> dict[str, Any]:
    return next(
        case for case in config["sensitivity"]["cases"] if case["case_id"] == case_id
    )


def curve(
    rows: list[dict[str, str]], case_id: str, curve_kind: str, vtg_v: float | None = None
) -> list[dict[str, str]]:
    selected = [
        row
        for row in rows
        if row["case_id"] == case_id
        and row["curve_kind"] == curve_kind
        and (vtg_v is None or same_value(float(row["vtg_v"]), vtg_v))
    ]
    key = "vtg_v" if curve_kind == "transfer" else "external_vds_v"
    return sorted(selected, key=lambda row: float(row[key]))


def point_for(
    rows: list[dict[str, str]],
    case_id: str,
    curve_kind: str,
    *,
    vtg_v: float,
    vds_v: float,
) -> dict[str, str]:
    selected = [
        row
        for row in rows
        if row["case_id"] == case_id
        and row["curve_kind"] == curve_kind
        and same_value(float(row["vtg_v"]), vtg_v)
        and same_value(float(row["external_vds_v"]), vds_v, abs_tol=1.0e-9)
    ]
    if len(selected) != 1:
        raise RuntimeError(
            f"expected one {case_id}/{curve_kind}/VTG={vtg_v}/VDS={vds_v}; "
            f"found {len(selected)}"
        )
    return selected[0]


def report_csv_rows_match(
    report_rows: list[dict[str, Any]], csv_rows: list[dict[str, str]], fields: list[str]
) -> bool:
    text_fields = {
        "point_uid",
        "parameter_group_id",
        "changed_parameter",
        "case_id",
        "execution_mode",
        "device_id",
        "curve_kind",
        "curve_id",
        "mesh_level",
        "stage_id",
        "mode_id",
        "circuit_solution_list_json",
    }
    bool_fields = {"circuit_coupled", "circuit_closure_applicable", "converged"}
    if len(report_rows) != len(csv_rows):
        return False
    for report_row, csv_row in zip(report_rows, csv_rows, strict=True):
        for field in fields:
            if field in text_fields:
                if str(report_row[field]) != csv_row[field]:
                    return False
            elif field in bool_fields:
                if bool(report_row[field]) is not as_bool(csv_row[field]):
                    return False
            elif not close(
                float(report_row[field]),
                float(csv_row[field]),
                rel_tol=2.0e-12,
                abs_tol=1.0e-300,
            ):
                return False
    return True


def png_dimensions(path: Path) -> tuple[int, int]:
    with path.open("rb") as stream:
        header = stream.read(24)
    if (
        len(header) != 24
        or header[:8] != b"\x89PNG\r\n\x1a\n"
        or header[12:16] != b"IHDR"
    ):
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def nearest_channel_state(
    rows: list[dict[str, str]], baseline: dict[str, Any]
) -> dict[str, float]:
    target_x = float(baseline["geometry"]["channel_length_cm"]) / 2.0
    target_y = float(baseline["geometry"]["bottom_oxide_thickness_cm"]) + (
        float(baseline["geometry"]["channel_thickness_cm"]) / 2.0
    )
    channel = [row for row in rows if row["region"] == "channel"]
    nearest = min(
        channel,
        key=lambda row: (float(row["x_cm"]) - target_x) ** 2
        + (float(row["y_cm"]) - target_y) ** 2,
    )
    return {
        "potential_v": float(nearest["potential_v"]),
        "electron_density_cm3": float(nearest["electron_density_cm3"]),
    }


def checker_is_independent() -> tuple[bool, str]:
    tree = ast.parse(CHECKER_PATH.read_text(encoding="utf-8"))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
    forbidden = [
        name
        for name in imported
        if name == "devsim" or name.startswith("run_t03_p3_contact_resistance")
    ]
    return not forbidden, f"imports={sorted(imported)} forbidden={forbidden}"


def main() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    paths = {
        name: ROOT / value for name, value in outputs.items() if name != "run_directory"
    }
    run_dir = ROOT / outputs["run_directory"]
    report = load_json(paths["report"])
    contract = load_json(paths["contract_report"])
    snapshot = load_json(paths["config_snapshot"])
    solver_log = load_json(paths["solver_log"])
    state_manifest = load_json(paths["state_manifest"])
    transfer_rows, transfer_fields = load_csv(paths["transfer_csv"])
    output_rows, output_fields = load_csv(paths["output_csv"])
    metric_rows, metric_fields = load_csv(paths["metric_csv"])
    balance_rows, balance_fields = load_csv(paths["circuit_balance_csv"])
    reference_rows, reference_fields = load_csv(paths["reference_comparison_csv"])
    state_summary_rows, state_summary_fields = load_csv(paths["state_summary_csv"])
    baseline = load_json(ROOT / config["dependencies"]["t01_baseline_config"])
    t02_report = load_json(ROOT / config["dependencies"]["t02_c_report"])
    acceptance = config["acceptance"]
    ids = case_ids(config)
    checks: list[dict[str, Any]] = []

    runner_checks = report.get("checks", {})
    add_check(
        checks,
        "identity:runner_contract_stage_and_all_runner_gates_passed",
        report.get("status") == "PASS"
        and config.get("schema_version") == 2
        and config.get("revision") == 2
        and config.get("case_id") == "IGZO_T03_P3_CONTACT_RESISTANCE_V2"
        and report.get("case_id") == config["case_id"]
        and report.get("stage") == config["stage"]
        and report.get("parameter_group_id") == "P3"
        and report.get("evidence_level") == "E2"
        and report.get("formal_sensitivity_run") is True
        and report.get("independent_persisted_evidence_check_complete") is False
        and contract.get("contract_status") == "PASS"
        and contract.get("config", {}).get("sha256") == sha256(CONFIG_PATH)
        and len(runner_checks) == 25
        and all(item.get("status") == "PASS" for item in runner_checks.values())
        and not report.get("failures"),
        (
            f"runner={report.get('status')}/{report.get('evidence_level')} "
            f"contract={contract.get('contract_status')} checks={len(runner_checks)}"
        ),
    )

    snapshot_inputs = snapshot.get("inputs", {})
    inputs_valid = (
        snapshot.get("case_id") == config["case_id"]
        and snapshot.get("stage") == config["stage"]
        and snapshot.get("parameter_group_id") == "P3"
        and snapshot.get("devsim_version") == "2.10.0"
        and "runner_script" in snapshot_inputs
        and all(
            (ROOT / item["path"]).is_file()
            and item["sha256"] == sha256(ROOT / item["path"])
            for item in snapshot_inputs.values()
        )
        and snapshot.get("contract_recorded_machine_state")
        == {
            name: contract["inputs"][name]
            for name in ("project_config", "experiments_config")
        }
    )
    add_check(
        checks,
        "inputs:snapshot_hashes_and_circuit_api_provenance_match",
        inputs_valid
        and snapshot.get("circuit_api", {}).get("terminal_current_scaling")
        == (
            "2D contact edge current multiplied by frozen device width before "
            "integration into the external circuit"
        ),
        f"inputs={len(snapshot_inputs)} devsim={snapshot.get('devsim_version')}",
    )

    artifact_names = (
        "config_snapshot",
        "solver_log",
        "state_manifest",
        "transfer_csv",
        "output_csv",
        "metric_csv",
        "circuit_balance_csv",
        "reference_comparison_csv",
        "state_summary_csv",
    )
    artifact_valid = all(
        paths[name].is_file()
        and report["artifacts"][name]["path"] == str(paths[name].relative_to(ROOT))
        and report["artifacts"][name]["sha256"] == sha256(paths[name])
        for name in artifact_names
    )
    add_check(
        checks,
        "artifacts:runner_hashes_match_all_primary_persisted_outputs",
        artifact_valid,
        f"artifacts={len(artifact_names)}",
    )

    required_point_fields = {
        "point_uid",
        "case_id",
        "r_pair_w_kohm_um",
        "r_pair_ohm",
        "execution_mode",
        "circuit_coupled",
        "device_id",
        "curve_kind",
        "curve_id",
        "point_index",
        "stage_id",
        "vbg_v",
        "vtg_v",
        "external_source_v",
        "external_drain_v",
        "external_vds_v",
        "internal_source_v",
        "internal_drain_v",
        "internal_device_vds_v",
        "source_current_a_per_cm",
        "drain_current_a_per_cm",
        "source_current_terminal_a",
        "drain_current_terminal_a",
        "external_source_current_terminal_a",
        "external_drain_current_terminal_a",
        "source_resistor_current_external_to_internal_a",
        "drain_resistor_current_external_to_internal_a",
        "source_kcl_residual_a",
        "drain_kcl_residual_a",
        "source_kcl_relative_residual",
        "drain_kcl_relative_residual",
        "source_drop_v",
        "drain_drop_v",
        "total_resistor_drop_v",
        "circuit_ohms_law_residual_v",
        "circuit_ohms_law_relative_residual",
        "voltage_partition_residual_v",
        "total_resistor_power_w",
        "circuit_closure_applicable",
        "center_channel_potential_v",
        "center_channel_electron_density_cm3",
        "converged",
    }
    all_rows = [*transfer_rows, *output_rows]
    grids_valid = all(
        [float(row["vtg_v"]) for row in curve(transfer_rows, case_id, "transfer")]
        == transfer_grid(config)
        for case_id in ids
    )
    output_vds = [
        float(value)
        for value in config["bias_protocol"]["output"]["external_drain_values_v"]
    ]
    output_grid_valid = all(
        [
            float(row["external_vds_v"])
            for row in curve(output_rows, case_id, "output", gate)
        ]
        == output_vds
        for case_id in ids
        for gate in (0.3, 0.5, 1.0)
    )
    point_uids = [row["point_uid"] for row in all_rows]
    points_valid = (
        required_point_fields <= set(transfer_fields)
        and transfer_fields == output_fields
        and len(transfer_rows) == int(acceptance["required_transfer_point_count"])
        and len(output_rows) == int(acceptance["required_output_point_count"])
        and len(all_rows) == int(acceptance["required_total_reported_point_count"])
        and len(set(point_uids)) == len(point_uids)
        and grids_valid
        and output_grid_valid
        and all(
            row["stage_id"] == "T03_P3_CONTACT_RESISTANCE"
            and row["parameter_group_id"] == "P3"
            and same_value(float(row["vbg_v"]), 0.0)
            and as_bool(row["converged"])
            for row in all_rows
        )
    )
    add_check(
        checks,
        "points:headers_unique_ids_exact_cases_bias_grids_and_counts_match",
        points_valid,
        (
            f"fields={len(transfer_fields)} transfer={len(transfer_rows)} "
            f"output={len(output_rows)} grids={grids_valid}/{output_grid_valid}"
        ),
    )

    report_rows_match = report_csv_rows_match(
        report.get("transfer_points", []), transfer_rows, transfer_fields
    ) and report_csv_rows_match(
        report.get("output_points", []), output_rows, output_fields
    )
    add_check(
        checks,
        "points:runner_report_embedded_points_match_csv_values",
        report_rows_match,
        f"report_transfer={len(report.get('transfer_points', []))} report_output={len(report.get('output_points', []))}",
    )

    runs = solver_log.get("runs", [])
    records = solver_log.get("solver_records", [])
    expected_counts: list[int] = []
    expected_run_identity: list[tuple[str, str, float | None]] = []
    for case_id in ids:
        expected_counts.extend([41, 12, 13, 15])
        expected_run_identity.extend(
            [
                (case_id, "transfer", None),
                (case_id, "output", 0.3),
                (case_id, "output", 0.5),
                (case_id, "output", 1.0),
            ]
        )
    observed_identity = [
        (
            str(run["case_id"]),
            str(run["curve_kind"]),
            None
            if run.get("target_top_gate_v") is None
            else float(run["target_top_gate_v"]),
        )
        for run in runs
    ]
    solve_roles = [record.get("solve_role") for record in records]
    solver_valid = (
        observed_identity == expected_run_identity
        and [int(run["dc_solve_count"]) for run in runs] == expected_counts
        and len(records) == int(acceptance["required_total_dc_solve_count"])
        and all(record.get("converged") is True for record in records)
        and solve_roles.count("poisson_zero") == 12
        and solve_roles.count("coupled_zero") == 12
        and solve_roles.count("reported_transfer") == 93
        and solve_roles.count("reported_output") == 63
        and not solver_log.get("errors")
        and solver_log.get("current_device") is None
        and float(solver_log.get("wall_seconds", math.inf))
        <= float(config["resource_budget"]["maximum_wall_seconds"])
    )
    add_check(
        checks,
        "solver:twelve_fresh_devices_and_243_frozen_dc_records_converged",
        solver_valid,
        (
            f"runs={len(runs)} counts={[run.get('dc_solve_count') for run in runs]} "
            f"records={len(records)} wall={solver_log.get('wall_seconds')}"
        ),
    )

    expected_circuit_nodes = {
        "p3_source_external",
        "p3_source_internal",
        "p3_drain_external",
        "p3_drain_internal",
        "VP3SourceExternal.I",
        "VP3DrainExternal.I",
    }
    execution_valid = True
    circuit_run_count = 0
    for run in runs:
        case = case_for(config, str(run["case_id"]))
        expected_coupled = float(case["r_pair_ohm"]) > 0.0
        observed_coupled = bool(run["circuit_coupled"])
        execution_valid = execution_valid and observed_coupled is expected_coupled
        if observed_coupled:
            circuit_run_count += 1
            execution_valid = execution_valid and expected_circuit_nodes <= set(
                run["circuit_nodes"]
            )
        else:
            execution_valid = execution_valid and run["circuit_nodes"] == []
    for row in all_rows:
        case = case_for(config, row["case_id"])
        expected_coupled = float(case["r_pair_ohm"]) > 0.0
        execution_valid = execution_valid and as_bool(row["circuit_coupled"]) is expected_coupled
        execution_valid = execution_valid and close(
            float(row["r_pair_ohm"]), float(case["r_pair_ohm"]), rel_tol=1.0e-13
        )
        execution_valid = execution_valid and close(
            float(row["r_pair_w_kohm_um"]),
            float(case["r_pair_w_kohm_um"]),
            rel_tol=1.0e-13,
        )
        expected_mode = str(case["execution_mode"])
        execution_valid = execution_valid and row["execution_mode"] == expected_mode
    add_check(
        checks,
        "coupling:ideal_direct_and_eight_nonzero_circuit_devices_are_exact",
        execution_valid
        and circuit_run_count
        == int(config["resource_budget"]["required_circuit_coupled_device_count"]),
        f"circuit_runs={circuit_run_count} exact={execution_valid}",
    )

    width_cm = float(baseline["device"]["width_cm"])
    maximum_all_point_imbalance = 0.0
    maximum_nonzero_vds_imbalance = 0.0
    nonzero_vds_row_count = 0
    current_units_valid = True
    for row in all_rows:
        source = float(row["source_current_a_per_cm"])
        drain = float(row["drain_current_a_per_cm"])
        imbalance = abs(source + drain) / max(abs(source), abs(drain), 1.0e-300)
        maximum_all_point_imbalance = max(maximum_all_point_imbalance, imbalance)
        if float(row["external_vds_v"]) > 1.0e-12:
            nonzero_vds_row_count += 1
            maximum_nonzero_vds_imbalance = max(
                maximum_nonzero_vds_imbalance, imbalance
            )
        current_units_valid = current_units_valid and close(
            float(row["source_current_terminal_a"]), source * width_cm,
            rel_tol=5.0e-11, abs_tol=1.0e-25,
        ) and close(
            float(row["drain_current_terminal_a"]), drain * width_cm,
            rel_tol=5.0e-11, abs_tol=1.0e-25,
        )
        current_units_valid = current_units_valid and close(
            float(row["relative_current_imbalance"]),
            abs(source + drain) / max(abs(source), abs(drain), 1.0e-300),
            rel_tol=5.0e-11,
            abs_tol=1.0e-30,
        )
    add_check(
        checks,
        "transport:terminal_width_conversion_and_nonzero_vds_device_current_conservation_recompute",
        current_units_valid
        and acceptance["relative_device_terminal_current_imbalance_gate_domain"]
        == "external VDS>0"
        and nonzero_vds_row_count == len(all_rows) - 9
        and maximum_nonzero_vds_imbalance
        <= float(acceptance["maximum_relative_device_terminal_current_imbalance"]),
        (
            f"units={current_units_valid} rows={nonzero_vds_row_count} "
            f"maximum_nonzero_vds_imbalance={maximum_nonzero_vds_imbalance:.6e} "
            f"maximum_all_point_imbalance_nongating={maximum_all_point_imbalance:.6e}"
        ),
    )

    closure_rows = [row for row in all_rows if as_bool(row["circuit_closure_applicable"])]
    maximum_kcl = 0.0
    maximum_ohm = 0.0
    maximum_partition = 0.0
    closure_recomputed = True
    floor = float(acceptance["circuit_relative_residual_floor_a"])
    for row in closure_rows:
        case = case_for(config, row["case_id"])
        source_r = float(case["r_source_ohm"])
        drain_r = float(case["r_drain_ohm"])
        source_external = float(row["external_source_v"])
        source_internal = float(row["internal_source_v"])
        drain_external = float(row["external_drain_v"])
        drain_internal = float(row["internal_drain_v"])
        source_resistor = (source_external - source_internal) / source_r
        drain_resistor = (drain_external - drain_internal) / drain_r
        source_terminal = float(row["source_current_terminal_a"])
        drain_terminal = float(row["drain_current_terminal_a"])
        source_kcl = source_terminal - source_resistor
        drain_kcl = drain_terminal - drain_resistor
        source_relative = abs(source_kcl) / max(
            abs(source_terminal), abs(source_resistor), floor
        )
        drain_relative = abs(drain_kcl) / max(
            abs(drain_terminal), abs(drain_resistor), floor
        )
        source_drop = source_internal - source_external
        drain_drop = drain_external - drain_internal
        total_drop = source_drop + drain_drop
        expected_drop = abs(float(row["external_drain_current_terminal_a"])) * float(
            case["r_pair_ohm"]
        )
        ohm_residual = total_drop - expected_drop
        ohm_relative = abs(ohm_residual) / max(
            abs(total_drop), abs(expected_drop), 1.0e-30
        )
        internal_vds = drain_internal - source_internal
        external_vds = drain_external - source_external
        partition = external_vds - (source_drop + internal_vds + drain_drop)
        power = source_resistor**2 * source_r + drain_resistor**2 * drain_r
        pairs = (
            (source_resistor, row["source_resistor_current_external_to_internal_a"]),
            (drain_resistor, row["drain_resistor_current_external_to_internal_a"]),
            (source_kcl, row["source_kcl_residual_a"]),
            (drain_kcl, row["drain_kcl_residual_a"]),
            (source_relative, row["source_kcl_relative_residual"]),
            (drain_relative, row["drain_kcl_relative_residual"]),
            (source_drop, row["source_drop_v"]),
            (drain_drop, row["drain_drop_v"]),
            (total_drop, row["total_resistor_drop_v"]),
            (ohm_residual, row["circuit_ohms_law_residual_v"]),
            (ohm_relative, row["circuit_ohms_law_relative_residual"]),
            (partition, row["voltage_partition_residual_v"]),
            (power, row["total_resistor_power_w"]),
        )
        closure_recomputed = closure_recomputed and all(
            close(expected, float(observed), rel_tol=5.0e-10, abs_tol=1.0e-20)
            for expected, observed in pairs
        )
        maximum_kcl = max(maximum_kcl, source_relative, drain_relative)
        maximum_ohm = max(maximum_ohm, ohm_relative)
        maximum_partition = max(maximum_partition, abs(partition))
    add_check(
        checks,
        "circuit:kcl_ohm_voltage_partition_and_power_recompute_within_gates",
        closure_recomputed
        and bool(closure_rows)
        and maximum_kcl <= float(acceptance["maximum_circuit_kcl_relative_residual"])
        and maximum_ohm
        <= float(acceptance["maximum_circuit_ohms_law_relative_residual"])
        and maximum_partition
        <= float(acceptance["maximum_circuit_voltage_partition_absolute_residual_v"])
        and all(float(row["total_resistor_power_w"]) >= -1.0e-30 for row in closure_rows),
        (
            f"rows={len(closure_rows)} recomputed={closure_recomputed} "
            f"kcl={maximum_kcl:.6e} ohm={maximum_ohm:.6e} "
            f"partition={maximum_partition:.6e}"
        ),
    )

    balance_by_uid = {row["point_uid"]: row for row in balance_rows}
    balance_valid = (
        len(balance_rows) == len(all_rows)
        and len(balance_by_uid) == len(all_rows)
        and set(balance_fields) <= set(transfer_fields)
    )
    for point in all_rows:
        persisted = balance_by_uid.get(point["point_uid"])
        if persisted is None:
            balance_valid = False
            continue
        for field in balance_fields:
            if field in {
                "point_uid",
                "case_id",
                "curve_kind",
                "curve_id",
            }:
                balance_valid = balance_valid and persisted[field] == point[field]
            elif field in {"circuit_coupled", "circuit_closure_applicable"}:
                balance_valid = balance_valid and as_bool(persisted[field]) is as_bool(
                    point[field]
                )
            else:
                balance_valid = balance_valid and close(
                    float(persisted[field]),
                    float(point[field]),
                    rel_tol=2.0e-12,
                    abs_tol=1.0e-300,
                )
    add_check(
        checks,
        "circuit:dedicated_balance_table_matches_every_reported_point",
        balance_valid,
        f"rows={len(balance_rows)} fields={len(balance_fields)} exact={balance_valid}",
    )

    zero_rows = [
        row
        for row in output_rows
        if same_value(float(row["external_vds_v"]), 0.0, abs_tol=1.0e-9)
    ]
    maximum_zero = max(
        abs(float(row["external_drain_current_a_per_cm"])) for row in zero_rows
    )
    rail_tolerance = float(
        acceptance["maximum_circuit_voltage_partition_absolute_residual_v"]
    )
    circuit_rows = [row for row in all_rows if as_bool(row["circuit_coupled"])]
    rails_valid = all(
        float(row["external_source_v"]) - rail_tolerance
        <= float(row["internal_source_v"])
        <= float(row["internal_drain_v"]) + rail_tolerance
        and float(row["internal_drain_v"])
        <= float(row["external_drain_v"]) + rail_tolerance
        for row in circuit_rows
    )
    resolved = [
        abs(float(row["external_drain_current_a_per_cm"]))
        for row in all_rows
        if float(row["external_vds_v"]) > 0.0
        and float(row["vtg_v"]) >= 0.3 - 1.0e-12
    ]
    add_check(
        checks,
        "bias:zero_vds_current_resolved_positive_current_and_internal_rails_pass",
        acceptance["zero_external_vds_absolute_current_gate_domain"]
        == "external VDS=0"
        and len(zero_rows) == 9
        and maximum_zero
        <= float(acceptance["maximum_zero_external_vds_absolute_current_a_per_cm"])
        and min(resolved)
        >= float(acceptance["minimum_resolved_positive_current_a_per_cm"])
        and rails_valid,
        (
            f"zero_rows={len(zero_rows)} max_zero={maximum_zero:.6e} "
            f"min_resolved={min(resolved):.6e} rails={rails_valid}"
        ),
    )

    transfer_monotonic = all(
        all(
            float(right["external_drain_current_a_per_cm"])
            > float(left["external_drain_current_a_per_cm"])
            for left, right in zip(
                curve(transfer_rows, case_id, "transfer"),
                curve(transfer_rows, case_id, "transfer")[1:],
            )
        )
        for case_id in ids
    )
    maximum_output_drop = 0.0
    for case_id in ids:
        for gate in (0.3, 0.5, 1.0):
            values = [
                abs(float(row["external_drain_current_a_per_cm"]))
                for row in curve(output_rows, case_id, "output", gate)
            ]
            maximum_output_drop = max(
                maximum_output_drop,
                max(
                    (left - right) / max(left, right, 1.0e-300)
                    for left, right in zip(values, values[1:])
                ),
            )
    add_check(
        checks,
        "curves:transfer_strict_and_output_nondecreasing_monotonicity_recompute",
        transfer_monotonic
        and maximum_output_drop
        <= float(acceptance["maximum_monotonic_relative_current_drop"]),
        f"transfer={transfer_monotonic} maximum_output_drop={maximum_output_drop:.6e}",
    )

    required_metric_fields = {
        "case_id",
        "r_pair_w_kohm_um",
        "transfer_high_gate_current_proxy_terminal_a",
        "transfer_high_gate_current_relative_reduction",
        "linear_fit_conductance_s",
        "linear_region_total_resistance_ohm",
        "linear_region_total_resistance_width_kohm_um",
        "added_total_resistance_width_kohm_um",
        "declared_pair_resistance_width_kohm_um",
        "added_resistance_relative_difference",
        "added_resistance_diagnostic_within_15_percent",
        "parameter_claim_status",
    }
    fit_vds = [0.001, 0.005, 0.01]
    width_um = float(config["sensitivity"]["width_um"])
    recomputed_metrics: list[dict[str, float | str | bool]] = []
    for case_id in ids:
        high = point_for(
            transfer_rows, case_id, "transfer", vtg_v=1.0, vds_v=0.01
        )
        fit_rows = [
            point_for(output_rows, case_id, "output", vtg_v=1.0, vds_v=value)
            for value in fit_vds
        ]
        currents = [
            abs(float(row["external_drain_current_terminal_a"])) for row in fit_rows
        ]
        conductance = sum(
            voltage * current for voltage, current in zip(fit_vds, currents, strict=True)
        ) / sum(voltage * voltage for voltage in fit_vds)
        resistance = 1.0 / conductance
        recomputed_metrics.append(
            {
                "case_id": case_id,
                "high_current": abs(float(high["external_drain_current_terminal_a"])),
                "conductance": conductance,
                "resistance": resistance,
                "resistance_width": resistance * width_um / 1000.0,
            }
        )
    ideal_high = float(recomputed_metrics[0]["high_current"])
    ideal_width = float(recomputed_metrics[0]["resistance_width"])
    metric_valid = required_metric_fields <= set(metric_fields) and len(metric_rows) == 3
    diagnostic_limit = float(
        config["diagnostic_hypotheses"][
            "extracted_added_resistance_matches_declared_pair"
        ]["maximum_relative_difference"]
    )
    for expected, persisted in zip(recomputed_metrics, metric_rows, strict=True):
        case = case_for(config, str(expected["case_id"]))
        added = float(expected["resistance_width"]) - ideal_width
        declared = float(case["r_pair_w_kohm_um"])
        difference = 0.0 if declared == 0.0 else abs(added - declared) / declared
        reduction = (ideal_high - float(expected["high_current"])) / ideal_high
        numeric_pairs = (
            (expected["high_current"], persisted["transfer_high_gate_current_proxy_terminal_a"]),
            (reduction, persisted["transfer_high_gate_current_relative_reduction"]),
            (expected["conductance"], persisted["linear_fit_conductance_s"]),
            (expected["resistance"], persisted["linear_region_total_resistance_ohm"]),
            (expected["resistance_width"], persisted["linear_region_total_resistance_width_kohm_um"]),
            (added, persisted["added_total_resistance_width_kohm_um"]),
            (declared, persisted["declared_pair_resistance_width_kohm_um"]),
            (difference, persisted["added_resistance_relative_difference"]),
        )
        metric_valid = metric_valid and persisted["case_id"] == expected["case_id"]
        metric_valid = metric_valid and all(
            close(float(value), float(observed), rel_tol=5.0e-11, abs_tol=1.0e-18)
            for value, observed in numeric_pairs
        )
        metric_valid = metric_valid and as_bool(
            persisted["added_resistance_diagnostic_within_15_percent"]
        ) is (difference <= diagnostic_limit)
        metric_valid = metric_valid and persisted["parameter_claim_status"] == (
            "NUMERICAL_LUMPED_SERIES_RESISTANCE_PROXY_NOT_MEASURED_OR_CALIBRATED"
        )
    add_check(
        checks,
        "metrics:ols_total_resistance_current_proxies_and_diagnostic_recompute",
        metric_valid,
        json.dumps(recomputed_metrics, sort_keys=True),
    )

    report_metric_valid = len(report.get("metrics", [])) == len(metric_rows)
    metric_text = {"parameter_group_id", "case_id", "parameter_claim_status"}
    metric_bool = {"added_resistance_diagnostic_within_15_percent"}
    for report_row, csv_row in zip(report.get("metrics", []), metric_rows):
        for field in metric_fields:
            if field in metric_text:
                report_metric_valid = report_metric_valid and str(report_row[field]) == csv_row[field]
            elif field in metric_bool:
                report_metric_valid = report_metric_valid and bool(report_row[field]) is as_bool(csv_row[field])
            else:
                report_metric_valid = report_metric_valid and close(
                    float(report_row[field]), float(csv_row[field]),
                    rel_tol=2.0e-12, abs_tol=1.0e-300,
                )
    add_check(
        checks,
        "metrics:runner_report_and_metric_csv_match",
        report_metric_valid,
        f"report={len(report.get('metrics', []))} csv={len(metric_rows)}",
    )

    selected_ordering_valid = True
    ordering_count = 0
    for kind, items, rows in (
        (
            "transfer",
            acceptance["required_current_ordering_biases"]["transfer"],
            transfer_rows,
        ),
        (
            "output",
            acceptance["required_current_ordering_biases"]["output"],
            output_rows,
        ),
    ):
        for item in items:
            values = [
                abs(
                    float(
                        point_for(
                            rows,
                            case_id,
                            kind,
                            vtg_v=float(item["vtg_v"]),
                            vds_v=float(item["external_vds_v"]),
                        )["external_drain_current_terminal_a"]
                    )
                )
                for case_id in ids
            ]
            selected_ordering_valid = selected_ordering_valid and values[0] > values[1] > values[2]
            ordering_count += 1
    resistance_widths = [float(row["resistance_width"]) for row in recomputed_metrics]
    high_reduction = (
        ideal_high - float(recomputed_metrics[-1]["high_current"])
    ) / ideal_high
    add_check(
        checks,
        "response:selected_current_ordering_resistance_ordering_and_minimum_response_pass",
        selected_ordering_valid
        and ordering_count == 9
        and resistance_widths[0] < resistance_widths[1] < resistance_widths[2]
        and high_reduction
        >= float(
            acceptance[
                "minimum_high_proxy_relative_current_reduction_at_largest_r_pair"
            ]
        ),
        (
            f"orderings={ordering_count}/{selected_ordering_valid} "
            f"RtotalW={resistance_widths} high_reduction={high_reduction:.6e}"
        ),
    )

    t02_references = [
        row
        for row in t02_report["family_points"]
        if row["family_id"] == "top_primary"
        and row["sweep_direction"] == "forward"
        and same_value(float(row["fixed_secondary_gate_v"]), 0.0)
    ]
    reference_valid = len(reference_rows) == 31 and {
        "primary_gate_v",
        "p3_abs_external_drain_current_a_per_cm",
        "t02_c_abs_drain_current_a_per_cm",
        "current_relative_difference",
        "center_channel_potential_difference_v",
        "center_density_relative_difference",
    } <= set(reference_fields)
    max_reference_current = 0.0
    max_reference_potential = 0.0
    max_reference_density = 0.0
    for persisted in reference_rows:
        gate = float(persisted["primary_gate_v"])
        p3 = point_for(
            transfer_rows, "ideal_control", "transfer", vtg_v=gate, vds_v=0.01
        )
        t02 = next(
            row
            for row in t02_references
            if same_value(float(row["primary_gate_v"]), gate)
        )
        p3_current = abs(float(p3["external_drain_current_a_per_cm"]))
        t02_current = abs(float(t02["drain_current_a_per_cm"]))
        current_difference = relative_difference(p3_current, t02_current)
        potential_difference = abs(
            float(p3["center_channel_potential_v"])
            - float(t02["center_channel_potential_v"])
        )
        density_difference = relative_difference(
            float(p3["center_channel_electron_density_cm3"]),
            float(t02["center_channel_electron_density_cm3"]),
        )
        expected = (
            (p3_current, persisted["p3_abs_external_drain_current_a_per_cm"]),
            (t02_current, persisted["t02_c_abs_drain_current_a_per_cm"]),
            (current_difference, persisted["current_relative_difference"]),
            (potential_difference, persisted["center_channel_potential_difference_v"]),
            (density_difference, persisted["center_density_relative_difference"]),
        )
        reference_valid = reference_valid and all(
            close(value, float(observed), rel_tol=5.0e-11, abs_tol=1.0e-18)
            for value, observed in expected
        )
        max_reference_current = max(max_reference_current, current_difference)
        max_reference_potential = max(max_reference_potential, potential_difference)
        max_reference_density = max(max_reference_density, density_difference)
    add_check(
        checks,
        "reference:ideal_transfer_recomputes_against_persisted_t02_c",
        reference_valid
        and max_reference_current
        <= float(acceptance["maximum_t02_c_reference_current_relative_difference"])
        and max_reference_potential
        <= float(acceptance["maximum_t02_c_reference_center_potential_difference_v"])
        and max_reference_density
        <= float(acceptance["maximum_t02_c_reference_center_density_relative_difference"]),
        (
            f"rows={len(reference_rows)} valid={reference_valid} "
            f"current={max_reference_current:.6e} potential={max_reference_potential:.6e} "
            f"density={max_reference_density:.6e}"
        ),
    )

    manifest_entries = state_manifest.get("entries", [])
    summary_by_id = {row["state_id"]: row for row in state_summary_rows}
    state_valid = (
        state_manifest.get("case_id") == config["case_id"]
        and state_manifest.get("stage") == config["stage"]
        and int(state_manifest.get("entry_count", -1))
        == int(acceptance["required_state_count"])
        and len(manifest_entries) == int(acceptance["required_state_count"])
        and len(state_summary_rows) == int(acceptance["required_state_count"])
        and {
            "state_id",
            "case_id",
            "r_pair_w_kohm_um",
            "node_row_count",
            "channel_element_count",
            "node_csv",
            "element_csv",
            "vtk_file_count",
        }
        <= set(state_summary_fields)
    )
    vtk_count = 0
    node_count = 0
    element_count = 0
    final_points = {
        case_id: point_for(
            output_rows, case_id, "output", vtg_v=1.0, vds_v=0.2
        )
        for case_id in ids
    }
    for entry in manifest_entries:
        state_id = str(entry["state_id"])
        case_id = str(entry["case_id"])
        summary = summary_by_id.get(state_id)
        node_path = ROOT / entry["node_csv"]
        element_path = ROOT / entry["element_csv"]
        if summary is None or not node_path.is_file() or not element_path.is_file():
            state_valid = False
            continue
        node_rows, node_fields = load_csv(node_path)
        element_rows, element_fields = load_csv(element_path)
        channel_nodes = [row for row in node_rows if row["region"] == "channel"]
        nearest = nearest_channel_state(node_rows, baseline)
        final = final_points[case_id]
        node_count += len(node_rows)
        element_count += len(element_rows)
        state_valid = state_valid and {
            "state_id",
            "case_id",
            "region",
            "x_cm",
            "y_cm",
            "potential_v",
            "electron_density_cm3",
            "internal_source_v",
            "internal_drain_v",
        } <= set(node_fields)
        state_valid = state_valid and {
            "state_id",
            "case_id",
            "element_index",
            "centroid_x_cm",
            "centroid_y_cm",
            "electron_current_density_magnitude_a_per_cm2",
            "projection_method",
        } <= set(element_fields)
        state_valid = state_valid and len(node_rows) == int(entry["node_row_count"])
        state_valid = state_valid and len(channel_nodes) == int(entry["channel_node_count"])
        state_valid = state_valid and len(element_rows) == int(entry["channel_element_count"])
        state_valid = state_valid and sha256(node_path) == entry["node_csv_sha256"]
        state_valid = state_valid and sha256(element_path) == entry["element_csv_sha256"]
        state_valid = state_valid and close(
            nearest["potential_v"], float(entry["center_channel_potential_v"]),
            rel_tol=2.0e-12, abs_tol=1.0e-12,
        ) and close(
            nearest["electron_density_cm3"],
            float(entry["center_channel_electron_density_cm3"]),
            rel_tol=2.0e-12,
            abs_tol=1.0e-6,
        )
        state_valid = state_valid and close(
            float(entry["absolute_external_drain_current_terminal_a"]),
            abs(float(final["external_drain_current_terminal_a"])),
            rel_tol=2.0e-12,
            abs_tol=1.0e-25,
        )
        state_valid = state_valid and close(
            float(entry["internal_source_v"]), float(final["internal_source_v"]),
            rel_tol=2.0e-12, abs_tol=1.0e-15,
        ) and close(
            float(entry["internal_drain_v"]), float(final["internal_drain_v"]),
            rel_tol=2.0e-12, abs_tol=1.0e-15,
        )
        for field in state_summary_fields:
            if field in {"state_id", "state_label", "parameter_group_id", "case_id", "mesh_level", "stage_id", "node_csv", "element_csv"}:
                state_valid = state_valid and str(entry[field]) == summary[field]
            else:
                state_valid = state_valid and close(
                    float(entry[field]), float(summary[field]),
                    rel_tol=2.0e-12, abs_tol=1.0e-300,
                )
        vtk_files = entry.get("vtk_files", [])
        vtk_count += len(vtk_files)
        state_valid = state_valid and len(vtk_files) == 6
        for vtk in vtk_files:
            vtk_path = ROOT / vtk["path"]
            state_valid = state_valid and vtk_path.is_file()
            state_valid = state_valid and vtk_path.stat().st_size > 0
            state_valid = state_valid and sha256(vtk_path) == vtk["sha256"]
    add_check(
        checks,
        "states:three_node_element_circuit_states_and_18_vtk_files_verify",
        state_valid and vtk_count == int(acceptance["required_vtk_file_count"]),
        (
            f"states={len(manifest_entries)} nodes={node_count} elements={element_count} "
            f"vtk={vtk_count} valid={state_valid}"
        ),
    )

    figure_valid = len(report.get("figures", [])) == 2
    dimensions: list[tuple[int, int]] = []
    for figure in report.get("figures", []):
        path = ROOT / figure["path"]
        figure_valid = figure_valid and path.is_file() and path.stat().st_size > 0
        figure_valid = figure_valid and sha256(path) == figure["sha256"]
        dimensions.append(png_dimensions(path))
    add_check(
        checks,
        "figures:two_nonempty_png_hashes_and_dimensions_verify",
        figure_valid and all(width >= 1000 and height >= 1000 for width, height in dimensions),
        f"figures={len(report.get('figures', []))} dimensions={dimensions}",
    )

    independent, independent_detail = checker_is_independent()
    failure_archives = sorted(
        path
        for path in (ROOT / "results" / "tcad" / "t03_sensitivity").glob(
            "p3_contact_resistance_v2_*"
        )
        if path.is_dir()
    )
    add_check(
        checks,
        "provenance:checker_is_independent_and_no_failure_archive_was_needed",
        independent
        and not failure_archives
        and config["failure_retention"]["runner_pass_required_before_independent_check"]
        is True
        and config["failure_retention"]["recovery_requires_new_contract_revision"]
        is True,
        f"{independent_detail} failure_archives={[str(path.relative_to(ROOT)) for path in failure_archives]}",
    )

    evidence_text = json.dumps(report.get("evidence_boundary", {}), ensure_ascii=False)
    limitations_text = " ".join(str(value) for value in report.get("limitations", []))
    evidence_valid = (
        "TLM-extracted" in evidence_text
        and "complete T03" in evidence_text
        and "not project TLM measurements" in limitations_text
        and "independent persisted-evidence checker" in limitations_text
        and report.get("t03_p3_completion", {}).get("complete_p3_contact_group")
        is False
        and report.get("t03_p3_completion", {}).get("p5_or_downstream_permitted_next")
        is False
    )
    add_check(
        checks,
        "boundary:runner_remains_e2_numerical_proxy_and_downstream_closed",
        evidence_valid,
        (
            f"runner_complete={report.get('t03_p3_completion', {}).get('complete_p3_contact_group')} "
            f"downstream={report.get('t03_p3_completion', {}).get('p5_or_downstream_permitted_next')}"
        ),
    )

    failures = [item["name"] for item in checks if item["status"] == "FAIL"]
    status = "PASS" if not failures else "FAIL"
    result = {
        "status": status,
        "case_id": config["case_id"],
        "stage": config["stage"],
        "parameter_group_id": "P3",
        "evidence_level": "E3" if status == "PASS" else "E0",
        "independent_of_simulation_runner": True,
        "runner_imported": False,
        "devsim_imported": False,
        "checker": {
            "path": str(CHECKER_PATH.relative_to(ROOT)),
            "sha256": sha256(CHECKER_PATH),
        },
        "checks": checks,
        "failures": failures,
        "summary": {
            "check_count": len(checks),
            "pass_count": sum(item["status"] == "PASS" for item in checks),
            "transfer_point_count": len(transfer_rows),
            "output_point_count": len(output_rows),
            "reported_point_count": len(all_rows),
            "device_count": len(runs),
            "dc_solve_count": len(records),
            "circuit_closure_point_count": len(closure_rows),
            "state_count": len(manifest_entries),
            "state_node_row_count": node_count,
            "state_element_row_count": element_count,
            "vtk_file_count": vtk_count,
            "maximum_nonzero_vds_relative_terminal_current_imbalance": maximum_nonzero_vds_imbalance,
            "maximum_all_point_relative_terminal_current_imbalance_nongating": maximum_all_point_imbalance,
            "maximum_circuit_kcl_relative_residual": maximum_kcl,
            "maximum_circuit_ohms_law_relative_residual": maximum_ohm,
            "maximum_circuit_voltage_partition_absolute_residual_v": maximum_partition,
            "maximum_zero_external_vds_absolute_current_a_per_cm": maximum_zero,
            "maximum_output_monotonic_relative_drop": maximum_output_drop,
            "largest_pair_high_gate_current_relative_reduction": high_reduction,
            "linear_region_total_resistance_width_kohm_um": resistance_widths,
            "t02_c_maximum_current_relative_difference": max_reference_current,
            "t02_c_maximum_center_potential_difference_v": max_reference_potential,
            "t02_c_maximum_center_density_relative_difference": max_reference_density,
            "figure_dimensions": [list(value) for value in dimensions],
            "runner_wall_seconds": solver_log.get("wall_seconds"),
            "run_directory_bytes": sum(
                path.stat().st_size for path in run_dir.rglob("*") if path.is_file()
            ),
        },
        "t03_p3_completion": {
            "status": "PASS" if status == "PASS" else "BLOCKED",
            "input_contract_passed": contract.get("contract_status") == "PASS",
            "formal_runner_passed": report.get("status") == "PASS",
            "independent_check_passed": status == "PASS",
            "complete_p3_contact_group": status == "PASS",
            "complete_t03_five_group_sensitivity": False,
            "p5_permitted_after_documentation": status == "PASS",
            "compact_model_or_downstream_permitted": False,
            "experimental_calibration_permitted": False,
        },
        "allowed_claim": (
            "A controlled three-point symmetric lumped contact-series-resistance "
            "numerical sensitivity is complete for the frozen 2D IGZO teaching model."
        )
        if status == "PASS"
        else "No T03-P3 completion claim is permitted.",
        "prohibited_claims": config["evidence_boundary"]["prohibited_claims"],
    }
    paths["check_report"].parent.mkdir(parents=True, exist_ok=True)
    paths["check_report"].write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"T03_P3_CONTACT_RESISTANCE_CHECK_{status} "
        f"{result['summary']['pass_count']}/{result['summary']['check_count']} "
        f"report={paths['check_report']}"
    )
    for failure in failures:
        detail = next(item["detail"] for item in checks if item["name"] == failure)
        print(f"T03_P3_CONTACT_RESISTANCE_CHECK_ERROR {failure}: {detail}", file=sys.stderr)
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
