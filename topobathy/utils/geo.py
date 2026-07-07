"""Small geospatial helpers shared across topobathy tools."""

from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = ["EARTH_RADIUS_KM", "local_enu_km", "great_circle_km"]

EARTH_RADIUS_KM = 6371.0


def local_enu_km(
    lon: ArrayLike,
    lat: ArrayLike,
    lat0_deg: float,
) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    """Project lon/lat (degrees) to a local equirectangular ENU plane in km.

    Cheap, accurate enough for the ~100 km Tokyo Bay extent used for
    inverse-distance interpolation. ``lat0_deg`` is the reference latitude used
    for the east-west metric (typically the mean latitude of the query points).
    """
    lon_a = np.asarray(lon, dtype=np.float64)
    lat_a = np.asarray(lat, dtype=np.float64)
    coslat0 = np.cos(np.radians(lat0_deg))
    x = EARTH_RADIUS_KM * np.radians(lon_a) * coslat0
    y = EARTH_RADIUS_KM * np.radians(lat_a)
    return x, y


def great_circle_km(
    lon1: ArrayLike,
    lat1: ArrayLike,
    lon2: ArrayLike,
    lat2: ArrayLike,
) -> NDArray[np.float64]:
    """Haversine great-circle distance (km) between two lon/lat sets (degrees)."""
    lon1_r = np.radians(np.asarray(lon1, dtype=np.float64))
    lat1_r = np.radians(np.asarray(lat1, dtype=np.float64))
    lon2_r = np.radians(np.asarray(lon2, dtype=np.float64))
    lat2_r = np.radians(np.asarray(lat2, dtype=np.float64))
    dlon = lon2_r - lon1_r
    dlat = lat2_r - lat1_r
    a = (
        np.sin(dlat / 2.0) ** 2
        + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2.0) ** 2
    )
    dist: NDArray[np.float64] = 2.0 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(a))
    return dist
