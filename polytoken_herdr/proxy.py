"""Forward a private child PTY through the single serialized terminal writer."""
import errno
from contextlib import suppress
import fcntl
import os
from pathlib import Path
import pty
import select
import signal
import subprocess
import sys
import termios
import tty


def run_proxy(command, env, output, input_fd=0):
    master, slave = pty.openpty()
    child = None
    saved = None
    previous_resize = signal.getsignal(signal.SIGWINCH)

    def resize(*args):
        with suppress(OSError, termios.error):
            if input_fd is not None and os.isatty(input_fd):
                size = fcntl.ioctl(input_fd, termios.TIOCGWINSZ, b"\0" * 8)
                fcntl.ioctl(master, termios.TIOCSWINSZ, size)

    try:
        signal.signal(signal.SIGWINCH, resize)
        resize()
        helper = str(Path(__file__).with_name("pty_child.py").resolve())
        child = subprocess.Popen([sys.executable, helper, *command], env=env,
                                 stdin=slave, stdout=slave, stderr=slave, start_new_session=True)
        # Retain the slave until after draining: macOS can discard unread
        # output when the final slave closes. Child exit is observed via poll.
        os.set_blocking(master, False)
        if input_fd is not None and os.isatty(input_fd):
            saved = termios.tcgetattr(input_fd)
            tty.setraw(input_fd)
        pending = bytearray()
        source = input_fd
        while True:
            readers = [master]
            if source is not None and len(pending) < 65536:
                readers.append(source)
            readable, writable, _ = select.select(readers, [master] if pending else [], [], 0.2)
            if master in readable:
                try:
                    data = os.read(master, 65536)
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    data = b""
                if not data:
                    break
                output.feed(data)
            if source is not None and source in readable:
                data = os.read(source, 4096)
                if data:
                    pending.extend(data)
                else:
                    source = None
            if master in writable:
                try:
                    count = os.write(master, pending)
                    del pending[:count]
                except BlockingIOError:
                    pass
                except OSError as error:
                    if error.errno != errno.EIO:
                        raise
                    pending.clear()
                    source = None
            if child.poll() is not None:
                # Drain bytes written between select and observing exit. A
                # descendant retaining the slave must not extend this forever.
                for _ in range(16):
                    try:
                        final = os.read(master, 65536)
                    except BlockingIOError:
                        break
                    except OSError as error:
                        if error.errno == errno.EIO:
                            break
                        raise
                    if not final:
                        break
                    output.feed(final)
                break
        return child.wait(timeout=5)
    finally:
        try:
            signal.signal(signal.SIGWINCH, previous_resize)
            if child is not None and child.poll() is None:
                with suppress(ProcessLookupError):
                    child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    with suppress(ProcessLookupError):
                        child.kill()
                    child.wait()
        finally:
            # Resource restoration must survive child-shutdown errors too.
            if saved is not None:
                with suppress(OSError, termios.error):
                    termios.tcsetattr(input_fd, termios.TCSANOW, saved)
            with suppress(OSError):
                os.close(master)
            if slave is not None:
                with suppress(OSError):
                    os.close(slave)
            with suppress(OSError):
                output.finish()
