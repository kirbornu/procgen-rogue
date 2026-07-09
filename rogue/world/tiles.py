"""Tile definitions as numpy structured records.

Storing the map as a numpy array of a compact record type keeps FOV and
rendering vectorised and fast, while the ``new_tile`` factory keeps *defining*
a new terrain type (water, lava, doors, ...) a one-liner.  Each tile carries the
glyphs/colours for both its lit and remembered (dark) appearance, so the
renderer never branches on tile type.
"""
from __future__ import annotations

import numpy as np

from .. import config

# A single drawable cell: character code + foreground + background colour.
graphic_dt = np.dtype(
    [
        ("ch", np.int32),
        ("fg", "3B"),
        ("bg", "3B"),
    ]
)

# A tile: its physics (walkable/transparent) plus lit and dark graphics.
tile_dt = np.dtype(
    [
        ("walkable", np.bool_),
        ("transparent", np.bool_),
        ("dark", graphic_dt),
        ("light", graphic_dt),
    ]
)


def new_tile(
    *,
    walkable: bool,
    transparent: bool,
    dark: tuple,
    light: tuple,
) -> np.ndarray:
    """Build a 0-d array of ``tile_dt`` for use as a template value."""
    return np.array((walkable, transparent, dark, light), dtype=tile_dt)


# Rendered for tiles that have never been seen.
SHROUD = np.array((ord(" "), config.WHITE, config.BLACK), dtype=graphic_dt)

FLOOR = new_tile(
    walkable=True,
    transparent=True,
    dark=(ord("."), config.DARK_GREY, config.FLOOR_DARK_BG),
    light=(ord("."), config.GREY, config.FLOOR_LIGHT_BG),
)

WALL = new_tile(
    walkable=False,
    transparent=False,
    dark=(ord("#"), config.DARK_GREY, config.WALL_DARK_BG),
    light=(ord("#"), config.WHITE, config.WALL_LIGHT_BG),
)
