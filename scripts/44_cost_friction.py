"""Does the money matter separately from the distance? Re-runs the Phase 4a gravity model with
the annual cost of the commute as the friction term, and reports how closely cost tracks
distance and drive time at county scale.

Cost is each ED's cheapest annual public-transport cost to the HEI (minimum over its campuses,
peak schedule, 140 days, from p3_cost.csv), cohort-weighted to county over every ED.
Writes outputs/p4_cost_check.csv (one row per field) and prints the correlations.
"""

from __future__ import annotations

import importlib

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

import config as C

m41 = importlib.import_module("41_county_accessibility")
m42 = importlib.import_module("42_gravity_model")


def county_cost() -> pd.DataFrame:
    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"id": str})
    origins["origin_id"] = origins["id"].str.zfill(6)
    origins["county"] = origins["county"].map(m41.county_of)
    camp = pd.read_csv(C.PROC / "campuses_p3.csv")
    camp["hei"] = camp["institution"].map(m41.HEI_OF_INSTITUTION)
    cost = pd.read_csv(C.OUT / "p3_cost.csv", dtype={"origin_id": str})
    cost = cost[cost["schedule"] == "peak"]
    cost["origin_id"] = cost["origin_id"].str.zfill(6)
    cost = cost.merge(camp[["id", "hei"]].rename(columns={"id": "campus_id"}), on="campus_id").dropna(subset=["hei"])
    best = cost.groupby(["origin_id", "hei"], as_index=False)["pt_year"].min()
    best = best.merge(origins[["origin_id", "county", "cohort_17_19"]], on="origin_id")
    best["w"] = best["cohort_17_19"].clip(lower=1)
    best["cw"] = best["pt_year"] * best["w"]
    g = best.groupby(["county", "hei"]).agg(cw=("cw", "sum"), w=("w", "sum")).reset_index()
    g["cost_eur"] = (g["cw"] / g["w"]).round(1)
    return g[["county", "hei", "cost_eur"]]


def main() -> None:
    cc = county_cost()
    acc = pd.read_csv(C.OUT / "p4_county_hei.csv").merge(cc, on=["county", "hei"], how="left")
    r_km = np.corrcoef(acc["cost_eur"], acc["km"])[0, 1]
    r_car = np.corrcoef(acc["cost_eur"], acc["car_min"])[0, 1]
    rows = []
    for field in m42.FIELDS:
        p = m42.build_panel(field).merge(cc, on=["county", "hei"], how="left")
        p["cost_100"] = p["cost_eur"] / 100.0
        full = smf.glm("n ~ cost_100 + home + hei + county", data=p, family=sm.families.Poisson()).fit(cov_type="HC1")
        base = smf.glm("n ~ home + hei + county", data=p, family=sm.families.Poisson()).fit()
        b, se = full.params["cost_100"], full.bse["cost_100"]
        rows.append({"field": field, "pct_per100eur": round(100 * (np.exp(b) - 1), 1), "z": round(b / se, 1),
                     "dev_drop": round(base.deviance - full.deviance, 1), "aic": round(full.aic, 1)})
    out = pd.DataFrame(rows)
    out["r_cost_km"] = round(r_km, 2)
    out["r_cost_car"] = round(r_car, 2)
    out.to_csv(C.OUT / "p4_cost_check.csv", index=False)
    print(f"county x HEI cost vs straight-line km r={r_km:.2f}, vs car minutes r={r_car:.2f}")
    print(out.to_string(index=False))


if __name__ == "__main__":
    main()
