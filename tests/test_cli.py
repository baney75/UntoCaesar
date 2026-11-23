"""caesar's messages: the banner, one NEXT line, and what set and confirm refuse to do."""

import contextlib
import io

import pytest

from caesar import checks as C
from caesar import cli
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
    assert lines[-1].startswith("NEXT: ")
    assert sum(1 for x in lines if x.startswith("NEXT: ")) == 1


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
    assert status.strip().splitlines()[-1] == "NEXT: caesar --job " + str(job) + " ask"
    assert ask.strip().splitlines()[-1].startswith("NEXT: caesar --job " + str(job) + " set screen.ssa1099 <yes or no>")


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
    assert out.strip().endswith("NEXT: caesar --job " + str(job) + " ask")
    answer(job, ("business.1.name", "Birch Design"))
    _, out = run(job, "ask")
    assert "set business.1.owner <taxpayer or spouse>" in out
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
    assert "set eic.children <number>" in out
    assert "even one you do not list as a dependent" in out
