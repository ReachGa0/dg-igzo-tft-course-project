#!/usr/bin/env python3
"""Check the planning scaffold and frozen baseline for consistency."""

from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
REPORT_PATH = ROOT / "results" / "reports" / "project_check.json"

REQUIRED_FILES = [
    "AGENTS.md",
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    "README.md",
    "ARCHITECTURE.md",
    "AI_CONTEXT.md",
    "AI_LOG.md",
    "PROJECT_PLAN.md",
    "DECISIONS.md",
    "STATUS.md",
    "Makefile",
    "config/project.json",
    "config/experiments.json",
    "config/tcad_baseline.json",
    "references/papers_manifest.csv",
    "references/senior_work_manifest.csv",
    "docs/01_\u9009\u9898\u8bba\u8bc1\u4e0e\u521b\u65b0\u70b9.md",
    "docs/02_\u6587\u732e\u8c03\u7814\u77e9\u9635.md",
    "docs/03_\u96c6\u6210\u7535\u8def\u8bbe\u8ba1\u5168\u6d41\u7a0b.md",
    "docs/04_\u57fa\u7840\u77e5\u8bc6\u901f\u67e5.md",
    "docs/05_\u9a8c\u8bc1\u4e0e\u9a8c\u6536\u6807\u51c6.md",
    "docs/06_\u660e\u65e5\u6c47\u62a5\u7a3f.md",
    "docs/07_PPT\u4e0e\u62a5\u544a\u63d0\u7eb2.md",
    "docs/08_\u98ce\u9669\u4e0e\u964d\u7ea7\u7b56\u7565.md",
    "docs/09_\u77e5\u8bc6\u70b9\u8be6\u89e3\u4e0e\u5b9e\u9a8c\u8bbe\u8ba1\u539f\u7406.md",
    "docs/10_\u5b66\u957f\u8d44\u6599\u5bf9\u7167\u4e0e\u6570\u636e\u7ee7\u627f\u8bf4\u660e.md",
    "docs/11_\u4e8c\u7ef4TCAD\u5b9e\u65bd\u8def\u7ebf.md",
    "docs/12_\u8bfe\u7a0b\u8981\u6c42\u6620\u5c04\u4e0e\u5b8c\u6574\u5b9e\u9a8c\u77e9\u9635.md",
    "scripts/import_senior_reference.py",
    "scripts/build_self_contained_report.py",
    "tcad/README.md",
    "tcad/run_dg_electrostatic.py",
    "report/src/\u5b9e\u9a8c\u62a5\u544a_\u8349\u7a3f.xhtml",
    "report/evidence_matrix.csv",
    "models/level61/README.md",
    "spice/models/README.md",
    "spice/netlists/devices/README.md",
    "spice/netlists/cells/README.md",
    "spice/netlists/blocks/README.md",
    "pdk/tech/README.md",
    "pdk/tech/layers.csv",
    "pdk/drc/README.md",
]

REQUIRED_DIRS = [
    "config",
    "docs",
    "references",
    "data/raw",
    "data/processed",
    "data/raw/senior_reference",
    "data/processed/senior_reference",
    "models/level61",
    "models/dual_gate",
    "models/ferroelectric",
    "spice/models",
    "spice/netlists/devices",
    "spice/netlists/cells",
    "spice/netlists/blocks",
    "pdk/tech",
    "pdk/drc",
    "pdk/lvs",
    "pdk/pcells",
    "layout/cells",
    "layout/blocks",
    "layout/gds",
    "verification/drc",
    "verification/lvs",
    "verification/simulation",
    "scripts",
    "tests",
    "results/figures",
    "results/tables",
    "results/reports",
    "results/tcad/dg_electrostatic",
    "tcad/structures",
    "tcad/physics",
    "tcad/tests",
    "ppt",
    "report",
    "report/src",
    "report/assets",
    "report/final",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def add_check(checks: list[dict[str, object]], name: str, passed: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})


