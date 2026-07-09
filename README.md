# procgen-rogue

A tiny ASCII roguelike written in Python with [tcod]. It is deliberately small
but structured as a **foundation to build on**: clean layers, component-based
entities, all tunables in one place, and game logic that runs without a display
so it can be tested head-lessly.

```
     #####.######
     #..........#
     #..........#
     #.....g....#      @  you            g  a monster
     #.......@..#      #  wall           %  remains
     ############      .  floor          /  loot (a stick)
```

## What's in the box (the brief, implemented)

- **ASCII only**, rendered in a Dwarf-Fortress-style grid (tcod/SDL window).
- **One player** (`@`) with a **camera that follows** and scrolls the map.
- **Procedural dungeon**: simple square rooms joined by right-angle corridors.
- **Monsters** (`g`) that just stand and **trade blows when you get adjacent**.
- **Bump to attack**: walk into a monster to hit it; it hits back on its turn.
- **Rewards + loot**: killing a monster grants gold and drops a **stick** into
  your inventory. Sticks come in **tiers 1–5** (rarer at higher tiers).
- **Fog of war** with a **radius of 10** tiles; explored areas are remembered
  and drawn dimmed.

## Run it

```bash
pip install -r requirements.txt
python main.py            # random dungeon
python main.py --seed 42  # reproducible dungeon
```

> The game opens a windowed ASCII grid (tcod's SDL backend — the same approach
> Dwarf Fortress uses), so it needs a graphical session. Cross-platform on
> Windows / macOS / Linux. The rendering layer is isolated (`rogue/ui/`), so a
> pure-terminal backend could be added later without touching game logic.

### Controls

| Keys | Action |
|------|--------|
| Arrow keys · `hjkl` · numpad | Move / bump-attack (8 directions) |
| `y` `u` `b` `n` | Diagonal moves |
| `.` · numpad `5` | Wait a turn |
| `i` | Toggle inventory |
| `Esc` · `q` | Quit |

## Run the tests

All game logic is display-independent, so the suite runs anywhere:

```bash
pip install pytest
pytest -q
```

## Architecture

The code is split so that **new ideas slot in without rewrites**. Nothing in the
engine or world layers imports the renderer.

```
main.py                 entry point (arg parsing) -> rogue.app.run
rogue/
├── config.py           every tunable, in one dataclass
├── rng.py              seedable, centralised randomness
├── geometry.py         directions + distance helpers
├── entity.py           Entity = position + glyph + a bag of components
├── components.py       Fighter / MonsterAI / Inventory / Loot / Progress
├── items.py            Item + loot rolling (sticks, tiers 1–5)
├── actions.py          the verbs: Move / Melee / Bump / Wait
├── input.py            key events -> actions / UI commands
├── engine.py           owns the world, runs turns, FOV, combat outcomes
├── app.py              tcod window + main loop (the display boundary)
├── world/
│   ├── tiles.py        tile records (walkable/transparent + lit/dark glyphs)
│   ├── game_map.py     terrain grid, visibility, entities, FOV
│   └── procgen.py      rooms + corridors generator
└── ui/
    ├── camera.py       viewport that follows the player and clamps to edges
    └── renderer.py     draws map, fog, entities, HUD, log, overlays
```

**Turn model:** turn-based. The player performs one `Action`; if it consumes a
turn, every monster takes its turn, then FOV is recomputed.

## Extending it (by design)

Some concrete "next ideas" and where they go:

- **New monster type** — add a factory in `spawn.py`; give it a different
  `Fighter` stats or a new AI component. A chasing monster is a new `take_turn`
  in `components.py`; the turn loop is untouched.
- **New loot / equipment** — add an `ItemKind` in `items.py` and (optionally) a
  roll table. Inventory, combat and rendering already treat items generically.
- **New player verb** (throw, quaff, open door) — a new `Action` subclass plus a
  key binding in `input.py`.
- **New terrain** (water, lava, doors) — one `new_tile(...)` call in `tiles.py`;
  FOV and rendering pick it up automatically.
- **Different map styles** (caves, BSP, vaults) — a sibling module to
  `procgen.py` returning a `GameMap`; nothing downstream cares how it was built.
- **Descending / multiple levels, saving, XP levels, ranged combat** — the
  engine already isolates state, so these are additive.

[tcod]: https://python-tcod.readthedocs.io/
