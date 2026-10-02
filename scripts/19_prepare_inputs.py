"""Prepare the derived inputs that the Phase 3 pipeline reads but that are not themselves downloads:

  data/processed/saps/*.csv                 CSO SAPS 2022 tables, unzipped from the raw archive
  data/processed/rail_stops.csv             every GTFS stop served by a rail route (route_type 2)
  data/processed/study-area-p3-<date>.osm.pbf   the OSM extract cropped to BBOX_P3 (osmium)
  data/osrm/study-area-p3-<date>.osrm*      the OSRM car graph (MLD: extract, partition, customize)

Each step is skipped when its output already exists; pass --force to rebuild everything.
Needs osmium-tool and osrm-backend on PATH (both from Homebrew; versions in docs/environment.md).
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import zipfile

import pandas as pd

import config as C

FORCE = "--force" in sys.argv
OSRM_DIR = C.ROOT / "data" / "osrm"
OSRM_GRAPH = OSRM_DIR / f"study-area-p3-{C.SNAPSHOT}.osrm"
SAPS_ZIP = C.RAW / f"cso-saps-2022-{C.SNAPSHOT}.zip"


def _todo(path) -> bool:
    if path.exists() and not FORCE:
        print(f"  exists, skipped: {path.name}")
        return False
    return True


def saps() -> None:
    out = C.PROC / "saps"
    out.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(SAPS_ZIP) as z:
        for name in z.namelist():
            if name.endswith(".csv") and _todo(out / name):
                z.extract(name, out)
                print(f"  unzipped {name}")


def rail_stops() -> None:
    dest = C.PROC / "rail_stops.csv"
    if not _todo(dest):
        return
    with zipfile.ZipFile(C.GTFS_RAW) as z:
        read = lambda f, **k: pd.read_csv(z.open(f), dtype=str, **k)
        routes = read("routes.txt")
        trips = read("trips.txt", usecols=["route_id", "trip_id"])
        rail_trips = set(trips[trips["route_id"].isin(set(routes[routes["route_type"] == "2"]["route_id"]))]["trip_id"])
        ids = set()
        for ch in pd.read_csv(z.open("stop_times.txt"), dtype=str, usecols=["trip_id", "stop_id"], chunksize=2_000_000):
            ids |= set(ch[ch["trip_id"].isin(rail_trips)]["stop_id"])
        stops = read("stops.txt")
    stops[stops["stop_id"].isin(ids)][["stop_id", "stop_name", "stop_lat", "stop_lon"]].to_csv(dest, index=False)
    print(f"  wrote {dest.name} ({len(ids)} rail stops)")


def crop_osm() -> None:
    if not _todo(C.OSM_CLIP_P3):
        return
    W, S, E, N = C.BBOX_P3
    subprocess.run(["osmium", "extract", "--bbox", f"{W},{S},{E},{N}", "--overwrite",
                    "-o", str(C.OSM_CLIP_P3), str(C.OSM_RAW)], check=True)
    print(f"  cropped {C.OSM_CLIP_P3.name}")


def osrm_graph() -> None:
    if not _todo(OSRM_GRAPH.with_suffix(".osrm.mldgr")):
        return
    OSRM_DIR.mkdir(parents=True, exist_ok=True)
    pbf = OSRM_DIR / C.OSM_CLIP_P3.name
    shutil.copyfile(C.OSM_CLIP_P3, pbf)
    profile = next(p for p in ("/opt/homebrew/share/osrm/profiles/car.lua",
                               "/usr/local/share/osrm/profiles/car.lua",
                               "/usr/share/osrm/profiles/car.lua") if shutil.os.path.exists(p))
    subprocess.run(["osrm-extract", "-p", profile, str(pbf)], check=True)
    subprocess.run(["osrm-partition", str(OSRM_GRAPH)], check=True)
    subprocess.run(["osrm-customize", str(OSRM_GRAPH)], check=True)
    print(f"  built {OSRM_GRAPH.name} with {profile}")


def main() -> None:
    for step in (saps, rail_stops, crop_osm, osrm_graph):
        print(step.__name__)
        step()


if __name__ == "__main__":
    main()
