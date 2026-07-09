# procgen-rogue

A tiny ASCII roguelike written in Python with [tcod]. It is deliberately small
but structured as a **foundation to build on**: clean layers, component-based
entities, all tunables in one place, and game logic that runs without a display
so it can be tested head-lessly.

```
     #####.######
     #..........#
     #..........#
     #.,.g.~~.O.#      @  you       #  wall     O  portal    T  merchant
     #..[]...@..#      g  monster    .  floor    >  stairs    ,  trash
     #....>..~~..#      %  remains    /  loot     ~  water     []  crate
```

## What's in the box (the brief, implemented)

- **ASCII only**, rendered in a Dwarf-Fortress-style grid (tcod/SDL window).
- **One player** (`@`) with a **camera that follows** and scrolls the map.
- **Procedural caves**: the default map comes from a multi-layer noise field
  (the "Noise Lab" generator) — a cell is a wall wherever the noise brightness
  is above `0.4`, floor otherwise. (A classic rooms-and-corridors generator is
  still bundled and used by the tests.)
- **Portals** (`O`): the noise splits the floor into disconnected regions, so
  the big-enough regions are strung into a random **one-way chain** — each region
  holds a portal that drops you into the *next* region, far from that region's
  own exit, so you have to cross it. The last region in the chain has **no
  portal**; it holds the down-stairs instead.
- **Descending** (`>`): at the end of the portal chain, **walk onto the
  down-stairs** to drop to a freshly generated, deeper level where monsters are
  **stronger and more numerous**. Your HP, gold, inventory and equipment carry
  over.
- **Merchant** (`T`, ringed by crates): bump into them to open a shop where you
  **sell items** (for `100 × level` gold) and **buy permanent stat upgrades** for
  any of the item stats. Each repeat upgrade of the same stat costs more. A
  merchant appears on some levels, not all.
- **Decorations**: cosmetic floor features that block neither movement nor sight
  (for now) — scattered **trash** (`,`), **water** ponds (`~`, in big clusters)
  and **crates** (`[]`).
- **Procedural monsters**: each rolls random HP, attack power, crit and dodge
  chances, and a **speed** (0..1 chance to step toward you each turn, so some
  stand still and some roam). A monster's overall danger sets both its **colour**
  (the redder, the deadlier) and the power of the loot it drops.
- **Attack radius + auto-attack**: any enemy within the player's attack range is
  struck automatically each turn - unless the player spends the turn on an
  *activity*. Moving and waiting are not activities, so you fight while doing them.
- **Activities**: deliberate turns that occupy the player and suppress the
  auto-attack — **heal** (restore HP) and **scout** (widen your field of view
  until you next move).
- **Procedural loot**: killing a monster grants gold and drops a generated
  **item** whose level scales with the monster's danger. Names are built from
  adjective/noun word lists (higher level → more words, e.g. *"Twisted
  Whispering Ravenous Runed Cane"*), and each item carries several **random
  bonuses** (more at higher level): max HP, damage, attack range, view radius,
  crit chance, dodge chance, heal power.
- **Equipment**: the player can **use only two items at once**; their bonuses
  add to the effective stats. Everything else just sits in the inventory. The
  inventory screen also shows your full **character sheet** (all current stats).
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
| Arrow keys · numpad · `Q W E / A D / Z X C` | Move / bump-attack (8 directions) |
| `s` · `.` · numpad `5` | Wait a turn |
| `r` | Heal (activity: restore HP) |
| `f` | Scout (activity: widen view until you move) |
| walk onto `>` | Descend to the next level |
| walk into `T` | Open the merchant's shop |
| `i` | Open / close inventory |
| ↑/↓ · `w`/`x` | (in inventory / shop) move selection |
| `Enter` | (inventory) equip/unequip · (shop) buy/sell |
| `Esc` | Close overlay / quit |

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
├── components.py       Fighter / MonsterAI / Inventory / Equipment / Loot / …
├── bonuses.py          BonusType enum shared by items and stats
├── items.py            procedural item + name/bonus generation
├── spawn.py            entity factories (player, procedural monsters)
├── actions.py          the verbs: Move / Melee / Bump / Wait / Heal / Scout
├── input.py            key events -> actions / UI commands
├── engine.py           owns the world, runs turns, FOV, combat outcomes
├── app.py              tcod window + main loop (the display boundary)
├── world/
│   ├── tiles.py        tile records (walkable/transparent + lit/dark glyphs)
│   ├── game_map.py     terrain grid, visibility, entities, FOV
│   ├── noise.py        Noise Lab field generator (stdlib only)
│   └── procgen.py      generators: noise cave (default) + rooms/corridors
└── ui/
    ├── camera.py       viewport that follows the player and clamps to edges
    └── renderer.py     draws map, fog, entities, HUD, log, overlays
```

**Turn model:** turn-based. The player performs one `Action`; if it consumes a
turn, every monster takes its turn, then FOV is recomputed.

## Extending it (by design)

Some concrete "next ideas" and where they go:

- **New monster type** — add a factory in `spawn.py`; give it different
  `Fighter` stats or a new AI component. Smarter behaviour (fleeing, ranged) is a
  new `take_turn` in `components.py`; the turn loop is untouched.
- **New bonus kind** — add a `BonusType` in `bonuses.py`, a roll in `items.py`,
  and read it where the stat is applied (`Fighter` / `engine`). Generation,
  inventory and the equip UI handle it automatically.
- **New item theme / rarer names** — extend the word lists or name pattern in
  `items.py`; nothing else changes.
- **New player verb** (throw, quaff, open door) — a new `Action` subclass plus a
  key binding in `input.py`. Return `is_activity=True` from its `ActionResult`
  to make it an *activity* (occupies the player, suppresses the auto-attack),
  the same pattern `HealAction` and `ScoutAction` use.
- **New terrain** (water, lava, doors) — one `new_tile(...)` call in `tiles.py`;
  FOV and rendering pick it up automatically.
- **Different map styles** (BSP, vaults, a different noise config) — write a
  `generator(cfg, rng) -> (GameMap, player)` and pass it to `Engine(generator=…)`;
  nothing downstream cares how the map was built.
- **Descending / multiple levels, saving, XP levels, ranged combat** — the
  engine already isolates state, so these are additive.

[tcod]: https://python-tcod.readthedocs.io/
