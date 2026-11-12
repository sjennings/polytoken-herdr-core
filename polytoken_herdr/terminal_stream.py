"""Preserve terminal boundaries while extracting fixed reporter frames."""
# pattern: Functional Core
from .report import STATE_OUTPUT, RELEASE_OUTPUT


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


class ReporterStream(OutputStream):
    """Extract fixed inline callback frames before serializing TUI boundaries.

    A callback writes to the child's controlling tty. Its frame may interrupt
    a TUI escape sequence, so remove it from the TUI stream and reinsert it at
    the next complete sequence boundary. Prefix buffering is bounded by the
    longest fixed frame; unrecognized bytes remain ordinary terminal output.
    """
    FRAMES = tuple(STATE_OUTPUT.values()) + (RELEASE_OUTPUT,)

    def __init__(self):
        super().__init__()
        self.candidate = b""

    def feed(self, data):
        output = bytearray()
        for byte in data:
            self.candidate += bytes([byte])
            while self.candidate:
                if self.candidate in self.FRAMES:
                    output.extend(self.status(self.candidate))
                    self.candidate = b""
                elif any(frame.startswith(self.candidate) for frame in self.FRAMES):
                    break
                else:
                    output.extend(super().feed(self.candidate[:1]))
                    self.candidate = self.candidate[1:]
        return bytes(output)
