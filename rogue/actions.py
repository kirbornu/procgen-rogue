"""Actions - the verbs of the game.

Input and AI both produce :class:`Action` objects; ``perform`` applies them to
the world and reports whether a game turn was consumed.  New verbs (open door,
throw, cast, ...) are new subclasses - the turn loop never needs to know about
them individually.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING

from . import config

if TYPE_CHECKING:
    from .engine import Engine
    from .entity import Entity


@dataclass
class ActionResult:
    #: Whether performing this action advances the world (monsters then act).
    advances_turn: bool = False


class Action:
    def __init__(self, actor: "Entity") -> None:
        self.actor = actor

    def perform(self, engine: "Engine") -> ActionResult:  # pragma: no cover
        raise NotImplementedError


class WaitAction(Action):
    """Pass the turn without doing anything else."""

    def perform(self, engine: "Engine") -> ActionResult:
        return ActionResult(advances_turn=True)


class QuitAction(Action):
    """Handled by the app layer; never advances a turn."""

    def perform(self, engine: "Engine") -> ActionResult:
        return ActionResult(advances_turn=False)


class MoveAction(Action):
    def __init__(self, actor: "Entity", dx: int, dy: int) -> None:
        super().__init__(actor)
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine") -> ActionResult:
        dest_x = self.actor.x + self.dx
        dest_y = self.actor.y + self.dy
        game_map = engine.game_map

        if not game_map.in_bounds(dest_x, dest_y):
            return ActionResult(advances_turn=False)
        if not game_map.is_walkable(dest_x, dest_y):
            if self.actor is engine.player:
                engine.log.add("The way is blocked.", config.TEXT_DIM)
            return ActionResult(advances_turn=False)
        if game_map.blocking_entity_at(dest_x, dest_y) is not None:
            return ActionResult(advances_turn=False)

        self.actor.move(self.dx, self.dy)
        return ActionResult(advances_turn=True)


class MeleeAction(Action):
    """Resolve one attack from ``actor`` against ``target``.

    ``resolve`` contains the damage logic so both the player's bump-attack and a
    monster's retaliation share exactly the same code path.
    """

    def __init__(self, actor: "Entity", target: "Entity") -> None:
        super().__init__(actor)
        self.target = target

    def resolve(self, engine: "Engine") -> None:
        attacker, target = self.actor, self.target
        if attacker.fighter is None or target.fighter is None:
            return

        damage = max(0, attacker.fighter.power - target.fighter.defense)
        by_player = attacker is engine.player
        color = config.HP_BAR_FILLED if by_player else config.MONSTER_COLOR
        hit = "hit" if by_player else "hits"  # "You hit" vs "Goblin hits"

        if damage > 0:
            engine.log.add(
                f"{attacker.name} {hit} {target.name} for {damage}.", color
            )
            target.fighter.take_damage(damage)
        else:
            engine.log.add(
                f"{attacker.name} {hit} {target.name} but deal no damage.",
                config.TEXT_DIM,
            )

        if target.fighter.hp <= 0:
            engine.kill(target, attacker)

    def perform(self, engine: "Engine") -> ActionResult:
        self.resolve(engine)
        return ActionResult(advances_turn=True)


class BumpAction(Action):
    """Directional player intent: attack a blocker if present, else step there.

    This keeps controls to a single set of movement keys while supporting the
    "walk into a monster to fight it" convention.
    """

    def __init__(self, actor: "Entity", dx: int, dy: int) -> None:
        super().__init__(actor)
        self.dx = dx
        self.dy = dy

    def perform(self, engine: "Engine") -> ActionResult:
        dest_x = self.actor.x + self.dx
        dest_y = self.actor.y + self.dy
        target = engine.game_map.blocking_entity_at(dest_x, dest_y)
        if target is not None and target.fighter is not None:
            return MeleeAction(self.actor, target).perform(engine)
        return MoveAction(self.actor, self.dx, self.dy).perform(engine)
