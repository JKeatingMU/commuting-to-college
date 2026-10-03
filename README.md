# Commuting to College

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23108980.svg)](https://doi.org/10.5281/zenodo.23108980)

**Accessibility, cost, emissions and choice for higher education in Leinster**

> This is individual research and analysis by John G. Keating. It is not an official Maynooth University publication, and it
> does not represent the views or policy of Maynooth University.
> Who made it, why, an interest to declare, how AI assistance was used and how to report errors: [ABOUT.md](ABOUT.md).

How long does the weekday journey to college take from each part of Leinster, by public transport and by car? What
does it cost, what does it emit, who carries the heaviest burden, and does it shape where students enrol? The study
models realistic commutes from 1,197 Electoral Divisions across Leinster (except Wexford) and County Monaghan to 14
higher-education campuses, at two times of day, and compares the result with census journeys and with where new entrants actually went.

- **Read the report:** https://jkeatingmu.github.io/commuting-to-college/
- **Cite it:** see [How to cite](#how-to-cite) and `CITATION.cff`
- **DOI:** [10.5281/zenodo.23108980](https://doi.org/10.5281/zenodo.23108980) (all versions, resolves to the latest);
  version 1.0.0: [10.5281/zenodo.23108981](https://doi.org/10.5281/zenodo.23108981)
- **Version:** 1.0.0 (2026-10-02). Data snapshot 27 August 2026; enrolment data 30 August 2026; fares as from January 2027.

## What is in the report

One page with a landing summary and question-led branches:

| Branch | Question |
|---|---|
| Find your area | Journey time, annual cost and carbon from any area to each campus |
| Who can reach | How much of the college-entry cohort can reach each campus within a given time |
| Cost | What the commute costs a year, by mode |
| Carbon | What the commute emits a year, with adjustable assumptions |
| Who bears it | The commute by area deprivation, for households without a car, and against the SUSI 30 km line |
| Choice | Whether students enrol where the commute is easier, across eight fields of study |
| Worked example: Maynooth | What one institution can do with the data (an illustration, not a plan) |
| Methods and citing | How every number was produced, its limits, the data sources and the version history |

The report measures *potential* accessibility. It cannot say why any individual student chose a college, and the
enrolment model shows a strong association, not proof that the commute causes the choice.

## Repository layout

| Path | Contents |
|---|---|
| `index.html` | The report (a single self-contained file; this is what GitHub Pages serves) |
| `scripts/` | The pipeline, numbered in run order; `config.py` holds every path, date and parameter |
| `scripts/sections/` | The report's sections, one module each |
| `outputs/` | Every derived table behind the report (CSV and JSON) |
| `data/raw/` | The small openly licensed inputs, and `MANIFEST.md` listing every input with its source and checksum |
| `docs/` | Data sources and licences, the cost and emissions model notes, the environment and pinned versions |

## How to reproduce

1. **Software.** Python 3.12 with the packages pinned in `docs/requirements.lock.txt`; OpenJDK 21 (for r5py and
   Conveyal R5); `osmium-tool` and `osrm-backend`. Versions are in `docs/environment.md`.
2. **Inputs.** Download the large inputs listed in `data/raw/MANIFEST.md` (census tables and boundaries, the national
   GTFS timetable, the OpenStreetMap extract) into `data/raw/` with the file names given there, and check them
   against the SHA-256 sums. The small inputs are already in `data/raw/`.
3. **Run.** `./run_pipeline.sh` runs every step from the raw inputs to `outputs/hei-commute.html`. Script
   `19_prepare_inputs` unzips the census tables, extracts the rail stops, crops the road network and builds the
   OSRM car graph; script `22` (r5py public-transport matrices) is the slow one.

Public-transport times depend on the timetable snapshot. Operators do not keep old timetables online, so the exact
GTFS file used (27 August 2026) is archived as its own Zenodo record: [10.5281/zenodo.23121634](https://doi.org/10.5281/zenodo.23121634).

## Data and licences

| Part | Licence |
|---|---|
| Code (`scripts/`, `run_pipeline.sh`) | MIT (`LICENSE`) |
| The report and documentation (`index.html`, `docs/`, this README) | CC BY 4.0 |
| Derived data tables (`outputs/`) | ODbL 1.0, because the travel times are derived from OpenStreetMap |
| Inputs in `data/raw/` | Their publishers' licences, all CC BY 4.0 |

Details and attribution: `DATA-LICENCE.md` and `docs/DATA-SOURCES.md`.

**Attribution.** Contains Central Statistics Office data (Census 2022), © CSO, CC BY 4.0. Contains Tailte Éireann boundary data, CC BY 4.0. Public-transport timetables © National Transport Authority, CC BY 4.0. Map and routing data © OpenStreetMap contributors, available under the Open Database Licence (ODbL 1.0). County outlines from geoBoundaries (source: Ordnance Survey Ireland), CC BY 4.0. Pobal HP Deprivation Index 2022 (Haase and Pratschke), © Pobal, CC BY 4.0. Higher-education entrant counts from the Higher Education Authority (Student Record System, via data.gov.ie), CC BY 4.0. School details from the Department of Education, Data on Individual Schools, CC BY 4.0. This is individual research and analysis, not an official Maynooth University publication.

## How to cite

Keating, J. G. (2026). *Commuting to College: Accessibility, Cost, Emissions and Choice for Higher Education in Leinster* (Version 1.0.0) [Data set and report]. Maynooth University. https://doi.org/10.5281/zenodo.23108981. Individual research and analysis, not an official Maynooth University publication.

## Contact

John G. Keating ([ORCID 0000-0002-5063-2773](https://orcid.org/0000-0002-5063-2773)), john.keating@mu.ie. Corrections and questions are welcome through the repository's issues.
