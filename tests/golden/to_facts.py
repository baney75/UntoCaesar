"""Convert a case in TaxCalcBench's layout to caesar set facts.

A case folder holds input.json in TaxCalcBench's tax year 2024 schema ({"input": {"return_header",
"return_data"}}), filled with synthetic tax year 2025 figures, and either output.xml (the expected
Form 1040 lines, as TaxCalcBench scores them) or a refusal in expected.json. Facts the schema has
no field for (screening answers, W-2 box 12 codes, business miles, a misread value for the
scripted person to reject) go in a top-level "untocaesar" object beside "input".

Usage: python3 tests/golden/to_facts.py <case folder>   prints the caesar set commands.
"""

from __future__ import annotations

import json
import shlex
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from caesar import facts as F  # noqa: E402

STATUS = {"single": "single", "married_jointly": "mfj", "married_separately": "mfs",
          "head_of_household": "hoh", "qualifying_widow": "qss", "qualifying_surviving_spouse": "qss"}
CHILD_RELATIONSHIPS = {"son", "daughter", "stepson", "stepdaughter", "stepchild", "foster child", "brother", "sister",
                       "half brother", "half sister", "stepbrother", "stepsister", "grandchild", "niece", "nephew"}
SENIOR_BEFORE = "1961-01-02"
UNDER_17_AFTER = "2008-12-31"


def v(node, key, default=None):
    """The value of a TaxCalcBench {label, value} field."""
    if not isinstance(node, dict) or key not in node:
        return default
    field = node[key]
    if isinstance(field, dict) and "value" in field:
        return field["value"] if field["value"] is not None else default
    return field if field is not None else default


def amount(x) -> str:
    return str(x if x not in (None, "") else 0)


def yes(flag) -> str:
    return "yes" if flag else "no"


def screens(rd: dict, extra: dict) -> dict:
    s1 = rd.get("irs1040_schedule1") or {}
    found = {
        "screen.ssa1099": bool((rd.get("ssa_1099") or {}).get("ssa_1099_grp")),
        "screen.1099r": bool(rd.get("irs1099_r")),
        "screen.1099g": bool(s1.get("irs1099_g")),
        "screen.1099b": bool((rd.get("irs8949") or {}).get("irs1099_b_grp")),
        "screen.1099k": bool(v(rd, "received_form_1099K")) or any(c.get("irs1099_k") for c in rd.get("irs1040_schedulec") or []),
        "screen.1098e": bool(v(s1, "student_interest", 0)) or bool(v(s1, "paid_student_loan_interest")),
        "screen.student_loan_interest": bool(v(s1, "student_interest", 0)) or bool(v(s1, "paid_student_loan_interest")),
        "screen.1098t": bool((rd.get("irs8863") or {}).get("student_educational_instn_grp")),
        "screen.tuition": bool((rd.get("irs8863") or {}).get("student_educational_instn_grp")),
        "screen.1095a": bool(v(rd.get("irs8962") or {}, "received_1095a")),
        "screen.itemize": bool(v(rd, "will_itemize")),
        "screen.educator_expenses": bool(v(s1, "qualified_educator")),
        "screen.other_credits": bool((rd.get("irs2441") or {}).get("qualifying_person_grp")),
        "screen.claimed_as_dependent": bool(v(rd["irs1040"], "tp_dependent")) or bool(v(rd["irs1040"], "sp_dependent")),
    }
    out = {}
    for name, _, _ in F.DOCUMENT_SCREENS:
        out[name] = yes(found.get(name))
    for name, _, _ in F.SITUATION_SCREENS:
        out[name] = yes(found.get(name))
    out.update(extra.get("screens", {}))
    return out


