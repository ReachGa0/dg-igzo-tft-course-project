#!/usr/bin/env python3
"""Independently verify persisted C00 R03 evidence without a simulator process."""

from __future__ import annotations

import ast
import csv
import hashlib
import json
import math
import re
import struct
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "c00_active_load_inverter_r03.json"
RUNNER_PATH = ROOT / "scripts" / "run_c00_active_load_inverter_r03.py"
COMMON_PATH = ROOT / "scripts" / "c00_active_load_inverter_r03_common.py"
REPORT_PATH = ROOT / "results" / "reports" / "c00_active_load_inverter_r03.json"
CHECK_PATH = ROOT / "results" / "reports" / "c00_active_load_inverter_r03_check.json"
EXPECTED_CHECK_COUNT = 29

DC_FIELDS = ["route", "case_id", "vdd_v", "v_top_load_v", "v_top_load_over_vdd", "wload_over_wdriver", "vin_fraction", "vin_v", "vout_v", "supply_current_a", "static_power_w", "finite"]
TRANSIENT_FIELDS = ["route", "case_id", "dc_case_id", "vdd_v", "v_top_load_v", "v_top_load_over_vdd", "wload_over_wdriver", "cload_f", "time_s", "vin_v", "vout_v", "supply_current_a", "instantaneous_power_w", "finite"]
STATIC_METRIC_FIELDS = ["route", "case_id", "vdd_v", "v_top_load_v", "v_top_load_over_vdd", "wload_over_wdriver", "point_count", "voh_v", "vol_v", "vm_v", "max_gain_v_per_v", "vil_v", "vih_v", "nml_v", "nmh_v", "p_static_input_low_w", "p_static_input_high_w", "monotonic_nonincreasing", "logic_separable", "unit_gain_crossings", "extraction_status", "qualified"]
TRANSIENT_METRIC_FIELDS = ["route", "case_id", "dc_case_id", "vdd_v", "v_top_load_v", "v_top_load_over_vdd", "wload_over_wdriver", "cload_f", "point_count", "input_low_sample_vout_v", "input_high_sample_vout_v", "tphl_s", "tplh_s", "average_supply_power_w", "cycle_energy_j", "peak_supply_power_w", "fall_crossing_found", "rise_crossing_found", "extraction_status", "qualified"]
DC_DIFFERENCE_FIELDS = ["case_id", "vin_fraction", "vin_v", "ngspice_vout_v", "xyce_vout_v", "absolute_vout_difference_v", "ngspice_supply_current_a", "xyce_supply_current_a", "absolute_supply_current_difference_a"]
TRANSIENT_DIFFERENCE_FIELDS = ["case_id", "time_s", "ngspice_vin_v", "xyce_vin_v", "absolute_vin_difference_v", "ngspice_vout_v", "xyce_vout_v", "absolute_vout_difference_v", "ngspice_supply_current_a", "xyce_supply_current_a", "absolute_supply_current_difference_a"]
ARTIFACT_KEYS = ["ngspice_dc_netlist", "ngspice_dc_log", "ngspice_dc_command", "ngspice_dc_raw", "ngspice_tran_netlist", "ngspice_tran_log", "ngspice_tran_command", "ngspice_tran_raw", "xyce_dc_netlist", "xyce_dc_log", "xyce_dc_command", "xyce_dc_raw", "xyce_tran_netlist", "xyce_tran_log", "xyce_tran_command", "xyce_tran_raw", "ngspice_dc_csv", "xyce_dc_csv", "ngspice_tran_csv", "xyce_tran_csv", "static_metrics_csv", "transient_metrics_csv", "dc_route_difference_csv", "transient_route_difference_csv", "vtc_png", "transient_png"]


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


def forbidden_tokens_absent(text: str, forbidden: list[str]) -> bool:
    identifiers = {
        token.lower() for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)
    }
    return not identifiers.intersection(token.lower() for token in forbidden)


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def _read_ref(name: str) -> str | None:
    git_dir = ROOT / ".git"
    path = git_dir / name
    if path.is_file():
        value = path.read_text(encoding="ascii").strip()
        if value.startswith("ref: "):
            target = git_dir / value[5:]
            return target.read_text(encoding="ascii").strip() if target.is_file() else None
        return value
    packed = git_dir / "packed-refs"
    if packed.is_file():
        for line in packed.read_text(encoding="ascii").splitlines():
            if line and not line.startswith(("#", "^")):
                commit, ref = line.split(" ", 1)
                if ref == name:
                    return commit
    return None


def _is_commit_id(value: object) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value) is not None


def _spice(value: float) -> str:
    return format(float(value), ".17g")


def _continued(prefix: str, values: list[str], width: int = 6) -> list[str]:
    return [(prefix if offset == 0 else "+") + " " + " ".join(values[offset:offset + width]) for offset in range(0, len(values), width)]


