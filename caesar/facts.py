"""The interview: which facts caesar knows, the question for each, and how facts are stored.

v0's scope is an allowlist. caesar rejects a fact this module does not list, and any answer
that puts the return outside v0 is a refusal. Facts live in <job>/facts.toml, each with a
value, where it came from (a document and box, or the person's answer) and whether the
person confirmed it. Only caesar confirm writes the confirmation (see confirm.py).
"""

from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

STATUSES = ("single", "mfj", "mfs", "hoh", "qss")
STATUS_NAMES = {
    "single": "single",
    "mfj": "married filing jointly",
    "mfs": "married filing separately",
    "hoh": "head of household",
    "qss": "qualifying surviving spouse",
}
# W-2 box 12 codes v0 accepts: amounts already left out of or included in box 1 that need no
# other form or line in v0. Any other code (W for HSA, Q for combat pay, A, B, M, N for
# uncollected tax, and so on) is a refusal.
BOX12_OK = {"C", "D", "E", "F", "G", "J", "S", "AA", "BB", "DD", "EE"}
TEXT_LIMIT = 200


@dataclass(frozen=True)
class Spec:
    name: str
    kind: str  # status, yesno, money, number, count, owner, codes, text
    question: str
    refuse: str = ""  # what is out of scope when the answer triggers a refusal
    refuse_on: str = "yes"  # for yesno facts, the answer that triggers it


# Documents. The interview opens with these, modeled on the knockout questions in IRS
# Direct File. Any yes is a refusal.
DOCUMENT_SCREENS = [
    ("screen.ssa1099", "Form SSA-1099 or RRB-1099 (Social Security or railroad retirement benefits)", "Social Security benefits (Form SSA-1099)"),
    ("screen.1099r", "Form 1099-R (a pension, annuity, IRA, 401(k) or other retirement distribution)", "retirement distributions (Form 1099-R)"),
    ("screen.1099g", "Form 1099-G (unemployment compensation or a state or local tax refund)", "unemployment compensation and state tax refunds (Form 1099-G)"),
    ("screen.1099b", "Form 1099-B or 1099-DA (sales of stocks, funds, crypto or other assets)", "capital gains or losses (Form 1099-B, Schedule D)"),
    ("screen.1099k", "Form 1099-K (payment card or payment app transactions)", "Form 1099-K"),
    ("screen.1098e", "Form 1098-E (student loan interest)", "the student loan interest deduction (Form 1098-E)"),
    ("screen.1098t", "Form 1098-T (college tuition)", "education credits and tuition (Form 1098-T, Form 8863)"),
    ("screen.1095a", "Form 1095-A (Marketplace health insurance)", "the premium tax credit (Form 1095-A, Form 8962)"),
    ("screen.5498sa", "Form 5498-SA or 1099-SA (a health savings account)", "health savings accounts (Form 8889)"),
    ("screen.k1", "a Schedule K-1 (from a partnership, S corporation, estate or trust)", "Schedule K-1 income"),
    ("screen.other_forms", "any other tax form besides Forms W-2, 1099-INT, 1099-DIV and 1099-NEC (for example 1099-MISC, W-2G, 1099-S, 1099-C, 1099-Q or 1098)",
     "documents caesar has no rule for"),
]

