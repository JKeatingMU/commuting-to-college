"""Phase 3 r5py matrices - one process, one network build, everything cached to parquet.

  p3_pt_<sched>_am.parquet / _pm.parquet   EDs <-> campuses, walk+transit, p25/50/75
  p3_car_freeflow.parquet                  EDs -> campuses, free-flow car (minutes)
  p3_car_to_station.parquet                EDs -> rail stations, free-flow car
  p3_dr_s2c_<sched>.parquet                stations -> campuses, transit (AM)
  p3_dr_c2s_<sched>.parquet                campuses -> stations, transit (PM)

Skips anything already on disk. Re-run after deleting a parquet to refresh it.
"""

from __future__ import annotations

import datetime

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config as C
from r5py import TransportNetwork, TravelTimeMatrix, TransportMode

WIN = datetime.timedelta(minutes=C.DEPART_WINDOW_MIN)
MAXT = datetime.timedelta(minutes=C.MAX_TRIP_MIN)
MAXWALK = datetime.timedelta(minutes=C.MAX_WALK_MIN)
TRANSIT = [TransportMode.TRANSIT, TransportMode.WALK]


def _tidy(ttm, pref):
    df = pd.DataFrame(ttm).copy()
    ren = {f"travel_time_p{p}": f"{pref}_p{p}" for p in C.PERCENTILES}
    if "travel_time" in df.columns:
        ren["travel_time"] = f"{pref}_p50"
    df = df.rename(columns=ren)
    cols = [c for c in df.columns if c.startswith(pref)]
    for c in cols:
        if pd.api.types.is_timedelta64_dtype(df[c]):
            df[c] = df[c].dt.total_seconds() / 60.0
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["from_id", "to_id"] + cols]


def _need(name):
    p = C.PROC / name
    return None if p.exists() else p


def main() -> None:
    origins = gpd.read_file(C.PROC / "origins_p3.gpkg")
    campuses = gpd.read_file(C.PROC / "campuses_p3.gpkg")
    stations = _stations()
    print(f"{len(origins)} EDs, {len(campuses)} campuses, {len(stations)} rail stations")

    net = TransportNetwork(str(C.OSM_CLIP_P3), [str(C.GTFS_RAW)])

    CARMAX = datetime.timedelta(minutes=C.CAR_MAX_MIN)

    def ttm(origins_, dests_, departure=None, modes=TRANSIT, window=True):
        is_car = TransportMode.CAR in modes
        kw = dict(transport_modes=modes,
                  percentiles=[50] if is_car else C.PERCENTILES,
                  max_time=CARMAX if is_car else MAXT, snap_to_network=True)
        if departure is not None:
            kw["departure"] = departure
            if window:
                kw["departure_time_window"] = WIN
        if TransportMode.WALK in modes:
            kw["max_time_walking"] = MAXWALK
            kw["speed_walking"] = C.WALK_SPEED_KMH
        return TravelTimeMatrix(net, origins=origins_, destinations=dests_, **kw)

    # ---- PT, both schedules ----
    for sname, sch in C.SCHEDULES.items():
        f = _need(f"p3_pt_{sname}_am.parquet")
        if f:
            print(f"  PT {sname} AM: EDs -> campuses  @ {sch['am']:%H:%M}")
            _tidy(ttm(origins, campuses, sch["am"]), "am").to_parquet(f)
        f = _need(f"p3_pt_{sname}_pm.parquet")
        if f:
            print(f"  PT {sname} PM: campuses -> EDs  @ {sch['pm']:%H:%M}")
            _tidy(ttm(campuses, origins, sch["pm"]), "pm").to_parquet(f)

    # ---- free-flow car: done with OSRM (script 23) - R5's per-origin car Dijkstra
    #      over the 15-county network is far too slow at this scale. ----

    # ---- drive-to-rail transit legs, both schedules ----
    for sname, sch in C.SCHEDULES.items():
        f = _need(f"p3_dr_s2c_{sname}.parquet")
        if f:
            print(f"  DR {sname}: stations -> campuses (AM)")
            _tidy(ttm(stations, campuses,
                      sch["am"] + datetime.timedelta(minutes=25)), "am").to_parquet(f)
        f = _need(f"p3_dr_c2s_{sname}.parquet")
        if f:
            print(f"  DR {sname}: campuses -> stations (PM)")
            _tidy(ttm(campuses, stations, sch["pm"]), "pm").to_parquet(f)

    print("done")


def _stations():
    rs = pd.read_csv(C.PROC / "rail_stops.csv")
    w, s, e, n = C.BBOX_P3
    rs = rs[rs.stop_lon.between(w, e) & rs.stop_lat.between(s, n)].copy()
    rs = rs.rename(columns={"stop_id": "id"})
    rs["geometry"] = [Point(xy) for xy in zip(rs.stop_lon, rs.stop_lat)]
    return gpd.GeoDataFrame(rs, geometry="geometry", crs="EPSG:4326").reset_index(drop=True)


if __name__ == "__main__":
    main()
