"""Cost section: what a year of commuting costs, by campus, county and fare type.

Per-ED points come from the shared table (common.ed_table); this module adds the county
roll-up, the headline figures and the model parameters. Design: docs/cost-model.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C
from sections.common import CAMPUS_NAME, CAMPUS_ORDER, MU

KEY = "cost"
COLS = ("gc", "fuel", "car", "pt", "ft")   # shared-table columns this section reads
BORDER_MIDLAND = {"Carlow", "Kilkenny", "Laois", "Longford", "Louth", "Monaghan", "Offaly", "Westmeath"}


def data() -> dict:
    cost = pd.read_csv(C.OUT / "p3_cost.csv", dtype={"origin_id": str})
    cost = cost[cost["schedule"] == "peak"]
    cty = pd.read_csv(C.OUT / "p3_cost_by_county.csv")

    counties, head = {}, {}
    for cid in CAMPUS_ORDER:
        g = cost[cost["campus_id"] == cid]
        cg = cty[cty["campus_id"] == cid].sort_values("km_1way")
        counties[cid] = [[r["county"], int(r["km_1way"]), r["car_fuel_day"], r["car_day"],
                          r["pt_day"], int(r["pt_year"]), int(r["cohort"])]
                         for r in cg.to_dict("records")]
        tot = g["cohort_17_19"].sum()
        by_pt = cg.sort_values("pt_day")
        ftc = g.groupby("fare_type")["cohort_17_19"].sum()
        head[cid] = {
            "wpt": round((g["pt_day"] * g["cohort_17_19"]).sum() / tot, 2),
            "wfuel": round((g["car_fuel_day"] * g["cohort_17_19"]).sum() / tot, 2),
            "far_c": by_pt.iloc[-1]["county"], "far_y": int(by_pt.iloc[-1]["pt_year"]),
            "near_c": by_pt.iloc[0]["county"], "near_y": int(by_pt.iloc[0]["pt_year"]),
            "ft": {k: round(100 * ftc.get(k, 0) / tot) for k in ("zone", "coach", "intercity")},
        }

    mu = cost[cost["campus_id"] == MU]
    far = [np.average(g["pt_year"], weights=g["cohort_17_19"])
           for c, g in mu.groupby("county") if c in BORDER_MIDLAND]

    fu = C.FUEL[C.FUEL_TYPE]
    dz = C.FUEL["diesel"]
    return {
        "counties": counties, "head": head,
        "params": {
            "fuel_l": fu["eur_per_litre"], "fuel_100": fu["litre_per_100km"],
            "fuel_km": round(C.FUEL_EUR_PER_KM, 3),
            "diesel_l": dz["eur_per_litre"], "diesel_100": dz["litre_per_100km"],
            "diesel_km": round(dz["eur_per_litre"] * dz["litre_per_100km"] / 100, 3),
            "car_full": C.CAR_FULL_EUR_PER_KM,
            "leap": C.LEAP_90MIN_EUR, "dcap": C.LEAP_DAILY_CAP_EUR, "wcap": C.LEAP_WEEKLY_CAP_EUR,
            "coach": round(C.COACH_EUR_PER_DAY, 2), "coach_wk": C.COACH_WEEKLY_EUR,
            "coach_catch": C.COACH_CATCHMENT_KM, "coach_stop": C.COACH_STOP_KM,
            "days_yr": C.COMMUTE_DAYS_PER_YEAR,
            "reg_base": C.REGIONAL_DAILY_BASE, "reg_km": C.REGIONAL_DAILY_PER_KM,
            "reg_floor": round(2 * C.LEAP_90MIN_EUR, 2), "pnr": C.PARK_AND_RIDE_EUR,
            "toll_m50": C.TOLL_M50_EUR, "toll_m4": C.TOLL_M4_EUR, "toll_m1": C.TOLL_M1_EUR,
            "m50_gpo": C.M50_TOLL_MIN_GPO_KM, "dshz_km": C.DSHZ_MAX_KM_FROM_GPO,
            "dshz_counties": sorted(c.title() for c in C.DSHZ_COUNTIES),
            "parking": [[CAMPUS_NAME[c], C.CAMPUS_PARKING_EUR[c]] for c in CAMPUS_ORDER],
            "mu_parking": C.CAMPUS_PARKING_EUR[MU],
            # Irish Rail Young-Adult single fares, Aug 2026, and the 2026 regional-model
            # coefficients they were fitted to (the deployed model scales these by 15% for 2027).
            "cal": [["Carlow", 73, 8.20, 9.95], ["Portlaoise", 78, 8.60, 12.65],
                    ["Athlone", 120, 10.80, 16.65]],
            "reg_base_2026": 4.0, "reg_km_2026": 0.052,
            "mu_far": [int(round(min(far), -1)), int(round(max(far), -1))],
        },
    }


CSS = """
  .sec-cost .chartwrap{position:relative;max-width:940px;margin:0 auto}
  .sec-cost svg.chart{width:100%;height:auto;display:block;overflow:hidden;touch-action:none;cursor:grab}
  .sec-cost svg.chart.grabbing{cursor:grabbing}
  .sec-cost .chartctl{position:absolute;right:6px;top:6px;display:flex;flex-direction:column;gap:4px}
  .sec-cost .chartctl button{width:26px;height:26px;border:1px solid var(--hair-strong);background:var(--surface);
    color:var(--ink);border-radius:6px;cursor:pointer;font-size:14px;line-height:1;font-family:inherit}
  .sec-cost .chartctl button:hover{border-color:var(--navy)}
  .sec-cost .offnote{font-size:.74rem;color:var(--faint);margin:.4rem 0 0}
