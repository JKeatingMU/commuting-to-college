"""Phase 3 free-flow car matrices via a local OSRM server.

Produces the same parquet shape script 22 used to (from_id, to_id, car_p50 minutes):
  p3_car_freeflow.parquet     EDs -> campuses
  p3_car_to_station.parquet   EDs -> rail stations

Requires osrm-routed running on the p3 graph, e.g.:
  osrm-routed --algorithm mld --max-table-size 20000 \
    ~/HEI-commute-access/data/osrm/study-area-p3-20260827.osrm
This script starts and stops it itself if it is not already up.
"""

from __future__ import annotations

import subprocess
import time

import geopandas as gpd
import pandas as pd
import requests
from shapely.geometry import Point

import config as C

OSRM = "http://127.0.0.1:5111"
GRAPH = C.ROOT / "data" / "osrm" / f"study-area-p3-{C.SNAPSHOT}.osrm"


def _stations():
    rs = pd.read_csv(C.PROC / "rail_stops.csv")
    w, s, e, n = C.BBOX_P3
    rs = rs[rs.stop_lon.between(w, e) & rs.stop_lat.between(s, n)].copy()
    rs["geometry"] = [Point(xy) for xy in zip(rs.stop_lon, rs.stop_lat)]
    return gpd.GeoDataFrame(rs.rename(columns={"stop_id": "id"}),
                            geometry="geometry", crs="EPSG:4326").reset_index(drop=True)


def _table(src_lonlat, dst_lonlat):
    """OSRM /table -> minutes DataFrame-ready list of (si, di, minutes)."""
    coords = src_lonlat + dst_lonlat
    nS = len(src_lonlat)
    coord_str = ";".join(f"{lon:.6f},{lat:.6f}" for lon, lat in coords)
    sources = ";".join(str(i) for i in range(nS))
    dests = ";".join(str(i) for i in range(nS, len(coords)))
    url = f"{OSRM}/table/v1/driving/{coord_str}?sources={sources}&destinations={dests}&annotations=duration"
    r = requests.get(url, timeout=120)
    r.raise_for_status()
    durations = r.json()["durations"]
    out = []
    for si, row in enumerate(durations):
        for di, sec in enumerate(row):
            if sec is not None:
                out.append((si, di, sec / 60.0))
    return out


def _up():
    try:
        requests.get(f"{OSRM}/health", timeout=2)
        return True
    except Exception:
        return False


def main() -> None:
    proc = None
    if not _up():
        print("starting osrm-routed ...")
        proc = subprocess.Popen(
            ["osrm-routed", "--algorithm", "mld", "--port", "5111",
             "--max-table-size", "20000", str(GRAPH)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        for _ in range(60):
            time.sleep(1)
            if _up():
                break
        else:
            raise SystemExit("osrm-routed did not come up")

    try:
        origins = gpd.read_file(C.PROC / "origins_p3.gpkg")
        campuses = gpd.read_file(C.PROC / "campuses_p3.gpkg")
        stations = _stations()

        o_ll = list(zip(origins.geometry.x, origins.geometry.y))
        for dests, name, idcol in (
            (campuses, "p3_car_freeflow.parquet", campuses),
            (stations, "p3_car_to_station.parquet", stations),
        ):
            d_ll = list(zip(dests.geometry.x, dests.geometry.y))
            rows = _table(o_ll, d_ll)
            df = pd.DataFrame(rows, columns=["si", "di", "car_p50"])
            df["from_id"] = df["si"].map(dict(enumerate(origins["id"])))
            df["to_id"] = df["di"].map(dict(enumerate(idcol["id"])))
            df = df[["from_id", "to_id", "car_p50"]]
            df.to_parquet(C.PROC / name)
            print(f"  wrote {name}: {len(df):,} rows, "
                  f"median {df.car_p50.median():.0f} min")
    finally:
        if proc:
            proc.terminate()


if __name__ == "__main__":
    main()
