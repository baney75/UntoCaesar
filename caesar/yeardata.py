"""Load one tax year's figures, line rules and citations from caesar/years/<year>.toml."""

from __future__ import annotations

import tomllib
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

YEARS_DIR = Path(__file__).parent / "years"
SUPPORTED_YEARS = (2025,)


class YearData:
    def __init__(self, year: int):
        path = YEARS_DIR / f"{year}.toml"
        with path.open("rb") as f:
            self.raw = tomllib.load(f)
        self.year = year
        self.sources = self.raw["sources"]
        self.figures = self.raw["figures"]
        self.lines = self.raw["lines"]
        self.tax_table = self.figures["tax_table"]["rows"]

    def fig(self, name: str, key: str | None = None):
        entry = self.figures[name]
        value = entry[key] if key else entry
        return Decimal(value) if isinstance(value, str) and _is_number(value) else value

    def citation(self, src: str, at: str) -> dict:
        source = self.sources[src]
        return {"source": source["title"], "url": source["url"], "revision": source["revision"], "at": at}

    def figure_citation(self, name: str) -> dict:
        entry = self.figures[name]
        return self.citation(entry["src"], entry["at"])

    def figure_also(self, name: str) -> list[dict]:
        """Further citations a figure lists under also, beside its main one."""
        return [self.citation(x["src"], x["at"]) for x in self.figures[name].get("also", [])]

    def line_info(self, line_id: str) -> dict:
        """Label, rule and citation for an output line id such as 1040.16 or se-spouse.12."""
        form, line = line_id.split(".", 1)
        key = f"{form.split('-')[0]}.{line}"
        entry = self.lines[key]
        return {"label": entry["label"], "rule": entry["rule"], "citation": self.citation(entry["src"], entry["at"])}


def _is_number(text: str) -> bool:
    try:
        Decimal(text)
    except ArithmeticError:
        return False
    return True


@lru_cache(maxsize=None)
def load(year: int) -> YearData:
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"tax year {year} is not supported; supported: {', '.join(map(str, SUPPORTED_YEARS))}")
    return YearData(year)
