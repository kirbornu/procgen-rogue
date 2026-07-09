"""Factory functions that assemble entities from components.

Centralising construction here means the *recipe* for the player or a monster
lives in one place.  Adding a new monster type is adding a function (or a data
row) here; nothing else in the code needs to change.
"""
from __future__ import annotations

from . import config
from .components import Fighter, Inventory, Loot, MonsterAI, Progress
from .entity import Entity, RenderOrder


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
    player.add("fighter", Fighter(hp=cfg.player_hp, power=cfg.player_power, defense=cfg.player_defense))
    player.add("inventory", Inventory(capacity=cfg.inventory_capacity))
    player.add("progress", Progress())
    return player


def make_monster(x: int, y: int) -> Entity:
    """A plain standing monster: stays put, hits back, drops loot on death."""
    monster = Entity(
        x,
        y,
        char="g",
        color=config.MONSTER_COLOR,
        name="Goblin",
        blocks_movement=True,
        render_order=RenderOrder.ACTOR,
    )
    monster.add("fighter", Fighter(hp=8, power=3, defense=0))
    monster.add("ai", MonsterAI())
    monster.add("loot", Loot(gold=0))
    return monster
