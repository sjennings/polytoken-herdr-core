"""Absolute-path entrypoint for generated hooks and hc launches."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    if sys.argv[1:] == ["hook"]:
        from polytoken_herdr.hook import main
        main()
    else:
        from polytoken_herdr.cli import main
        raise SystemExit(main())
