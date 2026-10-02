"""Standalone "What the Commute Costs" page, built from the same section code as the merged
report (scripts/sections/cost.py). Writes outputs/hei-commute-cost.html.
Design + assumptions: docs/cost-model.md.
"""

from __future__ import annotations

import config as C
from sections import cost
from sections.common import standalone


def main() -> None:
    html = standalone(
        cost, "What the Commute Costs", "Commuting to College &middot; cost",
        "What a year of commuting costs: student and Young Adult public-transport fares, the Maynooth "
        "commuter coaches, or car fuel, parking and tolls. Pick a campus; every dot is one of 1,197 "
        "Electoral Divisions. Cost may deter enrolment as much as time does, especially for "
        "lower-income students a long way from campus.")
    (C.OUT / "hei-commute-cost.html").write_text(html)
    print(f"wrote hei-commute-cost.html ({len(html)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
