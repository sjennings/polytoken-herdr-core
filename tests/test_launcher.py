from pathlib import Path
import tempfile
import unittest

from polytoken_herdr.config import prepare
from polytoken_herdr.launcher import launch_command, polytoken_command


class LauncherTests(unittest.TestCase):
    def test_prompt_and_paths_are_separate_arguments(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / ".polytoken"
            prepare(config)
            command = launch_command("worker", root, config, "local", "a; $(false)")
            self.assertEqual(command[:3], ["hc", "run", "--bg"])
            self.assertEqual(command[-1], "a; $(false)")
            self.assertIn(str(config.resolve()), command)
            self.assertNotIn("--force", command)

    def test_rejects_config_outside_project_hook_discovery_location(self):
        with tempfile.TemporaryDirectory() as root:
            config = Path(root) / "adapter-config"
            prepare(config)
            with self.assertRaisesRegex(ValueError, "hook discovery"):
                launch_command("worker", root, config, "local", "hello")

    def test_polytoken_launch_is_attached_and_does_not_accept_legal_terms(self):
        command = polytoken_command("/config", "/sessions", "model", "hello")
        self.assertIn("new", command)
        self.assertNotIn("--no-attach", command)
        self.assertNotIn("--accept-license-terms", command)
        self.assertEqual(command[-2:], ["--prompt", "hello"])
