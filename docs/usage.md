# Setup and use (experimental)

This adapter is experimental. Human-run tests confirmed startup, follow-up input,
and terminal shutdown with stock Polytoken. Some permission and cleanup paths
remain unverified. Do not rely on status as an authorization gate or as proof of
task completion.

## Requirements

- macOS or Linux with Unix sockets; Windows is not supported.
- Python 3.10+ using only the standard library.
- `hc` and `polytoken` on PATH. Development probes used hc 0.1.15 and
  Polytoken 0.9.4.
- A working Polytoken provider configuration, configured by the user.

From this checkout, prepare a NEW `.polytoken` directory in the target project.
On tested Polytoken 0.9.4, `--config-dir` loads model configuration but did not
redirect hook discovery in our runtime probe. The launcher therefore requires
`--config` to resolve to `<cwd>/.polytoken`. Existing directories are refused;
use a separate scratch project for evaluation rather than overwriting them.

Prepare:

```sh
python3 -m polytoken_herdr.cli prepare /absolute/project/path/.polytoken
```

The command refuses an existing directory. It writes only `hooks.json`; it does
not copy credentials or alter global/project hooks. Generated hooks reference
this checkout and Python interpreter by absolute path. Keep both in place, or
prepare a new directory after moving them. Add provider/model configuration to
that directory if needed. Normal Polytoken global configuration may still be
inherited: this directory is not a security sandbox and does not disable global
hooks or global permission rules.

Launch a new session:

```sh
python3 -m polytoken_herdr.cli launch \
  --name worker --cwd /absolute/project/path \
  --config /absolute/project/path/.polytoken \
  --model YOUR_MODEL --prompt 'Inspect the project and summarize its structure.'
```

This starts an hc-managed terminal containing the adapter wrapper and the stock
Polytoken TUI. The initial prompt is supplied with Polytoken's `--prompt`; it is
not typed into a possibly unready terminal. The wrapper creates a private
session registry and relay. Polytoken runs on a private PTY; the wrapper forwards
input and resize events and serializes TUI bytes with hook status reports so
OSC cannot interrupt a partially written control sequence. No shell interprets the prompt as a command.

## Global installation

Use `python3 -m polytoken_herdr.cli prepare --global` to add the hooks to
`$XDG_CONFIG_HOME/polytoken/hooks.json` (default `~/.config/polytoken/hooks.json`).
Existing entries are preserved. Before changing an existing file, the installer
saves `hooks.json.herdr-backup`; it refuses to overwrite an earlier backup.
Matching adapter hooks are left unchanged, while conflicting names or malformed
entries stop installation. Close other configuration editors during installation.

Launch with `--global` instead of `--config`. The launcher uses normal Polytoken
configuration discovery and rejects project hooks that disable or duplicate the
adapter entries. Outside managed launches, the hooks return without reporting
because no private relay connection is supplied.

To remove the installation, remove only the five `herdr-*` entries installed by
this adapter from the user hooks file. Restore the backup only if you have made
no subsequent changes to that file. Restart or reload Polytoken for hook changes
to take effect. Global hook discovery passed an isolated stock-daemon probe.
The human-run global TUI probe also passed its status and termination checks;
see the [verification record](review.md) for interaction limits.

## Observe and interact

```sh
hc get worker
hc read worker
hc wait worker
hc attach worker
```

Use `hc attach` to handle first-start legal acceptance, permission dialogs,
authentication, and questions yourself. Ctrl+\\ detaches the hc viewer without
ending the wrapper or Polytoken TUI. Do not use Polytoken's own detach/reattach
commands to move this managed session to another terminal: that is unsupported.
Closing its TUI ends the managed session and triggers private-registry cleanup.
The temporary registry is not durable session history.

Ordinary follow-up input uses `hc send worker 'Your next task'` only after the
human has completed startup and the session is ready. The human-run probe verified
`hc send --if idle --wait` returning idle on a new turn. Never send approval keys or
use `hc send --force` to get around a blocked permission/question. If a send
fails, inspect before retrying; do not assume it was undelivered.

