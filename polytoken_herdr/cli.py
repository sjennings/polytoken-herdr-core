"""Explicit configuration and hc-managed launch commands."""
import argparse
import subprocess
import sys

from .config import prepare, prepare_global, global_directory
from .launcher import launch_command, run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    setup = commands.add_parser("prepare", help="Create hooks in a NEW dedicated config directory")
    setup.add_argument("directory", nargs="?")
    setup.add_argument("--global", dest="global_config", action="store_true",
                       help="Add hooks to the user configuration, preserving existing entries")
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
        if args.command == "launch":
            return subprocess.call(launch_command(args.name, args.cwd, args.config, args.model, args.prompt))
        return run(args.config, args.model, args.prompt)
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        print(f"polytoken-herdr: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