# Elective items no form shows, and other situations. Any yes is a refusal.
SITUATION_SCREENS = [
    ("screen.educator_expenses", "Were you (or your spouse) a teacher or other educator who wants to deduct classroom expenses?",
     "the educator expense deduction"),
    ("screen.ira_contributions", "Did you (or your spouse) put money into a traditional IRA for 2025 that you want to deduct?",
     "the IRA deduction"),
    ("screen.student_loan_interest", "Did you (or your spouse) pay interest on a student loan in 2025?",
     "the student loan interest deduction"),
    ("screen.tuition", "Did you pay tuition or other college or job-training costs in 2025 for yourself, your spouse or a dependent?",
     "education credits and tuition (Form 8863)"),
    ("screen.hsa_contributions", "Did you (or your spouse) put money into a health savings account (HSA) for 2025, other than through payroll?",
     "health savings accounts (Form 8889)"),
    ("screen.claimed_as_dependent", "Can anyone claim you (or your spouse) as a dependent on their 2025 return?",
     "a filer who can be claimed as a dependent"),
    ("screen.itemize", "Do you want to itemize deductions (Schedule A) instead of taking the standard deduction?",
     "itemized deductions (Schedule A)"),
    ("screen.sold_property", "In 2025, did you sell, trade or give away stocks, funds, crypto or other digital assets, a home or other property, even with no form?",
     "capital gains or losses (Schedule D, Form 8949)"),
    ("screen.rental_royalty", "Did you have rental or royalty income?", "rental or royalty income (Schedule E)"),
    ("screen.foreign", "Did you have income from outside the U.S., or a bank or financial account in another country?",
     "foreign income or foreign accounts"),
    ("screen.other_income", "Did you have any income besides W-2 wages, 1099-INT interest, 1099-DIV dividends and self-employment income? For example alimony, gambling winnings, jury duty pay, prizes, cash tips not on a W-2, or a canceled debt.",
     "income other than wages, interest, ordinary dividends and self-employment"),
    ("screen.other_adjustments", "Do you want to deduct self-employed health insurance, a SEP, SIMPLE or other self-employed retirement plan, an early withdrawal penalty, alimony paid, moving expenses for the military, or any other adjustment to income?",
     "adjustments to income other than half of self-employment tax"),
    ("screen.other_credits", "Do you want to claim any credit other than the child tax credit or credit for other dependents, such as the child and dependent care credit, the earned income credit, a retirement savings credit, an energy or vehicle credit, or the adoption credit?",
     "credits other than the child tax credit and the credit for other dependents"),
    ("screen.household_employee", "Did you pay a household employee, such as a nanny or housekeeper, $2,800 or more?",
     "household employment taxes (Schedule H)"),
    ("screen.new_deductions", "Did you get tips or overtime pay you want to deduct, or pay interest on a loan for a new car you want to deduct?",
     "the 2025 deductions for qualified tips, qualified overtime and car loan interest (Schedule 1-A, Parts II to IV)"),
    ("screen.other_taxes", "Do you owe any other tax, such as tax on an IRA or HSA, household employment tax, repayment of a credit, or tax on tips not reported to your employer?",
     "Schedule 2 taxes other than self-employment tax"),
    ("screen.net_operating_loss", "Do you have a net operating loss from an earlier year to carry forward?", "net operating losses"),
    ("screen.qbi_loss_carryforward", "Do you have a qualified business loss carryforward from 2024 (Form 8995, line 16 of last year's return)?",
     "a qualified business loss carryforward"),
    ("screen.state_return", "Do you want caesar to prepare a state or local return too?",
     "state and local returns (caesar prepares only the federal Form 1040)"),
]

# The relationship, age and residency tests for an EIC qualifying child, from Pub 596 (2025),
# Rule 8, pages 10 and 11, and the 2025 Form 1040 instructions, EIC Step 3, page 41. The joint
# return test and "younger than you" are left out, so the count can only be too high, which only
# makes the EIC screen refuse more often.
EIC_CHILDREN_QUESTION = (
    "How many children lived with you in the United States for more than half of 2025 and are your son, daughter,"
    " stepchild, foster child, brother, sister, half brother, half sister, stepbrother, stepsister, or a descendant"
    " of one of them (such as a grandchild, niece or nephew), and at the end of 2025 were under 19, or under 24 and"
    " a full-time student, or any age and permanently and totally disabled? Count every such child, even one you do"
    " not list as a dependent or who paid more than half of their own support. (0 if none)")

PERSON_QUESTIONS = [
    ("born_before_1961", "Was {who} born before January 2, 1961?"),
    ("blind", "Is {who} blind (see the Form 1040 instructions for line 12d)?"),
    ("ssn_valid_for_work", "Does {who} have a Social Security number valid for work, issued before the return's due date?"),
]