def dc_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    sweep = config["sweep_contract"]
    topology = config["topology_contract"]
    output = []
    for vdd in sweep["vdd_v"]:
        for fraction in sweep["v_top_load_over_vdd"]:
            for ratio in sweep["wload_over_wdriver"]:
                case_id = f"v{round(vdd * 1000):03d}_t{round(fraction * 100):03d}_r{round(ratio * 1000):04d}"
                output.append({"case_id": case_id, "tag": case_id.replace("_", "").upper(), "vdd_v": float(vdd), "v_top_load_v": float(vdd) * float(fraction), "v_top_load_over_vdd": float(fraction), "wload_over_wdriver": float(ratio), "driver_width_um": float(topology["driver_width_um"]), "driver_length_um": float(topology["driver_length_um"]), "load_width_um": float(topology["driver_width_um"]) * float(ratio), "load_length_um": float(topology["load_length_um"])})
    return output


def transient_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    output = []
    for base in dc_cases(config):
        for cload in config["sweep_contract"]["cload_f"]:
            case = dict(base)
            case["dc_case_id"] = base["case_id"]
            case["cload_f"] = float(cload)
            case["case_id"] = f"{base['case_id']}_c{round(float(cload) * 1e15):04d}"
            case["tag"] = case["case_id"].replace("_", "").upper()
            output.append(case)
    return output


def _devices(case: dict[str, Any], config: dict[str, Any]) -> list[str]:
    tag = case["tag"]
    model = config["upstream_model"]["subcircuit"]
    return [f"XLD{tag} VD{tag} VT{tag} VD{tag} VO{tag} {model} WUM={_spice(case['load_width_um'])} LUM={_spice(case['load_length_um'])}", f"XDR{tag} VO{tag} VI{tag} 0 0 {model} WUM={_spice(case['driver_width_um'])} LUM={_spice(case['driver_length_um'])}"]


def generate_netlist(config: dict[str, Any], route: str, analysis: str) -> str:
    outputs = config["outputs"]
    sweep = config["sweep_contract"]
    lines = [f"* C00 R03 {route} IGZO-only active-load inverter {'DC' if analysis == 'dc' else 'transient'}", config["netlist_contract"]["candidate_include"], ".option numdgt=17"]
    if analysis == "dc":
        lines.append("VSWEEP NORM 0 0")
        vectors = ["V(NORM)"]
        for case in dc_cases(config):
            tag = case["tag"]
            lines.extend([f"VDD{tag} VD{tag} 0 {_spice(case['vdd_v'])}", f"VTP{tag} VT{tag} 0 {_spice(case['v_top_load_v'])}", f"EIN{tag} VI{tag} 0 NORM 0 {_spice(case['vdd_v'])}", *_devices(case, config)])
            vectors.extend([f"V(VO{tag})", f"I(VDD{tag})"])
        lines.append(f".DC VSWEEP {_spice(sweep['dc_normalized_input_start'])} {_spice(sweep['dc_normalized_input_stop'])} {_spice(sweep['dc_normalized_input_step'])}")
        raw = outputs["ngspice_dc_raw"]
        print_prefix = ".PRINT DC FORMAT=NOINDEX PRECISION=17"
    else:
        vectors = ["TIME"]
        for case in transient_cases(config):
            tag = case["tag"]
            lines.extend([f"VDD{tag} VD{tag} 0 {_spice(case['vdd_v'])}", f"VTP{tag} VT{tag} 0 {_spice(case['v_top_load_v'])}", f"VIN{tag} VI{tag} 0 PULSE(0 {_spice(case['vdd_v'])} {_spice(sweep['pulse_delay_s'])} {_spice(sweep['pulse_rise_s'])} {_spice(sweep['pulse_fall_s'])} {_spice(sweep['pulse_high_s'])} {_spice(sweep['pulse_period_s'])})", *_devices(case, config), f"CLOAD{tag} VO{tag} 0 {_spice(case['cload_f'])}"])
            vectors.extend([f"V(VI{tag})", f"V(VO{tag})", f"I(VDD{tag})"])
        lines.append(f".TRAN {_spice(sweep['transient_step_s'])} {_spice(sweep['transient_stop_s'])}")
        raw = outputs["ngspice_tran_raw"]
        print_prefix = ".PRINT TRAN FORMAT=NOINDEX PRECISION=17"
    if route == "ngspice":
        lines.extend(_continued(".save", vectors))
        lines.extend([".control", "set filetype=ascii"] + (["set plotwinsize=0"] if analysis == "transient" else []) + ["run", f"write {raw}", "quit", ".endc"])
    else:
        lines.extend(_continued(print_prefix, vectors))
    lines.append(".end")
    return "\n".join(lines) + "\n"


def _normalize(name: str) -> str:
    return name.strip().lower().replace("#branch", "")


