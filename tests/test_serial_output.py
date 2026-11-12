import io
import unittest
from polytoken_herdr.stream import SerializedOutput


class SerializedOutputTests(unittest.TestCase):
    def test_status_does_not_interrupt_split_tui_control_sequence(self):
        sink = io.BytesIO()
        output = SerializedOutput(sink)
        output.feed(b"\x1b[31")
        output.feed(b"\x1b]7501;state=blocked:app=polytoken\x1b\\")
        self.assertEqual(sink.getvalue(), b"\x1b[31")
        output.feed(b"mtext")
        self.assertEqual(sink.getvalue(), b"\x1b[31m\x1b]7501;state=blocked:app=polytoken\x1b\\text")

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
        self.assertEqual(sink.getvalue(), b"screen")

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
            output.feed(b"\x1b]7501;state=idle:app=polytoken\x1b\\")
        output.feed(b"hello")
        self.assertEqual(sink.getvalue(), b"\x1b]750\x18hello")

    def test_clear_after_incomplete_child_output_cancels_sequence(self):
        sink = io.BytesIO()
        output = SerializedOutput(sink)
        output.feed(b"\x1b]unfinished")
        output.feed(b"\x1b]7501;state=working:app=polytoken\x1b\\")
        output.finish()
        output.feed(b"CLEAR")
        self.assertEqual(sink.getvalue(), b"\x1b]unfinished\x18\x1b]7501;state=clear\x1b\\CLEAR")

    def test_finish_clears_status_when_no_release_arrived(self):
        sink = io.BytesIO()
        output = SerializedOutput(sink)
        output.feed(b"\x1b]7501;state=working:app=polytoken\x1b\\screen")
        output.finish()
        self.assertEqual(sink.getvalue(),
                         b"\x1b]7501;state=working:app=polytoken\x1b\\screen\x1b]7501;state=clear\x1b\\")


class ReporterFinishTests(unittest.TestCase):
    def test_release_waiting_on_incomplete_tui_sequence_is_emitted_on_finish(self):
        import io
        from polytoken_herdr.stream import SerializedOutput
        sink = io.BytesIO()
        output = SerializedOutput(sink)
        output.feed(b"\x1b[31")
        output.feed(b"\x1b]7501;state=clear\x1b\\")
        output.finish()
        self.assertTrue(sink.getvalue().endswith(b"\x18\x1b]7501;state=clear\x1b\\"))
