# pattern: Imperative Shell tests
import io
import os
from contextlib import nullcontext
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_stock_reporter import launch_stock_child


class StockChildTests(unittest.TestCase):
    def test_child_binds_recorder_to_its_private_tui_without_generated_python(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            recorder = root / "recorder"
            env = {"HC_SESSION": "phc-stock-owned", "HC_TERMINAL_ID": "t1", "HC_SOCKET": str(root / "core.sock")}
            with patch.dict(os.environ, env, clear=True), \
                 patch("probe_stock_reporter.terminal_output", return_value=nullcontext(io.BytesIO())), \
                 patch("probe_stock_reporter.run_proxy", return_value=0) as run:
                self.assertEqual(launch_stock_child(root / "sessions", recorder), 0)
                argv, child_env, output = run.call_args.args
                self.assertIn(str(root / "sessions"), argv)
                self.assertEqual(child_env["HERDR_BIN_PATH"], str(recorder.resolve()))
                self.assertEqual(child_env["HERDR_PANE_ID"], "t1")

    def test_child_refuses_default_or_missing_private_core_before_launch(self):
        with patch.dict(os.environ, {"HC_SESSION": "default", "HC_TERMINAL_ID": "t1"}, clear=True), \
             patch("probe_stock_reporter.run_proxy") as run:
            with self.assertRaises(ValueError):
                launch_stock_child(Path("/private/probe/sessions"), Path("/private/probe/recorder"))
            run.assert_not_called()
