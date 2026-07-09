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
from ..spawn import (
    make_decoration,
    make_merchant,
    make_monster,
    make_player,
    make_stairs,
    make_teleport,
)
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


def generate_dungeon(
    cfg: config.Config, rng: Rng, depth: int = 1, player: "Entity" | None = None
) -> Tuple[GameMap, "Entity"]:
    """Build a fresh dungeon and return ``(game_map, player)``.

    Signature matches the noise generator so either can be handed to the engine.
    When ``player`` is given (descending) it is reused, keeping HP and inventory.
    """
    game_map = GameMap(cfg.map_width, cfg.map_height)
    rooms: List[RectRoom] = []

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
            # First room: place (or drop in) the player.
            cx, cy = new_room.center
            if player is None:
                player = make_player(cx, cy, cfg)
            else:
                player.x, player.y = cx, cy
        else:
            # Carve a corridor back to the previous room.
            for cx, cy in _tunnel_between(rooms[-1].center, new_room.center, rng):
                game_map.tiles[cx, cy] = tiles.FLOOR
            _populate_room(game_map, new_room, cfg, rng, depth)

        rooms.append(new_room)

    assert player is not None, "generation must place at least one room"
    game_map.entities.append(player)
    game_map.entities.append(make_stairs(*rooms[-1].center))
    return game_map, player


def _populate_room(
    game_map: GameMap, room: RectRoom, cfg: config.Config, rng: Rng, depth: int
) -> None:
    count = rng.randint(0, cfg.max_monsters_per_room)
    for _ in range(count):
        mx = rng.randint(room.x1 + 1, room.x2 - 1)
        my = rng.randint(room.y1 + 1, room.y2 - 1)
        if any(True for _ in game_map.entities_at(mx, my)):
            continue
        game_map.entities.append(make_monster(rng, mx, my, depth))


# ---------------------------------------------------------------------------
# Noise-cave generator (the default)
#
# The Noise Lab script produces a greyscale field; a cell is a wall wherever the
# brightness is above ``wall_threshold`` and floor otherwise.  This leaves the
# floor split into disconnected regions.  The big-enough regions are strung into
# a random *chain*: every region but the last holds a one-way portal to the next,
# and the final region holds the down-stairs (and no portal).  Within each region
# the arrival point and the exit (portal or stairs) sit far apart, so the player
# has to cross the region to move on.  Small pockets are left as rock.
# ---------------------------------------------------------------------------


def generate_noise_dungeon(
    cfg: config.Config, rng: Rng, depth: int = 1, player: "Entity" | None = None
) -> Tuple[GameMap, "Entity"]:
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

    # Regions big enough to hold a portal form the traversable chain, in random
    # order; anything smaller is left as unreachable rock.
    chain = [r for r in _floor_regions(game_map) if len(r) >= cfg.min_teleport_region]
    if not chain:  # pathological: carve a single safe tile so the game runs
        cx, cy = n // 2, n // 2
        game_map.tiles[cx, cy] = tiles.FLOOR
        chain = [[(cx, cy)]]
    rng.shuffle(chain)

    # Each region gets a far-apart (entry, exit) pair: the player arrives at
    # ``entry`` and leaves from ``exit`` (a portal, or the stairs in the last).
    entries_exits = [_far_pair(region) for region in chain]
    occupied = set()

    # The player starts at the first region's entry.
    px, py = entries_exits[0][0]
    if player is None:
        player = make_player(px, py, cfg)
    else:
        player.x, player.y = px, py
    game_map.entities.append(player)
    occupied.add((px, py))

    # Portals link region i -> the entry of region i+1 (one-way).  The last
    # region gets the down-stairs instead, placed far from where you arrive.
    last = len(chain) - 1
    for i in range(len(chain)):
        entry, exit_cell = entries_exits[i]
        if i < last:
            portal = make_teleport(*exit_cell)
            portal.get("teleport").dest = entries_exits[i + 1][0]
            game_map.entities.append(portal)
        else:
            game_map.entities.append(make_stairs(*exit_cell))
        occupied.add(entry)
        occupied.add(exit_cell)

    _place_merchant(game_map, chain, cfg, rng, occupied)
    _populate_cave(game_map, chain, cfg, rng, occupied, depth)
    _decorate_cave(game_map, chain, cfg, rng, occupied)
    return game_map, player


