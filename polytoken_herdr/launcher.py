"""Launch attached Polytoken with its built-in Herdr status reporter."""
# pattern: Imperative Shell
import os
import signal
from contextlib import contextmanager
from pathlib import Path
import subprocess
import shutil
import sys
import tempfile

from .report import polytoken_command, session_id
from .reporter import reporter_environment
from .output import terminal_output
from .stream import SerializedOutput
from .proxy import run_proxy


def launch_command(name, cwd, config, model, prompt):
    command = ["hc", "run", "--bg", "--name", name, "--cwd", str(Path(cwd).resolve()),
               sys.executable, str(Path(__file__).with_name("entry.py").resolve()), "run"]
    command += ["--global"] if config is None else ["--config", str(Path(config).resolve())]
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
def run(config, model, prompt, resume=None, sessions=None):
    if resume is not None:
        session_id(resume)
    # Outside hc, use native Polytoken with no reporter or registry changes.
    if not os.environ.get("HC_TERMINAL_ID"):
        return wait_for_tui(polytoken_command(config, sessions, model, prompt, resume), dict(os.environ))
    # Explicit registries (including restore) belong to their original caller.
    # Never reap those registries or the user's default registry.
    if sessions is not None or resume is not None:
        sessions = str(Path(sessions).resolve()) if sessions is not None else None
        env = reporter_environment(dict(os.environ), sessions)
        with terminal_output() as sink:
            return run_proxy(polytoken_command(config, sessions, model, prompt, resume), env, SerializedOutput(sink))
    root = Path(tempfile.mkdtemp(prefix="ph-", dir="/tmp"))
    sessions = str(root / "sessions")
    env = reporter_environment(dict(os.environ), sessions)
    try:
        with terminal_output() as sink:
            return run_proxy(polytoken_command(config, sessions, model, prompt, resume), env, SerializedOutput(sink))
    finally:
        ignore_termination()
        cleanup_registry(root, env)
