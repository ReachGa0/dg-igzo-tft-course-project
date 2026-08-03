#!/usr/bin/env python3
"""Shared hash helpers for the M01 Xyce R06 recovery gate."""

from __future__ import annotations

import hashlib
import json
import os
import stat
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def digest_tree(root: Path) -> dict[str, int | str]:
    """Hash regular files and symlinks without following links."""
    digest = hashlib.sha256()
    regular_file_count = 0
    symlink_count = 0
    total_regular_bytes = 0
    paths = sorted(root.rglob("*"), key=lambda value: value.relative_to(root).as_posix())
    for path in paths:
        relative = path.relative_to(root).as_posix()
        info = path.lstat()
        mode = stat.S_IMODE(info.st_mode)
        if path.is_symlink():
            target = os.readlink(path)
            record = f"L\0{relative}\0{mode:o}\0{target}\n".encode("utf-8")
            symlink_count += 1
        elif path.is_file():
            content_hash = sha256(path)
            record = (
                f"F\0{relative}\0{mode:o}\0{info.st_size}\0{content_hash}\n"
            ).encode("utf-8")
            regular_file_count += 1
            total_regular_bytes += info.st_size
        else:
            continue
        digest.update(record)
    return {
        "regular_file_count": regular_file_count,
        "symlink_count": symlink_count,
        "total_regular_bytes": total_regular_bytes,
        "tree_sha256": digest.hexdigest(),
    }


def tree_matches(root: Path, expected: dict[str, Any]) -> bool:
    if not root.is_dir():
        return False
    actual = digest_tree(root)
    return all(actual.get(key) == expected.get(key) for key in actual)
