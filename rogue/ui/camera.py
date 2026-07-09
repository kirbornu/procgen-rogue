"""A viewport that follows the player and clamps to the map edges."""
from __future__ import annotations

from typing import Tuple


class Camera:
    def __init__(self, view_width: int, view_height: int) -> None:
        self.view_width = view_width
        self.view_height = view_height
        self.x = 0
        self.y = 0

    def center_on(self, target_x: int, target_y: int, map_width: int, map_height: int) -> None:
        """Centre the view on a target, clamped so it never shows past the map."""
        self.x = target_x - self.view_width // 2
        self.y = target_y - self.view_height // 2
        # Clamp so the viewport stays within the map bounds when possible.
        self.x = max(0, min(self.x, max(0, map_width - self.view_width)))
        self.y = max(0, min(self.y, max(0, map_height - self.view_height)))

    def to_screen(self, world_x: int, world_y: int) -> Tuple[int, int]:
        return world_x - self.x, world_y - self.y

    def in_view(self, screen_x: int, screen_y: int) -> bool:
        return 0 <= screen_x < self.view_width and 0 <= screen_y < self.view_height
