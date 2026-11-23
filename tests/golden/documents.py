"""Write each golden case's documents and scripted answers, for the model-in-the-loop evals.

Test build: synthetic cases only, not for real records.

A case's documents/ folder holds the papers a person would hand over: one text file per W-2,
1099-INT, 1099-DIV, 1099-NEC and out-of-scope form, and a records summary for each Schedule C
business. Every name is made up. Social Security numbers use area 000, which is never issued,
and employer identification numbers use prefix 00, which is not on the IRS list of valid EIN
prefixes ("How EINs are assigned and valid EIN prefixes", irs.gov, read 2026-11-23).

answers.json holds what the scripted person says: for each fact the interview asks, either the
answer itself or the document that holds it. A misread case's W-2 shows the misread value, and
its answers.json carries the true value the person gives when caesar asks again.

Usage: python3 tests/golden/documents.py [--check]   writes (or checks) every case's files.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import to_facts  # noqa: E402

CASES = HERE / "2025"
BANNER = "Test build: synthetic cases only, not for real records."
SSN = "000-00-{:04d}"
EIN = "00-{:07d}"

# The label each fact's value sits after on its document, for the documents and for the eval's
# no-model reader (evals/drivers.py), which fills facts only from what the documents say.
W2_LABELS = {"employer": "c Employer's name", "box1": "1 Wages, tips, other compensation",
             "box2": "2 Federal income tax withheld", "box3": "3 Social security wages",
             "box4": "4 Social security tax withheld", "box5": "5 Medicare wages and tips",
             "box6": "6 Medicare tax withheld", "box7": "7 Social security tips", "box8": "8 Allocated tips",
             "box10": "10 Dependent care benefits", "box12": "12 Codes", "box13_statutory": "13 Statutory employee"}
W2_FIELDS = [("box2", "withholding"), ("box3", "social_security_wages"), ("box4", "social_security_tax"),
             ("box5", "medicare_wages_and_tips"), ("box6", "medicare_tax_withheld"), ("box7", "social_security_tips"),
             ("box8", "allocated_tips"), ("box10", "dependent_care_benefits")]
INT_LABELS = {"payer": "PAYER'S name", "box1": "1 Interest income", "box2": "2 Early withdrawal penalty",
              "box3": "3 Interest on U.S. Savings Bonds and Treasury obligations",
              "box4": "4 Federal income tax withheld", "box8": "8 Tax-exempt interest"}
DIV_LABELS = {"payer": "PAYER'S name", "box1a": "1a Total ordinary dividends", "box1b": "1b Qualified dividends",
              "box2a": "2a Total capital gain distr.", "box4": "4 Federal income tax withheld"}
NEC_LABELS = {"payer": "PAYER'S name", "box1": "1 Nonemployee compensation",
              "box3": "3 Excess golden parachute payments", "box4": "4 Federal income tax withheld"}
BUSINESS_LABELS = {
    "gross_receipts": "Gross receipts for 2025 (all customers, including every 1099-NEC)",
    "returns": "Returns and refunds to customers", "other_income": "Other business income",
    "advertising": "Advertising", "commissions": "Commissions and fees paid", "contract_labor": "Contract labor",
    "employee_benefits": "Employee benefit programs", "insurance": "Insurance (not health)",
    "mortgage_interest": "Mortgage interest, business property", "other_interest": "Other business interest",
    "legal_professional": "Legal and professional services", "office": "Office expense",
    "pension_plans": "Pension and profit-sharing plans", "rent_equipment": "Rent or lease of equipment",
    "rent_other": "Rent of other business property", "repairs": "Repairs and maintenance", "supplies": "Supplies",
    "taxes_licenses": "Taxes and licenses", "travel": "Travel (not meals)", "meals": "Business meals, full cost",
    "utilities": "Utilities", "wages": "Wages paid to employees",
    "business_miles": "Business miles driven (from the mileage log)", "parking_tolls": "Business parking and tolls"}
BUSINESS_FIELDS = [("gross_receipts", "gross_receipts_cash"), ("returns", "returns_allowances"),
                   ("other_income", "other_income"), ("advertising", "advertising"),
                   ("commissions", "commissions_fees"), ("contract_labor", "contract_labor"),
                   ("employee_benefits", "employee_benefit"), ("insurance", "insurance"),
                   ("mortgage_interest", "mortgage_interest"), ("other_interest", "other_interest"),
                   ("legal_professional", "legal_professional"), ("office", "office_expense"),
                   ("pension_plans", "pension_psp"), ("rent_equipment", "machinery_equip_rent"),
                   ("rent_other", "other_rent"), ("repairs", "repairs_maintenance"), ("supplies", "supplies"),
                   ("taxes_licenses", "tax_licenses"), ("travel", "travel"), ("meals", "meal_entertainment"),
                   ("utilities", "utilities"), ("wages", "wages_expense")]


def money(x) -> str:
    return f"{float(x or 0):,.2f}"


def form(title: str, rows: list[tuple[str, str]]) -> str:
    width = max(len(k) for k, _ in rows)
    body = "\n".join(f"{k.ljust(width)}  {v}" for k, v in rows)
    return f"{BANNER}\n\n{title}\n{'=' * len(title)}\n{body}\n"


def documents(case: dict) -> dict[str, str]:
    """{file name: text} for a case, from its input.json."""
    rd = case["input"]["return_data"]
    extra = case.get("untocaesar", {})
    v = to_facts.v
    names = {"taxpayer": "Test Person", "spouse": "Test Spouse"}
    out: dict[str, str] = {}
    n = 0

    def ids():
        nonlocal n
        n += 1
        return SSN.format(n), EIN.format(1000 + n)

    misread = extra.get("misread", {})
    for i, w in enumerate(rd.get("w2") or [], 1):
        ssn, ein = ids()
        who = v(w, "who_applies_to", "taxpayer")
        box1 = misread.get(f"w2.{i}.box1", v(w, "wages", 0))
        box12 = extra.get("w2_box12", {}).get(str(i), "none")
        values = {"employer": v(w, "employer_name", f"employer {i}"), "box1": money(box1),
                  "box12": box12 if box12 != "none" else "(empty)",
                  "box13_statutory": "X" if v(w, "statutory_employee") else "(not checked)"}
        for box, key in W2_FIELDS:
            values[box] = money(v(w, key))
        out[f"w2-{i}.txt"] = form("Form W-2 Wage and Tax Statement 2025", [
            ("a Employee's SSN", ssn), ("b Employer identification number (EIN)", ein),
            (W2_LABELS["employer"], values["employer"]), ("e Employee's name", names[who]),
            *[(W2_LABELS[box], values[box]) for box in W2_LABELS if box != "employer"]])

    sb = rd.get("irs1040_scheduleb") or {}
    for i, x in enumerate(sb.get("irs1099_int") or [], 1):
        ssn, ein = ids()
        out[f"1099-int-{i}.txt"] = form("Form 1099-INT Interest Income 2025", [
            (INT_LABELS["payer"], v(x, "interest_1099int_payer")), ("PAYER'S TIN", ein), ("RECIPIENT'S TIN", ssn),
            (INT_LABELS["box1"], money(v(x, "interest_1099int_interest"))),
            (INT_LABELS["box2"], money(v(x, "interest_1099int_early_withdrawal"))),
            (INT_LABELS["box3"], money(v(x, "interest_1099int_us_saving_bond_treasury_obligations"))),
            (INT_LABELS["box4"], money(v(x, "interest_1099int_fed_inc_tax_withheld"))),
            (INT_LABELS["box8"], money(v(x, "interest_1099int_tax_exempt"))),
        ])
    for i, x in enumerate(sb.get("irs1099_div") or [], 1):
        ssn, ein = ids()
        out[f"1099-div-{i}.txt"] = form("Form 1099-DIV Dividends and Distributions 2025", [
            (DIV_LABELS["payer"], v(x, "dividend_1099div_payer")), ("PAYER'S TIN", ein), ("RECIPIENT'S TIN", ssn),
            (DIV_LABELS["box1a"], money(v(x, "dividend_1099div_ordinary_div"))),
            (DIV_LABELS["box1b"], money(v(x, "dividend_1099div_qualified_div"))),
            (DIV_LABELS["box2a"], money(v(x, "dividend_1099div_capital_gain_distr"))),
            (DIV_LABELS["box4"], money(v(x, "dividend_1099div_federal_inc_tax_withheld"))),
        ])

    nec = 0
    for b, c in enumerate(rd.get("irs1040_schedulec") or [], 1):
        for x in c.get("irs1099_nec") or []:
            nec += 1
            ssn, ein = ids()
            out[f"1099-nec-{nec}.txt"] = form("Form 1099-NEC Nonemployee Compensation 2025", [
                (NEC_LABELS["payer"], x.get("nec_payer_name")), ("PAYER'S TIN", ein), ("RECIPIENT'S TIN", ssn),
                ("RECIPIENT'S name", names[v(c, "who_applies_to", "taxpayer")]),
                (NEC_LABELS["box1"], money(x.get("nec_comp"))),
                (NEC_LABELS["box3"], money(x.get("nec_golden_parachute"))),
                (NEC_LABELS["box4"], money(x.get("nec_fed_wh"))),
            ])
        listed = extra.get("business") or []
        more = listed[b - 1] if b <= len(listed) else {}
        rows = [("Business", v(c, "business_name")), ("Owner", names[v(c, "who_applies_to", "taxpayer")])]
        for key, field in BUSINESS_FIELDS:
            rows.append((BUSINESS_LABELS[key], money(v(c, field, 0))))
        other = c.get("other_expense_detail") or []
        for x in other:
            rows.append((f"Other expense: {x.get('description', 'other')}", money(x.get("amount", x.get("value", 0)))))
        if not other:
            rows.append(("Other expenses", money(0)))
        rows.append((BUSINESS_LABELS["business_miles"], f"{int(more.get('business_miles', 0)):,}"))
        rows.append((BUSINESS_LABELS["parking_tolls"], money(more.get("parking_tolls", 0))))
        out[f"business-{b}-records.txt"] = form(f"2025 business records summary: {v(c, 'business_name')}", rows)

    ssa = (rd.get("ssa_1099") or {}).get("ssa_1099_grp") or []
    for i, x in enumerate(ssa, 1):
        out[f"ssa-1099-{i}.txt"] = form("Form SSA-1099 Social Security Benefit Statement 2025",
                                        [("Box 5 Net benefits for 2025", money(v(x, "ssa_net_benefits")))])
    for i, x in enumerate(rd.get("irs1099_r") or [], 1):
        out[f"1099-r-{i}.txt"] = form("Form 1099-R Distributions From Pensions, Annuities, Retirement Plans 2025", [
            ("1 Gross distribution", money(v(x, "gross_distribution_amt_input"))),
            ("2a Taxable amount", money(v(x, "taxable_amt_input")))])
    for i, x in enumerate((rd.get("irs1040_schedule1") or {}).get("irs1099_g") or [], 1):
        out[f"1099-g-{i}.txt"] = form("Form 1099-G Certain Government Payments 2025", [
            ("PAYER'S name", v(x, "g_payer_name")), ("1 Unemployment compensation", money(v(x, "g_unemployment_comp"))),
            ("4 Federal income tax withheld", money(v(x, "g_fed_wh")))])
    return out


def where(name: str, docs: dict[str, str]) -> str | None:
    """The document that holds a fact, or None when the person answers it."""
    parts = name.split(".")
    prefix = {"w2": "w2", "int1099": "1099-int", "div1099": "1099-div", "nec1099": "1099-nec"}.get(parts[0])
    if prefix and len(parts) == 3 and parts[2] != "owner":
        return f"{prefix}-{parts[1]}.txt"
    if parts[0] == "business" and len(parts) == 3 and parts[2] not in (
            "name", "owner", "material_participation", "all_at_risk", "inventory", "home_office", "vehicle_actual",
            "depreciation"):
        return f"business-{parts[1]}-records.txt"
    return None


def answers(case: dict, docs: dict[str, str]) -> dict:
    """What the scripted person says for each fact: {"say": text} or {"document": file name}."""
    out = {}
    for name, (value, _source) in to_facts.all_facts(case).items():
        doc = where(name, docs)
        out[name] = {"document": doc} if doc in docs else {"say": value}
    truth = to_facts.truth(case)["facts"]
    for name in case.get("untocaesar", {}).get("misread", {}):
        out[name]["correction"] = truth[name]
    return {"test_build": BANNER, "facts": out}


def write(folder: Path, check: bool = False) -> list[str]:
    """Write a case's documents and answers.json, or, with check, list the files that differ."""
    case = to_facts.load(folder)
    docs = documents(case)
    want = {f"documents/{k}": v for k, v in docs.items()}
    want["answers.json"] = json.dumps(answers(case, docs), indent=2) + "\n"
    stale = sorted(str(p.relative_to(folder)) for p in (folder / "documents").glob("*") if
                   f"documents/{p.name}" not in want) if (folder / "documents").exists() else []
    differ = [k for k, text in want.items() if not (folder / k).exists() or (folder / k).read_text(encoding="utf-8") != text]
    if not check:
        (folder / "documents").mkdir(exist_ok=True)
        for k in differ:
            (folder / k).write_text(want[k], encoding="utf-8")
        for k in stale:
            (folder / k).unlink()
    return differ + stale


def main(argv: list[str]) -> int:
    check = "--check" in argv
    bad = {f.name: d for f in sorted(CASES.iterdir()) if (f / "input.json").exists() and (d := write(f, check))}
    for name, files in bad.items():
        print(f"{name}: {'out of date' if check else 'wrote'} {', '.join(files)}")
    return 1 if check and bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
