"""Merged report "Commuting to College": one entry point with question-led branches.

Every branch is assembled from the section modules in scripts/sections/ (reach, cost, carbon,
choice), which share one per-ED x campus table, one campus selector and one theme. A branch's
`parts` name a section and, optionally, an alternative template (the Maynooth worked example uses
the reach and choice modules' MAIN_MU parts).

Inputs: the p3_* and p4_* outputs, p3_od_long.csv, p3_cost.csv, p3_cost_by_county.csv,
p3_emissions.csv, p3_emissions_by_county.csv, p3_pop_weighted.csv, p4_model_fit.csv.
Output: outputs/hei-commute.html
"""

from __future__ import annotations

import re
from html import escape as html_escape

import numpy as np
import pandas as pd

import config as C
from sections import burden, carbon, choice, cost, reach, validation
from sections.common import APP_JS, BASE_CSS, FONTS, MU, county_shapes, ed_table, json_script, section_bundle

SECTION_MODS = [cost, carbon, choice, reach, burden, validation]
DUBLIN_AREA = {"Dublin City", "Dún Laoghaire-Rathdown", "Fingal", "South Dublin", "Kildare"}
BORDER_MIDLAND = {"Carlow", "Kilkenny", "Laois", "Longford", "Louth", "Monaghan", "Offaly", "Westmeath"}
VERSION = "1.0.0"
CONCEPT_DOI = "10.5281/zenodo.23108980"   # all versions; resolves to the latest
VERSION_DOI = "10.5281/zenodo.23108981"   # this version (1.0.0)


def _pct(x):
    """Percent, rounded half up, to match the page's own Math.round."""
    return int(100 * x + 0.5 + 1e-9)


def _wavg(g, col):
    return float(np.average(g[col], weights=g["cohort_17_19"]))


def headlines():
    pw = pd.read_csv(C.OUT / "p3_pop_weighted.csv")
    pw = pw[(pw["schedule"] == "peak") & (pw["threshold_min"] == 60)]
    share = {(r.target, r.mode): r.cohort_share for r in pw.itertuples()}

    fit = pd.read_csv(C.OUT / "p4_model_fit.csv")
    fit = fit[(fit["friction"] == "car_min") & (fit["spec"] == "county FE")
              & (fit["z"].abs() >= 6)]   # the well-measured fields, as in sections/choice.py
    lo, hi = -fit["pct_per10"].max(), -fit["pct_per10"].min()

    cst = pd.read_csv(C.OUT / "p3_cost.csv")
    mu = cst[(cst["campus_id"] == MU) & (cst["schedule"] == "peak")]
    by = {c: g for c, g in mu.groupby("county")}
    dub = [_wavg(by[c], "pt_year") for c in DUBLIN_AREA if c in by]
    bm_pt = [_wavg(by[c], "pt_year") for c in BORDER_MIDLAND if c in by]
    bm_fuel = [_wavg(by[c], "car_fuel_year") for c in BORDER_MIDLAND if c in by]

    em = pd.read_csv(C.OUT / "p3_emissions.csv")
    emu = em[em["campus_id"] == MU]
    vt = pd.read_csv(C.OUT / "p3_validation_towns.csv")
    vc = pd.read_csv(C.OUT / "p3_validation_counties.csv")

    return {
        "pt60": _pct(share[("any_hei", "pt_plus_rail")]),
        "car60": _pct(share[("any_hei", "car")]),
        "mu_pt60": _pct(share[("maynooth", "pt_plus_rail")]),
        "mu_car60": _pct(share[("maynooth", "car")]),
        "decay_lo": int(lo + 0.5), "decay_hi": int(hi + 0.5), "n_clean": len(fit),
        "dub_pt": [int(round(min(dub), -1)), int(round(max(dub), -1))],
        "bm_pt": [int(round(min(bm_pt), -1)), int(round(max(bm_pt), -1))],
        "bm_fuel": [int(round(min(bm_fuel), -2)), int(round(max(bm_fuel), -2))],
        "mu_car_kg": int(round(_wavg(emu, "car_kg_year"), -1)),
        "mu_pt_kg": int(round(_wavg(emu, "pt_kg_year"), -1)),
        "cohort": int(mu.drop_duplicates("origin_id")["cohort_17_19"].sum()),
        "r_cty": round(float(np.corrcoef(vc["model_car_saving"], vc["share_car"])[0, 1]), 2),
        "v_bias": round(float((vt["model_mix"] - vt["reported_min"]).mean()), 1),
        "v_mae": round(float((vt["model_mix"] - vt["reported_min"]).abs().mean())),
    }


def about_markdown(h: dict) -> str:
    """docs/ABOUT.md with its figures filled from the headlines (also shipped in the release)."""
    md = (C.ROOT / "docs" / "ABOUT.md").read_text()
    md = md.replace("{MU_PT60}", str(h["mu_pt60"])).replace("{MU_CAR60}", str(h["mu_car60"]))
    assert not re.search(r"\{[A-Z0-9_]+\}", md), "unfilled placeholder in ABOUT.md"
    return md


