"""Head-less tests for the game logic.

None of these touch the renderer, so they run anywhere - no display required.
They double as executable documentation of how the systems fit together.
"""
from __future__ import annotations

from dataclasses import replace

from rogue import config
from rogue.actions import BumpAction, HealAction, MoveAction, ScoutAction, WaitAction
from rogue.bonuses import UPGRADE_STEP, BonusType
from rogue.components import Fighter, MonsterAI
from rogue.engine import Engine
from rogue.entity import Entity
from rogue.geometry import Direction, chebyshev
from rogue.items import MAX_LEVEL, generate_item
from rogue.rng import Rng
from rogue.spawn import danger_color, danger_level, make_monster
from rogue.ui.camera import Camera
from rogue.world.game_map import GameMap
from rogue.world.procgen import generate_dungeon, generate_noise_dungeon


def make_engine(**kwargs):
    """Engine wired to the fast, fully-connected room generator.

    The real game defaults to the pure-Python noise cave, which takes a few
    seconds to build; tests use rooms so the suite stays quick and combat starts
    from a predictable, connected layout.
    """
    kwargs.setdefault("generator", generate_dungeon)
    return Engine(**kwargs)


def test_generation_is_deterministic_and_placed_player():
    map_a, player_a = generate_dungeon(config.DEFAULT, Rng(123))
    map_b, player_b = generate_dungeon(config.DEFAULT, Rng(123))
    # Same seed -> identical layout and player start.
    assert (map_a.tiles == map_b.tiles).all()
    assert (player_a.x, player_a.y) == (player_b.x, player_b.y)
    # The player always spawns on a walkable tile.
    assert map_a.is_walkable(player_a.x, player_a.y)


def test_fov_radius_limits_visibility():
    engine = make_engine(seed=7)
    px, py = engine.player.x, engine.player.y
    # Nothing outside the fog-of-war radius is visible.
    for x in range(engine.game_map.width):
        for y in range(engine.game_map.height):
            if engine.game_map.visible[x, y]:
                assert chebyshev(px, py, x, y) <= config.DEFAULT.fov_radius


def test_wait_advances_turn():
    engine = make_engine(seed=1)
    assert WaitAction(engine.player).perform(engine).advances_turn


def test_move_into_wall_is_blocked():
    engine = make_engine(seed=1)
    # Force a wall next to the player and confirm we cannot step into it.
    from rogue.world import tiles

    px, py = engine.player.x, engine.player.y
    engine.game_map.tiles[px + 1, py] = tiles.WALL
    result = MoveAction(engine.player, 1, 0).perform(engine)
    assert not result.advances_turn
    assert (engine.player.x, engine.player.y) == (px, py)


def _place_monster(engine, dx, dy, *, hp=None, power=5):
    """Drop a monster with deterministic combat stats near the player.

    Procedural monsters roll random crit/dodge/power, so tests pin those down to
    keep combat assertions reliable.
    """
    monster = make_monster(engine.rng, engine.player.x + dx, engine.player.y + dy)
    if hp is not None:
        monster.fighter.base_max_hp = hp
        monster.fighter.hp = hp
    monster.fighter.base_power = power
    monster.fighter.base_crit_chance = 0.0
    monster.fighter.base_dodge_chance = 0.0
    monster.fighter.defense = 0
    engine.game_map.entities.append(monster)
    return monster


def _adjacent_monster(engine, **kwargs):
    return _place_monster(engine, 1, 0, **kwargs)


def test_bump_attack_kills_monster_and_awards_loot():
    engine = make_engine(seed=1)
    monster = _adjacent_monster(engine, hp=1)
    engine.handle_player_action(BumpAction(engine.player, 1, 0))

    assert not monster.is_alive
    assert engine.player.get("progress").kills == 1
    assert engine.player.get("progress").gold > 0
    # Loot is a procedurally generated item with at least one bonus.
    items = engine.player.inventory.items
    assert len(items) == 1
    assert 1 <= len(items[0].bonuses) <= len(BonusType)


def test_monster_retaliates_when_adjacent():
    engine = make_engine(seed=1)
    _adjacent_monster(engine, hp=50)  # tough enough to survive and hit back
    start_hp = engine.player.fighter.hp
    engine.handle_player_action(WaitAction(engine.player))
    assert engine.player.fighter.hp < start_hp


def test_auto_attack_strikes_enemy_in_range_on_wait():
    engine = make_engine(seed=1)
    monster = _adjacent_monster(engine, hp=50)
    before = monster.fighter.hp
    # Waiting is not an activity, so the auto-attack fires.
    engine.handle_player_action(WaitAction(engine.player))
    assert monster.fighter.hp < before


