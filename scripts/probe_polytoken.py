#!/usr/bin/env python3
"""Credential-free bounded startup probe. No license acceptance or live hooks."""
import io
import json
import os
from pathlib import Path
import shutil
import sys
import subprocess
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from polytoken_herdr.config import hooks
from polytoken_herdr.relay import Relay


class Provider(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        self.reply({"object": "list", "data": [{"id": "local-probe", "object": "model", "owned_by": "local"}]})

    def reply(self, value):
        data = json.dumps(value).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        if self.path == "/hook-done":
            self.server.hook_done.set()
            self.reply({})
            return
        payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        print("provider POST", self.path, "stream=", payload.get("stream"), flush=True)
        chunk = {"id": "probe", "object": "chat.completion.chunk", "created": 1,
                 "model": "local-probe", "choices": [{"index": 0,
                 "delta": {"role": "assistant", "tool_calls": [{"index": 0,
                     "id": "probe-completion", "type": "function", "function": {
                         "name": "exec_structured_output",
                         "arguments": json.dumps({"output": "OK"})}}]},
                 "finish_reason": "tool_calls"}]}
        tools = [tool.get("function", {}).get("name") for tool in payload.get("tools", [])]
        if "exec_structured_output" not in tools:
            chunk["choices"][0].update(delta={"role": "assistant", "content": "OK"}, finish_reason="stop")
        if getattr(self.server, "ask_question", False):
            self.server.ask_question = False
            arguments = {"questions": [{"id": "probe", "context": "Isolated test. You may leave this question pending and detach the hc viewer with Ctrl+\\, or submit an answer to receive OK. Empty submission does not dismiss the question.",
                                       "question": "Test human input", "mode": "text", "allow_free_text": True}]}
            chunk["choices"][0].update(delta={"role": "assistant", "tool_calls": [{"index": 0,
                "id": "probe-question", "type": "function", "function": {"name": "ask_user_question",
                "arguments": json.dumps(arguments)}}]}, finish_reason="tool_calls")
        data = ("data: " + json.dumps(chunk) + "\n\ndata: [DONE]\n\n").encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    binary = shutil.which("polytoken")
    if not binary:
        raise SystemExit("polytoken is required")
    with tempfile.TemporaryDirectory(prefix="pt-probe-", dir="/tmp") as root:
        root = Path(root)
        env = {key: value for key, value in os.environ.items()
               if key in ("PATH", "LANG", "TERM", "SHELL", "TMPDIR")}
        env["HOME"] = str(root)
        for kind in ("CONFIG", "DATA", "STATE", "CACHE"):
            path = root / kind.lower()
            path.mkdir(mode=0o700)
            env[f"XDG_{kind}_HOME"] = str(path)
        server = ThreadingHTTPServer(("127.0.0.1", 0), Provider)
        server.hook_done = threading.Event()
        question_probe = "--question" in sys.argv
        server.ask_question = question_probe
        if server.ask_question:
            env["POLYTOKEN_HERDR_WAIT_EVENT"] = "interrogative_wants_open"
        env["POLYTOKEN_HERDR_DONE_URL"] = f"http://127.0.0.1:{server.server_port}/hook-done"
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        output = io.BytesIO()
        relay = Relay(root / "relay.sock", output)
        relay.__enter__()
        env["POLYTOKEN_HERDR_SOCKET"] = str(relay.path)
        env["POLYTOKEN_HERDR_TOKEN"] = relay.token
        try:
            config = json.loads((Path(__file__).resolve().parents[1] /
                                 "tests/fixtures/polytoken/config.json").read_text())
            config["providers"]["local-probe"]["url"] = f"http://127.0.0.1:{server.server_port}/v1"
            project = root / "project"
            project.mkdir()
            config_dir = (root / "config" / "polytoken" if "--global" in sys.argv else
                          project / ("adapter-config" if "--separate-config" in sys.argv else ".polytoken"))
            config_dir.mkdir(parents=True)
            (config_dir / "config.json").write_text(json.dumps(config))
            import shlex
            capture = root / "capture"
            capture.mkdir(mode=0o700)
            env["POLYTOKEN_HERDR_CAPTURE"] = str(capture)
            env["POLYTOKEN_HERDR_PROBE"] = "present"
            handler = shlex.join([sys.executable, str(Path(__file__).with_name("capture_hook.py").resolve())])
            events = ("session_start", "pre_user_prompt", "pre_model_turn", "pre_tool_use", "stop",
                      "interrogative_wants_open", "interrogative_has_closed")
            (config_dir / "hooks.json").write_text(json.dumps(hooks() + [
                {"name": "probe-" + event, "event": event, "handler": {"bash": handler}}
                for event in events]))
            base = [binary, "--working-dir", str(project)]
            if "--global" not in sys.argv:
                base += ["--config-dir", str(config_dir)]
            command = base + ["exec", "--model", "local-probe",
                              "--max-tool-turns", "1", "Reply OK"]
            daemon_probe = "--daemon" in sys.argv
            sessions = str(root / "sessions")
            if daemon_probe:
                command = base + ["new", "--no-attach", "--sessions-dir", sessions,
                                  "--model", "local-probe", "--prompt", "Reply OK"]
            try:
                result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=45)
                print("exit:", result.returncode)
                print(result.stdout)
                print(result.stderr)
                if daemon_probe and result.returncode == 0:
                    assert server.hook_done.wait(20), "Daemon did not emit stop within 20 seconds"
                records = [json.loads(path.read_text()) for path in capture.glob("*.json")]
                print("hooks:", json.dumps(records, indent=2))
                if not daemon_probe:
                    assert any(record["event"] == "pre_model_turn" for record in records), records
                assert all(record["endpoint_inherited"] for record in records), records
                if result.returncode == 0:
                    expected = "blocked" if question_probe else ("idle" if daemon_probe else "working")
                    assert relay.status.state == expected, (relay.status.state, expected)
                    assert b"state=working" in output.getvalue(), output.getvalue()
                    print("production relay status:", relay.status.state)
                return result.returncode
            except subprocess.TimeoutExpired as error:
                print("TIMEOUT (child killed):", 45)
                print((error.stdout or b"").decode(errors="replace"))
                print((error.stderr or b"").decode(errors="replace"))
                return 124
            finally:
                if daemon_probe:
                    # Restricted to this probe's private registry, never global reap.
                    cleanup = subprocess.run([binary, "reap", "--force", "--sessions-dir", sessions],
                                             env=env, capture_output=True, text=True, timeout=20)
                    print("scratch daemon cleanup:", cleanup.returncode, cleanup.stdout, cleanup.stderr)
                    if cleanup.returncode:
                        raise RuntimeError("Scratch daemon cleanup failed")
                    after = [json.loads(path.read_text()) for path in capture.glob("*.json")]
                    closed = [record for record in after if record["event"] == "interrogative_has_closed"]
                    print("close events observed by cleanup return:", json.dumps(closed))
                    print("relay state after cleanup:", relay.status.state)
                    listed = subprocess.run([binary, "sessions", "--sessions-dir", sessions, "--format", "json"],
                                            env=env, capture_output=True, text=True, timeout=20, check=True)
                    print("scratch live-session listing:", listed.stdout)
                    assert json.loads(listed.stdout) == [], "Scratch daemon remains live after cleanup"
        finally:
            relay.__exit__(None, None, None)
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    raise SystemExit(main())
