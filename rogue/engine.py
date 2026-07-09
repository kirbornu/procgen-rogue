"""The engine owns the game state and drives one turn at a time.

It knows nothing about tcod rendering or key codes - it consumes
:class:`~rogue.actions.Action` objects and mutates the world.  That separation
is what lets the whole simulation run head-less in tests.
"""
from __future__ import annotations

from typing import Optional

from . import config
from .actions import Action
from .entity import Entity, RenderOrder
from .items import roll_loot
from .message_log import MessageLog
from .rng import Rng
from .world.game_map import GameMap
from .world.procgen import generate_dungeon


class Engine:
    def __init__(self, cfg: config.Config = config.DEFAULT, seed: Optional[int] = None) -> None:
        self.cfg = cfg
        self.rng = Rng(seed)
        self.log = MessageLog()
        self.game_over = False
        #: While True the FOV radius is boosted; cleared as soon as the player moves.
        self.scouting = False

        self.game_map, self.player = generate_dungeon(cfg, self.rng)
        self.update_fov()
        self.log.add("You descend into the dungeon.", config.TITLE_COLOR)

    # --- turn loop ---------------------------------------------------------
    def handle_player_action(self, action: Action) -> None:
        """Perform the player's action and, if it took time, run the world.

        Turn order for the player: perform the chosen action, then - unless it
        was an activity - automatically attack any enemy in range, then let the
        monsters act, then refresh the field of view.
        """
        if self.game_over:
            return
        before = (self.player.x, self.player.y)
        result = action.perform(self)
        if not result.advances_turn:
            return

        # Relocating cancels the scouting FOV bonus.
        if (self.player.x, self.player.y) != before:
            self.scouting = False

        # Auto-attack fires on ordinary turns (moving/waiting) but not while the
        # player is occupied with an activity such as healing or scouting.
        if not result.is_activity:
            self.auto_attack(self.player)

        self.process_monster_turns()
        self.update_fov()

    def auto_attack(self, attacker: Entity) -> None:
        """Strike the nearest living enemy within the attacker's attack range."""
        fighter = attacker.fighter
        if fighter is None or not attacker.is_alive:
            return

        nearest: Optional[Entity] = None
        nearest_dist = fighter.attack_range + 1
        for other in self.game_map.actors:
            if other is attacker or other.fighter is None:
                continue
            dist = attacker.distance_to(other)
            if dist <= fighter.attack_range and dist < nearest_dist:
                nearest, nearest_dist = other, dist

        if nearest is not None:
            from .actions import MeleeAction

            MeleeAction(attacker, nearest).resolve(self)

    def process_monster_turns(self) -> None:
        # Snapshot: entities may die (and be swapped to corpses) mid-iteration.
        for entity in list(self.game_map.entities):
            if entity is self.player:
                continue
            if entity.ai is not None and entity.is_alive:
                entity.ai.take_turn(self)

    def update_fov(self) -> None:
        radius = self.cfg.fov_radius
        if self.scouting:
            radius += self.cfg.scout_fov_bonus
        self.game_map.compute_fov(self.player.x, self.player.y, radius)

    # --- combat outcomes ---------------------------------------------------
    def kill(self, target: Entity, killer: Entity) -> None:
        """Resolve a lethal blow: reward + loot the killer, or end the game."""
        if target is self.player:
            self.log.add("You die!", config.MONSTER_COLOR)
            self.game_over = True
            target.char = "%"
            target.color = config.CORPSE_COLOR
            return

        self.log.add(f"{target.name} dies.", config.CORPSE_COLOR)
        self._award(target, killer)
        self._to_corpse(target)

    def _award(self, target: Entity, killer: Entity) -> None:
        """Grant the killer their reward and drop loot into their inventory."""
        loot_marker = target.get("loot")
        if loot_marker is None:
            return

        item = roll_loot(self.rng, self.cfg)
        progress = killer.get("progress")
        inventory = killer.inventory

        if progress is not None:
            reward = self.cfg.reward_gold_per_tier * item.tier
            progress.gold += reward
            progress.kills += 1

        if inventory is not None:
            if inventory.add(item):
                self.log.add(f"You loot a {item.display_name}.", config.ITEM_COLOR)
            else:
                self.log.add("Your pack is full; the loot is lost.", config.TEXT_DIM)

    def _to_corpse(self, entity: Entity) -> None:
        entity.char = "%"
        entity.color = config.CORPSE_COLOR
        entity.blocks_movement = False
        entity.render_order = RenderOrder.CORPSE
        entity.name = f"remains of {entity.name}"
        # Strip the components that made it a live actor.
        entity._components.pop("ai", None)
        entity._components.pop("fighter", None)
        entity._components.pop("loot", None)
