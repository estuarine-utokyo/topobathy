"""Tests for the separation model and chart-datum -> T.P. vertical conversion."""

from __future__ import annotations

import numpy as np
import pandas as pd

from topobathy import config
from topobathy.datum import (
    GeoidModel,
    SeparationModel,
    add_tp_elevation,
    chart_datum_to_tp_elevation,
)


def _toy_model(method: str = "idw") -> SeparationModel:
    return SeparationModel(
        lon=np.array([139.0, 140.0]),
        lat=np.array([35.0, 35.0]),
        tp_minus_cd=np.array([1.0, 2.0]),
        names=("west", "east"),
        power=2.0,
        method=method,  # type: ignore[arg-type]
    )


def test_z0_exact_at_gauge() -> None:
    f = _toy_model()
    z0 = f.interpolate([139.0, 140.0], [35.0, 35.0])
    assert np.allclose(z0, [1.0, 2.0])


def test_z0_midpoint_between_gauges() -> None:
    f = _toy_model()
    # equidistant midpoint -> equal IDW weights -> mean of the two gauge values
    z0 = f.interpolate([139.5], [35.0])
    assert np.isclose(z0[0], 1.5, atol=1e-6)


def test_z0_within_gauge_range() -> None:
    f = _toy_model()
    z0 = f.interpolate([139.25, 139.75], [35.0, 35.0])
    assert np.all((z0 >= 1.0) & (z0 <= 2.0))


def test_chart_datum_elevation_is_negative_offset() -> None:
    f = _toy_model()
    h = f.chart_datum_elevation([139.0], [35.0])
    assert np.isclose(h[0], -1.0)  # chart datum lies 1 m below T.P.


def test_depth_to_tp() -> None:
    f = _toy_model()
    assert np.isclose(f.depth_to_tp([10.0], [140.0], [35.0])[0], 12.0)


def test_grid_shape_and_values() -> None:
    f = _toy_model()
    lon_c, lat_c, g = f.grid((139.0, 140.0, 35.0, 35.0), dlon=0.5, dlat=1.0)
    assert g.shape == (lat_c.size, lon_c.size)
    assert np.isclose(g[0, 0], 1.0) and np.isclose(g[0, -1], 2.0)


def test_linear_and_tps_methods_run() -> None:
    f = _toy_model()
    q = ([139.3, 139.7], [35.0, 35.0])
    for m in ("linear", "tps"):
        v = f.interpolate(*q, method=m)  # type: ignore[arg-type]
        assert v.shape == (2,) and np.all(np.isfinite(v))


def test_vertical_conversion_per_mark() -> None:
    mark = np.array(["N", "M", "L"])
    depth_cd = np.array([10.0, 0.0, 0.0])
    z0 = np.array([1.5, 1.5, 1.5])
    z_tp = chart_datum_to_tp_elevation(mark, depth_cd, z0)
    assert np.isclose(z_tp[0], -(10.0 + 1.5))  # N: seabed below T.P.
    assert np.isclose(z_tp[1], -1.5)  # M: at chart datum
    assert np.isnan(z_tp[2])  # L: unknown HHW height


def test_add_tp_elevation_columns() -> None:
    df = pd.DataFrame(
        {
            "mark": ["N", "M"],
            "lon": [139.5, 139.5],
            "lat": [35.0, 35.0],
            "depth_cd": [5.0, 0.0],
        }
    )
    out = add_tp_elevation(df, _toy_model())
    assert {"z0", "z_tp"} <= set(out.columns)
    assert np.isclose(out.loc[0, "z_tp"], -(5.0 + out.loc[0, "z0"]))
    assert np.isclose(out.loc[1, "z_tp"], -out.loc[1, "z0"])


def test_bundled_datum_table_loads() -> None:
    f = SeparationModel.from_csv(config.default_z0_table())
    assert len(f.lon) >= 80  # Kanto-South ports from the JCG 一覧表 + JMA anchors
    # T.P. - chart datum: ~0.56 m (Izu Islands) to ~1.17 m (inner Tokyo Bay)
    assert 0.5 < f.tp_minus_cd.min() and f.tp_minus_cd.max() < 1.25
    # inner Tokyo Bay (Tokyo/Chiba) must be near ~1.15 m, NOT the old ~1.9 m
    tokyo = f.interpolate([139.77], [35.66])[0]
    assert 1.0 < tokyo < 1.3


def test_nationwide_jcg_table_present() -> None:
    from importlib import resources

    csv_path = resources.files("topobathy.data") / "japan_tide_datums_jcg.csv"
    f = SeparationModel.from_csv(str(csv_path))
    assert len(f.lon) > 500  # ~1000 gazetted ports nationwide
    assert 0.0 < f.tp_minus_cd.min() and f.tp_minus_cd.max() < 3.0


def test_cross_validation_is_small() -> None:
    f = SeparationModel.from_csv(config.default_z0_table(), method="linear")
    cv = f.cross_validate()
    assert cv.n >= 80
    # leave-one-out interpolation error should be well below the ~1 m signal
    assert 0.0 < cv.rms < 0.15 and np.isfinite(cv.max_abs)


def test_geoid_loader_and_bilinear(tmp_path) -> None:  # type: ignore[no-untyped-def]
    # tiny 2x3 GSIGEO-style ASC: header then lat S->N, lon W->E
    asc = tmp_path / "geoid.asc"
    asc.write_text(
        "35.000000 139.000000 1.000000 1.000000 2 3 1 test\n"
        "36.0 36.5 37.0\n"
        "38.0 38.5 39.0\n"
    )
    g = GeoidModel.from_gsigeo_asc(asc)
    assert g.grid.shape == (2, 3)
    # exact node (row 0 = south edge lat 35, col 0 = west edge lon 139)
    assert np.isclose(g.height([139.0], [35.0])[0], 36.0)
    # bilinear centre of the SW cell
    assert np.isclose(g.height([139.5], [35.5])[0], (36.0 + 36.5 + 38.0 + 38.5) / 4)
    # outside grid -> NaN
    assert np.isnan(g.height([150.0], [35.0])[0])
