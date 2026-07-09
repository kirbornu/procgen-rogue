"""procgen-rogue: a small, extensible ASCII roguelike foundation.

The package is split into clear layers so new ideas can be bolted on without
rewrites:

    config      - all tunables in one place
    rng         - seedable, centralised randomness
    geometry    - directions / small vector helpers
    entity      - component-based entities (the extension point for behaviour)
    components  - Fighter / MonsterAI / Inventory / ... (add more freely)
    items       - item definitions + loot rolling (sticks tier 1-5 for now)
    actions     - the verbs of the game (Move, Melee, Wait, ...)
    input       - maps raw key events onto actions
    engine      - owns the world, runs turns, recomputes FOV
    world/      - tiles, the game map, and procedural generation
    ui/         - camera + renderer (the only part that talks to a display)

The engine and world layers never import the renderer, so all game logic can
be exercised head-less (see tests/).
"""

__version__ = "0.1.0"
