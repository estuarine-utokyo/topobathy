"""GSI geoid model loader (「日本のジオイド2011」 GSIGEO2011 ASCII grid).

Provides the geoid height ``N`` (geoid above the WGS84/GRS80 ellipsoid) so the
:class:`~topobathy.datum.separation.SeparationModel` can express the chart datum
as an **ellipsoidal** height (for GNSS / ellipsoidally-referenced surveys):

    楕円体高 = 標高 (T.P.) + N        (標高 zero surface ≈ geoid)

The GSIGEO2011 grid is distributed by GSI (国土地理院) as ``gsigeo2011_ver2_x.asc``.
It is **not** bundled here; download it once (direct, no login) with
``scripts/get_gsigeo.py`` → ``$DATA_DIR/geoid/``. This loader parses the standard
ASCII format:

    header:  glamn glomn dgla dglo nla nlo [kind] [version]
             (S-edge lat, W-edge lon, dlat, dlon in deg; #lat, #lon points)
    body:    nla*nlo geoid heights (m), latitude S->N (outer), lon W->E (inner);
             missing value 999.xxxx.

Whitespace tokenisation is used for the body, so the values-per-line count does
not matter.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import ArrayLike, NDArray

__all__ = ["GeoidModel"]

_MISSING = 900.0  # GSIGEO uses 999.0000 for no-data; treat >= this as NaN


@dataclass(frozen=True)
class GeoidModel:
    """Regular lon/lat grid of geoid height ``N`` (m) above the ellipsoid."""

    lat0: float  # south-edge latitude (deg)
    lon0: float  # west-edge longitude (deg)
    dlat: float  # latitude spacing (deg)
    dlon: float  # longitude spacing (deg)
    grid: NDArray[np.float64]  # (nlat, nlon), NaN where missing

    @classmethod
    def from_gsigeo_asc(cls, path: str | Path) -> "GeoidModel":
        """Parse a GSIGEO2011 ``*.asc`` file."""
        text = Path(path).read_text().split()
        lat0, lon0, dlat, dlon = (float(text[i]) for i in range(4))
        nla, nlo = int(text[4]), int(text[5])
        # body starts after the 6 header numbers (+ optional kind/version tokens
        # that are non-numeric or extra ints); take the LAST nla*nlo float tokens.
        n = nla * nlo
        body = np.array(text[-n:], dtype=np.float64)
        if body.size != n:
            raise ValueError(f"{path}: expected {n} geoid values, got {body.size}")
        grid = body.reshape(nla, nlo)
        grid[grid >= _MISSING] = np.nan
        return cls(lat0=lat0, lon0=lon0, dlat=dlat, dlon=dlon, grid=grid)

    def height(self, lon: ArrayLike, lat: ArrayLike) -> NDArray[np.float64]:
        """Bilinearly interpolate geoid height ``N`` (m). NaN outside the grid or
        where any surrounding node is missing."""
        lon_a = np.asarray(lon, dtype=np.float64)
        lat_a = np.asarray(lat, dtype=np.float64)
        nla, nlo = self.grid.shape
        fi = (lat_a - self.lat0) / self.dlat
        fj = (lon_a - self.lon0) / self.dlon
        i0 = np.floor(fi).astype(int)
        j0 = np.floor(fj).astype(int)
        inside = (i0 >= 0) & (i0 < nla - 1) & (j0 >= 0) & (j0 < nlo - 1)
        out = np.full(lon_a.shape, np.nan, dtype=np.float64)
        if not inside.any():
            return out
        ii = i0[inside]
        jj = j0[inside]
        ti = fi[inside] - ii
        tj = fj[inside] - jj
        g = self.grid
        v = (
            g[ii, jj] * (1 - ti) * (1 - tj)
            + g[ii + 1, jj] * ti * (1 - tj)
            + g[ii, jj + 1] * (1 - ti) * tj
            + g[ii + 1, jj + 1] * ti * tj
        )
        out[inside] = v
        return out