def test_heal_restores_hp():
    engine = make_engine(seed=1)  # player starts alone in the first room
    engine.player.fighter.hp = 5
    engine.handle_player_action(HealAction(engine.player))
    assert engine.player.fighter.hp == 5 + config.DEFAULT.heal_amount


def test_activity_suppresses_auto_attack():
    engine = make_engine(seed=1)
    monster = _adjacent_monster(engine, hp=50)
    before = monster.fighter.hp
    # Healing is an activity, so the player does not auto-attack this turn.
    engine.handle_player_action(HealAction(engine.player))
    assert monster.fighter.hp == before


def test_scouting_boosts_fov_and_clears_on_move():
    engine = make_engine(seed=3)
    engine.scouting = False
    engine.update_fov()
    base = int(engine.game_map.visible.sum())
    engine.scouting = True
    engine.update_fov()
    assert int(engine.game_map.visible.sum()) >= base

    # Performing the scout activity sets the state...
    engine = make_engine(seed=3)
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
    engine = make_engine(cfg=cfg, seed=1)
    # Enemy two tiles away: out of a range-1 reach, in range for this config.
    monster = _place_monster(engine, 2, 0, hp=50)
    before = monster.fighter.hp
    engine.handle_player_action(WaitAction(engine.player))
    assert monster.fighter.hp < before


def test_generated_item_is_bounded_and_named_by_level():
    rng = Rng(99)
    for _ in range(500):
        requested = rng.randint(0, 9)  # includes out-of-range to test clamping
        item = generate_item(rng, requested)
        assert 1 <= item.level <= MAX_LEVEL
        # Bonuses aggregate by type, so distinct count is 1..#bonus types.
        assert 1 <= len(item.bonuses) <= len(BonusType)
        # Higher level -> more words: exactly `level` words in the name.
        assert len(item.name.split()) == item.level
        assert all(value >= 0 for value in item.bonuses.values())


def test_equipment_is_limited_to_two_items():
    engine = make_engine(seed=1)
    eq = engine.player.get("equipment")
    items = [generate_item(engine.rng, 3) for _ in range(3)]
    for item in items:
        engine.player.inventory.add(item)

    engine.toggle_equip(items[0])
    engine.toggle_equip(items[1])
    assert len(eq.equipped) == 2
    engine.toggle_equip(items[2])  # third is refused
    assert len(eq.equipped) == 2 and not eq.is_equipped(items[2])
    engine.toggle_equip(items[0])  # unequipping frees a slot
    assert len(eq.equipped) == 1


def test_equipped_bonuses_apply_and_revert():
    engine = make_engine(seed=1)
    fighter = engine.player.fighter
    base_hp, base_power = fighter.max_hp, fighter.power

    item = generate_item(engine.rng, 5)
    item.bonuses.clear()
    item.bonuses[BonusType.MAX_HP] = 10
    item.bonuses[BonusType.DAMAGE] = 3
    engine.player.inventory.add(item)

    engine.toggle_equip(item)
    assert fighter.max_hp == base_hp + 10
    assert fighter.power == base_power + 3

    engine.toggle_equip(item)  # unequip reverts stats and re-clamps HP
    assert fighter.max_hp == base_hp
    assert fighter.hp <= base_hp


def test_view_and_heal_bonuses_reach_the_engine():
    engine = make_engine(seed=1)
    base_heal = engine.heal_amount()
    item = generate_item(engine.rng, 3)
    item.bonuses.clear()
    item.bonuses[BonusType.HEAL_POWER] = 4
    item.bonuses[BonusType.VIEW_RADIUS] = 3
    engine.player.inventory.add(item)
    engine.toggle_equip(item)

    assert engine.heal_amount() == base_heal + 4
    assert engine._player_bonus(BonusType.VIEW_RADIUS) == 3


def test_monster_moves_only_when_it_has_speed():
    import types

    from rogue.world import tiles

    game_map = GameMap(20, 3)
    game_map.tiles[1:19, 1:2] = tiles.FLOOR  # a one-row corridor at y=1

    player = Entity(1, 1, "@", (255, 255, 255), "You", blocks_movement=True)
    player.add("fighter", Fighter(10, 5, 2))
    stub = types.SimpleNamespace(game_map=game_map, player=player, rng=Rng(0))

    still = Entity(10, 1, "r", (0, 0, 0), "Rat", blocks_movement=True)
    still.add("fighter", Fighter(5, 2, 0))
    still.add("ai", MonsterAI(speed=0.0))
    game_map.entities.append(still)
    still.ai.take_turn(stub)
    assert (still.x, still.y) == (10, 1)  # speed 0 -> never moves

    fast = Entity(12, 1, "o", (0, 0, 0), "Ogre", blocks_movement=True)
    fast.add("fighter", Fighter(5, 2, 0))
    fast.add("ai", MonsterAI(speed=1.0, sight=20))
    game_map.entities.append(fast)
    fast.ai.take_turn(stub)
    assert fast.x == 11  # stepped one tile toward the player at x=1


