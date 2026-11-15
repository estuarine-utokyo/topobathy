#!/usr/bin/env python3
"""Report the state of the Tokyo Bay data archive under $DATA_DIR/geodata/bathymetry.

Read-only and light (no file contents are read except the Sanbanze checksum check):
for each top-level dataset directory, whether it has a README, the number of entries, the
newest file time; the derived-DEM chain in M7001/TP; and the Sanbanze checksum check.
The curated description of each dataset is in docs/data_archive.md; this script shows
whether the disk still matches it.
"""
from __future__ import annotations

import hashlib
import sys
from datetime import datetime
from pathlib import Path

from topobathy import config

CHAIN = [
    "M7001_dem_tokyobay_50m_m7001_only.nc", "M7001_dem_tokyobay_50m_chiba_channel.nc",
    "M7001_dem_tokyobay_50m_futtsu.nc", "M7001_dem_tokyobay_50m_sanbanze.nc", "M7001_dem_tokyobay_50m.nc",
    "M7001_dem_tokyobay_10m_m7001_only.nc", "M7001_dem_tokyobay_10m_chiba_channel.nc",
    "M7001_dem_tokyobay_10m_futtsu.nc", "M7001_dem_tokyobay_10m_sanbanze.nc", "M7001_dem_tokyobay_10m.nc",
    "M7001_dem_futtsu_5m.nc",
]


def newest(p: Path) -> str:
    t = max((f.stat().st_mtime for f in p.rglob("*") if f.is_file()), default=p.stat().st_mtime)
    return datetime.fromtimestamp(t).strftime("%Y-%m-%d")


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for blk in iter(lambda: f.read(1 << 20), b""):
            h.update(blk)
    return h.hexdigest()


def main() -> int:
    b = config.get_bathymetry_dir()
    print(f"archive: {b}\n")
    print(f"{'directory':24s} {'README':7s} {'entries':>7s}  newest")
    for d in sorted(p for p in b.iterdir() if p.is_dir()):
        has = any(c.name.lower().startswith("readme") for c in d.iterdir())
        n = sum(1 for _ in d.iterdir())
        print(f"{d.name:24s} {'yes' if has else 'NO':7s} {n:7d}  {newest(d)}")
    tp = b / "M7001" / "TP"
    print("\nDEM chain (M7001/TP):")
    for name in CHAIN:
        f = tp / name
        print(f"  {name:46s} " + (datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                                  if f.exists() else "MISSING"))
    manifest = Path(__file__).resolve().parent.parent / "docs" / "sanbanze_chiba_ap.sha256"
    sd = b / "tokyo_bay" / "Sanbanze_Chiba_AP"
    bad = 0
    n = 0
    for line in manifest.read_text().splitlines():
        digest, rel = line.split(None, 1)
        n += 1
        f = sd / rel.strip()
        if not f.exists() or sha256(f) != digest:
            bad += 1
            print(f"  CHECKSUM MISMATCH/MISSING: {rel}")
    print(f"\nSanbanze_Chiba_AP checksums: {n - bad}/{n} ok")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
