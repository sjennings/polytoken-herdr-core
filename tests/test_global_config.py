import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from polytoken_herdr import config


class GlobalConfigTests(unittest.TestCase):
    def test_install_preserves_existing_hooks_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            original = '[{"name":"other","event":"stop","handler":{"bash":"true"}}]\n'
            (path / "hooks.json").write_text(original)
            config.prepare_global(path)
            self.assertEqual(json.loads((path / "hooks.json").read_text()), json.loads(original) + config.hooks())
            self.assertEqual((path / "hooks.json.herdr-backup").read_text(), original)
            first = (path / "hooks.json").read_bytes()
            config.prepare_global(path)
            self.assertEqual((path / "hooks.json").read_bytes(), first)
            config.validate_global(path)

    def test_conflict_preserves_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            original = json.dumps([dict(config.hooks()[0], handler={"bash": "other"})])
            (path / "hooks.json").write_text(original)
            with self.assertRaises(ValueError):
                config.prepare_global(path)
            self.assertEqual((path / "hooks.json").read_text(), original)

    def test_invalid_shape_preserves_file(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            (path / "hooks.json").write_text('{}')
            with self.assertRaises(ValueError):
                config.prepare_global(path)
            self.assertEqual((path / "hooks.json").read_text(), '{}')

    def test_global_launch_uses_default_config_and_no_project_directory(self):
        from polytoken_herdr.launcher import launch_command, polytoken_command
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": root}):
                config.prepare_global(config.global_directory())
                command = launch_command("worker", root, None, "model", "hello")
                self.assertIn("--global", command)
                self.assertNotIn("--config", command)
                self.assertFalse((Path(root) / '.polytoken').exists())
                self.assertNotIn("--config-dir", polytoken_command(None, '/sessions', 'model', 'hello'))

    def test_global_launch_rejects_project_disabling_adapter(self):
        from polytoken_herdr.launcher import launch_command
        with tempfile.TemporaryDirectory() as root:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": root}):
                config.prepare_global(config.global_directory())
                project = Path(root) / 'project'
                (project / '.polytoken').mkdir(parents=True)
                (project / '.polytoken/hooks.json').write_text('["!herdr-stop"]')
                with self.assertRaisesRegex(ValueError, "project"):
                    launch_command('worker', project, None, None, None)

    def test_malformed_hook_name_is_rejected_without_write(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            original = '[{"name": []}]'
            (path / 'hooks.json').write_text(original)
            with self.assertRaises(ValueError):
                config.prepare_global(path)
            self.assertEqual((path / 'hooks.json').read_text(), original)

    def test_xdg_global_directory(self):
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "/tmp/isolated-config"}):
            self.assertEqual(config.global_directory(), Path('/tmp/isolated-config/polytoken'))
