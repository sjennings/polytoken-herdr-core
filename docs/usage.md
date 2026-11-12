# Setup and use (experimental)

Use Python 3.10+ on Unix, stock Polytoken and herdr-core (`hc`). The adapter uses only the Python standard library. Current local checks use Polytoken 0.9.7 and hc 0.1.20 on macOS. The operator decided the first-run agreement in a dedicated scratch profile; native start, release, restore and blocked-input checks then passed without further dialog responses. See [the verification record](review.md).

## Installation and migration

Run `./install.sh` from the checkout. It links the launcher, skill and mod, installs the menu entry and icon, and removes the old adapter's global hooks. `./uninstall.sh` unlinks this checkout and removes its menu entry, icon and obsolete hooks. Tests run both scripts in temporary homes.

The global hook location is `$XDG_CONFIG_HOME/polytoken/hooks.json`, defaulting to `~/.config/polytoken/hooks.json`. Migration removes these exact names, regardless of their old handler path, plus string entries disabling them:

- `herdr-session_start`
- `herdr-pre_model_turn`
- `herdr-stop`
- `herdr-interrogative_wants_open`
- `herdr-interrogative_has_closed`

Other entries are preserved. The original file is saved as `hooks.json.herdr-backup` if no earlier backup exists. Malformed JSON and symlinked hook files are refused. Close configuration editors while migrating. Already-running Polytoken daemons may retain old hooks until restarted; the installer does not drive those sessions. Unmigrated entries call `polytoken-herdr hook`, which now does nothing and exits 0.

`polytoken-herdr prepare --global` and `remove --global` both perform that cleanup. They install no new hooks. `prepare DIRECTORY` creates the directory if needed and migrates any old adapter hooks there, preserving provider configuration. `--config DIRECTORY` passes the directory to Polytoken; status no longer depends on Polytoken's project hook-discovery rules. `--global` uses native configuration discovery.

Installer reruns update the owned menu fields and launch command while preserving other program entries, unknown fields and existing match aliases. They retain the first `programs.json.herdr-backup`.

## Launch and interact

In a Herdr app pane or another hc terminal:

```sh
polytoken-herdr run --global
polytoken-herdr run --global --model YOUR_MODEL --prompt 'Inspect the project.'
```

The shell alias `polytoken='polytoken-herdr run --global'` continues to work. Outside hc, `run` launches native Polytoken with the requested configuration, model and prompt, without adding reporter variables or a private registry.

For direct herdr-core users, launch a separate terminal:

```sh
polytoken-herdr launch --global --name worker --cwd /absolute/project \
  --model YOUR_MODEL --prompt 'Inspect the project.'
hc attach worker
```

The Herdr app invokes terminal controls automatically. When using hc directly, Ctrl+\\ detaches its viewer; `hc get worker` reads status and `hc send worker 'Next task' --if idle --wait` sends ordinary work. `hc kill worker` and `hc rm worker` finish it. Inspect a failed send before retrying. Humans handle agreements, authentication, permissions and questions; never send approval keys or force a blocked send.

## Status meaning and limitations

