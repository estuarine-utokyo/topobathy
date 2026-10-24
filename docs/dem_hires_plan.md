# High-resolution (10 m / 5 m) Tokyo Bay DEM — feasibility and plan

Status: **plan** (2026-10-24). Goal: a new DEM on the window of the 50 m DEM
(139.50–140.35 E, 34.85–35.80 N) at 10 m or 5 m, built **from the original data**, not by
resampling the 50 m grid.

## Sources (owner decisions 2026-10-24)

| source | use |
|---|---|
| M7001 (JHA chart soundings → T.P.) | everywhere — the base |
| Fisheries Agency 2022 Futtsu survey (0.5 m, T.P.) | inside its footprint |
| Endo (2020) 50 m grid | **Chiba channel cross-section only** (floor depth, half-width) |
| Cabinet Office tsunami topography | **not used** — does not resolve the Chiba channel and is out of date |
| OSM coastline (xcoast) | hydro-flattening (land = NaN) |

## Measurements (`scripts/hires_dem_feasibility.py`, job 7167276)

M7001 in the window: 688 523 points — 604 443 `N` (digitised depth contours), 28 077 `M`
(low-tide line), 56 003 `L` (coastline, no depth, not gridded).

| | value |
|---|---|
| nearest-neighbour spacing of `N`+`M` points | p5 3.8 m, p25 12.8 m, **median 26.9 m**, p75 44.3 m, p95 80.3 m |
| median spacing by depth | 0–5 m: 12.4 m; 5–10 m: 13.6 m; 10–20 m: 14.4 m; 20–50 m: 19.0 m; > 50 m: 38.8 m |
| wet cells holding ≥ 1 point | **10 m: 1.8 %** (595 451 of ~33.0 M); **5 m: 0.47 %** (618 815 of ~132 M) |

The points are dense **along** the contours (≈ 13–27 m) but the contours themselves are
far apart, so almost every 10 m cell and practically every 5 m cell is interpolated. A
finer grid follows the contour shapes more faithfully (bends, narrow features) down to
about the along-contour spacing, i.e. **≈ 10–25 m**; it adds no new information below
that, except where the Futtsu survey (0.5 m) exists.

Pilot gridding (same method as the 50 m DEM: GMT `blockmedian` + `surface`, tension
0.35, 2 km coverage mask, OSM hydro-flattening) on a 0.1° × 0.1° tile off Ichihara:

| spacing | tile grid | wall time | peak memory | whole window (×81 by area, serial) |
|---|---|---|---|---|
| 0.0001° (≈ 9 × 11 m) | 1001 × 1001 | 15 s | 0.6 GB | ≈ 0.3 h |
| 0.00005° (≈ 4.5 × 5.6 m) | 2001 × 2001 | 57 s | 0.8 GB | ≈ 1.3 h |

Cost is not a constraint at either spacing (one job, or tiles in parallel).

| spacing | grid | cells | float32, uncompressed | compressed (estimate) |
|---|---|---|---|---|
| 0.0001° | 8501 × 9501 | 80.8 M | 323 MB | ≈ 80–150 MB |
| 0.00005° | 17 001 × 19 001 | 323 M | 1.29 GB | ≈ 0.3–0.6 GB |

## Recommendation

**0.0001° (≈ 10 m) for the whole window.** It matches the along-contour sounding spacing
(median 14 m shallower than 20 m), keeps the file near 100 MB, and the Futtsu survey still
contributes ≈ 400 nodes per cell. 5 m would quadruple the size for interpolation only,
except at Futtsu; if 5 m is needed there, it is better made as a separate Futtsu-only
product directly from the 0.5 m survey.

## Build plan (each step a job; the 50 m chain is the template)

1. **M7001 base at 0.0001°** — `topobathy-m7001-dem --spacing 0.0001 --tension 0.35
   --mask-km 2.0` over the window (or 4–8 overlapping tiles in parallel, then mosaicked
   with the overlap trimmed). Check tension: at 10 m the spline is evaluated much closer
   to the contours, so overshoot between them must be checked (same test as for 50 m).
2. **Chiba channel** — the same two steps as at 50 m (harmonic refill of the flats within
   900 m of the axis, then the straight channel cut), at 10 m. The floor depth (18.98 m
   below T.P.) and floor half-width (175 m) come from the Endo grid. **Open question:**
   the side slope 1:25 is what the 50 m Endo grid shows, i.e. smoothed by its 50 m cells;
   the real dredged slope is probably steeper, and a 10 m grid would show the difference.
   It needs a value from a source (the channel's dredging design) or an owner decision.
3. **Futtsu** — block-median the 0.5 m survey to 0.0001° (cells ≥ 50 % covered), merge
   inside its footprint with an edge ramp (250 m at 50 m; narrower at 10 m, e.g. 100 m),
   water cells only, no datum shift (both T.P.).
4. **Checks** — the 10 m DEM block-averaged to 50 m vs the 50 m DEM (should agree on flat
   seabed; differences only where the finer grid resolves shape), maps before/after at
   the Chiba channel and Futtsu, overshoot statistics.
5. **Products** — `$DATA_DIR/geodata/bathymetry/M7001/TP/M7001_dem_tokyobay_10m.nc` (and the
   stages `_m7001_only`, `_chiba_channel`, as at 50 m), a README beside them, and a
   section in [`dem.md`](dem.md).
