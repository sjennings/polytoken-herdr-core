#!/usr/bin/env python3
"""Scratch-test hook: retain field names and routing metadata, never tool input."""
import json
import os
from pathlib import Path
import sys
import uuid

payload = json.load(sys.stdin)
record = {
    "event": os.environ.get("POLYTOKEN_HOOK_EVENT"),
    "session": os.environ.get("POLYTOKEN_SESSION_ID"),
    "fields": sorted(payload),
    "interrogative_id_type": type(payload.get("interrogative_id")).__name__,
    "endpoint_inherited": os.environ.get("POLYTOKEN_HERDR_PROBE") == "present",
}
path = Path(os.environ["POLYTOKEN_HERDR_CAPTURE"])
(path / (uuid.uuid4().hex + ".json")).write_text(json.dumps(record))
if record["event"] == os.environ.get("POLYTOKEN_HERDR_WAIT_EVENT", "stop") and os.environ.get("POLYTOKEN_HERDR_DONE_URL"):
    import urllib.request
    request = urllib.request.Request(os.environ["POLYTOKEN_HERDR_DONE_URL"], data=b"{}")
    with urllib.request.urlopen(request, timeout=2):
        pass
# Empty stdout and exit 0 preserve the event's default proceed outcome.
