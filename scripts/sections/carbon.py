"""Carbon section: the CO2 of a year of commuting by car and by public transport, with every
assumption adjustable. All arithmetic is redone client-side from routed distance and the fare
bucket in the shared table. Design, factors and sources: docs/emissions-model.md.
"""

from __future__ import annotations

import pandas as pd

import config as C
from sections.common import CAMPUS_ORDER

KEY = "co2"
COLS = ("km", "ft")   # shared-table columns this section reads


def data() -> dict:
    cty = pd.read_csv(C.OUT / "p3_emissions_by_county.csv")
    return {
        "countyOrder": {cid: list(cty[cty["campus_id"] == cid].sort_values("km_1way")["county"])
                        for cid in CAMPUS_ORDER},
        "fareShort": ["bus and DART", "commuter coach", "intercity rail"],
    }


CSS = """
  .sec-co2 .lab{display:grid;grid-template-columns:1fr 1fr;gap:1.2rem;align-items:stretch;margin-top:1rem}
  .sec-co2 .lab .panel{margin-top:0;display:flex;flex-direction:column}
  .sec-co2 .lab .panel:first-child .sliders{flex:1}
  @media (max-width:760px){.sec-co2 .lab{grid-template-columns:1fr}}
  .sec-co2 .big3{display:grid;grid-template-columns:repeat(3,1fr);gap:.7rem;margin:.2rem 0}
  .sec-co2 .big3 .k{background:var(--surface-alt);border-radius:8px;padding:.8rem .6rem;text-align:center}
  .sec-co2 .big3 .n{font-family:"Spectral",Georgia,serif;font-size:clamp(1.4rem,5vw,2rem);font-weight:600;line-height:1.1}
  .sec-co2 .big3 .n.car{color:var(--coral)} .sec-co2 .big3 .n.pt{color:var(--green)} .sec-co2 .big3 .n.save{color:var(--navy)}
  .sec-co2 .big3 .u{font-size:.7rem;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-top:.2rem}
  @media (max-width:560px){.sec-co2 .big3{grid-template-columns:1fr}}
  .sec-co2 .ctx{font-size:.92rem;color:var(--muted);margin-top:.6rem;text-align:justify;hyphens:auto}
  .sec-co2 .ctx b{color:var(--ink)}
  .sec-co2 .sliders{display:grid;gap:.85rem;margin-top:.3rem}
  .sec-co2 .sld{font-size:.82rem;color:var(--muted)}
  .sec-co2 .sld .row{display:flex;justify-content:space-between;align-items:baseline}
  .sec-co2 .sld b{color:var(--ink);font-variant-numeric:tabular-nums}
  .sec-co2 .sld input[type=range]{width:100%;accent-color:var(--navy);margin-top:.15rem}
  .sec-co2 .sld select{width:100%;margin-top:.15rem}
  .sec-co2 .reset{font:inherit;font-size:.78rem;padding:.25rem .6rem;background:var(--surface-alt);color:var(--muted);
    border:1px solid var(--hair-strong);border-radius:6px;cursor:pointer;margin-top:.7rem;align-self:flex-start}
  .sec-co2 .reset:hover{color:var(--ink)}
  .sec-co2 .chartwrap{position:relative;margin-top:.5rem;cursor:zoom-in;border-radius:8px;transition:background .15s}
  .sec-co2 .chartwrap:hover{background:var(--surface-alt)}
  .sec-co2 svg.chart{width:100%;height:auto;display:block;overflow:visible}
  .co2-modal{position:fixed;inset:0;background:rgba(10,12,10,.72);display:none;align-items:center;
    justify-content:center;z-index:50;cursor:zoom-out;padding:clamp(1rem,4vw,3rem)}
  .co2-modal.show{display:flex}
  .co2-modal .inner{background:var(--surface);border:1px solid var(--hair);border-radius:12px;
    padding:1.4rem 1.6rem;max-width:min(96vw,1000px);width:100%;box-shadow:0 24px 60px rgba(0,0,0,.4)}
  .co2-modal svg{width:100%;height:auto;display:block}
  @media print{.co2-modal{display:none!important}}
"""

_LEGEND = """<div class="lg">
        <span><i style="background:var(--coral)"></i>Car (line)</span>
        <span><i style="background:var(--blue)"></i>Intercity rail</span>
        <span><i style="background:var(--coach)"></i>Commuter coach</span>
        <span><i style="background:var(--green)"></i>Dublin zone</span>
      </div>"""

