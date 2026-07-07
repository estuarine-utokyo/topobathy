#!/usr/bin/env python3
"""Build the Kanto-South tide-station datum table for the M7001 → T.P. conversion.

Sourced from the **authoritative JCG 一覧表** (海上保安庁「平均水面、最高水面及び最低
水面一覧表」, parsed into `topobathy/data/japan_tide_datums_jcg.csv` by
`scripts/parse_jcg_datum_table.py`): every gazetted port carries the official
`z0_msl_m` = 平均水面下(Z0) = MSL − 基本水準面, and many carry 最低水面の楕円体高.

`tp_minus_cd_m = z0_msl_m − ζ_MSL`, where ζ_MSL = local MSL above T.P. In Tokyo Bay
ζ_MSL ≈ 0.03 m (validated: JCG z0 matches the harmonic Hm2+Hs2+Hk1+Ho1, and
z0 − 0.03 matches the JMA 潮位表基準面). ζ_MSL grows a little toward Suruga Bay /
the Izu Islands (~0.05–0.09 m), so those stations are **overridden with the exact
JMA 潮位表基準面 T.P.−CD** (no ζ_MSL assumption) — see `JMA_DIRECT` below.

Supersedes the earlier harmonic-file (`Tide-ToKYOWAN.txt`) build: the JCG 一覧表 is
the official superset (85 vs 38 Kanto ports) and adds the ellipsoidal heights.

Run (login node, parses one small CSV): python scripts/build_z0_table.py
"""

from __future__ import annotations

import csv
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JCG = REPO / "topobathy" / "data" / "japan_tide_datums_jcg.csv"
OUT = REPO / "topobathy" / "data" / "kanto_south_tp_minus_cd.csv"

# Kanto-South extent (M7001 sheet + margin): lon, lat bounds.
REGION = (138.0, 141.6, 32.9, 36.2)
MSL_MINUS_TP = 0.03  # ζ_MSL in Tokyo Bay (validated vs JMA 潮位表基準面)

# Exact JMA 潮位表基準面 T.P.−CD (= −潮位表基準面の標高), fetched per station (2026-07)
# from https://www.data.jma.go.jp/kaiyou/db/tide/suisan/ . These override the
# z0−ζ_MSL approximation where ζ_MSL departs from 0.03 m (Suruga Bay, Izu Islands,
# NE Pacific) or to pin the primary bay gauges exactly.
JMA_DIRECT = [
    # name_ja, lon, lat, tp_minus_cd_m
    ("東京(JMA)", 139.770, 35.653, 1.141),
    ("横浜(JMA)", 139.650, 35.450, 1.150),
    ("布良(JMA)", 139.833, 34.917, 0.867),
    ("岡田(伊豆大島,JMA)", 139.383, 34.783, 0.848),
    ("三宅島坪田(JMA)", 139.550, 34.050, 0.638),
    ("八丈島神湊(JMA)", 139.800, 33.133, 0.563),
    ("御前崎(JMA)", 138.217, 34.617, 0.965),
    ("清水港(JMA)", 138.517, 35.017, 0.864),
    ("石廊崎(JMA)", 138.850, 34.617, 0.957),
    ("内浦(JMA)", 138.883, 35.017, 0.923),
    ("小名浜(JMA)", 140.900, 36.933, 1.000),
]
_OVERRIDE_RADIUS = 0.03  # deg: a JMA-direct station replaces a JCG port within this


def _load_region() -> list[dict[str, str]]:
    lon_lo, lon_hi, lat_lo, lat_hi = REGION
    rows: list[dict[str, str]] = []
    with JCG.open(encoding="utf-8") as fh:
        for r in csv.DictReader(row for row in fh if not row.lstrip().startswith("#")):
            lon, lat = float(r["lon"]), float(r["lat"])
            if lon_lo <= lon <= lon_hi and lat_lo <= lat <= lat_hi:
                rows.append(r)
    return rows


def main() -> int:
    if not JCG.is_file():
        raise SystemExit(f"{JCG} missing — run scripts/parse_jcg_datum_table.py first")
    rows = _load_region()

    # Apply the exact-JMA overrides: drop any JCG port within the radius of a JMA
    # station, then add the JMA station (exact T.P.−CD).
    kept: list[dict[str, str]] = []
    for r in rows:
        lon, lat = float(r["lon"]), float(r["lat"])
        if any(
            abs(lon - jl) <= _OVERRIDE_RADIUS and abs(lat - ja) <= _OVERRIDE_RADIUS
            for _, jl, ja, _ in JMA_DIRECT
        ):
            continue
        kept.append(
            {
                "station": r["station"],
                "name_ja": r["name_ja"],
                "lon": r["lon"],
                "lat": r["lat"],
                "tp_minus_cd_m": r["tp_minus_cd_m"],  # = z0_msl − 0.03 (from JCG build)
                "z0_msl_m": r["z0_msl_m"],
                "cd_ellipsoidal_m": r.get("cd_ellipsoidal_m", ""),
                "source": "jcg_heights_table",
            }
        )
    for name, lon, lat, tp in JMA_DIRECT:
        kept.append(
            {
                "station": name,
                "name_ja": name,
                "lon": f"{lon}",
                "lat": f"{lat}",
                "tp_minus_cd_m": f"{tp}",
                "z0_msl_m": f"{tp + MSL_MINUS_TP:.3f}",
                "cd_ellipsoidal_m": "",
                "source": "jma_tide_table",
            }
        )
    kept.sort(key=lambda r: (float(r["lat"]), float(r["lon"])))

    header = (
        "# Kanto-South tide-station datum table for M7001 → T.P. (tp_minus_cd_m =\n"
        "# T.P. − 基本水準面, m). Built by scripts/build_z0_table.py from the JCG 一覧表\n"
        "# (topobathy/data/japan_tide_datums_jcg.csv; source=jcg_heights_table,\n"
        "# tp = z0_msl − ζ_MSL≈0.03) with exact JMA 潮位表基準面 anchors\n"
        "# (source=jma_tide_table) for Suruga Bay / Izu Islands / NE Pacific.\n"
        "# See docs/vertical_datum.md.\n"
    )
    OUT.write_text("")
    with OUT.open("w", newline="", encoding="utf-8") as fh:
        fh.write(header)
        w = csv.DictWriter(
            fh,
            fieldnames=[
                "station",
                "name_ja",
                "lon",
                "lat",
                "tp_minus_cd_m",
                "z0_msl_m",
                "cd_ellipsoidal_m",
                "source",
            ],
        )
        w.writeheader()
        w.writerows(kept)

    tps = [float(r["tp_minus_cd_m"]) for r in kept]
    n_jma = sum(r["source"] == "jma_tide_table" for r in kept)
    print(
        f"wrote {OUT}  ({len(kept)} stations: {len(kept) - n_jma} JCG 一覧表 + {n_jma} JMA exact)"
    )
    print(f"  tp_minus_cd_m range [{min(tps):.3f}, {max(tps):.3f}] m")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
