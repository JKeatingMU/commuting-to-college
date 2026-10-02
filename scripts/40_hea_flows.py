"""Phase 4: HEA new-entrant flows, county of domicile -> HEI, by field of study.

Parses the multi-year block files captured from the HEA "Access Our Data - Students"
dashboard (Choose Your Own Data: rows = County, columns = Institute; filters =
Field of Study = <field>, New Entrant = Yes, Course Level = Undergraduate). Values
are rounded to the nearest 5 by the HEA.

Three fields are captured, each its own dated file:
  computing         Information and Communication Technologies (ICTs)   snapshot 20260827
  natural_sciences  Natural sciences, mathematics and statistics        snapshot 20260830
  engineering       Engineering, manufacturing and construction         snapshot 20260830

Output: outputs/p4_flows.csv   one row per field x county x HEI x year (+ a pooled total)
"""
from __future__ import annotations

import io
import re

import pandas as pd

import config as C

FIELD_FILES = {
    "computing": "hea-ict-newentrants-county-institute-20260827.txt",
    "natural_sciences": "hea-naturalsci-newentrants-county-institute-20260830.txt",
    "engineering": "hea-engineering-newentrants-county-institute-20260830.txt",
    "business": "hea-business-newentrants-county-institute-20260830.txt",
    "health": "hea-health-newentrants-county-institute-20260830.txt",
    "arts": "hea-arts-newentrants-county-institute-20260830.txt",
    "social_science": "hea-socialscience-newentrants-county-institute-20260830.txt",
    "education": "hea-education-newentrants-county-institute-20260830.txt",
}
FIELD_LABEL = {
    "computing": "Information and Communication Technologies (ICTs)",
    "natural_sciences": "Natural sciences, mathematics and statistics",
    "engineering": "Engineering, manufacturing and construction",
    "business": "Business, administration and law",
    "health": "Health and welfare",
    "arts": "Arts and humanities",
    "social_science": "Social sciences, journalism and information",
    "education": "Education",
}

# HEA institute name -> our modelled HEI code. Institutes we do not model are dropped.
INSTITUTE_TO_HEI = {
    "Maynooth University": "MU",
    "Dublin City University": "DCU",
    "University College Dublin": "UCD",
    "Trinity College Dublin": "TCD",
    "TU Dublin Blanchardstown": "TU Dublin",
    "TU Dublin City": "TU Dublin",
    "TU Dublin Tallaght": "TU Dublin",
    "Dundalk IT": "DkIT",
    "TUS Athlone": "TUS",
    "SETU Carlow": "SETU",
    "SETU Waterford": "SETU",
}
# study region = the 12 HEA counties that make up the Phase 3 origin set (Dublin is one)
STUDY_COUNTIES = ["Carlow", "Dublin", "Kildare", "Kilkenny", "Laois", "Longford",
                  "Louth", "Meath", "Monaghan", "Offaly", "Westmeath", "Wicklow"]
POOLED_YEAR = "2018/2019-2024/2025"


def parse_blocks(text: str) -> pd.DataFrame:
    rows = []
    for block in re.split(r"^### ", text, flags=re.M):
        block = block.strip()
        if not block:
            continue
        head, _, body = block.partition("\n")
        year = head.strip().replace("_", "/")
        df = pd.read_csv(io.StringIO(body))
        df = df[~df["County"].isin(["TOTAL", "N/A"])]
        long = df.melt(id_vars="County", var_name="institute", value_name="n")
        long = long[~long["institute"].isin(["Row_Total"])]
        long["year"] = year
        rows.append(long)
    return pd.concat(rows, ignore_index=True)


def flows_for_field(field: str) -> pd.DataFrame:
    raw = parse_blocks((C.RAW / FIELD_FILES[field]).read_text())
    raw["hei"] = raw["institute"].map(INSTITUTE_TO_HEI)
    kept = raw[raw["hei"].notna()].copy()
    kept["n"] = pd.to_numeric(kept["n"], errors="coerce").fillna(0).astype(int)
    # multi-campus HEIs (TU Dublin) -> sum the campus columns into the institution
    flows = (kept.groupby(["County", "hei", "year"], as_index=False)["n"].sum()
             .rename(columns={"County": "county"}))
    inside = flows[flows["county"].isin(STUDY_COUNTIES)].copy()
    pooled = (inside.groupby(["county", "hei"], as_index=False)["n"].sum()
              .assign(year=POOLED_YEAR))
    out = pd.concat([inside, pooled], ignore_index=True)
    out.insert(0, "field", field)
    dropped = sorted(set(raw.loc[raw["hei"].isna(), "institute"]) - {"Row_Total"})
    return out, dropped


def main() -> None:
    parts, all_dropped = [], {}
    for field in FIELD_FILES:
        out, dropped = flows_for_field(field)
        parts.append(out)
        all_dropped[field] = dropped
        pooled = out[out["year"] == POOLED_YEAR]
        print(f"\n=== {field}  ({FIELD_LABEL[field]}) ===")
        print(f"study-region undergraduate new entrants, pooled 2018/19-2024/25, by HEI:")
        print(pooled.groupby("hei")["n"].sum().sort_values(ascending=False).to_string())
        print(f"total (study region, pooled): {pooled['n'].sum():,}")

    flows = pd.concat(parts, ignore_index=True)
    flows.to_csv(C.OUT / "p4_flows.csv", index=False)
    print(f"\nwrote p4_flows.csv ({len(flows)} rows, {flows['field'].nunique()} fields)")

    print("\npooled study-region totals by field x HEI:")
    piv = (flows[flows.year == POOLED_YEAR]
           .pivot_table(index="hei", columns="field", values="n", aggfunc="sum", fill_value=0))
    print(piv.to_string())
    for f, d in all_dropped.items():
        print(f"\n{f}: institutes outside the modelled set (dropped): {d}")


if __name__ == "__main__":
    main()
