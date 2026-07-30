#!/usr/bin/env python3
"""Generate the reproducible S00 data, unit, and conflict audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
AUDIT_CONFIG = ROOT / "config" / "s00_data_audit.json"
PROJECT_CONFIG = ROOT / "config" / "project.json"
TCAD_CONFIG = ROOT / "config" / "tcad_baseline.json"
BASELINE_MANIFEST = ROOT / "data" / "raw" / "baseline" / "manifest.json"
SENIOR_MANIFEST = ROOT / "data" / "raw" / "senior_reference" / "manifest.json"
PAPERS_MANIFEST = ROOT / "references" / "papers_manifest.csv"
OUTPUT_DIR = ROOT / "data" / "processed" / "s00"
REPORT_PATH = ROOT / "results" / "reports" / "s00_data_audit.json"
SOURCE_DOCUMENT_FILES = {
    "project": "config/project.json",
    "tcad": "config/tcad_baseline.json",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dotted_value(document: dict[str, Any], key: str) -> Any:
    value: Any = document
    for segment in key.split("."):
        if not isinstance(value, dict) or segment not in value:
            raise KeyError(key)
        value = value[segment]
    return value


def csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def hash_row(
    *,
    dataset_id: str,
    source_id: str,
    source_path: Path,
    expected_sha256: str | None,
    source_role: str,
    use_status: str,
    scope: str,
) -> tuple[dict[str, Any], bool]:
    exists = source_path.is_file()
    actual_sha256 = sha256(source_path) if exists else ""
    passed = exists and (expected_sha256 is None or actual_sha256 == expected_sha256)
    return (
        {
            "dataset_id": dataset_id,
            "source_id": source_id,
            "source_path": str(source_path),
            "source_role": source_role,
            "use_status": use_status,
            "scope": scope,
            "bytes": source_path.stat().st_size if exists else 0,
            "sha256": actual_sha256,
            "expected_sha256": expected_sha256 or "computed_from_source",
            "hash_status": "PASS" if passed else "FAIL",
        },
        passed,
    )


def collect_source_inventory(project: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []

    baseline = load_json(BASELINE_MANIFEST)
    for record in baseline["files"]:
        source = Path(record["source"])
        destination = ROOT / record["destination"]
        source_row, source_ok = hash_row(
            dataset_id="IGZO_FROZEN_BASELINE_V1",
            source_id=f"baseline_source:{record['destination']}",
            source_path=source,
            expected_sha256=record["sha256"],
            source_role="frozen_baseline_source",
            use_status="reference_only",
            scope="IGZO-only whitelisted import",
        )
        destination_row, destination_ok = hash_row(
            dataset_id="IGZO_FROZEN_BASELINE_V1",
            source_id=f"baseline_copy:{record['destination']}",
            source_path=destination,
            expected_sha256=record["sha256"],
            source_role="project_raw_copy",
            use_status="reference_only",
            scope="IGZO-only whitelisted import",
        )
        rows.extend((source_row, destination_row))
        if not source_ok or not destination_ok:
            errors.append(f"baseline hash mismatch: {record['destination']}")
        if "sno" in record["destination"].lower():
            errors.append(f"non-IGZO baseline import: {record['destination']}")

    senior = load_json(SENIOR_MANIFEST)
    for record in senior["files"]:
        use_status = str(record["use_status"])
        scope = "teacher requirement" if use_status == "authoritative_requirement" else "senior reference only"
        row, passed = hash_row(
            dataset_id=(
                "COURSE_REQUIREMENT_CONTRACT_V1"
                if use_status == "authoritative_requirement"
                else "SENIOR_REFERENCE_INDEX_V1"
            ),
            source_id=f"senior:{record['relative_path']}",
            source_path=Path(record["source_path"]),
            expected_sha256=record["sha256"],
            source_role=str(record["role"]),
            use_status=use_status,
            scope=scope,
        )
        rows.append(row)
        if not passed:
            errors.append(f"senior source hash mismatch: {record['relative_path']}")

    paper_root = Path(project["source_roots"]["papers_wsl"])
    for record in csv_rows(PAPERS_MANIFEST):
        path = paper_root / record["filename"]
        row, passed = hash_row(
            dataset_id="HZO_LITERATURE_MATRIX_V1",
            source_id=f"paper:{record['id']}",
            source_path=path,
            expected_sha256=None,
            source_role=str(record["project_role"]),
            use_status="reference_only",
            scope="optional HZO literature; not IGZO T01 I-V input",
        )
        rows.append(row)
        if not passed:
            errors.append(f"paper source missing: {record['filename']}")

    return rows, errors


def build_parameter_rows(
    audit: dict[str, Any], project: dict[str, Any], tcad: dict[str, Any]
) -> tuple[list[dict[str, Any]], list[str]]:
    documents = {"project": project, "tcad": tcad}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for record in audit["parameters"]:
        source_document = str(record["source_document"])
        source_key = str(record["source_key"])
        try:
            source_value = dotted_value(documents[source_document], source_key)
        except (KeyError, ValueError) as error:
            errors.append(f"parameter source unavailable: {record['parameter_id']}: {error}")
            source_value = None
        source_matches = source_value == record["value"]
        if not source_matches:
            errors.append(
                f"parameter source mismatch: {record['parameter_id']} config={record['value']} source={source_value}"
            )
        if not isinstance(record["value"], (int, float)) or not str(record["unit"]).strip():
            errors.append(f"parameter lacks numeric value or unit: {record['parameter_id']}")
        rows.append(
            {
                "record_type": "parameter",
                "dataset_id": "IGZO_T01_TEACHING_BASELINE_V1",
                "record_id": record["parameter_id"],
                "symbol_or_field": record["symbol"],
                "value": record["value"],
                "unit": record["unit"],
                "layer_or_model": record["layer_or_model"],
                "source_type": record["source_type"],
                "source_reference": f"{SOURCE_DOCUMENT_FILES[source_document]}:{source_key}",
                "fitted_or_fixed": record["fitted_or_fixed"],
                "allowed_use": record["allowed_use"],
                "valid_range": record["valid_range"],
                "unit_basis": "source configuration value",
                "source_value_status": "PASS" if source_matches else "FAIL",
            }
        )
    return rows, errors


def build_data_field_rows(audit: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    declared_dataset_ids = {str(record["dataset_id"]) for record in audit["datasets"]}
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    for record in audit["data_field_units"]:
        if record["dataset_id"] not in declared_dataset_ids:
            errors.append(f"data field has undeclared dataset: {record['field_id']}")
        if not str(record["unit"]).strip():
            errors.append(f"data field lacks unit: {record['field_id']}")
        rows.append(
            {
                "record_type": "data_field",
                "dataset_id": record["dataset_id"],
                "record_id": record["field_id"],
                "symbol_or_field": f"{record['field_name']} -> {record['canonical_name']}",
                "value": "",
                "unit": record["unit"],
                "layer_or_model": "source_data_column",
                "source_type": "declared_source_column",
                "source_reference": record["source_reference"],
                "fitted_or_fixed": "not_fitted",
                "allowed_use": record["allowed_use"],
                "valid_range": "dataset-specific; see boundary table",
                "unit_basis": record["unit_basis"],
                "source_value_status": "DECLARED",
            }
        )
    return rows, errors


def build_dataset_rows(audit: dict[str, Any]) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    errors: list[str] = []
    seen: set[str] = set()
    for record in audit["datasets"]:
        dataset_id = str(record["dataset_id"])
        if dataset_id in seen:
            errors.append(f"duplicate dataset id: {dataset_id}")
        seen.add(dataset_id)
        missing = list(record["missing_fields"])
        rows.append(
            {
                "dataset_id": dataset_id,
                "material_scope": record["material_scope"],
                "source_type": record["source_type"],
                "use_status": record["use_status"],
                "evidence_level": record["evidence_level"],
                "allowed_uses": record["allowed_uses"],
                "prohibited_uses": record["prohibited_uses"],
                "metadata_status": record["metadata_status"],
                "missing_fields": ";".join(missing) if missing else "none",
            }
        )
        if record["material_scope"] == "n_type_IGZO_only" and record["use_status"] != "teaching_baseline":
            errors.append(f"active IGZO dataset has unexpected status: {dataset_id}")
    return rows, errors


def build_conflict_rows(audit: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "conflict_id": record["conflict_id"],
            "subject": record["subject"],
            "record_a": record["record_a"],
            "record_b": record["record_b"],
            "resolution": record["resolution"],
            "impact": record["impact"],
            "status": record["status"],
        }
        for record in audit["conflicts"]
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check-only", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    audit = load_json(AUDIT_CONFIG)
    project = load_json(PROJECT_CONFIG)
    tcad = load_json(TCAD_CONFIG)
    errors: list[str] = []
    if audit["project_id"] != project["project_id"]:
        errors.append("project ID mismatch")
    if audit["audit_id"] != "S00_DATA_UNIT_AUDIT_V1":
        errors.append("unexpected audit ID")

    source_rows, source_errors = collect_source_inventory(project)
    parameter_rows, parameter_errors = build_parameter_rows(audit, project, tcad)
    data_field_rows, data_field_errors = build_data_field_rows(audit)
    unit_rows = parameter_rows + data_field_rows
    dataset_rows, dataset_errors = build_dataset_rows(audit)
    conflict_rows = build_conflict_rows(audit)
    errors.extend(source_errors)
    errors.extend(parameter_errors)
    errors.extend(data_field_errors)
    errors.extend(dataset_errors)
    declared_dataset_ids = {str(record["dataset_id"]) for record in audit["datasets"]}
    unknown_source_datasets = sorted(
        {str(row["dataset_id"]) for row in source_rows} - declared_dataset_ids
    )
    if unknown_source_datasets:
        errors.append(f"source inventory has undeclared datasets: {unknown_source_datasets}")

    g0 = audit["g0_decision"]
    expected_g0 = "TEACHING_BASELINE_ONLY"
    if g0["status"] != expected_g0:
        errors.append(f"unexpected G0 decision: {g0['status']}")
    if not g0["t01_permitted"] or g0["quantitative_fitting_permitted"]:
        errors.append("G0 teaching-only policy is inconsistent")

    output_paths = {
        "source_inventory": OUTPUT_DIR / "source_inventory.csv",
        "unit_table": OUTPUT_DIR / "unit_table.csv",
        "dataset_boundary": OUTPUT_DIR / "dataset_boundary.csv",
        "conflict_register": OUTPUT_DIR / "conflict_register.csv",
        "report": REPORT_PATH,
    }
    report = {
        "status": "PASS" if not errors else "FAIL",
        "audit_id": audit["audit_id"],
        "project_id": project["project_id"],
        "source_inventory": {
            "records": len(source_rows),
            "hash_pass": sum(row["hash_status"] == "PASS" for row in source_rows),
            "hash_fail": sum(row["hash_status"] == "FAIL" for row in source_rows),
        },
        "unit_table": {
            "records": len(unit_rows),
            "parameter_records": len(parameter_rows),
            "data_field_records": len(data_field_rows),
            "units_complete": all(str(row["unit"]).strip() for row in unit_rows),
            "source_value_pass": sum(row["source_value_status"] == "PASS" for row in parameter_rows),
        },
        "dataset_boundary": {"records": len(dataset_rows)},
        "conflict_register": {
            "records": len(conflict_rows),
            "open_external_inputs": sum(row["status"] == "open_external_input" for row in conflict_rows),
        },
        "g0_decision": g0,
        "outputs": {name: str(path.relative_to(ROOT)) for name, path in output_paths.items()},
        "evidence_boundary": (
            "S00 verifies source identity, hashes, units, and scope separation. It does not create "
            "condition-complete experimental IGZO I-V data. T01 is permitted only as an E2 "
            "teaching-parameter simulation until the listed primary data fields are supplied."
        ),
        "errors": errors,
    }

    if not args.check_only:
        write_csv(
            output_paths["source_inventory"],
            source_rows,
            [
                "dataset_id", "source_id", "source_path", "source_role", "use_status", "scope",
                "bytes", "sha256", "expected_sha256", "hash_status",
            ],
        )
        write_csv(
            output_paths["unit_table"],
            unit_rows,
            [
                "record_type", "dataset_id", "record_id", "symbol_or_field", "value", "unit",
                "layer_or_model", "source_type", "source_reference", "fitted_or_fixed", "allowed_use",
                "valid_range", "unit_basis", "source_value_status",
            ],
        )
        write_csv(
            output_paths["dataset_boundary"],
            dataset_rows,
            [
                "dataset_id", "material_scope", "source_type", "use_status", "evidence_level",
                "allowed_uses", "prohibited_uses", "metadata_status", "missing_fields",
            ],
        )
        write_csv(
            output_paths["conflict_register"],
            conflict_rows,
            ["conflict_id", "subject", "record_a", "record_b", "resolution", "impact", "status"],
        )
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    label = "PASS" if not errors else "FAIL"
    print(
        f"S00_AUDIT_{label} sources={len(source_rows)} parameters={len(parameter_rows)} "
        f"fields={len(data_field_rows)} datasets={len(dataset_rows)} conflicts={len(conflict_rows)} "
        f"g0={g0['status']}"
    )
    if errors:
        for error in errors:
            print(f"S00_AUDIT_ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
