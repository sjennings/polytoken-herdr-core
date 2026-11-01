import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from polytoken_herdr.relay import Relay


class HookTests(unittest.TestCase):
    def invoke(self, payload, env):
        return subprocess.run([sys.executable, "-m", "polytoken_herdr.hook"],
                              input=payload, text=True, capture_output=True, env=env, timeout=3)

    def test_unmanaged_and_malformed_input_are_quiet_and_allow(self):
        env = {key: value for key, value in os.environ.items() if not key.startswith("POLYTOKEN_HERDR_")}
        for payload in ("{}", "broken", "x" * 1048577):
            result = self.invoke(payload, env)
            self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))

    def test_real_hook_process_reports_session_without_stdout(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            output = io.BytesIO()
            with Relay(Path(directory) / "relay.sock", output) as relay:
                env = dict(os.environ, POLYTOKEN_HERDR_SOCKET=str(relay.path),
                           POLYTOKEN_HERDR_TOKEN=relay.token,
                           POLYTOKEN_SESSION_ID="a", POLYTOKEN_HOOK_EVENT="session_start")
                result = self.invoke(json.dumps({"event": "session_start", "session_id": "a"}), env)
                self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
                self.assertIn(b"state=idle", output.getvalue())
                env["POLYTOKEN_HOOK_EVENT"] = "pre_model_turn"
                result = self.invoke(json.dumps({"event": "pre_model_turn", "prompt_id": "p", "input": "secret"}), env)
                self.assertEqual(result.returncode, 0)
                self.assertIn(b"state=working", output.getvalue())
                self.assertNotIn(b"secret", output.getvalue())

    def test_missing_socket_does_not_deny_tool(self):
        env = dict(os.environ, POLYTOKEN_HERDR_SOCKET="/nonexistent/socket", POLYTOKEN_HERDR_TOKEN="token",
                   POLYTOKEN_SESSION_ID="a", POLYTOKEN_HOOK_EVENT="pre_model_turn")
        result = self.invoke('{"prompt_id":"p"}', env)
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