# (fact, kind, question, what is out of scope when it has an amount or a yes)
W2_BOXES = [
    ("employer", "text", "employer name (box c)", ""),
    ("box1", "money", "box 1, wages, tips, other compensation", ""),
    ("box2", "money", "box 2, federal income tax withheld", ""),
    ("box3", "money", "box 3, social security wages", ""),
    ("box4", "money", "box 4, social security tax withheld", ""),
    ("box5", "money", "box 5, Medicare wages and tips", ""),
    ("box6", "money", "box 6, Medicare tax withheld", ""),
    ("box7", "money", "box 7, social security tips (0 if empty)", ""),
    ("box8", "money", "box 8, allocated tips (0 if empty)", "allocated tips (W-2 box 8, Form 4137)"),
    ("box10", "money", "box 10, dependent care benefits (0 if empty)", "dependent care benefits (W-2 box 10, Form 2441)"),
    ("box12", "codes", "box 12 codes, letters only, comma separated (for example D,DD), or none", ""),
    ("box13_statutory", "yesno", "box 13, is the Statutory employee box checked?", "statutory employee income (W-2 box 13)"),
]

INT_BOXES = [
    ("payer", "text", "payer's name", ""),
    ("box1", "money", "box 1, interest income", ""),
    ("box3", "money", "box 3, interest on U.S. savings bonds and Treasury obligations (0 if empty)", ""),
    ("box4", "money", "box 4, federal income tax withheld (0 if empty)", ""),
    ("box8", "money", "box 8, tax-exempt interest (0 if empty)", ""),
    ("other_boxes", "yesno", "is there any amount in box 2, 5, 6, 7, 9, 10, 11, 12, 13 or 15?",
     "Form 1099-INT boxes other than 1, 3, 4 and 8"),
]

DIV_BOXES = [
    ("payer", "text", "payer's name", ""),
    ("box1a", "money", "box 1a, total ordinary dividends", ""),
    ("box1b", "money", "box 1b, qualified dividends (0 if empty)",
     "qualified dividends (they need the Qualified Dividends and Capital Gain Tax Worksheet)"),
    ("box4", "money", "box 4, federal income tax withheld (0 if empty)", ""),
    ("other_boxes", "yesno", "is there any amount in box 2a to 2f, 3, 5, 6, 7, 9, 10, 12, 13 or 16?",
     "Form 1099-DIV boxes other than 1a, 1b and 4 (for example capital gain distributions or section 199A dividends)"),
]

NEC_BOXES = [
    ("payer", "text", "payer's name", ""),
    ("box1", "money", "box 1, nonemployee compensation", ""),
    ("box3", "money", "box 3, excess golden parachute payments (0 if empty)", "excess golden parachute payments (1099-NEC box 3)"),
    ("box4", "money", "box 4, federal income tax withheld (0 if empty)", ""),
]

# (fact, question, answer that refuses, what is out of scope)
BUSINESS_SCREENS = [
    ("material_participation", "Did {who} materially participate in this business in 2025 (work in it regularly, continuously and substantially)?",
     "no", "a business in which the owner did not materially participate (Form 8582)"),
    ("all_at_risk", "Is all of the money {who} put into this business at risk (paid by {who}, not borrowed without personal liability)?",
     "no", "a business with amounts not at risk (Form 6198)"),
    ("inventory", "Does this business sell products from inventory, or have cost of goods sold?",
     "yes", "inventory and cost of goods sold (Schedule C Part III)"),
    ("home_office", "Do you want to deduct business use of your home (home office)?", "yes",
     "the home office deduction (Form 8829 or the simplified method)"),
    ("vehicle_actual", "For a car or truck used in this business, do you want to deduct actual expenses (gas, repairs, depreciation, lease payments) instead of the standard mileage rate?",
     "yes", "actual vehicle expenses"),
    ("depreciation", "Do you want to deduct depreciation, section 179 expense, depletion, or the energy efficient buildings deduction for this business?",
     "yes", "depreciation, section 179, depletion and the section 179D deduction (Form 4562)"),
]