def _far_pair(region: List[Tuple[int, int]]) -> Tuple[Tuple[int, int], Tuple[int, int]]:
    """Two far-apart cells of a region (approximate diameter endpoints)."""

    def dist2(a, b):
        return (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2

    a = region[0]
    b = max(region, key=lambda c: dist2(a, c))
    c = max(region, key=lambda c: dist2(b, c))
    return b, c  # (entry, exit)


def _floor_regions(game_map: GameMap) -> List[List[Tuple[int, int]]]:
    """Return every 8-connected walkable region as a list of its cells."""
    width, height = game_map.width, game_map.height
    walkable = game_map.tiles["walkable"]
    seen = [[False] * height for _ in range(width)]
    regions: List[List[Tuple[int, int]]] = []

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
            regions.append(region)
    return regions


def _populate_cave(game_map, regions, cfg, rng, occupied, depth: int) -> None:
    spots = [cell for region in regions for cell in region if cell not in occupied]
    if not spots:
        return
    # Deeper levels are more crowded; the cap rises with depth too.
    base = len(spots) // cfg.monster_spacing
    count = min(base + (depth - 1) * base // 2, cfg.max_monsters * depth, len(spots))
    for mx, my in rng.sample(spots, count) if count > 0 else []:
        game_map.entities.append(make_monster(rng, mx, my, depth))


def _place_merchant(game_map, chain, cfg, rng, occupied) -> None:
    """Maybe drop a merchant into a random region, ringed by crates."""
    if not rng.chance(cfg.merchant_chance):
        return
    region = rng.choice(chain)
    free = [c for c in region if c not in occupied]
    if not free:
        return
    mx, my = rng.choice(free)
    game_map.entities.append(make_merchant(mx, my))
    occupied.add((mx, my))

    # Lots of crates around the merchant's stall.
    nearby = [
        c
        for c in region
        if c not in occupied and abs(c[0] - mx) <= 3 and abs(c[1] - my) <= 3
    ]
    rng.shuffle(nearby)
    for cell in nearby[: cfg.merchant_box_count]:
        game_map.entities.append(make_decoration("box", *cell))
        occupied.add(cell)


def _decorate_cave(game_map, chain, cfg, rng, occupied) -> None:
    """Scatter cosmetic trash, water ponds and crates over the floor."""
    decorated: set = set()

    for _ in range(cfg.water_clusters):
        floor = [c for region in chain for c in region if c not in occupied and c not in decorated]
        if not floor:
            break
        _grow_blob(game_map, rng.choice(floor), cfg.water_cluster_size, occupied, decorated, rng, "water")

    floor_count = sum(len(region) for region in chain)
    _scatter(game_map, chain, int(floor_count * cfg.trash_fraction), occupied, decorated, rng, "trash")
    _scatter(game_map, chain, cfg.box_count, occupied, decorated, rng, "box")


def _grow_blob(game_map, seed, size, occupied, decorated, rng, kind) -> None:
    """Flood a rough blob of decorations of ``kind`` outward from ``seed``."""
    walkable = game_map.tiles["walkable"]
    w, h = game_map.width, game_map.height
    frontier = [seed]
    placed = 0
    while frontier and placed < size:
        x, y = frontier.pop(rng.randint(0, len(frontier) - 1))
        if (x, y) in occupied or (x, y) in decorated or not walkable[x, y]:
            continue
        game_map.entities.append(make_decoration(kind, x, y))
        decorated.add((x, y))
        placed += 1
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = x + dx, y + dy
            if 0 <= nx < w and 0 <= ny < h and walkable[nx, ny] and (nx, ny) not in occupied and (nx, ny) not in decorated:
                frontier.append((nx, ny))


def _scatter(game_map, chain, count, occupied, decorated, rng, kind) -> None:
    candidates = [c for region in chain for c in region if c not in occupied and c not in decorated]
    if count <= 0 or not candidates:
        return
    for cell in rng.sample(candidates, min(count, len(candidates))):
        game_map.entities.append(make_decoration(kind, *cell))
        decorated.add(cell)
