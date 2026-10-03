"""Reach section (Phase 3): who can reach which campus. Two parts:
  MAIN     - the "Who can reach" branch: findings, population-weighted reach, head-to-head,
             car versus public transport, the accessibility map, every ED, the Heuston effect.
  MAIN_MU  - for the Maynooth worked example: the commuter-coach network, a second instance of
             the map (coach layer on) and the schools in the catchment with the shortlist.

Per-institution best times are derived client-side from the OD rows, and per-institution costs
from the shared per-ED table, rather than being stored a second time.
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString, box

import config as C

KEY = "reach"
COLS = ("pt", "car")   # shared-table columns read (peak daily cost, for the head-to-head)

W, S, E, N = C.BBOX_P3
SVG_W, SVG_H = 720, 940
MODES = ["pt", "pt_plus_rail", "car"]
SCHEDS = ["peak", "late"]
HEIS = ["MU", "DCU", "UCD", "TCD", "TU Dublin", "Marino", "NCAD", "RCSI", "IADT", "TUS", "DkIT", "SETU"]
INST_COLOUR = {
    "MU": "#05668d", "DCU": "#028090", "UCD": "#d85128", "TCD": "#5c4d7d",
    "TU Dublin": "#3f7d5f", "Marino": "#b08900", "NCAD": "#8c3b4a", "RCSI": "#1f6f8b",
    "IADT": "#c05780", "TUS": "#c98a2e", "DkIT": "#9c4a86", "SETU": "#3f8a6e",
}
SHORT = {
    "mu_maynooth": "MU", "dcu_glasnevin": "DCU", "ucd_belfield": "UCD",
    "tcd_college_green": "TCD", "tud_grangegorman": "TUD-G", "tud_blanchardstown": "TUD-B",
    "tud_tallaght": "TUD-T", "marino": "Marino", "ncad": "NCAD", "rcsi": "RCSI",
    "iadt": "IADT", "tus_athlone": "TUS", "dkit_dundalk": "DkIT", "setu_carlow": "SETU",
}
HEUSTON_TOWNS = ["Monasterevin", "Portarlington South", "Portlaoighise Urban"]


def _project(lon, lat):
    return (round((lon - W) / (E - W) * SVG_W, 1), round((N - lat) / (N - S) * SVG_H, 1))


def _n(v):
    return None if pd.isna(v) else round(float(v))


def _land():
    prov = gpd.read_file(C.RAW / "ie-adm1-geoboundaries.geojson").to_crs(4326)
    out = []
    for geom in prov.clip(box(W, S, E, N)).geometry.simplify(0.005):
        for poly in ([geom] if geom.geom_type == "Polygon" else list(geom.geoms)):
            for ring in [poly.exterior, *poly.interiors]:
                out.append("M" + " L".join(f"{x},{y}" for x, y in (_project(*p) for p in ring.coords)) + " Z")
    return out


def _schools(o_idx):
    sch = pd.read_csv(C.OUT / "p3_schools.csv", dtype={"oid": str})
    sch["oid"] = sch["oid"].str.zfill(6)
    sch = sch[sch["oid"].isin(o_idx)]
    # nearest DAILY Maynooth commuter-coach corridor within 2 km, per school
    daily = [cr for cr in json.loads((C.OUT / "p3_coach_routes.json").read_text()) if cr.get("daily")]
    lines = gpd.GeoSeries([LineString(cr["path"]) for cr in daily], crs=4326).to_crs(2157).reset_index(drop=True)
    codes = [cr["route"] for cr in daily]
    spts = gpd.GeoSeries(gpd.points_from_xy(sch["lon"], sch["lat"]), crs=4326).to_crs(2157)

    def coach_of(pt):
        d = lines.distance(pt)
        return codes[int(d.values.argmin())] if float(d.min()) <= 2000 else ""

    sch = sch.assign(coach=[coach_of(p) for p in spts])
    rows = []
    for r in sch.to_dict("records"):
        s_ = lambda k: r[k].strip() if isinstance(r[k], str) else ""
        rows.append([s_("roll"), s_("name"), s_("county"), s_("ed_name"), s_("pp_type"), s_("gender"),
                     s_("ethos"), int(bool(r["irish_medium"])), int(bool(r["fee_paying"])), int(bool(r["deis"])),
                     int(r["enrolment"]) if pd.notna(r["enrolment"]) else -1, o_idx[r["oid"]],
                     *_project(r["lon"], r["lat"]), s_("eircode"), r["coach"],
                     int(r["lc"]) if pd.notna(r["lc"]) else -1])
    return rows


def data() -> dict:
    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"id": str})
    origins["oid"] = origins["id"].str.zfill(6)
    campuses = pd.read_csv(C.PROC / "campuses_p3.csv")
    o_idx = {o: i for i, o in enumerate(origins["oid"])}
    c_idx = {c: i for i, c in enumerate(campuses["id"])}

    # index of each origin in the shared per-ED table (common.ed_table orders by p3_cost)
    cost = pd.read_csv(C.OUT / "p3_cost.csv", dtype={"origin_id": str})
    t_order = list(cost[cost["schedule"] == "peak"]["origin_id"].str.zfill(6).drop_duplicates())
    t_idx = {o: i for i, o in enumerate(t_order)}

    od = pd.read_csv(C.OUT / "p3_od_long.csv", dtype={"origin_id": str})
    od["origin_id"] = od["origin_id"].str.zfill(6)
    od = od[od["reachable"]]
    od_rows = [[o_idx[r["origin_id"]], c_idx[r["campus_id"]], MODES.index(r["mode"]),
                SCHEDS.index(r["schedule"]), round(r["am_p50"]), round(r["roundtrip_p50"])]
               for r in od.to_dict("records")]

    ea = pd.read_csv(C.OUT / "p3_ed_access.csv", dtype={"origin_id": str})
    ea["origin_id"] = ea["origin_id"].str.zfill(6)
    ea_rows = [[o_idx[r["origin_id"]], MODES.index(r["mode"]), SCHEDS.index(r["schedule"]),
                (r["most_accessible_inst"] if isinstance(r["most_accessible_inst"], str) else ""),
                _n(r["am_any_hei"]), _n(r["am_university"]), _n(r["am_maynooth"]), _n(r["am_regional_hei"])]
               for r in ea.to_dict("records")]
    adv = pd.read_csv(C.OUT / "p3_car_advantage.csv", dtype={"origin_id": str})
    adv["origin_id"] = adv["origin_id"].str.zfill(6)
    adv_rows = [[o_idx[r["origin_id"]], SCHEDS.index(r["schedule"]), _n(r["car_vs_pt"]), _n(r["car_vs_ptrail"])]
                for r in adv.to_dict("records")]

    coach = json.loads((C.OUT / "p3_coach_routes.json").read_text())
    for cr in coach:
        cr["pts"] = [_project(lon, lat) for lon, lat in cr.pop("path")]
        cr.pop("stops", None)

    return {
        "meta": {"n_eds": int(len(origins)), "cohort": int(origins["cohort_17_19"].sum()),
                 "gtfs": C.GTFS_RAW.name, "osm": C.OSM_RAW.name, "date": C.ANALYSIS_DATE.isoformat(),
                 "thresholds": C.ACCESS_THRESHOLDS, "modes": MODES},
        "origins": [{"n": r["name"], "c": r["county"], "coh": int(r["cohort_17_19"]), "t": t_idx.get(r["oid"]),
                     **dict(zip(("x", "y"), _project(r["lon"], r["lat"])))}
                    for r in origins.to_dict("records")],
        "campuses": [{"id": r["id"], "n": r["name"], "i": r["institution"], "s": SHORT.get(r["id"], r["institution"]),
                      "col": INST_COLOUR.get(r["institution"], "#999"),
                      **dict(zip(("x", "y"), _project(r["lon"], r["lat"])))}
                     for r in campuses.to_dict("records")],
        "od": od_rows, "ea": ea_rows, "adv": adv_rows,
        "pw": pd.read_csv(C.OUT / "p3_pop_weighted.csv").to_dict("records"),
        "cty": pd.read_csv(C.OUT / "p3_by_county.csv").to_dict("records"),
        "heis": HEIS, "coach": coach, "schools": _schools(o_idx), "land": _land(),
        "svg": {"w": SVG_W, "h": SVG_H}, "heuston": HEUSTON_TOWNS,
    }


CSS = """
  .sec-reach ul.finds{margin:.6rem 0 0;padding:0;list-style:none}
  .sec-reach ul.finds li{position:relative;padding:.55rem 0 .55rem 1.4rem;border-bottom:1px solid var(--hair);font-size:.96rem}
  .sec-reach ul.finds li:last-child{border-bottom:none}
  .sec-reach ul.finds li::before{content:"";position:absolute;left:.2rem;top:1.15rem;width:7px;height:7px;border-radius:50%;background:var(--teal)}
  .sec-reach ul.finds li.warn::before{background:var(--coral)}
  .sec-reach ul.finds b{color:var(--ink)}
  .sec-reach .mono{font-family:"IBM Plex Mono",monospace}
  .sec-reach .chartrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(250px,1fr));gap:1rem;margin-top:1rem}
  .sec-reach svg.pwc{width:100%;height:175px;display:block}
  .sec-reach svg.pwc .grid{stroke:var(--hair)} .sec-reach svg.pwc .axl{font-size:9px;fill:var(--faint)}
  .sec-reach svg.pwc .ct{font-size:10px;fill:var(--muted);font-weight:600}
  .sec-reach svg.pwc .pt{fill:none;stroke:var(--faint);stroke-width:1.6;stroke-dasharray:3 3}
  .sec-reach svg.pwc .rail{fill:none;stroke:var(--teal);stroke-width:1.8}
  .sec-reach svg.pwc .car{fill:none;stroke:var(--coral);stroke-width:2}
  .sec-reach .clegend{font-size:.75rem;color:var(--muted);margin:.4rem 0 0;display:flex;gap:1rem;flex-wrap:wrap;text-align:left}
  .sec-reach #r-h2tbl td,.sec-reach #r-h2tbl th{text-align:right}
  .sec-reach #r-h2tbl td.l,.sec-reach #r-h2tbl th.l{text-align:left}
  .sec-reach #r-h2tbl tr.sub td{background:var(--surface-alt);font-size:.66rem;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);font-weight:600}
  .sec-reach #r-h2tbl tr.win td:last-child{color:var(--teal);font-weight:600}
  .sec-reach #r-h2tbl tr.lose td:last-child{color:var(--coral);font-weight:600}
  .sec-reach .mgrid{display:grid;grid-template-columns:minmax(0,1.6fr) minmax(240px,1fr);gap:1.1rem;margin-top:1rem}
  @media (max-width:820px){.sec-reach .mgrid{grid-template-columns:1fr}}
  .sec-reach .mapcard{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:.5rem;position:relative}
  .sec-reach .maphint{font-size:.74rem;color:var(--faint);margin:.15rem .3rem .3rem;text-align:left}
  .sec-reach svg.map{width:100%;height:auto;display:block;touch-action:none;cursor:grab;background:var(--surface);user-select:none;-webkit-user-select:none}
  .sec-reach .zoomctl{position:absolute;right:14px;top:14px;display:flex;flex-direction:column;gap:4px}
  .sec-reach .zoomctl button{width:28px;height:28px;border:1px solid var(--hair-strong);background:var(--surface);color:var(--ink);
    border-radius:6px;font-size:16px;cursor:pointer;font-family:inherit}
  .sec-reach .controls label.chk{text-transform:none;letter-spacing:0;font-size:.82rem;color:var(--ink);cursor:pointer}
  .sec-reach .controls button{font:inherit;font-size:.78rem;padding:.3rem .7rem;border:1px solid var(--navy);background:var(--navy);color:#fff;border-radius:6px;cursor:pointer}
  .sec-reach .controls input[type=number]{font:inherit;font-size:.82rem;padding:.25rem .4rem;width:5rem;border:1px solid var(--hair-strong);background:var(--surface);color:var(--ink);border-radius:6px}
  .sec-reach .sidecard{background:var(--surface);border:1px solid var(--hair);border-radius:10px;padding:.9rem 1rem}
  .sec-reach .sidecard h3{margin:0;font-size:.98rem}
  .sec-reach .sidecard .sub{font-size:.78rem;color:var(--faint);margin:.1rem 0 .55rem}
  .sec-reach .legend{display:flex;flex-wrap:wrap;gap:.28rem .62rem;margin:.5rem .2rem 0;font-size:.72rem;color:var(--muted)}
  .sec-reach .legend span{display:inline-flex;align-items:center;gap:.28rem;white-space:nowrap}
  .sec-reach .legend span.tog{cursor:pointer;user-select:none}
  .sec-reach .legend span.tog.off{opacity:.38;text-decoration:line-through}
  .sec-reach .sw{width:9px;height:9px;border-radius:50%;display:inline-block;flex:0 0 auto}
  .sec-reach .legendhint{font-size:.7rem;color:var(--faint);margin:.4rem 0 .1rem;text-align:center}
  .sec-reach circle.ed{stroke-width:0} .sec-reach circle.ed.sel{stroke:var(--ink);stroke-width:2}
  .sec-reach .hit{cursor:pointer;fill:transparent}
  .sec-reach text.edl{font-size:9px;fill:var(--muted);pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:2.5px}
  .sec-reach text.cl{font-size:8px;fill:var(--ink);font-weight:600;pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:2.5px}
  .sec-reach path.land{fill:var(--surface-alt);stroke:var(--hair-strong);stroke-width:.8}
  .sec-reach path.coach{fill:none;stroke:var(--coach);stroke-width:2.2;stroke-linejoin:round;stroke-linecap:round;opacity:.92;pointer-events:stroke;cursor:help}
  .sec-reach path.coach.res{stroke:var(--faint);stroke-width:1.6;stroke-dasharray:5 4;opacity:.75}
  .sec-reach circle.coachend{fill:var(--coach);stroke:var(--surface);stroke-width:1.4;pointer-events:none}
  .sec-reach circle.coachend.res{fill:var(--faint)}
  .sec-reach text.coachl{font-size:8.5px;fill:var(--coach);font-weight:600;pointer-events:none;paint-order:stroke;stroke:var(--surface);stroke-width:2.6px}
  .sec-reach text.coachl.res{fill:var(--muted)}
  .sec-reach .coachkey{font-size:.76rem;color:var(--muted);margin:.5rem 0 0;display:none;gap:1.1rem;flex-wrap:wrap}
  .sec-reach path.school{cursor:pointer}
  .sec-reach .edfilter{font:inherit;font-size:.88rem;padding:.35rem .55rem;border:1px solid var(--hair-strong);border-radius:6px;background:var(--surface);color:var(--ink);width:min(300px,60%)}
  .sec-reach #r-edt th{cursor:pointer}
  .sec-reach #s-scTbl tbody tr:hover td{background:var(--surface-alt)}
  .sec-reach #s-scTbl td.l:first-child,.sec-reach #s-scTbl th.l:first-child{white-space:normal;min-width:12rem}
  .sec-reach #s-scTbl th{cursor:pointer}
  .sec-reach #s-scDet td,.sec-reach #s-scHeis td{padding:.25rem .4rem;border-bottom:1px solid var(--hair)}
  .sec-reach .tall{max-height:460px;overflow-y:auto}
"""


def _map_html(h2id: str, coach_on: bool) -> str:
    chk = " checked" if coach_on else ""
    return f"""
<h2 id="{h2id}">Accessibility map</h2>
<p class="note">1,197 Electoral Divisions, one dot each. Scroll to zoom, drag to pan; hover a dot for its campuses;
  <b>click a campus marker to isolate the areas it wins</b> (its modelled catchment). The "most accessible campus"
  colour is the shortest modelled trip, not where a student would choose to go.</p>
<div class="p3map" data-coach="{int(coach_on)}">
  <div class="controls">
    <label>Schedule <select class="m-sched">
      <option value="peak">Peak: arrive 08:30, leave 18:30</option>
      <option value="late">Late: arrive 10:00, leave 17:00</option></select></label>
    <label>Mode <select class="m-mode">
      <option value="pt_plus_rail">PT + drive-to-rail</option><option value="pt">Public transport</option>
      <option value="car">Car</option></select></label>
    <label>Colour <select class="m-colour">
      <option value="best">Most accessible campus</option>
      <option value="hei">Minutes to any HEI</option>
      <option value="mu">Minutes to Maynooth</option></select></label>
    <label>Show <select class="m-layers">
      <option value="both">Areas and campuses</option><option value="eds">Areas only</option>
      <option value="campuses">Campuses only</option></select></label>
    <label class="chk"><input type="checkbox" class="m-schools"> Post-primary schools</label>
    <label class="chk"><input type="checkbox" class="m-coach"{chk}> Maynooth commuter coaches</label>
  </div>
  <div class="mgrid">
    <div class="mapcard">
      <svg class="map" viewBox="0 0 720 940" preserveAspectRatio="xMidYMid meet"></svg>
      <div class="zoomctl"><button class="zin" aria-label="Zoom in">+</button><button class="zout" aria-label="Zoom out">&minus;</button><button class="zrst" aria-label="Reset view">&#8635;</button></div>
      <div class="legend"></div>
      <div class="legendhint"></div>
    </div>
    <div class="sidecard">
      <h3 class="sT">Hover a dot</h3><div class="sub sS">Electoral Division</div>
      <table class="sTbl"><thead><tr><th class="l">Campus</th><th>AM</th><th>Round&nbsp;trip</th></tr></thead><tbody></tbody></table>
    </div>
  </div>
  <p class="coachkey">
    <span><svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="var(--coach)" stroke-width="2.2"/></svg> Daily commuter coach (Monday to Friday, one timed morning run)</span>
    <span><svg width="24" height="8"><line x1="0" y1="4" x2="24" y2="4" stroke="var(--faint)" stroke-width="1.6" stroke-dasharray="5 4"/></svg> Weekend residential coach (Friday out, Sunday back)</span>
    <span>Hover a line for the timetable. These services are already in the public-transport times.</span>
  </p>
</div>
"""


MAIN = """
<h2 id="r-findings">Key findings</h2>
<ul class="finds" id="r-finds"></ul>

<h2 id="r-reach">Population-weighted reach</h2>
<p class="note">Share of the study area's 17 to 19 cohort within N minutes (morning, one way) of the selected target, a
  group of institutions or one named HEI, for each mode and each timetable. "A university" = MU, DCU, UCD, Trinity,
  TU&nbsp;Dublin, TUS, SETU; "a regional HEI" = TUS&nbsp;Athlone, Dundalk&nbsp;IT, SETU&nbsp;Carlow. For a named HEI the
  figure is the best trip to any of its campuses.</p>
<div class="controls"><label>Within reach of <select id="r-pwTarget"></select></label></div>
<p class="clegend">
  <span><svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="var(--faint)" stroke-width="1.6" stroke-dasharray="3 3"/></svg> Public transport</span>
  <span><svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="var(--teal)" stroke-width="2"/></svg> PT + drive-to-rail</span>
  <span><svg width="22" height="8"><line x1="0" y1="4" x2="22" y2="4" stroke="var(--coral)" stroke-width="2"/></svg> Car</span></p>
<div class="chartrow" id="r-charts"></div>
<div class="panel scroll"><table id="r-pw">
  <thead><tr><th class="l">Timetable</th><th class="l">Mode</th><th>30&nbsp;min</th><th>45</th><th>60</th><th>75</th><th>90</th></tr></thead>
  <tbody></tbody></table></div>

<h2 id="r-h2h">Head to head on commuting</h2>
<p class="note">The students genuinely weighing two institutions on commute grounds are those who can reach <i>both</i>
  within a reasonable trip: the <b>contested cohort</b>. For them, how do the two compare, in journey time and in daily
  cost, by public transport and by car? Home defaults to Maynooth; pick any comparator. Times are one-way morning minutes;
  cost is the round-trip daily figure from the <a href="#cost">cost model</a> (student rail season or coach, or car fuel,
  parking and toll).</p>
<p class="note"><b>An example.</b> Set this to <b>Maynooth against DCU</b> at 60&nbsp;minutes: <b id="r-h2ex">many students</b>
  can reach both within the hour. The county breakdown shows where each institution wins the
  commute. The figures below update as you change the selectors.</p>
<div class="controls">
  <label>Home <select id="r-h2home"></select></label>
  <label>Versus <select id="r-h2away"></select></label>
  <label>Reachable within <select id="r-h2thr">
    <option value="45">45 min</option><option value="60" selected>60 min</option>
    <option value="75">75 min</option><option value="90">90 min</option></select></label>
</div>
<div class="stat" id="r-h2stat"></div>
<div class="panel scroll"><table id="r-h2tbl"><tbody></tbody></table></div>
<p class="note">Cohort-weighted medians and shares over the contested cohort. "Better" means faster or cheaper by more
  than a rounding margin. Potential accessibility only: real choice also turns on course availability, points and
  reputation (see <a href="#choice">the enrolment model</a>).</p>
<div class="panel scroll"><table id="r-h2cty">
  <thead><tr><th class="l">County</th><th>Contested cohort</th><th>Home faster: PT</th><th>Home faster: car</th>
    <th>Home cheaper: PT</th><th>Home cheaper: car</th></tr></thead><tbody></tbody></table></div>

<h2 id="r-carpt">Car versus public transport</h2>
<p class="note">Minutes a full private-car commute saves over the best public-transport option (PT + drive-to-rail), to
  the nearest HEI, at the morning peak. This is the reachability gap that a car closes, largest in exactly the rural
  areas where car ownership is highest and the alternatives thinnest. It is a measure of <i>dependence on the car</i>,
  not of good provision.</p>
<div class="cgrid"><div class="panel scroll"><table id="r-advCty">
  <thead><tr><th class="l">County</th><th>Median car saving (peak)</th><th>Within 60&nbsp;min by car</th>
    <th>By public transport</th></tr></thead><tbody></tbody></table></div>
<div class="cmapbox"><h4>Minutes the car saves (median, peak)</h4><svg id="r-cmap"></svg><div class="clg" id="r-cmapLg"></div></div></div>
""" + _map_html("r-map", False) + """
<h2 id="r-eds">Every Electoral Division</h2>
<p class="note">Best morning one-way trip to any HEI, a university or Maynooth, for the mode and schedule chosen on the
  map. Type to filter; click a column to sort. With a campus catchment selected on the map, the table narrows to it.</p>
<input class="edfilter" id="r-edq" placeholder="filter by area or county&hellip;" autocomplete="off">
<span id="r-edCount" style="font-size:.82rem;color:var(--muted);margin-left:.6rem"></span>
<div class="panel scroll tall"><table id="r-edt"><thead><tr>
  <th class="l" data-k="n">Electoral Division</th><th class="l" data-k="c">County</th><th data-k="coh">17-19</th>
  <th data-k="hei">Any HEI</th><th data-k="uni">University</th><th data-k="mu">Maynooth</th>
  <th class="l" data-k="mi">Most accessible</th></tr></thead><tbody></tbody></table></div>

<h2 id="r-heuston">A worked example: the Heuston effect</h2>
<p class="note">The tools above support asking not just <i>which</i> campus wins an area but <i>why</i>. Here is one
  pattern worth knowing about.</p>
<p id="r-heuP"></p>
<div class="panel scroll"><table id="r-heuTbl">
  <thead><tr><th class="l">From</th><th>NCAD</th><th class="l">Next best</th><th>&nbsp;</th></tr></thead><tbody></tbody></table></div>
<p class="note" style="margin-top:.7rem"><b>Two lessons.</b> First, for the intercity-rail catchment a campus's position
  relative to the terminus matters more than anything about the institution. Second, "most accessible" is the shortest
  trip, not the chosen one: a real applicant trades ten minutes against the course and the campus they actually want, so
  this map describes <i>reach</i>, not demand.</p>
"""

COACH = """
<h2 id="s-coach">The Maynooth coach network</h2>
<p class="note">Maynooth has something the other campuses do not: a fan of <b>dedicated commuter coaches</b> run by
  private operators (JJ&nbsp;Kavanagh, Kearns, Streamline, Slevins, Wexford&nbsp;Bus and others) that collect students each
  morning, run to the North Campus for first lectures, and return in the late afternoon. They reach <b id="s-coachReach"></b>
  and account for much of Maynooth's public-transport presence in the midlands and south-east.</p>
<p class="note">These services <b>are already in the model</b>: they sit in the Transport for Ireland national feed and feed
  the public-transport times throughout this report. Some are near-direct (Athboy 45&nbsp;min, Dundrum 90); others are long
  milk-runs that collect across a whole county before turning for Maynooth (Portlaoise and Birr are both over two hours).
  Either way each route is a <i>single</i> timed departure, so a student catches the morning coach or falls back on a
  multi-leg rail-and-bus trip; and because the study reports the <i>median</i> over a 60-minute departure window, the
  modelled time blends the coach with those slower fallbacks. Read the schedule below as the best case a coach town
  actually has. The <a href="#cost">cost model</a> credits the coach fare to every area within reach of a stop.</p>
<div class="panel scroll"><table id="s-coachTbl">
  <thead><tr><th class="l">Route</th><th class="l">Corridor</th><th class="l">Operator</th>
    <th class="l">Runs</th><th>Boards</th><th>On campus</th><th>Run time</th></tr></thead><tbody></tbody></table></div>
<p class="note" style="margin-top:.6rem"><b>UM04</b> (Wexford) and <b>UM15</b> (Carrick-on-Suir) run only Friday out and
  Sunday back. They serve students who have <i>relocated</i> to Maynooth for the week, not daily commuters, and are shown
  dashed on the map. The line between "commutes" and "moves and travels home at weekends" is exactly what the enrolment
  model cannot yet see (see <a href="#choice/p-sharpen">How to sharpen the answer</a>).</p>
"""

SCHOOLS = """
<h2 id="s-schools">Schools in the catchment</h2>
<p class="note">Post-primary schools whose Electoral Division puts them within a chosen commute of a chosen HEI. A school
  inherits its area's population-weighted travel time, so the figure is the commute its typical intake faces, not a
  door-to-door route for the school building. This is <b>reach, not enrolment</b>: a school being commutable does not mean
  its students choose that HEI. Every school attribute is from the Department of Education's "Data on Individual Schools" for 2025/26 (roll number,
  type, gender, ethos, Irish-medium classification, fee-paying status, DEIS status, enrolment by year group), CC&nbsp;BY&nbsp;4.0.
  Pick any HEI: the tool works the same way for all of them.</p>
