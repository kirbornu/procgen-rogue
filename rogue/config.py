"""Central configuration.

Every tunable number lives here so balancing and layout changes never require
hunting through logic code.  Grouped with :class:`dataclasses` so future work
can load overrides from a file or a menu and pass a modified ``Config`` around
instead of reaching for globals.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# --- Colours (RGB) ---------------------------------------------------------
WHITE = (0xFF, 0xFF, 0xFF)
BLACK = (0x00, 0x00, 0x00)
GREY = (0x80, 0x80, 0x80)
DARK_GREY = (0x40, 0x40, 0x40)

FLOOR_LIGHT_BG = (0x30, 0x30, 0x28)
FLOOR_DARK_BG = (0x10, 0x10, 0x0E)
WALL_LIGHT_BG = (0x60, 0x55, 0x45)
WALL_DARK_BG = (0x20, 0x1E, 0x18)

PLAYER_COLOR = (0xFF, 0xFF, 0xFF)
MONSTER_COLOR = (0xD0, 0x50, 0x50)
CORPSE_COLOR = (0x9E, 0x2A, 0x2A)
ITEM_COLOR = (0xC8, 0xA8, 0x50)
TELEPORT_COLOR = (0x50, 0xE0, 0xE0)
STAIRS_COLOR = (0xF0, 0xE0, 0x50)

HP_BAR_FILLED = (0x30, 0x80, 0x30)
HP_BAR_EMPTY = (0x60, 0x18, 0x18)
TEXT_COLOR = (0xC0, 0xC0, 0xC0)
TEXT_DIM = (0x70, 0x70, 0x70)
TITLE_COLOR = (0xFF, 0xE0, 0x80)


@dataclass(frozen=True)
class Config:
    """Immutable bag of tunables handed to the systems that need them."""

    # Console (the whole window, in character cells).
    screen_width: int = 80
    screen_height: int = 50

    # Layout: the map viewport sits on top, the HUD/log fills the rest.
    map_view_height: int = 43
    log_height: int = 6  # rows reserved for the message log

    # The actual dungeon is larger than the viewport so the camera scrolls.
    map_width: int = 100
    map_height: int = 60

    # Field of view (the "fog of war radius" from the brief).
    fov_radius: int = 10

    # Dungeon generation (rooms-and-corridors generator).
    room_max_size: int = 12
    room_min_size: int = 6
    max_rooms: int = 32
    max_monsters_per_room: int = 2

    # Noise-cave generator (the default). The map is a square of this side; a
    # cell is a wall wherever the noise brightness exceeds ``wall_threshold``.
    noise_map_size: int = 88
    wall_threshold: float = 0.4
    max_monsters: int = 40  # cap for a whole cave (grows with depth)
    monster_spacing: int = 45  # ~1 monster per this many floor tiles
    min_teleport_region: int = 2  # smallest region that still gets a teleport

    # Combat / progression.
    player_hp: int = 30
    player_power: int = 5
    player_defense: int = 2
    player_attack_range: int = 1  # auto-attack reach, in tiles (Chebyshev)
    inventory_capacity: int = 64
    equipment_slots: int = 2  # how many items the player can use at once

    # Activities (deliberate turns that suppress the auto-attack).
    heal_amount: int = 1  # HP restored per "heal" activity
    scout_fov_bonus: int = 6  # extra FOV radius while scouting, until you move

    # Loot: sticks come in tiers 1..5; lower tiers are more common.
    loot_tier_weights: tuple[int, ...] = (40, 26, 18, 11, 5)
    reward_gold_per_tier: int = 10

    @property
    def status_row(self) -> int:
        """Row index of the single-line status bar (HP / gold / kills)."""
        return self.map_view_height

    @property
    def log_row(self) -> int:
        """First row of the scrolling message log."""
        return self.map_view_height + 1

    @property
    def controls_row(self) -> int:
        """Bottom row reserved for the always-on key-hint bar."""
        return self.screen_height - 1


DEFAULT = Config()
