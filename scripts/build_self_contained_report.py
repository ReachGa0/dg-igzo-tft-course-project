#!/usr/bin/env python3
"""Assemble chapter sources and embed local images into one final HTML file."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
import sys
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "report"
DEFAULT_MANIFEST = REPORT_ROOT / "manifest.json"
REPORT_MANIFEST = ROOT / "results" / "reports" / "self_contained_report.json"
XHTML_NS = "http://www.w3.org/1999/xhtml"
EXPECTED_SECTIONS = [f"section-{index:02d}" for index in range(1, 13)]
EXPECTED_APPENDICES = [f"appendix-{letter}" for letter in "abcde"]
PLACEHOLDER_PATTERN = re.compile(r"\[待填写[^\]]*\]")


def tag(name: str) -> str:
    return f"{{{XHTML_NS}}}{name}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-placeholders", action="store_true")
    return parser.parse_args()


def resolve_project_path(relative: str, label: str) -> Path:
    value = Path(relative)
    if value.is_absolute():
        raise ValueError(f"{label} must be project-relative: {relative}")
    path = (ROOT / value).resolve()
    try:
        path.relative_to(ROOT.resolve())
    except ValueError as error:
        raise ValueError(f"{label} escapes the project root: {relative}") from error
    return path


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(path)
    manifest = json.loads(path.read_text(encoding="utf-8"))
    errors: list[str] = []
    chapters = manifest.get("chapters", [])
    appendices = manifest.get("appendices", [])

    if manifest.get("schema_version") != 1:
        errors.append("report manifest schema_version must be 1")
    if manifest.get("authoring_mode") != "chapter_sources":
        errors.append("authoring_mode must be chapter_sources")
    if manifest.get("submission_mode") != "single_self_contained_html":
        errors.append("submission_mode must be single_self_contained_html")
    if [item.get("id") for item in chapters] != EXPECTED_SECTIONS:
        errors.append("chapter IDs must be section-01 through section-12 in order")
    if [item.get("number") for item in chapters] != list(range(1, 13)):
        errors.append("chapter numbers must be 1 through 12 in order")
    if [item.get("id") for item in appendices] != EXPECTED_APPENDICES:
        errors.append("appendix IDs must be appendix-a through appendix-e in order")

    records = chapters + appendices
    sources = [item.get("source") for item in records]
    if any(not isinstance(source, str) or not source for source in sources):
        errors.append("every chapter and appendix needs a source path")
    if len(sources) != len(set(sources)):
        errors.append("chapter and appendix source paths must be unique")
    if not manifest.get("shell") or not manifest.get("output"):
        errors.append("report manifest needs shell and output paths")
    if errors:
        raise ValueError("; ".join(errors))
    return manifest


def parse_fragment(record: dict[str, Any], required_class: str) -> tuple[ET.Element, Path, str]:
    path = resolve_project_path(record["source"], f"source for {record['id']}")
    if not path.is_file():
        raise FileNotFoundError(path)
    source_text = path.read_text(encoding="utf-8")
    element = ET.fromstring(source_text)
    if element.tag != tag("section"):
        raise ValueError(f"Fragment root must be <section>: {path}")
    if element.attrib.get("id") != record["id"]:
        raise ValueError(
            f"Fragment ID mismatch for {path}: {element.attrib.get('id')} != {record['id']}"
        )
    classes = set(element.attrib.get("class", "").split())
    if required_class not in classes:
        raise ValueError(f"Fragment {path} must include class {required_class}")
    heading = element.find(tag("h2"))
    if heading is None or not "".join(heading.itertext()).strip():
        raise ValueError(f"Fragment {path} needs a non-empty h2")
    return element, path, source_text


def add_toc_item(toc: ET.Element, text: str, target_id: str) -> None:
    item = ET.SubElement(toc, tag("li"))
    link = ET.SubElement(item, tag("a"), {"href": f"#{target_id}"})
    link.text = text


def assemble_report(
    manifest: dict[str, Any],
) -> tuple[ET.Element, Path, list[dict[str, str]], str]:
    shell_path = resolve_project_path(manifest["shell"], "report shell")
    if not shell_path.is_file():
        raise FileNotFoundError(shell_path)
    shell_text = shell_path.read_text(encoding="utf-8")
    root = ET.fromstring(shell_text)
    if root.tag != tag("html"):
        raise ValueError("Report shell root must be <html>")

    content = root.find(f".//{tag('div')}[@id='report-content']")
    toc = root.find(f".//{tag('nav')}[@id='report-toc']/{tag('ol')}")
    if content is None or toc is None:
        raise ValueError("Report shell needs #report-content and #report-toc > ol")
    if list(content) or list(toc):
        raise ValueError("Report shell content and TOC containers must start empty")

    source_records: list[dict[str, str]] = []
    source_texts = [shell_text]
    for record in manifest["chapters"]:
        element, path, source_text = parse_fragment(record, "report-chapter")
        add_toc_item(toc, f"{record['number']}. {record['title']}", record["id"])
        content.append(element)
        source_records.append(
            {"id": record["id"], "type": "chapter", "source": str(path.relative_to(ROOT))}
        )
        source_texts.append(source_text)

    for record in manifest["appendices"]:
        element, path, source_text = parse_fragment(record, "report-appendix")
        add_toc_item(toc, f"附录{record['label']}：{record['title']}", record["id"])
        content.append(element)
        source_records.append(
            {"id": record["id"], "type": "appendix", "source": str(path.relative_to(ROOT))}
        )
        source_texts.append(source_text)

    return root, shell_path, source_records, "\n".join(source_texts)


def validate_structure(root: ET.Element) -> list[str]:
    errors: list[str] = []
    sections = [section.attrib.get("id", "") for section in root.findall(f".//{tag('section')}")]
    main_sections = [section_id for section_id in sections if section_id.startswith("section-")]
    appendices = [section_id for section_id in sections if section_id.startswith("appendix-")]
    if main_sections != EXPECTED_SECTIONS:
        errors.append("Assembled report chapters are missing, duplicated, or out of order")
    if appendices != EXPECTED_APPENDICES:
        errors.append("Assembled report appendices are missing, duplicated, or out of order")
    if root.find(f".//{tag('style')}") is None:
        errors.append("Inline CSS <style> is required")
    for link in root.findall(f".//{tag('link')}"):
        if link.attrib.get("rel", "").lower() == "stylesheet":
            errors.append("External stylesheet links are not allowed")
    for script in root.findall(f".//{tag('script')}"):
        if script.attrib.get("src"):
            errors.append("External script sources are not allowed")
    return errors


def is_forbidden_resource(source: str) -> bool:
    lowered = source.lower()
    return (
        lowered.startswith(("http://", "https://", "file://", "/", "\\"))
        or bool(re.match(r"^[a-zA-Z]:[\\/]", source))
    )


def embed_images(root: ET.Element) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    report_root = REPORT_ROOT.resolve()
    for image in root.findall(f".//{tag('img')}"):
        source = image.attrib.get("src", "")
        if not image.attrib.get("alt", "").strip():
            raise ValueError("Every image needs non-empty alt text")
        if source.startswith("data:image/"):
            records.append({"source": "already_embedded", "bytes": 0})
            continue
        if not source or is_forbidden_resource(source):
            raise ValueError(f"Forbidden or empty image source: {source!r}")
        image_path = (report_root / source).resolve()
        try:
            image_path.relative_to(report_root)
        except ValueError as error:
            raise ValueError(f"Report image escapes report/: {source}") from error
        if not image_path.is_file():
            raise FileNotFoundError(f"Missing report image: {image_path}")
        mime_type, _ = mimetypes.guess_type(image_path.name)
        if not mime_type or not mime_type.startswith("image/"):
            raise ValueError(f"Unsupported report image type: {image_path}")
        encoded = base64.b64encode(image_path.read_bytes()).decode("ascii")
        image.attrib["src"] = f"data:{mime_type};base64,{encoded}"
        records.append(
            {
                "source": str(image_path.relative_to(ROOT)),
                "bytes": image_path.stat().st_size,
                "mime_type": mime_type,
            }
        )
    return records


def main() -> int:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = load_manifest(manifest_path)
    root, shell_path, source_records, all_source_text = assemble_report(manifest)
    errors = validate_structure(root)
    placeholders = PLACEHOLDER_PATTERN.findall(all_source_text)
    if placeholders and not args.allow_placeholders:
        errors.append(f"Unresolved placeholders: {len(placeholders)}")
    if errors:
        raise ValueError("; ".join(errors))

    image_records = embed_images(root)
    if args.check_only:
        print(
            "REPORT_STRUCTURE_PASS "
            f"chapters=12 appendices=5 placeholders={len(placeholders)} "
            f"images={len(image_records)} manifest={manifest_path}"
        )
        return 0

    output = args.output.resolve() if args.output else resolve_project_path(manifest["output"], "output")
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.register_namespace("", XHTML_NS)
    serialized = ET.tostring(root, encoding="unicode", method="html")
    output.write_text("<!DOCTYPE html>\n" + serialized + "\n", encoding="utf-8")

    final_text = output.read_text(encoding="utf-8")
    external_images = re.findall(r'<img[^>]+src=["\'](?!data:image/)', final_text)
    if external_images:
        raise RuntimeError("Final report still contains external image references")

    result_manifest = {
        "status": "PASS",
        "authoring_mode": manifest["authoring_mode"],
        "submission_mode": manifest["submission_mode"],
        "source_manifest": str(manifest_path.relative_to(ROOT)),
        "shell": str(shell_path.relative_to(ROOT)),
        "output": str(output.relative_to(ROOT)),
        "chapters": 12,
        "appendices": 5,
        "source_files": source_records,
        "images_embedded": len(image_records),
        "external_images": 0,
        "output_bytes": output.stat().st_size,
        "images": image_records,
    }
    REPORT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MANIFEST.write_text(
        json.dumps(result_manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        "SELF_CONTAINED_REPORT_PASS "
        f"chapters=12 appendices=5 images={len(image_records)} output={output}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (FileNotFoundError, ValueError, RuntimeError) as error:
        print(f"REPORT_BUILD_FAIL {error}", file=sys.stderr)
        raise SystemExit(1) from None
