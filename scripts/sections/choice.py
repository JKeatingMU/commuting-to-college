"""Choice section: does accessibility predict where students enrol? County-scale PPML gravity
model of HEA new-entrant flows, eight ISCED fields. Two parts: the Choice branch (MAIN) and
"Where Maynooth departs from its geography" (MAIN_MU, shown in the Maynooth worked example).

Reads the p4_* outputs from scripts 40-42 and the CAO computing course list.
"""

from __future__ import annotations

import json

import geopandas as gpd
import numpy as np
import pandas as pd

import config as C

KEY = "choice"
COLS = ()   # reads nothing from the shared per-ED table

HEIS = ["MU", "DCU", "UCD", "TCD", "TU Dublin", "DkIT", "TUS", "SETU"]
COL = {"MU": "#05668d", "DCU": "#028090", "UCD": "#d85128", "TCD": "#5c4d7d",
       "TU Dublin": "#3f7d5f", "DkIT": "#9c4a86", "TUS": "#c98a2e", "SETU": "#3f8a6e"}
CAMPUS = {"MU": (-6.599, 53.382), "DCU": (-6.257, 53.386), "UCD": (-6.221, 53.309),
          "TCD": (-6.255, 53.344), "TU Dublin": (-6.279, 53.356),
          "DkIT": (-6.393, 54.006), "TUS": (-7.937, 53.423), "SETU": (-6.943, 52.834)}
FIELDS = ["computing", "natural_sciences", "engineering", "business", "health",
          "arts", "social_science", "education"]
FIELD_LABEL = {"computing": "Computing (ICT)",
               "natural_sciences": "Natural Sciences, Maths and Statistics",
               "engineering": "Engineering, Manufacturing and Construction",
               "business": "Business, Administration and Law",
               "health": "Health and Welfare",
               "arts": "Arts and Humanities",
               "social_science": "Social Sciences, Journalism and Information",
               "education": "Education"}
FIELD_SHORT = {"computing": "Computing", "natural_sciences": "Natural Sciences",
               "engineering": "Engineering", "business": "Business", "health": "Health",
               "arts": "Arts and Humanities", "social_science": "Social Sciences",
               "education": "Education"}
FIELD_COL = {"computing": "#d85128", "natural_sciences": "#028090", "engineering": "#7d6ca8",
             "business": "#c98a2e", "health": "#4a8f5b", "arts": "#b8556f",
             "social_science": "#4c7bb0", "education": "#9c7b3f"}

SVG_W, SVG_H = 620, 720
BB = (-8.10, 52.20, -5.95, 54.45)   # w,s,e,n


def _proj(lon, lat):
    w, s, e, n = BB
    return (round((lon - w) / (e - w) * SVG_W, 1), round((n - lat) / (n - s) * SVG_H, 1))


def _paths(geom):
    polys = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    out = []
    for poly in polys:
        for ring in [poly.exterior, *poly.interiors]:
            out.append("M" + " L".join(f"{x},{y}" for x, y in (_proj(*p) for p in ring.coords)) + "Z")
    return " ".join(out)


def _kildare_check() -> dict:
    """Census 2022 journey times in Kildare towns against the model (script 35): an independent check on the
    Maynooth residuals."""
    t = pd.read_csv(C.OUT / "p3_validation_towns.csv")
    t["diff"] = t["reported_min"] - t["model_mix"]
    k = t[t["county"] == "Kildare"]
    show = k[k["name"].isin(["Celbridge", "Leixlip", "Maynooth", "Naas"])].sort_values("diff", ascending=False)
    return {"mean": round(float(k["diff"].mean()), 1), "n": len(k),
            "towns": [[r.name, r.reported_min, r.model_mix] for r in show.itertuples()]}


def data() -> dict:
    cty_geo = gpd.read_file(C.PROC / "p4_counties.gpkg")
    pred = pd.read_csv(C.OUT / "p4_predictions.csv")
    cov = pd.read_csv(C.OUT / "p4_county.csv")
    fit = pd.read_csv(C.OUT / "p4_model_fit.csv")
    flows_all = pd.read_csv(C.OUT / "p4_flows.csv")

    tot = pred.groupby(["field", "county"])["n"].sum().rename("county_total").reset_index()
    pred = pred.merge(tot, on=["field", "county"])
    pred["share"] = (pred["n"] / pred["county_total"].clip(lower=1)).round(4)
    pred["pred_share"] = (pred["predicted"] / pred["county_total"].clip(lower=1)).round(4)

    counties = []
    for r in cty_geo.itertuples():
        cx, cy = _proj(*r.geometry.representative_point().coords[0])
        cc = cov[cov.county == r.county].iloc[0]
        counties.append({"name": r.county, "d": _paths(r.geometry), "cx": cx, "cy": cy,
                         "cohort": int(cc.cohort_17_19), "tl": round(float(cc.third_level_share), 3)})

    county_totals = {f: {} for f in FIELDS}
    cells = {f: {} for f in FIELDS}
    for r in pred.itertuples():
        cells[r.field].setdefault(r.county, {})[r.hei] = {
            "n": int(r.n), "pred": round(r.predicted, 1), "pred_km": round(r.predicted_km, 1),
            "resid": round(r.residual, 1), "share": r.share, "pred_share": r.pred_share,
            "car": round(r.car_min, 1), "pt": round(r.ptrail_min, 1), "km": round(r.km, 1),
            "home": int(r.home)}
        county_totals[r.field][r.county] = int(r.county_total)

    # Decay: share ~ exp(a + b*car) per field. A degenerate raw fit (b >= 0, as for Education,
    # where one far provider dominates) is flagged ok=False and left out of the decay chart and
    # the halving ranking. R-squared, slope z and a 95% band for the line are carried too.
    XMAX = int(np.ceil(pred["car_min"].max() / 20) * 20)
    decay = {}
    for f in FIELDS:
        sub = pred[pred.field == f]
        sc = sub[sub["share"] > 0]
        x = sc["car_min"].to_numpy(float)
        ylog = np.log(sc["share"].to_numpy(float))
        b, a = np.polyfit(x, ylog, 1)
        ok = bool(b < 0)
        resid = ylog - (a + b * x)
        n = len(x)
        resid_sd = float(np.sqrt((resid ** 2).sum() / (n - 2)))
        xbar = float(x.mean())
        sxx = float(((x - xbar) ** 2).sum())
        slope_se = resid_sd / np.sqrt(sxx)
        r2 = float(1 - (resid ** 2).sum() / ((ylog - ylog.mean()) ** 2).sum())
        band = []
        for xv in range(0, XMAX + 1, 4):
            se = resid_sd * np.sqrt(1 / n + (xv - xbar) ** 2 / sxx)
            band.append([xv, round(float(np.exp(a + b * xv - 1.96 * se)), 5),
                         round(float(np.exp(a + b * xv + 1.96 * se)), 5)])
        decay[f] = {"a": round(float(a), 4), "b": round(float(b), 5), "ok": ok,
                    "halving_min": int(round(-0.6931 / b)) if ok else None,
                    "r2": round(r2, 2), "n": n, "slope_z": round(float(b / slope_se), 1),
                    "band": band,
                    "pts": [[round(p.car_min, 1), round(p.share, 4), p.hei, p.county]
                            for p in sub.itertuples() if p.share > 0]}

    fieldstat = {}
    for f in FIELDS:
        row = lambda fr: fit[(fit.field == f) & (fit.spec == "county FE") & (fit.friction == fr)].iloc[0]
        hd, km, pt = row("car_min"), row("km"), row("ptrail_min")
        pooled = flows_all[(flows_all.field == f) & (flows_all.year == "2018/2019-2024/2025")]
        fieldstat[f] = {
            "label": FIELD_LABEL[f], "short": FIELD_SHORT[f], "col": FIELD_COL[f],
            "car_pct": float(hd.pct_per10), "car_z": float(hd.z), "car_dev": float(hd.dev_drop_vs_FE),
            "km_pct": float(km.pct_per10), "km_dev": float(km.dev_drop_vs_FE),
            "pt_pct": float(pt.pct_per10), "pt_dev": float(pt.dev_drop_vs_FE),
            "halving": decay[f]["halving_min"], "decay_ok": decay[f]["ok"],
            "n": int(pooled["n"].sum()),
            "zeros": round(100 * (pred[pred.field == f]["n"] == 0).mean()),
            "by_hei": {h: int(pooled[pooled.hei == h]["n"].sum()) for h in HEIS},
        }
        shares = np.array([fieldstat[f]["by_hei"][h] for h in HEIS], float)
        fieldstat[f]["hhi"] = round(float(((shares / shares.sum()) ** 2).sum()), 3)
    cost = pd.read_csv(C.OUT / "p4_cost_check.csv").set_index("field")
    for f in FIELDS:
        fieldstat[f]["cost_pct"] = float(cost.loc[f, "pct_per100eur"])
        fieldstat[f]["cost_dev"] = float(cost.loc[f, "dev_drop"])

    return {
        "svg": {"w": SVG_W, "h": SVG_H},
        "heis": HEIS, "col": COL, "fields": FIELDS,
        "campuses": {h: _proj(*CAMPUS[h]) for h in HEIS},
        "counties": counties, "countyTotals": county_totals, "cells": cells,
        "courses": json.loads((C.RAW / "cao-computing-courses-2025-20260827.json").read_text()),
        "fit": fit.to_dict("records"), "fieldstat": fieldstat, "decay": decay,
        "kildare": _kildare_check(),
        "cost_r_km": float(pd.read_csv(C.OUT / "p4_cost_check.csv")["r_cost_km"].iloc[0]),
        "meta": {"n_counties": len(counties), "n_heis": len(HEIS), "n_cells": int(len(pred)),
                 "total_flows": int(pred["n"].sum()), "years": "2018/19 to 2024/25",
                 "decay_xmax": XMAX},
    }


