"""Only the person confirms: the signed ledger, the keychain and the facts.toml golden case."""

import json
import secrets
import shutil
import subprocess
import sys

import pytest
import runner
from conftest import REAL_LOAD_KEY

from caesar import cli, keystore, ledger, mcp
from caesar import confirm as K

FOLDER = runner.CASES / "single-w2"


@pytest.fixture(autouse=True)
def caesar_cmd(monkeypatch):
    monkeypatch.setenv("CAESAR_CMD", "caesar")


def job_with_facts(tmp_path):
    path = (tmp_path / "job").resolve()
    server = mcp.Server(local_only=True, root=tmp_path / "outside")
    for args in (("new",), ("set", "screen.ssa1099", "no", "--source", "answer"),
                 ("set", "screen.1099r", "no", "--source", "answer")):
        runner.caesar(path, *args)
    return path, server


def confirm(server, path):
    reply = server.handle({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                           "params": {"name": "caesar_confirm", "arguments": {"job": str(path)}}})
    return reply["result"]["content"][0]["text"]


def states(path):
    return {name: e["confirmed"] for name, e in cli.Job(path).facts().items()}


# -- the ledger ------------------------------------------------------------------

def test_an_entry_covers_only_the_value_and_source_it_was_signed_for(tmp_path, test_keychain):
    path, _ = job_with_facts(tmp_path)
    job = cli.Job(path)
    key, _ = keystore.load_key(create=True)
    facts = job.facts()
    ledger.record(path, key, job.job_id(), [("screen.ssa1099", facts["screen.ssa1099"], "yes")], K.PERSON)
    assert states(path)["screen.ssa1099"] == "yes"
    runner.caesar(path, "set", "screen.ssa1099", "yes", "--source", "answer")
    assert states(path)["screen.ssa1099"] == "", "a new value needs a new confirmation"
    runner.caesar(path, "set", "screen.ssa1099", "no", "--source", "answer")
    assert states(path)["screen.ssa1099"] == "yes", "the person's answer covers the value it was shown"

    state = json.loads(job.state_path.read_text(encoding="utf-8"))
    state["id"] = "another-job"
    job.save_state(state)
    assert states(path)["screen.ssa1099"] == "", "an entry from another job confirms nothing"


@pytest.mark.parametrize("text", ["", "not json", "[]", '{"entries": 5}', '{"entries": [5, {"fact": 1}]}'])
def test_a_broken_ledger_is_unconfirmed_never_an_error(tmp_path, text):
    path, _ = job_with_facts(tmp_path)
    keystore.load_key(create=True)
    (path / ledger.NAME).write_text(text, encoding="utf-8")
    assert set(states(path).values()) == {""}
    code, out = runner.caesar(path, "status")
    assert code == 0 and "Not confirmed by the person: 2." in out


def test_newest_answer_wins(tmp_path):
    path, _ = job_with_facts(tmp_path)
    job = cli.Job(path)
    key, _ = keystore.load_key(create=True)
    entry = job.facts()["screen.ssa1099"]
    ledger.record(path, key, job.job_id(), [("screen.ssa1099", entry, "yes")], K.PERSON)
    ledger.record(path, key, job.job_id(), [("screen.ssa1099", entry, "no")], K.PERSON)
    assert states(path)["screen.ssa1099"] == "no"


def test_a_non_ascii_mac_confirms_nothing_and_breaks_nothing(tmp_path, test_keychain):
    # second-F6: a bad ledger means unconfirmed, never an error.
    path, _ = job_with_facts(tmp_path)
    keystore.load_key(create=True)  # with no key the ledger is never read
    entry = cli.Job(path).facts()["screen.ssa1099"]
    (path / ledger.NAME).write_text(json.dumps({"entries": [{"fact": "screen.ssa1099", "value": entry["value"],
        "source": entry["source"], "answer": "yes", "by": K.PERSON, "mac": "\u00e9"}]}), encoding="utf-8")
    assert states(path)["screen.ssa1099"] == ""
    code, out = runner.caesar(path, "status")
    assert code == 0 and "NEXT: " in out


