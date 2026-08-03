#!/usr/bin/env python3
"""Shared deterministic netlist, parser, and metric helpers for M01 R03."""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


RAW_FIELDS = [
    "row_index",
    "row_uid",
    "curve_id",
    "dataset_id",
    "split",
    "kind",
    "topology",
    "selection_role",
    "optimizer_input",
    "vbg_v",
    "vtg_v",
    "vds_v",
    "primary_axis_v",
    "target_current_a_per_cm",
    "model_current_a_per_cm",
    "w_um",
    "l_um",
    "temperature_k",
    "route",
    "source_current_a",
    "current_a_per_cm",
    "finite_current",
]

METRIC_FIELDS = [
    "route",
    "metric_scope",
    "curve_id",
    "split",
    "kind",
    "topology",
    "scored_point_count",
    "audit_point_count",
    "curve_count",
    "linear_nrmse",
    "log_rmse_dec",
    "max_abs_model_error_a_per_cm",
    "max_log_model_error_dec",
]

DIFFERENCE_FIELDS = [
    "row_index",
    "row_uid",
    "curve_id",
    "split",
    "kind",
    "topology",
    "selection_role",
    "primary_axis_v",
    "vds_v",
    "ngspice_current_a_per_cm",
    "xyce_current_a_per_cm",
    "absolute_difference_a_per_cm",
    "log_difference_dec",
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


def _spice_float(value: str | float) -> str:
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ValueError(f"non-finite SPICE value: {value}")
    return format(parsed, ".17g")


def _continued(prefix: str, values: Iterable[str], width: int = 8) -> list[str]:
    items = list(values)
    lines: list[str] = []
    for offset in range(0, len(items), width):
        lead = prefix if offset == 0 else "+"
        lines.append(f"{lead} {' '.join(items[offset:offset + width])}")
    return lines


def generate_device_netlist(
    rows: list[dict[str, str]],
    route: str,
    include_line: str,
    raw_output: str,
) -> str:
    if route not in {"ngspice", "xyce"}:
        raise ValueError(f"unsupported route: {route}")
    if not include_line.isascii() or not raw_output.isascii():
        raise ValueError("formal netlists require repository-relative ASCII paths")
    lines = [
        f"* M01 R03 {route} IGZO-only device DC",
        include_line,
        ".option numdgt=17",
        "VSWEEP SWEEP 0 0",
    ]
    current_names: list[str] = []
    for index, row in enumerate(rows):
        suffix = f"{index:03d}"
        lines.extend(
            [
                f"VDS{suffix} D{suffix} 0 {_spice_float(row['vds_v'])}",
                f"VTG{suffix} TG{suffix} 0 {_spice_float(row['vtg_v'])}",
                f"VBG{suffix} BG{suffix} 0 {_spice_float(row['vbg_v'])}",
                (
                    f"XDEV{suffix} D{suffix} TG{suffix} BG{suffix} 0 "
                    "IGZO_DG_BEHAVIORAL_R03_PORTABLE "
                    f"WUM={_spice_float(row['w_um'])} LUM={_spice_float(row['l_um'])}"
                ),
            ]
        )
        current_names.append(f"I(VDS{suffix})")
    lines.append(".DC VSWEEP 0 0 1")
    if route == "ngspice":
        lines.extend(_continued(".save", current_names))
        lines.extend(
            [
                ".control",
                "set filetype=ascii",
                "run",
                f"write {raw_output}",
                "quit",
                ".endc",
            ]
        )
    else:
        lines.extend(
            _continued(".PRINT DC FORMAT=NOINDEX PRECISION=17", current_names)
        )
    lines.append(".end")
    text = "\n".join(lines) + "\n"
    if not text.isascii():
        raise ValueError("generated netlist is not ASCII")
    return text


def parse_ngspice_ascii_raw(path: Path) -> dict[str, float]:
    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    try:
        variables_index = next(i for i, line in enumerate(lines) if line.strip() == "Variables:")
        values_index = next(i for i, line in enumerate(lines) if line.strip() == "Values:")
    except StopIteration as exc:
        raise ValueError("ngspice ASCII raw file lacks Variables/Values sections") from exc
    variables: list[str] = []
    for line in lines[variables_index + 1 : values_index]:
        parts = line.split()
        if len(parts) >= 3 and parts[0].isdigit():
            variables.append(parts[1])
    numeric: list[float] = []
    for line in lines[values_index + 1 :]:
        parts = line.replace(",", " ").split()
        if not parts:
            continue
        candidate = parts[-1]
        try:
            numeric.append(float(candidate))
        except ValueError:
            continue
        if len(numeric) == len(variables):
            break
    if len(variables) < 2 or len(numeric) != len(variables):
        raise ValueError(
            f"ngspice raw cardinality mismatch variables={len(variables)} values={len(numeric)}"
        )
    return {_normalize_current_name(name): value for name, value in zip(variables, numeric)}


def parse_xyce_prn(path: Path) -> dict[str, float]:
    lines = path.read_text(encoding="ascii", errors="strict").splitlines()
    for index, line in enumerate(lines):
        headers = line.split()
        if not any(_normalize_current_name(item).startswith("i(vds") for item in headers):
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
                _normalize_current_name(name): value
                for name, value in zip(headers, values)
            }
    raise ValueError("Xyce PRN lacks one complete registered-current row")


