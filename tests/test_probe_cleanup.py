# pattern: Imperative Shell tests
import json
from pathlib import Path
import selectors
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_cleanup import process_identity, shutdown_registry, cleanup_actions

SERVER = '''
import http.server, json, os, signal, sys, threading
root, mode = sys.argv[1:]
if mode == "stubborn": signal.signal(signal.SIGTERM, signal.SIG_IGN)
class Handler(http.server.BaseHTTPRequestHandler):
 def log_message(self, *args): pass
 def do_GET(self):
  self.send_response(200); self.end_headers()
  self.wfile.write(json.dumps(dict(session_id="owned", pid=os.getpid())).encode())
 def do_POST(self):
  self.send_response(200); self.end_headers(); self.wfile.write(b'{}')
  if mode == "graceful": threading.Thread(target=self.server.shutdown).start()
server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
print(server.server_port, flush=True)
server.serve_forever()
server.server_close()
'''


class ProbeCleanupTests(unittest.TestCase):
    def test_process_scheduling_state_is_not_part_of_identity(self):
        with patch("probe_cleanup.subprocess.run") as run:
            run.return_value.returncode = 0
            run.return_value.stdout = "S Mon Nov 12 12:00:00 2026 polytoken daemon /private/probe"
            first = process_identity(100)
            run.return_value.stdout = "R Mon Nov 12 12:00:00 2026 polytoken daemon /private/probe"
            self.assertEqual(process_identity(100), first)

    def test_graceful_and_stubborn_owned_children_both_exit_without_force_cli(self):
        for mode in ("graceful", "stubborn"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                child = subprocess.Popen([sys.executable, "-u", "-c", SERVER, str(root), mode],
                                         stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                try:
                    with selectors.DefaultSelector() as ready:
                        ready.register(child.stdout, selectors.EVENT_READ)
                        self.assertTrue(ready.select(5), "test daemon did not start")
                    port = int(child.stdout.readline())
                    entry = root / "sessions-v1/owned"
                    entry.mkdir(parents=True)
                    credential = entry / "credential.json"
                    credential.write_text(json.dumps({"token": "test-fixture-token"}))
                    (entry / "record.json").write_text(json.dumps({
                        "pid": child.pid, "port": port, "session_id": "owned", "project_path": str(root),
                        "credential_file_path": str(credential)}))
                    shutdown_registry(root, timeout=0.1)
                    child.wait(timeout=2)
                finally:
                    if child.poll() is None:
                        child.kill()
                    child.communicate(timeout=5)

    def test_mismatched_record_is_refused_before_network_or_signals(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            entry = root / "sessions-v1/owned"
            entry.mkdir(parents=True)
            (entry / "record.json").write_text(json.dumps({
                "pid": 123, "port": 1, "session_id": "different", "project_path": str(root)}))
            with patch("probe_cleanup.os.kill") as kill:
                with self.assertRaises(ValueError):
                    shutdown_registry(root)
                kill.assert_not_called()

    def test_cleanup_attempts_remaining_actions_after_early_failure(self):
        calls = []
        def fail():
            calls.append("failed")
            raise RuntimeError("injected cleanup failure")
        with self.assertRaises(RuntimeError):
            cleanup_actions([fail, lambda: calls.append("daemon"), lambda: calls.append("core")])
        self.assertEqual(calls, ["failed", "daemon", "core"])
