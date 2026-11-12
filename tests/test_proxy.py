import io
import fcntl
import pty
import struct
import signal
import termios
import os
import sys
import unittest
from unittest.mock import patch
from polytoken_herdr.proxy import run_proxy
from polytoken_herdr.launcher import termination_cleanup
from polytoken_herdr.stream import SerializedOutput


class ProxyTests(unittest.TestCase):
    def test_child_has_controlling_terminal_and_exit_code_is_preserved(self):
        sink = io.BytesIO()
        command = [sys.executable, "-c", "import os; f=os.open('/dev/tty',os.O_RDWR); print('PTY_OK', flush=True); os.close(f); raise SystemExit(7)"]
        code = run_proxy(command, dict(os.environ), SerializedOutput(sink), input_fd=None)
        self.assertEqual(code, 7)
        self.assertIn(b"PTY_OK", sink.getvalue())

    def test_initial_size_is_forwarded_and_parent_terminal_settings_restored(self):
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 37, 101, 0, 0))
            original = termios.tcgetattr(slave)
            sink = io.BytesIO()
            command = [sys.executable, "-c", "import os; s=os.get_terminal_size(0); print(f'{s.lines}x{s.columns}',flush=True)"]
            self.assertEqual(run_proxy(command, dict(os.environ), SerializedOutput(sink), input_fd=slave), 0)
            self.assertIn(b"37x101", sink.getvalue())
            restored = termios.tcgetattr(slave)
            # macOS sets PENDIN on raw->canonical restoration, even without a proxy.
            restored[3] &= ~getattr(termios, "PENDIN", 0)
            original[3] &= ~getattr(termios, "PENDIN", 0)
            self.assertEqual(restored, original)
        finally:
            os.close(master)
            os.close(slave)

    def test_live_resize_reaches_child(self):
        master, slave = pty.openpty()
        try:
            fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 24, 80, 0, 0))

            class ResizeSink(io.BytesIO):
                resized = False

                def write(self, data):
                    count = super().write(data)
                    if b"READY" in self.getvalue() and not self.resized:
                        self.resized = True
                        fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 42, 111, 0, 0))
                        os.kill(os.getpid(), signal.SIGWINCH)
                    return count

            sink = ResizeSink()
            child = ("import os,signal,threading; ready=threading.Event(); "
                     "signal.signal(signal.SIGWINCH, lambda *args: ready.set()); "
                     "print('READY',flush=True); "
                     "assert ready.wait(3), 'resize not received'; "
                     "s=os.get_terminal_size(0); print(f'{s.lines}x{s.columns}',flush=True)")
            code = run_proxy([sys.executable, "-c", child], dict(os.environ), SerializedOutput(sink), input_fd=slave)
            self.assertEqual(code, 0, sink.getvalue())
            self.assertIn(b"42x111", sink.getvalue())
        finally:
            os.close(master)
            os.close(slave)

    def test_wrapper_termination_reaps_real_child(self):
        class TerminateSink(io.BytesIO):
            child_pid = None

            def write(self, data):
                count = super().write(data)
                if self.child_pid is None and b"\n" in self.getvalue():
                    self.child_pid = int(self.getvalue().strip())
                    os.kill(os.getpid(), signal.SIGTERM)
                return count

        sink = TerminateSink()
        child = "import os,threading; print(os.getpid(),flush=True); threading.Event().wait(10)"
        with self.assertRaises(SystemExit) as raised:
            with termination_cleanup():
                run_proxy([sys.executable, "-c", child], dict(os.environ), SerializedOutput(sink), input_fd=None)
        self.assertEqual(raised.exception.code, 143)
        self.assertIsNotNone(sink.child_pid)
        with self.assertRaises(ProcessLookupError):
            os.kill(sink.child_pid, 0)

    def test_child_exit_during_termination_preserves_error_and_closes_pty(self):
        from unittest.mock import Mock
        master, slave = pty.openpty()
        child = Mock()
        child.poll.return_value = None
        child.terminate.side_effect = ProcessLookupError()
        child.wait.return_value = 0
        output = SerializedOutput(io.BytesIO())
        try:
            with patch("polytoken_herdr.proxy.pty.openpty", return_value=(master, slave)), \
                 patch("polytoken_herdr.proxy.subprocess.Popen", return_value=child), \
                 patch("polytoken_herdr.proxy.select.select", side_effect=ValueError("original failure")), \
                 patch.object(output, "finish", wraps=output.finish) as finish:
                with self.assertRaisesRegex(ValueError, "original failure"):
                    run_proxy(["unused"], dict(os.environ), output, input_fd=None)
                finish.assert_called_once()
            for fd in (master, slave):
                with self.assertRaises(OSError):
                    os.fstat(fd)
        finally:
            for fd in (master, slave):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_child_wait_error_still_closes_pty_and_finishes_output(self):
        from unittest.mock import Mock
        master, slave = pty.openpty()
        child = Mock()
        child.poll.return_value = None
        child.wait.side_effect = OSError("wait failed")
        output = SerializedOutput(io.BytesIO())
        try:
            with patch("polytoken_herdr.proxy.pty.openpty", return_value=(master, slave)), \
                 patch("polytoken_herdr.proxy.subprocess.Popen", return_value=child), \
                 patch("polytoken_herdr.proxy.select.select", side_effect=ValueError("input failed")), \
                 patch.object(output, "finish", wraps=output.finish) as finish:
                with self.assertRaisesRegex(OSError, "wait failed"):
                    run_proxy(["unused"], dict(os.environ), output, input_fd=None)
                finish.assert_called_once()
            for fd in (master, slave):
                with self.assertRaises(OSError):
                    os.fstat(fd)
        finally:
            for fd in (master, slave):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_terminal_restore_failure_still_finishes_output_and_closes_pty(self):
        parent_master, parent_slave = pty.openpty()
        child_master, child_slave = pty.openpty()
        output = SerializedOutput(io.BytesIO())
        def fail_restore(*args):
            raise termios.error(5, "terminal hung up")

        try:
            with patch("polytoken_herdr.proxy.pty.openpty", return_value=(child_master, child_slave)), \
                 patch("polytoken_herdr.proxy.termios.tcsetattr", side_effect=fail_restore), \
                 patch.object(output, "finish", wraps=output.finish) as finish:
                self.assertEqual(run_proxy([sys.executable, "-c", "pass"], dict(os.environ), output, parent_slave), 0)
                finish.assert_called_once()
            with self.assertRaises(OSError):
                os.fstat(child_master)
        finally:
            for fd in (parent_master, parent_slave, child_master, child_slave):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_immediate_exit_preserves_final_terminal_restore_bytes(self):
        sink = io.BytesIO()
        final = b"FINAL\x1b[?25h\x1b[?1049l"
        child = "import os; os.write(1," + repr(final) + "); os._exit(0)"
        self.assertEqual(run_proxy([sys.executable, "-c", child], dict(os.environ), SerializedOutput(sink), input_fd=None), 0)
        self.assertTrue(sink.getvalue().endswith(final + b"\x1b]7501;state=clear\x1b\\"), sink.getvalue())

    def test_child_exiting_without_release_still_clears_status(self):
        sink = io.BytesIO()
        working = b"\x1b]7501;state=working:app=polytoken\x1b\\"
        child = "import os; os.write(1," + repr(working) + "); os._exit(3)"
        self.assertEqual(run_proxy([sys.executable, "-c", child], dict(os.environ), SerializedOutput(sink), input_fd=None), 3)
        self.assertIn(working, sink.getvalue())
        self.assertTrue(sink.getvalue().endswith(b"\x1b]7501;state=clear\x1b\\"), sink.getvalue())

    def test_missed_readiness_still_preserves_final_output(self):
        import select
        real_select = select.select
        sink = io.BytesIO()
        first = True

        def miss_first_readiness(*args, **kwargs):
            nonlocal first
            if first:
                first = False
                # Wait for buffered bytes, not child exit: macOS may hold
                # session-leader exit until its controlling PTY is drained.
                self.assertTrue(real_select(args[0][:1], [], [], 3)[0])
                return [], [], []
            return real_select(*args, **kwargs)

        with patch("polytoken_herdr.proxy.select.select", side_effect=miss_first_readiness):
            code = run_proxy([sys.executable, "-c", "print('FINAL',flush=True)"], dict(os.environ), SerializedOutput(sink), input_fd=None)
        self.assertEqual(code, 0)
        self.assertIn(b"FINAL", sink.getvalue())

    def test_input_write_eio_does_not_replace_child_exit_code(self):
        import errno
        real_write = os.write
        read_fd, write_fd = os.pipe()
        try:
            real_write(write_fd, b"hello\n")
            os.close(write_fd)
            write_fd = None
            sink = io.BytesIO()
            calls = []

            def hangup(fd, data):
                calls.append(fd)
                raise OSError(errno.EIO, "child PTY closed")

            # Child exits independently of input; the injected EIO represents
            # the slave disappearing after select reported it writable.
            child = "import threading; threading.Event().wait(0.1); raise SystemExit(7)"
            with patch("polytoken_herdr.proxy.os.write", side_effect=hangup):
                code = run_proxy([sys.executable, "-c", child], dict(os.environ), SerializedOutput(sink), input_fd=read_fd)
            self.assertTrue(calls)
            self.assertEqual(code, 7)
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)

    def test_input_reaches_child_and_output_is_forwarded(self):
        read_fd, write_fd = os.pipe()
        try:
            os.write(write_fd, b"hello\n")
            os.close(write_fd)
            write_fd = None
            sink = io.BytesIO()
            code = run_proxy([sys.executable, "-c", "print('received:'+input(), flush=True)"],
                             dict(os.environ), SerializedOutput(sink), input_fd=read_fd)
            self.assertEqual(code, 0)
            self.assertIn(b"received:hello", sink.getvalue())
        finally:
            os.close(read_fd)
            if write_fd is not None:
                os.close(write_fd)
