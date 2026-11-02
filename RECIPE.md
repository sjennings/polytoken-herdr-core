# Polytoken

A small pane for the polytoken-herdr-core plugin: start a Polytoken session
that reports its status to Herdr, jump to one that is already running, and
see — and fix with one command — when the plugin is not fully installed.
It is a launcher and a setup check, not a second agent list; the app's
sidebar already shows every agent's status.

![Polytoken](preview.png)

## What you see

One column, 12 px padding, theme `background`, all text in the UI font.

- **Header**, one row: "Polytoken" in 13 px semibold, "launch and resume"
  in 11.5 px `dim` beside it.
- **Setup card** (only when something is missing): a `surface` card with an
  8 px radius and a 1 px `border`, "Setup incomplete" in 12.5 px semibold
  `blocked`, one 12 px `muted` line per problem (launcher, app-menu entry,
  global hooks), the fixing `install.sh` command in 12 px semibold `accent`,
  and a "Check again" button.
- **Start a session**: an 11.5 px `dim` label, then a row with a 28 px
  model input (`surface` background, `input` border, placeholder "default
  model"), a solid "New tab" button and a bordered "Split right" button,
  both 28 px high, 12.5 px text, 6 px radius.
- **Running sessions**: an 11.5 px `dim` label, then one 30 px row per live
  Polytoken session: an 8 px rounded status dot in the status color
  (`working`, `blocked`, `idle`, `done`), the session title truncated in
  12.5 px, and its space name in 11.5 px `dim`. With none running, one
  12 px `muted` line: "No Polytoken sessions are running. Start one above."

## How it behaves

- Typing a model name and pressing **New tab** opens a new tab running the
  adapter's `run --global` mode with `--model <name>` appended when the
  field is not empty; **Split right** splits the focused pane instead; the
  field's Enter key opens the tab. The launched session reports `working`,
  `idle` and `blocked` like every Herdr agent.
- The sessions list follows the app's live agent data: rows appear, change
  status color and disappear without the pane polling. Clicking a row runs
  `agent.focus` for that terminal.
- The setup check runs when the pane opens and when "Check again" is
  pressed. It reads; it never installs, repairs or writes anything.
- With nothing missing, the setup card is absent.

## Built from

- One mod, `mods/polytoken/`: `mod.json` `{ "place": "none" }` (it appears
  only where a tab or split puts it: `tab.new --mod polytoken`,
  `pane.split --mod polytoken`), no props. `main.js` default-exports one
  `View` holding an `InputState`.
- `herdr`: `agents()` (filter `app === "polytoken"`), `focused()`,
  `home()`, `appHome()`, `knownAgents()` (the app-menu `run` argv),
  `exec("sh", ["-c", …])` twice (reads
  `${XDG_CONFIG_HOME:-$HOME/.config}/polytoken/hooks.json`, and resolves
  the mods symlink so the install command names the real checkout),
  `run()`, `theme()`. Commands: `tab.new {name, argv}`, `pane.split {direction,
  pane, argv}`, `agent.focus {terminal}`.
- Node built-ins: `fs/promises` (`stat` on `~/.local/bin/polytoken-herdr`).
- Sessions launch through the `polytoken` entry the plugin's `install.sh`
  writes to `programs.json`, falling back to the linked launcher. The
  status reporting itself comes from polytoken-herdr-core's hooks, not from
  this mod.
- No icons or art; the status colors are the theme's.

## Watch out

- `herdr-app check` proves only the first render; the setup card's three
  states and a real launch need the live app.
- The mod is trusted code with command access; everything it runs is one
  `sh -c cat` of the hooks file. It reads the user's `programs.json` via
  `knownAgents()`.
- `knownAgents()` decides the launch argv; without the `programs.json`
  entry the pane falls back to `~/.local/bin/polytoken-herdr run --global`
  and the setup card flags the missing menu entry anyway.
- The sessions list is live terminals only; the adapter keeps no history,
  so "recent" means "running".
- With `XDG_CONFIG_HOME` set, the hooks check follows it, matching the
  adapter's own config discovery.

## Done when

- `herdr-app check mods/polytoken` passes.
- With the plugin installed, opening the pane shows no setup card; after
  `./uninstall.sh` it lists the missing pieces and the `install.sh`
  command.
- "New tab" with a model opens a tab whose agent turns `working` during a
  model turn; a running session appears in the list and clicking it focuses
  its pane.
- `tests/test_plugin_scripts.py` links and unlinks the mod with the rest of
  the plugin.
