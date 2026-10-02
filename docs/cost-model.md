# Commute cost model — design & decisions

Estimates the **financial** cost of a round-trip commute from an Electoral Division to an HEI
campus, by mode, to sit alongside the travel-time model. Motivation: cost may deter enrolment
more than time does, especially for lower-income students a long way from Maynooth.

Status (4 Sep 2026): **all 14 campuses**, standalone interactive report. Public-transport fares
updated to the **NTA determination for January 2027** (announced 3 Sep 2026; see the PT section).
Not wired into the main Phase 3 accessibility report.
- Parameters: `scripts/config.py` (cost block)
- Computation: `scripts/29_costs_p3.py` → `outputs/p3_cost.csv`, `outputs/p3_cost_by_county.csv`,
  `outputs/p3_cost_mu.png`
- Report: `scripts/30_cost_report.py` → `outputs/hei-commute-cost.html` ("What the Commute Costs" —
  campus dropdown, cost-vs-distance scatter, by-county table, dark/light toggle). PT dots are
  coloured by `fare_type` (zone / coach / intercity); a "Case Study" section explains why the PT
  points form flat bands rather than one line.

`p3_cost.csv` carries a `fare_type` column: **zone** (flat Dublin 90-min fare + caps),
**coach** (flat JJ Kavanagh season ticket, MU only), **intercity** (distance-scaled). Only the
last rises with distance — hence the multi-band PT scatter for MU/Dublin campuses and the single
clean line for the regional campuses (no zone, no coach).

## Confirmed decisions (John, 27 Aug 2026)

1. **Car cost basis** — headline = **marginal cost** (fuel + campus parking + tolls); the family
   car is assumed to exist already. Full running cost (Revenue civil-service per-km rate) reported
   as a secondary figure.
2. **PT fare basis** — **per-trip Student / Young-Adult Leap fare with the weekly cap applied**.
   This is the honest upper bound. Monthly / annual / TaxSaver tickets are cheaper per commute
   day and are noted as a caveat, not modelled.
3. **Scope** — prototype **MU only** first, see whether the numbers tell a story, then decide
   whether to wire cost through the whole report (map colour option, ED table, side panel).

## Parameters (August 2026 snapshot — assumptions, revise freely)

### Car — fuel cost = routed road km × consumption × pump price
| Parameter | Value | Basis |
|---|---|---|
| Petrol | €1.84 / litre | **AA Ireland** monthly fuel survey, August 2026 |
| Diesel | €1.92 / litre | AA Ireland, August 2026 (excise restoration adds ~10c from Sept — caveat) |
| Consumption, petrol | 6.7 L / 100 km (≈ 42 mpg) | Typical car, real-world combined |
| Consumption, diesel | 5.3 L / 100 km (≈ 53 mpg) | Typical car, real-world combined |
| → fuel cost, **petrol (headline)** | **€0.123 / km** | derived |
| → fuel cost, diesel | €0.102 / km | derived — the two fuel types are within ~20% |
| Full running cost | €0.40 / km | Revenue civil-service motoring rate, mid-range engine — *secondary figure only* |
| Distances | OSRM routed road km, Phase 3 OSM graph | `annotations=distance` |
| Occupancy | 1 (no lift-sharing) | Caveat — rural lift-sharing is real and unmodelled |

Fuel is reported as its own line (`car_fuel_day`). Marginal ("all-in") car cost adds campus
student parking (per-campus `CAMPUS_PARKING_EUR`, assumption — MU €2, regional €1, Dublin €3–25
"if available") and a motorway toll by a crude region rule:
| Campus group | Toll rule | Basis |
|---|---|---|
| Dublin campuses | M50 €3.50 × 2 for EDs > 18 km from the GPO and not in Dublin City | dominant Dublin-bound toll |
| Maynooth | M4 €2.90 × 2 for EDs at lon < −6.95 **and** lat > 53.20 | M4-corridor band (Kinnegad/Mullingar/Longford/Athlone) |
| Dundalk IT | M1 €2.10 × 2 for EDs south of lat 53.90 | M1 Gormanston |
| TUS Athlone | M4 €2.90 × 2 for EDs east of lon −7.55, north of lat 53.05 | M4/M6 from the Dublin side |
| SETU Carlow | none | M9 / M7 toll-free |
Full running cost (`car_full_day`) replaces fuel with a €0.40/km Revenue rate — CSV only.

