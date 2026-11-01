from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_processes import descendants, assert_exited


class ProcessProbeTests(unittest.TestCase):
    def test_walks_only_descendants_of_owned_root(self):
        tree = {100: "101\n102\n", 101: "103\n", 102: "", 103: ""}
        def run(command, **kwargs):
            self.assertEqual(command[:2], ["pgrep", "-P"])
            output = tree[int(command[2])]
            return SimpleNamespace(returncode=0 if output else 1, stdout=output)
        with patch("probe_processes.subprocess.run", side_effect=run):
            self.assertEqual(descendants(100), {101, 102, 103})

    def test_enumeration_failure_is_not_an_empty_tree(self):
        with patch("probe_processes.subprocess.run", return_value=SimpleNamespace(returncode=2, stdout="")):
            with self.assertRaises(RuntimeError):
                descendants(100)

    def test_survivor_fails_check(self):
        with patch("probe_processes.os.kill", return_value=None):
            with self.assertRaisesRegex(AssertionError, "101"):
                assert_exited({101})

    def test_missing_pid_passes(self):
        with patch("probe_processes.os.kill", side_effect=ProcessLookupError):
            assert_exited({101})
