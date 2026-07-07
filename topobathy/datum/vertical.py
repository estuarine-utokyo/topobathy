"""Vertical-datum conversion: chart datum (基本水準面) -> Tokyo Peil (T.P.).

The J-BIRD marks reference three different vertical data:

* ``N`` — depth-contour point, value = **depth below chart datum** (positive down).
* ``M`` — low-tide line, sitting **at the chart datum** itself (stored value 0).
* ``L`` — coastline at 略最高高潮面 (approx. HHW); its height above T.P. is **not**
  recorded in M7001, so no numeric T.P. elevation can be assigned from this
  dataset alone.

We express the result as a **T.P.-referenced elevation** ``z_tp`` (metres,
**positive up**, i.e. topo-bathy convention: seabed negative). With the local
offset ``z0 = T.P. - chart_datum`` (metres, from :class:`~topobathy.datum.z0.Z0Field`):

* ``N``: the seabed lies ``depth_cd`` below chart datum, i.e. ``depth_cd + z0``
  below T.P., so ``z_tp = -(depth_cd + z0)``.
* ``M``: at chart datum, i.e. ``z0`` below T.P., so ``z_tp = -z0``.
* ``L``: ``z_tp = NaN`` (geometry retained; elevation unknown from M7001).

A T.P.-referenced **depth** (positive down) is simply ``-z_tp``.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from numpy.typing import ArrayLike, NDArray

from topobathy.datum.separation import SeparationModel

__all__ = ["chart_datum_to_tp_elevation", "add_tp_elevation"]


def chart_datum_to_tp_elevation(
    mark: ArrayLike,
    depth_cd: ArrayLike,
    z0: ArrayLike,
) -> NDArray[np.float64]:
    """Convert per-point chart-datum values to T.P. elevation ``z_tp`` (m, +up).

    ``N`` -> ``-(depth_cd + z0)``; ``M`` -> ``-z0``; everything else -> ``NaN``.
    """
    mark_a = np.asarray(mark)
    depth_a = np.asarray(depth_cd, dtype=np.float64)
    z0_a = np.asarray(z0, dtype=np.float64)

    z_tp = np.full(depth_a.shape, np.nan, dtype=np.float64)
    is_n = mark_a == "N"
    is_m = mark_a == "M"
    z_tp[is_n] = -(depth_a[is_n] + z0_a[is_n])
    z_tp[is_m] = -z0_a[is_m]
    return z_tp


def add_tp_elevation(df: pd.DataFrame, model: SeparationModel) -> pd.DataFrame:
    """Return a copy of ``df`` with ``z0`` and ``z_tp`` columns added.

    ``df`` must have ``mark``, ``lon``, ``lat``, ``depth_cd`` columns (the
    canonical :func:`~topobathy.io.jbird.read_jbird` schema). ``z0`` is the
    ``T.P. − 基本水準面`` separation interpolated from the tide-station
    :class:`~topobathy.datum.separation.SeparationModel` at each point; ``z_tp``
    is the T.P. elevation (m, positive up) per :func:`chart_datum_to_tp_elevation`.
    """
    out = df.copy()
    z0 = model.interpolate(out["lon"].to_numpy(), out["lat"].to_numpy())
    out["z0"] = z0
    out["z_tp"] = chart_datum_to_tp_elevation(
        out["mark"].to_numpy(), out["depth_cd"].to_numpy(), z0
    )
    return out
