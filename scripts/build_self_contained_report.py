#!/usr/bin/env python3
"""Validate an XHTML draft and embed local images into one final HTML file."""

from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import re
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "report" / "src" / "实验报告_草稿.xhtml"
DEFAULT_OUTPUT = ROOT / "report" / "final" / "实验报告.html"
REPORT_MANIFEST = ROOT / "results" / "reports" / "self_contained_report.json"
XHTML_NS = "http://www.w3.org/1999/xhtml"
EXPECTED_SECTIONS = [f"section-{index:02d}" for index in range(1, 13)]
PLACEHOLDER_PATTERN = re.compile(r"\[待填写[^\]]*\]")


def tag(name: str) -> str:
    return f"{{{XHTML_NS}}}{name}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check-only", action="store_true")
    parser.add_argument("--allow-placeholders", action="store_true")
    return parser.parse_args()


def validate_structure(root: ET.Element) -> list[str]:
    errors: list[str] = []
    sections = [section.attrib.get("id", "") for section in root.findall(f".//{tag('section')}")]
    missing = [section_id for section_id in EXPECTED_SECTIONS if section_id not in sections]
    if missing:
        errors.append(f"Missing required sections: {', '.join(missing)}")
    if len([item for item in sections if item in EXPECTED_SECTIONS]) != 12:
        errors.append("The report must contain exactly 12 required main sections")
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


def embed_images(root: ET.Element, source_dir: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for image in root.findall(f".//{tag('img')}"):
        source = image.attrib.get("src", "")
        if not image.attrib.get("alt", "").strip():
            raise ValueError("Every image needs non-empty alt text")
        if source.startswith("data:image/"):
            records.append({"source": "already_embedded", "bytes": 0})
            continue
        if not source or is_forbidden_resource(source):
            raise ValueError(f"Forbidden or empty image source: {source!r}")
        image_path = (source_dir / source).resolve()
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
    source = args.source.resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    source_text = source.read_text(encoding="utf-8")
    root = ET.fromstring(source_text)
    errors = validate_structure(root)
    placeholders = PLACEHOLDER_PATTERN.findall(source_text)
    if placeholders and not args.allow_placeholders:
        errors.append(f"Unresolved placeholders: {len(placeholders)}")
    if errors:
        raise ValueError("; ".join(errors))

    if args.check_only:
        print(
            "REPORT_STRUCTURE_PASS "
            f"sections=12 placeholders={len(placeholders)} source={source}"
        )
        return 0

    image_records = embed_images(root, source.parent)
    ET.register_namespace("", XHTML_NS)
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized = ET.tostring(root, encoding="unicode", method="html")
    output.write_text("<!DOCTYPE html>\n" + serialized + "\n", encoding="utf-8")

    final_text = output.read_text(encoding="utf-8")
    external_images = re.findall(r'<img[^>]+src=["\'](?!data:image/)', final_text)
    if external_images:
        raise RuntimeError("Final report still contains external image references")

    manifest = {
        "status": "PASS",
        "source": str(source.relative_to(ROOT)),
        "output": str(output.relative_to(ROOT)),
        "sections": 12,
        "images_embedded": len(image_records),
        "external_images": 0,
        "output_bytes": output.stat().st_size,
        "images": image_records,
    }
    REPORT_MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    REPORT_MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n", encoding="utf-8"
    )
    print(
        "SELF_CONTAINED_REPORT_PASS "
        f"sections=12 images={len(image_records)} output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
