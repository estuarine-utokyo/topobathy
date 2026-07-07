"""General vertical-datum **separation model** (最低水面モデル) for Japan.

Converts depths/heights between the nautical **chart datum** (基本水準面 ≈ 略最低
低潮面) and the geodetic datums **T.P.** (東京湾平均海面, national 標高 datum) and the
**WGS84 ellipsoid** — anywhere in Japan, following the Japan Coast Guard's
ellipsoidally-referenced-survey (ERS) method (Okubo et al. 2022, Tokyo Bay;
Shiozawa et al. 2023, Report of Hydrographic and Oceanographic Researches No. 61).

The chart datum is a spatially-varying tidal surface. Its height is modelled as a
continuous **separation surface** built from tide-station datums:

    Z0(x, y)   = 平均水面 − 基本水準面           (tidal, from harmonic constants / Z0区分図)
    ζ_MSL(x,y) = 平均水面 の T.P.(≈ジオイド) 上の高さ  (sea-surface topography; small)

    (T.P. − 基本水準面)(x, y) = Z0(x, y) − ζ_MSL(x, y)        # what this model interpolates
    最低水面の標高  H_CD(x, y) = −(T.P. − 基本水準面)          # chart datum in 標高 (T.P.)
    最低水面の楕円体高          = N_geoid(x, y) + H_CD(x, y)   # + GSI geoid (optional, for ERS)

Depth conversion (M7001 etc., chart-datum depth positive-down):

    depth_TP(x, y) = depth_CD(x, y) + (T.P. − 基本水準面)(x, y)
    z_tp           = −depth_TP                                  # elevation, positive up

The model is driven by a **tide-station datum table** (``lon, lat, tp_minus_cd_m``)
and is therefore applicable nationwide — supply stations covering the area of
interest (see ``scripts/fetch_jma_tide_datums.py`` to build one from JMA 潮位表).
This module handles the horizontal interpolation of the separation surface; the
optional ellipsoidal branch uses :class:`topobathy.datum.geoid.GeoidModel`.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Literal

import numpy as np
from numpy.typing import ArrayLike, NDArray

from topobathy.utils.geo import local_enu_km

if TYPE_CHECKING:
    from topobathy.datum.geoid import GeoidModel

__all__ = ["SeparationModel", "CrossValidation", "Z0Field"]

Method = Literal["idw", "linear", "cubic", "tps"]


@dataclass(frozen=True)
class CrossValidation:
    """Leave-one-out interpolation-uncertainty summary (metres)."""

    method: str
    n: int
    rms: float
    mae: float
    max_abs: float
    resid: NDArray[np.float64]

    def __str__(self) -> str:
        return (
            f"leave-one-out CV ({self.method}, n={self.n}): "
            f"RMS {self.rms * 100:.1f} cm, MAE {self.mae * 100:.1f} cm, "
            f"max {self.max_abs * 100:.1f} cm"
        )


@dataclass(frozen=True)
class SeparationModel:
    """Continuous ``T.P. − 基本水準面`` (chart-datum) separation from tide stations.

    Attributes
    ----------
    lon, lat
        Station coordinates (degrees).
    tp_minus_cd
        Station values of ``T.P. − 基本水準面`` (m) — the metres to ADD to a
        chart-datum depth to obtain a T.P.-referenced depth.
    names
        Station identifiers (for reporting).
    power
        IDW exponent (used by ``method="idw"``).
    method
        Default horizontal interpolation: ``"idw"`` (robust, no overshoot; the
        default), ``"linear"``/``"cubic"`` (scipy griddata on a local ENU plane,
        IDW fallback outside the convex hull), or ``"tps"`` (thin-plate-spline
        RBF, smooth — as in continuous-datum literature, but can overshoot for
        sparse/clustered stations).
    """

    lon: NDArray[np.float64]
    lat: NDArray[np.float64]
    tp_minus_cd: NDArray[np.float64]
    names: tuple[str, ...] = field(default_factory=tuple)
    power: float = 2.0
    method: Method = "idw"

    # ------------------------------------------------------------------ I/O ----
    @classmethod
    def from_csv(
        cls,
        path: str | Path,
        power: float = 2.0,
        method: Method = "idw",
        value_column: str = "tp_minus_cd_m",
    ) -> "SeparationModel":
        """Load a tide-station datum CSV (columns ``lon, lat, <value_column>``,
        optional ``station``). Lines starting with ``#`` are comments."""
        lon: list[float] = []
        lat: list[float] = []
        val: list[float] = []
        names: list[str] = []
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(
                row for row in fh if not row.lstrip().startswith("#")
            )
            for row in reader:
                lon.append(float(row["lon"]))
                lat.append(float(row["lat"]))
                val.append(float(row[value_column]))
                names.append(row.get("station", "?"))
        if not lon:
            raise ValueError(f"No station rows parsed from {path}")
        return cls(
            lon=np.asarray(lon, dtype=np.float64),
            lat=np.asarray(lat, dtype=np.float64),
            tp_minus_cd=np.asarray(val, dtype=np.float64),
            names=tuple(names),
            power=power,
            method=method,
        )

    # -------------------------------------------------------- interpolation ----
    def interpolate(
        self, lon: ArrayLike, lat: ArrayLike, method: Method | None = None
    ) -> NDArray[np.float64]:
        """Interpolate ``T.P. − 基本水準面`` (m) onto query points."""
        qlon = np.asarray(lon, dtype=np.float64)
        qlat = np.asarray(lat, dtype=np.float64)
        if qlon.size == 0:
            return np.empty(0, dtype=np.float64)
        m = method or self.method
        lat0 = float(np.mean(qlat))
        sx, sy = local_enu_km(self.lon, self.lat, lat0)
        qx, qy = local_enu_km(qlon, qlat, lat0)
        if m == "idw":
            return self._idw(sx, sy, qx, qy)
        if m in ("linear", "cubic"):
            return self._griddata(sx, sy, qx, qy, m)
        if m == "tps":
            return self._tps(sx, sy, qx, qy)
        raise ValueError(f"unknown interpolation method: {m!r}")

    def _idw(
        self,
        sx: NDArray[np.float64],
        sy: NDArray[np.float64],
        qx: NDArray[np.float64],
        qy: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        d = np.hypot(qx[:, None] - sx[None, :], qy[:, None] - sy[None, :])  # km
        w = 1.0 / np.maximum(d, 1e-9) ** self.power
        out: NDArray[np.float64] = (w * self.tp_minus_cd[None, :]).sum(1) / w.sum(1)
        on = np.isclose(d.min(1), 0.0)
        if on.any():
            out[on] = self.tp_minus_cd[np.argmin(d[on], axis=1)]
        return out

    def _griddata(
        self,
        sx: NDArray[np.float64],
        sy: NDArray[np.float64],
        qx: NDArray[np.float64],
        qy: NDArray[np.float64],
        method: str,
    ) -> NDArray[np.float64]:
        from scipy.interpolate import griddata
        from scipy.spatial import QhullError

        pts = np.column_stack([sx, sy])
        q = np.column_stack([qx, qy])
        try:
            out = griddata(pts, self.tp_minus_cd, q, method=method)
        except QhullError:  # degenerate (collinear / <3 stations) -> IDW
            return self._idw(sx, sy, qx, qy)
        nan = np.isnan(out)
        if nan.any():  # outside the convex hull -> IDW fallback
            out[nan] = self._idw(sx, sy, qx[nan], qy[nan])
        return np.asarray(out, dtype=np.float64)

    def _tps(
        self,
        sx: NDArray[np.float64],
        sy: NDArray[np.float64],
        qx: NDArray[np.float64],
        qy: NDArray[np.float64],
    ) -> NDArray[np.float64]:
        from scipy.interpolate import RBFInterpolator

        try:
            rbf = RBFInterpolator(
                np.column_stack([sx, sy]), self.tp_minus_cd, kernel="thin_plate_spline"
            )
        except ValueError:  # too few stations for the TPS polynomial -> IDW
            return self._idw(sx, sy, qx, qy)
        return np.asarray(rbf(np.column_stack([qx, qy])), dtype=np.float64)

    # ------------------------------------------------------------- products ----
    def chart_datum_elevation(
        self, lon: ArrayLike, lat: ArrayLike, method: Method | None = None
    ) -> NDArray[np.float64]:
        """Height of the chart datum (最低水面) in **T.P. 標高** (m, negative:
        the chart datum lies below T.P.)."""
        return -self.interpolate(lon, lat, method)

    def depth_to_tp(
        self,
        depth_cd: ArrayLike,
        lon: ArrayLike,
        lat: ArrayLike,
        method: Method | None = None,
    ) -> NDArray[np.float64]:
        """Convert a chart-datum depth (m, positive down) to a T.P. depth."""
        return np.asarray(depth_cd, dtype=np.float64) + self.interpolate(
            lon, lat, method
        )

    def chart_datum_ellipsoidal_height(
        self,
        lon: ArrayLike,
        lat: ArrayLike,
        geoid: "GeoidModel",
        method: Method | None = None,
    ) -> NDArray[np.float64]:
        """Ellipsoidal (WGS84) height of the chart datum = ``geoid.N + H_CD``.

        The full ERS separation surface; requires a :class:`GeoidModel`.
        """
        h_tp = self.chart_datum_elevation(lon, lat, method)
        return h_tp + geoid.height(lon, lat)

    def grid(
        self,
        extent: tuple[float, float, float, float],
        dlon: float,
        dlat: float | None = None,
        method: Method | None = None,
    ) -> tuple[NDArray[np.float64], NDArray[np.float64], NDArray[np.float64]]:
        """Sample ``T.P. − 基本水準面`` on a regular lon/lat grid (the "最低水面
        モデル"). Returns ``(lon_centers, lat_centers, field)`` with ``field``
        shape ``(nlat, nlon)``."""
        dlat = dlat if dlat is not None else dlon
        lon_min, lon_max, lat_min, lat_max = extent
        lon_c = np.arange(lon_min, lon_max + 0.5 * dlon, dlon)
        lat_c = np.arange(lat_min, lat_max + 0.5 * dlat, dlat)
        mesh_lon, mesh_lat = np.meshgrid(lon_c, lat_c)
        vals = self.interpolate(mesh_lon.ravel(), mesh_lat.ravel(), method)
        return lon_c, lat_c, vals.reshape(mesh_lat.shape)

    def cross_validate(self, method: Method | None = None) -> CrossValidation:
        """Leave-one-out cross-validation of the interpolation: drop each station,
        predict its value from the rest, and summarise the residuals — an estimate
        of the separation-surface interpolation uncertainty (cf. IHO S-44)."""
        m = method or self.method
        n = len(self.tp_minus_cd)
        resid = np.full(n, np.nan, dtype=np.float64)
        if n >= 3:
            idx = np.arange(n)
            for i in range(n):
                keep = idx != i
                sub = SeparationModel(
                    self.lon[keep],
                    self.lat[keep],
                    self.tp_minus_cd[keep],
                    power=self.power,
                    method=m,
                )
                resid[i] = (
                    sub.interpolate(self.lon[i : i + 1], self.lat[i : i + 1], m)[0]
                    - self.tp_minus_cd[i]
                )
        return CrossValidation(
            method=m,
            n=n,
            rms=float(np.sqrt(np.nanmean(resid**2))),
            mae=float(np.nanmean(np.abs(resid))),
            max_abs=float(np.nanmax(np.abs(resid))),
            resid=resid,
        )

    def report(self, values: NDArray[np.float64] | None = None) -> str:
        """One-line summary of the model (and, if given, the interpolated range)."""
        head = (
            f"SeparationModel: {len(self.tp_minus_cd)} tide stations, "
            f"method={self.method}"
            + (f" (IDW p={self.power})" if self.method == "idw" else "")
            + f"; station T.P.−基本水準面 "
            f"[{self.tp_minus_cd.min():.3f},{self.tp_minus_cd.max():.3f}] m"
        )
        if values is None or values.size == 0:
            return head
        return (
            f"{head}; interpolated [{values.min():.3f}, {values.max():.3f}] "
            f"mean {values.mean():.3f} m"
        )


# Backwards-compatible alias (the model interpolates Z0 = T.P. − chart datum).
Z0Field = SeparationModel
