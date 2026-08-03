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

from m01_xyce_r06_common import digest_tree as digest_r06_tree
from m01_xyce_r07_common import digest_tree as digest_r07_tree
from m01_xyce_r08_common import digest_tree as digest_r08_tree
from m01_xyce_r09_common import digest_tree as digest_r09_tree
from m01_xyce_r10_common import digest_tree as digest_r10_tree


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
    "results/reports/tcad_t03_p2_bulk_traps_formal_v3.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_v3_check.json",
    "results/reports/project_check_t03_p2_bulk_formal_boundary_checker_bug_failed.json",
    "results/reports/project_check_t03_p2_bulk_v2_failure_checker_math_import_bug_failed.json",
    "results/reports/tcad_t03_p2_bulk_traps_formal_input_contract_v3_checker_v2_curve_loader_bug_failed.json",
    "results/tables/tcad_t03_p2_bulk_traps_equation_smoke_cases.csv",
    "results/tables/tcad_t03_p2_bulk_traps_integration_samples.csv",
    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_transfer.csv",
    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_metrics.csv",
    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_zero_control_comparison.csv",
    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_state_summary.csv",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/input_snapshot.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/solver_log.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_equation_smoke/state_nodes.csv",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/input_snapshot.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/solver_log.json",
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/state_manifest.json",
    "report/assets/tcad_t03_p2_bulk_traps_formal_v3_sensitivity.png",
    "report/assets/tcad_t03_p2_bulk_traps_formal_v3_states.png",
    "references/t03_p3_contact_sources.csv",
    "config/tcad_t03_p3_contact_resistance.json",
    "config/tcad_t03_p3_contact_resistance_v1_failed.json",
    "scripts/check_t03_p3_contact_contract.py",
    "scripts/check_t03_p3_contact_contract_v1.py",
    "scripts/check_t03_p3_contact_resistance.py",
    "tcad/run_t03_p3_contact_resistance.py",
    "tcad/run_t03_p3_contact_resistance_v1_failed.py",
    "results/reports/tcad_t03_p3_contact_input_contract.json",
    "results/reports/tcad_t03_p3_contact_input_contract_v1.json",
    "results/reports/tcad_t03_p3_contact_input_contract_v2.json",
    "results/reports/tcad_t03_p3_contact_input_contract_v1_checker_initial_assertions_failed.json",
    "results/reports/tcad_t03_p3_contact_resistance.json",
    "results/reports/tcad_t03_p3_contact_resistance_device_terminal_current_conservation.json",
    "results/reports/tcad_t03_p3_contact_resistance_v2.json",
    "results/reports/tcad_t03_p3_contact_resistance_v2_check.json",
    "results/reports/report_check_t03_p3_v1_appendix_image_path_failed.json",
    "results/tables/tcad_t03_p3_contact_transfer.csv",
    "results/tables/tcad_t03_p3_contact_output.csv",
    "results/tables/tcad_t03_p3_contact_metrics.csv",
    "results/tables/tcad_t03_p3_contact_circuit_balance.csv",
    "results/tables/tcad_t03_p3_contact_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p3_contact_state_summary.csv",
    "results/tables/tcad_t03_p3_contact_v2_transfer.csv",
    "results/tables/tcad_t03_p3_contact_v2_output.csv",
    "results/tables/tcad_t03_p3_contact_v2_metrics.csv",
    "results/tables/tcad_t03_p3_contact_v2_circuit_balance.csv",
    "results/tables/tcad_t03_p3_contact_v2_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p3_contact_v2_state_summary.csv",
    "results/tcad/t03_sensitivity/p3_contact_resistance/input_snapshot.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance/solver_log.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance/state_manifest.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance_v2/input_snapshot.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance_v2/solver_log.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance_v2/state_manifest.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance_device_terminal_current_conservation/failure_archive_manifest.json",
    "results/tcad/t03_sensitivity/p3_contact_resistance_device_terminal_current_conservation/failure_archive_supplement.json",
    "report/assets/tcad_t03_p3_contact_sensitivity.png",
    "report/assets/tcad_t03_p3_contact_states.png",
    "report/assets/tcad_t03_p3_contact_v2_sensitivity.png",
    "report/assets/tcad_t03_p3_contact_v2_states.png",
    "references/t03_p5_temperature_sources.csv",
    "config/tcad_t03_p5_temperature.json",
    "scripts/check_t03_p5_temperature_contract.py",
    "config/compact_m00_input_validation.json",
    "config/compact_m00_input_validation_r02.json",
    "references/m00_dataset_registry.csv",
    "scripts/check_m00_compact_model_contract.py",
    "scripts/check_m00_compact_model_contract_r02.py",
    "models/fit_m00_teaching_compact.py",
    "scripts/check_m00_compact_model_fit.py",
    "models/fit_m00_teaching_compact_r02.py",
    "scripts/check_m00_compact_model_fit_r02.py",
    "results/reports/m00_compact_model_input_contract.json",
    "results/reports/m00_compact_model_input_contract_r02.json",
    "results/reports/m00_compact_model_input_contract_dependency_status_mismatch_failed.json",
    "results/compact/m00_teaching_fit_r01/input_snapshot.json",
    "results/compact/m00_teaching_fit_r01/selected_rows_manifest.csv",
    "results/compact/m00_teaching_fit_r01/optimizer_log.json",
    "results/tables/m00_compact_model_predictions.csv",
    "results/tables/m00_compact_model_curve_metrics.csv",
    "results/tables/m00_compact_model_parameters.csv",
    "models/dual_gate/igzo_dg_teaching_r01.json",
    "report/assets/m00_compact_model_fit.png",
    "report/assets/m00_compact_model_residuals.png",
    "results/reports/m00_compact_model_fit.json",
    "results/compact/m00_teaching_fit_r02/input_snapshot.json",
    "results/compact/m00_teaching_fit_r02/selected_rows_manifest.csv",
    "results/compact/m00_teaching_fit_r02/optimizer_log.json",
    "results/tables/m00_compact_model_predictions_r02.csv",
    "results/tables/m00_compact_model_curve_metrics_r02.csv",
    "results/tables/m00_compact_model_parameters_r02.csv",
    "models/dual_gate/igzo_dg_teaching_r02.json",
    "spice/models/igzo_dg_behavioral_r02.inc",
    "models/level61/igzo_level15_r02.inc",
    "models/level61/igzo_level15_r02_parameters.json",
    "report/assets/m00_compact_model_fit_r02.png",
    "report/assets/m00_compact_model_residuals_r02.png",
    "results/reports/m00_compact_model_fit_r02.json",
    "results/reports/m00_compact_model_fit_check_r02.json",
    "config/m01_simulator_cross_check_contract.json",
    "scripts/check_m01_simulator_cross_check_contract.py",
    "results/reports/m01_simulator_cross_check_contract.json",
    "results/reports/m01_simulator_cross_check_contract_v2.json",
    "results/reports/m01_simulator_cross_check_contract_v3.json",
    "config/m01_simulator_preflight_r01.json",
    "scripts/run_m01_simulator_preflight.py",
    "results/reports/m01_simulator_preflight_r01.json",
    "results/compact/m01_simulator_cross_check_r01/syntax_preflight.log",
    "config/m01_open_source_recovery_contract_r01.json",
    "scripts/check_m01_open_source_recovery_contract.py",
    "results/reports/m01_open_source_recovery_contract_r01.json",
    "results/reports/m01_open_source_recovery_contract_r01_e3.json",
    "config/m01_xyce_build_preflight_r01.json",
    "scripts/check_m01_xyce_build_preflight_contract.py",
    "scripts/run_m01_xyce_build_preflight.py",
    "scripts/check_m01_xyce_build_preflight.py",
    "results/reports/m01_xyce_build_preflight_contract_r01.json",
    "config/m01_xyce_build_preflight_r02.json",
    "scripts/check_m01_xyce_build_preflight_r02_contract.py",
    "scripts/run_m01_xyce_build_preflight_r02.py",
    "scripts/check_m01_xyce_build_preflight_r02.py",
    "config/m01_xyce_build_preflight_r03.json",
    "scripts/check_m01_xyce_build_preflight_r03_contract.py",
    "scripts/run_m01_xyce_build_preflight_r03.py",
    "scripts/check_m01_xyce_build_preflight_r03.py",
    "results/reports/m01_xyce_build_preflight_contract_r03.json",
    "config/m01_xyce_build_preflight_r04.json",
    "scripts/check_m01_xyce_build_preflight_r04_contract.py",
    "scripts/run_m01_xyce_build_preflight_r04.py",
    "scripts/check_m01_xyce_build_preflight_r04.py",
    "results/reports/m01_xyce_build_preflight_contract_r04.json",
    "config/m01_xyce_build_preflight_r05.json",
    "scripts/check_m01_xyce_build_preflight_r05_contract.py",
    "scripts/run_m01_xyce_build_preflight_r05.py",
    "scripts/check_m01_xyce_build_preflight_r05.py",
    "results/reports/m01_xyce_build_preflight_contract_r05.json",
    "results/reports/m01_xyce_build_preflight_r05.json",
    "results/compact/m01_xyce_build_preflight_r05/preflight.log",
    "results/compact/m01_xyce_build_preflight_r05/source_manifest.json",
    "results/compact/m01_xyce_build_preflight_r05/build_manifest.json",
    "results/compact/m01_xyce_build_preflight_r05/suitesparse_configure.log",
    "results/compact/m01_xyce_build_preflight_r05/suitesparse_build_install.log",
    "results/compact/m01_xyce_build_preflight_r05/trilinos_configure.log",
    "results/compact/m01_xyce_build_preflight_r05/trilinos_build_install.log",
    "results/compact/m01_xyce_build_preflight_r05/xyce_configure.log",
    "results/compact/m01_xyce_build_preflight_r05/xyce_build_install.log",
    "config/m01_xyce_build_preflight_r06.json",
    "scripts/m01_xyce_r06_common.py",
    "scripts/check_m01_xyce_build_preflight_r06_contract.py",
    "scripts/run_m01_xyce_build_preflight_r06.py",
    "scripts/check_m01_xyce_build_preflight_r06.py",
    "results/reports/m01_xyce_build_preflight_contract_r06.json",
    "results/reports/project_check_m01_xyce_r06_contract_source_subprocess_literal_failed.json",
    "results/reports/project_check_m01_xyce_r06_failure_next_scope_stale_failed.json",
    "config/m01_xyce_build_preflight_r07.json",
    "scripts/m01_xyce_r07_common.py",
    "scripts/check_m01_xyce_build_preflight_r07_contract.py",
    "scripts/run_m01_xyce_build_preflight_r07.py",
    "scripts/check_m01_xyce_build_preflight_r07.py",
    "config/m01_xyce_build_preflight_r08.json",
    "scripts/m01_xyce_r08_common.py",
    "scripts/check_m01_xyce_build_preflight_r08_contract.py",
    "scripts/run_m01_xyce_build_preflight_r08.py",
    "scripts/check_m01_xyce_build_preflight_r08.py",
    "config/m01_xyce_build_preflight_r09.json",
    "scripts/m01_xyce_r09_common.py",
    "scripts/check_m01_xyce_build_preflight_r09_contract.py",
    "scripts/run_m01_xyce_build_preflight_r09.py",
    "scripts/check_m01_xyce_build_preflight_r09.py",
    "config/m01_xyce_build_preflight_r10.json",
    "scripts/m01_xyce_r10_common.py",
    "scripts/check_m01_xyce_build_preflight_r10_contract.py",
    "scripts/run_m01_xyce_build_preflight_r10.py",
    "scripts/check_m01_xyce_build_preflight_r10.py",
    "results/reports/m01_xyce_build_preflight_contract_r10.json",
    "results/reports/project_check_m01_xyce_r10_static_pass_r08_next_scope_stale_failed.json",
    "results/reports/m01_xyce_build_preflight_r10_runner_unicode_path_failed.json",
    "results/compact/m01_xyce_build_preflight_r10_runner_unicode_path_failed.log",
    "results/compact/m01_xyce_build_preflight_r10/preflight.log",
    "results/compact/m01_xyce_build_preflight_r10/bsource_self_test.cir",
    "results/compact/m01_xyce_build_preflight_r10/bsource_self_test.log",
    "results/compact/m01_xyce_build_preflight_r10/bsource_self_test.prn",
    "results/compact/m01_xyce_build_preflight_r10/xyce_version.log",
    "results/compact/m01_xyce_build_preflight_r10/xyce_license.log",
    "results/compact/m01_xyce_build_preflight_r10/xyce_bsource_self_test.log",
    "config/m01_xyce_build_preflight_r11.json",
    "scripts/m01_xyce_r11_common.py",
    "scripts/check_m01_xyce_build_preflight_r11_contract.py",
    "scripts/run_m01_xyce_build_preflight_r11.py",
    "scripts/check_m01_xyce_build_preflight_r11.py",
    "scripts/check_t03_p5_temperature.py",
    "tcad/run_t03_p5_temperature.py",
    "results/reports/tcad_t03_p5_temperature_input_contract.json",
    "results/reports/tcad_t03_p5_temperature.json",
    "results/reports/tcad_t03_p5_temperature_check.json",
    "results/reports/project_check_t03_p5_p3_next_gate_stale_failed.json",
    "results/tables/tcad_t03_p5_temperature_transfer.csv",
    "results/tables/tcad_t03_p5_temperature_metrics.csv",
    "results/tables/tcad_t03_p5_temperature_t02_c_reproduction.csv",
    "results/tables/tcad_t03_p5_temperature_state_summary.csv",
    "results/tcad/t03_sensitivity/p5_temperature/input_snapshot.json",
    "results/tcad/t03_sensitivity/p5_temperature/solver_log.json",
    "results/tcad/t03_sensitivity/p5_temperature/state_manifest.json",
    "report/assets/tcad_t03_p5_temperature_sensitivity.png",
    "report/assets/tcad_t03_p5_temperature_states.png",
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
    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3",
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
        current_next_scope = config.get("tcad_track", {}).get("next_scope", "")
        r08_scope_active = current_next_scope.startswith(
            "establish and commit M01 Xyce build/tool preflight revision-8"
        ) or current_next_scope.startswith(
            "execute M01 Xyce build/tool preflight revision-8"
        ) or current_next_scope.startswith(
            "preserve and commit the M01 Xyce build/tool preflight revision-8"
        ) or current_next_scope.startswith(
            "establish and commit M01 Xyce build/tool preflight revision-9"
        ) or current_next_scope.startswith(
            "execute M01 Xyce build/tool preflight revision-9"
        ) or current_next_scope.startswith(
            "preserve and commit the M01 Xyce build/tool preflight revision-9"
        ) or current_next_scope.startswith(
            "establish and commit M01 Xyce build/tool preflight revision-10"
        ) or current_next_scope.startswith(
            "execute M01 Xyce build/tool preflight revision-10"
        ) or current_next_scope.startswith(
            "preserve and commit the M01 Xyce build/tool preflight revision-10"
        ) or current_next_scope.startswith(
            "establish and commit M01 Xyce build/tool preflight revision-11"
        ) or current_next_scope.startswith(
            "execute M01 Xyce build/tool preflight revision-11"
        ) or current_next_scope.startswith(
            "preserve and commit the M01 Xyce build/tool preflight revision-11"
        )
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
            sensitivity.get("status") == "verified"
            and sensitivity.get("completed_parameter_groups")
            == ["P1", "P2", "P3", "P4", "P5"]
            and sensitivity.get("partially_completed_parameter_groups") == []
            and sensitivity.get("remaining_parameter_groups") == []
            and sensitivity.get("remaining_substages") == []
            and sensitivity.get("p2_bulk_equation_smoke_evidence")
            == {
                "status": "smoke_verified",
                "runner_evidence": "E2",
                "independent_persisted_check_evidence": "E3",
                "devices": 3,
                "coupled_dc_solves": 21,
                "state_node_rows": 7257,
                "integration_sample_rows": 6,
                "equation_smoke_itself_completes_formal_transfer_sensitivity": False,
            }
            and sensitivity.get("p2_bulk_formal_contract_evidence")
            == {
                "status": "input_contract_ready_v3",
                "revision": 3,
                "contract_evidence": "E3",
                "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
                "v1_failure_preserved": True,
                "v2_failure_preserved": True,
                "formal_sensitivity_completed": True,
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
            and sensitivity.get("p2_bulk_formal_v3_evidence")
            == {
                "status": "formal_sensitivity_verified",
                "runner_evidence": "E2",
                "independent_persisted_check_evidence": "E3",
                "runner_checks_passed": 17,
                "independent_checks_passed": 16,
                "devices": 8,
                "converged_dc_records": 456,
                "transfer_points": 376,
                "states": 8,
                "vtk_files": 48,
                "wall_seconds": 36.66947608400005,
                "maximum_relative_terminal_current_imbalance": 6.012869303315774e-9,
                "zero_controls_exactly_reproduce_t02_c": True,
                "nta_diagnostic": "VTH and SS proxies strictly increase while gm proxy strictly decreases",
                "nga_diagnostic": "VTH proxy strictly increases and gm proxy strictly decreases while SS proxy mildly decreases",
                "formal_sensitivity_completed": True,
                "complete_p2_trap_group": True,
                "complete_t03_five_group_sensitivity": False,
            }
            and sensitivity.get("p3_contact_contract_evidence")
            == {
                "status": "input_contract_ready_v2_after_v1_failure",
                "revision": 2,
                "contract_evidence": "E3",
                "contract_checks_passed": 34,
                "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
                "v1_failure_preserved": True,
                "relative_current_gate_domain": "external VDS>0",
                "zero_vds_absolute_current_gate_domain": "external VDS=0",
                "relative_threshold_changed": False,
                "zero_vds_absolute_threshold_changed": False,
                "physical_input_changed": False,
                "literature_source_rows": 2,
                "r_pair_w_values_kohm_um": [0.0, 0.5, 4.5],
                "planned_devices": 12,
                "planned_dc_solves": 243,
                "planned_reported_points": 156,
                "planned_states": 3,
                "initial_checker_failure_preserved": True,
                "formal_sensitivity_completed": False,
                "complete_p3_contact_group": False,
                "complete_t03_five_group_sensitivity": False,
            }
            and sensitivity.get("p3_contact_v1_failure_evidence")
            == {
                "status": "FAIL_PRESERVED",
                "evidence_level": "E0",
                "devices": 12,
                "converged_dc_solves": 243,
                "transfer_points": 93,
                "output_points": 63,
                "states": 3,
                "vtk_files": 18,
                "runner_checks_passed": 24,
                "runner_checks_total": 25,
                "failed_gate": "device_terminal_current_conservation",
                "failure_classification": "acceptance_gate_applicability_bug",
                "maximum_all_point_relative_terminal_current_imbalance": 1.672051696284307,
                "maximum_nonzero_vds_relative_terminal_current_imbalance": 3.3534440908787024e-11,
                "maximum_zero_vds_absolute_current_a_per_cm": 1.0845387955775905e-19,
                "maximum_circuit_kcl_relative_residual": 2.421775820902517e-12,
                "maximum_circuit_ohms_law_relative_residual": 1.2092244533030856e-12,
                "maximum_circuit_voltage_partition_absolute_residual_v": 0.0,
                "independent_persisted_check_run": False,
                "failure_archive_manifest_preserved": True,
                "failure_archive_filename_collision_supplemented": True,
                "formal_sensitivity_completed": False,
                "complete_p3_contact_group": False,
                "complete_t03_five_group_sensitivity": False,
            }
            and sensitivity.get("p3_contact_v2_evidence")
            == {
                "status": "formal_sensitivity_verified",
                "runner_evidence": "E2",
                "independent_persisted_check_evidence": "E3",
                "runner_checks_passed": 25,
                "independent_checks_passed": 20,
                "devices": 12,
                "converged_dc_solves": 243,
                "transfer_points": 93,
                "output_points": 63,
                "states": 3,
                "state_node_rows": 7257,
                "state_element_rows": 7680,
                "vtk_files": 18,
                "wall_seconds": 24.73534312699485,
                "maximum_nonzero_vds_relative_terminal_current_imbalance": 3.3534440908787024e-11,
                "maximum_zero_vds_absolute_current_a_per_cm": 1.0845387955775905e-19,
                "maximum_circuit_kcl_relative_residual": 2.421775820902517e-12,
                "maximum_circuit_ohms_law_relative_residual": 1.2092244533030856e-12,
                "maximum_circuit_voltage_partition_absolute_residual_v": 0.0,
                "largest_pair_high_gate_current_relative_reduction": 0.0016139591451679268,
                "linear_region_total_resistance_width_kohm_um": [
                    2780.13344904325,
                    2780.633291954896,
                    2784.6320382862077,
                ],
                "v1_failure_reinterpreted_as_pass": False,
                "formal_sensitivity_completed": True,
                "complete_p3_contact_group": True,
                "complete_t03_five_group_sensitivity": False,
            }
            and sensitivity.get("p3_outputs")
            == [
                "references/t03_p3_contact_sources.csv",
                "config/tcad_t03_p3_contact_resistance.json",
                "config/tcad_t03_p3_contact_resistance_v1_failed.json",
                "scripts/check_t03_p3_contact_contract.py",
                "scripts/check_t03_p3_contact_contract_v1.py",
                "tcad/run_t03_p3_contact_resistance.py",
                "tcad/run_t03_p3_contact_resistance_v1_failed.py",
                "scripts/check_t03_p3_contact_resistance.py",
                "results/reports/tcad_t03_p3_contact_input_contract_v1_checker_initial_assertions_failed.json",
                "results/reports/tcad_t03_p3_contact_input_contract.json",
                "results/reports/tcad_t03_p3_contact_input_contract_v1.json",
                "results/reports/tcad_t03_p3_contact_resistance.json",
                "results/reports/tcad_t03_p3_contact_resistance_device_terminal_current_conservation.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance/input_snapshot.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance/solver_log.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance/state_manifest.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance_device_terminal_current_conservation/failure_archive_manifest.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance_device_terminal_current_conservation/failure_archive_supplement.json",
                "results/tables/tcad_t03_p3_contact_transfer.csv",
                "results/tables/tcad_t03_p3_contact_output.csv",
                "results/tables/tcad_t03_p3_contact_metrics.csv",
                "results/tables/tcad_t03_p3_contact_circuit_balance.csv",
                "results/tables/tcad_t03_p3_contact_t02_c_reproduction.csv",
                "results/tables/tcad_t03_p3_contact_state_summary.csv",
                "report/assets/tcad_t03_p3_contact_sensitivity.png",
                "report/assets/tcad_t03_p3_contact_states.png",
                "results/reports/tcad_t03_p3_contact_input_contract_v2.json",
                "results/reports/tcad_t03_p3_contact_resistance_v2.json",
                "results/reports/tcad_t03_p3_contact_resistance_v2_check.json",
                "results/tables/tcad_t03_p3_contact_v2_transfer.csv",
                "results/tables/tcad_t03_p3_contact_v2_output.csv",
                "results/tables/tcad_t03_p3_contact_v2_metrics.csv",
                "results/tables/tcad_t03_p3_contact_v2_circuit_balance.csv",
                "results/tables/tcad_t03_p3_contact_v2_t02_c_reproduction.csv",
                "results/tables/tcad_t03_p3_contact_v2_state_summary.csv",
                "results/tcad/t03_sensitivity/p3_contact_resistance_v2/input_snapshot.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance_v2/solver_log.json",
                "results/tcad/t03_sensitivity/p3_contact_resistance_v2/state_manifest.json",
                "report/assets/tcad_t03_p3_contact_v2_sensitivity.png",
                "report/assets/tcad_t03_p3_contact_v2_states.png",
            ]
            and sensitivity.get("p5_temperature_contract_evidence")
            == {
                "status": "input_contract_ready",
                "revision": 1,
                "contract_evidence": "E3",
                "contract_checks_passed": 23,
                "simulation_status": "NOT_RUN_BY_CONTRACT_CHECK",
                "temperature_values_k": [250.0, 300.0, 350.0],
                "thermal_voltage_values_v": [
                    0.021543333155,
                    0.025851999786,
                    0.030160666417,
                ],
                "only_temperature_dependent_term": (
                    "V_t in the existing Scharfetter-Gummel "
                    "electron-current expression"
                ),
                "configured_mobility_cm2_vs": 35.5,
                "mobility_temperature_law_active": False,
                "planned_devices": 3,
                "planned_dc_solves": 123,
                "planned_reported_points": 93,
                "planned_states": 3,
                "planned_vtk_files": 18,
                "formal_sensitivity_completed": True,
                "complete_p5_temperature_group": True,
                "complete_t03_five_group_sensitivity": True,
            }
            and sensitivity.get("p5_temperature_evidence")
            == {
                "status": "formal_sensitivity_verified",
                "runner_evidence": "E2",
                "independent_persisted_check_evidence": "E3",
                "runner_checks_passed": 14,
                "independent_checks_passed": 15,
                "devices": 3,
                "converged_dc_solves": 123,
                "transfer_points": 93,
                "states": 3,
                "state_node_rows": 7257,
                "state_element_rows": 7680,
                "vtk_files": 18,
                "wall_seconds": 9.126646766999329,
                "maximum_relative_terminal_current_imbalance": (
                    4.3730079797195624e-10
                ),
                "maximum_endpoint_metric_relative_response": 0.9419341662870279,
                "temperature_values_k": [250.0, 300.0, 350.0],
                "vth_proxy_v": [
                    0.24540900212816344,
                    0.26385685799760256,
                    0.2819769165981422,
                ],
                "ss_proxy_mv_per_dec": [
                    117.13784095935709,
                    137.59377510040815,
                    157.79613260681256,
                ],
                "gm_proxy_s_per_cm": [
                    3.9847163606731224e-5,
                    3.937599666287622e-5,
                    3.8812821127225277e-5,
                ],
                "low_gate_current_proxy_a_per_cm": [
                    4.032928160350107e-11,
                    2.100900501789906e-10,
                    6.945440894357022e-10,
                ],
                "high_gate_current_proxy_a_per_cm": [
                    3.6469841491285194e-5,
                    3.593724333278673e-5,
                    3.529250269768652e-5,
                ],
                "configured_mobility_cm2_vs": 35.5,
                "t02_c_300k_curve_state_vth_gm_exact_reproduction": True,
                "complete_p5_temperature_group": True,
                "complete_t03_five_group_sensitivity": True,
                "m00_contract_permitted_after_documentation": True,
                "compact_model_simulation_permitted_before_m00_contract": False,
            }
            and sensitivity.get("p5_outputs")
            == [
                "references/t03_p5_temperature_sources.csv",
                "config/tcad_t03_p5_temperature.json",
                "scripts/check_t03_p5_temperature_contract.py",
                "tcad/run_t03_p5_temperature.py",
                "scripts/check_t03_p5_temperature.py",
                "results/reports/tcad_t03_p5_temperature_input_contract.json",
                "results/reports/tcad_t03_p5_temperature.json",
                "results/reports/tcad_t03_p5_temperature_check.json",
                "results/reports/project_check_t03_p5_p3_next_gate_stale_failed.json",
                "results/tables/tcad_t03_p5_temperature_transfer.csv",
                "results/tables/tcad_t03_p5_temperature_metrics.csv",
                "results/tables/tcad_t03_p5_temperature_t02_c_reproduction.csv",
                "results/tables/tcad_t03_p5_temperature_state_summary.csv",
                "results/tcad/t03_sensitivity/p5_temperature/input_snapshot.json",
                "results/tcad/t03_sensitivity/p5_temperature/solver_log.json",
                "results/tcad/t03_sensitivity/p5_temperature/state_manifest.json",
                "report/assets/tcad_t03_p5_temperature_sensitivity.png",
                "report/assets/tcad_t03_p5_temperature_states.png",
            ]
            and all(
                path in sensitivity.get("p2_outputs", [])
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
                    "results/reports/tcad_t03_p2_bulk_traps_formal_v3.json",
                    "results/reports/tcad_t03_p2_bulk_traps_formal_v3_check.json",
                    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_transfer.csv",
                    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_metrics.csv",
                    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_t02_c_reproduction.csv",
                    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_zero_control_comparison.csv",
                    "results/tables/tcad_t03_p2_bulk_traps_formal_v3_state_summary.csv",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/input_snapshot.json",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/solver_log.json",
                    "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3/state_manifest.json",
                    "report/assets/tcad_t03_p2_bulk_traps_formal_v3_sensitivity.png",
                    "report/assets/tcad_t03_p2_bulk_traps_formal_v3_states.png",
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
        v3_report_path = (
            ROOT / "results/reports/tcad_t03_p2_bulk_traps_formal_v3.json"
        )
        v3_check_path = (
            ROOT / "results/reports/tcad_t03_p2_bulk_traps_formal_v3_check.json"
        )
        v3_run_dir = (
            ROOT / "results/tcad/t03_sensitivity/p2_bulk_traps_formal_v3"
        )
        v3_report = json.loads(v3_report_path.read_text(encoding="utf-8"))
        v3_check = json.loads(v3_check_path.read_text(encoding="utf-8"))
        v3_solver_log = json.loads(
            (v3_run_dir / "solver_log.json").read_text(encoding="utf-8")
        )
        v3_state_manifest = json.loads(
            (v3_run_dir / "state_manifest.json").read_text(encoding="utf-8")
        )
        v3_table_paths = {
            "curves": ROOT
            / "results/tables/tcad_t03_p2_bulk_traps_formal_v3_transfer.csv",
            "metrics": ROOT
            / "results/tables/tcad_t03_p2_bulk_traps_formal_v3_metrics.csv",
            "t02_c": ROOT
            / "results/tables/tcad_t03_p2_bulk_traps_formal_v3_t02_c_reproduction.csv",
            "zero": ROOT
            / "results/tables/tcad_t03_p2_bulk_traps_formal_v3_zero_control_comparison.csv",
            "states": ROOT
            / "results/tables/tcad_t03_p2_bulk_traps_formal_v3_state_summary.csv",
        }
        v3_tables = {}
        for table_id, table_path in v3_table_paths.items():
            with table_path.open("r", encoding="utf-8", newline="") as stream:
                v3_tables[table_id] = list(csv.DictReader(stream))
        v3_solver_records = [
            record
            for run in v3_solver_log.get("runs", [])
            for record in run.get("solver_records", [])
        ]
        v3_runner_checks = v3_report.get("checks", {})
        v3_summary = v3_report.get("summary_metrics", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_v3_runner_evidence",
            v3_report.get("status") == "PASS"
            and v3_report.get("case_id") == "IGZO_T03_P2_BULK_TRAPS_FORMAL_V3"
            and v3_report.get("stage") == "T03-P2-BULK-TRAPS-FORMAL"
            and v3_report.get("evidence_level") == "E2"
            and v3_report.get("formal_sensitivity_run") is True
            and v3_report.get("independent_persisted_evidence_check_complete")
            is False
            and len(v3_runner_checks) == 17
            and all(
                item.get("status") == "PASS"
                for item in v3_runner_checks.values()
            )
            and not v3_report.get("failures")
            and v3_summary.get("device_count") == 8
            and v3_summary.get("dc_solve_count") == 456
            and v3_summary.get("reported_point_count") == 376
            and v3_summary.get("state_count") == 8
            and v3_summary.get("vtk_file_count") == 48
            and math.isclose(
                v3_summary.get("maximum_relative_terminal_current_imbalance"),
                6.012869303315774e-9,
                rel_tol=1e-12,
            )
            and len(v3_solver_log.get("runs", [])) == 8
            and len(v3_solver_records) == 456
            and all(record.get("converged") is True for record in v3_solver_records),
            (
                f"status={v3_report.get('status')} checks={len(v3_runner_checks)} "
                f"devices={v3_summary.get('device_count')} "
                f"records={len(v3_solver_records)} points={len(v3_tables['curves'])}"
            ),
        )
        v3_independent_checks = v3_check.get("checks", [])
        v3_recomputed = v3_check.get("recomputed_diagnostics", {})
        v3_completion = v3_check.get("t03_p2_completion", {})
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_v3_independent_completion",
            v3_check.get("status") == "PASS"
            and v3_check.get("evidence_level") == "E3"
            and v3_check.get("independent_of_simulation_runner") is True
            and v3_check.get("runner_imported") is False
            and v3_check.get("devsim_imported") is False
            and len(v3_independent_checks) == 16
            and all(item.get("status") == "PASS" for item in v3_independent_checks)
            and not v3_check.get("failures")
            and v3_recomputed.get("device_count") == 8
            and v3_recomputed.get("dc_solve_count") == 456
            and v3_recomputed.get("curve_point_count") == 376
            and v3_recomputed.get("metric_row_count") == 8
            and v3_recomputed.get("state_count") == 8
            and v3_recomputed.get("vtk_file_count") == 48
            and v3_completion.get("bulk_formal_runner_passed") is True
            and v3_completion.get("bulk_formal_independent_check_passed") is True
            and v3_completion.get("complete_p2_trap_group") is True
            and v3_completion.get("complete_t03_five_group_sensitivity") is False
            and v3_completion.get("p3_or_p5_permitted_after_documentation") is True
            and v3_completion.get("experimental_calibration_permitted") is False,
            (
                f"status={v3_check.get('status')} checks={len(v3_independent_checks)} "
                f"p2={v3_completion.get('complete_p2_trap_group')} "
                f"t03={v3_completion.get('complete_t03_five_group_sensitivity')}"
            ),
        )
        v3_metrics_by_family = {
            family: sorted(
                (
                    row
                    for row in v3_tables["metrics"]
                    if row["bulk_family_id"] == family
                ),
                key=lambda row: float(row["bulk_value_cm3_ev"]),
            )
            for family in ("NTA", "NGA")
        }
        nta_vth = [float(row["vth_proxy_v"]) for row in v3_metrics_by_family["NTA"]]
        nta_ss = [float(row["ss_proxy_mv_per_dec"]) for row in v3_metrics_by_family["NTA"]]
        nta_gm = [float(row["gm_proxy_s_per_cm"]) for row in v3_metrics_by_family["NTA"]]
        nga_vth = [float(row["vth_proxy_v"]) for row in v3_metrics_by_family["NGA"]]
        nga_ss = [float(row["ss_proxy_mv_per_dec"]) for row in v3_metrics_by_family["NGA"]]
        nga_gm = [float(row["gm_proxy_s_per_cm"]) for row in v3_metrics_by_family["NGA"]]
        v3_manifest_entries = v3_state_manifest.get("entries", [])
        v3_artifact_hashes = v3_check.get("artifact_hashes", {})
        v3_figures = v3_report.get("figures", [])
        add_check(
            checks,
            "t03_p2_bulk_traps:formal_v3_artifacts_diagnostics_and_boundary",
            len(v3_tables["curves"]) == 376
            and len(v3_tables["metrics"]) == 8
            and len(v3_tables["t02_c"]) == 62
            and len(v3_tables["zero"]) == 47
            and len(v3_tables["states"]) == 8
            and all(len(rows) == 4 for rows in v3_metrics_by_family.values())
            and all(
                row.get("parameter_claim_status")
                == "NUMERICAL_PROXY_NOT_PHYSICALLY_VALIDATED"
                for row in v3_tables["metrics"]
            )
            and all(lower < upper for lower, upper in zip(nta_vth, nta_vth[1:]))
            and all(lower < upper for lower, upper in zip(nta_ss, nta_ss[1:]))
            and all(lower > upper for lower, upper in zip(nta_gm, nta_gm[1:]))
            and all(lower < upper for lower, upper in zip(nga_vth, nga_vth[1:]))
            and all(lower > upper for lower, upper in zip(nga_ss, nga_ss[1:]))
            and all(lower > upper for lower, upper in zip(nga_gm, nga_gm[1:]))
            and v3_state_manifest.get("entry_count") == 8
            and len(v3_manifest_entries) == 8
            and sum(
                int(entry.get("vtk_file_count", 0))
                for entry in v3_manifest_entries
            )
            == 48
            and all(
                (ROOT / entry["node_csv"]).is_file()
                and (ROOT / entry["element_csv"]).is_file()
                and (ROOT / entry["bulk_node_csv"]).is_file()
                for entry in v3_manifest_entries
            )
            and len(v3_artifact_hashes) == 8
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in v3_artifact_hashes.values()
            )
            and len(v3_figures) == 2
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in v3_figures
            )
            and "numerical proxies"
            in v3_check.get("evidence_boundary", {}).get("allowed_claim", "")
            and "Document P2 completion"
            in v3_check.get("evidence_boundary", {}).get("next_gate", ""),
            (
                f"tables={[len(v3_tables[key]) for key in v3_tables]} "
                f"states={len(v3_manifest_entries)} vtk="
                f"{sum(int(entry.get('vtk_file_count', 0)) for entry in v3_manifest_entries)} "
                f"NGA_SS={nga_ss}"
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

    p3_config_path = ROOT / "config" / "tcad_t03_p3_contact_resistance.json"
    p3_v1_config_path = (
        ROOT / "config" / "tcad_t03_p3_contact_resistance_v1_failed.json"
    )
    p3_v1_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p3_contact_input_contract_v1.json"
    )
    p3_v2_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p3_contact_input_contract_v2.json"
    )
    p3_v1_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p3_contact_resistance.json"
    )
    p3_v1_versioned_report_path = (
        ROOT
        / "results"
        / "reports"
        / "tcad_t03_p3_contact_resistance_device_terminal_current_conservation.json"
    )
    p3_v2_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p3_contact_resistance_v2.json"
    )
    p3_v2_check_path = (
        ROOT
        / "results"
        / "reports"
        / "tcad_t03_p3_contact_resistance_v2_check.json"
    )
    p3_v1_run_dir = (
        ROOT / "results" / "tcad" / "t03_sensitivity" / "p3_contact_resistance"
    )
    p3_v2_run_dir = (
        ROOT / "results" / "tcad" / "t03_sensitivity" / "p3_contact_resistance_v2"
    )
    p3_v1_archive_dir = (
        ROOT
        / "results"
        / "tcad"
        / "t03_sensitivity"
        / "p3_contact_resistance_device_terminal_current_conservation"
    )
    p3_report_check_failure_path = (
        ROOT
        / "results"
        / "reports"
        / "report_check_t03_p3_v1_appendix_image_path_failed.json"
    )
    p3_failed_checker_path = (
        ROOT
        / "results"
        / "reports"
        / "tcad_t03_p3_contact_input_contract_v1_checker_initial_assertions_failed.json"
    )
    try:
        p3_config = json.loads(p3_config_path.read_text(encoding="utf-8"))
        p3_v1_config = json.loads(p3_v1_config_path.read_text(encoding="utf-8"))
        p3_v1_contract = json.loads(p3_v1_contract_path.read_text(encoding="utf-8"))
        p3_contract = json.loads(p3_v2_contract_path.read_text(encoding="utf-8"))
        p3_v1_report = json.loads(p3_v1_report_path.read_text(encoding="utf-8"))
        p3_v1_versioned_report = json.loads(
            p3_v1_versioned_report_path.read_text(encoding="utf-8")
        )
        p3_v2_report = json.loads(p3_v2_report_path.read_text(encoding="utf-8"))
        p3_v2_check = json.loads(p3_v2_check_path.read_text(encoding="utf-8"))
        p3_v1_snapshot = json.loads(
            (p3_v1_run_dir / "input_snapshot.json").read_text(encoding="utf-8")
        )
        p3_v1_solver_log = json.loads(
            (p3_v1_run_dir / "solver_log.json").read_text(encoding="utf-8")
        )
        p3_v1_state_manifest = json.loads(
            (p3_v1_run_dir / "state_manifest.json").read_text(encoding="utf-8")
        )
        p3_v2_snapshot = json.loads(
            (p3_v2_run_dir / "input_snapshot.json").read_text(encoding="utf-8")
        )
        p3_v2_solver_log = json.loads(
            (p3_v2_run_dir / "solver_log.json").read_text(encoding="utf-8")
        )
        p3_v2_state_manifest = json.loads(
            (p3_v2_run_dir / "state_manifest.json").read_text(encoding="utf-8")
        )
        p3_v1_archive_manifest = json.loads(
            (p3_v1_archive_dir / "failure_archive_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        p3_v1_archive_supplement = json.loads(
            (p3_v1_archive_dir / "failure_archive_supplement.json").read_text(
                encoding="utf-8"
            )
        )
        p3_report_check_failure = json.loads(
            p3_report_check_failure_path.read_text(encoding="utf-8")
        )
        p3_failed_checker = json.loads(
            p3_failed_checker_path.read_text(encoding="utf-8")
        )
        p3_contract_checks = p3_contract.get("checks", [])
        add_check(
            checks,
            "t03_p3_contact:v2_static_recovery_contract",
            p3_config.get("schema_version") == 2
            and p3_config.get("revision") == 2
            and p3_config.get("case_id") == "IGZO_T03_P3_CONTACT_RESISTANCE_V2"
            and p3_config.get("stage") == "T03-P3-CONTACT-RESISTANCE"
            and p3_contract.get("status") == "PASS"
            and p3_contract.get("contract_status") == "PASS"
            and p3_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and p3_contract.get("evidence_level") == "E3"
            and p3_contract.get("case_id") == p3_config.get("case_id")
            and p3_contract.get("config", {}).get("sha256")
            == sha256(p3_config_path)
            and len(p3_contract_checks) == 34
            and all(item.get("status") == "PASS" for item in p3_contract_checks)
            and not p3_contract.get("failures"),
            (
                f"status={p3_contract.get('status')} "
                f"checks={len(p3_contract_checks)} "
                f"simulation={p3_contract.get('simulation_status')}"
            ),
        )
        planned = p3_contract.get("planned_run", {})
        p3_mapping = p3_config.get("literature_mapping", {})
        p3_values = p3_config.get("sensitivity", {}).get("values_kohm_um", [])
        add_check(
            checks,
            "t03_p3_contact:frozen_plan_and_source_boundary",
            p3_values == [0.0, 0.5, 4.5]
            and planned.get("values_kohm_um") == p3_values
            and planned.get("devices") == 12
            and planned.get("dc_solves") == 243
            and planned.get("reported_points") == 156
            and planned.get("states") == 3
            and planned.get("vtk_files") == 18
            and p3_mapping.get("source_rc_convention_inherited") is False
            and p3_mapping.get("project_case_labels_do_not_name_metals") is True
            and p3_mapping.get("mapping_is_measurement_or_calibration") is False
            and p3_config.get("contact_model_contract", {}).get("barrier_height_ev")
            is None
            and p3_config.get("failure_retention", {}).get(
                "relax_preregistered_thresholds_after_failure_permitted"
            )
            is False
            and p3_config.get("acceptance", {}).get(
                "maximum_relative_device_terminal_current_imbalance"
            )
            == 1e-5
            and p3_config.get("acceptance", {}).get(
                "relative_device_terminal_current_imbalance_gate_domain"
            )
            == "external VDS>0"
            and p3_config.get("acceptance", {}).get(
                "maximum_zero_external_vds_absolute_current_a_per_cm"
            )
            == 1e-16
            and p3_config.get("acceptance", {}).get(
                "zero_external_vds_absolute_current_gate_domain"
            )
            == "external VDS=0",
            f"values={p3_values} plan={planned}",
        )
        p3_inputs = p3_contract.get("inputs", {})
        p3_immutable_inputs = {
            name: item
            for name, item in p3_inputs.items()
            if name not in {"project_config", "experiments_config"}
        }
        p3_recorded_machine_state = p3_v2_snapshot.get(
            "contract_recorded_machine_state", {}
        )
        add_check(
            checks,
            "t03_p3_contact:contract_inputs_and_recorded_machine_state_preserved",
            len(p3_inputs) == 31
            and len(p3_immutable_inputs) == 29
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in p3_immutable_inputs.values()
            )
            and p3_recorded_machine_state.get("project_config")
            == p3_inputs.get("project_config")
            and p3_recorded_machine_state.get("experiments_config")
            == p3_inputs.get("experiments_config")
            and "without running DEVSIM"
            in p3_contract.get("evidence_boundary", {}).get(
                "contract_allowed_claim", ""
            )
            and "runner E2 plus independent persisted-evidence E3 PASS"
            in p3_contract.get("evidence_boundary", {}).get(
                "future_run_allowed_claim", ""
            ),
            (
                f"inputs={len(p3_inputs)} immutable={len(p3_immutable_inputs)}"
            ),
        )

        expected_v1_hashes = p3_config.get("remediation", {}).get(
            "expected_v1_hashes", {}
        )
        v1_runner_checks = p3_v1_report.get("checks", {})
        v1_all_points = [
            *p3_v1_report.get("transfer_points", []),
            *p3_v1_report.get("output_points", []),
        ]
        v1_nonzero_points = [
            row for row in v1_all_points if float(row["external_vds_v"]) > 1e-12
        ]
        v1_zero_points = [
            row
            for row in p3_v1_report.get("output_points", [])
            if math.isclose(
                float(row["external_vds_v"]), 0.0, rel_tol=0.0, abs_tol=1e-12
            )
        ]
        v1_max_nonzero = max(
            float(row["relative_current_imbalance"]) for row in v1_nonzero_points
        )
        v1_max_zero = max(
            abs(float(row["external_drain_current_a_per_cm"]))
            for row in v1_zero_points
        )
        add_check(
            checks,
            "t03_p3_contact:v1_single_gate_failure_and_numerical_evidence",
            p3_v1_config.get("case_id") == "IGZO_T03_P3_CONTACT_RESISTANCE_V1"
            and p3_v1_contract.get("status") == "PASS"
            and len(p3_v1_contract.get("checks", [])) == 30
            and p3_v1_report == p3_v1_versioned_report
            and p3_v1_report.get("status") == "FAIL"
            and p3_v1_report.get("evidence_level") == "E0"
            and p3_v1_report.get("failures")
            == ["device_terminal_current_conservation"]
            and len(v1_runner_checks) == 25
            and sum(
                item.get("status") == "PASS" for item in v1_runner_checks.values()
            )
            == 24
            and len(p3_v1_solver_log.get("runs", [])) == 12
            and len(p3_v1_solver_log.get("solver_records", [])) == 243
            and all(
                record.get("converged")
                for record in p3_v1_solver_log.get("solver_records", [])
            )
            and len(p3_v1_report.get("transfer_points", [])) == 93
            and len(p3_v1_report.get("output_points", [])) == 63
            and len(v1_nonzero_points) == 147
            and len(v1_zero_points) == 9
            and math.isclose(
                v1_max_nonzero,
                3.3534440908787024e-11,
                rel_tol=1e-12,
                abs_tol=0.0,
            )
            and math.isclose(
                v1_max_zero,
                1.0845387955775905e-19,
                rel_tol=1e-12,
                abs_tol=0.0,
            )
            and p3_v1_state_manifest.get("entry_count") == 3
            and sum(
                len(entry.get("vtk_files", []))
                for entry in p3_v1_state_manifest.get("entries", [])
            )
            == 18
            and p3_v1_report.get("independent_persisted_evidence_check_complete")
            is False,
            (
                f"runner={sum(item.get('status') == 'PASS' for item in v1_runner_checks.values())}/"
                f"{len(v1_runner_checks)} devices={len(p3_v1_solver_log.get('runs', []))} "
                f"dc={len(p3_v1_solver_log.get('solver_records', []))} "
                f"nonzero={v1_max_nonzero:.6e} zero={v1_max_zero:.6e}"
            ),
        )
        add_check(
            checks,
            "t03_p3_contact:v1_hashes_and_failure_archive_supplement",
            len(expected_v1_hashes) == 11
            and all(
                (ROOT / path).is_file()
                and sha256(ROOT / path) == expected_hash
                for path, expected_hash in expected_v1_hashes.items()
            )
            and p3_v1_snapshot.get("case_id")
            == "IGZO_T03_P3_CONTACT_RESISTANCE_V1"
            and p3_v1_archive_manifest.get("status") == "FAIL_PRESERVED"
            and p3_v1_archive_manifest.get("failed_gate")
            == "device_terminal_current_conservation"
            and p3_v1_archive_supplement.get("status")
            == "FAIL_PRESERVED_WITH_SUPPLEMENT"
            and p3_v1_archive_supplement.get("original_manifest_collision", {}).get(
                "present"
            )
            is True
            and p3_v1_archive_supplement.get("original_manifest_collision", {}).get(
                "original_manifest_preserved_unmodified"
            )
            is True
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in [
                    *p3_v1_archive_supplement.get("unique_recovery_copies", []),
                    *p3_v1_archive_supplement.get("primary_v1_evidence", []),
                ]
            ),
            (
                f"hashes={len(expected_v1_hashes)} "
                f"archive={p3_v1_archive_manifest.get('status')} "
                f"supplement={p3_v1_archive_supplement.get('status')}"
            ),
        )
        v2_output_paths = [
            ROOT / value for value in p3_config.get("outputs", {}).values()
        ]
        v2_runner_checks = p3_v2_report.get("checks", {})
        v2_all_points = [
            *p3_v2_report.get("transfer_points", []),
            *p3_v2_report.get("output_points", []),
        ]
        v2_nonzero_points = [
            row for row in v2_all_points if float(row["external_vds_v"]) > 1e-12
        ]
        v2_zero_points = [
            row
            for row in p3_v2_report.get("output_points", [])
            if math.isclose(
                float(row["external_vds_v"]), 0.0, rel_tol=0.0, abs_tol=1e-12
            )
        ]
        v2_circuit_points = [
            row for row in v2_all_points if row.get("circuit_closure_applicable")
        ]
        v2_max_nonzero = max(
            float(row["relative_current_imbalance"]) for row in v2_nonzero_points
        )
        v2_max_zero = max(
            abs(float(row["external_drain_current_a_per_cm"]))
            for row in v2_zero_points
        )
        v2_max_kcl = max(
            max(
                float(row["source_kcl_relative_residual"]),
                float(row["drain_kcl_relative_residual"]),
            )
            for row in v2_circuit_points
        )
        v2_max_ohm = max(
            float(row["circuit_ohms_law_relative_residual"])
            for row in v2_circuit_points
        )
        v2_max_partition = max(
            abs(float(row["voltage_partition_residual_v"]))
            for row in v2_circuit_points
        )
        v2_summary = p3_v2_report.get("summary_metrics", {})
        add_check(
            checks,
            "t03_p3_contact:v2_formal_runner_and_numerical_gates",
            p3_v2_report.get("status") == "PASS"
            and p3_v2_report.get("evidence_level") == "E2"
            and p3_v2_report.get("case_id")
            == "IGZO_T03_P3_CONTACT_RESISTANCE_V2"
            and p3_v2_report.get("formal_sensitivity_run") is True
            and p3_v2_report.get(
                "independent_persisted_evidence_check_complete"
            )
            is False
            and not p3_v2_report.get("failures")
            and len(v2_runner_checks) == 25
            and all(item.get("status") == "PASS" for item in v2_runner_checks.values())
            and len(p3_v2_solver_log.get("runs", [])) == 12
            and len(p3_v2_solver_log.get("solver_records", [])) == 243
            and all(
                record.get("converged")
                for record in p3_v2_solver_log.get("solver_records", [])
            )
            and len(p3_v2_report.get("transfer_points", [])) == 93
            and len(p3_v2_report.get("output_points", [])) == 63
            and len(v2_nonzero_points) == 147
            and len(v2_zero_points) == 9
            and len(v2_circuit_points) == 66
            and math.isclose(
                v2_max_nonzero, 3.3534440908787024e-11, rel_tol=1e-12
            )
            and math.isclose(v2_max_zero, 1.0845387955775905e-19, rel_tol=1e-12)
            and math.isclose(v2_max_kcl, 2.421775820902517e-12, rel_tol=1e-12)
            and math.isclose(v2_max_ohm, 1.2092244533030856e-12, rel_tol=1e-12)
            and math.isclose(v2_max_partition, 0.0, abs_tol=0.0)
            and math.isclose(
                v2_summary.get("largest_pair_high_gate_current_relative_reduction"),
                0.0016139591451679268,
                rel_tol=1e-12,
            )
            and v2_summary.get("linear_region_total_resistance_width_kohm_um")
            == [2780.13344904325, 2780.633291954896, 2784.6320382862077],
            (
                f"runner={sum(item.get('status') == 'PASS' for item in v2_runner_checks.values())}/"
                f"{len(v2_runner_checks)} devices={len(p3_v2_solver_log.get('runs', []))} "
                f"dc={len(p3_v2_solver_log.get('solver_records', []))} "
                f"points={len(v2_all_points)} nonzero={v2_max_nonzero:.6e} "
                f"zero={v2_max_zero:.6e}"
            ),
        )
        v2_artifacts = p3_v2_report.get("artifacts", {})
        v2_vtk_artifacts = [
            item
            for entry in p3_v2_state_manifest.get("entries", [])
            for item in entry.get("vtk_files", [])
        ]
        add_check(
            checks,
            "t03_p3_contact:v2_persisted_outputs_and_hashes",
            all(path.exists() for path in v2_output_paths)
            and len(v2_artifacts) == 9
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in v2_artifacts.values()
            )
            and p3_v2_snapshot.get("case_id")
            == "IGZO_T03_P3_CONTACT_RESISTANCE_V2"
            and p3_v2_state_manifest.get("entry_count") == 3
            and sum(
                int(entry.get("node_row_count", 0))
                for entry in p3_v2_state_manifest.get("entries", [])
            )
            == 7257
            and sum(
                int(entry.get("channel_element_count", 0))
                for entry in p3_v2_state_manifest.get("entries", [])
            )
            == 7680
            and len(v2_vtk_artifacts) == 18
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in v2_vtk_artifacts
            )
            and not list(p3_v2_run_dir.parent.glob("p3_contact_resistance_v2_*")),
            (
                f"outputs={sum(path.exists() for path in v2_output_paths)}/"
                f"{len(v2_output_paths)} artifacts={len(v2_artifacts)} "
                f"states={p3_v2_state_manifest.get('entry_count')} vtk={len(v2_vtk_artifacts)}"
            ),
        )
        v2_checker_checks = p3_v2_check.get("checks", [])
        v2_check_summary = p3_v2_check.get("summary", {})
        v2_completion = p3_v2_check.get("t03_p3_completion", {})
        add_check(
            checks,
            "t03_p3_contact:v2_independent_e3_completion_and_boundary",
            p3_v2_check.get("status") == "PASS"
            and p3_v2_check.get("evidence_level") == "E3"
            and p3_v2_check.get("independent_of_simulation_runner") is True
            and p3_v2_check.get("runner_imported") is False
            and p3_v2_check.get("devsim_imported") is False
            and not p3_v2_check.get("failures")
            and len(v2_checker_checks) == 20
            and all(item.get("status") == "PASS" for item in v2_checker_checks)
            and v2_check_summary.get("check_count") == 20
            and v2_check_summary.get("pass_count") == 20
            and v2_check_summary.get("device_count") == 12
            and v2_check_summary.get("dc_solve_count") == 243
            and v2_check_summary.get("reported_point_count") == 156
            and v2_check_summary.get("state_count") == 3
            and v2_check_summary.get("vtk_file_count") == 18
            and v2_completion.get("status") == "PASS"
            and v2_completion.get("complete_p3_contact_group") is True
            and v2_completion.get("complete_t03_five_group_sensitivity") is False
            and v2_completion.get("p5_permitted_after_documentation") is True
            and v2_completion.get("compact_model_or_downstream_permitted") is False
            and "frozen 2D IGZO teaching model"
            in p3_v2_check.get("allowed_claim", "")
            and any(
                "TLM-extracted" in claim
                for claim in p3_v2_check.get("prohibited_claims", [])
            )
            and p3_config.get("remediation", {}).get("physical_input_changed")
            is False
            and p3_config.get("remediation", {}).get("relative_threshold_changed")
            is False
            and p3_config.get("remediation", {}).get(
                "zero_vds_absolute_threshold_changed"
            )
            is False,
            (
                f"checker={sum(item.get('status') == 'PASS' for item in v2_checker_checks)}/"
                f"{len(v2_checker_checks)} completion={v2_completion.get('status')} "
                f"p3={v2_completion.get('complete_p3_contact_group')}"
            ),
        )
        add_check(
            checks,
            "t03_p3_contact:report_image_path_failure_is_preserved",
            p3_report_check_failure.get("status") == "FAIL_PRESERVED"
            and p3_report_check_failure.get("exit_code") == 2
            and p3_report_check_failure.get("failure_classification")
            == "report_source_image_path_error"
            and p3_report_check_failure.get("tcad_or_spice_run") is False
            and p3_report_check_failure.get("physical_input_changed") is False
            and p3_report_check_failure.get("simulation_result_changed") is False
            and p3_report_check_failure.get("acceptance_threshold_changed") is False,
            p3_report_check_failure.get("error", "missing error"),
        )
        failed_checks = [
            item
            for item in p3_failed_checker.get("checks", [])
            if item.get("status") == "FAIL"
        ]
        add_check(
            checks,
            "t03_p3_contact:initial_checker_failure_preserved",
            p3_failed_checker.get("status") == "FAIL"
            and p3_failed_checker.get("contract_status") == "FAIL"
            and p3_failed_checker.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(p3_failed_checker.get("checks", [])) == 30
            and len(failed_checks) == 3
            and [item.get("name") for item in failed_checks]
            == [
                "dependencies:g0_and_complete_t02_gate_passed",
                "literature:magnitudes_are_not_inherited_as_project_metal_parameters",
                "model:no_barrier_injection_or_contact_region_claim_is_implemented",
            ],
            f"status={p3_failed_checker.get('status')} failed_checks={len(failed_checks)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "t03_p3_contact:v2_contract_and_v1_failure", False, str(error))

    p5_config_path = ROOT / "config" / "tcad_t03_p5_temperature.json"
    p5_contract_path = (
        ROOT / "results" / "reports" / "tcad_t03_p5_temperature_input_contract.json"
    )
    p5_report_path = (
        ROOT / "results" / "reports" / "tcad_t03_p5_temperature.json"
    )
    p5_check_path = (
        ROOT / "results" / "reports" / "tcad_t03_p5_temperature_check.json"
    )
    p5_snapshot_path = (
        ROOT
        / "results"
        / "tcad"
        / "t03_sensitivity"
        / "p5_temperature"
        / "input_snapshot.json"
    )
    p5_solver_path = p5_snapshot_path.with_name("solver_log.json")
    p5_manifest_path = p5_snapshot_path.with_name("state_manifest.json")
    p5_metric_path = (
        ROOT / "results" / "tables" / "tcad_t03_p5_temperature_metrics.csv"
    )
    p5_curve_path = (
        ROOT / "results" / "tables" / "tcad_t03_p5_temperature_transfer.csv"
    )
    p5_reference_path = (
        ROOT
        / "results"
        / "tables"
        / "tcad_t03_p5_temperature_t02_c_reproduction.csv"
    )
    p5_state_summary_path = (
        ROOT
        / "results"
        / "tables"
        / "tcad_t03_p5_temperature_state_summary.csv"
    )
    p5_source_path = ROOT / "references" / "t03_p5_temperature_sources.csv"
    try:
        p5_config = json.loads(p5_config_path.read_text(encoding="utf-8"))
        p5_contract = json.loads(p5_contract_path.read_text(encoding="utf-8"))
        p5_report = json.loads(p5_report_path.read_text(encoding="utf-8"))
        p5_check = json.loads(p5_check_path.read_text(encoding="utf-8"))
        p5_snapshot = json.loads(p5_snapshot_path.read_text(encoding="utf-8"))
        p5_solver = json.loads(p5_solver_path.read_text(encoding="utf-8"))
        p5_manifest = json.loads(p5_manifest_path.read_text(encoding="utf-8"))
        p5_experiments = json.loads(experiments_path.read_text(encoding="utf-8"))
        p5_t03 = next(
            item for item in p5_experiments["experiments"] if item["id"] == "T03"
        )
        with p5_source_path.open("r", encoding="utf-8", newline="") as stream:
            p5_source_rows = list(csv.DictReader(stream))
        with p5_metric_path.open("r", encoding="utf-8", newline="") as stream:
            p5_metric_rows = list(csv.DictReader(stream))
        with p5_curve_path.open("r", encoding="utf-8", newline="") as stream:
            p5_curve_rows = list(csv.DictReader(stream))
        with p5_reference_path.open("r", encoding="utf-8", newline="") as stream:
            p5_reference_rows = list(csv.DictReader(stream))
        with p5_state_summary_path.open(
            "r", encoding="utf-8", newline=""
        ) as stream:
            p5_state_summary_rows = list(csv.DictReader(stream))

        p5_checks = p5_contract.get("checks", [])
        add_check(
            checks,
            "t03_p5_temperature:static_contract_e3",
            p5_contract.get("status") == "PASS"
            and p5_contract.get("contract_status") == "PASS"
            and p5_contract.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and p5_contract.get("evidence_level") == "E3"
            and len(p5_checks) == 23
            and all(item.get("status") == "PASS" for item in p5_checks)
            and not p5_contract.get("failures")
            and p5_contract.get("config", {}).get("path")
            == "config/tcad_t03_p5_temperature.json"
            and p5_contract.get("config", {}).get("sha256")
            == sha256(p5_config_path),
            (
                f"checks={sum(item.get('status') == 'PASS' for item in p5_checks)}/"
                f"{len(p5_checks)} simulation={p5_contract.get('simulation_status')}"
            ),
        )
        p5_inputs = p5_contract.get("inputs", {})
        p5_contract_mutable_names = {"project_config", "experiments_config"}
        p5_contract_immutable = {
            name: item
            for name, item in p5_inputs.items()
            if name not in p5_contract_mutable_names
        }
        p5_snapshot_inputs = p5_snapshot.get("inputs", {})
        p5_snapshot_immutable = {
            name: item
            for name, item in p5_snapshot_inputs.items()
            if name not in p5_contract_mutable_names
        }
        add_check(
            checks,
            "t03_p5_temperature:contract_and_run_inputs_are_preserved",
            len(p5_inputs) == 23
            and len(p5_contract_immutable) == 21
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in p5_contract_immutable.values()
            )
            and len(p5_snapshot_inputs) == 25
            and len(p5_snapshot_immutable) == 23
            and p5_snapshot_inputs.get("project_config")
            == p5_inputs.get("project_config")
            and p5_snapshot_inputs.get("experiments_config")
            == p5_inputs.get("experiments_config")
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in p5_snapshot_immutable.values()
            )
            and len(p5_source_rows) == 4
            and {row["source_id"] for row in p5_source_rows}
            == {
                "NIST_CODATA_2022_BOLTZMANN_EV_PER_K",
                "PROJECT_ARCHITECTURE_P5_POINTS",
                "T01_BASELINE_300K",
                "T01_SG_IMPLEMENTATION",
            },
            (
                f"contract_inputs={len(p5_inputs)} "
                f"run_inputs={len(p5_snapshot_inputs)} "
                f"source_rows={len(p5_source_rows)}"
            ),
        )

        p5_model = p5_config.get("temperature_model_contract", {})
        p5_scope = p5_config.get("scope", {})
        p5_plan = p5_contract.get("planned_run", {})
        p5_temperatures = p5_config.get("sensitivity", {}).get("values_k", [])
        p5_thermal_values = p5_config.get("sensitivity", {}).get(
            "thermal_voltage_values_v", []
        )
        p5_computed_thermal = [
            p5_model.get("boltzmann_ev_per_k", 0.0) * value
            for value in p5_temperatures
        ]
        add_check(
            checks,
            "t03_p5_temperature:vt_only_model_and_plan",
            p5_config.get("case_id") == "IGZO_T03_P5_TEMPERATURE_V1"
            and p5_config.get("stage") == "T03-P5-TEMPERATURE"
            and p5_config.get("parameter_group_id") == "P5"
            and p5_config.get("status") == "planned"
            and p5_scope.get("changed_variable") == "lattice_temperature_k"
            and p5_scope.get("changed_variable_count") == 1
            and p5_temperatures == [250.0, 300.0, 350.0]
            and all(
                math.isclose(left, right, rel_tol=1e-12, abs_tol=1e-15)
                for left, right in zip(p5_thermal_values, p5_computed_thermal)
            )
            and p5_model.get("changed_devsim_parameter")
            == "channel region parameter V_t"
            and p5_model.get("mobility_changed") is False
            and p5_model.get("mobility_temperature_law_active") is False
            and p5_model.get("effective_density_of_states_changed") is False
            and p5_model.get("bandgap_or_affinity_changed") is False
            and p5_model.get("permittivity_changed") is False
            and p5_model.get("contact_model_changed") is False
            and p5_model.get("trap_model_active") is False
            and p5_model.get("self_heating_active") is False
            and p5_plan
            == {
                "changed_variable": "lattice_temperature_k",
                "temperature_values_k": [250.0, 300.0, 350.0],
                "thermal_voltage_values_v": [
                    0.021543333155,
                    0.025851999786,
                    0.030160666417,
                ],
                "devices": 3,
                "reported_points": 93,
                "dc_solves": 123,
                "states": 3,
                "vtk_files": 18,
            },
            f"temperatures={p5_temperatures} plan={p5_plan}",
        )

        p5_runner_checks = p5_report.get("checks", {})
        p5_runner_summary = p5_report.get("summary_metrics", {})
        p5_runner_completion = p5_report.get("t03_p5_completion", {})
        p5_reproduction = p5_report.get(
            "t02_c_300k_reference_reproduction", {}
        )
        p5_solver_runs = p5_solver.get("runs", [])
        expected_p5_arrays = {
            "vth_proxy_v": [
                0.24540900212816344,
                0.26385685799760256,
                0.2819769165981422,
            ],
            "ss_proxy_mv_per_dec": [
                117.13784095935709,
                137.59377510040815,
                157.79613260681256,
            ],
            "gm_proxy_s_per_cm": [
                3.9847163606731224e-5,
                3.937599666287622e-5,
                3.8812821127225277e-5,
            ],
            "low_gate_current_proxy_a_per_cm": [
                4.032928160350107e-11,
                2.100900501789906e-10,
                6.945440894357022e-10,
            ],
            "high_gate_current_proxy_a_per_cm": [
                3.6469841491285194e-5,
                3.593724333278673e-5,
                3.529250269768652e-5,
            ],
        }
        add_check(
            checks,
            "t03_p5_temperature:formal_runner_e2_and_numeric_results",
            p5_report.get("status") == "PASS"
            and p5_report.get("case_id") == p5_config.get("case_id")
            and p5_report.get("stage") == "T03-P5-TEMPERATURE"
            and p5_report.get("parameter_group_id") == "P5"
            and p5_report.get("evidence_level") == "E2"
            and len(p5_runner_checks) == 14
            and all(
                item.get("status") == "PASS"
                for item in p5_runner_checks.values()
            )
            and not p5_report.get("failures")
            and p5_runner_summary.get("device_count") == 3
            and p5_runner_summary.get("dc_solve_count") == 123
            and p5_runner_summary.get("reported_point_count") == 93
            and p5_runner_summary.get("state_count") == 3
            and p5_runner_summary.get("vtk_file_count") == 18
            and p5_runner_summary.get("temperature_values_k")
            == [250.0, 300.0, 350.0]
            and p5_runner_summary.get("thermal_voltage_values_v")
            == [0.021543333155, 0.025851999786, 0.030160666417]
            and all(
                len(p5_runner_summary.get(name, [])) == 3
                and all(
                    math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15)
                    for actual, expected in zip(
                        p5_runner_summary[name], expected_values
                    )
                )
                for name, expected_values in expected_p5_arrays.items()
            )
            and math.isclose(
                p5_runner_summary.get(
                    "maximum_relative_terminal_current_imbalance", 1.0
                ),
                4.3730079797195624e-10,
                rel_tol=1e-12,
                abs_tol=1e-18,
            )
            and math.isclose(
                p5_runner_summary.get(
                    "maximum_endpoint_metric_relative_response", 0.0
                ),
                0.9419341662870279,
                rel_tol=1e-12,
                abs_tol=1e-15,
            )
            and len(p5_report.get("curve_points", [])) == 93
            and len(p5_report.get("sensitivity_metrics", [])) == 3
            and len(p5_report.get("topology_summaries", [])) == 3
            and len(p5_solver_runs) == 3
            and [item.get("temperature_k") for item in p5_solver_runs]
            == [250.0, 300.0, 350.0]
            and all(item.get("status") == "PASS" for item in p5_solver_runs)
            and sum(len(item.get("solver_records", [])) for item in p5_solver_runs)
            == 123
            and all(
                record.get("converged") is True
                for item in p5_solver_runs
                for record in item.get("solver_records", [])
            )
            and not p5_solver.get("errors")
            and math.isclose(
                p5_solver.get("wall_seconds", 0.0),
                9.126646766999329,
                rel_tol=1e-12,
                abs_tol=1e-12,
            )
            and p5_reproduction
            == {
                "point_count": 31,
                "maximum_current_relative_difference": 0.0,
                "maximum_center_potential_difference_v": 0.0,
                "maximum_center_density_relative_difference": 0.0,
                "vth_difference_v": 0.0,
                "gm_relative_difference": 0.0,
            }
            and p5_runner_completion.get("status")
            == "RUNNER_PASS_INDEPENDENT_CHECK_REQUIRED"
            and p5_runner_completion.get(
                "p5_temperature_three_point_runner_complete"
            )
            is True
            and p5_runner_completion.get("complete_p5_temperature_group")
            is False
            and p5_runner_completion.get(
                "complete_t03_five_group_sensitivity"
            )
            is False,
            (
                f"runner={sum(item.get('status') == 'PASS' for item in p5_runner_checks.values())}/"
                f"{len(p5_runner_checks)} devices={p5_runner_summary.get('device_count')} "
                f"dc={p5_runner_summary.get('dc_solve_count')}"
            ),
        )

        p5_independent_checks = p5_check.get("checks", [])
        p5_independent_summary = p5_check.get("summary", {})
        p5_independent_completion = p5_check.get("t03_p5_completion", {})
        add_check(
            checks,
            "t03_p5_temperature:independent_e3_closes_numerical_t03",
            p5_check.get("status") == "PASS"
            and p5_check.get("case_id") == p5_config.get("case_id")
            and p5_check.get("stage") == "T03-P5-TEMPERATURE"
            and p5_check.get("parameter_group_id") == "P5"
            and p5_check.get("evidence_level") == "E3"
            and p5_check.get("independent_of_simulation_runner") is True
            and p5_check.get("runner_imported") is False
            and p5_check.get("devsim_imported") is False
            and len(p5_independent_checks) == 15
            and all(
                item.get("status") == "PASS" for item in p5_independent_checks
            )
            and not p5_check.get("failures")
            and p5_independent_summary.get("check_count") == 15
            and p5_independent_summary.get("pass_count") == 15
            and p5_independent_summary.get("device_count") == 3
            and p5_independent_summary.get("dc_solve_count") == 123
            and p5_independent_summary.get("reported_point_count") == 93
            and p5_independent_summary.get("state_count") == 3
            and p5_independent_summary.get("vtk_file_count") == 18
            and p5_independent_summary.get("run_directory_bytes") == 9295067
            and p5_independent_completion
            == {
                "status": "PASS",
                "complete_p5_temperature_group": True,
                "complete_t03_five_group_sensitivity": True,
                "m00_contract_permitted_after_documentation": True,
                "compact_model_simulation_permitted_before_m00_contract": False,
                "spice_circuit_layout_pex_or_hzo_permitted": False,
            }
            and "frozen 2D n-IGZO teaching model"
            in p5_check.get("allowed_claim", "")
            and "all five numerical T03 groups"
            in p5_check.get("allowed_claim", ""),
            (
                f"independent={sum(item.get('status') == 'PASS' for item in p5_independent_checks)}/"
                f"{len(p5_independent_checks)} completion="
                f"{p5_independent_completion.get('status')}"
            ),
        )

        p5_outputs = p5_config.get("outputs", {})
        p5_output_files = [
            ROOT / value
            for name, value in p5_outputs.items()
            if name != "run_directory"
        ]
        p5_run_directory = ROOT / p5_outputs.get("run_directory", "")
        p5_artifacts = p5_report.get("artifacts", {})
        p5_figures = p5_report.get("figures", [])
        p5_state_entries = p5_manifest.get("entries", [])
        p5_state_hash_records = [
            {"path": entry[key], "sha256": entry[hash_key]}
            for entry in p5_state_entries
            for key, hash_key in (
                ("node_csv", "node_csv_sha256"),
                ("element_csv", "element_csv_sha256"),
            )
        ] + [
            item
            for entry in p5_state_entries
            for item in entry.get("vtk_files", [])
        ]
        add_check(
            checks,
            "t03_p5_temperature:persisted_artifacts_states_and_hashes",
            len(p5_outputs) == 13
            and p5_run_directory.is_dir()
            and all(path.is_file() and path.stat().st_size > 0 for path in p5_output_files)
            and len(p5_artifacts) == 7
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in p5_artifacts.values()
            )
            and len(p5_figures) == 2
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in p5_figures
            )
            and p5_manifest.get("case_id") == p5_config.get("case_id")
            and p5_manifest.get("stage") == "T03-P5-TEMPERATURE"
            and p5_manifest.get("entry_count") == 3
            and len(p5_state_entries) == 3
            and p5_report.get("state_outputs") == p5_state_entries
            and sum(item.get("node_row_count", 0) for item in p5_state_entries)
            == 7257
            and sum(
                item.get("channel_element_count", 0) for item in p5_state_entries
            )
            == 7680
            and sum(item.get("vtk_file_count", 0) for item in p5_state_entries)
            == 18
            and len(p5_state_hash_records) == 24
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                for item in p5_state_hash_records
            )
            and len(p5_curve_rows) == 93
            and len(p5_metric_rows) == 3
            and len(p5_reference_rows) == 31
            and len(p5_state_summary_rows) == 3,
            (
                f"artifacts={len(p5_artifacts)} figures={len(p5_figures)} "
                f"states={len(p5_state_entries)} vtk="
                f"{sum(item.get('vtk_file_count', 0) for item in p5_state_entries)}"
            ),
        )

        p5_machine_contract = p5_t03.get("p5_temperature_contract_evidence", {})
        p5_machine_evidence = p5_t03.get("p5_temperature_evidence", {})
        p5_prohibited_claims = " ".join(
            p5_config.get("evidence_boundary", {}).get("prohibited_claims", [])
        )
        add_check(
            checks,
            "t03_p5_temperature:documented_completion_boundary",
            p5_t03.get("status") == "verified"
            and p5_t03.get("completed_parameter_groups")
            == ["P1", "P2", "P3", "P4", "P5"]
            and p5_t03.get("remaining_parameter_groups") == []
            and p5_t03.get("remaining_substages") == []
            and p5_machine_contract.get("status") == "input_contract_ready"
            and p5_machine_contract.get("contract_checks_passed") == 23
            and p5_machine_contract.get("formal_sensitivity_completed") is True
            and p5_machine_evidence.get("status")
            == "formal_sensitivity_verified"
            and p5_machine_evidence.get("runner_checks_passed") == 14
            and p5_machine_evidence.get("independent_checks_passed") == 15
            and p5_machine_evidence.get("complete_p5_temperature_group") is True
            and p5_machine_evidence.get("complete_t03_five_group_sensitivity")
            is True
            and p5_machine_evidence.get(
                "m00_contract_permitted_after_documentation"
            )
            is True
            and p5_machine_evidence.get(
                "compact_model_simulation_permitted_before_m00_contract"
            )
            is False
            and "without running DEVSIM"
            in p5_config.get("evidence_boundary", {}).get(
                "contract_allowed_claim", ""
            )
            and "V_t-only"
            in p5_config.get("evidence_boundary", {}).get(
                "future_run_allowed_claim", ""
            )
            and "experimental or calibrated" in p5_prohibited_claims
            and "physical VTH" in p5_prohibited_claims
            and "compact-model" in p5_prohibited_claims
            and "complete T03 before" in p5_prohibited_claims,
            config.get("tcad_track", {}).get("next_scope", ""),
        )
        p5_project_check_failure = json.loads(
            (
                ROOT
                / "results"
                / "reports"
                / "project_check_t03_p5_p3_next_gate_stale_failed.json"
            ).read_text(encoding="utf-8")
        )
        p5_project_failed_checks = [
            item
            for item in p5_project_check_failure.get("results", [])
            if item.get("status") == "FAIL"
        ]
        add_check(
            checks,
            "t03_p5_temperature:p3_next_gate_stale_checker_failure_preserved",
            p5_project_check_failure.get("status") == "FAIL"
            and p5_project_check_failure.get("checks") == 540
            and p5_project_check_failure.get("failures") == 1
            and len(p5_project_failed_checks) == 1
            and p5_project_failed_checks[0].get("name")
            == "t03_p3_contact:contract_inputs_preserved_and_next_gate"
            and "establish a formal M00 teaching compact-model"
            in p5_project_failed_checks[0].get("detail", ""),
            (
                f"status={p5_project_check_failure.get('status')} "
                f"checks={p5_project_check_failure.get('checks')} "
                f"failures={len(p5_project_failed_checks)}"
            ),
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "t03_p5_temperature:formal_sensitivity_and_independent_check",
            False,
            str(error),
        )

    try:
        m00_config_path = ROOT / "config" / "compact_m00_input_validation.json"
        m00_registry_path = ROOT / "references" / "m00_dataset_registry.csv"
        m00_report_path = ROOT / "results" / "reports" / "m00_compact_model_input_contract.json"
        m00_failure_path = (
            ROOT
            / "results"
            / "reports"
            / "m00_compact_model_input_contract_dependency_status_mismatch_failed.json"
        )
        m00_fit_path = ROOT / "results" / "reports" / "m00_compact_model_fit.json"
        m00_r02_config_path = (
            ROOT / "config" / "compact_m00_input_validation_r02.json"
        )
        m00_r02_report_path = (
            ROOT / "results" / "reports" / "m00_compact_model_input_contract_r02.json"
        )
        m00_run_dir = ROOT / "results" / "compact" / "m00_teaching_fit_r01"
        m00_snapshot_path = m00_run_dir / "input_snapshot.json"
        m00_manifest_path = m00_run_dir / "selected_rows_manifest.csv"
        m00_optimizer_path = m00_run_dir / "optimizer_log.json"
        m00_prediction_path = (
            ROOT / "results" / "tables" / "m00_compact_model_predictions.csv"
        )
        m00_metric_path = (
            ROOT / "results" / "tables" / "m00_compact_model_curve_metrics.csv"
        )
        m00_parameter_path = (
            ROOT / "results" / "tables" / "m00_compact_model_parameters.csv"
        )
        m00_validity_path = (
            ROOT / "models" / "dual_gate" / "igzo_dg_teaching_r01.json"
        )
        m00_config = json.loads(m00_config_path.read_text(encoding="utf-8"))
        m00_report = json.loads(m00_report_path.read_text(encoding="utf-8"))
        m00_failure = json.loads(m00_failure_path.read_text(encoding="utf-8"))
        m00_fit = json.loads(m00_fit_path.read_text(encoding="utf-8"))
        m00_r02_config = json.loads(m00_r02_config_path.read_text(encoding="utf-8"))
        m00_r02_report = json.loads(m00_r02_report_path.read_text(encoding="utf-8"))
        m00_r02_fit_path = ROOT / "results" / "reports" / "m00_compact_model_fit_r02.json"
        m00_r02_check_path = ROOT / "results" / "reports" / "m00_compact_model_fit_check_r02.json"
        m00_r02_fit = json.loads(m00_r02_fit_path.read_text(encoding="utf-8"))
        m00_r02_check = json.loads(m00_r02_check_path.read_text(encoding="utf-8"))
        m00_snapshot = json.loads(m00_snapshot_path.read_text(encoding="utf-8"))
        m00_optimizer = json.loads(m00_optimizer_path.read_text(encoding="utf-8"))
        m00_validity = json.loads(m00_validity_path.read_text(encoding="utf-8"))
        with m00_registry_path.open("r", encoding="utf-8", newline="") as stream:
            m00_registry_rows = list(csv.DictReader(stream))
        with m00_manifest_path.open("r", encoding="utf-8", newline="") as stream:
            m00_manifest_rows = list(csv.DictReader(stream))
        with m00_prediction_path.open("r", encoding="utf-8", newline="") as stream:
            m00_prediction_rows = list(csv.DictReader(stream))
        with m00_metric_path.open("r", encoding="utf-8", newline="") as stream:
            m00_metric_rows = list(csv.DictReader(stream))
        with m00_parameter_path.open("r", encoding="utf-8", newline="") as stream:
            m00_parameter_rows = list(csv.DictReader(stream))
        m00_experiment = next(
            item for item in experiments["experiments"] if item["id"] == "M00"
        )
        m00_checks = m00_report.get("checks", [])
        m00_plan = m00_report.get("planned_fit", {})

        def m00_csv_row_count(path: Path) -> int:
            with path.open("r", encoding="utf-8", newline="") as stream:
                return sum(1 for _ in csv.DictReader(stream))

        add_check(
            checks,
            "m00_contract:static_report_and_frozen_split",
            m00_report.get("status") == "PASS"
            and m00_report.get("contract_status") == "PASS"
            and m00_report.get("fit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_report.get("tcad_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_report.get("circuit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_report.get("evidence_level") == "E3"
            and len(m00_checks) == 25
            and all(item.get("status") == "PASS" for item in m00_checks)
            and not m00_report.get("failures")
            and m00_plan.get("parameter_count") == 11
            and m00_plan.get("training_curves") == 9
            and m00_plan.get("training_scored_points") == 163
            and m00_plan.get("holdout_curves") == 4
            and m00_plan.get("holdout_scored_points") == 70
            and m00_plan.get("zero_vds_invariant_points") == 7,
            (
                f"checks={len(m00_checks)} train={m00_plan.get('training_curves')}/"
                f"{m00_plan.get('training_scored_points')} holdout="
                f"{m00_plan.get('holdout_curves')}/{m00_plan.get('holdout_scored_points')}"
            ),
        )
        registry_valid = (
            len(m00_registry_rows) == 13
            and len({item["dataset_id"] for item in m00_registry_rows}) == 13
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                and m00_csv_row_count(ROOT / item["path"])
                == int(item["row_count"])
                for item in m00_registry_rows
            )
        )
        add_check(
            checks,
            "m00_contract:config_registry_and_source_hashes",
            sha256(m00_config_path) == m00_report.get("config", {}).get("sha256")
            and sha256(ROOT / "scripts" / "check_m00_compact_model_contract.py")
            == m00_report.get("contract_checker", {}).get("sha256")
            and sha256(m00_registry_path) == m00_report.get("registry", {}).get("sha256")
            and m00_report.get("registry", {}).get("dataset_count") == 13
            and registry_valid
            and m00_config.get("dataset_contract", {}).get("formal_fit_dataset_ids")
            == [
                "T01_D_B_IDVD", "T01_D_C_IDVG", "T02_C_DG_TRANSFER",
                "T03_P4_LENGTH_TRANSFER", "T03_P3_V2_OUTPUT",
            ],
            f"registry_rows={len(m00_registry_rows)} config={m00_report.get('config', {}).get('sha256')}",
        )
        m00_failed_checks = [
            item for item in m00_failure.get("checks", [])
            if item.get("status") == "FAIL"
        ]
        add_check(
            checks,
            "m00_contract:dependency_status_mismatch_failure_preserved",
            m00_failure.get("status") == "FAIL"
            and m00_failure.get("fit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_failure.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(m00_failure.get("checks", [])) == 25
            and len(m00_failed_checks) == 1
            and m00_failed_checks[0].get("name")
            == "dependencies:t01_t02_t03_numerical_gates_complete"
            and "T01=complete_e2" in m00_failed_checks[0].get("detail", "")
            and "T02=bidirectional_verified" in m00_failed_checks[0].get("detail", ""),
            f"status={m00_failure.get('status')} failures={len(m00_failed_checks)}",
        )
        m00_fit_checks = m00_fit.get("checks", [])
        m00_fit_failures = [
            item for item in m00_fit_checks if item.get("status") == "FAIL"
        ]
        m00_aggregate = m00_fit.get("aggregate_metrics", {})
        add_check(
            checks,
            "m00_fit:r01_formal_runner_holdout_gm_failure",
            m00_fit.get("status") == "FAIL"
            and m00_fit.get("fit_status") == "FAIL"
            and m00_fit.get("evidence_level") == "E0"
            and m00_fit.get("formal_fit_run") is True
            and m00_fit.get("formal_fit_run_ordinal") == 1
            and m00_fit.get("independent_persisted_evidence_check_complete") is False
            and len(m00_fit_checks) == 24
            and len(m00_fit_failures) == 3
            and [item.get("name") for item in m00_fit_failures]
            == [
                "metrics:holdout_transfer_gm",
                "routes:unexecuted_candidates_generated_only_after_numerical_pass",
                "artifacts:required_outputs_persisted_without_overwrite",
            ]
            and m00_optimizer.get("success") is True
            and m00_optimizer.get("nfev") == 18
            and m00_optimizer.get("objective_curve_count") == 9
            and m00_optimizer.get("objective_scored_point_count") == 163
            and m00_optimizer.get("holdout_curve_ids_in_objective") == []
            and m00_fit.get("holdout_evaluation", {}).get(
                "loaded_after_optimizer_termination"
            )
            is True
            and math.isclose(
                m00_aggregate["train"]["linear"],
                0.07992032871127945,
                rel_tol=1e-12,
            )
            and math.isclose(
                m00_aggregate["train"]["log"],
                0.08322021984917954,
                rel_tol=1e-12,
            )
            and math.isclose(
                m00_aggregate["holdout"]["linear"],
                0.12343417497579379,
                rel_tol=1e-12,
            )
            and math.isclose(
                m00_aggregate["holdout"]["log"],
                0.14878932576826395,
                rel_tol=1e-12,
            ),
            (
                f"runner={sum(item.get('status') == 'PASS' for item in m00_fit_checks)}/"
                f"{len(m00_fit_checks)} nfev={m00_optimizer.get('nfev')} "
                f"holdout={m00_aggregate.get('holdout')}"
            ),
        )
        m00_role_counts = {
            role: sum(
                row.get("selection_role") == role for row in m00_prediction_rows
            )
            for role in ("scored", "zero_vds_invariant", "repeated_low_vds_audit")
        }
        m00_l12_metric = next(
            row
            for row in m00_metric_rows
            if row["curve_id"] == "holdout_t03_dual_length_12"
        )
        m00_t02_metric = next(
            row
            for row in m00_metric_rows
            if row["curve_id"] == "holdout_t02_dual_secondary_0p0"
        )
        m00_artifacts = m00_fit.get("artifacts", {})
        add_check(
            checks,
            "m00_fit:r01_persisted_failure_evidence_and_hashes",
            len(m00_manifest_rows) == 247
            and len(m00_prediction_rows) == 247
            and len(m00_metric_rows) == 13
            and len(m00_parameter_rows) == 11
            and m00_role_counts
            == {
                "scored": 233,
                "zero_vds_invariant": 7,
                "repeated_low_vds_audit": 7,
            }
            and all(
                float(row["lower"]) < float(row["value"]) < float(row["upper"])
                for row in m00_parameter_rows
            )
            and math.isclose(
                float(m00_t02_metric["gm_relative_error"]),
                0.37451382711143505,
                rel_tol=1e-12,
            )
            and m00_t02_metric["curve_acceptance_status"] == "PASS"
            and math.isclose(
                float(m00_l12_metric["gm_relative_error"]),
                0.5123844130308577,
                rel_tol=1e-12,
            )
            and m00_l12_metric["curve_acceptance_status"] == "FAIL"
            and len(m00_artifacts) == 9
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                and (ROOT / item["path"]).stat().st_size == int(item["bytes"])
                for item in m00_artifacts.values()
            )
            and m00_snapshot.get("runner", {}).get("sha256")
            == sha256(ROOT / "models" / "fit_m00_teaching_compact.py")
            and m00_snapshot.get("independent_checker", {}).get("sha256")
            == sha256(ROOT / "scripts" / "check_m00_compact_model_fit.py")
            and m00_validity.get("simulator_status", {}).get("ngspice")
            == "CANDIDATE_ONLY_NOT_EXECUTED",
            (
                f"manifest={len(m00_manifest_rows)} predictions={len(m00_prediction_rows)} "
                f"metrics={len(m00_metric_rows)} parameters={len(m00_parameter_rows)} "
                f"gm={m00_l12_metric['gm_relative_error']} artifacts={len(m00_artifacts)}"
            ),
        )
        m00_forbidden_outputs = [
            ROOT / m00_config["outputs"][key]
            for key in (
                "ngspice_candidate",
                "aimspice_candidate",
                "aimspice_mapping",
                "independent_check_report",
            )
        ]
        add_check(
            checks,
            "m00_fit:r01_failure_boundary_and_downstream_absence",
            all(not path.exists() for path in m00_forbidden_outputs)
            and m00_fit.get("simulator_status", {}).get("tcad") == "NOT_RUN"
            and m00_fit.get("simulator_status", {}).get("circuit") == "NOT_RUN"
            and m00_fit.get("simulator_status", {}).get("ngspice") == "NOT_RUN"
            and m00_fit.get("simulator_status", {}).get("aimspice") == "NOT_RUN"
            and "R01" in config.get("tcad_track", {}).get(
                "m00_r01_failure_boundary", ""
            )
            and "0.512384" in config.get("tcad_track", {}).get(
                "m00_r01_failure_boundary", ""
            ),
            f"absent={sum(not path.exists() for path in m00_forbidden_outputs)}/4",
        )
        m00_machine = m00_experiment.get("contract_evidence", {})
        m00_formal = m00_experiment.get("formal_fit_evidence", {})
        m00_r02_machine = m00_experiment.get("r02_contract_evidence", {})
        m00_r02_execution = m00_experiment.get("r02_execution_evidence", {})
        m00_prohibited = " ".join(
            m00_config.get("evidence_boundary", {}).get("prohibited_claims", [])
        )
        m00_r02_checks = m00_r02_report.get("checks", [])
        m00_r02_plan = m00_r02_report.get("planned_fit", {})
        m00_r02_recovery = m00_r02_config.get("structure_recovery_contract", {})
        m00_r02_basis = m00_r02_recovery.get("pre_fit_identifiability_basis", {})
        m00_r02_change = m00_r02_recovery.get("r02_change", {})
        m00_r02_output_paths = [
            ROOT / value
            for key, value in m00_r02_config["outputs"].items()
            if key != "contract_report"
        ]
        add_check(
            checks,
            "m00_r02_contract:static_structure_recovery",
            m00_r02_report.get("status") == "PASS"
            and m00_r02_report.get("contract_status") == "PASS"
            and m00_r02_report.get("evidence_level") == "E3"
            and m00_r02_report.get("fit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_r02_report.get("tcad_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_r02_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_r02_report.get("circuit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(m00_r02_checks) == 27
            and all(item.get("status") == "PASS" for item in m00_r02_checks)
            and not m00_r02_report.get("failures")
            and m00_r02_plan.get("parameter_count") == 10
            and m00_r02_plan.get("training_curves") == 9
            and m00_r02_plan.get("training_scored_points") == 163
            and m00_r02_plan.get("holdout_curves") == 4
            and m00_r02_plan.get("holdout_scored_points") == 70
            and m00_r02_plan.get("zero_vds_invariant_points") == 7
            and m00_r02_plan.get("fixed_length_geometry_exponent") == 1.0
            and m00_r02_plan.get("free_length_parameter_count") == 1
            and m00_r02_report.get("config", {}).get("sha256")
            == sha256(m00_r02_config_path)
            and m00_r02_report.get("contract_checker", {}).get("sha256")
            == sha256(ROOT / "scripts" / "check_m00_compact_model_contract_r02.py"),
            (
                f"checks={len(m00_r02_checks)} parameters="
                f"{m00_r02_plan.get('parameter_count')} fit="
                f"{m00_r02_report.get('fit_status')} formal_outputs_present="
                f"{sum(path.exists() for path in m00_r02_output_paths)}/"
                f"{len(m00_r02_output_paths)}"
            ),
        )
        unchanged_r02_sections = (
            "dataset_contract", "scored_curves", "split_summary",
            "audit_and_exclusion_contract", "metric_contract", "acceptance",
            "validity_domain",
        )
        m00_r01_parameter_map = {
            item["name"]: item for item in m00_config["parameter_contract"]
        }
        m00_r02_parameter_map = {
            item["name"]: item for item in m00_r02_config["parameter_contract"]
        }
        add_check(
            checks,
            "m00_r02_contract:unchanged_split_thresholds_and_holdout_isolation",
            all(
                m00_r02_config[name] == m00_config[name]
                for name in unchanged_r02_sections
            )
            and m00_r02_config["acceptance"]["maximum_holdout_gm_relative_error"]
            == 0.5
            and set(m00_r02_config["outputs"].values()).isdisjoint(
                set(m00_config["outputs"].values())
            )
            and set(m00_r02_parameter_map)
            == set(m00_r01_parameter_map) - {"length_exponent"}
            and all(
                m00_r02_parameter_map[name] == m00_r01_parameter_map[name]
                for name in set(m00_r02_parameter_map) - {"length_vth_slope_v"}
            )
            and m00_r02_parameter_map["length_vth_slope_v"]["initial"] == 0.0
            and m00_r02_basis.get("training_reference_length_curve_count") == 8
            and m00_r02_basis.get("training_nonreference_length_curve_count") == 1
            and m00_r02_basis.get("r01_holdout_curve_values_or_metrics_used") is False
            and m00_r02_basis.get("r01_fitted_parameter_values_used") is False
            and m00_r02_change.get("fixed_length_geometry_exponent") == 1.0
            and m00_r02_change.get("removed_free_parameter") == "length_exponent"
            and "regularizing teaching assumption" in config.get(
                "tcad_track", {}
            ).get("m00_r02_contract_boundary", ""),
            (
                f"sections={len(unchanged_r02_sections)} parameters="
                f"{len(m00_r02_parameter_map)} fixed_exponent="
                f"{m00_r02_change.get('fixed_length_geometry_exponent')}"
            ),
        )
        m00_r02_runner_path = ROOT / "models" / "fit_m00_teaching_compact_r02.py"
        m00_r02_checker_path = ROOT / "scripts" / "check_m00_compact_model_fit_r02.py"
        m00_r02_runner_source = m00_r02_runner_path.read_text(encoding="utf-8")
        m00_r02_checker_source = m00_r02_checker_path.read_text(encoding="utf-8")
        makefile_source = (ROOT / "Makefile").read_text(encoding="utf-8")
        add_check(
            checks,
            "m00_r02_execution_chain:runner_fixed_kernel_and_holdout_isolation",
            "compact_m00_input_validation_r02.json" in m00_r02_runner_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 24" in m00_r02_runner_source
            and "* (reference_length / lengths)" in m00_r02_runner_source
            and 'parameters["length_exponent"]' not in m00_r02_runner_source
            and '"formal_run_revision": 2' in m00_r02_runner_source
            and '"formal_fit_revision": 2' in m00_r02_runner_source
            and '"command": "make m00-compact-model-r02-fit"'
            in m00_r02_runner_source
            and "if existing_outputs:" in m00_r02_runner_source
            and "refusing to overwrite R02 formal outputs" in m00_r02_runner_source
            and m00_r02_runner_source.find("result = least_squares")
            < m00_r02_runner_source.find("holdout_curves =")
            and 'run_directory.mkdir(parents=True, exist_ok=False)'
            in m00_r02_runner_source
            and 'path.open("x"' in m00_r02_runner_source
            and "M00_COMPACT_MODEL_R02_SYNTHETIC_SELF_TEST_" in m00_r02_runner_source,
            (
                f"runner={m00_r02_runner_path.relative_to(ROOT)} "
                f"outputs_present={sum(path.exists() for path in m00_r02_output_paths)}/"
                f"{len(m00_r02_output_paths)}"
            ),
        )
        checker_import_roots = set(
            re.findall(
                r"^(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)",
                m00_r02_checker_source,
                flags=re.MULTILINE,
            )
        )
        add_check(
            checks,
            "m00_r02_execution_chain:independent_checker_and_make_targets",
            "compact_m00_input_validation_r02.json" in m00_r02_checker_source
            and "EXPECTED_CHECK_COUNT = 20" in m00_r02_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 24" in m00_r02_checker_source
            and "* (reference_length / length)" in m00_r02_checker_source
            and "len(parameter_rows) == 10" in m00_r02_checker_source
            and 'report_path.open("x"' in m00_r02_checker_source
            and checker_import_roots.isdisjoint(
                {"numpy", "scipy", "devsim", "subprocess", "fit_m00_teaching_compact_r02"}
            )
            and "m00-compact-model-r02-self-test:" in makefile_source
            and "m00-compact-model-r02-fit:" in makefile_source
            and "m00-compact-model-r02-fit-check:" in makefile_source,
            f"imports={sorted(checker_import_roots)} checks=20 targets=3",
        )
        m00_r02_fit_checks = m00_r02_fit.get("checks", [])
        m00_r02_check_checks = m00_r02_check.get("checks", [])
        m00_r02_artifacts = m00_r02_fit.get("artifacts", {})
        m00_r02_artifact_hashes_pass = (
            len(m00_r02_artifacts) == 12
            and all(
                (ROOT / item["path"]).is_file()
                and sha256(ROOT / item["path"]) == item["sha256"]
                and (ROOT / item["path"]).stat().st_size == int(item["bytes"])
                for item in m00_r02_artifacts.values()
            )
        )
        add_check(
            checks,
            "m00_r02_formal:runner_two_level_input_isolation_and_pass",
            m00_r02_fit.get("status") == "PASS"
            and m00_r02_fit.get("fit_status") == "PASS"
            and m00_r02_fit.get("evidence_level") == "E2"
            and m00_r02_fit.get("formal_fit_run") is True
            and m00_r02_fit.get("formal_fit_revision") == 2
            and m00_r02_fit.get("formal_fit_run_ordinal") == 1
            and m00_r02_fit.get("independent_persisted_evidence_check_complete") is False
            and len(m00_r02_fit_checks) == 24
            and all(item.get("status") == "PASS" for item in m00_r02_fit_checks)
            and not m00_r02_fit.get("failures")
            and m00_r02_fit.get("optimizer", {}).get("objective_curve_count") == 9
            and m00_r02_fit.get("optimizer", {}).get("objective_scored_point_count") == 163
            and m00_r02_fit.get("optimizer", {}).get("holdout_curve_ids_in_objective") == []
            and m00_r02_fit.get("holdout_evaluation", {}).get(
                "loaded_after_optimizer_termination"
            ) is True
            and m00_r02_fit.get("holdout_evaluation", {}).get(
                "used_to_change_parameters_or_thresholds"
            ) is False
            and m00_r02_fit.get("split_summary", {}).get("holdout_scored_point_count") == 70
            and len(m00_r02_fit.get("parameters", {})) == 10
            and m00_r02_fit.get("simulator_status", {}).get("tcad") == "NOT_RUN"
            and m00_r02_fit.get("simulator_status", {}).get("circuit") == "NOT_RUN"
            and m00_r02_fit.get("simulator_status", {}).get("ngspice")
            == "CANDIDATE_GENERATED_NOT_EXECUTED"
            and m00_r02_fit.get("simulator_status", {}).get("aimspice")
            == "CANDIDATE_GENERATED_NOT_EXECUTED"
            and all(path.exists() for path in m00_r02_output_paths)
            and m00_r02_artifact_hashes_pass,
            (
                f"runner={sum(item.get('status') == 'PASS' for item in m00_r02_fit_checks)}/"
                f"{len(m00_r02_fit_checks)} train="
                f"{m00_r02_fit.get('optimizer', {}).get('objective_curve_count')}/"
                f"{m00_r02_fit.get('optimizer', {}).get('objective_scored_point_count')} "
                f"artifacts={len(m00_r02_artifacts)}"
            ),
        )
        add_check(
            checks,
            "m00_r02_formal:independent_e3_recalculation_and_boundary",
            m00_r02_check.get("status") == "PASS"
            and m00_r02_check.get("evidence_level") == "E3"
            and m00_r02_check.get("independent_of_fit_runner") is True
            and m00_r02_check.get("runner_imported") is False
            and m00_r02_check.get("scipy_imported") is False
            and m00_r02_check.get("numpy_imported") is False
            and len(m00_r02_check_checks) == 20
            and all(item.get("status") == "PASS" for item in m00_r02_check_checks)
            and not m00_r02_check.get("failures")
            and m00_r02_check.get("summary", {}).get("persisted_prediction_count") == 247
            and m00_r02_check.get("summary", {}).get("parameter_count") == 10
            and m00_r02_check.get("m00_completion", {}).get(
                "complete_m00_r02_reference_kernel_fit"
            ) is True
            and m00_r02_check.get("m00_completion", {}).get(
                "m01_contract_permitted_after_documentation"
            ) is True
            and m00_r02_check.get("m00_completion", {}).get(
                "spice_execution_permitted_in_m00"
            ) is False
            and m00_r02_check.get("m00_completion", {}).get(
                "circuit_or_downstream_permitted"
            ) is False
            and m00_r02_check.get("checker", {}).get("sha256")
            == sha256(m00_r02_checker_path),
            (
                f"checks={sum(item.get('status') == 'PASS' for item in m00_r02_check_checks)}/"
                f"{len(m00_r02_check_checks)} predictions="
                f"{m00_r02_check.get('summary', {}).get('persisted_prediction_count')}"
            ),
        )
        add_check(
            checks,
            "m00_contract:machine_state_next_gate_and_boundary",
            m00_experiment.get("status") == "verified"
            and m00_experiment.get("current_evidence") == "E3"
            and m00_experiment.get("depends_on") == ["S00", "T01", "T02", "T03"]
            and m00_machine.get("status") == "input_validation_contract_ready"
            and m00_machine.get("contract_evidence") == "E3"
            and m00_machine.get("contract_checks_passed") == 25
            and m00_machine.get("fit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_machine.get("formal_fit_completed") is False
            and m00_machine.get("m01_or_downstream_permitted") is False
            and m00_formal.get("status") == "failed_holdout_gm_gate"
            and m00_formal.get("formal_fit_run_completed") is True
            and m00_formal.get("formal_fit_run_ordinal") == 1
            and m00_formal.get("formal_fit_passed") is False
            and m00_formal.get("runner_checks_passed") == 21
            and m00_formal.get("runner_checks_total") == 24
            and math.isclose(
                m00_formal.get("failing_value"), 0.5123844130308577,
                rel_tol=1e-12,
            )
            and m00_formal.get("frozen_limit") == 0.5
            and m00_formal.get("independent_check_run") is False
            and m00_formal.get("model_candidates_generated") is False
            and m00_formal.get("m01_or_downstream_permitted") is False
            and m00_r02_machine.get("status")
            == "structural_recovery_contract_ready"
            and m00_r02_machine.get("revision") == 2
            and m00_r02_machine.get("contract_evidence") == "E3"
            and m00_r02_machine.get("contract_checks_passed") == 27
            and m00_r02_machine.get("fit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m00_r02_machine.get("formal_fit_completed") is False
            and m00_r02_machine.get("parameter_count") == 10
            and m00_r02_machine.get("fixed_length_geometry_exponent") == 1.0
            and m00_r02_machine.get("r01_holdout_used_for_structure_or_parameters")
            is False
            and m00_r02_machine.get("r01_failure_preserved") is True
            and m00_r02_machine.get("m01_or_downstream_permitted") is False
            and m00_r02_execution.get("status") == "formal_fit_and_independent_check_verified"
            and m00_r02_execution.get("revision") == 2
            and m00_r02_execution.get("execution_chain_evidence")
            == "E2"
            and m00_r02_execution.get("runner_implemented") is True
            and m00_r02_execution.get("independent_checker_implemented") is True
            and m00_r02_execution.get("synthetic_self_test_passed") is True
            and m00_r02_execution.get("expected_runner_check_count") == 24
            and m00_r02_execution.get("expected_independent_check_count") == 20
            and m00_r02_execution.get("formal_fit_run_completed") is True
            and m00_r02_execution.get("formal_fit_run_ordinal") == 1
            and m00_r02_execution.get("formal_fit_passed") is True
            and m00_r02_execution.get("runner_checks_passed") == 24
            and m00_r02_execution.get("runner_checks_total") == 24
            and m00_r02_execution.get("independent_check_run") is True
            and m00_r02_execution.get("independent_checks_passed") == 20
            and m00_r02_execution.get("independent_checks_total") == 20
            and m00_r02_execution.get("formal_outputs_present") is True
            and m00_r02_execution.get("holdout_scored") is True
            and m00_r02_execution.get("model_candidates_generated") is True
            and m00_r02_execution.get("candidate_execution") is False
            and m00_r02_execution.get("m01_contract_permitted") is True
            and m00_r02_execution.get("m01_or_downstream_permitted") is False
            and (
                config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit an M01 open-source second-simulator recovery contract"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "implement and commit the pure-source Xyce build/tool preflight"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-2"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-3"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-4"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-5"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-5"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-6"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-6 36/37"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
                )
                or r08_scope_active
            )
            and "M01" in config.get("tcad_track", {}).get(
                "m00_r02_formal_result_boundary", ""
            )
            and "experimental fitting" in m00_prohibited
            and "independent external validation" in m00_prohibited
            and "circuit-ready" in m00_prohibited,
            config.get("tcad_track", {}).get("next_scope", ""),
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "m00_contract:static_input_validation", False, str(error))

    m01_contract_path = ROOT / "config" / "m01_simulator_cross_check_contract.json"
    m01_contract_report_path = ROOT / "results" / "reports" / "m01_simulator_cross_check_contract_v3.json"
    m01_checker_path = ROOT / "scripts" / "check_m01_simulator_cross_check_contract.py"
    m01_preflight_config_path = ROOT / "config" / "m01_simulator_preflight_r01.json"
    m01_preflight_runner_path = ROOT / "scripts" / "run_m01_simulator_preflight.py"
    m01_preflight_report_path = ROOT / "results" / "reports" / "m01_simulator_preflight_r01.json"
    try:
        m01_contract = json.loads(m01_contract_path.read_text(encoding="utf-8"))
        m01_report = json.loads(m01_contract_report_path.read_text(encoding="utf-8"))
        m01_experiment = experiment_map["M01"]
        m01_preflight_machine = m01_experiment.get("preflight_execution_chain", {})
        m01_checks = m01_report.get("checks", [])
        m01_future_paths = [
            ROOT / value
            for key, value in m01_contract.get("outputs", {}).items()
            if key not in {
                "contract_report", "historical_failed_contract_reports",
                "run_directory", "preflight_report", "syntax_log",
            }
        ]
        add_check(
            checks,
            "m01_contract:static_boundary_and_no_execution",
            m01_report.get("status") == "PASS"
            and m01_report.get("contract_status") == "PASS"
            and m01_report.get("evidence_level") == "E3"
            and m01_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m01_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m01_report.get("circuit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(m01_checks) == 32
            and all(item.get("status") == "PASS" for item in m01_checks)
            and m01_experiment.get("status") == "preflight_failed_tool_provenance"
            and m01_experiment.get("current_evidence") == "E0"
            and m01_experiment.get("contract_evidence", {}).get("status")
            == "simulator_cross_check_contract_ready"
            and m01_experiment.get("contract_evidence", {}).get("revision") == 3
            and m01_experiment.get("contract_evidence", {}).get("contract_checks_passed") == 32
            and m01_experiment.get("contract_evidence", {}).get("target_row_count") == 247
            and m01_experiment.get("contract_evidence", {}).get("target_curve_count") == 13
            and m01_experiment.get("contract_evidence", {}).get("simulation_run_by_contract_check") is False
            and m01_experiment.get("contract_evidence", {}).get("ngspice_run_by_contract_check") is False
            and m01_experiment.get("contract_evidence", {}).get("aimspice_run_by_contract_check") is False
            and m01_experiment.get("contract_evidence", {}).get("circuit_or_downstream_permitted") is False
            and config.get("tcad_track", {}).get("m01_contract_boundary", "").startswith(
                "The E3 M01 revision-3 contract freezes"
            )
            and m01_report.get("config", {}).get("sha256") == sha256(m01_contract_path)
            and m01_report.get("checker", {}).get("sha256") == sha256(m01_checker_path)
            and all(not path.exists() for path in m01_future_paths)
            and m01_contract_path.exists()
            and m01_contract_report_path.exists(),
            f"checks={sum(item.get('status') == 'PASS' for item in m01_checks)}/{len(m01_checks)} future_absent="
            f"{sum(not path.exists() for path in m01_future_paths)}/{len(m01_future_paths)}",
        )
        m01_preflight_config = json.loads(
            m01_preflight_config_path.read_text(encoding="utf-8")
        )
        m01_preflight_runner_source = m01_preflight_runner_path.read_text(
            encoding="utf-8"
        )
        preflight_outputs = [
            ROOT / value for value in m01_preflight_config["outputs"].values()
        ]
        numerical_outputs = [
            ROOT / value
            for value in m01_preflight_config[
                "numerical_outputs_that_must_remain_absent"
            ]
        ]
        ng_preflight = m01_preflight_config["routes"]["ngspice_behavioral"]
        aim_preflight = m01_preflight_config["routes"]["aimspice_level15"]
        preflight_rules = m01_preflight_config["preflight_rules"]
        add_check(
            checks,
            "m01_preflight_chain:committed_contract_binding_and_exclusive_outputs",
            m01_preflight_config.get("status") == "preflight_planned"
            and m01_preflight_config.get("revision") == 1
            and m01_preflight_config.get("evidence_level_before_run") == "E0"
            and m01_preflight_config.get("bound_contract_commit")
            == "49b93a456b490b56f7d431ee24e11b3a388c66b5"
            and m01_preflight_config.get("contract", {}).get("sha256")
            == sha256(m01_contract_path)
            and m01_preflight_config.get("contract", {}).get("report_sha256")
            == sha256(m01_contract_report_path)
            and all(path.exists() for path in preflight_outputs)
            and all(not path.exists() for path in numerical_outputs),
            (
                f"outputs_present={sum(path.exists() for path in preflight_outputs)}/"
                f"{len(preflight_outputs)} numerical_absent="
                f"{sum(not path.exists() for path in numerical_outputs)}/"
                f"{len(numerical_outputs)}"
            ),
        )
        add_check(
            checks,
            "m01_preflight_chain:single_version_probe_and_no_aimspice_or_netlist",
            ng_preflight.get("allowed_probe_argv")
            == [ng_preflight.get("tool_path"), "--version"]
            and preflight_rules.get("ngspice_version_probe_only") is True
            and preflight_rules.get("aimspice_process_invocation_by_runner") is False
            and preflight_rules.get("device_netlist_invocation_permitted") is False
            and preflight_rules.get("numerical_curve_generation_permitted") is False
            and aim_preflight.get("runner_must_not_invoke") is True
            and aim_preflight.get("license_provenance", {}).get(
                "auditable_for_formal_project_evidence"
            ) is False
            and aim_preflight.get("documented_batch_cli_status") == "NOT_ESTABLISHED"
            and m01_preflight_runner_source.count("subprocess.run(") == 1
            and "ng_result = subprocess.run(" in m01_preflight_runner_source
            and "aimspice_runner_invoked=false" in m01_preflight_runner_source
            and "M01_SIMULATOR_PREFLIGHT_" in m01_preflight_runner_source,
            "one ngspice version subprocess; AIM-Spice and device netlists prohibited",
        )
        add_check(
            checks,
            "m01_preflight_chain:machine_state_boundary_and_make_target",
            m01_preflight_machine.get("status")
            == "formal_preflight_failed_tool_provenance"
            and m01_preflight_machine.get("revision") == 1
            and m01_preflight_machine.get("current_evidence") == "E0"
            and m01_preflight_machine.get("expected_check_count") == 13
            and m01_preflight_machine.get("formal_preflight_run_completed") is True
            and m01_preflight_machine.get("formal_preflight_run_ordinal") == 1
            and m01_preflight_machine.get("formal_preflight_status") == "FAIL"
            and m01_preflight_machine.get("checks_passed") == 11
            and m01_preflight_machine.get("checks_failed") == 2
            and m01_preflight_machine.get("aimspice_process_invocation_permitted") is False
            and m01_preflight_machine.get("aimspice_process_invoked") is False
            and m01_preflight_machine.get("device_netlist_invocation_permitted") is False
            and m01_preflight_machine.get("device_netlist_invoked") is False
            and m01_preflight_machine.get("numerical_curve_generation_permitted") is False
            and m01_preflight_machine.get("numerical_outputs_created") is False
            and m01_preflight_machine.get("circuit_or_downstream_permitted") is False
            and "m01-simulator-preflight:" in (ROOT / "Makefile").read_text(
                encoding="utf-8"
            )
            and "11/13 with E0/FAIL"
            in config.get("tcad_track", {}).get(
                "m01_r01_preflight_failure_boundary", ""
            ),
            (
                f"status={m01_preflight_machine.get('status')} "
                f"evidence={m01_preflight_machine.get('current_evidence')}"
            ),
        )
        m01_preflight_report = json.loads(
            m01_preflight_report_path.read_text(encoding="utf-8")
        )
        preflight_checks = m01_preflight_report.get("checks", [])
        preflight_failures = m01_preflight_report.get("failures", [])
        preflight_failure_names = {
            item.get("name") for item in preflight_failures
        }
        preflight_log_path = ROOT / m01_preflight_report["log"]["path"]
        preflight_log = preflight_log_path.read_text(encoding="utf-8")
        add_check(
            checks,
            "m01_preflight_result:expected_tool_provenance_failure_preserved",
            m01_preflight_report.get("status") == "FAIL"
            and m01_preflight_report.get("preflight_status") == "FAIL"
            and m01_preflight_report.get("evidence_level") == "E0"
            and m01_preflight_report.get("ngspice_preflight_status") == "PASS"
            and m01_preflight_report.get("aimspice_preflight_status") == "FAIL"
            and len(preflight_checks) == 13
            and sum(item.get("status") == "PASS" for item in preflight_checks) == 11
            and preflight_failure_names == {
                "aimspice:license_provenance_is_auditable",
                "aimspice:documented_reproducible_batch_cli",
            }
            and m01_preflight_report.get("config", {}).get("sha256")
            == sha256(m01_preflight_config_path)
            and m01_preflight_report.get("runner", {}).get("sha256")
            == sha256(m01_preflight_runner_path)
            and m01_preflight_report.get("log", {}).get("sha256")
            == sha256(preflight_log_path)
            and sha256(m01_preflight_report_path)
            == m01_preflight_machine.get("artifact_hashes", {}).get(
                "preflight_report_sha256"
            )
            and sha256(preflight_log_path)
            == m01_preflight_machine.get("artifact_hashes", {}).get(
                "preflight_log_sha256"
            ),
            f"checks={sum(item.get('status') == 'PASS' for item in preflight_checks)}/{len(preflight_checks)} failures={sorted(preflight_failure_names)}",
        )
        process_invocations = m01_preflight_report.get("summary", {}).get(
            "simulator_process_invocations", []
        )
        add_check(
            checks,
            "m01_preflight_result:no_aimspice_netlist_numerical_or_downstream_execution",
            m01_preflight_report.get("device_simulation_status")
            == "NOT_RUN_BY_PREFLIGHT"
            and m01_preflight_report.get("spice_numerical_status")
            == "NOT_RUN_BY_PREFLIGHT"
            and m01_preflight_report.get("circuit_status")
            == "NOT_RUN_BY_PREFLIGHT"
            and len(process_invocations) == 1
            and process_invocations[0].get("tool") == "ngspice"
            and process_invocations[0].get("argv")
            == ng_preflight.get("allowed_probe_argv")
            and process_invocations[0].get("netlist_argument_supplied") is False
            and m01_preflight_report.get("summary", {}).get(
                "aimspice_invoked_by_runner"
            ) is False
            and m01_preflight_report.get("summary", {}).get(
                "numerical_outputs_created"
            ) is False
            and all(not path.exists() for path in numerical_outputs)
            and "device_netlist_invoked=false" in preflight_log
            and "numerical_curve_generated=false" in preflight_log
            and "aimspice_runner_invoked=false" in preflight_log
            and "formal_result=FAIL_STOP_M01" in preflight_log,
            f"processes={len(process_invocations)} numerical_absent={sum(not path.exists() for path in numerical_outputs)}/{len(numerical_outputs)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "m01_contract:static_boundary_and_no_execution", False, str(error))

    m01_recovery_config_path = ROOT / "config" / "m01_open_source_recovery_contract_r01.json"
    m01_recovery_report_path = ROOT / "results" / "reports" / "m01_open_source_recovery_contract_r01_e3.json"
    m01_recovery_checker_path = ROOT / "scripts" / "check_m01_open_source_recovery_contract.py"
    try:
        m01_recovery_config = json.loads(m01_recovery_config_path.read_text(encoding="utf-8"))
        m01_recovery_report = json.loads(m01_recovery_report_path.read_text(encoding="utf-8"))
        m01_recovery_experiment = experiment_map["M01"].get("open_source_recovery_contract", {})
        recovery_checks = m01_recovery_report.get("checks", [])
        recovery_future_paths = [
            ROOT / value
            for key, value in m01_recovery_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        recovery_failed_archive = ROOT / "results" / "reports" / "m01_open_source_recovery_contract_r01.json"
        add_check(
            checks,
            "m01_open_source_recovery:static_contract_and_no_execution",
            m01_recovery_report.get("status") == "PASS"
            and m01_recovery_report.get("contract_status") == "PASS"
            and m01_recovery_report.get("evidence_level") == "E3"
            and m01_recovery_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m01_recovery_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and m01_recovery_report.get("circuit_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(recovery_checks) == 30
            and all(item.get("status") == "PASS" for item in recovery_checks)
            and m01_recovery_report.get("config", {}).get("sha256") == sha256(m01_recovery_config_path)
            and m01_recovery_report.get("checker", {}).get("sha256") == sha256(m01_recovery_checker_path)
            and m01_recovery_report.get("config", {}).get("path") == "config/m01_open_source_recovery_contract_r01.json"
            and m01_recovery_config.get("outputs", {}).get("contract_report") == str(m01_recovery_report_path.relative_to(ROOT))
            and m01_recovery_experiment.get("status") == "contract_ready"
            and m01_recovery_experiment.get("evidence_level") == "E3"
            and m01_recovery_experiment.get("simulation_run_by_contract_check") is False
            and m01_recovery_experiment.get("device_netlist_created_by_contract_check") is False
            and m01_recovery_experiment.get("numerical_outputs_created_by_contract_check") is False
            and m01_recovery_config.get("xyce_source_provenance", {}).get("proprietary_binary_accepted") is False
            and m01_recovery_config.get("xyce_source_provenance", {}).get("source_build_required") is True
            and m01_recovery_config.get("scope", {}).get("active_material_scope") == "IGZO only"
            and m01_recovery_config.get("no_execution_rules", {}).get("circuit_or_downstream_permitted") is False
            and all(not path.exists() for path in recovery_future_paths)
            and recovery_failed_archive.is_file()
            and json.loads(recovery_failed_archive.read_text(encoding="utf-8")).get("status") == "FAIL",
            f"checks={sum(item.get('status') == 'PASS' for item in recovery_checks)}/{len(recovery_checks)} future_absent="
            f"{sum(not path.exists() for path in recovery_future_paths)}/{len(recovery_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(checks, "m01_open_source_recovery:static_contract_and_no_execution", False, str(error))

    m01_xyce_preflight_config_path = ROOT / "config" / "m01_xyce_build_preflight_r01.json"
    m01_xyce_preflight_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r01.json"
    )
    m01_xyce_preflight_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_contract.py"
    )
    m01_xyce_preflight_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight.py"
    m01_xyce_preflight_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight.py"
    try:
        xyce_preflight_config = json.loads(
            m01_xyce_preflight_config_path.read_text(encoding="utf-8")
        )
        xyce_contract_report = json.loads(
            m01_xyce_preflight_contract_report_path.read_text(encoding="utf-8")
        )
        xyce_contract_checks = xyce_contract_report.get("checks", [])
        xyce_machine = experiment_map["M01"].get("xyce_build_preflight", {})
        xyce_future_paths = [
            ROOT / value
            for key, value in xyce_preflight_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        xyce_run_report_path = ROOT / xyce_preflight_config["outputs"]["preflight_report"]
        xyce_independent_report_path = ROOT / xyce_preflight_config["outputs"]["independent_check_report"]
        xyce_run_report = json.loads(xyce_run_report_path.read_text(encoding="utf-8"))
        xyce_independent_report = json.loads(
            xyce_independent_report_path.read_text(encoding="utf-8")
        )
        xyce_formal_paths = [
            ROOT / value for value in xyce_preflight_config["formal_outputs_that_must_remain_absent"]
        ]
        xyce_runner_source = m01_xyce_preflight_runner_path.read_text(encoding="utf-8")
        xyce_checker_source = m01_xyce_preflight_checker_path.read_text(encoding="utf-8")
        makefile_source = (ROOT / "Makefile").read_text(encoding="utf-8")
        historical_hash = xyce_preflight_config.get("historical_hash_boundary", {})
        add_check(
            checks,
            "m01_xyce_preflight:static_contract_and_unexecuted_chain",
            xyce_contract_report.get("status") == "PASS"
            and xyce_contract_report.get("contract_status") == "PASS"
            and xyce_contract_report.get("evidence_level") == "E3"
            and xyce_contract_report.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(xyce_contract_checks) == 25
            and all(item.get("status") == "PASS" for item in xyce_contract_checks)
            and xyce_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_preflight_config_path)
            and xyce_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_preflight_contract_checker_path)
            and xyce_machine.get("status") == "preflight_failed_build"
            and xyce_machine.get("current_evidence") == "E0"
            and xyce_machine.get("expected_contract_check_count") == 25
            and xyce_machine.get("expected_runner_check_count") == 29
            and xyce_machine.get("expected_independent_check_count") == 20
            and xyce_machine.get("formal_run_completed") is False
            and xyce_machine.get("device_netlist_invoked") is False
            and xyce_machine.get("numerical_outputs_created") is False
            and xyce_machine.get("serial_build") is True
            and xyce_machine.get("mpi_build") is False
            and xyce_machine.get("fortran_build") is False
            and xyce_machine.get("proprietary_binary_accepted") is False
            and xyce_machine.get("preflight_run_completed") is True
            and xyce_machine.get("preflight_run_ordinal") == 1
            and xyce_machine.get("preflight_status") == "FAIL"
            and xyce_machine.get("runner_checks_passed") == 14
            and xyce_machine.get("runner_checks_failed") == 15
            and xyce_machine.get("independent_check_status") == "FAIL"
            and xyce_machine.get("independent_checks_passed") == 9
            and xyce_machine.get("independent_checks_failed") == 11
            and xyce_run_report.get("status") == "FAIL"
            and xyce_run_report.get("evidence_level") == "E0"
            and len(xyce_run_report.get("checks", [])) == 29
            and sum(item.get("status") == "PASS" for item in xyce_run_report.get("checks", [])) == 14
            and xyce_run_report.get("summary", {}).get("formal_device_dc_invoked") is False
            and xyce_run_report.get("summary", {}).get("formal_m01_outputs_created") is False
            and xyce_independent_report.get("status") == "FAIL"
            and xyce_independent_report.get("evidence_level") == "E0"
            and len(xyce_independent_report.get("checks", [])) == 20
            and sum(item.get("status") == "PASS" for item in xyce_independent_report.get("checks", [])) == 9
            and xyce_independent_report.get("summary", {}).get("formal_device_dc_invoked") is False
            and xyce_independent_report.get("summary", {}).get("formal_m01_outputs_created") is False
            and all((ROOT / value).is_file() for value in xyce_machine.get("result_paths", []))
            and all(not path.exists() for path in xyce_formal_paths)
            and sha256(xyce_run_report_path) == xyce_machine.get("artifact_hashes", {}).get("preflight_report_sha256")
            and sha256(xyce_independent_report_path) == xyce_machine.get("artifact_hashes", {}).get("independent_check_report_sha256")
            and historical_hash.get("historical_contract_and_report_must_remain_unchanged")
            is True
            and historical_hash.get("historical_recorded_xyce_archive_sha256")
            != historical_hash.get("actual_rehashed_xyce_archive_sha256")
            and xyce_preflight_config.get("source_provenance", {})
            .get("xyce", {})
            .get("archive_sha256")
            == "b5a883196f0a2b3972fd13c541fecf04735bfabc7d124d7c7e17de707204f4e2"
            and "EXPECTED_CHECK_COUNT = 29" in xyce_runner_source
            and "subprocess.run" in xyce_runner_source
            and '"-syntax"' in xyce_runner_source
            and "formal_device_dc_invoked=false" in xyce_runner_source
            and "EXPECTED_CHECK_COUNT = 20" in xyce_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 29" in xyce_checker_source
            and "import subprocess" not in xyce_checker_source
            and "m01-xyce-build-preflight-contract-check:" in makefile_source
            and "m01-xyce-build-preflight:" in makefile_source
            and "m01-xyce-build-preflight-check:" in makefile_source
            and config.get("tcad_track", {})
            .get("m01_xyce_build_preflight_contract_boundary", "")
            .startswith("The revision-1 Xyce build/tool preflight contract pins"),
            f"contract_checks={sum(item.get('status') == 'PASS' for item in xyce_contract_checks)}/{len(xyce_contract_checks)} "
            f"runner={sum(item.get('status') == 'PASS' for item in xyce_run_report.get('checks', []))}/29 "
            f"independent={sum(item.get('status') == 'PASS' for item in xyce_independent_report.get('checks', []))}/20",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight:static_contract_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r02_config_path = ROOT / "config" / "m01_xyce_build_preflight_r02.json"
    m01_xyce_r02_contract_report_path = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r02.json"
    m01_xyce_r02_contract_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r02_contract.py"
    m01_xyce_r02_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r02.py"
    m01_xyce_r02_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r02.py"
    try:
        r02_config = json.loads(m01_xyce_r02_config_path.read_text(encoding="utf-8"))
        r02_contract_report = json.loads(m01_xyce_r02_contract_report_path.read_text(encoding="utf-8"))
        r02_machine = experiment_map["M01"].get("xyce_build_preflight_r02", {})
        r02_contract_checks = r02_contract_report.get("checks", [])
        r02_future_paths = [
            ROOT / value
            for key, value in r02_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r02_formal_paths = [ROOT / value for value in r02_config.get("formal_outputs_that_must_remain_absent", [])]
        r02_runner_source = m01_xyce_r02_runner_path.read_text(encoding="utf-8")
        r02_checker_source = m01_xyce_r02_checker_path.read_text(encoding="utf-8")
        r02_contract_source = m01_xyce_r02_contract_checker_path.read_text(encoding="utf-8")
        add_check(
            checks,
            "m01_xyce_preflight_r02:static_contract_and_unexecuted_chain",
            r02_contract_report.get("status") == "FAIL"
            and r02_contract_report.get("contract_status") == "FAIL"
            and r02_contract_report.get("evidence_level") == "E0"
            and r02_contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r02_contract_checks) == 25
            and sum(item.get("status") == "PASS" for item in r02_contract_checks) == 22
            and sum(item.get("status") == "FAIL" for item in r02_contract_checks) == 3
            and r02_contract_report.get("config", {}).get("sha256") == sha256(m01_xyce_r02_config_path)
            and r02_contract_report.get("checker", {}).get("sha256") == sha256(m01_xyce_r02_contract_checker_path)
            and r02_machine.get("status") == "contract_failed_checker"
            and r02_machine.get("revision") == 2
            and r02_machine.get("current_evidence") == "E0"
            and r02_machine.get("contract_check_completed") is True
            and r02_machine.get("contract_status") == "FAIL"
            and r02_machine.get("contract_checks_passed") == 22
            and r02_machine.get("contract_checks_failed") == 3
            and r02_machine.get("formal_run_completed") is False
            and r02_machine.get("device_netlist_invoked") is False
            and r02_machine.get("numerical_outputs_created") is False
            and r02_machine.get("explicit_blas_lapack_paths") is True
            and r02_machine.get("r01_failure_preserved") is True
            and all(not path.exists() for path in r02_future_paths)
            and all(not path.exists() for path in r02_formal_paths)
            and r02_config.get("build_plan", {}).get("suitesparse_cmake_options")
            and "m01-xyce-build-preflight-r02-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r02:" in makefile_source
            and "m01-xyce-build-preflight-r02-check:" in makefile_source
            and (
                config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-3"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-3"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-4"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-5"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-5"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-6"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-6 36/37"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
                )
                or r08_scope_active
            ),
            f"contract_checks={sum(item.get('status') == 'PASS' for item in r02_contract_checks)}/{len(r02_contract_checks)} future_absent="
            f"{sum(not path.exists() for path in r02_future_paths)}/{len(r02_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r02:static_contract_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r03_config_path = ROOT / "config" / "m01_xyce_build_preflight_r03.json"
    m01_xyce_r03_contract_report_path = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r03.json"
    m01_xyce_r03_contract_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r03_contract.py"
    m01_xyce_r03_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r03.py"
    m01_xyce_r03_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r03.py"
    try:
        r03_config = json.loads(m01_xyce_r03_config_path.read_text(encoding="utf-8"))
        r03_machine = experiment_map["M01"].get("xyce_build_preflight_r03", {})
        r03_contract_exists = m01_xyce_r03_contract_report_path.is_file()
        r03_contract_report = (
            json.loads(m01_xyce_r03_contract_report_path.read_text(encoding="utf-8"))
            if r03_contract_exists
            else {}
        )
        r03_contract_checks = r03_contract_report.get("checks", [])
        r03_future_paths = [
            ROOT / value
            for key, value in r03_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r03_formal_paths = [
            ROOT / value for value in r03_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r03_runner_source = m01_xyce_r03_runner_path.read_text(encoding="utf-8")
        r03_checker_source = m01_xyce_r03_checker_path.read_text(encoding="utf-8")
        r03_contract_source = m01_xyce_r03_contract_checker_path.read_text(encoding="utf-8")
        r03_planned_state = (
            not r03_contract_exists
            and r03_machine.get("status") == "contract_planned"
            and r03_machine.get("current_evidence") == "E0"
            and r03_machine.get("contract_check_completed") is False
        )
        r03_ready_state = (
            r03_contract_exists
            and r03_contract_report.get("status") == "PASS"
            and r03_contract_report.get("contract_status") == "PASS"
            and r03_contract_report.get("evidence_level") == "E3"
            and r03_contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r03_contract_checks) == 25
            and all(item.get("status") == "PASS" for item in r03_contract_checks)
            and r03_contract_report.get("config", {}).get("sha256") == sha256(m01_xyce_r03_config_path)
            and r03_contract_report.get("checker", {}).get("sha256") == sha256(m01_xyce_r03_contract_checker_path)
            and r03_machine.get("status") == "contract_ready"
            and r03_machine.get("current_evidence") == "E3"
            and r03_machine.get("contract_check_completed") is True
            and r03_machine.get("contract_status") == "PASS"
            and r03_machine.get("contract_checks_passed") == 25
            and r03_machine.get("contract_checks_failed") == 0
            and r03_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r03_contract_report_path)
            and r03_machine.get("result_paths") == [
                "results/reports/m01_xyce_build_preflight_contract_r03.json"
            ]
        )
        r03_failed_state = (
            r03_contract_exists
            and r03_contract_report.get("status") == "FAIL"
            and r03_contract_report.get("contract_status") == "FAIL"
            and r03_contract_report.get("evidence_level") == "E0"
            and r03_contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r03_contract_checks) == 25
            and sum(item.get("status") == "PASS" for item in r03_contract_checks) == 21
            and sum(item.get("status") == "FAIL" for item in r03_contract_checks) == 4
            and r03_contract_report.get("config", {}).get("sha256") == sha256(m01_xyce_r03_config_path)
            and r03_contract_report.get("checker", {}).get("sha256") == sha256(m01_xyce_r03_contract_checker_path)
            and r03_machine.get("status") == "contract_failed_checker"
            and r03_machine.get("current_evidence") == "E0"
            and r03_machine.get("contract_check_completed") is True
            and r03_machine.get("contract_status") == "FAIL"
            and r03_machine.get("contract_checks_passed") == 21
            and r03_machine.get("contract_checks_failed") == 4
            and r03_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r03_contract_report_path)
            and r03_machine.get("result_paths") == [
                "results/reports/m01_xyce_build_preflight_contract_r03.json"
            ]
        )
        next_scope = config.get("tcad_track", {}).get("next_scope", "")
        next_scope_valid = (
            (r03_planned_state and next_scope.startswith("establish and commit M01 Xyce build/tool preflight revision-3"))
            or (r03_ready_state and next_scope.startswith("execute M01 Xyce build/tool preflight revision-3"))
            or (
                r03_failed_state
                and (
                    next_scope.startswith("establish and commit M01 Xyce build/tool preflight revision-4")
                    or next_scope.startswith("establish and commit M01 Xyce build/tool preflight revision-5")
                    or next_scope.startswith("execute M01 Xyce build/tool preflight revision-5")
                    or next_scope.startswith("establish and commit M01 Xyce build/tool preflight revision-6")
                    or next_scope.startswith(
                        "preserve and commit the M01 Xyce build/tool preflight revision-6 36/37"
                    )
                    or next_scope.startswith(
                        "establish and commit M01 Xyce build/tool preflight revision-7"
                    )
                    or next_scope.startswith(
                        "execute M01 Xyce build/tool preflight revision-7"
                    )
                    or next_scope.startswith(
                        "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
                    )
                    or r08_scope_active
                )
            )
        )
        add_check(
            checks,
            "m01_xyce_preflight_r03:contract_state_and_unexecuted_chain",
            r03_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R03"
            and r03_config.get("revision") == 3
            and r03_machine.get("revision") == 3
            and r03_machine.get("expected_contract_check_count") == 25
            and r03_machine.get("expected_runner_check_count") == 29
            and r03_machine.get("expected_independent_check_count") == 20
            and r03_machine.get("formal_run_completed") is False
            and r03_machine.get("preflight_run_completed") is False
            and r03_machine.get("device_netlist_invoked") is False
            and r03_machine.get("numerical_outputs_created") is False
            and r03_machine.get("ngspice_invoked") is False
            and r03_machine.get("aimspice_invoked") is False
            and r03_machine.get("explicit_blas_lapack_paths") is True
            and r03_machine.get("r01_failure_preserved") is True
            and r03_machine.get("r02_failure_preserved") is True
            and r03_machine.get("serial_build") is True
            and r03_machine.get("mpi_build") is False
            and r03_machine.get("fortran_build") is False
            and r03_machine.get("proprietary_binary_accepted") is False
            and r03_machine.get("circuit_or_downstream_permitted") is False
            and all(not path.exists() for path in r03_future_paths)
            and all(not path.exists() for path in r03_formal_paths)
            and r03_config.get("build_plan", {}).get("parallel_jobs") == 2
            and r03_config.get("build_plan", {}).get("suitesparse_cmake_options")
            and "-DBLAS_LIBRARIES=/home/reachgao/.local/linear-algebra/lib/libblas.so"
            in r03_config["build_plan"]["suitesparse_cmake_options"]
            and "-DLAPACK_LIBRARIES=/home/reachgao/.local/linear-algebra/lib/liblapack.so"
            in r03_config["build_plan"]["suitesparse_cmake_options"]
            and "formal_device_dc_invoked=false" in r03_runner_source
            and "EXPECTED_CHECK_COUNT = 20" in r03_checker_source
            and "import subprocess" not in r03_checker_source
            and "re.search" in r03_contract_source
            and "m01-xyce-build-preflight-r03-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r03:" in makefile_source
            and "m01-xyce-build-preflight-r03-check:" in makefile_source
            and (r03_planned_state or r03_ready_state or r03_failed_state)
            and next_scope_valid,
            f"planned={r03_planned_state} ready={r03_ready_state} failed={r03_failed_state} future_absent="
            f"{sum(not path.exists() for path in r03_future_paths)}/{len(r03_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r03:contract_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r04_config_path = ROOT / "config" / "m01_xyce_build_preflight_r04.json"
    m01_xyce_r04_contract_report_path = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r04.json"
    m01_xyce_r04_contract_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r04_contract.py"
    m01_xyce_r04_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r04.py"
    m01_xyce_r04_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r04.py"
    try:
        r04_config = json.loads(m01_xyce_r04_config_path.read_text(encoding="utf-8"))
        r04_machine = experiment_map["M01"].get("xyce_build_preflight_r04", {})
        r04_contract_exists = m01_xyce_r04_contract_report_path.is_file()
        r04_contract_report = (
            json.loads(m01_xyce_r04_contract_report_path.read_text(encoding="utf-8"))
            if r04_contract_exists
            else {}
        )
        r04_contract_checks = r04_contract_report.get("checks", [])
        r04_future_paths = [
            ROOT / value
            for key, value in r04_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r04_formal_paths = [
            ROOT / value for value in r04_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r04_runner_source = m01_xyce_r04_runner_path.read_text(encoding="utf-8")
        r04_checker_source = m01_xyce_r04_checker_path.read_text(encoding="utf-8")
        r04_contract_source = m01_xyce_r04_contract_checker_path.read_text(encoding="utf-8")
        r04_planned_state = (
            not r04_contract_exists
            and r04_machine.get("status") == "contract_planned"
            and r04_machine.get("current_evidence") == "E0"
            and r04_machine.get("contract_check_completed") is False
        )
        r04_failed_state = (
            r04_contract_exists
            and r04_contract_report.get("status") == "FAIL"
            and r04_contract_report.get("contract_status") == "FAIL"
            and r04_contract_report.get("evidence_level") == "E0"
            and r04_contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r04_contract_checks) == 26
            and sum(item.get("status") == "PASS" for item in r04_contract_checks) == 25
            and sum(item.get("status") == "FAIL" for item in r04_contract_checks) == 1
            and r04_contract_report.get("failures", [{}])[0].get("name")
            == "experiment:r04_is_planned_and_prior_failures_bound"
            and r04_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r04_config_path)
            and r04_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r04_contract_checker_path)
            and r04_machine.get("status") == "contract_failed_checker"
            and r04_machine.get("current_evidence") == "E0"
            and r04_machine.get("contract_check_completed") is True
            and r04_machine.get("contract_status") == "FAIL"
            and r04_machine.get("contract_checks_passed") == 25
            and r04_machine.get("contract_checks_failed") == 1
            and r04_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r04_contract_report_path)
            and r04_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r04.json"]
        )
        r04_next_scope_valid = (
            r04_planned_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "establish and commit M01 Xyce build/tool preflight revision-4"
            )
        ) or (
            r04_failed_state
            and (
                config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-5"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-5"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-6"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-6 36/37"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
                )
                or r08_scope_active
            )
        )
        add_check(
            checks,
            "m01_xyce_preflight_r04:contract_state_and_unexecuted_chain",
            (r04_planned_state or r04_failed_state)
            and r04_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R04"
            and r04_config.get("revision") == 4
            and r04_machine.get("revision") == 4
            and r04_machine.get("expected_contract_check_count") == 26
            and r04_machine.get("expected_runner_check_count") == 29
            and r04_machine.get("expected_independent_check_count") == 20
            and r04_machine.get("formal_run_completed") is False
            and r04_machine.get("preflight_run_completed") is False
            and r04_machine.get("device_netlist_invoked") is False
            and r04_machine.get("numerical_outputs_created") is False
            and r04_machine.get("ngspice_invoked") is False
            and r04_machine.get("aimspice_invoked") is False
            and r04_machine.get("explicit_blas_lapack_paths") is True
            and r04_machine.get("r01_failure_preserved") is True
            and r04_machine.get("r02_failure_preserved") is True
            and r04_machine.get("r03_failure_preserved") is True
            and r04_machine.get("serial_build") is True
            and r04_machine.get("mpi_build") is False
            and r04_machine.get("fortran_build") is False
            and r04_machine.get("proprietary_binary_accepted") is False
            and r04_machine.get("circuit_or_downstream_permitted") is False
            and all(not path.exists() for path in r04_future_paths)
            and all(not path.exists() for path in r04_formal_paths)
            and r04_config.get("build_plan", {}).get("parallel_jobs") == 2
            and "-DBLAS_LIBRARIES=/home/reachgao/.local/linear-algebra/lib/libblas.so"
            in r04_config["build_plan"]["suitesparse_cmake_options"]
            and "-DLAPACK_LIBRARIES=/home/reachgao/.local/linear-algebra/lib/liblapack.so"
            in r04_config["build_plan"]["suitesparse_cmake_options"]
            and "run_m01_xyce_build_preflight.py" in r04_runner_source
            and "formal_device_dc_invoked=false" in r04_runner_source
            and "check_m01_xyce_build_preflight.py" in r04_checker_source
            and "EXPECTED_CHECK_COUNT = 20" in r04_checker_source
            and "import subprocess" not in r04_checker_source
            and "r03_contract_failure_binding" in r04_contract_source
            and "m01-xyce-build-preflight-r04-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r04:" in makefile_source
            and "m01-xyce-build-preflight-r04-check:" in makefile_source
            and r04_next_scope_valid,
            f"planned={r04_planned_state} failed={r04_failed_state} future_absent="
            f"{sum(not path.exists() for path in r04_future_paths)}/{len(r04_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r04:contract_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r05_config_path = ROOT / "config" / "m01_xyce_build_preflight_r05.json"
    m01_xyce_r05_contract_report_path = ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r05.json"
    m01_xyce_r05_contract_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r05_contract.py"
    m01_xyce_r05_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r05.py"
    m01_xyce_r05_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r05.py"
    m01_xyce_r05_preflight_report_path = ROOT / "results" / "reports" / "m01_xyce_build_preflight_r05.json"
    m01_xyce_r05_independent_report_path = ROOT / "results" / "reports" / "m01_xyce_build_preflight_check_r05.json"
    try:
        r05_config = json.loads(m01_xyce_r05_config_path.read_text(encoding="utf-8"))
        r05_machine = experiment_map["M01"].get("xyce_build_preflight_r05", {})
        r05_contract_exists = m01_xyce_r05_contract_report_path.is_file()
        r05_contract_report = (
            json.loads(m01_xyce_r05_contract_report_path.read_text(encoding="utf-8"))
            if r05_contract_exists
            else {}
        )
        r05_contract_checks = r05_contract_report.get("checks", [])
        r05_preflight_exists = m01_xyce_r05_preflight_report_path.is_file()
        r05_preflight_report = (
            json.loads(m01_xyce_r05_preflight_report_path.read_text(encoding="utf-8"))
            if r05_preflight_exists
            else {}
        )
        r05_preflight_checks = r05_preflight_report.get("checks", [])
        r05_future_paths = [
            ROOT / value
            for key, value in r05_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r05_formal_paths = [
            ROOT / value for value in r05_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r05_runner_source = m01_xyce_r05_runner_path.read_text(encoding="utf-8")
        r05_checker_source = m01_xyce_r05_checker_path.read_text(encoding="utf-8")
        r05_contract_source = m01_xyce_r05_contract_checker_path.read_text(encoding="utf-8")
        r05_r04_binding = r05_config.get("r04_contract_failure_binding", {})
        r05_planned_state = (
            not r05_contract_exists
            and r05_machine.get("status") == "contract_planned"
            and r05_machine.get("current_evidence") == "E0"
            and r05_machine.get("contract_check_completed") is False
        )
        r05_ready_state = (
            r05_contract_exists
            and r05_contract_report.get("status") == "PASS"
            and r05_contract_report.get("contract_status") == "PASS"
            and r05_contract_report.get("evidence_level") == "E3"
            and r05_contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and r05_contract_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r05_contract_checks) == 27
            and all(item.get("status") == "PASS" for item in r05_contract_checks)
            and r05_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r05_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r05_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r05_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r05_config_path)
            and r05_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r05_contract_checker_path)
            and r05_machine.get("status") == "contract_ready"
            and r05_machine.get("current_evidence") == "E3"
            and r05_machine.get("contract_check_completed") is True
            and r05_machine.get("contract_status") == "PASS"
            and r05_machine.get("contract_checks_passed") == 27
            and r05_machine.get("contract_checks_failed") == 0
            and r05_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r05_contract_report_path)
            and r05_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r05.json"]
        )
        r05_failed_required_paths = [
            ROOT / value
            for value in r05_machine.get("result_paths", [])
        ]
        r05_failed_absent_paths = [
            ROOT / r05_config["outputs"][key]
            for key in (
                "bsource_self_test_netlist",
                "bsource_self_test_log",
                "bsource_self_test_output",
                "device_syntax_netlist",
                "device_syntax_log",
                "device_syntax_output",
                "independent_check_report",
            )
        ]
        r05_xyce_build_log = ROOT / r05_config["outputs"]["run_directory"] / "xyce_build_install.log"
        r05_xyce_build_text = (
            r05_xyce_build_log.read_text(encoding="utf-8", errors="replace")
            if r05_xyce_build_log.is_file()
            else ""
        )
        r05_failed_state = (
            r05_contract_exists
            and r05_preflight_exists
            and r05_contract_report.get("status") == "PASS"
            and r05_contract_report.get("evidence_level") == "E3"
            and r05_preflight_report.get("status") == "FAIL"
            and r05_preflight_report.get("preflight_status") == "FAIL"
            and r05_preflight_report.get("build_status") == "FAIL"
            and r05_preflight_report.get("evidence_level") == "E0"
            and len(r05_preflight_checks) == 29
            and sum(item.get("status") == "PASS" for item in r05_preflight_checks) == 19
            and sum(item.get("status") == "FAIL" for item in r05_preflight_checks) == 10
            and r05_preflight_report.get("summary", {}).get("process_invocations") == 12
            and r05_preflight_report.get("summary", {}).get("ngspice_invoked") is False
            and r05_preflight_report.get("summary", {}).get("aimspice_invoked") is False
            and r05_preflight_report.get("summary", {}).get("controlled_bsource_self_test_invoked") is False
            and r05_preflight_report.get("summary", {}).get("device_syntax_only_invoked") is False
            and r05_preflight_report.get("summary", {}).get("formal_device_dc_invoked") is False
            and r05_preflight_report.get("summary", {}).get("formal_m01_outputs_created") is False
            and r05_preflight_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r05_config_path)
            and r05_preflight_report.get("runner", {}).get("sha256")
            == sha256(m01_xyce_r05_runner_path)
            and r05_machine.get("status") == "preflight_failed_build"
            and r05_machine.get("current_evidence") == "E0"
            and r05_machine.get("contract_check_completed") is True
            and r05_machine.get("contract_status") == "PASS"
            and r05_machine.get("contract_checks_passed") == 27
            and r05_machine.get("contract_checks_failed") == 0
            and r05_machine.get("preflight_run_completed") is True
            and r05_machine.get("preflight_run_ordinal") == 1
            and r05_machine.get("preflight_status") == "FAIL"
            and r05_machine.get("runner_checks_passed") == 19
            and r05_machine.get("runner_checks_failed") == 10
            and r05_machine.get("independent_check_run") is False
            and r05_machine.get("independent_check_status") == "NOT_RUN_RUNNER_FAILED"
            and r05_machine.get("suitesparse_install_passed") is True
            and r05_machine.get("trilinos_install_passed") is True
            and r05_machine.get("xyce_configure_passed") is True
            and r05_machine.get("xyce_install_passed") is False
            and r05_machine.get("controlled_bsource_self_test_invoked") is False
            and r05_machine.get("device_syntax_only_invoked") is False
            and r05_machine.get("artifact_hashes", {}).get("preflight_report_sha256")
            == sha256(m01_xyce_r05_preflight_report_path)
            and r05_machine.get("artifact_hashes", {}).get("preflight_log_sha256")
            == sha256(ROOT / r05_config["outputs"]["preflight_log"])
            and r05_machine.get("artifact_hashes", {}).get("source_manifest_sha256")
            == sha256(ROOT / r05_config["outputs"]["source_manifest"])
            and r05_machine.get("artifact_hashes", {}).get("build_manifest_sha256")
            == sha256(ROOT / r05_config["outputs"]["build_manifest"])
            and all(path.is_file() for path in r05_failed_required_paths)
            and all(not path.exists() for path in r05_failed_absent_paths)
            and Path(r05_config["source_provenance"]["suitesparse"]["install_prefix"]).is_dir()
            and Path(r05_config["source_provenance"]["trilinos"]["install_prefix"]).is_dir()
            and not Path(r05_config["source_provenance"]["xyce"]["install_prefix"]).exists()
            and "cannot open: No such file or directory" in r05_xyce_build_text
            and "exec of /usr/bin/m4 failed" in r05_xyce_build_text
            and not m01_xyce_r05_independent_report_path.exists()
        )
        r05_next_scope_valid = (
            r05_planned_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "establish and commit M01 Xyce build/tool preflight revision-5"
            )
        ) or (
            r05_ready_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute M01 Xyce build/tool preflight revision-5"
            )
        ) or (
            r05_failed_state
            and (
                config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-6"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-6 36/37"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "establish and commit M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "execute M01 Xyce build/tool preflight revision-7"
                )
                or config.get("tcad_track", {}).get("next_scope", "").startswith(
                    "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
                )
                or r08_scope_active
            )
        )
        add_check(
            checks,
            "m01_xyce_preflight_r05:contract_and_runner_state",
            (r05_planned_state or r05_ready_state or r05_failed_state)
            and r05_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R05"
            and r05_config.get("revision") == 5
            and r05_config.get("status") == "preflight_planned"
            and r05_machine.get("revision") == 5
            and r05_machine.get("expected_contract_check_count") == 27
            and r05_machine.get("expected_runner_check_count") == 29
            and r05_machine.get("expected_independent_check_count") == 20
            and r05_machine.get("formal_run_completed") is False
            and r05_machine.get("preflight_run_completed") is r05_failed_state
            and r05_machine.get("device_netlist_invoked") is False
            and r05_machine.get("numerical_outputs_created") is False
            and r05_machine.get("ngspice_invoked") is False
            and r05_machine.get("aimspice_invoked") is False
            and r05_machine.get("explicit_blas_lapack_paths") is True
            and r05_machine.get("r01_failure_preserved") is True
            and r05_machine.get("r02_failure_preserved") is True
            and r05_machine.get("r03_failure_preserved") is True
            and r05_machine.get("r04_failure_preserved") is True
            and r05_machine.get("serial_build") is True
            and r05_machine.get("mpi_build") is False
            and r05_machine.get("fortran_build") is False
            and r05_machine.get("proprietary_binary_accepted") is False
            and r05_machine.get("circuit_or_downstream_permitted") is False
            and (
                (not r05_failed_state and all(not path.exists() for path in r05_future_paths))
                or r05_failed_state
            )
            and all(not path.exists() for path in r05_formal_paths)
            and r05_config.get("build_plan", {}).get("parallel_jobs") == 2
            and "-DBLAS_LIBRARIES=/home/reachgao/.local/linear-algebra/lib/libblas.so"
            in r05_config["build_plan"]["suitesparse_cmake_options"]
            and "-DLAPACK_LIBRARIES=/home/reachgao/.local/linear-algebra/lib/liblapack.so"
            in r05_config["build_plan"]["suitesparse_cmake_options"]
            and r05_r04_binding.get("contract_report")
            == "results/reports/m01_xyce_build_preflight_contract_r04.json"
            and r05_r04_binding.get("contract_report_sha256")
            == sha256(m01_xyce_r04_contract_report_path)
            and r05_r04_binding.get("contract_checks_passed") == 25
            and r05_r04_binding.get("contract_checks_failed") == 1
            and r05_r04_binding.get("must_remain_unchanged") is True
            and "run_m01_xyce_build_preflight.py" in r05_runner_source
            and "formal_device_dc_invoked=false" in r05_runner_source
            and "check_m01_xyce_build_preflight.py" in r05_checker_source
            and "EXPECTED_CHECK_COUNT = 20" in r05_checker_source
            and "import subprocess" not in r05_checker_source
            and "r04_contract_failure_binding" in r05_contract_source
            and 'r05["status"] == "contract_planned"' in r05_contract_source
            and "m01-xyce-build-preflight-r05-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r05:" in makefile_source
            and "m01-xyce-build-preflight-r05-check:" in makefile_source
            and r05_next_scope_valid,
            f"planned={r05_planned_state} ready={r05_ready_state} failed={r05_failed_state} future_absent="
            f"{sum(not path.exists() for path in r05_future_paths)}/{len(r05_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r05:contract_and_runner_state",
            False,
            str(error),
        )

    m01_xyce_r06_config_path = ROOT / "config" / "m01_xyce_build_preflight_r06.json"
    m01_xyce_r06_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r06.json"
    )
    m01_xyce_r06_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r06_contract.py"
    )
    m01_xyce_r06_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r06.py"
    m01_xyce_r06_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r06.py"
    m01_xyce_r06_common_path = ROOT / "scripts" / "m01_xyce_r06_common.py"
    try:
        r06_config = json.loads(m01_xyce_r06_config_path.read_text(encoding="utf-8"))
        r06_machine = experiment_map["M01"].get("xyce_build_preflight_r06", {})
        r06_contract_exists = m01_xyce_r06_contract_report_path.is_file()
        r06_contract_report = (
            json.loads(m01_xyce_r06_contract_report_path.read_text(encoding="utf-8"))
            if r06_contract_exists
            else {}
        )
        r06_contract_checks = r06_contract_report.get("checks", [])
        r06_future_paths = [
            ROOT / value
            for key, value in r06_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r06_formal_paths = [
            ROOT / value
            for value in r06_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r06_sources = r06_config["source_provenance"]
        r06_tools = r06_config["toolchain"]
        r06_reuse = r06_config["dependency_reuse"]
        r06_new_roots = [
            *(Path(value) for value in r06_config["build_directories"].values()),
            Path(r06_tools["generator_install_prefix"]),
            Path(r06_sources["xyce"]["install_prefix"]),
        ]
        r06_generator_sources_ok = all(
            Path(r06_sources[key]["archive_path"]).is_file()
            and sha256(Path(r06_sources[key]["archive_path"]))
            == r06_sources[key]["archive_sha256"]
            and (Path(r06_sources[key]["source_dir"]) / "configure").is_file()
            and sha256(Path(r06_sources[key]["source_dir"]) / "configure")
            == r06_sources[key]["configure_sha256"]
            and (Path(r06_sources[key]["source_dir"]) / r06_sources[key]["license_file"]).is_file()
            and sha256(
                Path(r06_sources[key]["source_dir"]) / r06_sources[key]["license_file"]
            )
            == r06_sources[key]["license_sha256"]
            for key in ("m4", "bison", "flex")
        )
        r06_reuse_actual = {
            key: digest_r06_tree(Path(r06_reuse[key]["install_prefix"]))
            for key in ("suitesparse", "trilinos")
        }
        r06_reuse_ok = all(
            all(
                r06_reuse_actual[key].get(field) == r06_reuse[key].get(field)
                for field in r06_reuse_actual[key]
            )
            for key in ("suitesparse", "trilinos")
        )
        r06_planned_state = (
            not r06_contract_exists
            and r06_machine.get("status") == "contract_planned"
            and r06_machine.get("current_evidence") == "E0"
            and r06_machine.get("contract_check_completed") is False
            and r06_machine.get("result_paths") == []
            and r06_machine.get("artifact_hashes") == {}
        )
        r06_ready_state = (
            r06_contract_exists
            and r06_contract_report.get("status") == "PASS"
            and r06_contract_report.get("contract_status") == "PASS"
            and r06_contract_report.get("evidence_level") == "E3"
            and r06_contract_report.get("simulation_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and r06_contract_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and r06_contract_report.get("build_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r06_contract_checks) == 37
            and all(item.get("status") == "PASS" for item in r06_contract_checks)
            and r06_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r06_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r06_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r06_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r06_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r06_config_path)
            and r06_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r06_contract_checker_path)
            and r06_machine.get("status") == "contract_ready"
            and r06_machine.get("current_evidence") == "E3"
            and r06_machine.get("contract_check_completed") is True
            and r06_machine.get("contract_status") == "PASS"
            and r06_machine.get("contract_checks_passed") == 37
            and r06_machine.get("contract_checks_failed") == 0
            and r06_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r06_contract_report_path)
            and r06_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r06.json"]
        )
        r06_failed_state = (
            r06_contract_exists
            and r06_contract_report.get("status") == "FAIL"
            and r06_contract_report.get("contract_status") == "FAIL"
            and r06_contract_report.get("evidence_level") == "E0"
            and r06_contract_report.get("simulation_status")
            == "NOT_RUN_BY_CONTRACT_CHECK"
            and r06_contract_report.get("spice_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and r06_contract_report.get("build_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r06_contract_checks) == 37
            and sum(item.get("status") == "PASS" for item in r06_contract_checks) == 36
            and [item.get("name") for item in r06_contract_checks if item.get("status") == "FAIL"]
            == ["checker:r06_independent_standard_library"]
            and r06_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r06_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r06_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r06_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r06_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r06_config_path)
            and r06_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r06_contract_checker_path)
            and r06_machine.get("status") == "contract_failed_checker"
            and r06_machine.get("current_evidence") == "E0"
            and r06_machine.get("contract_check_completed") is True
            and r06_machine.get("contract_status") == "FAIL"
            and r06_machine.get("contract_checks_passed") == 36
            and r06_machine.get("contract_checks_failed") == 1
            and r06_machine.get("contract_failure_category")
            == "independent_checker_runner_path_literal_false_positive"
            and r06_machine.get("artifact_hashes", {}).get("contract_config_sha256")
            == sha256(m01_xyce_r06_config_path)
            and r06_machine.get("artifact_hashes", {}).get("contract_checker_sha256")
            == sha256(m01_xyce_r06_contract_checker_path)
            and r06_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r06_contract_report_path)
            and r06_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r06.json"]
        )
        r06_next_scope_valid = (
            r06_planned_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "establish and commit M01 Xyce build/tool preflight revision-6"
            )
        ) or (
            r06_ready_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute M01 Xyce build/tool preflight revision-6"
            )
        ) or (
            r06_failed_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-6 36/37"
            )
        ) or (
            r06_failed_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "establish and commit M01 Xyce build/tool preflight revision-7"
            )
        ) or (
            r06_failed_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute M01 Xyce build/tool preflight revision-7"
            )
        ) or (
            r06_failed_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
            )
        ) or (
            r06_failed_state and r08_scope_active
        )
        r06_runner_source = m01_xyce_r06_runner_path.read_text(encoding="utf-8")
        r06_checker_source = m01_xyce_r06_checker_path.read_text(encoding="utf-8")
        r06_contract_source = m01_xyce_r06_contract_checker_path.read_text(encoding="utf-8")
        r06_common_source = m01_xyce_r06_common_path.read_text(encoding="utf-8")
        add_check(
            checks,
            "m01_xyce_preflight_r06:contract_state_and_unexecuted_chain",
            (r06_planned_state or r06_ready_state or r06_failed_state)
            and r06_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R06"
            and r06_config.get("revision") == 6
            and r06_config.get("status") == "preflight_planned"
            and r06_machine.get("revision") == 6
            and r06_machine.get("expected_contract_check_count") == 37
            and r06_machine.get("expected_runner_check_count") == 47
            and r06_machine.get("expected_independent_check_count") == 25
            and r06_machine.get("formal_run_completed") is False
            and r06_machine.get("preflight_run_completed") is False
            and r06_machine.get("device_netlist_invoked") is False
            and r06_machine.get("numerical_outputs_created") is False
            and r06_machine.get("ngspice_invoked") is False
            and r06_machine.get("aimspice_invoked") is False
            and r06_machine.get("serial_build") is True
            and r06_machine.get("mpi_build") is False
            and r06_machine.get("fortran_build") is False
            and r06_machine.get("source_built_m4_bison_flex") is True
            and r06_machine.get("reuse_r05_suitesparse") is True
            and r06_machine.get("reuse_r05_trilinos") is True
            and r06_machine.get("reuse_r05_partial_xyce") is False
            and r06_machine.get("r05_failure_preserved") is True
            and r06_machine.get("implementation_project_check_history", {}).get(
                "failed_report_sha256"
            )
            == sha256(
                ROOT
                / r06_machine["implementation_project_check_history"][
                    "failed_report_path"
                ]
            )
            and r06_machine.get("implementation_project_check_history", {}).get(
                "failed_checks_passed"
            )
            == 655
            and r06_machine.get("implementation_project_check_history", {}).get(
                "failed_checks_failed"
            )
            == 1
            and r06_machine.get("implementation_project_check_history", {}).get(
                "failure_category"
            )
            == "contract_checker_source_import_literal_false_positive"
            and r06_machine.get("implementation_project_check_history", {}).get(
                "fixed_check_status"
            )
            == "PASS"
            and r06_machine.get("implementation_project_check_history", {}).get(
                "fixed_checks_passed"
            )
            == 657
            and r06_machine.get("implementation_project_check_history", {}).get(
                "failure_preserved"
            )
            is True
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "failed_report_sha256"
            )
            == sha256(
                ROOT
                / r06_machine["failure_state_project_check_history"][
                    "failed_report_path"
                ]
            )
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "failed_checks_passed"
            )
            == 653
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "failed_checks_failed"
            )
            == 5
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "failure_category"
            )
            == "historical_next_scope_allowlists_stale_after_r06_contract_failure"
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "fixed_check_status"
            )
            == "PASS"
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "fixed_checks_passed"
            )
            == 659
            and r06_machine.get("failure_state_project_check_history", {}).get(
                "failure_preserved"
            )
            is True
            and r06_machine.get("proprietary_binary_accepted") is False
            and r06_machine.get("circuit_or_downstream_permitted") is False
            and all(not path.exists() for path in r06_future_paths)
            and all(not path.exists() for path in r06_formal_paths)
            and all(not path.exists() for path in r06_new_roots)
            and len(r06_new_roots) == len(set(r06_new_roots))
            and r06_generator_sources_ok
            and r06_reuse_ok
            and r06_reuse.get("dependency_rebuild_permitted") is False
            and r06_config["build_plan"].get("generator_build_order") == ["m4", "bison", "flex"]
            and r06_config["build_plan"].get("suitesparse_or_trilinos_commands_permitted")
            is False
            and r06_config["build_plan"].get("parallel_jobs") == 2
            and r06_config["r05_failure_binding"].get("preflight_report_sha256")
            == sha256(m01_xyce_r05_preflight_report_path)
            and "EXPECTED_CHECK_COUNT = 47" in r06_runner_source
            and "formal_device_dc_invoked=false" in r06_runner_source
            and "r05_partial_xyce_reused=false" in r06_runner_source
            and "EXPECTED_CHECK_COUNT = 25" in r06_checker_source
            and "import subprocess" not in r06_checker_source
            and "EXPECTED_CHECK_COUNT = 37" in r06_contract_source
            and re.search(r"^import subprocess\b", r06_contract_source, re.MULTILINE) is None
            and "def digest_tree" in r06_common_source
            and "import subprocess" not in r06_common_source
            and "m01-xyce-build-preflight-r06-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r06:" in makefile_source
            and "m01-xyce-build-preflight-r06-check:" in makefile_source
            and r06_next_scope_valid,
            f"planned={r06_planned_state} ready={r06_ready_state} failed={r06_failed_state} future_absent="
            f"{sum(not path.exists() for path in r06_future_paths)}/{len(r06_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r06:contract_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r07_config_path = ROOT / "config" / "m01_xyce_build_preflight_r07.json"
    m01_xyce_r07_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r07.json"
    )
    m01_xyce_r07_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r07_contract.py"
    )
    m01_xyce_r07_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r07.py"
    m01_xyce_r07_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r07.py"
    m01_xyce_r07_common_path = ROOT / "scripts" / "m01_xyce_r07_common.py"
    m01_xyce_r07_preflight_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_r07.json"
    )
    try:
        r07_config = json.loads(m01_xyce_r07_config_path.read_text(encoding="utf-8"))
        r07_machine = experiment_map["M01"].get("xyce_build_preflight_r07", {})
        r07_contract_exists = m01_xyce_r07_contract_report_path.is_file()
        r07_preflight_exists = m01_xyce_r07_preflight_report_path.is_file()
        r07_contract_report = (
            json.loads(m01_xyce_r07_contract_report_path.read_text(encoding="utf-8"))
            if r07_contract_exists
            else {}
        )
        r07_preflight_report = (
            json.loads(m01_xyce_r07_preflight_report_path.read_text(encoding="utf-8"))
            if r07_preflight_exists
            else {}
        )
        r07_contract_checks = r07_contract_report.get("checks", [])
        r07_preflight_checks = r07_preflight_report.get("checks", [])
        r07_future_paths = [
            ROOT / value
            for key, value in r07_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r07_formal_paths = [
            ROOT / value
            for value in r07_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r07_sources = r07_config["source_provenance"]
        r07_tools = r07_config["toolchain"]
        r07_reuse = r07_config["dependency_reuse"]
        r07_new_roots = [
            *(Path(value) for value in r07_config["build_directories"].values()),
            Path(r07_tools["generator_install_prefix"]),
            Path(r07_sources["xyce"]["install_prefix"]),
        ]
        r07_generator_sources_ok = all(
            Path(r07_sources[key]["archive_path"]).is_file()
            and sha256(Path(r07_sources[key]["archive_path"]))
            == r07_sources[key]["archive_sha256"]
            and (Path(r07_sources[key]["source_dir"]) / "configure").is_file()
            and sha256(Path(r07_sources[key]["source_dir"]) / "configure")
            == r07_sources[key]["configure_sha256"]
            and (
                Path(r07_sources[key]["source_dir"])
                / r07_sources[key]["license_file"]
            ).is_file()
            and sha256(
                Path(r07_sources[key]["source_dir"])
                / r07_sources[key]["license_file"]
            )
            == r07_sources[key]["license_sha256"]
            for key in ("m4", "bison", "flex")
        )
        r07_reuse_actual = {
            key: digest_r07_tree(Path(r07_reuse[key]["install_prefix"]))
            for key in ("suitesparse", "trilinos")
        }
        r07_reuse_ok = all(
            all(
                r07_reuse_actual[key].get(field) == r07_reuse[key].get(field)
                for field in r07_reuse_actual[key]
            )
            for key in ("suitesparse", "trilinos")
        )
        r07_r06 = r07_config["r06_contract_failure_binding"]
        r07_r06_bindings = [
            (r07_r06["config_path"], r07_r06["config_sha256"]),
            (
                r07_r06["contract_checker_path"],
                r07_r06["contract_checker_sha256"],
            ),
            (r07_r06["contract_report_path"], r07_r06["contract_report_sha256"]),
            (
                r07_r06["implementation_project_check_failure_path"],
                r07_r06["implementation_project_check_failure_sha256"],
            ),
            (
                r07_r06["failure_state_project_check_failure_path"],
                r07_r06["failure_state_project_check_failure_sha256"],
            ),
        ]
        r07_r06_binding_ok = all(
            (ROOT / relative).is_file() and sha256(ROOT / relative) == expected
            for relative, expected in r07_r06_bindings
        )
        r07_planned_state = (
            not r07_contract_exists
            and r07_machine.get("status") == "contract_planned"
            and r07_machine.get("current_evidence") == "E0"
            and r07_machine.get("contract_check_completed") is False
            and r07_machine.get("result_paths") == []
            and r07_machine.get("artifact_hashes") == {}
        )
        r07_ready_state = (
            r07_contract_exists
            and r07_contract_report.get("status") == "PASS"
            and r07_contract_report.get("contract_status") == "PASS"
            and r07_contract_report.get("evidence_level") == "E3"
            and r07_contract_report.get("build_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r07_contract_checks) == 39
            and all(item.get("status") == "PASS" for item in r07_contract_checks)
            and r07_contract_report.get("summary", {}).get("simulator_processes_invoked")
            == 0
            and r07_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r07_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r07_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r07_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r07_config_path)
            and r07_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r07_contract_checker_path)
            and r07_machine.get("status") == "contract_ready"
            and r07_machine.get("current_evidence") == "E3"
            and r07_machine.get("contract_check_completed") is True
            and r07_machine.get("contract_status") == "PASS"
            and r07_machine.get("contract_checks_passed") == 39
            and r07_machine.get("contract_checks_failed") == 0
            and r07_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r07_contract_report_path)
            and r07_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r07.json"]
        )
        r07_failed_required_paths = [
            ROOT / value for value in r07_machine.get("result_paths", [])
        ]
        r07_failed_absent_paths = [
            ROOT / r07_config["outputs"][key]
            for key in (
                "bsource_self_test_output",
                "device_syntax_netlist",
                "device_syntax_log",
                "device_syntax_output",
                "independent_check_report",
            )
        ]
        r07_failed_state = (
            r07_contract_exists
            and r07_preflight_exists
            and r07_contract_report.get("status") == "PASS"
            and r07_contract_report.get("contract_status") == "PASS"
            and r07_contract_report.get("evidence_level") == "E3"
            and len(r07_contract_checks) == 39
            and all(item.get("status") == "PASS" for item in r07_contract_checks)
            and r07_preflight_report.get("status") == "FAIL"
            and r07_preflight_report.get("preflight_status") == "FAIL"
            and r07_preflight_report.get("build_status") == "PASS"
            and r07_preflight_report.get("evidence_level") == "E0"
            and len(r07_preflight_checks) == 47
            and sum(item.get("status") == "PASS" for item in r07_preflight_checks) == 42
            and sum(item.get("status") == "FAIL" for item in r07_preflight_checks) == 5
            and r07_preflight_report.get("summary", {}).get("process_invocations") == 23
            and r07_preflight_report.get("summary", {}).get("ngspice_invoked") is False
            and r07_preflight_report.get("summary", {}).get("aimspice_invoked") is False
            and r07_preflight_report.get("summary", {}).get("controlled_generator_smoke_invoked") is True
            and r07_preflight_report.get("summary", {}).get("controlled_bsource_self_test_invoked") is True
            and r07_preflight_report.get("summary", {}).get("device_syntax_only_invoked") is False
            and r07_preflight_report.get("summary", {}).get("formal_device_dc_invoked") is False
            and r07_preflight_report.get("summary", {}).get("formal_m01_outputs_created") is False
            and r07_preflight_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r07_config_path)
            and r07_preflight_report.get("runner", {}).get("sha256")
            == sha256(m01_xyce_r07_runner_path)
            and r07_preflight_report.get("xyce_binary", {}).get("sha256")
            == r07_machine.get("xyce_binary_sha256")
            and r07_machine.get("status") == "preflight_failed_self_test"
            and r07_machine.get("current_evidence") == "E0"
            and r07_machine.get("contract_check_completed") is True
            and r07_machine.get("contract_status") == "PASS"
            and r07_machine.get("contract_checks_passed") == 39
            and r07_machine.get("contract_checks_failed") == 0
            and r07_machine.get("preflight_run_completed") is True
            and r07_machine.get("preflight_run_ordinal") == 1
            and r07_machine.get("preflight_status") == "FAIL"
            and r07_machine.get("build_status") == "PASS"
            and r07_machine.get("runner_checks_passed") == 42
            and r07_machine.get("runner_checks_failed") == 5
            and r07_machine.get("independent_check_run") is False
            and r07_machine.get("independent_check_status") == "NOT_RUN_RUNNER_FAILED"
            and r07_machine.get("xyce_install_passed") is True
            and r07_machine.get("controlled_bsource_self_test_invoked") is True
            and r07_machine.get("device_syntax_only_invoked") is False
            and r07_machine.get("actual_self_test_output_path")
            == "results/compact/m01_xyce_build_preflight_r07/bsource_self_test.prn"
            and sha256(
                ROOT / r07_machine["actual_self_test_output_path"]
            ) == r07_machine.get("actual_self_test_output_sha256")
            and r07_machine.get("artifact_hashes", {}).get("preflight_report_sha256")
            == sha256(m01_xyce_r07_preflight_report_path)
            and r07_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r07_contract_report_path)
            and all(path.is_file() for path in r07_failed_required_paths)
            and all(not path.exists() for path in r07_failed_absent_paths)
            and Path(r07_tools["generator_install_prefix"]).is_dir()
            and Path(r07_sources["xyce"]["install_prefix"]).is_dir()
            and not (
                ROOT / r07_config["outputs"]["independent_check_report"]
            ).exists()
        )
        r07_next_scope_valid = (
            r07_planned_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "establish and commit M01 Xyce build/tool preflight revision-7"
            )
        ) or (
            r07_ready_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "execute M01 Xyce build/tool preflight revision-7"
            )
        ) or (
            r07_failed_state
            and config.get("tcad_track", {}).get("next_scope", "").startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-7 42/47"
            )
        ) or (
            r07_failed_state and r08_scope_active
        )
        r07_runner_source = m01_xyce_r07_runner_path.read_text(encoding="utf-8")
        r07_checker_source = m01_xyce_r07_checker_path.read_text(encoding="utf-8")
        r07_contract_source = m01_xyce_r07_contract_checker_path.read_text(
            encoding="utf-8"
        )
        r07_common_source = m01_xyce_r07_common_path.read_text(encoding="utf-8")
        add_check(
            checks,
            "m01_xyce_preflight_r07:contract_state_and_unexecuted_chain",
            (r07_planned_state or r07_ready_state or r07_failed_state)
            and r07_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R07"
            and r07_config.get("revision") == 7
            and r07_config.get("status") == "preflight_planned"
            and r07_machine.get("revision") == 7
            and r07_machine.get("expected_contract_check_count") == 39
            and r07_machine.get("expected_runner_check_count") == 47
            and r07_machine.get("expected_independent_check_count") == 25
            and r07_machine.get("formal_run_completed") is False
            and r07_machine.get("preflight_run_completed") is r07_failed_state
            and r07_machine.get("device_netlist_invoked") is False
            and r07_machine.get("numerical_outputs_created") is False
            and r07_machine.get("ngspice_invoked") is False
            and r07_machine.get("aimspice_invoked") is False
            and r07_machine.get("serial_build") is True
            and r07_machine.get("mpi_build") is False
            and r07_machine.get("fortran_build") is False
            and r07_machine.get("source_built_m4_bison_flex") is True
            and r07_machine.get("reuse_r05_suitesparse") is True
            and r07_machine.get("reuse_r05_trilinos") is True
            and r07_machine.get("reuse_r05_partial_xyce") is False
            and r07_machine.get("reuse_r06_xyce_or_outputs") is False
            and r07_machine.get("r05_failure_preserved") is True
            and r07_machine.get("r06_contract_failure_preserved") is True
            and r07_machine.get("r06_contract_report_sha256")
            == sha256(ROOT / r07_r06["contract_report_path"])
            and r07_machine.get("proprietary_binary_accepted") is False
            and r07_machine.get("circuit_or_downstream_permitted") is False
            and (r07_failed_state or all(not path.exists() for path in r07_future_paths))
            and all(not path.exists() for path in r07_formal_paths)
            and (r07_failed_state or all(not path.exists() for path in r07_new_roots))
            and len(r07_new_roots) == len(set(r07_new_roots))
            and r07_generator_sources_ok
            and r07_reuse_ok
            and r07_r06_binding_ok
            and r07_reuse.get("dependency_rebuild_permitted") is False
            and r07_config["build_plan"].get("generator_build_order")
            == ["m4", "bison", "flex"]
            and r07_config["build_plan"].get(
                "suitesparse_or_trilinos_commands_permitted"
            )
            is False
            and r07_config["build_plan"].get("parallel_jobs") == 2
            and "EXPECTED_CHECK_COUNT = 47" in r07_runner_source
            and "formal_device_dc_invoked=false" in r07_runner_source
            and "r05_partial_xyce_reused=false" in r07_runner_source
            and "r06_xyce_or_outputs_reused=false" in r07_runner_source
            and "EXPECTED_CHECK_COUNT = 25" in r07_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 47" in r07_checker_source
            and "run_m01_xyce_build_preflight_r07.py" in r07_checker_source
            and "import subprocess" not in r07_checker_source
            and "subprocess." not in r07_checker_source
            and re.search(
                r"^(?:from\s+run_m01_xyce_build_preflight_r07\s+import|import\s+run_m01_xyce_build_preflight_r07\b)",
                r07_checker_source,
                re.MULTILINE,
            )
            is None
            and "EXPECTED_CHECK_COUNT = 39" in r07_contract_source
            and "r06_contract_failure_binding" in r07_contract_source
            and re.search(r"^import subprocess\b", r07_contract_source, re.MULTILINE)
            is None
            and "def digest_tree" in r07_common_source
            and "import subprocess" not in r07_common_source
            and "m01-xyce-build-preflight-r07-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r07:" in makefile_source
            and "m01-xyce-build-preflight-r07-check:" in makefile_source
            and r07_next_scope_valid,
            f"planned={r07_planned_state} ready={r07_ready_state} failed={r07_failed_state} future_absent="
            f"{sum(not path.exists() for path in r07_future_paths)}/{len(r07_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r07:contract_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r08_config_path = ROOT / "config" / "m01_xyce_build_preflight_r08.json"
    m01_xyce_r08_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r08.json"
    )
    m01_xyce_r08_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r08_contract.py"
    )
    m01_xyce_r08_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r08.py"
    m01_xyce_r08_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r08.py"
    m01_xyce_r08_common_path = ROOT / "scripts" / "m01_xyce_r08_common.py"
    try:
        r08_config = json.loads(m01_xyce_r08_config_path.read_text(encoding="utf-8"))
        r08_machine = experiment_map["M01"].get("xyce_build_preflight_r08", {})
        r08_contract_exists = m01_xyce_r08_contract_report_path.is_file()
        r08_contract_report = (
            json.loads(m01_xyce_r08_contract_report_path.read_text(encoding="utf-8"))
            if r08_contract_exists
            else {}
        )
        r08_contract_checks = r08_contract_report.get("checks", [])
        r08_future_paths = [
            ROOT / value
            for key, value in r08_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r08_formal_paths = [
            ROOT / value for value in r08_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r08 = r08_config["r07_failure_binding"]
        r08_r07_bindings = [
            (r08["config_path"], r08["config_sha256"]),
            (r08["contract_checker_path"], r08["contract_checker_sha256"]),
            (r08["contract_report_path"], r08["contract_report_sha256"]),
            (r08["runner_path"], r08["runner_sha256"]),
            (r08["independent_checker_path"], r08["independent_checker_sha256"]),
            (r08["preflight_report_path"], r08["preflight_report_sha256"]),
            (r08["preflight_log_path"], r08["preflight_log_sha256"]),
            (r08["source_manifest_path"], r08["source_manifest_sha256"]),
            (r08["build_manifest_path"], r08["build_manifest_sha256"]),
            (r08["self_test_output_path"], r08["self_test_output_sha256"]),
            (r08["xyce_build_log_path"], r08["xyce_build_log_sha256"]),
        ]
        r08_r07_binding_ok = (
            r08["bound_commit"] == "9a7375ef30ae90adf5214b3c7421a5f7a8cab726"
            and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in r08_r07_bindings
            )
        )
        r08_failure_report_path = ROOT / r08_machine.get("contract_failure_report_path", "missing")
        r08_failure_log_path = ROOT / r08_machine.get("contract_failure_log_path", "missing")
        r08_failed_state = (
            not r08_contract_exists
            and r08_machine.get("status") == "contract_failed_checker"
            and r08_machine.get("current_evidence") == "E0"
            and r08_machine.get("contract_check_completed") is True
            and r08_machine.get("contract_status") == "ABORTED_BEFORE_REPORT"
            and r08_machine.get("registered_checks_before_abort") == 30
            and r08_machine.get("expected_checks_before_abort") == 36
            and r08_machine.get("contract_failure_category") == "contract_registry_mismatch"
            and r08_failure_report_path.is_file()
            and r08_failure_log_path.is_file()
            and r08_machine.get("artifact_hashes", {}).get("contract_failure_report_sha256")
            == sha256(r08_failure_report_path)
            and r08_machine.get("artifact_hashes", {}).get("contract_failure_log_sha256")
            == sha256(r08_failure_log_path)
            and r08_machine.get("result_paths")
            == [
                "results/reports/m01_xyce_build_preflight_contract_r08_registry_mismatch_failed.json",
                "results/compact/m01_xyce_build_preflight_r08_contract_registry_mismatch_failed.log",
            ]
        )
        r08_ready_state = (
            r08_contract_exists
            and r08_contract_report.get("status") == "PASS"
            and r08_contract_report.get("contract_status") == "PASS"
            and r08_contract_report.get("evidence_level") == "E3"
            and r08_contract_report.get("build_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and len(r08_contract_checks) == 36
            and all(item.get("status") == "PASS" for item in r08_contract_checks)
            and r08_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r08_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r08_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r08_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r08_contract_report.get("config", {}).get("sha256") == sha256(m01_xyce_r08_config_path)
            and r08_contract_report.get("checker", {}).get("sha256") == sha256(m01_xyce_r08_contract_checker_path)
            and r08_machine.get("status") == "contract_ready"
            and r08_machine.get("current_evidence") == "E3"
            and r08_machine.get("contract_check_completed") is True
            and r08_machine.get("contract_status") == "PASS"
            and r08_machine.get("contract_checks_passed") == 36
            and r08_machine.get("contract_checks_failed") == 0
            and r08_machine.get("artifact_hashes", {}).get("contract_report_sha256") == sha256(m01_xyce_r08_contract_report_path)
            and r08_machine.get("result_paths") == ["results/reports/m01_xyce_build_preflight_contract_r08.json"]
        )
        r08_next_scope = config.get("tcad_track", {}).get("next_scope", "")
        r08_next_scope_valid = (
            r08_ready_state
            and r08_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-8"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-8 30/36"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-9"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-9 34/36"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-10"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-10"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-10 runner Unicode-path failure"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-11"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-11"
            )
        ) or (
            r08_failed_state
            and r08_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-11"
            )
        )
        r08_runner_source = m01_xyce_r08_runner_path.read_text(encoding="utf-8")
        r08_checker_source = m01_xyce_r08_checker_path.read_text(encoding="utf-8")
        r08_contract_source = m01_xyce_r08_contract_checker_path.read_text(encoding="utf-8")
        r08_common_source = m01_xyce_r08_common_path.read_text(encoding="utf-8")
        r08_tools = r08_config["toolchain"]
        r08_binary = Path(r08_tools["xyce_binary"])
        r08_candidate = ROOT / r08_config["device_syntax_check"]["candidate_path"]
        add_check(
            checks,
            "m01_xyce_preflight_r08:contract_state_and_unexecuted_chain",
            (r08_failed_state or r08_ready_state)
            and r08_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R08"
            and r08_config.get("revision") == 8
            and r08_config.get("status") == "preflight_planned"
            and r08_machine.get("revision") == 8
            and r08_machine.get("expected_contract_check_count") == 36
            and r08_machine.get("expected_runner_check_count") == 32
            and r08_machine.get("expected_independent_check_count") == 25
            and r08_machine.get("formal_run_completed") is False
            and r08_machine.get("device_netlist_invoked") is False
            and r08_machine.get("numerical_outputs_created") is False
            and r08_machine.get("ngspice_invoked") is False
            and r08_machine.get("aimspice_invoked") is False
            and r08_machine.get("r07_failure_preserved") is True
            and r08_machine.get("r07_runner_rerun") is False
            and r08_machine.get("r07_independent_checker_run") is False
            and r08_machine.get("proprietary_binary_accepted") is False
            and r08_machine.get("circuit_or_downstream_permitted") is False
            and r08_r07_binding_ok
            and r08_binary.is_file()
            and sha256(r08_binary) == r08["xyce_binary_sha256"]
            and r08_candidate.is_file()
            and sha256(r08_candidate) == r08_config["device_syntax_check"]["candidate_sha256"]
            and all(not path.exists() for path in r08_future_paths)
            and all(not path.exists() for path in r08_formal_paths)
            and "EXPECTED_CHECK_COUNT = 32" in r08_runner_source
            and "EXPECTED_CHECK_COUNT = 25" in r08_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 32" in r08_checker_source
            and "EXPECTED_CHECK_COUNT = 36" in r08_contract_source
            and "def read_xyce_prn" in r08_common_source
            and "import subprocess" not in r08_checker_source
            and "import subprocess" not in r08_common_source
            and "m01-xyce-build-preflight-r08-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r08:" in makefile_source
            and "m01-xyce-build-preflight-r08-check:" in makefile_source
            and r08_next_scope_valid,
            f"failed={r08_failed_state} ready={r08_ready_state} future_absent="
            f"{sum(not path.exists() for path in r08_future_paths)}/{len(r08_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r08:contract_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r09_config_path = ROOT / "config" / "m01_xyce_build_preflight_r09.json"
    m01_xyce_r09_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r09.json"
    )
    m01_xyce_r09_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r09_contract.py"
    )
    m01_xyce_r09_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r09.py"
    m01_xyce_r09_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r09.py"
    m01_xyce_r09_common_path = ROOT / "scripts" / "m01_xyce_r09_common.py"
    try:
        r09_config = json.loads(m01_xyce_r09_config_path.read_text(encoding="utf-8"))
        r09_machine = experiment_map["M01"].get("xyce_build_preflight_r09", {})
        r09_contract_exists = m01_xyce_r09_contract_report_path.is_file()
        r09_contract_report = (
            json.loads(m01_xyce_r09_contract_report_path.read_text(encoding="utf-8"))
            if r09_contract_exists
            else {}
        )
        r09_future_paths = [
            ROOT / value
            for key, value in r09_config.get("outputs", {}).items()
            if key != "contract_report"
        ]
        r09_formal_paths = [
            ROOT / value for value in r09_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r09_r07 = r09_config["r07_failure_binding"]
        r09_r07_bindings = [
            (r09_r07["config_path"], r09_r07["config_sha256"]),
            (r09_r07["contract_checker_path"], r09_r07["contract_checker_sha256"]),
            (r09_r07["contract_report_path"], r09_r07["contract_report_sha256"]),
            (r09_r07["runner_path"], r09_r07["runner_sha256"]),
            (r09_r07["independent_checker_path"], r09_r07["independent_checker_sha256"]),
            (r09_r07["preflight_report_path"], r09_r07["preflight_report_sha256"]),
            (r09_r07["preflight_log_path"], r09_r07["preflight_log_sha256"]),
            (r09_r07["source_manifest_path"], r09_r07["source_manifest_sha256"]),
            (r09_r07["build_manifest_path"], r09_r07["build_manifest_sha256"]),
            (r09_r07["self_test_output_path"], r09_r07["self_test_output_sha256"]),
            (r09_r07["xyce_build_log_path"], r09_r07["xyce_build_log_sha256"]),
        ]
        r09_r08 = r09_config["r08_failure_binding"]
        r09_r08_bindings = [
            (r09_r08["config_path"], r09_r08["config_sha256"]),
            (r09_r08["common_hash_helper_path"], r09_r08["common_hash_helper_sha256"]),
            (r09_r08["contract_checker_path"], r09_r08["contract_checker_sha256"]),
            (r09_r08["runner_path"], r09_r08["runner_sha256"]),
            (r09_r08["independent_checker_path"], r09_r08["independent_checker_sha256"]),
            (r09_r08["failure_report_path"], r09_r08["failure_report_sha256"]),
            (r09_r08["failure_log_path"], r09_r08["failure_log_sha256"]),
        ]
        r09_r08_failure_report = json.loads(
            (ROOT / r09_r08["failure_report_path"]).read_text(encoding="utf-8")
        )
        r09_r07_binding_ok = (
            r09_r07["bound_commit"] == "9a7375ef30ae90adf5214b3c7421a5f7a8cab726"
            and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in r09_r07_bindings
            )
        )
        r09_r08_binding_ok = (
            r09_r08["bound_commit"] == "95d656324fb5c4a301ed903961512a446b90669a"
            and r09_r08["must_remain_unchanged"] is True
            and r09_r08_failure_report.get("status") == "FAIL"
            and r09_r08_failure_report.get("contract_status") == "ABORTED_BEFORE_REPORT"
            and r09_r08_failure_report.get("failure_category") == "contract_registry_mismatch"
            and r09_r08_failure_report.get("registered_checks_before_abort") == 30
            and r09_r08_failure_report.get("expected_checks") == 36
            and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in r09_r08_bindings
            )
        )
        r09_runner_source = m01_xyce_r09_runner_path.read_text(encoding="utf-8")
        r09_checker_source = m01_xyce_r09_checker_path.read_text(encoding="utf-8")
        r09_contract_source = m01_xyce_r09_contract_checker_path.read_text(encoding="utf-8")
        r09_common_source = m01_xyce_r09_common_path.read_text(encoding="utf-8")
        r09_tools = r09_config["toolchain"]
        r09_binary = Path(r09_tools["xyce_binary"])
        r09_candidate = ROOT / r09_config["device_syntax_check"]["candidate_path"]
        r09_machine_planned = (
            r09_machine.get("status") == "contract_planned"
            and r09_machine.get("revision") == 9
            and r09_machine.get("current_evidence") == "E0"
            and r09_machine.get("contract_check_completed") is False
            and r09_machine.get("contract_status") == "NOT_RUN"
            and r09_machine.get("result_paths") == []
            and r09_machine.get("artifact_hashes") == {}
        )
        r09_next_scope = config.get("tcad_track", {}).get("next_scope", "")
        r09_failure_log_path = ROOT / r09_machine.get("contract_failure_log_path", "missing")
        r09_failed_state = (
            r09_contract_exists
            and r09_contract_report.get("status") == "FAIL"
            and r09_contract_report.get("contract_status") == "FAIL"
            and r09_contract_report.get("evidence_level") == "E0"
            and r09_contract_report.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R09"
            and r09_contract_report.get("summary", {}).get("check_count") == 36
            and r09_contract_report.get("summary", {}).get("passed") == 34
            and r09_contract_report.get("summary", {}).get("failed") == 2
            and r09_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r09_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r09_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r09_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r09_machine.get("status") == "contract_failed_checker"
            and r09_machine.get("contract_check_completed") is True
            and r09_machine.get("contract_status") == "FAIL"
            and r09_machine.get("contract_checks_passed") == 34
            and r09_machine.get("contract_checks_failed") == 2
            and r09_machine.get("contract_failure_category") == "contract_assertion_allowlist_and_next_gate"
            and r09_failure_log_path.is_file()
            and r09_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r09_contract_report_path)
            and r09_machine.get("artifact_hashes", {}).get("contract_failure_log_sha256")
            == sha256(r09_failure_log_path)
            and r09_machine.get("result_paths")
            == [
                "results/reports/m01_xyce_build_preflight_contract_r09.json",
                "results/compact/m01_xyce_build_preflight_r09_contract_assertions_failed.log",
            ]
        )
        r09_next_scope_valid = (
            r09_machine_planned
            and r09_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-9"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-9 34/36"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-10"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-10"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-10 runner Unicode-path failure"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-11"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-11"
            )
        ) or (
            r09_failed_state
            and r09_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-11"
            )
        )
        add_check(
            checks,
            "m01_xyce_preflight_r09:implementation_state_and_unexecuted_chain",
            r09_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R09"
            and r09_config.get("revision") == 9
            and r09_config.get("status") == "preflight_planned"
            and r09_config.get("scope", {}).get("active_material_scope") == "IGZO only"
            and r09_config.get("scope", {}).get("formal_m01_numerical_run") is False
            and r09_config.get("scope", {}).get("circuit_or_downstream_permitted") is False
            and (r09_machine_planned or r09_failed_state)
            and (not r09_contract_exists if r09_machine_planned else r09_contract_exists)
            and all(not path.exists() for path in r09_future_paths)
            and all(not path.exists() for path in r09_formal_paths)
            and r09_r07_binding_ok
            and r09_r08_binding_ok
            and r09_binary.is_file()
            and sha256(r09_binary) == r09_r07["xyce_binary_sha256"]
            and r09_candidate.is_file()
            and sha256(r09_candidate) == r09_config["device_syntax_check"]["candidate_sha256"]
            and "EXPECTED_CHECK_COUNT = 36" in r09_contract_source
            and "EXPECTED_CHECK_COUNT = 32" in r09_runner_source
            and "EXPECTED_CHECK_COUNT = 25" in r09_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 32" in r09_checker_source
            and "def read_xyce_prn" in r09_common_source
            and "import subprocess" not in r09_checker_source
            and "import subprocess" not in r09_common_source
            and re.search(r"^(?:import|from)\s+subprocess\b", r09_contract_source, re.MULTILINE) is None
            and "m01-xyce-build-preflight-r09-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r09:" in makefile_source
            and "m01-xyce-build-preflight-r09-check:" in makefile_source
            and all("r08" not in source.lower() for source in (r09_runner_source, r09_checker_source, r09_common_source))
            and r09_machine.get("r08_contract_failure_preserved") is True
            and r09_machine.get("r08_runner_rerun") is False
            and r09_machine.get("r08_independent_checker_run") is False
            and r09_machine.get("r07_runner_rerun") is False
            and r09_machine.get("r07_independent_checker_run") is False
            and r09_machine.get("ngspice_invoked") is False
            and r09_machine.get("aimspice_invoked") is False
            and r09_machine.get("build_processes_invoked") == 0
            and r09_machine.get("simulator_processes_invoked") == 0
            and r09_machine.get("circuit_or_downstream_permitted") is False
            and r09_next_scope_valid,
            f"planned={r09_machine_planned} failed={r09_failed_state} r08_binding={r09_r08_binding_ok} future_absent="
            f"{sum(not path.exists() for path in r09_future_paths)}/{len(r09_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r09:implementation_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r10_config_path = ROOT / "config" / "m01_xyce_build_preflight_r10.json"
    m01_xyce_r10_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r10.json"
    )
    m01_xyce_r10_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r10_contract.py"
    )
    m01_xyce_r10_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r10.py"
    m01_xyce_r10_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r10.py"
    m01_xyce_r10_common_path = ROOT / "scripts" / "m01_xyce_r10_common.py"
    try:
        r10_config = json.loads(m01_xyce_r10_config_path.read_text(encoding="utf-8"))
        r10_machine = experiment_map["M01"].get("xyce_build_preflight_r10", {})
        r10_contract_exists = m01_xyce_r10_contract_report_path.is_file()
        r10_contract_report = (
            json.loads(m01_xyce_r10_contract_report_path.read_text(encoding="utf-8"))
            if r10_contract_exists
            else {}
        )
        r10_failure_report_path = ROOT / r10_machine.get("runner_failure_report_path", "missing")
        r10_failure_log_path = ROOT / r10_machine.get("runner_failure_log_path", "missing")
        r10_failure_report = (
            json.loads(r10_failure_report_path.read_text(encoding="utf-8"))
            if r10_failure_report_path.is_file()
            else {}
        )
        r10_outputs = r10_config.get("outputs", {})
        r10_future_paths = [
            ROOT / value
            for key, value in r10_outputs.items()
            if key != "contract_report"
        ]
        r10_run_directory = ROOT / r10_outputs["run_directory"]
        r10_partial_output_keys = [
            "preflight_log",
            "bsource_self_test_netlist",
            "bsource_self_test_log",
            "bsource_self_test_output",
            "xyce_version_command_log",
            "xyce_license_command_log",
            "bsource_self_test_command_log",
            "device_syntax_netlist",
        ]
        r10_partial_paths = [ROOT / r10_outputs[key] for key in r10_partial_output_keys]
        r10_uncreated_future_paths = [
            path
            for path in r10_future_paths
            if path != r10_run_directory and path not in r10_partial_paths
        ]
        r10_formal_paths = [
            ROOT / value for value in r10_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r10_r07 = r10_config["r07_failure_binding"]
        r10_r08 = r10_config["r08_failure_binding"]
        r10_r09 = r10_config["r09_failure_binding"]
        r10_r08_bindings = [
            (r10_r08["config_path"], r10_r08["config_sha256"]),
            (r10_r08["common_hash_helper_path"], r10_r08["common_hash_helper_sha256"]),
            (r10_r08["contract_checker_path"], r10_r08["contract_checker_sha256"]),
            (r10_r08["runner_path"], r10_r08["runner_sha256"]),
            (r10_r08["independent_checker_path"], r10_r08["independent_checker_sha256"]),
            (r10_r08["failure_report_path"], r10_r08["failure_report_sha256"]),
            (r10_r08["failure_log_path"], r10_r08["failure_log_sha256"]),
        ]
        r10_r09_bindings = [
            (r10_r09["config_path"], r10_r09["config_sha256"]),
            (r10_r09["common_hash_helper_path"], r10_r09["common_hash_helper_sha256"]),
            (r10_r09["contract_checker_path"], r10_r09["contract_checker_sha256"]),
            (r10_r09["runner_path"], r10_r09["runner_sha256"]),
            (r10_r09["independent_checker_path"], r10_r09["independent_checker_sha256"]),
            (r10_r09["failure_report_path"], r10_r09["failure_report_sha256"]),
            (r10_r09["failure_log_path"], r10_r09["failure_log_sha256"]),
        ]
        r10_r08_failure_report = json.loads(
            (ROOT / r10_r08["failure_report_path"]).read_text(encoding="utf-8")
        )
        r10_r09_failure_report = json.loads(
            (ROOT / r10_r09["failure_report_path"]).read_text(encoding="utf-8")
        )
        r10_r08_binding_ok = (
            r10_r08["bound_commit"] == "95d656324fb5c4a301ed903961512a446b90669a"
            and r10_r08["must_remain_unchanged"] is True
            and r10_r08_failure_report.get("status") == "FAIL"
            and r10_r08_failure_report.get("contract_status") == "ABORTED_BEFORE_REPORT"
            and r10_r08_failure_report.get("registered_checks_before_abort") == 30
            and r10_r08_failure_report.get("expected_checks") == 36
            and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in r10_r08_bindings
            )
        )
        r10_r09_binding_ok = (
            r10_r09["bound_commit"] == "9285865"
            and r10_r09["must_remain_unchanged"] is True
            and r10_r09_failure_report.get("status") == "FAIL"
            and r10_r09_failure_report.get("contract_status") == "FAIL"
            and r10_r09_failure_report.get("evidence_level") == "E0"
            and r10_r09_failure_report.get("summary", {}).get("check_count") == 36
            and r10_r09_failure_report.get("summary", {}).get("passed") == 34
            and r10_r09_failure_report.get("summary", {}).get("failed") == 2
            and r10_r09_failure_report.get("summary", {}).get("build_processes_invoked") == 0
            and r10_r09_failure_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r10_r09_failure_report.get("summary", {}).get("device_netlist_created") is False
            and r10_r09_failure_report.get("summary", {}).get("numerical_outputs_created") is False
            and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in r10_r09_bindings
            )
        )
        r10_runner_source = m01_xyce_r10_runner_path.read_text(encoding="utf-8")
        r10_checker_source = m01_xyce_r10_checker_path.read_text(encoding="utf-8")
        r10_contract_source = m01_xyce_r10_contract_checker_path.read_text(encoding="utf-8")
        r10_common_source = m01_xyce_r10_common_path.read_text(encoding="utf-8")
        r10_tools = r10_config["toolchain"]
        r10_binary = Path(r10_tools["xyce_binary"])
        r10_candidate = ROOT / r10_config["device_syntax_check"]["candidate_path"]
        r10_machine_planned = (
            r10_machine.get("status") == "contract_planned"
            and r10_machine.get("revision") == 10
            and r10_machine.get("current_evidence") == "E0"
            and r10_machine.get("contract_check_completed") is False
            and r10_machine.get("contract_status") == "NOT_RUN"
            and r10_machine.get("result_paths") == []
            and r10_machine.get("artifact_hashes") == {}
        )
        r10_static_pass = (
            r10_contract_exists
            and r10_contract_report.get("status") == "PASS"
            and r10_contract_report.get("contract_status") == "PASS"
            and r10_contract_report.get("evidence_level") == "E3"
            and r10_contract_report.get("build_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and r10_contract_report.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R10"
            and len(r10_contract_report.get("checks", [])) == 36
            and all(item.get("status") == "PASS" for item in r10_contract_report.get("checks", []))
            and r10_contract_report.get("summary", {}).get("check_count") == 36
            and r10_contract_report.get("summary", {}).get("passed") == 36
            and r10_contract_report.get("summary", {}).get("failed") == 0
            and r10_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r10_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r10_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r10_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r10_contract_report.get("config", {}).get("sha256") == sha256(m01_xyce_r10_config_path)
            and r10_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r10_contract_checker_path)
            and sha256(m01_xyce_r10_contract_report_path)
            == "a7dbcf6d639897f6648d25a151d3a29c48c3dc352992a7872104b684b29fe785"
        )
        r10_ready_state = (
            r10_static_pass
            and r10_machine.get("status") == "contract_ready"
            and r10_machine.get("revision") == 10
            and r10_machine.get("current_evidence") == "E3"
            and r10_machine.get("contract_check_completed") is True
            and r10_machine.get("contract_status") == "PASS"
            and r10_machine.get("contract_checks_passed") == 36
            and r10_machine.get("contract_checks_failed") == 0
            and r10_machine.get("preflight_run_completed") is False
            and r10_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r10_contract_report_path)
            and r10_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r10.json"]
        )
        r10_failure_summary = r10_failure_report.get("summary", {})
        r10_failure_partial = r10_failure_report.get("partial_run", {})
        r10_failure_static = r10_failure_report.get("static_contract", {})
        r10_completed_commands = r10_failure_report.get("commands_completed", [])
        r10_partial_tree = (
            digest_r10_tree(r10_run_directory)
            if r10_run_directory.is_dir()
            else {}
        )
        r10_expected_result_paths = [
            "results/reports/m01_xyce_build_preflight_contract_r10.json",
            "results/reports/m01_xyce_build_preflight_r10_runner_unicode_path_failed.json",
            "results/compact/m01_xyce_build_preflight_r10_runner_unicode_path_failed.log",
            *[r10_outputs[key] for key in r10_partial_output_keys],
        ]
        r10_partial_hashes_ok = (
            all(path.is_file() for path in r10_partial_paths)
            and sha256(ROOT / r10_outputs["preflight_log"])
            == r10_failure_partial.get("preflight_log_sha256")
            and sha256(ROOT / r10_outputs["bsource_self_test_netlist"])
            == r10_failure_partial.get("self_test_netlist_sha256")
            and sha256(ROOT / r10_outputs["bsource_self_test_output"])
            == next(
                (
                    item.get("output_sha256")
                    for item in r10_completed_commands
                    if item.get("name") == "xyce_bsource_self_test"
                ),
                None,
            )
            and sha256(ROOT / r10_outputs["device_syntax_netlist"])
            == r10_failure_partial.get("partial_device_syntax_netlist_sha256")
            and (ROOT / r10_outputs["device_syntax_netlist"]).stat().st_size == 0
        )
        r10_commands_ok = (
            len(r10_completed_commands) == 3
            and [item.get("name") for item in r10_completed_commands]
            == ["xyce_version", "xyce_license", "xyce_bsource_self_test"]
            and all(item.get("returncode") == 0 for item in r10_completed_commands)
            and all(
                (ROOT / item["log_path"]).is_file()
                and sha256(ROOT / item["log_path"]) == item.get("log_sha256")
                for item in r10_completed_commands
            )
        )
        r10_failed_state = (
            r10_static_pass
            and r10_failure_report_path.is_file()
            and r10_failure_log_path.is_file()
            and r10_failure_report.get("status") == "FAIL"
            and r10_failure_report.get("evidence_level") == "E0"
            and r10_failure_report.get("stage_id") == "M01"
            and r10_failure_report.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R10"
            and r10_failure_report.get("implementation_commit") == "bd7ebda"
            and r10_failure_report.get("static_contract_commit") == "8dff9ad"
            and r10_failure_report.get("failure_category")
            == "runner_unicode_path_ascii_encoding"
            and r10_failure_report.get("failure_phase")
            == "device_syntax_netlist_write_before_parser_only_command"
            and r10_failure_report.get("exception", {}).get("type") == "UnicodeEncodeError"
            and r10_failure_report.get("exception", {}).get("source")
            == "scripts/run_m01_xyce_build_preflight_r10.py:336"
            and r10_failure_static.get("status") == "PASS"
            and r10_failure_static.get("evidence_level") == "E3"
            and r10_failure_static.get("check_count") == 36
            and r10_failure_static.get("passed") == 36
            and r10_failure_static.get("failed") == 0
            and r10_failure_static.get("report_sha256")
            == sha256(m01_xyce_r10_contract_report_path)
            and r10_commands_ok
            and r10_failure_summary.get("process_invocations") == 3
            and r10_failure_summary.get("build_processes_invoked") == 0
            and r10_failure_summary.get("simulator_processes_invoked") == 3
            and r10_failure_summary.get("controlled_bsource_self_test_invoked") is True
            and r10_failure_summary.get("device_syntax_only_invoked") is False
            and r10_failure_summary.get("formal_device_dc_invoked") is False
            and r10_failure_summary.get("device_netlist_invoked") is False
            and r10_failure_summary.get("partial_device_syntax_file_created") is True
            and r10_failure_summary.get("partial_device_syntax_file_bytes") == 0
            and r10_failure_summary.get("formal_m01_outputs_created") is False
            and r10_failure_summary.get("numerical_outputs_created") is False
            and r10_failure_summary.get("ngspice_invoked") is False
            and r10_failure_summary.get("aimspice_invoked") is False
            and r10_failure_summary.get("circuit_or_downstream_invoked") is False
            and r10_failure_partial.get("directory")
            == "results/compact/m01_xyce_build_preflight_r10"
            and r10_failure_partial.get("tree_sha256")
            == "5a3d1ac4ff62848fb7132db9211a6281a477b43900e87ddfe6047f6da9fef85e"
            and r10_partial_tree.get("tree_sha256") == r10_failure_partial.get("tree_sha256")
            and r10_partial_tree.get("regular_file_count") == 8
            and r10_partial_hashes_ok
            and r10_machine.get("status") == "preflight_failed_runner"
            and r10_machine.get("revision") == 10
            and r10_machine.get("current_evidence") == "E0"
            and r10_machine.get("preflight_run_completed") is True
            and r10_machine.get("preflight_run_ordinal") == 1
            and r10_machine.get("preflight_status") == "FAIL"
            and r10_machine.get("build_status") == "REUSED_HASH_BOUND_R07_INSTALL"
            and r10_machine.get("runner_checks_registered_before_abort") == 16
            and r10_machine.get("runner_checks_passed_before_abort") == 16
            and r10_machine.get("runner_checks_failed_before_abort") == 0
            and r10_machine.get("runner_failure_category")
            == "runner_unicode_path_ascii_encoding"
            and r10_machine.get("process_invocations") == 3
            and r10_machine.get("controlled_bsource_self_test_invoked") is True
            and r10_machine.get("device_syntax_only_invoked") is False
            and r10_machine.get("formal_device_dc_invoked") is False
            and r10_machine.get("observed_self_test_value_v") == 1.25
            and r10_machine.get("partial_run_tree_sha256")
            == r10_failure_partial.get("tree_sha256")
            and r10_machine.get("contract_check_completed") is True
            and r10_machine.get("contract_status") == "PASS"
            and r10_machine.get("contract_checks_passed") == 36
            and r10_machine.get("contract_checks_failed") == 0
            and r10_machine.get("simulator_processes_invoked") == 3
            and r10_machine.get("result_paths") == r10_expected_result_paths
            and r10_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r10_contract_report_path)
            and r10_machine.get("artifact_hashes", {}).get("runner_failure_report_sha256")
            == sha256(r10_failure_report_path)
            and r10_machine.get("artifact_hashes", {}).get("runner_failure_log_sha256")
            == sha256(r10_failure_log_path)
            and all(not path.exists() for path in r10_uncreated_future_paths)
        )
        r10_next_scope = config.get("tcad_track", {}).get("next_scope", "")
        r10_next_scope_valid = (
            r10_machine_planned
            and r10_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-10 output/parser recovery contract"
            )
        ) or (
            r10_ready_state
            and r10_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-10"
            )
        ) or (
            r10_failed_state
            and r10_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-10 runner Unicode-path failure"
            )
        ) or (
            r10_failed_state
            and r10_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-11"
            )
        ) or (
            r10_failed_state
            and r10_next_scope.startswith(
                "execute M01 Xyce build/tool preflight revision-11"
            )
        ) or (
            r10_failed_state
            and r10_next_scope.startswith(
                "preserve and commit the M01 Xyce build/tool preflight revision-11"
            )
        )
        add_check(
            checks,
            "m01_xyce_preflight_r10:implementation_state_and_unexecuted_chain",
            r10_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R10"
            and r10_config.get("revision") == 10
            and r10_config.get("status") == "preflight_planned"
            and r10_config.get("scope", {}).get("active_material_scope") == "IGZO only"
            and r10_config.get("scope", {}).get("formal_m01_numerical_run") is False
            and r10_config.get("scope", {}).get("circuit_or_downstream_permitted") is False
            and (r10_machine_planned or r10_ready_state or r10_failed_state)
            and (not r10_contract_exists if r10_machine_planned else r10_contract_exists)
            and (
                (r10_machine_planned or r10_ready_state)
                and all(not path.exists() for path in r10_future_paths)
                or r10_failed_state
                and r10_run_directory.is_dir()
                and all(path.is_file() for path in r10_partial_paths)
                and all(not path.exists() for path in r10_uncreated_future_paths)
            )
            and all(not path.exists() for path in r10_formal_paths)
            and r10_r08_binding_ok
            and r10_r09_binding_ok
            and r10_binary.is_file()
            and sha256(r10_binary) == r10_r07["xyce_binary_sha256"]
            and r10_candidate.is_file()
            and sha256(r10_candidate) == r10_config["device_syntax_check"]["candidate_sha256"]
            and "EXPECTED_CHECK_COUNT = 36" in r10_contract_source
            and "EXPECTED_CHECK_COUNT = 32" in r10_runner_source
            and "EXPECTED_CHECK_COUNT = 25" in r10_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 32" in r10_checker_source
            and "def read_xyce_prn" in r10_common_source
            and "import subprocess" not in r10_checker_source
            and "import subprocess" not in r10_common_source
            and re.search(r"^(?:import|from)\s+subprocess\b", r10_contract_source, re.MULTILINE) is None
            and "m01-xyce-build-preflight-r10-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r10:" in makefile_source
            and "m01-xyce-build-preflight-r10-check:" in makefile_source
            and all("r09" not in source.lower() for source in (r10_runner_source, r10_checker_source, r10_common_source))
            and r10_machine.get("r09_contract_failure_preserved") is True
            and r10_machine.get("r09_runner_rerun") is False
            and r10_machine.get("r09_independent_checker_run") is False
            and r10_machine.get("r08_runner_rerun") is False
            and r10_machine.get("r08_independent_checker_run") is False
            and r10_machine.get("r07_runner_rerun") is False
            and r10_machine.get("r07_independent_checker_run") is False
            and r10_machine.get("ngspice_invoked") is False
            and r10_machine.get("aimspice_invoked") is False
            and r10_machine.get("build_processes_invoked") == 0
            and (
                r10_machine.get("simulator_processes_invoked") == 0
                if not r10_failed_state
                else r10_machine.get("simulator_processes_invoked") == 3
            )
            and r10_machine.get("circuit_or_downstream_permitted") is False
            and r10_next_scope_valid,
            f"planned={r10_machine_planned} ready={r10_ready_state} failed={r10_failed_state} "
            f"r08_binding={r10_r08_binding_ok} r09_binding={r10_r09_binding_ok} "
            f"future_absent={sum(not path.exists() for path in r10_uncreated_future_paths)}/{len(r10_uncreated_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r10:implementation_state_and_unexecuted_chain",
            False,
            str(error),
        )

    m01_xyce_r11_config_path = ROOT / "config" / "m01_xyce_build_preflight_r11.json"
    m01_xyce_r11_contract_report_path = (
        ROOT / "results" / "reports" / "m01_xyce_build_preflight_contract_r11.json"
    )
    m01_xyce_r11_contract_checker_path = (
        ROOT / "scripts" / "check_m01_xyce_build_preflight_r11_contract.py"
    )
    m01_xyce_r11_runner_path = ROOT / "scripts" / "run_m01_xyce_build_preflight_r11.py"
    m01_xyce_r11_checker_path = ROOT / "scripts" / "check_m01_xyce_build_preflight_r11.py"
    m01_xyce_r11_common_path = ROOT / "scripts" / "m01_xyce_r11_common.py"
    try:
        r11_config = json.loads(m01_xyce_r11_config_path.read_text(encoding="utf-8"))
        r11_machine = experiment_map["M01"].get("xyce_build_preflight_r11", {})
        r11_outputs = r11_config["outputs"]
        r11_future_paths = [
            ROOT / value for key, value in r11_outputs.items() if key != "contract_report"
        ]
        r11_formal_paths = [
            ROOT / value for value in r11_config.get("formal_outputs_that_must_remain_absent", [])
        ]
        r11_contract_exists = m01_xyce_r11_contract_report_path.is_file()
        r11_contract_report = (
            json.loads(m01_xyce_r11_contract_report_path.read_text(encoding="utf-8"))
            if r11_contract_exists
            else {}
        )
        r11_r07 = r11_config["r07_failure_binding"]
        r11_r10 = r11_config["r10_failure_binding"]
        r11_r10_static_path = ROOT / r11_r10["static_contract_report_path"]
        r11_r10_failure_path = ROOT / r11_r10["runner_failure_report_path"]
        r11_r10_failure_log_path = ROOT / r11_r10["runner_failure_log_path"]
        r11_r10_static = json.loads(r11_r10_static_path.read_text(encoding="utf-8"))
        r11_r10_failure = json.loads(r11_r10_failure_path.read_text(encoding="utf-8"))
        r11_r10_summary = r11_r10_failure.get("summary", {})
        r11_r10_bindings = [
            (r11_r10["config_path"], r11_r10["config_sha256"]),
            (r11_r10["common_hash_helper_path"], r11_r10["common_hash_helper_sha256"]),
            (r11_r10["contract_checker_path"], r11_r10["contract_checker_sha256"]),
            (r11_r10["runner_path"], r11_r10["runner_sha256"]),
            (r11_r10["independent_checker_path"], r11_r10["independent_checker_sha256"]),
            (r11_r10["static_contract_report_path"], r11_r10["static_contract_report_sha256"]),
            (r11_r10["runner_failure_report_path"], r11_r10["runner_failure_report_sha256"]),
            (r11_r10["runner_failure_log_path"], r11_r10["runner_failure_log_sha256"]),
        ]
        r11_r10_partial_directory = ROOT / r11_r10["partial_run_directory"]
        r11_r10_tree = (
            digest_r10_tree(r11_r10_partial_directory)
            if r11_r10_partial_directory.is_dir()
            else {}
        )
        r11_r10_binding_ok = (
            r11_r10["bound_commit"] == "63be6a45e583b61027b18614cec4f83ce93848ad"
            and r11_r10["must_remain_unchanged"] is True
            and r11_r10["runner_rerun"] is False
            and r11_r10["independent_checker_run"] is False
            and r11_r10_static.get("status") == "PASS"
            and r11_r10_static.get("evidence_level") == "E3"
            and r11_r10_static.get("summary", {}).get("passed") == 36
            and r11_r10_static.get("summary", {}).get("failed") == 0
            and r11_r10_failure.get("status") == "FAIL"
            and r11_r10_failure.get("evidence_level") == "E0"
            and r11_r10_failure.get("failure_category")
            == "runner_unicode_path_ascii_encoding"
            and r11_r10_summary.get("process_invocations") == 3
            and r11_r10_summary.get("build_processes_invoked") == 0
            and r11_r10_summary.get("controlled_bsource_self_test_invoked") is True
            and r11_r10_summary.get("device_syntax_only_invoked") is False
            and r11_r10_summary.get("formal_device_dc_invoked") is False
            and all(
                (ROOT / path).is_file() and sha256(ROOT / path) == expected
                for path, expected in r11_r10_bindings
            )
            and all(
                r11_r10_tree.get(key) == value
                for key, value in r11_r10["partial_run_tree"].items()
            )
        )
        r11_machine_planned = (
            r11_machine.get("status") == "contract_planned"
            and r11_machine.get("revision") == 11
            and r11_machine.get("current_evidence") == "E0"
            and r11_machine.get("contract_check_completed") is False
            and r11_machine.get("contract_status") == "NOT_RUN"
            and r11_machine.get("result_paths") == []
            and r11_machine.get("artifact_hashes") == {}
        )
        r11_static_pass = (
            r11_contract_exists
            and r11_contract_report.get("status") == "PASS"
            and r11_contract_report.get("contract_status") == "PASS"
            and r11_contract_report.get("evidence_level") == "E3"
            and r11_contract_report.get("build_status") == "NOT_RUN_BY_CONTRACT_CHECK"
            and r11_contract_report.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R11"
            and len(r11_contract_report.get("checks", [])) == 36
            and all(item.get("status") == "PASS" for item in r11_contract_report.get("checks", []))
            and r11_contract_report.get("summary", {}).get("passed") == 36
            and r11_contract_report.get("summary", {}).get("failed") == 0
            and r11_contract_report.get("summary", {}).get("build_processes_invoked") == 0
            and r11_contract_report.get("summary", {}).get("simulator_processes_invoked") == 0
            and r11_contract_report.get("summary", {}).get("device_netlist_created") is False
            and r11_contract_report.get("summary", {}).get("numerical_outputs_created") is False
            and r11_contract_report.get("config", {}).get("sha256")
            == sha256(m01_xyce_r11_config_path)
            and r11_contract_report.get("checker", {}).get("sha256")
            == sha256(m01_xyce_r11_contract_checker_path)
        )
        r11_ready_state = (
            r11_static_pass
            and r11_machine.get("status") == "contract_ready"
            and r11_machine.get("revision") == 11
            and r11_machine.get("current_evidence") == "E3"
            and r11_machine.get("contract_check_completed") is True
            and r11_machine.get("contract_status") == "PASS"
            and r11_machine.get("contract_checks_passed") == 36
            and r11_machine.get("contract_checks_failed") == 0
            and r11_machine.get("preflight_run_completed") is False
            and r11_machine.get("result_paths")
            == ["results/reports/m01_xyce_build_preflight_contract_r11.json"]
            and r11_machine.get("artifact_hashes", {}).get("contract_report_sha256")
            == sha256(m01_xyce_r11_contract_report_path)
        )
        r11_runner_source = m01_xyce_r11_runner_path.read_text(encoding="utf-8")
        r11_checker_source = m01_xyce_r11_checker_path.read_text(encoding="utf-8")
        r11_contract_source = m01_xyce_r11_contract_checker_path.read_text(encoding="utf-8")
        r11_common_source = m01_xyce_r11_common_path.read_text(encoding="utf-8")
        r11_candidate_contract = r11_config["device_syntax_check"]
        r11_candidate = ROOT / r11_candidate_contract["candidate_path"]
        r11_next_scope = config.get("tcad_track", {}).get("next_scope", "")
        r11_next_scope_valid = (
            r11_machine_planned
            and r11_next_scope.startswith(
                "establish and commit M01 Xyce build/tool preflight revision-11 path-safe parser contract"
            )
        ) or (
            r11_ready_state
            and r11_next_scope.startswith("execute M01 Xyce build/tool preflight revision-11")
        )
        r11_expected_archive_paths = [
            r11_r10["static_contract_report_path"],
            r11_r10["runner_failure_report_path"],
            r11_r10["runner_failure_log_path"],
            r11_r10["partial_run_directory"],
        ]
        add_check(
            checks,
            "m01_xyce_preflight_r11:path_safe_contract_and_unexecuted_chain",
            r11_config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R11"
            and r11_config.get("revision") == 11
            and r11_config.get("status") == "preflight_planned"
            and r11_config.get("scope", {}).get("active_material_scope") == "IGZO only"
            and r11_config.get("scope", {}).get("formal_m01_numerical_run") is False
            and r11_config.get("scope", {}).get("circuit_or_downstream_permitted") is False
            and (r11_machine_planned or r11_ready_state)
            and (not r11_contract_exists if r11_machine_planned else r11_contract_exists)
            and all(not path.exists() for path in r11_future_paths)
            and all(not path.exists() for path in r11_formal_paths)
            and r11_r10_binding_ok
            and r11_machine.get("r10_runner_failure_preserved") is True
            and r11_machine.get("r10_failure_bound_commit") == r11_r10["bound_commit"]
            and r11_machine.get("r10_failure_archive_paths") == r11_expected_archive_paths
            and r11_machine.get("r10_partial_run_tree_sha256")
            == r11_r10["partial_run_tree"]["tree_sha256"]
            and r11_machine.get("r10_runner_rerun") is False
            and r11_machine.get("r10_independent_checker_run") is False
            and r11_candidate.is_file()
            and sha256(r11_candidate) == r11_candidate_contract["candidate_sha256"]
            and r11_candidate_contract.get("include_path_mode") == "repository_relative_ascii"
            and r11_candidate_contract.get("include_path")
            == r11_candidate_contract.get("candidate_path")
            and r11_candidate_contract.get("include_path", "").isascii()
            and not Path(r11_candidate_contract.get("include_path", "")).is_absolute()
            and r11_candidate_contract.get("runner_working_directory") == "project_root"
            and r11_candidate_contract.get("netlist_encoding") == "ascii"
            and r11_candidate_contract.get("absolute_project_path_forbidden") is True
            and "EXPECTED_CHECK_COUNT = 36" in r11_contract_source
            and "EXPECTED_CHECK_COUNT = 32" in r11_runner_source
            and "EXPECTED_CHECK_COUNT = 25" in r11_checker_source
            and "EXPECTED_RUNNER_CHECK_COUNT = 32" in r11_checker_source
            and "candidate_relative_path" in r11_runner_source
            and "candidate_include_path = candidate_relative_path.as_posix()" in r11_runner_source
            and "candidate_include_path.isascii()" in r11_runner_source
            and "not candidate_relative_path.is_absolute()" in r11_runner_source
            and "str(ROOT) not in device_syntax_text" in r11_runner_source
            and "def read_xyce_prn" in r11_common_source
            and "import subprocess" not in r11_checker_source
            and "import subprocess" not in r11_common_source
            and re.search(r"^(?:import|from)\s+subprocess\b", r11_contract_source, re.MULTILINE) is None
            and "m01-xyce-build-preflight-r11-contract-check:" in makefile_source
            and "m01-xyce-build-preflight-r11:" in makefile_source
            and "m01-xyce-build-preflight-r11-check:" in makefile_source
            and r11_machine.get("ngspice_invoked") is False
            and r11_machine.get("aimspice_invoked") is False
            and r11_machine.get("build_processes_invoked") == 0
            and r11_machine.get("simulator_processes_invoked") == 0
            and r11_machine.get("device_netlist_invoked") is False
            and r11_machine.get("numerical_outputs_created") is False
            and r11_machine.get("proprietary_binary_accepted") is False
            and r11_machine.get("circuit_or_downstream_permitted") is False
            and "not parser execution"
            in config.get("tcad_track", {}).get(
                "m01_xyce_build_preflight_r11_contract_boundary", ""
            )
            and r11_next_scope_valid,
            f"planned={r11_machine_planned} ready={r11_ready_state} "
            f"r10_binding={r11_r10_binding_ok} "
            f"future_absent={sum(not path.exists() for path in r11_future_paths)}/{len(r11_future_paths)}",
        )
    except Exception as error:  # noqa: BLE001
        add_check(
            checks,
            "m01_xyce_preflight_r11:path_safe_contract_and_unexecuted_chain",
            False,
            str(error),
        )

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