# (fact, Schedule C line, question). Every amount is the business's 2025 total.
BUSINESS_AMOUNTS = [
    ("gross_receipts", "1", "gross receipts or sales, including every Form 1099-NEC box 1 for this business"),
    ("returns", "2", "returns and allowances (0 if none)"),
    ("other_income", "6", "other business income not in gross receipts (0 if none)"),
    ("advertising", "8", "advertising"),
    ("business_miles", "9", "business miles driven (a number of miles, not dollars; 0 if none)"),
    ("parking_tolls", "9", "business parking fees and tolls"),
    ("commissions", "10", "commissions and fees paid"),
    ("contract_labor", "11", "contract labor paid"),
    ("employee_benefits", "14", "employee benefit programs"),
    ("insurance", "15", "insurance other than health insurance"),
    ("mortgage_interest", "16a", "mortgage interest paid to banks for business property"),
    ("other_interest", "16b", "other business interest"),
    ("legal_professional", "17", "legal and professional services"),
    ("office", "18", "office expense"),
    ("pension_plans", "19", "contributions to employee pension and profit-sharing plans"),
    ("rent_equipment", "20a", "rent or lease of machinery and equipment"),
    ("rent_other", "20b", "rent of other business property"),
    ("repairs", "21", "repairs and maintenance"),
    ("supplies", "22", "supplies"),
    ("taxes_licenses", "23", "taxes and licenses"),
    ("travel", "24a", "business travel (not meals)"),
    ("meals", "24b", "the full cost of business meals (caesar deducts 50 percent)"),
    ("utilities", "25", "utilities"),
    ("wages", "26", "wages paid to employees"),
    ("other_expenses", "27b", "other business expenses not listed above"),
]


def who(person: str) -> str:
    return "you" if person == "taxpayer" else "your spouse"


