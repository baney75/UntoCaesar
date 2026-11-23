"""Only the person confirms: the peer checks, the signed ledger, the keychain and the SPEC golden cases."""

import json
import os
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

import pytest
import runner
from conftest import REAL_LOAD_KEY

from caesar import ask, cli, keystore, ledger, mcp, peer
from caesar import confirm as K

UNIX = hasattr(socket, "AF_UNIX")
needs_unix = pytest.mark.skipif(not UNIX, reason="Local Studio's question socket is Unix only")
FOLDER = runner.CASES / "single-w2"


@pytest.fixture(autouse=True)
def caesar_cmd(monkeypatch):
    monkeypatch.setenv("CAESAR_CMD", "caesar")


def short_dir():
    # A Unix socket path must stay short; macOS temp folders are long.
    return tempfile.mkdtemp(prefix="ls", dir="/tmp" if os.path.isdir("/tmp") else None)


class FakeLocalStudio:
    """A question socket in this test process. reply(request) gives the answer line, or None to close."""

    def __init__(self, reply):
        self.dir = short_dir()
        self.path = os.path.join(self.dir, "ask.sock")
        self.reply = reply
        self.received = []
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(self.path)
        self.sock.listen()
        threading.Thread(target=self.serve, daemon=True).start()

    def serve(self):
        while True:
            try:
                conn, _ = self.sock.accept()
            except OSError:
                return
            with conn:
                data = b""
                while not data.endswith(b"\n"):
                    chunk = conn.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                self.received.append(data)
                answer = self.reply(json.loads(data)) if data else None
                if answer is not None:
                    conn.sendall((json.dumps(answer) + "\n").encode())

    def close(self):
        self.sock.close()
        shutil.rmtree(self.dir, ignore_errors=True)


@pytest.fixture
def studio(monkeypatch):
    made = []

    def start(reply, pid=None, trust_this_process=True):
        fake = FakeLocalStudio(reply)
        made.append(fake)
        monkeypatch.setenv("LOCAL_STUDIO_ASK", fake.path)
        monkeypatch.setenv("LOCAL_STUDIO_ASK_TOKEN", "a" * 64)
        monkeypatch.setenv("LOCAL_STUDIO_ASK_PID", str(os.getpid() if pid is None else pid))
        monkeypatch.setenv("LOCAL_STUDIO_THREAD", "thread-1")
        if trust_this_process:
            monkeypatch.setattr(peer, "installed_apps", lambda: [os.path.realpath(peer.exe_of(os.getpid()))])
        return fake

    yield start
    for fake in made:
        fake.close()


def settled(fake, n):
    """The fake records a connection only once it has read to the end; wait for n of them."""
    deadline = time.monotonic() + 5
    while len(fake.received) < n and time.monotonic() < deadline:
        time.sleep(0.01)
    return fake.received


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


# -- the peer checks -----------------------------------------------------------

@needs_unix
def test_a_peer_with_the_wrong_pid_gets_nothing(studio, tmp_path):
    fake = studio(lambda r: {"status": "answered", "answer": "Yes"}, pid=os.getpid() + 100000)
    reply = ask.ask("Is this right?", ["Yes", "No"])
    assert reply["status"] == "refused" and "not Local Studio's" in reply["error"]
    path, server = job_with_facts(tmp_path)
    out = confirm(server, path)
    assert "question card was not reached" in out
    assert settled(fake, 2) == [b"", b""], "the token went to a socket served by another pid"
    assert set(states(path).values()) == {""}


@needs_unix
def test_a_peer_that_is_not_the_installed_app_gets_nothing(studio, tmp_path):
    fake = studio(lambda r: {"status": "answered", "answer": "Yes"}, trust_this_process=False)
    reply = ask.ask("Is this right?", ["Yes", "No"])
    assert reply["status"] == "refused"
    assert "not the installed Local Studio app" in reply["error"] or "no installed Local Studio app" in reply["error"]
    path, server = job_with_facts(tmp_path)
    confirm(server, path)
    assert settled(fake, 2) == [b"", b""]
    assert set(states(path).values()) == {""}


@needs_unix
@pytest.mark.parametrize("answer", [{"status": "refused", "error": "unknown token"}, {"status": "cancelled"}, None,
                                    {"status": "answered", "answer": "maybe"}, {"status": "answered", "answer": 1}])
