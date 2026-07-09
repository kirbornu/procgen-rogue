"""Translate raw keyboard events into game actions or UI commands.

Keeping the key map here (and separate from what the actions *do*) means
rebinding, adding a config file, or supporting an alternate layout is a local
change.  Three movement schemes are supported at once: arrow keys, roguelike
vi-keys (hjkl + yubn diagonals), and the numeric keypad.
"""
from __future__ import annotations

import enum
from typing import Optional, Union

import tcod.event

from .actions import Action, BumpAction, WaitAction
from .entity import Entity

K = tcod.event.KeySym

# Direction offset for every movement key.
MOVE_KEYS: dict[int, tuple[int, int]] = {
    # Arrows
    K.UP: (0, -1),
    K.DOWN: (0, 1),
    K.LEFT: (-1, 0),
    K.RIGHT: (1, 0),
    # vi-keys (KeySym names for letters are upper-case but map the plain keys)
    K.H: (-1, 0),
    K.J: (0, 1),
    K.K: (0, -1),
    K.L: (1, 0),
    K.Y: (-1, -1),
    K.U: (1, -1),
    K.B: (-1, 1),
    K.N: (1, 1),
    # Numeric keypad
    K.KP_1: (-1, 1),
    K.KP_2: (0, 1),
    K.KP_3: (1, 1),
    K.KP_4: (-1, 0),
    K.KP_6: (1, 0),
    K.KP_7: (-1, -1),
    K.KP_8: (0, -1),
    K.KP_9: (1, -1),
}

WAIT_KEYS = {K.PERIOD, K.KP_5, K.CLEAR}


class Command(enum.Enum):
    """Non-turn UI commands the app layer handles directly."""

    QUIT = enum.auto()
    TOGGLE_INVENTORY = enum.auto()


Dispatch = Union[Action, Command, None]


def dispatch(event: tcod.event.Event, player: Entity) -> Dispatch:
    if isinstance(event, tcod.event.Quit):
        return Command.QUIT
    if not isinstance(event, tcod.event.KeyDown):
        return None

    key = event.sym
    if key in MOVE_KEYS:
        dx, dy = MOVE_KEYS[key]
        return BumpAction(player, dx, dy)
    if key in WAIT_KEYS:
        return WaitAction(player)
    if key == K.I:
        return Command.TOGGLE_INVENTORY
    if key in (K.ESCAPE, K.Q):
        return Command.QUIT
    return None
