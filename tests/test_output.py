import os
import time
import threading
import select
import unittest

from polytoken_herdr.output import StatusOutput


class OutputTests(unittest.TestCase):
    def test_writes_exact_bytes(self):
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            output = StatusOutput(write_fd, timeout=0.05)
            output.write(b"status")
            output.flush()
            self.assertEqual(os.read(read_fd, 6), b"status")
        finally:
            os.close(read_fd)
            os.close(write_fd)

    def test_bulk_output_recovers_after_stall_longer_than_status_deadline(self):
        read_fd, write_fd = os.pipe()
        received = bytearray()
        worker = None
        done = threading.Event()
        try:
            os.set_blocking(write_fd, False)
            while True:
                try:
                    os.write(write_fd, b"x" * 4096)
                except BlockingIOError:
                    break

            def drain():
                # Deliberate output-stall stimulus, not a readiness guess.
                done.wait(0.3)
                while not done.is_set():
                    if select.select([read_fd], [], [], 0.1)[0]:
                        received.extend(os.read(read_fd, 65536))
                        if received.endswith(b"SCREEN-END"):
                            return

            worker = threading.Thread(target=drain)
            worker.start()
            StatusOutput(write_fd).write_bulk(b"SCREEN-END")
            worker.join(timeout=2)
            self.assertFalse(worker.is_alive())
            self.assertTrue(received.endswith(b"SCREEN-END"))
        finally:
            done.set()
            if worker is not None:
                worker.join(timeout=2)
            os.close(read_fd)
            os.close(write_fd)

    def test_full_pipe_times_out_instead_of_blocking(self):
        read_fd, write_fd = os.pipe()
        try:
            os.set_blocking(write_fd, False)
            while True:
                try:
                    os.write(write_fd, b"x" * 4096)
                except BlockingIOError:
                    break
            output = StatusOutput(write_fd, timeout=0.05)
            start = time.monotonic()
            with self.assertRaises(TimeoutError):
                output.write(b"status")
            self.assertLess(time.monotonic() - start, 1)
        finally:
            os.close(read_fd)
            os.close(write_fd)
