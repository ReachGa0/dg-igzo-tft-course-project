#!/usr/bin/env python3
"""Run the revision-3 Xyce preflight with explicit user-local BLAS/LAPACK paths."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "m01_xyce_build_preflight_r03.json"
IMPLEMENTATION_PATH = ROOT / "scripts" / "run_m01_xyce_build_preflight.py"
spec = importlib.util.spec_from_file_location("m01_xyce_build_preflight_r01_impl", IMPLEMENTATION_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError(f"Cannot load reviewed R01 runner: {IMPLEMENTATION_PATH}")
implementation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(implementation)

implementation.CONFIG_PATH = CONFIG_PATH
implementation.EXPECTED_CHECK_COUNT = 29
implementation.__file__ = str(Path(__file__))
# formal_device_dc_invoked=false is the registered no-formal execution marker.
R03_STATIC_BOUNDARY_MARKER = "formal_device_dc_invoked=false"
config: dict[str, Any] = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

original_run_command = implementation.run_command


def run_command(*args: Any, **kwargs: Any) -> tuple[bool, str]:
    name = kwargs.get("name", args[0] if args else "")
    if name == "suitesparse_configure":
        argv = list(kwargs["argv"])
        argv.extend(config["build_plan"]["suitesparse_cmake_options"])
        kwargs["argv"] = argv
    return original_run_command(*args, **kwargs)


implementation.run_command = run_command
original_add_check = implementation.add_check


def add_check(checks: list[dict[str, str]], name: str, passed: bool, detail: str) -> None:
    if name == "identity:revision_1_xyce_build_preflight":
        name = "identity:revision_3_xyce_build_preflight"
        passed = (
            config.get("stage_id") == "M01"
            and config.get("preflight_id") == "M01_XYCE_BUILD_PREFLIGHT_R03"
            and config.get("revision") == 3
            and config.get("status") == "preflight_planned"
        )
    original_add_check(checks, name, passed, detail)


implementation.add_check = add_check


if __name__ == "__main__":
    result = implementation.run_preflight()
    raise SystemExit(0 if result["status"] == "PASS" else 1)
