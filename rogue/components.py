"""Entity components.

Each component is a small data-holder with optional helpers.  They keep a back
reference to their owning :class:`~rogue.entity.Entity` (set on ``entity.add``)
so a component can reach its siblings when needed.
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from . import config
from .geometry import Direction
from .items import Item

if TYPE_CHECKING:
    from .engine import Engine
    from .entity import Entity


class Component:
    """Base class; ``entity`` is filled in when attached via ``Entity.add``."""

    entity: "Entity"


class Fighter(Component):
    """Hit points and the raw stats melee resolves against."""

    def __init__(self, hp: int, power: int, defense: int) -> None:
        self.max_hp = hp
        self._hp = hp
        self.power = power
        self.defense = defense

    @property
    def hp(self) -> int:
        return self._hp

    @hp.setter
    def hp(self, value: int) -> None:
        self._hp = max(0, min(self.max_hp, value))

    def take_damage(self, amount: int) -> None:
        self.hp -= amount

    def heal(self, amount: int) -> int:
        before = self.hp
        self.hp += amount
        return self.hp - before


class MonsterAI(Component):
    """Baseline behaviour for the brief: stand still, hit back when adjacent.

    Deliberately trivial and self-contained.  Smarter monsters (chasers,
    fleers, ranged) become new AI components that swap in here without touching
    the turn loop.
    """

    #: Chebyshev range at which the monster will trade blows.
    attack_range: int = 1

    def take_turn(self, engine: "Engine") -> None:
        player = engine.player
        if not self.entity.is_alive or not player.is_alive:
            return
        if self.entity.distance_to(player) <= self.attack_range:
            from .actions import MeleeAction

            MeleeAction(self.entity, player).resolve(engine)
        # Otherwise the monster simply stands, exactly as specified.


class Inventory(Component):
    """A flat list of items with a capacity cap."""

    def __init__(self, capacity: int) -> None:
        self.capacity = capacity
        self.items: List[Item] = []

    @property
    def is_full(self) -> bool:
        return len(self.items) >= self.capacity

    def add(self, item: Item) -> bool:
        if self.is_full:
            return False
        self.items.append(item)
        return True

    def tier_counts(self) -> dict[int, int]:
        """Return {tier: count} - handy for the HUD summary."""
        counts: dict[int, int] = {}
        for item in self.items:
            counts[item.tier] = counts.get(item.tier, 0) + 1
        return counts


class Loot(Component):
    """What an entity yields when it dies: a gold reward and a rolled drop."""

    def __init__(self, gold: int) -> None:
        self.gold = gold


class Progress(Component):
    """Player-side progression: gold and kill count (easy to extend to XP)."""

    def __init__(self) -> None:
        self.gold = 0
        self.kills = 0
