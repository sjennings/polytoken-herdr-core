#!/usr/bin/env python3
"""PTY fixture for probe_hc: production relay and output, synthetic event facts."""
from pathlib import Path
import sys
import socket
import os
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from polytoken_herdr.output import terminal_output
from polytoken_herdr.stream import SerializedOutput
from polytoken_herdr.relay import Relay, report
from polytoken_herdr.proxy import run_proxy


def emit_events(feed, path, token):
    for message in (
        {"session": "probe", "event": "session_start"},
        {"session": "probe", "event": "pre_model_turn", "prompt_id": "p"},
        {"session": "probe", "event": "interrogative_wants_open", "interrogative_id": "q"},
    ):
        if "--split-output" in sys.argv:
            feed(b"\x1b]0;fixture-title")
        if "--split-csi" in sys.argv:
            feed(b"\x1b[31")
        if not report(path, token, message):
            raise RuntimeError("Production relay rejected fixture report")
        if "--split-output" in sys.argv:
            feed(b"\x1b\\")
        if "--split-csi" in sys.argv:
            feed(b"m\x1b[0m")
    with socket.socket(socket.AF_UNIX) as ready:
        ready.settimeout(2)
        ready.connect(sys.argv[1])
        ready.sendall(b"reported")
    input()  # Keep fixture alive until probe_hc cleans it up.


def main():
    if "--child" in sys.argv:
        emit_events(lambda data: os.write(1, data), os.environ["PROBE_SOCKET"], os.environ["PROBE_TOKEN"])
        return
    with tempfile.TemporaryDirectory(prefix="phr-", dir="/tmp") as directory:
        with terminal_output() as sink:
            output = SerializedOutput(sink) if ("--serialized" in sys.argv or "--proxy" in sys.argv) else sink
            with Relay(Path(directory) / "relay.sock", output) as relay:
                if "--proxy" in sys.argv:
                    env = dict(os.environ, PROBE_SOCKET=str(relay.path), PROBE_TOKEN=relay.token)
                    command = [sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--child"]
                    run_proxy(command, env, output)
                else:
                    feed = output.feed if isinstance(output, SerializedOutput) else lambda data: os.write(1, data)
                    emit_events(feed, relay.path, relay.token)


if __name__ == "__main__":
    main()
