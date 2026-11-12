# pattern: Functional Core tests
import unittest
from polytoken_herdr.report import parse_report, session_id, polytoken_command


class ReportTests(unittest.TestCase):
    def test_three_states_translate_to_fixed_osc_and_capture_session(self):
        for state in ("working", "idle", "blocked"):
            with self.subTest(state=state):
                report = parse_report(["report-agent", "--source", "tui", "--agent", "polytoken",
                                       "--state", state, "--message", "--not-an-option",
                                       "--seq", "4", "--agent-session-id", "abc-123._",
                                       "--", "polytoken", "continue", "abc-123._"])
                self.assertEqual(report.output, f"\x1b]7501;state={state}:app=polytoken\x1b\\".encode())
                self.assertEqual(report.session, "abc-123._")

    def test_release_clears_and_metadata_emits_nothing(self):
        self.assertEqual(parse_report(["release-agent", "--source", "tui"]).output,
                         b"\x1b]7501;state=clear\x1b\\")
        self.assertEqual(parse_report(["report-metadata", "--model", "anything"]).output, b"")

    def test_invalid_callbacks_are_rejected(self):
        for args in ([], ["unknown"], ["report-agent"],
                     ["report-agent", "--state", "done"],
                     ["report-agent", "--state", "idle", "--state", "blocked"],
                     ["report-agent", "--state"],
                     ["report-agent", "--state", "--"],
                     ["report-agent", "--state", "idle", "--agent-session-id", "-option"],
                     ["report-agent", "--state", "idle", "--agent-session-id", "bad\nID"]):
            with self.subTest(args=args), self.assertRaises(ValueError):
                parse_report(args)

    def test_session_ids_are_restricted_ascii_operands(self):
        for value in ("", "-option", "x/y", "a b", "é", "x\x00", "x\n"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                session_id(value)
        self.assertEqual(session_id("session-1.foo_bar"), "session-1.foo_bar")

    def test_native_arguments_preserve_prompt_and_sessions_path(self):
        self.assertEqual(polytoken_command("/config", "/sessions with spaces", "model", "$(false)"),
                         ["polytoken", "--config-dir", "/config", "new", "--sessions-dir",
                          "/sessions with spaces", "--model", "model", "--prompt", "$(false)"])
        self.assertEqual(polytoken_command(None, "/sessions", "ignored", "ignored", "abc"),
                         ["polytoken", "continue", "--sessions-dir", "/sessions", "--", "abc"])
        with self.assertRaises(ValueError):
            polytoken_command(None, None, None, None, "-bad")