def specs(facts: dict) -> list[Spec]:
    """Every fact the interview needs, in order, given the facts known so far."""
    out = []
    for name, form, what in DOCUMENT_SCREENS:
        out.append(Spec(name, "yesno", f"For 2025, did you (or your spouse) get {form}?", what))
    for name, question, what in SITUATION_SCREENS:
        out.append(Spec(name, "yesno", question, what))

    out.append(Spec("filing_status", "status",
                    "What is your 2025 filing status: single, mfj (married filing jointly), mfs (married filing separately), hoh (head of household) or qss (qualifying surviving spouse)?"))
    status = value(facts, "filing_status")
    joint = status == "mfj"
    for key, question in PERSON_QUESTIONS:
        out.append(Spec(f"taxpayer.{key}", "yesno", question.format(who=who("taxpayer"))))
    if joint:
        for key, question in PERSON_QUESTIONS:
            out.append(Spec(f"spouse.{key}", "yesno", question.format(who=who("spouse"))))
    if status == "mfs":
        out.append(Spec("spouse.itemizes", "yesno", "Will your spouse itemize deductions on their separate return?",
                        "a married filing separately return when the spouse itemizes"))
        out.append(Spec("spouse.no_income_not_filing", "yesno",
                        "Did your spouse have no income, not file a return, and not be anyone's dependent in 2025?",
                        "the spouse boxes on a married filing separately return"))

    out.append(Spec("dependents.count", "count", "How many dependents will you list on your return? (0 if none)"))
    for i in range(1, count(facts, "dependents.count") + 1):
        d = f"dependent.{i}"
        out.append(Spec(f"{d}.qualifying_child", "yesno",
                        f"Dependent {i}: is this person your qualifying child (your son, daughter, stepchild, foster child, brother, sister or a descendant of one of them, who lived with you more than half of 2025)?"))
        if value(facts, f"{d}.qualifying_child") == "yes":
            out.append(Spec(f"{d}.under_17", "yesno", f"Dependent {i}: was this child under age 17 at the end of 2025 (born after December 31, 2008)?"))
        out.append(Spec(f"{d}.ssn_valid_for_work", "yesno", f"Dependent {i}: does this person have a Social Security number valid for work, issued before the return's due date?"))
        if value(facts, f"{d}.ssn_valid_for_work") == "no":
            out.append(Spec(f"{d}.has_tin", "yesno", f"Dependent {i}: does this person have an ITIN or ATIN issued before the return's due date?"))
        out.append(Spec(f"{d}.us_person", "yesno", f"Dependent {i}: is this person a U.S. citizen, U.S. national or U.S. resident alien?"))

    # A qualifying child for the EIC need not be a dependent: Pub 596 (2025), Rule 8, has no support
    # test, so this is asked of everyone (see checks.eic_may_apply).
    out.append(Spec("eic.children", "count", EIC_CHILDREN_QUESTION))

    out.append(Spec("w2.count", "count", "How many Forms W-2 did you (and your spouse, on a joint return) get for 2025? (0 if none)"))
    for i in range(1, count(facts, "w2.count") + 1):
        if joint:
            out.append(Spec(f"w2.{i}.owner", "owner", f"W-2 number {i}: whose W-2 is it, taxpayer or spouse?"))
        for box, kind, question, refuse in W2_BOXES:
            out.append(Spec(f"w2.{i}.{box}", kind, f"W-2 number {i}: {question}", refuse))

    out.append(Spec("int1099.count", "count", "How many Forms 1099-INT did you get for 2025? (0 if none)"))
    for i in range(1, count(facts, "int1099.count") + 1):
        for box, kind, question, refuse in INT_BOXES:
            out.append(Spec(f"int1099.{i}.{box}", kind, f"1099-INT number {i}: {question}", refuse))

    out.append(Spec("div1099.count", "count", "How many Forms 1099-DIV did you get for 2025? (0 if none)"))
    for i in range(1, count(facts, "div1099.count") + 1):
        for box, kind, question, refuse in DIV_BOXES:
            out.append(Spec(f"div1099.{i}.{box}", kind, f"1099-DIV number {i}: {question}", refuse))

    out.append(Spec("nec1099.count", "count", "How many Forms 1099-NEC did you get for 2025? (0 if none)"))
    for i in range(1, count(facts, "nec1099.count") + 1):
        if joint:
            out.append(Spec(f"nec1099.{i}.owner", "owner", f"1099-NEC number {i}: whose is it, taxpayer or spouse?"))
        for box, kind, question, refuse in NEC_BOXES:
            out.append(Spec(f"nec1099.{i}.{box}", kind, f"1099-NEC number {i}: {question}", refuse))

    out.append(Spec("business.count", "count",
                    "How many self-employment businesses (Schedule C) do you have? Count freelance or gig work as a business. (0 if none)"))
    for i in range(1, count(facts, "business.count") + 1):
        b = f"business.{i}"
        out.append(Spec(f"{b}.name", "text", f"Business {i}: what is the business's name, or what does it do?"))
        if joint:
            out.append(Spec(f"{b}.owner", "owner", f"Business {i}: who owns it, taxpayer or spouse?"))
        owner = value(facts, f"{b}.owner") or "taxpayer"
        for key, question, refuse_on, what in BUSINESS_SCREENS:
            out.append(Spec(f"{b}.{key}", "yesno", f"Business {i}: {question.format(who=who(owner))}", what, refuse_on))
        for key, line, question in BUSINESS_AMOUNTS:
            kind = "number" if key == "business_miles" else "money"
            out.append(Spec(f"{b}.{key}", kind, f"Business {i}, Schedule C line {line}: {question}"))

    out.append(Spec("payments.estimated", "money",
                    "How much did you pay in 2025 estimated tax payments, plus any 2024 refund you applied to 2025? (0 if none)"))
    return out


def refusal(spec: Spec, val: str) -> str:
    """The out-of-scope item this answer triggers, or "" if none."""
    if spec.kind == "codes":
        bad = [c for c in val.split(",") if c not in BOX12_OK] if val != "none" else []
        return f"W-2 box 12 code {', '.join(bad)}" if bad else ""
    if not spec.refuse:
        return ""
    if spec.kind == "yesno":
        return spec.refuse if val == spec.refuse_on else ""
    if spec.kind == "money":
        return spec.refuse if val.strip("0.") else ""
    return ""


