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
    "config/s00_data_audit.json",
    "config/tcad_baseline.json",
    "config/tcad_t01_baseline.json",
    "config/tcad_t01_b_smoke.json",
    "config/tcad_t01_c_transfer.json",
    "config/tcad_t01_d_mesh_refinement.json",
    "config/tcad_t01_d_idvd.json",
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
    "scripts/audit_s00_data.py",
    "scripts/check_t01_a_contract.py",
    "scripts/check_t01_b_smoke.py",
    "scripts/check_t01_c_transfer.py",
    "scripts/check_t01_d_mesh_refinement.py",
    "scripts/check_t01_d_idvd.py",
    "scripts/build_self_contained_report.py",
    "tcad/README.md",
    "tcad/run_dg_electrostatic.py",
    "tcad/run_t01_single_gate_smoke.py",
    "tcad/run_t01_single_gate_transfer.py",
    "tcad/run_t01_single_gate_mesh_refinement.py",
    "tcad/run_t01_single_gate_idvd.py",
    "report/manifest.json",
    "report/src/\u5b9e\u9a8c\u62a5\u544a_\u8349\u7a3f.xhtml",
    "report/evidence_matrix.csv",
    "data/processed/s00/source_inventory.csv",
    "data/processed/s00/unit_table.csv",
    "data/processed/s00/dataset_boundary.csv",
    "data/processed/s00/conflict_register.csv",
    "results/reports/s00_data_audit.json",
    "results/reports/tcad_t01_input_contract.json",
    "results/reports/tcad_t01_b_smoke.json",
    "results/reports/tcad_t01_b_smoke_check.json",
    "results/tables/tcad_t01_b_bias_points.csv",
    "results/tables/tcad_t01_b_mesh_summary.csv",
    "results/reports/tcad_t01_c_transfer.json",
    "results/reports/tcad_t01_c_transfer_check.json",
    "results/tables/tcad_t01_c_idvg.csv",
    "results/tables/tcad_t01_c_mesh_comparison.csv",
    "results/tcad/t01_single_gate/t01_c_transfer/state_manifest.json",
    "results/reports/tcad_t01_d_mesh_refinement.json",
    "results/reports/tcad_t01_d_mesh_refinement_check.json",
    "results/tables/tcad_t01_d_mesh_bias_points.csv",
    "results/tables/tcad_t01_d_mesh_summary.csv",
    "results/tables/tcad_t01_d_mesh_comparison.csv",
    "results/tables/tcad_t01_d_t01_c_reproduction.csv",
    "results/tcad/t01_single_gate/t01_d_mesh_refinement/state_manifest.json",
    "results/reports/tcad_t01_d_idvd.json",
    "results/reports/tcad_t01_d_idvd_check.json",
    "results/tables/tcad_t01_d_idvd_points.csv",
    "results/tables/tcad_t01_d_idvd_curve_metrics.csv",
    "results/tables/tcad_t01_d_idvd_mesh_summary.csv",
    "results/tables/tcad_t01_d_idvd_mesh_comparison.csv",
    "results/tables/tcad_t01_d_idvd_da_reproduction.csv",
    "report/assets/tcad_t01_d_idvd.png",
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
    "results/tcad/t01_single_gate/t01_b_smoke",
    "results/tcad/t01_single_gate/t01_c_transfer",
    "results/tcad/t01_single_gate/t01_d_mesh_refinement",
    "results/tcad/t01_single_gate/t01_d_idvd",
    "tcad/structures",
    "tcad/physics",
    "tcad/tests",
    "ppt",
    "report",
    "report/src",
    "report/chapters",
    "report/appendices",
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
        teaching_baseline = config.get("teaching_baseline", {})
        add_check(
            checks,
            "config:teaching_baseline",
            teaching_baseline.get("mobility_cm2_vs") == 35.5
            and teaching_baseline.get("vth_v") == 0.21
            and teaching_baseline.get("evidence_level") == "E1",
            json.dumps(teaching_baseline, sort_keys=True),
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
            "config:report_authoring_mode",
            course_requirements.get("report_authoring_mode") == "chapter_sources",
            str(course_requirements.get("report_authoring_mode")),
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

    s00_report_path = ROOT / "results" / "reports" / "s00_data_audit.json"
    try:
        s00_config = json.loads((ROOT / "config" / "s00_data_audit.json").read_text(encoding="utf-8"))
        s00_report = json.loads(s00_report_path.read_text(encoding="utf-8"))
        source_inventory_path = ROOT / "data" / "processed" / "s00" / "source_inventory.csv"
        unit_table_path = ROOT / "data" / "processed" / "s00" / "unit_table.csv"
        boundary_path = ROOT / "data" / "processed" / "s00" / "dataset_boundary.csv"
        conflict_path = ROOT / "data" / "processed" / "s00" / "conflict_register.csv"
        with source_inventory_path.open("r", encoding="utf-8", newline="") as stream:
            source_inventory = list(csv.DictReader(stream))
        with unit_table_path.open("r", encoding="utf-8", newline="") as stream:
            unit_rows = list(csv.DictReader(stream))
        with boundary_path.open("r", encoding="utf-8", newline="") as stream:
            boundary_rows = list(csv.DictReader(stream))
        with conflict_path.open("r", encoding="utf-8", newline="") as stream:
            conflict_rows = list(csv.DictReader(stream))
        add_check(
            checks,
            "s00:audit_config",
            s00_config.get("project_id") == config.get("project_id")
            and s00_config.get("audit_id") == "S00_DATA_UNIT_AUDIT_V1",
            str(s00_config.get("audit_id")),
        )
        add_check(
            checks,
            "s00:source_inventory_hashes",
            bool(source_inventory)
            and all(
                row.get("hash_status") == "PASS"
                and Path(row.get("source_path", "")).is_file()
                and sha256(Path(row["source_path"])) == row.get("sha256")
                for row in source_inventory
            ),
            f"records={len(source_inventory)}",
        )
        add_check(
            checks,
            "s00:unit_table",
            bool(unit_rows)
            and all(row.get("unit", "").strip() for row in unit_rows)
            and all(
                row.get("source_value_status") in {"PASS", "DECLARED"}
                for row in unit_rows
            )
            and s00_report.get("unit_table", {}).get("source_value_pass")
            == s00_report.get("unit_table", {}).get("parameter_records"),
            f"records={len(unit_rows)}",
        )
        add_check(
            checks,
            "s00:scope_registers",
            len(boundary_rows) == len(s00_config.get("datasets", []))
            and len(conflict_rows) == len(s00_config.get("conflicts", [])),
            f"datasets={len(boundary_rows)} conflicts={len(conflict_rows)}",
        )
        g0 = s00_report.get("g0_decision", {})
        add_check(
            checks,
            "s00:teaching_only_gate",
            g0.get("status") == "TEACHING_BASELINE_ONLY"
            and g0.get("t01_permitted") is True
            and g0.get("quantitative_fitting_permitted") is False,
            str(g0.get("status")),
        )
        add_check(
            checks,
            "s00:audit_report",
            s00_report.get("status") == "PASS"
            and s00_report.get("source_inventory", {}).get("hash_fail") == 0,
            str(s00_report.get("status")),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "s00:audit", False, str(error))

    t01_contract_path = ROOT / "results" / "reports" / "tcad_t01_input_contract.json"
    try:
        t01_config = json.loads((ROOT / "config" / "tcad_t01_baseline.json").read_text(encoding="utf-8"))
        t01_report = json.loads(t01_contract_path.read_text(encoding="utf-8"))
        add_check(
            checks,
            "t01_a:contract_status",
            t01_report.get("status") == "PASS"
            and t01_report.get("stage") == "T01-A"
            and t01_report.get("case_id") == t01_config.get("case_id"),
            str(t01_report.get("status")),
        )
        add_check(
            checks,
            "t01_a:simulation_not_run",
            t01_config.get("execution_boundary", {}).get("simulation_run") is False
            and t01_config.get("execution_boundary", {}).get("simulation_status") == "NOT_RUN"
            and t01_report.get("simulation_run") is False
            and t01_report.get("simulation_status") == "NOT_RUN",
            str(t01_report.get("simulation_status")),
        )
        add_check(
            checks,
            "t01_a:single_gate_contract",
            t01_config.get("device", {}).get("single_gate") is True
            and t01_config.get("device", {}).get("top_gate_present") is False
            and t01_config.get("device", {}).get("top_oxide_present") is False
            and t01_config.get("physics", {}).get("equations", {}).get("drift_diffusion") == "electron_only",
            "single gate, electron-only transport",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t01_a:contract", False, str(error))

    t01_b_report_path = ROOT / "results" / "reports" / "tcad_t01_b_smoke.json"
    t01_b_check_path = ROOT / "results" / "reports" / "tcad_t01_b_smoke_check.json"
    try:
        t01_b_config = json.loads((ROOT / "config" / "tcad_t01_b_smoke.json").read_text(encoding="utf-8"))
        t01_b_report = json.loads(t01_b_report_path.read_text(encoding="utf-8"))
        t01_b_check = json.loads(t01_b_check_path.read_text(encoding="utf-8"))
        t01_b_checks = t01_b_report.get("checks", {})
        add_check(
            checks,
            "t01_b:smoke_status",
            t01_b_report.get("status") == "PASS"
            and t01_b_report.get("case_id") == t01_b_config.get("case_id")
            and t01_b_report.get("stage") == "T01-B"
            and t01_b_report.get("evidence_level") == "E2",
            str(t01_b_report.get("status")),
        )
        add_check(
            checks,
            "t01_b:independent_check",
            t01_b_check.get("status") == "PASS"
            and t01_b_check.get("case_id") == t01_b_config.get("case_id")
            and t01_b_check.get("stage") == "T01-B",
            str(t01_b_check.get("status")),
        )
        add_check(
            checks,
            "t01_b:authorized_scope",
            t01_b_report.get("executed_bias_stage_ids") == ["T01_A_STAGE_0", "T01_A_STAGE_1"]
            and t01_b_config.get("scope", {}).get("allowed_bias_stage_ids") == ["T01_A_STAGE_0", "T01_A_STAGE_1"],
            str(t01_b_report.get("executed_bias_stage_ids")),
        )
        add_check(
            checks,
            "t01_b:acceptance_checks",
            bool(t01_b_checks) and all(result.get("status") == "PASS" for result in t01_b_checks.values()),
            f"checks={len(t01_b_checks)}",
        )
        output_paths = [
            ROOT / value
            for key, value in t01_b_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        state_paths = [ROOT / item["state_csv"] for item in t01_b_report.get("mesh", [])]
        run_directory = ROOT / t01_b_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t01_b:raw_outputs",
            all(path.is_file() and path.stat().st_size > 0 for path in output_paths + state_paths)
            and run_directory.is_dir()
            and any(run_directory.glob("*.vtm")),
            f"files={len(output_paths) + len(state_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t01_b:smoke", False, str(error))

    t01_c_report_path = ROOT / "results" / "reports" / "tcad_t01_c_transfer.json"
    t01_c_check_path = ROOT / "results" / "reports" / "tcad_t01_c_transfer_check.json"
    try:
        t01_c_config = json.loads(
            (ROOT / "config" / "tcad_t01_c_transfer.json").read_text(encoding="utf-8")
        )
        t01_c_report = json.loads(t01_c_report_path.read_text(encoding="utf-8"))
        t01_c_check = json.loads(t01_c_check_path.read_text(encoding="utf-8"))
        t01_c_checks = t01_c_report.get("checks", {})
        add_check(
            checks,
            "t01_c:transfer_status",
            t01_c_report.get("status") == "PASS"
            and t01_c_report.get("case_id") == t01_c_config.get("case_id")
            and t01_c_report.get("stage") == "T01-C"
            and t01_c_report.get("evidence_level") == "E2",
            str(t01_c_report.get("status")),
        )
        add_check(
            checks,
            "t01_c:independent_check",
            t01_c_check.get("status") == "PASS"
            and t01_c_check.get("case_id") == t01_c_config.get("case_id")
            and t01_c_check.get("stage") == "T01-C",
            str(t01_c_check.get("status")),
        )
        add_check(
            checks,
            "t01_c:authorized_scope",
            t01_c_report.get("executed_bias_stage_ids")
            == ["T01_A_STAGE_0", "T01_A_STAGE_1", "T01_A_STAGE_2"]
            and t01_c_report.get("reported_bias_stage_id") == "T01_A_STAGE_2",
            str(t01_c_report.get("executed_bias_stage_ids")),
        )
        add_check(
            checks,
            "t01_c:acceptance_checks",
            bool(t01_c_checks)
            and all(result.get("status") == "PASS" for result in t01_c_checks.values()),
            f"checks={len(t01_c_checks)}",
        )
        warning_threshold = t01_c_config.get("acceptance", {}).get(
            "mesh_relative_current_difference_warning_threshold"
        )
        log_limit = t01_c_config.get("acceptance", {}).get(
            "maximum_log10_mesh_current_difference_decades"
        )
        mesh_sensitivity = t01_c_report.get("mesh_sensitivity", {})
        add_check(
            checks,
            "t01_c:mesh_warning_boundary",
            t01_c_report.get("maximum_relative_mesh_current_difference", 0.0)
            > warning_threshold
            and t01_c_report.get("maximum_log10_mesh_current_difference_decades", float("inf"))
            <= log_limit
            and mesh_sensitivity.get("status") == "WARNING"
            and mesh_sensitivity.get("quantitative_absolute_current_use_permitted") is False,
            (
                f"relative={t01_c_report.get('maximum_relative_mesh_current_difference')} "
                f"log_decades={t01_c_report.get('maximum_log10_mesh_current_difference_decades')}"
            ),
        )
        output_paths = [
            ROOT / value
            for key, value in t01_c_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        state_manifest = json.loads(
            (ROOT / t01_c_report["outputs"]["state_manifest"]).read_text(encoding="utf-8")
        )
        state_paths = [ROOT / entry["state_csv"] for entry in state_manifest.get("entries", [])]
        vtk_paths = [
            ROOT / f"{entry['vtk_base']}.vtm"
            for entry in state_manifest.get("entries", [])
            if entry.get("vtk_base")
        ]
        run_directory = ROOT / t01_c_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t01_c:raw_outputs",
            all(path.is_file() and path.stat().st_size > 0 for path in output_paths + state_paths + vtk_paths)
            and len(state_paths) == 16
            and len(vtk_paths) == 6
            and run_directory.is_dir(),
            f"files={len(output_paths) + len(state_paths) + len(vtk_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t01_c:transfer", False, str(error))

    t01_d_report_path = ROOT / "results" / "reports" / "tcad_t01_d_mesh_refinement.json"
    t01_d_check_path = ROOT / "results" / "reports" / "tcad_t01_d_mesh_refinement_check.json"
    try:
        t01_d_config = json.loads(
            (ROOT / "config" / "tcad_t01_d_mesh_refinement.json").read_text(
                encoding="utf-8"
            )
        )
        t01_d_report = json.loads(t01_d_report_path.read_text(encoding="utf-8"))
        t01_d_check = json.loads(t01_d_check_path.read_text(encoding="utf-8"))
        t01_d_checks = t01_d_report.get("checks", {})
        add_check(
            checks,
            "t01_d_a:mesh_refinement_status",
            t01_d_report.get("status") == "PASS"
            and t01_d_report.get("case_id") == t01_d_config.get("case_id")
            and t01_d_report.get("stage") == "T01-D-A"
            and t01_d_report.get("evidence_level") == "E2",
            str(t01_d_report.get("status")),
        )
        add_check(
            checks,
            "t01_d_a:independent_check",
            t01_d_check.get("status") == "PASS"
            and t01_d_check.get("case_id") == t01_d_config.get("case_id")
            and t01_d_check.get("stage") == "T01-D-A",
            str(t01_d_check.get("status")),
        )
        mesh_convergence = t01_d_report.get("mesh_convergence", {})
        current_limit = t01_d_config["acceptance"][
            "maximum_finest_pair_relative_current_difference"
        ]
        potential_limit = t01_d_config["acceptance"][
            "maximum_finest_pair_center_potential_difference_v"
        ]
        add_check(
            checks,
            "t01_d_a:limited_mesh_convergence_gate",
            mesh_convergence.get("status") == "PASS"
            and mesh_convergence.get("pair")
            == t01_d_config["mesh_ladder"]["convergence_pair"]
            and mesh_convergence.get("maximum_relative_current_difference", float("inf"))
            <= current_limit
            and mesh_convergence.get(
                "maximum_center_channel_potential_difference_v", float("inf")
            )
            <= potential_limit
            and mesh_convergence.get(
                "numerical_low_vds_positive_bias_absolute_current_converged"
            )
            is True
            and mesh_convergence.get("experimental_quantitative_use_permitted") is False
            and mesh_convergence.get("idvd_stage_permitted_next") is True,
            (
                f"current={mesh_convergence.get('maximum_relative_current_difference')} "
                f"potential={mesh_convergence.get('maximum_center_channel_potential_difference_v')}"
            ),
        )
        reproduction_rows = t01_d_report.get("t01_c_fine_reproduction", [])
        node_counts = [
            int(row["node_count_with_interface_duplicates"])
            for row in t01_d_report.get("mesh", [])
        ]
        add_check(
            checks,
            "t01_d_a:baseline_reproduction_and_node_growth",
            len(reproduction_rows) == 3
            and max(float(row["relative_current_difference"]) for row in reproduction_rows)
            <= t01_d_config["acceptance"][
                "maximum_t01_c_fine_reproduction_relative_current_difference"
            ]
            and len(node_counts) == 4
            and all(higher > lower for lower, higher in zip(node_counts, node_counts[1:])),
            f"reproduction_rows={len(reproduction_rows)} node_counts={node_counts}",
        )
        add_check(
            checks,
            "t01_d_a:acceptance_checks",
            bool(t01_d_checks)
            and all(result.get("status") == "PASS" for result in t01_d_checks.values()),
            f"checks={len(t01_d_checks)}",
        )
        output_paths = [
            ROOT / value
            for key, value in t01_d_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        state_manifest = json.loads(
            (ROOT / t01_d_report["outputs"]["state_manifest"]).read_text(encoding="utf-8")
        )
        state_paths = [ROOT / entry["state_csv"] for entry in state_manifest.get("entries", [])]
        vtk_paths = [
            ROOT / item["path"]
            for entry in state_manifest.get("entries", [])
            for item in entry.get("vtk_files", [])
        ]
        run_directory = ROOT / t01_d_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t01_d_a:raw_outputs",
            all(
                path.is_file() and path.stat().st_size > 0
                for path in output_paths + state_paths + vtk_paths
            )
            and len(state_paths) == 4
            and len(vtk_paths) >= 4
            and run_directory.is_dir(),
            f"files={len(output_paths) + len(state_paths) + len(vtk_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t01_d_a:mesh_refinement", False, str(error))

    t01_db_report_path = ROOT / "results" / "reports" / "tcad_t01_d_idvd.json"
    t01_db_check_path = ROOT / "results" / "reports" / "tcad_t01_d_idvd_check.json"
    try:
        t01_db_config = json.loads(
            (ROOT / "config" / "tcad_t01_d_idvd.json").read_text(encoding="utf-8")
        )
        t01_db_report = json.loads(t01_db_report_path.read_text(encoding="utf-8"))
        t01_db_check = json.loads(t01_db_check_path.read_text(encoding="utf-8"))
        add_check(
            checks,
            "t01_d_b:idvd_status",
            t01_db_report.get("status") == "PASS"
            and t01_db_report.get("case_id") == t01_db_config.get("case_id")
            and t01_db_report.get("stage") == "T01-D-B"
            and t01_db_report.get("evidence_level") == "E2",
            str(t01_db_report.get("status")),
        )
        add_check(
            checks,
            "t01_d_b:independent_check",
            t01_db_check.get("status") == "PASS"
            and t01_db_check.get("case_id") == t01_db_config.get("case_id")
            and t01_db_check.get("stage") == "T01-D-B"
            and len(t01_db_check.get("checks", [])) == 16,
            f"status={t01_db_check.get('status')} checks={len(t01_db_check.get('checks', []))}",
        )
        completion = t01_db_report.get("idvd_completion", {})
        summary_metrics = t01_db_report.get("summary_metrics", {})
        acceptance = t01_db_config["acceptance"]
        add_check(
            checks,
            "t01_d_b:limited_idvd_gate",
            completion.get("status") == "PASS"
            and completion.get("production_mesh") == t01_db_config["mesh"]["production_level"]
            and completion.get("reference_mesh") == t01_db_config["mesh"]["reference_level"]
            and completion.get("sampled_bias_point_count")
            == acceptance["required_total_reported_bias_points"]
            and completion.get("continuous_curve_validation_permitted") is False
            and completion.get("experimental_quantitative_use_permitted") is False
            and completion.get("t01_dc_stage_permitted_next") is True
            and summary_metrics.get(
                "maximum_reference_relative_current_difference", float("inf")
            )
            <= acceptance["maximum_reference_relative_current_difference"]
            and summary_metrics.get(
                "maximum_reference_center_potential_difference_v", float("inf")
            )
            <= acceptance["maximum_reference_center_potential_difference_v"],
            (
                f"points={completion.get('sampled_bias_point_count')} "
                f"mesh_current={summary_metrics.get('maximum_reference_relative_current_difference')}"
            ),
        )
        runner_checks = t01_db_report.get("checks", {})
        add_check(
            checks,
            "t01_d_b:acceptance_checks",
            bool(runner_checks)
            and all(result.get("status") == "PASS" for result in runner_checks.values()),
            f"checks={len(runner_checks)}",
        )
        output_paths = [
            ROOT / value
            for key, value in t01_db_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        run_directory = ROOT / t01_db_report.get("outputs", {}).get("run_directory", "")
        figure_path = ROOT / t01_db_report.get("figure", {}).get("path", "")
        add_check(
            checks,
            "t01_d_b:raw_outputs",
            all(path.is_file() and path.stat().st_size > 0 for path in output_paths)
            and run_directory.is_dir()
            and figure_path.is_file()
            and figure_path.stat().st_size > 0,
            f"files={len(output_paths)} figure={figure_path}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t01_d_b:idvd", False, str(error))

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

    report_manifest_path = ROOT / "report" / "manifest.json"
    try:
        report_manifest = json.loads(report_manifest_path.read_text(encoding="utf-8"))
        chapters = report_manifest["chapters"]
        appendices = report_manifest["appendices"]
        required_sections = [f"section-{index:02d}" for index in range(1, 13)]
        required_appendices = [f"appendix-{letter}" for letter in "abcde"]
        add_check(
            checks,
            "report:authoring_and_submission_modes",
            report_manifest.get("authoring_mode") == "chapter_sources"
            and report_manifest.get("submission_mode") == "single_self_contained_html",
            f"{report_manifest.get('authoring_mode')} -> {report_manifest.get('submission_mode')}",
        )
        add_check(
            checks,
            "report:required_sections",
            [item.get("id") for item in chapters] == required_sections,
            f"chapters={len(chapters)}",
        )
        add_check(
            checks,
            "report:required_appendices",
            [item.get("id") for item in appendices] == required_appendices,
            f"appendices={len(appendices)}",
        )

        section_tag = "{http://www.w3.org/1999/xhtml}section"
        fragment_texts: list[str] = []
        fragments_valid = True
        fragment_specs = [
            *((item, "report-chapter") for item in chapters),
            *((item, "report-appendix") for item in appendices),
        ]
        for record, required_class in fragment_specs:
            fragment_path = ROOT / record["source"]
            if not fragment_path.is_file():
                fragments_valid = False
                continue
            fragment_text = fragment_path.read_text(encoding="utf-8")
            fragment_texts.append(fragment_text)
            fragment_root = ET.fromstring(fragment_text)
            classes = set(fragment_root.attrib.get("class", "").split())
            if (
                fragment_root.tag != section_tag
                or fragment_root.attrib.get("id") != record["id"]
                or required_class not in classes
            ):
                fragments_valid = False
        add_check(
            checks,
            "report:chapter_and_appendix_sources",
            fragments_valid and len(fragment_texts) == 17,
            f"valid_sources={len(fragment_texts)}/17",
        )

        shell_path = ROOT / report_manifest["shell"]
        report_text = shell_path.read_text(encoding="utf-8")
        report_root = ET.fromstring(report_text)
        namespace = {"h": "http://www.w3.org/1999/xhtml"}
        content = report_root.find(".//h:div[@id='report-content']", namespace)
        toc = report_root.find(".//h:nav[@id='report-toc']/h:ol", namespace)
        add_check(
            checks,
            "report:shell_contract",
            content is not None and toc is not None and not list(content) and not list(toc),
            "empty content and TOC containers",
        )
        add_check(
            checks,
            "report:print_chapter_breaks",
            "report-chapter" in report_text and "page-break-before" in report_text,
            "chapter print pagination declared",
        )
        combined_text = "\n".join([report_text, *fragment_texts])
        forbidden_images = re.findall(
            r'<img[^>]+src=["\'](?:https?://|file://|[A-Za-z]:[\\/]|/)', combined_text, re.IGNORECASE
        )
        add_check(checks, "report:no_forbidden_image_sources", not forbidden_images, f"count={len(forbidden_images)}")
        add_check(
            checks,
            "report:placeholder_guard",
            "[\u5f85\u586b\u5199" in combined_text,
            "chapter drafts intentionally remain non-final until placeholders are resolved",
        )
        add_check(
            checks,
            "report:current_scope_title",
            "双栅 IGZO" in combined_text and "单极性逻辑" in combined_text,
            "report shell and chapter placeholders use current scope",
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
