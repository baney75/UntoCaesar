"""caesar's messages: the banner, one NEXT line, and what set and confirm refuse to do."""

import contextlib
import io

import pytest

from caesar import checks as C
from caesar import cli
from caesar import engine, yeardata
from caesar import facts as F

BANNER = "Test build: synthetic cases only, not for real records."


def run(job, *args):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cli.main(["--job", str(job), *args])
    return code, buf.getvalue()


@pytest.fixture
def job(tmp_path, monkeypatch):
    monkeypatch.setenv("CAESAR_CMD", "caesar")
    monkeypatch.delenv("CAESAR_SCRIPTED_PERSON", raising=False)
    return tmp_path / "job"


def check_message(out):
    lines = out.strip().splitlines()
    assert lines[0] == BANNER
    assert sum(1 for x in lines if x.startswith("NEXT: ")) == 1
    # NEXT is the last line, or a set whose heredoc runs on to the end.
    if lines[-1] == cli.END:
        assert lines[-4].startswith("NEXT: ") and lines[-4].endswith(" --stdin <<'CAESAR_END'")
    else:
        assert lines[-1].startswith("NEXT: ")


def set_stdin(job, monkeypatch, name, body):
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(body.encode("utf-8")), encoding="utf-8"))
    return run(job, "set", name, "--stdin")


def test_every_message_has_the_banner_and_one_next_line(job):
    for args in (("status",), ("new",), ("status",), ("ask",), ("facts",), ("compute",), ("check",),
                 ("set", "screen.ssa1099", "no", "--source", "answer"), ("set", "nope", "1", "--source", "x"),
                 ("explain", "16"), ("worksheet",), ("done",), ("confirm",)):
        _, out = run(job, *args)
        check_message(out)


def test_status_repeats_the_next_line(job):
    run(job, "new")
    _, ask = run(job, "ask")
    _, status = run(job, "status")
    assert status.strip().splitlines()[-1] == "NEXT: caesar --job " + cli.quote_arg(str(job)) + " ask"
    assert ask.strip().splitlines()[-1].startswith("NEXT: caesar --job " + cli.quote_arg(str(job)) + " set screen.ssa1099 <yes or no>")


@pytest.mark.parametrize("extra", [["--confirmed"], ["--confirmed=yes"], ["--confirm"], ["confirmed=yes"]])
def test_set_cannot_mark_a_fact_confirmed(job, extra):
    run(job, "new")
    code, out = run(job, "set", "screen.ssa1099", "no", "--source", "answer", *extra)
    assert code == 2
    assert "Only the person can, through caesar confirm" in out
    assert "screen.ssa1099" not in (job / "facts.toml").read_text(encoding="utf-8")


def test_set_cannot_target_the_confirmed_field(job):
    run(job, "new")
    code, out = run(job, "set", "screen.ssa1099.confirmed", "yes", "--source", "answer")
    assert code == 2


def test_set_rejects_a_fact_outside_the_schema(job):
    run(job, "new")
    code, out = run(job, "set", "w2.1.box1", "50000", "--source", "W-2 box 1")
    assert code == 2 and "no fact named w2.1.box1" in out
    code, out = run(job, "set", "income.crypto", "5", "--source", "answer")
    assert code == 2


def test_set_validates_values(job):
    run(job, "new")
    code, out = run(job, "set", "screen.ssa1099", "maybe", "--source", "answer")
    assert code == 2 and "answer yes or no" in out


def test_screening_yes_is_a_refusal(job):
    run(job, "new")
    code, out = run(job, "set", "screen.1099r", "yes", "--source", "answer")
    assert code == 1
    assert "retirement distributions" in out
    assert out.strip().endswith("NEXT: none")


def test_confirm_without_a_person_records_nothing(job):
    run(job, "new")
    run(job, "set", "screen.ssa1099", "no", "--source", "answer")
    code, out = run(job, "confirm")
    assert "computed, not confirmed" in out
    assert 'confirmed = ""' in (job / "facts.toml").read_text(encoding="utf-8")


def test_no_start_gate(job, monkeypatch):
    monkeypatch.delenv("CAESAR_LOCAL_ONLY_ACK", raising=False)
    code, out = run(job, "new")
    assert code == 0


SCREENS_NO = [name for name, _, _ in F.DOCUMENT_SCREENS + F.SITUATION_SCREENS]


def answer(job, *pairs):
    for name, value in pairs:
        code, out = run(job, "set", name, value, "--source", "answer")
        assert code == 0, out
    return out


def test_joint_return_asks_each_business_owner(job):
    # second-F7: one Schedule C for each spouse must reach the owner questions.
    run(job, "new")
    answer(job, *[(name, "no") for name in SCREENS_NO])
    answer(job, ("filing_status", "mfj"))
    for who in ("taxpayer", "spouse"):
        answer(job, (f"{who}.born_before_1961", "no"), (f"{who}.blind", "no"), (f"{who}.ssn_valid_for_work", "yes"))
    answer(job, ("dependents.count", "0"), ("eic.children", "0"), ("w2.count", "0"), ("int1099.count", "0"),
           ("div1099.count", "0"), ("nec1099.count", "0"))
    out = answer(job, ("business.count", "2"))
    assert out.strip().endswith("NEXT: caesar --job " + cli.quote_arg(str(job)) + " ask")
    answer(job, ("business.1.name", "Birch Design"))
    _, out = run(job, "ask")
    assert "set business.1.owner --stdin <<'CAESAR_END'\nvalue: <taxpayer or spouse>\nsource: " in out
    answer(job, ("business.1.owner", "taxpayer"), ("business.2.name", "Fern Tutoring"))
    _, out = run(job, "status")
    assert "outside what caesar v0" not in out
    # Until business 2's owner is answered, nothing can be computed or prepared.
    _, out = run(job, "compute")
    assert "cannot compute" in out
    answer(job, ("business.2.owner", "spouse"))
    assert not C.fact_refusals(cli.Job(job).facts())
    answer(job, ("business.2.owner", "taxpayer"))
    assert C.fact_refusals(cli.Job(job).facts())


