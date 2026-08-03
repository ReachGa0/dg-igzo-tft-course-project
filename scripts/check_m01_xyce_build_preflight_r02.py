#!/usr/bin/env python3
"""Independently check persisted revision-2 Xyce preflight evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPLEMENTATION_PATH = ROOT / "scripts" / "check_m01_xyce_build_preflight.py"
spec = importlib.util.spec_from_file_location("m01_xyce_build_preflight_r01_check_impl", IMPLEMENTATION_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load reviewed R01 independent checker: {IMPLEMENTATION_PATH}")
implementation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(implementation)

implementation.CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r02.json"
implementation.RUNNER_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight_r02.py"
implementation.REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_r02.json"
implementation.CHECK_REPORT_PATH = ROOT / "results" / "reports" / "m01_xyce_build_preflight_check_r02.json"
implementation.EXPECTED_CHECK_COUNT = 20
implementation.EXPECTED_RUNNER_CHECK_COUNT = 29
implementation.__file__ = str(Path(__file__))


if __name__ == "__main__":
    result = implementation.check_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
