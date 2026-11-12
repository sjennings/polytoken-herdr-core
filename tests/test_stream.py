import unittest
from polytoken_herdr.terminal_stream import OutputStream


class StreamTests(unittest.TestCase):
    def test_split_csi_keeps_status_after_sequence(self):
        stream = OutputStream()
        self.assertEqual(stream.feed(b"\x1b[31"), b"\x1b[31")
        self.assertEqual(stream.status(b"STATUS"), b"")
        self.assertEqual(stream.feed(b"mtext"), b"mSTATUStext")

    def test_osc_bel_and_st_boundaries(self):
        for ending in (b"\x07", b"\x1b\\"):
            stream = OutputStream()
            stream.feed(b"\x1b]0;title")
            self.assertEqual(stream.status(b"STATUS"), b"")
            self.assertEqual(stream.feed(ending), ending + b"STATUS")

    def test_dcs_does_not_end_at_bel(self):
        stream = OutputStream()
        stream.feed(b"\x1bPpayload\x07")
        self.assertEqual(stream.status(b"STATUS"), b"")
        self.assertEqual(stream.feed(b"\x1b\\"), b"\x1b\\STATUS")

    def test_escape_intermediates_and_cancellation(self):
        stream = OutputStream()
        stream.feed(b"\x1b(")
        stream.status(b"STATUS")
        self.assertEqual(stream.feed(b"B"), b"BSTATUS")
        stream.feed(b"\x1b[12")
        stream.status(b"NEXT")
        self.assertEqual(stream.feed(b"\x18"), b"\x18NEXT")

    def test_pending_reports_are_bounded_and_keep_latest_snapshot(self):
        stream = OutputStream()
        stream.feed(b"\x1b[")
        for index in range(1000):
            self.assertEqual(stream.status(str(index).encode()), b"")
        self.assertEqual(stream.feed(b"m"), b"m999")

    def test_utf8_is_not_split_by_status(self):
        stream = OutputStream()
        self.assertEqual(stream.feed(b"\xe2"), b"\xe2")
        self.assertEqual(stream.status(b"STATUS"), b"")
        self.assertEqual(stream.feed(b"\x82\xac"), b"\x82\xacSTATUS")


class ReporterStreamTests(unittest.TestCase):
    def test_callback_inside_split_csi_is_moved_to_safe_boundary(self):
        from polytoken_herdr.terminal_stream import ReporterStream
        stream = ReporterStream()
        report = b"\x1b]7501;state=working:app=polytoken\x1b\\"
        output = stream.feed(b"\x1b[31") + stream.feed(report) + stream.feed(b"mtext")
        self.assertEqual(output, b"\x1b[31m" + report + b"text")

    def test_every_byte_split_and_unknown_escape_preserve_nonreport_output(self):
        from polytoken_herdr.terminal_stream import ReporterStream
        report = b"\x1b]7501;state=blocked:app=polytoken\x1b\\"
        original = b"hello\x1b]0;title\x1b\\\x1b[31m" + report + b"world\x1b[0m"
        for split in range(len(original) + 1):
            stream = ReporterStream()
            output = stream.feed(original[:split]) + stream.feed(original[split:])
            self.assertEqual(output, original)
        stream = ReporterStream()
        self.assertEqual(b"".join(stream.feed(bytes([byte])) for byte in original), original)
