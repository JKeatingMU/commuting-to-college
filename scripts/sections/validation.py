"""How well does the model match reality? A methods-only section comparing the model with what
students reported in Census 2022 (CSO PxStat F7145 by town, F7065 by county). Data from script 35.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

import config as C

KEY = "valid"
COLS = ()
MAIN = ""


def data() -> dict:
    t = pd.read_csv(C.OUT / "p3_validation_towns.csv")
    c = pd.read_csv(C.OUT / "p3_validation_counties.csv")
    big = t[t["weight"] >= 100]
    err = t["model_mix"] - t["reported_min"]
    return {
        "towns": [[r.name, r.county, r.reported_min, r.model_mix, r.model_ptr, r.model_car, r.share_active,
                   r.share_pt, r.share_car, round(r.weight)] for r in t.itertuples()],
        "counties": [[r.county, r.students, r.share_car, r.share_pt, r.share_active, r.model_car_saving] for r in c.itertuples()],
        "stats": {
            "n_towns": len(t), "n_big": len(big),
            "r_mix": round(float(np.corrcoef(t["model_mix"], t["reported_min"])[0, 1]), 2),
            "r_big": round(float(np.corrcoef(big["model_mix"], big["reported_min"])[0, 1]), 2),
            "r_ptr": round(float(np.corrcoef(t["model_ptr"], t["reported_min"])[0, 1]), 2),
            "r_car": round(float(np.corrcoef(t["model_car"], t["reported_min"])[0, 1]), 2),
            "bias": round(float(err.mean()), 1), "mae": round(float(err.abs().mean()), 1),
            "r_cty": round(float(np.corrcoef(c["model_car_saving"], c["share_car"])[0, 1]), 2),
        },
    }


CSS = """
  .vgrid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:1rem;margin-top:1rem}
  svg.vsc{width:100%;max-width:820px;margin:0 auto;height:auto;display:block;background:var(--surface);border:1px solid var(--hair);border-radius:10px}
  svg.vsc .grid{stroke:var(--hair)} svg.vsc .axl{fill:var(--faint);font-size:11px} svg.vsc .lab{fill:var(--muted);font-size:10px}
  svg.vsc .diag{stroke:var(--faint);stroke-dasharray:4 4}
