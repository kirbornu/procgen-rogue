"""Small spatial helpers shared across the codebase."""
from __future__ import annotations

from enum import Enum


def chebyshev(ax: int, ay: int, bx: int, by: int) -> int:
    """King-move distance - the natural metric for 8-directional melee range."""
    return max(abs(ax - bx), abs(ay - by))


class Direction(Enum):
    """The eight movement directions plus 'stay put'."""

    NW = (-1, -1)
    N = (0, -1)
    NE = (1, -1)
    W = (-1, 0)
    HERE = (0, 0)
    E = (1, 0)
    SW = (-1, 1)
    S = (0, 1)
    SE = (1, 1)

    @property
    def dx(self) -> int:
        return self.value[0]

    @property
    def dy(self) -> int:
        return self.value[1]
