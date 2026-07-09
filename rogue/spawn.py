"""Factory functions that assemble entities from components.

Monster stats are rolled here; a monster's overall danger drives both its colour
(the redder, the deadlier) and the level of loot it drops.  Keeping the recipe in
one place means a new foe is a new function or a tweak to the rolls - nothing
downstream needs to change.
"""
from __future__ import annotations

from . import config
from .components import (
    Equipment,
    Fighter,
    Inventory,
    Loot,
    MonsterAI,
    Progress,
    Stairs,
    Teleport,
)
from .entity import Entity, RenderOrder
from .items import MAX_LEVEL
from .rng import Rng

# Colour endpoints for the danger gradient (calm green -> lethal red).
CALM_COLOR = (0x60, 0xB0, 0x60)
DANGER_COLOR = (0xE8, 0x30, 0x30)

# Flavour: name (and glyph) rise with danger level.
MONSTER_NAMES = ["Rat", "Goblin", "Brute", "Ogre", "Horror"]


def make_player(x: int, y: int, cfg: config.Config) -> Entity:
    player = Entity(
        x,
        y,
        char="@",
        color=config.PLAYER_COLOR,
        name="You",
        blocks_movement=True,
        render_order=RenderOrder.PLAYER,
    )
    player.add(
        "fighter",
        Fighter(
            hp=cfg.player_hp,
            power=cfg.player_power,
            defense=cfg.player_defense,
            attack_range=cfg.player_attack_range,
        ),
    )
    player.add("inventory", Inventory(capacity=cfg.inventory_capacity))
    player.add("equipment", Equipment(capacity=cfg.equipment_slots))
    player.add("progress", Progress())
    return player


def _danger_fraction(hp: int, power: int, crit: float, dodge: float, speed: float) -> float:
    """Collapse a monster's stats into a 0..1 danger rating."""
    score = hp * 0.2 + power * 0.5 + crit * 100 * 0.2 + dodge * 100 * 0.2 + speed * 1
    return max(0.0, min(1.0, score / 100.0))


def danger_level(fraction: float) -> int:
    """Map a 0..1 danger fraction onto an item/monster level in 1..MAX_LEVEL."""
    return 1 + min(MAX_LEVEL - 1, int(fraction * MAX_LEVEL))


def danger_color(fraction: float) -> tuple:
    """Linearly interpolate the danger gradient at ``fraction``."""
    return tuple(
        int(calm + (danger - calm) * fraction)
        for calm, danger in zip(CALM_COLOR, DANGER_COLOR)
    )


def make_monster(rng: Rng, x: int, y: int, depth: int = 1) -> Entity:
    """Roll a random standing/roaming monster."""
    dgr = rng.randint(depth, 6 * depth)
    hp = rng.randint(dgr, 2 * dgr) + 2 * dgr
    power = rng.randint(dgr, 8 + dgr) + 2 * dgr
    crit = rng.randint(dgr, 2 * dgr) / 100.0
    dodge = rng.randint(dgr, 2 * dgr) / 100.0
    speed = rng.randint(1, 6) / 4.0  # 0, .25, .5, .75, 1 -> stands still ... always moves

    fraction = _danger_fraction(hp, power, crit, dodge, speed)
    level = danger_level(fraction)
    name = MONSTER_NAMES[min(4, level // len(MONSTER_NAMES))]

    monster = Entity(
        x,
        y,
        char=name[0].lower(),
        color=danger_color(fraction),
        name=name,
        blocks_movement=True,
        render_order=RenderOrder.ACTOR,
    )
    monster.add(
        "fighter",
        Fighter(hp=hp, power=power, defense=0, crit_chance=crit, dodge_chance=dodge),
    )
    monster.add("ai", MonsterAI(speed=speed))
    monster.add("loot", Loot(level=level))
    return monster


def make_teleport(x: int, y: int) -> Entity:
    portal = Entity(
        x,
        y,
        char="O",
        color=config.TELEPORT_COLOR,
        name="portal",
        blocks_movement=False,
        render_order=RenderOrder.ITEM,
    )
    portal.add("teleport", Teleport())
    return portal


def make_stairs(x: int, y: int) -> Entity:
    stairs = Entity(
        x,
        y,
        char=">",
        color=config.STAIRS_COLOR,
        name="stairs down",
        blocks_movement=False,
        render_order=RenderOrder.ITEM,
    )
    stairs.add("stairs", Stairs())
    return stairs