CSS = """
  .sec-choice .key{background:var(--surface-alt);border-left:3px solid var(--coral);border-radius:0 8px 8px 0;padding:.85rem 1.1rem;margin:1.1rem 0;font-size:.95rem}
  .sec-choice .key b{color:var(--ink)}
  .sec-choice .summary{background:var(--surface);border:1px solid var(--hair-strong);border-top:3px solid var(--navy);border-radius:8px;padding:1.1rem 1.3rem 1.2rem;margin:.6rem 0 1.6rem}
  .sec-choice .summary h3{margin:0 0 .5rem}
  .sec-choice .summary p{margin:.5rem 0}
  .sec-choice .summary ul{margin:.6rem 0 0;padding-left:1.2rem}
  .sec-choice .summary li{margin:.55rem 0;font-size:.95rem}
  .sec-choice .summary li::marker{color:var(--navy)}
  .sec-choice .summary b{color:var(--ink)}
  .sec-choice tr.mu td{background:var(--surface-alt);font-weight:600}
  .sec-choice tr.grouptop td{border-top:2px solid var(--hair-strong)}
  .sec-choice .mono{font-family:"IBM Plex Mono",monospace}
  .sec-choice svg.fig{width:100%;height:auto;display:block;background:var(--surface);border:1px solid var(--hair);border-radius:10px;margin:1rem auto}
  .sec-choice svg.fig.decay{max-width:940px}
  .sec-choice .fig text{fill:var(--muted);font-size:11px}
  .sec-choice .fig .axl{fill:var(--faint);font-size:10px}
  .sec-choice .fig .grid{stroke:var(--hair)}
  .sec-choice .cap{font-size:.8rem;color:var(--faint);margin:-.4rem 0 1rem;text-align:left}
  .sec-choice .p-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(300px,1fr);gap:1.1rem;margin-top:.6rem;align-items:start}
  @media (max-width:800px){.sec-choice .p-grid{grid-template-columns:1fr}}
  .sec-choice .mapcard{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:.4rem}
  .sec-choice .sidecard{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:.9rem 1rem}
  .sec-choice .sidecard h3{margin:0 0 .1rem;font-size:.95rem}
  .sec-choice .sidecard .sub{font-size:.78rem;color:var(--faint);margin:0 0 .5rem}
  .sec-choice .legend{display:flex;gap:.3rem .9rem;flex-wrap:wrap;font-size:.75rem;color:var(--muted);margin:.3rem 0}
  .sec-choice .legend span{display:inline-flex;align-items:center;gap:.3rem}
  .sec-choice .legend i{width:10px;height:10px;border-radius:2px}
  .sec-choice .barrow{display:grid;grid-template-columns:9rem 1fr 5.5rem;gap:.6rem;align-items:center;margin:.5rem 0;font-size:.9rem}
  .sec-choice .barrow .bt{background:var(--surface-alt);border-radius:4px;height:1.25rem;position:relative;overflow:hidden}
  .sec-choice .barrow .bf{position:absolute;left:0;top:0;bottom:0;border-radius:4px}
  .sec-choice .barrow .bv{font-variant-numeric:tabular-nums;text-align:right;color:var(--muted)}
  .sec-choice path.county{cursor:pointer}
  .sec-choice #p-sTbl th,.sec-choice #p-sTbl td{padding:.32rem .4rem;font-size:.8rem}
  .sec-choice #p-sTbl tr[data-h]:hover td{background:var(--surface-alt)}
  .sec-choice #p-caseTbl td{white-space:normal;vertical-align:top;font-size:.84rem;line-height:1.45}
  .sec-choice #p-caseTbl td:first-child{width:12rem}
  .sec-choice #p-sCourses table{margin-top:.2rem}
  .sec-choice #p-sCourses td{padding:.22rem .35rem;border-bottom:1px solid var(--hair)}
  .methods .eq{font-family:"IBM Plex Mono",monospace;font-size:.82rem;background:var(--surface-alt);padding:.55rem .7rem;border-radius:6px;margin:.5rem 0;overflow-x:auto;white-space:nowrap;text-align:left}
  .methods dl{margin:.4rem 0}
  .methods dt{font-weight:700;color:var(--ink);margin-top:.5rem}
  .methods dd{margin:.1rem 0 0}
"""

