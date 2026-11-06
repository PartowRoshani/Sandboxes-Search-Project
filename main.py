"""Simple entry point for the sand-grid project.

Run `python main.py` for a UCS example and offline animation, or pass
arguments such as `python main.py compare --example professor`.
"""
from __future__ import annotations

import sys
from sandgrid.cli import main


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args:
        print("Running the professor example with UCS and creating results/demo.html")
        args = ["solve", "--example", "professor", "--algorithm", "ucs",
                "--html", "results/demo.html"]
    raise SystemExit(main(args))
