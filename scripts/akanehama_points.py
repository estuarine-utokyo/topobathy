#!/usr/bin/env python
"""Extract the single-beam soundings (zone IX X/Y + depth) from the MLIT Akanehama
soil-placement survey spreadsheets (2019/2020, before/after) into one CSV.

Depth is positive down below the Chiba-Lighthouse tide-gauge D.L. = T.P.-1.198 m (checked in the reports' tide logs, 2026-11-15; the owner had said A.P. = T.P.-1.1344 m, a 0.064 m difference). Columns of the output:
survey, date, x_m, y_m, lon, lat, depth_ap_m  (x = northing, y = easting, plane rectangular zone IX).
The CRS is assumed to be EPSG:2451 (JGD2000 zone IX); JGD2000/2011 is not recorded.

  python scripts/akanehama_points.py --out akanehama_sb_points.csv
"""
from __future__ import annotations
import argparse, os, sys, glob
import numpy as np, pandas as pd

SRC = [  # (label, relative path glob, kind)
    ("2019-04-19_pre",  "2019/投入前/提出用データ/6-3_*.xls", "xls"),
    ("2019-08-06_post", "2019/投入後/提出用データ/07-3_*.xls", "xls"),
    ("2020-05-18_pre",  "2020/投入前/提出用データ/6-3_*.xlsx", "xlsx"),
    ("2020-07-30_post", "2020/投入後/提出用データ/7-3_*.xlsx", "xlsx"),
]


def rows_of(path, kind):
    if kind == "xls":
        import xlrd
        wb = xlrd.open_workbook(path)
        s = wb.sheet_by_name("水深計算書")
        return [s.row_values(i) for i in range(s.nrows)]
    import openpyxl
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = next(w for w in wb if w.title.startswith("測深記録_"))
    return [list(r) for r in ws.iter_rows(values_only=True)]


def extract(path, kind):
    rows = rows_of(path, kind)
    hdr = rows[0]
    ix = next(i for i, c in enumerate(hdr) if str(c).startswith("9系 X"))
    iy = next(i for i, c in enumerate(hdr) if str(c).startswith("9系 Y"))
    idp = next(i for i, c in enumerate(hdr) if str(c).strip() == "水深")
    idate = next(i for i, c in enumerate(hdr) if str(c).strip() == "DATE")
    out = []
    for r in rows[1:]:
        try:
            x, y, d = float(r[ix]), float(r[iy]), float(r[idp])
        except (TypeError, ValueError):
            continue
        out.append((x, y, d))
    return np.array(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.join(os.environ["DATA_DIR"], "geodata/bathymetry/Akanehama_MLIT"))
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    from pyproj import Transformer
    tr = Transformer.from_crs("EPSG:2451", "EPSG:4326", always_xy=True)
    frames = []
    for label, pat, kind in SRC:
        f = glob.glob(os.path.join(a.root, pat))
        if len(f) != 1:
            sys.exit(f"{label}: expected one file for {pat}, got {f}")
        p = extract(f[0], kind)
        lon, lat = tr.transform(p[:, 1], p[:, 0])
        df = pd.DataFrame(dict(survey=label, x_m=p[:, 0], y_m=p[:, 1], lon=lon, lat=lat, depth_ap_m=p[:, 2]))
        frames.append(df)
        print(f"{label}: n={len(df)} lon {lon.min():.4f}..{lon.max():.4f} lat {lat.min():.4f}..{lat.max():.4f} "
              f"depth {p[:,2].min():.2f}..{p[:,2].max():.2f} (mean {p[:,2].mean():.2f})")
    pd.concat(frames).to_csv(a.out, index=False, float_format="%.6f")


if __name__ == "__main__":
    main()
