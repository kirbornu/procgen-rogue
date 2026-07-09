"""The engine owns the game state and drives one turn at a time.

It knows nothing about tcod rendering or key codes - it consumes
:class:`~rogue.actions.Action` objects and mutates the world.  That separation
is what lets the whole simulation run head-less in tests.
"""
from __future__ import annotations

from typing import Optional

from . import config
from .actions import Action
from .bonuses import UPGRADE_BASE_COST, UPGRADE_STEP, BonusType, format_bonus
from .entity import Entity, RenderOrder
from .items import Item, generate_item
from .message_log import MessageLog
from .rng import Rng
from .world.game_map import GameMap
from .world.procgen import generate_noise_dungeon


class Engine:
    def __init__(
        self,
        cfg: config.Config = config.DEFAULT,
        seed: Optional[int] = None,
        generator=None,
    ) -> None:
        self.cfg = cfg
        self.rng = Rng(seed)
        self.log = MessageLog()
        self.game_over = False
        #: While True the FOV radius is boosted; cleared as soon as the player moves.
        self.scouting = False
        #: The merchant whose shop is open, or None.
        self.shop: Optional[Entity] = None

        # ``generator(cfg, rng, depth, player) -> (GameMap, player)``; defaults
        # to the noise cave.  Tests inject the faster room generator.
        self._generator = generator or generate_noise_dungeon
        self.depth = 1
        self.game_map, self.player = self._generator(cfg, self.rng, depth=self.depth)
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

        # Relocating cancels the scouting FOV bonus and may step onto a portal
        # or the down-stairs.
        if (self.player.x, self.player.y) != before:
            self.scouting = False
            self._maybe_teleport()
            if self.on_stairs():
                self.descend()  # rebuilds the world + FOV itself
                return

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
        radius = self.cfg.fov_radius + int(self._player_bonus(BonusType.VIEW_RADIUS))
        if self.scouting:
            radius += self.cfg.scout_fov_bonus
        self.game_map.compute_fov(self.player.x, self.player.y, radius)

    # --- portals & descending ---------------------------------------------
    def _maybe_teleport(self) -> None:
        """If the player stepped onto a portal, warp to its destination cell."""
        for entity in self.game_map.entities_at(self.player.x, self.player.y):
            portal = entity.get("teleport")
            if portal is not None and portal.dest is not None:
                self.player.x, self.player.y = portal.dest
                self.scouting = False
                self.log.add("You step through a shimmering portal.", config.TELEPORT_COLOR)
                return

    def on_stairs(self) -> bool:
        return any(e.has("stairs") for e in self.game_map.entities_at(self.player.x, self.player.y))

    def descend(self) -> None:
        """Regenerate a deeper, tougher level, carrying the player over."""
        self.depth += 1
        self.game_map, self.player = self._generator(
            self.cfg, self.rng, depth=self.depth, player=self.player
        )
        self.scouting = False
        self.update_fov()
        self.log.add(
            f"You descend to depth {self.depth}. The monsters here are stronger.",
            config.TITLE_COLOR,
        )

    # --- equipment/upgrade-derived player values ---------------------------
    def _player_bonus(self, btype: BonusType) -> float:
        """Sum of the player's equipped-item and permanent-upgrade bonuses."""
        total = 0.0
        equipment = self.player.get("equipment")
        if equipment is not None:
            total += equipment.total(btype)
        upgrades = self.player.get("upgrades")
        if upgrades is not None:
            total += upgrades.total(btype)
        return total

    def heal_amount(self) -> int:
        return self.cfg.heal_amount + int(self._player_bonus(BonusType.HEAL_POWER))

    def toggle_equip(self, item: Item) -> None:
        """Equip or unequip an inventory item (max two in use at once)."""
        equipment = self.player.get("equipment")
        if equipment is None:
            return
        result = equipment.toggle(item)
        if result == "equip":
            self.log.add(f"You ready the {item.name}.", item.color)
        elif result == "unequip":
            self.log.add(f"You stow the {item.name}.", config.TEXT_DIM)
        else:
            self.log.add("You can only use two items at once.", config.TEXT_DIM)
        self.update_fov()  # a view-radius item may have changed sight

    def character_sheet(self) -> list[tuple[str, str]]:
        """(label, value) pairs of the player's current effective stats."""
        fighter = self.player.fighter
        progress = self.player.get("progress")
        view = self.cfg.fov_radius + int(self._player_bonus(BonusType.VIEW_RADIUS))
        return [
            ("Max HP", str(fighter.max_hp)),
            ("Damage", str(fighter.power)),
            ("Defense", str(fighter.defense)),
            ("Atk Range", str(fighter.attack_range)),
            ("Crit", f"{fighter.crit_chance * 100:.0f}%"),
            ("Dodge", f"{fighter.dodge_chance * 100:.0f}%"),
            ("View", str(view)),
            ("Heal", str(self.heal_amount())),
            ("Gold", str(progress.gold if progress else 0)),
        ]

    # --- merchant / shop ---------------------------------------------------
    def open_shop(self, merchant: Entity) -> None:
        self.shop = merchant
        self.log.add("The merchant lays out their wares.", config.MERCHANT_COLOR)

    def close_shop(self) -> None:
        self.shop = None

    def upgrade_cost(self, btype: BonusType) -> int:
        """Gold cost of the next upgrade of ``btype`` (rises with each bought)."""
        upgrades = self.player.get("upgrades")
        owned = upgrades.count(btype) if upgrades is not None else 0
        return round(UPGRADE_BASE_COST[btype] * self.cfg.upgrade_cost_growth ** owned)

    def shop_rows(self) -> list[tuple]:
        """Rows shown in the shop: buyable upgrades, then sellable items."""
        rows = [("upgrade", btype) for btype in BonusType]
        rows += [("sell", item) for item in self.player.inventory.items]
        return rows

    def buy_upgrade(self, btype: BonusType) -> None:
        progress = self.player.get("progress")
        upgrades = self.player.get("upgrades")
        if progress is None or upgrades is None:
            return
        cost = self.upgrade_cost(btype)
        if progress.gold < cost:
            self.log.add("Not enough gold.", config.TEXT_DIM)
            return
        progress.gold -= cost
        upgrades.buy(btype)
        self.update_fov()
        self.log.add(
            f"Upgraded {format_bonus(btype, UPGRADE_STEP[btype])} for {cost}g.",
            config.MERCHANT_COLOR,
        )

    def sell_item(self, item: Item) -> None:
        inventory = self.player.inventory
        equipment = self.player.get("equipment")
        progress = self.player.get("progress")
        if item not in inventory.items:
            return
        if equipment is not None and equipment.is_equipped(item):
            equipment.equipped.remove(item)
            self.player.fighter.clamp_hp()
        inventory.items.remove(item)
        price = self.cfg.sell_price_per_level * item.level
        if progress is not None:
            progress.gold += price
        self.update_fov()
        self.log.add(f"Sold {item.display_name} for {price}g.", config.MERCHANT_COLOR)

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

        # The monster's danger level sets the power of the item it drops.
        item = generate_item(self.rng, loot_marker.level)
        progress = killer.get("progress")
        inventory = killer.inventory

        if progress is not None:
            reward = self.cfg.reward_gold_per_tier * item.level
            progress.gold += reward
            progress.kills += 1

        if inventory is not None:
            if inventory.add(item):
                self.log.add(f"You loot the {item.display_name}.", item.color)
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