def about_html(md: str) -> str:
    paras = [p.strip() for p in md.split("\n\n") if p.strip() and not p.startswith("# ")]
    out = []
    for p in paras:
        p = html_escape(" ".join(p.split()), quote=False)
        p = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", p)
        p = re.sub(r"\[(.+?)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', p)
        out.append(f"<p>{p}</p>")
    return "\n".join(out)


def main() -> None:
    table = ed_table()
    data = {"h": headlines(), "version": VERSION, "doi": VERSION_DOI,
            "snapshot": "27 August 2026 (HEA extracts 30 August 2026)",
            "fare_year": getattr(C, "FARE_YEAR", 2027), "analysis_date": C.ANALYSIS_DATE.strftime("%-d %B %Y")}
    b = section_bundle(SECTION_MODS)
    tpls = [(m.KEY, m.KEY, m.MAIN) for m in SECTION_MODS] + [("choice-mu", "choice", choice.MAIN_MU),
                                                           ("reach-mu", "reach", reach.MAIN_MU)]
    mains = "\n".join(f'<template id="main-{t}"><div class="sec-{k}">{html}</div></template>' for t, k, html in tpls)
    html = (_TEMPLATE
            .replace("/*__FONTS__*/", FONTS)
            .replace("/*__BASE_CSS__*/", BASE_CSS + b["css"])
            .replace("<!--__MAINS__-->", mains)
            .replace("__CONCEPT_DOI__", CONCEPT_DOI).replace("__VERSION_DOI__", VERSION_DOI)
            .replace("<!--__ABOUT__-->", about_html(about_markdown(data["h"])))
            .replace("/*__DATA__*/", json_script(data))
            .replace("/*__TABLE__*/", json_script(table))
            .replace("/*__COUNTIES__*/", json_script(county_shapes()))
            .replace("<!--__SECTION_DATA__-->", b["data"])
            .replace("/*__APP_JS__*/", APP_JS + b["js"]))
    assert "—" not in _TEMPLATE, "no em dashes in the shell text"
    out = C.OUT / "hei-commute.html"
    out.write_text(html)
    h = data["h"]
    print(f"wrote {out.name} ({len(html) / 1e6:.1f} MB); {len(table['eds'])} EDs, "
          f"{len(table['campuses'])} campuses; headline PT60 {h['pt60']}% car60 {h['car60']}%, "
          f"decay {h['decay_lo']}-{h['decay_hi']}% over {h['n_clean']} fields")


_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Commuting to College</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
/*__FONTS__*/
<style>
/*__BASE_CSS__*/
  html{scroll-padding-top:calc(var(--bar) + 12px)}
  .bar{position:sticky;top:0;z-index:30;height:var(--bar);display:flex;align-items:center;gap:1rem;
    padding:0 clamp(1rem,3vw,2rem);background:var(--surface);border-bottom:1px solid var(--hair)}
  .brand{font-family:"Spectral",Georgia,serif;font-weight:600;font-size:1.08rem;color:var(--ink);
    text-decoration:none;white-space:nowrap}
  .nav{display:flex;gap:.2rem;overflow-x:auto;scrollbar-width:none;flex:1;min-width:0}
  .nav::-webkit-scrollbar{display:none}
  .nav a{font-size:.8rem;color:var(--muted);text-decoration:none;padding:.35rem .6rem;border-radius:6px;white-space:nowrap}
  .nav a:hover{color:var(--ink);background:var(--surface-alt)}
  .nav a.on{color:var(--ink);background:var(--surface-alt);font-weight:600}
  .tbtn{width:34px;height:34px;flex:0 0 auto;border-radius:8px;border:1px solid var(--hair-strong);
    background:var(--surface);color:var(--ink);cursor:pointer;font-size:15px;line-height:1}
  .narrow{max-width:900px}
  .view{display:none}
  .view.on{display:block}
  h1.b{font-size:clamp(1.7rem,4.5vw,2.4rem)}
  .card .d{text-align:justify;hyphens:auto;-webkit-hyphens:auto}
  .tile .u{text-align:left}
  .answer{background:var(--surface);border:1px solid var(--hair);border-left:4px solid var(--navy);border-radius:10px;
    padding:1rem 1.2rem;margin:1.2rem 0}
  .answer h3{margin:0 0 .4rem;font-size:1.05rem}
  .answer p{margin:.35rem 0}
  .tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:.8rem;margin:1.4rem 0}
  .tile{background:var(--surface-alt);border-radius:10px;padding:.9rem 1rem}
  .tile .n{font-family:"Spectral",Georgia,serif;font-size:clamp(1.6rem,4vw,2.1rem);font-weight:600;line-height:1.1;color:var(--navy)}
  .tile .u{font-size:.84rem;color:var(--muted);margin-top:.3rem}
  .tile .u b{color:var(--ink)}
  .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(270px,1fr));gap:1rem;margin-top:1rem}
  .card{display:block;background:var(--surface);border:1px solid var(--hair);border-radius:12px;padding:1.05rem 1.15rem;
    text-decoration:none;color:var(--ink);transition:border-color .15s,transform .15s}
  a.card:hover{border-color:var(--navy);transform:translateY(-1px)}
  .card .k{font-size:.68rem;font-weight:600;letter-spacing:.1em;text-transform:uppercase;color:var(--faint)}
  .card .t{font-family:"Spectral",Georgia,serif;font-size:1.22rem;font-weight:600;margin:.2rem 0 .3rem;line-height:1.2}
  .card .d{font-size:.88rem;color:var(--muted)}
  .card .f{font-size:.76rem;color:var(--faint);margin-top:.55rem}
  .card.ex{border-style:dashed}
  .subnav{display:flex;flex-wrap:wrap;gap:.4rem;margin:.6rem 0 0}
  .subnav a{font-size:.78rem;padding:.25rem .65rem;border:1px solid var(--hair-strong);border-radius:999px;
    color:var(--muted);text-decoration:none;background:var(--surface)}
  .subnav a:hover{color:var(--ink);border-color:var(--navy)}
  .partlabel{font-size:.7rem;font-weight:600;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);
    margin:2rem auto 0;max-width:1240px;padding:0 clamp(1rem,4vw,2.4rem)}
  .finder{display:flex;flex-wrap:wrap;gap:.6rem;align-items:center}
  .finder input{font:inherit;font-size:.95rem;padding:.45rem .7rem;width:min(420px,100%);background:var(--surface);
    color:var(--ink);border:1px solid var(--hair-strong);border-radius:8px}
  .chips{display:flex;flex-wrap:wrap;gap:.4rem;margin-top:.6rem;font-size:.8rem;color:var(--faint);align-items:center}
  .chips button{font:inherit;font-size:.78rem;padding:.22rem .6rem;border:1px solid var(--hair-strong);border-radius:999px;
    background:var(--surface);color:var(--muted);cursor:pointer}
  .chips button:hover{color:var(--ink);border-color:var(--navy)}
  tr.grp th{border-bottom:none;padding-bottom:0;color:var(--faint)}
  .tb{display:inline-block;height:7px;border-radius:4px;vertical-align:middle;margin-left:.4rem}
  .na{color:var(--faint);font-size:.8rem}
  .m-merged .m-standalone{display:none}
  .cite{font-family:"IBM Plex Mono",monospace;font-size:.82rem;background:var(--surface-alt);border-radius:8px;
    padding:.8rem 1rem;line-height:1.55;text-align:left}
  .foot{font-size:.78rem;color:var(--faint);border-top:1px solid var(--hair);margin-top:2.5rem;padding-top:.9rem}
  @media print{.bar{display:none}}
