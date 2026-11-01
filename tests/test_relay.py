import io
import os
import time
from polytoken_herdr.output import StatusOutput
from concurrent.futures import ThreadPoolExecutor
import threading
import json
import socket
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from polytoken_herdr.relay import Relay, report


class RelayTests(unittest.TestCase):
    def test_authenticated_session_reports_only_emit_fixed_status(self):
        output = io.BytesIO()
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with Relay(Path(directory) / "relay.sock", output) as relay:
                self.assertFalse(report(relay.path, "wrong", {"event": "session_start", "session": "a"}))
                self.assertEqual(output.getvalue(), b"")
                self.assertTrue(report(relay.path, relay.token, {"event": "session_start", "session": "a"}))
                self.assertTrue(report(relay.path, relay.token, {"event": "pre_model_turn", "session": "a", "prompt_id": "p", "input": "SECRET"}))
                self.assertNotIn(b"SECRET", output.getvalue())
                self.assertIn(b"state=working:app=polytoken", output.getvalue())
                before = output.getvalue()
                self.assertFalse(report(relay.path, relay.token, {"event": "stop", "session": "other", "prompt_id": "p"}))
                self.assertEqual(output.getvalue(), before)
            self.assertFalse(relay.path.exists())

    def test_malformed_or_oversized_message_does_not_break_next_request(self):
        output = io.BytesIO()
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with Relay(Path(directory) / "relay.sock", output) as relay:
                for data in (b"not-json\n", b"x" * 8193 + b"\n",
                             b"[" * 1500 + b"0" + b"]" * 1500 + b"\n"):
                    with socket.socket(socket.AF_UNIX) as client:
                        client.settimeout(2)
                        client.connect(str(relay.path))
                        client.sendall(data)
                        self.assertEqual(client.recv(32), b"no\n")
                self.assertTrue(report(relay.path, relay.token, {"event": "session_start", "session": "a"}))

    def test_shutdown_clears_status_after_socket_stops(self):
        output = io.BytesIO()
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with Relay(Path(directory) / "relay.sock", output, clear_on_exit=True) as relay:
                report(relay.path, relay.token, {"event": "session_start", "session": "a"})
            self.assertTrue(output.getvalue().endswith(b"\x1b]7501;state=clear\x1b\\"))
            before = output.getvalue()
            self.assertFalse(report(relay.path, relay.token, {"event": "pre_model_turn", "session": "a", "prompt_id": "p"}))
            self.assertEqual(output.getvalue(), before)

    def test_closed_terminal_does_not_prevent_socket_cleanup(self):
        class ClosedTerminal:
            def write(self, data):
                raise OSError("terminal hung up")

        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with Relay(Path(directory) / "relay.sock", ClosedTerminal(), clear_on_exit=True) as relay:
                pass
            self.assertFalse(relay.path.exists())

    def test_decoder_recursion_failure_returns_rejection(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with Relay(Path(directory) / "relay.sock", io.BytesIO()) as relay:
                with patch("polytoken_herdr.relay.json.loads", side_effect=RecursionError):
                    with socket.socket(socket.AF_UNIX) as client:
                        client.settimeout(2)
                        client.connect(str(relay.path))
                        client.sendall(b"{}\n")
                        self.assertEqual(client.recv(16), b"no\n")

    def test_fifty_concurrent_prompt_reports_are_received(self):
        with tempfile.TemporaryDirectory(dir="/tmp") as directory:
            with Relay(Path(directory) / "relay.sock", io.BytesIO()) as relay:
                self.assertTrue(report(relay.path, relay.token, {"event": "session_start", "session": "a"}))
                barrier = threading.Barrier(50)

                def send(index):
                    barrier.wait(timeout=5)
                    return report(relay.path, relay.token, {"event": "interrogative_wants_open",
                                  "session": "a", "interrogative_id": str(index)})

                with ThreadPoolExecutor(max_workers=50) as pool:
                    results = list(pool.map(send, range(50)))
                self.assertEqual(sum(results), 50)
                self.assertEqual(len(relay.status.pending), 50)

    def test_stalled_terminal_rejects_report_and_shutdown_finishes(self):
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            while True:
                try:
                    os.write(write_fd, b"x" * 4096)
                except BlockingIOError:
                    break
            with tempfile.TemporaryDirectory(dir="/tmp") as directory:
                start = time.monotonic()
                with Relay(Path(directory) / "relay.sock", StatusOutput(write_fd, timeout=0.05), clear_on_exit=True) as relay:
                    self.assertFalse(report(relay.path, relay.token, {"event": "session_start", "session": "a"}))
                self.assertLess(time.monotonic() - start, 2)
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_missing_relay_is_nonblocking_failure(self):
        self.assertFalse(report(Path("/nonexistent/relay.sock"), "token", {}))
