"""Shared configuration for the HEI commute-accessibility MVP.

Every path, date and parameter the pipeline depends on lives here so a run is
fully described by this file plus the dated feeds in data/raw/.
"""

from __future__ import annotations

import datetime as _dt
from pathlib import Path

# --- paths -----------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
PROC = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
DOCS = ROOT / "docs"
for _d in (PROC, OUT):
    _d.mkdir(parents=True, exist_ok=True)

# Dated input snapshots (archived, never overwritten)
SNAPSHOT = "20260827"
OSM_RAW = RAW / f"ireland-osm-{SNAPSHOT}.osm.pbf"
GTFS_RAW = RAW / f"tfi-gtfs-all-{SNAPSHOT}.zip"
OSM_CLIP = PROC / f"study-area-{SNAPSHOT}.osm.pbf"

# Phase 2 — CSO Census 2022
BUA_GEOJSON = RAW / f"cso-builtup-areas-2022-{SNAPSHOT}.geojson"
SA_GEOJSON = RAW / f"cso-small-areas-2022-{SNAPSHOT}.geojson"
SAPS_BUA = PROC / "saps" / "SAPS_2022_BUA_270923.csv"
SAPS_SA = PROC / "saps" / "SAPS_2022_Small_Area_UR_171024.csv"

# Phase 2 origin unit: Electoral Divisions in the study counties (pop-weighted centroids).
P2_SA_COUNTIES = ["DUBLIN CITY", "DUN LAOGHAIRE/RATHDOWN", "FINGAL", "SOUTH DUBLIN",
                  "KILDARE", "MEATH", "WICKLOW"]
ED_POP_FLOOR = 100       # drop near-empty (non-residential) EDs
COHORT_AGES = (17, 18, 19)  # college-entry cohort: sets the regional total of the weights
# The census counts third-level students at their TERM-TIME address, so the 18-19 counts pile up
# beside campuses (Rathfarnham 724 aged 18-19 vs 99 aged 15-16). Each ED's weight is therefore its
# 15-17 year olds, who still live at home, rescaled so the regional total equals the 17-19 total.
# Corrected 2 Oct 2026; the report's Methods explains why.
COHORT_PROXY_AGES = (15, 16, 17)

# --- study area ----------------------------------------------------------
# Generous bounding box around all origins + campuses + routing slack.
# (west, south, east, north) in WGS84 degrees.
BBOX = (-7.10, 52.75, -5.85, 53.85)

# --- analysis time -----------------------------------------------------------
# A normal term Wednesday, inside the GTFS validity window (2026-08-26..2027-08-26).
ANALYSIS_DATE = _dt.date(2026, 10, 7)
assert ANALYSIS_DATE.weekday() == 2, "ANALYSIS_DATE must be a Wednesday"

# Morning: arrive on campus around 08:30 -> sample departures in this window.
AM_DEPART = _dt.datetime.combine(ANALYSIS_DATE, _dt.time(7, 30))
# Evening: leave campus around 18:30 -> sample departures in this window.
PM_DEPART = _dt.datetime.combine(ANALYSIS_DATE, _dt.time(18, 0))
DEPART_WINDOW_MIN = 60  # minutes; median over departures in [t, t+window]

# Travel-time percentiles to record (median is the headline).
PERCENTILES = [25, 50, 75]

# Walking / access parameters
MAX_WALK_MIN = 30           # max walk to first stop / from last stop
WALK_SPEED_KMH = 4.5
MAX_TRIP_MIN = 240          # cap; anything above counts as "not reachable"

# Drive-to-rail layer
PARKING_BUFFER_MIN = 6      # park + walk to platform
MAX_DRIVE_TO_STATION_MIN = 40   # applied AFTER the peak factor
# The drive leg here is local access to a commuter/rail station (mostly regional roads
# away from the M50 core), not a cross-city drive. R5 car time is free-flow; a flat 1.3x
# covers peak friction on that kind of route. A cross-city car commute (not modelled)
# would be far slower - see METHODS.
CAR_PEAK_FACTOR = 1.3

