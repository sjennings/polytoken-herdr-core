import os
import signal
import unittest

from polytoken_herdr.launcher import termination_cleanup, ignore_termination


class SignalTests(unittest.TestCase):
    def test_signal_during_normal_cleanup_is_ignored_and_handlers_restored(self):
        original = signal.getsignal(signal.SIGTERM)
        with termination_cleanup():
            ignore_termination()
            os.kill(os.getpid(), signal.SIGTERM)
            self.assertEqual(signal.getsignal(signal.SIGTERM), signal.SIG_IGN)
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)

    def test_termination_unwinds_and_restores_handlers(self):
        original = signal.getsignal(signal.SIGTERM)
        visited = []
        with self.assertRaises(SystemExit) as raised:
            with termination_cleanup():
                try:
                    os.kill(os.getpid(), signal.SIGTERM)
                finally:
                    visited.append("cleanup")
        self.assertEqual(raised.exception.code, 128 + signal.SIGTERM)
        self.assertEqual(visited, ["cleanup"])
        self.assertEqual(signal.getsignal(signal.SIGTERM), original)
