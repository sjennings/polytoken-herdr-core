#!/usr/bin/env python3
"""Verify installed hc status behavior using a disposable core, never the user's."""
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import uuid


def main():
    hc = shutil.which("hc")
    if hc is None:
        raise SystemExit("hc is required")
    # Keep the socket path short enough for macOS's Unix socket limit.
    with tempfile.TemporaryDirectory(prefix="ph-", dir="/tmp") as directory:
        env = {key: value for key, value in os.environ.items()
               if not key.startswith("HC_")}
        env["HC_SESSION"] = "probe-" + uuid.uuid4().hex[:8]
        for name in ("CONFIG", "STATE", "DATA", "CACHE", "RUNTIME"):
            path = Path(directory) / name.lower()
            path.mkdir(mode=0o700)
            env[f"XDG_{name}_HOME" if name != "RUNTIME" else "XDG_RUNTIME_DIR"] = str(path)

        def call(*args, check=True):
            return subprocess.run([hc, *args], env=env, text=True,
                                  capture_output=True, timeout=20, check=check)

        terminal = None
        started = False
        try:
            call("server", "start")
            started = True
            # A real PTY program emits status and stays alive for observation.
            program = ('printf "\\033]7501;state=working:app=polytoken\\033\\\\"; '
                       'printf "\\033]7501;state=blocked:kind=permission:app=polytoken\\033\\\\"; '
                       'read -r answer')
            use_relay = "--relay" in sys.argv
            ready = socket.socket(socket.AF_UNIX)
            ready.settimeout(5)
            ready_path = str(Path(directory) / "ready.sock")
            ready.bind(ready_path)
            ready.listen(1)
            argv = ([sys.executable, str(Path(__file__).with_name("relay_terminal_probe.py").resolve()), ready_path]
                    if use_relay else ["/bin/sh", "-c", program])
            if use_relay and "--split-output" in sys.argv:
                argv.append("--split-output")
            if use_relay and "--split-csi" in sys.argv:
                argv.append("--split-csi")
            if use_relay and "--serialized" in sys.argv:
                argv.append("--serialized")
            if use_relay and "--proxy" in sys.argv:
                argv.append("--proxy")
            launch = json.loads(call("run", "--bg", "--no-parent", "--name",
                                     "status-probe", *argv).stdout)
            terminal = "status-probe"
            try:
                if use_relay:
                    connection, _ = ready.accept()
                    with connection:
                        connection.settimeout(5)
                        assert connection.recv(32) == b"reported"
            finally:
                ready.close()
            waited = json.loads(call("wait", terminal, "--timeout", "5").stdout)
            assert waited["reason"] == "status" and waited["status"] == "blocked", waited
            assert waited["turn"] == 1, waited
            record = json.loads(call("get", terminal).stdout)
            print(json.dumps({"launch": launch, "wait": waited, "record": record}, indent=2))
            # Inspect only protocol facts, never screen text.
            assert record["status"]["state"] == "blocked", record
            if not use_relay:
                assert record["status"]["kind"] == "permission", record
            assert record["status"]["app"] == "polytoken", record
            refused = call("send", terminal, "must-not-arrive", check=False)
            assert refused.returncode == 9, (refused.returncode, refused.stderr)
            if use_relay and "--split-csi" in sys.argv:
                screen = call("read", terminal).stdout
                print("split-sequence screen:", repr(screen))
                assert not screen.strip(), "Split CSI was corrupted by concurrent status output"
            print("PASS: OSC status parsed and blocked send refused (exit 9)")
        finally:
            if terminal is not None:
                call("kill", terminal, check=False)
                call("rm", terminal, check=False)
            if started:
                call("server", "stop")


if __name__ == "__main__":
    main()
