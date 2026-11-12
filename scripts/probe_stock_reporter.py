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
from polytoken_herdr.reporter import reporter_environment
from mock_provider import Provider
from probe_reporter import unchanged_default
from probe_profile import prepare_profile


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactive", action="store_true", help="Attach a human to decide the agreement")
    parser.add_argument("--question", action="store_true", help="After initial idle, request one unanswered test question")
    parser.add_argument("--profile", help="New or probe-marked private profile retaining only human choices")
    args = parser.parse_args()
    if args.question and not args.interactive:
        parser.error("--question requires --interactive")
    if args.interactive and not sys.stdin.isatty():
        parser.error("--interactive requires a human terminal")
    with unchanged_default(), scratch_directory() as directory:
        root = Path(directory)
        session = "phc-stock-" + uuid.uuid4().hex[:12]
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
        callback_log = root / "callbacks.jsonl"
        callback_log.touch()
        recorder = root / "recorder"
        recorder.write_text("#!/usr/bin/env python3\nimport json, os, sys\n"
                            f"with open({str(callback_log)!r}, 'a') as output: output.write(json.dumps(sys.argv[1:]) + '\\n')\n"
                            f"os.execv({str(ROOT / 'bin/polytoken-herdr')!r}, [{str(ROOT / 'bin/polytoken-herdr')!r}, *sys.argv[1:]])\n")
        recorder.chmod(0o700)
        child = root / "launch.py"
        child.write_text("import os, sys\nfrom pathlib import Path\n"
                         f"sys.path.insert(0, {str(ROOT)!r})\n"
                         "from polytoken_herdr.reporter import reporter_environment\n"
                         "from polytoken_herdr.output import terminal_output\n"
                         "from polytoken_herdr.stream import SerializedOutput\n"
                         "from polytoken_herdr.proxy import run_proxy\n"
                         f"env = reporter_environment(dict(os.environ), {str(root / 'sessions')!r})\n"
                         f"env['HERDR_BIN_PATH'] = {str(recorder)!r}\n"
                         f"with terminal_output() as sink:\n"
                         f"    raise SystemExit(run_proxy(['polytoken', 'new', '--sessions-dir', {str(root / 'sessions')!r}, '--model', 'local-probe', '--prompt', 'Reply OK'], env, SerializedOutput(sink)))\n")
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
            hc("server", "start")
            started = True
            launched = json.loads(hc("run", "--bg", "--json", "--no-parent", "--no-notify",
                                     sys.executable, str(child)).stdout)
            terminal = launched["address"]
            owned.add(terminal)
            print("session:", session, "terminal:", terminal, flush=True)
            if args.interactive:
                print("Human check: decide the agreement yourself, wait for OK, then detach Ctrl+\\.", flush=True)
                if env.get("HC_SESSION") != session or terminal not in owned:
                    raise RuntimeError("refusing an unowned attachment")
                subprocess.run(["hc", "attach", terminal], env=env, cwd=root, check=True)
            waited = hc("wait", terminal, "--timeout", "3", check=False)
            print("wait:", waited.returncode, waited.stdout.strip(), flush=True)
            print("screen:", hc("read", terminal, "--lines", "0").stdout, flush=True)
            print("callbacks:", callback_log.read_text(), flush=True)
            record = json.loads(hc("get", terminal).stdout)
            print("status:", json.dumps(record.get("status")), flush=True)
            if args.question:
                assert record.get("status") == {"app": "polytoken", "state": "idle"}, "initial stock session did not reach idle"
                server.ask_question = True
                hc("send", terminal, "Ask the isolated test question", "--if", "idle", "--wait", "--timeout", "10")
                question = json.loads(hc("get", terminal).stdout)
                print("question status:", json.dumps(question.get("status")), flush=True)
                assert question.get("status") == {"app": "polytoken", "state": "blocked"}, question
                print("Human check: inspect the pending question and detach Ctrl+\\; answering is your choice.", flush=True)
                if env.get("HC_SESSION") != session or terminal not in owned:
                    raise RuntimeError("refusing an unowned attachment")
                subprocess.run(["hc", "attach", terminal], env=env, cwd=root, check=True)
            print("The probe never supplies an agreement, permission or question answer.", flush=True)
        finally:
            for terminal in owned:
                hc("kill", terminal, check=False)
                hc("rm", terminal, check=False)
            print("callbacks after shutdown:", callback_log.read_text(), flush=True)
            # This probe created the registry; reap only it, never the default registry.
            try:
                subprocess.run(["polytoken", "reap", "--sessions-dir", str(root / "sessions")],
                               env=env, cwd=root, stdin=subprocess.DEVNULL, capture_output=True, timeout=20, check=True)
            finally:
                try:
                    if started:
                        hc("server", "stop")
                finally:
                    server.shutdown()
                    server.server_close()
                    thread.join()


if __name__ == "__main__":
    main()
