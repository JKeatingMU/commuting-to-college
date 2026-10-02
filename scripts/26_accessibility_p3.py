"""Phase 3 population-weighted accessibility, across 3 modes x 2 schedules.

Outputs:
  outputs/p3_ed_access.csv    per ED x mode x schedule: best times, most accessible campus, counts
  outputs/p3_pop_weighted.csv cohort share within each threshold, per target x mode x schedule
  outputs/p3_by_county.csv    same, by county (60-min)
  outputs/p3_car_advantage.csv per ED: minutes car saves over PT (peak & late)
"""

from __future__ import annotations

import pandas as pd

import config as C

TARGETS = {
    "any_hei": None,
    "university": C.UNIVERSITIES,
    "maynooth": {"MU"},
    "regional_hei": C.REGIONAL_HEIS,
}


def _best(df):
    """per (origin) : min morning one-way to each target + most accessible campus."""
    rows = []
    for oid, g in df.groupby("origin_id"):
        gr = g[g["reachable"]]
        rec = {"origin_id": oid}
        for tn, insts in TARGETS.items():
            sub = gr if insts is None else gr[gr["institution"].isin(insts)]
            rec[f"am_{tn}"] = sub["am_p50"].min() if len(sub) else pd.NA
        b = gr.sort_values("am_p50").head(1)
        rec["most_accessible"] = b["campus"].iloc[0] if len(b) else pd.NA
        rec["most_accessible_inst"] = b["institution"].iloc[0] if len(b) else pd.NA
        rec["best_rt"] = gr["roundtrip_p50"].min() if len(gr) else pd.NA
        for t in C.ACCESS_THRESHOLDS:
            rec[f"n_within_{t}"] = int((gr["am_p50"] <= t).sum())
        rows.append(rec)
    return pd.DataFrame(rows)


def main() -> None:
    od = pd.read_csv(C.OUT / "p3_od_long.csv", dtype={"origin_id": str})
    od["origin_id"] = od["origin_id"].str.zfill(6)
    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"id": str})
    origins["origin_id"] = origins["id"].str.zfill(6)
    coh = dict(zip(origins["origin_id"], origins["cohort_17_19"]))
    cty = dict(zip(origins["origin_id"], origins["county"]))
    total = origins["cohort_17_19"].sum()

    ea_all, pw_rows, cty_rows = [], [], []
    for (sched, mode), g in od.groupby(["schedule", "mode"]):
        bt = _best(g)
        bt["schedule"] = sched
        bt["mode"] = mode
        bt["cohort"] = bt["origin_id"].map(coh)
        bt["county"] = bt["origin_id"].map(cty)
        ea_all.append(bt)
        for tn in TARGETS:
            v = pd.to_numeric(bt[f"am_{tn}"], errors="coerce")
            for t in C.ACCESS_THRESHOLDS:
                m = (v <= t).fillna(False)
                pw_rows.append({"schedule": sched, "mode": mode, "target": tn,
                                "threshold_min": t,
                                "cohort_share": round(bt.loc[m, "cohort"].sum() / total, 3)})
            m60 = (v <= 60).fillna(False)
            for c, cg in bt.assign(_m=m60).groupby("county"):
                cty_rows.append({"schedule": sched, "mode": mode, "target": tn, "county": c,
                                 "cohort_share": round(cg.loc[cg["_m"], "cohort"].sum()
                                                       / cg["cohort"].sum(), 3)})

    ea = pd.concat(ea_all, ignore_index=True)
    ea.to_csv(C.OUT / "p3_ed_access.csv", index=False)
    pd.DataFrame(pw_rows).to_csv(C.OUT / "p3_pop_weighted.csv", index=False)
    pd.DataFrame(cty_rows).to_csv(C.OUT / "p3_by_county.csv", index=False)

    # car advantage: PT best vs CAR best, per schedule
    adv = []
    for sched in C.SCHEDULES:
        pt = ea[(ea["mode"] == "pt") & (ea["schedule"] == sched)].set_index("origin_id")["am_any_hei"]
        pr = ea[(ea["mode"] == "pt_plus_rail") & (ea["schedule"] == sched)].set_index("origin_id")["am_any_hei"]
        cr = ea[(ea["mode"] == "car") & (ea["schedule"] == sched)].set_index("origin_id")["am_any_hei"]
        a = pd.DataFrame({"pt": pd.to_numeric(pt, errors="coerce"),
                          "pt_rail": pd.to_numeric(pr, errors="coerce"),
                          "car": pd.to_numeric(cr, errors="coerce")})
        a["schedule"] = sched
        a["car_vs_pt"] = a["pt"] - a["car"]
        a["car_vs_ptrail"] = a["pt_rail"] - a["car"]
        adv.append(a.reset_index())
    pd.concat(adv, ignore_index=True).to_csv(C.OUT / "p3_car_advantage.csv", index=False)

    print(f"study 17-19 cohort: {total:,}\n")
    pw = pd.DataFrame(pw_rows)
    for sched in C.SCHEDULES:
        print(f"### schedule = {sched}  ({C.SCHEDULES[sched]['label']})")
        for mode in ["pt", "pt_plus_rail", "car"]:
            piv = (pw[(pw.schedule == sched) & (pw["mode"] == mode)]
                   .pivot(index="target", columns="threshold_min", values="cohort_share")
                   .reindex(["any_hei", "university", "regional_hei", "maynooth"]))
            print(f"  -- {mode} -- (% of cohort within N min, one-way)")
            print((piv * 100).round(0).astype("Int64").to_string().replace("\n", "\n     "))
        print()


if __name__ == "__main__":
    main()
