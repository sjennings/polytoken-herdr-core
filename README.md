# polytoken-herdr-core

Run [Polytoken](https://docs.polytoken.dev/) in a [herdr-core](https://github.com/herdrdev/herdr-core) terminal, send it work with `hc`, and see when it is working or waiting for you.

This adapter works with stock Polytoken. It uses hooks to report session status to herdr-core and keeps the Polytoken terminal available through `hc attach`. You handle permissions, questions, and first-run agreements yourself.

The project is experimental. Human-run tests have confirmed startup, a follow-up prompt, and terminal shutdown with Polytoken 0.9.4 and hc 0.1.15 on macOS. Status reports can arrive late or be lost; `idle` does not mean a task succeeded.

## Try it

You need Python 3.10 or later, `polytoken` and `hc` on your PATH, and a working Polytoken model configuration. The adapter uses Python's standard library. It requires Unix sockets and a PTY; Windows is unsupported, and Linux has not yet been runtime-tested here.

Run the following commands from this checkout. Choose a project with no existing `.polytoken` directory:

```sh
python3 -m polytoken_herdr.cli prepare /absolute/project/path/.polytoken
```

This creates the adapter's hooks. It refuses to overwrite an existing directory. Configure your provider and model there if needed; see [setup details](docs/usage.md). Global Polytoken settings may still apply.

Launch a session, replacing `YOUR_MODEL` with your configured model name:

```sh
python3 -m polytoken_herdr.cli launch \
  --name worker \
  --cwd /absolute/project/path \
  --config /absolute/project/path/.polytoken \
  --model YOUR_MODEL \
  --prompt 'Inspect the project and summarize its structure.'
```

Keep this checkout and its Python interpreter in place. The generated hooks refer to both by absolute path.

## Install for all projects

To use your normal Polytoken user configuration instead of preparing each project:

```sh
python3 -m polytoken_herdr.cli prepare --global
python3 -m polytoken_herdr.cli launch --global \
  --name worker --cwd /absolute/project/path \
  --model YOUR_MODEL --prompt 'Inspect the project.'
```

The installer adds hooks to `$XDG_CONFIG_HOME/polytoken/hooks.json`, or
`~/.config/polytoken/hooks.json` when XDG_CONFIG_HOME is unset. It preserves
existing hook entries and saves the original file as `hooks.json.herdr-backup`.
Running it again leaves matching hooks unchanged; conflicting names stop the
installation. Close other configuration editors while installing.

Global hooks report only when a managed launcher supplies its private relay
connection. Ordinary Polytoken sessions do not report to Herdr. Keep any project
hooks from disabling the adapter's `herdr-*` entries. Global hook discovery and
the managed global-mode TUI have passed isolated runtime checks.

### Start Polytoken from the Herdr app

The Herdr app lists only programs that have a `run` command in its program
table, and Polytoken is not built in. After `prepare --global`, add an entry to
`~/.config/herdr-app/programs.json` (or `$HERDR_APP_HOME/programs.json`):

```json
{ "programs": {
    "polytoken": {
      "name": "Polytoken",
      "tile": "#6d28d9",
      "run": [
        "/absolute/path/to/python3",
        "/absolute/path/to/polytoken-herdr-core/polytoken_herdr/entry.py",
        "run", "--global"
      ]
    } } }
```

Use the interpreter from `which python3` and the absolute path to this
checkout. If the file already exists, merge the `polytoken` entry into its
`programs` object. Herdr reloads the file while running and reports invalid
JSON in `programs.error`.

The entry runs the adapter's `run` mode, which wraps Polytoken in the pane
Herdr opens. Do not use bare `polytoken` or `launch` here: bare Polytoken
reports no status, and `launch` starts a separate hidden worker. Polytoken uses
its default model; append `"--model", "YOUR_MODEL"` to choose another. If the
interpreter or checkout moves, Herdr shows the agent as not installed until you
update the paths.

## Work with the session

The `hc` commands below are for using herdr-core directly. The Herdr application
invokes these controls automatically; you do not need to run them yourself when
using the app. Permission decisions and answers to questions still belong to you.

Attach to complete startup or answer a question:

```sh
hc attach worker
```

Press **Ctrl+\\** to detach from the viewer while leaving Polytoken running. Use hc's viewer for this; moving the session with Polytoken's own detach commands is unsupported.

After startup, inspect its status or send another task:

```sh
hc get worker
hc send worker 'Describe the test setup.' --if idle --wait
```

If Polytoken needs a permission decision, attach and make that decision yourself. Do not send approval keys through automation or bypass a blocked terminal with `--force`.

When you are finished:

```sh
hc kill worker
hc rm worker
```

Closing the managed session triggers cleanup of its private Polytoken registry. Treat these sessions as temporary: the registry is not durable conversation history. If cleanup fails, the adapter prints the retained registry path. See [cleanup and recovery](docs/usage.md#cleanup-and-recovery).

## Status and limits

Herdr shows `working` when a model turn starts, `idle` when Polytoken hands back control, and `blocked` while a reported human-input prompt remains open. The adapter reads hook events, not screen text, and never reports `done`.

Reports are best effort. Use the conversation and the actual task results to judge completion. The adapter does not change Polytoken's permissions or isolate it from your global configuration.

The combined tests confirmed ordinary input, reattachment to a question, and terminal termination. Both observed processes exited in the global-mode test. That does not establish that every detached daemon exits or cover every permission path. The test provider's repeated-question bug is fixed, but answering and returning to idle still needs a stock-TUI check. The [verification record](docs/review.md) lists the evidence and limits.

For configuration, status details, and disposable test commands, see [setup and use](docs/usage.md).