# HEI groupings for population-weighted accessibility
UNIVERSITIES = {"MU", "DCU", "UCD", "TCD", "TU Dublin", "TUS", "SETU"}
REGIONAL_HEIS = {"TUS", "DkIT", "SETU"}
ACCESS_THRESHOLDS = [30, 45, 60, 75, 90]  # minutes, one-way (morning)

# ---- Phase 3: regional expansion, car mode, two schedules ----
OSM_CLIP_P3 = PROC / f"study-area-p3-{SNAPSHOT}.osm.pbf"   # bbox -8.35,52.25,-5.85,54.45
BBOX_P3 = (-8.35, 52.25, -5.85, 54.45)

P3_SA_COUNTIES = P2_SA_COUNTIES + [
    "WESTMEATH", "LONGFORD", "OFFALY", "LAOIS", "LOUTH", "MONAGHAN", "CARLOW", "KILKENNY"]

import datetime as _dt3
# Two arrival/departure schedules. Each: (AM depart window start, PM depart window start).
SCHEDULES = {
    "peak": {"am": _dt3.datetime.combine(ANALYSIS_DATE, _dt3.time(7, 30)),
             "pm": _dt3.datetime.combine(ANALYSIS_DATE, _dt3.time(18, 0)),
             "label": "arrive ~08:30 / leave ~18:30"},
    "late": {"am": _dt3.datetime.combine(ANALYSIS_DATE, _dt3.time(9, 0)),
             "pm": _dt3.datetime.combine(ANALYSIS_DATE, _dt3.time(16, 30)),
             "label": "arrive ~10:00 / leave ~17:00"},
}

# Car congestion uplift on R5 free-flow time: (schedule, leg) -> {dublin_bound, regional}
CAR_FACTOR = {
    ("peak", "am"): {"dublin": 1.50, "regional": 1.20},
    ("peak", "pm"): {"dublin": 1.45, "regional": 1.18},
    ("late", "am"): {"dublin": 1.25, "regional": 1.10},   # AM shoulder, ~09:00-10:00
    ("late", "pm"): {"dublin": 1.45, "regional": 1.18},   # 17:00 is still evening peak
}
DUBLIN_BOUND_INSTITUTIONS = {
    "DCU", "UCD", "TCD", "TU Dublin", "Marino", "NCAD", "RCSI", "IADT"}
# MU, TUS, SETU, DkIT, Carlow College -> "regional" (approached mostly from outside the M50)

# Car search radius - beyond this a car commute is treated as "not reachable".
# Kept tight because a wide radius makes R5's per-origin car Dijkstra explore the
# whole 15-county network (the Phase 3 slowdown).
CAR_MAX_MIN = 120

# Accessibility thresholds (minutes, one-way)
THRESHOLDS = [60, 90, 120]

# Java (Homebrew keg-only openjdk@21)
JAVA_HOME = "/opt/homebrew/opt/openjdk@21"

# ---- Phase 3 cost model (financial cost of the round-trip commute) ----
# Every figure here is a documented mid-2026-snapshot assumption. Rationale, sources and
# the confirmed design decisions are in docs/cost-model.md. Prototype scope = MU only.

# CAR - fuel cost = routed road km x consumption x pump price.
# Pump prices: AA Ireland monthly survey, August 2026 (petrol EUR1.84, diesel EUR1.92).
# Consumption: typical real-world combined - petrol ~6.7 L/100km (~42 mpg),
#              diesel ~5.3 L/100km (~53 mpg).
FUEL = {
    "petrol": {"eur_per_litre": 1.84, "litre_per_100km": 6.7},
    "diesel": {"eur_per_litre": 1.92, "litre_per_100km": 5.3},
}
FUEL_TYPE = "petrol"            # headline assumption; "diesel" is close (see below)
FUEL_EUR_PER_KM = FUEL[FUEL_TYPE]["eur_per_litre"] * FUEL[FUEL_TYPE]["litre_per_100km"] / 100
# petrol ~= 0.123 EUR/km, diesel ~= 0.102 EUR/km, blended ~= 0.113

# CAR - full running cost (secondary figure): Revenue civil-service motoring rate, mid-range
CAR_FULL_EUR_PER_KM  = 0.40

