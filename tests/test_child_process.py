import subprocess
import unittest
from unittest.mock import Mock, patch

from polytoken_herdr.launcher import wait_for_tui


class ChildProcessTests(unittest.TestCase):
    def test_normal_exit_preserves_exit_code(self):
        child = Mock()
        child.wait.return_value = 7
        with patch("polytoken_herdr.launcher.subprocess.Popen", return_value=child):
            self.assertEqual(wait_for_tui(["polytoken"], {}), 7)
        child.terminate.assert_not_called()

    def test_interruption_requests_graceful_exit_before_propagating(self):
        child = Mock()
        child.wait.side_effect = [SystemExit(143), 0]
        with patch("polytoken_herdr.launcher.subprocess.Popen", return_value=child):
            with self.assertRaises(SystemExit):
                wait_for_tui(["polytoken"], {})
        child.terminate.assert_called_once()
        child.kill.assert_not_called()
        self.assertEqual(child.wait.call_args.kwargs, {"timeout": 5})

    def test_unresponsive_child_is_killed_after_grace_period(self):
        child = Mock()
        child.wait.side_effect = [KeyboardInterrupt(), subprocess.TimeoutExpired("polytoken", 5), -9]
        with patch("polytoken_herdr.launcher.subprocess.Popen", return_value=child):
            with self.assertRaises(KeyboardInterrupt):
                wait_for_tui(["polytoken"], {})
        child.terminate.assert_called_once()
        child.kill.assert_called_once()
        self.assertEqual(child.wait.call_count, 3)
