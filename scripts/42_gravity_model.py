"""Phase 4: PPML gravity model of county -> HEI new-entrant flows, per field.

Fits flow_ij ~ exp( b * friction_ij + g * home_ij + county FE + HEI FE ) by
Poisson pseudo-maximum-likelihood (the standard estimator for gravity flows;
robust to the many zero cells and to over-dispersion). The friction term is
swapped between car commute minutes, public-transport commute minutes and
straight-line distance, and the three fits are compared. A second specification
drops the county fixed effects so the county covariates (cohort size, share of
adults with a third-level qualification) can enter.

The commute/accessibility side is identical across fields (the drive to Maynooth
is the drive to Maynooth whatever the subject); only the flows change. The model
is run separately for each field so the friction coefficients can be compared.

Outputs:
  outputs/p4_model_fit.csv     one row per (field x friction x specification)
  outputs/p4_predictions.csv   field x county x HEI: actual, predicted, residual
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf

import config as C

POISSON = sm.families.Poisson()

FRICTIONS = {"car_min": "car commute minutes",
             "ptrail_min": "public-transport commute minutes",
             "km": "straight-line distance (km)"}
FIELDS = ["computing", "natural_sciences", "engineering", "business", "health",
          "arts", "social_science", "education"]
POOLED_YEAR = "2018/2019-2024/2025"


def build_panel(field: str) -> pd.DataFrame:
    flows = pd.read_csv(C.OUT / "p4_flows.csv")
    flows = flows[(flows["field"] == field) & (flows["year"] == POOLED_YEAR)]
    acc = pd.read_csv(C.OUT / "p4_county_hei.csv")
    cty = pd.read_csv(C.OUT / "p4_county.csv")
    p = (acc.merge(flows[["county", "hei", "n"]], on=["county", "hei"], how="left")
         .merge(cty[["county", "cohort_17_19", "third_level_share"]], on="county", how="left"))
    p["n"] = p["n"].fillna(0).astype(int)
    # an HEI with no flow at all in this field carries no information and blows up
    # the Poisson HEI fixed effect - drop it (only bites for Education, where DkIT
    # never appears; the other six fields keep all eight HEIs)
    p = p[p.groupby("hei")["n"].transform("sum") > 0].copy()
    p["field"] = field
    p["log_cohort"] = np.log(p["cohort_17_19"])
    for f in FRICTIONS:
        p[f + "_10"] = p[f] / 10.0
    return p


def fit(panel, friction, county_fe, null_llf):
    rhs = [f"{friction}_10", "home", "hei"]
    rhs += ["county"] if county_fe else ["log_cohort", "third_level_share"]
    m = smf.glm(f"n ~ {' + '.join(rhs)}", data=panel, family=POISSON).fit(cov_type="HC1")
    b = m.params[f"{friction}_10"]
    se = m.bse[f"{friction}_10"]
    pr2 = 1 - m.llf / null_llf
    base_rhs = ["home", "hei"] + (["county"] if county_fe else
                                  ["log_cohort", "third_level_share"])
    base = smf.glm(f"n ~ {' + '.join(base_rhs)}", data=panel, family=POISSON).fit()
    dev_drop = base.deviance - m.deviance                     # chi-sq, 1 df
    return dict(field=panel["field"].iloc[0], friction=friction,
                spec="county FE" if county_fe else "county covariates",
                coef_per10=round(b, 4), se=round(se, 4),
                pct_per10=round(100 * (np.exp(b) - 1), 1), z=round(b / se, 1),
                home_coef=round(m.params.get("home", np.nan), 3),
                loglik=round(m.llf, 1), aic=round(m.aic, 1),
                pseudo_r2=round(pr2, 3), dev_drop_vs_FE=round(dev_drop, 1), model=m)


def decay_halving(panel) -> float:
    """minutes of extra car commute that halve a county's share, from share ~ exp(a+b*car)."""
    tot = panel.groupby("county")["n"].transform("sum").clip(lower=1)
    share = panel["n"] / tot
    m = share > 0
    b, a = np.polyfit(panel.loc[m, "car_min"], np.log(share[m]), 1)
    return round(-0.6931 / b, 1)


def main() -> None:
    fit_rows, pred_parts, summ = [], [], []
    for field in FIELDS:
        panel = build_panel(field)
        null_llf = smf.glm("n ~ 1", data=panel, family=POISSON).fit().llf
        rows = [fit(panel, f, cfe, null_llf)
                for cfe in (True, False) for f in FRICTIONS]
        fit_rows += rows

        # predictions from the headline model (county FE + car minutes) and the km model
        preds = {fr: next(r["model"] for r in rows
                          if r["spec"] == "county FE" and r["friction"] == fr)
                 for fr in ("car_min", "km")}
        pred = panel[["field", "county", "hei", "n", "car_min",
                      "ptrail_min", "km", "home"]].copy()
        pred["predicted"] = preds["car_min"].predict(panel).round(1)
        pred["predicted_km"] = preds["km"].predict(panel).round(1)
        pred["residual"] = (pred["n"] - pred["predicted"]).round(1)
        pred["resid_pct"] = np.where(pred["predicted"] >= 1,
                                     (100 * pred["residual"] / pred["predicted"]).round(0),
                                     np.nan)
        pred_parts.append(pred)

        hd = next(r for r in rows if r["spec"] == "county FE" and r["friction"] == "car_min")
        summ.append(dict(field=field, car_pct=hd["pct_per10"], car_z=hd["z"],
                         car_dev=hd["dev_drop_vs_FE"], halving_min=decay_halving(panel),
                         n=int(panel["n"].sum()), zeros=f"{(panel['n'] == 0).mean():.0%}"))

    tab = pd.DataFrame(fit_rows).drop(columns=["model"])
    tab.to_csv(C.OUT / "p4_model_fit.csv", index=False)
    pd.concat(pred_parts, ignore_index=True).to_csv(C.OUT / "p4_predictions.csv", index=False)

    print("model fit (all fields):")
    print(tab.to_string(index=False))
    print("\nheadline (county FE + car minutes) by field:")
    print(pd.DataFrame(summ).to_string(index=False))

    print("\nMaynooth residuals (car model), by field and county:")
    allpred = pd.concat(pred_parts, ignore_index=True)
    mu = allpred[allpred.hei == "MU"].pivot_table(index="county", columns="field",
                                                  values="residual")
    print(mu.round(0).to_string())


if __name__ == "__main__":
    main()