<div class="controls">
  <label>HEI <select id="s-scHei"></select></label>
  <label>Within <select id="s-scThr">
    <option value="30">30&nbsp;min</option><option value="45" selected>45&nbsp;min</option>
    <option value="60">60&nbsp;min</option><option value="75">75&nbsp;min</option>
    <option value="90">90&nbsp;min</option><option value="999">any</option></select></label>
  <label>Mode <select id="s-scMode">
    <option value="pt_plus_rail">PT + drive-to-rail</option><option value="pt">Public transport</option>
    <option value="car">Car</option></select></label>
  <label>Schedule <select id="s-scSched"><option value="peak">Peak (08:30)</option><option value="late">Late (10:00)</option></select></label>
  <label class="chk"><input type="checkbox" id="s-scDeis"> DEIS only</label>
  <label class="chk"><input type="checkbox" id="s-scIm"> Irish-medium only</label>
  <label class="chk"><input type="checkbox" id="s-scNoFee"> exclude fee-paying</label>
  <label class="chk"><input type="checkbox" id="s-scCoach"> on a Maynooth coach route</label>
  <label>Min pupils <input id="s-scMinE" type="number" value="0" min="0" step="50"></label>
  <button id="s-scDl">Download CSV</button>
</div>
<p class="note" id="s-scSummary"></p>
<div class="panel scroll tall"><table id="s-scTbl"><thead><tr>
  <th class="l" data-k="n">School</th><th class="l" data-k="ed">Town / area</th><th class="l" data-k="ty">Type</th>
  <th class="l" data-k="g">Gender</th><th data-k="de">DEIS</th><th data-k="im">Irish</th><th data-k="fp">Fee</th>
  <th class="l" data-k="co">Coach</th><th data-k="e">Pupils</th><th data-k="t">Min</th></tr></thead><tbody></tbody></table></div>
