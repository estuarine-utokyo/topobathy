"""CLI: build a continuous chart-datum model grid (最低水面モデル) as NetCDF.

The Japan Coast Guard ERS deliverable (Okubo et al. 2022; Shiozawa et al. 2023): a
regular lon/lat grid of the chart-datum ⇄ T.P. separation over an area of interest,
built by interpolating the tide-station datum table. Soundings are then converted
by sampling this model. Applicable anywhere in Japan — supply a station table for
the region (see ``scripts/fetch_jma_tide_datums.py``) and a bounding box.

Variables written (dims ``lat, lon``):

* ``tp_minus_cd``            — Z0 = T.P. − 基本水準面 (m)
* ``chart_datum_elevation``  — 最低水面の標高 = −(T.P. − 基本水準面) (m, T.P.)
* ``chart_datum_ellipsoidal`` — 最低水面の楕円体高 (m) — only if ``--geoid`` given

Example (Tokyo Bay, JCG 1′×1.5′ resolution)::

    topobathy-build-datum-model --bbox 139.55 140.30 34.90 35.75 \
        --dlat 0.016667 --dlon 0.025 --method linear \
        --out $DATA_DIR/bathymetry/M7001/TP/M7001_chart_datum_model.nc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import xarray as xr

from topobathy import config
from topobathy.datum import GeoidModel, SeparationModel


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="topobathy-build-datum-model",
        description="Build a continuous chart-datum model (最低水面モデル) NetCDF grid.",
    )
    p.add_argument("--z0-table", type=Path, default=None, help="tide-station datum CSV")
    p.add_argument(
        "--bbox",
        nargs=4,
        type=float,
        required=True,
        metavar=("LON_MIN", "LON_MAX", "LAT_MIN", "LAT_MAX"),
        help="grid extent (degrees)",
    )
    p.add_argument("--dlat", type=float, default=1.0 / 60.0, help="lat step (deg; 1′)")
    p.add_argument(
        "--dlon", type=float, default=1.5 / 60.0, help="lon step (deg; 1.5′)"
    )
    p.add_argument(
        "--method",
        default="linear",
        choices=["idw", "linear", "cubic", "tps"],
        help="interpolation (default: linear = TIN, the JCG method)",
    )
    p.add_argument("--z0-power", type=float, default=2.0, help="IDW exponent")
    p.add_argument(
        "--geoid",
        type=Path,
        default=None,
        help="GSI geoid .asc for the ellipsoidal-height variable (optional)",
    )
    p.add_argument("--out", type=Path, required=True, help="output NetCDF path")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    table = args.z0_table or config.default_z0_table()
    model = SeparationModel.from_csv(table, power=args.z0_power, method=args.method)

    lon_c, lat_c, tp_minus_cd = model.grid(
        tuple(args.bbox), dlon=args.dlon, dlat=args.dlat
    )
    cv = model.cross_validate()
    print(model.report(tp_minus_cd.ravel()), flush=True)
    print(f"uncertainty: {cv}", flush=True)

    data = {
        "tp_minus_cd": (("lat", "lon"), tp_minus_cd),
        "chart_datum_elevation": (("lat", "lon"), -tp_minus_cd),
    }
    if args.geoid is not None:
        geoid = GeoidModel.from_gsigeo_asc(args.geoid)
        mesh_lon, mesh_lat = np.meshgrid(lon_c, lat_c)
        n = geoid.height(mesh_lon.ravel(), mesh_lat.ravel()).reshape(tp_minus_cd.shape)
        data["chart_datum_ellipsoidal"] = (("lat", "lon"), -tp_minus_cd + n)

    ds = xr.Dataset(data, coords={"lon": lon_c, "lat": lat_c})
    ds["tp_minus_cd"].attrs = {
        "long_name": "T.P. minus chart datum (基本水準面)",
        "units": "m",
    }
    ds["chart_datum_elevation"].attrs = {
        "long_name": "chart datum elevation above T.P. (最低水面モデル)",
        "units": "m",
    }
    ds.attrs = {
        "title": "Chart-datum model (最低水面モデル): T.P. − 基本水準面 separation",
        "method": f"{args.method} interpolation of {model.lon.size} JMA/JCG tide stations",
        "reference": "JCG ERS method (Okubo et al. 2022; Shiozawa et al. 2023)",
        "uncertainty_loo_cv": str(cv),
        "z0_table": str(table),
        "generated_by": "topobathy topobathy-build-datum-model",
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(args.out)
    print(
        f"wrote {args.out}  grid {lat_c.size}x{lon_c.size} "
        f"(dlat {args.dlat * 60:.2f}′, dlon {args.dlon * 60:.2f}′)",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