### Public transport — Student / Young-Adult Leap, whole 17–19 cohort
YA/Student Leap = ~50% off adult fares across the TFI network (Dublin Bus, Irish Rail, DART,
Luas, Bus Éireann).

**Fare basis updated to the January 2027 NTA determination** (announced 3 September 2026; RTÉ,
NTA press release). First broad PSO fare adjustment since 2018; adult fares up ~15% on average;
the 50% YA / Student discount is retained. Confirmed figure: YA / Student Dublin 90-minute Leap
**€1.00 → €1.15** (adult €2.00 → €2.30). The caps and the regional / Irish Rail figures below are
the pre-2027 values scaled by the announced 15%, pending the full NTA fare table. `config.py`
carries a `FARE_YEAR = 2027` marker and the prior values in comments.

| Parameter | 2027 value | Prior (2022–2026) | Basis |
|---|---|---|---|
| Dublin 90-minute fare | **€1.15** | €1.00 | NTA determination, Jan 2027 — **confirmed** |
| Daily cap (Dublin zone) | €3.45 | €3.00 | +15% estimate, pending full table |
| Weekly cap (Dublin zone) | €13.80 | €12.00 | +15% estimate, pending full table |
| Fares per direction, in-zone | 1 if modelled trip ≤ 90 min, else 2 | — | 90-min fare covers transfers |
| **Regional daily round-trip cost** (outside DSHZ) | **€4.60 + €0.060 × gc_km** per day | €4.00 + €0.052 × gc_km | The Aug-2026 fit (YA weekly rail season ÷ 5, calibrated to Carlow / Portlaoise / Athlone) scaled by 15%. Intercity tickets bundle a Dublin city add-on → no separate local leg. Floor = local town-bus round trip (2 × the 90-min fare). |
| Off-peak / annual TaxSaver | not modelled | — | Would lower the regional figure a little further |

**Aug 2026 recalibration (kept):** the earlier regional model computed `2 × YA single` and was
~2× too high — a daily commuter buys a weekly/monthly season, not two singles a day. Re-checking
against the Irish Rail fares calculator (Carlow, Portlaoise, Athlone) fixed this; the model
matched published YA weekly seasons within ~5–10% before the 15% uplift.

**Effect of the Jan-2027 uplift:** the border/midland PT-to-MU figure rises from ~€1,000–1,300/yr
to ~€1,150–1,500/yr. Because the increase is close to uniform it does not change the *shape* of
cost against distance, so the Phase-4a finding (cost tracks distance at r = 0.97 and adds nothing
as a separate friction) is unaffected. Commercial coach operators (JJ Kavanagh etc.) are not PSO
and not bound by the determination, so `COACH_WEEKLY_EUR` is unchanged; car fuel and tolls are
still the Aug-2026 snapshot.

### PT + drive-to-rail
Computed (`pt_rail_day`) but **≡ plain PT everywhere**: you still pay essentially the whole rail
fare, and the feeder drive + park-and-ride only add cost. Drive-to-rail buys *time*, not *money*,
so the interactive report folds it into the public-transport line and explains why.

### Maynooth commuter coach (UM02–UM15)
| Parameter | Value | Basis |
|---|---|---|
| Student weekly ticket | €35 (→ **€7.00 / day** round trip) | JJ Kavanagh: Maynooth student weekly "from ~€30" (Carlow ~€40). YA/Student Leap also accepted. Term/academic tickets may be cheaper — confirm at tickets.jjkavanagh.ie |
| Coach catchment | ED within 15 km of a weekday UM route's first boarding town, **or** within 10 km of any pickup stop along it (stops from `p3_coach_routes.json`; Sunday-only UM04/UM15 excluded) | proxy for "can use the coach". Was board towns only until Oct 2026, which missed the corridor towns (Tullamore, Kinnegad, Navan, Newbridge, Arklow, ...) |
| Applied as | `min(regional PT cost, coach)` for MU trips from those EDs | the coach is a cost option as well as a time option |

