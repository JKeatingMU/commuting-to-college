"""Shared pieces for the report sections: campus names, the per-ED x campus table, style tokens,
the client-side APP state (campus, theme) and a standalone page wrapper.

A section module (cost.py, carbon.py, ...) exposes:
  data()   -> dict, the section's own small payload (the big per-ED table is shared, see ed_table)
  CSS      -> str, styles scoped under .sec-<key>
  MAIN     -> str, the section markup (h2 headings become the branch's sub-navigation)
  JS       -> str, registers SECTIONS.<key> = {init(root, ctx), methods(el, ctx)}
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

import config as C

CAMPUS_ORDER = ["mu_maynooth", "dcu_glasnevin", "ucd_belfield", "tcd_college_green",
                "tud_grangegorman", "tud_blanchardstown", "tud_tallaght", "marino", "ncad",
                "rcsi", "iadt", "tus_athlone", "dkit_dundalk", "setu_carlow"]
CAMPUS_NAME = {
    "mu_maynooth": "Maynooth University", "dcu_glasnevin": "DCU Glasnevin",
    "ucd_belfield": "UCD Belfield", "tcd_college_green": "Trinity College Dublin",
    "tud_grangegorman": "TU Dublin Grangegorman", "tud_blanchardstown": "TU Dublin Blanchardstown",
    "tud_tallaght": "TU Dublin Tallaght", "marino": "Marino Institute of Education",
    "ncad": "NCAD (Thomas St)", "rcsi": "RCSI (St Stephen's Green)", "iadt": "IADT Dún Laoghaire",
    "tus_athlone": "TUS Athlone", "dkit_dundalk": "Dundalk IT", "setu_carlow": "SETU Carlow",
}
FT = {"zone": 0, "coach": 1, "intercity": 2}
MU = "mu_maynooth"


def json_script(obj) -> str:
    """JSON safe to place inside <script type="application/json">."""
    return json.dumps(obj, separators=(",", ":")).replace("<", "\\u003c")


def _v(x, nd=None):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return None
    if nd is None:
        return int(round(float(x)))
    return round(float(x), nd)


def ed_table(only=None) -> dict:
    """One row per ED, one column set per campus: peak-schedule distance, cost, fare bucket and
    morning times. Shared by Find your area, Cost and Carbon (and later the Phase 3 sections)."""
    cost = pd.read_csv(C.OUT / "p3_cost.csv", dtype={"origin_id": str})
    cost = cost[cost["schedule"] == "peak"]
    od = pd.read_csv(C.OUT / "p3_od_long.csv", dtype={"origin_id": str})
    od = od[od["schedule"] == "peak"].pivot_table(
        index=["origin_id", "campus_id"], columns="mode", values="am_p50", aggfunc="first")

    eds = cost.drop_duplicates("origin_id")[["origin_id", "origin", "county", "cohort_17_19"]]
    pos = {o: i for i, o in enumerate(eds["origin_id"])}
    n = len(eds)
    cols = {}
    for cid in CAMPUS_ORDER:
        c = {k: [None] * n for k in ("gc", "km", "fuel", "car", "pt", "ft", "ptyr", "caryr",
                                      "tptr", "tpt", "tcar")}
        for r in cost[cost["campus_id"] == cid].itertuples():
            i = pos[r.origin_id]
            c["gc"][i] = _v(r.gc_km, 1)
            c["km"][i] = _v(r.km_1way, 1)
            c["fuel"][i] = _v(r.car_fuel_day, 2)
            c["car"][i] = _v(r.car_day, 2)
            c["pt"][i] = _v(r.pt_day, 2)
            c["ft"][i] = FT[r.fare_type]
            c["ptyr"][i] = _v(r.pt_year)
            c["caryr"][i] = _v(r.car_year)
            key = (r.origin_id, cid)
            if key in od.index:
                t = od.loc[key]
                c["tptr"][i] = _v(t.get("pt_plus_rail"))
                c["tpt"][i] = _v(t.get("pt"))
                c["tcar"][i] = _v(t.get("car"))
        cols[cid] = {k: v for k, v in c.items() if only is None or k in only}
    return {
        "eds": [[o, nm, cty, int(h)] for o, nm, cty, h in eds.itertuples(index=False)],
        "campuses": [[cid, CAMPUS_NAME[cid]] for cid in CAMPUS_ORDER],
        "col": cols,
        "co2": co2_params(),
    }


def county_shapes() -> dict:
    """County outlines, label points and campus points in the map frame (from script 34)."""
    s = json.loads((C.OUT / "p3_ed_shapes.json").read_text())
    return {k: s[k] for k in ("svg", "county", "label", "short", "campus")}


def co2_params() -> dict:
    return {
        "carG": C.CO2_CAR_G_PER_VKM, "carType": C.CO2_CAR_TYPE,
        "ptG": [C.CO2_PT_G_PER_PKM["zone"], C.CO2_PT_G_PER_PKM["coach"],
                C.CO2_PT_G_PER_PKM["intercity"]],
        "evKwhPerKm": C.CO2_EV_KWH_PER_KM, "gridG": C.CO2_GRID_G_PER_KWH,
        "occ": C.CO2_CAR_OCCUPANCY, "days": C.CO2_COMMUTE_DAYS, "distFactor": C.CO2_PT_DIST_FACTOR,
        "personAnnualT": C.CO2_PERSON_ANNUAL_T, "treeKg": C.CO2_TREE_KG_PER_YEAR,
    }


FONTS = """<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Spectral:wght@500;600&family=Public+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&display=swap">"""