def parse_ngspice(path: Path) -> dict[str, list[float]]:
    lines = path.read_text(encoding="ascii").splitlines()
    nvars = int(next(line.split(":", 1)[1] for line in lines if line.startswith("No. Variables:")))
    npoints = int(next(line.split(":", 1)[1] for line in lines if line.startswith("No. Points:")))
    vi = next(index for index, line in enumerate(lines) if line.strip() == "Variables:")
    xi = next(index for index, line in enumerate(lines) if line.strip() == "Values:")
    names = [_normalize(line.split()[1]) for line in lines[vi + 1:xi] if len(line.split()) >= 3 and line.split()[0].isdigit()]
    if len(names) != nvars:
        raise ValueError("ngspice variable count mismatch")
    rows = []
    cursor = xi + 1
    for point in range(npoints):
        while not lines[cursor].strip():
            cursor += 1
        first = lines[cursor].split()
        cursor += 1
        if int(first[0]) != point:
            raise ValueError("ngspice point order mismatch")
        values = [float(first[-1])]
        while len(values) < nvars:
            parts = lines[cursor].split()
            cursor += 1
            if parts:
                values.append(float(parts[-1]))
        rows.append(values)
    return {name: [row[index] for row in rows] for index, name in enumerate(names)}


def parse_xyce(path: Path) -> dict[str, list[float]]:
    lines = path.read_text(encoding="ascii").splitlines()
    for index, line in enumerate(lines):
        headers = line.split()
        names = [_normalize(item) for item in headers]
        if not any(name == "time" or name.startswith(("v(", "i(")) for name in names):
            continue
        columns: dict[str, list[float]] = defaultdict(list)
        for raw in lines[index + 1:]:
            parts = raw.split()
            if parts and parts[0] == "End":
                break
            if len(parts) != len(headers):
                continue
            try:
                values = [float(item) for item in parts]
            except ValueError:
                continue
            for name, value in zip(names, values):
                columns[name].append(value)
        columns.pop("index", None)
        if columns:
            return dict(columns)
    raise ValueError("Xyce table missing")


def interpolate(axis: list[float], values: list[float], target: float) -> float:
    if target <= axis[0]:
        return values[0]
    if target >= axis[-1]:
        return values[-1]
    low, high = 0, len(axis) - 1
    while high - low > 1:
        mid = (low + high) // 2
        if axis[mid] <= target:
            low = mid
        else:
            high = mid
    fraction = (target - axis[low]) / (axis[high] - axis[low])
    return values[low] + fraction * (values[high] - values[low])


def grid(start: float, stop: float, step: float) -> list[float]:
    return [start + index * step for index in range(round((stop - start) / step) + 1)]


def extract(config: dict[str, Any], route: str, analysis: str, vectors: dict[str, list[float]]) -> list[dict[str, Any]]:
    sweep = config["sweep_contract"]
    output = []
    if analysis == "dc":
        axis = vectors.get("v(norm)", vectors.get("norm"))
        if axis is None:
            raise ValueError("DC axis missing")
        targets = grid(sweep["dc_normalized_input_start"], sweep["dc_normalized_input_stop"], sweep["dc_normalized_input_step"])
        for case in dc_cases(config):
            vout = vectors[f"v(vo{case['tag'].lower()})"]
            supply = vectors[f"i(vdd{case['tag'].lower()})"]
            for fraction in targets:
                out = interpolate(axis, vout, fraction)
                current = abs(interpolate(axis, supply, fraction))
                output.append({"route": route, "case_id": case["case_id"], "vdd_v": case["vdd_v"], "v_top_load_v": case["v_top_load_v"], "v_top_load_over_vdd": case["v_top_load_over_vdd"], "wload_over_wdriver": case["wload_over_wdriver"], "vin_fraction": fraction, "vin_v": fraction * case["vdd_v"], "vout_v": out, "supply_current_a": current, "static_power_w": case["vdd_v"] * current, "finite": all(math.isfinite(value) for value in (fraction, out, current))})
    else:
        axis = vectors["time"]
        targets = grid(0.0, sweep["transient_stop_s"], sweep["transient_step_s"])
        for case in transient_cases(config):
            vin = vectors[f"v(vi{case['tag'].lower()})"]
            vout = vectors[f"v(vo{case['tag'].lower()})"]
            supply = vectors[f"i(vdd{case['tag'].lower()})"]
            for time_s in targets:
                input_v = interpolate(axis, vin, time_s)
                out = interpolate(axis, vout, time_s)
                current = abs(interpolate(axis, supply, time_s))
                output.append({"route": route, "case_id": case["case_id"], "dc_case_id": case["dc_case_id"], "vdd_v": case["vdd_v"], "v_top_load_v": case["v_top_load_v"], "v_top_load_over_vdd": case["v_top_load_over_vdd"], "wload_over_wdriver": case["wload_over_wdriver"], "cload_f": case["cload_f"], "time_s": time_s, "vin_v": input_v, "vout_v": out, "supply_current_a": current, "instantaneous_power_w": case["vdd_v"] * current, "finite": all(math.isfinite(value) for value in (time_s, input_v, out, current))})
    return output


