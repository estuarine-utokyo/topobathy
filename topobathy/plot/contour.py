"""Grid scattered points and draw filled-contour maps (matplotlib).

Reusable helpers for turning a scattered point dataset (lon, lat, value) into a
gridded field and a filled-contour map. Uses ``scipy.interpolate.griddata``
(linear, within the convex hull only — no extrapolation) plus an optional
nearest-neighbour distance mask that blanks grid cells farther than a threshold
from any data point (so land / data gaps stay empty rather than being bridged).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.interpolate import griddata
from scipy.spatial import cKDTree

from topobathy.utils.geo import local_enu_km

__all__ = ["GriddedField", "grid_scatter"]


@dataclass(frozen=True)
class GriddedField:
    """A regular lon/lat grid of an interpolated scalar (masked outside data)."""

    lon: NDArray[np.float64]  # 1-D grid longitudes
    lat: NDArray[np.float64]  # 1-D grid latitudes
    values: NDArray[np.float64]  # 2-D (nlat, nlon), NaN where masked


def grid_scatter(
    lon: ArrayLike,
    lat: ArrayLike,
    val: ArrayLike,
    bbox: tuple[float, float, float, float],
    nlon: int = 400,
    nlat: int = 400,
    mask_km: float | None = 2.0,
    method: str = "linear",
) -> GriddedField:
    """Interpolate scattered ``(lon, lat, val)`` onto a regular grid over ``bbox``.

    Parameters
    ----------
    bbox
        ``(lon_min, lon_max, lat_min, lat_max)`` grid extent (degrees).
    nlon, nlat
        Grid size.
    mask_km
        Blank grid cells whose nearest data point is farther than this many km
        (``None`` disables the mask).
    method
        ``griddata`` method (``"linear"`` recommended; no hull extrapolation).
    """
    lon_a = np.asarray(lon, dtype=np.float64)
    lat_a = np.asarray(lat, dtype=np.float64)
    val_a = np.asarray(val, dtype=np.float64)

    lon_min, lon_max, lat_min, lat_max = bbox
    glon = np.linspace(lon_min, lon_max, nlon)
    glat = np.linspace(lat_min, lat_max, nlat)
    mesh_lon, mesh_lat = np.meshgrid(glon, glat)

    grid = griddata(
        np.column_stack([lon_a, lat_a]),
        val_a,
        (mesh_lon, mesh_lat),
        method=method,
    )

    if mask_km is not None:
        lat0 = float(np.mean(lat_a))
        sx, sy = local_enu_km(lon_a, lat_a, lat0)
        tree = cKDTree(np.column_stack([sx, sy]))
        qx, qy = local_enu_km(mesh_lon.ravel(), mesh_lat.ravel(), lat0)
        dist, _ = tree.query(np.column_stack([qx, qy]), k=1)
        grid.ravel()[dist > mask_km] = np.nan

    return GriddedField(lon=glon, lat=glat, values=grid)
