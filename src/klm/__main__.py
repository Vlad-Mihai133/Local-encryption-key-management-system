from __future__ import annotations

import sys


if __name__ == "__main__":
    # UX choice:
    # - `python -m klm` starts the Tkinter UI
    # - `python -m klm --help` (or any args) runs the CLI
    if len(sys.argv) == 1:
        from klm.ui.app import run

        run()
    else:
        from klm.cli.main import main

        raise SystemExit(main(sys.argv[1:]))
