"""The game map: terrain grid, visibility state and the entities on it."""
from __future__ import annotations

from typing import Iterator, List, Optional, TYPE_CHECKING

import numpy as np
import tcod.constants
import tcod.map

from .. import config
from . import tiles

if TYPE_CHECKING:
    from ..entity import Entity


class GameMap:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        # Terrain starts as solid wall; the generator carves it out.
        self.tiles = np.full((width, height), fill_value=tiles.WALL, order="F")
        # Currently in view this turn.
        self.visible = np.full((width, height), fill_value=False, order="F")
        # Ever seen (drawn dimmed when out of view - the fog of war memory).
        self.explored = np.full((width, height), fill_value=False, order="F")
        self.entities: List["Entity"] = []

    # --- queries -----------------------------------------------------------
    def in_bounds(self, x: int, y: int) -> bool:
        return 0 <= x < self.width and 0 <= y < self.height

    def is_walkable(self, x: int, y: int) -> bool:
        return self.in_bounds(x, y) and bool(self.tiles["walkable"][x, y])

    def blocking_entity_at(self, x: int, y: int) -> Optional["Entity"]:
        for entity in self.entities:
            if entity.blocks_movement and entity.x == x and entity.y == y:
                return entity
        return None

    def entities_at(self, x: int, y: int) -> Iterator["Entity"]:
        for entity in self.entities:
            if entity.x == x and entity.y == y:
                yield entity

    @property
    def actors(self) -> Iterator["Entity"]:
        """Living entities that take turns."""
        for entity in self.entities:
            if entity.is_alive:
                yield entity

    # --- fov ---------------------------------------------------------------
    def compute_fov(self, x: int, y: int, radius: int) -> None:
        """Recompute ``visible`` from (x, y) and fold it into ``explored``."""
        self.visible[:] = tcod.map.compute_fov(
            self.tiles["transparent"],
            (x, y),
            radius=radius,
            algorithm=tcod.constants.FOV_SYMMETRIC_SHADOWCAST,
        )
        self.explored |= self.visible
