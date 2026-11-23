"""Every golden case runs the way the skill runs caesar, and every computed line is exact."""

import json
import re
import subprocess

import pytest
import runner

CASES = runner.case_folders()


def expected(folder):
    return json.loads((folder / "expected.json").read_text(encoding="utf-8"))


def test_suite_has_the_required_cases():
    names = {f.name for f in CASES}
    assert {"single-w2", "mfj-two-children", "hoh-blind-two-dependents", "freelancer-schedule-c",
            "w2-plus-side-business", "refuse-ssa1099", "refuse-1099r", "refuse-1099g", "refuse-schedule-b-interest",
            "refuse-qualified-dividends", "refuse-eic-one-child", "misread-w2-box1", "hostile-payer-name",
            "refuse-eic-child-not-dependent", "mfj-one-business-each",
            "refuse-amt-withheld-two-w2-one-employer"} <= names


@pytest.mark.parametrize("folder", CASES, ids=[f.name for f in CASES])
def test_case(folder, tmp_path):
    want = expected(folder)
    result = runner.run(folder, workdir=tmp_path)
    assert result["outcome"] == want["outcome"], result["output"][-2000:]
    if want["outcome"] == "prepared":
        assert result["lines"] == want["lines"]
        strict, lenient, n = runner.score(result["lines"], runner.expected_xml(folder))
        assert (strict, lenient) == (n, n)
        assert result["state"]["final"].startswith("prepared for the eval")
        assert result["return"]["test_build"] == "Test build: synthetic cases only, not for real records."
    elif want["outcome"] == "refused":
        assert result["at"] == want["at"]
        assert want["message"] in result["output"]
        assert result["output"].strip().endswith("NEXT: none")
    elif want["outcome"] == "check_failed":
        assert want["fix"] in result["state"]["check"]["fix"]
        last = result["transcript"][-1]
        assert last[0] == "check" and last[1] == 1
        assert f"set {want['fix']} --stdin <<'CAESAR_END'\nvalue: <amount>\n" in last[2]


def test_input_files_are_synthetic():
    for folder in CASES:
        case = json.loads((folder / "input.json").read_text(encoding="utf-8"))
        assert case["input"]["return_header"]["synthetic"] is True
        assert case["untocaesar"]["anchors"] or case["untocaesar"].get("misread")
        text = (folder / "input.json").read_text(encoding="utf-8")
        assert not re.search(r"\b(?!000)\d{3}-?\d{2}-?\d{4}\b", text), "looks like a real SSN"


def test_no_person_channel_leaves_every_fact_unconfirmed(tmp_path):
    folder = runner.CASES / "single-w2"
    result = runner.run(folder, scripted=False, workdir=tmp_path)
    assert result["outcome"] == "computed_not_confirmed"
    assert result["state"]["final"] == "computed, not confirmed"
    assert result["lines"] == expected(folder)["lines"]
    facts = (result["job"] / "facts.toml").read_text(encoding="utf-8")
    assert 'confirmed = "yes"' not in facts
    # first-F1: the run ends, and its last reply says confirm can still ask the person.
    assert "call the caesar_confirm tool" in result["transcript"][-1][2]


def test_hostile_payer_name_renders_inert(tmp_path):
    folder = runner.CASES / "hostile-payer-name"
    result = runner.run(folder, workdir=tmp_path)
    page = (result["job"] / "worksheet.html").read_text(encoding="utf-8")
    assert ('<meta http-equiv="Content-Security-Policy" content="default-src &#x27;none&#x27;; '
            'style-src &#x27;unsafe-inline&#x27;">') in page
    assert "<script" not in page.lower()
    assert "<img" not in page.lower()
    assert "&lt;img src=https://x/?d=1&gt;&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "Acme &quot;Payroll&quot; &amp; Co&#x27;s &lt;b&gt;" in page
    assert page.count("Test build: synthetic cases only, not for real records.") >= 1
    assert re.search(r"<(link|iframe|object|embed|base|form)\b", page) is None


PWNED = "/tmp/caesar-pwned"


def bash(script):
    return subprocess.run([runner.BASH, "-c", script], capture_output=True).returncode


def test_hostile_payer_name_goes_through_bash_byte_for_byte(tmp_path):
    # second-F7: the runner fills each NEXT set template with the name as it is and runs it in bash.
    bash(f"rm -f {PWNED}")
    folder = runner.CASES / "hostile-payer-name"
    case = json.loads((folder / "input.json").read_text(encoding="utf-8"))
    rd = case["input"]["return_data"]
    employer = rd["w2"][0]["employer_name"]["value"]
    payer = rd["irs1040_scheduleb"]["irs1099_int"][0]["interest_1099int_payer"]["value"]
    for needle in (f"$(touch {PWNED})", f"`touch {PWNED}`", '"', "'", "\\"):
        assert needle in employer
    (tmp_path / "hostile").mkdir()
    result = runner.run(folder, workdir=tmp_path / "hostile")
    assert bash(f"test -e {PWNED}") != 0, "a payer name ran a command"
    facts = runner.cli.Job(result["job"]).facts()
    assert facts["w2.1.employer"]["value"] == employer
    assert facts["w2.1.box1"]["source"] == f"W-2 from {employer}, box 1"
    assert facts["int1099.1.payer"]["value"] == payer

    rd["w2"][0]["employer_name"]["value"] = "Acme Payroll"
    rd["irs1040_scheduleb"]["irs1099_int"][0]["interest_1099int_payer"]["value"] = "First Bank"
    twin = tmp_path / "plain-payer-name"
    twin.mkdir()
    (twin / "input.json").write_text(json.dumps(case), encoding="utf-8")
    (tmp_path / "plain").mkdir()
    plain = runner.run(twin, workdir=tmp_path / "plain")
    assert result["outcome"] == plain["outcome"] == "prepared"
    assert result["lines"] == plain["lines"]
    assert result["state"]["final"] == plain["state"]["final"]
