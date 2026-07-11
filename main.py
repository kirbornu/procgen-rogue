#!/usr/bin/env python3
"""Entry point for procgen-rogue.

Usage:
    python main.py            # play with a random dungeon
    python main.py --seed 42  # reproduce a specific dungeon
"""
from __future__ import annotations

import argparse
import os
import sys

from rogue import app


def main() -> None:
    parser = argparse.ArgumentParser(description="A tiny ASCII roguelike.")
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for reproducible dungeon generation.",
    )
    args = parser.parse_args()

    # The UI language is bound at import time, so switching it in the menu asks
    # us to relaunch the process with the new choice in the environment.
    new_language = app.run(seed=args.seed)
    if new_language:
        os.environ["ROGUE_LANG"] = new_language
        os.execv(sys.executable, [sys.executable, *sys.argv])


if __name__ == "__main__":
    main()