"""

MAIN = """
<div class="controls"><label>Campus <select id="c-camp"></select></label></div>
<div class="panel">
  <div class="chartwrap">
    <svg class="chart" id="c-chart" viewBox="0 0 720 380" preserveAspectRatio="xMidYMid meet" shape-rendering="geometricPrecision"></svg>
    <div class="chartctl">
      <button id="c-zin" aria-label="Zoom in">+</button>
      <button id="c-zout" aria-label="Zoom out">&minus;</button>
      <button id="c-zrst" aria-label="Reset view">&#8635;</button>
    </div>
  </div>
  <div class="lg" id="c-lg"></div>
  <p class="offnote" id="c-offnote"></p>
</div>
<p class="note">Each dot is one of 1,197 Electoral Divisions: the cost of a round trip per day, peak
  schedule, against straight-line distance to the campus. Axes start at 0 to 150&nbsp;km and
  &euro;0 to &euro;80 a day so campuses compare directly. Scroll to zoom, drag to pan, <b>&#8635;</b> to
  reset; click a legend entry to hide a series.</p>
<div class="stat" id="c-stat"></div>

<h2 id="cost-by-county">By county</h2>
<p class="note">Population-weighted, peak schedule. "Car fuel" is fuel only; "car all-in" adds campus
  parking and any motorway toll. Public transport (PT) is the cheapest of the student rail or bus fare
  or the Maynooth commuter coach.</p>
<div class="cgrid"><div class="panel scroll"><table id="c-ctbl">
  <thead><tr><th class="l">County</th><th>km each way</th><th>Car fuel /day</th>
    <th>Car all-in /day</th><th>PT /day</th><th>PT /year</th></tr></thead>
  <tbody></tbody></table></div>
<div class="cmapbox"><h4>Public transport, &euro; a year</h4><svg id="c-cmap"></svg><div class="clg" id="c-cmapLg"></div></div></div>

<h2 id="cost-fare-bands">Why the public-transport dots form bands</h2>
<p class="note">Choose <b>Maynooth</b> and the public-transport dots split into three: two flat
  horizontal bands and one rising line. That is not a plotting artefact; it is three different fare
  structures in one series.</p>
