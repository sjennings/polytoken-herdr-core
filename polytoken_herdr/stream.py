"""Track output boundaries, never interpret terminal contents as agent status.

Single-owner stream: callers serialize feed/status. Status snapshots may be
coalesced while an escape sequence is incomplete; raw TUI bytes are preserved.
"""


import threading


class SerializedOutput:
    def __init__(self, sink):
        self.sink = sink
        self.stream = OutputStream()
        self.lock = threading.Lock()
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
        with self.lock:
            self._emit(self.stream.feed(data), bulk=True)

    def write(self, data):
        with self.lock:
            self._emit(self.stream.status(data))
        return len(data)

    def flush(self):
        pass  # Sink flush is part of each serialized write.

    def finish(self):
        with self.lock:
            incomplete = self.stream.mode != "text" or self.stream.utf8_remaining
            self.stream = OutputStream()
            if incomplete:
                self._emit(b"\x18")


class OutputStream:
    def __init__(self):
        self.mode = "text"
        self.string_kind = None
        self.utf8_remaining = 0
        self.pending = b""

    def status(self, data):
        self.pending = data
        return self._drain()

    def _drain(self):
        if self.mode == "text" and not self.utf8_remaining:
            data, self.pending = self.pending, b""
            return data
        return b""

    def feed(self, data):
        output = bytearray()
        for byte in data:
            output.append(byte)
            self._advance(byte)
            output.extend(self._drain())
        return bytes(output)

    def _advance(self, byte):
        if self.utf8_remaining:
            if 0x80 <= byte <= 0xBF:
                self.utf8_remaining -= 1
                return
            self.utf8_remaining = 0
        if 0xC2 <= byte <= 0xF4:
            self.utf8_remaining = 1 if byte < 0xE0 else (2 if byte < 0xF0 else 3)
            return
        if byte in (0x18, 0x1A):
            self.mode = "text"
        elif self.mode in ("string", "string_escape"):
            if (self.mode == "string_escape" and byte == 0x5C) or (self.string_kind == "osc" and byte == 7):
                self.mode = "text"
            else:
                self.mode = "string_escape" if byte == 0x1B else "string"
        elif byte == 0x1B:
            self.mode = "escape"
        elif self.mode == "escape":
            if byte == 0x5B:
                self.mode = "csi"
            elif byte in (0x5D, 0x50, 0x58, 0x5E, 0x5F):
                self.mode = "string"
                self.string_kind = "osc" if byte == 0x5D else "other"
            elif 0x20 <= byte <= 0x2F:
                self.mode = "intermediate"
            elif 0x30 <= byte <= 0x7E:
                self.mode = "text"
        elif self.mode == "intermediate" and 0x30 <= byte <= 0x7E:
            self.mode = "text"
        elif self.mode == "csi" and 0x40 <= byte <= 0x7E:
            self.mode = "text"