def _normalize_current_name(name: str) -> str:
    lowered = name.strip().lower().replace("#branch", "")
    if lowered.startswith("i("):
        return lowered
    if lowered.startswith("vds"):
        return f"i({lowered})"
    return lowered


def extract_route_rows(
    manifest_rows: list[dict[str, str]],
    prediction_rows: list[dict[str, str]],
    route: str,
    currents: dict[str, float],
) -> list[dict[str, Any]]:
    prediction_by_uid = {row["row_uid"]: row for row in prediction_rows}
    output: list[dict[str, Any]] = []
    for index, row in enumerate(manifest_rows):
        key = f"i(vds{index:03d})"
        if key not in currents:
            raise ValueError(f"missing route current {key}")
        source_current = float(currents[key])
        width_cm = float(row["w_um"]) * 1e-4
        current = abs(source_current) / width_cm
        prediction = prediction_by_uid[row["row_uid"]]
        output.append(
            {
                "row_index": index,
                **{field: row[field] for field in RAW_FIELDS if field in row},
                "model_current_a_per_cm": prediction["model_current_a_per_cm"],
                "route": route,
                "source_current_a": format(source_current, ".17g"),
                "current_a_per_cm": format(current, ".17g"),
                "finite_current": math.isfinite(current),
            }
        )
    return output


