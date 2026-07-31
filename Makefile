PYTHON ?= /mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/发送版本/课程3/.venv/bin/python
TCAD_PYTHON ?= /mnt/c/Users/ReachGao/Desktop/deepseek_work/大学课程/氧化物/发送版本/课程0/.venv/bin/python
DEVSIM_MATH_LIBS ?= liblapack.so.3:libblas.so.3

.PHONY: all import-baseline import-senior s00-audit s00-audit-check t01-a-check t01-b-smoke t01-b-check t01-c-transfer t01-c-check t01-d-mesh t01-d-mesh-check t01-d-idvd t01-d-idvd-check tcad-smoke report-check report check status

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