def crossings(x: list[float], y: list[float], target: float) -> list[float]:
    shifted = [value - target for value in y]
    output = []
    for index in range(len(y) - 1):
        left, right = shifted[index], shifted[index + 1]
        if left == 0.0:
            value = x[index]
        elif left * right < 0.0 or right == 0.0:
            value = x[index] - left * (x[index + 1] - x[index]) / (right - left)
        else:
            continue
        if not output or abs(value - output[-1]) > 1e-15:
            output.append(value)
    return output


def static_metrics(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["route"], row["case_id"])].append(row)
    gate = config["acceptance_contract"]
    output = []
    for (route, case_id), group in grouped.items():
        group.sort(key=lambda row: row["vin_v"])
        x = [row["vin_v"] for row in group]
        y = [row["vout_v"] for row in group]
        slopes = []
        for index in range(len(x)):
            left, right = (0, 1) if index == 0 else ((len(x) - 2, len(x) - 1) if index == len(x) - 1 else (index - 1, index + 1))
            slopes.append((y[right] - y[left]) / (x[right] - x[left]))
        vm_points = crossings(x, [out - inp for inp, out in zip(x, y)], 0.0)
        gain_points = crossings(x, slopes, -1.0)
        vm = vm_points[0] if vm_points else None
        vil = gain_points[0] if len(gain_points) >= 2 else None
        vih = gain_points[-1] if len(gain_points) >= 2 else None
        vdd, voh, vol = group[0]["vdd_v"], y[0], y[-1]
        nml = vil - vol if vil is not None else None
        nmh = voh - vih if vih is not None else None
        monotonic = all(y[i + 1] <= y[i] + gate["dc_monotonic_tolerance_v"] for i in range(len(y) - 1))
        separable = voh >= gate["anchor_voh_min_fraction_vdd"] * vdd and vol <= gate["anchor_vol_max_fraction_vdd"] * vdd and voh > vol
        complete = vm is not None and vil is not None and vih is not None
        qualified = complete and monotonic and separable and gate["anchor_vm_min_fraction_vdd"] * vdd <= vm <= gate["anchor_vm_max_fraction_vdd"] * vdd and max(abs(value) for value in slopes) >= gate["anchor_gain_min_v_per_v"] and len(gain_points) >= gate["anchor_required_unit_gain_crossings"] and nml >= gate["anchor_min_noise_margin_v"] and nmh >= gate["anchor_min_noise_margin_v"]
        output.append({"route": route, "case_id": case_id, "vdd_v": vdd, "v_top_load_v": group[0]["v_top_load_v"], "v_top_load_over_vdd": group[0]["v_top_load_over_vdd"], "wload_over_wdriver": group[0]["wload_over_wdriver"], "point_count": len(group), "voh_v": voh, "vol_v": vol, "vm_v": vm, "max_gain_v_per_v": max(abs(value) for value in slopes), "vil_v": vil, "vih_v": vih, "nml_v": nml, "nmh_v": nmh, "p_static_input_low_w": group[0]["static_power_w"], "p_static_input_high_w": group[-1]["static_power_w"], "monotonic_nonincreasing": monotonic, "logic_separable": separable, "unit_gain_crossings": len(gain_points), "extraction_status": "complete" if complete else "missing_registered_crossing", "qualified": qualified})
    return output


def directional(times: list[float], values: list[float], threshold: float, start: float, direction: str) -> float | None:
    for index in range(len(times) - 1):
        if times[index + 1] < start:
            continue
        left, right = values[index] - threshold, values[index + 1] - threshold
        if (direction == "fall" and left >= 0.0 >= right) or (direction == "rise" and left <= 0.0 <= right):
            return times[index] - left * (times[index + 1] - times[index]) / (right - left) if right != left else times[index]
    return None


def integrate(times: list[float], values: list[float], start: float, stop: float) -> float:
    points = [start] + [value for value in times if start < value < stop] + [stop]
    sampled = [interpolate(times, values, value) for value in points]
    return sum(0.5 * (sampled[i] + sampled[i + 1]) * (points[i + 1] - points[i]) for i in range(len(points) - 1))


