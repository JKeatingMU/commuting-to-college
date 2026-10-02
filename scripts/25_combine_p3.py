"""Phase 3: assemble the full OD table across 3 modes x 2 schedules.

modes:     pt | car | pt_plus_rail
schedules: peak (arrive 08:30 / leave 18:30) | late (arrive 10:00 / leave 17:00)

Output: outputs/p3_od_long.csv   one row per ED x campus x schedule x mode
"""

from __future__ import annotations

import pandas as pd

import config as C

PROC = C.PROC


def _pf(name):
    return pd.read_parquet(PROC / name)


def _regime(inst):
    return "dublin" if inst in C.DUBLIN_BOUND_INSTITUTIONS else "regional"


def main() -> None:
    origins = pd.read_csv(PROC / "origins_p3.csv", dtype={"ed_id": str, "id": str})
    origins["origin_id"] = origins["id"].str.zfill(6)
    campuses = pd.read_csv(PROC / "campuses_p3.csv")
    inst = dict(zip(campuses["id"], campuses["institution"]))

    car_ff = _pf("p3_car_freeflow.parquet").rename(
        columns={"from_id": "origin_id", "to_id": "campus_id", "car_p50": "car_ff"})
    car_ff["origin_id"] = car_ff["origin_id"].astype(str).str.zfill(6)

    car2st = _pf("p3_car_to_station.parquet").rename(
        columns={"from_id": "origin_id", "to_id": "station_id", "car_p50": "drive_ff"})
    car2st["origin_id"] = car2st["origin_id"].astype(str).str.zfill(6)

    rows = []
    for sname in C.SCHEDULES:
        am = _pf(f"p3_pt_{sname}_am.parquet").rename(
            columns={"from_id": "origin_id", "to_id": "campus_id"})
        pm = _pf(f"p3_pt_{sname}_pm.parquet").rename(
            columns={"from_id": "campus_id", "to_id": "origin_id"})
        for d in (am, pm):
            d["origin_id"] = d["origin_id"].astype(str).str.zfill(6)
        pt = am[["origin_id", "campus_id", "am_p50"]].merge(
            pm[["origin_id", "campus_id", "pm_p50"]], on=["origin_id", "campus_id"], how="outer")

        # --- CAR ---
        fam = {k: C.CAR_FACTOR[(sname, "am")][k] for k in ("dublin", "regional")}
        fpm = {k: C.CAR_FACTOR[(sname, "pm")][k] for k in ("dublin", "regional")}
        car = car_ff.copy()
        car["reg"] = car["campus_id"].map(inst).map(_regime)
        car["am_p50"] = car["car_ff"] * car["reg"].map(fam)
        car["pm_p50"] = car["car_ff"] * car["reg"].map(fpm)
        # a 2.5h+ one-way drive is not a daily commute
        car.loc[car["am_p50"] > 150, ["am_p50", "pm_p50"]] = pd.NA
        car = car[["origin_id", "campus_id", "am_p50", "pm_p50"]]

        # --- DRIVE-TO-RAIL ---
        s2c = _pf(f"p3_dr_s2c_{sname}.parquet").rename(
            columns={"from_id": "station_id", "to_id": "campus_id", "am_p50": "s2c"})
        c2s = _pf(f"p3_dr_c2s_{sname}.parquet").rename(
            columns={"from_id": "campus_id", "to_id": "station_id", "pm_p50": "c2s"})
        drive = car2st.copy()
        drive["drive"] = drive["drive_ff"] * C.CAR_FACTOR[(sname, "am")]["regional"]
        drive = drive[drive["drive"] <= C.MAX_DRIVE_TO_STATION_MIN]

        dam = drive.merge(s2c[["station_id", "campus_id", "s2c"]], on="station_id")
        dam["t"] = dam["drive"] + C.PARKING_BUFFER_MIN + dam["s2c"]
        dam = dam.groupby(["origin_id", "campus_id"], as_index=False)["t"].min().rename(columns={"t": "dr_am"})
        dpm = drive.merge(c2s[["station_id", "campus_id", "c2s"]], on="station_id")
        dpm["t"] = dpm["c2s"] + C.PARKING_BUFFER_MIN + dpm["drive"]
        dpm = dpm.groupby(["origin_id", "campus_id"], as_index=False)["t"].min().rename(columns={"t": "dr_pm"})

        hyb = (pt.merge(dam, on=["origin_id", "campus_id"], how="left")
                 .merge(dpm, on=["origin_id", "campus_id"], how="left"))
        hyb["am_p50"] = hyb[["am_p50", "dr_am"]].min(axis=1)
        hyb["pm_p50"] = hyb[["pm_p50", "dr_pm"]].min(axis=1)
        hyb = hyb[["origin_id", "campus_id", "am_p50", "pm_p50"]]

        for mode, df in (("pt", pt), ("car", car), ("pt_plus_rail", hyb)):
            d = df.copy()
            d["schedule"] = sname
            d["mode"] = mode
            rows.append(d)

    out = pd.concat(rows, ignore_index=True)
    out = out[out["campus_id"].isin(campuses["id"])]   # drop any campus no longer in the set
    out = out.merge(origins[["origin_id", "name", "county", "cohort_17_19"]]
                    .rename(columns={"name": "origin"}), on="origin_id", how="left")
    out = out.merge(campuses[["id", "name", "institution"]]
                    .rename(columns={"id": "campus_id", "name": "campus"}), on="campus_id", how="left")
    out["roundtrip_p50"] = out["am_p50"] + out["pm_p50"]
    out["reachable"] = out[["am_p50", "pm_p50"]].notna().all(axis=1)
    out.to_csv(C.OUT / "p3_od_long.csv", index=False)
    print(f"wrote p3_od_long.csv ({len(out):,} rows)")
    print(out.groupby(["schedule", "mode"]).agg(
        reach=("reachable", "mean"),
        med_am=("am_p50", "median")).round(2).to_string())


if __name__ == "__main__":
    main()
