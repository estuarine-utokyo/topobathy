"""Grid scattered soundings into a bathymetric DEM by the community-standard method.

**Continuous-curvature splines in tension** (Smith & Wessel 1990) via GMT
``surface`` — the de-facto standard for bathymetric grids (GEBCO Cook Book; NOAA
coastal DEMs / CUDEM). Splines in tension are smooth (unlike TIN, whose piecewise-
planar facets leave kinks) yet avoid the overshoot of pure minimum-curvature, and
they bridge across digitised depth contours without the terracing that TIN/nearest
produce on contour-derived data such as M7001.

Pipeline (mirrors GEBCO / GMT practice):
  1. ``blockmedian`` — robustly decimate the points to one median per grid cell
     (removes redundancy / spikes, prevents aliasing).
  2. ``surface`` — grid with a tension factor (0 = minimum curvature/harmonic-free,
     1 = harmonic; ~0.25–0.4 is the usual bathymetry range).
  3. coverage mask — blank cells farther than ``mask_km`` from any sounding
     (nearest-neighbour distance), so the grid is not extrapolated over land / gaps.

Requires GMT (via ``pygmt``); see ``environment.yml``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, cast

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike

if TYPE_CHECKING:
    import xarray as xr

__all__ = ["grid_dem"]

Region = tuple[float, float, float, float]  # (west, east, south, north)


def grid_dem(
    lon: ArrayLike,
    lat: ArrayLike,
    z: ArrayLike,
    region: Region,
    spacing: float | str,
    tension: float = 0.35,
    mask_km: float | None = 2.0,
    blockmedian: bool = True,
) -> "xr.DataArray":
    """Grid scattered ``(lon, lat, z)`` to a DEM with splines in tension (GMT).

    Parameters
    ----------
    lon, lat, z
        Sounding coordinates (degrees) and value (e.g. T.P. elevation, +up).
        Non-finite ``z`` are dropped.
    region
        ``(west, east, south, north)`` grid extent (degrees).
    spacing
        Grid spacing — degrees (float) or a GMT increment string (e.g. ``"250e"``
        for 250 m on a geographic grid).
    tension
        GMT ``surface`` tension factor in [0, 1] (default 0.35).
    mask_km
        Coverage mask: cells farther than this many km (great-circle) from any
        sounding are set to NaN, so the grid is not extrapolated over land / data
        gaps. ``None`` disables it.
    blockmedian
        Pre-decimate to one median sounding per cell (recommended).

    Returns
    -------
    xarray.DataArray
        The DEM grid (dims ``lat``/``y``, ``lon``/``x``), NaN outside coverage.
    """
    import pygmt

    lon_a = np.asarray(lon, dtype=np.float64)
    lat_a = np.asarray(lat, dtype=np.float64)
    z_a = np.asarray(z, dtype=np.float64)
    good = np.isfinite(lon_a) & np.isfinite(lat_a) & np.isfinite(z_a)
    pts = pd.DataFrame({"x": lon_a[good], "y": lat_a[good], "z": z_a[good]})
    if pts.empty:
        raise ValueError("no finite (lon, lat, z) soundings to grid")

    reg = list(region)
    # coltypes="g": treat the columns as geographic (lon/lat) so GMT uses
    # geographic distances for the tension spline and the grid carries lon/lat.
    table = (
        pygmt.blockmedian(data=pts, region=reg, spacing=spacing, coltypes="g")
        if blockmedian
        else pts
    )
    grid = pygmt.surface(
        data=table, region=reg, spacing=spacing, tension=tension, coltypes="g"
    )

    if mask_km is not None:
        grid = grid.where(
            _coverage(grid, pts["x"].to_numpy(), pts["y"].to_numpy()) <= mask_km
        )

    grid.name = "elevation"
    return cast("xr.DataArray", grid)


def _coverage(
    grid: "xr.DataArray", slon: np.ndarray, slat: np.ndarray
) -> "xr.DataArray":
    """Great-circle distance (km) from each grid node to its nearest sounding."""
    from scipy.spatial import cKDTree

    from topobathy.utils.geo import local_enu_km

    dim_y, dim_x = grid.dims
    glon = np.asarray(grid[dim_x].values, dtype=np.float64)
    glat = np.asarray(grid[dim_y].values, dtype=np.float64)
    lat0 = float(glat.mean())
    tree = cKDTree(np.column_stack(local_enu_km(slon, slat, lat0)))
    mesh_lon, mesh_lat = np.meshgrid(glon, glat)
    qx, qy = local_enu_km(mesh_lon.ravel(), mesh_lat.ravel(), lat0)
    dist, _ = tree.query(np.column_stack([qx, qy]), k=1)
    return grid.copy(data=dist.reshape(mesh_lat.shape))
