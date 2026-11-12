"""Serialize TUI output and the built-in reporter's fixed callback frames.

Single-owner stream: the proxy is its only writer. Status snapshots may be
coalesced while an escape sequence is incomplete; raw TUI bytes are preserved.
"""
# pattern: Imperative Shell
from .terminal_stream import ReporterStream
from .report import RELEASE_OUTPUT


class SerializedOutput:
    def __init__(self, sink):
        self.sink = sink
        self.stream = ReporterStream()
        self.needs_cancel = False

    def _emit(self, data, bulk=False):
        if data:
            write = getattr(self.sink, "write_bulk", self.sink.write) if bulk else self.sink.write
            try:
                if self.needs_cancel:
                    write(b"\x18")
                write(data)
                self.sink.flush()
                self.needs_cancel = False
            except OSError:
                self.needs_cancel = True
                raise

    def feed(self, data):
        self._emit(self.stream.feed(data), bulk=True)

    def finish(self):
        incomplete = self.stream.mode != "text" or self.stream.utf8_remaining
        pending = self.stream.pending
        self.stream = ReporterStream()
        if incomplete:
            self._emit(b"\x18")
        if pending == RELEASE_OUTPUT:
            self._emit(pending)
