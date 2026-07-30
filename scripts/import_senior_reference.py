#!/usr/bin/env python3
"""Index senior references, audit Office structure, and normalize XLSX data."""

from __future__ import annotations

import csv
import hashlib
import json
import posixpath
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "project.json"
RAW_DIR = ROOT / "data" / "raw" / "senior_reference"
PROCESSED_DIR = ROOT / "data" / "processed" / "senior_reference"
REFERENCE_MANIFEST = ROOT / "references" / "senior_work_manifest.csv"
IMPORT_REPORT = ROOT / "results" / "reports" / "senior_reference_import.json"
OFFICE_SUMMARY = PROCESSED_DIR / "office_structure_summary.json"

MAIN_NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PACKAGE_REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
WORD_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
DRAWING_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def shared_strings(archive: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(archive.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return ["".join(node.text or "" for node in item.iter(f"{{{MAIN_NS}}}t")) for item in root]


def first_sheet(archive: zipfile.ZipFile) -> tuple[str, str]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(archive.read("xl/_rels/workbook.xml.rels"))
    targets = {
        relationship.attrib["Id"]: relationship.attrib["Target"]
        for relationship in relationships.findall(f"{{{PACKAGE_REL_NS}}}Relationship")
    }
    sheet = workbook.find(f".//{{{MAIN_NS}}}sheet")
    if sheet is None:
        raise ValueError("XLSX workbook has no worksheet")
    relationship_id = sheet.attrib[f"{{{REL_NS}}}id"]
    target = targets[relationship_id].lstrip("/")
    if not target.startswith("xl/"):
        target = posixpath.normpath(posixpath.join("xl", target))
    return sheet.attrib["name"], target


def read_first_sheet(path: Path) -> tuple[str, dict[str, str]]:
    with zipfile.ZipFile(path) as archive:
        strings = shared_strings(archive)
        sheet_name, sheet_path = first_sheet(archive)
        root = ET.fromstring(archive.read(sheet_path))

    cells: dict[str, str] = {}
    for cell in root.iter(f"{{{MAIN_NS}}}c"):
        reference = cell.attrib["r"]
        cell_type = cell.attrib.get("t", "")
        value_node = cell.find(f"{{{MAIN_NS}}}v")
        if cell_type == "inlineStr":
            value = "".join(node.text or "" for node in cell.iter(f"{{{MAIN_NS}}}t"))
        elif value_node is None:
            value = ""
        elif cell_type == "s":
            value = strings[int(value_node.text or "0")]
        else:
            value = value_node.text or ""
        cells[reference] = value
    return sheet_name, cells


def number(value: str, reference: str) -> float:
    try:
        return float(value)
    except ValueError as error:
        raise ValueError(f"Expected numeric value at {reference}: {value!r}") from error


def classify(relative: Path) -> tuple[str, str, str, str]:
    name = relative.name
    if name == "实验课程项目与报告要求(1).html":
        return (
            "teacher_requirement",
            "课程项目与报告权威要求",
            "authoritative_requirement",
            "用于约束项目方向、报告十二章结构、参数组数量和单文件HTML交付格式",
        )
    if name == "VisualTCAD_Inverter.pptx":
        return (
            "method_reference",
            "VisualTCAD二维硅CMOS反相器操作流程",
            "reference_only",
            "只参考建模、边界设置和报告截图顺序；不能当作氧化物TFT结果",
        )
    if name == "1.xlsx":
        return (
            "reference_dataset",
            "VisualTCAD导出的IGZO Id-Vg参考数据",
            "reference_only",
            "缺少VDS、几何、材料参数和求解设置，只能作曲线形状与导入流程参考",
        )
    if name == "王道玺的实验数据1(4).xlsx":
        return (
            "reference_dataset",
            "两组反相器VTC参考数据",
            "reference_only",
            "两列工况含义和电路条件未写入表格，未澄清前不得用于定量验证",
        )
    if name == "结果分析与讨论（排版后）.pptx":
        return (
            "report_structure",
            "双栅IGZO 2T0C DRAM结果分析PPT模板",
            "reference_only",
            "可参考章节与图注结构；图中数值属于被汇报论文，不属于本项目实测",
        )
    if name == "小组周四论文汇报(1).pptx":
        return (
            "report_structure",
            "论文汇报PPT章节结构",
            "reference_only",
            "背景材料；作者介绍和论文结果不能作为本项目贡献",
        )
    if name == "小组：李延顺、韩佳辰、王道玺、王法楊、孙金良、赵原登.docx":
        return (
            "report_structure",
            "二极管参数调节报告示例",
            "reference_only",
            "实验对象与本项目无关，只参考分组比较方式；其同时改变量方案不作为控制变量范例",
        )
    if name == "研究方法以及结果(1).docx":
        return (
            "report_structure",
            "a-IGZO缺陷文献的研究方法摘要",
            "reference_only",
            "属于文献归纳，不是本项目DFT或实测结果",
        )
    if name.lower().endswith(".pdf"):
        return (
            "literature",
            "学长资料中的背景论文或软件手册",
            "reference_only",
            "引用前核对原论文题目、图号、条件和许可；不自动继承论文结论",
        )
    return ("reference", "学长项目辅助文件", "reference_only", "用途需人工确认")


def write_reference_manifest(source_files: list[tuple[Path, Path]]) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for source, relative in source_files:
        category, role, use_status, boundary = classify(relative)
        records.append(
            {
                "relative_path": relative.as_posix(),
                "category": category,
                "role": role,
                "use_status": use_status,
                "evidence_boundary": boundary,
                "bytes": source.stat().st_size,
                "sha256": sha256(source),
                "source_path": str(source),
            }
        )

    REFERENCE_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    with REFERENCE_MANIFEST.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    return records


def natural_part_key(name: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", name)
    return tuple(int(part) if part.isdigit() else part for part in parts)


def truncated(text: str, limit: int = 240) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[: limit - 3] + "..."


def summarize_docx(path: Path, senior_root: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        document = ET.fromstring(archive.read("word/document.xml"))
        paragraphs: list[str] = []
        for paragraph in document.iter(f"{{{WORD_NS}}}p"):
            text = "".join(node.text or "" for node in paragraph.iter(f"{{{WORD_NS}}}t"))
            if text.strip():
                paragraphs.append(truncated(text))
        table_count = sum(1 for _ in document.iter(f"{{{WORD_NS}}}tbl"))
        media_count = sum(name.startswith("word/media/") for name in archive.namelist())

    return {
        "relative_path": path.relative_to(senior_root).as_posix(),
        "format": "docx",
        "paragraph_count": len(paragraphs),
        "table_count": table_count,
        "media_count": media_count,
        "outline_excerpts": paragraphs[:12],
    }


def summarize_pptx(path: Path, senior_root: Path) -> dict[str, object]:
    with zipfile.ZipFile(path) as archive:
        slide_names = sorted(
            (
                name
                for name in archive.namelist()
                if name.startswith("ppt/slides/slide")
                and name.endswith(".xml")
                and "/_rels/" not in name
            ),
            key=natural_part_key,
        )
        slide_excerpts: list[dict[str, object]] = []
        for slide_number, slide_name in enumerate(slide_names, 1):
            slide = ET.fromstring(archive.read(slide_name))
            text = " ".join(
                node.text or ""
                for node in slide.iter(f"{{{DRAWING_NS}}}t")
                if (node.text or "").strip()
            )
            if text.strip():
                slide_excerpts.append(
                    {"slide": slide_number, "text_excerpt": truncated(text, limit=360)}
                )
        media_count = sum(name.startswith("ppt/media/") for name in archive.namelist())
        chart_count = sum(
            name.startswith("ppt/charts/chart") and name.endswith(".xml")
            for name in archive.namelist()
        )

    return {
        "relative_path": path.relative_to(senior_root).as_posix(),
        "format": "pptx",
        "slide_count": len(slide_names),
        "text_slide_count": len(slide_excerpts),
        "media_count": media_count,
        "chart_count": chart_count,
        "slide_excerpts": slide_excerpts,
    }


def write_office_structure_summary(senior_root: Path) -> dict[str, object]:
    records: list[dict[str, object]] = []
    office_paths = sorted(
        (
            path
            for path in senior_root.rglob("*")
            if path.is_file() and path.suffix.lower() in {".docx", ".pptx"}
        ),
        key=lambda item: item.as_posix(),
    )
    for path in office_paths:
        if path.suffix.lower() == ".docx":
            records.append(summarize_docx(path, senior_root))
        else:
            records.append(summarize_pptx(path, senior_root))

    summary = {
        "source_root": str(senior_root),
        "files": records,
        "evidence_boundary": (
            "Text excerpts and counts describe source-file structure only. Images remain in the "
            "original Office packages; cited numerical results retain their literature/senior identity."
        ),
    }
    OFFICE_SUMMARY.write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    return {
        "output": str(OFFICE_SUMMARY.relative_to(ROOT)),
        "files": len(records),
        "docx_files": sum(record["format"] == "docx" for record in records),
        "pptx_files": sum(record["format"] == "pptx" for record in records),
    }


def transition_summary(vin: list[float], vout: list[float]) -> dict[str, object]:
    slopes = [
        (vout[index + 1] - vout[index]) / (vin[index + 1] - vin[index])
        for index in range(len(vin) - 1)
        if vin[index + 1] != vin[index]
    ]
    peak_index = max(range(len(slopes)), key=lambda index: abs(slopes[index]))
    return {
        "vout_min_v": min(vout),
        "vout_max_v": max(vout),
        "max_abs_slope_v_per_v": abs(slopes[peak_index]),
        "steepest_interval_v": [vin[peak_index], vin[peak_index + 1]],
        "transition_midpoint_v": 0.5 * (vin[peak_index] + vin[peak_index + 1]),
    }


def normalize_inverter_vtc(path: Path) -> dict[str, object]:
    sheet, cells = read_first_sheet(path)
    expected = {"B1": "Vin", "C1": "Vout1", "D1": "Vout2"}
    for reference, value in expected.items():
        if cells.get(reference) != value:
            raise ValueError(f"Unexpected inverter XLSX header {reference}: {cells.get(reference)!r}")

    output = PROCESSED_DIR / "inverter_vtc_reference.csv"
    rows: list[dict[str, object]] = []
    for row_number in range(2, 10000):
        if f"B{row_number}" not in cells:
            break
        rows.append(
            {
                "source_file": path.name,
                "source_sheet": sheet,
                "source_row": row_number,
                "vin_v": number(cells[f"B{row_number}"], f"B{row_number}"),
                "vout_case_1_v": number(cells[f"C{row_number}"], f"C{row_number}"),
                "vout_case_2_v": number(cells[f"D{row_number}"], f"D{row_number}"),
                "condition_status": "missing_circuit_and_bias_metadata",
            }
        )

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    vin = [float(row["vin_v"]) for row in rows]
    case_1 = [float(row["vout_case_1_v"]) for row in rows]
    case_2 = [float(row["vout_case_2_v"]) for row in rows]
    return {
        "output": str(output.relative_to(ROOT)),
        "rows": len(rows),
        "vin_min_v": min(vin),
        "vin_max_v": max(vin),
        "case_1": transition_summary(vin, case_1),
        "case_2": transition_summary(vin, case_2),
        "inferred_output_ceiling_v": max(case_1 + case_2),
        "inference_warning": "The output ceiling may suggest VDD, but the workbook does not confirm VDD or circuit conditions.",
        "metadata_status": "UNRESOLVED",
    }


def normalize_igzo_transfer(path: Path) -> dict[str, object]:
    sheet, cells = read_first_sheet(path)
    if "I(Drain" not in cells.get("A1", "") or "Vapp(Gate" not in cells.get("C1", ""):
        raise ValueError("Unexpected IGZO XLSX header layout")

    output = PROCESSED_DIR / "igzo_tcad_transfer_reference.csv"
    rows: list[dict[str, object]] = []
    previous_current: float | None = None
    for row_number in range(1, 10000):
        if f"B{row_number}" not in cells or f"D{row_number}" not in cells:
            break
        drain_current = number(cells[f"B{row_number}"], f"B{row_number}")
        gate_voltage = number(cells[f"D{row_number}"], f"D{row_number}")
        flags: list[str] = []
        if drain_current <= 0:
            flags.append("nonpositive_current")
        if abs(drain_current) < 1e-25:
            flags.append("near_solver_floor")
        if (
            previous_current is not None
            and previous_current > 1e-25
            and drain_current < previous_current / 10
        ):
            flags.append("strong_nonmonotonic_drop")
        previous_current = drain_current
        rows.append(
            {
                "source_file": path.name,
                "source_sheet": sheet,
                "source_row": row_number,
                "v_gate_v": gate_voltage,
                "drain_current_a": drain_current,
                "abs_drain_current_a": abs(drain_current),
                "quality_flag": ";".join(flags) if flags else "ok",
                "condition_status": "missing_vds_geometry_material_and_solver_metadata",
            }
        )

    with output.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    review_rows = [row["source_row"] for row in rows if row["quality_flag"] != "ok"]
    flag_counts: dict[str, int] = {}
    for row in rows:
        if row["quality_flag"] == "ok":
            continue
        for flag in str(row["quality_flag"]).split(";"):
            flag_counts[flag] = flag_counts.get(flag, 0) + 1

    return {
        "output": str(output.relative_to(ROOT)),
        "rows": len(rows),
        "v_gate_min_v": min(float(row["v_gate_v"]) for row in rows),
        "v_gate_max_v": max(float(row["v_gate_v"]) for row in rows),
        "current_min_a": min(float(row["abs_drain_current_a"]) for row in rows),
        "current_max_a": max(float(row["abs_drain_current_a"]) for row in rows),
        "review_rows": review_rows,
        "flagged_rows": len(review_rows),
        "quality_flag_counts": flag_counts,
        "dynamic_range_warning": (
            "Do not report the full numerical dynamic range as physical Ion/Ioff because the low-current "
            "tail includes solver-floor values."
        ),
        "metadata_status": "UNRESOLVED",
    }


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    source_roots = config["source_roots"]
    senior_root = Path(source_roots["senior_reference"])
    requirements = Path(source_roots["teacher_requirements"])
    if not senior_root.is_dir():
        raise FileNotFoundError(f"Missing senior source directory: {senior_root}")
    if not requirements.is_file():
        raise FileNotFoundError(f"Missing teacher requirements file: {requirements}")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    IMPORT_REPORT.parent.mkdir(parents=True, exist_ok=True)

    source_files = [(requirements, Path("../实验课程项目与报告要求(1).html"))]
    source_files.extend(
        (path, path.relative_to(senior_root))
        for path in sorted(senior_root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    )
    manifest_records = write_reference_manifest(source_files)

    inverter_source = senior_root / "王道玺的实验数据1(4).xlsx"
    igzo_source = senior_root / "2026_07_30_s41928-021-00671-0 (1)" / "1.xlsx"
    datasets = {
        "inverter_vtc_reference": normalize_inverter_vtc(inverter_source),
        "igzo_tcad_transfer_reference": normalize_igzo_transfer(igzo_source),
    }
    office_structure = write_office_structure_summary(senior_root)

    raw_manifest = {
        "project_id": config["project_id"],
        "indexed_on": config["created"],
        "policy": "Source Office/PDF files remain in place; this project stores paths, hashes and normalized CSV only.",
        "source_root": str(senior_root),
        "teacher_requirements": str(requirements),
        "files": manifest_records,
    }
    raw_manifest_path = RAW_DIR / "manifest.json"
    raw_manifest_path.write_text(
        json.dumps(raw_manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    report = {
        "status": "PASS",
        "files_indexed": len(manifest_records),
        "datasets": datasets,
        "office_structure": office_structure,
        "evidence_boundary": (
            "Both XLSX files are senior-reference data with incomplete conditions. "
            "They are not condition-complete teacher-provided IGZO measurements and cannot establish model accuracy."
        ),
    }
    IMPORT_REPORT.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(
        "SENIOR_REFERENCE_IMPORT_PASS "
        f"files={len(manifest_records)} "
        f"inverter_rows={datasets['inverter_vtc_reference']['rows']} "
        f"igzo_rows={datasets['igzo_tcad_transfer_reference']['rows']} "
        f"office_files={office_structure['files']} "
        f"report={IMPORT_REPORT}"
    )


if __name__ == "__main__":
    main()
