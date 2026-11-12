"""Herdr app program entry and icon management for install.sh."""
import json
import os
import shutil
import tempfile
from pathlib import Path

PROGRAM_KEY = "polytoken"
ICON_RELPATH = "polytoken-icons/polytoken.webp"
BACKUP_NAME = "programs.json.herdr-backup"


def app_home():
    return Path(os.environ.get("HERDR_APP_HOME") or Path.home() / ".config" / "herdr-app")


def default_launcher():
    return Path.home() / ".local" / "bin" / "polytoken-herdr"


def program_entry(run):
    return {
        "name": "Polytoken",
        "icon": ICON_RELPATH,
        "tint": False,
        "tile": "#6d28d9",
        "run": list(run),
    }


def _icon_source():
    source = Path(__file__).resolve().parents[1] / "assets" / "polytoken.webp"
    if not source.is_file():
        raise ValueError(f"Icon missing from checkout: {source}")
    return source


def _install_icon(home):
    source = _icon_source()
    destination = Path(home) / ICON_RELPATH
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.is_file() and destination.read_bytes() == source.read_bytes():
        return
    temporary = destination.with_name(destination.name + ".tmp")
    shutil.copyfile(source, temporary)
    os.replace(temporary, destination)


def _atomic_write(target, document, original):
    fd, temporary = tempfile.mkstemp(prefix=".herdr-programs-", dir=target.parent)
    try:
        with os.fdopen(fd, "w") as output:
            json.dump(document, output, indent=2)
            output.write("\n")
        current = target.read_bytes() if target.exists() else None
        if current != original or target.is_symlink():
            raise ValueError("programs.json changed during the update; retry after inspecting it")
        os.replace(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def install_app(home, launcher):
    """Add this adapter's program entry and icon to a Herdr app home.

    Existing entries under other keys are preserved. A differing previous
    entry for this adapter is saved to programs.json.herdr-backup before it
    is updated (the first backup is retained). Unknown fields and match aliases
    are preserved. Returns True when programs.json changed.
    """
    home = Path(home)
    launcher = Path(launcher)
    if not launcher.exists():
        raise ValueError(f"Launcher not linked yet: {launcher}; run install.sh first")
    entry = program_entry([str(launcher), "run", "--global"])
    home.mkdir(parents=True, exist_ok=True)
    target = home / "programs.json"
    if target.is_symlink():
        raise ValueError("Refusing a symlinked programs.json")
    original = target.read_bytes() if target.exists() else None
    document = json.loads(original) if original is not None else {}
    if not isinstance(document, dict):
        raise ValueError("programs.json must contain an object")
    programs = document.get("programs")
    if programs is None:
        programs = {}
        document["programs"] = programs
    if not isinstance(programs, dict):
        raise ValueError('programs.json "programs" must contain an object')
    previous = programs.get(PROGRAM_KEY, {})
    if not isinstance(previous, dict):
        raise ValueError("polytoken program entry must contain an object")
    aliases = previous.get("match", [])
    if not isinstance(aliases, list) or not all(isinstance(alias, str) for alias in aliases):
        raise ValueError("polytoken match must contain an array of strings")
    entry = dict(previous, **entry)
    if programs.get(PROGRAM_KEY) == entry:
        _install_icon(home)
        return False
    backup_path = home / BACKUP_NAME
    if (PROGRAM_KEY in programs and original is not None
            and not (backup_path.exists() or backup_path.is_symlink())):
        # Refuse to overwrite an earlier recovery copy.
        with backup_path.open("xb") as backup:
            os.chmod(backup.name, 0o600)
            backup.write(original)
    programs[PROGRAM_KEY] = entry
    _atomic_write(target, document, original)
    _install_icon(home)
    return True


def remove_app(home):
    """Remove this adapter's program entry and icon from a Herdr app home.

    Other programs and the rest of the file are preserved. Returns the
    removed entry, or None when nothing was installed.
    """
    home = Path(home)
    target = home / "programs.json"
    removed = None
    if target.exists():
        if target.is_symlink():
            raise ValueError("Refusing a symlinked programs.json")
        original = target.read_bytes()
        document = json.loads(original)
        if not isinstance(document, dict):
            raise ValueError("programs.json must contain an object")
        programs = document.get("programs")
        if isinstance(programs, dict) and PROGRAM_KEY in programs:
            removed = programs.pop(PROGRAM_KEY)
            _atomic_write(target, document, original)
    icon = home / ICON_RELPATH
    if icon.is_symlink() or icon.exists():
        icon.unlink()
    try:
        icon.parent.rmdir()
    except OSError:
        pass  # Missing, or it holds other icons.
    return removed
