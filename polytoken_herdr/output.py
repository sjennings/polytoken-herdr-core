"""Bounded writes through a separately opened nonblocking terminal descriptor."""
import os
import select
import time
from contextlib import contextmanager


class StatusOutput:
    def __init__(self, fd, timeout=0.2):
        if os.get_blocking(fd):
            raise ValueError("Status output requires an independently opened nonblocking descriptor")
        self.fd = fd
        self.timeout = timeout

    def write(self, data):
        return self._write(data, self.timeout)

    def write_bulk(self, data):
        return self._write(data, 5.0)

    def _write(self, data, timeout):
        deadline = time.monotonic() + timeout
        remaining = memoryview(data)
        while remaining:
            wait = deadline - time.monotonic()
            if wait <= 0 or not select.select([], [self.fd], [], wait)[1]:
                raise TimeoutError("Terminal status output stalled")
            try:
                written = os.write(self.fd, remaining)
            except BlockingIOError:
                continue
            if written == 0:
                raise OSError("Terminal status output closed")
            remaining = remaining[written:]
        return len(data)

    def flush(self):
        pass  # os.write is unbuffered.


@contextmanager
def terminal_output():
    # Never use dup(stdout): dup shares file flags with the TUI descriptor.
    fd = os.open("/dev/tty", os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
    try:
        yield StatusOutput(fd)
    finally:
        os.close(fd)
