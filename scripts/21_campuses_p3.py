"""Phase 3 campus set: the 11 Dublin-area campuses plus 4 regional HEIs
(TUS Athlone, DkIT Dundalk, SETU Carlow, Carlow College).

Output: data/processed/campuses_p3.gpkg / .csv
"""

from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import Point

import config as C

# reuse the Phase 1/2 campuses, add the regionals
EXTRA = [
    ("tus_athlone", "TUS Athlone", "TUS", -7.9365, 53.4232),
    ("dkit_dundalk", "Dundalk IT", "DkIT", -6.3928, 54.0059),
    ("setu_carlow", "SETU Carlow", "SETU", -6.9432, 52.8338),
    # Carlow College (St Patrick's) dropped - closing.
]


def main() -> None:
    base = gpd.read_file(C.PROC / "campuses.gpkg").drop(columns="geometry")
    extra = pd.DataFrame(EXTRA, columns=["id", "name", "institution", "lon", "lat"])
    allc = pd.concat([base, extra], ignore_index=True)
    g = gpd.GeoDataFrame(allc, geometry=[Point(xy) for xy in zip(allc.lon, allc.lat)],
                         crs="EPSG:4326")
    g.to_file(C.PROC / "campuses_p3.gpkg", driver="GPKG")
    g.drop(columns="geometry").to_csv(C.PROC / "campuses_p3.csv", index=False)
    print(f"{len(g)} campuses -> campuses_p3.gpkg")
    print(g[["id", "name", "institution"]].to_string(index=False))
    w, s, e, n = C.BBOX_P3
    oob = g[~g.geometry.x.between(w, e) | ~g.geometry.y.between(s, n)]
    if len(oob):
        raise SystemExit(f"campus outside bbox: {list(oob['name'])}")


if __name__ == "__main__":
    main()
