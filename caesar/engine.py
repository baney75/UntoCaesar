"""The tax year 2025 Form 1040 engine for v0's scope.

Every line is whole dollars. A line that adds amounts from documents adds them with cents
and rounds only the total, half up (i1040, Rounding Off to Whole Dollars). Each line records
its inputs, so the worksheet and caesar explain can show the work. The rule and citation for
each line come from the year file.
"""

from __future__ import annotations

from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

from . import facts as F
from .yeardata import YearData

ZERO = Decimal(0)


def whole(amount: Decimal) -> int:
    return int(amount.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def money(facts: dict, name: str) -> Decimal:
    v = F.value(facts, name)
    return Decimal(v) if v is not None else ZERO


class Return:
    def __init__(self):
        self.lines: dict[str, int] = {}
        self.inputs: dict[str, list[str]] = {}

    def put(self, line_id: str, value, inputs) -> int:
        value = int(value)
        self.lines[line_id] = value
        self.inputs[line_id] = list(inputs)
        return value

    def get(self, line_id: str) -> int:
        return self.lines.get(line_id, 0)


def indexes(facts: dict, count_fact: str) -> list[int]:
    return list(range(1, F.count(facts, count_fact) + 1))


def owner_of(facts: dict, prefix: str) -> str:
    return F.value(facts, f"{prefix}.owner") or "taxpayer"


def sum_facts(facts: dict, names: list[str]) -> Decimal:
    return sum((money(facts, n) for n in names), ZERO)


def compute(facts: dict, year: YearData) -> Return:
    r = Return()
    status = F.value(facts, "filing_status")
    joint = status == "mfj"

    # Income, Form 1040 lines 1 to 3.
    w2s = [f"w2.{i}" for i in indexes(facts, "w2.count")]
    ints = [f"int1099.{i}" for i in indexes(facts, "int1099.count")]
    divs = [f"div1099.{i}" for i in indexes(facts, "div1099.count")]
    names = [f"{w}.box1" for w in w2s]
    r.put("1040.1a", whole(sum_facts(facts, names)), names)
    r.put("1040.1z", r.get("1040.1a"), ["1040.1a"])
    names = [f"{i}.box8" for i in ints]
    r.put("1040.2a", whole(sum_facts(facts, names)), names)
    names = [f"{i}.{b}" for i in ints for b in ("box1", "box3")]
    r.put("1040.2b", whole(sum_facts(facts, names)), names)
    names = [f"{d}.box1b" for d in divs]
    r.put("1040.3a", whole(sum_facts(facts, names)), names)
    names = [f"{d}.box1a" for d in divs]
    r.put("1040.3b", whole(sum_facts(facts, names)), names)

    # Schedule C, one per owner (caesar check refuses a second business for the same owner).
    owners = []
    for i in indexes(facts, "business.count"):
        b = f"business.{i}"
        owner = owner_of(facts, b)
        if owner in owners:
            continue
        owners.append(owner)
        schedule_c(r, facts, year, b, f"schc-{owner}")

    # Schedule SE for each owner with a Schedule C.
    for owner in owners:
        schedule_se(r, facts, year, owner, [w for w in w2s if owner_of(facts, w) == owner])

    # Schedule 1.
    if owners:
        c31 = [f"schc-{o}.31" for o in owners]
        r.put("s1.3", sum(r.get(x) for x in c31), c31)
        r.put("s1.10", r.get("s1.3"), ["s1.3"])
        se13 = [f"se-{o}.13" for o in owners if f"se-{o}.13" in r.lines]
        r.put("s1.15", sum(r.get(x) for x in se13), se13)
        r.put("s1.26", r.get("s1.15"), ["s1.15"])
        se12 = [f"se-{o}.12" for o in owners if f"se-{o}.12" in r.lines]
        r.put("s2.4", sum(r.get(x) for x in se12), se12)
        r.put("s2.21", r.get("s2.4"), ["s2.4"])

    r.put("1040.8", r.get("s1.10"), ["s1.10"])
    r.put("1040.9", r.get("1040.1z") + r.get("1040.2b") + r.get("1040.3b") + r.get("1040.8"),
          ["1040.1z", "1040.2b", "1040.3b", "1040.8"])
    r.put("1040.10", r.get("s1.26"), ["s1.26"])
    r.put("1040.11a", r.get("1040.9") - r.get("1040.10"), ["1040.9", "1040.10"])
    r.put("1040.11b", r.get("1040.11a"), ["1040.11a"])

    # Standard deduction, line 12e.
    boxes = ["taxpayer.born_before_1961", "taxpayer.blind"]
    if joint:
        boxes += ["spouse.born_before_1961", "spouse.blind"]
    checked = sum(1 for b in boxes if F.value(facts, b) == "yes")
    if checked:
        amount = year.fig("standard_deduction_chart", status)[checked - 1]
    else:
        amount = year.fig("standard_deduction", status)
    r.put("1040.12e", amount, ["filing_status"] + boxes)

    # Schedule 1-A Part V, enhanced deduction for seniors, line 13b.
    senior(r, facts, year, status)

    # Form 8995, line 13a.
    if owners:
        form_8995(r, year, status, owners)
    r.put("1040.13a", r.get("8995.15"), ["8995.15"] if "8995.15" in r.lines else [])
    r.put("1040.14", r.get("1040.12e") + r.get("1040.13a") + r.get("1040.13b"), ["1040.12e", "1040.13a", "1040.13b"])
    r.put("1040.15", max(0, r.get("1040.11b") - r.get("1040.14")), ["1040.11b", "1040.14"])

    # Tax, line 16.
    r.put("1040.16", tax(year, status, r.get("1040.15")), ["1040.15", "filing_status"])
    r.put("1040.17", 0, [])
    r.put("1040.18", r.get("1040.16") + r.get("1040.17"), ["1040.16", "1040.17"])

    # Schedule 8812, lines 19 and 28.
    if F.count(facts, "dependents.count"):
        schedule_8812(r, facts, year, status, w2s)
    r.put("1040.19", r.get("8812.14"), ["8812.14"] if "8812.14" in r.lines else [])
    r.put("1040.20", 0, [])
    r.put("1040.21", r.get("1040.19") + r.get("1040.20"), ["1040.19", "1040.20"])
    r.put("1040.22", max(0, r.get("1040.18") - r.get("1040.21")), ["1040.18", "1040.21"])
    r.put("1040.23", r.get("s2.21"), ["s2.21"])
    r.put("1040.24", r.get("1040.22") + r.get("1040.23"), ["1040.22", "1040.23"])

    # Payments.
    names = [f"{w}.box2" for w in w2s]
    r.put("1040.25a", whole(sum_facts(facts, names)), names)
    necs = [f"nec1099.{i}" for i in indexes(facts, "nec1099.count")]
    names = [f"{x}.box4" for x in ints + divs + necs]
    r.put("1040.25b", whole(sum_facts(facts, names)), names)
    r.put("1040.25c", 0, [])
    r.put("1040.25d", r.get("1040.25a") + r.get("1040.25b") + r.get("1040.25c"), ["1040.25a", "1040.25b", "1040.25c"])
    r.put("1040.26", whole(money(facts, "payments.estimated")), ["payments.estimated"])
    r.put("1040.27a", 0, [])
    r.put("1040.28", r.get("8812.27"), ["8812.27"] if "8812.27" in r.lines else [])
    for line in ("1040.29", "1040.30", "1040.31"):
        r.put(line, 0, [])
    parts = ["1040.27a", "1040.28", "1040.29", "1040.30", "1040.31"]
    r.put("1040.32", sum(r.get(x) for x in parts), parts)
    r.put("1040.33", r.get("1040.25d") + r.get("1040.26") + r.get("1040.32"), ["1040.25d", "1040.26", "1040.32"])
    r.put("1040.34", max(0, r.get("1040.33") - r.get("1040.24")), ["1040.33", "1040.24"])
    r.put("1040.35a", r.get("1040.34"), ["1040.34"])
    r.put("1040.37", max(0, r.get("1040.24") - r.get("1040.33")), ["1040.24", "1040.33"])
    return r


def schedule_c(r: Return, facts: dict, year: YearData, b: str, c: str) -> None:
    def amount(line: str, key: str) -> int:
        return r.put(f"{c}.{line}", whole(money(facts, f"{b}.{key}")), [f"{b}.{key}"])

    amount("1", "gross_receipts")
    amount("2", "returns")
    r.put(f"{c}.3", r.get(f"{c}.1") - r.get(f"{c}.2"), [f"{c}.1", f"{c}.2"])
    r.put(f"{c}.4", 0, [])
    r.put(f"{c}.5", r.get(f"{c}.3") - r.get(f"{c}.4"), [f"{c}.3", f"{c}.4"])
    amount("6", "other_income")
    r.put(f"{c}.7", r.get(f"{c}.5") + r.get(f"{c}.6"), [f"{c}.5", f"{c}.6"])

    expense_lines = []
    amount("8", "advertising")
    expense_lines.append("8")
    car = money(facts, f"{b}.business_miles") * year.fig("mileage", "rate") + money(facts, f"{b}.parking_tolls")
    r.put(f"{c}.9", whole(car), [f"{b}.business_miles", f"{b}.parking_tolls"])
    expense_lines.append("9")
    for line, key in (("10", "commissions"), ("11", "contract_labor"), ("14", "employee_benefits"), ("15", "insurance"),
                      ("16a", "mortgage_interest"), ("16b", "other_interest"), ("17", "legal_professional"),
                      ("18", "office"), ("19", "pension_plans"), ("20a", "rent_equipment"), ("20b", "rent_other"),
                      ("21", "repairs"), ("22", "supplies"), ("23", "taxes_licenses"), ("24a", "travel")):
        amount(line, key)
        expense_lines.append(line)
    r.put(f"{c}.24b", whole(money(facts, f"{b}.meals") * year.fig("meals", "rate")), [f"{b}.meals"])
    expense_lines.append("24b")
    for line, key in (("25", "utilities"), ("26", "wages"), ("27b", "other_expenses")):
        amount(line, key)
        expense_lines.append(line)
    ids = [f"{c}.{x}" for x in expense_lines]
    r.put(f"{c}.28", sum(r.get(x) for x in ids), ids)
    r.put(f"{c}.29", r.get(f"{c}.7") - r.get(f"{c}.28"), [f"{c}.7", f"{c}.28"])
    r.put(f"{c}.30", 0, [])
    r.put(f"{c}.31", r.get(f"{c}.29") - r.get(f"{c}.30"), [f"{c}.29", f"{c}.30"])


def schedule_se(r: Return, facts: dict, year: YearData, owner: str, w2s: list[str]) -> None:
    s = f"se-{owner}"
    r.put(f"{s}.2", r.get(f"schc-{owner}.31"), [f"schc-{owner}.31"])
    r.put(f"{s}.3", r.get(f"{s}.2"), [f"{s}.2"])
    line3 = r.get(f"{s}.3")
    a4 = whole(Decimal(line3) * year.fig("self_employment", "net_earnings_factor")) if line3 > 0 else line3
    r.put(f"{s}.4a", a4, [f"{s}.3"])
    if a4 < year.fig("self_employment", "minimum_net_earnings"):
        r.put(f"{s}.4c", 0, [f"{s}.4a"])
        return
    r.put(f"{s}.4c", a4, [f"{s}.4a"])
    r.put(f"{s}.6", r.get(f"{s}.4c"), [f"{s}.4c"])
    r.put(f"{s}.7", year.fig("self_employment", "ss_wage_base"), [])
    names = [f"{w}.{b}" for w in w2s for b in ("box3", "box7")]
    r.put(f"{s}.8a", whole(sum_facts(facts, names)), names)
    r.put(f"{s}.8d", r.get(f"{s}.8a"), [f"{s}.8a"])
    r.put(f"{s}.9", max(0, r.get(f"{s}.7") - r.get(f"{s}.8d")), [f"{s}.7", f"{s}.8d"])
    base = min(r.get(f"{s}.6"), r.get(f"{s}.9"))
    r.put(f"{s}.10", whole(Decimal(base) * year.fig("self_employment", "ss_rate")), [f"{s}.6", f"{s}.9"])
    r.put(f"{s}.11", whole(Decimal(r.get(f"{s}.6")) * year.fig("self_employment", "medicare_rate")), [f"{s}.6"])
    r.put(f"{s}.12", r.get(f"{s}.10") + r.get(f"{s}.11"), [f"{s}.10", f"{s}.11"])
    r.put(f"{s}.13", whole(Decimal(r.get(f"{s}.12")) * year.fig("self_employment", "deduction_rate")), [f"{s}.12"])


def senior(r: Return, facts: dict, year: YearData, status: str) -> None:
    people = ["taxpayer"] + (["spouse"] if status == "mfj" else [])

    def qualifies(person: str) -> bool:
        return (status != "mfs" and F.value(facts, f"{person}.born_before_1961") == "yes"
                and F.value(facts, f"{person}.ssn_valid_for_work") == "yes")

    if not any(qualifies(p) for p in people):
        r.put("1040.13b", 0, [])
        return
    r.put("s1a.1", r.get("1040.11b"), ["1040.11b"])
    r.put("s1a.3", r.get("s1a.1"), ["s1a.1"])
    r.put("s1a.31", r.get("s1a.3"), ["s1a.3"])
    threshold = year.fig("senior_deduction", "magi_threshold_mfj" if status == "mfj" else "magi_threshold_other")
    r.put("s1a.32", threshold, ["filing_status"])
    r.put("s1a.33", max(0, r.get("s1a.31") - r.get("s1a.32")), ["s1a.31", "s1a.32"])
    r.put("s1a.34", whole(Decimal(r.get("s1a.33")) * year.fig("senior_deduction", "rate")), ["s1a.33"])
    r.put("s1a.35", max(0, year.fig("senior_deduction", "amount") - r.get("s1a.34")), ["s1a.34"])
    r.put("s1a.36a", r.get("s1a.35") if qualifies("taxpayer") else 0,
          ["s1a.35", "taxpayer.born_before_1961", "taxpayer.ssn_valid_for_work"])
    if status == "mfj":
        r.put("s1a.36b", r.get("s1a.35") if qualifies("spouse") else 0,
              ["s1a.35", "spouse.born_before_1961", "spouse.ssn_valid_for_work"])
    parts = ["s1a.36a"] + (["s1a.36b"] if status == "mfj" else [])
    r.put("s1a.37", sum(r.get(x) for x in parts), parts)
    r.put("s1a.38", r.get("s1a.37"), ["s1a.37"])
    r.put("1040.13b", r.get("s1a.38"), ["s1a.38"])


def form_8995(r: Return, year: YearData, status: str, owners: list[str]) -> None:
    rows = []
    for owner in owners:
        line = f"8995-{owner}.1"
        se13 = f"se-{owner}.13"
        r.put(line, r.get(f"schc-{owner}.31") - r.get(se13), [f"schc-{owner}.31", se13])
        rows.append(line)
    r.put("8995.2", sum(r.get(x) for x in rows), rows)
    r.put("8995.3", 0, [])
    r.put("8995.4", max(0, r.get("8995.2") + r.get("8995.3")), ["8995.2", "8995.3"])
    r.put("8995.5", whole(Decimal(r.get("8995.4")) * year.fig("qbi", "rate")), ["8995.4"])
    r.put("8995.10", r.get("8995.5"), ["8995.5"])
    r.put("8995.11", r.get("1040.11a") - r.get("1040.12e") - r.get("1040.13b"), ["1040.11a", "1040.12e", "1040.13b"])
    r.put("8995.12", r.get("1040.3a"), ["1040.3a"])
    r.put("8995.13", max(0, r.get("8995.11") - r.get("8995.12")), ["8995.11", "8995.12"])
    r.put("8995.14", whole(Decimal(r.get("8995.13")) * year.fig("qbi", "income_limit_rate")), ["8995.13"])
    r.put("8995.15", min(r.get("8995.10"), r.get("8995.14")), ["8995.10", "8995.14"])


def tax(year: YearData, status: str, income: int) -> int:
    column = {"single": 2, "mfj": 3, "qss": 3, "mfs": 4, "hoh": 5}[status]
    if income < year.fig("tax_table_limit", "amount"):
        for row in year.tax_table:
            if row[0] <= income < row[1]:
                return row[column]
        raise ValueError(f"no Tax Table row for {income}")
    for start, end, rate, subtract in year.fig("tax_computation_worksheet", status):
        if income >= start and (end == 0 or income <= end):
            return whole(Decimal(income) * Decimal(rate) - Decimal(subtract))
    raise ValueError(f"no Tax Computation Worksheet row for {income}")


def dependents(facts: dict) -> tuple[list[str], list[str]]:
    """Dependents counted on Schedule 8812 line 4 (child tax credit) and line 6 (other dependents)."""
    children, others = [], []
    for i in indexes(facts, "dependents.count"):
        d = f"dependent.{i}"
        if F.value(facts, f"{d}.us_person") != "yes":
            continue
        has_ssn = F.value(facts, f"{d}.ssn_valid_for_work") == "yes"
        if (F.value(facts, f"{d}.qualifying_child") == "yes" and F.value(facts, f"{d}.under_17") == "yes" and has_ssn):
            children.append(d)
        elif has_ssn or F.value(facts, f"{d}.has_tin") == "yes":
            others.append(d)
    return children, others


def schedule_8812(r: Return, facts: dict, year: YearData, status: str, w2s: list[str]) -> None:
    children, others = dependents(facts)
    deps = [f"dependent.{i}" for i in indexes(facts, "dependents.count")]
    r.put("8812.1", r.get("1040.11a"), ["1040.11a"])
    r.put("8812.3", r.get("8812.1"), ["8812.1"])
    r.put("8812.4", len(children), [f"{d}.{k}" for d in deps for k in ("qualifying_child", "under_17", "ssn_valid_for_work", "us_person")
                                    if f"{d}.{k}" in facts])
    r.put("8812.5", r.get("8812.4") * year.fig("child_tax_credit", "per_child"), ["8812.4"])
    r.put("8812.6", len(others), [f"{d}.{k}" for d in deps for k in ("ssn_valid_for_work", "has_tin", "us_person") if f"{d}.{k}" in facts])
    r.put("8812.7", r.get("8812.6") * year.fig("child_tax_credit", "per_other_dependent"), ["8812.6"])
    r.put("8812.8", r.get("8812.5") + r.get("8812.7"), ["8812.5", "8812.7"])
    start = year.fig("child_tax_credit", "phaseout_start_mfj" if status == "mfj" else "phaseout_start_other")
    r.put("8812.9", start, ["filing_status"])
    over = r.get("8812.3") - r.get("8812.9")
    step = Decimal(year.fig("child_tax_credit", "phaseout_step"))
    over = int((Decimal(over) / step).to_integral_value(rounding=ROUND_CEILING) * step) if over > 0 else 0
    r.put("8812.10", over, ["8812.3", "8812.9"])
    r.put("8812.11", whole(Decimal(r.get("8812.10")) * year.fig("child_tax_credit", "phaseout_rate")), ["8812.10"])
    r.put("8812.12", max(0, r.get("8812.8") - r.get("8812.11")), ["8812.8", "8812.11"])

    r.put("clwa.1", r.get("1040.18"), ["1040.18"])
    r.put("clwa.2", 0, [])
    r.put("clwa.3", r.get("clwa.1") - r.get("clwa.2"), ["clwa.1", "clwa.2"])
    r.put("clwa.4", 0, [])
    r.put("clwa.5", r.get("clwa.3") - r.get("clwa.4"), ["clwa.3", "clwa.4"])
    r.put("8812.13", r.get("clwa.5"), ["clwa.5"])
    r.put("8812.14", min(r.get("8812.12"), r.get("8812.13")), ["8812.12", "8812.13"])
    if r.get("8812.12") == 0 or r.get("8812.4") == 0:
        r.put("8812.27", 0, ["8812.12", "8812.4"])
        return

    # Part II-A, additional child tax credit.
    r.put("8812.16a", r.get("8812.12") - r.get("8812.14"), ["8812.12", "8812.14"])
    if r.get("8812.16a") == 0:
        r.put("8812.27", 0, ["8812.16a"])
        return
    r.put("8812.16b", r.get("8812.4") * year.fig("additional_child_tax_credit", "per_child"), ["8812.4"])
    r.put("8812.17", min(r.get("8812.16a"), r.get("8812.16b")), ["8812.16a", "8812.16b"])

    r.put("eiw.1a", r.get("1040.1z"), ["1040.1z"])
    c31 = [x for x in r.lines if x.startswith("schc-") and x.endswith(".31")]
    r.put("eiw.2b", sum(r.get(x) for x in c31), c31)
    r.put("eiw.3", max(0, r.get("eiw.1a") + r.get("eiw.2b")), ["eiw.1a", "eiw.2b"])
    if r.get("eiw.3") > 0:
        r.put("eiw.5", r.get("s1.15"), ["s1.15"])
        r.put("eiw.7", r.get("eiw.3") - r.get("eiw.5"), ["eiw.3", "eiw.5"])
    else:
        r.put("eiw.7", 0, ["eiw.3"])
    r.put("8812.18a", r.get("eiw.7"), ["eiw.7"])
    floor = year.fig("additional_child_tax_credit", "earned_income_floor")
    r.put("8812.19", max(0, r.get("8812.18a") - floor), ["8812.18a"])
    r.put("8812.20", whole(Decimal(r.get("8812.19")) * year.fig("additional_child_tax_credit", "rate")), ["8812.19"])

    if r.get("8812.16b") < year.fig("additional_child_tax_credit", "three_child_trigger") or r.get("8812.20") >= r.get("8812.17"):
        if r.get("8812.16b") < year.fig("additional_child_tax_credit", "three_child_trigger"):
            r.put("8812.27", min(r.get("8812.17"), r.get("8812.20")), ["8812.17", "8812.20"])
        else:
            r.put("8812.27", r.get("8812.17"), ["8812.17", "8812.20"])
        return

    # Part II-B, three or more qualifying children.
    names = [f"{w}.{b}" for w in w2s for b in ("box4", "box6")]
    r.put("8812.21", whole(sum_facts(facts, names)), names)
    r.put("8812.22", r.get("s1.15"), ["s1.15"])
    r.put("8812.23", r.get("8812.21") + r.get("8812.22"), ["8812.21", "8812.22"])
    r.put("8812.24", 0, [])
    r.put("8812.25", max(0, r.get("8812.23") - r.get("8812.24")), ["8812.23", "8812.24"])
    r.put("8812.26", max(r.get("8812.20"), r.get("8812.25")), ["8812.20", "8812.25"])
    r.put("8812.27", min(r.get("8812.17"), r.get("8812.26")), ["8812.17", "8812.26"])
