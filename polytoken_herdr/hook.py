"""Observational hook: empty stdout, exit zero, no authorization decisions."""
import json
import os
import sys

from .relay import report


def main():
    try:
        path = os.environ.get("POLYTOKEN_HERDR_SOCKET")
        token = os.environ.get("POLYTOKEN_HERDR_TOKEN")
        if not path or not token:
            return
        raw = sys.stdin.buffer.read(1048577)
        if len(raw) > 1048576:
            return
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            return
        message = {"event": os.environ.get("POLYTOKEN_HOOK_EVENT"),
                   "session": os.environ.get("POLYTOKEN_SESSION_ID")}
        for key in ("prompt_id", "interrogative_id"):
            if key in payload:
                message[key] = payload[key]
        report(path, token, message)
    except (OSError, ValueError, TypeError, RecursionError):
        # Reporting must never grant, deny, or delay an authorization decision.
        return


if __name__ == "__main__":
    main()
