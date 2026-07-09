"""Procedural dungeon generation: square rooms joined by right-angle corridors.

The algorithm is intentionally the simplest thing that satisfies the brief so it
reads as a template.  Each new room is placed at random, discarded if it overlaps
an existing one, then connected to the previous room by an L-shaped tunnel.  The
generator only knows about tiles and the spawn factory, so swapping in caves,
BSP layouts or vaults later means writing a sibling module - nothing downstream
cares how the map was made.
"""
from __future__ import annotations

from typing import Iterator, List, Tuple, TYPE_CHECKING

from .. import config
from ..rng import Rng
from ..spawn import make_monster, make_player
from . import tiles
from .game_map import GameMap
from .noise import generate as generate_noise

if TYPE_CHECKING:
    from ..entity import Entity


class RectRoom:
    """A rectangular room, addressed by its outer corners (walls included)."""

    def __init__(self, x: int, y: int, width: int, height: int) -> None:
        self.x1 = x
        self.y1 = y
        self.x2 = x + width
        self.y2 = y + height

    @property
    def center(self) -> Tuple[int, int]:
        return (self.x1 + self.x2) // 2, (self.y1 + self.y2) // 2

    @property
    def inner(self) -> Tuple[slice, slice]:
        """The carve-able interior, leaving a one-tile wall border."""
        return slice(self.x1 + 1, self.x2), slice(self.y1 + 1, self.y2)

    def intersects(self, other: "RectRoom") -> bool:
        return (
            self.x1 <= other.x2
            and self.x2 >= other.x1
            and self.y1 <= other.y2
            and self.y2 >= other.y1
        )


def _tunnel_between(
    start: Tuple[int, int], end: Tuple[int, int], rng: Rng
) -> Iterator[Tuple[int, int]]:
    """Yield the cells of an L-shaped corridor between two points."""
    x1, y1 = start
    x2, y2 = end
    if rng.chance(0.5):
        corner_x, corner_y = x2, y1  # horizontal leg first, then vertical
    else:
        corner_x, corner_y = x1, y2  # vertical leg first, then horizontal

    for cell in _line(x1, y1, corner_x, corner_y):
        yield cell
    for cell in _line(corner_x, corner_y, x2, y2):
        yield cell


def _line(x1: int, y1: int, x2: int, y2: int) -> Iterator[Tuple[int, int]]:
    """Cells along an axis-aligned segment (inclusive)."""
    if x1 == x2:
        step = 1 if y2 >= y1 else -1
        for y in range(y1, y2 + step, step):
            yield x1, y
    else:
        step = 1 if x2 >= x1 else -1
        for x in range(x1, x2 + step, step):
            yield x, y1


def generate_dungeon(cfg: config.Config, rng: Rng) -> Tuple[GameMap, "Entity"]:
    """Build a fresh dungeon and return ``(game_map, player)``."""
    game_map = GameMap(cfg.map_width, cfg.map_height)
    rooms: List[RectRoom] = []
    player: "Entity" | None = None

    for _ in range(cfg.max_rooms):
        w = rng.randint(cfg.room_min_size, cfg.room_max_size)
        h = rng.randint(cfg.room_min_size, cfg.room_max_size)
        x = rng.randint(0, cfg.map_width - w - 1)
        y = rng.randint(0, cfg.map_height - h - 1)
        new_room = RectRoom(x, y, w, h)

        if any(new_room.intersects(other) for other in rooms):
            continue

        game_map.tiles[new_room.inner] = tiles.FLOOR

        if not rooms:
            # First room: drop the player in.
            cx, cy = new_room.center
            player = make_player(cx, cy, cfg)
        else:
            # Carve a corridor back to the previous room.
            for cx, cy in _tunnel_between(rooms[-1].center, new_room.center, rng):
                game_map.tiles[cx, cy] = tiles.FLOOR
            _populate_room(game_map, new_room, cfg, rng)

        rooms.append(new_room)

    assert player is not None, "generation must place at least one room"
    game_map.entities.append(player)
    return game_map, player


def _populate_room(
    game_map: GameMap, room: RectRoom, cfg: config.Config, rng: Rng
) -> None:
    count = rng.randint(0, cfg.max_monsters_per_room)
    for _ in range(count):
        mx = rng.randint(room.x1 + 1, room.x2 - 1)
        my = rng.randint(room.y1 + 1, room.y2 - 1)
        if any(True for _ in game_map.entities_at(mx, my)):
            continue
        game_map.entities.append(make_monster(rng, mx, my))


# ---------------------------------------------------------------------------
# Noise-cave generator (the default)
#
# The Noise Lab script produces a greyscale field; a cell is a wall wherever the
# brightness is above ``wall_threshold`` and floor otherwise.  Because the noise
# leaves the floor split into disconnected caverns, the player and every monster
# are placed inside the single largest connected region so the whole playable
# area is reachable (isolated pockets simply read as unexplored rock).
# ---------------------------------------------------------------------------


def generate_noise_dungeon(cfg: config.Config, rng: Rng) -> Tuple[GameMap, "Entity"]:
    """Build a cave from the noise generator and return ``(game_map, player)``."""
    n = cfg.noise_map_size
    noise_seed = rng.randint(1, 2**31 - 1)
    grid = generate_noise(noise_seed, n)  # grid[y][x] brightness in [0, 1]

    game_map = GameMap(n, n)
    threshold = cfg.wall_threshold
    for y in range(n):
        row = grid[y]
        for x in range(n):
            if row[x] <= threshold:  # bright -> wall, dark -> floor
                game_map.tiles[x, y] = tiles.FLOOR

    region = _largest_floor_region(game_map)
    if not region:  # pathological all-wall map: carve a single safe tile
        cx, cy = n // 2, n // 2
        game_map.tiles[cx, cy] = tiles.FLOOR
        region = [(cx, cy)]

    px, py = rng.choice(region)
    player = make_player(px, py, cfg)
    game_map.entities.append(player)
    _populate_cave(game_map, region, cfg, rng, player_pos=(px, py))
    return game_map, player


def _largest_floor_region(game_map: GameMap) -> List[Tuple[int, int]]:
    """Return the cells of the biggest 8-connected walkable region."""
    width, height = game_map.width, game_map.height
    walkable = game_map.tiles["walkable"]
    seen = [[False] * height for _ in range(width)]
    best: List[Tuple[int, int]] = []

    for sx in range(width):
        for sy in range(height):
            if seen[sx][sy] or not walkable[sx, sy]:
                continue
            stack = [(sx, sy)]
            seen[sx][sy] = True
            region: List[Tuple[int, int]] = []
            while stack:
                x, y = stack.pop()
                region.append((x, y))
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = x + dx, y + dy
                        if 0 <= nx < width and 0 <= ny < height and not seen[nx][ny] and walkable[nx, ny]:
                            seen[nx][ny] = True
                            stack.append((nx, ny))
            if len(region) > len(best):
                best = region
    return best


def _populate_cave(
    game_map: GameMap,
    region: List[Tuple[int, int]],
    cfg: config.Config,
    rng: Rng,
    player_pos: Tuple[int, int],
) -> None:
    spots = [cell for cell in region if cell != player_pos]
    if not spots:
        return
    count = min(cfg.max_monsters, len(spots) // cfg.monster_spacing)
    for mx, my in rng.sample(spots, count) if count > 0 else []:
        game_map.entities.append(make_monster(rng, mx, my))
