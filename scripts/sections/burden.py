"""Who bears the commute? The commute split by circumstance: by area deprivation (Pobal HP
Deprivation Index 2022), by car availability (Census 2022 SAPS Theme 15) and against the SUSI
30 km grant line. Each part has an area map (ED shapes) coloured to match its table.

Reads outputs/p3_burden_ed.csv and outputs/p3_ed_shapes.json (script 34) and the shared per-ED
table (times, distance, cost per campus).
"""

from __future__ import annotations

import json

import pandas as pd

import config as C

KEY = "burden"
COLS = ("km", "ptyr", "caryr", "tptr", "tcar")


def data() -> dict:
    b = pd.read_csv(C.OUT / "p3_burden_ed.csv", dtype={"id": str})
    b["id"] = b["id"].str.zfill(6)
    shapes = json.loads((C.OUT / "p3_ed_shapes.json").read_text())
    # align to the shared table's ED order (common.ed_table: first appearance in p3_cost)
    cost = pd.read_csv(C.OUT / "p3_cost.csv", dtype={"origin_id": str})
    order = list(cost[cost["schedule"] == "peak"]["origin_id"].str.zfill(6).drop_duplicates())
    b = b.set_index("id").loc[order]
    return {
        "dep": [round(float(v), 1) for v in b["dep_score"]],
        "band": [int(v) for v in b["dep_band"]],
        "nocar": [round(float(v), 3) for v in b["nocar_share"]],
        "path": [shapes["ed"][i] for i in order],
    }


CSS = """
  .sec-burden .bgrid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:1.1rem;align-items:start;margin-top:1rem}
  .sec-burden .bgrid .stat{margin-top:0}
  @media (max-width:880px){.sec-burden .bgrid{grid-template-columns:1fr}}
  .sec-burden .bmap{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:.4rem}
  .sec-burden svg.amap{width:100%;height:auto;display:block}
  .sec-burden svg.amap path.ed{stroke:var(--surface);stroke-width:.25}
  .sec-burden svg.amap path.ed.hl{stroke:var(--ink);stroke-width:1.1}
  .sec-burden svg.amap path.cty{fill:none;stroke:var(--ink);stroke-opacity:.55;stroke-width:.9;pointer-events:none}
  .sec-burden svg.amap text.cl{font-size:10px;font-weight:600;fill:var(--ink);paint-order:stroke;stroke:var(--surface);stroke-width:2.6px;pointer-events:none;text-anchor:middle}
  .sec-burden .blg{display:flex;flex-wrap:wrap;gap:.3rem .9rem;font-size:.74rem;color:var(--muted);margin:.4rem .3rem .2rem}
  .sec-burden .blg span{display:inline-flex;align-items:center;gap:.3rem}
  .sec-burden .blg i{width:11px;height:11px;border-radius:2px;display:inline-block}
  .sec-burden .mono{font-family:"IBM Plex Mono",monospace}
  .sec-burden .big3{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin:.8rem 0 .2rem}
  .sec-burden .big3 .k{background:var(--surface-alt);border-radius:8px;padding:.75rem .7rem}
  .sec-burden .big3 .n{font-family:"Spectral",Georgia,serif;font-size:clamp(1.4rem,4vw,1.9rem);font-weight:600;line-height:1.1;color:var(--navy)}
  .sec-burden .big3 .u{font-size:.76rem;color:var(--muted);margin-top:.2rem;text-align:left}
  @media (max-width:560px){.sec-burden .big3{grid-template-columns:1fr}}
  .sec-burden tr.sel td{background:var(--surface-alt)}
  .sec-burden th{white-space:normal;line-height:1.3}
"""

