"""Standalone "What the Commute Emits" page, built from the same section code as the merged
report (scripts/sections/carbon.py). Writes outputs/hei-commute-emissions.html.
Design, factors and sources: docs/emissions-model.md.
"""

from __future__ import annotations

import config as C
from sections import carbon
from sections.common import standalone


def main() -> None:
    html = standalone(
        carbon, "What the Commute Emits", "Commuting to College &middot; carbon",
        "The CO<sub>2</sub> of a year of round-trip commuting, by car and by public transport. The gap "
        "between car and public transport is also a carbon gap, and it widens sharply with distance. "
        "Pick a campus and a home county; move the sliders to change the assumptions.")
    (C.OUT / "hei-commute-emissions.html").write_text(html, encoding="utf-8")
    print(f"wrote hei-commute-emissions.html ({len(html)/1e6:.2f} MB)")


if __name__ == "__main__":
    main()
