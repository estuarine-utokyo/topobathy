"""Depth map of a sub-region: cmocean colours, xcoast (OSM) land on top.

Takes depth in metres, positive down, either on a lon/lat grid (DataArray with
``lon``/``lat``) or as scattered points (``lon``, ``lat``, ``depth`` arrays, drawn by
triangulation). Land is drawn over the water colours from the OSM land polygons,
so values that fall on land in a coarse source are hidden by the coastline.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np

from topobathy import config

__all__ = ["land_mask", "draw_depth_map"]

Region = tuple[float, float, float, float]  # (W, E, S, N)


def land_mask(region: Region, pad: float = 0.05):
    """xcoast CoastMask over region (+pad so polygons are not cut at the frame)."""
    import xcoast

    conf = xcoast.CoastmaskConfig(
        land_shp_path=config.osm_land_shp(),
        water_shp_path=config.osm_water_shp(),
        cache_dir=config.coastmask_cache_dir(),
        remove_orphan_islands=False,
    )
    w, e, s, n = region
    return xcoast.load((w - pad, s - pad, e + pad, n + pad), config=conf)


def draw_depth_map(region: Region, out: Path, *, grid=None, points=None, vmax: float = 30.0,
                   step: float = 2.0, contour: float = 5.0, contour_labels: bool = False,
                   cmap: str = "deep", title: str = "", source_note: str = "",
                   dpi: int = 300, figsize=(8.0, 6.4)) -> Path:
    """grid: DataArray depth (+down) with lon/lat; points: (lon, lat, depth) arrays."""
    import cmocean
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.tri as mtri

    w, e, s, n = region
    levels = np.arange(0.0, vmax + step / 2, step)
    cl = np.arange(contour, vmax + 0.1, contour) if contour > 0 else None
    cm = getattr(cmocean.cm, cmap)

    fig, ax = plt.subplots(figsize=figsize)
    if grid is not None:
        cf = ax.contourf(grid.lon, grid.lat, grid.clip(min=0), levels=levels, cmap=cm,
                         extend="max")
        cs = (ax.contour(grid.lon, grid.lat, grid, levels=cl, colors="k", linewidths=0.4,
                         alpha=0.5) if cl is not None else None)
    else:
        lon, lat, depth = (np.asarray(a, float) for a in points)
        tri = mtri.Triangulation(lon, lat)
        cf = ax.tricontourf(tri, np.clip(depth, 0, None), levels=levels, cmap=cm, extend="max")
        cs = (ax.tricontour(tri, depth, levels=cl, colors="k", linewidths=0.4, alpha=0.5)
              if cl is not None else None)
    if cs is not None and contour_labels:
        ax.clabel(cs, fmt="%g", fontsize=7, inline_spacing=2)
    land_mask(region).add_to_plain_mpl(ax, facecolor="#d9d6cf", edgecolor="#4a4a4a",
                                       linewidth=0.5, zorder=5)
    ax.set_xlim(w, e)
    ax.set_ylim(s, n)
    ax.set_aspect(1.0 / np.cos(np.radians((s + n) / 2)))
    ax.set_xlabel("Longitude (°E)")
    ax.set_ylabel("Latitude (°N)")
    if title:
        ax.set_title(title, loc="left", fontsize=11)
    cb = fig.colorbar(cf, ax=ax, shrink=0.85, pad=0.02)
    cb.set_label("Depth (m)")
    cb.ax.invert_yaxis()  # deeper downwards
    if source_note:
        # one clause per line, so a long note does not widen the figure
        ax.text(0.0, -0.11, source_note.replace("; ", "\n"), transform=ax.transAxes,
                fontsize=7, color="#52514e", va="top")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    return out