# Campus student parking, EUR/day (assumption). Dublin campuses are permit-limited, so the
# figure is "if a space is available at all". Only MU is used in the prototype.
CAMPUS_PARKING_EUR = {
    "mu_maynooth": 2.0, "dkit_dundalk": 1.0, "tus_athlone": 1.0, "setu_carlow": 1.0,
    "tud_blanchardstown": 3.0, "tud_tallaght": 3.0, "iadt": 4.0,
    "dcu_glasnevin": 6.0, "ucd_belfield": 6.0, "marino": 10.0,
    "tud_grangegorman": 15.0, "tcd_college_green": 25.0, "ncad": 25.0, "rcsi": 25.0,
}

# Tolls, EUR per pass (video / unregistered rate). The eFlow M4 toll plaza sits WEST of
# Maynooth, so an MU commute pays it only when approached along the M4 from the midlands.
TOLL_M4_EUR  = 2.90     # eFlow M4 (Kilcock-Enfield / Enfield-Kinnegad)
TOLL_M50_EUR = 3.50     # M50 eFlow, unregistered
TOLL_M1_EUR  = 2.10     # M1 Gormanston (Drogheda-Dublin)
# Crude M4-corridor test for an MU trip: EDs in the Kinnegad / Mullingar / Longford / Athlone
# band feed Maynooth along the M4 and pass the toll plaza each way.
MU_M4_TOLL_MAX_LON = -6.95
MU_M4_TOLL_MIN_LAT = 53.20
# Dublin-bound campus: EDs this far (straight line) from the GPO and not in the city pay the M50.
M50_TOLL_MIN_GPO_KM = 18

# PUBLIC TRANSPORT - Student / Young-Adult Leap Card assumed for the whole cohort ---------
# YA/Student Leap = ~50% off adult singles across the TFI network, with PAYG fare caps.
#
# FARES: NTA fare determination for JANUARY 2027, announced 3 September 2026 (RTE, NTA press
# release) - the first broad PSO fare adjustment since 2018. Adult fares up ~15% on average;
# the 50% Young-Adult / Student discount is retained. Confirmed figure: YA/Student Dublin
# 90-minute Leap EUR1.00 -> EUR1.15 (adult EUR2.00 -> EUR2.30). The daily/weekly caps and the
# regional/Irish Rail figures below are the pre-2027 values scaled by the announced 15%
# average, pending the full NTA fare table. Prior (2022-2026) values kept in comments.
FARE_YEAR          = 2027
LEAP_90MIN_EUR     = 1.15       # was 1.00 (2022-2026); announced Jan-2027 figure
LEAP_DAILY_CAP_EUR = 3.45       # was 3.00; +15% est.
LEAP_WEEKLY_CAP_EUR = 13.80     # was 12.00; +15% est.
# Regional (outside the DSHZ) daily ROUND-TRIP public-transport cost, EUR/day.
# Calibrated (Aug 2026) to the Irish Rail fares calculator, YA/Student Leap:
#   YA single ~= EUR4.16 + EUR0.055/gc_km ; daily RT (weekly season / 5) ~= 4.0 + 0.052*gc.
# Scaled by the announced 15% for Jan 2027: ~= 4.60 + 0.060*gc  (was 4.0 + 0.052*gc).
REGIONAL_DAILY_BASE   = 4.60    # was 4.0
REGIONAL_DAILY_PER_KM = 0.060   # was 0.052

# Maynooth commuter coach (UM routes). JJ Kavanagh Maynooth student weekly ticket "from ~EUR30"
# (Carlow ~EUR40) -> ~EUR6-8/day round trip. YA/Student Leap also accepted.
# NOTE: the commercial coach operators (JJ Kavanagh etc.) are NOT PSO and are not bound by the
# NTA fare determination; left unchanged here, though they typically raise fares in tandem.
COACH_WEEKLY_EUR   = 35.0      # representative UM-route student weekly ticket
COACH_EUR_PER_DAY  = COACH_WEEKLY_EUR / 5   # = 7.0, round trip
COACH_CATCHMENT_KM = 15       # an ED within this of a UM route's first boarding town can use the coach
COACH_STOP_KM      = 10       # ...or within this of any pickup stop along a weekday UM route

