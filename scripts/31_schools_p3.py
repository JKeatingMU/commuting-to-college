"""Phase 3 schools layer: post-primary schools in the commute study region,
joined to their Electoral Division so each inherits its ED's commute times.

Source: Department of Education, "Data on Individual Schools", post-primary, final 2025/26 (October
        Returns via P-POD, census date 30 Sep 2025, final as of 26 Jun 2026), CC BY 4.0 through the
        data.gov.ie record "Data on Individual Schools". Sheet "School Lists" gives roll number, name,
        address, Eircode, coordinates, type, gender, ethos, patron, Irish classification, fee-paying,
        Gaeltacht and DEIS flags and enrolment; sheet "Programme & Year" gives enrolment by year group
        (JC1 to LC2). Principal name, email and phone are in the file but are not carried forward.
        (Before 2 Oct 2026 the source was the Department's ArcGIS "Schools Map" layer, which states no licence.)

Output: outputs/p3_schools.csv   one row per post-primary school in the 15-county region
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from shapely.geometry import box

import config as C

SCHOOLS_XLSX = C.RAW / "doe-data-on-individual-schools-postprimary-2025-26-20261002.xlsx"
# Irish-medium = a full Irish-medium school or stream (an aonad): all, or some, pupils taught ALL subjects through Irish
IRISH_MEDIUM = {"All pupils taught all subjects through Irish", "Some pupils taught all subjects through Irish"}


def load_schools() -> gpd.GeoDataFrame:
    lst = pd.read_excel(SCHOOLS_XLSX, "School Lists", header=1, dtype={"Roll Number": str})
    yrs = pd.read_excel(SCHOOLS_XLSX, "Programme & Year", header=1, dtype={"Roll Number": str})
    lst = lst[lst["Roll Number"].notna() & lst["School Latitude"].notna()]
    yrs = yrs[["Roll Number", "JC 1", "JC 2", "JC 3", "TY", "LC 1", "LC 2"]].dropna(subset=["Roll Number"])
    df = lst.merge(yrs, on="Roll Number", how="left", validate="one_to_one")
    print(f"{len(df)} post-primary schools nationally in {SCHOOLS_XLSX.name}")
    return gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["School Longitude"], df["School Latitude"]), crs=4326)


def main() -> None:
    g = load_schools()

    W, S, E, N = C.BBOX_P3
    g = g[g.geometry.within(box(W, S, E, N))].copy()
    print(f"{len(g)} post-primary schools inside the study bounding box")

    # --- attach each school to its Electoral Division via the Small Area it sits in ---
    # CSO Small Areas 2022 geojson is EPSG:2157 (metres); work in that CRS.
    g2157 = g.to_crs(2157)
    bb = gpd.GeoSeries([box(W, S, E, N)], crs=4326).to_crs(2157).total_bounds
    print("reading Small Area boundaries (bbox-clipped, EPSG:2157) ...")
    sa = gpd.read_file(C.SA_GEOJSON, bbox=tuple(bb),
                       columns=["SA_GEOGID_2022", "ED_ID_STR", "ED_ENGLISH",
                                "COUNTY_ENGLISH"])
    if sa.crs is None:
        sa = sa.set_crs(2157)
    print(f"  {len(sa)} Small Areas")
    joined = gpd.sjoin(g2157, sa[["ED_ID_STR", "ED_ENGLISH", "COUNTY_ENGLISH", "geometry"]],
                       how="left", predicate="within")
    joined = joined[~joined.index.duplicated(keep="first")]
    joined["geometry"] = g["geometry"]   # keep WGS84 point for output

    origins = pd.read_csv(C.PROC / "origins_p3.csv", dtype={"ed_id": str})
    origins["oid"] = origins["ed_id"].str.zfill(6)
    valid = set(origins["oid"])
    joined["oid"] = joined["ED_ID_STR"].astype("string").str.zfill(6)
    keep = joined[joined["oid"].isin(valid)].copy()
    print(f"{len(keep)} schools fall inside a study-region ED "
          f"({len(joined) - len(keep)} outside)")

    yn = lambda s: keep[s].astype("string").str.strip().str.upper().eq("Y")
    num = lambda s: pd.to_numeric(keep[s], errors="coerce")
    out = pd.DataFrame({
        "roll": keep["Roll Number"].astype("string").str.strip(),
        "name": keep["Official School Name"].astype("string").str.strip().str.rstrip(", "),
        "county": keep["COUNTY_ENGLISH"].astype("string").str.title(),
        "eircode": keep["Eircode"].astype("string").str.strip(),
        "addr": keep[["Address 1", "Address 2", "Address 3", "Address 4"]].astype("string").apply(
            lambda r: ", ".join(x.strip() for x in r if isinstance(x, str) and x.strip()), axis=1),
        "pp_type": keep["Post Primary School Type"].astype("string").str.strip(),
        "attendance": keep["Pupil Attendance Type"].astype("string").str.strip(),
        "gender": keep["School Gender - Post Primary"].astype("string").str.strip(),
        "ethos": keep["Ethos"].astype("string").str.strip().str.title(),
        "patron": keep["Patron"].astype("string").str.strip(),
        "language": keep["Irish Classification - Post Primary"].astype("string").str.strip(),
        "irish_medium": keep["Irish Classification - Post Primary"].astype("string").str.strip().isin(IRISH_MEDIUM),
        "gaeltacht": yn("Gaeltacht Area Location (Y/N)"),
        "fee_paying": yn("Fee Paying School (Y/N)"),
        "deis": yn("DEIS (Y/N)"),
        "enrolment": num("Total 2025-2026"),
        "female": num("FEMALE"),
        "male": num("MALE"),
        "lc1": num("LC 1"),
        "lc2": num("LC 2"),
        "lc": num("LC 1").fillna(0) + num("LC 2").fillna(0),
        "lat": keep.geometry.y.round(6),
        "lon": keep.geometry.x.round(6),
        "oid": keep["oid"],
        "ed_name": keep["ED_ENGLISH"].astype("string").str.title(),
        "planning_area": keep["School Planning area"].astype("string").str.strip(),
    }).sort_values(["county", "name"]).reset_index(drop=True)

    out.to_csv(C.OUT / "p3_schools.csv", index=False)
    print(f"\nwrote p3_schools.csv ({len(out)} schools)")
    print(out.groupby("county").agg(n=("roll", "size"), pupils=("enrolment", "sum"),
                                    leaving_cert=("lc", "sum")).to_string())
    print("\nby type:", out["pp_type"].value_counts().to_dict())
    print("DEIS:", int(out["deis"].sum()), " fee-paying:", int(out["fee_paying"].sum()),
          " Irish-medium:", int(out["irish_medium"].sum()))


if __name__ == "__main__":
    main()
