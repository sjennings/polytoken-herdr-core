"""Keep one durable, never-replaced evidence journal per isolated core session."""
# pattern: Imperative Shell
import json
import os
from pathlib import Path
import re
import tempfile


class Capture:
    """Record the generated session before provisioning any runtime resources."""
    def __init__(self, session: str, directory: Path | None = None) -> None:
        if not re.fullmatch(r"(?:phc-|probe-)[A-Za-z0-9_-]+", session):
            raise ValueError("invalid probe session name")
        directory = directory or Path(tempfile.mkdtemp(prefix="phc-captures-", dir="/tmp"))
        directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.path = directory / (session + ".jsonl")
        self.session = session
        with self.path.open("x"):
            os.chmod(self.path, 0o600)
        self.write("created")
        print("capture:", self.path, flush=True)

    def write(self, event: str, **details: object) -> None:
        """Append nonsecret evidence with its exact session identity and sync it."""
        with self.path.open("a") as output:
            output.write(json.dumps(dict(details, session=self.session, event=event)) + "\n")
            output.flush()
            os.fsync(output.fileno())
