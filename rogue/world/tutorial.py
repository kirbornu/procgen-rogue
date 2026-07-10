"""The tutorial level: a small closed room, a few easy monsters, on-screen help.

It plugs in through the same ``generator(cfg, rng, depth, player)`` contract as
the dungeon generators, so the engine runs it with no special-casing.  The help
text lives in the language files (``lang.TUTORIAL['help']``).
"""
from __future__ import annotations

from typing import Tuple, TYPE_CHECKING

from .. import config
from ..rng import Rng
from ..spawn import make_player, make_tutorial_monster
from . import tiles
from .game_map import GameMap

if TYPE_CHECKING:
    from ..entity import Entity

#: Interior size of the tutorial room (walls add a one-tile border).
ROOM_SIZE = 10


def generate_tutorial(
    cfg: config.Config, rng: Rng, depth: int = 1, player: "Entity" | None = None
) -> Tuple[GameMap, "Entity"]:
    size = ROOM_SIZE + 2  # room interior plus a wall border
    game_map = GameMap(size, size)
    game_map.tiles[1 : size - 1, 1 : size - 1] = tiles.FLOOR

    start = (2, size // 2)
    if player is None:
        player = make_player(*start, cfg)
    else:
        player.x, player.y = start
    game_map.entities.append(player)

    # A few still, weak monsters to practise on.
    for mx, my in [(7, 2), (9, 5), (6, 8), (9, 9)]:
        game_map.entities.append(make_tutorial_monster(mx, my))

    return game_map, player
