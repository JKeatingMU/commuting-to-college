"""Phase 4: aggregate the Phase 3 ED-level accessibility up to county of domicile.

For each (county, HEI) it produces the cohort-weighted commute the county's
17-19 cohort faces to reach that HEI (minimum over the HEI's campuses), by car
and by public transport + drive-to-rail, on the peak schedule, plus the
cohort-weighted straight-line distance. County covariates: 17-19 cohort size,
share of adults with a third-level qualification (Census 2022), and a
"county contains a campus of this HEI" flag.

Outputs:
  outputs/p4_county.csv       one row per county
  outputs/p4_county_hei.csv   one row per county x HEI
"""
from __future__ import annotations

import numpy as np
import pandas as pd

import config as C

# our modelled computing HEIs and the campuses that belong to each
HEI_OF_INSTITUTION = {
    "MU": "MU", "DCU": "DCU", "UCD": "UCD", "TCD": "TCD",
    "TU Dublin": "TU Dublin", "DkIT": "DkIT", "TUS": "TUS", "SETU": "SETU",
}
# HEA reports Dublin as one county; the four admin counties collapse into it
# county that physically contains a campus of each HEI (within the study region)
HOME_COUNTY = {"MU": "Kildare", "DCU": "Dublin", "UCD": "Dublin", "TCD": "Dublin",
               "TU Dublin": "Dublin", "DkIT": "Louth", "TUS": "Westmeath",
               "SETU": "Carlow"}

THIRD_LEVEL = ["T10_4_HCT", "T10_4_ODNDT", "T10_4_HDPQT", "T10_4_PDT", "T10_4_DT"]


def _haversine_km(lon1, lat1, lon2, lat2):
    r = 6371.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp, dl = np.radians(lat2 - lat1), np.radians(lon2 - lon1)
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def county_of(name: str) -> str:
    n = (str(name).upper().replace("Ú", "U").replace("Á", "A")
         .replace("É", "E").replace("Ó", "O").replace("Í", "I"))
    if "DUBLIN" in n or "LAOGHAIRE" in n or n.strip() == "FINGAL":
        return "Dublin"
    return name.title().replace("Ún", "un")


def education_by_county() -> pd.Series:
    """third-level share of the 15+ population, by county, from Census 2022 SAPS."""
    sa = pd.read_csv(C.SA_GEOJSON.with_suffix(""), nrows=0) if False else None
    import geopandas as gpd
    g = gpd.read_file(C.SA_GEOJSON, columns=["SA_GEOGID_2022", "COUNTY_ENGLISH"])
    g["sa_id"] = g["SA_GEOGID_2022"].astype(str).str.lstrip("A")
    saps = pd.read_csv(C.SAPS_SA, encoding="latin-1",
                       usecols=["GEOGID", "T10_4_TT", "T10_4_NST", *THIRD_LEVEL])
    saps["sa_id"] = saps["GEOGID"].astype(str).str.strip()
    m = g.merge(saps, on="sa_id", how="left")
    m["county"] = m["COUNTY_ENGLISH"].map(county_of)
    agg = m.groupby("county").sum(numeric_only=True)
    denom = (agg["T10_4_TT"] - agg["T10_4_NST"]).clip(lower=1)
    return (agg[THIRD_LEVEL].sum(axis=1) / denom).rename("third_level_share")


CAR_CAP_MIN = 150   # 25_combine_p3 treats a one-way drive over 150 min as not a daily commute


def main() -> None:
    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"id": str})
    origins["origin_id"] = origins["id"].str.zfill(6)
    origins["county"] = origins["county"].map(county_of)
    campuses = pd.read_csv(C.PROC / "campuses_p3.csv")
    campuses["hei"] = campuses["institution"].map(HEI_OF_INSTITUTION)
    campuses = campuses[campuses["hei"].notna()]

    od = pd.read_csv(C.OUT / "p3_od_long.csv", dtype={"origin_id": str})
    od["origin_id"] = od["origin_id"].str.zfill(6)
    od = od[(od["schedule"] == "peak") & od["reachable"]]
    od = od.merge(campuses[["id", "hei"]].rename(columns={"id": "campus_id"}),
                  on="campus_id", how="inner")
    # min over the HEI's campuses, per origin x mode
    best = (od.groupby(["origin_id", "hei", "mode"], as_index=False)["am_p50"].min())
    best = best.pivot_table(index=["origin_id", "hei"], columns="mode",
                            values="am_p50").reset_index()
    # every ED x HEI pair, so an ED with no trip within the cap still counts in its county's average:
    # "not reachable" takes the cap (PT 240 min, car 150 min, as in 25_combine_p3), rather than
    # dropping out of the numerator while staying in the denominator (fixed 2 Oct 2026)
    grid = origins[["origin_id"]].merge(pd.DataFrame({"hei": sorted(campuses["hei"].unique())}), how="cross")
    best = grid.merge(best, on=["origin_id", "hei"], how="left")
    best["car"] = best["car"].fillna(CAR_CAP_MIN)
    for col in ("pt_plus_rail", "pt"):
        best[col] = best[col].fillna(C.MAX_TRIP_MIN)
    best = best.merge(origins[["origin_id", "county", "cohort_17_19", "lon", "lat"]],
                      on="origin_id", how="left")

    # straight-line km from each ED to the nearest campus of each HEI
    camp_xy = {h: campuses[campuses.hei == h][["lon", "lat"]].to_numpy()
               for h in campuses.hei.unique()}
    def nearest_km(row):
        cs = camp_xy[row["hei"]]
        return float(_haversine_km(row["lon"], row["lat"], cs[:, 0], cs[:, 1]).min())
    best["km"] = best.apply(nearest_km, axis=1)

    w = best["cohort_17_19"].clip(lower=1)
    for col in ("car", "pt_plus_rail", "pt", "km"):
        best[col + "_w"] = best[col] * w
    ch = (best.groupby(["county", "hei"])
          .agg(cohort=("cohort_17_19", "sum"),
               car_w=("car_w", "sum"), ptr_w=("pt_plus_rail_w", "sum"),
               pt_w=("pt_w", "sum"), km_w=("km_w", "sum"),
               n_eds=("origin_id", "nunique"))
          .reset_index())
    for src, dst in (("car_w", "car_min"), ("ptr_w", "ptrail_min"),
                     ("pt_w", "pt_min"), ("km_w", "km")):
        ch[dst] = (ch[src] / ch["cohort"]).round(2)
    ch = ch.drop(columns=["car_w", "ptr_w", "pt_w", "km_w"])
    ch["home"] = [int(HOME_COUNTY.get(h) == c) for c, h in zip(ch["county"], ch["hei"])]

    county = (origins.groupby("county")
              .agg(cohort_17_19=("cohort_17_19", "sum"), n_eds=("origin_id", "nunique"))
              .reset_index())
    county = county.merge(education_by_county().reset_index(), on="county", how="left")

    ch.to_csv(C.OUT / "p4_county_hei.csv", index=False)
    county.to_csv(C.OUT / "p4_county.csv", index=False)
    print(f"wrote p4_county_hei.csv ({len(ch)} rows), p4_county.csv ({len(county)} rows)")
    print("\ncounty covariates:")
    print(county.round(3).to_string(index=False))
    print("\naccessibility (peak) - car / PT+rail minutes, MU column:")
    print(ch[ch.hei == "MU"][["county", "car_min", "ptrail_min", "km", "home"]]
          .to_string(index=False))


if __name__ == "__main__":
    main()
