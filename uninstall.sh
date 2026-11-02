#!/bin/sh
# Remove what install.sh added: the launcher and skill links, the Herdr
# program entry and icon, and this adapter's global status hooks. Run it
# from this checkout before deleting the checkout.
#
# Honors the same overrides as install.sh (HERDR_APP_HOME,
# XDG_CONFIG_HOME, HOME, POLYTOKEN_HERDR_SKILLS, POLYTOKEN_HERDR_PYTHON).
set -eu
here=$(cd "$(dirname "$0")" && pwd -P)
python=${POLYTOKEN_HERDR_PYTHON:-python3}
skills=${POLYTOKEN_HERDR_SKILLS:-$HOME/.claude/skills}

remove_link() {
  if [ -L "$2" ]; then
    if [ "$(readlink "$2")" = "$1" ]; then
      rm "$2"
      echo "removed $2"
    else
      echo "left alone (points elsewhere): $2" >&2
    fi
  elif [ -e "$2" ]; then
    echo "left alone (not a symlink): $2" >&2
  fi
  return 0
}

remove_link "$here/bin/polytoken-herdr" "$HOME/.local/bin/polytoken-herdr"
remove_link "$here/skill/polytoken-herdr" "$skills/polytoken-herdr"

"$python" "$here/polytoken_herdr/entry.py" remove-app --home "${HERDR_APP_HOME:-$HOME/.config/herdr-app}"
"$python" "$here/polytoken_herdr/entry.py" remove --global