</style>
<script>(function(){var t;try{t=localStorage.getItem("hei-theme")}catch(e){}
  document.documentElement.setAttribute("data-theme",t||"dark");})();</script>
</head>
<body>
<div class="bar">
  <a class="brand" href="#home">Commuting to College</a>
  <nav class="nav" id="nav"></nav>
  <button class="tbtn" id="themeBtn" aria-label="Toggle dark or light mode" title="Toggle dark / light mode">&#9788;</button>
</div>

<section class="view" id="v-home"><div class="wrap">
  <p class="eyebrow">Higher education in Leinster &middot; accessibility, cost, emissions and choice</p>
  <h1>Commuting to College</h1>
  <p class="byline"><b>Professor John G. Keating</b>, Associate Dean for Teaching &amp; Learning, Faculty of
    Science &amp; Engineering, Maynooth University. Built with Claude Code assistance (<a href="#methods/m-about">how</a>).</p>
  <p class="disclaim">This is individual research and analysis. The views, interpretations and any errors are my own; it is not an official Maynooth University publication and does not represent the University&rsquo;s position. <a href="#methods/m-about">About this analysis</a>.</p>
  <p class="lead">How long, how costly and how carbon-heavy is the daily journey from home to college for
    the young people of Leinster, and does it shape where they choose to study? The study models a weekday
    commute from every one of <b id="hEd"></b> Electoral Divisions across Leinster (except Wexford) and Monaghan
    to 14 higher-education campuses, by public transport and by car, for the <b id="hCoh"></b> people aged 17 to 19 who live there.</p>
  <div class="answer" id="answer"></div>
  <div class="tiles" id="tiles"></div>
  <h2>Where would you like to start?</h2>
  <div class="cards" id="cards"></div>
  <p class="foot" id="foot"></p>
</div></section>

<section class="view" id="v-area"><div class="wrap">
  <p class="eyebrow">Find your area</p>
  <h1 class="b">From home to every campus</h1>
  <p class="lead">Type the name of a town or Electoral Division. You get the morning journey to each of the 14
    campuses by public transport and by car, what a year of that commute costs, and the carbon it emits.</p>
  <div class="panel">
    <div class="finder">
      <input id="aq" list="edlist" placeholder="Start typing a place, for example Naas or Tullamore" autocomplete="off">
      <datalist id="edlist"></datalist>
    </div>
    <div class="chips" id="aex"><span>Try:</span></div>
  </div>
  <div id="aout"></div>
  <p class="note" style="margin-top:1rem">Morning peak (arrive about 08:30), one representative term Wednesday.
    Public transport includes the option of driving to a railway station. Costs are for 140 commuting days:
    student and Young Adult fares (January <span class="fy"></span> fare levels) or car fuel plus campus parking
    and tolls. Carbon is operational CO<sub>2</sub> for a single-occupant petrol car or the public-transport
    mode used; the <a href="#emits">carbon branch</a> lets you change these assumptions.
    An Electoral Division is a small statistical area; the figures are for its population-weighted centre.</p>
</div></section>

<section class="view" id="v-methods"><div class="wrap">
  <p class="eyebrow">Methods, data and how to cite</p>
  <h1 class="b">How this was done</h1>
  <p class="lead">Every figure in this report is regenerated by a numbered pipeline of scripts from dated copies of
    public data. This section sets out the whole method in the order the work was done, then what the results can and
    cannot support, where the data came from, and how to reproduce it.</p>
  <nav class="subnav" id="sn-methods"></nav>
  <div class="m-merged">
    <h2 id="m-cite">How to cite</h2>
    <div class="cite" id="cite"></div>
    <p class="note">The DOI above identifies this version; <a href="https://doi.org/__CONCEPT_DOI__">__CONCEPT_DOI__</a> always
      resolves to the latest version. Archived on <a href="https://doi.org/__VERSION_DOI__">Zenodo</a> with the code and data;
      source at <a href="https://github.com/JKeatingMU/commuting-to-college">github.com/JKeatingMU/commuting-to-college</a>.
      This is individual research and analysis, not an official Maynooth University publication.</p>
    <h2 id="m-about">About this analysis</h2>
    <div class="methods" id="m-aboutBody">
<!--__ABOUT__-->
    </div>
    <h2 id="m-overview">Overview</h2>
    <div class="methods" id="m-overviewBody"></div>
    <h2 id="m-times">Travel times</h2>
    <div class="methods" id="m-reach"></div>
    <h2 id="m-cost">What the commute costs</h2>
    <div class="methods" id="m-costBody"></div>
    <h2 id="m-co2">What the commute emits</h2>
    <div class="methods" id="m-co2Body"></div>
    <h2 id="m-burden">Who bears the commute?</h2>
    <div class="methods" id="m-burdenBody"></div>
    <h2 id="m-choice">Does the commute shape the choice?</h2>
    <div class="methods" id="m-choiceBody"></div>
    <h2 id="m-valid">How well does the model match reality?</h2>
    <div class="methods" id="m-validBody"></div>
    <h2 id="m-limits">What this can and cannot say</h2>
    <div class="methods" id="m-limitsBody"></div>
    <h2 id="m-sources">Data sources</h2>
    <div class="scroll"><table>
      <thead><tr><th class="l">Source</th><th class="l">Used for</th><th class="l">Snapshot</th><th class="l">Licence</th></tr></thead>
      <tbody id="srcTbl"></tbody></table></div>
    <p class="note">Raw downloads are kept, dated, in <code>data/raw/</code>; the full licence review is in
      <code>docs/DATA-SOURCES.md</code>. <b>Attribution.</b> Contains Central Statistics Office data (Census 2022), &copy; CSO,
      CC BY 4.0. Contains Tailte &Eacute;ireann boundary data, CC BY 4.0. Public-transport timetables &copy; National Transport
      Authority, CC BY 4.0. Map and routing data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap
      contributors</a>, available under the Open Database Licence. County outlines from geoBoundaries (source: Ordnance Survey
      Ireland), CC BY 4.0. Pobal HP Deprivation Index 2022 (Haase and Pratschke), &copy; Pobal, CC BY 4.0. School details
      from the Department of Education, Data on Individual Schools, CC BY 4.0. Higher-education entrant counts from the Higher Education Authority, CC BY 4.0.</p>
    <h2 id="m-repro">Reproducing the results</h2>
    <div class="methods" id="m-reproBody"></div>
    <h2 id="m-versions">Version history</h2>
    <div class="scroll"><table><tbody id="verTbl"></tbody></table></div>
  </div>