def test_danger_maps_to_level_and_colour():
    assert danger_level(0.0) == 1
    assert danger_level(1.0) == MAX_LEVEL
    assert danger_level(0.0) <= danger_level(0.5) <= danger_level(1.0)
    low, high = danger_color(0.1), danger_color(0.9)
    assert high[0] > low[0]  # deadlier is redder
    assert high[1] < low[1]  # and less green


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

    engine = make_engine(seed=1)
    K = tcod.event.KeySym

    def key(sym):
        return tcod.event.KeyDown(sym=sym, scancode=0, mod=tcod.event.Modifier(0))

    # A movement key becomes a BumpAction with the right offset.
    move = dispatch(key(K.D), engine.player)  # 'd' -> east
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


def test_noise_dungeon_is_playable_and_deterministic():
    # Small map keeps the pure-Python noise fast enough for a unit test.
    cfg = replace(config.DEFAULT, noise_map_size=48)

    map_a, player_a = generate_noise_dungeon(cfg, Rng(7))
    map_b, player_b = generate_noise_dungeon(cfg, Rng(7))
    # Deterministic for a given seed.
    assert (map_a.tiles == map_b.tiles).all()
    assert (player_a.x, player_a.y) == (player_b.x, player_b.y)

    # Walls follow the brightness threshold: the map has both walls and floor.
    walkable = map_a.tiles["walkable"]
    assert walkable.any() and not walkable.all()

    # The player spawns on floor, and the single down-stairs is reachable from
    # the start by walking and taking portals (the whole chain is traversable).
    assert map_a.is_walkable(player_a.x, player_a.y)
    stairs = [e for e in map_a.entities if e.has("stairs")]
    assert len(stairs) == 1
    reachable = _reachable_via_portals(map_a, (player_a.x, player_a.y))
    assert (stairs[0].x, stairs[0].y) in reachable

    # The cave is populated with monsters on floor tiles.
    monsters = [e for e in map_a.entities if e.get("ai") is not None]
    assert monsters
    assert all(map_a.is_walkable(m.x, m.y) for m in monsters)


def test_noise_portals_form_a_one_way_chain():
    cfg = replace(config.DEFAULT, noise_map_size=48)
    game_map, player = generate_noise_dungeon(cfg, Rng(5))
    portals = [e for e in game_map.entities if e.get("teleport") is not None]
    stairs = [e for e in game_map.entities if e.has("stairs")]
    assert len(stairs) == 1

    # The final (stairs) region holds no portal.
    stairs_region = _flood_region(game_map, stairs[0].x, stairs[0].y)
    assert not any((p.x, p.y) in stairs_region for p in portals)

    # Every portal is one-way into a *different* region than the one it sits in.
    for portal in portals:
        dest = portal.get("teleport").dest
        assert dest is not None
        assert dest not in _flood_region(game_map, portal.x, portal.y)

    # And the chain is walkable end to end, from the player to the stairs.
    reachable = _reachable_via_portals(game_map, (player.x, player.y))
    assert (stairs[0].x, stairs[0].y) in reachable


def test_stepping_onto_a_portal_warps_to_its_destination():
    from rogue.spawn import make_teleport
    from rogue.world import tiles

    engine = make_engine(seed=1)
    px, py = engine.player.x, engine.player.y
    engine.game_map.tiles[px + 1, py] = tiles.FLOOR  # ensure a step east is legal

    portal = make_teleport(px + 1, py)
    portal.get("teleport").dest = (px + 6, py)
    engine.game_map.entities.append(portal)

    engine.handle_player_action(BumpAction(engine.player, 1, 0))
    assert (engine.player.x, engine.player.y) == (px + 6, py)


def test_descend_deepens_level_and_carries_player_over():
    engine = make_engine(seed=1)
    player = engine.player
    player.inventory.add(generate_item(engine.rng, 2))
    player.fighter.hp = 7
    items_before = len(player.inventory.items)

    engine.descend()

    assert engine.depth == 2
    assert engine.player is player  # same entity, so stats/inventory persist
    assert len(engine.player.inventory.items) == items_before
    assert engine.player.fighter.hp == 7


def test_deeper_monsters_are_tougher():
    rng = Rng(5)
    shallow = [make_monster(rng, 0, 0, depth=1).fighter.base_max_hp for _ in range(60)]
    deep = [make_monster(rng, 0, 0, depth=6).fighter.base_max_hp for _ in range(60)]
    assert sum(deep) / len(deep) > sum(shallow) / len(shallow)