MAIN = f"""
<div class="controls">
  <label>Campus <select id="e-campus"></select></label>
  <label>Home county <select id="e-county"></select></label>
</div>
<div class="panel">
  <div class="big3">
    <div class="k"><div class="n car" id="e-nCar">-</div><div class="u">kg CO2 a year by car</div></div>
    <div class="k"><div class="n pt" id="e-nPt">-</div><div class="u">by public transport</div></div>
    <div class="k"><div class="n save" id="e-nSave">-</div><div class="u">saved a year</div></div>
  </div>
  <div class="ctx" id="e-ctx"></div>
</div>

<h2 id="co2-assumptions">Adjust the assumptions</h2>
<p class="note">Every figure in this branch is recomputed from routed distance and the emission factors
  below. The chart sits next to the sliders so you can watch it move; its scale is fixed, so a change in
  position is a real change, not a rescaled axis.</p>
<div class="lab">
  <div class="panel">
    <div class="sliders">
      <div class="sld"><div class="row"><span>Commuting days a year</span><b id="e-vDays"></b></div>
        <input type="range" id="e-days" min="80" max="185" step="5"></div>
      <div class="sld"><div class="row"><span>Car powertrain</span><b id="e-vCar"></b></div>
        <select id="e-carType">
          <option value="petrol">Petrol</option><option value="diesel">Diesel</option>
          <option value="hybrid">Hybrid</option><option value="phev">Plug-in hybrid</option>
          <option value="ev">Battery electric</option></select></div>
      <div class="sld"><div class="row"><span>People in the car (lift-sharing)</span><b id="e-vOcc"></b></div>
        <input type="range" id="e-occ" min="1" max="4" step="0.5"></div>
      <div class="sld"><div class="row"><span>Grid carbon intensity (g CO2 per kWh)</span><b id="e-vGrid"></b></div>
        <input type="range" id="e-grid" min="80" max="360" step="10"></div>
      <div class="sld"><div class="row"><span>Public-transport load factor</span><b id="e-vLoad"></b></div>
        <input type="range" id="e-load" min="0.6" max="1.6" step="0.05"></div>
      <div class="sld"><div class="row"><span>Public-transport route against road distance</span><b id="e-vDist"></b></div>
        <input type="range" id="e-dist" min="0.85" max="1.3" step="0.05"></div>
    </div>
    <button class="reset" id="e-reset">Reset to defaults</button>
    <div class="ctx" id="e-factLine"></div>
  </div>
  <div class="panel">
    <p class="note" style="margin-top:0">Annual commute CO<sub>2</sub> against one-way road distance.
      Each dot is one of 1,197 Electoral Divisions; the line is the car. Click the chart to enlarge it.</p>
    <div class="chartwrap" id="e-chartWrap" title="Click to enlarge">
      <svg class="chart" id="e-chart" viewBox="0 0 640 380" preserveAspectRatio="xMidYMid meet"></svg>
    </div>
    {_LEGEND}
  </div>
</div>
<div class="co2-modal" id="e-modal" title="Click to close">
  <div class="inner"><svg class="chart" id="e-chartModal" viewBox="0 0 640 380" preserveAspectRatio="xMidYMid meet"></svg>
    {_LEGEND}</div>
</div>
<div class="stat" id="e-chartStat"></div>

<h2 id="co2-by-county">By county</h2>
<p class="note">Cohort-weighted for the selected campus, at the current settings. The last column is the
  whole-cohort scale: if every 17 to 19 year old in that county commuted to this campus, the annual
  difference between all of them driving and all of them taking public transport.</p>
<div class="cgrid"><div class="panel scroll"><table id="e-ctyTbl">
  <thead><tr><th class="l">County</th><th>km each way</th><th>Car kg/yr</th>
    <th>PT kg/yr</th><th>Saved kg/yr</th><th>Cohort</th><th>Cohort saving t/yr</th></tr></thead>
  <tbody></tbody></table></div>
<div class="cmapbox"><h4>CO<sub>2</sub> saved a year by switching, kg</h4><svg id="e-cmap"></svg><div class="clg" id="e-cmapLg"></div></div></div>
"""

