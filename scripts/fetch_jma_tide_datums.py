#!/usr/bin/env python3
"""Fetch JMA tide-table datum (潮位表基準面の標高) -> ``tp_minus_cd_m`` for stations.

Builds a nationwide-capable tide-station datum table for
:class:`topobathy.datum.separation.SeparationModel`. For each JMA station code it
reads ``潮位表基準面の標高`` (elevation of the tide-table datum ≈ chart datum,
relative to T.P.) from the JMA tidal database and records

    tp_minus_cd_m = − (潮位表基準面の標高) / 100      # T.P. − 基本水準面 (m)

Input: a CSV of ``code,name_ja,lon,lat`` (JMA station codes). Output: a datum CSV
with an added ``tp_minus_cd_m`` column (stations lacking a published datum, shown
as "-" by JMA, are skipped and logged).

This is a light HTTP job — run it on a GENKAI compute node (login node blocks
sustained outbound); it is polite (1 s between requests). The JMA tide tables are
public. Source: https://www.data.jma.go.jp/kaiyou/db/tide/suisan/

Usage:
    python scripts/fetch_jma_tide_datums.py stations_in.csv datums_out.csv
"""

from __future__ import annotations

import csv
import re
import sys
import time
import urllib.request
from pathlib import Path

URL = "https://www.data.jma.go.jp/kaiyou/db/tide/suisan/suisan.php?stn={code}"
# "潮位表基準面の標高：</td><td ...>-114.1(cm)" (HTML tags between label and
# value; value may be "-" when undetermined). Allow any tags/space in between.
_PATTERN = re.compile(
    r"潮位表基準面の標高[：:]\s*(?:<[^>]+>\s*)*(-?\d+(?:\.\d+)?)\s*\(?cm"
)
_UA = {"User-Agent": "topobathy/0.1 (research; contact via repo)"}


def fetch_datum_cm(code: str, timeout: float = 30.0) -> float | None:
    """Return 潮位表基準面の標高 [cm] for a JMA station code, or None if undetermined."""
    req = urllib.request.Request(URL.format(code=code), headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
        html = resp.read().decode("utf-8", errors="replace")
    m = _PATTERN.search(html)
    return float(m.group(1)) if m else None


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        sys.exit("usage: fetch_jma_tide_datums.py <stations_in.csv> <datums_out.csv>")
    src, dst = Path(args[0]), Path(args[1])

    with src.open(newline="", encoding="utf-8") as fh:
        rows = [r for r in csv.DictReader(fh) if not r["code"].startswith("#")]

    out: list[dict[str, str]] = []
    for r in rows:
        code = r["code"].strip()
        try:
            cm = fetch_datum_cm(code)
        except Exception as exc:  # network hiccup -> skip, keep going
            print(f"  {code} {r.get('name_ja', '')}: ERROR {exc}", flush=True)
            cm = None
        if cm is None:
            print(
                f"  {code} {r.get('name_ja', '')}: no published datum, skipped",
                flush=True,
            )
        else:
            out.append(
                {
                    "station": code,
                    "name_ja": r.get("name_ja", ""),
                    "lon": r["lon"],
                    "lat": r["lat"],
                    "tp_minus_cd_m": f"{-cm / 100.0:.3f}",
                    "source": "jma_tide_table",
                }
            )
            print(f"  {code} {r.get('name_ja', '')}: {-cm / 100.0:+.3f} m", flush=True)
        time.sleep(1.0)  # be polite

    dst.parent.mkdir(parents=True, exist_ok=True)
    with dst.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=["station", "name_ja", "lon", "lat", "tp_minus_cd_m", "source"],
        )
        w.writeheader()
        w.writerows(out)
    print(f"wrote {dst} ({len(out)}/{len(rows)} stations with a published datum)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
