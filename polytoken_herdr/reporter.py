"""Receive Polytoken's legacy pane callbacks and reopen their controlling tty."""
# pattern: Imperative Shell
import json
import os
from pathlib import Path
import subprocess

from .output import terminal_output
from .report import parse_report, session_id


def reporter_environment(original: dict[str, str], sessions: str | None) -> dict[str, str]:
    """Bind callbacks to this checkout only when running in an hc terminal."""
    env = dict(original)
    terminal = env.get("HC_TERMINAL_ID")
    if not terminal:
        return env
    env.update(HERDR_ENV="1", HERDR_PANE_ID=terminal,
               HERDR_BIN_PATH=str(Path(__file__).resolve().parents[1] / "bin" / "polytoken-herdr"),
               POLYTOKEN_HERDR_REPORTER="1", POLYTOKEN_HERDR_SESSIONS_DIR=sessions or "")
    return env


def callback(arguments: list[str]) -> int:
    """Translate one callback; stdout/stderr may both be /dev/null."""
    terminal = os.environ.get("HC_TERMINAL_ID")
    if (os.environ.get("POLYTOKEN_HERDR_REPORTER") != "1" or not terminal
            or os.environ.get("HERDR_PANE_ID") != terminal):
        raise ValueError("pane callbacks require a bound polytoken-herdr terminal")
    report = parse_report(arguments)
    if report.output:
        with terminal_output() as output:
            output.write(report.output)
    if report.session:
        # Synchronous bounded label write: no detached processes or stale label races
        # introduced by this adapter. A failed label update is a callback failure.
        subprocess.run(["hc", "label", terminal, "polytoken.session=" + report.session,
                        "polytoken.sessions_dir=" + os.environ.get("POLYTOKEN_HERDR_SESSIONS_DIR", "")],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=1, check=True)
    return 0


def restore_labels() -> tuple[str, str | None]:
    """Read a validated session and registry from the current terminal's labels."""
    terminal = os.environ.get("HC_TERMINAL_ID")
    if not terminal:
        raise ValueError("restore requires an hc terminal")
    record = subprocess.run(["hc", "get", "--json", terminal], stdin=subprocess.DEVNULL,
                            capture_output=True, text=True, timeout=5, check=True)
    document = json.loads(record.stdout)
    labels = document.get("labels") if isinstance(document, dict) else None
    if not isinstance(labels, dict) or not isinstance(labels.get("polytoken.session"), str):
        raise ValueError("missing Polytoken session label")
    identifier = session_id(labels["polytoken.session"])
    directory = labels.get("polytoken.sessions_dir", "")
    if not isinstance(directory, str) or "\0" in directory or (directory and not Path(directory).is_absolute()):
        raise ValueError("invalid Polytoken sessions directory label")
    return identifier, directory or None