TOKENS = """
  :root{--ground:#f8f9fa;--surface:#fff;--surface-alt:#eef1f3;--ink:#212529;--muted:#565e66;
    --faint:#868e96;--navy:#05668d;--teal:#028090;--coral:#d85128;--coach:#7d2fb8;--sand:#c98a2e;
    --green:#1f9e6b;--blue:#2f6fb0;--hair:#dee2e6;--hair-strong:#c6cdd3;--bar:52px}
  @media (prefers-color-scheme:dark){:root:not([data-theme=light]){--ground:#14181b;--surface:#1c2124;
    --surface-alt:#232a2e;--ink:#e9ecef;--muted:#a7aeb4;--faint:#79828a;--navy:#4ba3c7;--teal:#3cb0be;
    --coral:#ee7a4f;--coach:#c58cf0;--sand:#e0a860;--green:#43c088;--blue:#5b9bd8;--hair:#2c3338;--hair-strong:#3d454b}}
  :root[data-theme=dark]{--ground:#14181b;--surface:#1c2124;--surface-alt:#232a2e;--ink:#e9ecef;
    --muted:#a7aeb4;--faint:#79828a;--navy:#4ba3c7;--teal:#3cb0be;--coral:#ee7a4f;--coach:#c58cf0;
    --sand:#e0a860;--green:#43c088;--blue:#5b9bd8;--hair:#2c3338;--hair-strong:#3d454b}
"""

