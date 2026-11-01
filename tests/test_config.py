import json
from pathlib import Path
import tempfile
import unittest

from polytoken_herdr.config import prepare, validate


class ConfigTests(unittest.TestCase):
    def test_prepares_hooks_and_validates_without_provider_secrets(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "dedicated"
            prepare(target)
            validate(target)
            hooks = json.loads((target / "hooks.json").read_text())
            self.assertIn("interrogative_has_closed", [entry["event"] for entry in hooks])
            self.assertFalse((target / "config.json").exists())

    def test_refuses_existing_directory_without_changing_it(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root)
            original = target / "hooks.json"
            original.write_text("[]")
            with self.assertRaises(FileExistsError):
                prepare(target)
            self.assertEqual(original.read_text(), "[]")

    def test_rejects_changed_hooks(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / "dedicated"
            prepare(target)
            (target / "hooks.json").write_text("[]")
            with self.assertRaises(ValueError):
                validate(target)
