#!/usr/bin/env python3
"""Launch real Polytoken in isolated hc, without credentials or approvals."""
import argparse
import shlex
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import uuid
from http.server import ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from mock_provider import Provider
from probe_profile import prepare_profile
from probe_reporter import unchanged_default
from probe_capture import Capture
from probe_cleanup import cleanup_actions, shutdown_registry
from polytoken_herdr.launcher import termination_cleanup, wait_for_tui


def verify_followup(hc, previous_turn):
    sent = hc("send", "integration", "Reply OK again", "--if", "idle", "--wait", "--timeout", "15")
    print("followup:", sent.stdout)
    record = json.loads(hc("get", "integration").stdout)
    assert record.get("turn", 0) > previous_turn, "Followup did not complete a new turn"
    assert record.get("state") == "live", "Followup exited the TUI"
    assert record.get("status") == {"app": "polytoken", "state": "idle"}, "Followup did not return idle"
    print("PASS: ordinary hc send completed a new idle turn")


def verify_question(hc):
    hc("send", "integration", "Ask the test question", "--if", "idle", "--wait", "--timeout", "15")
    record = json.loads(hc("get", "integration").stdout)
    assert record.get("status") == {"app": "polytoken", "state": "blocked"}, "Question did not report blocked"
    refused = hc("send", "integration", "must not arrive", check=False)
    assert refused.returncode == 9, "hc did not refuse blocked input"
    print("PASS: real question reported blocked and ordinary input was refused")


def verify_shutdown(hc):
    hc("kill", "integration")
    record = json.loads(hc("get", "integration").stdout)
    print("shutdown:", json.dumps(record))
    assert record.get("state") == "finished", "Managed terminal is still live after hc kill"
    print("PASS: hc termination finished the managed terminal (not a descendant cleanup assertion)")


@termination_cleanup()
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path)
    parser.add_argument("--profile", help="Dedicated profile whose agreement the human already decided")
    parser.add_argument("--global", dest="global_config", action="store_true")
    parser.add_argument("--question", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    args = parser.parse_args()
    if args.interactive and not sys.stdin.isatty():
        parser.error("--interactive requires a human terminal")
    with unchanged_default(), tempfile.TemporaryDirectory(prefix="phi-", dir="/tmp") as directory:
        root = Path(directory)
        env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG", "SHELL", "TMPDIR")}
        home = prepare_profile(args.profile) if args.profile else root
        session = "probe-" + uuid.uuid4().hex[:12]
        capture = Capture(session, args.capture_dir)
        env.update(HOME=str(home), TERM="xterm-256color", HC_SESSION=session, HC_SOCKET=str(root / "core.sock"))
        for kind in ("CONFIG", "STATE", "DATA", "CACHE", "RUNTIME"):
            path = (root if kind == "RUNTIME" else home) / kind.lower()
            path.mkdir(mode=0o700, exist_ok=True)
            env[f"XDG_{kind}_HOME" if kind != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = False
        launched = False

        def hc(*arguments, check=True):
            if env.get("HC_SESSION") != session or not session or session == "default":
                raise RuntimeError("lost private core binding")
            if arguments[0] in ("kill", "rm", "send") and (not launched or arguments[1] != "integration"):
                raise RuntimeError("refusing an unowned terminal")
            return subprocess.run(["hc", *arguments], env=env, cwd=root, text=True,
                                  capture_output=True, timeout=30, check=check)

        def status(phase, expected):
            record = json.loads(hc("get", "integration").stdout)
            capture.write(phase, status=record.get("status"), turn=record.get("turn"), labels=record.get("labels"))
            assert record.get("status") == expected, (phase, record.get("status"))
            print("PASS:", phase, record.get("status"), flush=True)
            return record

        def shell_command(arguments, attach=False):
            hc("send", "integration", shlex.join(arguments))
            if attach:
                print("Decide startup yourself, wait for OK, then detach Ctrl+\\.", flush=True)
                wait_for_tui(["hc", "attach", "integration"], env)
            hc("wait", "integration", "--timeout", "10", check=False)

        try:
            config_dir = Path(env["XDG_CONFIG_HOME"]) / "polytoken"
            config_dir.mkdir(exist_ok=True)
            config = json.loads((Path(__file__).resolve().parents[1] / "tests/fixtures/polytoken/config.json").read_text())
            config["updates"] = {"automatic_check": False}
            config["providers"]["local-probe"]["url"] = f"http://127.0.0.1:{server.server_port}/v1"
            (config_dir / "config.json").write_text(json.dumps(config))
            started = True
            hc("server", "start")
            hc("run", "--bg", "--name", "integration", "--cwd", str(root), "/bin/sh")
            launched = True
            capture.write("terminal_created", terminal="integration")
            entry = Path(__file__).resolve().parents[1] / "polytoken_herdr/entry.py"
            # Explicit caller-owned registry keeps this probe in sole charge of cleanup.
            shell_command([sys.executable, str(entry), "run", "--global", "--sessions-dir", str(root / "sessions"),
                           "--model", "local-probe", "--prompt", "Reply OK"], attach=args.interactive)
            idle = {"app": "polytoken", "state": "idle"}
            initial = status("native_start", idle)
            identifier = initial["labels"]["polytoken.session"]
            verify_followup(hc, initial["turn"])
            # A CLI detach is ordinary user input from idle, never an answer to a dialog.
            hc("send", "integration", "/detach", "--if", "idle")
            hc("wait", "integration", "--output", "PROBE_RELEASE", "--timeout", "3", check=False)
            status("native_release", None)
            # Same terminal, retained labels: this executes the actual public restore path.
            shell_command([sys.executable, str(entry), "restore"])
            restored = status("native_restore", idle)
            assert restored["labels"]["polytoken.session"] == identifier, "restored a different native session"
            verify_followup(hc, restored["turn"])
            if args.question:
                server.ask_question = True
                verify_question(hc)
                status("native_question", {"app": "polytoken", "state": "blocked"})
                if args.interactive:
                    print("Inspect the pending test question and detach Ctrl+\\. No answer is sent by the probe.", flush=True)
                    subprocess.run(["hc", "attach", "integration"], env=env, check=True)
            verify_shutdown(hc)
            print("PASS: stock start, release, native restore and ordinary follow-up through the public adapter", flush=True)
        finally:
            actions = []
            if launched:
                actions += [lambda: hc("kill", "integration", check=False), lambda: hc("rm", "integration", check=False)]
            actions += [lambda: shutdown_registry(root)]
            if started:
                actions += [lambda: hc("server", "stop")]
            actions += [server.shutdown, server.server_close, thread.join]
            cleanup_actions(actions)
            capture.write("cleanup_complete")


if __name__ == "__main__":
    main()
