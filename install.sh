#!/bin/sh
# Install this checkout as a Herdr app plugin: launcher on PATH, agent
# skill, Herdr program entry with icon, and global status hooks. Rerun
# after moving the checkout. Reversible with uninstall.sh.
#
# Overrides (mainly for tests): HERDR_APP_HOME selects the app home,
# XDG_CONFIG_HOME relocates the global hooks, HOME relocates the bin and
# skill links, POLYTOKEN_HERDR_PYTHON picks the interpreter.
set -eu
here=$(cd "$(dirname "$0")" && pwd -P)
python=${POLYTOKEN_HERDR_PYTHON:-python3}
skills=${POLYTOKEN_HERDR_SKILLS:-$HOME/.claude/skills}
herdr_home=${HERDR_APP_HOME:-$HOME/.config/herdr-app}

mkdir -p "$HOME/.local/bin"
ln -sfn "$here/bin/polytoken-herdr" "$HOME/.local/bin/polytoken-herdr"
echo "linked $HOME/.local/bin/polytoken-herdr -> $here/bin/polytoken-herdr"

mkdir -p "$skills"
ln -sfn "$here/skill/polytoken-herdr" "$skills/polytoken-herdr"
echo "linked $skills/polytoken-herdr -> $here/skill/polytoken-herdr"

"$python" "$here/polytoken_herdr/entry.py" install-app --home "$herdr_home"

if ! "$python" "$here/polytoken_herdr/entry.py" prepare --global; then
  echo "install.sh: status hooks not installed; see the error above." >&2
  echo "install.sh: after resolving it, run install.sh again." >&2
  exit 1
fi

echo "Start Polytoken from the Herdr app's agent menu, or run: polytoken-herdr run --global"