# Components every section may use. Sections add only what is specific to them.
BASE_CSS = TOKENS + """
  *{box-sizing:border-box}
  body{margin:0;background:var(--ground);color:var(--ink);font-family:"Public Sans",-apple-system,sans-serif;font-size:16px;line-height:1.6}
  a{color:var(--navy)}
  .wrap{max-width:1240px;margin:0 auto;padding:clamp(1.3rem,4vw,3rem) clamp(1rem,4vw,2.4rem) 2rem}
  .eyebrow{font-size:.73rem;font-weight:600;letter-spacing:.14em;text-transform:uppercase;color:var(--navy);margin:0 0 .7rem}
  h1{font-family:"Spectral",Georgia,serif;font-weight:600;font-size:clamp(2rem,5.5vw,3rem);line-height:1.07;margin:0 0 .7rem}
  h2{font-family:"Spectral",Georgia,serif;font-weight:600;font-size:clamp(1.35rem,3.2vw,1.8rem);margin:2.4rem 0 .4rem;
    padding-bottom:.45rem;border-bottom:2px solid var(--ink)}
  h3{font-family:"Spectral",Georgia,serif;font-weight:600;font-size:1.15rem;margin:1.6rem 0 .3rem}
  p.lead{font-size:1.04rem;color:var(--muted);margin:0 0 1rem}
  p.note{font-size:.9rem;color:var(--muted)}
  p,li,.sum,.stat{text-align:justify;hyphens:auto;-webkit-hyphens:auto}
  .byline{font-size:.82rem;color:var(--muted);border-top:1px solid var(--hair);padding-top:.8rem;margin:.2rem 0 1.4rem;text-align:left}
  .byline b{color:var(--ink)}
  .disclaim{font-size:.82rem;color:var(--muted);border-left:3px solid var(--sand);padding:.15rem 0 .15rem .75rem;margin:-.6rem 0 1.4rem}
  .panel{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:1rem;margin-top:1rem}
  .stat,.sum{background:var(--surface-alt);border-radius:8px;padding:.85rem 1rem;margin-top:1rem;font-size:.95rem}
  .stat b,.sum b{color:var(--ink)}
  .controls{display:flex;flex-wrap:wrap;gap:.5rem .9rem;align-items:center;margin:1rem 0 .3rem}
  .controls label{font-size:.72rem;color:var(--muted);text-transform:uppercase;letter-spacing:.05em;
    display:inline-flex;gap:.45rem;align-items:center}
  select{font:inherit;font-size:.9rem;padding:.3rem .5rem;background:var(--surface);color:var(--ink);border:1px solid var(--hair-strong);border-radius:6px}
  .scroll{overflow-x:auto}
  table{width:100%;border-collapse:collapse;font-size:.86rem;color:var(--ink)}
  th,td{text-align:right;padding:.4rem .5rem;border-bottom:1px solid var(--hair);white-space:nowrap;font-variant-numeric:tabular-nums}
  th{font-size:.66rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);font-weight:600;vertical-align:bottom}
  td.l,th.l{text-align:left}
  .lg{display:flex;gap:.5rem 1.2rem;flex-wrap:wrap;font-size:.8rem;color:var(--muted);margin-top:.6rem}
  .lg span{display:inline-flex;align-items:center;gap:.35rem}
  .lg span[data-k]{cursor:pointer;user-select:none}
  .lg span.off{opacity:.35;text-decoration:line-through}
  .lg i{width:10px;height:10px;border-radius:50%;display:inline-block}
  svg.chart text{fill:var(--muted);font-size:11px}
  svg.chart .axl{fill:var(--faint);font-size:11px}
  svg.chart .grid{stroke:var(--hair)}
  .methods{font-size:.9rem;color:var(--muted);line-height:1.6}
  .methods b{color:var(--ink)}
  .methods code{font-family:"IBM Plex Mono",monospace;font-size:.85em;background:var(--surface-alt);padding:.1em .35em;border-radius:4px}
  .methods h4{font-size:.78rem;text-transform:uppercase;letter-spacing:.06em;color:var(--navy);margin:1.4rem 0 .3rem}
  .methods p{margin:.4rem 0}
  .methods .eg{border-left:2px solid var(--hair-strong);padding-left:.7rem;color:var(--faint);font-size:.85rem}
  .methods table{margin:.5rem 0 .3rem}
  .cgrid{display:grid;grid-template-columns:minmax(0,1.35fr) minmax(0,1fr);gap:1.1rem;align-items:start;margin-top:1rem}
  .cgrid > .panel{margin-top:0}
  @media (max-width:860px){.cgrid{grid-template-columns:1fr}}
  .cmapbox{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:.4rem}
  .cmapbox h4{font-size:.74rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:.3rem .4rem 0;font-weight:600}
  svg.cmap{width:100%;height:auto;display:block}
  svg.cmap path.c{stroke:var(--surface);stroke-width:1.2;stroke-linejoin:round}
  svg.cmap path.c:hover{stroke:var(--ink);stroke-width:1.6}
  svg.cmap text.cl{font-size:16px;font-weight:600;fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:2.8px;pointer-events:none;text-anchor:middle}
  svg.cmap text.cv{font-size:14px;fill:var(--muted);paint-order:stroke;stroke:var(--surface);stroke-width:2.6px;pointer-events:none;text-anchor:middle}
  .clg{display:flex;align-items:center;gap:.5rem;font-size:.74rem;color:var(--muted);margin:.35rem .4rem .2rem}
  .clg .ramp{flex:1;max-width:180px;height:9px;border-radius:5px}
"""

