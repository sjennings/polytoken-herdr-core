"""Launch one new Polytoken session in one hc-owned terminal."""
import os
import signal
from contextlib import contextmanager
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

from .config import validate, validate_global, global_directory, validate_project_with_global
from .relay import Relay
from .output import terminal_output
from .stream import SerializedOutput
from .proxy import run_proxy


def launch_command(name, cwd, config, model, prompt):
    if config is None:
        validate_global(global_directory())
        validate_project_with_global(cwd)
    else:
        config = Path(config).resolve()
        if config != (Path(cwd).resolve() / ".polytoken").resolve():
            raise ValueError("Polytoken hook discovery requires config at <cwd>/.polytoken")
        validate(config)
    command = ["hc", "run", "--bg", "--name", name, "--cwd", str(Path(cwd).resolve()),
               sys.executable, str(Path(__file__).with_name("entry.py").resolve()),
               "run"]
    command += ["--global"] if config is None else ["--config", str(config)]
    if model:
        command += ["--model", model]
    if prompt:
        command += ["--prompt", prompt]
    return command


def polytoken_command(config, sessions, model, prompt, resume=None):
    command = ["polytoken"]
    if config is not None:
        command += ["--config-dir", str(config)]
    if resume:
        return command + ["continue", "--", resume]
    command += ["new", "--sessions-dir", str(sessions)]
    if model:
        command += ["--model", model]
    if prompt:
        command += ["--prompt", prompt]
    return command


def cleanup_registry(root, env):
    try:
        subprocess.run(["polytoken", "reap", "--force", "--sessions-dir", str(root / "sessions")],
                       env=env, stdout=subprocess.DEVNULL, timeout=20, check=True)
    except (OSError, subprocess.SubprocessError) as error:
        raise RuntimeError(f"Daemon cleanup failed; registry retained at {root / 'sessions'}") from error
    shutil.rmtree(root)


def ignore_termination():
    for number in (signal.SIGTERM, signal.SIGHUP):
        signal.signal(number, signal.SIG_IGN)


@contextmanager
def termination_cleanup():
    signals = (signal.SIGTERM, signal.SIGHUP)
    previous = {number: signal.getsignal(number) for number in signals}

    def terminate(number, frame):
        # A repeated graceful termination must not interrupt registry cleanup.
        for item in signals:
            signal.signal(item, signal.SIG_IGN)
        raise SystemExit(128 + number)

    try:
        for number in signals:
            signal.signal(number, terminate)
        yield
    finally:
        for number, handler in previous.items():
            signal.signal(number, handler)


def wait_for_tui(command, env):
    child = subprocess.Popen(command, env=env)
    try:
        return child.wait()
    except BaseException:
        try:
            child.terminate()
        except ProcessLookupError:
            pass
        try:
            child.wait(timeout=5)
        except subprocess.TimeoutExpired:
            child.kill()
            child.wait()
        raise


@termination_cleanup()
def run(config, model, prompt, resume=None):
    if config is None:
        validate_global(global_directory())
        validate_project_with_global(Path.cwd())
    else:
        if Path(config).resolve() != (Path.cwd() / ".polytoken").resolve():
            raise ValueError("Polytoken hook discovery requires config at <cwd>/.polytoken")
        validate(config)
    if not os.environ.get("HC_TERMINAL_ID") or not sys.stdout.isatty():
        raise ValueError("run requires an hc terminal; use launch")
    root = Path(tempfile.mkdtemp(prefix="ph-", dir="/tmp"))
    env = dict(os.environ)
    try:
        with terminal_output() as sink:
            output = SerializedOutput(sink)
            with Relay(root / "relay.sock", output, clear_on_exit=True) as relay:
                env.update(POLYTOKEN_HERDR_SOCKET=str(relay.path), POLYTOKEN_HERDR_TOKEN=relay.token)
                try:
                    return run_proxy(polytoken_command(config, root / "sessions", model, prompt, resume),
                                     env, output)
                finally:
                    ignore_termination()
    finally:
        ignore_termination()
        # This registry belongs only to this launcher. Closing the TUI ends
        # the managed session; hc attach/detach leaves the TUI running.
        cleanup_registry(root, env)