"""

JS = r"""
SECTIONS.valid = (() => {
  const fmt = APP.fmt;
  function scatter(svg, pts, o){
    // pts: [x, y, r, colour, title, label]
    const W = 640, H = 420, L = 54, R = 14, T = 14, B = 44;
    const X = v => L + (v - o.x0) / (o.x1 - o.x0) * (W - L - R), Y = v => H - B - (v - o.y0) / (o.y1 - o.y0) * (H - B - T);
    let g = "";
    for (let v = o.y0; v <= o.y1; v += o.ys) g += `<line class="grid" x1="${L}" y1="${Y(v)}" x2="${W-R}" y2="${Y(v)}"/><text class="axl" x="${L-6}" y="${Y(v)+4}" text-anchor="end">${v}</text>`;
    for (let v = o.x0; v <= o.x1; v += o.xs) g += `<text class="axl" x="${X(v)}" y="${H-B+16}" text-anchor="middle">${v}</text>`;
    if (o.diag) g += `<line class="diag" x1="${X(Math.max(o.x0, o.y0))}" y1="${Y(Math.max(o.x0, o.y0))}" x2="${X(Math.min(o.x1, o.y1))}" y2="${Y(Math.min(o.x1, o.y1))}"/>`;
    g += `<text class="axl" x="${(L + W - R) / 2}" y="${H - 6}" text-anchor="middle">${o.xl}</text>`;
    g += `<text class="axl" transform="translate(14,${(T + H - B) / 2}) rotate(-90)" text-anchor="middle">${o.yl}</text>`;
    for (const [x, y, r, col, title, lab] of pts.slice().sort((a, b) => b[2] - a[2])) {
      g += `<circle cx="${X(x).toFixed(1)}" cy="${Y(y).toFixed(1)}" r="${r}" fill="${col}" fill-opacity="0.7" stroke="var(--surface)"><title>${title}</title></circle>`;
      if (lab) g += `<text class="lab" x="${(X(x) + r + 3).toFixed(1)}" y="${(Y(y) + 3).toFixed(1)}">${lab}</text>`;
    }
    svg.setAttribute("viewBox", `0 0 ${W} ${H}`); svg.innerHTML = g;
  }

  function methods(el){
    const D = APP.json("d-valid"), S = D.stats, CS = APP.counties();
    el.innerHTML = `
    <p>The model measures <i>potential</i> commutes; the census records <i>realised</i> ones. Comparing the two is not a
    test the model should pass exactly, but it shows where it agrees with what students do and where, and why, it does
    not. Two Census 2022 tables from the CSO's statistics database are used, both for students aged 19 and over:
    <b>F7145</b> (average journey time and means of travel, by town) and <b>F7065</b> (means of travel, by county).</p>
    <h4>Do students drive where the model says the car saves most time?</h4>
    <p>For each county, the share of students who travel to college by car (driver or passenger), against the median
    time the model says a car saves over public transport with drive-to-rail. The correlation across the 15 counties is
    <b>${S.r_cty}</b>: where public transport is relatively slow, students drive.</p>
    <div class="vgrid">
      <div class="cmapbox"><h4>Students who drive (census)</h4><svg id="v-map1"></svg><div class="clg" id="v-map1Lg"></div></div>
      <div class="cmapbox"><h4>Minutes the car saves (model)</h4><svg id="v-map2"></svg><div class="clg" id="v-map2Lg"></div></div>
    </div>
    <svg class="vsc" id="v-cty" style="margin-top:1rem"></svg>
    <h4>Do the modelled journey times match the reported ones?</h4>
    <p>For ${S.n_towns} census towns in the study counties, the average journey time students reported, against what the
    model implies for that town given how its students actually travel: the share who go by public transport times the
    modelled public-transport time to the quickest campus, plus the share who drive times the modelled car time, plus 15
    minutes for those who walk or cycle. Each dot is a town, sized by its young population, <b style="color:var(--navy)">navy</b>
    for Dublin and <b style="color:var(--sand)">sand</b> elsewhere; on the dashed line the model and the census agree.</p>
    <svg class="vsc" id="v-town"></svg>
    <p><b>The result.</b> On average the model is close: the mean difference is <b>${S.bias > 0 ? "+" : ""}${S.bias} minutes</b>.
    Town by town it is not: the typical gap is <b>${S.mae} minutes</b>, and the correlation is ${S.r_mix} across all towns and
    ${S.r_big} for the ${S.n_big} towns with at least 100 young people. Compared directly, without the mode mix, the correlation
    with the modelled public-transport time is ${S.r_ptr} and with the car time ${S.r_car}.</p>
    <p><b>Why the gaps fall where they do.</b> The misses are not random. <b>Commuter suburbs of Dublin</b> (Saggart,
    Newcastle, Rathcoole, Celbridge) report longer journeys than the model: the model sends their students to the quickest
    campus, often TU&nbsp;Dublin Tallaght or Maynooth, but many travel on into the city centre to the university they chose.
    <b>Distant towns</b> (Clones, Mountrath, Banagher) report shorter journeys: their students study at nearer campuses
    outside the region, which the model does not include, or have moved and are counted at their term-time address. Both
    are the gap between <i>potential</i> access and <i>realised</i> choice that the report describes throughout, and both
    point to the same improvements: the national campus set, and data on where each student actually studies.</p>
    <div class="scroll"><table id="v-tbl"><thead><tr><th class="l">Town</th><th class="l">County</th><th>Reported</th>
      <th>Model (mode mix)</th><th>Difference</th><th>Walk or cycle</th><th>Public transport</th><th>Car</th></tr></thead><tbody></tbody></table></div>
    <p class="note">The 20 largest towns by young population. Census journey times are self-reported and include students
    attending any college, further-education colleges among them; mode shares exclude "not stated".</p>`;

    const cty = Object.fromEntries(D.counties.map(r => [r[0], r]));
    const f1 = APP.ramp([241, 225, 196], [216, 81, 40]);
    const car = D.counties.map(r => r[2]), sav = D.counties.map(r => r[5]);
    const m1 = APP.countyMap(el.querySelector("#v-map1")), m2 = APP.countyMap(el.querySelector("#v-map2"));
    const [a0, a1, b0, b1] = [Math.min(...car), Math.max(...car), Math.min(...sav), Math.max(...sav)];
    m1.paint(c => cty[c] ? f1((cty[c][2] - a0) / (a1 - a0)) : "var(--surface-alt)", c => cty[c] ? Math.round(cty[c][2]) + "%" : "",
      c => cty[c] ? `${c}: ${cty[c][2]}% of students aged 19+ travel by car` : c);
    m2.paint(c => cty[c] ? f1((cty[c][5] - b0) / (b1 - b0)) : "var(--surface-alt)", c => cty[c] ? "+" + Math.round(cty[c][5]) + " min" : "",
      c => cty[c] ? `${c}: the car saves a median ${cty[c][5]} minutes (model)` : c);
    APP.rampLegend(el.querySelector("#v-map1Lg"), f1, Math.round(a0) + "%", Math.round(a1) + "%");
    APP.rampLegend(el.querySelector("#v-map2Lg"), f1, "+" + Math.round(b0) + " min", "+" + Math.round(b1) + " min");
    scatter(el.querySelector("#v-cty"), D.counties.map(r => [r[5], r[2], 6, "var(--coral)",
      `${r[0]}: model saving ${r[5]} min, ${r[2]}% drive`, CS.short[r[0]] || r[0]]),
      {x0: 10, x1: 70, xs: 10, y0: 0, y1: 60, ys: 10, xl: "minutes the car saves (model, median)", yl: "% of students who drive (census)"});
    const dub = new Set(["Dublin"]);
    scatter(el.querySelector("#v-town"), D.towns.map(r => [Math.min(r[3], 120), r[2], Math.min(13, Math.max(2.5, Math.sqrt(r[9]) / 3)),
      dub.has(r[1]) ? "var(--navy)" : "var(--sand)", `${r[0]} (${r[1]}): reported ${r[2]} min, model ${r[3]} min`, ""]),
      {x0: 0, x1: 120, xs: 20, y0: 0, y1: 80, ys: 20, diag: true, xl: "model, given how the town's students travel (minutes)",
       yl: "reported by students aged 19+ (minutes)"});
    el.querySelector("#v-tbl tbody").innerHTML = D.towns.slice().sort((a, b) => b[9] - a[9]).slice(0, 20).map(r => {
      const d = r[3] - r[2];
      return `<tr><td class="l">${r[0]}</td><td class="l">${r[1]}</td><td>${r[2].toFixed(1)}</td><td>${r[3].toFixed(1)}</td>` +
        `<td style="color:${d < 0 ? "var(--blue)" : "var(--coral)"}">${d > 0 ? "+" : ""}${d.toFixed(1)}</td>` +
        `<td>${Math.round(r[6])}%</td><td>${Math.round(r[7])}%</td><td>${Math.round(r[8])}%</td></tr>`; }).join("");
  }

  return {init(){}, methods};
})();
"""
