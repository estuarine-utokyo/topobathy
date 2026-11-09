# Sanbanze (Chiba) multi-year bathymetry — archived data

Gridded depth surveys of Sanbanze from the Sanbanze natural-environment database of Chiba
Prefecture, archived on 2026-11-09 at

`$DATA_DIR/geodata/bathymetry/tokyo_bay/Sanbanze_Chiba_AP/` (data + `README.md` + the original
Japanese `specification.pdf`).

The data are **not** in this repository (licence undocumented: group use only). The repository
tracks this note and the checksums `docs/sanbanze_chiba_ap.sha256`
(`cd` to the data directory, then `sha256sum -c <repo>/docs/sanbanze_chiba_ap.sha256`).

## Format (from `specification.pdf`, checked against the files)

- CSV with header `X,Y,Z`; one point per row; no processing was applied (only CR+LF → LF).
- **X column = zone-IX easting, Y column = zone-IX northing** (the specification calls them
  "Y" and "X" of the plane rectangular system), metres. Sanbanze is at easting ≈ +7 to +16 km,
  northing ≈ −47 to −35 km.
- Z = depth in **A.P.** (m, negative below A.P.). A.P. ≈ T.P. − 1.134 m in Tokyo Bay
  (see `vertical_datum.md`; convert before merging with T.P. data).
- Grid origins: 10 m mesh (easting 7686.70, northing −40674.20); 100 m mesh (5706.70, −47144.15).
- File name `<mesh><S|H><yy>JGD.csv`; S55=1980, S61=1986, H03=1991, H12=2000, H14=2002,
  H20=2008, H24=2012, H28=2016.

## Inventory (points; extent in easting / northing, km; Z range, m A.P.)

| file | n | easting | northing | Z |
|---|---|---|---|---|
| 10mS55 | 157 271 | 7.7–13.6 | −40.7 – −36.3 | −19.36 … 1.66 |
| 10mS61 | 157 270 | 7.7–13.6 | −40.7 – −36.3 | −11.60 … 3.00 |
| 10mH03 | 157 290 | 7.7–13.6 | −40.7 – −36.3 | −8.72 … 9999 (20 flags) |
| 10mH12 | 157 271 | 7.7–13.6 | −40.7 – −36.3 | −8.78 … 2.86 |
| 10mH14 | 157 290 | 7.7–13.6 | −40.7 – −36.3 | −8.74 … 9999 (23 flags) |
| 10mH20 | 234 277 | 7.7–14.6 | −40.7 – −35.1 | −15.01 … 3.54 |
| 10mH24 | 238 217 | 7.7–14.6 | −40.7 – −35.1 | −15.12 … 4.73 |
| 10mH28 | 149 018 | 7.8–13.5 | −40.5 – −36.8 | −7.87 … 0.33 |
| 100mS55 | 5 409 | 5.7–16.0 | −45.9 – −36.0 | −28.20 … 1.65 |
| 100mS61 | 2 693 | 7.3–14.0 | −41.0 – −35.8 | −16.90 … 3.10 |
| 100mH03 | 4 239 | 7.7–15.4 | −47.1 – −35.0 | −16.40 … 2.88 |
| 100mH12 | 2 385 | 7.7–14.0 | −41.0 – −35.8 | −15.50 … 2.86 |
| 100mH14 | 2 929 | 7.7–14.9 | −41.7 – −35.0 | −15.99 … 2.83 |
| 100mH20 | 2 829 | 7.7–14.7 | −41.8 – −35.1 | −15.50 … 2.71 |
| 100mH24 | 2 968 | 7.7–14.7 | −41.5 – −35.1 | −15.22 … 4.14 |
| 100mH28 | 1 513 | 7.8–13.5 | −40.4 – −36.8 | −7.76 … 0.29 |

## Caveats

- `Z = 9999.00` is an undocumented missing-value flag (10mH03, 10mH14); drop `Z >= 9000`.
- Some files (e.g. H28) have spaces before the commas; parse with whitespace stripped.
- "世界測地系" is not resolved to JGD2000 or JGD2011. The two differ by tens of cm in this area
  after 2011; irrelevant at 10–100 m grid spacing, but ask Chiba before using it at finer scale.
- No code in this repository reads these files yet. A gridding / T.P. conversion step should be
  added as a script before the data enter a DEM.
