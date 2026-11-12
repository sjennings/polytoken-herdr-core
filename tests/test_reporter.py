# pattern: Imperative Shell tests
import io
import os
from pathlib import Path
import unittest
from unittest.mock import patch
from contextlib import contextmanager

from polytoken_herdr import reporter


class ReporterTests(unittest.TestCase):
    def environment(self):
        return {"HC_TERMINAL_ID": "t99", "POLYTOKEN_HERDR_REPORTER": "1",
                "HERDR_PANE_ID": "t99", "POLYTOKEN_HERDR_SESSIONS_DIR": "/private/sessions"}

    def test_report_uses_reopened_terminal_and_records_restore_labels(self):
        output = io.BytesIO()
        @contextmanager
        def terminal():
            yield output
        with patch.dict(os.environ, self.environment(), clear=True), \
             patch.object(reporter, "terminal_output", terminal), \
             patch.object(reporter.subprocess, "run") as run:
            self.assertEqual(reporter.callback(["report-agent", "--state", "blocked",
                                               "--agent-session-id", "session-123"]), 0)
        self.assertEqual(output.getvalue(), b"\x1b]7501;state=blocked:app=polytoken\x1b\\")
        self.assertEqual(run.call_args.args[0], ["hc", "label", "t99", "polytoken.session=session-123",
                                               "polytoken.sessions_dir=/private/sessions"])
        self.assertGreater(run.call_args.kwargs["timeout"], 0)

    def test_callback_refuses_unbound_or_different_terminal(self):
        for env in ({}, dict(self.environment(), HERDR_PANE_ID="t100")):
            with self.subTest(env=env), patch.dict(os.environ, env, clear=True), \
                 patch.object(reporter, "terminal_output") as output:
                with self.assertRaises(ValueError):
                    reporter.callback(["release-agent"])
                output.assert_not_called()

    def test_environment_uses_absolute_executable_and_leaves_standalone_unchanged(self):
        original = {"HERDR_ENV": "legacy", "HERDR_BIN_PATH": "/legacy/herdr"}
        self.assertEqual(reporter.reporter_environment(original, "/sessions"), original)
        env = reporter.reporter_environment({"HC_TERMINAL_ID": "t99"}, "/sessions")
        self.assertEqual(env["HERDR_ENV"], "1")
        self.assertEqual(env["HERDR_PANE_ID"], "t99")
        self.assertTrue(Path(env["HERDR_BIN_PATH"]).is_absolute())
        self.assertTrue(os.access(env["HERDR_BIN_PATH"], os.X_OK))

    def test_restore_reads_only_own_terminal_and_validates_untrusted_labels(self):
        with patch.dict(os.environ, {"HC_TERMINAL_ID": "t99"}, clear=True), \
             patch.object(reporter.subprocess, "run") as run:
            run.return_value.stdout = '{"labels":{"polytoken.session":"session-123","polytoken.sessions_dir":"/private/sessions"}}'
            self.assertEqual(reporter.restore_labels(), ("session-123", "/private/sessions"))
            self.assertEqual(run.call_args.args[0], ["hc", "get", "--json", "t99"])
            for labels in ('{"polytoken.session":"-option"}',
                           '{"polytoken.session":"abc","polytoken.sessions_dir":"relative"}',
                           '{"polytoken.session":"abc","polytoken.sessions_dir":null}', '{}'):
                run.return_value.stdout = '{"labels":' + labels + '}'
                with self.subTest(labels=labels), self.assertRaises(ValueError):
                    reporter.restore_labels()
