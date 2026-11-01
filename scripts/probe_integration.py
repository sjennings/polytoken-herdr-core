#!/usr/bin/env python3
"""Launch real Polytoken in isolated hc, without credentials or approvals."""
import argparse
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
from polytoken_herdr.config import prepare, prepare_global
from polytoken_herdr.launcher import launch_command
from probe_polytoken import Provider
from probe_profile import prepare_profile
from probe_processes import descendants, assert_exited


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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--interactive", action="store_true",
                        help="Attach the human directly to the scratch terminal before checking status")
    parser.add_argument("--question", action="store_true",
                        help="After ordinary input, check a real blocked question and let the human reattach")
    parser.add_argument("--global", dest="global_config", action="store_true",
                        help="Test user hooks inside the isolated test profile")
    parser.add_argument("--profile", help="Reuse a dedicated test HOME; creates a new marked directory on first use")
    args = parser.parse_args()
    if args.question and not args.interactive:
        parser.error("--question requires --interactive")
    if args.interactive and not sys.stdin.isatty():
        parser.error("--interactive requires a human terminal")
    with tempfile.TemporaryDirectory(prefix="phi-", dir="/tmp") as directory:
        root = Path(directory)
        env = {key: value for key, value in os.environ.items()
               if key in ("PATH", "LANG", "SHELL", "TMPDIR")}
        home = prepare_profile(args.profile) if args.profile else root
        env.update(HOME=str(home), TERM="xterm-256color", HC_SESSION="probe-" + uuid.uuid4().hex[:8])
        for kind in ("CONFIG", "STATE", "DATA", "CACHE", "RUNTIME"):
            path = (root if kind == "RUNTIME" else home) / kind.lower()
            path.mkdir(mode=0o700, exist_ok=True)
            env[f"XDG_{kind}_HOME" if kind != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        started = False
        launched = False

        def hc(*args, check=True):
            return subprocess.run(["hc", *args], env=env, text=True, capture_output=True,
                                  timeout=30, check=check)

        try:
            project = root / "project"
            project.mkdir()
            config_dir = Path(env["XDG_CONFIG_HOME"]) / "polytoken" if args.global_config else project / ".polytoken"
            if args.global_config:
                prepare_global(config_dir)
            else:
                prepare(config_dir)
            config = json.loads((Path(__file__).resolve().parents[1] /
                                 "tests/fixtures/polytoken/config.json").read_text())
            config["providers"]["local-probe"]["url"] = f"http://127.0.0.1:{server.server_port}/v1"
            (config_dir / "config.json").write_text(json.dumps(config))
            hc("server", "start")
            started = True
            if args.global_config:
                # Validate inside a process with the isolated environment, not
                # against the caller's real global configuration.
                entry = Path(__file__).resolve().parents[1] / "polytoken_herdr" / "entry.py"
                command = [sys.executable, str(entry), "launch", "--global", "--name", "integration",
                           "--cwd", str(project), "--model", "local-probe", "--prompt", "Reply OK"]
            else:
                command = launch_command("integration", project, config_dir, "local-probe", "Reply OK")
            result = subprocess.run(command, env=env, text=True, capture_output=True, timeout=30, check=True)
            launched = True
            print("launch:", result.stdout, flush=True)
            if args.interactive:
                print("Attaching ONLY to the disposable test terminal. Read and decide on the agreement yourself.")
                print("If you proceed, wait for the mock's OK reply, then detach with Ctrl+\\. Do not quit Polytoken.")
                print("If you reject or cancel, verification will fail and the scratch instance will be cleaned up.", flush=True)
                subprocess.run(["hc", "attach", "integration"], env=env, check=True)
            waited = hc("wait", "integration", "--timeout", "15", check=False)
            print("wait:", waited.returncode, waited.stdout, waited.stderr)
            record = json.loads(hc("get", "integration").stdout)
            print("status:", json.dumps({key: record.get(key) for key in ("state", "status", "turn", "exit_code")}))
            print("screen (diagnostic only):", hc("read", "integration", "--lines", "30").stdout)
            assert (record.get("status") or {}).get("state") == "idle", "No idle hook status; startup may require a human (see diagnostic screen)"
            assert record.get("turn", 0) >= 1, "No working-to-idle transition observed"
            print("PASS: real launcher, hooks, relay and hc status")
            verify_followup(hc, record["turn"])
            if args.question:
                server.ask_question = True
                verify_question(hc)
                print("Reattaching to the test question. Leave it unanswered; detach with Ctrl+\\ when you have inspected it.", flush=True)
                subprocess.run(["hc", "attach", "integration"], env=env, check=True)
            before_shutdown = json.loads(hc("get", "integration").stdout)
            owned_pid = before_shutdown["pid"]
            observed = descendants(owned_pid) | {owned_pid}
            print("Observed probe process count:", len(observed))
            verify_shutdown(hc)
            assert_exited(observed)
        finally:
            if launched:
                hc("kill", "integration", check=False)
                hc("rm", "integration", check=False)
            if started:
                hc("server", "stop")
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
