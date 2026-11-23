"""Every figure and line in the year file carries an IRS citation, and the Tax Table is whole."""

import json

import runner

from caesar import yeardata

YEAR = yeardata.load(2025)


def test_every_source_is_an_irs_pdf_with_a_revision():
    for key, source in YEAR.sources.items():
        assert source["url"].startswith("https://www.irs.gov/pub/irs-prior/") and source["url"].endswith("--2025.pdf"), key
        assert source["title"].startswith("2025 ") or "2025" in source["title"], key
        assert source["revision"], key


def test_every_figure_has_a_citation():
    for name, entry in YEAR.figures.items():
        assert entry.get("src") in YEAR.sources, name
        assert entry.get("at"), name
        for more in entry.get("also", []):
            assert more["src"] in YEAR.sources and more["at"], name


def test_every_line_has_a_label_rule_and_citation():
    for key, entry in YEAR.lines.items():
        assert entry["label"] and entry["rule"], key
        assert entry["src"] in YEAR.sources and entry["at"], key


def test_every_line_the_engine_writes_is_in_the_year_file():
    for folder in runner.case_folders():
        want = json.loads((folder / "expected.json").read_text(encoding="utf-8"))
        for line_id in want.get("lines", {}):
            YEAR.line_info(line_id)


def test_tax_table_tiles_zero_to_one_hundred_thousand():
    rows = YEAR.tax_table
    assert rows[0][0] == 0 and rows[-1][1] == 100000
    for before, after in zip(rows, rows[1:]):
        assert before[1] == after[0]


def test_tax_table_matches_the_irs_example():
    # i1040 2025, Tax Table, page 68: married filing jointly, taxable income $25,300, tax $2,562.
    row = next(r for r in YEAR.tax_table if r[0] <= 25300 < r[1])
    assert row[3] == 2562


def test_figures_from_public_law_119_21():
    assert YEAR.fig("standard_deduction", "single") == 15750
    assert YEAR.fig("standard_deduction", "mfj") == 31500
    assert YEAR.fig("standard_deduction", "hoh") == 23625
    assert YEAR.fig("child_tax_credit", "per_child") == 2200
    assert YEAR.fig("senior_deduction", "amount") == 6000
