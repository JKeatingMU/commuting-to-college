"""Standalone "Commute and Choice" page (Phase 4a), built from the same section code as the
merged report (scripts/sections/choice.py). Writes outputs/hei-commute-phase4.html.
"""

from __future__ import annotations

import config as C
from sections import choice
from sections.common import standalone


def main() -> None:
    html = standalone(
        choice, "Commute and Choice", "Commuting to College &middot; enrolment",
        "Does accessibility predict where students actually enrol? New-entrant flows from each county "
        "to each HEI, compared with a gravity model, for eight fields of study: Computing, Natural "
        "Sciences, Engineering, Business, Health, Arts and Humanities, Social Sciences and Education, "
        "which between them cover all of Maynooth's teaching.")
    assert "—" not in html, "em dash slipped in"
    (C.OUT / "hei-commute-phase4.html").write_text(html)
    print(f"wrote hei-commute-phase4.html ({len(html)/1024:.0f} KB)")


if __name__ == "__main__":
    main()
