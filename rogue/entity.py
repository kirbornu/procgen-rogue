"""Component-based entities.

An :class:`Entity` is a position + a glyph + a bag of components.  Behaviour and
state live in the components, so new capabilities (equipment, status effects,
ranged attacks, factions, ...) are added by writing a new component and attaching
it - never by growing a giant Entity class or a rigid inheritance tree.

This is intentionally a *lightweight* ECS: components are plain objects that hold
data and small helpers, and the systems that act on them live in ``actions.py``,
``engine.py`` and the components themselves.  It scales to a real ECS later if
needed, but stays readable for a small game today.
"""
from __future__ import annotations

import enum
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .components import Component


class RenderOrder(enum.IntEnum):
    """Higher values are drawn last (on top)."""

    DECORATION = -1
    CORPSE = 0
    ITEM = 1
    ACTOR = 2
    PLAYER = 3


class Entity:
    def __init__(
        self,
        x: int,
        y: int,
        char: str,
        color: tuple,
        name: str,
        *,
        blocks_movement: bool = False,
        render_order: RenderOrder = RenderOrder.ACTOR,
    ) -> None:
        self.x = x
        self.y = y
        self.char = char
        self.color = color
        self.name = name
        self.blocks_movement = blocks_movement
        self.render_order = render_order
        self._components: Dict[str, "Component"] = {}

    # --- component plumbing ------------------------------------------------
    def add(self, key: str, component: "Component") -> "Entity":
        component.entity = self
        self._components[key] = component
        return self

    def get(self, key: str) -> Optional["Component"]:
        return self._components.get(key)

    def has(self, key: str) -> bool:
        return key in self._components

    # Convenience accessors for the components used all over the code.  New
    # well-known components can get a property here; ad-hoc ones use ``get``.
    @property
    def fighter(self):
        return self._components.get("fighter")

    @property
    def ai(self):
        return self._components.get("ai")

    @property
    def inventory(self):
        return self._components.get("inventory")

    # --- helpers -----------------------------------------------------------
    @property
    def is_alive(self) -> bool:
        return self.fighter is not None and self.fighter.hp > 0

    def move(self, dx: int, dy: int) -> None:
        self.x += dx
        self.y += dy

    def distance_to(self, other: "Entity") -> int:
        from .geometry import chebyshev

        return chebyshev(self.x, self.y, other.x, other.y)
