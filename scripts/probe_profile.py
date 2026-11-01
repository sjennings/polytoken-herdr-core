"""Explicit reusable test identity, separate from disposable runtime state."""
import os
from pathlib import Path

MARKER = ".polytoken-herdr-probe"


def prepare_profile(directory):
    path = Path(directory).expanduser().absolute()
    if path.is_symlink():
        raise ValueError("Test profile must not be a symlink")
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=False)
    except FileExistsError:
        info = path.stat()
        marker = path / MARKER
        if info.st_uid != os.getuid() or info.st_mode & 0o077 or marker.is_symlink() or not marker.is_file():
            raise ValueError("Refusing an existing directory that is not a private test profile")
        if marker.read_text() != "polytoken-herdr test profile v1\n":
            raise ValueError("Unrecognized test profile")
    else:
        (path / MARKER).write_text("polytoken-herdr test profile v1\n")
    return path
