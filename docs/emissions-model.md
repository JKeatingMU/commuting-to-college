# Commute carbon model - design & decisions

Estimates the **CO2 emissions** of a round-trip commute from an Electoral Division to an HEI
campus, by mode, to sit alongside the travel-time and cost models. Motivation: the car-versus-
public-transport gap in the commute is also a carbon gap, and a distant student who drives
carries a much larger footprint than a Dublin-area one who takes the bus or DART.

Status (September 2026): all 14 campuses, standalone interactive tool.
- Parameters: `scripts/config.py` (carbon block)
- Computation: `scripts/32_emissions_p3.py` -> `outputs/p3_emissions.csv`,
  `outputs/p3_emissions_by_county.csv`
- Report: `scripts/33_emissions_report.py` -> `outputs/hei-commute-emissions.html`
  (campus selector, per-commuter and cohort-scale figures, adjustable factors)

## What is counted

**Operational emissions only** - tank-to-wheel for liquid fuels, plug-to-wheel for electricity.
The model does **not** include:
- fuel supply (extraction, refining, distribution) - roughly +20-25% on petrol/diesel
  well-to-tank, which would widen the car-vs-PT gap
- vehicle manufacture and battery production - front-loaded, and larger per km for EVs
- rail and road infrastructure construction and maintenance

Operational-only is the honest basis for a "would switching mode change my commute footprint"
question and is what SEAI, the IPTEM model and DEFRA report as the headline number. A well-to-
wheel toggle is a candidate for a later version.

## Confirmed design choices

1. **Car basis** - grams CO2 per **vehicle**-kilometre for a **single-occupant** commute, using
   real-world (not lab / WLTP) consumption. This mirrors the cost model's occupancy = 1
   assumption. Lift-sharing is a slider in the tool, not a default.
2. **Public transport basis** - grams CO2 per **passenger**-kilometre at **average load**. A
   scheduled bus or train runs whether or not one more student boards, so its fuel is spread
   over its typical passenger count. This is the standard convention (SEAI, DEFRA). The
   *marginal* emission of one extra passenger on an existing service is near zero; that is a
   different, defensible framing and is noted in the report but not the headline.
3. **Distance** - routed road kilometres (`km_1way` from the OSRM car matrix) for both modes.
   The public-transport route distance is not in the OD data. Rail alignments run a little
   shorter than the road, regional bus routes a little longer; `CO2_PT_DIST_FACTOR = 1.0`
   treats the two as cancelling. This is the largest single approximation in the model.
4. **Commute pattern** - 140 round trips per academic year, the same illustrative figure as the
   cost model. Adjustable.

## Emission factors (grams CO2 per km)

### Car - per vehicle-km, real-world, single occupant

| Powertrain | g CO2 / vehicle-km | Basis |
|---|---|---|
| Petrol (headline) | 180 | Typical Irish petrol car, real-world combined. IPTEM fleet ~120 g/passenger-km at 1.49 occupancy -> ~180 g/vehicle-km. DEFRA "average car" ~170 g/vkm tank-to-wheel. |
| Diesel | 160 | Lower consumption offsets the higher carbon content of the fuel. |
| Full / self-charging hybrid | 120 | ~1/3 below an equivalent petrol car in mixed driving. |
| Plug-in hybrid | 95 | Over a real commute with imperfect charging discipline. |
| Battery electric | grid-dependent | `0.17 kWh/km x grid intensity`. At 240 g CO2/kWh that is **~41 g/vkm**. |

The **Irish grid** was about 234-259 g CO2/kWh in 2023 (SEAI), down from 332 g in 2022, and
lower again in 2024. The tool exposes grid intensity as a slider because it moves the EV and
electric-rail numbers materially and is falling year on year.

### Public transport - per passenger-km, average load

| `fare_type` bucket | Real services | g CO2 / passenger-km | Basis |
|---|---|---|---|
| `zone` | Dublin Bus + DART + Luas mix (Short Hop Zone) | 90 | DEFRA average local bus ~101 g/pkm; blended down by the electric DART / Luas share of a typical Dublin trip. |
| `coach` | JJ Kavanagh UM commuter coaches | 30 | DEFRA coach ~27 g/pkm; intercity coaches run at high load factors. |
| `intercity` | Irish Rail (mostly diesel ICR railcars) | 40 | DEFRA national rail ~35 g/pkm; the Irish network is less electrified than Britain's, so a little higher. IPTEM Irish Rail ~47-53 g/vehicle-km. |

Walking and cycling are zero in this model.

## Calculation

For each origin x campus (peak schedule):

```
car_kg_year = km_1way x 2 x commute_days x car_g_per_vkm / occupancy / 1000
pt_kg_year  = (km_1way x pt_dist_factor) x 2 x commute_days x pt_g_per_pkm[fare_type] / 1000
saving_kg_year = car_kg_year - pt_kg_year
```

Per-day and per-km versions are also written. County figures are cohort-weighted means plus a
cohort-scale total ("if every 17-19 entrant in county C commuted to campus X").

## Sources

- SEAI, *Energy in Ireland 2023 / 2024*, and SEAI transport & CO2 statistics
  (https://www.seai.ie/data-and-insights/seai-statistics/transport,
  https://www.seai.ie/data-and-insights/seai-statistics/co2). New-car CO2 114 g/km (2023);
  grid intensity ~234-259 g CO2/kWh (2023).
- Irish Passenger Transport Emissions and Mobility (IPTEM) model data descriptor,
  *Data in Brief* (https://pmc.ncbi.nlm.nih.gov/articles/PMC9043639/): private-car
  ~120-125 g CO2/passenger-km (tank-to-wheel, SEAI conversion factors), occupancy 1.49; Dublin
  Bus, Bus Eireann, Irish Rail and Luas energy-intensity series.
- UK DEFRA / DESNZ Greenhouse Gas Conversion Factors (2021 / 2024), used as a cross-check for
  the per-passenger-km figures: national rail ~35 g/pkm, local bus ~101 g/pkm, coach ~27 g/pkm.
- EPA Ireland, national greenhouse gas inventory (per-capita context figure).

## Known weaknesses / to revisit

- **PT route distance** is proxied by road distance - the biggest approximation. A proper PT
  distance (from the GTFS shapes or the r5py leg geometry) would tighten every public-transport
  number, especially for rail.
- **Operational only.** Well-to-tank fuel supply (~+20-25% on petrol/diesel) and vehicle/
  battery manufacture are excluded. Including them widens the car-vs-PT gap for ICE cars and
  narrows the EV advantage.
- **Average vs marginal PT load.** The headline uses average load. One extra student on an
  already-scheduled service adds almost nothing; if the study's framing is "what does this
  student's mode choice change tonight", the marginal figure is closer to zero for PT.
- **`zone` blend (90 g/pkm)** is a judgement call about the bus / DART / Luas split of a
  typical Dublin trip. A student who is entirely on the DART is far lower; one entirely on a
  diesel bus is ~101.
- **Coach load factor** assumes the UM coaches run reasonably full; off-peak they will not.
- Car powertrain headline is petrol; the Irish commuting fleet is majority diesel, which is a
  little lower per km. The tool defaults can be changed.
- Consistent with the cost model: no cycling, no accommodation-relocation comparison (a distant
  student who moves to Maynooth for the year has a small local footprint and no commute).
