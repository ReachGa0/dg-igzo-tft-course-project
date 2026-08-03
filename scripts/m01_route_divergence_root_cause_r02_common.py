#!/usr/bin/env python3
"""Shared deterministic helpers for the M01 route-divergence R02 probe."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from typing import Any


PROBE_FIELDS = [
    "route",
    "observable",
    "group",
    "expected",
    "actual",
    "absolute_error",
    "relative_error",
    "gate_role",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=PROBE_FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def portable_candidate_text(candidate_text: str) -> str:
    original = "limit(x/s,-60,60)"
    replacement = "min(max(x/s,-60),60)"
    if candidate_text.count(original) != 1:
        raise ValueError("candidate must contain exactly one registered limit expression")
    text = candidate_text.replace(
        "IGZO_DG_BEHAVIORAL_R02", "IGZO_DG_PORTABLE_PROBE_R02"
    )
    text = text.replace("M00_Q", "RCA_Q").replace("BIDS", "BPORT")
    return text.replace(original, replacement)


def analytical_source_current(
    point: dict[str, Any], parameters: dict[str, float]
) -> float:
    vtg = float(point["vtg_v"])
    vbg = float(point["vbg_v"])
    vds = float(point["vds_v"])
    width_um = float(point["w_um"])
    length_um = float(point["l_um"])
    if vds == 0.0:
        return 0.0

    soft = parameters["M00_SOFT"]

    def q(value: float) -> float:
        scaled = min(max(value / soft, -60.0), 60.0)
        return soft * math.log1p(math.exp(scaled))

    drive = (
        parameters["M00_ETA"] * (vtg + vbg)
        - parameters["M00_VTHDG"]
        - parameters["M00_KVTHL"] * math.log(length_um / 10.0)
    )
    magnitude = width_um * 1e-4 * (
        10.0 ** parameters["M00_LOGBETA"]
        * (10.0 / length_um)
        * (
            q(drive) ** parameters["M00_GAMMA"]
            - q(drive - parameters["M00_KD"] * abs(vds))
            ** parameters["M00_GAMMA"]
        )
        * (1.0 + parameters["M00_LAMBDA"] * abs(vds))
        + 10.0 ** parameters["M00_LOGGMIN"] * abs(vds)
    )
    device_current = math.copysign(magnitude, vds)
    return -device_current


def expected_observables(config: dict[str, Any]) -> dict[str, float]:
    probe = config["probe_contract"]
    values: dict[str, float] = {}
    labels = ("lo", "mid", "hi")
    for label, expected in zip(labels, probe["expected_clamp_outputs"]):
        values[f"v({label}_limit)"] = float(expected)
        values[f"v({label}_clamp)"] = float(expected)
    values["i(vsense)"] = float(probe["expected_branch_source_current_a"])
    for index, point in enumerate(probe["candidate_probe_points"]):
        expected = analytical_source_current(point, probe["candidate_parameters"])
        values[f"i(vorig{index})"] = expected
        values[f"i(vport{index})"] = expected
    return values


def _spice_float(value: Any) -> str:
    return format(float(value), ".17g")


def _continued(prefix: str, names: list[str], width: int = 6) -> list[str]:
    lines: list[str] = []
    for start in range(0, len(names), width):
        lead = prefix if start == 0 else "+"
        lines.append(f"{lead} {' '.join(names[start:start + width])}")
    return lines


def generate_probe_netlist(
    config: dict[str, Any], route: str, candidate_text: str
) -> str:
    if route not in {"ngspice", "xyce"}:
        raise ValueError(f"unsupported route {route}")
    outputs = config["outputs"]
    probe = config["probe_contract"]
    portable = portable_candidate_text(candidate_text)
    lines = [
        f"* M01 route-divergence root-cause R02 {route}",
        '.include "spice/models/igzo_dg_behavioral_r02.inc"',
        portable.rstrip(),
        ".option numdgt=17",
        "VSWEEP SWEEP 0 0",
        ".func RCA_LIMIT_PROBE(x) {limit(x,-60,60)}",
        ".func RCA_CLAMP_PROBE(x) {min(max(x,-60),60)}",
    ]
    labels = ("LO", "MID", "HI")
    for label, value in zip(labels, probe["expression_inputs"]):
        lines.append(f"B{label}LIMIT {label}_LIMIT 0 V={{RCA_LIMIT_PROBE({_spice_float(value)})}}")
        lines.append(f"B{label}CLAMP {label}_CLAMP 0 V={{RCA_CLAMP_PROBE({_spice_float(value)})}}")
    lines.extend(
        [
            f"VSENSE NSENSE 0 {_spice_float(probe['branch_sentinel_voltage_v'])}",
            f"RSENSE NSENSE 0 {_spice_float(probe['branch_sentinel_resistance_ohm'])}",
        ]
    )
    for index, point in enumerate(probe["candidate_probe_points"]):
        suffix = str(index)
        for family in ("ORIG", "PORT"):
            lines.extend(
                [
                    f"V{family}{suffix} D{family}{suffix} 0 {_spice_float(point['vds_v'])}",
                    f"VT{family}{suffix} T{family}{suffix} 0 {_spice_float(point['vtg_v'])}",
                    f"VB{family}{suffix} B{family}{suffix} 0 {_spice_float(point['vbg_v'])}",
                ]
            )
        lines.append(
            f"XORIG{suffix} DORIG{suffix} TORIG{suffix} BORIG{suffix} 0 "
            "IGZO_DG_BEHAVIORAL_R02 "
            f"WUM={_spice_float(point['w_um'])} LUM={_spice_float(point['l_um'])}"
        )
        lines.append(
            f"XPORT{suffix} DPORT{suffix} TPORT{suffix} BPORT{suffix} 0 "
            "IGZO_DG_PORTABLE_PROBE_R02 "
            f"WUM={_spice_float(point['w_um'])} LUM={_spice_float(point['l_um'])}"
        )
    observables = [
        "V(LO_LIMIT)", "V(LO_CLAMP)", "V(MID_LIMIT)", "V(MID_CLAMP)",
        "V(HI_LIMIT)", "V(HI_CLAMP)", "I(VSENSE)",
        "I(VORIG0)", "I(VPORT0)", "I(VORIG1)", "I(VPORT1)",
        "I(VORIG2)", "I(VPORT2)",
    ]
    lines.append(probe["analysis"])
    if route == "ngspice":
        lines.extend(_continued(".save", observables))
        lines.extend(
            [
                ".control",
                "set filetype=ascii",
                "run",
                f"write {outputs['ngspice_raw_output']}",
                "quit",
                ".endc",
            ]
        )
    else:
        lines.extend(_continued(".PRINT DC FORMAT=NOINDEX PRECISION=17", observables))
    lines.append(".end")
    text = "\n".join(lines) + "\n"
    if not text.isascii():
        raise ValueError("probe netlist must be ASCII")
    return text


def _normalize_name(name: str) -> str:
    lowered = name.strip().lower().replace("#branch", "")
    if lowered.startswith(("v(", "i(")):
        return lowered
    if lowered.startswith("v") and lowered[1:].isalnum():
        return f"i({lowered})"
    return lowered


def parse_ngspice_ascii_raw(path: Path) -> dict[str, float]:
    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    variables_index = next(i for i, line in enumerate(lines) if line.strip() == "Variables:")
    values_index = next(i for i, line in enumerate(lines) if line.strip() == "Values:")
    variables = [
        parts[1]
        for line in lines[variables_index + 1 : values_index]
        if len(parts := line.split()) >= 3 and parts[0].isdigit()
    ]
    numeric: list[float] = []
    for line in lines[values_index + 1 :]:
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        try:
            numeric.append(float(parts[-1]))
        except ValueError:
            continue
        if len(numeric) == len(variables):
            break
    if len(numeric) != len(variables):
        raise ValueError(f"ngspice cardinality {len(numeric)}/{len(variables)}")
    return {_normalize_name(name): value for name, value in zip(variables, numeric)}


def parse_xyce_prn(path: Path) -> dict[str, float]:
    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    for index, line in enumerate(lines):
        headers = line.split()
        if "Index" not in headers or not any("LIMIT" in item for item in headers):
            continue
        for data_line in lines[index + 1 :]:
            parts = data_line.split()
            if len(parts) != len(headers):
                continue
            try:
                values = [float(item) for item in parts]
            except ValueError:
                continue
            return {
                _normalize_name(name): value
                for name, value in zip(headers, values)
                if name.lower() != "index"
            }
    raise ValueError("Xyce PRN lacks a complete probe row")


def build_probe_rows(
    route: str, values: dict[str, float], expected: dict[str, float]
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for observable, reference in expected.items():
        if observable not in values:
            raise ValueError(f"missing {route} observable {observable}")
        actual = float(values[observable])
        absolute = abs(actual - reference)
        relative = absolute / max(abs(reference), 1e-30)
        if "_limit)" in observable:
            group, gate_role = "three_argument_limit", "classification"
        elif "_clamp)" in observable:
            group, gate_role = "explicit_clamp", "acceptance"
        elif observable == "i(vsense)":
            group, gate_role = "branch_sentinel", "acceptance"
        elif "vorig" in observable:
            group, gate_role = "original_candidate", "classification"
        else:
            group, gate_role = "portable_candidate", "acceptance"
        rows.append(
            {
                "route": route,
                "observable": observable,
                "group": group,
                "expected": format(reference, ".17g"),
                "actual": format(actual, ".17g"),
                "absolute_error": format(absolute, ".17g"),
                "relative_error": format(relative, ".17g"),
                "gate_role": gate_role,
            }
        )
    return rows


def group_rows(rows: list[dict[str, Any]], route: str, group: str) -> list[dict[str, Any]]:
    return [row for row in rows if row["route"] == route and row["group"] == group]