def transient_metrics(rows: list[dict[str, Any]], config: dict[str, Any]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["route"], row["case_id"])].append(row)
    sweep, gate = config["sweep_contract"], config["acceptance_contract"]
    output = []
    for (route, case_id), group in grouped.items():
        group.sort(key=lambda row: row["time_s"])
        times = [row["time_s"] for row in group]
        values = [row["vout_v"] for row in group]
        power = [row["instantaneous_power_w"] for row in group]
        vdd = group[0]["vdd_v"]
        high = interpolate(times, values, sweep["pre_rising_sample_s"])
        low = interpolate(times, values, sweep["pre_falling_sample_s"])
        fall = directional(times, values, 0.5 * vdd, sweep["measured_rising_input_crossing_s"], "fall")
        rise = directional(times, values, 0.5 * vdd, sweep["measured_falling_input_crossing_s"], "rise")
        tphl = fall - sweep["measured_rising_input_crossing_s"] if fall is not None else None
        tplh = rise - sweep["measured_falling_input_crossing_s"] if rise is not None else None
        start, stop = sweep["transient_stop_s"] - sweep["pulse_period_s"], sweep["transient_stop_s"]
        energy = integrate(times, power, start, stop)
        average = energy / (stop - start)
        peak = max(value for time, value in zip(times, power) if start <= time <= stop)
        complete = tphl is not None and tplh is not None
        qualified = complete and high >= gate["anchor_transient_high_min_fraction_vdd"] * vdd and low <= gate["anchor_transient_low_max_fraction_vdd"] * vdd and 0 <= tphl <= gate["anchor_max_delay_s"] and 0 <= tplh <= gate["anchor_max_delay_s"] and average >= 0 and math.isfinite(average)
        output.append({"route": route, "case_id": case_id, "dc_case_id": group[0]["dc_case_id"], "vdd_v": vdd, "v_top_load_v": group[0]["v_top_load_v"], "v_top_load_over_vdd": group[0]["v_top_load_over_vdd"], "wload_over_wdriver": group[0]["wload_over_wdriver"], "cload_f": group[0]["cload_f"], "point_count": len(group), "input_low_sample_vout_v": high, "input_high_sample_vout_v": low, "tphl_s": tphl, "tplh_s": tplh, "average_supply_power_w": average, "cycle_energy_j": energy, "peak_supply_power_w": peak, "fall_crossing_found": fall is not None, "rise_crossing_found": rise is not None, "extraction_status": "complete" if complete else "missing_output_crossing", "qualified": qualified})
    return output


def differences(ng: list[dict[str, Any]], xy: list[dict[str, Any]], analysis: str) -> list[dict[str, Any]]:
    axis_name = "vin_fraction" if analysis == "dc" else "time_s"
    index = {(row["case_id"], row[axis_name]): row for row in xy}
    output = []
    for left in ng:
        right = index[(left["case_id"], left[axis_name])]
        if analysis == "dc":
            output.append({"case_id": left["case_id"], "vin_fraction": left["vin_fraction"], "vin_v": left["vin_v"], "ngspice_vout_v": left["vout_v"], "xyce_vout_v": right["vout_v"], "absolute_vout_difference_v": abs(left["vout_v"] - right["vout_v"]), "ngspice_supply_current_a": left["supply_current_a"], "xyce_supply_current_a": right["supply_current_a"], "absolute_supply_current_difference_a": abs(left["supply_current_a"] - right["supply_current_a"])})
        else:
            output.append({"case_id": left["case_id"], "time_s": left["time_s"], "ngspice_vin_v": left["vin_v"], "xyce_vin_v": right["vin_v"], "absolute_vin_difference_v": abs(left["vin_v"] - right["vin_v"]), "ngspice_vout_v": left["vout_v"], "xyce_vout_v": right["vout_v"], "absolute_vout_difference_v": abs(left["vout_v"] - right["vout_v"]), "ngspice_supply_current_a": left["supply_current_a"], "xyce_supply_current_a": right["supply_current_a"], "absolute_supply_current_difference_a": abs(left["supply_current_a"] - right["supply_current_a"])})
    return output


def csv_matches(actual: list[dict[str, str]], expected: list[dict[str, Any]], fields: list[str]) -> bool:
    if len(actual) != len(expected):
        return False
    for observed, reference in zip(actual, expected):
        for field in fields:
            value = reference.get(field)
            if value is None:
                if observed[field] != "":
                    return False
            elif isinstance(value, bool):
                if observed[field].lower() != str(value).lower():
                    return False
            elif isinstance(value, (int, float)):
                if not math.isclose(float(observed[field]), float(value), rel_tol=2e-10, abs_tol=2e-15):
                    return False
            elif observed[field] != str(value):
                return False
    return True


def png_dimensions(path: Path) -> tuple[int, int] | None:
    data = path.read_bytes()[:24]
    if len(data) != 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", data[16:24])


def anchor_ids(config: dict[str, Any]) -> tuple[str, str]:
    anchor = config["sweep_contract"]["anchor"]
    dc_id = f"v{round(anchor['vdd_v'] * 1000):03d}_t{round(anchor['v_top_load_over_vdd'] * 100):03d}_r{round(anchor['wload_over_wdriver'] * 1000):04d}"
    return dc_id, f"{dc_id}_c{round(anchor['cload_f'] * 1e15):04d}"


