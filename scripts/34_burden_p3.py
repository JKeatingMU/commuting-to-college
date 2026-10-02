"""Inputs for "Who bears the commute?": deprivation and car availability per ED, plus
simplified ED and county shapes for the area maps.

Reads  data/raw/pobal-hp-deprivation-ed-2022-*.csv (Pobal HP Deprivation Index 2022, ED level, CC BY 4.0)
       Census 2022 SAPS Theme 15.1 (households by number of cars), Small Area level -> ED
       Small Area boundaries -> dissolved to ED and county
Writes outputs/p3_burden_ed.csv   (id, dep_score, dep_band, hh, hh_nocar, nocar_share)
       outputs/p3_ed_shapes.json  (SVG paths per ED and per county, county label points)
"""

from __future__ import annotations

import json

import geopandas as gpd
import pandas as pd

import config as C

POBAL = sorted(C.RAW.glob("pobal-hp-deprivation-ed-2022-*.csv"))[-1]
# The four bands the HEA uses for its socio-economic profiles, on Pobal's relative index
DEP_BINS = [-999, -10, 0, 10, 999]
DEP_LABELS = ["Disadvantaged", "Marginally below average", "Marginally above average", "Affluent"]
SIMPLIFY_M = 120
W, S, E, N = C.BBOX_P3
SVG_W, SVG_H = 720, 940   # same projection as the reach map


def _project(lon, lat):
    return (round((lon - W) / (E - W) * SVG_W, 1), round((N - lat) / (N - S) * SVG_H, 1))


def _path(geom):
    out = []
    for poly in ([geom] if geom.geom_type == "Polygon" else list(geom.geoms)):
        for ring in [poly.exterior, *poly.interiors]:
            pts = [_project(x, y) for x, y in ring.coords]
            out.append("M" + "L".join(f"{x},{y}" for x, y in pts) + "Z")
    return "".join(out)


def main() -> None:
    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"id": str})
    origins["id"] = origins["id"].str.zfill(6)

    dep = pd.read_csv(POBAL, dtype={"ED_ID_STR": str}, thousands=",", encoding="latin-1")
    dep["id"] = dep["ED_ID_STR"].str.strip().str.zfill(6)
    dep = dep[["id", "Index22_ED_std_rel_wt"]].rename(columns={"Index22_ED_std_rel_wt": "dep_score"})

    sa = gpd.read_file(C.SA_GEOJSON, columns=["SA_GEOGID_2022", "ED_ID_STR", "COUNTY_ENGLISH"])
    sa = sa[sa["COUNTY_ENGLISH"].isin(C.P3_SA_COUNTIES)].copy()
    sa["sa_id"] = sa["SA_GEOGID_2022"].astype(str).str.lstrip("A")
    sa["id"] = sa["ED_ID_STR"].astype(str).str.zfill(6)

    cars = pd.read_csv(C.SAPS_SA, encoding="latin-1", usecols=["GEOGID", "T15_1_NC", "T15_1_NSC", "T15_1_TC"])
    cars["sa_id"] = cars["GEOGID"].astype(str).str.strip()
    hh = (sa[["sa_id", "id"]].merge(cars, on="sa_id", how="left")
          .groupby("id")[["T15_1_NC", "T15_1_NSC", "T15_1_TC"]].sum().reset_index())
    hh["hh"] = (hh["T15_1_TC"] - hh["T15_1_NSC"]).clip(lower=0)
    hh["hh_nocar"] = hh["T15_1_NC"]
    hh["nocar_share"] = (hh["hh_nocar"] / hh["hh"].where(hh["hh"] > 0)).round(4)

    out = (origins[["id", "name", "county", "cohort_17_19"]]
           .merge(dep, on="id", how="left").merge(hh[["id", "hh", "hh_nocar", "nocar_share"]], on="id", how="left"))
    out["dep_band"] = pd.cut(out["dep_score"], DEP_BINS, labels=False)
    assert out["dep_score"].notna().all(), "unmatched deprivation scores"
    assert out["nocar_share"].notna().all(), "unmatched car availability"
    out.to_csv(C.OUT / "p3_burden_ed.csv", index=False)

    # shapes: dissolve Small Areas to ED and county, simplify in metres, project to the map frame
    g = sa.to_crs(2157)
    ed = g.dissolve("id")
    ed = ed[ed.index.isin(set(origins["id"]))]
    ed_paths = {i: _path(geom) for i, geom in ed.geometry.simplify(SIMPLIFY_M).to_crs(4326).items()}
    cty = g.dissolve("COUNTY_ENGLISH")
    cty_simpl = cty.geometry.simplify(SIMPLIFY_M * 2).to_crs(4326)
    # key counties by the names the tables use; keep a short map label alongside
    name = lambda c: "Dún Laoghaire-Rathdown" if "LAOGHAIRE" in c.upper() else c.title()
    short = lambda c: "DLR" if "LAOGHAIRE" in c.upper() else c.title()
    labels = {name(c): _project(*p.coords[0]) for c, p in cty.geometry.representative_point().to_crs(4326).items()}
    shorts = {name(c): short(c) for c in cty.index}
    camp = pd.read_csv(C.PROC / "campuses_p3.csv")
    shapes = {"svg": {"w": SVG_W, "h": SVG_H}, "ed": ed_paths,
              "campus": {r.id: _project(r.lon, r.lat) for r in camp.itertuples()},
              "county": {name(c): _path(geom) for c, geom in cty_simpl.items()}, "label": labels, "short": shorts}
    (C.OUT / "p3_ed_shapes.json").write_text(json.dumps(shapes, separators=(",", ":")))

    w = out["cohort_17_19"]
    print(f"wrote p3_burden_ed.csv ({len(out)} EDs) and p3_ed_shapes.json "
          f"({(C.OUT / 'p3_ed_shapes.json').stat().st_size / 1e3:.0f} KB, {len(ed_paths)} ED shapes)")
    print("cohort by deprivation band:")
    print((out.groupby("dep_band")["cohort_17_19"].sum() / w.sum() * 100).round(1)
          .rename(index=dict(enumerate(DEP_LABELS))).to_string())
    print(f"households with no car: {out['hh_nocar'].sum() / out['hh'].sum():.1%} "
          f"(ED range {out['nocar_share'].min():.0%} to {out['nocar_share'].max():.0%})")


if __name__ == "__main__":
    main()
