import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from polytoken_herdr import appconfig

ROOT = Path(__file__).resolve().parents[1]


class PluginScriptTests(unittest.TestCase):
    def environment(self, home):
        environment = {key: value for key, value in os.environ.items()
                       if key in ("PATH", "LANG", "SHELL", "TMPDIR")}
        # Installer tests exercise packaging, not the app or any core lifecycle.
        tools = home / "test-tools"
        tools.mkdir()
        app = tools / "herdr-app"
        app.write_text('#!/bin/sh\n[ "$1" = check ] && [ -f "$2/main.js" ]\n')
        app.chmod(0o700)
        environment.update({
            "PATH": str(tools) + os.pathsep + environment.get("PATH", "/usr/bin:/bin"),
            "HOME": str(home),
            "HERDR_APP_HOME": str(home / "herdr-app"),
            "XDG_CONFIG_HOME": str(home / "xdg"),
            "POLYTOKEN_HERDR_PYTHON": sys.executable,
        })
        return environment

    def preexisting(self, home):
        """Unrelated entries install.sh must not disturb."""
        (home / "herdr-app").mkdir(parents=True)
        (home / "herdr-app" / "programs.json").write_text(
            json.dumps({"programs": {"other": {"name": "Other"}}}))
        hooks = home / "xdg" / "polytoken"
        hooks.mkdir(parents=True)
        (hooks / "hooks.json").write_text(
            json.dumps([{"name": "other", "event": "stop", "handler": {"bash": "true"}}]))

    def programs(self, home):
        return json.loads((home / "herdr-app" / "programs.json").read_text())["programs"]

    def hooks(self, home):
        return json.loads((home / "xdg" / "polytoken" / "hooks.json").read_text())

    def hook_names(self, home):
        return {entry["name"] for entry in self.hooks(home)}

    def test_install_and_uninstall_round_trip(self):
        with tempfile.TemporaryDirectory() as root:
            home = Path(root)
            self.preexisting(home)
            hooks = home / "xdg" / "polytoken" / "hooks.json"
            entries = json.loads(hooks.read_text())
            hooks.write_text(json.dumps(entries + [{"name": "herdr-stop", "handler": {"bash": "/stale/entry.py hook"}}, "!herdr-session_start"]))
            environment = self.environment(home)
            subprocess.run([str(ROOT / "install.sh")], env=environment,
                           check=True, capture_output=True, text=True)

            launcher = home / ".local" / "bin" / "polytoken-herdr"
            self.assertEqual(os.readlink(launcher), str(ROOT / "bin" / "polytoken-herdr"))
            self.assertEqual(os.readlink(home / ".claude" / "skills" / "polytoken-herdr"),
                             str(ROOT / "skill" / "polytoken-herdr"))
            self.assertEqual(os.readlink(home / "herdr-app" / "mods" / "polytoken"),
                             str(ROOT / "mods" / "polytoken"))
            self.assertEqual(self.programs(home)["other"], {"name": "Other"})
            self.assertEqual(self.programs(home)["polytoken"]["run"][0], str(launcher))
            icon = home / "herdr-app" / appconfig.ICON_RELPATH
            self.assertEqual(icon.read_bytes(), appconfig._icon_source().read_bytes())
            self.assertEqual(self.hook_names(home), {"other"})
            self.assertIn("other", self.hook_names(home))
            with self.subTest("installed launcher wrapper runs adapter commands"):
                probe_environment = dict(environment)
                probe_environment["XDG_CONFIG_HOME"] = str(home / "xdg2")
                probe = subprocess.run([str(launcher), "remove", "--global"],
                                       env=probe_environment, capture_output=True, text=True)
                self.assertEqual(probe.returncode, 0, probe.stderr)
                self.assertIn("no adapter hooks found", probe.stdout)
                self.assertFalse((home / "xdg2" / "polytoken").exists())

            document = json.loads((home / "herdr-app" / "programs.json").read_text())
            document["programs"]["polytoken"]["match"] = ["my-extra-wrapper"]
            (home / "herdr-app" / "programs.json").write_text(json.dumps(document))
            subprocess.run([str(ROOT / "install.sh")], env=environment,
                           check=True, capture_output=True, text=True)
            self.assertEqual(self.programs(home)["polytoken"]["match"], ["my-extra-wrapper"])
            # Uninstall also cleans stale hooks even if an older version added them later.
            hooks.write_text(json.dumps(entries + ["!herdr-stop"]))
            subprocess.run([str(ROOT / "uninstall.sh")], env=environment,
                           check=True, capture_output=True, text=True)
            self.assertFalse(launcher.exists())
            self.assertFalse((home / ".claude" / "skills" / "polytoken-herdr").exists())
            self.assertFalse((home / "herdr-app" / "mods" / "polytoken").exists())
            self.assertEqual(self.programs(home), {"other": {"name": "Other"}})
            self.assertFalse(icon.exists())
            self.assertEqual(self.hook_names(home), {"other"})


if __name__ == "__main__":
    unittest.main()
