"""Items and loot generation.

Right now the only loot is a *stick* whose tier runs from 1 to 5, but the shape
here is deliberately general: an :class:`Item` is just data + a ``kind`` tag and
an optional ``tier``.  Adding swords, potions or rings later means adding new
``ItemKind`` entries and (optionally) new roll tables - no change to combat,
inventory or rendering code.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from . import config
from .rng import Rng


class ItemKind(Enum):
    STICK = "stick"


# Cosmetic names per tier keep flavour in data rather than in logic.
STICK_TIER_NAMES = {
    1: "Twig",
    2: "Branch",
    3: "Stick",
    4: "Cudgel",
    5: "Gnarled Staff",
}


@dataclass(frozen=True)
class Item:
    kind: ItemKind
    name: str
    char: str = "/"
    color: tuple = config.ITEM_COLOR
    tier: int = 1

    @property
    def display_name(self) -> str:
        return f"{self.name} [T{self.tier}]"


def make_stick(tier: int) -> Item:
    tier = max(1, min(5, tier))
    return Item(
        kind=ItemKind.STICK,
        name=STICK_TIER_NAMES[tier],
        char="/",
        color=config.ITEM_COLOR,
        tier=tier,
    )


def roll_loot(rng: Rng, cfg: config.Config) -> Item:
    """Roll a single loot drop.  Tier is chosen from the configured weights."""
    tier = rng.weighted_index(cfg.loot_tier_weights) + 1
    return make_stick(tier)