### Short Hop Zone proxy
In-zone if county ∈ {Dublin City, Dún Laoghaire-Rathdown, Fingal, South Dublin, Kildare} **and** within 45 km
straight-line of the GPO. Coarse — the true DSHZ boundary is a specific station list.

### Roll-ups
Reported per day, per week (5 round trips, PT weekly-capped), and per academic year
(140 round trips — illustrative full-time commuting pattern).

## Result — cost to Maynooth (peak, population-weighted €/day round trip; Jan-2027 PT fares)
| County | car fuel only | car all-in | PT (Leap/coach) | PT ≈ €/yr |
|---|---|---|---|---|
| Dublin | 7.5 | 9.5 | 3.0 | 410 |
| Kildare | 6.6 | 8.8 | 3.7 | 515 |
| Meath | 10.2 | 12.5 | 6.3 | 885 |
| Louth / Laois / Wicklow / Carlow | 16–21 | 18–23 | 7.1–7.6 | ~985–1,065 |
| Offaly / Westmeath | 18–21 | 26–27 | 7.3–8.1 | ~1,020–1,135 |
| Longford / Monaghan | 24–32 | 32–37 | 9.7–9.8 | ~1,350–1,370 |
| Kilkenny | 30.0 | 32.0 | 10.6 | 1,485 |

A border/midland student pays **≈ €1,000–1,500/yr** by public transport (a rail season, or the
JJ Kavanagh coach) vs ~**€410–505/yr** for a Dublin-area student — but **€3,400–4,500/yr in fuel
alone** if they drive, and more with parking and tolls. The car is where the real cost gradient
sits — a clear case for lift-sharing. The same pattern holds for every campus — see
`hei-commute-cost.html`. Figures are the January 2027 NTA fares for public transport; car fuel
and tolls remain the August 2026 snapshot.

## Known weaknesses / to revisit
- Regional PT: now the **YA weekly rail season ÷ 5**, validated against the Irish Rail fares
  calculator (Carlow/Portlaoise/Athlone, Aug 2026) — within ~5–10%. Bus Éireann-only corridors
  (no rail) not separately checked.
- **MU parking**: John says MU has a **flat annual student parking permit**, but not everyone
  gets a space. Current model uses €2/day for all MU car trips — revisit with the real permit
  price ÷ commute-days, and consider modelling "space not guaranteed".
- Other campus parking figures are guesses; Dublin campuses are really permit-limited, not
  pay-per-day.
- Coach price is a weekly-ticket figure; JJ Kavanagh term/academic tickets may be cheaper.
- Off-peak / annual TaxSaver would lower the regional PT figure a little further.
- Diesel vs petrol: model uses petrol; diesel is ~17% cheaper per km (cheaper fuel-per-km
  despite dearer diesel, because of lower consumption).
- No lift-sharing, no cycling, no accommodation-cost comparison (the real alternative for a
  distant student is rent for the year vs commute cost × ~140 days).
- PT fares are the NTA determination for January 2027 (announced 3 Sep 2026); car fuel and tolls
  are an August-2026 snapshot and excise restoration raises fuel further from Sept 2026.

## Change log
- **2 Oct 2026.** (1) Dún Laoghaire-Rathdown was never in the zone proxy: `DSHZ_COUNTIES` spelt it
  `DUN LAOGHAIRE/RATHDOWN`, the data `Dún Laoghaire-Rathdown`. DLR origins were charged the regional
  fare to every Dublin-side campus (e.g. UCD €4.89 → €2.32/day; MU €894 → €482/yr). (2) Coach
  catchment widened from board towns to every pickup stop (see above): MU coach-fare EDs 170 → 280;
  Westmeath 5 → 27, Offaly 24 → 55, Wicklow 3 → 29, Meath 8 → 19, Louth 25 → 37. Longford stays 0:
  no UM route serves it, its students take the Sligo-line train. Emissions (32/33) rerun: DLR PT
  now uses the Dublin-mix factor, MU PT 710 → 739 kg/yr.
- **2 Oct 2026 (later).** Area weights now come from 15 to 17 year olds rescaled to the 17 to 19 total, because
  the census counts third-level students at their term-time address (the report's Methods, "Travel times and population",
  explains the correction). Cohort-weighted county figures above moved by a few euro; MU car CO2 2,452 → 2,536 kg/yr, PT 739 → 744.
