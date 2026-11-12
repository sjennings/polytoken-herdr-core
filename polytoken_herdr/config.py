"""Remove obsolete adapter hooks while preserving the user's configuration."""
# pattern: Imperative Shell
import json
import os
import tempfile
from pathlib import Path

LEGACY_NAMES = {"herdr-" + event for event in (
    "session_start", "pre_model_turn", "stop", "interrogative_wants_open", "interrogative_has_closed")}


def global_directory() -> Path:
    """Locate Polytoken's user configuration without reading its contents."""
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config") / "polytoken"


def prepare(path: str | Path) -> None:
    """Create a project config directory or migrate its obsolete adapter hooks."""
    Path(path).mkdir(mode=0o700, parents=True, exist_ok=True)
    remove_global(path)


def prepare_global(path: str | Path) -> None:
    """Migrate old global hooks; the built-in reporter needs no installed hooks."""
    remove_global(path)


def remove_global(path):
    """Remove this adapter's global hooks, including stale copies.

    Owns the ``herdr-<event>`` names: entries carrying them are removed
    whatever handler they name (a moved checkout leaves stale entries), and
    so are string entries disabling them. Other entries are preserved.
    Returns the number of entries removed.
    """
    path = Path(path)
    target = path / "hooks.json"
    if target.is_symlink():
        raise ValueError("Refusing a symlinked hooks.json")
    if not target.exists():
        return 0
    original = target.read_bytes()
    entries = json.loads(original)
    if not isinstance(entries, list):
        raise ValueError("hooks.json must contain an array")
    names = LEGACY_NAMES

    def ours(entry):
        if isinstance(entry, dict):
            return isinstance(entry.get("name"), str) and entry["name"] in names
        if isinstance(entry, str):
            return entry.lstrip("!") in names
        return False

    kept = [entry for entry in entries if not ours(entry)]
    removed = len(entries) - len(kept)
    if not removed:
        return 0
    backup = path / "hooks.json.herdr-backup"
    if not (backup.exists() or backup.is_symlink()):
        with backup.open("xb") as output:
            os.chmod(output.name, 0o600)
            output.write(original)
    fd, temporary = tempfile.mkstemp(prefix=".herdr-hooks-", dir=path)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(kept, output, indent=2)
            output.write("\n")
        current = target.read_bytes()
        if current != original or target.is_symlink():
            raise ValueError("hooks.json changed during removal; retry after inspecting it")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)
    return removed
