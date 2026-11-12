#!/usr/bin/env python3
"""Observe stock Polytoken callbacks without accepting agreements or decisions."""
# pattern: Imperative Shell
from contextlib import contextmanager
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import shutil
import threading
import uuid
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from polytoken_herdr.launcher import termination_cleanup, wait_for_tui
from polytoken_herdr.reporter import reporter_environment
from polytoken_herdr.output import terminal_output
from polytoken_herdr.stream import SerializedOutput
from polytoken_herdr.proxy import run_proxy
from mock_provider import Provider
from probe_reporter import unchanged_default
from probe_profile import prepare_profile
from probe_capture import Capture
from probe_cleanup import shutdown_registry, cleanup_actions


@contextmanager
def scratch_directory():
    root = Path(tempfile.mkdtemp(prefix="phcs-", dir="/tmp"))
    try:
        yield root
    except BaseException:
        print("Probe failed; private registry retained for inspection:", root, flush=True)
        raise
    else:
        shutil.rmtree(root)


def launch_stock_child(sessions: Path, recorder: Path) -> int:
    """Run the stock TUI only inside this probe's explicitly private core."""
    if (not os.environ.get("HC_SESSION", "").startswith("phc-stock-")
            or not os.environ.get("HC_TERMINAL_ID")
            or Path(os.environ.get("HC_SOCKET", "/")).parent.resolve() != sessions.parent.resolve()):
        raise ValueError("stock child requires its owned probe core and registry")
    env = reporter_environment(dict(os.environ), str(sessions))
    env["HERDR_BIN_PATH"] = str(recorder.resolve())
    with terminal_output() as sink:
        return run_proxy(["polytoken", "new", "--sessions-dir", str(sessions),
                          "--model", "local-probe", "--prompt", "Reply OK"],
                         env, SerializedOutput(sink))


