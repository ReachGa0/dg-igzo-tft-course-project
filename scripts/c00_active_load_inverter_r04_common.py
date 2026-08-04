#!/usr/bin/env python3
"""Deterministic C00 R04 netlist, parser, metric, and plotting helpers."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


DC_FIELDS = [
    "route",
    "case_id",
    "vdd_v",
    "v_top_load_v",
    "v_top_load_over_vdd",
    "wload_over_wdriver",
    "vin_fraction",
    "vin_v",
    "vout_v",
    "supply_current_a",
    "static_power_w",
    "finite",
]

TRANSIENT_FIELDS = [
    "route",
    "case_id",
    "dc_case_id",
    "vdd_v",
    "v_top_load_v",
    "v_top_load_over_vdd",
    "wload_over_wdriver",
    "cload_f",
    "time_s",
    "vin_v",
    "vout_v",
    "supply_current_a",
    "instantaneous_power_w",
    "finite",
]

STATIC_METRIC_FIELDS = [
    "route",
    "case_id",
    "vdd_v",
    "v_top_load_v",
    "v_top_load_over_vdd",
    "wload_over_wdriver",
    "point_count",
    "voh_v",
    "vol_v",
    "vm_v",
    "max_gain_v_per_v",
    "vil_v",
    "vih_v",
    "nml_v",
    "nmh_v",
    "p_static_input_low_w",
    "p_static_input_high_w",
    "monotonic_nonincreasing",
    "logic_separable",
    "unit_gain_crossings",
    "extraction_status",
    "qualified",
]

TRANSIENT_METRIC_FIELDS = [
    "route",
    "case_id",
    "dc_case_id",
    "vdd_v",
    "v_top_load_v",
    "v_top_load_over_vdd",
    "wload_over_wdriver",
    "cload_f",
    "point_count",
    "input_low_sample_vout_v",
    "input_high_sample_vout_v",
    "tphl_s",
    "tplh_s",
    "average_supply_power_w",
    "cycle_energy_j",
    "peak_supply_power_w",
    "fall_crossing_found",
    "rise_crossing_found",
    "extraction_status",
    "qualified",
]

DC_DIFFERENCE_FIELDS = [
    "case_id",
    "vin_fraction",
    "vin_v",
    "ngspice_vout_v",
    "xyce_vout_v",
    "absolute_vout_difference_v",
    "ngspice_supply_current_a",
    "xyce_supply_current_a",
    "absolute_supply_current_difference_a",
]

TRANSIENT_DIFFERENCE_FIELDS = [
    "case_id",
    "time_s",
    "ngspice_vin_v",
    "xyce_vin_v",
    "absolute_vin_difference_v",
    "ngspice_vout_v",
    "xyce_vout_v",
    "absolute_vout_difference_v",
    "ngspice_supply_current_a",
    "xyce_supply_current_a",
    "absolute_supply_current_difference_a",
]


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


def write_json(path: Path, payload: dict[str, Any], *, exclusive: bool = True) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = "x" if exclusive else "w"
    with path.open(mode, encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, indent=2, ensure_ascii=False)
        stream.write("\n")


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _spice_float(value: float) -> str:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite SPICE value: {value}")
    return format(parsed, ".17g")


def _continued(prefix: str, values: Iterable[str], width: int = 6) -> list[str]:
    items = list(values)
    lines: list[str] = []
    for offset in range(0, len(items), width):
        lead = prefix if offset == 0 else "+"
        lines.append(f"{lead} {' '.join(items[offset:offset + width])}")
    return lines


def dc_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    sweep = config["sweep_contract"]
    topology = config["topology_contract"]
    cases: list[dict[str, Any]] = []
    for vdd in sweep["vdd_v"]:
        for fraction in sweep["v_top_load_over_vdd"]:
            for ratio in sweep["wload_over_wdriver"]:
                case_id = (
                    f"v{round(vdd * 1000):03d}_"
                    f"t{round(fraction * 100):03d}_"
                    f"r{round(ratio * 1000):04d}"
                )
                cases.append(
                    {
                        "case_id": case_id,
                        "tag": case_id.replace("_", "").upper(),
                        "vdd_v": float(vdd),
                        "v_top_load_v": float(vdd) * float(fraction),
                        "v_top_load_over_vdd": float(fraction),
                        "wload_over_wdriver": float(ratio),
                        "driver_width_um": float(topology["driver_width_um"]),
                        "driver_length_um": float(topology["driver_length_um"]),
                        "load_width_um": float(topology["driver_width_um"]) * float(ratio),
                        "load_length_um": float(topology["load_length_um"]),
                    }
                )
    return cases


def transient_cases(config: dict[str, Any]) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for dc_case in dc_cases(config):
        for cload in config["sweep_contract"]["cload_f"]:
            case = dict(dc_case)
            case["dc_case_id"] = dc_case["case_id"]
            case["cload_f"] = float(cload)
            case["case_id"] = (
                f"{dc_case['case_id']}_c{round(float(cload) * 1e15):04d}"
            )
            case["tag"] = case["case_id"].replace("_", "").upper()
            cases.append(case)
    return cases


def _device_lines(case: dict[str, Any], config: dict[str, Any]) -> list[str]:
    tag = case["tag"]
    subckt = config["upstream_model"]["subcircuit"]
    return [
        (
            f"XLD{tag} VD{tag} VT{tag} VD{tag} VO{tag} {subckt} "
            f"WUM={_spice_float(case['load_width_um'])} "
            f"LUM={_spice_float(case['load_length_um'])}"
        ),
        (
            f"XDR{tag} VO{tag} VI{tag} 0 0 {subckt} "
            f"WUM={_spice_float(case['driver_width_um'])} "
            f"LUM={_spice_float(case['driver_length_um'])}"
        ),
    ]


def generate_dc_netlist(config: dict[str, Any], route: str) -> str:
    if route not in {"ngspice", "xyce"}:
        raise ValueError(f"unsupported route: {route}")
    output = config["outputs"]
    sweep = config["sweep_contract"]
    cases = dc_cases(config)
    lines = [
        f"* C00 R04 {route} IGZO-only active-load inverter DC",
        config["netlist_contract"]["candidate_include"],
        ".option numdgt=17",
        "VSWEEP NORM 0 0",
    ]
    vectors = ["V(NORM)"]
    for case in cases:
        tag = case["tag"]
        lines.extend(
            [
                f"VDD{tag} VD{tag} 0 {_spice_float(case['vdd_v'])}",
                f"VTP{tag} VT{tag} 0 {_spice_float(case['v_top_load_v'])}",
                f"EIN{tag} VI{tag} 0 NORM 0 {_spice_float(case['vdd_v'])}",
                *_device_lines(case, config),
            ]
        )
        vectors.extend([f"V(VO{tag})", f"I(VDD{tag})"])
    lines.append(
        ".DC VSWEEP "
        f"{_spice_float(sweep['dc_normalized_input_start'])} "
        f"{_spice_float(sweep['dc_normalized_input_stop'])} "
        f"{_spice_float(sweep['dc_normalized_input_step'])}"
    )
    if route == "ngspice":
        lines.extend(_continued(".save", vectors))
        lines.extend(
            [
                ".control",
                "set filetype=ascii",
                "run",
                f"write {output['ngspice_dc_raw']}",
                "quit",
                ".endc",
            ]
        )
    else:
        lines.extend(_continued(".PRINT DC FORMAT=NOINDEX PRECISION=17", vectors))
    lines.append(".end")
    text = "\n".join(lines) + "\n"
    if not text.isascii():
        raise ValueError("generated DC netlist is not ASCII")
    return text


def generate_transient_netlist(config: dict[str, Any], route: str) -> str:
    if route not in {"ngspice", "xyce"}:
        raise ValueError(f"unsupported route: {route}")
    output = config["outputs"]
    sweep = config["sweep_contract"]
    cases = transient_cases(config)
    lines = [
        f"* C00 R04 {route} IGZO-only active-load inverter transient",
        config["netlist_contract"]["candidate_include"],
        ".option numdgt=17",
    ]
    # Xyce emits TIME implicitly for transient PRINT tables; requesting it again
    # creates two identically named columns. ngspice still needs TIME in .save.
    vectors = ["TIME"] if route == "ngspice" else []
    for case in cases:
        tag = case["tag"]
        lines.extend(
            [
                f"VDD{tag} VD{tag} 0 {_spice_float(case['vdd_v'])}",
                f"VTP{tag} VT{tag} 0 {_spice_float(case['v_top_load_v'])}",
                (
                    f"VIN{tag} VI{tag} 0 PULSE(0 {_spice_float(case['vdd_v'])} "
                    f"{_spice_float(sweep['pulse_delay_s'])} "
                    f"{_spice_float(sweep['pulse_rise_s'])} "
                    f"{_spice_float(sweep['pulse_fall_s'])} "
                    f"{_spice_float(sweep['pulse_high_s'])} "
                    f"{_spice_float(sweep['pulse_period_s'])})"
                ),
                *_device_lines(case, config),
                f"CLOAD{tag} VO{tag} 0 {_spice_float(case['cload_f'])}",
            ]
        )
        vectors.extend([f"V(VI{tag})", f"V(VO{tag})", f"I(VDD{tag})"])
    lines.append(
        f".TRAN {_spice_float(sweep['transient_step_s'])} "
        f"{_spice_float(sweep['transient_stop_s'])}"
    )
    if route == "ngspice":
        lines.extend(_continued(".save", vectors))
        lines.extend(
            [
                ".control",
                "set filetype=ascii",
                "set plotwinsize=0",
                "run",
                f"write {output['ngspice_tran_raw']}",
                "quit",
                ".endc",
            ]
        )
    else:
        lines.extend(_continued(".PRINT TRAN FORMAT=NOINDEX PRECISION=17", vectors))
    lines.append(".end")
    text = "\n".join(lines) + "\n"
    if not text.isascii():
        raise ValueError("generated transient netlist is not ASCII")
    return text


def _normalize_vector(name: str) -> str:
    return name.strip().lower().replace("#branch", "")


def parse_ngspice_ascii_raw(path: Path) -> dict[str, list[float]]:
    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    variable_count = None
    point_count = None
    for line in lines:
        if line.startswith("No. Variables:"):
            variable_count = int(line.split(":", 1)[1])
        elif line.startswith("No. Points:"):
            point_count = int(line.split(":", 1)[1])
    try:
        variables_index = next(i for i, line in enumerate(lines) if line.strip() == "Variables:")
        values_index = next(i for i, line in enumerate(lines) if line.strip() == "Values:")
    except StopIteration as exc:
        raise ValueError("ngspice raw lacks Variables/Values sections") from exc
    names: list[str] = []
    for line in lines[variables_index + 1 : values_index]:
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            names.append(_normalize_vector(parts[1]))
    if variable_count is None or point_count is None or len(names) != variable_count:
        raise ValueError("ngspice raw header cardinality mismatch")
    rows: list[list[float]] = []
    cursor = values_index + 1
    for expected_index in range(point_count):
        while cursor < len(lines) and not lines[cursor].strip():
            cursor += 1
        if cursor >= len(lines):
            raise ValueError("ngspice raw ended before all points")
        first = lines[cursor].split()
        cursor += 1
        if len(first) < 2 or int(first[0]) != expected_index:
            raise ValueError(f"ngspice raw point index mismatch at {expected_index}")
        values = [float(first[-1])]
        while len(values) < variable_count:
            if cursor >= len(lines):
                raise ValueError("ngspice raw ended inside a point")
            parts = lines[cursor].replace(",", " ").split()
            cursor += 1
            if not parts:
                continue
            values.append(float(parts[-1]))
        rows.append(values)
    return {
        name: [row[index] for row in rows]
        for index, name in enumerate(names)
    }


def parse_xyce_prn(path: Path) -> dict[str, list[float]]:
    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    for header_index, line in enumerate(lines):
        headers = line.split()
        normalized = [_normalize_vector(item) for item in headers]
        if not headers or not any(
            item == "time" or item.startswith(("v(", "i(")) for item in normalized
        ):
            continue
        occurrences: dict[str, int] = defaultdict(int)
        column_keys: list[str] = []
        duplicate_keys: dict[str, list[str]] = defaultdict(list)
        for name in normalized:
            occurrences[name] += 1
            key = name if occurrences[name] == 1 else f"{name}__duplicate_{occurrences[name]}"
            column_keys.append(key)
            if occurrences[name] > 1:
                duplicate_keys[name].append(key)
        if any(name != "time" for name in duplicate_keys):
            raise ValueError("Xyce PRN contains a duplicate non-TIME header")
        columns: dict[str, list[float]] = defaultdict(list)
        saw_row = False
        for data_line in lines[header_index + 1 :]:
            parts = data_line.split()
            if parts and parts[0] == "End":
                break
            if len(parts) != len(headers):
                continue
            try:
                values = [float(item) for item in parts]
            except ValueError:
                continue
            saw_row = True
            for name, value in zip(column_keys, values):
                columns[name].append(value)
        if saw_row:
            columns.pop("index", None)
            for duplicate in duplicate_keys.get("time", []):
                if len(columns["time"]) != len(columns[duplicate]) or any(
                    not math.isclose(left, right, rel_tol=0.0, abs_tol=1e-30)
                    for left, right in zip(columns["time"], columns[duplicate])
                ):
                    raise ValueError("Xyce duplicate TIME columns differ")
                columns.pop(duplicate)
            return dict(columns)
    raise ValueError("Xyce PRN lacks a complete numeric table")


def _axis(vectors: dict[str, list[float]], names: tuple[str, ...]) -> list[float]:
    for name in names:
        if name in vectors:
            return vectors[name]
    raise ValueError(f"missing registered axis: {names}")


def _vector(vectors: dict[str, list[float]], name: str) -> list[float]:
    normalized = _normalize_vector(name)
    if normalized not in vectors:
        raise ValueError(f"missing vector {normalized}")
    return vectors[normalized]


def native_axis_summary(
    vectors: dict[str, list[float]],
    axis_names: tuple[str, ...],
    registered_start: float,
    registered_stop: float,
) -> dict[str, Any]:
    axis = _axis(vectors, axis_names)
    lengths = {len(values) for values in vectors.values()}
    finite = all(math.isfinite(value) for values in vectors.values() for value in values)
    strictly_increasing = len(axis) >= 2 and all(
        right > left for left, right in zip(axis, axis[1:])
    )
    tolerance = max(1e-15, abs(registered_stop) * 1e-10)
    covers_start = bool(axis) and axis[0] <= registered_start + tolerance
    covers_stop = bool(axis) and axis[-1] >= registered_stop - tolerance
    equal_cardinality = len(lengths) == 1
    valid = (
        equal_cardinality
        and finite
        and strictly_increasing
        and covers_start
        and covers_stop
    )
    return {
        "point_count": len(axis),
        "vector_count": len(vectors),
        "all_vectors_same_length": equal_cardinality,
        "all_values_finite": finite,
        "axis_strictly_increasing": strictly_increasing,
        "covers_registered_start": covers_start,
        "covers_registered_stop": covers_stop,
        "valid": valid,
    }


def interpolate(axis: list[float], values: list[float], target: float) -> float:
    if len(axis) != len(values) or not axis:
        raise ValueError("interpolation vector cardinality mismatch")
    tolerance = max(1e-15, abs(target) * 1e-10)
    if target < axis[0] - tolerance or target > axis[-1] + tolerance:
        raise ValueError(f"target {target} outside axis [{axis[0]}, {axis[-1]}]")
    if target <= axis[0]:
        return float(values[0])
    if target >= axis[-1]:
        return float(values[-1])
    low = 0
    high = len(axis) - 1
    while high - low > 1:
        mid = (low + high) // 2
        if axis[mid] <= target:
            low = mid
        else:
            high = mid
    if axis[high] == axis[low]:
        return float(values[low])
    fraction = (target - axis[low]) / (axis[high] - axis[low])
    return float(values[low] + fraction * (values[high] - values[low]))


def _registered_grid(start: float, stop: float, step: float) -> list[float]:
    count = round((stop - start) / step) + 1
    return [start + index * step for index in range(count)]


def extract_dc_rows(
    config: dict[str, Any], route: str, vectors: dict[str, list[float]]
) -> list[dict[str, Any]]:
    sweep = config["sweep_contract"]
    axis = _axis(vectors, ("v(norm)", "norm"))
    grid = _registered_grid(
        float(sweep["dc_normalized_input_start"]),
        float(sweep["dc_normalized_input_stop"]),
        float(sweep["dc_normalized_input_step"]),
    )
    rows: list[dict[str, Any]] = []
    for case in dc_cases(config):
        vout = _vector(vectors, f"v(vo{case['tag']})")
        supply = _vector(vectors, f"i(vdd{case['tag']})")
        for fraction in grid:
            output_value = interpolate(axis, vout, fraction)
            supply_value = abs(interpolate(axis, supply, fraction))
            values = [fraction, output_value, supply_value]
            rows.append(
                {
                    "route": route,
                    "case_id": case["case_id"],
                    "vdd_v": case["vdd_v"],
                    "v_top_load_v": case["v_top_load_v"],
                    "v_top_load_over_vdd": case["v_top_load_over_vdd"],
                    "wload_over_wdriver": case["wload_over_wdriver"],
                    "vin_fraction": fraction,
                    "vin_v": fraction * case["vdd_v"],
                    "vout_v": output_value,
                    "supply_current_a": supply_value,
                    "static_power_w": case["vdd_v"] * supply_value,
                    "finite": all(math.isfinite(value) for value in values),
                }
            )
    return rows


def extract_transient_rows(
    config: dict[str, Any], route: str, vectors: dict[str, list[float]]
) -> list[dict[str, Any]]:
    sweep = config["sweep_contract"]
    axis = _axis(vectors, ("time",))
    grid = _registered_grid(
        0.0,
        float(sweep["transient_stop_s"]),
        float(sweep["transient_step_s"]),
    )
    rows: list[dict[str, Any]] = []
    for case in transient_cases(config):
        vin = _vector(vectors, f"v(vi{case['tag']})")
        vout = _vector(vectors, f"v(vo{case['tag']})")
        supply = _vector(vectors, f"i(vdd{case['tag']})")
        for time_s in grid:
            vin_value = interpolate(axis, vin, time_s)
            vout_value = interpolate(axis, vout, time_s)
            supply_value = abs(interpolate(axis, supply, time_s))
            values = [time_s, vin_value, vout_value, supply_value]
            rows.append(
                {
                    "route": route,
                    "case_id": case["case_id"],
                    "dc_case_id": case["dc_case_id"],
                    "vdd_v": case["vdd_v"],
                    "v_top_load_v": case["v_top_load_v"],
                    "v_top_load_over_vdd": case["v_top_load_over_vdd"],
                    "wload_over_wdriver": case["wload_over_wdriver"],
                    "cload_f": case["cload_f"],
                    "time_s": time_s,
                    "vin_v": vin_value,
                    "vout_v": vout_value,
                    "supply_current_a": supply_value,
                    "instantaneous_power_w": case["vdd_v"] * supply_value,
                    "finite": all(math.isfinite(value) for value in values),
                }
            )
    return rows


def _zero_crossing(x: list[float], y: list[float]) -> float | None:
    for index in range(len(y) - 1):
        left = y[index]
        right = y[index + 1]
        if left == 0.0:
            return x[index]
        if left * right < 0.0 or right == 0.0:
            if right == left:
                return x[index]
            fraction = -left / (right - left)
            return x[index] + fraction * (x[index + 1] - x[index])
    return None


def _slopes(x: list[float], y: list[float]) -> list[float]:
    if len(x) < 3 or len(x) != len(y):
        raise ValueError("at least three aligned points are required for gain")
    slopes: list[float] = []
    for index in range(len(x)):
        if index == 0:
            left, right = 0, 1
        elif index == len(x) - 1:
            left, right = len(x) - 2, len(x) - 1
        else:
            left, right = index - 1, index + 1
        slopes.append((y[right] - y[left]) / (x[right] - x[left]))
    return slopes


def _all_crossings(x: list[float], y: list[float], target: float) -> list[float]:
    shifted = [value - target for value in y]
    crossings: list[float] = []
    for index in range(len(shifted) - 1):
        left = shifted[index]
        right = shifted[index + 1]
        if left == 0.0:
            crossings.append(x[index])
        elif left * right < 0.0 or right == 0.0:
            fraction = -left / (right - left) if right != left else 0.0
            crossings.append(x[index] + fraction * (x[index + 1] - x[index]))
    deduplicated: list[float] = []
    for value in crossings:
        if not deduplicated or abs(value - deduplicated[-1]) > 1e-15:
            deduplicated.append(value)
    return deduplicated


def compute_static_metrics(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["route"]), str(row["case_id"]))].append(row)
    acceptance = config["acceptance_contract"]
    output: list[dict[str, Any]] = []
    for (route, case_id), group in grouped.items():
        group.sort(key=lambda item: float(item["vin_v"]))
        vin = [float(item["vin_v"]) for item in group]
        vout = [float(item["vout_v"]) for item in group]
        vdd = float(group[0]["vdd_v"])
        slopes = _slopes(vin, vout)
        vm = _zero_crossing(vin, [out - inp for inp, out in zip(vin, vout)])
        crossings = _all_crossings(vin, slopes, -1.0)
        vil = crossings[0] if len(crossings) >= 2 else None
        vih = crossings[-1] if len(crossings) >= 2 else None
        voh = vout[0]
        vol = vout[-1]
        nml = vil - vol if vil is not None else None
        nmh = voh - vih if vih is not None else None
        monotonic = all(
            vout[index + 1] <= vout[index] + float(acceptance["dc_monotonic_tolerance_v"])
            for index in range(len(vout) - 1)
        )
        logic_separable = (
            voh >= float(acceptance["anchor_voh_min_fraction_vdd"]) * vdd
            and vol <= float(acceptance["anchor_vol_max_fraction_vdd"]) * vdd
            and voh > vol
        )
        max_gain = max(abs(value) for value in slopes)
        complete = vm is not None and vil is not None and vih is not None
        qualified = (
            complete
            and monotonic
            and logic_separable
            and float(acceptance["anchor_vm_min_fraction_vdd"]) * vdd <= float(vm)
            <= float(acceptance["anchor_vm_max_fraction_vdd"]) * vdd
            and max_gain >= float(acceptance["anchor_gain_min_v_per_v"])
            and len(crossings) >= int(acceptance["anchor_required_unit_gain_crossings"])
            and float(nml) >= float(acceptance["anchor_min_noise_margin_v"])
            and float(nmh) >= float(acceptance["anchor_min_noise_margin_v"])
        )
        output.append(
            {
                "route": route,
                "case_id": case_id,
                "vdd_v": vdd,
                "v_top_load_v": group[0]["v_top_load_v"],
                "v_top_load_over_vdd": group[0]["v_top_load_over_vdd"],
                "wload_over_wdriver": group[0]["wload_over_wdriver"],
                "point_count": len(group),
                "voh_v": voh,
                "vol_v": vol,
                "vm_v": vm,
                "max_gain_v_per_v": max_gain,
                "vil_v": vil,
                "vih_v": vih,
                "nml_v": nml,
                "nmh_v": nmh,
                "p_static_input_low_w": group[0]["static_power_w"],
                "p_static_input_high_w": group[-1]["static_power_w"],
                "monotonic_nonincreasing": monotonic,
                "logic_separable": logic_separable,
                "unit_gain_crossings": len(crossings),
                "extraction_status": "complete" if complete else "missing_registered_crossing",
                "qualified": qualified,
            }
        )
    return output


def _directional_crossing(
    times: list[float], values: list[float], threshold: float, start: float, direction: str
) -> float | None:
    for index in range(len(times) - 1):
        if times[index + 1] < start:
            continue
        left = values[index] - threshold
        right = values[index + 1] - threshold
        directional = (direction == "fall" and left >= 0.0 >= right) or (
            direction == "rise" and left <= 0.0 <= right
        )
        if directional:
            if right == left:
                return times[index]
            fraction = -left / (right - left)
            return times[index] + fraction * (times[index + 1] - times[index])
    return None


def _trapezoid(times: list[float], values: list[float], start: float, stop: float) -> float:
    points = [start] + [time for time in times if start < time < stop] + [stop]
    sampled = [interpolate(times, values, time) for time in points]
    return sum(
        0.5 * (sampled[index] + sampled[index + 1]) * (points[index + 1] - points[index])
        for index in range(len(points) - 1)
    )


def compute_transient_metrics(
    rows: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(str(row["route"]), str(row["case_id"]))].append(row)
    sweep = config["sweep_contract"]
    acceptance = config["acceptance_contract"]
    output: list[dict[str, Any]] = []
    for (route, case_id), group in grouped.items():
        group.sort(key=lambda item: float(item["time_s"]))
        times = [float(item["time_s"]) for item in group]
        vout = [float(item["vout_v"]) for item in group]
        power = [float(item["instantaneous_power_w"]) for item in group]
        vdd = float(group[0]["vdd_v"])
        threshold = 0.5 * vdd
        high_sample = interpolate(times, vout, float(sweep["pre_rising_sample_s"]))
        low_sample = interpolate(times, vout, float(sweep["pre_falling_sample_s"]))
        output_fall = _directional_crossing(
            times,
            vout,
            threshold,
            float(sweep["measured_rising_input_crossing_s"]),
            "fall",
        )
        output_rise = _directional_crossing(
            times,
            vout,
            threshold,
            float(sweep["measured_falling_input_crossing_s"]),
            "rise",
        )
        tphl = (
            output_fall - float(sweep["measured_rising_input_crossing_s"])
            if output_fall is not None
            else None
        )
        tplh = (
            output_rise - float(sweep["measured_falling_input_crossing_s"])
            if output_rise is not None
            else None
        )
        period_stop = float(sweep["transient_stop_s"])
        period_start = period_stop - float(sweep["pulse_period_s"])
        energy = _trapezoid(times, power, period_start, period_stop)
        average_power = energy / (period_stop - period_start)
        peak_power = max(
            value for time, value in zip(times, power) if period_start <= time <= period_stop
        )
        complete = tphl is not None and tplh is not None
        qualified = (
            complete
            and high_sample
            >= float(acceptance["anchor_transient_high_min_fraction_vdd"]) * vdd
            and low_sample
            <= float(acceptance["anchor_transient_low_max_fraction_vdd"]) * vdd
            and 0.0 <= float(tphl) <= float(acceptance["anchor_max_delay_s"])
            and 0.0 <= float(tplh) <= float(acceptance["anchor_max_delay_s"])
            and math.isfinite(average_power)
            and average_power >= 0.0
        )
        output.append(
            {
                "route": route,
                "case_id": case_id,
                "dc_case_id": group[0]["dc_case_id"],
                "vdd_v": vdd,
                "v_top_load_v": group[0]["v_top_load_v"],
                "v_top_load_over_vdd": group[0]["v_top_load_over_vdd"],
                "wload_over_wdriver": group[0]["wload_over_wdriver"],
                "cload_f": group[0]["cload_f"],
                "point_count": len(group),
                "input_low_sample_vout_v": high_sample,
                "input_high_sample_vout_v": low_sample,
                "tphl_s": tphl,
                "tplh_s": tplh,
                "average_supply_power_w": average_power,
                "cycle_energy_j": energy,
                "peak_supply_power_w": peak_power,
                "fall_crossing_found": output_fall is not None,
                "rise_crossing_found": output_rise is not None,
                "extraction_status": "complete" if complete else "missing_output_crossing",
                "qualified": qualified,
            }
        )
    return output


def compute_dc_differences(
    ngspice_rows: list[dict[str, Any]], xyce_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    xyce = {
        (str(row["case_id"]), float(row["vin_fraction"])): row
        for row in xyce_rows
    }
    output: list[dict[str, Any]] = []
    for ng in ngspice_rows:
        key = (str(ng["case_id"]), float(ng["vin_fraction"]))
        if key not in xyce:
            raise ValueError(f"missing Xyce DC row {key}")
        xy = xyce[key]
        output.append(
            {
                "case_id": ng["case_id"],
                "vin_fraction": ng["vin_fraction"],
                "vin_v": ng["vin_v"],
                "ngspice_vout_v": ng["vout_v"],
                "xyce_vout_v": xy["vout_v"],
                "absolute_vout_difference_v": abs(float(ng["vout_v"]) - float(xy["vout_v"])),
                "ngspice_supply_current_a": ng["supply_current_a"],
                "xyce_supply_current_a": xy["supply_current_a"],
                "absolute_supply_current_difference_a": abs(
                    float(ng["supply_current_a"]) - float(xy["supply_current_a"])
                ),
            }
        )
    return output


def compute_transient_differences(
    ngspice_rows: list[dict[str, Any]], xyce_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    xyce = {
        (str(row["case_id"]), float(row["time_s"])): row
        for row in xyce_rows
    }
    output: list[dict[str, Any]] = []
    for ng in ngspice_rows:
        key = (str(ng["case_id"]), float(ng["time_s"]))
        if key not in xyce:
            raise ValueError(f"missing Xyce transient row {key}")
        xy = xyce[key]
        output.append(
            {
                "case_id": ng["case_id"],
                "time_s": ng["time_s"],
                "ngspice_vin_v": ng["vin_v"],
                "xyce_vin_v": xy["vin_v"],
                "absolute_vin_difference_v": abs(float(ng["vin_v"]) - float(xy["vin_v"])),
                "ngspice_vout_v": ng["vout_v"],
                "xyce_vout_v": xy["vout_v"],
                "absolute_vout_difference_v": abs(float(ng["vout_v"]) - float(xy["vout_v"])),
                "ngspice_supply_current_a": ng["supply_current_a"],
                "xyce_supply_current_a": xy["supply_current_a"],
                "absolute_supply_current_difference_a": abs(
                    float(ng["supply_current_a"]) - float(xy["supply_current_a"])
                ),
            }
        )
    return output


def anchor_ids(config: dict[str, Any]) -> tuple[str, str]:
    anchor = config["sweep_contract"]["anchor"]
    dc_id = (
        f"v{round(float(anchor['vdd_v']) * 1000):03d}_"
        f"t{round(float(anchor['v_top_load_over_vdd']) * 100):03d}_"
        f"r{round(float(anchor['wload_over_wdriver']) * 1000):04d}"
    )
    transient_id = f"{dc_id}_c{round(float(anchor['cload_f']) * 1e15):04d}"
    return dc_id, transient_id


def render_plots(
    config: dict[str, Any],
    dc_rows: list[dict[str, Any]],
    transient_rows: list[dict[str, Any]],
    vtc_path: Path,
    transient_path: Path,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    dc_anchor, transient_anchor = anchor_ids(config)
    fig, axes = plt.subplots(1, 2, figsize=(14, 6), constrained_layout=True)
    for route, color in (("ngspice", "#00796b"), ("xyce", "#c62828")):
        all_route = [row for row in dc_rows if row["route"] == route]
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in all_route:
            grouped[str(row["case_id"])].append(row)
        for case_id, group in grouped.items():
            group.sort(key=lambda item: float(item["vin_v"]))
            axes[0].plot(
                [float(item["vin_v"]) for item in group],
                [float(item["vout_v"]) for item in group],
                color=color,
                alpha=0.14 if case_id != dc_anchor else 1.0,
                linewidth=0.8 if case_id != dc_anchor else 2.4,
                label=route if case_id == dc_anchor else None,
            )
            axes[1].semilogy(
                [float(item["vin_v"]) for item in group],
                [max(float(item["static_power_w"]), 1e-20) for item in group],
                color=color,
                alpha=0.14 if case_id != dc_anchor else 1.0,
                linewidth=0.8 if case_id != dc_anchor else 2.4,
                label=route if case_id == dc_anchor else None,
            )
    axes[0].set(title="C00 active-load inverter VTC", xlabel="VIN (V)", ylabel="VOUT (V)")
    axes[1].set(title="Static supply power", xlabel="VIN (V)", ylabel="Power (W)")
    for axis in axes:
        axis.grid(True, alpha=0.25)
        axis.legend()
    vtc_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(vtc_path, dpi=180)
    plt.close(fig)

    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True, constrained_layout=True)
    for route, color in (("ngspice", "#00796b"), ("xyce", "#c62828")):
        group = [
            row
            for row in transient_rows
            if row["route"] == route and row["case_id"] == transient_anchor
        ]
        group.sort(key=lambda item: float(item["time_s"]))
        axes[0].plot(
            [float(item["time_s"]) * 1e6 for item in group],
            [float(item["vin_v"]) for item in group],
            color="#455a64",
            alpha=0.55,
            linewidth=1.1,
            label="VIN" if route == "ngspice" else None,
        )
        axes[0].plot(
            [float(item["time_s"]) * 1e6 for item in group],
            [float(item["vout_v"]) for item in group],
            color=color,
            linewidth=2.0,
            label=f"VOUT {route}",
        )
        axes[1].plot(
            [float(item["time_s"]) * 1e6 for item in group],
            [float(item["instantaneous_power_w"]) for item in group],
            color=color,
            linewidth=1.5,
            label=route,
        )
    axes[0].set(title=f"Anchor transient: {transient_anchor}", ylabel="Voltage (V)")
    axes[1].set(xlabel="Time (us)", ylabel="Supply power (W)")
    for axis in axes:
        axis.grid(True, alpha=0.25)
        axis.legend()
    transient_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(transient_path, dpi=180)
    plt.close(fig)
