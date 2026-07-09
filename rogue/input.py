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

from .actions import Action, BumpAction, HealAction, ScoutAction, WaitAction
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
    K.A: (-1, 0),
    K.X: (0, 1),
    K.W: (0, -1),
    K.D: (1, 0),
    K.Q: (-1, -1),
    K.E: (1, -1),
    K.Z: (-1, 1),
    K.C: (1, 1),
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

WAIT_KEYS = {K.PERIOD, K.KP_5, K.CLEAR, K.S}


class Command(enum.Enum):
    """Non-turn UI commands the app layer handles directly."""

    QUIT = enum.auto()
    TOGGLE_INVENTORY = enum.auto()


class InvCommand(enum.Enum):
    """Navigation while the inventory overlay is open."""

    UP = enum.auto()
    DOWN = enum.auto()
    EQUIP = enum.auto()  # toggle equip/unequip the selected item
    CLOSE = enum.auto()


class ShopCommand(enum.Enum):
    """Navigation while the merchant's shop is open."""

    UP = enum.auto()
    DOWN = enum.auto()
    SELECT = enum.auto()  # buy the upgrade / sell the item on the cursor
    CLOSE = enum.auto()


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
    if key == K.R:
        return HealAction(player)  # rest / heal (an activity)
    if key == K.F:
        return ScoutAction(player)  # scout (an activity)
    if key == K.I:
        return Command.TOGGLE_INVENTORY
    if key == K.ESCAPE:
        return Command.QUIT
    return None


def dispatch_inventory(event: tcod.event.Event) -> Optional[InvCommand]:
    """Key handling while the inventory overlay is open."""
    if isinstance(event, tcod.event.Quit):
        return InvCommand.CLOSE
    if not isinstance(event, tcod.event.KeyDown):
        return None

    key = event.sym
    if key in (K.UP, K.W, K.K, K.KP_8):
        return InvCommand.UP
    if key in (K.DOWN, K.X, K.J, K.KP_2):
        return InvCommand.DOWN
    if key in (K.RETURN, K.KP_ENTER, K.E):
        return InvCommand.EQUIP
    if key in (K.I, K.ESCAPE):
        return InvCommand.CLOSE
    return None


def dispatch_shop(event: tcod.event.Event) -> Optional[ShopCommand]:
    """Key handling while the merchant's shop is open."""
    if isinstance(event, tcod.event.Quit):
        return ShopCommand.CLOSE
    if not isinstance(event, tcod.event.KeyDown):
        return None

    key = event.sym
    if key in (K.UP, K.W, K.K, K.KP_8):
        return ShopCommand.UP
    if key in (K.DOWN, K.X, K.J, K.KP_2):
        return ShopCommand.DOWN
    if key in (K.RETURN, K.KP_ENTER, K.SPACE):
        return ShopCommand.SELECT
    if key in (K.ESCAPE,):
        return ShopCommand.CLOSE
    return None
