"""Explicit opt-in configuration; never merge or overwrite existing hooks."""
import json
import os
import tempfile
from pathlib import Path
import shlex
import sys

EVENTS = ("session_start", "pre_model_turn", "stop",
          "interrogative_wants_open", "interrogative_has_closed")


def hooks():
    entry = Path(__file__).with_name("entry.py").resolve()
    command = shlex.join([sys.executable, str(entry), "hook"])
    return [{"name": "herdr-" + event, "event": event, "handler": {"bash": command}}
            for event in EVENTS]


def prepare(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=False)
    (path / "hooks.json").write_text(json.dumps(hooks(), indent=2) + "\n")


def global_directory():
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "polytoken"


def _global_entries(path):
    target = Path(path) / "hooks.json"
    if target.is_symlink():
        raise ValueError("Refusing a symlinked hooks.json")
    original = target.read_bytes() if target.exists() else None
    entries = json.loads(original) if original is not None else []
    if not isinstance(entries, list):
        raise ValueError("hooks.json must contain an array")
    expected = {entry["name"]: entry for entry in hooks()}
    seen = set()
    for entry in entries:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(entry, (dict, str)) or (isinstance(entry, dict) and not isinstance(name, str)):
            raise ValueError("Invalid hook entry or name")
        if isinstance(entry, str) and entry.lstrip("!") in expected:
            raise ValueError("Adapter hooks are disabled by an existing entry")
        if name in expected:
            if name in seen or entry != expected[name]:
                raise ValueError(f"Conflicting adapter hook: {name}")
            seen.add(name)
    return target, original, entries, seen


def prepare_global(path):
    path = Path(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    target, original, entries, seen = _global_entries(path)
    missing = [entry for entry in hooks() if entry["name"] not in seen]
    if not missing:
        return
    # Refuse to overwrite an earlier recovery copy.
    if original is not None:
        with (path / "hooks.json.herdr-backup").open("xb") as backup:
            os.chmod(backup.name, 0o600)
            backup.write(original)
    fd, temporary = tempfile.mkstemp(prefix=".herdr-hooks-", dir=path)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(entries + missing, output, indent=2)
            output.write("\n")
        current = target.read_bytes() if target.exists() else None
        if current != original or target.is_symlink():
            raise ValueError("hooks.json changed during installation; retry after inspecting it")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def validate_project_with_global(cwd):
    target = Path(cwd) / ".polytoken" / "hooks.json"
    if not target.exists():
        return
    entries = json.loads(target.read_text())
    if not isinstance(entries, list):
        raise ValueError("Invalid project hooks array")
    names = {entry["name"] for entry in hooks()}
    for entry in entries:
        if isinstance(entry, str) and entry.lstrip("!") in names:
            raise ValueError("A project entry disables global adapter hooks")
        if isinstance(entry, dict) and isinstance(entry.get("name"), str) and entry["name"] in names:
            raise ValueError("Duplicate adapter hooks in project; choose one installation scope")


def validate_global(path):
    _, _, _, seen = _global_entries(path)
    if seen != {entry["name"] for entry in hooks()}:
        raise ValueError("Global adapter hooks are missing; run prepare --global first")


def validate(path):
    actual = json.loads((Path(path) / "hooks.json").read_text())
    if actual != hooks():
        raise ValueError("Dedicated hooks differ from this adapter; prepare a new config directory")