def test_no_keychain_means_nothing_signed(tmp_path):
    path, server = job_with_facts(tmp_path)
    with runner.scripted_person({"screen.ssa1099": "no", "screen.1099r": "no"}, path):
        # Inside the seam, take the keychain away again.
        keystore.load_key = lambda create, service=keystore.SERVICE: (None, "secret-tool is not installed")
        out = confirm(server, path)
    assert "No keychain: secret-tool is not installed" in out and "every fact stays unconfirmed" in out
    assert set(states(path).values()) == {""} and not (path / ledger.NAME).exists()
    assert "confirm_hash" not in cli.Job(path).state()  # nobody was asked, so confirm stays the next step


def test_the_scripted_person_is_reached_only_in_process(tmp_path, monkeypatch):
    # #9 first-F1: the old variable turns nothing on, and with no channel confirm records nothing.
    path, server = job_with_facts(tmp_path)
    truth = tmp_path / "person.json"
    truth.write_text(json.dumps({"facts": {"screen.ssa1099": "no", "screen.1099r": "no"}}), encoding="utf-8")
    monkeypatch.setenv("CAESAR_SCRIPTED_PERSON", str(truth))
    code, out = runner.caesar(path, "confirm")
    assert "records no confirmation" in out and set(states(path).values()) == {""}
    with runner.scripted_person({"screen.ssa1099": "no", "screen.1099r": "no"}, path):
        assert "2 confirmed, 0 rejected" in confirm(server, path)
        assert set(states(path).values()) == {"yes"}


# -- SPEC golden case -------------------------------------------------------------

def test_golden_model_edits_facts_toml_to_set_a_flag(tmp_path):
    result = runner.run(FOLDER, scripted=False, workdir=tmp_path)
    path = result["job"]
    assert result["state"]["final"] == "computed, not confirmed"
    facts_file = path / "facts.toml"
    facts_file.write_text(facts_file.read_text(encoding="utf-8").replace(
        'confirmed = ""\nby = ""', 'confirmed = "yes"\nby = "the person, in Local Studio"'), encoding="utf-8")
    # And a ledger the model wrote itself: a made-up signature, and one under a key it made.
    job = cli.Job(path)
    own_key = secrets.token_bytes(32)
    forged = [{"fact": n, "value": e["value"], "source": e["source"], "answer": "yes", "by": K.PERSON, "at": "",
               "mac": ledger.signed(own_key, job.job_id(), n, e["value"], e["source"], "yes", K.PERSON)}
              for n, e in job.facts().items()]
    forged.append(dict(forged[0], mac="0" * 64))
    (path / ledger.NAME).write_text(json.dumps({"entries": forged}), encoding="utf-8")
    keystore.load_key(create=True)
    for step in ("status", "compute", "check", "worksheet", "done"):
        code, out = runner.caesar(path, step)
        assert code in (0, 1), out
    assert json.loads((path / "state.json").read_text(encoding="utf-8"))["final"] == "computed, not confirmed"
    assert "State: computed, not confirmed." in out


# -- the keychain ------------------------------------------------------------------

def forget(service):
    keystore._cache.pop(service, None)
    if sys.platform == "darwin":
        subprocess.run(["/usr/bin/security", "delete-generic-password", "-s", service, "-a", keystore.ACCOUNT],
                       capture_output=True)
    elif sys.platform.startswith("linux") and shutil.which("secret-tool"):
        subprocess.run(["secret-tool", "clear", "service", service, "account", keystore.ACCOUNT], capture_output=True)
    elif sys.platform == "win32":
        try:
            keystore.dpapi_file(service).unlink(missing_ok=True)
        except keystore.NoKeychain:
            pass


def test_the_keychain_keeps_the_ledger_key():
    service = "UntoCaesar-test-" + secrets.token_hex(4)
    try:
        assert REAL_LOAD_KEY(create=False, service=service)[0] is None
        key, why = REAL_LOAD_KEY(create=True, service=service)
        if sys.platform in ("darwin", "win32"):
            assert key is not None, why
        if key is None:
            assert why, "no key needs a reason the reply can give"
            return
        assert len(key) == 32
        keystore._cache.pop(service, None)
        assert REAL_LOAD_KEY(create=False, service=service) == (key, "")
    finally:
        forget(service)


def test_no_secret_tool_means_no_key(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setattr(shutil, "which", lambda name: None)
    service = "UntoCaesar-test-none"
    keystore._cache.pop(service, None)
    assert REAL_LOAD_KEY(create=True, service=service) == (None, "secret-tool is not installed, so there is no keychain")
