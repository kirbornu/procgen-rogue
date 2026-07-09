"""The set of stat bonuses an item can grant the player.

Kept in its own module (no imports) so both ``items`` and ``components`` can
depend on it without a cycle.  Adding a new kind of bonus is one enum entry plus
wiring it wherever the stat is read (see ``components.Fighter`` and the engine).
"""
from __future__ import annotations

from enum import Enum


class BonusType(Enum):
    MAX_HP = "Max HP"
    DAMAGE = "Damage"
    ATTACK_RANGE = "Atk Range"
    VIEW_RADIUS = "View"
    CRIT_CHANCE = "Crit"
    DODGE_CHANCE = "Dodge"
    HEAL_POWER = "Heal"


#: Bonuses stored as a 0..1 probability, formatted as a percentage.
PERCENT_BONUSES = frozenset({BonusType.CRIT_CHANCE, BonusType.DODGE_CHANCE})

#: Bonuses that are whole numbers added to an integer stat.
INTEGER_BONUSES = frozenset(
    {
        BonusType.MAX_HP,
        BonusType.DAMAGE,
        BonusType.ATTACK_RANGE,
        BonusType.VIEW_RADIUS,
        BonusType.HEAL_POWER,
    }
)


def format_bonus(btype: BonusType, value: float) -> str:
    if btype in PERCENT_BONUSES:
        return f"+{value * 100:.0f}% {btype.value}"
    return f"+{value:g} {btype.value}"
