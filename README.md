# polytoken-herdr-core

Run [Polytoken](https://docs.polytoken.dev/) in a [herdr-core](https://github.com/herdrdev/herdr-core) terminal, send it work with `hc`, and see when it is working or waiting for you.

This adapter works with stock Polytoken. It uses hooks to report session status to herdr-core and keeps the Polytoken terminal available through `hc attach`. You handle permissions, questions, and first-run agreements yourself.

The project is experimental. Human-run tests have confirmed startup, a follow-up prompt, and terminal shutdown with Polytoken 0.9.4 and hc 0.1.15 on macOS. Status reports can arrive late or be lost; `idle` does not mean a task succeeded.

## Install as a Herdr app plugin

One script links this checkout into your PATH, Claude Code, and the Herdr
app:

```sh
git clone https://github.com/sjennings/polytoken-herdr-core
cd polytoken-herdr-core && ./install.sh
```

It installs four things and is safe to rerun:

- `bin/polytoken-herdr` into `~/.local/bin`, so `polytoken-herdr run --global` and the other adapter commands work from any directory.
- The agent skill in `skill/polytoken-herdr` into `~/.claude/skills`, so agents know the commands.
- The `polytoken` entry in the Herdr app's `programs.json` (other entries preserved) and the icon copied into the app home, so Polytoken appears in the agent menu.
- The global status hooks, as `prepare --global` installs them.

`./uninstall.sh` reverses all four; run it from this checkout before
deleting the checkout. If you move the checkout, rerun `./install.sh`; when
`prepare --global` reports a conflict with stale hooks from the old
location, run `polytoken-herdr remove --global` once and rerun the
installer. An existing manual `programs.json` entry keeps working; rerunning
`install.sh` replaces it with the launcher form and saves the previous file
as `programs.json.herdr-backup`.

There is no Herdr mod in this plugin. The app's built-in agents list
already shows every session reporting a status over OSC 7501, which is what
this adapter provides, and the agent-menu entry comes from `programs.json`.
A mod would duplicate both.

## How to use Polytoken with the Herdr app

The Herdr app's agent menu lists only programs it knows how to start. Polytoken
is not one of them by default. These steps add it once for all your projects;
they are the manual equivalent of `install.sh`, spelled out for transparency
and for installs without scripts.

You need the Herdr app, Python 3.10 or later, `polytoken` on your PATH, and a
Polytoken model configuration that already works when you run `polytoken` on
its own.

1. **Install the adapter's hooks.** From this checkout, run:

   ```sh
   python3 -m polytoken_herdr.cli prepare --global
   ```

   This adds the adapter's hooks to your Polytoken user configuration and
   keeps a backup of the original. See [Install for all projects](#install-for-all-projects)
   for details.

2. **Note two paths.** Run `which python3` for the interpreter, and `pwd` in
   this checkout for its location. Both must be absolute paths.

3. **Tell Herdr how to start Polytoken.** Create
   `~/.config/herdr-app/programs.json` (or `$HERDR_APP_HOME/programs.json`) with
   the following, substituting your two paths:

   ```json
   { "programs": {
       "polytoken": {
         "name": "Polytoken",
         "icon": "polytoken-icons/polytoken.webp",
         "tint": false,
         "tile": "#6d28d9",
         "run": [
           "/absolute/path/to/python3",
           "/absolute/path/to/polytoken-herdr-core/polytoken_herdr/entry.py",
           "run", "--global"
         ]
       } } }
   ```

   If the file already exists, add the `polytoken` entry to its `programs`
   object instead of replacing the file. Herdr reloads the file while it runs.
   If the JSON is invalid, Herdr writes the reason to `programs.error` in the
   same folder. When the launcher is linked into `~/.local/bin` (the first
   thing `install.sh` does), the `run` array can be the shorter
   `["/home/you/.local/bin/polytoken-herdr", "run", "--global"]`, which
   survives interpreter changes; that is the form `install.sh` writes.

4. **Add the Polytoken icon.** Copy `assets/polytoken.webp` from this checkout
   into the herdr-app home folder:

   ```sh
   mkdir -p ~/.config/herdr-app/polytoken-icons
   cp /absolute/path/to/polytoken-herdr-core/assets/polytoken.webp \
      ~/.config/herdr-app/polytoken-icons/polytoken.webp
   ```

   The image must live inside the herdr-app home folder: Herdr loads icon paths
   only relative to that folder, so absolute paths, URLs and symlinks pointing
   elsewhere will not work. `tint` is false because the icon is a full-color
   picture, not a one-color SVG glyph Herdr recolors. Don't use the folder's
   `icons/` directory; Herdr manages it.

5. **Start Polytoken from Herdr.** Polytoken now appears in the agent menu.
   Start it in a project folder. The first time, Polytoken may ask you to accept
   an agreement or make a permission decision. Answer in the pane yourself.

6. **Work in the pane.** Herdr shows the session as `working` during a model
   turn, `idle` when Polytoken hands back control, and `blocked` when it needs
   your answer. You don't need the `hc` commands in this README; the app runs
   them for you. When Polytoken exits, the adapter removes the session's
   temporary registry.

Polytoken starts with its default model. To choose another, add
`"--model", "YOUR_MODEL"` after `"--global"`.

Why this command: it runs the adapter's `run` mode inside the pane Herdr
opens, which lets Polytoken report its status. Bare `polytoken` reports no
status, and the adapter's `launch` command starts a separate hidden terminal.

If you move this checkout or your Python interpreter changes (for example after
a version-manager upgrade), Herdr shows Polytoken as not installed. Update the
paths in `programs.json`, or rerun `install.sh`: it rewrites the entry in the
launcher form, which resolves the interpreter at run time. The generated hooks
still name the interpreter `prepare --global` ran with, and a changed
interpreter makes them stale; `prepare --global` then reports them as a
conflict, so run `polytoken-herdr remove --global` once and rerun
`install.sh`.

The app menu entry has not yet had a recorded runtime test. The pane may be
labelled as Python rather than Polytoken.

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

## Work with the session

The `hc` commands below are for using herdr-core directly. When you use the
Herdr app, see [How to use Polytoken with the Herdr app](#how-to-use-polytoken-with-the-herdr-app).
Permission decisions and answers to questions still belong to you.

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
