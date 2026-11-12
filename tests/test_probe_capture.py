# pattern: Imperative Shell tests
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from probe_capture import Capture


class CaptureTests(unittest.TestCase):
    def test_session_is_persisted_before_start_and_previous_capture_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            capture = Capture("phc-probe-first", Path(directory))
            capture.write("observed", state="idle")
            original = capture.path.read_bytes()
            with self.assertRaises(FileExistsError):
                Capture("phc-probe-first", Path(directory))
            second = Capture("phc-probe-second", Path(directory))
            self.assertEqual(capture.path.read_bytes(), original)
            records = [json.loads(line) for line in original.splitlines()]
            self.assertEqual(records[0], {"session": "phc-probe-first", "event": "created"})
            self.assertEqual(records[1]["session"], "phc-probe-first")
            self.assertNotEqual(capture.path, second.path)
            self.assertEqual(capture.path.stat().st_mode & 0o777, 0o600)