<div class="mgrid" style="grid-template-columns:1fr 1fr">
  <div class="sidecard" id="s-scSide">
    <h3 id="s-scSt">Click a school</h3><div class="sub" id="s-scSs">in the table or on the map</div>
    <table id="s-scDet"><tbody></tbody></table>
  </div>
  <div class="sidecard">
    <h3>Competing HEIs within reach</h3><div class="sub">how the selected school's commute compares across every HEI</div>
    <table id="s-scHeis"><tbody><tr><td class="l" style="color:var(--faint)">select a school</td></tr></tbody></table>
  </div>
</div>
<h3>Marketing shortlist: an illustration</h3>
<p class="note">Catchment schools ranked by a simple opportunity score: the school's Leaving Certificate pupils (the
  two senior years, the students who will apply to college next) weighted by how easy the commute is to the selected HEI,
  so large senior cycles with a short commute rise to the top. It shows the kind of prompt an institution's
  recruitment team could draw from the data; it is not a prediction of where students go, and not a plan.</p>
<div class="panel scroll"><table id="s-scShort">
  <thead><tr><th>#</th><th class="l">School</th><th class="l">Town / area</th><th>Leaving Cert</th><th>Min</th><th>Score</th></tr></thead>
  <tbody></tbody></table></div>
<p class="note" style="margin-top:.7rem">Tick <b>"Post-primary schools"</b> on the map above to plot the filtered catchment
  as diamonds, sized by enrolment and coloured <b style="color:var(--navy)">navy</b>, <b style="color:var(--coral)">coral
  for DEIS</b> or <b style="color:var(--sand)">sand for fee-paying</b>. With <b>"Maynooth commuter coaches"</b> also on,
  schools within about 2&nbsp;km of a daily coach corridor get a violet ring. Clicking a diamond opens the detail panel.</p>