MAIN = """
<div class="summary" id="p-summary"></div>

<p>The flows are Higher Education Authority new-entrant counts by county of domicile and institution,
  undergraduate, 2018/19 to 2024/25, pooled, for each field of study in turn. The accessibility figures are
  the study's commute model aggregated to county, cohort-weighted, and are the same for every field (the
  drive to Maynooth is the drive to Maynooth whatever the subject). The region is the twelve counties of the
  study area (the four Dublin council areas count as one, as they do in the HEA data), with eight HEIs:
  Maynooth, DCU, UCD, Trinity, TU&nbsp;Dublin, Dundalk&nbsp;IT, TU&nbsp;Shannon and SETU.</p>
<p class="key"><b>Read this as a first look, not a finding.</b> County is a coarse unit: Dublin is a single
  cell hiding everything inside the M50, and a large county straddles several commute bands. Field-level
  flows from small counties are thin and the HEA rounds every figure to the nearest 5. The model is
  cross-sectional, so it cannot separate the commute from everything correlated with it (course reputation,
  points, the pull of a home-county campus). What it can do is show whether the commute carries signal,
  whether that signal is the same size in every field, and where an institution's recruitment sits above or
  below what its geography would predict.</p>
<p class="key" style="border-left-color:var(--navy)"><b>Domicile is not term-time address.</b> The flows
  and the commute are both keyed to the student's <i>home</i> county. But a large share of students
  relocate: the Eurostudent&nbsp;VIII survey (Ireland, 2022) found about 45% living with parents, 19% in
  student accommodation and 36% in the private rented sector, so roughly <b>half live away from home during
  term</b>. Relocation rises with distance and is more common at the nationally recruiting universities. For
  those students the daily commute is far shorter than their county of domicile suggests, which makes
  commute friction look like a <i>weaker</i> deterrent here than it is for the students who genuinely
  commute from home. The true commuter-only decay is likely steeper than the figures below. Separating the
  two needs a student-level record with both addresses (see <a href="#choice/p-sharpen">How to sharpen the
  answer</a>).</p>

<h2 id="p-does">Does the commute predict the choice?</h2>
<p id="p-fitAnswer" class="lead"></p>
<p>The test is a <b>gravity model</b> of the flows, run separately for each field. It asks: within a single
  county, once you account for how big that county's cohort is and how large and well-known each HEI is, do
  more of its students in that field end up at the HEIs that are easier to reach? Each row of the table below
  is one run of that model: for a given field, using a given measure of the commute (car time,
  public-transport time, or straight-line distance), with a fixed effect for the county. What you are looking
  for is whether the commute column comes out negative, whether it is large enough to matter, and whether it
  is beyond the reach of chance.</p>
<div class="panel scroll"><table id="p-fitTbl"></table></div>
<p class="cap"><b>Per&nbsp;10</b>: the change in a county's flow to an HEI for ten more minutes of commute
  (or ten more km), holding the county and the HEI fixed. A negative number means a longer commute goes with
  fewer students. <b>z</b>: how many standard errors the estimate sits from zero; above about 2 is "unlikely
  to be chance". <b>Deviance drop</b>: how much better the model fits once the commute term is added, on top
  of the county and HEI controls; above about 11 is significant at p&nbsp;&lt;&nbsp;0.001, and it is the fair
  way to compare the commute measures. <b>AIC</b>: overall model quality with a penalty for complexity; lower
  is better. The table shows the county-fixed-effects specification; a second specification that swaps the
  fixed effect for two plain county variables gives the same pattern with slightly smaller effects in most fields (see the
  methods).</p>
<p id="p-fitProse"></p>

<h2 id="p-field">Why the field matters</h2>
<p>The commute bites in all eight fields, but not by exactly the same amount. The bars below compare its size
  field by field; the text after them asks whether the differences mean anything.</p>
<div id="p-fieldBars"></div>
<p class="cap" id="p-fieldBarsCap"></p>
<p id="p-fieldProse"></p>

<h2 id="p-decay">The decay of choice with distance</h2>
<p>Each coloured line is an exponential fit for one field: how a county's share of new entrants going to an
  HEI falls as the car commute to it grows. The grey cloud behind is every individual county-HEI point. A
  steeper line is a field where the commute matters more.</p>
<div class="legend" id="p-decayLg"></div>
<svg class="fig decay" id="p-decayFig" viewBox="0 0 760 380"></svg>
<p class="cap" id="p-decayCap"></p>
<p id="p-decayConf"></p>

<h2 id="p-county">County by county</h2>
<p class="note">Pick a field, an HEI and what to shade. Click a county to open its panel; for Computing you
  can then click an HEI row to see its course list and 2025 points. What "computing" means differs sharply by
  HEI: the universities offer it through a handful of broad codes (Maynooth 4, DCU 3, Trinity 2, UCD 1), the
  technological sector through many named ones (TU&nbsp;Dublin 18, TU&nbsp;Shannon 20, SETU 18, Dundalk 6).</p>
<div class="controls">
  <label>Field <select id="p-mField"></select></label>
  <label>HEI <select id="p-mHei"></select></label>
  <label>Show <select id="p-mView">
    <option value="share">Actual share of the county's entrants in this field</option>
    <option value="car">Car commute to this HEI</option>
    <option value="resid">Model residual (actual minus predicted)</option>
  </select></label>
</div>
<div class="p-grid">
  <div class="mapcard">
    <svg class="fig" id="p-map" style="margin:0;border:none" viewBox="0 0 620 720"></svg>
    <div class="legend" id="p-mapLg"></div>
  </div>
  <div class="sidecard">
    <h3 id="p-sT">Click a county</h3><div class="sub" id="p-sS">its cohort and where its students in this field go</div>
    <div class="scroll"><table id="p-sTbl"><tbody></tbody></table></div>
    <div id="p-sCourses"></div>
  </div>
</div>
<p class="cap" id="p-mapCap" style="margin-top:.9rem">Click a county to open its panel.</p>

<h2 id="p-sharpen">How to sharpen the answer</h2>
<p>This analysis gives a strong, consistent association and shows where it matters. It is a first look, held
  back by four specific limits. Each can be lifted with a bounded, well-defined data request, and each lift
  has a concrete payoff. <b>This section doubles as the rationale for making those requests.</b> The analysis
  pipeline is already built, tested and documented; the data is the only missing piece.</p>
<div class="panel scroll"><table id="p-caseTbl">
  <thead><tr><th class="l">Data addition</th><th class="l">Removes</th><th class="l">Enables</th></tr></thead>
  <tbody>
    <tr><td class="l"><b>Eircode routing key</b> in place of county</td>
      <td class="l">Dublin as one cell; large counties spanning several commute bands</td>
      <td class="l">A recruitment target list of named districts, not a county; far tighter estimates</td></tr>
    <tr><td class="l"><b>Home <i>and</i> term-time address</b> per student</td>
      <td class="l">Commuters and relocators mixed together</td>
      <td class="l">The true deterrent for daily commuters; the size of the addressable "study locally" market</td></tr>
    <tr><td class="l"><b>Individual records</b> plus a socio-economic marker</td>
      <td class="l">County averages; time and money inseparable</td>
      <td class="l">A proper choice model; a direct test of whether the commute is a bigger barrier for lower-income students</td></tr>
    <tr><td class="l"><b>Year-by-year</b> counts, not pooled</td>
      <td class="l">Any trend hidden</td>
      <td class="l">Whether commute sensitivity is rising with the cost of living and study-from-home norms</td></tr>
  </tbody></table></div>

<h3>1. Finer geography: the Eircode routing key</h3>
<p><b>The gap.</b> County is coarse. Dublin is a single cell that hides everything inside the M50; Kildare
  spans a twenty-minute Maynooth commute in the north and an hour in the south. The friction coefficient is
  estimated from twelve county averages.</p>
<p><b>The fix, and what it buys.</b> Resolving flows to Eircode routing key (the first three characters, about
  140 non-identifying districts) turns Dublin into roughly thirty cells and splits every large county into
  commute bands. The commute term would then be identified from real within-city and within-county
  variation, and the standard errors would fall sharply. "Maynooth under-recruits Wicklow"
  becomes "Maynooth under-recruits these named districts, where its commute advantage is largest and its
  enrolment share is smallest": a targeting list, not a county.</p>
<p><b>The ask.</b> The HEA's student data already holds domicile at Eircode level. A research extract of
  new-entrant counts by <i>routing key by institution by field by year</i>, with small cells suppressed at
  source, is aggregate statistics and never leaves as identifiable data. Request through
  <span class="mono">statistics@hea.ie</span>.</p>

<h3>2. Both addresses: home and term-time</h3>
<p><b>The gap.</b> The flows and the commute are both keyed to the student's <i>home</i> address. About half
  of Irish higher-education students live away from home during term. For a relocating student the daily
  commute is nothing like the distance from home, so the model <i>understates</i> the deterrent for the
  students who genuinely commute, and cannot tell the two groups apart.</p>
<p><b>The fix, and what it buys.</b> A student record carrying <i>both</i> a home address and a term-time
  address splits the population into daily commuters and relocators. The commute model then applies to the
  right people, and the true commuter-only decay can be measured directly. It answers the question a
  recruitment strategy actually needs: of the Kildare and Wicklow students Maynooth is missing, how many
  would commute daily if they enrolled, and are therefore reachable with a "study locally" message, and how
  many were always going to move away? The first group is the addressable market.</p>
<p><b>The ask.</b> Maynooth's own student records hold term-time address. An internal research extract of
  <i>home routing key plus term-time routing key plus course plus year</i>, aggregated with small-cell
  suppression, handled as a research request through the Data Protection Office. This is not a Freedom of
  Information request against your own institution.</p>

<h3>3. Individual records and a socio-economic marker</h3>
<p><b>The gap.</b> County aggregates cannot support a proper choice model or separate the effects that travel
  with distance: points, school type, family background, the pull of a home-county campus. And because cost
  and distance are almost perfectly correlated at county scale, the analysis cannot say whether it is
  <i>time</i> or <i>money</i> that deters, which is the equity question. This matters more now: from January
  2027 the Young Adult and Student public-transport fare rises about 15%, the first broad increase since
  2018, so the money side of the commute is growing against a cost-of-living backdrop.</p>
<p><b>The fix, and what it buys.</b> Individual new-entrant records allow a destination-choice model with
  student-level controls, much tighter estimates, and an interaction between commute cost and a
  socio-economic indicator: HEAR or DARE status, school DEIS band, or the Pobal deprivation index for the
  student's area. That gives a direct test of whether the commute is a bigger barrier for lower-income
  students, the finding that would justify a commuter bursary, targeted transport support or a "study
  locally" access initiative with evidence rather than assumption.</p>
<p><b>The ask.</b> The same HEA or records-office extract as items 1 and 2, at individual rather than
  aggregate level, with the socio-economic marker attached and direct identifiers removed before release.</p>

<h3>4. Year by year, not pooled</h3>
<p><b>The gap.</b> Seven years are pooled to make the county-by-HEI counts large enough to model, which hides
  any trend.</p>
<p><b>The fix, and what it buys.</b> The finer geography in item 1 makes single-year cells large enough to
  keep separate. That shows whether commute sensitivity is rising. With cost-of-living pressure and the
  post-pandemic normalisation of studying from home, this is the difference between a stable background
  factor and a growing one that policy needs to act on now.</p>

<h3>The return</h3>
<p id="p-caseReturn"></p>
<p>For the sector, the same data quantifies how much geography shapes who reaches higher education, and where
  new provision or better regional transport would most widen participation. None of this requires new
  fieldwork or new methods. The pipeline that produced this report runs on the finer data unchanged; only
  the extract is outstanding.</p>
"""

MAIN_MU = """
<h2 id="p-mu">Where Maynooth departs from its geography</h2>
<p id="p-muProse"></p>
<div class="panel scroll"><table id="p-muTbl"></table></div>
<p class="cap" style="margin-top:.6rem">Residual from the county-fixed-effects model with car commute minutes
  as the friction term, one column per field. Positive (teal) means Maynooth recruits more students in that
  field from that county than its cohort size, the county's other options and the commute predict; negative
  (coral) means fewer. Counties are ordered by the Computing residual; &#8962; marks the home county. Treat
  the exact numbers as indicative, given the pooled counts and the rounding to the nearest five.</p>
"""