# --- gold: merchant, upgrades, selling, decorations, auto-descend ----------
def test_buy_upgrade_raises_stat_and_costs_escalate():
    engine = make_engine(seed=1)
    progress = engine.player.get("progress")
    progress.gold = 1000
    base = engine.player.fighter.max_hp

    cost1 = engine.upgrade_cost(BonusType.MAX_HP)
    engine.buy_upgrade(BonusType.MAX_HP)
    assert engine.player.fighter.max_hp == base + UPGRADE_STEP[BonusType.MAX_HP]
    assert progress.gold == 1000 - cost1
    # The next upgrade of the same stat costs more.
    assert engine.upgrade_cost(BonusType.MAX_HP) > cost1


def test_upgrade_blocked_without_gold():
    engine = make_engine(seed=1)
    progress = engine.player.get("progress")
    progress.gold = 0
    base_power = engine.player.fighter.power
    engine.buy_upgrade(BonusType.DAMAGE)
    assert engine.player.fighter.power == base_power
    assert progress.gold == 0


def test_sell_item_gives_gold_and_removes_it():
    engine = make_engine(seed=1)
    progress = engine.player.get("progress")
    progress.gold = 0
    item = generate_item(engine.rng, 3)
    engine.player.inventory.add(item)
    engine.toggle_equip(item)

    engine.sell_item(item)
    assert progress.gold == engine.cfg.sell_price_per_level * 3
    assert item not in engine.player.inventory.items
    assert not engine.player.get("equipment").is_equipped(item)


def test_character_sheet_reflects_upgrades():
    engine = make_engine(seed=1)
    engine.player.get("progress").gold = 1000
    before = int(dict(engine.character_sheet())["Damage"])
    engine.buy_upgrade(BonusType.DAMAGE)
    after = int(dict(engine.character_sheet())["Damage"])
    assert after > before


def test_bumping_a_merchant_opens_the_shop():
    from rogue.spawn import make_merchant
    from rogue.world import tiles

    engine = make_engine(seed=1)
    px, py = engine.player.x, engine.player.y
    engine.game_map.tiles[px + 1, py] = tiles.FLOOR
    merchant = make_merchant(px + 1, py)
    engine.game_map.entities.append(merchant)

    engine.handle_player_action(BumpAction(engine.player, 1, 0))
    assert engine.shop is merchant
    assert (engine.player.x, engine.player.y) == (px, py)  # bumping spent no move


def test_walking_onto_stairs_auto_descends():
    from rogue.world import tiles

    engine = make_engine(seed=1)
    stairs = [e for e in engine.game_map.entities if e.has("stairs")][0]
    engine.player.x, engine.player.y = stairs.x - 1, stairs.y
    engine.game_map.tiles[stairs.x - 1, stairs.y] = tiles.FLOOR
    engine.game_map.tiles[stairs.x, stairs.y] = tiles.FLOOR
    depth_before = engine.depth

    engine.handle_player_action(BumpAction(engine.player, 1, 0))
    assert engine.depth == depth_before + 1


def test_noise_cave_has_decorations_and_a_merchant():
    cfg = replace(config.DEFAULT, noise_map_size=48, merchant_chance=1.0)
    game_map, _ = generate_noise_dungeon(cfg, Rng(4))
    kinds = {e.get("decoration").kind for e in game_map.entities if e.get("decoration")}
    assert {"trash", "water", "box"} <= kinds
    assert any(e.has("merchant") for e in game_map.entities)
    # Decorations never block movement.
    assert all(not e.blocks_movement for e in game_map.entities if e.get("decoration"))


def _flood_region(game_map, sx, sy):
    """All cells 8-connected to (sx, sy) over walkable tiles."""
    walkable = game_map.tiles["walkable"]
    w, h = game_map.width, game_map.height
    seen = {(sx, sy)}
    stack = [(sx, sy)]
    while stack:
        x, y = stack.pop()
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and walkable[nx, ny]:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
    return seen


def _reachable_via_portals(game_map, start):
    """Cells reachable from ``start`` by walking, following portals one-way."""
    walkable = game_map.tiles["walkable"]
    w, h = game_map.width, game_map.height
    portals = {
        (e.x, e.y): e.get("teleport").dest
        for e in game_map.entities
        if e.get("teleport") is not None
    }
    seen = {start}
    stack = [start]
    while stack:
        x, y = stack.pop()
        dest = portals.get((x, y))
        if dest is not None and dest not in seen:
            seen.add(dest)
            stack.append(dest)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen and walkable[nx, ny]:
                    seen.add((nx, ny))
                    stack.append((nx, ny))
    return seen
