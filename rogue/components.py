"""Entity components.

Each component is a small data-holder with optional helpers.  They keep a back
reference to their owning :class:`~rogue.entity.Entity` (set on ``entity.add``)
so a component can reach its siblings when needed - for example ``Fighter`` reads
the owner's ``Equipment`` to fold item bonuses into its effective stats.
"""
from __future__ import annotations

from typing import List, Optional, TYPE_CHECKING

from . import config
from .bonuses import BonusType
from .items import Item

if TYPE_CHECKING:
    from .engine import Engine
    from .entity import Entity


class Component:
    """Base class; ``entity`` is filled in when attached via ``Entity.add``."""

    entity: "Entity"


class Fighter(Component):
    """Hit points and combat stats.

    Stats are stored as *base* values; the public properties add any bonuses
    from equipped items, so combat code can read ``fighter.power`` and always get
    the effective value without knowing about equipment.
    """

    def __init__(
        self,
        hp: int,
        power: int,
        defense: int,
        attack_range: int = 1,
        crit_chance: float = 0.0,
        dodge_chance: float = 0.0,
    ) -> None:
        self.base_max_hp = hp
        self._hp = hp
        self.base_power = power
        self.defense = defense
        self.base_attack_range = attack_range
        self.base_crit_chance = crit_chance
        self.base_dodge_chance = dodge_chance

    def _bonus(self, btype: BonusType) -> float:
        entity = getattr(self, "entity", None)
        equipment = entity.get("equipment") if entity is not None else None
        return equipment.total(btype) if equipment is not None else 0

    @property
    def max_hp(self) -> int:
        return self.base_max_hp + int(self._bonus(BonusType.MAX_HP))

    @property
    def power(self) -> int:
        return self.base_power + int(self._bonus(BonusType.DAMAGE))

    @property
    def attack_range(self) -> int:
        return self.base_attack_range + int(self._bonus(BonusType.ATTACK_RANGE))

    @property
    def crit_chance(self) -> float:
        return self.base_crit_chance + self._bonus(BonusType.CRIT_CHANCE)

    @property
    def dodge_chance(self) -> float:
        return self.base_dodge_chance + self._bonus(BonusType.DODGE_CHANCE)

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

    def clamp_hp(self) -> None:
        """Re-apply the max-HP cap, e.g. after equipment changed max_hp."""
        self.hp = self._hp


def _sign(value: int) -> int:
    return (value > 0) - (value < 0)


class MonsterAI(Component):
    """Procedural monster behaviour.

    ``speed`` is a 0..1 chance to take a step toward the player each turn, so
    speed 0 stands still (as the original monsters did) and speed 1 always
    advances.  When in melee range it trades blows instead of moving.
    """

    attack_range: int = 1

    def __init__(self, speed: float = 0.0, sight: int = 10) -> None:
        self.speed = speed
        self.sight = sight

    def take_turn(self, engine: "Engine") -> None:
        me = self.entity
        player = engine.player
        if not me.is_alive or not player.is_alive:
            return

        distance = me.distance_to(player)
        if distance <= self.attack_range:
            from .actions import MeleeAction

            MeleeAction(me, player).resolve(engine)
        elif distance <= self.sight and engine.rng.chance(self.speed):
            self._step_toward(engine, player.x, player.y)

    def _step_toward(self, engine: "Engine", tx: int, ty: int) -> None:
        me = self.entity
        game_map = engine.game_map
        dx, dy = _sign(tx - me.x), _sign(ty - me.y)
        # Try the diagonal first, then straighten out around obstacles.
        for ax, ay in ((dx, dy), (dx, 0), (0, dy)):
            if ax == 0 and ay == 0:
                continue
            nx, ny = me.x + ax, me.y + ay
            if game_map.is_walkable(nx, ny) and game_map.blocking_entity_at(nx, ny) is None:
                me.move(ax, ay)
                return


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


class Equipment(Component):
    """The (up to) two items the player is actively using.

    Equipped items' bonuses are summed by :meth:`total`, which ``Fighter`` and
    the engine query to build effective stats.  Everything else in the inventory
    just sits there until equipped.
    """

    def __init__(self, capacity: int = 2) -> None:
        self.capacity = capacity
        self.equipped: List[Item] = []

    @property
    def is_full(self) -> bool:
        return len(self.equipped) >= self.capacity

    def is_equipped(self, item: Item) -> bool:
        return item in self.equipped

    def toggle(self, item: Item) -> str:
        """Equip or unequip ``item``; returns 'equip' / 'unequip' / 'full'."""
        if item in self.equipped:
            self.equipped.remove(item)
            result = "unequip"
        elif not self.is_full:
            self.equipped.append(item)
            result = "equip"
        else:
            return "full"
        # Max HP may have changed; keep current HP within the new cap.
        entity = getattr(self, "entity", None)
        if entity is not None and entity.fighter is not None:
            entity.fighter.clamp_hp()
        return result

    def total(self, btype: BonusType) -> float:
        return sum(item.bonuses.get(btype, 0) for item in self.equipped)


class Loot(Component):
    """Marks an entity as dropping loot, and at what item level."""

    def __init__(self, level: int) -> None:
        self.level = level


class Progress(Component):
    """Player-side progression: gold and kill count (easy to extend to XP)."""

    def __init__(self) -> None:
        self.gold = 0
        self.kills = 0
