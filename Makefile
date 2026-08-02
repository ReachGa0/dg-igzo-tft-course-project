PYTHON ?= /mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/发送版本/课程3/.venv/bin/python
TCAD_PYTHON ?= /mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/发送版本/课程0/.venv/bin/python
DEVSIM_MATH_LIBS ?= liblapack.so.3:libblas.so.3

.PHONY: all import-baseline import-senior s00-audit s00-audit-check t01-a-check t01-b-smoke t01-b-check t01-c-transfer t01-c-check t01-d-mesh t01-d-mesh-check t01-d-idvd t01-d-idvd-check t01-d-extract t01-d-extract-check t02-a-contract-check t02-a-regression t02-a-regression-check t02-b-contract-check t02-b-minimal t02-b-minimal-check t02-c-contract-check t02-c-bidirectional t02-c-bidirectional-check t03-p4-l-contract-check t03-p4-l-sensitivity t03-p4-l-sensitivity-check t03-p1-bias-contract-check t03-p1-bias-sensitivity t03-p1-bias-sensitivity-check t03-p1-cap-ratio-contract-check t03-p1-cap-ratio-sensitivity t03-p1-cap-ratio-sensitivity-check t03-p2-dit-contract-check t03-p2-dit-equation-smoke t03-p2-dit-equation-smoke-check t03-p2-dit-formal-contract-check t03-p2-dit-formal t03-p2-dit-formal-check t03-p2-bulk-traps-contract-check t03-p2-bulk-traps-equation-smoke t03-p2-bulk-traps-equation-smoke-check tcad-smoke report-check report check status

all: import-baseline import-senior check

import-baseline:
	"$(PYTHON)" scripts/import_baseline.py

import-senior:
	"$(PYTHON)" scripts/import_senior_reference.py

s00-audit:
	"$(PYTHON)" scripts/audit_s00_data.py

s00-audit-check:
	"$(PYTHON)" scripts/audit_s00_data.py --check-only

t01-a-check:
	"$(PYTHON)" scripts/check_t01_a_contract.py

t01-b-smoke:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t01_single_gate_smoke.py

t01-b-check:
	"$(PYTHON)" scripts/check_t01_b_smoke.py

t01-c-transfer:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t01_single_gate_transfer.py

t01-c-check:
	"$(PYTHON)" scripts/check_t01_c_transfer.py

t01-d-mesh:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t01_single_gate_mesh_refinement.py

t01-d-mesh-check:
	"$(PYTHON)" scripts/check_t01_d_mesh_refinement.py

t01-d-idvd:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t01_single_gate_idvd.py

t01-d-idvd-check:
	"$(PYTHON)" scripts/check_t01_d_idvd.py

t01-d-extract:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t01_single_gate_extraction.py

t01-d-extract-check:
	"$(PYTHON)" scripts/check_t01_d_extraction.py

t02-a-contract-check:
	"$(PYTHON)" scripts/check_t02_a_contract.py

t02-a-regression:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t02_dual_gate_limit_regression.py

t02-a-regression-check:
	"$(PYTHON)" scripts/check_t02_a_limit_regression.py

t02-b-contract-check:
	"$(PYTHON)" scripts/check_t02_b_contract.py

t02-b-minimal:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t02_dual_gate_minimal_bias.py

t02-b-minimal-check:
	"$(PYTHON)" scripts/check_t02_b_minimal_bias.py

t02-c-contract-check:
	"$(PYTHON)" scripts/check_t02_c_contract.py

t02-c-bidirectional:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t02_dual_gate_bidirectional.py

t02-c-bidirectional-check:
	"$(PYTHON)" scripts/check_t02_c_bidirectional.py

t03-p4-l-contract-check:
	"$(PYTHON)" scripts/check_t03_p4_l_contract.py

t03-p4-l-sensitivity:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t03_p4_channel_length.py

t03-p4-l-sensitivity-check:
	"$(PYTHON)" scripts/check_t03_p4_channel_length.py

t03-p1-bias-contract-check:
	"$(PYTHON)" scripts/check_t03_p1_bias_contract.py

t03-p1-bias-sensitivity:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t03_p1_secondary_bias.py

t03-p1-bias-sensitivity-check:
	"$(PYTHON)" scripts/check_t03_p1_secondary_bias.py

t03-p1-cap-ratio-contract-check:
	"$(PYTHON)" scripts/check_t03_p1_cap_ratio_contract.py

t03-p1-cap-ratio-sensitivity:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t03_p1_capacitance_ratio.py

t03-p1-cap-ratio-sensitivity-check:
	"$(PYTHON)" scripts/check_t03_p1_capacitance_ratio.py

t03-p2-dit-contract-check:
	"$(PYTHON)" scripts/check_t03_p2_dit_contract.py

t03-p2-dit-equation-smoke:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t03_p2_dit_equation_smoke.py

t03-p2-dit-equation-smoke-check:
	"$(PYTHON)" scripts/check_t03_p2_dit_equation_smoke.py

t03-p2-dit-formal-contract-check:
	"$(PYTHON)" scripts/check_t03_p2_dit_formal_contract.py

t03-p2-dit-formal:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t03_p2_dit_formal.py

t03-p2-dit-formal-check:
	"$(PYTHON)" scripts/check_t03_p2_dit_formal.py

t03-p2-bulk-traps-contract-check:
	"$(PYTHON)" scripts/check_t03_p2_bulk_traps_contract.py

t03-p2-bulk-traps-equation-smoke:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_t03_p2_bulk_traps_equation_smoke.py

t03-p2-bulk-traps-equation-smoke-check:
	"$(PYTHON)" scripts/check_t03_p2_bulk_traps_equation_smoke.py

tcad-smoke:
	DEVSIM_MATH_LIBS="$(DEVSIM_MATH_LIBS)" "$(TCAD_PYTHON)" tcad/run_dg_electrostatic.py

report-check:
	"$(PYTHON)" scripts/build_self_contained_report.py --check-only --allow-placeholders

report:
	"$(PYTHON)" scripts/build_self_contained_report.py

check:
	"$(PYTHON)" scripts/check_project.py

status:
	@sed -n '1,220p' STATUS.md
