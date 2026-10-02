"""Phase 3: extract the Maynooth commuter-coach corridors (UM01-UM15) from the GTFS.

These dedicated Maynooth University coach services (JJ Kavanagh, Kearns, Streamline,
Slevins, Wexford Bus, ...) are already in the TFI national feed and already in the PT
matrices. This script pulls their route geometry + one representative inbound trip so
the report can draw them as a toggle-able map layer and tabulate them, plus every pickup
stop (used by 29_costs_p3 for the coach-fare catchment).

Output: outputs/p3_coach_routes.json
"""

from __future__ import annotations

import csv
import io
import json
import zipfile
from collections import defaultdict

from shapely.geometry import LineString

import config as C

# A trip "arrives at Maynooth" if its last stop falls inside this box around the town.
MAYN_S, MAYN_N, MAYN_W, MAYN_E = 53.355, 53.400, -6.625, -6.575
MORNING_MIN, MORNING_MAX = "05:30:00", "11:00:00"   # a weekday inbound in this window = commuter run


def _at_maynooth(stop):
    if not stop:
        return False
    lat, lon = float(stop["stop_lat"]), float(stop["stop_lon"])
    return MAYN_S <= lat <= MAYN_N and MAYN_W <= lon <= MAYN_E


def _reader(zf, name):
    return csv.DictReader(io.TextIOWrapper(zf.open(name), encoding="utf-8-sig"))


def main() -> None:
    zf = zipfile.ZipFile(C.GTFS_RAW)

    agency = {r["agency_id"]: r["agency_name"] for r in _reader(zf, "agency.txt")}

    routes = {r["route_id"]: r for r in _reader(zf, "routes.txt")
              if r["route_short_name"].upper().startswith("UM")
              and r["route_short_name"][2:].isdigit()}
    if not routes:
        raise SystemExit("no UM* routes found in the feed")

    cal = {r["service_id"]: r for r in _reader(zf, "calendar.txt")}

    trips = defaultdict(list)          # route_id -> [trip dict]
    trip_route, want_trips = {}, set()
    for r in _reader(zf, "trips.txt"):
        if r["route_id"] in routes:
            trips[r["route_id"]].append(r)
            trip_route[r["trip_id"]] = r["route_id"]
            want_trips.add(r["trip_id"])

    # stop_times.txt is large - single filtered pass
    st = defaultdict(list)
    for r in _reader(zf, "stop_times.txt"):
        if r["trip_id"] in want_trips:
            st[r["trip_id"]].append(r)
    for tid in st:
        st[tid].sort(key=lambda x: int(x["stop_sequence"]))

    stops = {r["stop_id"]: r for r in _reader(zf, "stops.txt")}

    # shapes: only those referenced by UM trips
    want_shapes = {t["shape_id"] for tl in trips.values() for t in tl if t.get("shape_id")}
    shape_pts = defaultdict(list)
    for r in _reader(zf, "shapes.txt"):
        if r["shape_id"] in want_shapes:
            shape_pts[r["shape_id"]].append(
                (int(r["shape_pt_sequence"]), float(r["shape_pt_lon"]), float(r["shape_pt_lat"])))
    for sid in shape_pts:
        shape_pts[sid].sort()

    def days(service_id):
        c = cal.get(service_id)
        if not c:
            return "?"
        wk = [c[d] == "1" for d in ("monday", "tuesday", "wednesday", "thursday")]
        fri, sun = c["friday"] == "1", c["sunday"] == "1"
        if all(wk):
            return "Mon-Fri" if fri else "Mon-Thu"
        if fri and sun and not any(wk):
            return "Fri + Sun"
        if sun and not any(wk) and not fri:
            return "Sun only"
        if fri and not any(wk):
            return "Fri only"
        return "term-time"

    def simplify(pts, tol=0.0018):
        line = LineString([(lon, lat) for _, lon, lat in pts]).simplify(tol)
        return list(line.coords)

    # one record per route_short_name (routes.txt sometimes splits a route into "UM11" + "UM11 a")
    by_short = {}
    for rid, rt in routes.items():
        by_short.setdefault(rt["route_short_name"], []).append((rid, rt))

    def _weekday_first(x):
        return (0 if days(x[1]["service_id"]).startswith("Mon") else 1, x[0])

    records = []
    for short, variants in sorted(by_short.items()):
        rt = variants[0][1]
        inbound = []
        for rid, _ in variants:
            for t in trips[rid]:
                seq = st.get(t["trip_id"], [])
                if seq and _at_maynooth(stops.get(seq[-1]["stop_id"])):
                    inbound.append((seq[-1]["arrival_time"], t, seq))
        if not inbound:
            continue
        morning = sorted((x for x in inbound if MORNING_MIN <= x[0] <= MORNING_MAX),
                         key=_weekday_first)
        arr, t, seq = (morning[0] if morning else sorted(inbound, key=lambda x: x[0])[0])
        commuter = bool(morning)

        board = seq[0]
        board_name = stops.get(board["stop_id"], {}).get("stop_name", "?")
        dep = board["departure_time"]
        run = _minutes(arr) - _minutes(dep)

        shp = shape_pts.get(t["shape_id"])
        if shp:
            path = [[round(lon, 5), round(lat, 5)] for lon, lat in simplify(shp)]
        else:
            path = [[round(float(stops[s["stop_id"]]["stop_lon"]), 5),
                     round(float(stops[s["stop_id"]]["stop_lat"]), 5)] for s in seq
                    if s["stop_id"] in stops]

        records.append({
            "route": rt["route_short_name"],
            "name": rt["route_long_name"],
            "origin": rt["route_long_name"].split(" - ")[0].strip(),
            "operator": agency.get(rt["agency_id"], rt["agency_id"]),
            "days": days(t["service_id"]),
            "daily": commuter,
            "board": board_name,
            "depart": dep[:5],
            "arrive": arr[:5],
            "run_min": round(run),
            "n_stops": len(seq),
            "path": path,
            "stops": [[round(float(stops[x["stop_id"]]["stop_lon"]), 5),
                       round(float(stops[x["stop_id"]]["stop_lat"]), 5),
                       stops[x["stop_id"]]["stop_name"]] for x in seq
                      if x["stop_id"] in stops and not _at_maynooth(stops[x["stop_id"]])],
        })

    out = C.OUT / "p3_coach_routes.json"
    out.write_text(json.dumps(records, indent=1))
    print(f"wrote {out.name}: {len(records)} routes")
    for r in records:
        print(f"  {r['route']:5s} {r['operator']:16s} {r['days']:11s} "
              f"{r['board'][:28]:28s} {r['depart']}->{r['arrive']} ({r['run_min']}m, {len(r['path'])} pts)")


def _minutes(hms):
    h, m, s = (int(x) for x in hms.split(":"))
    return h * 60 + m + s / 60


if __name__ == "__main__":
    main()