MAIN = """
<div class="controls">
  <label>Campus <select id="b-camp"></select></label>
  <label>Measure the commute to <select id="b-target">
    <option value="campus">the selected campus</option>
    <option value="nearest">each area's quickest campus by public transport</option></select></label>
</div>
<p class="note">Every figure uses the morning peak and public transport with the option of driving to a station, unless a
  column says otherwise. "Young people" is the college-entry cohort, 17 to 19 year olds, placed where they live at home.</p>

<h2 id="b-dep">Commute by deprivation</h2>
<p class="note">Each area is placed in one of four bands on the Pobal HP Deprivation Index 2022, the same bands the Higher
  Education Authority uses for its socio-economic profiles of students. Does college sit further away, and cost more to
  reach, for young people from disadvantaged areas?</p>
<div class="controls"><label>Areas <select id="b-area">
  <option value="all">All 15 county areas</option><option value="dub">Dublin (four council areas)</option>
  <option value="out">Outside Dublin</option></select></label>
  <label>Map colour <select id="b-depMap"><option value="band">Deprivation band</option>
  <option value="time">Public-transport time</option></select></label></div>
<div class="panel scroll"><table id="b-depTbl">
      <thead><tr><th class="l">Deprivation band</th><th>Young people</th><th>Within 60 min: public transport</th>
        <th>Within 60 min: car</th><th>Typical public-transport time (median)</th><th>Public transport &euro; a year</th>
        <th>Households with no car</th></tr></thead><tbody></tbody></table></div>
<div class="bgrid">
  <div class="bmap"><svg class="amap" id="b-depSvg"></svg><div class="blg" id="b-depLg"></div></div>
  <div><div class="stat" id="b-depStat"></div></div>
</div>

<h2 id="b-car">Without a car</h2>
<p class="note">The rest of this report shows the car commute "if a car is available". Here each area's share of households
  with no car (Census 2022) is taken into account: for those households, public transport <i>is</i> the commute.</p>
<div class="big3" id="b-carBig"></div>
<div class="controls"><label>Count an area as stranded when public transport takes over
  <select id="b-strand"><option value="60">60 min</option><option value="75">75 min</option><option value="90" selected>90 min</option></select></label></div>
<div class="panel scroll"><table id="b-carTbl">
      <thead><tr><th class="l">Area</th><th class="l">County</th><th>Households with no car</th><th>Young people without a car (est.)</th>
        <th>Public transport</th><th>Car</th></tr></thead><tbody></tbody></table></div>
<div class="bgrid">
  <div class="bmap"><svg class="amap" id="b-carSvg"></svg><div class="blg" id="b-carLg"></div></div>
  <div><div class="stat" id="b-carStat"></div></div>
</div>

<h2 id="b-susi">The SUSI 30 km line</h2>
<p class="note">SUSI pays the higher "non-adjacent" maintenance grant only when a student lives 30 km or more from college,
  measured as the shortest road route. Which areas sit under the line, so qualify only for the lower rate, yet face a long
  public-transport commute?</p>
<div class="controls"><label>A long commute is over
  <select id="b-long"><option value="45">45 min</option><option value="60" selected>60 min</option><option value="75">75 min</option></select></label></div>
<div class="panel scroll"><table id="b-susiTbl">
      <thead><tr><th class="l">Area</th><th class="l">County</th><th>Road km</th><th>Public transport</th><th>Car</th>
        <th>Young people</th></tr></thead><tbody></tbody></table></div>
<div class="bgrid">
  <div class="bmap"><svg class="amap" id="b-susiSvg"></svg><div class="blg" id="b-susiLg"></div></div>
  <div><div class="stat" id="b-susiStat"></div></div>
</div>
<p class="note">Road distance here is the routed distance from each area's population-weighted centre; SUSI measures each
  student's own Eircode with Google Maps' shortest route avoiding tolls. Areas within about 3&nbsp;km of the line could fall
  either side for an individual student, and are shown separately on the map.</p>
"""