JS = r"""
SECTIONS.co2 = (() => {
  let D, P, root, S, DEF, campus, cmap, county = "__all__";
  const ptsCache = {}, chartScale = {};
  const $ = s => root.querySelector(s), fmt = n => Math.round(n).toLocaleString("en-IE");

  function pts(cid){
    if (ptsCache[cid]) return ptsCache[cid];
    const t = APP.T(), c = t.col[cid];
    return ptsCache[cid] = t.eds.map((e, i) => c.km[i] == null ? null : [c.km[i], c.ft[i], e[3], e[2]]).filter(Boolean);
  }
  const carG = () => S.carType === "ev" ? P.evKwhPerKm * S.grid : P.carG[S.carType];
  const carKg = km => km * 2 * S.days * carG() / S.occ / 1000;
  const ptKg = (km, f) => km * S.dist * 2 * S.days * P.ptG[f] * S.load / 1000;

  function agg(cf){
    let car = 0, pt = 0, km = 0, w = 0; const fc = [0, 0, 0];
    for (const [d, f, coh, cty] of pts(campus)) {
      if (cf && cty !== cf) continue;
      car += carKg(d) * coh; pt += ptKg(d, f) * coh; km += d * coh; w += coh; fc[f] += coh;
    }
    return {car: car / w, pt: pt / w, km: km / w, cohort: w, fare: fc.indexOf(Math.max(...fc))};
  }
  function fillCounties(){
    const sel = $("#e-county"); sel.innerHTML = "";
    sel.add(new Option("All counties (cohort-weighted)", "__all__"));
    D.countyOrder[campus].forEach(c => sel.add(new Option(c, c)));
    sel.value = county = "__all__";
  }
  function draw(){
    $("#e-vDays").textContent = S.days;
    $("#e-vOcc").textContent = S.occ.toFixed(1).replace(/\.0$/, "");
    $("#e-vGrid").textContent = Math.round(S.grid);
    $("#e-vLoad").textContent = "x " + S.load.toFixed(2);
    $("#e-vDist").textContent = "x " + S.dist.toFixed(2);
    const cg = carG();
    $("#e-vCar").textContent = Math.round(cg) + " g/km";
    $("#e-days").value = S.days; $("#e-occ").value = S.occ; $("#e-grid").value = S.grid;
    $("#e-load").value = S.load; $("#e-dist").value = S.dist; $("#e-carType").value = S.carType;
    $("#e-factLine").innerHTML = "Now: <b>" + Math.round(cg) + " g CO<sub>2</sub> per km</b> for the car"
      + (S.occ > 1 ? ", shared " + S.occ + " ways" : "")
      + "; public transport <b>" + P.ptG.map(g => Math.round(g * S.load)).join(" / ")
      + "</b> g per passenger-km (zone / coach / rail). Grid intensity only moves the electric car.";

    const {km, fare, car, pt} = agg(county === "__all__" ? null : county), save = car - pt;
    $("#e-nCar").textContent = fmt(car); $("#e-nPt").textContent = fmt(pt);
    $("#e-nSave").textContent = (save >= 0 ? "" : "-") + fmt(Math.abs(save));
    const nm = APP.campusName(campus).split(" (")[0];
    const place = county === "__all__" ? "the average commuter to " + nm : "a " + county + " commuter to " + nm;
    $("#e-ctx").innerHTML = "For <b>" + place + "</b> (about " + Math.round(km) + " km each way, mostly "
      + D.fareShort[fare] + "), switching from the car to public transport saves about <b>" + fmt(save)
      + " kg CO<sub>2</sub> a year</b>: roughly <b>" + fmt(save * 4) + " kg over a four-year course</b>, about <b>"
      + (100 * save / (P.personAnnualT * 1000)).toFixed(0) + "%</b> of one person's annual emissions in Ireland, "
      + "or the yearly uptake of <b>" + fmt(save / P.treeKg) + " trees</b>.";
    drawChart(); drawTable();
  }
  function scaleFor(xmax){
    if (chartScale[campus]) return chartScale[campus];
    const worst = xmax * 2 * 185 * P.carG.petrol / 1000 * 1.08;
    const step = worst > 6000 ? 2000 : worst > 2500 ? 1000 : worst > 1200 ? 500 : 200;
    return chartScale[campus] = {ymax: Math.ceil(worst / step) * step, step};
  }
  function drawChart(){
    const W = 640, H = 380, m = {l:56, r:14, t:12, b:40}, rows = pts(campus);
    const xmax = Math.ceil(Math.max(...rows.map(r => r[0])) / 20) * 20, {ymax, step} = scaleFor(xmax);
    const X = v => m.l + v / xmax * (W - m.l - m.r), Y = v => H - m.b - v / ymax * (H - m.t - m.b);
    const cols = ["--green", "--coach", "--blue"].map(APP.css);
    let g = "";
    for (let yy = 0; yy <= ymax + 1; yy += step) {
      g += `<line class="grid" x1="${m.l}" y1="${Y(yy).toFixed(1)}" x2="${W-m.r}" y2="${Y(yy).toFixed(1)}"/>`;
      g += `<text class="axl" x="${m.l-8}" y="${(Y(yy)+3).toFixed(1)}" text-anchor="end">${fmt(yy)}</text>`;
    }
    const xstep = Math.max(20, Math.round(xmax / 6 / 20) * 20);
    for (let xv = 0; xv <= xmax; xv += xstep)
      g += `<text class="axl" x="${X(xv).toFixed(1)}" y="${H-m.b+16}" text-anchor="middle">${xv}</text>`;
    g += `<text class="axl" x="${(m.l + W - m.r) / 2}" y="${H-6}" text-anchor="middle">one-way road km</text>`;
    g += `<text class="axl" transform="translate(13,${(m.t+H-m.b)/2}) rotate(-90)" text-anchor="middle">kg CO2 per year</text>`;
    for (const r of rows)
      g += `<circle cx="${X(r[0]).toFixed(1)}" cy="${Y(ptKg(r[0], r[1])).toFixed(1)}" r="2" fill="${cols[r[1]]}" opacity="0.5"/>`;
    g += `<line x1="${X(0)}" y1="${Y(0).toFixed(1)}" x2="${X(xmax).toFixed(1)}" y2="${Y(carKg(xmax)).toFixed(1)}" stroke="${APP.css("--coral")}" stroke-width="2.5"/>`;
    $("#e-chart").innerHTML = g; $("#e-chartModal").innerHTML = g;
    $("#e-chartStat").innerHTML = "At the current settings the car emits about <b>" + Math.round(carG() / S.occ)
      + " g CO<sub>2</sub> per kilometre driven</b>; public transport is flatter because a bus or train is shared "
      + "many ways. The vertical gap between the line and the dots is the annual saving from switching mode, and it widens with distance.";
  }
  function drawTable(){
    const rows = D.countyOrder[campus].map(name => ({name, ...agg(name)})).sort((a, b) => a.km - b.km);
    const byC = Object.fromEntries(rows.map(r => [r.name, r.car - r.pt])), vs = Object.values(byC);
    const lo = Math.min(...vs), hi = Math.max(...vs), f = APP.ramp([226, 240, 232], [31, 128, 90]);
    cmap.paint(c => byC[c] != null ? f((byC[c] - lo) / ((hi - lo) || 1)) : "var(--surface-alt)",
      c => byC[c] != null ? fmt(byC[c]) : "", c => byC[c] != null ? `${c}: ${fmt(byC[c])} kg CO2 a year saved by switching from car to public transport` : c);
    cmap.campus(campus);
    APP.rampLegend($("#e-cmapLg"), f, fmt(lo) + " kg", fmt(hi) + " kg");
    $("#e-ctyTbl tbody").innerHTML = rows.map(r => {
      const save = r.car - r.pt;
      return `<tr><td class="l">${r.name}</td><td>${Math.round(r.km)}</td><td>${fmt(r.car)}</td><td>${fmt(r.pt)}</td>` +
        `<td>${fmt(save)}</td><td>${fmt(r.cohort)}</td><td>${fmt(save * r.cohort / 1000)}</td></tr>`;
    }).join("");
  }

  function init(r){
    root = r; D = APP.json("d-co2"); P = APP.T().co2;
    DEF = {days: P.days, carType: P.carType, occ: P.occ, grid: P.gridG, load: 1, dist: P.distFactor};
    S = {...DEF}; campus = APP.campus(); cmap = APP.countyMap($("#e-cmap"));
    APP.campusSelect($("#e-campus"));
    fillCounties();
    APP.onCampus(id => { campus = id; fillCounties(); draw(); });
    APP.onTheme(() => requestAnimationFrame(draw));
    $("#e-county").onchange = e => { county = e.target.value; draw(); };
    for (const k of ["days", "occ", "grid", "load", "dist"]) $("#e-" + k).oninput = e => { S[k] = +e.target.value; draw(); };
    $("#e-carType").onchange = e => { S.carType = e.target.value; draw(); };
    $("#e-reset").onclick = () => { S = {...DEF}; draw(); };
    const modal = $("#e-modal");
    $("#e-chartWrap").onclick = () => modal.classList.add("show");
    modal.onclick = () => modal.classList.remove("show");
    addEventListener("keydown", e => { if (e.key === "Escape") modal.classList.remove("show"); });
    draw();
  }

  function methods(el){
    const P = APP.T().co2, cg = P.carG;
    el.innerHTML = `
    <p>Operational CO<sub>2</sub> only: tank-to-wheel for fuel, plug-to-wheel for electricity. Fuel supply
      (about +20 to 25% for petrol and diesel), vehicle and battery manufacture, and rail and road construction
      are <b>not</b> included; adding them widens the gap between car and public transport for combustion cars.</p>
    <h4>Car: grams CO<sub>2</sub> per vehicle-km, single occupant, real-world driving</h4>
    <div class="scroll"><table><thead><tr><th class="l">Powertrain</th><th>g per vehicle-km</th></tr></thead><tbody>
      <tr><td class="l">Petrol</td><td>${cg.petrol}</td></tr>
      <tr><td class="l">Diesel</td><td>${cg.diesel}</td></tr>
      <tr><td class="l">Hybrid</td><td>${cg.hybrid}</td></tr>
      <tr><td class="l">Plug-in hybrid</td><td>${cg.phev}</td></tr>
      <tr><td class="l">Battery electric</td><td>${cg.ev} (at ${P.gridG} g/kWh grid)</td></tr>
    </tbody></table></div>
    <p>Basis: the Irish Passenger Transport Emissions and Mobility (IPTEM) model puts the private-car fleet at
      about 120 g CO<sub>2</sub> per <i>passenger</i>-km at an occupancy of 1.49, which is roughly 180 g per
      <i>vehicle</i>-km. The official new-car figure (114 g/km, SEAI 2023) is a laboratory number and understates
      real driving by 20 to 40%. DEFRA's "average car" is about 170 g per vehicle-km tank-to-wheel.</p>
    <h4>Public transport: grams CO<sub>2</sub> per passenger-km, average load</h4>
    <div class="scroll"><table><thead><tr><th class="l">Service</th><th>g per passenger-km</th></tr></thead><tbody>
      <tr><td class="l">Dublin zone (bus, DART and Luas mix)</td><td>${P.ptG[0]}</td></tr>
      <tr><td class="l">Maynooth commuter coach (UM routes)</td><td>${P.ptG[1]}</td></tr>
      <tr><td class="l">Intercity rail (Irish Rail, mostly diesel)</td><td>${P.ptG[2]}</td></tr>
    </tbody></table></div>
    <p>A scheduled bus or train runs whether or not one more student boards, so its fuel is spread over its typical
      passenger count: the standard average-load convention (SEAI, DEFRA). The <i>marginal</i> emission of one
      extra passenger on an existing service is close to zero. Cross-checks: DEFRA national rail about 35 g per
      passenger-km, local bus about 101, coach about 27.</p>
    <h4>The biggest approximation</h4>
    <p>Public-transport route distance is not in the journey data, so <b>routed road distance is used for both
      modes</b>. Rail alignments run a little shorter than the road, regional bus routes a little longer; the
      slider lets you push this either way. A proper public-transport distance from the timetable geometry would
      tighten every transport figure, rail most of all.</p>
    <h4>Other caveats</h4>
    <p>The Dublin-zone figure blends bus, DART and Luas: a student entirely on the DART emits far less, one
      entirely on a diesel bus close to 100 g per km. The coach figure assumes the UM routes run reasonably full.
      The commuting-days default is ${P.days}, an illustrative full-year pattern. The cohort-scale column is a
      hypothetical (not every young person in a county goes to the selected campus), included to show the order
      of magnitude, not as a forecast.</p>
    <h4>Sources</h4>
    <p>SEAI, <i>Energy in Ireland</i> and transport CO<sub>2</sub> statistics; the Irish Passenger Transport
      Emissions and Mobility (IPTEM) model, <i>Data in Brief</i>; UK DEFRA / DESNZ greenhouse-gas conversion
      factors (cross-check); EPA Ireland national inventory (per-capita context). Distances come from the study's
      OSRM road matrix; the fare bucket (zone, coach or rail) comes from the cost model. Parameters:
      <code>scripts/config.py</code>; computation: <code>scripts/32_emissions_p3.py</code>; design notes:
      <code>docs/emissions-model.md</code>.</p>`;
  }

  return {init, methods};
})();
"""
