from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import subprocess

from polytoken_herdr.launcher import cleanup_registry


class CleanupTests(unittest.TestCase):
    def test_success_removes_private_directory(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "private"
            root.mkdir()
            with patch("polytoken_herdr.launcher.subprocess.run") as run:
                cleanup_registry(root, {})
            self.assertFalse(root.exists())
            self.assertEqual(run.call_args.args[0][-1], str(root / "sessions"))

    def test_failure_retains_registry_and_reports_recovery_path(self):
        with tempfile.TemporaryDirectory() as parent:
            root = Path(parent) / "private"
            root.mkdir()
            with patch("polytoken_herdr.launcher.subprocess.run", side_effect=subprocess.TimeoutExpired("reap", 20)):
                with self.assertRaisesRegex(RuntimeError, "registry retained"):
                    cleanup_registry(root, {})
            self.assertTrue(root.exists())