</div></section>

<div id="branchViews"></div>
<!--__MAINS__-->

<script type="application/json" id="d-main">/*__DATA__*/</script>
<script type="application/json" id="d-table">/*__TABLE__*/</script>
<script type="application/json" id="d-counties">/*__COUNTIES__*/</script>
<!--__SECTION_DATA__-->

<script>
/*__APP_JS__*/

const D = APP.json("d-main");
const H = D.h;
const fmt = APP.fmt, eur = APP.eur, esc = APP.esc;
const WORD = n => ["zero","one","two","three","four","five","six","seven","eight","nine","ten"][n] ?? String(n);

const BRANCHES = [
  {id:"area", nav:"Find your area", k:"Start here", t:"From your area to every campus",
   d:"Journey time, annual cost and carbon from any of 1,197 local areas to each of the 14 campuses.",
   f:"For students, families and guidance counsellors", native:true},
  {id:"reach", nav:"Who can reach", k:"Accessibility", t:"Who can reach which campus?",
   d:"Share of young people within reach of each HEI, head-to-head comparisons, car versus public transport, the interactive map and every area in a table.",
   f:"For planners and anyone comparing institutions",
   lead:"How much of the 17 to 19 cohort can reach each campus within a given time, by public transport and by car, at two times of day.",
   parts:[{section:"reach"}]},
  {id:"cost", nav:"Cost", k:"Cost", t:"What does the commute cost?", parts:[{section:"cost"}],
   d:"The yearly cost of the journey to each campus by student fare, commuter coach or car, by county.",
   f:"For student support, access and HR",
   lead:"What a year of commuting costs: student and Young Adult public-transport fares, the Maynooth commuter coaches, or car fuel, parking and tolls. Cost may deter enrolment as much as time does, especially for lower-income students a long way from campus."},
  {id:"emits", nav:"Carbon", k:"Emissions", t:"What does the commute emit?", parts:[{section:"co2"}],
   d:"The CO₂ of a year of commuting by car and by public transport, with every assumption adjustable.",
   f:"For sustainability and Green Campus planning",
   lead:"The carbon of a year of commuting by car and by public transport. The gap between them widens sharply with distance. Choose a campus and a home county, and move the sliders to change the car, the occupancy, the grid and the load factors."},
  {id:"burden", nav:"Who bears it", k:"Equity", t:"Who bears the commute?", parts:[{section:"burden"}],
   d:"The commute split by circumstance: by area deprivation, for households without a car, and against the SUSI 30 km grant line.",
   f:"For access, student support and policy",
   lead:"The rest of this report averages over everyone. This branch asks who carries the long, costly or impossible journeys, and whether they are the young people with the fewest resources to absorb them. Each table has a map of the areas beside it, coloured to match."},
  {id:"choice", nav:"Choice", k:"Enrolment", t:"Does the commute shape the choice?",
   d:"Whether students enrol where the commute is easier, across eight fields of study, and what data would sharpen the answer.",
   f:"For admissions, recruitment and researchers",
   lead:"Does accessibility predict where students actually enrol? New-entrant flows from each county to each HEI, compared with a gravity model, for eight fields of study.",
   parts:[{section:"choice"}]},
  {id:"maynooth", nav:"Worked example: Maynooth", k:"Worked example", t:"What one institution can do with the data",
   d:"Maynooth as an exemplar: its commuter-coach network, the schools within reach and a recruitment shortlist, and where it departs from its geography.",
   f:"The same tools work for any HEI in the study", ex:true,
   lead:"An illustration of institutional use. Everything here can be run for any of the 14 campuses; Maynooth is shown because it has a distinctive commuter-coach network and because the enrolment model finds it under-recruiting counties on its doorstep. The marketing shortlist is a demonstration of the method, not a recruitment plan.",
   parts:[{section:"reach", tpl:"reach-mu", label:"Coaches, the map and the schools within reach"},
          {section:"choice", tpl:"choice-mu", label:"Enrolment against geography"}]},
  {id:"methods", nav:"Methods & citing", k:"Reference", t:"Methods, data and how to cite",
   d:"How every number was produced, the data sources and their dates, the version history and the citation.",
   f:"For researchers and anyone reusing the work", native:true},
];
const BY = Object.fromEntries(BRANCHES.map(b => [b.id, b]));

// ---------- landing ----------
document.getElementById("hEd").textContent = fmt(APP.T().eds.length);
document.getElementById("hCoh").textContent = fmt(H.cohort);
document.getElementById("answer").innerHTML =
  `<h3>The short answer</h3>
   <p>Almost every young person in the region (<b>${H.car60}%</b>) lives within an hour of a college campus by car,
   but only <b>${H.pt60}%</b> can get there within an hour by public transport, even allowing a drive to the train.</p>
   <p>Public transport is much cheaper and cleaner. To Maynooth, for example, a student fare costs about
   <b>${eur(H.dub_pt[0])} to ${eur(H.dub_pt[1])} a year</b> from Dublin and Kildare and <b>${eur(H.bm_pt[0])} to ${eur(H.bm_pt[1])}</b>
   from the midland and border counties, against <b>${eur(H.bm_fuel[0])} to ${eur(H.bm_fuel[1])}</b> a year in fuel alone
   to drive from the same counties; driving emits roughly ${WORD(Math.round(H.mu_car_kg / H.mu_pt_kg))} times the carbon.</p>
   <p>The commute shapes where students enrol: in the ${WORD(H.n_clean)} fields the data measure cleanly, an institution
   ten minutes further away by car draws <b>${H.decay_lo}% to ${H.decay_hi}% fewer</b> of a county's new entrants.</p>
   <p>Checked against Census 2022, the model agrees on average with the journey times students report (within
   ${Math.abs(H.v_bias)} minutes), though town by town the gap is about ${H.v_mae} minutes, and where public transport is
   slow relative to the car, students do drive (correlation ${H.r_cty} across counties). These are measures of potential
   access, mostly at county scale, not of any individual's choice; <a href="#methods/m-valid">see how the model compares</a>.</p>`;
