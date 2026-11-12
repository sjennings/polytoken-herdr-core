"""Parse the legacy Herdr reporter protocol without executing callback text."""
# pattern: Functional Core
from dataclasses import dataclass
import re

STATE_OUTPUT = {state: f"\x1b]7501;state={state}:app=polytoken\x1b\\".encode()
                for state in ("working", "idle", "blocked")}
RELEASE_OUTPUT = b"\x1b]7501;state=clear\x1b\\"


@dataclass(frozen=True, slots=True)
class Report:
    """Carry a fixed terminal sequence and an optional validated session ID."""
    output: bytes
    session: str | None = None


def session_id(value: str) -> str:
    """Validate a session ID before using it as a command operand or label."""
    if not re.fullmatch(r"[A-Za-z0-9._][A-Za-z0-9._-]*", value):
        raise ValueError("invalid Polytoken session ID")
    return value


def parse_report(arguments: list[str]) -> Report:
    """Translate legacy pane reports; never interpret a supplied resume command."""
    if not arguments:
        raise ValueError("missing pane callback")
    operation, *arguments = arguments
    if operation == "release-agent":
        return Report(RELEASE_OUTPUT)
    if operation == "report-metadata":
        return Report(b"")  # hc's OSC status has no model/facet metadata fields.
    if operation != "report-agent":
        raise ValueError("unsupported pane callback")
    fields = {}
    flags = {"--source", "--agent", "--state", "--message", "--seq", "--agent-session-id"}
    index = 0
    while index < len(arguments):
        flag = arguments[index]
        if flag == "--":
            break
        if flag not in flags:
            index += 1  # Pane operands and future flags are not executable input.
            continue
        if index + 1 == len(arguments) or arguments[index + 1] == "--":
            raise ValueError(f"missing value for {flag}")
        value = arguments[index + 1]
        if flag != "--message" and value.startswith("--"):
            raise ValueError(f"missing value for {flag}")
        if flag in fields:
            raise ValueError(f"duplicate {flag}")
        fields[flag] = value
        index += 2
    state = fields.get("--state")
    if state not in STATE_OUTPUT:
        raise ValueError("unsupported Polytoken state")
    identifier = fields.get("--agent-session-id")
    if identifier is not None:
        identifier = session_id(identifier)
    return Report(STATE_OUTPUT[state], identifier)


def polytoken_command(config: str | None, sessions: str | None, model: str | None,
                      prompt: str | None, resume: str | None = None) -> list[str]:
    """Build native Polytoken argv, preserving every option value as one operand."""
    command = ["polytoken"]
    if config is not None:
        command += ["--config-dir", str(config)]
    command += ["continue"] if resume is not None else ["new"]
    if sessions is not None:
        command += ["--sessions-dir", str(sessions)]
    if resume is not None:
        return command + ["--", session_id(resume)]
    if model:
        command += ["--model", model]
    if prompt:
        command += ["--prompt", prompt]
    return command