@termination_cleanup()
def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human", action="store_true", help="One-command agreement, status and question check")
    parser.add_argument("--capture-dir", type=Path, help="Keep unique append-only evidence files here (default: private /tmp directory)")
    parser.add_argument("--interactive", action="store_true", help="Attach a human to decide the agreement")
    parser.add_argument("--question", action="store_true", help="After initial idle, request one unanswered test question")
    parser.add_argument("--profile", help="New or probe-marked private profile retaining only human choices")
    args = parser.parse_args()
    if args.human:
        args.interactive = args.question = True
    if args.question and not args.interactive:
        parser.error("--question requires --interactive")
    if args.interactive and not sys.stdin.isatty():
        parser.error("--interactive requires a human terminal")
    with unchanged_default(), scratch_directory() as directory:
        root = Path(directory)
        session = "phc-stock-" + uuid.uuid4().hex[:12]
        capture = Capture(session, args.capture_dir)
        env = {key: value for key, value in os.environ.items() if key in ("PATH", "LANG", "SHELL", "TMPDIR")}
        home = prepare_profile(args.profile) if args.profile else root
        env.update(HOME=str(home), HC_SESSION=session, HC_SOCKET=str(root / "core.sock"), TERM="xterm-256color")
        for kind in ("CONFIG", "DATA", "CACHE", "STATE", "RUNTIME"):
            path = (root if kind == "RUNTIME" else home) / kind.lower()
            path.mkdir(mode=0o700, exist_ok=True)
            env[f"XDG_{kind}_HOME" if kind != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
        (home / "config/herdr-core").mkdir(exist_ok=True)
        (home / "config/herdr-core/config.toml").write_text('notes = false\n')
        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        config = json.loads((ROOT / "tests/fixtures/polytoken/config.json").read_text())
        config["updates"] = {"automatic_check": False}
        config["providers"]["local-probe"]["url"] = f"http://127.0.0.1:{server.server_port}/v1"
        config_dir = home / "config/polytoken"
        config_dir.mkdir(exist_ok=True)
        (config_dir / "config.json").write_text(json.dumps(config))
        callback_log = capture.path.with_suffix(".callbacks.jsonl")
        with callback_log.open("x"):
            callback_log.chmod(0o600)
        recorder = root / "recorder"
        recorder.write_text("#!/usr/bin/env python3\nimport json, os, subprocess, sys\n"
                            f"result = subprocess.run([{str(ROOT / 'bin/polytoken-herdr')!r}, *sys.argv[1:]], stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)\n"
                            f"record = dict(session={session!r}, argv=sys.argv[1:], exit=result.returncode, stderr=result.stderr[:4096], binding={{key:os.environ.get(key) for key in ('HC_TERMINAL_ID','HERDR_PANE_ID','POLYTOKEN_HERDR_REPORTER','HC_SESSION')}})\n"
                            f"with open({str(callback_log)!r}, 'a') as output: output.write(json.dumps(record) + '\\n')\n"
                            "raise SystemExit(result.returncode)\n")
        recorder.chmod(0o700)
        owned = set()
        started = False

        def hc(*args: str, check: bool = True) -> subprocess.CompletedProcess:
            if env.get("HC_SESSION") != session or not session.startswith("phc-stock-"):
                raise RuntimeError("lost private hc session binding")
            if args[0] in ("kill", "rm", "send", "keys") and (len(args) < 2 or args[1] not in owned):
                raise RuntimeError("refusing to drive an unowned terminal")
            return subprocess.run(["hc", *args], env=env, cwd=root, text=True,
                                  capture_output=True, timeout=20, check=check)

        try:
            started = True  # Also clean up a start interrupted after provisioning.
            hc("server", "start")
            launched = json.loads(hc("run", "--bg", "--json", "--no-parent", "--no-notify",
                                     sys.executable, str(Path(__file__).resolve()), "--child",
                                     str(root / "sessions"), str(recorder)).stdout)
            terminal = launched["address"]
            owned.add(terminal)
            capture.write("terminal_created", terminal=terminal)
            print("session:", session, "terminal:", terminal, flush=True)
            if args.interactive:
                print("1/2: Read and decide the agreement yourself. Wait for OK, then detach with Ctrl+\\.\nReject, quit the TUI, or press Ctrl+C to stop the check; cleanup runs automatically.", flush=True)
                if env.get("HC_SESSION") != session or terminal not in owned:
                    raise RuntimeError("refusing an unowned attachment")
                wait_for_tui(["hc", "attach", terminal], env)
            waited = hc("wait", terminal, "--timeout", "3", check=False)
            if not args.interactive:
                print("wait:", waited.returncode, waited.stdout.strip(), flush=True)
                print("screen:", hc("read", terminal, "--lines", "0").stdout, flush=True)
            record = json.loads(hc("get", terminal).stdout)
            print("status:", json.dumps(record.get("status")), flush=True)
            capture.write("initial_status", status=record.get("status"))
            if record.get("status") != {"app": "polytoken", "state": "idle"}:
                capture.write("incomplete", reason="initial idle not observed")
                print("INCOMPLETE: initial idle was not observed. Cleaning up this probe.", flush=True)
                return 2
            if args.question:
                server.ask_question = True
                hc("send", terminal, "Ask the isolated test question", "--if", "idle", "--wait", "--timeout", "10")
                question = json.loads(hc("get", terminal).stdout)
                capture.write("question_status", status=question.get("status"))
                print("question status:", json.dumps(question.get("status")), flush=True)
                assert question.get("status") == {"app": "polytoken", "state": "blocked"}, question
                print("2/2: Inspect the test question, then detach with Ctrl+\\. You may leave it unanswered.\nThe check will then close its own terminal and daemon.", flush=True)
                if env.get("HC_SESSION") != session or terminal not in owned:
                    raise RuntimeError("refusing an unowned attachment")
                wait_for_tui(["hc", "attach", terminal], env)
            print("The probe never supplies an agreement, permission or question answer.", flush=True)
        finally:
            actions = []
            for terminal in owned:
                actions += [lambda terminal=terminal: hc("kill", terminal, check=False),
                            lambda terminal=terminal: hc("rm", terminal, check=False)]
            actions += [lambda: shutdown_registry(root)]
            if started:
                actions += [lambda: hc("server", "stop")]
            actions += [server.shutdown, server.server_close, thread.join]
            try:
                cleanup_actions(actions)
            finally:
                capture.write("callbacks_recorded", path=str(callback_log))
                print("Callback evidence:", callback_log, flush=True)
            capture.write("cleanup_complete")
            print("Cleanup complete for", session, "— evidence:", capture.path, flush=True)
        return 0


if __name__ == "__main__":
    if sys.argv[1:2] == ["--child"]:
        raise SystemExit(launch_stock_child(Path(sys.argv[2]), Path(sys.argv[3])))
    raise SystemExit(main())
