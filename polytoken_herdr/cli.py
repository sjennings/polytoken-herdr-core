"""Explicit configuration and hc-managed launch commands."""
import argparse
import subprocess
import sys
from pathlib import Path

from .appconfig import app_home, default_launcher, install_app, remove_app
from .config import global_directory, prepare, prepare_global, remove_global
from .launcher import launch_command, run
from .reporter import callback, restore_labels


def main():
    if sys.argv[1:2] == ["pane"]:
        try:
            return callback(sys.argv[2:])
        except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
            print(f"polytoken-herdr callback: {error}", file=sys.stderr)
            return 1
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("prepare", help="Create a config directory or remove obsolete project hooks")
    setup.add_argument("directory", nargs="?")
    setup.add_argument("--global", dest="global_config", action="store_true",
                       help="Remove obsolete global adapter hooks, preserving other entries")
    teardown = commands.add_parser("remove", help="Remove this adapter's hooks from the user configuration")
    teardown.add_argument("--global", dest="global_config", action="store_true",
                          help="Remove the adapter's global hook entries, keeping other entries")
    for name, help_text in (
        ("install-app", "Add the Polytoken program entry and icon to the Herdr app home"),
        ("remove-app", "Remove the adapter's program entry and icon from the Herdr app home"),
    ):
        command = commands.add_parser(name, help=help_text)
        command.add_argument("--home", help="Herdr app home (default: $HERDR_APP_HOME or ~/.config/herdr-app)")
    commands.add_parser("restore", help="Resume the session recorded on this hc terminal")
    for name in ("launch", "run"):
        command = commands.add_parser(name)
        location = command.add_mutually_exclusive_group(required=True)
        location.add_argument("--config")
        location.add_argument("--global", dest="global_config", action="store_true")
        command.add_argument("--model")
        command.add_argument("--prompt")
        if name == "launch":
            command.add_argument("--name", required=True)
            command.add_argument("--cwd", default=".")
        else:
            command.add_argument("--sessions-dir", help="Use a caller-owned native registry; it will not be reaped")
            command.add_argument("--continue", dest="resume", metavar="SESSION_ID",
                                 help="Resume a stored Polytoken session; --model and --prompt are ignored")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            if args.global_config:
                if args.directory:
                    parser.error("prepare --global does not accept a directory; use XDG_CONFIG_HOME")
                prepare_global(global_directory())
            else:
                if not args.directory:
                    parser.error("prepare requires a directory or --global")
                prepare(args.directory)
            return 0
        if args.command == "remove":
            if not args.global_config:
                parser.error("remove requires --global")
            directory = global_directory()
            removed = remove_global(directory)
            print(f"polytoken-herdr: removed {removed} adapter hook(s) from {directory / 'hooks.json'}"
                  if removed else "polytoken-herdr: no adapter hooks found")
            return 0
        if args.command in ("install-app", "remove-app"):
            home = Path(args.home) if args.home else app_home()
            if args.command == "install-app":
                changed = install_app(home, default_launcher())
                print(f"polytoken-herdr: {'updated' if changed else 'already present'}: {home / 'programs.json'}")
            else:
                entry = remove_app(home)
                print(f"polytoken-herdr: removed the Polytoken entry from {home / 'programs.json'}"
                      if entry is not None else "polytoken-herdr: no Polytoken entry found")
            return 0
        if args.command == "restore":
            identifier, sessions = restore_labels()
            return run(None, None, None, identifier, sessions)
        if args.command == "launch":
            return subprocess.call(launch_command(args.name, args.cwd, args.config, args.model, args.prompt))
        return run(args.config, args.model, args.prompt, args.resume, args.sessions_dir)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"polytoken-herdr: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
