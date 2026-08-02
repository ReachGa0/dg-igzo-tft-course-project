#!/usr/bin/env python3
"""Check the planning scaffold and frozen baseline for consistency."""

from __future__ import annotations

import csv
import hashlib
import json
import math
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
    "config/tcad_t01_d_extraction.json",
    "config/tcad_t02_a_dual_gate_contract.json",
    "config/tcad_t02_b_minimal_bias.json",
    "config/tcad_t02_c_bidirectional.json",
    "config/tcad_t03_p4_channel_length.json",
    "config/tcad_t03_p4_channel_length_v1_failed.json",
    "config/tcad_t03_p1_secondary_bias.json",
    "config/tcad_t03_p1_capacitance_ratio.json",
    "config/tcad_t03_p2_interface_trap.json",
    "config/tcad_t03_p2_dit_formal.json",
    "references/papers_manifest.csv",
    "references/senior_work_manifest.csv",
    "references/t03_p2_dit_sources.csv",
    "references/t03_p2_bulk_trap_sources.csv",
    "config/tcad_t03_p2_bulk_traps.json",
    "config/tcad_t03_p2_bulk_traps_formal.json",
    "config/tcad_t03_p2_bulk_traps_formal_v1_failed.json",
    "config/tcad_t03_p2_bulk_traps_formal_v2_failed.json",
    "scripts/check_t03_p2_bulk_traps_contract.py",
    "scripts/check_t03_p2_bulk_traps_equation_smoke.py",
    "scripts/check_t03_p2_bulk_traps_formal_contract.py",
    "scripts/check_t03_p2_bulk_traps_formal.py",
    "tcad/run_t03_p2_bulk_traps_equation_smoke.py",
    "tcad/run_t03_p2_bulk_traps_formal.py",
    "tcad/run_t03_p2_bulk_traps_formal_v1_failed.py",
    "tcad/run_t03_p2_bulk_traps_formal_v2_failed.py",
    "results/reports/tcad_t03_p2_bulk_traps_input_contract.json",
    "results/reports/tcad_t03_p2_bulk_traps_equation_smoke.json",
    "results/reports/tcad_t03_p2_bulk_traps_equation_smoke_check.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v2.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v3.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_v1_runner_completed_without_exception.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_v2.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_v2_runner_completed_without_exception.json",
    "results/reports/project_check_t03_p2_bulk_formal_boundary_checker_bug_failed.json",
    "results/reports/project_check_t03_p2_bulk_v2_failure_checker_math_import_bug_failed.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v3_checker_v2_curve_loader_bug_failed.json",
    "results/tables/tcad_t03_p2_bulk_traps_equation_smoke_cases.csv",
    "results/tables/tcad_t03_p2_bulk_traps_integration_samples.csv",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/input_snapshot.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/solver_log.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/state_nodes.csv",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal/state_manifest.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v1_runner_completed_without_exception/failure_archive_manifest.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v1_runner_completed_without_exception/input_snapshot.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v1_runner_completed_without_exception/state_manifest.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v1_runner_completed_without_exception/external_artifacts/tcad_t03_p2_bulk_traps_formal_transfer.csv",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v2_runner_completed_without_exception/failure_archive_manifest.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v2_runner_completed_without_exception/input_snapshot.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v2_runner_completed_without_exception/state_manifest.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v2_runner_completed_without_exception/external_artifacts/tcad_t03_p2_bulk_traps_formal_v2_transfer.csv",
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
    "scripts/check_t01_d_extraction.py",
    "scripts/check_t02_a_contract.py",
    "scripts/check_t02_a_limit_regression.py",
    "scripts/check_t02_b_contract.py",
    "scripts/check_t02_b_minimal_bias.py",
    "scripts/check_t02_c_contract.py",
    "scripts/check_t02_c_bidirectional.py",
    "scripts/check_t03_p4_l_contract.py",
    "scripts/check_t03_p4_channel_length.py",
    "scripts/check_t03_p1_bias_contract.py",
    "scripts/check_t03_p1_secondary_bias.py",
    "scripts/check_t03_p1_cap_ratio_contract.py",
    "scripts/check_t03_p1_capacitance_ratio.py",
    "scripts/check_t03_p2_dit_contract.py",
    "scripts/check_t03_p2_dit_equation_smoke.py",
    "scripts/check_t03_p2_dit_formal_contract.py",
    "scripts/check_t03_p2_dit_formal.py",
    "scripts/build_self_contained_report.py",
    "tcad/README.md",
    "tcad/run_dg_electrostatic.py",
    "tcad/run_t01_single_gate_smoke.py",
    "tcad/run_t01_single_gate_transfer.py",
    "tcad/run_t01_single_gate_mesh_refinement.py",
    "tcad/run_t01_single_gate_idvd.py",
    "tcad/run_t01_single_gate_extraction.py",
    "tcad/run_t02_dual_gate_limit_regression.py",
    "tcad/run_t02_dual_gate_minimal_bias.py",
    "tcad/run_t02_dual_gate_bidirectional.py",
    "tcad/run_t03_p4_channel_length.py",
    "tcad/run_t03_p1_secondary_bias.py",
    "tcad/run_t03_p1_capacitance_ratio.py",
    "tcad/run_t03_p2_dit_equation_smoke.py",
    "tcad/run_t03_p2_dit_formal.py",
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
    "results/reports/tcad_t01_d_extraction.json",
    "results/reports/tcad_t01_d_extraction_check.json",
    "results/tables/tcad_t01_d_extraction_idvg.csv",
    "results/tables/tcad_t01_d_extraction_mesh_summary.csv",
    "results/tables/tcad_t01_d_extraction_mesh_comparison.csv",
    "results/tables/tcad_t01_d_extraction_parameter_proxies.csv",
    "results/tables/tcad_t01_d_extraction_state_summary.csv",
    "results/tables/tcad_t01_d_extraction_db_reproduction.csv",
    "results/tcad/t01_single_gate/t01_d_extraction/state_manifest.json",
    "report/assets/tcad_t01_dc_extraction.png",
    "report/assets/tcad_t01_dc_state_maps.png",
    "results/reports/tcad_t02_a_input_contract.json",
    "results/reports/tcad_t02_a_limit_regression.json",
    "results/reports/tcad_t02_a_limit_regression_check.json",
    "results/tables/tcad_t02_a_disabled_regression.csv",
    "results/tables/tcad_t02_a_topology_summary.csv",
    "results/tcad/t02_dual_gate/t02_a_limit_regression/state_manifest.json",
    "results/reports/tcad_t02_b_input_contract.json",
    "results/reports/tcad_t02_b_minimal_bias.json",
    "results/reports/tcad_t02_b_minimal_bias_check.json",
    "results/tables/tcad_t02_b_minimal_bias.csv",
    "results/tables/tcad_t02_b_state_summary.csv",
    "results/tcad/t02_dual_gate/t02_b_minimal_bias/state_manifest.json",
    "report/assets/tcad_t02_b_minimal_bias.png",
    "results/reports/tcad_t02_c_input_contract.json",
    "results/reports/tcad_t02_c_bidirectional.json",
    "results/reports/tcad_t02_c_bidirectional_check.json",
    "results/tables/tcad_t02_c_bidirectional_families.csv",
    "results/tables/tcad_t02_c_coupling_metrics.csv",
    "results/tables/tcad_t02_c_reverse_comparison.csv",
    "results/tables/tcad_t02_c_reciprocal_comparison.csv",
    "results/tables/tcad_t02_c_state_summary.csv",
    "results/tcad/t02_dual_gate/t02_c_bidirectional/state_manifest.json",
    "report/assets/tcad_t02_c_bidirectional_families.png",
    "report/assets/tcad_t02_c_state_maps.png",
    "results/reports/tcad_t03_p4_l_input_contract.json",
    "results/reports/tcad_t03_p4_l_sensitivity.json",
    "results/reports/tcad_t03_p4_l_sensitivity_check.json",
    "results/reports/tcad_t03_p4_l_input_contract_v1_failed.json",
    "results/reports/tcad_t03_p4_l_sensitivity_v1_failed.json",
    "results/tables/tcad_t03_p4_l_transfer_curves.csv",
    "results/tables/tcad_t03_p4_l_metrics.csv",
    "results/tables/tcad_t03_p4_l_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p4_l_state_summary.csv",
    "results/tcad/t03_sensitivity/p4_channel_length/state_manifest.json",
    "results/tcad/t03_sensitivity/p4_channel_length_v1_failed/state_manifest.json",
    "report/assets/tcad_t03_p4_l_sensitivity.png",
    "report/assets/tcad_t03_p4_l_state_maps.png",
    "report/assets/tcad_t03_p4_l_sensitivity_v1_failed.png",
    "report/assets/tcad_t03_p4_l_state_maps_v1_failed.png",
    "results/reports/tcad_t03_p1_bias_input_contract.json",
    "results/reports/tcad_t03_p1_bias_sensitivity.json",
    "results/reports/tcad_t03_p1_bias_sensitivity_check.json",
    "results/tables/tcad_t03_p1_bias_transfer_curves.csv",
    "results/tables/tcad_t03_p1_bias_metrics.csv",
    "results/tables/tcad_t03_p1_bias_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p1_bias_state_summary.csv",
    "results/tcad/t03_sensitivity/p1_secondary_bias/state_manifest.json",
    "report/assets/tcad_t03_p1_bias_sensitivity.png",
    "report/assets/tcad_t03_p1_bias_state_maps.png",
    "results/reports/tcad_t03_p1_cap_ratio_input_contract.json",
    "results/reports/tcad_t03_p1_cap_ratio_sensitivity.json",
    "results/reports/tcad_t03_p1_cap_ratio_sensitivity_check.json",
    "results/tables/tcad_t03_p1_cap_ratio_transfer_curves.csv",
    "results/tables/tcad_t03_p1_cap_ratio_metrics.csv",
    "results/tables/tcad_t03_p1_cap_ratio_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p1_cap_ratio_state_summary.csv",
    "results/tcad/t03_sensitivity/p1_capacitance_ratio/state_manifest.json",
    "report/assets/tcad_t03_p1_cap_ratio_sensitivity.png",
    "report/assets/tcad_t03_p1_cap_ratio_state_maps.png",
    "results/reports/tcad_t03_p2_dit_input_contract.json",
    "results/reports/tcad_t03_p2_dit_equation_smoke.json",
    "results/reports/tcad_t03_p2_dit_equation_smoke_check.json",
    "results/tables/tcad_t03_p2_dit_equation_smoke_cases.csv",
    "results/tables/tcad_t03_p2_dit_interface_samples.csv",
    "results/tcad/t03_sensitivity/p2_dit_equation_smoke/input_snapshot.json",
    "results/tcad/t03_sensitivity/p2_dit_equation_smoke/solver_log.json",
    "results/tcad/t03_sensitivity/p2_dit_equation_smoke/state_nodes.csv",
    "results/reports/tcad_t03_p2_dit_formal_input_contract.json",
    "results/reports/tcad_t03_p2_dit_formal.json",
    "results/reports/tcad_t03_p2_dit_formal_check.json",
    "results/reports/tcad_t03_p2_dit_formal_v1_failed.json",
    "results/reports/tcad_t03_p2_dit_formal_input_contract_v1_ss_linearity_failed.json",
    "results/reports/tcad_t03_p2_dit_formal_v1_ss_linearity_failed.json",
    "results/tables/tcad_t03_p2_dit_formal_transfer.csv",
    "results/tables/tcad_t03_p2_dit_formal_metrics.csv",
    "results/tables/tcad_t03_p2_dit_formal_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p2_dit_formal_state_summary.csv",
    "results/tcad/t03_sensitivity/p2_dit_formal/state_manifest.json",
    "report/assets/tcad_t03_p2_dit_formal_sensitivity.png",
    "report/assets/tcad_t03_p2_dit_formal_states.png",
    "report/assets/tcad_t03_p2_dit_formal_sensitivity_v1_ss_linearity_failed.png",
    "report/assets/tcad_t03_p2_dit_formal_states_v1_ss_linearity_failed.png",
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
    "results/tcad/t02_dual_gate/t02_a_limit_regression",
    "results/tcad/t02_dual_gate/t02_b_minimal_bias",
    "results/tcad/t02_dual_gate/t02_c_bidirectional",
    "results/tcad/t03_sensitivity/p4_channel_length",
    "results/tcad/t03_sensitivity/p4_channel_length_v1_failed",
    "results/tcad/t03_sensitivity/p1_secondary_bias",
    "results/tcad/t03_sensitivity/p1_capacitance_ratio",
    "results/tcad/t03_sensitivity/p2_dit_equation_smoke",
    "results/tcad/t03_sensitivity/p2_dit_formal",
    "results/tcad/t03_sensitivity/p2_dit_formal_v1_failed",
    "results/tcad/t03_sensitivity/p2_dit_formal_v1_ss_linearity_failed",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke",
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
        add_check(
            checks,
            "experiments:t03_completed_and_partial_groups_are_distinct",
            sensitivity.get("completed_parameter_groups") == ["P1", "P4"]
            and sensitivity.get("partially_completed_parameter_groups") == ["P2"]
            and sensitivity.get("remaining_parameter_groups")
            == ["P2", "P3", "P5"]
            and sensitivity.get("remaining_substages")
            == [
                "T03-P2-BULK-TRAPS formal isolated NTA/NGA transfer sensitivity",
                "T03-P3",
                "T03-P5",
            ]
            and sensitivity.get("p2_bulk_equation_smoke_evidence")
            == {
                "status": "smoke_verified",
                "runner_evidence": "E2",
                "independent_persisted_check_evidence": "E3",
                "devices": 3,
                "coupled_dc_solves": 21,
                "state_node_rows": 7257,
                "integration_sample_rows": 6,
                "formal_transfer_sensitivity_completed": False,
            }
            and sensitivity.get("p2_bulk_formal_contract_evidence")
            == {
                "status": "input_contract_ready_v3",
                "revision": 3,
                "contract_evidence": "E3",
                "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
                "v1_failure_preserved": True,
                "v2_failure_preserved": True,
                "formal_sensitivity_completed": False,
            }
            and sensitivity.get("p2_bulk_formal_v1_failure_evidence")
            == {
                "status": "FAIL_PRESERVED",
                "evidence_level": "E0",
                "devices": 8,
                "converged_dc_records": 328,
                "transfer_points": 248,
                "states": 8,
                "vtk_files": 48,
                "failed_vth_bracket_case": "NTA=5e19 cm^-3 eV^-1",
                "maximum_gate_v": 1.0,
                "maximum_current_a_per_cm": 3.137504658975777e-6,
                "constant_current_criterion_a_per_cm": 1e-5,
                "maximum_nonzero_trap_zero_equilibrium_internal_potential_v": 0.15750389258195557,
                "formal_sensitivity_completed": False,
            }
            and sensitivity.get("p2_bulk_formal_v2_failure_evidence")
            == {
                "status": "FAIL_PRESERVED",
                "evidence_level": "E0",
                "devices": 8,
                "converged_dc_records": 440,
                "transfer_points": 360,
                "states": 8,
                "vtk_files": 48,
                "maximum_gate_v": 1.7,
                "failed_case": "NTA=5e19 cm^-3 eV^-1",
                "constant_current_criterion_a_per_cm": 1e-5,
                "maximum_current_a_per_cm": 1.4190074297322551e-5,
                "diagnostic_bracket_vth_v": 1.466667576519075,
                "gm_evaluation_v": 1.666667576519075,
                "failure_reason": "VTH+0.2 V gm evaluation is outside the frozen central-difference grid",
                "wall_seconds": 28.414362409002933,
                "independent_persisted_check_run": False,
                "formal_sensitivity_completed": False,
            }
            and all(
                path in sensitivity.get("p2_partial_outputs", [])
                for path in [
                    "results/reports/tcad_t03_p2_bulk_traps_equation_smoke.json",
                    "results/reports/tcad_t03_p2_bulk_traps_equation_smoke_check.json",
                    "results/tables/tcad_t03_p2_bulk_traps_equation_smoke_cases.csv",
                    "results/tables/tcad_t03_p2_bulk_traps_integration_samples.csv",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/input_snapshot.json",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/solver_log.json",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/state_nodes.csv",
                    "config/tcad_t03_p2_bulk_traps_formal.json",
                    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract.json",
                    "config/tcad_t03_p2_bulk_traps_formal_v1_failed.json",
                    "config/tcad_t03_p2_bulk_traps_formal_v2_failed.json",
                    "tcad/run_t03_p2_bulk_traps_formal_v2_failed.py",
                    "results/reports/tcad_t03_p2_bulk_traps_formal_v1_runner_completed_without_exception.json",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v1_runner_completed_without_exception/failure_archive_manifest.json",
                    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v2.json",
                    "results/reports/tcad_t03_p2_bulk_traps_formal_v2_runner_completed_without_exception.json",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v2_runner_completed_without_exception/failure_archive_manifest.json",
                    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v3.json",
                ]
            ),
            (
                f"complete={sensitivity.get('completed_parameter_groups')} "
                f"partial={sensitivity.get('partially_completed_parameter_groups')} "
                f"remaining={sensitivity.get('remaining_substages')}"
            ),
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

    t01_dc_report_path = ROOT / "results" / "reports" / "tcad_t01_d_extraction.json"
    t01_dc_check_path = ROOT / "results" / "reports" / "tcad_t01_d_extraction_check.json"
    try:
        t01_dc_config = json.loads(
            (ROOT / "config" / "tcad_t01_d_extraction.json").read_text(encoding="utf-8")
        )
        t01_dc_report = json.loads(t01_dc_report_path.read_text(encoding="utf-8"))
        t01_dc_check = json.loads(t01_dc_check_path.read_text(encoding="utf-8"))
        add_check(
            checks,
            "t01_d_c:completion_status",
            t01_dc_report.get("status") == "PASS"
            and t01_dc_report.get("case_id") == t01_dc_config.get("case_id")
            and t01_dc_report.get("stage") == "T01-D-C"
            and t01_dc_report.get("evidence_level") == "E2",
            str(t01_dc_report.get("status")),
        )
        add_check(
            checks,
            "t01_d_c:independent_check",
            t01_dc_check.get("status") == "PASS"
            and t01_dc_check.get("case_id") == t01_dc_config.get("case_id")
            and t01_dc_check.get("stage") == "T01-D-C"
            and len(t01_dc_check.get("checks", [])) == 17,
            f"status={t01_dc_check.get('status')} checks={len(t01_dc_check.get('checks', []))}",
        )
        completion = t01_dc_report.get("t01_completion", {})
        requirements = completion.get("requirements", {})
        add_check(
            checks,
            "t01_d_c:complete_teaching_model_gate",
            completion.get("status") == "PASS"
            and completion.get("complete_t01_numerical_stage_gate") == "PASS"
            and set(requirements.values()) == {"PASS"}
            and completion.get("t02_stage_permitted_next") is True
            and completion.get("experimental_calibration_permitted") is False
            and completion.get("physical_parameter_validation_permitted") is False
            and completion.get("physical_ion_ioff_claim_permitted") is False
            and completion.get("compact_model_calibrated") is False,
            f"requirements={requirements} next={completion.get('t02_stage_permitted_next')}",
        )
        parameter_proxies = t01_dc_report.get("parameter_proxies", [])
        summary_metrics = t01_dc_report.get("summary_metrics", {})
        acceptance = t01_dc_config["acceptance"]
        add_check(
            checks,
            "t01_d_c:numerical_proxy_boundary",
            len(parameter_proxies) == 2
            and all(
                row.get("parameter_claim_status")
                == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
                for row in parameter_proxies
            )
            and summary_metrics.get("vth_proxy_mesh_difference_v", float("inf"))
            <= acceptance["maximum_vth_proxy_mesh_difference_v"]
            and summary_metrics.get("ss_proxy_mesh_relative_difference", float("inf"))
            <= acceptance["maximum_ss_proxy_mesh_relative_difference"]
            and summary_metrics.get("mobility_proxy_mesh_relative_difference", float("inf"))
            <= acceptance["maximum_mobility_proxy_mesh_relative_difference"]
            and t01_dc_report.get("teaching_target_diagnostic_only", {}).get(
                "acceptance_depends_on_target_match"
            )
            is False,
            f"proxies={len(parameter_proxies)} metrics={summary_metrics}",
        )
        runner_checks = t01_dc_report.get("checks", {})
        state_outputs = t01_dc_report.get("state_outputs", [])
        state_manifest = json.loads(
            (ROOT / t01_dc_report["outputs"]["state_manifest"]).read_text(encoding="utf-8")
        )
        state_entries = state_manifest.get("entries", [])
        state_paths = [
            ROOT / path
            for entry in state_entries
            for path in (entry["node_csv"], entry["element_csv"])
        ]
        vtk_paths = [
            ROOT / item["path"]
            for entry in state_entries
            for item in entry.get("vtk_files", [])
        ]
        output_paths = [
            ROOT / value
            for key, value in t01_dc_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        run_directory = ROOT / t01_dc_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t01_d_c:checks_and_raw_outputs",
            bool(runner_checks)
            and len(runner_checks) == 12
            and all(result.get("status") == "PASS" for result in runner_checks.values())
            and [entry.get("state_id") for entry in state_outputs]
            == acceptance["required_state_ids"]
            and [entry.get("state_id") for entry in state_entries]
            == acceptance["required_state_ids"]
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in output_paths + state_paths + vtk_paths
            )
            and len(state_paths) == 6
            and len(vtk_paths) == 15
            and run_directory.is_dir(),
            f"checks={len(runner_checks)} states={len(state_entries)} vtk={len(vtk_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t01_d_c:extraction", False, str(error))

    t02_a_contract_path = ROOT / "results" / "reports" / "tcad_t02_a_input_contract.json"
    t02_a_report_path = ROOT / "results" / "reports" / "tcad_t02_a_limit_regression.json"
    t02_a_check_path = ROOT / "results" / "reports" / "tcad_t02_a_limit_regression_check.json"
    try:
        t02_a_config = json.loads(
            (ROOT / "config" / "tcad_t02_a_dual_gate_contract.json").read_text(
                encoding="utf-8"
            )
        )
        t02_a_contract = json.loads(t02_a_contract_path.read_text(encoding="utf-8"))
        t02_a_report = json.loads(t02_a_report_path.read_text(encoding="utf-8"))
        t02_a_check = json.loads(t02_a_check_path.read_text(encoding="utf-8"))
        contract_checks = t02_a_contract.get("checks", [])
        add_check(
            checks,
            "t02_a:input_contract",
            t02_a_contract.get("status") == "PASS"
            and t02_a_contract.get("contract_status") == "PASS"
            and t02_a_contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and t02_a_contract.get("case_id") == t02_a_config.get("case_id")
            and len(contract_checks) == 16
            and all(result.get("status") == "PASS" for result in contract_checks),
            f"status={t02_a_contract.get('status')} checks={len(contract_checks)}",
        )
        add_check(
            checks,
            "t02_a:simulation_and_independent_check",
            t02_a_report.get("status") == "PASS"
            and t02_a_report.get("case_id") == t02_a_config.get("case_id")
            and t02_a_report.get("stage") == "T02-A"
            and t02_a_report.get("evidence_level") == "E2"
            and t02_a_check.get("status") == "PASS"
            and t02_a_check.get("case_id") == t02_a_config.get("case_id")
            and t02_a_check.get("stage") == "T02-A"
            and len(t02_a_check.get("checks", [])) == 14,
            (
                f"simulation={t02_a_report.get('status')} independent="
                f"{t02_a_check.get('status')} checks={len(t02_a_check.get('checks', []))}"
            ),
        )
        completion = t02_a_report.get("t02_a_completion", {})
        metrics = t02_a_report.get("summary_metrics", {})
        acceptance = t02_a_config["acceptance"]
        add_check(
            checks,
            "t02_a:disabled_limit_gate",
            completion.get("status") == "PASS"
            and completion.get("input_contract_frozen") is True
            and completion.get("disabled_top_stack_returns_t01") is True
            and completion.get("enabled_zero_bias_topology_smoke") is True
            and completion.get("t02_b_minimal_bias_family_permitted_next") is True
            and completion.get("t02_complete") is False
            and completion.get("nonzero_dual_gate_coupling_verified") is False
            and metrics.get(
                "maximum_disabled_t01_relative_current_difference", float("inf")
            )
            <= acceptance["maximum_disabled_t01_relative_current_difference"]
            and metrics.get(
                "maximum_disabled_t01_center_potential_difference_v", float("inf")
            )
            <= acceptance["maximum_disabled_t01_center_potential_difference_v"]
            and metrics.get(
                "maximum_disabled_t01_center_density_relative_difference", float("inf")
            )
            <= acceptance["maximum_disabled_t01_center_density_relative_difference"],
            f"completion={completion} metrics={metrics}",
        )
        topology = {
            bool(item["top_coupling_enabled"]): item
            for item in t02_a_report.get("topology", [])
        }
        disabled_topology = topology.get(False, {})
        enabled_topology = topology.get(True, {})
        add_check(
            checks,
            "t02_a:topology_modes",
            disabled_topology.get("regions")
            == sorted(acceptance["required_disabled_regions"])
            and disabled_topology.get("contacts")
            == sorted(acceptance["required_disabled_contacts"])
            and enabled_topology.get("regions")
            == sorted(acceptance["required_enabled_regions"])
            and enabled_topology.get("contacts")
            == sorted(acceptance["required_enabled_contacts"])
            and enabled_topology.get("node_count_with_interface_duplicates", 0)
            > disabled_topology.get("node_count_with_interface_duplicates", 0)
            and disabled_topology.get("dc_solve_count")
            == acceptance["required_disabled_dc_solve_count"]
            and enabled_topology.get("dc_solve_count")
            == acceptance["required_enabled_zero_bias_dc_solve_count"],
            (
                f"disabled_nodes={disabled_topology.get('node_count_with_interface_duplicates')} "
                f"enabled_nodes={enabled_topology.get('node_count_with_interface_duplicates')}"
            ),
        )
        runner_checks = t02_a_report.get("checks", {})
        state_entries = t02_a_report.get("state_outputs", [])
        state_paths = [ROOT / entry["state_csv"] for entry in state_entries]
        vtk_paths = [
            ROOT / item["path"]
            for entry in state_entries
            for item in entry.get("vtk_files", [])
        ]
        output_paths = [
            ROOT / value
            for key, value in t02_a_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        run_directory = ROOT / t02_a_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t02_a:checks_and_raw_outputs",
            len(runner_checks) == 10
            and all(result.get("status") == "PASS" for result in runner_checks.values())
            and len(state_entries) == 1
            and len(vtk_paths) == 6
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in output_paths + state_paths + vtk_paths
            )
            and run_directory.is_dir(),
            f"checks={len(runner_checks)} states={len(state_entries)} vtk={len(vtk_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t02_a:limit_regression", False, str(error))

    t02_b_contract_path = ROOT / "results" / "reports" / "tcad_t02_b_input_contract.json"
    t02_b_report_path = ROOT / "results" / "reports" / "tcad_t02_b_minimal_bias.json"
    t02_b_check_path = ROOT / "results" / "reports" / "tcad_t02_b_minimal_bias_check.json"
    try:
        t02_b_config = json.loads(
            (ROOT / "config" / "tcad_t02_b_minimal_bias.json").read_text(
                encoding="utf-8"
            )
        )
        t02_b_contract = json.loads(t02_b_contract_path.read_text(encoding="utf-8"))
        t02_b_report = json.loads(t02_b_report_path.read_text(encoding="utf-8"))
        t02_b_check = json.loads(t02_b_check_path.read_text(encoding="utf-8"))
        contract_checks = t02_b_contract.get("checks", [])
        add_check(
            checks,
            "t02_b:input_contract",
            t02_b_contract.get("status") == "PASS"
            and t02_b_contract.get("contract_status") == "PASS"
            and t02_b_contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and t02_b_contract.get("case_id") == t02_b_config.get("case_id")
            and len(contract_checks) == 17
            and all(result.get("status") == "PASS" for result in contract_checks),
            f"status={t02_b_contract.get('status')} checks={len(contract_checks)}",
        )
        add_check(
            checks,
            "t02_b:simulation_and_independent_check",
            t02_b_report.get("status") == "PASS"
            and t02_b_report.get("case_id") == t02_b_config.get("case_id")
            and t02_b_report.get("stage") == "T02-B"
            and t02_b_report.get("evidence_level") == "E2"
            and t02_b_check.get("status") == "PASS"
            and t02_b_check.get("case_id") == t02_b_config.get("case_id")
            and t02_b_check.get("stage") == "T02-B"
            and len(t02_b_check.get("checks", [])) == 14,
            (
                f"simulation={t02_b_report.get('status')} independent="
                f"{t02_b_check.get('status')} checks={len(t02_b_check.get('checks', []))}"
            ),
        )
        completion = t02_b_report.get("t02_b_completion", {})
        metrics = t02_b_report.get("summary_metrics", {})
        acceptance = t02_b_config["acceptance"]
        add_check(
            checks,
            "t02_b:minimal_top_gate_response_gate",
            completion.get("status") == "PASS"
            and completion.get("minimal_nonzero_top_gate_family_completed") is True
            and completion.get("top_gate_response_direction_verified") is True
            and completion.get("t02_c_bidirectional_family_permitted_next") is True
            and completion.get("t02_complete") is False
            and completion.get("delta_vth_verified") is False
            and completion.get("gm_verified") is False
            and metrics.get("maximum_relative_terminal_current_imbalance", float("inf"))
            <= acceptance["maximum_relative_terminal_current_imbalance"]
            and metrics.get("endpoint_current_ratio", 0.0)
            >= acceptance["minimum_endpoint_current_ratio"]
            and metrics.get("endpoint_center_potential_increase_v", 0.0)
            >= acceptance["minimum_endpoint_center_potential_increase_v"]
            and metrics.get("endpoint_center_density_ratio", 0.0)
            >= acceptance["minimum_endpoint_center_density_ratio"],
            f"completion={completion} metrics={metrics}",
        )
        topology = t02_b_report.get("topology", {})
        bias_points = t02_b_report.get("bias_points", [])
        add_check(
            checks,
            "t02_b:topology_and_bias_grid",
            topology.get("regions") == sorted(acceptance["required_regions"])
            and topology.get("contacts") == sorted(acceptance["required_contacts"])
            and topology.get("interfaces") == sorted(acceptance["required_interfaces"])
            and topology.get("mesh_level") == "interface_4x"
            and [float(row["vtg_v"]) for row in bias_points]
            == [float(value) for value in acceptance["required_top_gate_values_v"]]
            and all(float(row["vbg_v"]) == 0.0 for row in bias_points)
            and all(float(row["vds_v"]) == 0.01 for row in bias_points),
            f"nodes={topology.get('node_count_with_interface_duplicates')} points={len(bias_points)}",
        )
        runner_checks = t02_b_report.get("checks", {})
        state_entries = t02_b_report.get("state_outputs", [])
        state_paths = [ROOT / entry["state_csv"] for entry in state_entries]
        vtk_paths = [
            ROOT / item["path"]
            for entry in state_entries
            for item in entry.get("vtk_files", [])
        ]
        output_paths = [
            ROOT / value
            for key, value in t02_b_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        run_directory = ROOT / t02_b_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t02_b:checks_and_raw_outputs",
            len(runner_checks) == 10
            and all(result.get("status") == "PASS" for result in runner_checks.values())
            and [entry.get("state_id") for entry in state_entries]
            == acceptance["required_state_ids"]
            and len(state_paths) == 2
            and len(vtk_paths) == 12
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in output_paths + state_paths + vtk_paths
            )
            and run_directory.is_dir(),
            f"checks={len(runner_checks)} states={len(state_entries)} vtk={len(vtk_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t02_b:minimal_bias", False, str(error))

    t02_c_contract_path = ROOT / "results" / "reports" / "tcad_t02_c_input_contract.json"
    t02_c_report_path = ROOT / "results" / "reports" / "tcad_t02_c_bidirectional.json"
    t02_c_check_path = ROOT / "results" / "reports" / "tcad_t02_c_bidirectional_check.json"
    try:
        t02_c_config = json.loads(
            (ROOT / "config" / "tcad_t02_c_bidirectional.json").read_text(
                encoding="utf-8"
            )
        )
        t02_c_contract = json.loads(t02_c_contract_path.read_text(encoding="utf-8"))
        t02_c_report = json.loads(t02_c_report_path.read_text(encoding="utf-8"))
        t02_c_check = json.loads(t02_c_check_path.read_text(encoding="utf-8"))
        contract_checks = t02_c_contract.get("checks", [])
        add_check(
            checks,
            "t02_c:input_contract",
            t02_c_contract.get("status") == "PASS"
            and t02_c_contract.get("contract_status") == "PASS"
            and t02_c_contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and t02_c_contract.get("case_id") == t02_c_config.get("case_id")
            and len(contract_checks) == 21
            and all(result.get("status") == "PASS" for result in contract_checks),
            f"status={t02_c_contract.get('status')} checks={len(contract_checks)}",
        )
        add_check(
            checks,
            "t02_c:simulation_and_independent_check",
            t02_c_report.get("status") == "PASS"
            and t02_c_report.get("case_id") == t02_c_config.get("case_id")
            and t02_c_report.get("stage") == "T02-C"
            and t02_c_report.get("evidence_level") == "E2"
            and t02_c_check.get("status") == "PASS"
            and t02_c_check.get("case_id") == t02_c_config.get("case_id")
            and t02_c_check.get("stage") == "T02-C"
            and len(t02_c_check.get("checks", [])) == 17
            and all(
                result.get("status") == "PASS"
                for result in t02_c_check.get("checks", [])
            )
            and not t02_c_check.get("failures"),
            (
                f"simulation={t02_c_report.get('status')} independent="
                f"{t02_c_check.get('status')} checks={len(t02_c_check.get('checks', []))}"
            ),
        )
        completion = t02_c_report.get("t02_c_completion", {})
        metrics = t02_c_report.get("summary_metrics", {})
        acceptance = t02_c_config["acceptance"]
        add_check(
            checks,
            "t02_c:complete_numerical_gate",
            completion.get("status") == "PASS"
            and completion.get("complete_t02_numerical_stage_gate") == "PASS"
            and completion.get("t02_complete") is True
            and completion.get("t03_controlled_sensitivity_permitted_next") is True
            and completion.get("experimental_calibration_permitted") is False
            and completion.get("physical_parameter_validation_permitted") is False
            and metrics.get("maximum_relative_terminal_current_imbalance", float("inf"))
            <= acceptance["maximum_relative_terminal_current_imbalance"]
            and metrics.get(
                "maximum_forward_reverse_relative_current_difference", float("inf")
            )
            <= acceptance["maximum_forward_reverse_relative_current_difference"]
            and metrics.get(
                "maximum_reciprocal_top_bottom_relative_current_difference", float("inf")
            )
            <= acceptance["maximum_reciprocal_top_bottom_relative_current_difference"],
            f"completion={completion} metrics={metrics}",
        )
        family_points = t02_c_report.get("family_points", [])
        forward_points = [
            row for row in family_points if row.get("sweep_direction") == "forward"
        ]
        reverse_points = [
            row for row in family_points if row.get("sweep_direction") == "reverse"
        ]
        coupling_metrics = t02_c_report.get("coupling_metrics", [])
        add_check(
            checks,
            "t02_c:families_and_limited_extraction",
            len(family_points) == acceptance["required_total_reported_point_count"]
            and len(forward_points) == acceptance["required_forward_reported_point_count"]
            and len(reverse_points) == acceptance["required_reverse_reported_point_count"]
            and len(coupling_metrics) == acceptance["required_forward_family_count"]
            and all(float(row.get("gm_proxy_s_per_cm", 0.0)) > 0.0 for row in coupling_metrics)
            and all(
                float(row.get("coupling_slope_v_per_v", 0.0)) < 0.0
                and float(row.get("coupling_fit_r_squared", 0.0))
                >= acceptance["minimum_coupling_fit_r_squared"]
                for row in coupling_metrics
            )
            and len(t02_c_report.get("reverse_path_summaries", []))
            == acceptance["required_reverse_family_count"]
            and t02_c_report.get("reciprocal_symmetry_summary", {}).get("point_count")
            == acceptance["required_primary_gate_point_count"]
            * len(acceptance["required_fixed_secondary_gate_values_v"]),
            (
                f"points={len(family_points)} forward={len(forward_points)} "
                f"reverse={len(reverse_points)} metrics={len(coupling_metrics)}"
            ),
        )
        runner_checks = t02_c_report.get("checks", {})
        state_entries = t02_c_report.get("state_outputs", [])
        state_paths = [
            ROOT / entry[key]
            for entry in state_entries
            for key in ("node_csv", "element_csv")
        ]
        vtk_paths = [
            ROOT / item["path"]
            for entry in state_entries
            for item in entry.get("vtk_files", [])
        ]
        figure_paths = [ROOT / item["path"] for item in t02_c_report.get("figures", [])]
        output_paths = [
            ROOT / value
            for key, value in t02_c_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        run_directory = ROOT / t02_c_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t02_c:checks_and_raw_outputs",
            len(runner_checks) == 15
            and all(result.get("status") == "PASS" for result in runner_checks.values())
            and [entry.get("state_id") for entry in state_entries]
            == acceptance["required_state_ids"]
            and len(state_paths) == 12
            and len(vtk_paths) == 36
            and len(figure_paths) == 2
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in output_paths + state_paths + vtk_paths + figure_paths + [t02_c_check_path]
            )
            and run_directory.is_dir(),
            (
                f"checks={len(runner_checks)} states={len(state_entries)} "
                f"state_csv={len(state_paths)} vtk={len(vtk_paths)} figures={len(figure_paths)}"
            ),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t02_c:bidirectional", False, str(error))

    t03_config_path = ROOT / "config" / "tcad_t03_p4_channel_length.json"
    t03_contract_path = ROOT / "results" / "reports" / "tcad_t03_p4_l_input_contract.json"
    t03_report_path = ROOT / "results" / "reports" / "tcad_t03_p4_l_sensitivity.json"
    t03_check_path = ROOT / "results" / "reports" / "tcad_t03_p4_l_sensitivity_check.json"
    try:
        t03_config = json.loads(t03_config_path.read_text(encoding="utf-8"))
        t03_contract = json.loads(t03_contract_path.read_text(encoding="utf-8"))
        t03_report = json.loads(t03_report_path.read_text(encoding="utf-8"))
        t03_check = json.loads(t03_check_path.read_text(encoding="utf-8"))
        t03_runner_checks = t03_report.get("checks", {})
        t03_completion = t03_report.get("t03_p4_l_completion", {})
        t03_diagnostic = t03_report.get("diagnostic_hypotheses", {}).get(
            "ideal_inverse_length", {}
        )
        add_check(
            checks,
            "t03_p4_l:contract_and_simulation",
            t03_contract.get("contract_status") == "PASS"
            and t03_contract.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(t03_contract.get("checks", [])) == 25
            and all(item.get("status") == "PASS" for item in t03_contract["checks"])
            and t03_report.get("status") == "PASS"
            and t03_report.get("case_id") == t03_config.get("case_id")
            and t03_report.get("evidence_level") == "E2"
            and len(t03_runner_checks) == 16
            and all(item.get("status") == "PASS" for item in t03_runner_checks.values())
            and not t03_report.get("failures"),
            f"contract={t03_contract.get('contract_status')} simulation={t03_report.get('status')} runner_checks={len(t03_runner_checks)}",
        )
        add_check(
            checks,
            "t03_p4_l:independent_check_and_completion_boundary",
            t03_check.get("status") == "PASS"
            and t03_check.get("case_id") == t03_config.get("case_id")
            and t03_check.get("stage") == "T03-P4-L"
            and t03_check.get("evidence_level") == "E3"
            and len(t03_check.get("checks", [])) == 14
            and all(item.get("status") == "PASS" for item in t03_check["checks"])
            and not t03_check.get("failures")
            and t03_completion.get("p4_channel_length_three_point_group_complete") is True
            and t03_completion.get("complete_t03_five_group_sensitivity") is False
            and t03_completion.get("another_t03_group_permitted_next") is True
            and t03_completion.get("experimental_calibration_permitted") is False
            and t03_completion.get("physical_short_channel_claim_permitted") is False,
            f"independent={t03_check.get('status')} completion={t03_completion}",
        )
        add_check(
            checks,
            "t03_p4_l:failed_ideal_scaling_diagnostic_is_not_silently_relaxed",
            t03_diagnostic.get("status") == "FAIL"
            and t03_diagnostic.get("completion_gate") is False
            and t03_diagnostic.get("checks")
            and all(value is False for value in t03_diagnostic["checks"].values())
            and t03_config.get("remediation", {}).get("prior_status") == "FAIL"
            and t03_config.get("remediation", {}).get("prior_failed_checks")
            == [
                "vth_and_gm_numerical_proxies_are_valid",
                "current_and_gm_length_products_are_stable",
                "log_current_length_slope_matches_frozen_gate",
            ],
            f"diagnostic={t03_diagnostic.get('status')} completion_gate={t03_diagnostic.get('completion_gate')}",
        )
        t03_output_paths = [
            ROOT / value
            for key, value in t03_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        t03_state_entries = t03_report.get("state_outputs", [])
        t03_state_paths = [
            ROOT / entry[key]
            for entry in t03_state_entries
            for key in ("node_csv", "element_csv")
        ]
        t03_vtk_paths = [
            ROOT / item["path"]
            for entry in t03_state_entries
            for item in entry.get("vtk_files", [])
        ]
        t03_figures = [ROOT / item["path"] for item in t03_report.get("figures", [])]
        t03_run_directory = ROOT / t03_report.get("outputs", {}).get("run_directory", "")
        add_check(
            checks,
            "t03_p4_l:raw_outputs_and_figures_exist",
            len(t03_state_entries) == 3
            and len(t03_state_paths) == 6
            and len(t03_vtk_paths) == 18
            and len(t03_figures) == 2
            and all(path.is_file() and path.stat().st_size > 0 for path in t03_output_paths + t03_state_paths + t03_vtk_paths + t03_figures + [t03_check_path])
            and t03_run_directory.is_dir(),
            f"states={len(t03_state_entries)} state_csv={len(t03_state_paths)} vtk={len(t03_vtk_paths)} figures={len(t03_figures)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p4_l:channel_length_sensitivity", False, str(error))

    t03_p1_config_path = ROOT / "config" / "tcad_t03_p1_secondary_bias.json"
    t03_p1_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p1_bias_input_contract.json"
    )
    t03_p1_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p1_bias_sensitivity.json"
    )
    t03_p1_check_path = (
        ROOT / "results" / "reports" / "tcad_t03_p1_bias_sensitivity_check.json"
    )
    try:
        t03_p1_config = json.loads(t03_p1_config_path.read_text(encoding="utf-8"))
        t03_p1_contract = json.loads(t03_p1_contract_path.read_text(encoding="utf-8"))
        t03_p1_report = json.loads(t03_p1_report_path.read_text(encoding="utf-8"))
        t03_p1_check = json.loads(t03_p1_check_path.read_text(encoding="utf-8"))
        t03_p1_runner_checks = t03_p1_report.get("checks", {})
        t03_p1_completion = t03_p1_report.get("t03_p1_bias_completion", {})
        add_check(
            checks,
            "t03_p1_bias:contract_and_simulation",
            t03_p1_contract.get("contract_status") == "PASS"
            and t03_p1_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(t03_p1_contract.get("checks", [])) == 22
            and all(
                item.get("status") == "PASS"
                for item in t03_p1_contract["checks"]
            )
            and t03_p1_report.get("status") == "PASS"
            and t03_p1_report.get("case_id") == t03_p1_config.get("case_id")
            and t03_p1_report.get("evidence_level") == "E2"
            and len(t03_p1_runner_checks) == 14
            and all(
                item.get("status") == "PASS"
                for item in t03_p1_runner_checks.values()
            )
            and not t03_p1_report.get("failures"),
            (
                f"contract={t03_p1_contract.get('contract_status')} "
                f"simulation={t03_p1_report.get('status')} "
                f"runner_checks={len(t03_p1_runner_checks)}"
            ),
        )
        add_check(
            checks,
            "t03_p1_bias:independent_check_and_partial_completion_boundary",
            t03_p1_check.get("status") == "PASS"
            and t03_p1_check.get("case_id") == t03_p1_config.get("case_id")
            and t03_p1_check.get("stage") == "T03-P1-BIAS"
            and t03_p1_check.get("evidence_level") == "E3"
            and t03_p1_check.get("independent_of_simulation_runner") is True
            and len(t03_p1_check.get("checks", [])) == 14
            and all(
                item.get("status") == "PASS" for item in t03_p1_check["checks"]
            )
            and not t03_p1_check.get("failures")
            and t03_p1_completion.get("p1_bias_five_point_substage_complete")
            is True
            and t03_p1_completion.get("complete_p1_bias_and_capacitance_group")
            is False
            and t03_p1_completion.get("capacitance_ratio_substage_permitted_next")
            is True
            and t03_p1_completion.get("complete_t03_five_group_sensitivity")
            is False
            and t03_p1_completion.get("experimental_calibration_permitted")
            is False
            and t03_p1_completion.get("physical_capacitance_ratio_claim_permitted")
            is False,
            (
                f"independent={t03_p1_check.get('status')} "
                f"completion={t03_p1_completion}"
            ),
        )
        t03_p1_output_paths = [
            ROOT / value
            for key, value in t03_p1_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        t03_p1_state_entries = t03_p1_report.get("state_outputs", [])
        t03_p1_state_paths = [
            ROOT / entry[key]
            for entry in t03_p1_state_entries
            for key in ("node_csv", "element_csv")
        ]
        t03_p1_vtk_paths = [
            ROOT / item["path"]
            for entry in t03_p1_state_entries
            for item in entry.get("vtk_files", [])
        ]
        t03_p1_figures = [
            ROOT / item["path"] for item in t03_p1_report.get("figures", [])
        ]
        t03_p1_run_directory = (
            ROOT / t03_p1_report.get("outputs", {}).get("run_directory", "")
        )
        add_check(
            checks,
            "t03_p1_bias:raw_outputs_and_figures_exist",
            len(t03_p1_state_entries) == 5
            and len(t03_p1_state_paths) == 10
            and len(t03_p1_vtk_paths) == 30
            and len(t03_p1_figures) == 2
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in t03_p1_output_paths
                + t03_p1_state_paths
                + t03_p1_vtk_paths
                + t03_p1_figures
                + [t03_p1_check_path]
            )
            and t03_p1_run_directory.is_dir(),
            (
                f"states={len(t03_p1_state_entries)} "
                f"state_csv={len(t03_p1_state_paths)} "
                f"vtk={len(t03_p1_vtk_paths)} figures={len(t03_p1_figures)}"
            ),
        )
        ratio = t03_p1_config.get("capacitance_ratio_control", {})
        prohibited = " ".join(
            t03_p1_report.get("evidence_boundary", {}).get(
                "prohibited_claims", []
            )
        )
        add_check(
            checks,
            "t03_p1_bias:fixed_ratio_is_not_complete_p1",
            t03_p1_config.get("scope", {}).get("changed_variable_count") == 1
            and t03_p1_config.get("scope", {}).get("changed_variable")
            == "fixed_bottom_gate_bias_v"
            and ratio.get("status") == "controlled_not_scanned"
            and ratio.get("fixed_top_to_bottom_ratio") == 1.0
            and "complete P1" in prohibited
            and "physical top-to-bottom capacitance ratio" in prohibited
            and "complete T03" in prohibited,
            (
                f"changed={t03_p1_config.get('scope', {}).get('changed_variable')} "
                f"ratio={ratio.get('fixed_top_to_bottom_ratio')}"
            ),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p1_bias:secondary_bias_sensitivity", False, str(error))

    t03_p1_ratio_config_path = (
        ROOT / "config" / "tcad_t03_p1_capacitance_ratio.json"
    )
    t03_p1_ratio_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p1_cap_ratio_input_contract.json"
    )
    t03_p1_ratio_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p1_cap_ratio_sensitivity.json"
    )
    t03_p1_ratio_check_path = (
        ROOT
        / "results"
        / "reports"
        / "tcad_t03_p1_cap_ratio_sensitivity_check.json"
    )
    try:
        t03_p1_ratio_config = json.loads(
            t03_p1_ratio_config_path.read_text(encoding="utf-8")
        )
        t03_p1_ratio_contract = json.loads(
            t03_p1_ratio_contract_path.read_text(encoding="utf-8")
        )
        t03_p1_ratio_report = json.loads(
            t03_p1_ratio_report_path.read_text(encoding="utf-8")
        )
        t03_p1_ratio_check = json.loads(
            t03_p1_ratio_check_path.read_text(encoding="utf-8")
        )
        t03_p1_ratio_runner_checks = t03_p1_ratio_report.get("checks", {})
        t03_p1_ratio_completion = t03_p1_ratio_report.get(
            "t03_p1_completion", {}
        )
        add_check(
            checks,
            "t03_p1_cap_ratio:contract_and_simulation",
            t03_p1_ratio_contract.get("contract_status") == "PASS"
            and t03_p1_ratio_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(t03_p1_ratio_contract.get("checks", [])) == 20
            and all(
                item.get("status") == "PASS"
                for item in t03_p1_ratio_contract["checks"]
            )
            and t03_p1_ratio_report.get("status") == "PASS"
            and t03_p1_ratio_report.get("case_id")
            == t03_p1_ratio_config.get("case_id")
            and t03_p1_ratio_report.get("stage") == "T03-P1-CAP-RATIO"
            and t03_p1_ratio_report.get("evidence_level") == "E2"
            and len(t03_p1_ratio_runner_checks) == 16
            and all(
                item.get("status") == "PASS"
                for item in t03_p1_ratio_runner_checks.values()
            )
            and not t03_p1_ratio_report.get("failures"),
            (
                f"contract={t03_p1_ratio_contract.get('contract_status')} "
                f"simulation={t03_p1_ratio_report.get('status')} "
                f"runner_checks={len(t03_p1_ratio_runner_checks)}"
            ),
        )
        add_check(
            checks,
            "t03_p1_cap_ratio:independent_check_and_numerical_p1_boundary",
            t03_p1_ratio_check.get("status") == "PASS"
            and t03_p1_ratio_check.get("case_id")
            == t03_p1_ratio_config.get("case_id")
            and t03_p1_ratio_check.get("stage") == "T03-P1-CAP-RATIO"
            and t03_p1_ratio_check.get("evidence_level") == "E3"
            and t03_p1_ratio_check.get("independent_of_simulation_runner") is True
            and len(t03_p1_ratio_check.get("checks", [])) == 13
            and all(
                item.get("status") == "PASS"
                for item in t03_p1_ratio_check["checks"]
            )
            and not t03_p1_ratio_check.get("failures")
            and t03_p1_ratio_completion.get(
                "p1_bias_five_point_substage_complete"
            )
            is True
            and t03_p1_ratio_completion.get(
                "p1_capacitance_ratio_five_point_substage_complete"
            )
            is True
            and t03_p1_ratio_completion.get("complete_p1_numerical_group")
            is True
            and t03_p1_ratio_completion.get(
                "complete_t03_five_group_sensitivity"
            )
            is False
            and t03_p1_ratio_completion.get("one_of_p2_p3_p5_permitted_next")
            is True
            and t03_p1_ratio_completion.get("experimental_calibration_permitted")
            is False
            and t03_p1_ratio_completion.get(
                "physical_capacitance_ratio_claim_permitted"
            )
            is False,
            (
                f"independent={t03_p1_ratio_check.get('status')} "
                f"completion={t03_p1_ratio_completion}"
            ),
        )
        ratio_encoding = t03_p1_ratio_config.get("ratio_encoding", {})
        ratio_points = ratio_encoding.get("points", [])
        ratio_scope = t03_p1_ratio_config.get("scope", {})
        ratio_boundary = " ".join(
            t03_p1_ratio_config.get("evidence_boundary", {}).get(
                "prohibited_claims", []
            )
        )
        add_check(
            checks,
            "t03_p1_cap_ratio:fixed_sum_encoding_and_p1_p4_ownership",
            ratio_scope.get("changed_variable_count") == 1
            and ratio_scope.get("changed_variable")
            == "effective_top_to_bottom_gate_capacitance_ratio"
            and [item.get("ratio") for item in ratio_points]
            == [0.5, 0.75, 1.0, 1.5, 2.0]
            and all(
                abs(
                    item.get("top_relative_permittivity", 0.0)
                    + item.get("bottom_relative_permittivity", 0.0)
                    - 13.6
                )
                <= 1e-12
                and abs(
                    item.get("top_relative_permittivity", 0.0)
                    / item.get("bottom_relative_permittivity", 1.0)
                    - item.get("ratio", 0.0)
                )
                <= 1e-12
                for item in ratio_points
            )
            and ratio_encoding.get("status")
            == "controlled_effective_coupling_proxy_not_material_measurement"
            and t03_p1_ratio_config.get("p1_p4_variable_ownership", {}).get(
                "boundary"
            )
            == "P4 owns physical geometry and common-mode dielectric changes; P1 owns only this fixed-sum differential coupling allocation."
            and "measured or physically extracted top-to-bottom capacitance ratio"
            in ratio_boundary
            and "complete T03 five-group sensitivity" in ratio_boundary,
            (
                f"ratios={[item.get('ratio') for item in ratio_points]} "
                f"sum={ratio_encoding.get('fixed_relative_permittivity_sum')}"
            ),
        )
        t03_p1_ratio_output_paths = [
            ROOT / value
            for key, value in t03_p1_ratio_report.get("outputs", {}).items()
            if key != "run_directory"
        ]
        t03_p1_ratio_state_entries = t03_p1_ratio_report.get(
            "state_outputs", []
        )
        t03_p1_ratio_state_paths = [
            ROOT / entry[key]
            for entry in t03_p1_ratio_state_entries
            for key in ("node_csv", "element_csv")
        ]
        t03_p1_ratio_vtk_paths = [
            ROOT / item["path"]
            for entry in t03_p1_ratio_state_entries
            for item in entry.get("vtk_files", [])
        ]
        t03_p1_ratio_figures = [
            ROOT / item["path"]
            for item in t03_p1_ratio_report.get("figures", [])
        ]
        t03_p1_ratio_run_directory = (
            ROOT / t03_p1_ratio_report.get("outputs", {}).get("run_directory", "")
        )
        ratio_summary = t03_p1_ratio_report.get("summary_metrics", {})
        add_check(
            checks,
            "t03_p1_cap_ratio:raw_outputs_and_figures_exist",
            ratio_summary.get("dc_solve_count") == 205
            and ratio_summary.get("reported_point_count") == 155
            and ratio_summary.get("state_count") == 5
            and len(t03_p1_ratio_state_entries) == 5
            and len(t03_p1_ratio_state_paths) == 10
            and len(t03_p1_ratio_vtk_paths) == 30
            and len(t03_p1_ratio_figures) == 2
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in t03_p1_ratio_output_paths
                + t03_p1_ratio_state_paths
                + t03_p1_ratio_vtk_paths
                + t03_p1_ratio_figures
                + [t03_p1_ratio_check_path]
            )
            and t03_p1_ratio_run_directory.is_dir(),
            (
                f"states={len(t03_p1_ratio_state_entries)} "
                f"state_csv={len(t03_p1_ratio_state_paths)} "
                f"vtk={len(t03_p1_ratio_vtk_paths)} "
                f"figures={len(t03_p1_ratio_figures)}"
            ),
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "t03_p1_cap_ratio:capacitance_ratio_sensitivity",
            False,
            str(error),
        )

    t03_p2_config_path = ROOT / "config" / "tcad_t03_p2_interface_trap.json"
    t03_p2_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_dit_input_contract.json"
    )
    t03_p2_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_dit_equation_smoke.json"
    )
    t03_p2_check_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_dit_equation_smoke_check.json"
    )
    try:
        t03_p2_config = json.loads(t03_p2_config_path.read_text(encoding="utf-8"))
        t03_p2_contract = json.loads(t03_p2_contract_path.read_text(encoding="utf-8"))
        t03_p2_report = json.loads(t03_p2_report_path.read_text(encoding="utf-8"))
        t03_p2_check = json.loads(t03_p2_check_path.read_text(encoding="utf-8"))
        t03_p2_runner_checks = t03_p2_report.get("checks", {})
        t03_p2_completion = t03_p2_report.get("t03_p2_completion", {})
        add_check(
            checks,
            "t03_p2_dit:contract_and_equation_smoke",
            t03_p2_contract.get("contract_status") == "PASS"
            and t03_p2_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and t03_p2_contract.get("evidence_level") == "E3"
            and len(t03_p2_contract.get("checks", [])) == 22
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_contract.get("checks", [])
            )
            and t03_p2_report.get("status") == "PASS"
            and t03_p2_report.get("case_id") == t03_p2_config.get("case_id")
            and t03_p2_report.get("stage") == "T03-P2-DIT-CONTRACT-SMOKE"
            and t03_p2_report.get("evidence_level") == "E2"
            and len(t03_p2_runner_checks) == 14
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_runner_checks.values()
            )
            and not t03_p2_report.get("failures"),
            (
                f"contract={t03_p2_contract.get('contract_status')} "
                f"smoke={t03_p2_report.get('status')} "
                f"runner_checks={len(t03_p2_runner_checks)}"
            ),
        )
        add_check(
            checks,
            "t03_p2_dit:independent_check_and_partial_boundary",
            t03_p2_check.get("status") == "PASS"
            and t03_p2_check.get("case_id") == t03_p2_config.get("case_id")
            and t03_p2_check.get("stage") == "T03-P2-DIT-CONTRACT-SMOKE"
            and t03_p2_check.get("evidence_level") == "E3"
            and t03_p2_check.get("independent_of_simulation_runner") is True
            and len(t03_p2_check.get("checks", [])) == 15
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_check.get("checks", [])
            )
            and not t03_p2_check.get("failures")
            and t03_p2_completion.get("status") == "PARTIAL"
            and t03_p2_completion.get("dit_literature_input_contract_passed") is True
            and t03_p2_completion.get("dit_interface_equation_smoke_passed") is True
            and t03_p2_completion.get("formal_three_point_dit_sensitivity_complete")
            is False
            and t03_p2_completion.get("bulk_tail_and_deep_traps_complete") is False
            and t03_p2_completion.get("complete_p2_trap_group") is False
            and t03_p2_completion.get("complete_t03_five_group_sensitivity") is False
            and t03_p2_completion.get(
                "formal_three_point_dit_sensitivity_permitted_next"
            )
            is True
            and t03_p2_completion.get("experimental_calibration_permitted") is False,
            (
                f"independent={t03_p2_check.get('status')} "
                f"completion={t03_p2_completion}"
            ),
        )
        t03_p2_artifacts = [
            ROOT / item["path"] for item in t03_p2_report.get("artifacts", {}).values()
        ]
        t03_p2_artifact_hashes_match = all(
            path.is_file()
            and path.stat().st_size > 0
            and t03_p2_report["artifacts"][name]["sha256"] == sha256(path)
            for name, path in (
                (name, ROOT / item["path"])
                for name, item in t03_p2_report.get("artifacts", {}).items()
            )
        )
        with (
            (ROOT / t03_p2_config["outputs"]["case_summary_csv"]).open(
                "r", encoding="utf-8", newline=""
            ) as case_stream,
            (ROOT / t03_p2_config["outputs"]["interface_samples_csv"]).open(
                "r", encoding="utf-8", newline=""
            ) as interface_stream,
            (ROOT / t03_p2_config["outputs"]["state_nodes_csv"]).open(
                "r", encoding="utf-8", newline=""
            ) as state_stream,
        ):
            t03_p2_cases = list(csv.DictReader(case_stream))
            t03_p2_interfaces = list(csv.DictReader(interface_stream))
            t03_p2_states = list(csv.DictReader(state_stream))
        t03_p2_resource = t03_p2_report.get("resource_usage", {})
        add_check(
            checks,
            "t03_p2_dit:persisted_outputs_counts_and_hashes",
            len(t03_p2_artifacts) == 5
            and t03_p2_artifact_hashes_match
            and len(t03_p2_cases) == 5
            and [row.get("case_id") for row in t03_p2_cases]
            == t03_p2_config["acceptance"]["required_case_ids"]
            and len(t03_p2_interfaces) == 195
            and len(t03_p2_states) == 12095
            and t03_p2_resource.get("device_count") == 5
            and t03_p2_resource.get("dc_solve_count") == 17
            and t03_p2_resource.get("state_node_row_count") == 12095
            and t03_p2_resource.get("interface_sample_row_count") == 195
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in t03_p2_artifacts
                + [t03_p2_contract_path, t03_p2_report_path, t03_p2_check_path]
            ),
            (
                f"cases={len(t03_p2_cases)} interfaces={len(t03_p2_interfaces)} "
                f"states={len(t03_p2_states)} dc={t03_p2_resource.get('dc_solve_count')}"
            ),
        )
        t03_p2_scope = t03_p2_config.get("scope", {})
        t03_p2_literature = t03_p2_config.get("literature_input", {})
        t03_p2_prohibited = " ".join(
            t03_p2_config.get("evidence_boundary", {}).get("prohibited_claims", [])
        )
        add_check(
            checks,
            "t03_p2_dit:single_interface_literature_range_and_closed_scan",
            t03_p2_scope.get("changed_variable_count") == 1
            and t03_p2_scope.get("active_interface") == "bottom_oxide_channel"
            and t03_p2_scope.get("inactive_interface") == "channel_top_oxide"
            and t03_p2_literature.get("source_evidence_level") == "E1"
            and t03_p2_literature.get("formal_sensitivity_values_cm2_ev")
            == [8.43e11, 3.07e12, 6.02e12]
            and t03_p2_report.get("formal_sensitivity_run") is False
            and "completed D_it sensitivity" in t03_p2_prohibited
            and "bulk N_tail" in t03_p2_prohibited
            and "complete T03" in t03_p2_prohibited,
            (
                f"active={t03_p2_scope.get('active_interface')} "
                f"future_points={t03_p2_literature.get('formal_sensitivity_values_cm2_ev')}"
            ),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p2_dit:equation_smoke", False, str(error))

    t03_p2_formal_config_path = ROOT / "config" / "tcad_t03_p2_dit_formal.json"
    t03_p2_formal_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_dit_formal_input_contract.json"
    )
    t03_p2_formal_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_dit_formal.json"
    )
    t03_p2_formal_check_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_dit_formal_check.json"
    )
    try:
        t03_p2_formal_config = json.loads(
            t03_p2_formal_config_path.read_text(encoding="utf-8")
        )
        t03_p2_formal_contract = json.loads(
            t03_p2_formal_contract_path.read_text(encoding="utf-8")
        )
        t03_p2_formal_report = json.loads(
            t03_p2_formal_report_path.read_text(encoding="utf-8")
        )
        t03_p2_formal_check = json.loads(
            t03_p2_formal_check_path.read_text(encoding="utf-8")
        )
        t03_p2_formal_runner_checks = t03_p2_formal_report.get("checks", {})
        add_check(
            checks,
            "t03_p2_dit_formal:contract_run_and_independent_check",
            t03_p2_formal_contract.get("contract_status") == "PASS"
            and t03_p2_formal_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and t03_p2_formal_contract.get("evidence_level") == "E3"
            and len(t03_p2_formal_contract.get("checks", [])) == 21
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_formal_contract.get("checks", [])
            )
            and t03_p2_formal_report.get("status") == "PASS"
            and t03_p2_formal_report.get("stage") == "T03-P2-DIT-FORMAL"
            and t03_p2_formal_report.get("case_id")
            == t03_p2_formal_config.get("case_id")
            and t03_p2_formal_report.get("evidence_level") == "E2"
            and len(t03_p2_formal_runner_checks) == 14
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_formal_runner_checks.values()
            )
            and not t03_p2_formal_report.get("failures")
            and t03_p2_formal_check.get("status") == "PASS"
            and t03_p2_formal_check.get("evidence_level") == "E3"
            and t03_p2_formal_check.get("independent_of_simulation_runner") is True
            and len(t03_p2_formal_check.get("checks", [])) == 16
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_formal_check.get("checks", [])
            )
            and not t03_p2_formal_check.get("failures"),
            (
                f"contract={t03_p2_formal_contract.get('contract_status')} "
                f"run={t03_p2_formal_report.get('status')} "
                f"independent={t03_p2_formal_check.get('status')}"
            ),
        )

        t03_p2_formal_artifact_paths = [
            ROOT / item["path"]
            for item in t03_p2_formal_report.get("artifacts", {}).values()
        ]
        t03_p2_formal_figure_paths = [
            ROOT / item["path"] for item in t03_p2_formal_report.get("figures", [])
        ]
        t03_p2_formal_artifact_hashes_match = all(
            path.is_file()
            and path.stat().st_size > 0
            and item.get("sha256") == sha256(path)
            for item in t03_p2_formal_report.get("artifacts", {}).values()
            for path in [ROOT / item["path"]]
        ) and all(
            path.is_file()
            and path.stat().st_size > 0
            and item.get("sha256") == sha256(path)
            for item in t03_p2_formal_report.get("figures", [])
            for path in [ROOT / item["path"]]
        )
        with (
            (ROOT / t03_p2_formal_config["outputs"]["curve_csv"]).open(
                "r", encoding="utf-8", newline=""
            ) as curve_stream,
            (ROOT / t03_p2_formal_config["outputs"]["metric_csv"]).open(
                "r", encoding="utf-8", newline=""
            ) as metric_stream,
            (ROOT / t03_p2_formal_config["outputs"]["state_summary_csv"]).open(
                "r", encoding="utf-8", newline=""
            ) as state_stream,
        ):
            t03_p2_formal_curves = list(csv.DictReader(curve_stream))
            t03_p2_formal_metrics = list(csv.DictReader(metric_stream))
            t03_p2_formal_states = list(csv.DictReader(state_stream))
        t03_p2_formal_manifest = json.loads(
            (ROOT / t03_p2_formal_config["outputs"]["state_manifest"]).read_text(
                encoding="utf-8"
            )
        )
        t03_p2_formal_state_paths = [
            ROOT / entry[key]
            for entry in t03_p2_formal_manifest.get("entries", [])
            for key in ("node_csv", "element_csv")
        ]
        t03_p2_formal_vtk_paths = [
            ROOT / item["path"]
            for entry in t03_p2_formal_manifest.get("entries", [])
            for item in entry.get("vtk_files", [])
        ]
        t03_p2_formal_summary = t03_p2_formal_report.get("summary_metrics", {})
        add_check(
            checks,
            "t03_p2_dit_formal:persisted_counts_hashes_states_and_figures",
            t03_p2_formal_summary.get("device_count") == 4
            and t03_p2_formal_summary.get("dc_solve_count") == 164
            and t03_p2_formal_summary.get("reported_point_count") == 124
            and t03_p2_formal_summary.get("state_count") == 4
            and len(t03_p2_formal_curves) == 124
            and len(t03_p2_formal_metrics) == 4
            and len(t03_p2_formal_states) == 4
            and t03_p2_formal_manifest.get("entry_count") == 4
            and len(t03_p2_formal_state_paths) == 8
            and len(t03_p2_formal_vtk_paths) == 24
            and len(t03_p2_formal_artifact_paths) == 7
            and len(t03_p2_formal_figure_paths) == 2
            and t03_p2_formal_artifact_hashes_match
            and all(
                path.is_file() and path.stat().st_size > 0
                for path in t03_p2_formal_state_paths + t03_p2_formal_vtk_paths
            ),
            (
                f"curves={len(t03_p2_formal_curves)} metrics={len(t03_p2_formal_metrics)} "
                f"states={len(t03_p2_formal_states)} vtk={len(t03_p2_formal_vtk_paths)}"
            ),
        )

        t03_p2_formal_dit = [
            float(row["dit_cm2_ev"]) for row in t03_p2_formal_metrics
        ]
        t03_p2_formal_vth = [
            float(row["vth_proxy_v"]) for row in t03_p2_formal_metrics
        ]
        t03_p2_formal_ss = [
            float(row["ss_proxy_mv_per_dec"]) for row in t03_p2_formal_metrics
        ]
        t03_p2_formal_ioff = [
            float(row["ioff_proxy_a_per_cm"]) for row in t03_p2_formal_metrics
        ]
        t03_p2_formal_gm = [
            float(row["gm_proxy_s_per_cm"]) for row in t03_p2_formal_metrics
        ]
        t03_p2_formal_ss_r2 = [
            float(row["ss_fit_r_squared"]) for row in t03_p2_formal_metrics
        ]
        add_check(
            checks,
            "t03_p2_dit_formal:controlled_grid_proxies_and_t02_c_regression",
            t03_p2_formal_dit == [0.0, 8.43e11, 3.07e12, 6.02e12]
            and all(a < b for a, b in zip(t03_p2_formal_vth, t03_p2_formal_vth[1:]))
            and all(a < b for a, b in zip(t03_p2_formal_ss, t03_p2_formal_ss[1:]))
            and all(a < b for a, b in zip(t03_p2_formal_ioff, t03_p2_formal_ioff[1:]))
            and all(a > b for a, b in zip(t03_p2_formal_gm, t03_p2_formal_gm[1:]))
            and min(t03_p2_formal_ss_r2) >= 0.98
            and t03_p2_formal_report.get("zero_dit_t02_c_reproduction")
            == {
                "point_count": 31,
                "maximum_current_relative_difference": 0.0,
                "maximum_center_potential_difference_v": 0.0,
                "maximum_center_density_relative_difference": 0.0,
                "vth_difference_v": 0.0,
                "gm_relative_difference": 0.0,
            },
            (
                f"VTH={t03_p2_formal_vth} SS={t03_p2_formal_ss} "
                f"I_low={t03_p2_formal_ioff} gm={t03_p2_formal_gm}"
            ),
        )

        t03_p2_formal_completion = t03_p2_formal_report.get(
            "t03_p2_completion", {}
        )
        t03_p2_formal_failure_paths = [
            ROOT / "results/reports/tcad_t03_p2_dit_formal_v1_failed.json",
            ROOT
            / "results/reports/tcad_t03_p2_dit_formal_input_contract_v1_ss_linearity_failed.json",
            ROOT
            / "results/reports/tcad_t03_p2_dit_formal_v1_ss_linearity_failed.json",
            ROOT / "results/tcad/t03_sensitivity/p2_dit_formal_v1_failed",
            ROOT
            / "results/tcad/t03_sensitivity/p2_dit_formal_v1_ss_linearity_failed",
            ROOT
            / "report/assets/tcad_t03_p2_dit_formal_sensitivity_v1_ss_linearity_failed.png",
            ROOT
            / "report/assets/tcad_t03_p2_dit_formal_states_v1_ss_linearity_failed.png",
        ]
        add_check(
            checks,
            "t03_p2_dit_formal:failure_history_and_partial_p2_boundary",
            all(path.exists() for path in t03_p2_formal_failure_paths)
            and t03_p2_formal_completion.get("status") == "PARTIAL"
            and t03_p2_formal_completion.get(
                "formal_three_point_dit_sensitivity_complete"
            )
            is True
            and t03_p2_formal_completion.get("interface_dit_substage_complete") is True
            and t03_p2_formal_completion.get("bulk_tail_and_deep_traps_complete")
            is False
            and t03_p2_formal_completion.get("complete_p2_trap_group") is False
            and t03_p2_formal_completion.get(
                "complete_t03_five_group_sensitivity"
            )
            is False
            and t03_p2_formal_completion.get("bulk_trap_contract_permitted_next")
            is True
            and t03_p2_formal_completion.get("experimental_calibration_permitted")
            is False,
            f"completion={t03_p2_formal_completion}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p2_dit_formal:formal_sensitivity", False, str(error))

    t03_p2_bulk_config_path = ROOT / "config" / "tcad_t03_p2_bulk_traps.json"
    t03_p2_bulk_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_bulk_traps_input_contract.json"
    )
    t03_p2_bulk_source_path = ROOT / "references" / "t03_p2_bulk_trap_sources.csv"
    try:
        t03_p2_bulk_config = json.loads(
            t03_p2_bulk_config_path.read_text(encoding="utf-8")
        )
        t03_p2_bulk_contract = json.loads(
            t03_p2_bulk_contract_path.read_text(encoding="utf-8")
        )
        with t03_p2_bulk_source_path.open(
            "r", encoding="utf-8", newline=""
        ) as source_stream:
            t03_p2_bulk_sources = list(csv.DictReader(source_stream))
        add_check(
            checks,
            "t03_p2_bulk_traps:static_contract_only",
            t03_p2_bulk_config.get("case_id")
            == "IGZO_T03_P2_BULK_TRAPS_CONTRACT_V1"
            and t03_p2_bulk_config.get("stage")
            == "T03-P2-BULK-TRAPS-CONTRACT"
            and t03_p2_bulk_contract.get("contract_status") == "PASS"
            and t03_p2_bulk_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and t03_p2_bulk_contract.get("evidence_level") == "E3"
            and len(t03_p2_bulk_contract.get("checks", [])) == 30
            and all(
                item.get("status") == "PASS"
                for item in t03_p2_bulk_contract.get("checks", [])
            )
            and not t03_p2_bulk_contract.get("failures")
            and t03_p2_bulk_contract.get("config", {}).get("sha256")
            == sha256(t03_p2_bulk_config_path),
            (
                f"contract={t03_p2_bulk_contract.get('contract_status')} "
                f"simulation={t03_p2_bulk_contract.get('simulation_status')} "
                f"checks={len(t03_p2_bulk_contract.get('checks', []))}"
            ),
        )
        literature = t03_p2_bulk_config.get("literature_input", {})
        tail = literature.get("tail", {})
        deep = literature.get("deep", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:source_equations_points_and_integration",
            len(t03_p2_bulk_sources) == 2
            and {row.get("parameter_symbol") for row in t03_p2_bulk_sources}
            == {"NTA", "NGA"}
            and all(row.get("doi") == literature.get("doi") for row in t03_p2_bulk_sources)
            and tail.get("formal_sensitivity_values_cm3_ev")
            == [1e18, 5e18, 5e19]
            and deep.get("formal_sensitivity_values_cm3_ev")
            == [1e16, 5e16, 5e17]
            and t03_p2_bulk_config.get("energy_integration", {}).get("order") == 96
            and t03_p2_bulk_contract.get("maximum_integration_relative_error", 1.0)
            <= t03_p2_bulk_config["energy_integration"][
                "maximum_relative_error_vs_reference"
            ],
            (
                f"sources={len(t03_p2_bulk_sources)} "
                f"tail={tail.get('formal_sensitivity_values_cm3_ev')} "
                f"deep={deep.get('formal_sensitivity_values_cm3_ev')} "
                f"integration_error={t03_p2_bulk_contract.get('maximum_integration_relative_error')}"
            ),
        )
        boundary = t03_p2_bulk_config.get("evidence_boundary", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:equation_smoke_is_next_and_p2_remains_partial",
            t03_p2_bulk_contract.get("planned_next_equation_smoke", {}).get(
                "simulation_run"
            )
            is False
            and t03_p2_bulk_contract.get("planned_future_sensitivity", {}).get(
                "formal_scan_run"
            )
            is False
            and "Only this contract PASS permits" in boundary.get("next_gate", "")
            and "P2 or T03 has completed"
            in " ".join(boundary.get("prohibited_claims", [])),
            boundary.get("next_gate", ""),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p2_bulk_traps:contract", False, str(error))

    t03_p2_bulk_smoke_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_bulk_traps_equation_smoke.json"
    )
    t03_p2_bulk_smoke_check_path = (
        ROOT / "results" / "reports" / "tcad_t03_p2_bulk_traps_equation_smoke_check.json"
    )
    try:
        t03_p2_bulk_smoke_report = json.loads(
            t03_p2_bulk_smoke_report_path.read_text(encoding="utf-8")
        )
        t03_p2_bulk_smoke_check = json.loads(
            t03_p2_bulk_smoke_check_path.read_text(encoding="utf-8")
        )
        smoke_config = t03_p2_bulk_config.get("next_equation_smoke", {})
        smoke_resource_usage = t03_p2_bulk_smoke_report.get("resource_usage", {})
        smoke_checks = t03_p2_bulk_smoke_report.get("checks", [])
        independent_checks = t03_p2_bulk_smoke_check.get("checks", [])
        add_check(
            checks,
            "t03_p2_bulk_traps:equation_smoke_evidence",
            t03_p2_bulk_smoke_report.get("status") == "PASS"
            and t03_p2_bulk_smoke_report.get("case_id") == smoke_config.get("case_id")
            and t03_p2_bulk_smoke_report.get("stage") == smoke_config.get("stage")
            and t03_p2_bulk_smoke_report.get("evidence_level") == "E2"
            and t03_p2_bulk_smoke_report.get("formal_sensitivity_run") is False
            and len(t03_p2_bulk_smoke_report.get("case_summaries", [])) == 3
            and smoke_resource_usage.get("device_count") == 3
            and smoke_resource_usage.get("dc_solve_count") == 21
            and smoke_resource_usage.get("state_node_row_count") == 7257
            and smoke_resource_usage.get("integration_sample_row_count") == 6
            and all(item.get("status") == "PASS" for item in smoke_checks.values())
            and not t03_p2_bulk_smoke_report.get("failures")
            and t03_p2_bulk_smoke_report.get("contract_report", {}).get("sha256")
            == sha256(t03_p2_bulk_contract_path)
            and t03_p2_bulk_smoke_check.get("status") == "PASS"
            and t03_p2_bulk_smoke_check.get("evidence_level") == "E3"
            and t03_p2_bulk_smoke_check.get("independent_of_simulation_runner") is True
            and len(independent_checks) == 16
            and all(item.get("status") == "PASS" for item in independent_checks)
            and not t03_p2_bulk_smoke_check.get("failures"),
            (
                f"runner={t03_p2_bulk_smoke_report.get('status')} "
                f"independent={t03_p2_bulk_smoke_check.get('status')} "
                f"devices={smoke_resource_usage.get('device_count')} "
                f"solves={smoke_resource_usage.get('dc_solve_count')}"
            ),
        )
        smoke_boundary = t03_p2_bulk_smoke_report.get("evidence_boundary", {})
        smoke_completion = t03_p2_bulk_smoke_report.get("t03_p2_completion", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:equation_smoke_boundary",
            smoke_completion.get("bulk_trap_equation_smoke_passed") is True
            and smoke_completion.get("bulk_tail_and_deep_traps_complete") is False
            and smoke_completion.get("formal_bulk_sensitivity_complete") is False
            and smoke_completion.get("complete_p2_trap_group") is False
            and smoke_completion.get("complete_t03_five_group_sensitivity") is False
            and "formal NTA or NGA transfer sensitivity has completed"
            in smoke_boundary.get("prohibited_claims", [])
            and "P2 or T03 has completed" in smoke_boundary.get("prohibited_claims", [])
            and "Only a passed equation smoke" in smoke_boundary.get("next_gate", ""),
            smoke_boundary.get("next_gate", ""),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p2_bulk_traps:equation_smoke", False, str(error))

    t03_p2_bulk_formal_config_path = (
        ROOT / "config" / "tcad_t03_p2_bulk_traps_formal.json"
    )
    t03_p2_bulk_formal_contract_path = (
        ROOT
        / "results"
        / "reports"
        / "tcad_t03_p2_bulk_traps_formal_input_contract_v3.json"
    )
    try:
        t03_p2_bulk_formal_config = json.loads(
            t03_p2_bulk_formal_config_path.read_text(encoding="utf-8")
        )
        t03_p2_bulk_formal_contract = json.loads(
            t03_p2_bulk_formal_contract_path.read_text(encoding="utf-8")
        )
        formal_checks = t03_p2_bulk_formal_contract.get("checks", [])
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_contract_evidence",
            t03_p2_bulk_formal_contract.get("status") == "PASS"
            and t03_p2_bulk_formal_contract.get("contract_status") == "PASS"
            and t03_p2_bulk_formal_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and t03_p2_bulk_formal_contract.get("case_id")
            == "IGZO_T03_P2_BULK_TRAPS_FORMAL_V3"
            and t03_p2_bulk_formal_contract.get("stage")
            == "T03-P2-BULK-TRAPS-FORMAL"
            and t03_p2_bulk_formal_contract.get("evidence_level") == "E3"
            and t03_p2_bulk_formal_contract.get("config", {}).get("sha256")
            == sha256(t03_p2_bulk_formal_config_path)
            and len(formal_checks) == 24
            and all(item.get("status") == "PASS" for item in formal_checks)
            and not t03_p2_bulk_formal_contract.get("failures"),
            (
                f"status={t03_p2_bulk_formal_contract.get('status')} "
                f"simulation={t03_p2_bulk_formal_contract.get('simulation_status')} "
                f"checks={len(formal_checks)}"
            ),
        )
        planned_formal = t03_p2_bulk_formal_contract.get(
            "planned_formal_sensitivity", {}
        )
        formal_budget = t03_p2_bulk_formal_config.get("resource_budget", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_contract_frozen_counts",
            planned_formal.get("families")
            == {
                "NTA": [0.0, 1e18, 5e18, 5e19],
                "NGA": [0.0, 1e16, 5e16, 5e17],
            }
            and planned_formal.get("device_count") == 8
            and planned_formal.get("reported_point_count") == 376
            and planned_formal.get("dc_solve_count") == 456
            and planned_formal.get("state_count") == 8
            and planned_formal.get("formal_sensitivity_run") is False
            and formal_budget.get("required_total_device_count") == 8
            and formal_budget.get("required_total_reported_point_count") == 376
            and formal_budget.get("required_total_dc_solve_count") == 456,
            (
                f"devices={planned_formal.get('device_count')} "
                f"points={planned_formal.get('reported_point_count')} "
                f"solves={planned_formal.get('dc_solve_count')} "
                f"states={planned_formal.get('state_count')}"
            ),
        )
        formal_boundary = t03_p2_bulk_formal_contract.get("evidence_boundary", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_contract_boundary",
            "without running DEVSIM"
            in formal_boundary.get("allowed_claim_after_contract_pass", "")
            and any(
                "the formal NTA/NGA transfer sensitivity passed before both" in claim
                for claim in formal_boundary.get("prohibited_claims", [])
            )
            and any(
                "P2, T03" in claim
                for claim in formal_boundary.get("prohibited_claims", [])
            )
            and "Only this V3 formal contract PASS permits"
            in formal_boundary.get("next_gate", "")
            and t03_p2_bulk_formal_config.get("status") == "planned",
            formal_boundary.get("next_gate", ""),
        )
        v1_config_path = (
            ROOT / "config/tcad_t03_p2_bulk_traps_formal_v1_failed.json"
        )
        v1_contract = json.loads(
            (
                ROOT
                / "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract.json"
            ).read_text(encoding="utf-8")
        )
        v1_report = json.loads(
            (
                ROOT
                / "results/reports/tcad_t03_p2_bulk_traps_formal_v1_runner_completed_without_exception.json"
            ).read_text(encoding="utf-8")
        )
        v1_archive_dir = (
            ROOT
            / "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v1_runner_completed_without_exception"
        )
        v1_archive = json.loads(
            (v1_archive_dir / "failure_archive_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        v1_snapshot = json.loads(
            (v1_archive_dir / "input_snapshot.json").read_text(encoding="utf-8")
        )
        v1_state_manifest = json.loads(
            (v1_archive_dir / "state_manifest.json").read_text(encoding="utf-8")
        )
        with (
            v1_archive_dir
            / "external_artifacts/tcad_t03_p2_bulk_traps_formal_transfer.csv"
        ).open("r", encoding="utf-8", newline="") as stream:
            v1_curve_rows = list(csv.DictReader(stream))
        v1_high_rows = [
            row
            for row in v1_curve_rows
            if row["bulk_family_id"] == "NTA"
            and float(row["bulk_value_cm3_ev"]) == 5e19
        ]
        v1_entries = v1_state_manifest.get("entries", [])
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_v1_failure_inputs_and_outputs_preserved",
            v1_contract.get("contract_status") == "PASS"
            and v1_contract.get("config", {}).get("sha256")
            == sha256(v1_config_path)
            and v1_report.get("status") == "FAIL"
            and v1_report.get("evidence_level") == "E0"
            and v1_report.get("formal_sensitivity_run") is False
            and v1_report.get("summary_metrics", {}).get("device_count") == 8
            and v1_report.get("summary_metrics", {}).get("dc_solve_count") == 328
            and v1_report.get("summary_metrics", {}).get("reported_point_count")
            == 248
            and v1_archive.get("status") == "FAIL_PRESERVED"
            and v1_archive.get("failed_gate")
            == "runner_completed_without_exception"
            and v1_snapshot.get("inputs", {}).get("runner_script", {}).get(
                "sha256"
            )
            == sha256(ROOT / "tcad/run_t03_p2_bulk_traps_formal_v1_failed.py")
            and len(v1_curve_rows) == 248
            and len(v1_high_rows) == 31
            and max(abs(float(row["drain_current_a_per_cm"])) for row in v1_high_rows)
            < 1e-5
            and v1_state_manifest.get("entry_count") == 8
            and len(v1_entries) == 8
            and sum(int(entry.get("vtk_file_count", 0)) for entry in v1_entries)
            == 48
            and all(
                (ROOT / entry["node_csv"]).is_file()
                and (ROOT / entry["element_csv"]).is_file()
                and (ROOT / entry["bulk_node_csv"]).is_file()
                for entry in v1_entries
            ),
            (
                f"report={v1_report.get('status')} rows={len(v1_curve_rows)} "
                f"states={len(v1_entries)} vtk="
                f"{sum(int(entry.get('vtk_file_count', 0)) for entry in v1_entries)}"
            ),
        )
        v2_config_path = (
            ROOT / "config/tcad_t03_p2_bulk_traps_formal_v2_failed.json"
        )
        v2_contract = json.loads(
            (
                ROOT
                / "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v2.json"
            ).read_text(encoding="utf-8")
        )
        v2_report_path = (
            ROOT / "results/reports/tcad_t03_p2_bulk_traps_formal_v2.json"
        )
        v2_report = json.loads(v2_report_path.read_text(encoding="utf-8"))
        v2_archive_dir = (
            ROOT
            / "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v2_runner_completed_without_exception"
        )
        v2_archive = json.loads(
            (v2_archive_dir / "failure_archive_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        v2_snapshot = json.loads(
            (v2_archive_dir / "input_snapshot.json").read_text(encoding="utf-8")
        )
        v2_solver_log = json.loads(
            (v2_archive_dir / "solver_log.json").read_text(encoding="utf-8")
        )
        v2_state_manifest = json.loads(
            (v2_archive_dir / "state_manifest.json").read_text(encoding="utf-8")
        )
        with (
            v2_archive_dir
            / "external_artifacts/tcad_t03_p2_bulk_traps_formal_v2_transfer.csv"
        ).open("r", encoding="utf-8", newline="") as stream:
            v2_curve_rows = list(csv.DictReader(stream))
        v2_high_rows = sorted(
            (
                row
                for row in v2_curve_rows
                if row["bulk_family_id"] == "NTA"
                and float(row["bulk_value_cm3_ev"]) == 5e19
            ),
            key=lambda row: float(row["primary_gate_v"]),
        )
        v2_criterion = 1e-5
        v2_brackets = [
            (lower, upper)
            for lower, upper in zip(v2_high_rows, v2_high_rows[1:])
            if abs(float(lower["drain_current_a_per_cm"]))
            < v2_criterion
            < abs(float(upper["drain_current_a_per_cm"]))
        ]
        v2_vth = math.nan
        if len(v2_brackets) == 1:
            lower, upper = v2_brackets[0]
            lower_current = abs(float(lower["drain_current_a_per_cm"]))
            upper_current = abs(float(upper["drain_current_a_per_cm"]))
            lower_voltage = float(lower["primary_gate_v"])
            upper_voltage = float(upper["primary_gate_v"])
            v2_vth = lower_voltage + (
                (math.log10(v2_criterion) - math.log10(lower_current))
                * (upper_voltage - lower_voltage)
                / (math.log10(upper_current) - math.log10(lower_current))
            )
        v2_entries = v2_state_manifest.get("entries", [])
        v2_runner_detail = v2_report.get("checks", {}).get(
            "runner_completed_without_exception", {}
        ).get("detail", "")
        v2_solver_records = [
            record
            for run in v2_solver_log.get("runs", [])
            for record in run.get("solver_records", [])
        ]
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_v2_extraction_grid_failure_preserved",
            v2_report.get("status") == "FAIL"
            and v2_contract.get("contract_status") == "PASS"
            and v2_contract.get("config", {}).get("sha256")
            == sha256(v2_config_path)
            and v2_report.get("evidence_level") == "E0"
            and v2_report.get("formal_sensitivity_run") is False
            and v2_report.get("independent_persisted_evidence_check_complete")
            is False
            and v2_report.get("summary_metrics", {}).get("device_count") == 8
            and v2_report.get("summary_metrics", {}).get("dc_solve_count") == 440
            and v2_report.get("summary_metrics", {}).get("reported_point_count")
            == 360
            and v2_report.get("summary_metrics", {}).get("state_count") == 8
            and v2_report.get("summary_metrics", {}).get("vtk_file_count") == 48
            and v2_archive.get("status") == "FAIL_PRESERVED"
            and v2_archive.get("failed_gate")
            == "runner_completed_without_exception"
            and v2_snapshot.get("inputs", {}).get("formal_config", {}).get(
                "sha256"
            )
            == sha256(v2_config_path)
            and v2_snapshot.get("inputs", {}).get("runner_script", {}).get(
                "sha256"
            )
            == sha256(ROOT / "tcad/run_t03_p2_bulk_traps_formal_v2_failed.py")
            and len(v2_solver_log.get("runs", [])) == 8
            and len(v2_solver_records) == 440
            and all(record.get("converged") is True for record in v2_solver_records)
            and len(v2_curve_rows) == 360
            and len(v2_high_rows) == 45
            and len(v2_brackets) == 1
            and math.isclose(v2_vth, 1.466667576519075, rel_tol=1e-12)
            and math.isclose(
                max(
                    abs(float(row["drain_current_a_per_cm"]))
                    for row in v2_high_rows
                ),
                1.4190074297322551e-5,
                rel_tol=1e-12,
            )
            and "gm evaluation voltage 1.666667576519075 is outside the central-difference grid"
            in v2_runner_detail
            and v2_state_manifest.get("entry_count") == 8
            and len(v2_entries) == 8
            and sum(int(entry.get("vtk_file_count", 0)) for entry in v2_entries)
            == 48
            and all(
                (ROOT / entry["node_csv"]).is_file()
                and (ROOT / entry["element_csv"]).is_file()
                and (ROOT / entry["bulk_node_csv"]).is_file()
                for entry in v2_entries
            )
            and not (
                ROOT
                / "results/reports/tcad_t03_p2_bulk_traps_formal_v2_check.json"
            ).exists(),
            (
                f"report={v2_report.get('status')} records={len(v2_solver_records)} "
                f"rows={len(v2_curve_rows)} states={len(v2_entries)} "
                f"vth={v2_vth:.12f} gm_eval={v2_vth + 0.2:.12f}"
            ),
        )
        v3_contract_checker_failure = json.loads(
            (
                ROOT
                / "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v3_checker_v2_curve_loader_bug_failed.json"
            ).read_text(encoding="utf-8")
        )
        add_check(
            checks,
            "t03_p2_bulk_traps:v3_contract_checker_csv_loader_bug_preserved",
            v3_contract_checker_failure.get("status") == "FAIL"
            and v3_contract_checker_failure.get("failure_class")
            == "contract_checker_input_loader_bug"
            and v3_contract_checker_failure.get("error_type")
            == "JSONDecodeError"
            and v3_contract_checker_failure.get("simulation_run") is False
            and v3_contract_checker_failure.get("contract_assertions_evaluated")
            is False
            and v3_contract_checker_failure.get("acceptance_thresholds_changed")
            is False
            and v3_contract_checker_failure.get("physical_inputs_changed") is False
            and "v2_curve_csv" in v3_contract_checker_failure.get(
                "error_detail", ""
            ),
            v3_contract_checker_failure.get("error_detail", ""),
        )
        archived_boundary_failure = json.loads(
            (
                ROOT
                / "results"
                / "reports"
                / "project_check_t03_p2_bulk_formal_boundary_checker_bug_failed.json"
            ).read_text(encoding="utf-8")
        )
        archived_failed_checks = [
            item
            for item in archived_boundary_failure.get("results", [])
            if item.get("status") == "FAIL"
        ]
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_contract_checker_failure_preserved",
            archived_boundary_failure.get("status") == "FAIL"
            and archived_boundary_failure.get("checks") == 420
            and archived_boundary_failure.get("failures") == 1
            and len(archived_failed_checks) == 1
            and archived_failed_checks[0].get("name")
            == "t03_p2_bulk_traps:formal_contract_boundary",
            (
                f"status={archived_boundary_failure.get('status')} "
                f"checks={archived_boundary_failure.get('checks')} "
                f"failures={len(archived_failed_checks)}"
            ),
        )
        archived_math_import_failure = json.loads(
            (
                ROOT
                / "results"
                / "reports"
                / "project_check_t03_p2_bulk_v2_failure_checker_math_import_bug_failed.json"
            ).read_text(encoding="utf-8")
        )
        archived_math_failed_checks = [
            item
            for item in archived_math_import_failure.get("results", [])
            if item.get("status") == "FAIL"
        ]
        add_check(
            checks,
            "t03_p2_bulk_traps:v2_failure_checker_math_import_bug_preserved",
            archived_math_import_failure.get("status") == "FAIL"
            and archived_math_import_failure.get("checks") == 441
            and archived_math_import_failure.get("failures") == 1
            and len(archived_math_failed_checks) == 1
            and archived_math_failed_checks[0].get("name")
            == "t03_p2_bulk_traps:formal_contract"
            and archived_math_failed_checks[0].get("detail")
            == "name 'math' is not defined",
            (
                f"status={archived_math_import_failure.get('status')} "
                f"checks={archived_math_import_failure.get('checks')} "
                f"failures={len(archived_math_failed_checks)}"
            ),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p2_bulk_traps:formal_contract", False, str(error))

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
