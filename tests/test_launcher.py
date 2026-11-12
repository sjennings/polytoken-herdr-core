# pattern: Imperative Shell tests
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from polytoken_herdr.launcher import launch_command, run


class LauncherTests(unittest.TestCase):
    def test_launch_preserves_public_commands_without_requiring_hooks(self):
        with tempfile.TemporaryDirectory() as root:
            command = launch_command("worker", root, None, "local", "a; $(false)")
            self.assertEqual(command[:3], ["hc", "run", "--bg"])
            self.assertIn("--global", command)
            self.assertEqual(command[-1], "a; $(false)")
            config = Path(root) / "custom-config"
            config.mkdir()
            self.assertIn(str(config.resolve()), launch_command("worker", root, config, None, None))

    def test_standalone_runs_without_changing_environment_or_registry(self):
        with patch.dict(os.environ, {"PATH": "/bin", "HERDR_ENV": "original"}, clear=True), \
             patch("polytoken_herdr.launcher.wait_for_tui", return_value=7) as wait, \
             patch("polytoken_herdr.launcher.tempfile.mkdtemp") as temporary:
            self.assertEqual(run(None, "model", "hello"), 7)
            temporary.assert_not_called()
            self.assertEqual(wait.call_args.args[0], ["polytoken", "new", "--model", "model", "--prompt", "hello"])
            self.assertEqual(wait.call_args.args[1], dict(os.environ))

    def test_managed_run_binds_reporter_and_cleans_only_its_private_registry(self):
        with tempfile.TemporaryDirectory() as root, \
             patch.dict(os.environ, {"HC_TERMINAL_ID": "t99"}, clear=True), \
             patch("polytoken_herdr.launcher.tempfile.mkdtemp", return_value=root), \
             patch("polytoken_herdr.launcher.terminal_output"), \
             patch("polytoken_herdr.launcher.run_proxy", return_value=0) as wait, \
             patch("polytoken_herdr.launcher.cleanup_registry") as cleanup:
            self.assertEqual(run(None, None, None), 0)
            command, env, output = wait.call_args.args
            self.assertEqual(command, ["polytoken", "new", "--sessions-dir", root + "/sessions"])
            self.assertEqual(env["HERDR_ENV"], "1")
            self.assertEqual(cleanup.call_args.args[0], Path(root))

    def test_explicit_registry_is_not_reaped_or_deleted(self):
        with patch.dict(os.environ, {"HC_TERMINAL_ID": "t99"}, clear=True), \
             patch("polytoken_herdr.launcher.terminal_output"), \
             patch("polytoken_herdr.launcher.run_proxy", return_value=0) as wait, \
             patch("polytoken_herdr.launcher.cleanup_registry") as cleanup:
            run(None, None, None, "abc", "/caller-owned/sessions")
            self.assertIn("/caller-owned/sessions", wait.call_args.args[0])
            cleanup.assert_not_called()

    def test_resume_uses_native_history_registry_and_never_reaps_it(self):
        with patch.dict(os.environ, {"HC_TERMINAL_ID": "t99"}, clear=True), \
             patch("polytoken_herdr.launcher.terminal_output"), \
             patch("polytoken_herdr.launcher.run_proxy", return_value=0) as wait, \
             patch("polytoken_herdr.launcher.cleanup_registry") as cleanup:
            run(None, None, None, "abc")
            self.assertEqual(wait.call_args.args[0], ["polytoken", "continue", "--", "abc"])
            cleanup.assert_not_called()