def test_eic_child_question_is_asked_without_dependents(job):
    # sol-F1: an EIC qualifying child need not be a dependent, so the question is always asked.
    run(job, "new")
    answer(job, *[(name, "no") for name in SCREENS_NO])
    answer(job, ("filing_status", "single"), ("taxpayer.born_before_1961", "no"), ("taxpayer.blind", "no"),
           ("taxpayer.ssn_valid_for_work", "yes"), ("dependents.count", "0"))
    _, out = run(job, "ask")
    assert "set eic.children --stdin <<'CAESAR_END'\nvalue: <number>\n" in out
    assert "even one you do not list as a dependent" in out


@pytest.mark.parametrize("by", ["person", "", "Person"])
def test_a_confirmation_caesar_did_not_record_is_refused_on_load(job, by):
    # first-F2: only caesar confirm's own channels can mark a fact confirmed.
    run(job, "new")
    answer(job, ("screen.ssa1099", "no"))
    path = job / "facts.toml"
    text = path.read_text(encoding="utf-8").replace('confirmed = ""\nby = ""', f'confirmed = "yes"\nby = "{by}"')
    path.write_text(text, encoding="utf-8")
    for args in (("status",), ("check",), ("done",)):
        code, out = run(job, *args)
        check_message(out)
        assert code == 2 and "only caesar confirm records" in out
        assert out.strip().endswith("NEXT: none")


def to_w2_employer(job):
    run(job, "new")
    answer(job, *[(name, "no") for name in SCREENS_NO])
    answer(job, ("filing_status", "single"), ("taxpayer.born_before_1961", "no"), ("taxpayer.blind", "no"),
           ("taxpayer.ssn_valid_for_work", "yes"), ("dependents.count", "0"), ("eic.children", "0"), ("w2.count", "1"))
    _, out = run(job, "ask")
    return out


def test_a_text_fact_is_set_from_a_heredoc_not_shell_quotes(job, monkeypatch):
    # second-F7: document text never lands inside shell syntax the model must escape.
    out = to_w2_employer(job)
    assert out.strip().endswith("set w2.1.employer --stdin <<'CAESAR_END'\nvalue: <name>\n"
                                "source: <document and box, or: answer>\nCAESAR_END")
    check_message(out)
    name = "Acme \"Payroll\" & Co's $(touch x) `id` C:\\new"
    code, out = set_stdin(job, monkeypatch, "w2.1.employer", f"value: {name}\nsource: W-2 from {name}, box c\n")
    assert code == 0, out
    stored = cli.Job(job).facts()["w2.1.employer"]
    assert stored["value"] == name and stored["source"] == f"W-2 from {name}, box c"


@pytest.mark.parametrize("body", ["value: CAESAR_END\nsource: answer\n", "value: Acme\nsource: CAESAR_END\n",
                                  "value: Acme\nCAESAR_END\nsource: answer\n"])
def test_set_stdin_refuses_the_heredoc_delimiter(job, monkeypatch, body):
    to_w2_employer(job)
    code, out = set_stdin(job, monkeypatch, "w2.1.employer", body)
    assert code == 2 and "cannot be CAESAR_END" in out
    assert "w2.1.employer" not in cli.Job(job).facts()


@pytest.mark.parametrize("body", ["", "value: Acme\n", "source: answer\nvalue: Acme\n", "value: Acme\nsource: x\nmore\n"])
def test_set_stdin_needs_a_value_line_and_a_source_line(job, monkeypatch, body):
    to_w2_employer(job)
    code, out = set_stdin(job, monkeypatch, "w2.1.employer", body)
    assert code == 2 and "exactly two lines" in out


def test_set_stdin_takes_nothing_from_the_command_line(job, monkeypatch):
    to_w2_employer(job)
    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"value: Acme\nsource: W-2\n"), encoding="utf-8"))
    code, out = run(job, "set", "w2.1.employer", "Other", "--stdin")
    assert code == 2 and "from the heredoc only" in out
    code, out = run(job, "set", "w2.1.employer")
    assert code == 2 and "needs a value and --source" in out


@pytest.mark.parametrize("box6, refused", [("1450", False), ("1451.01", True)])
def test_additional_medicare_tax_withheld_below_every_8959_threshold_is_refused(box6, refused):
    # sol-F1: box 6 over 1.45% of box 5 plus $1 is Additional Medicare Tax withheld, even on $100,000 of wages.
    facts = {name: {"value": v, "source": "answer", "confirmed": "yes"} for name, v in [("filing_status", "single"),
             ("w2.count", "1"), ("w2.1.box1", "100000"), ("w2.1.box5", "100000"), ("w2.1.box6", box6)]}
    report = C.run(facts, engine.compute(facts, yeardata.load(2025)), yeardata.load(2025))
    assert any("Form 8959 is needed to claim it" in f.message for f in report.refusals) == refused
