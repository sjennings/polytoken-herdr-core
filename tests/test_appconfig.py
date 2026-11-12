import json
import tempfile
import unittest
from pathlib import Path

from polytoken_herdr import appconfig


class AppInstallTests(unittest.TestCase):
    def test_install_into_fresh_home(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "herdr-app"
            launcher = Path(root) / "bin" / "polytoken-herdr"
            launcher.parent.mkdir()
            launcher.touch()
            self.assertTrue(appconfig.install_app(home, launcher))
            document = json.loads((home / "programs.json").read_text())
            self.assertEqual(document["programs"]["polytoken"],
                             appconfig.program_entry([str(launcher), "run", "--global"]))
            icon = home / appconfig.ICON_RELPATH
            self.assertEqual(icon.read_bytes(), appconfig._icon_source().read_bytes())

    def test_install_preserves_other_programs(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "herdr-app"
            home.mkdir()
            original = {"programs": {"other": {"name": "Other"}}, "shells": ["zsh"]}
            (home / "programs.json").write_text(json.dumps(original))
            launcher = Path(root) / "polytoken-herdr"
            launcher.touch()
            appconfig.install_app(home, launcher)
            document = json.loads((home / "programs.json").read_text())
            self.assertEqual(document["programs"]["other"], {"name": "Other"})
            self.assertEqual(document["shells"], ["zsh"])

    def test_reinstall_is_idempotent_without_backup(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "herdr-app"
            launcher = Path(root) / "polytoken-herdr"
            launcher.touch()
            self.assertTrue(appconfig.install_app(home, launcher))
            before = (home / "programs.json").read_bytes()
            self.assertFalse(appconfig.install_app(home, launcher))
            self.assertEqual((home / "programs.json").read_bytes(), before)
            self.assertFalse((home / appconfig.BACKUP_NAME).exists())

    def test_replacing_a_differing_entry_backs_it_up_first(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "herdr-app"
            home.mkdir()
            original = '{"programs": {"polytoken": {"name": "Custom", "run": ["x"]}}}'
            (home / "programs.json").write_text(original)
            launcher = Path(root) / "polytoken-herdr"
            launcher.touch()
            self.assertTrue(appconfig.install_app(home, launcher))
            self.assertEqual((home / appconfig.BACKUP_NAME).read_text(), original)
            document = json.loads((home / "programs.json").read_text())
            self.assertNotEqual(document["programs"]["polytoken"]["name"], "Custom")

    def test_reinstall_preserves_custom_fields_aliases_and_original_backup(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "herdr-app"
            home.mkdir()
            launcher = Path(root) / "polytoken-herdr"
            launcher.touch()
            original = {"programs": {"polytoken": {"name": "Custom", "run": ["old"],
                        "match": ["custom-wrapper", "second-wrapper"], "extension": "keep"}}}
            (home / "programs.json").write_text(json.dumps(original))
            (home / appconfig.BACKUP_NAME).write_text("old backup")
            appconfig.install_app(home, launcher)
            entry = json.loads((home / "programs.json").read_text())["programs"]["polytoken"]
            self.assertEqual(entry["extension"], "keep")
            self.assertEqual(entry["match"], ["custom-wrapper", "second-wrapper"])
            self.assertEqual(entry["run"], [str(launcher), "run", "--global"])
            self.assertEqual((home / appconfig.BACKUP_NAME).read_text(), "old backup")
            self.assertFalse(appconfig.install_app(home, launcher))

    def test_invalid_json_preserves_file(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root) / "herdr-app"
            home.mkdir()
            (home / "programs.json").write_text("{nope")
            launcher = Path(root) / "polytoken-herdr"
            launcher.touch()
            with self.assertRaises(ValueError):
                appconfig.install_app(home, launcher)
            self.assertEqual((home / "programs.json").read_text(), "{nope")

    def test_missing_launcher_is_refused(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(ValueError):
                appconfig.install_app(Path(root) / "home", Path(root) / "absent")


class AppRemoveTests(unittest.TestCase):
    def installed_home(self, root):
        home = Path(root) / "herdr-app"
        launcher = Path(root) / "polytoken-herdr"
        launcher.touch()
        appconfig.install_app(home, launcher)
        return home

    def test_remove_takes_only_this_adapter(self):
        with tempfile.TemporaryDirectory() as root:
            home = self.installed_home(root)
            document = json.loads((home / "programs.json").read_text())
            document["programs"]["other"] = {"name": "Other"}
            (home / "programs.json").write_text(json.dumps(document))
            removed = appconfig.remove_app(home)
            self.assertEqual(removed["name"], "Polytoken")
            document = json.loads((home / "programs.json").read_text())
            self.assertEqual(document["programs"], {"other": {"name": "Other"}})
            self.assertFalse((home / appconfig.ICON_RELPATH).exists())
            self.assertFalse((home / "polytoken-icons").exists())

    def test_remove_keeps_a_directory_it_does_not_own(self):
        with tempfile.TemporaryDirectory() as root:
            home = self.installed_home(root)
            (home / "polytoken-icons" / "other.webp").write_bytes(b"other")
            appconfig.remove_app(home)
            self.assertTrue((home / "polytoken-icons" / "other.webp").exists())

    def test_remove_without_install_is_a_no_op(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertIsNone(appconfig.remove_app(Path(root) / "home"))


if __name__ == "__main__":
    unittest.main()
