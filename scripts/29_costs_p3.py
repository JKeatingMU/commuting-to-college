"""Phase 3 commute COST model - all 14 campuses.

Financial cost of a round-trip commute from each ED to each HEI campus, by mode.
Design + confirmed decisions + every parameter: docs/cost-model.md ; config.py (cost block).

Outputs:
  outputs/p3_cost.csv            per ED x campus x schedule: EUR/day, /week, /year + components
  outputs/p3_cost_by_county.csv  per county x campus (peak, population-weighted)
  outputs/p3_cost_mu.png         static MU chart (companion to the interactive report)
"""

from __future__ import annotations

import json
import math
import subprocess
import time

import matplotlib
import pandas as pd
import requests

import config as C

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OSRM = "http://127.0.0.1:5111"
GRAPH = C.ROOT / "data" / "osrm" / f"study-area-p3-{C.SNAPSHOT}.osrm"
MU = "mu_maynooth"



def _gc_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _up():
    try:
        requests.get(f"{OSRM}/health", timeout=2)
        return True
    except Exception:
        return False


def _osrm_km(src_ll, dst_ll):
    coords = src_ll + dst_ll
    nS = len(src_ll)
    cs = ";".join(f"{lo:.6f},{la:.6f}" for lo, la in coords)
    src = ";".join(map(str, range(nS)))
    dst = ";".join(map(str, range(nS, len(coords))))
    url = (f"{OSRM}/table/v1/driving/{cs}?sources={src}&destinations={dst}&annotations=distance")
    r = requests.get(url, timeout=180)
    r.raise_for_status()
    return r.json()["distances"]  # metres [src][dst]


def _toll_rt(cid, inst, lon, lat, gpo_km, county):
    """Round-trip toll cost, EUR. Crude region rules - see docs/cost-model.md."""
    if inst in C.DUBLIN_BOUND_INSTITUTIONS:
        return 2 * C.TOLL_M50_EUR if (gpo_km > C.M50_TOLL_MIN_GPO_KM
                                      and county != "DUBLIN CITY") else 0.0
    if cid == MU:
        return 2 * C.TOLL_M4_EUR if (lon < C.MU_M4_TOLL_MAX_LON
                                     and lat > C.MU_M4_TOLL_MIN_LAT) else 0.0
    if inst == "DkIT":
        return 2 * C.TOLL_M1_EUR if lat < 53.90 else 0.0
    if inst == "TUS":
        return 2 * C.TOLL_M4_EUR if (lon > -7.55 and lat > 53.05) else 0.0
    return 0.0   # SETU Carlow: M9/M7 toll-free


def _regional_daily(gc_km):
    """Daily round-trip student PT cost to an out-of-zone destination (weekly season / 5)."""
    return max(2 * C.LEAP_90MIN_EUR, C.REGIONAL_DAILY_BASE + C.REGIONAL_DAILY_PER_KM * gc_km)


def _pt_day(cid, inst, oo, am_p50):
    """Round-trip public-transport cost EUR/day + fare type ('zone'|'coach'|'intercity')."""
    dublin_side = inst in C.DUBLIN_BOUND_INSTITUTIONS or cid == MU
    if dublin_side and oo["in_zone"]:
        n = 1 if pd.notna(am_p50) and am_p50 <= 90 else 2
        return min(2 * n * C.LEAP_90MIN_EUR, C.LEAP_DAILY_CAP_EUR), "zone"
    day, ft = _regional_daily(oo[f"gc_{cid}"]), "intercity"
    if cid == MU and oo["coach_ok"] and C.COACH_EUR_PER_DAY < day:
        day, ft = C.COACH_EUR_PER_DAY, "coach"
    return day, ft


def _pt_rail_day(cid, inst, oo, km, pt_day):
    """PT + drive-to-rail: rail-leg fare + short feeder drive + P&R parking. Never > plain PT."""
    dublin_side = inst in C.DUBLIN_BOUND_INSTITUTIONS or cid == MU
    if dublin_side and oo["in_zone"]:
        return pt_day
    day = _regional_daily(oo[f"gc_{cid}"]) + \
        2 * min(km * 0.25, 20) * C.FUEL_EUR_PER_KM + C.PARK_AND_RIDE_EUR
    if cid == MU and oo["coach_ok"]:
        day = min(day, C.COACH_EUR_PER_DAY)
    return min(day, pt_day)


