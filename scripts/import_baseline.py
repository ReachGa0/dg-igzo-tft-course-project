#!/usr/bin/env python3
"""Import a frozen, hashed subset of the existing course assets."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "project.json"
DEST_ROOT = ROOT / "data" / "raw" / "baseline"

SELECTIONS = {
    "ngspice": [
        "spice/netlists/igzo_transfer.cir",
        "spice/netlists/igzo_output.cir",
        "data/igzo_transfer.csv",
        "data/igzo_output.csv",
    ],
    "aimspice": [
        "01_igzo_transfer.cir",
        "02_igzo_output.cir",
    ],
    "klayout_pdk": [
        "layouts/igzo_tft_W60_L10.gds",
    ],
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def selected_files(source_root: Path, patterns: list[str]) -> list[Path]:
    files: set[Path] = set()
    for pattern in patterns:
        matches = [path for path in source_root.glob(pattern) if path.is_file()]
        if not matches:
            raise FileNotFoundError(f"No baseline files matched {source_root / pattern}")
        files.update(matches)
    return sorted(files, key=lambda path: path.as_posix())


def clear_previous_import() -> None:
    """Remove only files managed by the previous baseline manifest."""

    manifest_path = DEST_ROOT / "manifest.json"
    if not manifest_path.is_file():
        return
    previous = json.loads(manifest_path.read_text(encoding="utf-8"))
    for record in previous.get("files", []):
        destination = ROOT / record["destination"]
        try:
            destination.relative_to(DEST_ROOT)
        except ValueError as error:
            raise RuntimeError(f"Refusing to remove unmanaged path: {destination}") from error
        if destination.is_file():
            destination.unlink()
    for directory in sorted(
        (path for path in DEST_ROOT.rglob("*") if path.is_dir()),
        key=lambda path: len(path.parts),
        reverse=True,
    ):
        try:
            directory.rmdir()
        except OSError:
            pass


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    source_roots = config["source_roots"]
    clear_previous_import()
    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    records: list[dict[str, object]] = []
    for asset_name, patterns in SELECTIONS.items():
        source_root = Path(source_roots[asset_name])
        if not source_root.is_dir():
            raise FileNotFoundError(f"Missing source root: {source_root}")

        for source in selected_files(source_root, patterns):
            relative = source.relative_to(source_root)
            destination = DEST_ROOT / asset_name / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            source_hash = sha256(source)
            destination_hash = sha256(destination)
            if source_hash != destination_hash:
                raise RuntimeError(f"Hash mismatch after copy: {source}")
            records.append(
                {
                    "asset": asset_name,
                    "source": str(source),
                    "destination": str(destination.relative_to(ROOT)),
                    "bytes": source.stat().st_size,
                    "sha256": source_hash,
                }
            )

    manifest = {
        "project_id": config["project_id"],
        "imported_on": config["created"],
        "policy": "IGZO-only whitelisted copies of existing course assets; papers and excluded material assets are not copied.",
        "files": records,
    }
    manifest_path = DEST_ROOT / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    print(f"BASELINE_IMPORT_PASS files={len(records)} manifest={manifest_path}")


if __name__ == "__main__":
    main()
