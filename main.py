#!/usr/bin/env python3
"""Entry point for procgen-rogue.

Usage:
    python main.py            # play with a random dungeon
    python main.py --seed 42  # reproduce a specific dungeon
"""
from __future__ import annotations

import argparse

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
    app.run(seed=args.seed)


if __name__ == "__main__":
    main()