<div class="panel scroll"><table id="c-ftbl">
  <thead><tr><th class="l">Fare type</th><th class="l">Applies to</th>
    <th>Shape on chart</th><th>Cohort share</th></tr></thead>
  <tbody></tbody></table></div>
<p class="note" id="c-ftnote"></p>
<p class="note" id="c-why"></p>
<p class="note"><b>Caveat on the coach band.</b> It credits the season-ticket price to any area within
  <span class="c-catch"></span> of a weekday Maynooth coach route's starting town, or
  <span class="c-stop"></span> of any stop along it, and assumes a seat is available. These services
  run one to three vehicles per route, so the coach band is a lower bound on cost for those areas, not
  a statement about capacity.</p>
"""

JS = r"""
SECTIONS.cost = (() => {
  let D, P, root, CID, svg, cmap, rowsCache = {};
  const hidden = new Set();
  const $ = s => root.querySelector(s);
  const SERIES = [
    ["zone",  "PT, Dublin zone fare (flat)",            "green", r => r[5] === 0 ? r[3] : null],
    ["coach", "PT, Maynooth commuter coach (flat)",     "coach", r => r[5] === 1 ? r[3] : null],
    ["inter", "PT, intercity fare (rises with distance)", "blue", r => r[5] === 2 ? r[3] : null],
    ["fuel",  "Car, fuel only",                          "sand",  r => r[1]],
    ["car",   "Car, fuel + parking + toll",              "coral", r => r[2]],
  ];
  const MAXX = 150, MAXY = 80, W = 720, H = 380, L = 60, R = 14, T = 14, B = 40;
  let vw = {x0:0, x1:MAXX, y0:0, y1:MAXY}, raf = 0, drag = null;
  const resetView = () => { vw = {x0:0, x1:MAXX, y0:0, y1:MAXY}; };

  function rows(cid){
    if (rowsCache[cid]) return rowsCache[cid];
    const t = APP.T(), c = t.col[cid];
    return rowsCache[cid] = t.eds.map((e, i) => c.gc[i] == null ? null :
      [c.gc[i], c.fuel[i], c.car[i], c.pt[i], e[3], c.ft[i]]).filter(Boolean);
  }
  function niceTicks(lo, hi, target){
    const raw = (hi - lo) / target, mag = Math.pow(10, Math.floor(Math.log10(raw)));
    const step = [1, 2, 2.5, 5, 10].find(s => s * mag >= raw) * mag, out = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(+v.toFixed(6));
    return out;
  }
  function redraw(){ if (raf) return; raf = requestAnimationFrame(() => { raf = 0; draw(); }); }
  function draw(){
    const rs = rows(CID), {x0, x1, y0, y1} = vw;
    const X = v => L + (v - x0) / (x1 - x0) * (W - L - R), Y = v => H - B - (v - y0) / (y1 - y0) * (H - B - T);
    const g = [`<line class="grid" x1="${L}" y1="${H-B}" x2="${W-R}" y2="${H-B}"/>`,
               `<line class="grid" x1="${L}" y1="${T}" x2="${L}" y2="${H-B}"/>`];
    niceTicks(y0, y1, 5).forEach(v => {
      g.push(`<line class="grid" x1="${L}" y1="${Y(v).toFixed(1)}" x2="${W-R}" y2="${Y(v).toFixed(1)}"/>`);
      g.push(`<text class="axl" x="${L-8}" y="${(Y(v)+4).toFixed(1)}" text-anchor="end">${v}</text>`);
    });
    niceTicks(x0, x1, 6).forEach(v =>
      g.push(`<text class="axl" x="${X(v).toFixed(1)}" y="${H-B+16}" text-anchor="middle">${v}</text>`));
    g.push(`<text class="axl" x="${(L+W-R)/2}" y="${H-4}" text-anchor="middle">straight-line distance to campus (km)</text>`);
    g.push(`<text class="axl" transform="translate(15,${(T+H-B)/2}) rotate(-90)" text-anchor="middle">round-trip cost per day (&euro;)</text>`);
    [...SERIES].reverse().forEach(([k, , cv, fn]) => {
      if (hidden.has(k)) return;
      g.push(rs.map(r => {
        const v = fn(r);
        if (v == null || r[0] < x0 || r[0] > x1 || v < y0 || v > y1) return "";
        return `<circle cx="${X(r[0]).toFixed(1)}" cy="${Y(v).toFixed(1)}" r="1.9" fill="var(--${cv})" fill-opacity="0.85"/>`;
      }).join(""));
    });
    svg.innerHTML = g.join("");
    $("#c-lg").innerHTML = SERIES.map(([k, label, cv]) =>
      `<span data-k="${k}" class="${hidden.has(k) ? "off" : ""}"><i style="background:var(--${cv})"></i>${label}</span>`).join("");
    $("#c-lg").querySelectorAll("span").forEach(s => s.onclick = () => {
      const k = s.dataset.k; hidden.has(k) ? hidden.delete(k) : hidden.add(k); redraw(); });
  }
  function chart(){
    resetView();
    const rs = rows(CID), off = rs.filter(r => r[0] > MAXX);
    const oc = off.reduce((a, r) => a + r[4], 0), tc = rs.reduce((a, r) => a + r[4], 0);
    $("#c-offnote").textContent = off.length
      ? `${off.length} distant areas beyond ${MAXX} km (${(100*oc/tc).toFixed(1)}% of this campus's cohort) are outside the default view.` : "";
    if (raf) { cancelAnimationFrame(raf); raf = 0; }
    draw();
  }
  function dataAt(cx, cy){
    const r = svg.getBoundingClientRect(), px = (cx - r.left) / r.width * W, py = (cy - r.top) / r.height * H;
    return [vw.x0 + (px - L) / (W - L - R) * (vw.x1 - vw.x0), vw.y0 + (H - B - py) / (H - B - T) * (vw.y1 - vw.y0)];
  }
  function setView(x0, x1, y0, y1){
    if (x1 - x0 < 4 || y1 - y0 < 3) return;
    x0 = Math.max(0, x0); x1 = Math.min(MAXX, x1); y0 = Math.max(0, y0); y1 = Math.min(MAXY, y1);
    if (x1 - x0 < 4 || y1 - y0 < 3) return;
    vw = {x0, x1, y0, y1}; redraw();
  }
  const zoomAt = (cx, cy, f) => setView(cx - (cx - vw.x0) * f, cx + (vw.x1 - cx) * f, cy - (cy - vw.y0) * f, cy + (vw.y1 - cy) * f);
  function wireChart(){
    svg.addEventListener("wheel", e => { e.preventDefault();
      const [dx, dy] = dataAt(e.clientX, e.clientY); zoomAt(dx, dy, Math.exp(e.deltaY * 0.0016)); }, {passive:false});
    svg.addEventListener("pointerdown", e => { drag = {x:e.clientX, y:e.clientY, v:{...vw}};
      svg.classList.add("grabbing"); svg.setPointerCapture(e.pointerId); });
    svg.addEventListener("pointermove", e => { if (!drag) return;
      const r = svg.getBoundingClientRect();
      const ddx = (e.clientX - drag.x) / r.width * W / (W - L - R) * (drag.v.x1 - drag.v.x0);
      const ddy = (e.clientY - drag.y) / r.height * H / (H - B - T) * (drag.v.y1 - drag.v.y0);
      let x0 = drag.v.x0 - ddx, x1 = drag.v.x1 - ddx, y0 = drag.v.y0 + ddy, y1 = drag.v.y1 + ddy;
      if (x0 < 0) { x1 -= x0; x0 = 0; } if (x1 > MAXX) { x0 -= x1 - MAXX; x1 = MAXX; }
      if (y0 < 0) { y1 -= y0; y0 = 0; } if (y1 > MAXY) { y0 -= y1 - MAXY; y1 = MAXY; }
      vw = {x0, x1, y0, y1}; redraw(); });
    const end = () => { drag = null; svg.classList.remove("grabbing"); };
    svg.addEventListener("pointerup", end); svg.addEventListener("pointercancel", end);
    const mid = () => [(vw.x0 + vw.x1) / 2, (vw.y0 + vw.y1) / 2];
    $("#c-zin").onclick = () => zoomAt(...mid(), 0.7);
    $("#c-zout").onclick = () => zoomAt(...mid(), 1 / 0.7);
    $("#c-zrst").onclick = () => { resetView(); redraw(); };
  }
  function tables(){
    const h = D.head[CID], nm = APP.campusName(CID), ft = h.ft;
    $("#c-ctbl tbody").innerHTML = D.counties[CID].map(r =>
      `<tr><td class="l">${r[0]}</td><td>${r[1]}</td><td>${r[2].toFixed(2)}</td>` +
      `<td>${r[3].toFixed(2)}</td><td>${r[4].toFixed(2)}</td><td>&euro;${r[5].toLocaleString("en-IE")}</td></tr>`).join("");
    const cr = D.counties[CID], byC = Object.fromEntries(cr.map(r => [r[0], r])), ys = cr.map(r => r[5]);
    const lo = Math.min(...ys), hi = Math.max(...ys), f = APP.ramp([241, 225, 196], [216, 81, 40]);
    cmap.paint(c => byC[c] ? f((byC[c][5] - lo) / ((hi - lo) || 1)) : "var(--surface-alt)",
      c => byC[c] ? "\u20ac" + (Math.round(byC[c][5] / 10) * 10).toLocaleString("en-IE") : "",
      c => byC[c] ? `${c}: \u20ac${byC[c][5].toLocaleString("en-IE")} a year by public transport, ${byC[c][1]} km each way` : c);
    cmap.campus(CID);
    APP.rampLegend($("#c-cmapLg"), f, "\u20ac" + lo.toLocaleString("en-IE"), "\u20ac" + hi.toLocaleString("en-IE"));
    $("#c-stat").innerHTML = `Cohort-weighted public-transport cost to <b>${nm}</b>: <b>&euro;${h.wpt.toFixed(2)} a day</b> ` +
      `(fuel-only car &euro;${h.wfuel.toFixed(2)} a day). A student in <b>${h.far_c}</b> pays about ` +
      `<b>&euro;${h.far_y.toLocaleString("en-IE")} a year</b> by public transport, against &euro;${h.near_y.toLocaleString("en-IE")} ` +
      `from <b>${h.near_c}</b>, over ${P.days_yr} round trips.`;
    const rowsF = [
      ["green", "Dublin zone fare", "Areas inside the Dublin Short Hop Zone", "flat (about &euro;2.30 to &euro;3.45 a day)", ft.zone],
      ["coach", "Maynooth commuter coach", "Areas near a weekday Maynooth coach route or its stops", "flat (about &euro;7 a day)", ft.coach],
      ["blue", "Intercity fare", "Everywhere else", "rises with distance", ft.intercity],
    ];
    $("#c-ftbl tbody").innerHTML = rowsF.map(r =>
      `<tr><td class="l"><span style="color:var(--${r[0]})">&#9679;</span> ${r[1]}</td><td class="l">${r[2]}</td><td>${r[3]}</td><td>${r[4]}%</td></tr>`).join("");
    $("#c-ftnote").innerHTML = ft.zone || ft.coach
      ? `For <b>${nm}</b>, ${ft.zone}% of the cohort pays a flat zone fare and ${ft.coach}% a flat coach fare; ` +
        `the remaining ${ft.intercity}% pay a distance-based intercity fare. The two flat groups are the horizontal bands on the chart.`
      : `For <b>${nm}</b>, every area pays a distance-based intercity fare; neither flat regime reaches it, so the public-transport dots form one clean line.`;
  }
  function show(cid){ CID = cid; chart(); tables(); }

  function init(r){
    root = r; D = APP.json("d-cost"); P = D.params; svg = $("#c-chart"); cmap = APP.countyMap($("#c-cmap"));
    root.querySelectorAll(".c-catch").forEach(e => e.innerHTML = `${P.coach_catch}&nbsp;km`);
    root.querySelectorAll(".c-stop").forEach(e => e.innerHTML = `${P.coach_stop}&nbsp;km`);
    $("#c-why").innerHTML = `<b>Why the shapes.</b> A <b>zonal Leap fare</b> is one price for the whole Dublin
      Short Hop Zone: it does not rise with distance, so those areas sit on a flat line (two, really:
      &euro;${(2 * P.leap).toFixed(2)} for a round trip of two 90-minute legs, &euro;${P.dcap.toFixed(2)} once the
      daily cap applies). A <b>commuter-coach season ticket</b> is also one price however far the town is:
      another flat line, at about &euro;${Math.round(P.coach)} a day. Only the <b>intercity fare</b> is charged by
      distance, so only it looks linear. <b>SETU Carlow</b> is a single clean line because neither flat regime
      reaches it: Carlow is outside the Dublin zone, and the Maynooth coach network does not serve it.`;
    APP.campusSelect($("#c-camp"));
    wireChart();
    APP.onCampus(show);
    show(APP.campus());
  }

  function methods(el){
    D = D || APP.json("d-cost"); P = D.params;
    const egFuel = (2 * 40 * P.fuel_km).toFixed(2);
    const parkRows = P.parking.map(r => `<tr><td class="l">${r[0]}</td><td>&euro;${r[1].toFixed(2)}</td></tr>`).join("");
    const calRows = P.cal.map(r => `<tr><td class="l">${r[0]}</td><td>${r[1]}</td><td>&euro;${r[2].toFixed(2)}</td>` +
      `<td>&euro;${r[3].toFixed(2)}</td><td>&euro;${(P.reg_base_2026 + P.reg_km_2026 * r[1]).toFixed(2)}</td>` +
      `<td>&euro;${(P.reg_base + P.reg_km * r[1]).toFixed(2)}</td></tr>`).join("");
    el.innerHTML = `
  <p>Public-transport fares are the <b>NTA fare determination for January 2027</b>, announced on
  3 September 2026: the Young Adult and Student Leap 90-minute Dublin fare rises from &euro;1.00 to &euro;1.15,
  and adult fares by about 15% on average, the first broad adjustment since 2018. The caps and regional
  figures scale the pre-2027 values by that 15%, pending the full fare table. Car fuel and tolls are an
  <b>August 2026</b> snapshot. Every figure is an explicit assumption meant to show the <i>shape</i> of the
  cost gradient, not to be exact to the euro.</p>

  <h4>What the chart shows</h4>
  <p>One dot per Electoral Division (population-weighted centre), plotting the cost of a <b>round-trip</b>
  commute <b>per day</b> against straight-line distance to the selected campus, for the peak schedule
  (arrive about 08:30). It is <i>potential</i> cost: what the trip would cost, not whether anyone makes it.</p>

  <h4>Distances</h4>
  <p>Car distance is routed road kilometres from a local <b>OSRM</b> server on the study's OpenStreetMap
  network (default car profile). The chart and the rail-fare model use straight-line (great-circle)
  distance, written <code>gc_km</code> below.</p>

  <h4>Car: fuel</h4>
  <p><code>fuel &euro;/day = 2 &times; road_km &times; (litres per 100 km &divide; 100) &times; &euro; per litre</code></p>
  <div class="scroll"><table>
    <thead><tr><th class="l">Fuel</th><th>Pump price</th><th>Consumption</th><th>&euro; per km</th></tr></thead>
    <tbody>
      <tr><td class="l">Petrol (headline)</td><td>&euro;${P.fuel_l.toFixed(2)}/L</td><td>${P.fuel_100} L/100 km</td><td>&euro;${P.fuel_km}</td></tr>
      <tr><td class="l">Diesel</td><td>&euro;${P.diesel_l.toFixed(2)}/L</td><td>${P.diesel_100} L/100 km</td><td>&euro;${P.diesel_km}</td></tr>
    </tbody></table></div>
  <p>Pump prices: AA Ireland monthly survey, August 2026. Consumption is a typical real-world combined
  figure. Diesel is about 17% cheaper per km (lower consumption outweighs the dearer fuel).</p>
  <p class="eg"><b>Worked example.</b> An area 40 km by road from campus: 2 &times; 40 &times; &euro;${P.fuel_km}
  = <b>&euro;${egFuel} a day</b> in fuel (about &euro;${Math.round(P.days_yr * egFuel).toLocaleString("en-IE")} a year over ${P.days_yr} round trips).</p>

  <h4>Car: parking and tolls ("all-in")</h4>
  <p>The all-in line adds campus <b>student parking</b> per day (assumed; Dublin campuses are permit-limited,
  so read these as "if a space is available"):</p>
  <div class="scroll"><table><thead><tr><th class="l">Campus</th><th>Parking &euro;/day</th></tr></thead>
    <tbody>${parkRows}</tbody></table></div>
  <p>plus a <b>motorway toll</b> (each way) by a deliberately crude regional rule:</p>
  <div class="scroll"><table><thead><tr><th class="l">Campus group</th><th class="l">Toll rule</th></tr></thead>
    <tbody>
      <tr><td class="l">Dublin campuses</td><td class="l">M50 &euro;${P.toll_m50.toFixed(2)} for areas more than ${P.m50_gpo} km from the GPO and not in Dublin City</td></tr>
      <tr><td class="l">Maynooth</td><td class="l">M4 &euro;${P.toll_m4.toFixed(2)} for areas on the M4 corridor (Kinnegad, Mullingar, Longford, Athlone)</td></tr>
      <tr><td class="l">Dundalk IT</td><td class="l">M1 &euro;${P.toll_m1.toFixed(2)} for areas south of Dunleer</td></tr>
      <tr><td class="l">TUS Athlone</td><td class="l">M4 &euro;${P.toll_m4.toFixed(2)} from the Dublin side</td></tr>
      <tr><td class="l">SETU Carlow</td><td class="l">none (M9 and M7 are toll-free)</td></tr>
    </tbody></table></div>
  <p>The rule keys off the destination and a rough origin region, not the actual route, so it will over- or
  under-charge individual areas. <b>Full running cost</b> (fuel replaced by a &euro;${P.car_full.toFixed(2)}/km
  Revenue civil-service rate, covering depreciation, insurance and maintenance) is in the data files but not
  plotted: a student using the family car feels the marginal cost, not this.</p>

  <h4>Public transport: Dublin zone</h4>
  <p>A Student or Young Adult Leap Card is assumed for the whole 17 to 19 cohort (about 50% off adult fares).
  Inside the Dublin Short Hop Zone the fare is flat: the <b>&euro;${P.leap.toFixed(2)} 90-minute fare</b> (one or
  two per direction), with a <b>&euro;${P.dcap.toFixed(2)} daily cap</b> and <b>&euro;${P.wcap.toFixed(2)} weekly cap</b>.
  "In zone" is a proxy: county in {${P.dshz_counties.join(", ")}} <i>and</i> within ${P.dshz_km} km
  straight-line of the GPO. The true boundary is a station list, so a few areas near the boundary will be
  misclassified.</p>

  <h4>Public transport: regional rail and bus season</h4>
  <p>Outside the zone, a daily commuter buys a <b>Young Adult weekly rail season ticket</b>, so the cost is
  that ticket divided by five:</p>
  <p><code>regional &euro;/day round trip = ${P.reg_base.toFixed(2)} + ${P.reg_km} &times; gc_km</code>
  (floor &euro;${P.reg_floor.toFixed(2)} a day, a local town-bus round trip)</p>
  <p>Calibrated against the <b>Irish Rail fares calculator</b> (Young Adult and Student, August 2026), then
  scaled by the announced 15% for January 2027. A YA weekly season is about 4.7 times the single fare, so a
  season divided by five is about 0.95 times the single, per day, for the whole round trip.</p>
  <div class="scroll"><table>
    <thead><tr><th class="l">From Dublin</th><th>gc km</th><th>YA single (2026)</th>
      <th>YA day return (2026)</th><th>2026 model &euro;/day</th><th>2027 model &euro;/day</th></tr></thead>
    <tbody>${calRows}</tbody></table></div>
  <p>Not separately checked: Bus &Eacute;ireann-only corridors with no rail, and off-peak or annual TaxSaver
  tickets (which would lower this a little).</p>

  <h4>Public transport: Maynooth commuter coach</h4>
  <p>The Maynooth college coach routes (UM02 to UM15; JJ Kavanagh and others) sell a student weekly ticket
  of about &euro;${P.coach_wk}, or <b>&euro;${P.coach.toFixed(2)} a day</b> round trip. It is used wherever it beats
  the rail season and an area is within ${P.coach_catch} km of a weekday route's starting town or
  ${P.coach_stop} km of any pickup stop along it (Tullamore, Kinnegad, Navan, Newbridge and others). This
  assumes a seat is available.</p>

  <h4>Drive-to-rail</h4>
  <p>Computed, but it never lowers the public-transport cost: the whole rail season is still paid, and the
  drive to the station plus &euro;${P.pnr.toFixed(2)} a day park-and-ride only add to it. Drive-to-rail buys
  time, not money.</p>

  <h4>Fare basis and history</h4>
  <p>An August 2026 recalibration replaced a regional model that charged twice the single fare for a round
  trip (about twice too high) with the season-ticket version above, within about 5 to 10% of published
  YA weekly seasons. The January 2027 determination then raised public-transport costs by about 15%,
  close to uniformly, so the shape of cost against distance is unchanged. On 2 October 2026 two
  corrections were made: Dún Laoghaire-Rathdown was added to the Dublin fare zone (a spelling mismatch had
  left it out), and the coach catchment was widened from each route's starting town to every stop. A
  student in the midland and border counties now pays about <b>&euro;${P.mu_far[0].toLocaleString("en-IE")} to
  &euro;${P.mu_far[1].toLocaleString("en-IE")} a year</b> by public transport to Maynooth.</p>

  <h4>Roll-ups and caveats</h4>
  <p>Reported per day and per academic year (<b>${P.days_yr} round trips</b>, an illustrative full-time
  pattern of about 28 teaching weeks of five days). Potential cost only. The car mode assumes a car is
  available, which is itself unevenly distributed. Lift-sharing, cycling and the accommodation alternative
  (a year's rent against the commute) are not modelled. Maynooth sells a flat annual student parking
  permit with a limited number of spaces; the model uses a flat &euro;${P.mu_parking.toFixed(2)} a day for
  all Maynooth car trips.</p>

  <div class="m-standalone"><h4>Reproduce</h4>
  <p>Parameters: <code>scripts/config.py</code>. Computation: <code>scripts/29_costs_p3.py</code>
  (writes <code>outputs/p3_cost.csv</code>). Design notes: <code>docs/cost-model.md</code>.</p></div>`;
  }

  return {init, methods};
})();
"""