const tiles = [
  [`${H.pt60}%`, `of 17 to 19 year olds within <b>60 minutes</b> of a campus by public transport (${H.car60}% by car)`],
  [`${H.mu_pt60}%`, `within 60 minutes of <b>Maynooth</b> by public transport (${H.mu_car60}% by car)`],
  [`${H.decay_lo}–${H.decay_hi}%`, `fewer new entrants for each <b>extra 10 minutes</b> by car`],
  [`${eur(H.bm_pt[0])}+`, `a year by public transport to Maynooth from the <b>midlands and border</b>`],
  [`${fmt(H.mu_car_kg)} kg`, `CO₂ a year to drive to Maynooth, against <b>${fmt(H.mu_pt_kg)} kg</b> by public transport`],
];
document.getElementById("tiles").innerHTML = tiles.map(([n,u]) => `<div class="tile"><div class="n">${n}</div><div class="u">${u}</div></div>`).join("");
document.getElementById("cards").innerHTML = BRANCHES.map(b =>
  `<a class="card${b.ex?" ex":""}" href="#${b.id}"><div class="k">${b.k}</div><div class="t">${b.t}</div>
   <div class="d">${b.d}</div><div class="f">${b.f}</div></a>`).join("");
document.getElementById("foot").innerHTML =
  `Individual research and analysis, not an official Maynooth University publication &middot; Version ${esc(D.version)} &middot; data snapshot ${esc(D.snapshot)} &middot; public-transport fares January ${D.fare_year}
   &middot; map and routing data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>
   &middot; <a href="#methods">methods, data, licences and how to cite</a>`;
document.getElementById("nav").innerHTML = BRANCHES.map(b => `<a href="#${b.id}" data-b="${b.id}">${b.nav}</a>`).join("");
document.querySelectorAll(".fy").forEach(e => e.textContent = D.fare_year);

// ---------- theme ----------
document.getElementById("themeBtn").addEventListener("click", () => APP.setTheme(APP.theme() === "dark" ? "light" : "dark"));

function branchShell(b){
  const sec = document.createElement("section");
  sec.className = "view"; sec.id = "v-" + b.id;
  sec.innerHTML = `<div class="wrap" style="padding-bottom:0"><p class="eyebrow">${b.k}</p>
    <h1 class="b">${b.t}</h1><p class="lead">${b.lead}</p>
    <nav class="subnav" id="sn-${b.id}"></nav></div><div id="fr-${b.id}"></div>`;
  document.getElementById("branchViews").appendChild(sec);
  return sec;
}

const norm = s => s.replace(/\s+/g, " ").trim();

function buildBranch(b){
  const sec = branchShell(b);
  const host = sec.querySelector("#fr-" + b.id), sn = sec.querySelector("#sn-" + b.id);
  b.parts.forEach(p => {
    if (b.parts.length > 1 && p.label) {
      const l = document.createElement("p"); l.className = "partlabel"; l.textContent = p.label; host.appendChild(l);
    }
    const body = document.createElement("div");
    body.className = "wrap"; body.style.paddingTop = "0"; body.style.paddingBottom = "0";
    body.appendChild(document.getElementById("main-" + (p.tpl || p.section)).content.cloneNode(true));
    host.appendChild(body);
    body.querySelectorAll("h2[id]").forEach(h => {
      const a = document.createElement("a"); a.href = `#${b.id}/${h.id}`; a.textContent = norm(h.textContent); sn.appendChild(a);
    });
    SECTIONS[p.section].init(body.firstElementChild);
  });
  b.built = true;
}

function scrollToSub(b, sub){
  const h = document.querySelector(`#v-${b.id} [id="${sub}"]`);
  if (h) window.scrollTo({top: h.getBoundingClientRect().top + window.scrollY - document.querySelector(".bar").offsetHeight - 10});
}

// ---------- routing ----------
function go(h){
  try { history.pushState(null, "", "#" + h); } catch (e) {}
  route(h);
}
document.addEventListener("click", e => {
  const a = e.target.closest && e.target.closest('a[href^="#"]');
  if (!a || e.metaKey || e.ctrlKey || e.shiftKey) return;
  e.preventDefault(); go(a.getAttribute("href").slice(1));
});
function route(h){
  if (typeof h !== "string") h = location.hash.slice(1);
  const [id, sub] = (h || "home").split("/");
  const b = BY[id];
  const view = b ? id : "home";
  if (b && !b.native && !b.built) buildBranch(b);
  document.querySelectorAll(".view").forEach(v => v.classList.toggle("on", v.id === "v-" + view));
  document.querySelectorAll("#nav a").forEach(a => a.classList.toggle("on", a.dataset.b === view));
  if (view === "area") areaRoute(sub);
  if (view === "methods") methodsInit();
  if (b && sub && id !== "area") scrollToSub(b, sub); else window.scrollTo(0, 0);
  document.title = b ? `${b.nav} · Commuting to College` : "Commuting to College";
}
window.addEventListener("popstate", () => route());

// ---------- find your area ----------
const T = APP.T();
const edIdx = Object.fromEntries(T.eds.map((e, i) => [e[0], i]));
const label = e => `${e[1]} (${e[2]})`;
const byLabel = Object.fromEntries(T.eds.map((e, i) => [label(e), i]));
document.getElementById("edlist").innerHTML = T.eds.map(label).sort((a, b) => a.localeCompare(b))
  .map(l => `<option value="${esc(l)}">`).join("");