def main() -> None:
    P = C
    origins = pd.read_csv(P.PROC / "origins_p3.csv", dtype={"id": str})
    origins["oid"] = origins["id"].str.zfill(6)
    campuses = pd.read_csv(P.PROC / "campuses_p3.csv")
    inst_of = dict(zip(campuses["id"], campuses["institution"]))

    od = pd.read_csv(P.OUT / "p3_od_long.csv", dtype={"origin_id": str})
    od["origin_id"] = od["origin_id"].str.zfill(6)
    od = (od[od["mode"] == "pt"][["origin_id", "campus_id", "schedule", "am_p50"]]
          .drop_duplicates(["origin_id", "campus_id", "schedule"]))

    # --- OSRM routed distance, EDs -> every campus ---
    proc = None
    if not _up():
        print("starting osrm-routed ...")
        proc = subprocess.Popen(
            ["osrm-routed", "--algorithm", "mld", "--port", "5111",
             "--max-table-size", "20000", str(GRAPH)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            time.sleep(1)
            if _up():
                break
        else:
            raise SystemExit("osrm-routed did not come up")
    try:
        o_ll = list(zip(origins["lon"], origins["lat"]))
        c_ll = list(zip(campuses["lon"], campuses["lat"]))
        dm = _osrm_km(o_ll, c_ll)
    finally:
        if proc:
            proc.terminate()

    for j, cid in enumerate(campuses["id"]):
        origins[f"km_{cid}"] = [row[j] / 1000.0 if row and row[j] is not None else float("nan")
                                for row in dm]
        clat, clon = campuses.loc[j, "lat"], campuses.loc[j, "lon"]
        origins[f"gc_{cid}"] = [_gc_km(la, lo, clat, clon)
                                for lo, la in zip(origins["lon"], origins["lat"])]
    origins["gpo_km"] = [_gc_km(la, lo, *P.GPO_LATLON)
                         for lo, la in zip(origins["lon"], origins["lat"])]
    origins["in_zone"] = ((origins["county"].str.upper().isin(P.DSHZ_COUNTIES))
                          & (origins["gpo_km"] <= P.DSHZ_MAX_KM_FROM_GPO))
    # UM commuter coach: weekday routes from 28_coach_routes_p3 (Sunday-only routes excluded)
    um = [r for r in json.loads((P.OUT / "p3_coach_routes.json").read_text()) if r["daily"]]
    board = [r["stops"][0][:2] for r in um]
    pickup = [s[:2] for r in um for s in r["stops"]]
    origins["coach_ok"] = [
        any(_gc_km(la, lo, sla, slo) <= P.COACH_CATCHMENT_KM for slo, sla in board)
        or any(_gc_km(la, lo, sla, slo) <= P.COACH_STOP_KM for slo, sla in pickup)
        for lo, la in zip(origins["lon"], origins["lat"])]
    o = origins.set_index("oid")

    am = {(r["origin_id"], r["campus_id"], r["schedule"]): r["am_p50"] for r in od.to_dict("records")}

    rows = []
    for oid, oo in o.iterrows():
        cty = oo["county"].upper()
        for cid in campuses["id"]:
            inst = inst_of[cid]
            km = oo[f"km_{cid}"]
            if not (km == km):
                continue
            toll = _toll_rt(cid, inst, oo["lon"], oo["lat"], oo["gpo_km"], cty)
            park = P.CAMPUS_PARKING_EUR[cid]
            fuel = 2 * km * P.FUEL_EUR_PER_KM
            for sched in ("peak", "late"):
                a = am.get((oid, cid, sched))
                pt, fare_type = _pt_day(cid, inst, oo, a)
                ptr = _pt_rail_day(cid, inst, oo, km, pt)
                rows.append({
                    "origin_id": oid, "origin": oo["name"], "county": oo["county"],
                    "cohort_17_19": int(oo["cohort_17_19"]), "campus_id": cid,
                    "institution": inst, "schedule": sched,
                    "km_1way": round(km, 1), "gc_km": round(oo[f"gc_{cid}"], 1),
                    "in_zone": bool(oo["in_zone"]),
                    "fare_type": fare_type,
                    "coach": bool(cid == MU and oo["coach_ok"]),
                    "car_fuel_day": round(fuel, 2),
                    "car_day": round(fuel + park + toll, 2),
                    "car_full_day": round(2 * km * P.CAR_FULL_EUR_PER_KM + park + toll, 2),
                    "car_park": park, "car_toll": round(toll, 2),
                    "pt_day": round(pt, 2), "pt_rail_day": round(ptr, 2),
                    "car_fuel_year": round(P.COMMUTE_DAYS_PER_YEAR * fuel),
                    "car_year": round(P.COMMUTE_DAYS_PER_YEAR * (fuel + park + toll)),
                    "pt_year": round(P.COMMUTE_DAYS_PER_YEAR * pt),
                })
    cost = pd.DataFrame(rows)
    cost.to_csv(P.OUT / "p3_cost.csv", index=False)

    peak = cost[cost["schedule"] == "peak"]

    def cw(g, col):
        return round((g[col] * g["cohort_17_19"]).sum() / g["cohort_17_19"].sum(), 2)

    by = (peak.groupby(["campus_id", "institution", "county"])
          .apply(lambda g: pd.Series({
              "eds": len(g), "cohort": int(g["cohort_17_19"].sum()),
              "km_1way": round(g["km_1way"].mean()),
              "car_fuel_day": cw(g, "car_fuel_day"), "car_day": cw(g, "car_day"),
              "pt_day": cw(g, "pt_day"), "pt_rail_day": cw(g, "pt_rail_day"),
              "pt_year": round(P.COMMUTE_DAYS_PER_YEAR * cw(g, "pt_day")),
          }), include_groups=False).reset_index())
    by.to_csv(P.OUT / "p3_cost_by_county.csv", index=False)

    # --- static MU chart (companion) ---
    mu = peak[peak["campus_id"] == MU]
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.scatter(mu["gc_km"], mu["pt_day"], s=8, alpha=.4, color="#028090",
               label="Public transport (student Leap / coach)")
    ax.scatter(mu["gc_km"], mu["car_fuel_day"], s=8, alpha=.35, color="#e6a15c",
               label="Car - fuel only")
    ax.scatter(mu["gc_km"], mu["car_day"], s=8, alpha=.4, color="#d85128",
               label="Car - fuel + parking + toll")
    ax.set_xlabel("Straight-line distance to Maynooth (km)")
    ax.set_ylabel("Round-trip cost per day (EUR)")
    ax.set_title(f"Daily commute cost to Maynooth by mode  (peak; {P.FUEL_TYPE}, "
                 f"EUR{P.FUEL[P.FUEL_TYPE]['eur_per_litre']:.2f}/L)")
    ax.legend(frameon=False, fontsize=8)
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(P.OUT / "p3_cost_mu.png", dpi=130)

    # --- console summary ---
    f = P.FUEL[P.FUEL_TYPE]
    print(f"\ncost model - {peak['origin_id'].nunique():,} EDs x {len(campuses)} campuses")
    print(f"fuel: {P.FUEL_TYPE} EUR{f['eur_per_litre']}/L x {f['litre_per_100km']} L/100km "
          f"= EUR{P.FUEL_EUR_PER_KM:.3f}/km  (diesel ~0.102)\n")
    print("  population-weighted EUR/day round trip, by campus (peak):")
    g = (peak.groupby(["institution", "campus_id"])
         .apply(lambda x: pd.Series({
             "car_fuel": cw(x, "car_fuel_day"), "car_marg": cw(x, "car_day"),
             "pt": cw(x, "pt_day"), "pt_rail": cw(x, "pt_rail_day")}),
             include_groups=False)
         .sort_values("pt"))
    print(g.to_string())
    print("\n  wrote p3_cost.csv, p3_cost_by_county.csv, p3_cost_mu.png")


if __name__ == "__main__":
    main()
