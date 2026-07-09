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
    #: Whether this was a deliberate *activity* (heal, scout, ...).  Activities
    #: occupy the player, so the automatic attack is suppressed for the turn.
    #: Moving and waiting are NOT activities and still auto-attack.
    is_activity: bool = False


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


class HealAction(Action):
    """Activity: tend wounds to recover a small amount of HP.

    Being an activity, it suppresses the auto-attack for the turn - you cannot
    fight and bandage at the same time - while monsters still get to act.
    """

    def perform(self, engine: "Engine") -> ActionResult:
        fighter = self.actor.fighter
        if fighter is None:
            return ActionResult(advances_turn=False)
        recovered = fighter.heal(engine.heal_amount())
        if recovered > 0:
            engine.log.add(f"You tend your wounds (+{recovered} HP).", config.HP_BAR_FILLED)
        else:
            engine.log.add("You are already at full health.", config.TEXT_DIM)
        return ActionResult(advances_turn=True, is_activity=True)


class ScoutAction(Action):
    """Activity: widen your field of view until you next move.

    Sets the scouting state on the engine; :meth:`Engine.update_fov` then uses
    the boosted radius, and moving clears it.
    """

    def perform(self, engine: "Engine") -> ActionResult:
        engine.scouting = True
        engine.log.add("You scan the surroundings.", config.TITLE_COLOR)
        return ActionResult(advances_turn=True, is_activity=True)


class DescendAction(Action):
    """Activate the down-stairs to move on to a deeper, tougher level."""

    def perform(self, engine: "Engine") -> ActionResult:
        if not engine.on_stairs():
            engine.log.add("There are no stairs to descend here.", config.TEXT_DIM)
            return ActionResult(advances_turn=False)
        # descend() rebuilds the world and refreshes FOV itself, so the normal
        # post-action turn processing must not run on the old map.
        engine.descend()
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
        af, tf = attacker.fighter, target.fighter
        if af is None or tf is None:
            return

        by_player = attacker is engine.player
        hit = "hit" if by_player else "hits"  # "You hit" vs "Goblin hits"

        # The defender may evade the blow entirely.
        if engine.rng.chance(tf.dodge_chance):
            dodge = "dodge" if target is engine.player else "dodges"
            engine.log.add(f"{target.name} {dodge} the blow.", config.TEXT_DIM)
            return

        damage = max(0, af.power - tf.defense)
        crit = engine.rng.chance(af.crit_chance)
        if crit:
            damage *= 2

        if damage > 0:
            suffix = " (crit!)" if crit else ""
            color = config.TITLE_COLOR if crit else (
                config.HP_BAR_FILLED if by_player else config.MONSTER_COLOR
            )
            engine.log.add(f"{attacker.name} {hit} {target.name} for {damage}{suffix}.", color)
            tf.take_damage(damage)
        else:
            engine.log.add(
                f"{attacker.name} {hit} {target.name} but deal no damage.",
                config.TEXT_DIM,
            )

        if tf.hp <= 0:
            engine.kill(target, attacker)

    def perform(self, engine: "Engine") -> ActionResult:
        self.resolve(engine)
        return ActionResult(advances_turn=True)


class BumpAction(Action):
    """Directional player intent: step there, or hold ground against a blocker.

    Combat itself is handled by the engine's auto-attack (any enemy within the
    player's attack range is struck automatically on a non-activity turn), so
    bumping an enemy simply spends the turn in place and lets the auto-attack
    land.  Walking into a wall does nothing and costs no turn.
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
            # Hold position and fight; the auto-attack resolves the damage.
            return ActionResult(advances_turn=True)
        return MoveAction(self.actor, self.dx, self.dy).perform(engine)