def normalize(kind: str, raw: str) -> str:
    """Check and normalize a value. Raises ValueError with a plain message."""
    text = raw.strip()
    low = text.lower()
    if kind == "status":
        aliases = {"married filing jointly": "mfj", "married filing separately": "mfs", "head of household": "hoh",
                   "qualifying surviving spouse": "qss"}
        low = aliases.get(low, low)
        if low not in STATUSES:
            raise ValueError("use one of: single, mfj, mfs, hoh, qss")
        return low
    if kind == "yesno":
        if low in ("yes", "y"):
            return "yes"
        if low in ("no", "n"):
            return "no"
        raise ValueError("answer yes or no")
    if kind == "owner":
        if low in ("taxpayer", "you", "me"):
            return "taxpayer"
        if low == "spouse":
            return "spouse"
        raise ValueError("answer taxpayer or spouse")
    if kind == "count":
        if not re.fullmatch(r"\d{1,2}", text):
            raise ValueError("give a whole number from 0 to 99")
        return str(int(text))
    if kind == "codes":
        if low in ("none", "0", ""):
            return "none"
        codes = [c.strip().upper() for c in text.split(",") if c.strip()]
        if not all(re.fullmatch(r"[A-Z]{1,2}", c) for c in codes):
            raise ValueError("give box 12 letter codes separated by commas, or none")
        return ",".join(codes)
    if kind == "text":
        if not text or len(text) > TEXT_LIMIT:
            raise ValueError(f"give between 1 and {TEXT_LIMIT} characters")
        if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in text):
            raise ValueError("use one line with no control characters")
        return text
    if kind in ("money", "number"):
        cleaned = text.replace("$", "").replace(",", "")
        match = re.fullmatch(r"(\d{1,12})(?:\.(\d{1,2}))?", cleaned)
        if not match:
            raise ValueError("give zero or a positive amount such as 52000 or 52000.50, with at most two decimal places")
        return f"{int(match[1])}.{(match[2] or '').ljust(2, '0')}"
    raise ValueError(f"unknown kind {kind}")


def value(facts: dict, name: str) -> str | None:
    entry = facts.get(name)
    return entry["value"] if entry else None


def count(facts: dict, name: str) -> int:
    v = value(facts, name)
    return int(v) if v is not None else 0


def spec_for(facts: dict, name: str) -> Spec | None:
    return next((s for s in specs(facts) if s.name == name), None)


def missing(facts: dict) -> list[Spec]:
    return [s for s in specs(facts) if s.name not in facts]


def unknown(facts: dict) -> list[str]:
    """Stored facts the interview no longer asks for, for example after a count went down."""
    known = {s.name for s in specs(facts)}
    return [name for name in facts if name not in known]


def refusals(facts: dict) -> list[str]:
    """Out-of-scope items from the answers so far, in interview order."""
    found = []
    for spec in specs(facts):
        if spec.name in facts:
            what = refusal(spec, facts[spec.name]["value"])
            if what and what not in found:
                found.append(what)
    return found


# ---------------------------------------------------------------------------
# facts.toml
# ---------------------------------------------------------------------------

# confirmed is "" (not yet), "yes" or "no" (the person rejected the value). by names who answered.
def load(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("rb") as f:
        data = tomllib.load(f)
    return {name: {"value": str(e["value"]), "source": str(e.get("source", "")),
                   "confirmed": str(e.get("confirmed", "")), "by": str(e.get("by", ""))}
            for name, e in data.get("facts", {}).items()}


def save(path: Path, facts: dict, year: int) -> None:
    lines = [f"# UntoCaesar facts for tax year {year}. Written by caesar: change a fact with caesar set.",
             "# Test build: synthetic cases only, not for real records.",
             f"year = {year}", ""]
    for name in sorted(facts, key=sort_key):
        e = facts[name]
        lines += [f"[facts.{quote(name)}]", f"value = {quote(e['value'])}", f"source = {quote(e['source'])}",
                  f"confirmed = {quote(e['confirmed'])}", f"by = {quote(e['by'])}", ""]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("\n".join(lines), encoding="utf-8")
    tmp.replace(path)


def sort_key(name: str):
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in name.split(".")]


def quote(text: str) -> str:
    out = ['"']
    for ch in text:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append(f"\\u{ord(ch):04x}")
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)