const EX = ["Naas Urban", "Tullamore Urban", "Dundalk No. 4 Urban", "Rathfarnham", "Arklow No. 1 Urban"];
EX.forEach(n => {
  const i = T.eds.findIndex(e => e[1] === n); if (i < 0) return;
  const btn = document.createElement("button"); btn.textContent = n.replace(/ (Urban|No\. \d+ Urban)$/, "");
  btn.onclick = () => go("area/" + T.eds[i][0]);
  document.getElementById("aex").appendChild(btn);
});
const aq = document.getElementById("aq");
let curArea = null;
function pick(){ const i = byLabel[aq.value]; if (i != null && T.eds[i][0] !== curArea) go("area/" + T.eds[i][0]); }
aq.addEventListener("change", pick);
aq.addEventListener("input", () => { if (byLabel[aq.value] != null) pick(); });

function areaRoute(id){
  curArea = id;
  const i = edIdx[id];
  const out = document.getElementById("aout");
  if (i == null) { out.innerHTML = ""; return; }
  const e = T.eds[i]; aq.value = label(e);
  const rows = T.campuses.map(([cid, name]) => {
    const c = T.col[cid];
    if (c.km[i] == null) return null;
    const [ck, pk] = APP.co2Year(c.km[i], c.ft[i]);
    return {name, ptr: c.tptr[i], car: c.tcar[i], km: c.km[i], ptyr: c.ptyr[i], caryr: c.caryr[i], ck, pk};
  }).filter(Boolean);
  const key = r => r.ptr == null ? 1e9 : r.ptr;
  rows.sort((a, b) => key(a) - key(b) || (a.car ?? 1e9) - (b.car ?? 1e9));
  const w60pt = rows.filter(r => r.ptr != null && r.ptr <= 60).length;
  const w60car = rows.filter(r => r.car != null && r.car <= 60).length;
  const best = rows[0];
  const bar = (m, col) => m == null ? "" : `<span class="tb" style="width:${Math.min(m, 150) * .55}px;background:var(${col})"></span>`;
  const t = m => m == null ? `<span class="na">not within reach</span>` : `${m} min`;
  const n = v => v == null ? `<span class="na">&ndash;</span>` : fmt(v);
  out.innerHTML = `<h2>${esc(e[1])} <span style="font-size:.6em;color:var(--muted);font-family:'Public Sans',sans-serif">${esc(e[2])}</span></h2>
    <div class="sum">${fmt(e[3])} people aged 17 to 19 live here. Within an hour, <b>${w60pt}</b> of the 14 campuses can be reached by
    public transport and <b>${w60car}</b> by car. ${best.ptr != null ? `The quickest by public transport is <b>${esc(best.name)}</b>, ${best.ptr} minutes.` : "No campus can be reached by public transport within the modelled window."}</div>
    <div class="panel scroll"><table>
      <thead><tr class="grp"><th class="l"></th><th colspan="2" class="l">Morning journey</th><th></th><th colspan="2">Cost a year</th><th colspan="2">CO₂ kg a year</th></tr>
      <tr><th class="l">Campus</th><th class="l">Public transport</th><th class="l">Car</th><th>km</th>
        <th>Public transport</th><th>Car</th><th>Public transport</th><th>Car</th></tr></thead>
      <tbody>${rows.map(r => `<tr><td class="l">${esc(r.name)}</td>
        <td class="l">${t(r.ptr)}${bar(r.ptr, "--teal")}</td><td class="l">${t(r.car)}${bar(r.car, "--coral")}</td>
        <td>${r.km ?? ""}</td><td>${r.ptyr == null ? n(null) : eur(r.ptyr)}</td><td>${r.caryr == null ? n(null) : eur(r.caryr)}</td>
        <td>${n(r.pk)}</td><td>${n(r.ck)}</td></tr>`).join("")}</tbody></table></div>`;
}

