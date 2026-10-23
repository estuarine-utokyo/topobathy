"""Readers for gridded / tiled bathymetry sources other than M7001.

All readers return depth below the source's own vertical datum (m, positive down)
over a lon/lat region ``(W, E, S, N)``:

* :func:`read_cao_2025`  -- Cabinet Office tsunami topography (首都直下地震モデル, 2025),
  nested 10/30/90 m grids in plane-rectangular zone IX, datum T.P. The finest grid
  covering each target cell wins. Returned on a regular lon/lat grid (nearest cell).
* :func:`read_mesh500`   -- Japan Coast Guard 500 m mesh depths (tiled text points).
* :func:`read_srtm15plus` -- SRTM15+ global grid (15 arc-second), datum ~ mean sea level.

The CAO data may not be redistributed as they are (also not converted): keep any grid
returned here in memory or inside the group data area, never in a repository.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

from topobathy import config

__all__ = ["read_cao_2025", "read_mesh500", "read_srtm15plus"]

Region = tuple[float, float, float, float]  # (W, E, S, N)

CAO_ZONES = {"08": "EPSG:2450", "09": "EPSG:2451", "14": "EPSG:2456"}


def _cao_dir() -> Path:
    return config.get_bathymetry_dir() / "CAO_shutochokka_2025" / "extracted"


def cao_areas(zone: str = "09") -> pd.DataFrame:
    """Area table of one plane-rectangular zone: name, dx, x_w, y_n, nx, ny."""
    xls = _cao_dir() / "計算範囲設定" / f"計算範囲設定_第{zone}系.xls"
    rows = []
    for sheet, df in pd.read_excel(xls, sheet_name=None, header=None).items():
        if not re.match(r"\d{4}m$", str(sheet)):
            continue
        for r in df.itertuples(index=False):
            name = str(r[1])
            if not re.match(r"\d{4}-\d{2}$", name):
                continue
            # columns: 1 area, 2 dx, 3/4 SW x/y, 5/6 NE x/y, 7/8 NW x/y, 9/10 nx/ny
            rows.append(dict(name=name, dx=float(r[2]), x_w=float(r[7]), y_n=float(r[8]),
                             nx=int(r[9]), ny=int(r[10])))
    return pd.DataFrame(rows)


def _cao_file(zone: str, name: str) -> Path:
    hits = list((_cao_dir() / "地形データ").glob(f"地形データ_第{zone}系/**/depth_{name}.dat"))
    if not hits:
        raise FileNotFoundError(f"CAO depth_{name}.dat (zone {zone}) not found")
    return hits[0]


def _read_cao_dat(path: Path, nx: int, ny: int) -> np.ndarray:
    """Fortran (10f8.2), NW corner first, rows west->east, north->south."""
    vals = np.array([float(line[i:i + 8]) for line in path.read_text().splitlines()
                     for i in range(0, len(line), 8) if line[i:i + 8].strip()])
    if vals.size != nx * ny:
        raise ValueError(f"{path.name}: {vals.size} values, expected {nx}x{ny}")
    return vals.reshape(ny, nx)


def read_cao_2025(region: Region, spacing: float = 0.0001, zone: str = "09",
                  sizes: tuple[float, ...] = (90.0, 30.0, 10.0)) -> xr.DataArray:
    """Depth (m below T.P., +down) on a lon/lat grid; finer CAO grids override coarser."""
    from pyproj import Transformer

    w, e, s, n = region
    lon = np.arange(w, e + spacing / 2, spacing)
    lat = np.arange(s, n + spacing / 2, spacing)
    glon, glat = np.meshgrid(lon, lat)
    tr = Transformer.from_crs("EPSG:4326", CAO_ZONES[zone], always_xy=True)
    # JPC: northing / easting; the CAO tables call easting "X" (see the dataset README)
    xe, yn = tr.transform(glon, glat)
    out = np.full(glon.shape, np.nan)
    used = []
    areas = cao_areas(zone)
    for dx in sizes:
        for a in areas[areas.dx == dx].itertuples():
            ix = np.floor((xe - a.x_w) / a.dx).astype(int)
            iy = np.floor((a.y_n - yn) / a.dx).astype(int)
            inside = (ix >= 0) & (ix < a.nx) & (iy >= 0) & (iy < a.ny)
            if not inside.any():
                continue
            d = _read_cao_dat(_cao_file(zone, a.name), a.nx, a.ny)
            out[inside] = d[iy[inside], ix[inside]]
            used.append(a.name)
    da = xr.DataArray(out, coords=dict(lat=lat, lon=lon), dims=("lat", "lon"), name="depth")
    da.attrs.update(units="m", positive="down", datum="T.P.", areas=",".join(used))
    return da


def read_mesh500(region: Region, pad: float = 0.05) -> pd.DataFrame:
    """JCG 500 m mesh points (flag, lat, lon, depth m +down) inside region (+pad)."""
    w, e, s, n = region
    d = config.get_bathymetry_dir() / "mesh500"
    frames = []
    for la in range(int(np.floor(s - pad)), int(np.floor(n + pad)) + 1):
        for lo in range(int(np.floor(w - pad)), int(np.floor(e + pad)) + 1):
            f = d / f"mesh500_{la}_{lo}.txt"
            if f.exists():
                frames.append(pd.read_csv(f, sep=r"\s+", header=None,
                                          names=["flag", "lat", "lon", "depth"]))
    p = pd.concat(frames, ignore_index=True)
    return p[p.lon.between(w - pad, e + pad) & p.lat.between(s - pad, n + pad)].reset_index(
        drop=True)


def read_srtm15plus(region: Region, pad: float = 0.02) -> xr.DataArray:
    """SRTM15+ depth (m, +down; land negative) over region (+pad)."""
    w, e, s, n = region
    z = xr.open_dataset(config.get_bathymetry_dir() / "SRTM15plus" / "SRTM15+.nc")["z"]
    z = z.sel(lon=slice(w - pad, e + pad), lat=slice(s - pad, n + pad)).load()
    da = -z
    da.name = "depth"
    da.attrs.update(units="m", positive="down", datum="mean sea level (approx.)")
    return da
