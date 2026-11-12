# pattern: Imperative Shell tests
import sys
import unittest
from unittest.mock import patch
from polytoken_herdr import cli


class CliTests(unittest.TestCase):
    def test_sessions_directory_both_forms_and_continue_remain_separate_operands(self):
        for options in (["--sessions-dir", "/path with spaces"], ["--sessions-dir=/path with spaces"]):
            with self.subTest(options=options), \
                 patch.object(sys, "argv", ["polytoken-herdr", "run", "--global", *options,
                                            "--continue", "valid-id"]), \
                 patch.object(cli, "run", return_value=0) as run:
                self.assertEqual(cli.main(), 0)
                run.assert_called_once_with(None, None, None, "valid-id", "/path with spaces")

    def test_restore_passes_only_validated_labels_to_launcher(self):
        with patch.object(sys, "argv", ["polytoken-herdr", "restore"]), \
             patch.object(cli, "restore_labels", return_value=("abc", "/sessions")), \
             patch.object(cli, "run", return_value=0) as run:
            self.assertEqual(cli.main(), 0)
            run.assert_called_once_with(None, None, None, "abc", "/sessions")

    def test_invalid_resume_is_rejected_before_starting_a_child(self):
        from polytoken_herdr.launcher import run
        with patch("polytoken_herdr.launcher.tempfile.mkdtemp") as temporary, \
             patch("polytoken_herdr.launcher.wait_for_tui") as wait:
            with self.assertRaises(ValueError):
                run(None, None, None, "-bad")
            wait.assert_not_called()
            temporary.assert_not_called()
