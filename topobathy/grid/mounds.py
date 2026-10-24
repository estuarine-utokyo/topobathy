"""Find seabed mounds on a lon/lat depth grid by topographic prominence.

A mound is a local summit of the seabed (a local minimum of depth). Its height above
the surrounding seabed is the topographic *prominence*: the summit elevation minus the
highest saddle (col) through which it connects to higher terrain (another, higher
summit or the shore). This is computed exactly with one union-find sweep over the cells
sorted from shallow to deep; land and no-data cells are treated as the highest terrain,
so a mound on a slope rising to the shore is measured against the col towards the shore.

Mounds are kept when

* the summit depth is in [zmin, zmax],
* the prominence is at least ``min_prominence``,
* the summit lies within ``max_shore_dist`` (m) of land,
* (optional) the width at half height and the flank slope are in range.

Size and steepness are measured on the upper half of the mound: the cells connected to
the summit that lie above summit - prominence / 2. Their area gives the equivalent-circle
diameter ``width`` (full width at half height), and the mean flank slope over that upper
half is ``slope = (prominence / 2) / (width / 2)``. (The base above the col is not used:
on a flat surrounding seabed it spreads over the whole flat.) A minimum slope rejects
broad, gentle swells, keeping mounds that stand out from the surrounding seabed.

Typical use (depth +down, NaN = land / no data)::

    from topobathy.grid.mounds import find_mounds
    tab = find_mounds(depth, lon, lat, zmin=7, zmax=14, min_prominence=1, max_shore_dist=2000)
"""

from __future__ import annotations

import numpy as np

__all__ = ["find_mounds"]

_LAND = 1.0e6  # elevation given to land / no-data cells (higher than any seabed)


def _cell_size_m(lon: np.ndarray, lat: np.ndarray) -> tuple[float, float]:
    lat0 = np.radians(float(np.mean(lat)))
    dx = float(np.mean(np.abs(np.diff(lon)))) * 111_320.0 * np.cos(lat0)
    dy = float(np.mean(np.abs(np.diff(lat)))) * 111_320.0
    return dx, dy


def _prominence(elev: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (peak_index, prominence) for every local summit of ``elev`` (2-D, finite).

    Union-find over cells in descending elevation, 8-connected. When two components
    meet at a cell, the component with the lower summit ends there: its prominence is
    summit - cell elevation. The highest summit gets prominence = inf.
    """
    ny, nx = elev.shape
    flat = elev.ravel()
    order = np.argsort(-flat, kind="stable")
    parent = -np.ones(flat.size, dtype=np.int64)  # -1 = not yet processed
    peak = np.zeros(flat.size, dtype=np.int64)    # root -> summit cell

    def find(i: int) -> int:
        root = i
        while parent[root] != root:
            root = parent[root]
        while parent[i] != root:  # path compression
            parent[i], i = root, parent[i]
        return root

    peaks, proms = [], []
    nbrs = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
    for c in order:
        cy, cx = divmod(int(c), nx)
        roots = set()
        for oy, ox in nbrs:
            y, x = cy + oy, cx + ox
            if 0 <= y < ny and 0 <= x < nx:
                j = y * nx + x
                if parent[j] >= 0:
                    roots.add(find(j))
        parent[c] = c
        if not roots:  # new summit
            peak[c] = c
            continue
        roots = sorted(roots, key=lambda r: flat[peak[r]], reverse=True)
        top = roots[0]
        for r in roots[1:]:  # lower summits end at this col
            peaks.append(peak[r])
            proms.append(flat[peak[r]] - flat[c])
            parent[r] = top
        parent[c] = top
    # remaining roots: highest summits (prominence = inf)
    for c in range(flat.size):
        if parent[c] == c:
            peaks.append(peak[c])
            proms.append(np.inf)
    return np.asarray(peaks), np.asarray(proms)


def find_mounds(depth: np.ndarray, lon: np.ndarray, lat: np.ndarray, *, zmin: float,
                zmax: float, min_prominence: float, max_shore_dist: float,
                min_slope: float = 0.0, width_range: tuple[float, float] | None = None
                ) -> list[dict]:
    """Mounds on ``depth`` (2-D, lat x lon, m +down; NaN or <= 0 = land / no data).

    Returns a list of dicts (lon, lat, depth, prominence, width, slope, shore_dist),
    highest prominence first. ``max_shore_dist`` and ``width_range`` (full width at half
    height) in metres; ``min_slope`` = minimum mean flank slope of the upper half (m/m).
    """
    # jsasaki 2026-10-24: owner: width / slope filters (sandy mound tops in mud)
    from scipy.ndimage import distance_transform_edt, label

    depth = np.asarray(depth, dtype=float)
    land = ~np.isfinite(depth) | (depth <= 0.0)
    elev = np.where(land, _LAND, -depth)
    dx, dy = _cell_size_m(lon, lat)
    shore = distance_transform_edt(~land, sampling=(dy, dx))

    pk, pr = _prominence(elev)
    iy, ix = np.unravel_index(pk, depth.shape)
    out = []
    for y, x, p in zip(iy, ix, pr):
        if land[y, x] or not np.isfinite(p):
            continue
        z = depth[y, x]
        #---> jsasaki 2026-10-24: width at half height and upper-half flank slope
        if not (zmin <= z <= zmax and p >= min_prominence and shore[y, x] <= max_shore_dist):
            continue
        upper, _ = label(~land & (elev >= elev[y, x] - p / 2.0),
                         structure=np.ones((3, 3), dtype=bool))
        ncell = int((upper == upper[y, x]).sum())
        width = 2.0 * np.sqrt(ncell * dx * dy / np.pi)
        slope = (p / 2.0) / (width / 2.0)
        if slope < min_slope:
            continue
        if width_range is not None and not (width_range[0] <= width <= width_range[1]):
            continue
        out.append({"lon": float(lon[x]), "lat": float(lat[y]), "depth": float(z),
                    "prominence": float(p), "width": float(width), "slope": float(slope),
                    "shore_dist": float(shore[y, x])})
        #<--- jsasaki 2026-10-24
    out.sort(key=lambda d: -d["prominence"])
    return out
