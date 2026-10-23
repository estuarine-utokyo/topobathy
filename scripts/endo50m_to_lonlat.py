#!/usr/bin/env python3
"""Regrid the Endo (2020) 50 m Tokyo Bay bathymetry points onto a lon/lat NetCDF.

Source: ``$DATA_DIR/geodata/bathymetry/tokyobay_endo/Raster_data/50m_JGD_point_water.shp``,
the water cells of the 50 m grid built by M. Endo (2020-07, see
``東京湾地形データの編集手順.docx`` in the same directory): the earlier 50 m Tokyo Bay data
(inner bay to Kisarazu, dredged pits included), shifted to the GSI coastline and merged
with the Sanbanze survey of FY2011 (Chiba Prefecture), IDW-interpolated to 50 m cell
centres in JGD2011 plane rectangular zone IX (EPSG:6677). ``grid_code`` = elevation (m, +up);
the vertical datum is not stated in the document.

Output: ``elevation`` (+up, m) on a regular lon/lat grid (nearest 50 m cell), NaN on land
and outside the data. Also prints the depth difference from the M7001 T.P. DEM over cells
where M7001 is 10-30 m deep, as a datum check.

    python scripts/endo50m_to_lonlat.py --out $DATA_DIR/geodata/bathymetry/tokyobay_endo/nc/endo_50m_lonlat.nc
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pyogrio
import xarray as xr
from pyproj import Transformer

from topobathy import config

CELL = 50.0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src_default = (config.get_bathymetry_dir() / "tokyobay_endo" / "Raster_data"
                   / "50m_JGD_point_water.shp")
    ap.add_argument("--src", type=Path, default=src_default)
    ap.add_argument("--spacing", type=float, default=0.0005, help="lon/lat spacing (deg)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    df = pyogrio.read_dataframe(args.src, columns=["grid_code", "POINT_X", "POINT_Y"],
                                read_geometry=False)
    x, y, elev = (df[c].to_numpy(float) for c in ("POINT_X", "POINT_Y", "grid_code"))
    z = -elev  # depth, +down
    x0, y0 = x.min(), y.min()
    ix = np.rint((x - x0) / CELL).astype(int)
    iy = np.rint((y - y0) / CELL).astype(int)
    assert np.allclose(x0 + ix * CELL, x, atol=0.5) and np.allclose(y0 + iy * CELL, y, atol=0.5)
    grid = np.full((iy.max() + 1, ix.max() + 1), np.nan)
    grid[iy, ix] = z

    to_ll = Transformer.from_crs("EPSG:6677", "EPSG:4326", always_xy=True)
    to_xy = Transformer.from_crs("EPSG:4326", "EPSG:6677", always_xy=True)
    lon_c, lat_c = to_ll.transform(x, y)
    d = args.spacing
    lon = np.arange(np.floor(lon_c.min() / d) * d, lon_c.max() + d, d)
    lat = np.arange(np.floor(lat_c.min() / d) * d, lat_c.max() + d, d)
    LON, LAT = np.meshgrid(lon, lat)
    X, Y = to_xy.transform(LON, LAT)
    jx = np.rint((X - x0) / CELL).astype(int)
    jy = np.rint((Y - y0) / CELL).astype(int)
    ok = (jx >= 0) & (jx < grid.shape[1]) & (jy >= 0) & (jy < grid.shape[0])
    depth = np.full(LON.shape, np.nan)
    depth[ok] = grid[jy[ok], jx[ok]]

    ds = xr.Dataset(
        {"elevation": (("lat", "lon"), (-depth).astype("float32"),
                       {"units": "m", "positive": "up",
                        "long_name": "elevation (negative = depth), vertical datum not stated"})},
        coords={"lon": ("lon", lon, {"units": "degrees_east"}),
                "lat": ("lat", lat, {"units": "degrees_north"})},
        attrs={"source": str(args.src),
               "history": "50 m JGD2011 zone IX cells (EPSG:6677) -> lon/lat, nearest cell; "
                          "scripts/endo50m_to_lonlat.py (topobathy)",
               "note": "Endo (2020) edit of the earlier 50 m Tokyo Bay data + Sanbanze FY2011 survey"})
    args.out.parent.mkdir(parents=True, exist_ok=True)
    ds.to_netcdf(args.out, encoding={"elevation": {"zlib": True, "complevel": 4}})
    print(f"wrote {args.out}: {len(df)} points; lon {lon_c.min():.4f}-{lon_c.max():.4f}, "
          f"lat {lat_c.min():.4f}-{lat_c.max():.4f}; depth {np.nanmin(z):.1f} to {np.nanmax(z):.1f} m")

    m7 = config.get_bathymetry_dir() / "M7001" / "TP" / "M7001_dem_tokyobay_50m.nc"
    ref = -xr.open_dataset(m7)["elevation"].interp(
        lon=xr.DataArray(lon_c, dims="p"), lat=xr.DataArray(lat_c, dims="p"),
        method="nearest").to_numpy()
    for lo, hi in ((10, 30), (2, 10)):
        sel = np.isfinite(ref) & (ref >= lo) & (ref <= hi)
        dd = z[sel] - ref[sel]
        print(f"Endo 50 m vs M7001 (M7001 depth {lo}-{hi} m T.P.): n={sel.sum()} "
              f"median={np.median(dd):+.2f} m mean={dd.mean():+.2f} m "
              f"RMS={np.sqrt((dd ** 2).mean()):.2f} m (positive = Endo deeper)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