# Park-and-ride: many Irish Rail commuter car parks are free; the busier ones ~EUR4/day.
PARK_AND_RIDE_EUR = 3.0       # per day, added to the PT + drive-to-rail cost

# Short Hop Zone proxy: in-zone if in one of these counties AND within DSHZ_MAX_KM_FROM_GPO
# straight-line of Dublin city centre (GPO).
DSHZ_COUNTIES = {"DUBLIN CITY", "DÚN LAOGHAIRE-RATHDOWN", "FINGAL", "SOUTH DUBLIN", "KILDARE"}
DSHZ_MAX_KM_FROM_GPO = 45
GPO_LATLON = (53.3498, -6.2603)

# Roll-ups
COMMUTE_DAYS_PER_WEEK = 5
COMMUTE_DAYS_PER_YEAR = 140    # illustrative full-time commuting pattern

# ============================================================================
# COMMUTE CARBON MODEL  (added Sep 2026 - see docs/emissions-model.md)
# ============================================================================
# Operational CO2 only: tank-to-wheel for fuels, plug-to-wheel for electricity.
# Fuel-supply / vehicle-manufacture / infrastructure emissions are excluded, and
# noted as a caveat. Everything here is adjustable in the report tool.
# Sources: SEAI "Energy in Ireland"; the Irish Passenger Transport Emissions &
# Mobility (IPTEM) model; UK DEFRA/DESNZ GHG conversion factors as a cross-check.
CO2_YEAR = 2026

# CAR - grams CO2 per VEHICLE-km, single-occupant commute, real-world driving.
# Irish fleet real-world average is ~170-185 g/vkm (IPTEM ~120 g/passenger-km at
# 1.49 occupancy). Official new-car figure (114 g/km, SEAI 2023) is a lab number
# and understates real-world driving by 20-40%.
CO2_CAR_G_PER_VKM = {
    "petrol": 180.0,   # typical Irish petrol car, real-world combined
    "diesel": 160.0,   # lower consumption offsets higher carbon content per litre
    "hybrid": 120.0,   # full / self-charging hybrid
    "phev":    95.0,   # plug-in hybrid over a mixed charge-and-fuel commute
    "ev":      41.0,   # recomputed below from grid intensity x consumption
}
CO2_CAR_TYPE = "petrol"         # headline; fleet ~ 55% diesel / 38% petrol / rest hybrid+EV
CO2_CAR_OCCUPANCY = 1.0         # a commute is one person per car (matches the cost model)

CO2_EV_KWH_PER_KM = 0.17       # real-world consumption including charging losses
CO2_GRID_G_PER_KWH = 240.0    # SEAI: Irish grid 2023 ~234-259 g/kWh, still falling
CO2_CAR_G_PER_VKM["ev"] = round(CO2_EV_KWH_PER_KM * CO2_GRID_G_PER_KWH, 1)

# PUBLIC TRANSPORT - grams CO2 per PASSENGER-km, keyed to the fare_type bucket in
# p3_cost.csv. Average-load allocation (a bus running anyway spreads its fuel over
# its typical passenger count) - the standard convention.
CO2_PT_G_PER_PKM = {
    "zone":      90.0,   # Dublin mix: Dublin Bus (diesel/hybrid) + DART / Luas (electric)
    "coach":     30.0,   # intercity coach at a high load factor (DEFRA coach ~27)
    "intercity": 40.0,   # Irish Rail, mostly diesel ICR railcars (DEFRA national rail ~35)
}
# PT route distance is not in the OD data; routed road km is the proxy. Rail runs
# a little shorter than the road, regional bus a little longer - roughly cancels.
CO2_PT_DIST_FACTOR = 1.0

CO2_COMMUTE_DAYS = COMMUTE_DAYS_PER_YEAR   # 140, same illustrative pattern as the cost model

# Context anchors used by the report
CO2_PERSON_ANNUAL_T = 11.0     # Ireland per-capita territorial emissions, tonnes (EPA)
CO2_TREE_KG_PER_YEAR = 21.0    # rough sequestration of one mature broadleaf, kg/yr
