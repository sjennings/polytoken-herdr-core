import unittest

from polytoken_herdr.status import Status


class StatusTests(unittest.TestCase):
    def event(self, state, event, **fields):
        return state.apply({"session": "session-a", "event": event, **fields})

    def test_only_session_start_can_bind_and_other_sessions_cannot_change_status(self):
        state = Status()
        self.assertIsNone(self.event(state, "pre_model_turn", prompt_id="a"))
        self.assertEqual(self.event(state, "session_start"), "idle")
        self.assertIsNone(state.apply({"session": "other", "event": "pre_model_turn"}))
        self.assertEqual(state.state, "idle")

    def test_handback_is_idle_not_success(self):
        state = Status()
        self.event(state, "session_start")
        self.event(state, "pre_model_turn", prompt_id="a")
        self.assertEqual(self.event(state, "stop", prompt_id="a"), "idle")

    def test_old_handback_does_not_override_new_prompt(self):
        state = Status()
        self.event(state, "session_start")
        self.event(state, "pre_model_turn", prompt_id="a")
        self.event(state, "pre_model_turn", prompt_id="b")
        self.assertIsNone(self.event(state, "stop", prompt_id="a"))
        self.assertEqual(state.state, "working")

    def test_multiple_prompts_keep_status_blocked_until_all_close(self):
        state = Status()
        self.event(state, "session_start")
        self.event(state, "pre_model_turn", prompt_id="a")
        for identity in ("one", "two"):
            self.event(state, "interrogative_wants_open", interrogative_id=identity)
        self.event(state, "stop", prompt_id="a")
        self.assertEqual(state.state, "blocked")
        self.event(state, "interrogative_has_closed", interrogative_id="one")
        self.assertEqual(state.state, "blocked")
        self.event(state, "interrogative_has_closed", interrogative_id="two")
        self.assertEqual(state.state, "idle")

    def test_close_before_open_cannot_resurrect_prompt(self):
        state = Status()
        self.event(state, "session_start")
        self.event(state, "interrogative_has_closed", interrogative_id="one")
        self.event(state, "interrogative_wants_open", interrogative_id="one")
        self.assertEqual(state.state, "idle")

    def test_late_session_start_does_not_reset_work(self):
        state = Status()
        self.event(state, "session_start")
        self.event(state, "pre_model_turn", prompt_id="a")
        self.assertIsNone(self.event(state, "session_start"))
        self.assertEqual(state.state, "working")

    def test_prompt_history_limit_fails_visibly_without_forgetting_closed_ids(self):
        state = Status(max_interrogatives=2)
        self.event(state, "session_start")
        for key in ("one", "two", "three"):
            self.event(state, "interrogative_has_closed", interrogative_id=key)
        self.assertEqual(state.state, "error")
        self.event(state, "pre_model_turn", prompt_id="new")
        self.assertEqual(state.state, "error")
        self.assertLessEqual(len(state.closed), 2)

    def test_malformed_identity_and_unknown_events_are_ignored(self):
        state = Status()
        for message in ({}, {"session": [], "event": "session_start"},
                        {"session": "a", "event": "unexpected"}):
            self.assertIsNone(state.apply(message))
        self.assertIsNone(state.session)


if __name__ == "__main__":
    unittest.main()