# Client-side shared state. Sections read the per-ED table through APP.T() and follow the campus
# chosen anywhere on the page through APP.onCampus().
APP_JS = r"""
const APP = (() => {
  const camL = [], themeL = [];
  let campus = "mu_maynooth", T = null;
  const fmt = n => n == null ? null : Math.round(n).toLocaleString("en-IE");
  const esc = s => String(s).replace(/[&<>"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;"}[c]));
  function json(id){ const el = document.getElementById(id); return el ? JSON.parse(el.textContent) : null; }
  return {
    fmt, esc, json,
    eur: n => "€" + fmt(n),
    T(){ return T || (T = json("d-table")); },
    campus: () => campus,
    campusName: id => (APP.T().campuses.find(c => c[0] === (id || campus)) || [, ""])[1],
    setCampus(id){ if (id === campus) return; campus = id; camL.forEach(f => f(id)); },
    onCampus(f){ camL.push(f); },
    theme: () => document.documentElement.getAttribute("data-theme") || "dark",
    setTheme(t){
      document.documentElement.setAttribute("data-theme", t);
      try { localStorage.setItem("hei-theme", t); } catch (e) {}
      themeL.forEach(f => f(t));
    },
    onTheme(f){ themeL.push(f); },
    css: v => getComputedStyle(document.documentElement).getPropertyValue(v).trim(),
    // a campus <select> that follows, and sets, the shared campus
    campusSelect(sel){
      APP.T().campuses.forEach(([id, nm]) => sel.add(new Option(nm, id)));
      sel.value = campus;
      sel.addEventListener("change", () => APP.setCampus(sel.value));
      APP.onCampus(id => { sel.value = id; });
    },
    // offer a generated file: the artifact viewer's downloads capability when present, else a plain blob link
    async download(filename, text, type){
      let dl = null;
      try { dl = window.claude && window.claude.use ? await window.claude.use("downloads") : null; } catch (e) {}
      if (dl) {
        try { await dl.save({filename, data: text}); }
        catch (e) { if (e && e.code !== "declined") alert("Download unavailable here (" + (e.code || e.message) + ")."); }
        return;
      }
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob([text], {type: (type || "text/plain") + ";charset=utf-8"}));
      a.download = filename; document.body.append(a); a.click(); a.remove();
    },
    // shared county shapes and a reusable county map (choropleth beside a county table)
    counties(){ return APP._cs || (APP._cs = json("d-counties")); },
    countyMap(svg){
      const CS = APP.counties(), NS = "http://www.w3.org/2000/svg";
      const el = (t, a) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); return n; };
      svg.setAttribute("viewBox", `0 0 ${CS.svg.w} ${CS.svg.h}`); svg.classList.add("cmap"); svg.innerHTML = "";
      const gP = el("g", {}), gT = el("g", {}), gM = el("g", {}); svg.append(gP, gT, gM);
      const paths = {}, vals = {};
      Object.entries(CS.county).forEach(([c, d]) => { const p = el("path", {d, class: "c"}); p.append(el("title", {})); gP.append(p); paths[c] = p; });
      Object.entries(CS.label).forEach(([c, [x, y]]) => {
        const t = el("text", {x, y, class: "cl"}); t.textContent = CS.short[c]; gT.append(t);
        const v = el("text", {x, y: y + 16, class: "cv"}); gT.append(v); vals[c] = v; });
      return {
        // fill(name) -> colour, label(name) -> short value text, title(name) -> hover text
        paint(fill, label, title){
          for (const c in paths) { paths[c].setAttribute("fill", fill(c)); paths[c].firstChild.textContent = title ? title(c) : c;
            vals[c].textContent = label ? label(c) : ""; }
        },
        campus(cid){
          gM.innerHTML = ""; const p = cid && CS.campus[cid]; if (!p) return;
          gM.append(el("circle", {cx: p[0], cy: p[1], r: 7, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 2}));
          gM.append(el("circle", {cx: p[0], cy: p[1], r: 2.6, fill: "var(--ink)"}));
        },
      };
    },
    // sequential colour between two rgb triples, t in 0..1
    ramp(a, b){ return t => { t = Math.max(0, Math.min(1, t)); return `rgb(${a.map((x, k) => Math.round(x + (b[k] - x) * t)).join(",")})`; }; },
    rampLegend(el, f, lo, hi){ el.innerHTML = `<span>${lo}</span><span class="ramp" style="background:linear-gradient(90deg,${f(0)},${f(.5)},${f(1)})"></span><span>${hi}</span>`; },
    // CO2 at default settings, the same arithmetic the carbon tool uses
    co2Year(km, ft, s){
      const P = APP.T().co2; s = s || {};
      const days = s.days ?? P.days, occ = s.occ ?? P.occ, type = s.carType ?? P.carType;
      const grid = s.grid ?? P.gridG, load = s.load ?? 1, dist = s.dist ?? P.distFactor;
      const g = type === "ev" ? P.evKwhPerKm * grid : P.carG[type];
      return [km * 2 * days * g / occ / 1000, km * dist * 2 * days * P.ptG[ft] * load / 1000];
    },
  };
})();
const SECTIONS = {};
"""


