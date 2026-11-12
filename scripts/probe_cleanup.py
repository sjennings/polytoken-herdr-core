"""Stop only authenticated daemons created in a probe's private session tree."""
# pattern: Imperative Shell
from collections.abc import Callable
import json
import os
from pathlib import Path
import signal
import subprocess
import time
from urllib.request import Request, ProxyHandler, build_opener


def process_identity(pid: int) -> str | None:
    """Read an immediate process identity without signalling any process group."""
    result = subprocess.run(["ps", "-p", str(pid), "-o", "stat=,lstart=,command="],
                            capture_output=True, text=True, timeout=5, check=False)
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise RuntimeError("cannot verify probe daemon identity")
    value = result.stdout.strip()
    return None if not value or value.startswith("Z") else value.split(None, 1)[1]


def wait_exited(pid: int, identity: str, timeout: float) -> bool:
    """Bound the drain wait and treat a changed identity as the old process exiting."""
    deadline = time.monotonic() + timeout
    while process_identity(pid) == identity:
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.05)
    return True


def shutdown_registry(root: Path, timeout: float = 10) -> None:
    """Authenticate each owned daemon, terminate it, then verify its disappearance.

    The documented /health and /terminate routes avoid confirmation flags.
    Credential material remains local and is never printed or captured.
    """
    launch_path = str(root.absolute())
    root = root.resolve()
    opener = build_opener(ProxyHandler({}))
    paths = sorted((root / "sessions-v1").glob("*/record.json"))
    paths += sorted((root / "sessions").glob("*/record.json"))
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("refusing a registry outside the owned probe tree")
        record = json.loads(path.read_text())
        pid, port, identifier = record["pid"], record["port"], record["session_id"]
        if (type(pid) is not int or pid <= 1 or type(port) is not int or not 0 < port < 65536
                or identifier != path.parent.name or Path(record["project_path"]).resolve() != root):
            raise ValueError("probe daemon record does not match its private launch")
        identity = process_identity(pid)
        if identity is None:
            continue
        # The unique scratch path must also be present in the process command.
        if str(root) not in identity and launch_path not in identity:
            raise ValueError("probe daemon command does not name its private tree")
        credential = Path(record["credential_file_path"])
        if credential.is_symlink() or not credential.resolve().is_relative_to(root):
            raise ValueError("refusing a credential outside the owned probe tree")
        token = json.loads(credential.read_text())["token"]
        headers = {"Authorization": "Bearer " + token}
        address = f"http://127.0.0.1:{port}"
        with opener.open(Request(address + "/health", headers=headers), timeout=5) as response:
            health = json.load(response)
        if health.get("session_id") != identifier or health.get("pid") != pid:
            raise ValueError("authenticated daemon does not match the private record")
        with opener.open(Request(address + "/terminate", data=b"", headers=headers, method="POST"), timeout=5) as response:
            if response.status != 200:
                raise RuntimeError("probe daemon did not accept termination")
        if wait_exited(pid, identity, timeout):
            continue
        # Escalate only the immediate PID after rechecking its complete identity.
        for number in (signal.SIGTERM, signal.SIGKILL):
            if process_identity(pid) != identity:
                break
            try:
                os.kill(pid, number)
            except ProcessLookupError:
                break
            if wait_exited(pid, identity, 2):
                break
        else:
            raise RuntimeError("probe daemon did not exit; private registry retained")


def cleanup_actions(actions: list[Callable[[], object]]) -> None:
    """Attempt every cleanup, even on failure, without a second signal interrupting it."""
    from contextlib import ExitStack
    numbers = (signal.SIGINT, signal.SIGTERM, signal.SIGHUP)
    previous = {number: signal.getsignal(number) for number in numbers}
    try:
        for number in numbers:
            signal.signal(number, signal.SIG_IGN)
        with ExitStack() as stack:
            for action in reversed(actions):
                stack.callback(action)
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)
