#!/usr/bin/env python3
"""Parse the JCG「平均水面、最高水面及び最低水面一覧表」PDF into a datum table.

The Japan Coast Guard (海上保安庁) publishes, per port nationwide, the official
tidal / chart-datum quantities used for nautical charts. This script extracts, for
every port, the columns needed to build a vertical-datum separation model anywhere
in Japan:

* ``z0_msl_m``         — 平均水面下 (Z0) = 平均水面 − 最低水面 (基本水準面), i.e. MSL
  above chart datum (m). This is the authoritative Z0 (= Hm2+Hs2+Hk1+Ho1).
* ``cd_ellipsoidal_m`` — 最低水面の楕円体高 = chart datum height above the GRS80
  ellipsoid (m), where published (GNSS-surveyed ports). With a geoid model this
  gives the exact chart-datum 標高 / T.P. offset.

The PDF is a text (FlateDecode) table; parsing uses word positions (``pymupdf``),
so values are read programmatically — no transcription. Column x-bands were
calibrated on the layout (lat ~310, lon ~358, Z0 ~502, 楕円体高 ~528 pt).

Source (public): https://www1.kaiho.mlit.go.jp/TIDE/datum/index.pdf
Save it at ``$DATA_DIR/tides/jcg_datum/heights_index.pdf`` and run:

    python scripts/parse_jcg_datum_table.py            # -> topobathy/data/japan_tide_datums_jcg.csv
"""

from __future__ import annotations

import csv
import os
import sys
from pathlib import Path

import fitz  # pymupdf

OUT = (
    Path(__file__).resolve().parents[1]
    / "topobathy"
    / "data"
    / "japan_tide_datums_jcg.csv"
)

# column x-bands (pt) in the A4 landscape-of-portrait table layout
LAT_X = (300.0, 342.0)
LON_X = (345.0, 382.0)
Z0_X = (492.0, 516.0)
ELL_X = (518.0, 543.0)
NAME_X = (80.0, 112.0)
# 所在 (location description) markers — reject these as a "name"
_DESC = (
    "頂",
    "BM",
    "にある",
    "防波堤",
    "構内",
    "基部",
    "そば",
    "付近",
    "験潮",
    "金属標",
)

HEADER = """\
# JCG official tidal-datum table (海上保安庁「平均水面、最高水面及び最低水面一覧表」).
# One row per gazetted port nationwide. Parsed from the public PDF by
# scripts/parse_jcg_datum_table.py (word-position extraction; no transcription).
#  z0_msl_m         = 平均水面下(Z0) = 平均水面 − 最低水面(基本水準面), MSL above chart datum.
#  cd_ellipsoidal_m = 最低水面の楕円体高 (GRS80 ellipsoid), where GNSS-published (else blank).
#  tp_minus_cd_m    = z0_msl_m − ζ_MSL(≈0.03 m Kanto): T.P. − 基本水準面 (approx.; for the
#                     exact value use cd_ellipsoidal_m with a GSI geoid, see docs/vertical_datum.md).
# Source: https://www1.kaiho.mlit.go.jp/TIDE/datum/index.pdf
"""

MSL_MINUS_TP = (
    0.03  # ζ_MSL used for the convenience tp_minus_cd_m column (Kanto anchor)
)


def _dms(s: str) -> float | None:
    parts = s.split("-")
    try:
        v = float(parts[0]) + float(parts[1]) / 60.0
        if len(parts) > 2:
            v += float(parts[2]) / 3600.0
        return v
    except (ValueError, IndexError):
        return None


def _in(x: float, band: tuple[float, float]) -> bool:
    return band[0] <= x <= band[1]


def parse(pdf: Path) -> list[dict[str, object]]:
    doc = fitz.open(pdf)
    rows: list[dict[str, object]] = []
    for page in doc:
        by_y: dict[int, list[tuple[float, str]]] = {}
        for x0, y0, _x1, _y1, txt, *_ in page.get_text("words"):
            by_y.setdefault(round(y0 / 2.0) * 2, []).append((x0, txt))
        for toks in by_y.values():
            toks.sort()
            name = lat = lon = z0 = ell = None
            for x, t in toks:
                if _in(x, NAME_X) and name is None and not t[0].isdigit():
                    if not any(d in t for d in _DESC):
                        name = t
                elif _in(x, LAT_X) and "-" in t:
                    lat = _dms(t)
                elif _in(x, LON_X) and "-" in t:
                    lon = _dms(t)
                elif _in(x, Z0_X):
                    try:
                        z0 = float(t)
                    except ValueError:
                        pass
                elif _in(x, ELL_X):
                    try:
                        ell = float(t)
                    except ValueError:
                        pass
            if lat is not None and lon is not None and z0 is not None:
                rows.append(
                    {
                        "name": name or "",
                        "lon": round(lon, 4),
                        "lat": round(lat, 4),
                        "z0_msl_m": z0,
                        "cd_ellipsoidal_m": ell,
                    }
                )
    return rows


def dedupe(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Collapse near-coincident rows (same port, benchmark sub-lines) by ~100 m,
    keeping a named row and any published ellipsoidal height."""
    best: dict[tuple[float, float], dict[str, object]] = {}
    for r in rows:
        key = (round(float(r["lon"]), 3), round(float(r["lat"]), 3))
        cur = best.get(key)
        if cur is None:
            best[key] = dict(r)
            continue
        if not cur["name"] and r["name"]:
            cur["name"] = r["name"]
        if cur["cd_ellipsoidal_m"] is None and r["cd_ellipsoidal_m"] is not None:
            cur["cd_ellipsoidal_m"] = r["cd_ellipsoidal_m"]
    return list(best.values())


def main() -> int:
    data_dir = os.environ.get("DATA_DIR")
    if not data_dir:
        sys.exit("ERROR: DATA_DIR unset")
    pdf = Path(data_dir) / "tides" / "jcg_datum" / "heights_index.pdf"
    if not pdf.is_file():
        sys.exit(f"ERROR: {pdf} not found (download index.pdf; see module docstring)")

    rows = dedupe(parse(pdf))
    rows.sort(key=lambda r: (r["lat"], r["lon"]))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        fh.write(HEADER)
        w = csv.writer(fh)
        w.writerow(
            [
                "station",
                "name_ja",
                "lon",
                "lat",
                "tp_minus_cd_m",
                "z0_msl_m",
                "cd_ellipsoidal_m",
                "source",
            ]
        )
        for i, r in enumerate(rows):
            tp = round(float(r["z0_msl_m"]) - MSL_MINUS_TP, 3)
            ell = "" if r["cd_ellipsoidal_m"] is None else r["cd_ellipsoidal_m"]
            w.writerow(
                [
                    f"jcg{i:04d}",
                    r["name"],
                    r["lon"],
                    r["lat"],
                    tp,
                    r["z0_msl_m"],
                    ell,
                    "jcg_heights_table",
                ]
            )

    z0s = [float(r["z0_msl_m"]) for r in rows]
    n_ell = sum(r["cd_ellipsoidal_m"] is not None for r in rows)
    print(f"wrote {OUT}  ({len(rows)} ports; {n_ell} with 最低水面楕円体高)")
    print(f"  z0_msl_m range [{min(z0s):.2f}, {max(z0s):.2f}] m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