def section_bundle(mods) -> dict:
    """Collect CSS / data scripts / JS for a list of section modules."""
    return {
        "css": "\n".join(m.CSS for m in mods),
        "data": "\n".join(f'<script type="application/json" id="d-{m.KEY}">{json_script(m.data())}</script>'
                          for m in mods),
        "js": "\n".join(m.JS for m in mods),
    }


def standalone(mod, title: str, eyebrow: str, lead: str) -> str:
    """A self-contained page for one section, built from the same code as the merged report."""
    b = section_bundle([mod])
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{title}</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
{FONTS}
<style>{BASE_CSS}{b["css"]}
  .tbtn{{position:fixed;top:12px;right:14px;z-index:20;width:34px;height:34px;border-radius:8px;
    border:1px solid var(--hair-strong);background:var(--surface);color:var(--ink);cursor:pointer;font-size:15px}}
  @media print{{.tbtn{{display:none}}}}
</style>
<script>(function(){{var t;try{{t=localStorage.getItem("hei-theme")}}catch(e){{}}
  document.documentElement.setAttribute("data-theme",t||"dark");}})();</script>
</head><body>
<button class="tbtn" id="themeBtn" aria-label="Toggle dark or light mode">&#9788;</button>
<div class="wrap" style="max-width:1080px">
  <p class="eyebrow">{eyebrow}</p>
  <h1>{title}</h1>
  <p class="byline"><b>Professor John G. Keating</b>, Associate Dean for Teaching &amp; Learning, Faculty of
    Science &amp; Engineering, Maynooth University. Built with Claude Code assistance.</p>
  <p class="disclaim">This is individual research and analysis. The views, interpretations and any errors are my own; it is not an official Maynooth University publication and does not represent the University&rsquo;s position.</p>
  <p class="lead">{lead}</p>
  <div id="root" class="sec-{mod.KEY}">{getattr(mod, "STANDALONE_MAIN", mod.MAIN)}</div>
  <h2>Methods</h2>
  <div id="methods" class="methods"></div>
  <p class="note" style="margin-top:2rem">Contains Central Statistics Office data (Census 2022), &copy; CSO, CC BY 4.0; Tailte
    &Eacute;ireann boundary data, CC BY 4.0. Public-transport timetables &copy; National Transport Authority, CC BY 4.0. Map and
    routing data &copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, ODbL. Other sources
    and licences: see the merged report's Methods.</p>
</div>
<script type="application/json" id="d-table">{json_script(ed_table(mod.COLS) if mod.COLS else {})}</script>
<script type="application/json" id="d-counties">{json_script(county_shapes())}</script>
{b["data"]}
<script>{APP_JS}
{b["js"]}
document.addEventListener("click", e => {{
  const a = e.target.closest && e.target.closest('a[href^="#"]'); if (!a) return;
  const el = document.getElementById(a.getAttribute("href").split("/")[1] || "");
  if (el) {{ e.preventDefault(); el.scrollIntoView(); }}
}});
document.getElementById("themeBtn").onclick = () => APP.setTheme(APP.theme() === "dark" ? "light" : "dark");
SECTIONS.{mod.KEY}.init(document.getElementById("root"));
SECTIONS.{mod.KEY}.methods(document.getElementById("methods"));
</script>
</body></html>"""
