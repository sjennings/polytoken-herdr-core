import io
import unittest
from polytoken_herdr.stream import SerializedOutput


class SerializedOutputTests(unittest.TestCase):
    def test_status_does_not_interrupt_split_tui_control_sequence(self):
        sink = io.BytesIO()
        output = SerializedOutput(sink)
        output.feed(b"\x1b[31")
        output.write(b"\x1b]7501;state=blocked\x1b\\")
        self.assertEqual(sink.getvalue(), b"\x1b[31")
        output.feed(b"mtext")
        self.assertEqual(sink.getvalue(), b"\x1b[31m\x1b]7501;state=blocked\x1b\\text")

    def test_tui_output_uses_bulk_writer_not_short_status_deadline(self):
        class BudgetSink(io.BytesIO):
            bulk_calls = 0

            def write_bulk(self, data):
                self.bulk_calls += 1
                return super().write(data)

        sink = BudgetSink()
        output = SerializedOutput(sink)
        output.feed(b"screen")
        self.assertEqual(sink.bulk_calls, 1)
        output.write(b"STATUS")
        self.assertEqual(sink.bulk_calls, 1)
        self.assertEqual(sink.getvalue(), b"screenSTATUS")

    def test_partial_failed_status_is_cancelled_before_next_output(self):
        class PartialSink(io.BytesIO):
            fail = True

            def write(self, data):
                if self.fail:
                    self.fail = False
                    super().write(data[:5])
                    raise TimeoutError("partial write")
                return super().write(data)

        sink = PartialSink()
        output = SerializedOutput(sink)
        with self.assertRaises(TimeoutError):
            output.write(b"\x1b]7501;state=idle\x1b\\")
        output.feed(b"hello")
        self.assertEqual(sink.getvalue(), b"\x1b]750\x18hello")

    def test_clear_after_incomplete_child_output_cancels_sequence(self):
        sink = io.BytesIO()
        output = SerializedOutput(sink)
        output.feed(b"\x1b]unfinished")
        output.write(b"OLD")
        output.finish()
        output.write(b"CLEAR")
        self.assertEqual(sink.getvalue(), b"\x1b]unfinished\x18CLEAR")