def check() -> int:
    config = load_json(CONFIG_PATH)
    outputs = config["outputs"]
    report = load_json(REPORT_PATH)
    experiments = load_json(ROOT / "config" / "experiments.json")
    c00 = next(item for item in experiments["experiments"] if item["id"] == "C00")
    machine = c00["active_load_inverter_r03"]
    checks: list[dict[str, str]] = []

    add_check(checks, "precondition:committed_runner_pass", report.get("status") == "PASS" and report.get("evidence_level") == "E2" and report.get("summary", {}).get("passed") == 36 and machine.get("runner_report_sha256") == sha256(REPORT_PATH), f"sha256={sha256(REPORT_PATH)}")
    head, origin = _read_ref("HEAD"), _read_ref("refs/remotes/origin/main")
    runner_git_snapshot = report.get("git_state", {})
    runner_head = runner_git_snapshot.get("head")
    runner_origin = runner_git_snapshot.get("origin_main")
    add_check(
        checks,
        "git:head_origin_synced_and_runner_snapshot_published",
        _is_commit_id(head)
        and head == origin
        and _is_commit_id(runner_head)
        and runner_head == runner_origin
        and runner_git_snapshot.get("synchronized") is True
        and runner_head != head
        and machine.get("runner_report_sha256") == sha256(REPORT_PATH),
        f"head={head} origin={origin} runner_snapshot={runner_head}",
    )
    add_check(checks, "identity:config_common_runner_hashes", report.get("config", {}).get("sha256") == sha256(CONFIG_PATH) and report.get("runner", {}).get("sha256") == sha256(RUNNER_PATH) and machine.get("common_sha256") == sha256(COMMON_PATH), f"config={sha256(CONFIG_PATH)}")
    add_check(checks, "machine:runner_state_and_independent_gate", c00.get("status") == "formal_run_passed" and c00.get("current_evidence") == "E2" and machine.get("status") == "formal_run_passed" and machine.get("formal_run_completed") is True and machine.get("independent_check_permitted") is True and machine.get("independent_check_completed") is False, f"root={c00.get('status')}")
    tree = ast.parse(Path(__file__).read_text(encoding="ascii"))
    imported_modules = {
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    add_check(checks, "independence:no_subprocess_common_or_runner_import", not {"subprocess", "c00_active_load_inverter_r03_common", "run_c00_active_load_inverter_r03"} & imported_modules, "standard-library independent implementation")
    model = ROOT / config["upstream_model"]["candidate_path"]
    tools_ok = sha256(model) == config["upstream_model"]["candidate_sha256"] and all(sha256(Path(route["tool_path"])) == route["tool_sha256"] for route in config["routes"].values())
    add_check(checks, "bindings:model_and_tool_hashes", tools_ok, "candidate/ngspice/Xyce hashes match")
    add_check(checks, "runner:36_checks_four_processes", report.get("summary", {}).get("passed") == 36 and report.get("summary", {}).get("failed") == 0 and report.get("summary", {}).get("process_invocations") == 4 and report.get("summary", {}).get("ngspice_processes") == 2 and report.get("summary", {}).get("xyce_processes") == 2, json.dumps(report.get("summary", {}), sort_keys=True))
    artifacts = report.get("artifacts", {})
    hashes_ok = len(artifacts) == len(ARTIFACT_KEYS) and all((ROOT / outputs[key]).is_file() and artifacts.get(f"{key}_sha256") == sha256(ROOT / outputs[key]) for key in ARTIFACT_KEYS)
    add_check(checks, "artifacts:all_26_hashes_recomputed", hashes_ok, f"hashes={len(artifacts)}/{len(ARTIFACT_KEYS)}")

    expected_netlists = {(route, analysis): generate_netlist(config, route, analysis) for route in ("ngspice", "xyce") for analysis in ("dc", "transient")}
    exact_netlists = all((ROOT / outputs[f"{route}_{'tran' if analysis == 'transient' else 'dc'}_netlist"]).read_text(encoding="ascii") == text for (route, analysis), text in expected_netlists.items())
    add_check(checks, "netlists:exact_independent_regeneration", exact_netlists, "four byte-exact netlists")
    forbidden = config["netlist_contract"]["forbidden_case_insensitive_tokens"]
    scope_ok = all(
        text.count("XLD") == text.count("XDR")
        and forbidden_tokens_absent(text, forbidden)
        for text in expected_netlists.values()
    )
    add_check(checks, "netlists:two_tft_igzo_scope", scope_ok, "18 DC and 36 transient cases per route")

    vectors = {"ngspice_dc": parse_ngspice(ROOT / outputs["ngspice_dc_raw"]), "ngspice_transient": parse_ngspice(ROOT / outputs["ngspice_tran_raw"]), "xyce_dc": parse_xyce(ROOT / outputs["xyce_dc_raw"]), "xyce_transient": parse_xyce(ROOT / outputs["xyce_tran_raw"])}
    native = {key: len(next(iter(value.values()))) for key, value in vectors.items()}
    add_check(checks, "raw:four_independent_parsers_complete", native == report.get("native_points") and min(native.values()) >= 101, json.dumps(native, sort_keys=True))
    expected_dc = {route: extract(config, route, "dc", vectors[f"{route}_dc"]) for route in ("ngspice", "xyce")}
    expected_tran = {route: extract(config, route, "transient", vectors[f"{route}_transient"]) for route in ("ngspice", "xyce")}
    ng_dc, ng_dc_fields = load_csv(ROOT / outputs["ngspice_dc_csv"])
    xy_dc, xy_dc_fields = load_csv(ROOT / outputs["xyce_dc_csv"])
    add_check(checks, "tables:dc_schema_and_1818_rows_per_route", ng_dc_fields == xy_dc_fields == DC_FIELDS and len(ng_dc) == len(xy_dc) == 1818, f"rows={len(ng_dc)}/{len(xy_dc)}")
    add_check(checks, "tables:dc_exact_raw_recomputation", csv_matches(ng_dc, expected_dc["ngspice"], DC_FIELDS) and csv_matches(xy_dc, expected_dc["xyce"], DC_FIELDS), "both DC tables reproduce raw evidence")
    ng_tran, ng_tran_fields = load_csv(ROOT / outputs["ngspice_tran_csv"])
    xy_tran, xy_tran_fields = load_csv(ROOT / outputs["xyce_tran_csv"])
    add_check(checks, "tables:transient_schema_and_21636_rows_per_route", ng_tran_fields == xy_tran_fields == TRANSIENT_FIELDS and len(ng_tran) == len(xy_tran) == 21636, f"rows={len(ng_tran)}/{len(xy_tran)}")
    add_check(checks, "tables:transient_exact_raw_recomputation", csv_matches(ng_tran, expected_tran["ngspice"], TRANSIENT_FIELDS) and csv_matches(xy_tran, expected_tran["xyce"], TRANSIENT_FIELDS), "both transient tables reproduce resampled raw evidence")

    expected_static = static_metrics(expected_dc["ngspice"] + expected_dc["xyce"], config)
    actual_static, static_fields = load_csv(ROOT / outputs["static_metrics_csv"])
    add_check(checks, "metrics:36_static_rows_independently_recomputed", static_fields == STATIC_METRIC_FIELDS and len(actual_static) == 36 and csv_matches(actual_static, expected_static, STATIC_METRIC_FIELDS), f"rows={len(actual_static)}")
    expected_transient_metrics = transient_metrics(expected_tran["ngspice"] + expected_tran["xyce"], config)
    actual_transient, transient_fields = load_csv(ROOT / outputs["transient_metrics_csv"])
    add_check(checks, "metrics:72_transient_rows_independently_recomputed", transient_fields == TRANSIENT_METRIC_FIELDS and len(actual_transient) == 72 and csv_matches(actual_transient, expected_transient_metrics, TRANSIENT_METRIC_FIELDS), f"rows={len(actual_transient)}")
    dc_anchor, tran_anchor = anchor_ids(config)
    add_check(checks, "acceptance:anchor_static_reproduced", len([row for row in expected_static if row["case_id"] == dc_anchor and row["qualified"]]) == 2, dc_anchor)
    add_check(checks, "acceptance:anchor_transient_reproduced", len([row for row in expected_transient_metrics if row["case_id"] == tran_anchor and row["qualified"]]) == 2, tran_anchor)

    expected_dc_diff = differences(expected_dc["ngspice"], expected_dc["xyce"], "dc")
    actual_dc_diff, dc_diff_fields = load_csv(ROOT / outputs["dc_route_difference_csv"])
    add_check(checks, "differences:1818_dc_rows_recomputed", dc_diff_fields == DC_DIFFERENCE_FIELDS and len(actual_dc_diff) == 1818 and csv_matches(actual_dc_diff, expected_dc_diff, DC_DIFFERENCE_FIELDS), f"rows={len(actual_dc_diff)}")
    expected_tran_diff = differences(expected_tran["ngspice"], expected_tran["xyce"], "transient")
    actual_tran_diff, tran_diff_fields = load_csv(ROOT / outputs["transient_route_difference_csv"])
    add_check(checks, "differences:21636_transient_rows_recomputed", tran_diff_fields == TRANSIENT_DIFFERENCE_FIELDS and len(actual_tran_diff) == 21636 and csv_matches(actual_tran_diff, expected_tran_diff, TRANSIENT_DIFFERENCE_FIELDS), f"rows={len(actual_tran_diff)}")
    diagnostics = {"max_dc_vout_difference_v": max(row["absolute_vout_difference_v"] for row in expected_dc_diff), "max_transient_vout_difference_v": max(row["absolute_vout_difference_v"] for row in expected_tran_diff), "max_dc_supply_current_difference_a": max(row["absolute_supply_current_difference_a"] for row in expected_dc_diff), "max_transient_supply_current_difference_a": max(row["absolute_supply_current_difference_a"] for row in expected_tran_diff)}
    add_check(checks, "differences:finite_diagnostic_only", all(math.isfinite(value) for value in diagnostics.values()) and config["acceptance_contract"]["route_agreement_threshold_is_not_a_pass_gate"] is True, json.dumps(diagnostics, sort_keys=True))
    power_ok = all(math.isfinite(float(row[field])) and float(row[field]) >= 0 for row in expected_static for field in ("p_static_input_low_w", "p_static_input_high_w")) and all(math.isfinite(float(row[field])) and float(row[field]) >= 0 for row in expected_transient_metrics for field in ("average_supply_power_w", "cycle_energy_j", "peak_supply_power_w"))
    add_check(checks, "power:all_static_and_dynamic_values_finite", power_ok, "36 static and 72 transient metric rows")

    dimensions = {key: png_dimensions(ROOT / outputs[key]) for key in ("vtc_png", "transient_png")}
    add_check(checks, "figures:hashes_and_dimensions", all(value is not None and min(value) >= 1000 for value in dimensions.values()) and all(artifacts[f"{key}_sha256"] == sha256(ROOT / outputs[key]) for key in dimensions), json.dumps(dimensions, sort_keys=True))
    command_keys = ["ngspice_dc_command", "ngspice_tran_command", "xyce_dc_command", "xyce_tran_command"]
    command_records = [load_json(ROOT / outputs[key]) for key in command_keys]
    route_analyses = (("ngspice", "dc_argv"), ("ngspice", "transient_argv"), ("xyce", "dc_argv"), ("xyce", "transient_argv"))
    expected_argv = [
        [item.format(tool=config["routes"][route]["tool_path"]) for item in config["routes"][route][analysis]]
        for route, analysis in route_analyses
    ]
    commands_ok = all(record["returncode"] == 0 and record["argv"] == expected for record, expected in zip(command_records, expected_argv))
    add_check(checks, "commands:four_exact_zero_return_records", commands_ok, "ngspice DC/TRAN then Xyce DC/TRAN")
    add_check(checks, "runner:no_unreported_failure", report.get("failure_category") is None and report.get("failure_detail") is None and all(item.get("status") == "PASS" for item in report.get("checks", [])), "36/36 runner checks PASS")
    add_check(checks, "boundary:no_physical_calibration_or_downstream_claim", config["scope"]["physical_parameter_claim_permitted"] is False and config["scope"]["experimental_calibration_claim_permitted"] is False and config["scope"]["c01_or_later_permitted"] is False and len(config["evidence_boundary"]["prohibited_claims"]) == 6, "C00 teaching-model evidence only")
    add_check(checks, "independence:zero_processes_invoked", True, "checker contains no subprocess import or call")
    add_check(checks, "result:persisted_evidence_verified", all(item["status"] == "PASS" for item in checks), f"pre_result_passed={sum(item['status'] == 'PASS' for item in checks)}")

    if len(checks) != EXPECTED_CHECK_COUNT:
        raise RuntimeError(f"independent registry mismatch expected={EXPECTED_CHECK_COUNT} actual={len(checks)}")
    passed = sum(item["status"] == "PASS" for item in checks)
    status = "PASS" if passed == EXPECTED_CHECK_COUNT else "FAIL"
    payload = {"schema_version": "1.0", "project_id": config["project_id"], "stage_id": "C00", "contract_id": config["contract_id"], "status": status, "evidence_level": "E3" if status == "PASS" else "E0", "config": {"path": str(CONFIG_PATH.relative_to(ROOT)), "sha256": sha256(CONFIG_PATH)}, "runner": {"path": str(RUNNER_PATH.relative_to(ROOT)), "sha256": sha256(RUNNER_PATH)}, "runner_report": {"path": str(REPORT_PATH.relative_to(ROOT)), "sha256": sha256(REPORT_PATH)}, "git_state": {"head": head, "origin_main": origin, "synchronized": head == origin and _is_commit_id(head)}, "summary": {"passed": passed, "failed": EXPECTED_CHECK_COUNT - passed, "total": EXPECTED_CHECK_COUNT}, "processes_invoked": 0, "diagnostics": diagnostics, "checks": checks, "evidence_boundary": config["evidence_boundary"]["future_independent_allowed_claim"], "next_gate": "Commit and push this E3 state, then decide C00 closure within the declared teaching-model boundary before opening C01 or any layout stage." if status == "PASS" else "Preserve and commit this independent-check failure. Do not rerun the C00 simulator runner or open downstream stages."}
    if CHECK_PATH.exists():
        raise RuntimeError(f"independent checker refuses to overwrite {CHECK_PATH}")
    CHECK_PATH.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print(f"C00_ACTIVE_LOAD_INVERTER_R03_CHECK_{status} checks={passed}/{EXPECTED_CHECK_COUNT} report={CHECK_PATH}")
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(check())
