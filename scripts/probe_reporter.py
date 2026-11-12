#!/usr/bin/env python3
"""Exercise reporter callbacks in an owned hc core, without launching an agent."""
# pattern: Imperative Shell
from contextlib import contextmanager
import argparse
import json
import os
from pathlib import Path
import socket
import shutil
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from polytoken_herdr.reporter import reporter_environment
from probe_capture import Capture
from probe_cleanup import cleanup_actions


def emit(control: str) -> None:
    """Run callbacks with null streams and a changed cwd in an owned terminal."""
    connection = socket.socket(socket.AF_UNIX)
    connection.connect(control)
    stream = connection.makefile("rwb", buffering=0)
    env = reporter_environment(dict(os.environ), str(Path(control).parent / "sessions"))
    os.chdir("/")
    for state in ("working", "idle", "blocked", "clear"):
        args = ["release-agent"] if state == "clear" else [
            "report-agent", "--source", "polytoken", "--agent", "polytoken",
            "--state", state, "--seq", "1", "--agent-session-id", "probe-session"]
        if state == "working":
            os.write(1, b"\x1b[31")  # Deliberately split a TUI CSI across the callback write.
        result = subprocess.run([env["HERDR_BIN_PATH"], "pane", *args], env=env,
                                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=5, check=False)
        if state == "working":
            os.write(1, b"mSPLIT-CSI-CHECK\x1b[0m\n")
        stream.write((json.dumps({"state": state, "exit": result.returncode}) + "\n").encode())
        if stream.readline() != b"next\n":
            raise RuntimeError("probe control connection closed")
    connection.close()


def default_terminals() -> list[str]:
    """Read only default-core terminal identities, never their contents."""
    env = dict(os.environ, HC_SESSION="default")
    for key in ("HC_SOCKET", "HC_TERMINAL_ID"):
        env.pop(key, None)
    result = subprocess.run(["hc", "ls", "--all", "--json"], env=env,
                            capture_output=True, text=True, timeout=10, check=True)
    data = json.loads(result.stdout)
    records = data if isinstance(data, list) else data.get("terminals", [])
    return sorted(record["address"] for record in records)


@contextmanager
def unchanged_default():
    """Compare default terminal identities even when a private assertion fails."""
    before = default_terminals()
    try:
        yield
    finally:
        after = default_terminals()
        assert before == after, (before, after)
        print("PASS: default session terminal identities unchanged:", json.dumps(after), flush=True)


def probe() -> None:
    """Create a unique isolated core and verify all translated states and release."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, help="Keep append-only per-session evidence here")
    args = parser.parse_args()
    with unchanged_default(), tempfile.TemporaryDirectory(prefix="phcr-", dir="/tmp") as directory:
        root = Path(directory)
        session = "phc-probe-" + uuid.uuid4().hex[:12]
        capture = Capture(session, args.capture_dir)
        env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG", "SHELL", "TMPDIR")}
        env.update(HOME=str(root), HC_SESSION=session, HC_SOCKET=str(root / "core.sock"), TERM="xterm-256color")
        for kind in ("CONFIG", "DATA", "CACHE", "STATE", "RUNTIME"):
            path = root / kind.lower()
            path.mkdir(mode=0o700)
            env[f"XDG_{kind}_HOME" if kind != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
        (root / "config/herdr-core").mkdir()
        (root / "config/herdr-core/config.toml").write_text('notes = false\n')
        owned = set()
        started = False

        def hc(*args: str, check: bool = True) -> subprocess.CompletedProcess:
            if env.get("HC_SESSION") != session or not session.startswith("phc-probe-"):
                raise RuntimeError("lost private hc session binding")
            if args[0] in ("kill", "rm", "send") and (len(args) < 2 or args[1] not in owned):
                raise RuntimeError("refusing to drive an unowned terminal")
            return subprocess.run(["hc", *args], env=env, cwd=root, text=True,
                                  capture_output=True, timeout=15, check=check)

        listener = socket.socket(socket.AF_UNIX)
        listener.settimeout(15)
        control = str(root / "control.sock")
        listener.bind(control)
        listener.listen(1)
        try:
            started = True  # Also clean up a start interrupted after provisioning.
            hc("server", "start")
            if shutil.which("herdr-app"):
                checked = subprocess.run(["herdr-app", "check", str(ROOT / "mods/polytoken")],
                                         env=env, cwd=root, capture_output=True, text=True, timeout=15, check=True)
                print("mod check:", checked.stdout.strip(), flush=True)
            result = hc("run", "--bg", "--json", "--no-parent", "--no-notify", "--name", "callback-probe",
                        sys.executable, str(Path(__file__).resolve()), "--proxy-emit", control)
            record = json.loads(result.stdout)
            identifier = record["address"]
            owned.add(identifier)
            capture.write("terminal_created", terminal=identifier)
            print("session:", session, "terminal:", identifier, flush=True)
            connection, _ = listener.accept()
            connection.settimeout(10)
            with connection, connection.makefile("rwb", buffering=0) as stream:
                for expected in ("working", "idle", "blocked", "clear"):
                    emitted = json.loads(stream.readline())
                    assert emitted == {"state": expected, "exit": 0}, emitted
                    record = json.loads(hc("get", identifier).stdout)
                    status = record.get("status")
                    capture.write("observed", expected=expected, status=status)
                    assert status == (None if expected == "clear" else {"app": "polytoken", "state": expected}), record
                    if expected == "working":
                        screen = hc("read", identifier, "--lines", "0").stdout
                        assert "SPLIT-CSI-CHECK" in screen and "mSPLIT-CSI-CHECK" not in screen, screen
                        print("PASS: deliberately split CSI survived callback output", flush=True)
                    if expected != "clear":
                        assert record["labels"]["polytoken.session"] == "probe-session", record
                    print("PASS:", expected, "observed through hc get; callback streams were null", flush=True)
                    stream.write(b"next\n")
            hc("wait", identifier, "--timeout", "5")
        finally:
            actions = [listener.close]
            for identifier in owned:
                actions += [lambda identifier=identifier: hc("kill", identifier, check=False),
                            lambda identifier=identifier: hc("rm", identifier, check=False)]
            if started:
                actions += [lambda: hc("server", "stop")]
            cleanup_actions(actions)
            capture.write("cleanup_complete")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--proxy-emit"]:
        from polytoken_herdr.output import terminal_output
        from polytoken_herdr.proxy import run_proxy
        from polytoken_herdr.stream import SerializedOutput
        with terminal_output() as sink:
            raise SystemExit(run_proxy([sys.executable, str(Path(__file__).resolve()), "--emit", sys.argv[2]],
                                       dict(os.environ), SerializedOutput(sink)))
    elif sys.argv[1:2] == ["--emit"]:
        emit(sys.argv[2])
    else:
        probe()
