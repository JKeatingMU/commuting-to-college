"""Phase 3 commute CARBON model - all 14 campuses.

CO2 emissions of a round-trip commute from each ED to each HEI campus, by mode.
Operational (tank-to-wheel / plug-to-wheel) only. Design + every parameter:
docs/emissions-model.md ; config.py (carbon block).

Reads  outputs/p3_cost.csv   (for km_1way, fare_type, cohort, county - peak schedule)
Writes outputs/p3_emissions.csv            per ED x campus: kg CO2 / day, / year, per km, by mode
       outputs/p3_emissions_by_county.csv  per county x campus: cohort-weighted + cohort-scale totals
"""

from __future__ import annotations

import pandas as pd

import config as C

CAR_G = C.CO2_CAR_G_PER_VKM[C.CO2_CAR_TYPE]
DAYS = C.CO2_COMMUTE_DAYS


def _row_emissions(km_1way: float, fare_type: str) -> dict:
    pt_g = C.CO2_PT_G_PER_PKM.get(fare_type, C.CO2_PT_G_PER_PKM["intercity"])
    car_day = km_1way * 2 * CAR_G / C.CO2_CAR_OCCUPANCY / 1000.0            # kg / day
    pt_day = km_1way * C.CO2_PT_DIST_FACTOR * 2 * pt_g / 1000.0            # kg / day
    return {
        "car_kg_day": round(car_day, 3),
        "pt_kg_day": round(pt_day, 3),
        "car_kg_year": round(car_day * DAYS, 1),
        "pt_kg_year": round(pt_day * DAYS, 1),
        "saving_kg_year": round((car_day - pt_day) * DAYS, 1),
        "car_g_per_km": round(2 * CAR_G / C.CO2_CAR_OCCUPANCY, 1),
        "pt_g_per_km": round(2 * pt_g * C.CO2_PT_DIST_FACTOR, 1),
    }


def main() -> None:
    cost = pd.read_csv(C.OUT / "p3_cost.csv", dtype={"origin_id": str})
    cost = cost[cost["schedule"] == "peak"].copy()

    em = cost.apply(lambda r: _row_emissions(r["km_1way"], r["fare_type"]), axis=1, result_type="expand")
    out = pd.concat(
        [cost[["origin_id", "origin", "county", "cohort_17_19", "campus_id", "institution",
               "km_1way", "gc_km", "fare_type"]].reset_index(drop=True),
         em.reset_index(drop=True)],
        axis=1,
    )
    out.to_csv(C.OUT / "p3_emissions.csv", index=False)
    print(f"p3_emissions.csv  {len(out):,} rows")

    # per county x campus: cohort-weighted means + cohort-scale annual tonnes
    w = out.copy()
    for col in ("car_kg_year", "pt_kg_year", "saving_kg_year", "km_1way"):
        w[f"_w_{col}"] = w[col] * w["cohort_17_19"]
    g = w.groupby(["campus_id", "institution", "county"], as_index=False).agg(
        eds=("origin_id", "count"),
        cohort=("cohort_17_19", "sum"),
        km_1way=("_w_km_1way", "sum"),
        car_kg_year=("_w_car_kg_year", "sum"),
        pt_kg_year=("_w_pt_kg_year", "sum"),
        saving_kg_year=("_w_saving_kg_year", "sum"),
        fare_type=("fare_type", lambda s: s.value_counts().idxmax()),
    )
    for col in ("km_1way", "car_kg_year", "pt_kg_year", "saving_kg_year"):
        g[col] = (g[col] / g["cohort"]).round(1)
    # cohort-scale: whole county's 17-19 entrants commuting to this campus, tonnes/yr
    g["cohort_car_t"] = (g["car_kg_year"] * g["cohort"] / 1000).round(0)
    g["cohort_pt_t"] = (g["pt_kg_year"] * g["cohort"] / 1000).round(0)
    g["cohort_saving_t"] = (g["saving_kg_year"] * g["cohort"] / 1000).round(0)
    g = g.sort_values(["campus_id", "km_1way"])
    g.to_csv(C.OUT / "p3_emissions_by_county.csv", index=False)
    print(f"p3_emissions_by_county.csv  {len(g):,} rows")

    mu = out[out["campus_id"] == "mu_maynooth"]
    tot = mu["cohort_17_19"].sum()
    wcar = (mu["car_kg_year"] * mu["cohort_17_19"]).sum() / tot
    wpt = (mu["pt_kg_year"] * mu["cohort_17_19"]).sum() / tot
    print(f"\nMU, cohort-weighted: car {wcar:,.0f} kg/yr  PT {wpt:,.0f} kg/yr  "
          f"saving {wcar - wpt:,.0f} kg/yr  ({C.CO2_CAR_TYPE} car, {DAYS} days, "
          f"EV would be {C.CO2_CAR_G_PER_VKM['ev']:.0f} g/vkm)")


if __name__ == "__main__":
    main()
