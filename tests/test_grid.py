"""Tests for the DEM gridding (splines in tension via GMT)."""

from __future__ import annotations

import numpy as np
import pytest

pytest.importorskip("pygmt")  # GMT is an optional (heavy) dependency

from topobathy.grid import grid_dem  # noqa: E402


def _synthetic():
    # a smooth bowl over Tokyo Bay coords, sampled at scattered points
    rng = np.random.default_rng(0)
    lon = 139.6 + 0.6 * rng.random(400)
    lat = 35.0 + 0.6 * rng.random(400)
    z = -((lon - 139.9) ** 2 + (lat - 35.3) ** 2) * 300.0  # bowl, seabed negative
    return lon, lat, z


def test_grid_dem_shape_and_geographic_coords() -> None:
    lon, lat, z = _synthetic()
    dem = grid_dem(
        lon, lat, z, region=(139.6, 140.2, 35.0, 35.6), spacing=0.02, mask_km=10.0
    )
    # geographic grid: lat/lon coords
    assert set(dem.dims) == {"lat", "lon"}
    assert dem.sizes["lon"] > 5 and dem.sizes["lat"] > 5


def test_grid_dem_recovers_smooth_field() -> None:
    lon, lat, z = _synthetic()
    dem = grid_dem(
        lon,
        lat,
        z,
        region=(139.65, 140.15, 35.05, 35.55),
        spacing=0.02,
        tension=0.35,
        mask_km=10.0,
    )
    # sample the analytic field at grid nodes and compare where defined
    LON, LAT = np.meshgrid(dem["lon"].values, dem["lat"].values)
    truth = -((LON - 139.9) ** 2 + (LAT - 35.3) ** 2) * 300.0
    err = np.abs(dem.values - truth)
    finite = np.isfinite(err)
    # a tension spline should recover a smooth bowl to well within its amplitude
    assert np.nanmedian(err[finite]) < 2.0


def test_grid_dem_mask_blanks_far_cells() -> None:
    # two clusters; the empty middle should be masked out
    lon = np.r_[
        139.7 + 0.02 * np.random.default_rng(1).random(50),
        140.1 + 0.02 * np.random.default_rng(2).random(50),
    ]
    lat = np.r_[
        35.5 + 0.02 * np.random.default_rng(3).random(50),
        35.1 + 0.02 * np.random.default_rng(4).random(50),
    ]
    z = -10.0 * np.ones_like(lon)
    dem = grid_dem(
        lon, lat, z, region=(139.6, 140.3, 35.0, 35.6), spacing=0.02, mask_km=3.0
    )
    assert np.isnan(dem.values).any()  # the gap between clusters is blanked


def test_grid_dem_land_geom_clips() -> None:
    from shapely.geometry import box

    lon, lat, z = _synthetic()
    land = box(139.90, 35.15, 140.10, 35.45)  # a land box inside the region
    dem = grid_dem(
        lon,
        lat,
        z,
        region=(139.65, 140.15, 35.05, 35.55),
        spacing=0.02,
        mask_km=50.0,
        land_geom=land,
    )
    LON, LAT = np.meshgrid(dem["lon"].values, dem["lat"].values)
    inside = (LON > 139.92) & (LON < 140.08) & (LAT > 35.17) & (LAT < 35.43)
    west_water = LON < 139.80
    assert np.all(np.isnan(dem.values[inside]))  # land cells blanked
    assert np.isfinite(dem.values[west_water]).any()  # water cells kept
