"""Standalone "Commuting to College: who can reach which campus" page (Phase 3), built from the
same section code as the merged report (scripts/sections/reach.py). Writes
outputs/hei-commute-phase3.html. Needs the p3_* outputs from scripts 20-31.
"""

from __future__ import annotations

import config as C
from sections import reach
from sections.common import standalone


def main() -> None:
    html = standalone(
        reach, "Who Can Reach Which Campus", "Commuting to College &middot; accessibility",
        "How much of the 17 to 19 cohort in 1,197 Electoral Divisions across Leinster (except Wexford) and Monaghan can reach each of 14 "
        "higher-education campuses, by public transport, by public transport with a drive to the train, and by "
        "car, at two times of day. Includes the Maynooth commuter-coach network and the post-primary schools "
        "within each campus's reach.")
    assert "\u2014" not in html, "em dash slipped in"
    (C.OUT / "hei-commute-phase3.html").write_text(html)
    print(f"wrote hei-commute-phase3.html ({len(html)/1e6:.1f} MB)")


if __name__ == "__main__":
    main()
