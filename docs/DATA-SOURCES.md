# Data sources and licences

Checked 2 October 2026 against each publisher's own pages (links below). This is a working record for the release,
not legal advice. "Release" means the public GitHub repository and its Zenodo archive.

## 1. Sources

| Source | File in `data/raw/` | Used for | Licence | Status | Redistribute raw file in release? |
|---|---|---|---|---|---|
| CSO Census 2022 Small Area Population Statistics (SAPS), incl. Theme 15.1 cars and Theme 11 commuting | `cso-saps-2022-20260827.zip` | Population, the 15 to 19 age counts, car availability | CC BY 4.0 | **Confirmed** (CSO: statistics "licensed under Creative Commons Attribution (version 4.0 cc-by). Reproduction is authorised subject to acknowledgement of the source"; data.gov.ie lists SAP2022 tables as CC BY 4.0) | Yes, with attribution |
| Tailte Éireann / CSO Small Area and built-up area boundaries 2022 | `cso-small-areas-2022-20260827.geojson`, `cso-builtup-areas-2022-20260827.geojson` | Area centres, ED and county shapes, census towns | CC BY 4.0 | **Confirmed** (data.gov.ie: published by Tailte Éireann, CC BY 4.0) | Yes, with attribution |
| CSO PxStat F7145 and F7065 (Census 2022: students' journey time and means of travel, by town and by county) | `cso-f7145-2022-20261002.json`, `cso-f7065-2022-20261002.json` | Validation | CC BY 4.0 | **Confirmed** (CSO PxStat statement as above) | Yes, with attribution |
| National Transport Authority GTFS (Transport for Ireland, all operators) | `tfi-gtfs-all-20260827.zip` | Public-transport timetables | CC BY 4.0 | **Confirmed** (data.gov.ie "NTA GTFS": CC BY 4.0, publisher NTA) | **Yes, and recommended**: operators do not keep old timetables online, so the dated snapshot is what makes the travel times reproducible |
| OpenStreetMap (Geofabrik Ireland extract) | `ireland-osm-20260827.osm.pbf` | Street and road network for r5py and OSRM | ODbL 1.0 | **Confirmed**; see section 2 for what it means for the outputs | No (large, freely downloadable by date from Geofabrik's archive; record the checksum) |
| geoBoundaries IRL ADM1 / ADM2 (source: Ordnance Survey Ireland) | `ie-adm1-geoboundaries.geojson`, `ie-adm2-geoboundaries.geojson` | Map outlines | CC BY 4.0 | **Confirmed** (geoBoundaries metadata: boundaryLicense CC BY 4.0, boundarySource Ordnance Survey Ireland) | Yes, with attribution |
| Department of Education post-primary schools (ArcGIS Online "Schools Map", item `e71d0ca28fc54513b9a169dac2ebc28d`, owner `statistics_unit_DOE`, public, updated May 2026) | `doe-postprimary-schools-20260827.geojson` | Schools in the catchment | **Not stated**: the item's licence, access-information and copyright fields are empty, as are the layer's and service's; the gov.ie "Data on Individual Schools" pages (yearly files to 2025/26) state none either. The Department's datasets on data.gov.ie are CC BY 4.0, but only to 2016/17 nationally (2019/20 for Dublin) | **Resolved 2 Oct 2026**: the same school data is CC BY 4.0 through the data.gov.ie record "Data on Individual Schools" (publisher Department of Education, updated 22 Sep 2026), whose resource is the Department's "Data on Individual Schools" collection. The ArcGIS item itself still states nothing | **Superseded 2 Oct 2026**: no longer read by the pipeline. Do not release the snapshot (it carries principals' names and emails) |
| Department of Education, Data on Individual Schools: post-primary, final 2025/26 (October Returns via P-POD, census date 30 Sep 2025, final as of 26 Jun 2026) | `doe-data-on-individual-schools-postprimary-2025-26-20261002.xlsx` | **The schools source since 2 Oct 2026** (script 31): roll number, name, address, Eircode, latitude/longitude, county, ethos, type, Irish classification, gender, fee-paying, DEIS, enrolment by sex and by year group (JC1 to LC2) | CC BY 4.0 | **Confirmed** via the data.gov.ie record above | Yes, with attribution. Drop the principal name, email and phone columns before release (not used, and personal data) |
| Pobal HP Deprivation Index 2022, ED level | `pobal-hp-deprivation-ed-2022-20261002.csv` | Deprivation bands | CC BY 4.0 | **Confirmed** (data.gov.ie, publisher Pobal) | Yes, with attribution |
| HEA "Access Our Data: Students", new entrants by county and institution, eight fields | `hea-*-newentrants-county-institute-*.txt` | Enrolment model | CC BY 4.0 | **Confirmed via data.gov.ie** (checked 2 Oct 2026): the record "HEA Higher Education Student and Graduate Data" (publisher HEA, licence CC BY 4.0, source the Student Record System) has as its resource the HEA page "Data for Download and Visualisations", under which "Access our Data: Students (Enrolments)" sits. The hea.ie pages themselves state no licence. Counts are already rounded to 5 by the HEA | Yes, with attribution; a courtesy note to opendata@hea.ie is optional |
| CAO computing course list with 2025 end-of-season points | `cao-computing-courses-2025-20260827.json` | Course lists in the enrolment county panel | **No open licence found** | Factual, published information; shown in the report in small part | **No**: keep it out of the data release; the report shows a few rows, cited |
| NTA fare determination (January 2027), Irish Rail and operator fares, AA Ireland fuel prices | cited in `scripts/config.py` | Cost model | Published figures | Cited as facts, not redistributed as datasets | n/a |
| SEAI, IPTEM, UK DESNZ conversion factors, EPA per-capita emissions | cited in `scripts/config.py` | Emissions model | Published figures | Cited as facts | n/a |
| Eurostudent VIII (Ireland, 2022) | cited in the report | Share of students living away from home | Published figures | Cited | n/a |

## 2. OpenStreetMap: produced work or derivative database?

The OSM Foundation's test: "If the published result of your project is intended for the extraction of the original
data, then it is a database and not a Produced Work. Otherwise it is a Produced Work." Images, maps and reports are
usually Produced Works. The guideline gives no example for routing results or aggregated values.

- **The report** (the HTML pages, charts and maps) is a **Produced Work**. It needs the attribution
  "© OpenStreetMap contributors" with a link to the licence.
- **The derived tables** (travel times and road distances per area and campus, and anything computed from them: cost,
  emissions, accessibility, the county commute in the enrolment model) are best treated as a **Derivative Database**.
  They are not intended for extracting OSM data, but they are systematic, cell-by-cell outputs of the road network, and
  ODbL 4.6 asks that a Derivative Database used to make a public Produced Work be offered too. Releasing them under
  ODbL 1.0 is the safe course, and it costs nothing: they are being released anyway.

## 3. Proposed licensing for the release

| Part | Licence | Notes |
|---|---|---|
| Code (`scripts/`) | MIT | r5py (MIT), OSRM (BSD-2) and the Python libraries are dependencies, not redistributed |
| Report and documentation (`outputs/*.html`, `docs/`) | CC BY 4.0 | With the OSM attribution and the source list below; stated as individual research and analysis, not an official Maynooth University publication |
| Derived data tables (`outputs/*.csv`, `*.json`) | ODbL 1.0 | Share-alike, because of the OSM-derived travel times. The CC BY 4.0 inputs can be included: CC BY asks only for attribution, which the ODbL release keeps |
| Raw inputs re-shared (GTFS snapshot, census, boundaries, Pobal, CSO tables) | Their own licences (CC BY 4.0) | Each with its attribution line; HEA files only once confirmed; CAO and OSM extract not re-shared |

## 4. Attribution text for the release (README, report footer, Zenodo record)

> Contains Central Statistics Office data (Census 2022), © CSO, CC BY 4.0. Contains Tailte Éireann boundary data,
> CC BY 4.0. Public-transport timetables © National Transport Authority, CC BY 4.0. Map and routing data
> © OpenStreetMap contributors, available under the Open Database Licence (ODbL 1.0). County outlines from
> geoBoundaries (source: Ordnance Survey Ireland), CC BY 4.0. Pobal HP Deprivation Index 2022 (Haase and Pratschke),
> © Pobal, CC BY 4.0. Higher-education entrant counts from the Higher
> Education Authority (Student Record System, via data.gov.ie), CC BY 4.0. School details from the Department of Education, Data on Individual Schools, CC BY 4.0. This is individual research and analysis, not an official Maynooth University publication.

## 5. Actions before release

1. ~~Email opendata@hea.ie~~ HEA terms confirmed through the data.gov.ie record (CC BY 4.0, 2 Oct 2026). A courtesy
   note with the report link is optional.
2. ~~Ask the Department of Education~~ Resolved 2 Oct 2026 through the data.gov.ie "Data on Individual Schools" record
   (CC BY 4.0). No email needed.
3. Add the attribution text to the report footer and the Methods data-sources table.
4. Generate `data/raw/MANIFEST.md`: each raw file with source URL, download date, size and SHA-256.

## Sources

- CSO copyright policy: https://www.cso.ie/en/aboutus/whoweare/copyrightpolicy/
- data.gov.ie, CSO SAP2022 households with cars: https://data.gov.ie/dataset/sap2022t15t1lea22-households-with-cars
- data.gov.ie, Small Areas 2022 (Tailte Éireann): https://data.gov.ie/dataset/cso-small-areas-national-statistical-boundaries-2022-ungeneralised1
- data.gov.ie, NTA GTFS: https://data.gov.ie/en_GB/dataset/nta-gtfs
- OSMF, Produced Work guideline: https://osmfoundation.org/wiki/Licence/Community_Guidelines/Produced_Work_-_Guideline
- OSMF, attribution guidelines: https://osmfoundation.org/wiki/Licence/Attribution_Guidelines
- geoBoundaries API, IRL: https://www.geoboundaries.org/api/current/gbOpen/IRL/ADM1/
- data.gov.ie, Pobal HP Deprivation Index 2022: https://data.gov.ie/dataset/pobal-hp-deprivation-index-scores-2022
- data.gov.ie, Department of Education post-primary schools: https://data.gov.ie/ga/dataset/post-primary-schools
- HEA, open data: https://hea.ie/about-us/open-data-in-the-hea/
- data.gov.ie, Department of Education "Data on Individual Schools" (CC BY 4.0): https://data.gov.ie/dataset/data-on-individual-schools
- Department of Education, post-primary schools enrolment figures: https://www.gov.ie/en/department-of-education/collections/post-primary-schools-enrolment-figures/
- data.gov.ie, HEA Higher Education Student and Graduate Data (CC BY 4.0): https://data.gov.ie/dataset/hea-higher-education-student-and-graduate-data
- HEA, Data for Download and Visualisations (the record's resource; hosts Access our Data): https://hea.ie/statistics/data-for-download-and-visualisations/
