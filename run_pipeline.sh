#!/usr/bin/env bash
# The full pipeline behind the published report, from the dated raw downloads in data/raw/
# (see data/raw/MANIFEST.md) to outputs/hei-commute.html. Script 22 (r5py) is the slow step.
set -euo pipefail
cd "$(dirname "$0")"
source .venv/bin/activate
export JAVA_HOME=${JAVA_HOME:-/opt/homebrew/opt/openjdk@21}
export PATH="$JAVA_HOME/bin:$PATH"
cd scripts
for s in 19_prepare_inputs 20_origins_p3 21_campuses_p3 22_matrices_p3 23_car_osrm_p3 25_combine_p3 \
         26_accessibility_p3 28_coach_routes_p3 29_costs_p3 31_schools_p3 32_emissions_p3 34_burden_p3 \
         35_validation_p3 40_hea_flows 41_county_accessibility 42_gravity_model 44_cost_friction \
         50_merged_report; do
  echo "=== $s ==="; python "$s.py"
done