def compute_metrics(
    route_rows: list[dict[str, Any]], current_floor: float
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in route_rows:
        grouped[str(row["curve_id"])].append(row)
    metrics: list[dict[str, Any]] = []
    for curve_id in sorted(grouped):
        rows = grouped[curve_id]
        scored = [row for row in rows if row["selection_role"] == "scored"]
        if not scored:
            raise ValueError(f"curve {curve_id} has no scored rows")
        target = [abs(float(row["target_current_a_per_cm"])) for row in scored]
        route = [float(row["current_a_per_cm"]) for row in scored]
        model = [abs(float(row["model_current_a_per_cm"])) for row in scored]
        scale = max(max(target), current_floor)
        linear = math.sqrt(sum((a - b) ** 2 for a, b in zip(route, target)) / len(scored)) / scale
        log_error = [
            math.log10(max(a, current_floor)) - math.log10(max(b, current_floor))
            for a, b in zip(route, target)
        ]
        model_log_error = [
            abs(math.log10(max(a, current_floor)) - math.log10(max(b, current_floor)))
            for a, b in zip(route, model)
        ]
        metrics.append(
            {
                "route": rows[0]["route"],
                "metric_scope": "curve",
                "curve_id": curve_id,
                "split": rows[0]["split"],
                "kind": rows[0]["kind"],
                "topology": rows[0]["topology"],
                "scored_point_count": len(scored),
                "audit_point_count": len(rows) - len(scored),
                "curve_count": 1,
                "linear_nrmse": format(linear, ".17g"),
                "log_rmse_dec": format(
                    math.sqrt(sum(value * value for value in log_error) / len(log_error)),
                    ".17g",
                ),
                "max_abs_model_error_a_per_cm": format(
                    max(abs(a - b) for a, b in zip(route, model)), ".17g"
                ),
                "max_log_model_error_dec": format(max(model_log_error), ".17g"),
            }
        )
    for split in ("train", "holdout"):
        selected = [row for row in metrics if row["split"] == split]
        metrics.append(
            {
                "route": route_rows[0]["route"],
                "metric_scope": "aggregate_equal_curve_weight",
                "curve_id": "__aggregate__",
                "split": split,
                "kind": "mixed",
                "topology": "mixed",
                "scored_point_count": sum(int(row["scored_point_count"]) for row in selected),
                "audit_point_count": sum(int(row["audit_point_count"]) for row in selected),
                "curve_count": len(selected),
                "linear_nrmse": format(
                    sum(float(row["linear_nrmse"]) for row in selected) / len(selected),
                    ".17g",
                ),
                "log_rmse_dec": format(
                    sum(float(row["log_rmse_dec"]) for row in selected) / len(selected),
                    ".17g",
                ),
                "max_abs_model_error_a_per_cm": format(
                    max(float(row["max_abs_model_error_a_per_cm"]) for row in selected),
                    ".17g",
                ),
                "max_log_model_error_dec": format(
                    max(float(row["max_log_model_error_dec"]) for row in selected),
                    ".17g",
                ),
            }
        )
    return metrics


def compute_route_differences(
    ngspice_rows: list[dict[str, Any]],
    xyce_rows: list[dict[str, Any]],
    current_floor: float,
) -> list[dict[str, Any]]:
    if [row["row_uid"] for row in ngspice_rows] != [row["row_uid"] for row in xyce_rows]:
        raise ValueError("route row order differs")
    output: list[dict[str, Any]] = []
    for left, right in zip(ngspice_rows, xyce_rows):
        ng_current = float(left["current_a_per_cm"])
        xyce_current = float(right["current_a_per_cm"])
        output.append(
            {
                "row_index": left["row_index"],
                "row_uid": left["row_uid"],
                "curve_id": left["curve_id"],
                "split": left["split"],
                "kind": left["kind"],
                "topology": left["topology"],
                "selection_role": left["selection_role"],
                "primary_axis_v": left["primary_axis_v"],
                "vds_v": left["vds_v"],
                "ngspice_current_a_per_cm": format(ng_current, ".17g"),
                "xyce_current_a_per_cm": format(xyce_current, ".17g"),
                "absolute_difference_a_per_cm": format(abs(ng_current - xyce_current), ".17g"),
                "log_difference_dec": format(
                    abs(
                        math.log10(max(ng_current, current_floor))
                        - math.log10(max(xyce_current, current_floor))
                    ),
                    ".17g",
                ),
            }
        )
    return output


def render_plots(
    ngspice_rows: list[dict[str, Any]],
    xyce_rows: list[dict[str, Any]],
    difference_rows: list[dict[str, Any]],
    overlay_path: Path,
    difference_path: Path,
    current_floor: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    grouped_ng: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_xy: dict[str, list[dict[str, Any]]] = defaultdict(list)
    grouped_diff: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ngspice_rows:
        grouped_ng[str(row["curve_id"])].append(row)
    for row in xyce_rows:
        grouped_xy[str(row["curve_id"])].append(row)
    for row in difference_rows:
        grouped_diff[str(row["curve_id"])].append(row)
    curves = sorted(grouped_ng)
    overlay_path.parent.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(4, 4, figsize=(14, 11), constrained_layout=True)
    for axis, curve_id in zip(axes.flat, curves):
        left = grouped_ng[curve_id]
        right = grouped_xy[curve_id]
        x = [float(row["primary_axis_v"]) for row in left]
        axis.semilogy(x, [max(float(row["current_a_per_cm"]), current_floor) for row in left], label="ngspice")
        axis.semilogy(x, [max(float(row["current_a_per_cm"]), current_floor) for row in right], "--", label="Xyce")
        axis.semilogy(x, [max(abs(float(row["target_current_a_per_cm"])), current_floor) for row in left], ":", label="target")
        axis.set_title(curve_id, fontsize=8)
        axis.grid(True, alpha=0.25)
    for axis in axes.flat[len(curves) :]:
        axis.axis("off")
    axes.flat[0].legend(fontsize=7)
    fig.supxlabel("Frozen primary axis (V)")
    fig.supylabel("|ID|/W (A/cm)")
    fig.savefig(overlay_path, dpi=160)
    plt.close(fig)

    fig, axes = plt.subplots(4, 4, figsize=(14, 11), constrained_layout=True)
    for axis, curve_id in zip(axes.flat, curves):
        rows = grouped_diff[curve_id]
        axis.plot(
            [float(row["primary_axis_v"]) for row in rows],
            [float(row["log_difference_dec"]) for row in rows],
        )
        axis.set_title(curve_id, fontsize=8)
        axis.grid(True, alpha=0.25)
    for axis in axes.flat[len(curves) :]:
        axis.axis("off")
    fig.supxlabel("Frozen primary axis (V)")
    fig.supylabel("ngspice-Xyce |Delta log10(ID)| (dec)")
    fig.savefig(difference_path, dpi=160)
    plt.close(fig)
