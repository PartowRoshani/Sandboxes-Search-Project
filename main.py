"""Entry point for all sand-grid solvers and command-line experiments."""
from __future__ import annotations

import sys
from sandgrid.cli import main

if __name__ == '__main__':
    arguments = sys.argv[1:]
    if not arguments:
        arguments = ['solve','--example','professor','--algorithm','greedy',
                     '--html','results/professor_greedy.html']
    raise SystemExit(main(arguments))