// ---------- methods ----------
const SOURCES = [
  ["CSO Census 2022 Small Area Population Statistics (incl. car availability) and boundaries; Tailte \u00c9ireann Small Areas", "Population, area weights and centres, car availability, area and county shapes", "27 Aug 2026", "CC BY 4.0 (confirmed)"],
  ["National Transport Authority GTFS (Transport for Ireland, all operators); the snapshot used is archived at <a href=\"https://doi.org/10.5281/zenodo.23121634\">doi.org/10.5281/zenodo.23121634</a>", "Public-transport timetables", "27 Aug 2026", "CC BY 4.0 (confirmed)"],
  ["OpenStreetMap, Geofabrik Ireland extract", "Street and road network for routing (r5py, OSRM)", "27 Aug 2026", "ODbL 1.0 (confirmed); the derived tables are released under ODbL"],
  ["geoBoundaries IRL ADM1 / ADM2 (source: Ordnance Survey Ireland)", "Map outlines", "27 Aug 2026", "CC BY 4.0 (confirmed)"],
  ["Department of Education, Data on Individual Schools: post-primary, final 2025/26 (October Returns)", "Schools in the catchment; Leaving Certificate pupils for the shortlist", "2 Oct 2026", "CC BY 4.0 (confirmed, data.gov.ie record \"Data on Individual Schools\")"],
  ["Pobal HP Deprivation Index 2022, Electoral Division level", "Deprivation bands (Who bears the commute?)", "2 Oct 2026", "CC BY 4.0 (confirmed)"],
  ["CSO Census 2022 tables F7145 and F7065 (students' journey time and means of travel)", "Validation of the model", "2 Oct 2026", "CC BY 4.0 (confirmed)"],
  ["HEA new entrants by county of domicile and institution", "Enrolment (choice) model", "30 Aug 2026", "CC BY 4.0 (confirmed, data.gov.ie record for the HEA Student Record System)"],
  ["CAO 2025 computing course list and points", "Course lists in the enrolment county panel", "27 Aug 2026", "Published facts, cited; not redistributed"],
  ["NTA fare determination; Irish Rail and operator fares; AA Ireland fuel prices", "Cost model", "Jan 2027 fares", "Published figures (cited)"],
  ["SEAI, IPTEM, UK DESNZ conversion factors; EPA per-capita emissions", "Emissions model", "2026", "Published figures (cited)"],
];
let methodsDone = false;
function methodsInit(){
  if (methodsDone) return; methodsDone = true;
  const T = APP.T();
  document.getElementById("cite").textContent =
    `Keating, J. G. (2026). Commuting to College: Accessibility, Cost, Emissions and Choice for Higher Education in Leinster (Version ${D.version}). Maynooth University. https://doi.org/${D.doi}`;
  document.getElementById("m-overviewBody").innerHTML = `
    <p><b>The question.</b> How long, how costly and how carbon-heavy is the daily journey from home to a higher-education
    campus for the young people of Leinster, and does it shape where they enrol? The study measures <i>potential</i>
    accessibility, the journey a student could make, and then tests it against where students actually went.</p>
    <p><b>Where.</b> Fifteen county areas: the four Dublin council areas (Dublin City, D&uacute;n Laoghaire-Rathdown, Fingal and
    South Dublin), Kildare, Meath, Wicklow, Westmeath, Longford, Offaly, Laois, Louth, Carlow, Kilkenny and Monaghan. That is
    all of Leinster except Wexford, plus Monaghan in Ulster. <b>Who.</b> ${fmt(T.eds.length)} Electoral Divisions, each represented by its
    population-weighted centre (from Census 2022 Small Areas) and weighted by its 17 to 19 year olds, the college-entry
    cohort: ${fmt(H.cohort)} people in all. Because the census counts third-level students at their term-time address, its
    18 and 19 year olds cluster beside campuses (Rathfarnham, beside UCD's residences, has 724 aged 18 to 19 against 99 aged
    15 to 16). Each area's weight is therefore its 15 to 17 year olds, who still live at home, scaled so that the regional
    total matches the census count of 17 to 19 year olds; this moves 6.5% of the weight away from campus areas and back to
    where students would commute from. <b>To what.</b> Fourteen campuses: the eleven in and around Dublin (Maynooth, DCU,
    UCD, Trinity, three TU&nbsp;Dublin sites, Marino, NCAD, RCSI, IADT) and three regional campuses (TUS Athlone, Dundalk IT,
    SETU Carlow).</p>
    <p><b>How.</b> Three modes: scheduled public transport; public transport with the option of driving to a railway
    station; and a full car commute. Two timetables: a peak day (arrive about 08:30, leave about 18:30) and a later one
    (arrive about 10:00, leave about 17:00). One representative term Wednesday, ${D.analysis_date}. On top of the journey
    times sit three further models: the annual <b>cost</b> of the commute, its <b>carbon</b>, and a county-scale
    <b>enrolment</b> model of where new entrants actually went.</p>
    <p><b>Built in phases.</b> A pilot of 18 towns (phase 1), 584 Electoral Divisions in Dublin and the commuter counties
    (phase 2), the full region with car travel and two timetables (phase 3), then cost, carbon and the enrolment model
    (phase 4a). The version history below records each step.</p>`;
  SECTIONS.reach.methods(document.getElementById("m-reach"));
  SECTIONS.cost.methods(document.getElementById("m-costBody"));
  SECTIONS.co2.methods(document.getElementById("m-co2Body"));
  SECTIONS.burden.methods(document.getElementById("m-burdenBody"));
  SECTIONS.choice.methods(document.getElementById("m-choiceBody"));
  SECTIONS.valid.methods(document.getElementById("m-validBody"));
  document.getElementById("m-limitsBody").innerHTML = `
    <p>Everything here is <b>potential accessibility</b>: the modelled journey a student could make, not the one they do
    make, and not their choice. The enrolment model is a first look at the link between the two, not proof of cause.
    The main limits, part by part:</p>
    <h4>Travel times</h4>
    <ul>
      <li>Each area is represented by one point, its population-weighted centre, so variation within an Electoral Division
      is lost. Area weights use 15 to 17 year olds as a stand-in for where the college-entry cohort lives at home, which
      assumes the age profile is similar from area to area.</li>
      <li>One representative term Wednesday and one timetable snapshot (August 2026). Times are medians over a 60-minute
      departure window, which under-credits services that run once, such as the Maynooth commuter coaches.</li>
      <li>The car mode assumes a car is available, and that is itself unevenly spread and correlated with the rural areas
      where the car matters most. Congestion is a fixed factor keyed to the destination and time of day, not to the route.</li>
    </ul>
    <h4>Cost and carbon</h4>
    <ul>
      <li>Fares assume every student holds a Student or Young Adult Leap Card. January 2027 caps and regional fares scale
      the earlier figures by the announced 15%, pending the full fare table. Campus parking charges are assumptions, and
      the toll rule is crude.</li>
      <li>Lift-sharing, cycling and the alternative of renting near campus are not modelled.</li>
      <li>Carbon is operational only (tank-to-wheel or plug-to-wheel); routed road distance stands in for public-transport
      route distance.</li>
    </ul>
    <h4>Enrolment</h4>
    <ul>
      <li>County scale, with Dublin as a single cell; seven years pooled, so any trend is hidden; counts rounded to the
      nearest 5 by the HEA.</li>
      <li>The student's <i>home</i> county, not where they live in term. About half of Irish students live away from home
      during term, so the commute deterrent for genuine commuters is likely understated.</li>
      <li>Cross-sectional: course reputation, points and the pull of a home-county campus travel with distance and cannot
      be separated from it. At county scale cost and distance are almost perfectly correlated, so time and money cannot be
      told apart.</li>
      <li>Social Sciences and Education are weak fits (a small, awkwardly bounded field; and providers missing from or
      outside the data) and are indicative only.</li>
    </ul>
    <h4>Schools</h4>
    <ul><li>The schools layer is reach, not feeder flow: it shows which schools a campus is commutable from, not which send
    it students.</li></ul>
    <p>The <a href="#choice/p-sharpen">How to sharpen the answer</a> section sets out the data that would lift the
    enrolment limits, and what each addition would buy.</p>`;
  document.getElementById("m-reproBody").innerHTML = `
    <p>A run is <code>scripts/config.py</code> (every path, date and parameter) plus the dated raw feeds in
    <code>data/raw/</code>. Versions are pinned in <code>docs/environment.md</code> (Python 3.12, r5py with Conveyal R5 on
    OpenJDK 21, OSRM); <code>data/raw/MANIFEST.md</code> lists every input with its source and checksum.
    <code>run_pipeline.sh</code> runs the scripts below in order, with no manual steps:</p>
    <div class="scroll"><table><thead><tr><th class="l">Scripts</th><th class="l">Step</th><th class="l">Writes</th></tr></thead><tbody>
      <tr><td class="l"><code>19</code></td><td class="l">Unzip the census tables, extract the rail stops, crop the road network, build the OSRM car graph</td><td class="l">prepared inputs</td></tr>
      <tr><td class="l"><code>20</code>, <code>21</code></td><td class="l">Area centres and cohorts; campuses</td><td class="l"><code>origins_p3</code>, <code>campuses_p3</code></td></tr>
      <tr><td class="l"><code>22</code></td><td class="l">Public-transport and drive-to-rail times (r5py), both timetables</td><td class="l">cached matrices</td></tr>
      <tr><td class="l"><code>23</code></td><td class="l">Car times (OSRM) with the congestion factors</td><td class="l">cached matrices</td></tr>
      <tr><td class="l"><code>25</code>, <code>26</code></td><td class="l">Combine; accessibility and population-weighted reach</td><td class="l"><code>p3_od_long</code>, <code>p3_ed_access</code>, <code>p3_pop_weighted</code></td></tr>
      <tr><td class="l"><code>28</code>, <code>31</code></td><td class="l">Commuter-coach routes and stops; post-primary schools</td><td class="l"><code>p3_coach_routes</code>, <code>p3_schools</code></td></tr>
      <tr><td class="l"><code>29</code>, <code>32</code></td><td class="l">Cost model; emissions model</td><td class="l"><code>p3_cost</code>, <code>p3_emissions</code></td></tr>
      <tr><td class="l"><code>35</code></td><td class="l">Comparison with census-reported journey times and modes</td><td class="l"><code>p3_validation_towns</code>, <code>p3_validation_counties</code></td></tr>
      <tr><td class="l"><code>34</code></td><td class="l">Deprivation and car availability per area; area and county shapes</td><td class="l"><code>p3_burden_ed</code>, <code>p3_ed_shapes</code></td></tr>
      <tr><td class="l"><code>40</code> to <code>42</code></td><td class="l">HEA flows, county accessibility, gravity model</td><td class="l"><code>p4_flows</code>, <code>p4_model_fit</code>, <code>p4_predictions</code></td></tr>
      <tr><td class="l"><code>44</code></td><td class="l">The annual cost of the commute tested as the friction term</td><td class="l"><code>p4_cost_check</code></td></tr>
      <tr><td class="l"><code>27</code>, <code>30</code>, <code>33</code>, <code>43</code>, <code>50</code></td><td class="l">The four part reports and this merged report, from the shared section code in <code>scripts/sections/</code></td><td class="l"><code>outputs/*.html</code></td></tr>
    </tbody></table></div>
    <p>Design notes for the cost and carbon models are in <code>docs/cost-model.md</code> and <code>docs/emissions-model.md</code>.</p>`;
  document.getElementById("srcTbl").innerHTML = SOURCES.map(s =>
    `<tr><td class="l" style="white-space:normal">${s[0]}</td><td class="l" style="white-space:normal">${s[1]}</td><td class="l">${s[2]}</td><td class="l" style="white-space:normal">${s[3]}</td></tr>`).join("");
  document.getElementById("verTbl").innerHTML = [
    ["Phase 1 to 2", "Aug 2026", "Pilot: 18 towns, then 584 Electoral Divisions in Dublin and the commuter counties, public transport only"],
    ["Phase 3", "Aug 2026", "1,197 Electoral Divisions in 15 county areas, 14 campuses, car mode, two timetables, commuter coaches, schools"],
    ["Cost and emissions", "Sep 2026", "Annual commute cost (January 2027 fares) and CO₂ by mode"],
    ["Phase 4a", "Aug to Sep 2026", "County-scale enrolment model, eight fields of study"],
    ["Corrections", "2 Oct 2026", "Commuter-coach fare catchment widened to every stop; Dún Laoghaire-Rathdown added to the Dublin fare zone"],
    ["Correction", "2 Oct 2026", "Area weights taken from 15 to 17 year olds (rescaled), because the census counts students at their term-time address; reach figures fall by up to 4 points, the enrolment model is essentially unchanged"],
    ["Who bears the commute?", "2 Oct 2026", "Commute by deprivation band, for households without a car, and against the SUSI 30 km line, with area maps"],
    ["Schools source", "2 Oct 2026", "Schools now read from the Department of Education's Data on Individual Schools (final 2025/26, CC BY 4.0) instead of its map layer; same schools and enrolments. The shortlist now ranks by Leaving Certificate pupils rather than total enrolment"],
    ["Validation; county maps", "2 Oct 2026", "Comparison with Census 2022 journey times and modes; county maps beside the county tables"],
    ["Correction", "2 Oct 2026", "Enrolment model: areas with no trip to an HEI inside the time limit now count at the limit in the county average instead of dropping out. The commute effect is unchanged in direction and slightly larger; Maynooth's under-recruitment is now Wicklow in every field and Kildare in Business, Health, Natural Sciences and Social Sciences, not Kildare in every field"],
    [D.version, "Oct 2026", "This merged report"],
  ].map(r => `<tr><td class="l">${esc(r[0])}</td><td class="l">${r[1]}</td><td class="l" style="white-space:normal">${r[2]}</td></tr>`).join("");
  const sn = document.getElementById("sn-methods");
  document.querySelectorAll("#v-methods h2[id]").forEach(h => {
    const a = document.createElement("a"); a.href = `#methods/${h.id}`; a.textContent = h.textContent; sn.appendChild(a); });
}

route();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
