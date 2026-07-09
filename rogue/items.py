"""Procedurally generated items.

An item has a *level* (1..5), a random name assembled from adjective/noun word
lists (higher level -> more words), and between 1 and 10 stat bonuses drawn from
:class:`~rogue.bonuses.BonusType`.  Bonus magnitudes scale with the item level,
which is itself derived from the power of the monster that dropped it.

Everything here is data + rolling; how bonuses *affect* the player lives in the
components/engine, so new bonus kinds or name themes drop in without touching
this file's structure.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from . import config
from .bonuses import BonusType, format_bonus
from .rng import Rng

# --- flavour word lists ----------------------------------------------------
ADJECTIVES: List[str] = [
    "Rusty", "Gleaming", "Ancient", "Cursed", "Blessed", "Jagged", "Twisted",
    "Runed", "Feral", "Ethereal", "Vicious", "Humming", "Frostbitten", "Charred",
    "Gilded", "Ravenous", "Whispering", "Fabled", "Wretched", "Storied",
]

NOUNS: List[str] = [
    "Stick", "Branch", "Cudgel", "Rod", "Stave", "Splinter", "Baton", "Switch",
    "Bough", "Shard", "Talon", "Fang", "Sliver", "Wand", "Cane",
]

# --- rarity colours by level (classic loot gradient) -----------------------
LEVEL_COLORS: Dict[int, tuple] = {
    1: (0xB0, 0xB0, 0xB0),  # grey
    2: (0x50, 0xC0, 0x50),  # green
    3: (0x50, 0x90, 0xE0),  # blue
    4: (0xB0, 0x60, 0xE0),  # purple
    5: (0xF0, 0xA0, 0x30),  # orange
}

# Relative frequency of each bonus type; the powerful reach/sight bonuses are
# deliberately rarer than raw HP/damage.
_BONUS_WEIGHTS: List[tuple] = [
    (BonusType.MAX_HP, 24),
    (BonusType.DAMAGE, 22),
    (BonusType.HEAL_POWER, 15),
    (BonusType.CRIT_CHANCE, 14),
    (BonusType.DODGE_CHANCE, 13),
    (BonusType.VIEW_RADIUS, 8),
    (BonusType.ATTACK_RANGE, 4),
]

MAX_LEVEL = 5
MIN_BONUSES = 1
MAX_BONUSES = 10


@dataclass(eq=False)  # identity equality: every rolled item is a distinct object
class Item:
    name: str
    level: int
    bonuses: Dict[BonusType, float] = field(default_factory=dict)
    char: str = "/"
    color: tuple = config.ITEM_COLOR

    @property
    def display_name(self) -> str:
        return f"L{self.level} {self.name}"

    def bonus_lines(self) -> List[str]:
        """Human-readable bonus strings, in a stable order."""
        return [
            format_bonus(btype, self.bonuses[btype])
            for btype in BonusType
            if btype in self.bonuses
        ]

    def bonus_summary(self) -> str:
        return ", ".join(self.bonus_lines())


def _generate_name(rng: Rng, level: int) -> str:
    """``level`` words: ``level - 1`` distinct adjectives then a noun."""
    adjectives = rng.sample(ADJECTIVES, max(0, level - 1))
    noun = rng.choice(NOUNS)
    return " ".join([*adjectives, noun])


def _pick_bonus_type(rng: Rng) -> BonusType:
    types = [t for t, _ in _BONUS_WEIGHTS]
    weights = [w for _, w in _BONUS_WEIGHTS]
    return types[rng.weighted_index(weights)]


def _roll_bonus_value(rng: Rng, btype: BonusType, level: int) -> float:
    if btype is BonusType.MAX_HP:
        return rng.randint(3, 8) + 2 * level
    if btype is BonusType.DAMAGE:
        return rng.randint(1, 2) + level
    if btype is BonusType.HEAL_POWER:
        return rng.randint(1, 2) + level // 2
    if btype is BonusType.CRIT_CHANCE:
        return (rng.randint(2, 5) + level) / 100.0
    if btype is BonusType.DODGE_CHANCE:
        return (rng.randint(1, 4) + level) / 100.0
    if btype is BonusType.VIEW_RADIUS:
        return 1 + (1 if level >= 4 else 0)
    if btype is BonusType.ATTACK_RANGE:
        return 1
    return 0  # pragma: no cover - exhaustive above


def generate_item(rng: Rng, level: int) -> Item:
    """Roll a fresh item of the given power ``level`` (clamped to 1..MAX_LEVEL)."""
    level = max(1, min(MAX_LEVEL, level))
    name = _generate_name(rng, level)

    bonuses: Dict[BonusType, float] = {}
    for _ in range(rng.randint(MIN_BONUSES, MAX_BONUSES)):
        btype = _pick_bonus_type(rng)
        bonuses[btype] = bonuses.get(btype, 0) + _roll_bonus_value(rng, btype, level)

    return Item(name=name, level=level, bonuses=bonuses, color=LEVEL_COLORS[level])