"""

MAIN_MU = COACH + _map_html("s-map", True) + SCHOOLS
STANDALONE_MAIN = MAIN + COACH + SCHOOLS

JS = r"""
SECTIONS.reach = (() => {
  let D = null, X = null;
  const SCHEDS = ["peak", "late"];
  const hn = h => h === "MU" ? "Maynooth University" : h;

  function data(){
    if (D) return D;
    D = APP.json("d-reach");
    const MODES = D.meta.modes;
    const OD = [[{}, {}], [{}, {}], [{}, {}]];
    D.od.forEach(([oi, ci, mi, si, am, rt]) => { (OD[mi][si][oi] = OD[mi][si][oi] || {})[ci] = [am, rt]; });
    const EA = [[{}, {}], [{}, {}], [{}, {}]];
    D.ea.forEach(([oi, mi, si, inst, hei, uni, mu, reg]) => { EA[mi][si][oi] = [inst, hei, uni, mu, reg]; });
    const ADV = {peak: {}, late: {}};
    D.adv.forEach(([oi, si, cvp, cvr]) => { ADV[SCHEDS[si]][oi] = {cvp, cvr}; });
    // per-institution best time (from OD) and peak daily cost (from the shared table)
    const HEIS = D.heis, HI = Object.fromEntries(HEIS.map((h, i) => [h, i]));
    const campByInst = HEIS.map(h => D.campuses.map((c, ci) => [c, ci]).filter(([c]) => c.i === h));
    const T = APP.T();
    const HT = SCHEDS.map((_, si) => HEIS.map((h, hi) => {
      const out = {};
      D.origins.forEach((o, oi) => {
        const best = mi => { let m = null; for (const [, ci] of campByInst[hi]) { const v = (OD[mi][si][oi] || {})[ci]; if (v && (m == null || v[0] < m)) m = v[0]; } return m; };
        const minCost = k => { if (o.t == null) return null; let m = null;
          for (const [c] of campByInst[hi]) { const v = T.col[c.id][k][o.t]; if (v != null && (m == null || v < m)) m = v; } return m; };
        out[oi] = {pa: best(0), pr: best(1), ca: best(2), pc: minCost("pt"), cc: minCost("car")};
      });
      return out;
    }));
    X = {MODES, OD, EA, ADV, HEIS, HI, HT,
      UNI: ["MU", "DCU", "UCD", "TCD", "TU Dublin", "TUS", "SETU"].map(h => HI[h]),
      REG: ["TUS", "DkIT", "SETU"].map(h => HI[h]), ALL: HEIS.map((_, i) => i),
      MFLD: {pt: "pa", pt_plus_rail: "pr", car: "ca"},
      cColour: i => { const c = D.campuses.find(x => x.i === i); return c ? c.col : "#bbb"; }};
    return D;
  }
  function bestT(idxs, si, oi, fld){ let m = null;
    for (const hi of idxs) { const r = X.HT[si][hi][oi]; if (r && r[fld] != null && (m == null || r[fld] < m)) m = r[fld]; } return m; }
  const targetIdx = t => t === "any_hei" ? X.ALL : t === "university" ? X.UNI : t === "regional_hei" ? X.REG : t.startsWith("hei:") ? [X.HI[t.slice(4)]] : X.ALL;
  const tgtLabel = t => t === "any_hei" ? "any HEI" : t === "university" ? "a university" : t === "regional_hei" ? "a regional HEI" : t === "hei:MU" ? "Maynooth" : t.slice(4);
  function pwv(sched, mode, target, t){
    const si = SCHEDS.indexOf(sched), idxs = targetIdx(target), fld = X.MFLD[mode]; let num = 0;
    D.origins.forEach((o, oi) => { const v = bestT(idxs, si, oi, fld); if (v != null && v <= t) num += o.coh; });
    return Math.round(100 * num / D.meta.cohort);
  }

  function init(root){
    data(); const $ = s => root.querySelector(s);
    if ($("#r-finds")) findings($);
    if ($("#r-pwTarget")) reachCharts($);
    if ($("#r-h2tbl")) headToHead($);
    if ($("#r-advCty")) carVsPt($);
    if ($("#r-heuP")) heuston($);
    if ($("#s-coachTbl")) coachTable($);
    const maps = [...root.querySelectorAll(".p3map")].map(m => mapInit(m, root));
    if (D.schools && D.schools.length) {
      // every map plots all schools by default, a click showing the school in that map's side panel;
      // the map that sits with the schools panel is then switched to the panel's filtered set
      const S = schoolList(), byRoll = Object.fromEntries(S.map(s => [s.r, s])), all = new Set(S.map(s => s.r));
      const maxE = Math.max(...S.map(s => s.e || 0), 1);
      maps.forEach(m => m.setSchools({all: S, maxE, inSet: () => all, detail: roll => m.showSchool(byRoll[roll])}));
    }
    if ($("#s-scTbl")) schools($, root, maps[maps.length - 1] || null);
  }

  function schoolList(){
    return D.schools.map(a => ({r: a[0], n: a[1], c: a[2], ed: a[3], ty: a[4], g: a[5], et: a[6], im: !!a[7], fp: !!a[8], de: !!a[9],
      e: a[10] < 0 ? null : a[10], oi: a[11], x: a[12], y: a[13], ei: a[14], co: a[15] || "", lc: a[16] < 0 ? null : a[16]}));
  }

  function findings($){
    const g = (s, m, tg, t) => pwv(s, m, tg, t), li = (t, cls) => `<li${cls ? ` class="${cls}"` : ""}>${t}</li>`;
    $("#r-finds").innerHTML = [
      li(`<b>The car changes everything for rural students.</b> At the peak, ${g("peak","pt","any_hei",60)}% of the 17 to 19
        cohort is within an hour of any HEI by public transport and ${g("peak","pt_plus_rail","any_hei",60)}% with drive-to-rail,
        but <b>${g("peak","car","any_hei",60)}% by car</b>. Within 90 minutes the car figure is ${g("peak","car","any_hei",90)}%.`),
      li(`<b>A 10:00 start barely helps public transport but helps the car.</b> Shifting to the later timetable ${(() => {
        const a = g("peak","pt","any_hei",60), b = g("late","pt","any_hei",60);
        return a === b ? `leaves the "any HEI within 60 min" figure unchanged at ${a}% by public transport, but moves it`
          : `moves the "any HEI within 60 min" figure from ${a}% to ${b}% by public transport, and`; })()}
        from ${g("peak","car","any_hei",60)}% to ${g("late","car","any_hei",60)}% by car: the peak congestion penalty is a car
        problem, and avoiding it is a car benefit.`),
      li(`<b>Maynooth stays peripheral on public transport</b>: ${g("peak","pt_plus_rail","hei:MU",60)}% of the cohort within an
        hour with drive-to-rail, against ${g("peak","car","hei:MU",60)}% by car.`, "warn"),
      li(`<b>The regional HEIs earn their place.</b> ${g("peak","pt_plus_rail","regional_hei",60)}% of the cohort is within an
        hour of a regional campus (TUS Athlone, Dundalk IT, SETU Carlow) with drive-to-rail, ${g("peak","car","regional_hei",60)}%
        by car: they carry the midlands, the border and the south-east.`),
    ].join("");
  }

  function reachCharts($){
    const sel = $("#r-pwTarget"), TH = D.meta.thresholds;
    sel.innerHTML = `<option value="any_hei">any HEI</option><option value="university">a university</option>` +
      `<option value="regional_hei">a regional HEI</option><optgroup label="a named HEI">` +
      X.HEIS.map(h => `<option value="hei:${h}">${hn(h)}</option>`).join("") + `</optgroup>`;
    function render(){
      const target = sel.value; let charts = "";
      for (const sc of SCHEDS) {
        const w = 270, hh = 200, pl = 40, pb = 34, pt = 20, pr = 8;
        const Xs = t => pl + (t - 30) / 60 * (w - pl - pr), Y = v => hh - pb - v / 100 * (hh - pb - pt);
        const line = m => TH.map((t, i) => `${i ? "L" : "M"}${Xs(t).toFixed(1)},${Y(pwv(sc, m, target, t) || 0).toFixed(1)}`).join(" ");
        let g = `<svg class="pwc" viewBox="0 0 ${w} ${hh}">`;
        [0, 25, 50, 75, 100].forEach(v => g += `<line class="grid" x1="${pl}" y1="${Y(v)}" x2="${w-pr}" y2="${Y(v)}"/><text class="axl" x="${pl-5}" y="${Y(v)+3}" text-anchor="end">${v}</text>`);
        [30, 60, 90].forEach(t => g += `<text class="axl" x="${Xs(t)}" y="${hh-pb+13}" text-anchor="middle">${t}</text>`);
        g += `<text class="axl" x="${pl+(w-pl-pr)/2}" y="${hh-6}" text-anchor="middle">minutes, one-way</text>`;
        g += `<text class="axl" transform="translate(11,${(hh-pb+pt)/2}) rotate(-90)" text-anchor="middle">% of 17 to 19 cohort</text>`;
        g += `<path class="pt" d="${line("pt")}"/><path class="rail" d="${line("pt_plus_rail")}"/><path class="car" d="${line("car")}"/>`;
        g += `<text class="ct" x="${pl}" y="12">${sc === "peak" ? "Peak" : "Late"}: within reach of ${tgtLabel(target)}</text></svg>`;
        charts += g;
      }
      $("#r-charts").innerHTML = charts;
      const nm = {pt: "Public transport", pt_plus_rail: "PT + drive-to-rail", car: "Car"};
      let rows = "";
      for (const sc of SCHEDS) X.MODES.forEach((m, mi) => {
        rows += `<tr${mi === 2 ? ' style="border-bottom:2px solid var(--hair-strong)"' : ""}><td class="l">${mi === 0 ? (sc === "peak" ? "Peak (08:30)" : "Late (10:00)") : ""}</td>` +
          `<td class="l">${nm[m]}</td>` + TH.map(t => `<td class="mono">${pwv(sc, m, target, t)}%</td>`).join("") + "</tr>";
      });
      $("#r-pw tbody").innerHTML = rows;
    }
    sel.onchange = render; render();
  }

  function headToHead($){
    const homeSel = $("#r-h2home"), awaySel = $("#r-h2away"), thrSel = $("#r-h2thr");
    const opts = X.HEIS.map(h => `<option value="${h}">${hn(h)}</option>`).join("");
    homeSel.innerHTML = opts; awaySel.innerHTML = opts; homeSel.value = "MU"; awaySel.value = "DCU";
    const fmtpct = v => v == null ? "&ndash;" : v + "%";
    const wmed = ps => { const a = ps.slice().sort((x, y) => x[0] - y[0]), tot = a.reduce((s, p) => s + p[1], 0);
      if (!tot) return null; let acc = 0; for (const p of a) { acc += p[1]; if (acc >= tot / 2) return p[0]; } return a[a.length - 1][0]; };
    const cmp = (rows, gh, ga) => { const hp = [], ap = []; let hw = 0, b = 0;
      rows.forEach(r => { const h = gh(r), a = ga(r); if (h == null || a == null) return;
        hp.push([h, r.coh]); ap.push([a, r.coh]); b += r.coh; if (h < a - 0.01) hw += r.coh; });
      return {h: wmed(hp), a: wmed(ap), pct: b ? Math.round(100 * hw / b) : null}; };
    const gT = (hi, si, fld) => r => { const x = X.HT[si][hi][r.oi]; return x ? x[fld] : null; };
    let exampleDone = false;
    function render(){
      const hh = X.HI[homeSel.value], ah = X.HI[awaySel.value], thr = +thrSel.value;
      const hN = homeSel.value === "MU" ? "Maynooth" : homeSel.value, aN = awaySel.value === "MU" ? "Maynooth" : awaySel.value;
      const clear = msg => { $("#r-h2stat").textContent = msg; $("#r-h2tbl tbody").innerHTML = ""; $("#r-h2cty tbody").innerHTML = ""; };
      if (homeSel.value === awaySel.value) return clear("Pick two different institutions.");
      const rows = [];
      D.origins.forEach((o, oi) => {
        const H0 = X.HT[0][hh][oi], A0 = X.HT[0][ah][oi];
        const hb = Math.min(...[H0.pa, H0.pr, H0.ca].filter(v => v != null)), ab = Math.min(...[A0.pa, A0.pr, A0.ca].filter(v => v != null));
        if (isFinite(hb) && isFinite(ab) && hb <= thr && ab <= thr) rows.push({oi, coh: o.coh, cty: o.c});
      });
      const tot = rows.reduce((a, r) => a + r.coh, 0);
      if (!exampleDone && homeSel.value === "MU" && awaySel.value === "DCU" && thr === 60) {
        exampleDone = true;
        $("#r-h2ex").innerHTML = `roughly ${(Math.round(tot / 1000) * 1000).toLocaleString("en-IE")} young people (about ${Math.round(100 * tot / D.meta.cohort)}% of the study area)`;
      }
      if (!tot) return clear("No cohort is within this threshold of both.");
      const Tm = (fld, si) => cmp(rows, gT(hh, si, fld), gT(ah, si, fld));
      const pt_p = Tm("pa", 0), pt_l = Tm("pa", 1), pr_p = Tm("pr", 0), ca_p = Tm("ca", 0), ca_l = Tm("ca", 1);
      const c_pt = Tm("pc", 0), c_car = Tm("cc", 0);
      const diff = (c, eur) => { if (c.h == null || c.a == null) return "&ndash;";
        const d = c.h - c.a, eps = eur ? 0.05 : 1; if (Math.abs(d) < eps) return "about the same";
        const who = d < 0 ? hN : aN; return eur ? `${who} by &euro;${Math.abs(d).toFixed(2)}` : `${who} by ${Math.round(Math.abs(d))} min`; };
      const cls = c => c.h == null || c.a == null ? "" : c.h < c.a - 0.01 ? "win" : c.h > c.a + 0.01 ? "lose" : "";
      const row = (lab, c, eur) => `<tr class="${cls(c)}"><td class="l">${lab}</td>` +
        `<td>${c.h == null ? "&ndash;" : (eur ? "&euro;" + c.h.toFixed(2) : Math.round(c.h))}</td>` +
        `<td>${c.a == null ? "&ndash;" : (eur ? "&euro;" + c.a.toFixed(2) : Math.round(c.a))}</td><td>${diff(c, eur)}</td></tr>`;
      const sub = t => `<tr class="sub"><td class="l">${t}</td><td>${hN}</td><td>${aN}</td><td>Better</td></tr>`;
      const share = (lab, v) => `<tr><td class="l">${lab}</td><td colspan="3" style="text-align:left">${fmtpct(v)}</td></tr>`;
      $("#r-h2tbl tbody").innerHTML = sub("One-way journey (minutes)") +
        row("Public transport, peak", pt_p) + row("Public transport, late", pt_l) + row("PT + drive-to-rail, peak", pr_p) +
        row("Car, peak", ca_p) + row("Car, late", ca_l) +
        `<tr class="sub"><td class="l">Cost (&euro; per day, round trip)</td><td></td><td></td><td></td></tr>` +
        row("Public transport", c_pt, 1) + row("Car (all-in)", c_car, 1) +
        `<tr class="sub"><td class="l">Share of the contested cohort for whom ${hN} is&hellip;</td><td></td><td></td><td></td></tr>` +
        share("faster by public transport", pt_p.pct) + share("faster by car", ca_p.pct) +
        share("cheaper by public transport", c_pt.pct) + share("cheaper by car", c_car.pct);
      const ptw = pt_p.h != null && pt_p.a != null ? (pt_p.h < pt_p.a ? "quicker" : pt_p.h > pt_p.a ? "slower" : "about level") : "&ndash;";
      const carw = c_car.h != null && c_car.a != null ? (c_car.h < c_car.a ? "cheaper" : "dearer") : "&ndash;";
      $("#r-h2stat").innerHTML = `<b>${tot.toLocaleString("en-IE")}</b> of the 17 to 19 cohort (${Math.round(100 * tot / D.meta.cohort)}% of the ` +
        `study area) are within ${thr}&nbsp;min of <b>both ${hN} and ${aN}</b>. For them, ${hN} is <b>${ptw}</b> by public transport, ` +
        `and its car commute is <b>${carw}</b>.`;
      const byC = {}; rows.forEach(r => (byC[r.cty] = byC[r.cty] || []).push(r));
      const cw = (rs, gh, ga) => { let w = 0, b = 0; rs.forEach(r => { const h = gh(r), a = ga(r); if (h == null || a == null) return;
        b += r.coh; if (h < a - 0.01) w += r.coh; }); return b ? Math.round(100 * w / b) : null; };
      $("#r-h2cty tbody").innerHTML = Object.entries(byC).map(([c, rs]) => [c, rs, rs.reduce((a, r) => a + r.coh, 0)])
        .sort((x, y) => y[2] - x[2]).map(([c, rs, coh]) => `<tr><td class="l">${c}</td><td class="mono">${coh.toLocaleString("en-IE")}</td>` +
          ["pa", "ca", "pc", "cc"].map(f => `<td class="mono">${fmtpct(cw(rs, gT(hh, 0, f), gT(ah, 0, f)))}</td>`).join("") + `</tr>`).join("");
    }
    homeSel.onchange = render; awaySel.onchange = render; thrSel.onchange = render; render();
  }

  function carVsPt($){
    const counties = [...new Set(D.origins.map(o => o.c))], oiByC = {};
    D.origins.forEach((o, i) => (oiByC[o.c] = oiByC[o.c] || []).push(i));
    const ctyShare = (c, mode, tgt) => { const r = D.cty.find(x => x.county === c && x.mode === mode && x.target === tgt && x.schedule === "peak");
      return r ? Math.round(r.cohort_share * 100) : null; };
    const med = arr => { const a = arr.filter(v => v != null).sort((x, y) => x - y); return a.length ? a[a.length >> 1] : null; };
    const sav = {}; counties.forEach(c => sav[c] = med(oiByC[c].map(oi => X.ADV.peak[oi]?.cvr)));
    counties.sort((a, b) => (sav[b] ?? -1) - (sav[a] ?? -1));
    const vs = counties.map(c => sav[c]).filter(v => v != null), lo = Math.min(...vs), hi = Math.max(...vs);
    const f = APP.ramp([241, 225, 196], [216, 81, 40]), cm = APP.countyMap($("#r-cmap"));
    cm.paint(c => sav[c] != null ? f((sav[c] - lo) / ((hi - lo) || 1)) : "var(--surface-alt)",
      c => sav[c] != null ? "+" + sav[c] + " min" : "", c => sav[c] != null ? `${c}: the car saves a median ${sav[c]} minutes over public transport` : c);
    APP.rampLegend($("#r-cmapLg"), f, "+" + lo + " min", "+" + hi + " min");
    $("#r-advCty tbody").innerHTML = counties.map(c => `<tr><td class="l">${c}</td><td class="mono">${sav[c] == null ? "&ndash;" : "+" + sav[c]}</td>` +
      `<td class="mono">${ctyShare(c, "car", "any_hei")}%</td><td class="mono">${ctyShare(c, "pt_plus_rail", "any_hei")}%</td></tr>`).join("");
  }

  function heuston($){
    const mi = 1, si = 0, ncad = D.campuses.findIndex(c => c.i === "NCAD");
    const wins = D.origins.map((o, i) => [o, X.EA[mi][si][i]]).filter(([, a]) => a && a[0] === "NCAD").map(([o]) => o);
    const byC = {}; wins.forEach(o => byC[o.c] = (byC[o.c] || 0) + 1);
    const outside = Object.entries(byC).filter(([c]) => !["Dublin City", "South Dublin", "Fingal", "Dún Laoghaire-Rathdown"].includes(c))
      .sort((a, b) => b[1] - a[1]).slice(0, 3).map(([c]) => c);
    $("#r-heuP").innerHTML = `With the map on its default mode, <b>public transport with drive-to-rail</b>, at the peak, and coloured
      by <b>most accessible campus</b>: <b>NCAD</b>, a small art and design college on Thomas Street, is the most accessible campus for
      <b>${wins.length} areas</b>, a broad band across ${outside.slice(0, -1).join(", ")} and ${outside[outside.length - 1]}, more than DCU,
      UCD or Marino. Nothing about the college explains it. NCAD sits about <b>700&nbsp;m from Heuston Station</b>, the terminus for every
      intercity line from the south-west and midlands (Cork, Limerick, Galway, Waterford) and for the Kildare commuter line. From a
      Heuston-line town the journey is: train to Heuston, then an 8 to 10 minute walk. <b>Every other Dublin campus needs a further
      cross-city leg</b> (Luas to Grangegorman or Trinity, bus or DART to UCD, DCU or Marino), which adds 10 to 25 minutes. So NCAD comes
      out ahead by a small margin across the whole intercity-rail catchment:`;
    $("#r-heuTbl tbody").innerHTML = D.heuston.map(name => {
      const oi = D.origins.findIndex(o => o.n === name); if (oi < 0) return "";
      const row = X.OD[mi][si][oi] || {};
      const others = Object.entries(row).filter(([ci]) => +ci !== ncad).sort((a, b) => a[1][0] - b[1][0]);
      const nb = others[0];
      return `<tr><td class="l">${name.replace(" Urban", "").replace("Portlaoighise", "Portlaoise")}</td><td class="mono">${row[ncad] ? row[ncad][0] : "&ndash;"}</td>` +
        `<td class="l">${nb ? D.campuses[nb[0]].n : ""}</td><td class="mono">${nb ? nb[1][0] : ""}</td></tr>`;
    }).join("");
  }

  function coachTable($){
    const daily = D.coach.filter(r => r.daily), res = D.coach.filter(r => !r.daily);
    const towns = [...new Set(daily.map(r => r.origin))];
    $("#s-coachReach").textContent = `${daily.length} towns: ${towns.slice(0, -1).join(", ")} and ${towns.slice(-1)}`;
    const hm = m => m < 60 ? `${m} min` : `${Math.floor(m / 60)}h${(m % 60).toString().padStart(2, "0")}`;
    const row = r => `<tr${r.daily ? "" : ' style="color:var(--muted)"'}><td class="l mono">${r.route}</td><td class="l">${r.name}</td>` +
      `<td class="l">${r.operator}</td><td class="l">${r.days}</td><td class="mono">${r.depart}</td><td class="mono">${r.arrive}</td>` +
      `<td class="mono">${hm(r.run_min)}</td></tr>`;
    $("#s-coachTbl tbody").innerHTML = daily.map(row).join("") + res.map(row).join("");
  }

  // ---- the map: one independent instance per .p3map container ----
  function mapInit(box, root){
    const q = s => box.querySelector(s), NS = "http://www.w3.org/2000/svg";
    const el = (t, a) => { const n = document.createElementNS(NS, t); for (const k in a) n.setAttribute(k, a[k]); return n; };
    const SVGW = D.svg.w, SVGH = D.svg.h, svg = q("svg.map");
    const gL = el("g", {}), gH = el("g", {}), gC = el("g", {}), gP = el("g", {}); svg.append(gL, gH, gC, gP);
    D.land.forEach(d => gL.append(el("path", {d, class: "land", "vector-effect": "non-scaling-stroke"})));
    let mSched = 0, mMode = 1, colour = "best", layers = "both", sel = null, catchment = null, catchClusters = null;
    let coachOn = box.dataset.coach === "1", schoolsOn = false, schoolSrc = null;
    const hidden = new Set();
    let k = 1, tx = 0, ty = 0; const MINK = 1, MAXK = 14;
    const sx = x => x * k + tx, sy = y => y * k + ty, ms = () => Math.pow(k, 0.58);
    const EA = () => X.EA[mMode][mSched];
    q(".coachkey").style.display = coachOn ? "flex" : "none";

    function convexHull(pts){
      if (pts.length < 3) return pts.slice();
      const p = pts.slice().sort((a, b) => a[0] - b[0] || a[1] - b[1]);
      const cr = (o, a, b) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
      const lo = []; for (const x of p) { while (lo.length >= 2 && cr(lo[lo.length - 2], lo[lo.length - 1], x) <= 0) lo.pop(); lo.push(x); }
      const up = []; for (let i = p.length - 1; i >= 0; i--) { const x = p[i]; while (up.length >= 2 && cr(up[up.length - 2], up[up.length - 1], x) <= 0) up.pop(); up.push(x); }
      lo.pop(); up.pop(); return lo.concat(up);
    }
    function expandHull(h, amt){
      if (h.length < 3) return h;
      const cx = h.reduce((s, p) => s + p[0], 0) / h.length, cy = h.reduce((s, p) => s + p[1], 0) / h.length;
      return h.map(([x, y]) => { const dx = x - cx, dy = y - cy, d = Math.hypot(dx, dy) || 1; return [x + dx / d * amt, y + dy / d * amt]; });
    }
    function clusterIdx(idxs, thr){
      const par = idxs.map((_, i) => i), find = x => par[x] === x ? x : (par[x] = find(par[x]));
      for (let a = 0; a < idxs.length; a++) for (let b = a + 1; b < idxs.length; b++) {
        const A = D.origins[idxs[a]], B = D.origins[idxs[b]];
        if (Math.hypot(A.x - B.x, A.y - B.y) < thr) par[find(a)] = find(b);
      }
      const g = {}; idxs.forEach((v, i) => { (g[find(i)] = g[find(i)] || []).push(v); });
      return Object.values(g);
    }
    function rtCol(v){ if (v == null) return "#c3c3c3";
      const t = Math.max(0, Math.min(1, (v - 25) / 95)), A = [2, 102, 141], B = [2, 128, 144], Cc = [216, 81, 40];
      const [p, r, fr] = t < .5 ? [A, B, t * 2] : [B, Cc, (t - .5) * 2];
      return `rgb(${p.map((x, i) => Math.round(x + (r[i] - x) * fr)).join(",")})`; }
    function edFill(oi){ const a = EA()[oi]; if (!a) return "#c3c3c3";
      if (colour === "best") return a[0] ? X.cColour(a[0]) : "#c3c3c3";
      return rtCol(colour === "hei" ? a[1] : a[3]); }
    const topLabels = new Set(D.origins.map((o, i) => [i, o.coh]).sort((a, b) => b[1] - a[1]).slice(0, 26).map(x => x[0]));
    function labelSet(){
      const cand = D.origins.map((o, i) => [i, o]).sort((a, b) => b[1].coh - a[1].coh), placed = [], out = new Set();
      for (const [i, o] of cand) { if (out.size > 75) break;
        const x = sx(o.x) + 7, y = sy(o.y) - 6, w = o.n.length * 4.5;
        if (x < 0 || x > SVGW || y < 0 || y > SVGH) continue;
        if (!placed.some(p => Math.abs(p.x - x) < (p.w + w) / 2 && Math.abs(p.y - y) < 11)) { placed.push({x, y, w}); out.add(i); } }
      return out;
    }
    function drawHulls(){
      gH.innerHTML = ""; if (!catchment || !catchClusters) return;
      const col = X.cColour(catchment);
      for (const cl of catchClusters) {
        const scr = cl.map(i => [sx(D.origins[i].x), sy(D.origins[i].y)]);
        if (scr.length < 3) { scr.forEach(([x, y]) => gH.append(el("circle", {cx: x, cy: y, r: 9, fill: col, "fill-opacity": .12, "pointer-events": "none"}))); continue; }
        const h = expandHull(convexHull(scr), 9);
        gH.append(el("path", {d: "M" + h.map(p => p.map(n => n.toFixed(1)).join(",")).join(" L") + " Z", fill: col, "fill-opacity": .13,
          stroke: col, "stroke-opacity": .5, "stroke-width": 1.4, "stroke-linejoin": "round", "vector-effect": "non-scaling-stroke", "pointer-events": "none"}));
      }
    }
    function drawCoaches(){
      gC.innerHTML = ""; if (!coachOn) return;
      for (const r of D.coach) {
        const res = !r.daily, p = el("path", {d: "M" + r.pts.map(([x, y]) => `${sx(x).toFixed(1)},${sy(y).toFixed(1)}`).join(" L"),
          class: "coach" + (res ? " res" : ""), "vector-effect": "non-scaling-stroke"});
        const rt = r.run_min < 60 ? `${r.run_min} min` : `${Math.floor(r.run_min / 60)}h${(r.run_min % 60).toString().padStart(2, "0")}`;
        const ti = el("title", {}); ti.textContent = `${r.route} · ${r.origin} to Maynooth · ${r.operator} · ${r.days} · dep ${r.depart}, arr ${r.arrive} (${rt})`;
        p.append(ti); gC.append(p);
        const [ox, oy] = r.pts[0];
        gC.append(el("circle", {cx: sx(ox), cy: sy(oy), r: 3.1 * ms(), class: "coachend" + (res ? " res" : ""), "vector-effect": "non-scaling-stroke"}));
        if (k > 1.15 || D.coach.length <= 12) {
          const t = el("text", {x: sx(ox) + 5 * ms(), y: sy(oy) + 3 * ms(), class: "coachl" + (res ? " res" : "")});
          t.textContent = r.route; t.style.fontSize = (8.5 * ms()) + "px"; gC.append(t);
        }
      }
    }
    function drawSchools(){
      if (!schoolsOn || !schoolSrc) return;
      const inSet = schoolSrc.inSet(), maxE = schoolSrc.maxE;
      schoolSrc.all.forEach(s => {
        if (!inSet.has(s.r)) return;
        const cx = sx(s.x), cy = sy(s.y), rr = (3.0 + 5.0 * Math.sqrt((s.e > 0 ? s.e : 120) / maxE)) * ms();
        if (coachOn && s.co) gP.append(el("circle", {cx, cy, r: rr + 3.2 * ms(), fill: "none", stroke: "var(--coach)", "stroke-width": 1.6, "vector-effect": "non-scaling-stroke", "pointer-events": "none"}));
        const dm = el("path", {d: `M ${cx},${cy-rr} L ${cx+rr},${cy} L ${cx},${cy+rr} L ${cx-rr},${cy} Z`, class: "school",
          fill: s.de ? "var(--coral)" : s.fp ? "var(--sand)" : "var(--navy)", stroke: "var(--surface)", "stroke-width": 1});
        dm.addEventListener("click", e => { e.stopPropagation(); schoolSrc.detail(s.r); });
        const ti = el("title", {}); ti.textContent = `${s.n} · ${s.ed || s.c} · ${s.e > 0 ? s.e + " pupils" : "enrolment n/a"}` + (s.co ? ` · ${s.co} coach corridor` : "");
        dm.append(ti); gP.append(dm);
      });
    }
    function draw(){
      gP.innerHTML = ""; drawHulls(); drawCoaches();
      if (layers !== "campuses") {
        const labels = (k > 1.3 || layers === "eds") ? labelSet() : topLabels;
        D.origins.forEach((o, i) => {
          const inst = EA()[i]?.[0];
          if (colour === "best" && !catchment && inst && hidden.has(inst)) return;
          const cx = sx(o.x), cy = sy(o.y), inCatch = !catchment || inst === catchment;
          const dot = el("circle", {cx, cy, r: (sel === i ? 3.8 : 2.4) * ms() * (inCatch ? 1 : .8), class: "ed" + (sel === i ? " sel" : ""), fill: edFill(i)});
          if (!inCatch) dot.setAttribute("fill-opacity", "0.12");
          gP.append(dot);
          const hit = el("circle", {cx, cy, r: Math.max(8, 4 * ms()), class: "hit"});
          hit.addEventListener("mouseenter", () => { if (!catchment) select(i); });
          hit.addEventListener("click", () => { if (!dragged) select(i); });
          gP.append(hit);
          if ((labels.has(i) || sel === i) && inCatch) { const t = el("text", {x: cx + 6 * ms(), y: cy - 4 * ms(), class: "edl"});
            t.textContent = o.n; t.style.fontSize = (9 * ms()) + "px"; gP.append(t); }
        });
      }
      drawSchools();
      if (layers !== "eds") D.campuses.forEach(c => {
        const s = ms(), dy = layers === "campuses" ? 0 : -9 * s;
        const g = el("g", {transform: `translate(${sx(c.x)},${sy(c.y) + dy}) scale(${s})`});
        g.append(el("circle", {r: 8, fill: "var(--surface)", stroke: "var(--hair-strong)", "stroke-width": 1, "vector-effect": "non-scaling-stroke"}));
        g.append(el("path", {d: "M -6,-1.4 L 0,-5 L 6,-1.4 L 0,2.2 Z", fill: "var(--ink)"}));
        g.append(el("path", {d: "M -3.4,0.7 L -3.4,2.8 Q 0,4.6 3.4,2.8 L 3.4,0.7", fill: "none", stroke: "var(--ink)", "stroke-width": 1, "vector-effect": "non-scaling-stroke"}));
        if (dy < -4) g.append(el("path", {d: `M 0,5 L 0,${-dy / s}`, stroke: "var(--hair-strong)", "stroke-width": 1, "vector-effect": "non-scaling-stroke"}));
        if (catchment === c.i) g.append(el("circle", {r: 11, fill: "none", stroke: "var(--navy)", "stroke-width": 2, "vector-effect": "non-scaling-stroke"}));
        const t = el("text", {x: 9, y: 2, class: "cl"}); t.textContent = c.s; g.append(t);
        g.style.cursor = "pointer"; g.addEventListener("click", e => { e.stopPropagation(); if (!dragged) selectCampus(c.i); });
        gP.append(g);
      });
      legend();
    }
    function legend(){
      const lg = q(".legend"), hint = q(".legendhint"); lg.innerHTML = "";
      if (colour === "best") {
        const used = [...new Set(D.origins.map((o, i) => EA()[i]?.[0]).filter(Boolean))]
          .sort((a, b) => D.campuses.findIndex(c => c.i === a) - D.campuses.findIndex(c => c.i === b));
        used.forEach(inst => { const s = document.createElement("span");
          s.className = "tog" + (hidden.has(inst) ? " off" : ""); s.innerHTML = `<span class="sw" style="background:${X.cColour(inst)}"></span>${inst}`;
          if (!catchment) s.onclick = () => { hidden.has(inst) ? hidden.delete(inst) : hidden.add(inst); draw(); };
          lg.append(s); });
        hint.textContent = catchment ? "" : "Click a campus name to show or hide the areas whose quickest trip is to it.";
      } else {
        [30, 60, 90, 120].forEach(v => { const s = document.createElement("span"); s.innerHTML = `<span class="sw" style="background:${rtCol(v)}"></span>${v} min`; lg.append(s); });
        hint.textContent = "";
      }
    }
    const apply = () => { gL.setAttribute("transform", `translate(${tx},${ty}) scale(${k})`); draw(); };
    const HEAD_ED = "<tr><th class='l'>Campus</th><th>AM</th><th>Round&nbsp;trip</th></tr>", HEAD_C = "<tr><th class='l'>County</th><th>Areas</th><th>17-19</th></tr>";
    function select(i){
      sel = i; catchment = null; const o = D.origins[i], row = X.OD[mMode][mSched][i] || {};
      const r = D.campuses.map((c, ci) => ({c, v: row[ci]})).filter(x => x.v).sort((a, b) => a.v[1] - b.v[1]);
      q(".sTbl thead").innerHTML = HEAD_ED; q(".sT").textContent = o.n; q(".sS").textContent = `${o.c} · cohort 17 to 19: ${o.coh}`;
      q(".sTbl tbody").innerHTML = r.length ? r.map((x, j) => `<tr${j === 0 ? ' style="color:var(--navy);font-weight:600"' : ""}>` +
        `<td class="l">${x.c.n}</td><td class="mono">${x.v[0]}</td><td class="mono">${x.v[1]}</td></tr>`).join("")
        : `<tr><td class="l" colspan="3" style="color:var(--coral)">no campus reachable</td></tr>`;
      edTable(); draw();
    }
    function selectCampus(inst){
      catchment = (catchment === inst) ? null : inst; sel = null; catchClusters = null;
      if (catchment) {
        const mem = D.origins.map((o, i) => ({o, i})).filter(x => EA()[x.i]?.[0] === catchment);
        catchClusters = clusterIdx(mem.map(x => x.i), 26);
        const coh = mem.reduce((a, x) => a + x.o.coh, 0), byC = {};
        mem.forEach(x => { byC[x.o.c] = byC[x.o.c] || {n: 0, c: 0}; byC[x.o.c].n++; byC[x.o.c].c += x.o.coh; });
        q(".sTbl thead").innerHTML = HEAD_C; q(".sT").textContent = D.campuses.find(c => c.i === catchment).n + ": catchment";
        q(".sS").textContent = `${mem.length} areas · ${coh.toLocaleString("en-IE")} of the 17 to 19 cohort (${Math.round(100 * coh / D.meta.cohort)}%) · click again to clear`;
        q(".sTbl tbody").innerHTML = Object.entries(byC).sort((a, b) => b[1].c - a[1].c)
          .map(([c, v]) => `<tr><td class="l">${c}</td><td class="mono">${v.n}</td><td class="mono">${v.c.toLocaleString("en-IE")}</td></tr>`).join("");
      } else {
        q(".sTbl thead").innerHTML = HEAD_ED; q(".sT").textContent = "Hover a dot"; q(".sS").textContent = "Electoral Division"; q(".sTbl tbody").innerHTML = "";
      }
      edTable(); draw();
    }
    const refreshCatch = () => { if (catchment) { const c = catchment; catchment = null; selectCampus(c); } };
    const clamp = () => { const m = 150; tx = Math.min(m, Math.max(SVGW - SVGW * k - m, tx)); ty = Math.min(m, Math.max(SVGH - SVGH * k - m, ty)); };
    const zoomAt = (vx, vy, f) => { const nk = Math.min(MAXK, Math.max(MINK, k * f)), wx = (vx - tx) / k, wy = (vy - ty) / k; k = nk; tx = vx - wx * k; ty = vy - wy * k; clamp(); apply(); };
    const toV = (cx, cy) => { const r = svg.getBoundingClientRect(); return [(cx - r.left) / r.width * SVGW, (cy - r.top) / r.height * SVGH]; };
    svg.addEventListener("wheel", e => { e.preventDefault(); const [vx, vy] = toV(e.clientX, e.clientY); zoomAt(vx, vy, Math.exp(-e.deltaY * 0.0016)); }, {passive: false});
    let drag = null, dragged = false;
    svg.addEventListener("pointerdown", e => { drag = {x: e.clientX, y: e.clientY, tx, ty, moved: false}; });
    svg.addEventListener("pointermove", e => { if (!drag) return; const r = svg.getBoundingClientRect();
      const dx = (e.clientX - drag.x) * SVGW / r.width, dy = (e.clientY - drag.y) * SVGH / r.height;
      if (!drag.moved && Math.hypot(dx, dy) > 4) { drag.moved = true; svg.setPointerCapture(e.pointerId); }
      if (drag.moved) { tx = drag.tx + dx; ty = drag.ty + dy; clamp(); apply(); } });
    const endDrag = () => { dragged = drag && drag.moved; drag = null; setTimeout(() => dragged = false, 0); };
    svg.addEventListener("pointerup", endDrag); svg.addEventListener("pointercancel", endDrag);
    q(".zin").onclick = () => zoomAt(SVGW / 2, SVGH / 2, 1.4); q(".zout").onclick = () => zoomAt(SVGW / 2, SVGH / 2, 1 / 1.4);
    q(".zrst").onclick = () => { k = 1; tx = 0; ty = 0; apply(); };
    q(".m-sched").onchange = e => { mSched = SCHEDS.indexOf(e.target.value); if (sel != null) select(sel); refreshCatch(); edTable(); draw(); };
    q(".m-mode").onchange = e => { mMode = X.MODES.indexOf(e.target.value); if (sel != null) select(sel); refreshCatch(); edTable(); draw(); };
    q(".m-colour").onchange = e => { colour = e.target.value; draw(); };
    q(".m-layers").onchange = e => { layers = e.target.value; draw(); };
    q(".m-coach").onchange = e => { coachOn = e.target.checked; q(".coachkey").style.display = coachOn ? "flex" : "none"; draw(); };
    q(".m-schools").onchange = e => { schoolsOn = e.target.checked; draw(); };
    svg.addEventListener("click", e => { if ((e.target === svg || e.target.classList.contains("land")) && catchment) selectCampus(catchment); });

    // the ED table, when this map's root has one
    const edt = root.querySelector("#r-edt"), edq = root.querySelector("#r-edq");
    let sK = "hei", sA = true;
    function edTable(){
      if (!edt) return;
      const f = edq.value.toLowerCase();
      let rows = D.origins.map((o, i) => { const a = EA()[i] || []; return {n: o.n, c: o.c, coh: o.coh, hei: a[1], uni: a[2], mu: a[3], mi: a[0] || "-"}; })
        .filter(r => !f || r.n.toLowerCase().includes(f) || r.c.toLowerCase().includes(f));
      if (catchment) rows = rows.filter(r => r.mi === catchment);
      root.querySelector("#r-edCount").textContent = catchment
        ? `showing the ${rows.length} areas where ${catchment} is the most accessible campus; clear the campus selection on the map to see all` : `${rows.length} areas`;
      rows.sort((a, b) => { let x = a[sK], y = b[sK]; if (x == null) x = 1e9; if (y == null) y = 1e9;
        return typeof x === "string" ? (sA ? x.localeCompare(y) : y.localeCompare(x)) : (sA ? x - y : y - x); });
      edt.querySelector("tbody").innerHTML = rows.slice(0, 500).map(r => `<tr><td class="l">${r.n}</td><td class="l">${r.c}</td>` +
        `<td class="mono">${r.coh}</td><td class="mono">${r.hei ?? "-"}</td><td class="mono">${r.uni ?? "-"}</td><td class="mono">${r.mu ?? "-"}</td>` +
        `<td class="l">${r.mi}</td></tr>`).join("");
    }
    if (edt) {
      edq.addEventListener("input", edTable);
      edt.querySelectorAll("th").forEach(th => th.onclick = () => { const k2 = th.dataset.k; if (k2 === sK) sA = !sA; else { sK = k2; sA = true; } edTable(); });
    }
    apply(); edTable();
    select(D.origins.findIndex(o => o.n.toLowerCase().startsWith("maynooth")));
    function showSchool(s){
      if (!s) return;
      select(s.oi);
      q(".sT").textContent = s.n;
      q(".sS").textContent = `${s.ed || s.c} · ${s.ty}, ${s.g.toLowerCase()} · ${s.e == null ? "enrolment n/a" : s.e + " pupils"}` +
        `${s.lc == null ? "" : ", " + s.lc + " Leaving Cert"} · times are its area's`;
    }
    return {draw, showSchool, setSchools: src => { schoolSrc = src; }};
  }

  function schools($, root, map){
    if (!D.schools || !D.schools.length) return;
    const S = schoolList();
    const byRoll = Object.fromEntries(S.map(s => [s.r, s])), maxE = Math.max(...S.map(s => s.e || 0), 1);
    const modeName = {pt: "public transport", pt_plus_rail: "PT + drive-to-rail", car: "car"};
    const timeTo = (s, hei, mode, si) => { const row = X.HT[si][X.HI[hei]][s.oi]; return row ? row[X.MFLD[mode]] : null; };
    $("#s-scHei").innerHTML = X.HEIS.map(h => `<option value="${h}">${hn(h)}</option>`).join(""); $("#s-scHei").value = "MU";
    let scK = "t", scAsc = true, lastRoll = null;
    const cfg = () => ({hei: $("#s-scHei").value, thr: +$("#s-scThr").value, mode: $("#s-scMode").value, si: SCHEDS.indexOf($("#s-scSched").value),
      deis: $("#s-scDeis").checked, im: $("#s-scIm").checked, noFee: $("#s-scNoFee").checked, coach: $("#s-scCoach").checked, minE: +$("#s-scMinE").value || 0});
    const filtered = () => { const c = cfg();
      return S.map(s => ({...s, t: timeTo(s, c.hei, c.mode, c.si)})).filter(s => s.t != null && s.t <= c.thr
        && (!c.deis || s.de) && (!c.im || s.im) && (!c.noFee || !s.fp) && (!c.coach || s.co) && ((s.e || 0) >= c.minE)); };
    function showDetail(roll){
      const c = cfg(), s = byRoll[roll]; if (!s) return; lastRoll = roll;
      $("#s-scSt").textContent = s.n;
      $("#s-scSs").textContent = `${s.ed || s.c}, ${s.c}` + (s.ei ? ` · ${s.ei}` : "") + ` · roll ${s.r}`;
      const d = [["Type", s.ty], ["Gender", s.g], ["Ethos", s.et || "-"], ["Language", s.im ? "Irish-medium" : "English-medium"],
        ["DEIS", s.de ? "Yes" : "No"], ["Fee-paying", s.fp ? "Yes" : "No"], ["Maynooth coach", s.co ? `on the ${s.co} corridor` : "not on a daily corridor"],
        ["Enrolment", s.e == null ? "-" : s.e.toLocaleString("en-IE")],
        ["Leaving Cert pupils", s.lc == null ? "-" : s.lc.toLocaleString("en-IE")]];
      $("#s-scDet tbody").innerHTML = d.map(([k, v]) => `<tr><td class="l" style="color:var(--muted)">${k}</td><td class="l">${v}</td></tr>`).join("");
      const reach = X.HEIS.map(h => ({h, t: timeTo(s, h, c.mode, c.si)})).filter(x => x.t != null).sort((a, b) => a.t - b.t);
      $("#s-scHeis tbody").innerHTML = reach.length ? reach.map(x => `<tr${x.h === c.hei ? ' style="font-weight:700;color:var(--navy)"' : ""}>` +
        `<td class="l">${x.h === "MU" ? "Maynooth" : x.h}</td><td class="mono">${Math.round(x.t)} min</td></tr>`).join("")
        : `<tr><td class="l" colspan="2" style="color:var(--coral)">no HEI reachable by this mode</td></tr>`;
    }
    function render(){
      const c = cfg(), rows = filtered(), pupils = rows.reduce((a, s) => a + (s.e || 0), 0);
      $("#s-scSummary").innerHTML = `<b>${rows.length} schools</b> within ${c.thr === 999 ? "any distance" : c.thr + "&nbsp;min"} of ` +
        `<b>${c.hei === "MU" ? "Maynooth" : c.hei}</b> by ${modeName[c.mode]} (${c.si ? "late" : "peak"} schedule), <b>${pupils.toLocaleString("en-IE")}&nbsp;pupils</b>. ` +
        `${rows.filter(s => s.de).length} DEIS, ${rows.filter(s => s.fp).length} fee-paying, ${rows.filter(s => s.im).length} Irish-medium, ` +
        `${rows.filter(s => s.co).length} on a Maynooth coach corridor.`;
      rows.sort((a, b) => { let va = a[scK], vb = b[scK];
        if (scK === "de" || scK === "im" || scK === "fp") { va = va ? 1 : 0; vb = vb ? 1 : 0; }
        if (typeof va === "string") return va.localeCompare(vb || "") * (scAsc ? 1 : -1);
        va = va == null ? 1e9 : va; vb = vb == null ? 1e9 : vb; return (va - vb) * (scAsc ? 1 : -1); });
      $("#s-scTbl tbody").innerHTML = rows.map(s => `<tr data-r="${s.r}" style="cursor:pointer"><td class="l">${s.n}</td><td class="l">${s.ed || s.c}</td>` +
        `<td class="l">${s.ty}</td><td class="l">${s.g}</td><td class="mono">${s.de ? "&#10003;" : ""}</td><td class="mono">${s.im ? "&#10003;" : ""}</td>` +
        `<td class="mono">${s.fp ? "&#10003;" : ""}</td><td class="l mono" style="color:var(--coach)">${s.co || ""}</td>` +
        `<td class="mono">${s.e == null ? "&ndash;" : s.e}</td><td class="mono">${Math.round(s.t)}</td></tr>`).join("");
      $("#s-scTbl tbody").querySelectorAll("tr").forEach(tr => tr.onclick = () => showDetail(tr.dataset.r));
      const div = c.thr === 999 ? 90 : c.thr;
      $("#s-scShort tbody").innerHTML = rows.map(s => ({s, sc: (s.lc || 0) * Math.max(0, 1 - s.t / Math.max(div, 1))}))
        .sort((a, b) => b.sc - a.sc).slice(0, 15).map((x, i) => `<tr><td class="mono">${i + 1}</td><td class="l">${x.s.n}</td>` +
          `<td class="l">${x.s.ed || x.s.c}</td><td class="mono">${x.s.lc == null ? "&ndash;" : x.s.lc}</td><td class="mono">${Math.round(x.s.t)}</td>` +
          `<td class="mono">${Math.round(x.sc)}</td></tr>`).join("");
      if (lastRoll) showDetail(lastRoll);
      if (map) map.draw();
    }
    if (map) map.setSchools({all: S, maxE, inSet: () => new Set(filtered().map(s => s.r)),
      detail: roll => { showDetail(roll); $("#s-scSide").scrollIntoView({block: "center"}); }});
    $("#s-scTbl thead").querySelectorAll("th[data-k]").forEach(th => th.onclick = () => {
      const kk = th.dataset.k; if (scK === kk) scAsc = !scAsc; else { scK = kk; scAsc = ["n", "ed", "ty", "g", "co"].includes(kk); } render(); });
    ["#s-scHei", "#s-scThr", "#s-scMode", "#s-scSched", "#s-scDeis", "#s-scIm", "#s-scNoFee", "#s-scCoach"].forEach(id => $(id).addEventListener("change", render));
    $("#s-scMinE").addEventListener("input", render);
    $("#s-scDl").onclick = async () => {
      const c = cfg(), rows = filtered().sort((a, b) => a.t - b.t);
      const esc = v => { v = v == null ? "" : String(v); return /[",\n]/.test(v) ? '"' + v.replace(/"/g, '""') + '"' : v; };
      const hdr = ["roll", "school", "town_ed", "county", "type", "gender", "ethos", "irish_medium", "deis", "fee_paying",
        "maynooth_coach_route", "enrolment", "leaving_cert_pupils", "eircode", "minutes_to_hei", "hei", "mode", "schedule"];
      const text = hdr.join(",") + "\n" + rows.map(s => [s.r, s.n, s.ed, s.c, s.ty, s.g, s.et, s.im ? "Y" : "N", s.de ? "Y" : "N",
        s.fp ? "Y" : "N", s.co, s.e, s.lc, s.ei, Math.round(s.t), c.hei, c.mode, c.si ? "late" : "peak"].map(esc).join(",")).join("\n");
      APP.download(`schools-${c.hei.replace(/\s+/g, "")}-${c.thr}min-${c.mode}-${c.si ? "late" : "peak"}.csv`, text, "text/csv");
    };
    render();
  }

  function methods(el){
    data();
    el.innerHTML = `
  <p><b>Public transport.</b> <b>r5py</b> (Conveyal R5) on the Transport for Ireland national GTFS (<code>${D.meta.gtfs}</code>)
  and an OpenStreetMap street network, analysis date ${D.meta.date}. Walk plus scheduled transit, median door-to-door minutes
  over a 60-minute departure window, one representative term Wednesday. <b>PT + drive-to-rail</b> adds the option of driving
  to a rail station (car time by the rule below, capped at 40&nbsp;min, plus 6&nbsp;min to park) and takes the better of the two.</p>
  <p><b>Car.</b> Free-flow drive times come from a local <b>OSRM</b> server on the same OpenStreetMap network, using OSRM's
  default car profile (road-class speeds and turn penalties, no live traffic). Each free-flow time is multiplied by a
  <b>congestion factor</b> that depends on the destination and the time of day:</p>
  <div class="scroll"><table>
    <thead><tr><th class="l">&nbsp;</th><th>Morning peak (arrive 08:30)</th><th>Morning shoulder (arrive 10:00)</th><th>Evening (leave 17:00 to 18:30)</th></tr></thead>
    <tbody>
      <tr><td class="l">Dublin-bound campus</td><td>&times;1.50</td><td>&times;1.25</td><td>&times;1.45</td></tr>
      <tr><td class="l">Regional campus (MU, TUS, DkIT, SETU)</td><td>&times;1.20</td><td>&times;1.10</td><td>&times;1.18</td></tr>
    </tbody></table></div>
  <p>"Dublin-bound" is any campus inside the Dublin built-up area (DCU, UCD, Trinity, the three TU&nbsp;Dublin sites, Marino,
  NCAD, RCSI, IADT); the rest are approached mostly from outside the M50. This is a deliberate simplification: it keys off the
  destination, not the route, so a drive from Athlone to a Dublin campus gets the same &times;1.50 whether or not the M50 is on
  the path. A one-way drive over 150&nbsp;minutes is treated as not a daily commute.</p>
  <div class="m-standalone"><p><b>Population.</b> 1,197 Electoral Divisions in 15 county areas (Leinster except Wexford, plus Monaghan; Dublin's four council areas counted separately), each represented by its population-weighted centre (from
  Census 2022 Small Areas) and weighted by its college-entry cohort (${D.meta.cohort.toLocaleString("en-IE")} in all). The census
  counts third-level students at their term-time address, so its 18 and 19 year olds cluster beside campuses; each area's
  weight is therefore its 15 to 17 year olds, who still live at home, scaled so the regional total equals the census
  count of 17 to 19 year olds.</p></div>
  <p><b>Schools.</b> The ${D.schools.length} post-primary schools come from the Department of Education's "Data on Individual
  Schools", post-primary, final 2025/26 (the October Returns, census date 30&nbsp;September&nbsp;2025; CC&nbsp;BY&nbsp;4.0), placed by
  the Department's own coordinates and filtered to the study region by spatial join to the Small Area each school sits in.
  Roll number, name, Eircode, type, gender, ethos, patron, Irish classification, fee-paying status, DEIS status and
  enrolment by year group are the Department's fields. "Irish-medium" means all or some pupils are taught every subject
  through Irish (an Irish-medium school or stream). Each school takes its Electoral Division's commute time. The
  shortlist's opportunity score is Leaving Certificate pupils (fifth and sixth year) &times;
  <code>max(0, 1 &minus; time / threshold)</code>, a deliberately simple prompt with no behavioural content.</p>
  <div class="m-standalone"><p><b>Caveats.</b> Potential accessibility only. The car mode assumes a car is available, which is itself unevenly
  distributed and correlated with the rural areas where it matters most. Points, course availability, accommodation and cost
  sit between this and enrolment; the <a href="#choice">enrolment model</a> takes the first look at that link. The Maynooth
  commuter coaches <i>are</i> in the public-transport layer, but their single timed morning run is under-credited by a
  departure-window median. The schools layer is <b>reach, not feeder flow</b>: it shows which schools a campus is commutable
  from, not which schools send it students.</p></div>
  <div class="m-standalone"><p><b>Reproduce.</b> Scripts <code>20</code> to <code>26</code> (origins, campuses, r5py and OSRM matrices, accessibility),
  <code>28</code> (coach routes) and <code>31</code> (schools); parameters in <code>scripts/config.py</code>.</p></div>`;
  }

  return {init, methods};
})();
"""