def main() -> int:
    checks: list[dict[str, object]] = []

    for relative in REQUIRED_DIRS:
        path = ROOT / relative
        add_check(checks, f"directory:{relative}", path.is_dir(), str(path))

    for relative in REQUIRED_FILES:
        path = ROOT / relative
        valid = path.is_file() and path.stat().st_size > 0
        add_check(checks, f"file:{relative}", valid, f"bytes={path.stat().st_size if path.exists() else 0}")

    try:
        agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        required_markers = {
            "DG-IGZO-TFT-PDK",
            "git status --short --branch",
            "make check",
            "AI_LOG.md",
            "STATUS.md",
            "不得称为原生 HSPICE Level 61",
        }
        add_check(
            checks,
            "handoff:agents_contract",
            all(marker in agents_text for marker in required_markers),
            f"markers={sum(marker in agents_text for marker in required_markers)}/{len(required_markers)}",
        )
        claude_text = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
        copilot_text = (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
        add_check(checks, "handoff:claude_pointer", "AGENTS.md" in claude_text, "points to AGENTS.md")
        add_check(checks, "handoff:copilot_pointer", "AGENTS.md" in copilot_text, "points to AGENTS.md")
    except Exception as error:  # noqa: BLE001
        add_check(checks, "handoff:agent_entries", False, str(error))

    config_path = ROOT / "config" / "project.json"
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        add_check(checks, "config:json", True, config["project_id"])
    except Exception as error:  # noqa: BLE001 - report all configuration failures
        add_check(checks, "config:json", False, str(error))
        config = {}

    if config:
        deadlines = config.get("deadlines", {})
        try:
            briefing = date.fromisoformat(deadlines["teacher_briefing"])
            ppt = date.fromisoformat(deadlines["ppt"])
            report = date.fromisoformat(deadlines["report"])
            add_check(
                checks,
                "config:deadline_order",
                briefing < ppt < report,
                f"{briefing} < {ppt} < {report}",
            )
        except Exception as error:  # noqa: BLE001
            add_check(checks, "config:deadline_order", False, str(error))

        required_counts = {"INV": 2, "NAND2": 3, "NOR2": 3, "XOR2": 12, "RING5": 10, "FULL_ADDER_1BIT": 33}
        add_check(
            checks,
            "config:device_counts",
            config.get("required_cells") == required_counts,
            json.dumps(config.get("required_cells"), sort_keys=True),
        )
        device_keys = set(config.get("baseline_devices", {}))
        add_check(
            checks,
            "config:igzo_only_devices",
            device_keys == {"IGZO_TFT"},
            ",".join(sorted(device_keys)),
        )
        logic_style = config.get("logic_style", {})
        add_check(
            checks,
            "config:active_load_logic",
            logic_style.get("primary") == "dual_gate_igzo_active_load",
            str(logic_style.get("primary")),
        )

        for key in ("papers_wsl", "ngspice", "aimspice", "klayout_pdk", "senior_reference"):
            source = Path(config["source_roots"][key])
            add_check(checks, f"source:{key}", source.is_dir(), str(source))
        requirements = Path(config["source_roots"]["teacher_requirements"])
        add_check(checks, "source:teacher_requirements", requirements.is_file(), str(requirements))

        course_requirements = config.get("course_requirements", {})
        add_check(
            checks,
            "config:final_report_format",
            course_requirements.get("final_report_format") == "single_self_contained_html",
            str(course_requirements.get("final_report_format")),
        )
        add_check(
            checks,
            "config:parameter_groups_minimum",
            int(course_requirements.get("minimum_parameter_groups", 0)) >= 5,
            str(course_requirements.get("minimum_parameter_groups")),
        )

    papers_path = ROOT / "references" / "papers_manifest.csv"
    try:
        with papers_path.open("r", encoding="utf-8-sig", newline="") as stream:
            papers = list(csv.DictReader(stream))
        unique_files = {row["filename"] for row in papers}
        source_root = Path(config["source_roots"]["papers_wsl"])
        all_exist = all((source_root / row["filename"]).is_file() for row in papers)
        dois_present = all(row["doi"].startswith("10.") for row in papers)
        add_check(checks, "papers:count", len(papers) == 13, f"rows={len(papers)}")
        add_check(checks, "papers:unique", len(unique_files) == 13, f"unique={len(unique_files)}")
        add_check(checks, "papers:sources", all_exist, str(source_root))
        add_check(checks, "papers:doi", dois_present, "all 13 DOI fields populated")
    except Exception as error:  # noqa: BLE001
        add_check(checks, "papers:manifest", False, str(error))

    baseline_manifest_path = ROOT / "data" / "raw" / "baseline" / "manifest.json"
    try:
        baseline = json.loads(baseline_manifest_path.read_text(encoding="utf-8"))
        records = baseline["files"]
        valid_records = True
        for record in records:
            destination = ROOT / record["destination"]
            if (
                not destination.is_file()
                or destination.stat().st_size != record["bytes"]
                or sha256(destination) != record["sha256"]
            ):
                valid_records = False
                break
        expected_destinations = {
            "data/raw/baseline/ngspice/spice/netlists/igzo_transfer.cir",
            "data/raw/baseline/ngspice/spice/netlists/igzo_output.cir",
            "data/raw/baseline/ngspice/data/igzo_transfer.csv",
            "data/raw/baseline/ngspice/data/igzo_output.csv",
            "data/raw/baseline/aimspice/01_igzo_transfer.cir",
            "data/raw/baseline/aimspice/02_igzo_output.cir",
            "data/raw/baseline/klayout_pdk/layouts/igzo_tft_W60_L10.gds",
        }
        destinations = {record["destination"] for record in records}
        add_check(checks, "baseline:manifest", len(records) == 7, f"files={len(records)}")
        add_check(checks, "baseline:hashes", valid_records, "all imported files match manifest")
        add_check(
            checks,
            "baseline:igzo_only_selection",
            destinations == expected_destinations,
            f"destinations={len(destinations)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "baseline:manifest", False, str(error))

    experiments_path = ROOT / "config" / "experiments.json"
    try:
        experiments = json.loads(experiments_path.read_text(encoding="utf-8"))
        parameter_groups = experiments["parameter_groups"]
        group_ids = [group["id"] for group in parameter_groups]
        experiment_ids = [experiment["id"] for experiment in experiments["experiments"]]
        add_check(
            checks,
            "experiments:parameter_groups",
            len(parameter_groups) >= 5 and len(set(group_ids)) == len(group_ids),
            f"groups={len(parameter_groups)}",
        )
        add_check(
            checks,
            "experiments:ids_unique",
            len(experiment_ids) == len(set(experiment_ids)),
            f"experiments={len(experiment_ids)}",
        )
        expected_experiment_ids = {
            "S00", "T00", "T01", "T02", "T03", "M00", "M01", "C00", "C01",
            "C02", "C03", "L00", "V00", "V01", "PEX0", "FE0", "R00",
        }
        add_check(
            checks,
            "experiments:complete_stage_set",
            set(experiment_ids) == expected_experiment_ids,
            f"stages={len(experiment_ids)}",
        )
        add_check(
            checks,
            "experiments:project_id",
            experiments.get("project_id") == config.get("project_id"),
            str(experiments.get("project_id")),
        )
        experiment_map = {item["id"]: item for item in experiments["experiments"]}
        dependencies_valid = all(
            set(item.get("depends_on", [])) <= set(experiment_map)
            for item in experiments["experiments"]
        )
        add_check(
            checks,
            "experiments:dependencies_exist",
            dependencies_valid,
            "all dependencies reference known stages",
        )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(experiment_id: str) -> bool:
            if experiment_id in visiting:
                return False
            if experiment_id in visited:
                return True
            visiting.add(experiment_id)
            valid = all(visit(dependency) for dependency in experiment_map[experiment_id].get("depends_on", []))
            visiting.remove(experiment_id)
            visited.add(experiment_id)
            return valid

        dependencies_acyclic = dependencies_valid and all(visit(item) for item in experiment_map)
        add_check(
            checks,
            "experiments:dependency_dag",
            dependencies_acyclic,
            "dependency graph is acyclic",
        )
        sensitivity = next(item for item in experiments["experiments"] if item["id"] == "T03")
        add_check(
            checks,
            "experiments:high_difficulty_five_groups",
            len(sensitivity["parameter_group_ids"]) >= 5,
            ",".join(sensitivity["parameter_group_ids"]),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "experiments:json", False, str(error))

    senior_manifest_path = ROOT / "data" / "raw" / "senior_reference" / "manifest.json"
    try:
        senior_manifest = json.loads(senior_manifest_path.read_text(encoding="utf-8"))
        senior_records = senior_manifest["files"]
        valid_sources = all(
            Path(record["source_path"]).is_file()
            and Path(record["source_path"]).stat().st_size == record["bytes"]
            and sha256(Path(record["source_path"])) == record["sha256"]
            for record in senior_records
        )
        add_check(checks, "senior:manifest", len(senior_records) >= 15, f"files={len(senior_records)}")
        add_check(checks, "senior:source_hashes", valid_sources, "all referenced source files match")
    except Exception as error:  # noqa: BLE001
        add_check(checks, "senior:manifest", False, str(error))

    senior_csv_specs = {
        "data/processed/senior_reference/inverter_vtc_reference.csv": {
            "minimum_rows": 181,
            "columns": {"vin_v", "vout_case_1_v", "vout_case_2_v", "condition_status"},
        },
        "data/processed/senior_reference/igzo_tcad_transfer_reference.csv": {
            "minimum_rows": 123,
            "columns": {"v_gate_v", "drain_current_a", "quality_flag", "condition_status"},
        },
    }
    for relative, specification in senior_csv_specs.items():
        try:
            with (ROOT / relative).open("r", encoding="utf-8", newline="") as stream:
                rows = list(csv.DictReader(stream))
            columns = set(rows[0]) if rows else set()
            valid = len(rows) >= specification["minimum_rows"] and specification["columns"] <= columns
            add_check(checks, f"senior_csv:{Path(relative).name}", valid, f"rows={len(rows)}")
        except Exception as error:  # noqa: BLE001
            add_check(checks, f"senior_csv:{Path(relative).name}", False, str(error))

    tcad_config_path = ROOT / "config" / "tcad_baseline.json"
    try:
        tcad_config = json.loads(tcad_config_path.read_text(encoding="utf-8"))
        mesh_levels = tcad_config["mesh_levels"]
        add_check(
            checks,
            "tcad:mesh_levels",
            {"coarse", "fine"} <= set(mesh_levels),
            ",".join(mesh_levels),
        )
        add_check(
            checks,
            "tcad:evidence_boundary",
            "No mobile charge" in tcad_config["evidence_boundary"],
            tcad_config["evidence_boundary"],
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "tcad:config", False, str(error))

    tcad_report_path = ROOT / "results" / "reports" / "tcad_dg_electrostatic.json"
    try:
        tcad_report = json.loads(tcad_report_path.read_text(encoding="utf-8"))
        output_files = [ROOT / value for key, value in tcad_report["outputs"].items() if key != "vtk_directory"]
        outputs_exist = all(path.is_file() and path.stat().st_size > 0 for path in output_files)
        add_check(checks, "tcad:smoke_status", tcad_report["status"] == "PASS", tcad_report["status"])
        add_check(checks, "tcad:smoke_outputs", outputs_exist, f"files={len(output_files)}")
    except Exception as error:  # noqa: BLE001
        add_check(checks, "tcad:smoke_report", False, str(error))

    report_template_path = ROOT / "report" / "src" / "\u5b9e\u9a8c\u62a5\u544a_\u8349\u7a3f.xhtml"
    try:
        report_text = report_template_path.read_text(encoding="utf-8")
        report_root = ET.fromstring(report_text)
        namespace = {"h": "http://www.w3.org/1999/xhtml"}
        section_ids = [node.attrib.get("id", "") for node in report_root.findall(".//h:section", namespace)]
        required_sections = {f"section-{index:02d}" for index in range(1, 13)}
        add_check(
            checks,
            "report:required_sections",
            required_sections <= set(section_ids),
            f"main_sections={len(required_sections & set(section_ids))}",
        )
        forbidden_images = re.findall(
            r'<img[^>]+src=["\'](?:https?://|file://|[A-Za-z]:[\\/]|/)', report_text, re.IGNORECASE
        )
        add_check(checks, "report:no_forbidden_image_sources", not forbidden_images, f"count={len(forbidden_images)}")
        add_check(
            checks,
            "report:placeholder_guard",
            "[\u5f85\u586b\u5199" in report_text,
            "draft intentionally remains non-final until placeholders are resolved",
        )
        add_check(
            checks,
            "report:current_scope_title",
            "双栅 IGZO" in report_text and "单极性逻辑" in report_text,
            "report title and theory placeholder use current scope",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "report:template", False, str(error))

    failures = [check for check in checks if check["status"] == "FAIL"]
    report = {
        "project": config.get("project_id", "UNKNOWN"),
        "status": "PASS" if not failures else "FAIL",
        "checks": len(checks),
        "failures": len(failures),
        "results": checks,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    if failures:
        for failure in failures:
            print(f"FAIL {failure['name']}: {failure['detail']}", file=sys.stderr)
        print(f"PROJECT_CHECK_FAIL failures={len(failures)} report={REPORT_PATH}", file=sys.stderr)
        return 1

    print(f"PROJECT_CHECK_PASS checks={len(checks)} report={REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
