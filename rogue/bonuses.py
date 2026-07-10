"""The set of stat bonuses an item can grant the player.

Kept in its own module (no imports) so both ``items`` and ``components`` can
depend on it without a cycle.  Adding a new kind of bonus is one enum entry plus
wiring it wherever the stat is read (see ``components.Fighter`` and the engine).
"""
from __future__ import annotations

from enum import Enum

from . import config

from importlib import import_module
lang = import_module(f"rogue.lang.{config.Config.language}")
stats = lang.STATS

class BonusType(Enum):
    MAX_HP = stats['hp']
    DAMAGE = stats['dm']
    ATTACK_RANGE = stats['at']
    VIEW_RADIUS = stats['vw']
    CRIT_CHANCE = stats['cr']
    DODGE_CHANCE = stats['dg']
    HEAL_POWER = stats['hl']


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


# --- permanent upgrades (bought from the merchant) -------------------------
#: How much one purchased upgrade raises a stat.
UPGRADE_STEP = {
    BonusType.MAX_HP: 5,
    BonusType.DAMAGE: 2,
    BonusType.ATTACK_RANGE: 1,
    BonusType.VIEW_RADIUS: 1,
    BonusType.CRIT_CHANCE: 0.02,
    BonusType.DODGE_CHANCE: 0.02,
    BonusType.HEAL_POWER: 1,
}

#: Gold cost of the *first* upgrade of each stat; later ones cost more (see
#: ``Config.upgrade_cost_growth``).  Powerful stats start pricier.
UPGRADE_BASE_COST = {
    BonusType.MAX_HP: 40,
    BonusType.DAMAGE: 70,
    BonusType.ATTACK_RANGE: 4000,
    BonusType.VIEW_RADIUS: 100,
    BonusType.CRIT_CHANCE: 90,
    BonusType.DODGE_CHANCE: 90,
    BonusType.HEAL_POWER: 50,
}
