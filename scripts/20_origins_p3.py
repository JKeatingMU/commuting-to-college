"""Phase 3 origins: Electoral Divisions across the expanded 15-area study region
(Dublin + Kildare/Meath/Wicklow + Westmeath/Longford/Offaly/Laois + Louth/Monaghan
+ Carlow/Kilkenny). Population-weighted centroids from Small Areas, 17-19 cohort.

Output: data/processed/origins_p3.gpkg / .csv
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd

import config as C

WGS84 = "EPSG:4326"
COHORT_COLS = [f"T1_1AGE{a}T" for a in C.COHORT_AGES]
PROXY_COLS = [f"T1_1AGE{a}T" for a in C.COHORT_PROXY_AGES]


def main() -> None:
    print("reading Small Area boundaries ...")
    sa = gpd.read_file(
        C.SA_GEOJSON,
        columns=["SA_GEOGID_2022", "ED_ID_STR", "ED_ENGLISH", "COUNTY_ENGLISH"],
    ).to_crs(2157)
    sa = sa[sa["COUNTY_ENGLISH"].isin(C.P3_SA_COUNTIES)].copy()
    sa["pt"] = sa.geometry.representative_point()
    sa["sa_id"] = sa["SA_GEOGID_2022"].astype(str).str.lstrip("A")
    print(f"  {len(sa)} SAs, {sa['ED_ID_STR'].nunique()} EDs, "
          f"{sa['COUNTY_ENGLISH'].nunique()} counties")

    saps = pd.read_csv(C.SAPS_SA, encoding="latin-1", usecols=["GEOGID", "T1_1AGETT", *sorted(set(COHORT_COLS + PROXY_COLS))])
    saps["sa_id"] = saps["GEOGID"].astype(str).str.strip()
    saps["sa_pop"] = saps["T1_1AGETT"].astype(int)
    saps["sa_cohort"] = saps[COHORT_COLS].sum(axis=1).astype(int)
    saps["sa_proxy"] = saps[PROXY_COLS].sum(axis=1).astype(int)

    sa = sa.merge(saps[["sa_id", "sa_pop", "sa_cohort", "sa_proxy"]], on="sa_id", how="left")
    print(f"  SA population join matched {sa['sa_pop'].notna().mean():.0%}")
    sa[["sa_pop", "sa_cohort", "sa_proxy"]] = sa[["sa_pop", "sa_cohort", "sa_proxy"]].fillna(0)
    w = sa["sa_pop"].clip(lower=1)
    sa["xw"], sa["yw"], sa["w"] = sa["pt"].x * w, sa["pt"].y * w, w

    g = sa.groupby("ED_ID_STR").agg(
        name=("ED_ENGLISH", "first"), county=("COUNTY_ENGLISH", "first"),
        pop=("sa_pop", "sum"), cohort_census=("sa_cohort", "sum"), proxy=("sa_proxy", "sum"),
        n_sa=("sa_pop", "size"),
        xw=("xw", "sum"), yw=("yw", "sum"), w=("w", "sum"),
    ).reset_index()
    g["cx"], g["cy"] = g["xw"] / g["w"], g["yw"] / g["w"]

    before = len(g)
    g = g[g["pop"] >= C.ED_POP_FLOOR].copy()
    # home-based weight: 15-17 year olds rescaled to the 17-19 census total (see config.COHORT_PROXY_AGES)
    k = g["cohort_census"].sum() / g["proxy"].sum()
    # largest-remainder rounding, so the weights sum exactly to the census total
    raw = g["proxy"] * k
    base = raw.astype(int)
    short = int(round(g["cohort_census"].sum())) - int(base.sum())
    base[(raw - base).sort_values(ascending=False).index[:short]] += 1
    g["cohort_17_19"] = base
    moved = (g["cohort_17_19"] - g["cohort_census"]).abs().sum() / 2 / g["cohort_census"].sum()
    print(f"  cohort weights: 15-17 x {k:.3f}; {moved:.1%} of the census 17-19 weight relocated")
    print(f"{len(g)}/{before} EDs at pop >= {C.ED_POP_FLOOR}  "
          f"(total pop {int(g['pop'].sum()):,}, cohort 17-19 {int(g['cohort_17_19'].sum()):,})")

    pts = gpd.GeoDataFrame(g.drop(columns=["xw", "yw", "w"]),
                           geometry=gpd.points_from_xy(g["cx"], g["cy"]), crs=2157).to_crs(WGS84)
    pts["lon"], pts["lat"] = pts.geometry.x, pts.geometry.y
    pts["ed_id"] = pts["ED_ID_STR"]
    pts["id"] = pts["ED_ID_STR"]
    pts["name"] = pts["name"].str.title()
    pts["county"] = pts["county"].str.title().replace(
        {"Dun Laoghaire/Rathdown": "Dún Laoghaire-Rathdown"})

    out = pts[["ed_id", "id", "name", "county", "pop", "cohort_17_19", "cohort_census", "n_sa",
               "lon", "lat", "geometry"]]
    out.sort_values("pop", ascending=False).to_file(C.PROC / "origins_p3.gpkg", driver="GPKG")
    out.drop(columns="geometry").sort_values("pop", ascending=False).to_csv(
        C.PROC / "origins_p3.csv", index=False)

    print("\nby county:")
    print(out.groupby("county").agg(EDs=("ed_id", "size"), pop=("pop", "sum"),
                                    cohort=("cohort_17_19", "sum")).sort_values("cohort", ascending=False).to_string())


if __name__ == "__main__":
    main()