Polytoken can run ordinary `hc` commands via its shell tool using the installed
herdr-core skill. Child work should follow that skill's ownership and cleanup
rules. This adapter neither adds privileged tools nor overrides permissions.

## Status meaning and limitations

- `idle`: session-start hook or model handback requested. Not proof of success,
  readiness for input, or absence of later work.
- `working`: a model turn is starting.
- `blocked`: at least one reported human prompt has not closed.
- `error`: the relay's retained human-prompt history reached its 4,096-ID limit;
  start a new managed session after handling pending work.
- No status: startup has not reported, the terminal finished, or reporting is
  unavailable. Do not infer a status from screen contents.

The adapter never emits `done`. Other hooks can continue a turn after `stop`.
Interrogative hooks are asynchronous, so status may lag. Delivery failures are
best effort: the hook never denies a tool or changes an approval decision just
because status reporting failed. Polytoken cancellation and subagent prompt
payloads still need runtime validation. A child sharing the user's environment
can read relay credentials; this protects against accidental cross-session
routing, not malicious code running as the same OS user.

### Output stalls

The wrapper serializes TUI output and status. Status-only writes have a 0.2-second
deadline; bulk TUI writes have a five-second deadline. A longer terminal stall
ends the managed session through cleanup rather than hanging indefinitely.
Status delivery is best effort during a stall, and reports deferred inside a
control sequence may be coalesced to the latest snapshot. A partial failed write
is cancelled before subsequent output to avoid leaving an unfinished OSC.

## Cleanup and recovery

The wrapper attempts cleanup on normal exit and SIGTERM/SIGHUP. If reaping
fails, it retains the private registry and prints its path; inspect that exact
registry rather than running a global reap. SIGKILL or machine loss cannot run
cleanup. Actual hc termination behavior still needs the runtime checks in
[review and acceptance checks](review.md). Do not treat unit tests as proof that
no daemon can remain after a forced termination.

## Checks

```sh
python3 -m unittest discover -s tests -v
python3 scripts/probe_hc.py
python3 scripts/probe_polytoken.py
python3 scripts/probe_polytoken.py --daemon
python3 scripts/probe_integration.py
```

Without a reusable profile, each run creates a fresh HOME and may show the legal
agreement again. For human-assisted checks, use a dedicated profile:

```sh
python3 scripts/probe_integration.py --interactive \
  --profile ~/.local/share/polytoken-herdr-test-profile
```

Choose a new directory on first use. Later runs retain that profile's settings
and any acceptance you gave there. The probe refuses existing unmarked directories;
do not point it at your normal HOME or Polytoken configuration. Project files and
hc runtime state remain disposable. Do not run concurrent probes with one profile.
The probe does not copy acceptance records or accept an agreement for you.

Run this in your own terminal. It attaches you directly to the disposable terminal.
Read and decide on the agreement yourself. If you proceed, wait for the mock
provider's OK reply, then detach with Ctrl+\\ (do not quit Polytoken). The probe
checks structured status, sends an ordinary `Reply OK again` prompt with
`hc send --if idle --wait`, and requires a newer turn returning to idle. It then
terminates its own terminal and checks hc reports it finished before removing
the test instance. That finished-state check does not prove all daemon descendants
were reaped. No `--force` send or automatic permission answer is used. Rejecting
or closing the session leaves validation incomplete. A human-run corrected interactive probe
passed initial status (idle, turn 1), ordinary guarded follow-up (idle, turn 2),
and hc termination (finished, exit 129, status cleared). Human permission paths,
reattachment, and absence of surviving daemon descendants remain separate checks. The probe does not
accept on your behalf. All probes use disposable state; they must never be
pointed at the user's live registry/core. See [feasibility](feasibility.md) for
observed evidence and unresolved verification.
