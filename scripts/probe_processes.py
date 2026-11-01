"""Observe only a probe-owned launcher's descendants; never signal them."""
import os
import subprocess


def descendants(pid):
    pending = [pid]
    found = set()
    while pending:
        parent = pending.pop()
        result = subprocess.run(["pgrep", "-P", str(parent)], text=True,
                                capture_output=True, timeout=5)
        if result.returncode not in (0, 1):
            raise RuntimeError("Cannot enumerate probe descendants")
        for item in result.stdout.split():
            child = int(item)
            if child not in found:
                found.add(child)
                pending.append(child)
        if len(found) > 1024:
            raise RuntimeError("Probe process tree exceeded observation limit")
    return found


def assert_exited(pids):
    remaining = []
    for pid in sorted(pids):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        remaining.append(pid)
    if remaining:
        raise AssertionError(f"Observed probe processes still exist after shutdown: {remaining}")
    print("PASS: observed launcher descendants no longer exist (not proof against unobserved detached processes)")
