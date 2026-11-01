from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

scripts = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(scripts))
import probe_integration


class IntegrationProbeTests(unittest.TestCase):
    def test_followup_requires_new_idle_turn(self):
        calls = []

        def hc(*args):
            calls.append(args)
            if args[0] == "send":
                return SimpleNamespace(stdout='{}')
            return SimpleNamespace(stdout='{"state":"live","status":{"app":"polytoken","state":"idle"},"turn":2}')

        probe_integration.verify_followup(hc, 1)
        self.assertEqual(calls[0], ("send", "integration", "Reply OK again", "--if", "idle", "--wait", "--timeout", "15"))

    def test_question_requires_blocked_status_and_refused_send(self):
        calls = []
        def hc(*args, **kwargs):
            calls.append(args)
            if args[0] == "get":
                return SimpleNamespace(stdout='{"status":{"app":"polytoken","state":"blocked"}}')
            return SimpleNamespace(stdout='{}', returncode=9 if "must not arrive" in args else 0)
        probe_integration.verify_question(hc)
        self.assertNotIn("--force", [item for call in calls for item in call])

    def test_question_rejects_unblocked_status(self):
        def hc(*args, **kwargs):
            return SimpleNamespace(stdout='{"status":{"state":"idle"}}', returncode=0)
        with self.assertRaisesRegex(AssertionError, "blocked"):
            probe_integration.verify_question(hc)

    def test_shutdown_requires_finished_terminal(self):
        def hc(*args):
            return SimpleNamespace(stdout='{"state":"finished","exit_code":143}')

        probe_integration.verify_shutdown(hc)

    def test_shutdown_rejects_still_live_terminal(self):
        def hc(*args):
            return SimpleNamespace(stdout='{"state":"live"}')

        with self.assertRaisesRegex(AssertionError, "still live"):
            probe_integration.verify_shutdown(hc)

    def test_stale_idle_is_not_followup_success(self):
        def hc(*args):
            return SimpleNamespace(stdout='{"state":"live","status":{"app":"polytoken","state":"idle"},"turn":1}')

        with self.assertRaisesRegex(AssertionError, "new turn"):
            probe_integration.verify_followup(hc, 1)
