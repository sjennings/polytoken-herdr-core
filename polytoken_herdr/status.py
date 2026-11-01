"""Reduce hook facts without treating handback as successful completion.

The caller serializes apply() and terminal writes. Arrival order is not source
order: closed interrogative IDs must remain known for this relay's lifetime.
"""


def identity(value):
    return isinstance(value, str) and 0 < len(value) <= 256 and value.isprintable()


class Status:
    def __init__(self, max_interrogatives=4096):
        self.max_interrogatives = max_interrogatives
        self.failed = False
        self.session = None
        self.prompt = None
        self.activity = "idle"
        self.pending = set()
        self.closed = set()

    @property
    def state(self):
        if self.failed:
            return "error"
        return "blocked" if self.pending else self.activity

    def apply(self, message):
        if not isinstance(message, dict) or not identity(message.get("session")):
            return None
        event = message.get("event")
        if self.session is None:
            if event != "session_start":
                return None
            self.session = message["session"]
            return self.state
        if message["session"] != self.session or self.failed:
            return None
        if event == "pre_model_turn":
            if not identity(message.get("prompt_id")):
                return None
            self.prompt = message["prompt_id"]
            self.activity = "working"
        elif event == "stop":
            if self.prompt is None or message.get("prompt_id") != self.prompt:
                return None
            self.activity = "idle"
        elif event in ("interrogative_wants_open", "interrogative_has_closed"):
            key = message.get("interrogative_id")
            if not identity(key):
                return None
            if key not in self.closed and key not in self.pending:
                if len(self.closed) + len(self.pending) >= self.max_interrogatives:
                    self.failed = True
                    return self.state
            if event == "interrogative_has_closed":
                self.closed.add(key)
                self.pending.discard(key)
            elif key not in self.closed:
                self.pending.add(key)
        else:
            return None
        return self.state