JS = r"""
SECTIONS.burden = (() => {
  let D = null;
  const BANDS = ["Disadvantaged", "Marginally below average", "Marginally above average", "Affluent"];
  const BCOL = ["var(--coral)", "var(--sand)", "var(--teal)", "var(--navy)"];
  const DUB = new Set(["Dublin City", "Dún Laoghaire-Rathdown", "Fingal", "South Dublin"]);
  const fmt = APP.fmt, pct = v => Math.round(100 * v) + "%";

  function wmedian(pairs){
    const a = pairs.filter(p => p[0] != null).sort((x, y) => x[0] - y[0]), tot = a.reduce((s, p) => s + p[1], 0);
    if (!tot) return null; let acc = 0; for (const p of a) { acc += p[1]; if (acc >= tot / 2) return p[0]; } return a[a.length - 1][0];
  }

  // one row per area, measured to the selected campus or to the area's quickest campus by public transport
  function rows(target){
    const T = APP.T(), cid = APP.campus(), ids = T.campuses.map(c => c[0]);
    return T.eds.map((e, i) => {
      let c = T.col[cid];
      if (target === "nearest") {
        let best = null, bv = Infinity;
        for (const k of ids) { const v = T.col[k].tptr[i] ?? (T.col[k].tcar[i] != null ? 1000 + T.col[k].tcar[i] : null);
          if (v != null && v < bv) { bv = v; best = k; } }
        c = T.col[best || cid];
      }
      return {i, name: e[1], county: e[2], coh: e[3], dub: DUB.has(e[2]), band: D.band[i], dep: D.dep[i], nocar: D.nocar[i],
        ptr: c.tptr[i], car: c.tcar[i], km: c.km[i], ptyr: c.ptyr[i]};
    });
  }

  function makeMap(svg){
    const NS = "http://www.w3.org/2000/svg", el = (t, a) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); return n; };
    const CS = APP.counties();
    svg.setAttribute("viewBox", `0 0 ${CS.svg.w} ${CS.svg.h}`);
    const gE = el("g", {}), gC = el("g", {}), gT = el("g", {}); svg.append(gE, gC, gT);
    const paths = D.path.map((d, i) => { const p = el("path", {d, class: "ed"}); p.append(el("title", {})); gE.append(p); return p; });
    Object.values(CS.county).forEach(d => gC.append(el("path", {d, class: "cty"})));
    Object.entries(CS.label).forEach(([c, [x, y]]) => { const t = el("text", {x, y, class: "cl"}); t.textContent = CS.short[c]; gT.append(t); });
    const mk = el("g", {}); gT.append(mk);
    return {
      paint(fill, title, hl){
        paths.forEach((p, i) => { p.setAttribute("fill", fill(i)); p.firstChild.textContent = title(i); p.classList.toggle("hl", !!(hl && hl(i))); });
      },
      campus(cid){
        mk.innerHTML = ""; const c = cid && CS.campus[cid]; if (!c) return;
        mk.append(el("circle", {cx: c[0], cy: c[1], r: 7, fill: "var(--surface)", stroke: "var(--ink)", "stroke-width": 2}));
        mk.append(el("circle", {cx: c[0], cy: c[1], r: 2.6, fill: "var(--ink)"}));
      },
    };
  }
  const lg = (el, items) => { el.innerHTML = items.map(([c, t, x]) => `<span><i style="background:${c};${x || ""}"></i>${t}</span>`).join(""); };
  const tm = v => v == null ? "&ndash;" : Math.round(v) + " min";
  function timeCol(v){ if (v == null) return "var(--hair-strong)";
    const t = Math.max(0, Math.min(1, (v - 20) / 100)), A = [31, 158, 107], B = [201, 138, 46], Cc = [216, 81, 40];
    const [p, q, f] = t < .5 ? [A, B, t * 2] : [B, Cc, (t - .5) * 2];
    return `rgb(${p.map((x, k) => Math.round(x + (q[k] - x) * f)).join(",")})`; }

  function init(root){
    D = D || APP.json("d-burden");
    const $ = s => root.querySelector(s);
    APP.campusSelect($("#b-camp"));
    const mDep = makeMap($("#b-depSvg")), mCar = makeMap($("#b-carSvg")), mSusi = makeMap($("#b-susiSvg"));
    const target = () => $("#b-target").value, campName = () => target() === "nearest" ? "each area's quickest campus" : APP.campusName();

    function dep(){
      const R = rows(target()), area = $("#b-area").value;
      const F = R.filter(r => area === "all" || (area === "dub" ? r.dub : !r.dub));
      const tot = F.reduce((s, r) => s + r.coh, 0);
      const out = BANDS.map((b, k) => {
        const g = F.filter(r => r.band === k), w = g.reduce((s, r) => s + r.coh, 0);
        if (!w) return null;
        const share = f => g.reduce((s, r) => s + (f(r) ? r.coh : 0), 0) / w;
        return {k, w, pt60: share(r => r.ptr != null && r.ptr <= 60), car60: share(r => r.car != null && r.car <= 60),
          med: wmedian(g.map(r => [r.ptr ?? 9999, r.coh])), cost: g.reduce((s, r) => s + (r.ptyr || 0) * r.coh, 0) / w,
          nocar: g.reduce((s, r) => s + r.nocar * r.coh, 0) / w};
      }).filter(Boolean);
      $("#b-depTbl tbody").innerHTML = out.map(o => `<tr><td class="l"><span style="color:${BCOL[o.k]}">&#9632;</span> ${BANDS[o.k]}</td>` +
        `<td class="mono">${fmt(o.w)} <span style="color:var(--faint)">(${pct(o.w / tot)})</span></td><td class="mono">${pct(o.pt60)}</td><td class="mono">${pct(o.car60)}</td>` +
        `<td class="mono">${o.med >= 9999 ? "no trip" : tm(o.med)}</td><td class="mono">${APP.eur(o.cost)}</td><td class="mono">${pct(o.nocar)}</td></tr>`).join("");
      const lo = out.reduce((a, b) => b.pt60 < a.pt60 ? b : a), hi = out.reduce((a, b) => b.pt60 > a.pt60 ? b : a);
      const where = area === "all" ? "Across the region" : area === "dub" ? "In Dublin" : "Outside Dublin";
      $("#b-depStat").innerHTML = `${where}, measured to <b>${campName()}</b>, the band with the poorest public-transport reach is
        <b>${BANDS[lo.k].toLowerCase()}</b> (${pct(lo.pt60)} within an hour) and the best is <b>${BANDS[hi.k].toLowerCase()}</b> (${pct(hi.pt60)}).` +
        (area === "all" ? ` Use the Areas filter to compare Dublin with the rest of the region: about 70% of young people in
        disadvantaged areas live in Dublin, close to most campuses, while 71% of those in the marginally-below-average band live
        outside it, in the rural and midland areas where commutes are longest.` : "");
      const byMap = $("#b-depMap").value, sel = new Set(F.map(r => r.i));
      mDep.paint(i => !sel.has(i) ? "var(--surface-alt)" : byMap === "band" ? BCOL[D.band[i]] : timeCol(R[i].ptr),
        i => `${R[i].name}, ${R[i].county}\n${BANDS[D.band[i]]} (index ${D.dep[i]})\nPublic transport ${R[i].ptr == null ? "not within reach" : Math.round(R[i].ptr) + " min"}`);
      byMap === "band" ? lg($("#b-depLg"), BANDS.map((b, k) => [BCOL[k], b]))
        : lg($("#b-depLg"), [[timeCol(30), "30 min"], [timeCol(60), "60 min"], [timeCol(90), "90 min"], [timeCol(120), "120 min or more"], ["var(--hair-strong)", "not within reach"]]);
    }

    function car(){
      const R = rows(target()), thr = +$("#b-strand").value, W = R.reduce((s, r) => s + r.coh, 0);
      const best = r => Math.min(r.ptr ?? Infinity, r.car ?? Infinity);
      const sh = f => R.reduce((s, r) => s + f(r) * r.coh, 0) / W;
      const all = sh(r => best(r) <= 60), real = sh(r => (1 - r.nocar) * (best(r) <= 60) + r.nocar * (r.ptr != null && r.ptr <= 60)),
        pto = sh(r => r.ptr != null && r.ptr <= 60);
      $("#b-carBig").innerHTML = [[pct(all), "within an hour of " + campName() + " if every household had a car"],
        [pct(real), "allowing for the households that have no car"], [pct(pto), "by public transport alone"]]
        .map(([n, u]) => `<div class="k"><div class="n">${n}</div><div class="u">${u}</div></div>`).join("");
      const stranded = R.filter(r => r.ptr == null || r.ptr > thr).map(r => ({...r, carless: r.coh * r.nocar}))
        .sort((a, b) => b.carless - a.carless);
      const totCarless = stranded.reduce((s, r) => s + r.carless, 0);
      $("#b-carTbl tbody").innerHTML = stranded.slice(0, 15).map(r => `<tr><td class="l">${r.name}</td><td class="l">${r.county}</td>` +
        `<td class="mono">${pct(r.nocar)}</td><td class="mono">${fmt(r.carless)}</td><td class="mono">${r.ptr == null ? "not within reach" : tm(r.ptr)}</td><td class="mono">${tm(r.car)}</td></tr>`).join("");
      $("#b-carStat").innerHTML = `An estimated <b>${fmt(totCarless)} young people</b> live in households without a car in areas where public
        transport to ${campName()} takes more than ${thr} minutes or is not available: for them there is no realistic daily commute. The
        table lists the 15 areas with the most; the map outlines all ${stranded.length}.`;
      const ncCol = v => { const t = Math.min(1, v / 0.4); return `rgba(216,81,40,${(0.08 + 0.85 * t).toFixed(2)})`; };
      const sset = new Set(stranded.map(r => r.i));
      mCar.paint(i => ncCol(D.nocar[i]), i => `${R[i].name}, ${R[i].county}\n${pct(D.nocar[i])} of households have no car\nPublic transport ${R[i].ptr == null ? "not within reach" : Math.round(R[i].ptr) + " min"}`,
        i => sset.has(i));
      lg($("#b-carLg"), [[ncCol(0.02), "under 5% of households without a car"], [ncCol(0.15), "15%"], [ncCol(0.3), "30%"], [ncCol(0.45), "40% or more"],
        ["var(--surface)", `outlined: public transport over ${thr} min`, "outline:1.5px solid var(--ink)"]]);
    }

    function susi(){
      const R = rows(target()), lim = +$("#b-long").value;
      const under = R.filter(r => r.km != null && r.km < 30), longU = under.filter(r => r.ptr == null || r.ptr > lim);
      const nU = under.reduce((s, r) => s + r.coh, 0), nL = longU.reduce((s, r) => s + r.coh, 0);
      $("#b-susiStat").innerHTML = `Measured to <b>${campName()}</b>: <b>${fmt(nU)}</b> young people live under 30&nbsp;km by road, so would
        receive the lower adjacent rate. Of them, <b>${fmt(nL)}</b> (${nU ? pct(nL / nU) : "0%"}) face a public-transport commute over
        ${lim} minutes each way.`;
      $("#b-susiTbl tbody").innerHTML = longU.sort((a, b) => b.coh - a.coh).slice(0, 15).map(r => `<tr><td class="l">${r.name}</td><td class="l">${r.county}</td>` +
        `<td class="mono">${r.km.toFixed(1)}</td><td class="mono">${r.ptr == null ? "not within reach" : tm(r.ptr)}</td><td class="mono">${tm(r.car)}</td><td class="mono">${fmt(r.coh)}</td></tr>`).join("")
        || `<tr><td class="l" colspan="6" style="color:var(--faint)">No area under 30 km has a public-transport commute this long.</td></tr>`;
      const cat = r => r.km == null ? 4 : (r.km < 30 && (r.ptr == null || r.ptr > lim)) ? 0 : Math.abs(r.km - 30) <= 3 ? 1 : r.km < 30 ? 2 : 3;
      const CC = ["var(--coral)", "var(--sand)", "var(--teal)", "var(--surface-alt)", "var(--hair-strong)"];
      mSusi.paint(i => CC[cat(R[i])], i => `${R[i].name}, ${R[i].county}\n${R[i].km == null ? "" : R[i].km.toFixed(1) + " km by road"}\nPublic transport ${R[i].ptr == null ? "not within reach" : Math.round(R[i].ptr) + " min"}`);
      lg($("#b-susiLg"), [[CC[0], `under 30 km, public transport over ${lim} min`], [CC[1], "within 3 km of the line"], [CC[2], "under 30 km"], [CC[3], "30 km or more"]]);
    }

    function all(){
      const nearest = target() === "nearest";
      [mDep, mCar, mSusi].forEach(m => m.campus(nearest ? null : APP.campus()));
      dep(); car(); susi();
    }
    APP.onCampus(all);
    ["#b-target", "#b-area", "#b-depMap"].forEach(s => $(s).addEventListener("change", s === "#b-target" ? all : dep));
    $("#b-strand").addEventListener("change", car);
    $("#b-long").addEventListener("change", susi);
    all();
  }

  function methods(el){
    el.innerHTML = `
    <p><b>Deprivation.</b> The Pobal HP Deprivation Index 2022 (Haase and Pratschke), published by Pobal at Electoral Division level under
    CC BY 4.0, combines Census 2022 measures of age dependency, lone parenthood, education, social class, unemployment and housing into a
    single relative score. Areas are grouped into the four bands the HEA uses for its socio-economic profiles of students: disadvantaged
    (below &minus;10), marginally below average (&minus;10 to 0), marginally above average (0 to 10) and affluent (above 10). Scores
    describe the area, not the household: a disadvantaged family can live in an affluent area and the reverse.</p>
    <p><b>Car availability.</b> Census 2022 Small Area statistics, Theme 15.1 (households by number of cars), summed to Electoral
    Division; the share with no car excludes households that did not state. The estimate of young people without a car applies the
    area's share of car-less households to its 17 to 19 cohort; households with teenagers are probably more likely than average to have
    a car, and a car in the household may not be available to the student, so the estimate cuts both ways. "Allowing for car
    ownership" counts car-less households as able to commute only by public transport.</p>
    <p><b>The SUSI line.</b> SUSI pays the non-adjacent rate when a student's normal residence is 30&nbsp;km or more from college,
    measured with Google Maps as the shortest route avoiding tolls (the threshold was cut from 45&nbsp;km in Budget 2022). The study's
    distance is the routed road distance (OSRM, fastest route) from each area's population-weighted centre, so areas near the line are
    approximate; the fastest route can be a little longer than the shortest.</p>
    <p><b>Shapes.</b> Electoral Division and county outlines are dissolved from the Census 2022 Small Area boundaries and simplified to
    about 120&nbsp;m for display. Parameters and the join: <code>scripts/34_burden_p3.py</code>.</p>`;
  }

  return {init, methods};
})();
"""
