---
name: polytoken-herdr
description: Start Polytoken with Herdr status reporting, or drive a running Polytoken session over hc. Use when the user asks to run Polytoken "in herdr" or "with status", to start a managed Polytoken worker, or to attach, send work to, wait on, or finish a Polytoken session.
allowed-tools: Bash(polytoken-herdr:*), Bash(hc:*)
---

# Polytoken in Herdr

`polytoken-herdr` runs the polytoken-herdr-core adapter: stock Polytoken in
an hc terminal that reports `working`, `idle`, and `blocked` to the Herdr
app. The statuses are best effort; judge results by the conversation, not
the status. The adapter never reports `done`.

| The user wants | Run |
| --- | --- |
| Polytoken in this terminal (a Herdr pane), status reported | `polytoken-herdr run --global` |
| A hidden hc-managed session | `polytoken-herdr launch --global --name worker --cwd /abs/project --prompt 'Inspect the project.'` |
| Attach to answer a question or use the TUI | `hc attach worker` (detach with Ctrl+\\) |
| Check a session | `hc get worker` |
| Send work when idle | `hc send worker 'Describe the test setup.' --if idle --wait` |
| Finish | `hc kill worker` then `hc rm worker` |

- `run --global` must run inside an hc terminal (the Herdr app's panes are)
  and needs the global hooks from `polytoken-herdr prepare --global`.
- The plugin's Herdr pane is the `polytoken` mod: open it with
  `herdr-app do tab.new --name Polytoken --mod polytoken`. It starts
  sessions, lists running ones and shows setup problems.
- Humans decide agreements, permissions, and answers to questions. Attach
  and let them answer; never send approval keys through automation and
  never bypass a blocked terminal with `hc send --force`.
- Closing the session cleans up its temporary session registry. Treat these
  sessions as disposable; the registry is not conversation history.
- Project-scoped use with a dedicated config directory exists; see the
  polytoken-herdr-core README before using `--config` instead of `--global`.
