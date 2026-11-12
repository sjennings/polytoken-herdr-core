"""Absolute-path entrypoint for callbacks and hc launches."""
# pattern: Imperative Shell
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    from polytoken_herdr.cli import main
    raise SystemExit(main())
