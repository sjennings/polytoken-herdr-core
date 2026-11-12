# pattern: Imperative Shell tests
import json
from pathlib import Path
import tempfile
import unittest

from polytoken_herdr.config import prepare, prepare_global, remove_global

LEGACY = ["herdr-session_start", "herdr-pre_model_turn", "herdr-stop",
          "herdr-interrogative_wants_open", "herdr-interrogative_has_closed"]


class ConfigTests(unittest.TestCase):
    def test_prepare_creates_directory_without_status_hooks(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "config"
            prepare(path)
            self.assertTrue(path.is_dir())
            self.assertEqual(list(path.iterdir()), [])
            prepare(path)

    def test_prepare_migrates_stale_global_and_project_hooks_preserving_others(self):
        for migrate in (prepare, prepare_global, remove_global):
            with self.subTest(migrate=migrate.__name__), tempfile.TemporaryDirectory() as root:
                path = Path(root)
                unrelated = {"name": "other", "handler": {"bash": "true"}}
                entries = [{"name": name, "handler": {"bash": "/old/entry.py hook"}} for name in LEGACY]
                entries += ["!herdr-stop", unrelated]
                original = json.dumps(entries)
                (path / "hooks.json").write_text(original)
                (path / "config.json").write_text("{}")
                migrate(path)
                self.assertEqual(json.loads((path / "hooks.json").read_text()), [unrelated])
                self.assertEqual((path / "hooks.json.herdr-backup").read_text(), original)
                migrate(path)
                self.assertEqual((path / "hooks.json.herdr-backup").read_text(), original)
                self.assertEqual((path / "config.json").read_text(), "{}")

    def test_missing_global_config_creates_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "missing"
            prepare_global(path)
            self.assertFalse(path.exists())
            self.assertEqual(remove_global(path), 0)

    def test_malformed_and_symlinked_hooks_are_not_modified(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root)
            target = path / "hooks.json"
            for text in ("{bad", "{}"):
                target.write_text(text)
                with self.assertRaises(ValueError):
                    prepare_global(path)
                self.assertEqual(target.read_text(), text)
            target.unlink()
            other = path / "other.json"
            other.write_text('[]')
            target.symlink_to(other)
            with self.assertRaises(ValueError):
                remove_global(path)
            self.assertEqual(other.read_text(), '[]')
