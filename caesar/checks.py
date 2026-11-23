"""caesar check: refusals, consistency checks and confirmations.

A refusal means the return is outside v0 and caesar stops. A failure means a fact needs
fixing. Every refusal and failure has a plain message and, where it rests on a figure, the
year file citation for that figure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from . import facts as F
from .engine import Return, dependents, indexes, money, owner_of, whole
from .yeardata import YearData


@dataclass
class Finding:
    message: str
    fact: str = ""  # the fact to fix, when there is one
    citation: dict | None = None


@dataclass
class Report:
    refusals: list[Finding] = field(default_factory=list)
    failures: list[Finding] = field(default_factory=list)
    unconfirmed: list[str] = field(default_factory=list)
    rejected: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.refusals and not self.failures


def fact_refusals(facts: dict) -> list[Finding]:
    """Refusals that follow from the answers alone, before any math."""
    out = [Finding(f"caesar v0 does not handle {what}.") for what in F.refusals(facts)]
    status = F.value(facts, "filing_status")
    deps = indexes(facts, "dependents.count")
    filers = ["taxpayer"] + (["spouse"] if status == "mfj" else [])
    for i in deps:
        d = f"dependent.{i}"
        if F.value(facts, f"{d}.us_person") == "no":
            out.append(Finding(f"caesar v0 does not handle dependent {i}, who is not a U.S. citizen, national or resident.", f"{d}.us_person"))
        if F.value(facts, f"{d}.ssn_valid_for_work") == "no" and F.value(facts, f"{d}.has_tin") == "no":
            out.append(Finding(f"Dependent {i} has no SSN, ITIN or ATIN, and caesar v0 does not handle a dependent without one.", f"{d}.has_tin"))
    if deps and any(F.value(facts, f"{p}.ssn_valid_for_work") == "no" for p in filers):
        out.append(Finding("caesar v0 does not handle the child tax credit identification rules for a filer without a Social Security number valid for work."))
    owners = [owner_of(facts, f"business.{i}") for i in indexes(facts, "business.count")]
    if len(owners) != len(set(owners)):
        out.append(Finding("caesar v0 handles one Schedule C per person; more than one business for the same person is outside v0."))
    return out


def run(facts: dict, ret: Return | None, year: YearData) -> Report:
    report = Report()
    report.refusals = fact_refusals(facts)
    for spec in F.missing(facts):
        report.failures.append(Finding(f"No answer yet for {spec.name}: {spec.question}", spec.name))
    for name in F.unknown(facts):
        report.failures.append(Finding(f"{name} is not a fact caesar v0 knows.", name))
    for name, entry in facts.items():
        if entry["confirmed"] == "no":
            report.rejected.append(name)
            report.failures.append(Finding(
                f"The person said {name} = {entry['value']} (source: {entry['source']}) is wrong. Read the document again and set the right value.", name))
        elif entry["confirmed"] != "yes":
            report.unconfirmed.append(name)
    if report.refusals or ret is None:
        return report

    consistency(facts, report)
    detectors(facts, ret, year, report)
    return report


def consistency(facts: dict, report: Report) -> None:
    for i in indexes(facts, "w2.count"):
        w = f"w2.{i}"
        if money(facts, f"{w}.box2") > money(facts, f"{w}.box1"):
            report.failures.append(Finding(
                f"W-2 number {i}: federal income tax withheld (box 2) is more than wages (box 1). Check both boxes.", f"{w}.box2"))
    status = F.value(facts, "filing_status")
    owners = ["taxpayer"] + (["spouse"] if status == "mfj" else [])
    for owner in owners:
        necs = [f"nec1099.{i}" for i in indexes(facts, "nec1099.count") if owner_of(facts, f"nec1099.{i}") == owner]
        businesses = [f"business.{i}" for i in indexes(facts, "business.count") if owner_of(facts, f"business.{i}") == owner]
        nec_total = sum((money(facts, f"{n}.box1") for n in necs), Decimal(0))
        receipts = sum((money(facts, f"{b}.gross_receipts") for b in businesses), Decimal(0))
        whose = "your" if owner == "taxpayer" else "your spouse's"
        if necs and not businesses:
            report.failures.append(Finding(
                f"There is a Form 1099-NEC for {whose} work but no Schedule C business. Nonemployee compensation goes on Schedule C: add the business.", "business.count"))
        elif nec_total > receipts:
            report.failures.append(Finding(
                f"{whose.capitalize()} Forms 1099-NEC add up to ${nec_total:,.2f}, more than Schedule C gross receipts of ${receipts:,.2f}. Gross receipts must include every 1099-NEC box 1.",
                f"{businesses[0]}.gross_receipts"))


def detectors(facts: dict, ret: Return, year: YearData, report: Report) -> None:
    """Refusals that need the computed return: the forms v0 would have to add."""
    status = F.value(facts, "filing_status")
    line = ret.get
    joint = status == "mfj"
    filers = ["taxpayer"] + (["spouse"] if joint else [])
    w2s = [f"w2.{i}" for i in indexes(facts, "w2.count")]

    # Schedule C loss.
    for c in [x[:-3] for x in ret.lines if x.startswith("schc-") and x.endswith(".31")]:
        if line(f"{c}.31") < 0:
            report.refusals.append(Finding("caesar v0 does not handle a Schedule C loss.", "",
                                           year.line_info(f"{c}.31")["citation"]))

    # Schedule B.
    limit = year.fig("schedule_b_threshold", "amount")
    if line("1040.2b") > limit or line("1040.3b") > limit:
        report.refusals.append(Finding(
            f"Taxable interest or ordinary dividends over ${limit:,} need Schedule B, which caesar v0 does not handle.", "",
            year.figure_citation("schedule_b_threshold")))

    # Form 8995-A.
    if "8995.11" in ret.lines and line("8995.11") > year.fig("qbi_threshold", status):
        report.refusals.append(Finding(
            "Taxable income before the qualified business income deduction is over the Form 8995 limit, so Form 8995-A is needed, which caesar v0 does not handle.",
            "", year.figure_citation("qbi_threshold")))

    # Additional Medicare Tax, Form 8959.
    medicare = sum((money(facts, f"{w}.box5") for w in w2s), Decimal(0))
    medicare += sum((Decimal(line(f"se-{p}.6")) for p in filers), Decimal(0))
    one_employer = max((money(facts, f"{w}.box5") for w in w2s), default=Decimal(0))
    if medicare > year.fig("additional_medicare_screen", status) or one_employer > year.fig("additional_medicare_screen", "employer_withholding_wages"):
        report.refusals.append(Finding(
            "Medicare wages and self-employment income are over the Additional Medicare Tax threshold, so Form 8959 is needed, which caesar v0 does not handle.",
            "", year.figure_citation("additional_medicare_screen")))

    # Net investment income tax, Form 8960.
    if line("1040.11b") > year.fig("niit_screen", status) and line("1040.2b") + line("1040.3b") > 0:
        report.refusals.append(Finding(
            "Income is over the net investment income tax threshold and there is interest or dividend income, so Form 8960 may be needed, which caesar v0 does not handle.",
            "", year.figure_citation("niit_screen")))

    # Excess social security tax, Schedule 3 line 11.
    cap = Decimal(year.fig("excess_social_security", "amount"))
    for p in filers:
        mine = [w for w in w2s if owner_of(facts, w) == p]
        if sum((money(facts, f"{w}.box4") for w in mine), Decimal(0)) > cap:
            report.refusals.append(Finding(
                "Social security tax withheld is more than the most one person can owe, so the excess goes on Schedule 3, line 11, which caesar v0 does not handle.",
                "", year.figure_citation("excess_social_security")))
            break

    # Alternative minimum tax, Form 6251. AMTI here is line 11b minus line 13a (no Schedule A,
    # and the standard deduction and Schedule 1-A deduction are added back). Tentative minimum
    # tax is figured at the 26 and 28 percent rates without Part III, which can only lower it,
    # so if even this is not above line 16, Form 6251 cannot show AMT.
    amti = Decimal(line("1040.11b") - line("1040.13a"))
    exemption = Decimal(year.fig("amt_screen", "exemption")[status])
    start = Decimal(year.fig("amt_screen", "phaseout_start")[status])
    exemption = max(Decimal(0), exemption - max(Decimal(0), amti - start) * year.fig("amt_screen", "phaseout_rate"))
    base = max(Decimal(0), amti - exemption)
    top = Decimal(year.fig("amt_screen", "low_rate_top")[status])
    if base <= top:
        tmt = base * year.fig("amt_screen", "low_rate")
    else:
        tmt = base * year.fig("amt_screen", "high_rate") - Decimal(year.fig("amt_screen", "high_rate_subtract")[status])
    if whole(tmt) > line("1040.16"):
        report.refusals.append(Finding(
            "The alternative minimum tax screen says Form 6251 may be needed, which caesar v0 does not handle.", "",
            year.figure_citation("amt_screen")))

    # Earned income credit.
    if eic_may_apply(facts, ret, year):
        report.refusals.append(Finding(
            "You may qualify for the earned income credit. caesar v0 cannot claim it, and a return without it could cost you the credit, so caesar stops here.",
            "", year.figure_citation("eic_screen")))


def eic_may_apply(facts: dict, ret: Return, year: YearData) -> bool:
    """True when the facts pass the income and SSN tests of the EIC steps in the 1040 instructions.

    caesar does not hold birth dates, so it does not apply the Step 4 age test (25 to 64 with
    no qualifying child) and refuses whenever the other tests pass. A qualifying child for the
    EIC need not be a dependent: it meets the relationship, age, residency and joint return
    tests, with no support test (Pub 596 (2025), Rule 8, pages 10 and 11; i1040 2025, EIC
    Step 3, page 41). So the number of children is the larger of the eic.children answer and
    the dependents who are qualifying children with a valid SSN. A larger count only raises the
    income limit, so the screen errs toward refusing.
    """
    status = F.value(facts, "filing_status")
    filers = ["taxpayer"] + (["spouse"] if status == "mfj" else [])
    if any(F.value(facts, f"{p}.ssn_valid_for_work") != "yes" for p in filers):
        return False
    dependents_counted = sum(1 for i in indexes(facts, "dependents.count")
                             if F.value(facts, f"dependent.{i}.qualifying_child") == "yes"
                             and F.value(facts, f"dependent.{i}.ssn_valid_for_work") == "yes")
    children = max(dependents_counted, F.count(facts, "eic.children"))
    limits = year.fig("eic_screen", "agi_limit_mfj" if status == "mfj" else "agi_limit_other")
    limit = limits[min(children, 3)]
    earned = ret.get("1040.1z") + sum(ret.get(x) for x in ret.lines if x.startswith("schc-") and x.endswith(".31")) - ret.get("s1.15")
    investment = ret.get("1040.2a") + ret.get("1040.2b") + ret.get("1040.3b")
    return (earned > 0 and earned < limit and ret.get("1040.11b") < limit
            and investment <= year.fig("eic_screen", "investment_income_limit"))