def all_facts(case: dict) -> dict[str, tuple[str, str]]:
    """Every fact the case gives, as {name: (raw value, source)}."""
    rd = case["input"]["return_data"]
    extra = case.get("untocaesar", {})
    f1040 = rd["irs1040"]
    out: dict[str, tuple[str, str]] = {}

    def put(name, value, source):
        out[name] = (str(value), source)

    for name, answer in screens(rd, extra).items():
        put(name, answer, "answer")
    status = STATUS[v(f1040, "filing_status")]
    put("filing_status", status, "answer")
    put("taxpayer.born_before_1961", yes(v(f1040, "tp_date_of_birth", "2000-01-01") < SENIOR_BEFORE), "answer: date of birth")
    put("taxpayer.blind", yes(v(f1040, "tp_blind")), "answer")
    put("taxpayer.ssn_valid_for_work", yes(v(rd, "has_ssn", True)), "answer")
    if status == "mfj":
        put("spouse.born_before_1961", yes(v(f1040, "sp_date_of_birth", "2000-01-01") < SENIOR_BEFORE), "answer: spouse date of birth")
        put("spouse.blind", yes(v(f1040, "sp_blind")), "answer")
        put("spouse.ssn_valid_for_work", extra.get("spouse_ssn_valid_for_work", "yes"), "answer")

    deps = f1040.get("dependent_detail") or []
    put("dependents.count", len(deps), "answer")
    for i, d in enumerate(deps, 1):
        child = (str(d.get("dependent_relationship", "")).lower() in CHILD_RELATIONSHIPS
                 and int(d.get("dependent_months_lived", 0)) > 6)
        put(f"dependent.{i}.qualifying_child", yes(child), "answer")
        put(f"dependent.{i}.under_17", yes(str(d.get("dependent_date_of_birth", "")) > UNDER_17_AFTER), "answer: date of birth")
        has_ssn = bool(d.get("dependent_ssn"))
        put(f"dependent.{i}.ssn_valid_for_work", yes(has_ssn), "answer")
        if not has_ssn:
            put(f"dependent.{i}.has_tin", yes(d.get("dependent_itin")), "answer")
        put(f"dependent.{i}.us_person", yes(d.get("dependent_us_citizen_national_or_resident_alien", True)), "answer")

    w2s = rd.get("w2") or []
    put("w2.count", len(w2s), "answer: number of W-2s")
    box12 = extra.get("w2_box12", {})
    for i, w in enumerate(w2s, 1):
        name = v(w, "employer_name", f"employer {i}")
        src = f"W-2 from {name}"
        put(f"w2.{i}.owner", v(w, "who_applies_to", "taxpayer"), src)
        put(f"w2.{i}.employer", name, f"{src}, box c")
        for box, key in (("box1", "wages"), ("box2", "withholding"), ("box3", "social_security_wages"),
                         ("box4", "social_security_tax"), ("box5", "medicare_wages_and_tips"),
                         ("box6", "medicare_tax_withheld"), ("box7", "social_security_tips"),
                         ("box8", "allocated_tips"), ("box10", "dependent_care_benefits")):
            put(f"w2.{i}.{box}", amount(v(w, key, 0)), f"{src}, {box.replace('box', 'box ')}")
        put(f"w2.{i}.box12", box12.get(str(i), "none"), f"{src}, box 12")
        put(f"w2.{i}.box13_statutory", yes(v(w, "statutory_employee")), f"{src}, box 13")

    sb = rd.get("irs1040_scheduleb") or {}
    ints = sb.get("irs1099_int") or []
    put("int1099.count", len(ints), "answer: number of 1099-INTs")
    for i, n in enumerate(ints, 1):
        payer = v(n, "interest_1099int_payer", f"payer {i}")
        src = f"1099-INT from {payer}"
        put(f"int1099.{i}.payer", payer, f"{src}, payer's name")
        put(f"int1099.{i}.box1", amount(v(n, "interest_1099int_interest", 0)), f"{src}, box 1")
        put(f"int1099.{i}.box3", amount(v(n, "interest_1099int_us_saving_bond_treasury_obligations", 0)), f"{src}, box 3")
        put(f"int1099.{i}.box4", amount(v(n, "interest_1099int_fed_inc_tax_withheld", 0)), f"{src}, box 4")
        put(f"int1099.{i}.box8", amount(v(n, "interest_1099int_tax_exempt", 0)), f"{src}, box 8")
        other = ("early_withdrawal", "investment_expenses", "foreign_taxes_paid", "specified_private_act_bond",
                 "market_discount", "bond_premium", "bond_premium_treasury", "bond_premium_tax_exempt")
        put(f"int1099.{i}.other_boxes", yes(any(v(n, f"interest_1099int_{k}", 0) for k in other)), f"{src}, other boxes")

    divs = sb.get("irs1099_div") or []
    put("div1099.count", len(divs), "answer: number of 1099-DIVs")
    for i, d in enumerate(divs, 1):
        payer = v(d, "dividend_1099div_payer", f"payer {i}")
        src = f"1099-DIV from {payer}"
        put(f"div1099.{i}.payer", payer, f"{src}, payer's name")
        put(f"div1099.{i}.box1a", amount(v(d, "dividend_1099div_ordinary_div", 0)), f"{src}, box 1a")
        put(f"div1099.{i}.box1b", amount(v(d, "dividend_1099div_qualified_div", 0)), f"{src}, box 1b")
        put(f"div1099.{i}.box4", amount(v(d, "dividend_1099div_federal_inc_tax_withheld", 0)), f"{src}, box 4")
        other = ("capital_gain_distr", "unrecap_sec_1250_gain", "section_1202_gain", "collectibles_gain",
                 "section_897_ordinary_div", "section_897_capital_gain", "nondividend_distributions",
                 "section_199a_dividends", "investment_expenses", "foreign_tax_paid", "cash_liquidation_distrib",
                 "noncash_liquidation_distrib", "exempt_interest_div", "specified_private_activity_bond")
        put(f"div1099.{i}.other_boxes", yes(any(v(d, f"dividend_1099div_{k}", 0) for k in other)), f"{src}, other boxes")

    businesses = rd.get("irs1040_schedulec") or []
    necs = [(c, n) for c in businesses for n in (c.get("irs1099_nec") or [])]
    put("nec1099.count", len(necs), "answer: number of 1099-NECs")
    for i, (c, n) in enumerate(necs, 1):
        payer = n.get("nec_payer_name", f"payer {i}")
        src = f"1099-NEC from {payer}"
        put(f"nec1099.{i}.owner", v(c, "who_applies_to", "taxpayer"), src)
        put(f"nec1099.{i}.payer", payer, f"{src}, payer's name")
        put(f"nec1099.{i}.box1", amount(n.get("nec_comp", 0)), f"{src}, box 1")
        put(f"nec1099.{i}.box3", amount(n.get("nec_golden_parachute", 0)), f"{src}, box 3")
        put(f"nec1099.{i}.box4", amount(n.get("nec_fed_wh", 0)), f"{src}, box 4")

    put("business.count", len(businesses), "answer: number of businesses")
    business_extra = extra.get("business", [])
    for i, c in enumerate(businesses, 1):
        more = business_extra[i - 1] if i - 1 < len(business_extra) else {}
        b = f"business.{i}"
        name = v(c, "business_name", f"business {i}")
        src = f"answer: {name} records"
        put(f"{b}.name", name, "answer")
        put(f"{b}.owner", v(c, "who_applies_to", "taxpayer"), "answer")
        put(f"{b}.material_participation", yes(v(c, "material_participate", True)), "answer")
        put(f"{b}.all_at_risk", yes(v(c, "schc_at_risk", True)), "answer")
        put(f"{b}.inventory", more.get("inventory", "no"), "answer")
        put(f"{b}.home_office", yes(v(c, "business_home_area", 0)), "answer")
        put(f"{b}.vehicle_actual", more.get("vehicle_actual", "no"), "answer")
        put(f"{b}.depreciation", yes(v(c, "depletion", 0) or more.get("depreciation") == "yes"), "answer")
        other_expenses = sum(x.get("amount", x.get("value", 0)) or 0 for x in (c.get("other_expense_detail") or []))
        for key, field in (("gross_receipts", "gross_receipts_cash"), ("returns", "returns_allowances"),
                           ("other_income", "other_income"), ("advertising", "advertising"),
                           ("commissions", "commissions_fees"), ("contract_labor", "contract_labor"),
                           ("employee_benefits", "employee_benefit"), ("insurance", "insurance"),
                           ("mortgage_interest", "mortgage_interest"), ("other_interest", "other_interest"),
                           ("legal_professional", "legal_professional"), ("office", "office_expense"),
                           ("pension_plans", "pension_psp"), ("rent_equipment", "machinery_equip_rent"),
                           ("rent_other", "other_rent"), ("repairs", "repairs_maintenance"), ("supplies", "supplies"),
                           ("taxes_licenses", "tax_licenses"), ("travel", "travel"), ("meals", "meal_entertainment"),
                           ("utilities", "utilities"), ("wages", "wages_expense")):
            put(f"{b}.{key}", amount(v(c, field, 0)), src)
        put(f"{b}.business_miles", amount(more.get("business_miles", 0)), f"answer: {name} mileage log")
        put(f"{b}.parking_tolls", amount(more.get("parking_tolls", 0)), src)
        put(f"{b}.other_expenses", amount(other_expenses), src)

    paid = sum(v(f1040, f"estimated_tax_payment_{q}", 0) or 0 for q in range(1, 5)) + (v(f1040, "applied_from_prior_year", 0) or 0)
    put("payments.estimated", amount(paid), "answer: estimated tax payment records")

    for name, wrong in extra.get("misread", {}).items():
        out[name] = (str(wrong), out[name][1])
    return out


def convert(case: dict) -> list[tuple[str, str, str]]:
    """The caesar set calls for a case, in interview order: (fact, value, source)."""
    given = all_facts(case)
    current: dict = {}
    ordered = []
    while True:
        spec = next((s for s in F.specs(current) if s.name not in current and s.name in given), None)
        if spec is None:
            break
        raw, source = given[spec.name]
        current[spec.name] = {"value": F.normalize(spec.kind, raw), "source": source, "confirmed": "", "by": ""}
        ordered.append((spec.name, raw, source))
    return ordered


def truth(case: dict) -> dict:
    """The scripted person's true values: the case's facts without any misread."""
    clean = dict(case)
    clean["untocaesar"] = {k: val for k, val in case.get("untocaesar", {}).items() if k != "misread"}
    return {"facts": {name: raw for name, raw, _ in convert(clean)}}


def load(folder: Path) -> dict:
    return json.loads((folder / "input.json").read_text(encoding="utf-8"))


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__)
        return 2
    for name, value, source in convert(load(Path(argv[0]))):
        print(f"caesar set {name} {shlex.quote(value)} --source {shlex.quote(source)}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
