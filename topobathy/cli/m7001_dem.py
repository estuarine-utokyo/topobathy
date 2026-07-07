"""CLI: grid the M7001 T.P. soundings into a bathymetric DEM (splines in tension).

Reads a T.P.-converted M7001 point product (from ``topobathy-m7001-to-tp``) and
grids the depth-carrying ``N`` marks (+ ``M`` low-tide line) into a regular DEM of
**T.P. elevation** (m, positive up; seabed negative) by the community-standard
method — GMT ``surface`` (continuous-curvature splines in tension; GEBCO Cook Book,
NOAA CUDEM). This is smooth (no TIN facets) and bridges the digitised depth
contours without terracing. Output: a CF NetCDF grid.

Example (Tokyo Bay, ~180 m grid)::

    topobathy-m7001-dem --region 139.55 140.30 34.90 35.75 --spacing 0.002 \
        --out $DATA_DIR/bathymetry/M7001/TP/M7001_dem_tokyobay.nc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np

from topobathy import config
from topobathy.grid import grid_dem
from topobathy.io import read_points


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="topobathy-m7001-dem",
        description="Grid M7001 T.P. soundings into a DEM (splines in tension).",
    )
    p.add_argument(
        "--tp-product",
        type=Path,
        default=None,
        help="T.P. product parquet/csv (default: $DATA_DIR/.../TP/M7001_TP.parquet)",
    )
    p.add_argument(
        "--region",
        nargs=4,
        type=float,
        default=[139.55, 140.30, 34.90, 35.75],
        metavar=("W", "E", "S", "N"),
        help="grid extent (deg; default: the Tokyo Bay window)",
    )
    p.add_argument(
        "--spacing",
        type=float,
        default=0.002,
        help="grid spacing (deg; default 0.002 ≈ 180 m)",
    )
    p.add_argument(
        "--tension", type=float, default=0.35, help="GMT surface tension (default 0.35)"
    )
    p.add_argument(
        "--mask-km",
        type=float,
        default=2.0,
        help="blank cells farther than this (km) from any sounding (default 2)",
    )
    p.add_argument(
        "--marks",
        nargs="+",
        default=["N", "M"],
        help="marks to grid (default: N M; both carry a T.P. elevation)",
    )
    p.add_argument("--out", type=Path, required=True, help="output NetCDF path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    product = args.tp_product or (config.m7001_tp_dir() / "M7001_TP.parquet")
    print(f"product: {product}", flush=True)

    df = read_points(product)
    w, e, s, n = args.region
    pad = 0.05  # include soundings just outside the window so edges are constrained
    sel = (
        df["mark"].isin(args.marks)
        & df["lon"].between(w - pad, e + pad)
        & df["lat"].between(s - pad, n + pad)
        & np.isfinite(df["z_tp"])
    )
    d = df.loc[sel]
    print(
        f"soundings: {len(d):,} (marks {'/'.join(args.marks)}) in window+pad",
        flush=True,
    )

    dem = grid_dem(
        d["lon"].to_numpy(),
        d["lat"].to_numpy(),
        d["z_tp"].to_numpy(),
        region=(w, e, s, n),
        spacing=args.spacing,
        tension=args.tension,
        mask_km=args.mask_km,
    )
    valid = np.isfinite(dem.values)
    print(
        f"DEM {dem.sizes} elevation [{float(dem.min()):.2f}, {float(dem.max()):.2f}] m; "
        f"{valid.mean():.0%} covered",
        flush=True,
    )

    dem.attrs = {
        "long_name": "seabed elevation above Tokyo Peil (T.P.)",
        "units": "m",
        "positive": "up",
        "datum": "Tokyo Peil (T.P. / 東京湾平均海面)",
        "method": (
            f"GMT surface (continuous-curvature spline in tension={args.tension}); "
            f"blockmedian pre-decimation; coverage mask {args.mask_km} km. "
            "Standard bathymetric gridding (Smith & Wessel 1990; GEBCO Cook Book)."
        ),
        "source": "M7001 (JHA/JCG) -> T.P. via topobathy; see docs/vertical_datum.md",
        "spacing_deg": str(args.spacing),
        "generated_by": "topobathy topobathy-m7001-dem",
    }
    ds = dem.to_dataset(name="elevation")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(args.out)
    print(f"wrote {args.out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