STANDALONE_MAIN = MAIN + MAIN_MU

JS = r"""
SECTIONS.choice = (() => {
  let D = null;
  const data = () => D || (D = APP.json("d-choice"));
  const FL = {computing:"Computing", natural_sciences:"Natural Sciences", engineering:"Engineering",
    business:"Business", health:"Health", arts:"Arts and Humanities", social_science:"Social Sciences",
    education:"Education"};

  // fields the data measure cleanly: the commute term well clear of chance (|z| >= 6)
  const clean = D => D.fields.filter(f => Math.abs(D.fieldstat[f].car_z) >= 6);
  const weak = D => D.fields.filter(f => Math.abs(D.fieldstat[f].car_z) < 6);
  const words = n => ["no", "one", "two", "three", "four", "five", "six", "seven", "eight"][n] || String(n);
  const listOf = a => a.length < 2 ? a.join("") : a.slice(0, -1).join(", ") + " and " + a[a.length - 1];
  const pcRange = (D, key, fs) => { const v = fs.map(f => Math.abs(D.fieldstat[f][key]));
    return [Math.round(Math.min(...v)), Math.round(Math.max(...v))]; };
  const bestBy = D => { const c = {}; for (const f of D.fields) {
      const b = D.fit.filter(r => r.field === f && r.spec === "county FE").sort((a, b) => a.aic - b.aic)[0].friction;
      c[b] = (c[b] || 0) + 1; } return c; };
  // Maynooth's residual pattern by county, from the headline model
  function muPattern(D){
    const big = D.fields.filter(f => f !== "education");
    const res = c => Object.fromEntries(big.map(f => [f, ((D.cells[f][c] || {}).MU || {}).resid]));
    const counties = D.counties.map(c => c.name);
    const under = counties.filter(c => big.every(f => res(c)[f] == null || res(c)[f] < 0));
    const fewer = c => big.filter(f => res(c)[f] != null && res(c)[f] <= -10);
    const more = c => big.filter(f => res(c)[f] != null && res(c)[f] >= 10);
    const tot = c => big.reduce((s, f) => s + (res(c)[f] || 0), 0);
    const over = counties.filter(c => more(c).length >= 3 && tot(c) > 0).sort((a, b) => tot(b) - tot(a));
    return {big, res, under, fewer, more, over};
  }

  // which commute measure fits best in each field (county FE, by AIC), described from the results
  function ranking(D){
    const NM = {km: "straight-line distance", car_min: "car time", ptrail_min: "public-transport time"};
    const std = ["car_min", "km", "ptrail_min"], odd = [];
    for (const f of D.fields) {
      const order = D.fit.filter(r => r.field === f && r.spec === "county FE").sort((a, b) => a.aic - b.aic).map(r => r.friction);
      if (order.join() !== std.join()) odd.push(`${FL[f]} (${order.map(k => NM[k]).join(", then ")})`);
    }
    const n = D.fields.length - odd.length, words = ["no", "one", "two", "three", "four", "five", "six", "seven", "eight"];
    return `In ${words[n] || n} of the ${words[D.fields.length]} fields <b>car time</b> fits best, <b>straight-line distance</b> is
      next and <b>public-transport time</b> is weakest` + (odd.length ? `; the exception${odd.length > 1 ? "s are" : " is"} ${odd.join(" and ")}` : "") + ".";
  }

  function init(root){
    const D = data(), $ = s => root.querySelector(s);
    if ($("#p-summary")) summary(D, $);
    if ($("#p-fitTbl")) { fitTable(D, $); fieldBars(D, $); decayChart(D, $); countyMap(D, $); caseReturn(D, $); }
    if ($("#p-muTbl")) muTable(D, $);
  }

  function summary(D, $){
    const fs = D.fieldstat, Cl = clean(D), [lo, hi] = pcRange(D, "car_pct", Cl);
    const top = Cl.reduce((a, b) => Math.abs(fs[b].car_pct) > Math.abs(fs[a].car_pct) ? b : a);
    const [rlo, rhi] = pcRange(D, "car_pct", Cl.filter(f => f !== top));
    const bb = bestBy(D), M = muPattern(D), kf = M.fewer("Kildare");
    $("#p-summary").innerHTML = `<h3>The short answer</h3>
    <p><b>Yes. Where students can study a subject close to home, most of them do.</b> Across the ${words(Cl.length)} fields
    the data measure cleanly, an HEI that is ten more minutes away by car draws roughly <b>${lo}% to ${hi}% fewer</b> of a
    county's entrants than one ten minutes closer, once the size of the county and the size and standing of each HEI are
    held constant. The effect is far beyond chance in every case.</p>
    <ul>
      <li><b>The commute matters in every field, most in ${FL[top]}</b> (${Math.abs(fs[top].car_pct)}% per ten minutes);
      in the others it is broadly similar, ${rlo}% to ${rhi}%. How long the drive takes predicts the pattern best (the
      best-fitting measure in ${words(bb.car_min || 0)} of the ${words(D.fields.length)} fields); public-transport
      reachability predicts it least.</li>
      <li><b>Maynooth recruits against its own geography in places.</b> It takes fewer students than its commute predicts
      from <b>${listOf(M.under)}</b> in every field it competes in${kf.length ? `, and from <b>Kildare</b>, its own county,
      in ${listOf(kf.map(f => FL[f]))}` : ""}; it takes more than predicted from <b>${listOf(M.over)}</b>. The
      <a href="#maynooth/p-mu">worked example</a> sets this out county by county.</li>
      ${top === "computing" ? `<li><b>Computing is the most commute-exposed field</b>, so it is the part of any HEI's
      offering most vulnerable to a nearer competitor opening a course.</li>` : ""}
      <li><b>Read the numbers as a first look, not a verdict.</b> This is county-scale, it uses the student's home address
      rather than where they live in term, and it cannot prove the commute <i>causes</i> the choice. It shows a strong,
      consistent association and points to where a finer study should look.</li>
    </ul>`;
  }

  function fitTable(D, $){
    let h = `<thead><tr><th class="l">Field</th><th class="l">Friction</th><th>Per 10</th><th>z</th><th>Deviance drop</th><th>AIC</th></tr></thead><tbody>`;
    const nm = {car_min:"Car commute minutes", ptrail_min:"Public-transport minutes", km:"Straight-line km"};
    for (const f of D.fields) {
      D.fit.filter(r => r.field === f && r.spec === "county FE").forEach((r, i) => {
        h += `<tr class="${i === 0 ? "grouptop" : ""}"><td class="l">${i === 0 ? FL[f] : ""}</td><td class="l">${nm[r.friction]}</td>` +
          `<td class="mono" style="color:${r.pct_per10 < 0 ? "var(--coral)" : "var(--teal)"}">${r.pct_per10 > 0 ? "+" : ""}${r.pct_per10}%</td>` +
          `<td class="mono">${r.z}</td><td class="mono">${r.dev_drop_vs_FE}</td><td class="mono">${r.aic}</td></tr>`;
      });
    }
    $("#p-fitTbl").innerHTML = h + "</tbody>";
    const fs = D.fieldstat, byCar = [...D.fields].sort((a, b) => fs[a].car_pct - fs[b].car_pct);
    const top = fs[byCar[0]], bot = fs[byCar[byCar.length - 1]];
    $("#p-fitAnswer").innerHTML = `<b>Yes, in every field.</b> In every version of the model the commute term is
      negative and far beyond chance: within a county, the HEIs that are harder to reach get fewer of that county's
      students. On the headline measure, ten more minutes by car is worth between <b>${Math.abs(bot.car_pct)}% fewer</b>
      entrants (${bot.short}) and <b>${Math.abs(top.car_pct)}% fewer</b> (${top.short}), holding the county and the HEI
      fixed. The commute matters most for ${top.short} and least for ${bot.short}; the next section looks at why.`;
    const W = weak(D);
    $("#p-fitProse").innerHTML = `<b>How the table gets there.</b> Read down the "Per&nbsp;10" column: it is negative in
      every row, so a longer commute always goes with a smaller flow. Read the "z" column: the values are well past 2, so
      none of this is a fluke of a small sample. Read the "deviance drop": adding the commute improves the fit by hundreds
      to thousands of points on one degree of freedom, when about 11 would already be conclusive, so the commute explains
      a real part of the pattern that the county and HEI controls cannot. That holds for every field${W.length ? `, though
      ${listOf(W.map(f => FL[f]))} ${W.length > 1 ? "are" : "is"} much weaker (deviance drop ${listOf(W.map(f => fs[f].car_dev))},
      z ${listOf(W.map(f => fs[f].car_z))}): the HEA's institute breakdown for Education omits Marino and Hibernia, and its
      two largest in-data providers are outside the region (see the methods), so read the exact numbers with caution` : ""}.<br><br>
      <b>Which measure of the commute matters most.</b> Within each field, comparing the three rows by deviance drop and AIC.
      ${ranking(D)} Choices track how long the drive takes a little more closely than straight-line distance, and both more
      closely than public-transport reachability. The headline figures use <b>car time</b>, the best fit and the
      accessibility measure this study is built on. The annual <i>financial cost</i> of the commute was also tried as a
      fourth measure: at county scale it moves almost in step with distance (correlation ${D.cost_r_km}) and fits less
      well than drive time in every field, so it cannot separate time from money; it is discussed in the methods.`;
  }

  function fieldBars(D, $){
    const fs = D.fields.map(f => D.fieldstat[f]).sort((a, b) => Math.abs(b.car_pct) - Math.abs(a.car_pct));
    const mx = Math.max(...fs.map(s => Math.abs(s.car_pct)));
    $("#p-fieldBars").innerHTML = fs.map(s => `<div class="barrow"><div class="l">${s.short}</div>` +
      `<div class="bt"><div class="bf" style="width:${Math.abs(s.car_pct) / mx * 100}%;background:${s.col}"></div></div>` +
      `<div class="bv">${s.car_pct}%</div></div>`).join("");
    const F = D.fieldstat, Cm = F.computing, N = F.natural_sciences, B = F.business, H = F.health, A = F.arts, S = F.social_science;
    const rank = [...D.fields].filter(f => F[f].decay_ok).sort((a, b) => F[a].halving - F[b].halving)
      .map(f => `${F[f].short} ${F[f].halving}&nbsp;min`);
    $("#p-fieldBarsCap").innerHTML = `Percentage change in a county's flow to an HEI per ten extra minutes of car
      commute, headline model. Every field is negative. The implied "halving distance" (extra car minutes that cut a
      county's share to an HEI in half), shortest first: ${rank.join(", ")}. (Education is left out here: its raw
      share-against-distance curve is degenerate because one provider, DCU, takes most of every county's intake
      regardless of distance.) The halving distances come from the raw curves, which do not hold county and HEI size
      constant, so they can order the fields differently from the bars.`;
    const Cl = clean(D), top = Cl.reduce((a, b) => Math.abs(F[b].car_pct) > Math.abs(F[a].car_pct) ? b : a);
    const others = Cl.filter(f => f !== top), [olo, ohi] = pcRange(D, "car_pct", others);
    const xs = Cl.map(f => F[f].hhi), ys = Cl.map(f => Math.abs(F[f].car_pct));
    const xm = xs.reduce((a, b) => a + b) / xs.length, ym = ys.reduce((a, b) => a + b) / ys.length;
    const r = xs.reduce((s, x, i) => s + (x - xm) * (ys[i] - ym), 0) /
      Math.sqrt(xs.reduce((s, x) => s + (x - xm) ** 2, 0) * ys.reduce((s, y) => s + (y - ym) ** 2, 0));
    const spread = Cl.slice().sort((a, b) => F[a].hhi - F[b].hhi)[0];
    $("#p-fieldProse").innerHTML = `<b>The differences between fields are smaller than they first look.</b> ${FL[top]} stands
      out at ${Math.abs(F[top].car_pct)}% per ten minutes; the other ${words(others.length)} well-measured fields lie between
      ${olo}% and ${ohi}%. A natural explanation for any difference is how widely each field is taught: where a near
      substitute always exists, a few extra minutes should be decisive. The data do not bear that out. Measured by how
      concentrated each field's entrants are across the eight HEIs, the more widely taught fields are not consistently the
      steeper ones (the correlation between concentration and the size of the effect is ${r.toFixed(2)}, ${Math.abs(r) < 0.4 ?
      "weak" : "moderate"}${r > 0 ? " and the wrong way round" : ""}), and ${FL[spread]}, the most
      evenly spread field, is among the gentler ones. Why ${FL[top]} is steepest is an open question. One candidate:
      computing is offered through many similar course codes across the technological sector (TU&nbsp;Dublin 18,
      TU&nbsp;Shannon 20, SETU 18, against the universities' handful), so a student can trade one for a shorter trip more
      easily than a named university programme.<br><br>
      <b>Education</b> is included for completeness but is the weakest fit of all eight. The HEA institute breakdown for
      this field <b>omits Marino and Hibernia entirely</b> (both linked colleges, together a few hundred primary-teaching
      entrants a year), and the two largest providers that do appear, Mary Immaculate College and the University of
      Limerick, are outside the twelve-county study region and so are not modelled. What is left within reach is
      <b>DCU</b> (which absorbed St&nbsp;Patrick's, Mater&nbsp;Dei and the Church of Ireland college and now dominates,
      ${F.education.by_hei.DCU.toLocaleString("en-IE")} pooled entrants) against Maynooth's Froebel primary programme
      (${F.education.by_hei.MU.toLocaleString("en-IE")}) and little else, so ${F.education.zeros}% of the cells are zero.
      The commute coefficient (${F.education.car_pct}%) is negative but the fit carries far less weight than the other
      fields.<br><br>
      For an institution the read is direct: its recruitment in ${FL[top]} is the most exposed to the commute, and the
      most vulnerable to a nearer competitor opening a course. The <a href="#maynooth/p-mu">worked example</a> shows how
      one institution's recruitment departs from what the commute predicts.`;
  }

  function decayChart(D, $){
    const W = 760, H = 380, L = 54, R = 14, T = 16, B = 42, xmax = D.meta.decay_xmax;
    const X = v => L + v / xmax * (W - L - R);
    const Yl = v => H - B - (Math.log(Math.max(v, .004)) - Math.log(.004)) / (0 - Math.log(.004)) * (H - B - T);
    let g = "";
    [1, .5, .25, .1, .05, .02, .01].forEach(v => { g += `<line class="grid" x1="${L}" y1="${Yl(v)}" x2="${W-R}" y2="${Yl(v)}"/>` +
      `<text class="axl" x="${L-6}" y="${Yl(v)+3}" text-anchor="end">${v*100}%</text>`; });
    for (let v = 0; v <= xmax; v += 20) g += `<text class="axl" x="${X(v)}" y="${H-B+14}" text-anchor="middle">${v}</text>`;
    g += `<text class="axl" x="${(L+W-R)/2}" y="${H-6}" text-anchor="middle">car commute to the HEI, minutes</text>`;
    g += `<text class="axl" transform="translate(12,${(T+H-B)/2}) rotate(-90)" text-anchor="middle">share of the county's entrants in the field</text>`;
    for (const f of D.fields) for (const [x, y] of D.decay[f].pts)
      g += `<circle cx="${X(x)}" cy="${Yl(y)}" r="1.6" fill="var(--faint)" fill-opacity="0.16"/>`;
    const ok = D.fields.filter(f => D.fieldstat[f].decay_ok);
    for (const f of ok) {
      const bnd = D.decay[f].band;
      const up = bnd.map(p => `${X(p[0])},${Yl(p[2])}`).join(" "), dn = bnd.slice().reverse().map(p => `${X(p[0])},${Yl(p[1])}`).join(" ");
      g += `<polygon points="${up} ${dn}" fill="${D.fieldstat[f].col}" fill-opacity="0.13" stroke="none"/>`;
    }
    for (const f of ok) {
      const dc = D.decay[f]; let d = "";
      for (let x = 0; x <= xmax; x += 4) d += (d ? "L" : "M") + X(x) + "," + Yl(Math.exp(dc.a + dc.b * x)) + " ";
      g += `<path d="${d}" fill="none" stroke="${D.fieldstat[f].col}" stroke-width="2.4"/>`;
    }
    $("#p-decayFig").innerHTML = g;
    $("#p-decayLg").innerHTML = ok.map(f => { const d = D.decay[f];
      return `<span><i style="background:${D.fieldstat[f].col}"></i>${D.fieldstat[f].short} (halves every ${d.halving_min} min; R&sup2; ${d.r2}, slope z ${d.slope_z})</span>`; }).join("");
    $("#p-decayCap").textContent = "Each coloured line is an exponential fit to that field's county-HEI shares; the " +
      "shaded band is the line's 95% confidence interval; the grey dots are every point. Log scale on the vertical axis, " +
      "zero-share pairs omitted. Education is omitted because its raw curve is degenerate (see above).";
    const main = ok.filter(f => f !== "social_science");
    const nlo = Math.min(...ok.map(f => D.decay[f].n)), nhi = Math.max(...ok.map(f => D.decay[f].n));
    const r2m = main.map(f => D.decay[f].r2), zm = main.map(f => Math.abs(D.decay[f].slope_z)), ss = D.decay.social_science;
    $("#p-decayConf").innerHTML = `<b>How much to trust the lines.</b> The dots scatter widely, and that is expected:
      at any given commute a county-HEI share can be anything from a couple of per cent to half, because it also depends
      on the county's size, the HEI's size and reputation, its points, and the pull of a home-county campus. A single
      dot is <i>not</i> well predicted by the commute alone, so the R&sup2; of these raw lines is low, about
      <b>${Math.min(...r2m)} to ${Math.max(...r2m)}</b> for the six main fields (and only ${ss.r2} for Social Sciences).
      What the lines <i>do</i> capture is the <b>average slope</b>. Each is fitted on ${nlo} to ${nhi} county-HEI points
      spread from a short drive to well over two hours, so even a noisy relationship pins the slope down: it sits
      <b>${Math.round(Math.min(...zm))} to ${Math.round(Math.max(...zm))} standard errors from zero</b> for the six main
      fields in this simplified view (Social Sciences is a marginal ${Math.abs(ss.slope_z)}), and the shaded bands show
      how narrow the line's own position is even where the dots are spread. The <b>gravity model above is the rigorous
      test</b>: it removes the county-size, HEI-size and home-county effects that cause most of this scatter and then
      measures the commute, which is why its numbers are far stronger. The decay curve is the plain-language picture;
      the model is the proof; both point the same way.`;
  }

  function countyMap(D, $){
    const MAP = $("#p-map");
    let selField = "computing", selHei = "MU", selView = "share", selCounty = null;
    $("#p-mField").innerHTML = D.fields.map(f => `<option value="${f}">${FL[f]}</option>`).join("");
    const cells = () => D.cells[selField];
    function heisIn(field){
      const s = new Set();
      for (const cty of Object.values(D.cells[field] || {})) for (const h of Object.keys(cty)) s.add(h);
      return D.heis.filter(h => s.has(h));
    }
    function fillHei(){
      const avail = heisIn(selField);
      if (!avail.includes(selHei)) selHei = avail.includes("MU") ? "MU" : avail[0];
      $("#p-mHei").innerHTML = avail.map(h => `<option value="${h}"${h === selHei ? " selected" : ""}>${h === "MU" ? "Maynooth" : h}</option>`).join("");
    }
    function val(cty, view){
      const cell = (cells()[cty] || {})[selHei]; if (!cell) return null;
      return view === "share" ? cell.share : view === "car" ? cell.car : cell.resid;
    }
    function colFor(v, lo, hi, view){
      if (v == null) return "var(--surface-alt)";
      if (view === "resid") { const m = Math.max(Math.abs(lo), Math.abs(hi)) || 1, t = v / m;
        return t >= 0 ? `rgba(2,128,144,${.12 + .7 * Math.min(1, t)})` : `rgba(216,81,40,${.12 + .7 * Math.min(1, -t)})`; }
      const t = (v - lo) / ((hi - lo) || 1);
      return view === "car" ? `rgba(216,81,40,${.12 + .75 * t})` : `rgba(2,128,144,${.12 + .8 * t})`;
    }
    function draw(){
      const vals = D.counties.map(c => val(c.name, selView)).filter(v => v != null);
      const lo = Math.min(...vals), hi = Math.max(...vals);
      let g = "";
      for (const c of D.counties) {
        const v = val(c.name, selView), sel = selCounty === c.name;
        g += `<path d="${c.d}" fill="${colFor(v, lo, hi, selView)}" stroke="${sel ? "var(--ink)" : "var(--hair-strong)"}" stroke-width="${sel ? 2 : 0.8}"` +
          ` vector-effect="non-scaling-stroke" data-c="${c.name}" class="county"/>`;
        g += `<text x="${c.cx}" y="${c.cy}" text-anchor="middle" style="fill:var(--ink);font-size:10px;font-weight:600;pointer-events:none">${c.name}</text>`;
        const v2 = v == null ? "" : selView === "share" ? Math.round(v * 100) + "%" : selView === "car" ? Math.round(v) : (v > 0 ? "+" : "") + Math.round(v);
        g += `<text x="${c.cx}" y="${c.cy + 12}" text-anchor="middle" style="fill:var(--muted);font-size:9px;pointer-events:none">${v2}</text>`;
      }
      const [px, py] = D.campuses[selHei];
      g += `<circle cx="${px}" cy="${py}" r="4.5" fill="${D.col[selHei]}" stroke="#fff" stroke-width="1.4"/>`;
      MAP.innerHTML = g;
      MAP.querySelectorAll("path.county").forEach(p => p.onclick = () => { selCounty = p.dataset.c; panel(); draw(); });
      const Lg = $("#p-mapLg");
      Lg.innerHTML = selView === "resid"
        ? `<span><i style="background:rgba(216,81,40,.7)"></i>fewer than predicted</span><span><i style="background:rgba(2,128,144,.7)"></i>more than predicted</span>`
        : selView === "car"
        ? `<span><i style="background:rgba(216,81,40,.2)"></i>${Math.round(lo)} min</span><span><i style="background:rgba(216,81,40,.85)"></i>${Math.round(hi)} min</span>`
        : `<span><i style="background:rgba(2,128,144,.2)"></i>${Math.round(lo * 100)}%</span><span><i style="background:rgba(2,128,144,.9)"></i>${Math.round(hi * 100)}%</span>`;
    }
    function courseList(hei){
      if (selField !== "computing") return `<div class="sub" style="margin-top:.6rem">Course lists are shown for Computing only.</div>`;
      const cs = (D.courses || {})[hei] || [], nm = hei === "MU" ? "Maynooth" : hei;
      if (!cs.length) return `<div class="sub" style="margin-top:.6rem">No computing course list for ${nm}.</div>`;
      return `<div style="margin-top:.7rem;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;color:var(--navy);font-weight:700">` +
        `${cs.length} computing course${cs.length > 1 ? "s" : ""} at ${nm} (2025)</div><table style="margin-top:.3rem"><tbody>` +
        cs.map(c => `<tr><td class="l mono" style="width:3.4rem">${c.code}</td>` +
          `<td class="l" style="white-space:normal;font-size:.78rem">${c.title}${c.level < 8 ? ' <span style="color:var(--faint)">L' + c.level + "</span>" : ""}</td>` +
          `<td class="mono" style="color:var(--faint)">${c.open ? "open" : (c.eos == null ? "" : c.eos)}</td></tr>`).join("") + "</tbody></table>";
    }
    function panel(){
      const c = D.counties.find(x => x.name === selCounty); if (!c) return;
      const tot = (D.countyTotals[selField] || {})[selCounty] || 0;
      $("#p-sT").textContent = `${selCounty} · ${FL[selField]}`;
      $("#p-sS").textContent = `17 to 19 cohort ${c.cohort.toLocaleString("en-IE")} · third-level share ${Math.round(c.tl * 100)}% · ${tot} ${FL[selField]} new entrants to the modelled HEIs (pooled)`;
      const rows = D.heis.map(h => ({h, ...(cells()[selCounty] || {})[h]})).filter(r => r.n != null).sort((a, b) => b.n - a.n);
      let t = `<thead><tr><th class="l">HEI</th><th>Went</th><th>Share</th><th>Car</th><th>Resid.</th></tr></thead><tbody>`;
      for (const r of rows) {
        const nc = selField === "computing" ? ((D.courses || {})[r.h] || []).length : 0;
        t += `<tr class="${r.h === "MU" ? "mu" : ""}" data-h="${r.h}" style="cursor:pointer"${nc ? ` title="${nc} computing courses: click to list"` : ""}>` +
          `<td class="l">${r.h === "MU" ? "Maynooth" : r.h}${r.home ? " &#8962;" : ""}${nc ? ` <span style="color:var(--faint);font-size:.72rem">${nc}</span>` : ""}</td>` +
          `<td class="mono">${r.n}</td><td class="mono">${Math.round(r.share * 100)}%</td><td class="mono">${Math.round(r.car)}</td>` +
          `<td class="mono" style="color:${r.resid < 0 ? "var(--coral)" : "var(--teal)"}">${r.resid > 0 ? "+" : ""}${r.resid}</td></tr>`;
      }
      $("#p-sTbl").innerHTML = t + "</tbody>";
      const sc = $("#p-sCourses"); sc.innerHTML = ""; sc.dataset.h = "";
      $("#p-sTbl").querySelectorAll("tr[data-h]").forEach(tr => tr.onclick = () => {
        const h = tr.dataset.h;
        if (sc.dataset.h === h) { sc.dataset.h = ""; sc.innerHTML = ""; } else { sc.dataset.h = h; sc.innerHTML = courseList(h); }
      });
    }
    function cap(){
      const fl = FL[selField];
      $("#p-mapCap").textContent = selView === "share"
        ? `Darker = a larger share of that county's ${fl} new entrants chose the selected HEI. The dot is the HEI's campus.`
        : selView === "car" ? "Darker = a longer cohort-weighted car commute from that county to the selected HEI."
        : `Teal = the selected HEI recruits more ${fl} students from that county than the model predicts; coral = fewer.`;
    }
    $("#p-mField").onchange = e => { selField = e.target.value; fillHei(); draw(); if (selCounty) panel(); cap(); };
    $("#p-mHei").onchange = e => { selHei = e.target.value; draw(); if (selCounty) panel(); };
    $("#p-mView").onchange = e => { selView = e.target.value; draw(); cap(); };
    fillHei(); draw(); cap();
  }

  function muRows(D){
    return D.counties.map(c => {
      const o = {c: c.name}; let home = false;
      for (const f of D.fields) { const cell = (D.cells[f][c.name] || {}).MU; if (cell) { o[f] = cell; home = home || !!cell.home; } }
      o.home = home; return o;
    }).filter(r => r.computing).sort((a, b) => a.computing.resid - b.computing.resid);
  }

  function muTable(D, $){
    const rows = muRows(D);
    const SH = {computing:"Comp.", natural_sciences:"Science", engineering:"Eng.", business:"Business",
      health:"Health", arts:"Arts", social_science:"Soc.Sci.", education:"Educ."};
    let t = `<thead><tr><th class="l">County</th><th>Car&nbsp;min</th>` + D.fields.map(f => `<th>${SH[f]}</th>`).join("") + `</tr></thead><tbody>`;
    for (const r of rows) {
      t += `<tr><td class="l">${r.c}${r.home ? " &#8962;" : ""}</td><td class="mono">${Math.round(r.computing.car)}</td>` +
        D.fields.map(f => { const v = r[f] ? r[f].resid : null;
          return v == null ? `<td class="mono">&ndash;</td>` : `<td class="mono" style="color:${v < 0 ? "var(--coral)" : "var(--teal)"}">${v > 0 ? "+" : ""}${v}</td>`; }).join("") + `</tr>`;
    }
    $("#p-muTbl").innerHTML = t + "</tbody>";
    const M = muPattern(D);
    const fmtR = (c, f) => { const v = M.res(c)[f]; return `${v > 0 ? "+" : ""}${Math.round(v)} in ${FL[f]}`; };
    const fmtF = (c, f) => { const v = Math.round(M.res(c)[f]); return `${FL[f]} (${v > 0 ? "+" : ""}${v})`; };
    const ord = (c, dir) => M.big.filter(f => M.res(c)[f] != null).sort((a, b) => dir * (M.res(c)[a] - M.res(c)[b])).slice(0, 3);
    const kf = M.fewer("Kildare"), km = M.more("Kildare");
    const ke = ((D.cells.education.Kildare || {}).MU || {}).resid;
    $("#p-muProse").innerHTML = `The table shows, for each county and field, how many more (teal) or fewer (coral)
      students Maynooth recruited than the model predicts from the county's cohort, its other options and the commute.<br><br>
      <b>Fewer than predicted in every field: ${listOf(M.under)}.</b> ${M.under.map(c => `${c}: ${ord(c, 1).map(f => fmtR(c, f)).join(", ")}`).join("; ")}.
      ${M.under.includes("Wicklow") ? "Wicklow is a short drive from Maynooth, yet sends it far fewer students than that drive predicts, right across its provision." : ""}<br><br>
      <b>Kildare, Maynooth's own county, is mixed.</b> Maynooth takes fewer Kildare students than predicted in
      ${kf.length ? listOf(kf.map(f => fmtF("Kildare", f))) : "no field by a clear margin"}${km.length ? `, but more in
      ${listOf(km.map(f => fmtF("Kildare", f)))}` : ""}${ke == null ? "" : ` and Education (${ke > 0 ? "+" : ""}${Math.round(ke)})`}.<br><br>
      <b>More than predicted: ${listOf(M.over)}.</b> ${M.over.map(c => `${c}: ${ord(c, -1).map(f => fmtR(c, f)).join(", ")}`).join("; ")}.<br><br>
      <b>Engineering</b> and <b>Health</b> residuals are small everywhere because Maynooth's intake in both is small
      (${D.fieldstat.engineering.by_hei.MU} and ${D.fieldstat.health.by_hei.MU} pooled entrants, the lowest of the eight HEIs). Read the exact
      numbers as indicative, given the pooled counts and the HEA's rounding to the nearest five. An earlier version of this
      report found Maynooth under-recruiting Kildare in every field and over-recruiting the midlands; that came from a fault
      in how county commute times were averaged, corrected on 2 October 2026 (see the version history in the methods).<br><br>
      <b>An independent check from the census.</b> Census 2022 records how long students aged 19 and over in each town
      actually travel to college. In Kildare's ${D.kildare.n} census towns they report journeys <b>${D.kildare.mean} minutes
      longer</b>, on average, than the model's trip to the quickest campus given how they travel; for example
      ${D.kildare.towns.map(t => `${t[0]} ${Math.round(t[1])} against ${Math.round(t[2])} minutes`).join(", ")}. For much
      of north Kildare the quickest campus is Maynooth, so a longer reported journey means many of these students travel
      past it. That fits the enrolment model's shortfall for Kildare in ${listOf(kf.map(f => FL[f]))}, from a different
      dataset and a different method (see
      <a href="#methods/m-valid">How well does the model match reality?</a>).`;
  }

  function caseReturn(D, $){
    const M = muPattern(D);
    const big = [...D.fields].filter(f => f !== "education")
      .sort((a, b) => D.fieldstat[b].by_hei.MU - D.fieldstat[a].by_hei.MU).slice(0, 3);
    const short = c => -Math.round(big.reduce((s, f) => s + Math.min(0, M.res(c)[f] || 0), 0));
    const cs = ["Wicklow", "Kildare"].map(c => [c, short(c)]).filter(x => x[1] > 0);
    $("#p-caseReturn").innerHTML = `For Maynooth the immediate value is a costed, targeted recruitment case. In its three
      largest fields (${listOf(big.map(f => FL[f]))}), the model puts Maynooth's pooled intake ${listOf(cs.map(([c, n]) =>
      `from ${c} about <b>${n} below</b>`))} what the commute predicts, over seven years of entrants. Recovering even a small
      share of those students shows up directly in student numbers and in fee and HEA block-grant income, against a
      recruitment spend that can be aimed at named districts rather than the whole region. The finer geography also tells
      you <i>which</i> districts, and item&nbsp;2 tells you how many of those students would actually commute rather than
      relocate.`;
  }

  function methods(el){
    const D = data();
    el.innerHTML = `
  <p>How the enrolment model is built, for a reader who is not a statistician.</p>
  <h4>1. The two datasets</h4>
  <p><b>The flows.</b> Higher Education Authority, "Access Our Data: Students". For every county in the Republic and
  every HEI, the HEA publishes how many <i>new entrants</i> (first-year students, not the whole student body) came
  from that county. The same extract was run once for each of eight ISCED fields of study: <i>Information and
  Communication Technologies</i>, <i>Natural sciences, mathematics and statistics</i>, <i>Engineering, manufacturing
  and construction</i>, <i>Business, administration and law</i>, <i>Health and welfare</i>, <i>Arts and
  humanities</i>, <i>Social sciences, journalism and information</i>, and <i>Education</i>, always at undergraduate
  level. For each field the seven academic years ${D.meta.years} are pooled into a single count per county-HEI pair,
  because a single year's county-by-HEI cell is tiny and rounded to the nearest 5; pooling gives stable counts, at the
  cost of hiding any trend. "County" is county <i>of domicile</i>, the student's home address when they applied, and
  Dublin is reported as one county. The model keeps the twelve counties of the study area and its eight HEIs (seven
  for Education, since Dundalk&nbsp;IT has no education intake), giving <b>${D.meta.total_flows.toLocaleString("en-IE")}
  students</b> across <b>${D.meta.n_cells} field-county-HEI cells</b>. Snapshots: computing captured 27 August 2026,
  the other seven fields 30 August, all in <code>data/raw/hea-*-newentrants-county-institute-*.txt</code>.</p>
  <p><b>What the HEA institute breakdown leaves out, for Education in particular.</b> The dataset covers the HEA-funded
  institutes. It does <b>not</b> include Marino Institute of Education or Hibernia College, both linked or private
  providers of primary teacher training (a few hundred new entrants a year between them, mostly Leinster). Mary
  Immaculate College and the University of Limerick, the two largest Education providers that <i>are</i> in the data,
  sit in Limerick, outside the study region, and are not modelled. Within reach that leaves DCU (which absorbed
  St&nbsp;Patrick's, Mater&nbsp;Dei and the Church of Ireland college) dominant, Maynooth's Froebel programme second,
  and little else, so the Education model is the weakest of the eight and its numbers are indicative only.</p>
  <p><b>The accessibility.</b> The study's commute model computes, for every Electoral Division, the morning one-way
  commute to every campus, by car and by public transport plus drive-to-rail, on a normal term weekday. For the
  enrolment model those figures are rolled up to county as a weighted average, the weight being each Electoral
  Division's college-entry cohort (its 15 to 17 year olds, rescaled to the 17 to 19 total, because the census counts
  third-level students at their term-time address). This side is <b>identical for all eight fields</b>: the commute from Kildare to
  Maynooth does not depend on the subject. Where an HEI has more than one campus (TU&nbsp;Dublin), the county takes the
  shortest. "Straight-line km" is the same cohort-weighted distance in a straight line to the nearest campus.</p>
  <p><b>Is this compilation new?</b> The raw enrolment counts are public, and whether distance relates to
  higher-education participation in Ireland has been studied before using straight-line or road distance. What is
  assembled here and not published anywhere as a single dataset is the join: HEA institution-level choice flows
  against a modelled multi-modal commute (car and scheduled public transport, door to door), at campus and field
  granularity, fitted with a gravity model. The commute surface itself is new.</p>
  <h4>2. Building the table</h4>
  <p>Each field-county-HEI triple becomes one row of data with: the number of students who made that move, the
  county's car commute, public-transport commute and distance to that HEI, whether the county contains a campus of
  that HEI, the county's 17 to 19 cohort size, and the county's share of adults who hold a third-level qualification
  (Census 2022). Nothing else.</p>
  <h4>3. The gravity model, in plain terms</h4>
  <p>A <b>gravity model</b> is the standard tool for flows between places, borrowed from the study of trade and
  migration. The flow from an origin to a destination scales with how big the origin is, how big the destination is,
  and a term that shrinks as the friction between them grows:</p>
  <p class="eq">students(county &rarr; HEI) = exp( b &times; commute + g &times; home-county + (a term for the county) + (a term for the HEI) )</p>
  <p>The two "terms" are <b>fixed effects</b>. The county term is a single number per county that absorbs everything
  about that county at once: its cohort size, its education level, its points profile. The HEI term does the same for
  each HEI. Because those are held constant, the commute coefficient <b>b</b> cannot be picking up "big counties send
  more students" or "famous HEIs attract more students". It can only pick up the pattern <i>within</i> a county:
  holding that county fixed, do more of its students go to the HEIs that are nearer? The model is run separately for
  each field, so the eight values of <b>b</b> can be compared. It is fitted by <b>Poisson pseudo-maximum-likelihood</b>,
  the estimator the flows literature uses for count data with many zeros and over-dispersion; it handles the zero
  cells without dropping them.</p>
  <h4>4. Reading the numbers</h4>
  <dl>
    <dt>Per&nbsp;10</dt><dd>The estimated <b>b</b>, as a percentage change in the flow for ten more minutes of commute
    (or ten more km), county and HEI held fixed. Negative means a longer commute goes with fewer students.</dd>
    <dt>z</dt><dd>The estimate divided by its standard error. The usual bar for "not a fluke" is about 2; these run well
    past it.</dd>
    <dt>Deviance drop</dt><dd>How much better the model fits once the commute term is added, on top of the county and
    HEI fixed effects. A chi-squared statistic on one degree of freedom; about 11 is already p&nbsp;&lt;&nbsp;0.001. This
    is the number compared across the three commute measures.</dd>
    <dt>AIC</dt><dd>Overall model quality with a penalty for parameters. Lower is better; used only to rank the three
    commute measures.</dd>
    <dt>Halving distance</dt><dd>From the decay curve: the extra car minutes that cut a county's share going to an HEI
    in half. A short halving distance is a field where the commute matters a lot.</dd>
  </dl>
  <h4>5. The friction comparison</h4>
  <p>Within each field the model is run three times, changing only the commute measure: car time, public-transport
  time, straight-line distance. Whichever gives the larger deviance drop and lower AIC is the one the flows track most
  closely. ${ranking(D)} The three are highly correlated and all strong; at county scale the drive time is the best guide
  and public-transport reachability the poorest. The whole comparison is also run with the county fixed effect swapped
  for two plain county variables (cohort size, third-level share); the effects come out a little smaller in most fields, the expected
  sign that the fixed effects were not manufacturing the result. Full numbers: <code>outputs/p4_model_fit.csv</code>.</p>
  <p>County commute times are cohort-weighted averages over every area in the county. An area with no trip to an HEI
  inside the time limit counts at the limit (240 minutes by public transport, 150 by car) rather than being left out;
  leaving it out had made distant HEIs look closer than they are by public transport, and the correction (2 October
  2026) mainly changed the Maynooth residuals.</p>
    <p><b>What about the money?</b> The annual financial cost of the commute, from the study's cost model (the
  cheapest public-transport option, including student Leap fares and coach tickets), was also tested as the commute
  measure (<code>scripts/44_cost_friction.py</code>). At county scale it adds nothing new: that fare rises close to
  linearly with distance, so cost correlates <b>${D.cost_r_km} with straight-line distance</b>, and in every field it fits
  less well than drive time. In money terms a county's flow to an HEI falls by roughly
  ${pcRange(D, "cost_pct", clean(D)).join("% to ")}% for every extra &euro;100 a year the commute costs, but that is the
  distance result restated in euros, not a separate finding.</p>
    <p>The public-transport fares in the cost model are the NTA fare determination for <b>January 2027</b>: the Young
  Adult and Student Leap 90-minute Dublin fare rises from &euro;1.00 to &euro;1.15, adult fares by about 15% on average.
  Because the rise is close to uniform, it lifts the level of the cost measure without changing its structure, so the
  finding above is unaffected. What it does do is raise the stakes of the question the county-scale data cannot
  answer: whether it is <i>time</i> or <i>money</i> that deters, which matters most for lower-income students in a
  period of rising fares. That needs a measure of household income by area, a question for the next stage of the
  study, and a more pressing one than it was.</p>
  <h4>6. Why the fields differ</h4>
  <p>The coefficients differ between fields, but less than they first appear: one field stands out as steepest and the
  rest sit close together. A natural explanation, that a field taught at many campuses always has a near substitute and
  so is more sensitive to an extra few minutes, is <b>not</b> borne out: a simple concentration index of each field's
  entrants across the eight HEIs (the sum of squared shares) barely tracks the coefficients. Education is the weakest
  fit by far: the two biggest providers in reach (Marino and Hibernia) are absent from the data and the next two (Mary
  Immaculate, University of Limerick) are outside the region, leaving one dominant destination and more than half the
  cells empty. Its commute coefficient is still negative, but only the other fields carry real analytical weight.</p>
    <h4>7. The decay curve and the Maynooth residuals</h4>
  <p>The scatter fits share = exp(a + b &times; car minutes) to each field's county-HEI shares; the slope gives the
  halving distance. For the Maynooth residual table, the headline model (county fixed effects, car time) produces a
  <b>predicted</b> flow for every field-county-HEI cell; the <b>residual</b> is the actual count minus that prediction.
  A positive residual for Maynooth in a field and county means Maynooth recruits more of that county's students in that
  field than its cohort, its commute and the county's other options predict. The residuals sum to roughly zero within
  each county by construction.</p>
  <h4>8. Course lists</h4>
  <p>The computing courses shown per HEI in the county panel are every CAO course the official Points Charts
  spreadsheet classifies in the ISCED field <i>Information and Communication Technologies</i>, 2025, with
  end-of-season points. Course lists for the other seven fields are not yet compiled.</p>
  <div class="m-standalone"><h4>9. What this can and cannot say</h4>
  <p><b>Can</b>: show that the commute carries real, sizeable signal for where a county's students enrol in
  ${words(clean(D).length)} of these eight fields, compare its size across fields, compare the three ways of measuring
  the commute, and flag the counties where an institution's
  recruitment departs from its geography, by field.</p>
  <p><b>Cannot</b>: prove the commute <i>causes</i> the choice (single cross-section; course reputation, points and the
  home-county pull travel with distance); resolve anything below county level (Dublin is one cell); distinguish a
  genuine daily commuter from a student who relocated (about half of Irish higher-education students live away from
  home during term, so the model understates the deterrent for those who actually commute); or say anything about
  trend, since the years are pooled. Field-level pooled counts are small and rounded; for Health the most locally
  recruiting providers (RCSI, the Munster and Connacht nursing schools) sit outside the modelled set, Social Sciences is
  a small, awkwardly bounded bucket, and Education loses Marino and Hibernia and its two biggest in-data providers to
  geography, so both should be read as indicative only. This is <b>potential accessibility against realised
  choice</b>, eight fields, one region, as a first pass. "How to sharpen the answer" sets out the four data additions
  that would lift each of these limits and what each would buy.</p></div>`;
  }

  return {init, methods};
})();
"""