def test_refused_cancelled_or_odd_answers_confirm_nothing(studio, tmp_path, answer):
    studio(lambda r: answer)
    path, server = job_with_facts(tmp_path)
    out = confirm(server, path)
    assert "Asked the person, in Local Studio about 0 of 2 facts" in out
    assert set(states(path).values()) == {""}
    assert not (path / ledger.NAME).exists()


@needs_unix
def test_the_person_answers_through_the_card(studio, tmp_path):
    # The control for the tests above: the same fake, trusted and answering, does confirm.
    fake = studio(lambda r: {"status": "answered", "answer": "No" if "1099r" in r["text"] else "Yes"})
    path, server = job_with_facts(tmp_path)
    out = confirm(server, path)
    assert "1 confirmed, 1 rejected" in out
    assert states(path) == {"screen.ssa1099": "yes", "screen.1099r": "no"}
    assert {e["by"] for e in cli.Job(path).facts().values()} == {K.PERSON}
    request = json.loads(fake.received[0])
    assert set(request) == {"token", "thread", "text", "choices"} and request["choices"] == ["Yes", "No"]
    assert request["thread"] == "thread-1" and "screen.1099r = no (source: answer)" in fake.received[0].decode()


@needs_unix
def test_no_keychain_means_no_question_and_nothing_signed(studio, tmp_path, monkeypatch):
    fake = studio(lambda r: {"status": "answered", "answer": "Yes"})
    monkeypatch.setattr(keystore, "load_key", lambda create, service=keystore.SERVICE: (None, "secret-tool is not installed"))
    path, server = job_with_facts(tmp_path)
    out = confirm(server, path)
    assert "No keychain: secret-tool is not installed" in out and "every fact stays unconfirmed" in out
    assert fake.received == [] and set(states(path).values()) == {""}


def test_no_ask_variables_means_no_person_channel():
    assert isinstance(K.channel(), K.NoPersonChannel)
    assert ask.ask("Is this right?", ["Yes", "No"])["status"] == "refused"


def test_exe_of_reads_this_process():
    exe = peer.exe_of(os.getpid())
    assert exe and os.path.isfile(exe)
    assert peer.exe_of(2**31 - 4) is None
    ok, why = peer.is_installed_app(os.getpid())
    assert not ok and why


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


def test_no_keychain_means_nothing_signed_on_any_system(tmp_path):
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


# -- SPEC golden cases -------------------------------------------------------------

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


LISTENER = r"""
import socket, sys
path, log = sys.argv[1], sys.argv[2]
s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
s.bind(path)
s.listen()
print("ready", flush=True)
while True:
    c, _ = s.accept()
    data = b""
    while not data.endswith(b"\n"):
        chunk = c.recv(4096)
        if not chunk:
            break
        data += chunk
    with open(log, "ab") as f:
        f.write(data)
    try:
        c.sendall(b'{"status": "answered", "answer": "Yes"}\n')
    except OSError:
        pass
    c.close()
"""


@needs_unix
def test_golden_model_starts_its_own_listener_and_calls_confirm(tmp_path, monkeypatch):
    where = short_dir()
    sock, log = os.path.join(where, "ask.sock"), tmp_path / "heard.bin"
    log.write_bytes(b"")
    listener = subprocess.Popen([sys.executable, "-c", LISTENER, sock, str(log)], stdout=subprocess.PIPE, text=True)
    try:
        assert listener.stdout.readline().strip() == "ready"
        monkeypatch.setenv("LOCAL_STUDIO_ASK", sock)
        monkeypatch.setenv("LOCAL_STUDIO_ASK_TOKEN", "b" * 64)
        monkeypatch.setenv("LOCAL_STUDIO_ASK_PID", str(listener.pid))
        assert isinstance(K.channel(), K.LocalStudio)
        # The whole case, with confirm reaching the model's listener through the real channel.
        result = runner.run(FOLDER, scripted=False, workdir=tmp_path / "run")
        assert "question card was not reached" in result["output"]
        assert "not the installed Local Studio app" in result["output"] or "no installed Local Studio app" in result["output"]
        assert result["state"]["final"] == "computed, not confirmed"
        # And confirm called again as the MCP tool, the way a launched caesar-mcp would.
        out = confirm(mcp.Server(local_only=True, root=tmp_path / "outside"), result["job"])
        assert "about 0 of" in out
        code, out = runner.caesar(result["job"], "done")
        assert "State: computed, not confirmed." in out
        time.sleep(0.2)
        assert log.read_bytes() == b"", "the model's listener heard a question"
    finally:
        listener.kill()
        listener.wait()
        shutil.rmtree(where, ignore_errors=True)


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
