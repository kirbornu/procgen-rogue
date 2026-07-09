"""Head-less tests for the game logic.

None of these touch the renderer, so they run anywhere - no display required.
They double as executable documentation of how the systems fit together.
"""
from __future__ import annotations

from dataclasses import replace

from rogue import config
from rogue.actions import BumpAction, HealAction, MoveAction, ScoutAction, WaitAction
from rogue.engine import Engine
from rogue.geometry import Direction, chebyshev
from rogue.items import make_stick, roll_loot
from rogue.rng import Rng
from rogue.spawn import make_monster
from rogue.ui.camera import Camera
from rogue.world.procgen import generate_dungeon


def test_generation_is_deterministic_and_placed_player():
    map_a, player_a = generate_dungeon(config.DEFAULT, Rng(123))
    map_b, player_b = generate_dungeon(config.DEFAULT, Rng(123))
    # Same seed -> identical layout and player start.
    assert (map_a.tiles == map_b.tiles).all()
    assert (player_a.x, player_a.y) == (player_b.x, player_b.y)
    # The player always spawns on a walkable tile.
    assert map_a.is_walkable(player_a.x, player_a.y)


def test_fov_radius_limits_visibility():
    engine = Engine(seed=7)
    px, py = engine.player.x, engine.player.y
    # Nothing outside the fog-of-war radius is visible.
    for x in range(engine.game_map.width):
        for y in range(engine.game_map.height):
            if engine.game_map.visible[x, y]:
                assert chebyshev(px, py, x, y) <= config.DEFAULT.fov_radius


def test_wait_advances_turn():
    engine = Engine(seed=1)
    assert WaitAction(engine.player).perform(engine).advances_turn


def test_move_into_wall_is_blocked():
    engine = Engine(seed=1)
    # Force a wall next to the player and confirm we cannot step into it.
    from rogue.world import tiles

    px, py = engine.player.x, engine.player.y
    engine.game_map.tiles[px + 1, py] = tiles.WALL
    result = MoveAction(engine.player, 1, 0).perform(engine)
    assert not result.advances_turn
    assert (engine.player.x, engine.player.y) == (px, py)


def test_bump_attack_kills_monster_and_awards_loot():
    engine = Engine(seed=1)
    px, py = engine.player.x, engine.player.y
    # Put a fragile monster right next to the player.
    monster = make_monster(px + 1, py)
    monster.fighter.hp = 1
    monster.fighter.defense = 0
    engine.game_map.entities.append(monster)

    engine.handle_player_action(BumpAction(engine.player, 1, 0))

    assert not monster.is_alive
    assert engine.player.get("progress").kills == 1
    assert engine.player.get("progress").gold > 0
    assert len(engine.player.inventory.items) == 1
    assert engine.player.inventory.items[0].kind.value == "stick"


def test_monster_retaliates_when_adjacent():
    engine = Engine(seed=1)
    px, py = engine.player.x, engine.player.y
    monster = make_monster(px + 1, py)
    engine.game_map.entities.append(monster)
    start_hp = engine.player.fighter.hp

    # Waiting next to a live monster should let it hit back.
    engine.handle_player_action(WaitAction(engine.player))
    assert engine.player.fighter.hp < start_hp


def _adjacent_monster(engine):
    """Drop a monster right next to the player and return it."""
    monster = make_monster(engine.player.x + 1, engine.player.y)
    engine.game_map.entities.append(monster)
    return monster


def test_auto_attack_strikes_enemy_in_range_on_wait():
    engine = Engine(seed=1)
    monster = _adjacent_monster(engine)
    before = monster.fighter.hp
    # Waiting is not an activity, so the auto-attack fires.
    engine.handle_player_action(WaitAction(engine.player))
    assert monster.fighter.hp < before


def test_heal_restores_hp():
    engine = Engine(seed=1)  # player starts alone in the first room
    engine.player.fighter.hp = 5
    engine.handle_player_action(HealAction(engine.player))
    assert engine.player.fighter.hp == 5 + config.DEFAULT.heal_amount


def test_activity_suppresses_auto_attack():
    engine = Engine(seed=1)
    monster = _adjacent_monster(engine)
    before = monster.fighter.hp
    # Healing is an activity, so the player does not auto-attack this turn.
    engine.handle_player_action(HealAction(engine.player))
    assert monster.fighter.hp == before


def test_scouting_boosts_fov_and_clears_on_move():
    engine = Engine(seed=3)
    engine.scouting = False
    engine.update_fov()
    base = int(engine.game_map.visible.sum())
    engine.scouting = True
    engine.update_fov()
    assert int(engine.game_map.visible.sum()) >= base

    # Performing the scout activity sets the state...
    engine = Engine(seed=3)
    engine.handle_player_action(ScoutAction(engine.player))
    assert engine.scouting is True

    # ...and moving to a new tile clears it.
    moved = False
    for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
        nx, ny = engine.player.x + dx, engine.player.y + dy
        if engine.game_map.is_walkable(nx, ny) and engine.game_map.blocking_entity_at(nx, ny) is None:
            engine.handle_player_action(BumpAction(engine.player, dx, dy))
            moved = True
            break
    assert moved and engine.scouting is False


def test_attack_range_reaches_beyond_adjacent():
    cfg = replace(config.DEFAULT, player_attack_range=2)
    engine = Engine(cfg=cfg, seed=1)
    # Enemy two tiles away: out of a range-1 reach, in range for this config.
    monster = make_monster(engine.player.x + 2, engine.player.y)
    engine.game_map.entities.append(monster)
    before = monster.fighter.hp
    engine.handle_player_action(WaitAction(engine.player))
    assert monster.fighter.hp < before


def test_loot_tiers_are_bounded():
    rng = Rng(99)
    for _ in range(500):
        item = roll_loot(rng, config.DEFAULT)
        assert 1 <= item.tier <= 5


def test_stick_tier_is_clamped():
    assert make_stick(0).tier == 1
    assert make_stick(9).tier == 5


def test_camera_clamps_to_map_bounds():
    cam = Camera(view_width=80, view_height=43)
    cam.center_on(0, 0, map_width=100, map_height=60)
    assert (cam.x, cam.y) == (0, 0)
    cam.center_on(999, 999, map_width=100, map_height=60)
    assert cam.x == 100 - 80
    assert cam.y == 60 - 43


def test_direction_offsets():
    assert (Direction.NE.dx, Direction.NE.dy) == (1, -1)
    assert (Direction.HERE.dx, Direction.HERE.dy) == (0, 0)


def test_input_dispatch_maps_keys():
    import tcod.event

    from rogue.input import Command, dispatch

    engine = Engine(seed=1)
    K = tcod.event.KeySym

    def key(sym):
        return tcod.event.KeyDown(sym=sym, scancode=0, mod=tcod.event.Modifier(0))

    # A movement key becomes a BumpAction with the right offset.
    move = dispatch(key(K.L), engine.player)  # vi 'l' -> east
    assert isinstance(move, BumpAction) and (move.dx, move.dy) == (1, 0)
    # Arrow keys work too.
    up = dispatch(key(K.UP), engine.player)
    assert isinstance(up, BumpAction) and (up.dx, up.dy) == (0, -1)
    # Wait and UI/quit commands resolve.
    assert isinstance(dispatch(key(K.PERIOD), engine.player), WaitAction)
    assert dispatch(key(K.I), engine.player) is Command.TOGGLE_INVENTORY
    assert dispatch(key(K.ESCAPE), engine.player) is Command.QUIT
    # Unbound keys are ignored.
    assert dispatch(key(K.F1), engine.player) is None
