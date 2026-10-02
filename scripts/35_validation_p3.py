"""How well does the model match reality? Compares modelled commutes with what students reported
in Census 2022.

Reads  data/raw/cso-f7145-2022-*.json  CSO PxStat F7145: students aged 19+ by town, average journey
                                       time and share by means of travel (218 towns plus aggregates)
       data/raw/cso-f7065-2022-*.json  CSO PxStat F7065: persons by county and means of travel
       data/raw/cso-builtup-areas-*    census town boundaries (joined to F7145 by GUID)
       outputs/p3_od_long.csv, p3_car_advantage.csv, data/processed/origins_p3.csv
Writes outputs/p3_validation_towns.csv, outputs/p3_validation_counties.csv

Each town's modelled time is the average over the Small Areas inside its boundary (weighted by
15-17 year olds, as elsewhere) of the morning-peak time to the quickest campus, by PT + drive-to-rail
and by car. The census figure is the reported average journey time of students aged 19+ living in
the town, to wherever they study, by whatever means.
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd

import config as C

F7145 = sorted(C.RAW.glob("cso-f7145-2022-*.json"))[-1]
F7065 = sorted(C.RAW.glob("cso-f7065-2022-*.json"))[-1]
BUA = sorted(C.RAW.glob("cso-builtup-areas-2022-*.geojson"))[-1]
STUDENTS = "Students at school or college aged 19 years and over"
STUDY_COUNTIES = {"Dublin", "Kildare", "Meath", "Wicklow", "Westmeath", "Longford", "Offaly", "Laois", "Louth",
                  "Monaghan", "Carlow", "Kilkenny"}   # BUA county names (Dublin is one)
WALK_MIN = 15   # assumed journey time for students who walk or cycle, for the mode-weighted estimate


def _jsonstat(path):
    """JSON-stat 2.0 cube -> long DataFrame of labels."""
    d = json.loads(path.read_text())
    ids, size, val = d["id"], d["size"], d["value"]
    idx = pd.MultiIndex.from_product([list(d["dimension"][k]["category"]["index"]) for k in ids], names=ids)
    df = pd.DataFrame({"value": val}, index=idx).reset_index()
    for k in ids:
        df[k + "_label"] = df[k].map(d["dimension"][k]["category"]["label"])
    return df


def towns(best) -> pd.DataFrame:
    f = _jsonstat(F7145)
    town_dim = [k for k in f.columns if k.startswith("C04160")][0]
    who_dim = [k for k in f.columns if k.startswith("C02704") and not k.endswith("_label")][0]
    sex_dim = [k for k in f.columns if k.startswith("C02199") and not k.endswith("_label")][0]
    f = f[(f[who_dim + "_label"] == STUDENTS) & (f[sex_dim + "_label"] == "Both sexes")]
    w = f.pivot_table(index=[town_dim, town_dim + "_label"], columns="STATISTIC_label", values="value").reset_index()
    w = w.rename(columns={town_dim: "guid", town_dim + "_label": "town", "Average journey time": "reported_min",
                          "Public (bus or train)": "share_pt", "Car (driver or passenger)": "share_car",
                          "Active (walking and cycling)": "share_active"})

    bua = gpd.read_file(BUA)[["URBAN_AREA_GUID", "URBAN_AREA_NAME", "COUNTY", "geometry"]].to_crs(2157)
    bua = bua[bua["COUNTY"].isin(STUDY_COUNTIES)]
    sa = gpd.read_file(C.SA_GEOJSON, columns=["SA_GEOGID_2022", "ED_ID_STR", "COUNTY_ENGLISH"])
    sa = sa[sa["COUNTY_ENGLISH"].isin(C.P3_SA_COUNTIES)].to_crs(2157)
    sa["sa_id"] = sa["SA_GEOGID_2022"].astype(str).str.lstrip("A")
    sa["id"] = sa["ED_ID_STR"].astype(str).str.zfill(6)
    ages = [f"T1_1AGE{a}T" for a in C.COHORT_PROXY_AGES]
    saps = pd.read_csv(C.SAPS_SA, encoding="latin-1", usecols=["GEOGID", *ages])
    saps["sa_id"] = saps["GEOGID"].astype(str).str.strip()
    saps["w"] = saps[ages].sum(axis=1)
    sa = sa.merge(saps[["sa_id", "w"]], on="sa_id", how="left").fillna({"w": 0})
    pts = sa.set_geometry(sa.geometry.representative_point())
    j = gpd.sjoin(pts[["id", "w", "geometry"]], bua, predicate="within")
    j = j.merge(best, on="id", how="inner")

    def agg(g):
        ww = g["w"].clip(lower=0.5)
        return pd.Series({"model_ptr": np.average(g["ptr"].fillna(C.MAX_TRIP_MIN), weights=ww),
                          "model_car": np.average(g["car"].fillna(150), weights=ww),
                          "n_sa": len(g), "weight": float(g["w"].sum())})
    m = j.groupby(["URBAN_AREA_GUID", "URBAN_AREA_NAME", "COUNTY"]).apply(agg).reset_index()
    out = w.merge(m, left_on="guid", right_on="URBAN_AREA_GUID", how="inner")
    out = out[["town", "URBAN_AREA_NAME", "COUNTY", "reported_min", "share_active", "share_pt", "share_car",
               "model_ptr", "model_car", "n_sa", "weight"]].rename(columns={"URBAN_AREA_NAME": "name", "COUNTY": "county"})
    # what the model implies for the town given how its students actually travel
    s = out["share_pt"] + out["share_car"] + out["share_active"]
    out["model_mix"] = (out["share_pt"] * out["model_ptr"] + out["share_car"] * out["model_car"]
                        + out["share_active"] * WALK_MIN) / s
    return out.round(1)


def counties() -> pd.DataFrame:
    f = _jsonstat(F7065)
    sex_dim = [k for k in f.columns if k.startswith("C02199") and not k.endswith("_label")][0]
    cty_dim = [k for k in f.columns if k.startswith("C04104") and not k.endswith("_label")][0]
    mode_dim = [k for k in f.columns if k.startswith("C02734") and not k.endswith("_label")][0]
    f = f[(f["STATISTIC_label"] == STUDENTS) & (f[sex_dim + "_label"] == "Both sexes")]
    p = f.pivot_table(index=cty_dim + "_label", columns=mode_dim + "_label", values="value")
    tot = p["All means of travel"] - p["Not stated"]
    c = pd.DataFrame({
        "county": p.index,
        "students": p["All means of travel"].values,
        "share_car": ((p["Motor car: Driver"] + p["Motor car: Passenger"]) / tot * 100).round(1).values,
        "share_pt": ((p["Bus, minibus or coach"] + p["Train, DART or LUAS"]) / tot * 100).round(1).values,
        "share_active": ((p["On foot"] + p["Bicycle"]) / tot * 100).round(1).values,
    })
    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"id": str})
    c = c[c["county"].isin(set(origins["county"]))]
    adv = pd.read_csv(C.OUT / "p3_car_advantage.csv", dtype={"origin_id": str})
    adv = adv[adv["schedule"] == "peak"].merge(origins[["id", "county", "cohort_17_19"]], left_on="origin_id", right_on="id")

    def wmed(g):
        g = g.dropna(subset=["car_vs_ptrail"]).sort_values("car_vs_ptrail")
        cw = g["cohort_17_19"].cumsum()
        return float(g["car_vs_ptrail"][cw >= cw.iloc[-1] / 2].iloc[0])
    sav = adv.groupby("county").apply(wmed).rename("model_car_saving").reset_index()
    return c.merge(sav, on="county").round(1)


def main() -> None:
    od = pd.read_csv(C.OUT / "p3_od_long.csv", dtype={"origin_id": str})
    od = od[od["schedule"] == "peak"]
    od["id"] = od["origin_id"].str.zfill(6)
    best = od.pivot_table(index="id", columns="mode", values="am_p50", aggfunc="min").reset_index()
    best = best.rename(columns={"pt_plus_rail": "ptr"})[["id", "ptr", "car"]]

    t = towns(best)
    t.to_csv(C.OUT / "p3_validation_towns.csv", index=False)
    c = counties()
    c.to_csv(C.OUT / "p3_validation_counties.csv", index=False)

    big = t[t["weight"] >= 100]
    r_mix = np.corrcoef(t["model_mix"], t["reported_min"])[0, 1]
    r_big = np.corrcoef(big["model_mix"], big["reported_min"])[0, 1]
    print(f"mode-weighted: r={r_mix:.2f} (all), r={r_big:.2f} ({len(big)} towns with 100+ young people); "
          f"mean error {(t['model_mix'] - t['reported_min']).mean():+.1f} min, "
          f"mean absolute error {(t['model_mix'] - t['reported_min']).abs().mean():.1f} min")
    r_pt = np.corrcoef(t["model_ptr"], t["reported_min"])[0, 1]
    r_car = np.corrcoef(t["model_car"], t["reported_min"])[0, 1]
    r_c = np.corrcoef(c["model_car_saving"], c["share_car"])[0, 1]
    print(f"towns: {len(t)} in the study area; reported vs modelled PT+rail r={r_pt:.2f}, vs car r={r_car:.2f}")
    print(t.sort_values("weight", ascending=False).head(8)[["name", "reported_min", "model_ptr", "model_car", "share_car"]].to_string(index=False))
    print(f"counties: {len(c)}; share of students driving vs modelled car saving r={r_c:.2f}")
    print(c.sort_values("model_car_saving").to_string(index=False))


if __name__ == "__main__":
    main()