[Polytoken's reporter](https://docs.polytoken.dev/using-polytoken/tui-orchestrators/) decides status:

| State | Meaning |
| --- | --- |
| `working` | A turn or background work is pending/running; services are excluded. |
| `idle` | No turn or background work is pending. This does not establish success. |
| `blocked` | A human decision is pending, including questions, permissions, goals or plan review. |
| No status | Release cleared status, startup has not reported, or reporting is unavailable. |

The adapter never emits `done`. It sets `HERDR_ENV=1`, `HERDR_PANE_ID` to the hc terminal ID and `HERDR_BIN_PATH` to this checkout's executable launcher. The callback marker binds reports to that terminal. These variables also activate Polytoken's legacy Herdr detection, including its bundled skill and keyboard mode; they do not emulate the older Herdr CLI. Use hc's own skill for terminal management.

Callbacks reopen `/dev/tty`, because their standard streams may be null. The private PTY proxy extracts only the four fixed callback OSC sequences and serializes them with TUI output at complete control-sequence and UTF-8 boundaries. A direct-write probe reproduced split-CSI corruption without this proxy. Unknown output remains TUI output; no screen text is used to infer status. Model/facet metadata is ignored because OSC 7501 has no equivalent fields.

This removes the old hook-event reduction, hook discovery dependency and relay socket. Reports still depend on successful callbacks and terminal output. Status-only writes have a 0.2-second deadline and bulk output has five seconds. A report arriving during an incomplete TUI sequence is deferred; pending snapshots can be coalesced. When the run ends, the adapter cancels any incomplete sequence and writes a clear itself, whether or not Polytoken's release arrived. Callback or label failures are not proof that hc observed a state. If the adapter itself is killed, the last status can remain. The adapter does not change permissions or provide a security boundary against processes running as the same OS user.

## Resume and restore

```sh
polytoken-herdr run --global --continue SESSION_ID
polytoken-herdr restore
```

`--continue` ignores `--model` and `--prompt` and uses native history/registry discovery. `restore` reads `polytoken.session` and `polytoken.sessions_dir` labels from the current terminal, validates the ID and directory, and resumes that session. Callback-supplied command text is never executed. IDs use ASCII letters, numbers, dot, underscore and dash, and cannot start with dash.

`run --sessions-dir DIRECTORY` (also `--sessions-dir=DIRECTORY`) selects a caller-owned registry, including for restore. Its path is recorded absolutely. The adapter never reaps or deletes an explicit registry or the native registry of a resumed session. Closing a resumed TUI leaves its daemon detached. A newly attached TUI is expected to own its reporter callbacks even when the daemon already exists; that behavior passed an isolated stock-TUI check with the retained registry. A new managed session's private tree is deleted on cleanup, so its recorded label cannot restore history that has already been deleted. Native and explicit registries are retained; durable restoration of disposable managed sessions is not implemented.

## Cleanup and recovery

A new managed session without `--sessions-dir` gets a private temporary registry. Normal exit or SIGTERM/SIGHUP attempts to reap only that registry. Reap failure retains it and reports the exact path. SIGKILL and machine loss cannot run cleanup. The proxy signals its immediate child; neither a finished hc terminal nor the disappearance of observed descendants establishes exhaustive detached-process cleanup.

## Checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/probe_reporter.py
python3 scripts/probe_stock_reporter.py
```

The callback probe creates a private HOME, XDG directories, socket, unique HC_SESSION and terminal. It verifies working, idle, blocked, release and a deliberately split CSI using null callback streams, then removes only its own terminal/core and compares the default session's terminal identities before and after.

The stock probe uses a local mock provider, disables update checks only in its scratch global config, records callback arguments, and shows any startup decision without answering it. `--interactive --question --profile DIRECTORY` lets a human perform the agreement and question checks in a new or probe-marked profile; it never supplies an answer. The probe stops its owned TUI and authenticates daemons from its private registry before requesting shutdown. A process that ignores shutdown is signalled only after its PID, start time and command are rechecked. All cleanup steps run even if an earlier step fails. It uses no forced CLI option. A failed cleanup retains its private directory for inspection. Reaching a licence agreement is an incomplete stock reporter check, not a pass. Neither probe copies acceptance records.

For the human check, run one command from the checkout:

```sh
python3 scripts/probe_stock_reporter.py --human
```

The first attachment asks you to decide the agreement, wait for the mock-provider OK and detach with Ctrl+\\. The probe then requests one ordinary test question from idle and attaches again. Inspect the question and detach; you may leave it unanswered. Rejecting the agreement, quitting the TUI, Ctrl+C or closing the probe triggers cleanup. A first attachment that never reaches idle is recorded as incomplete, with exit code 2.

Every run prints its evidence path. Each exact HC_SESSION is recorded before a core starts in an exclusive per-session journal; later runs cannot replace it. `--capture-dir DIRECTORY` collects those journals and raw callback arguments in a chosen directory. To retain only choices you make yourself for a later run, also pass `--profile DIRECTORY`, using a new or probe-marked private directory. Use one probe at a time per profile. The older combined launcher probe is a separate check and is not needed for this one-command reporter check.
