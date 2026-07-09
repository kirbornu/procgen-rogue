"""Centralised randomness.

All procedural systems draw from a single seedable :class:`Rng` so a whole run
can be reproduced from one seed - invaluable for debugging generation and, later,
for daily-challenge / shared-seed features.
"""
from __future__ import annotations

import random
from typing import Sequence, TypeVar

T = TypeVar("T")


class Rng:
    def __init__(self, seed: int | None = None) -> None:
        self.seed = seed
        self._random = random.Random(seed)

    def randint(self, low: int, high: int) -> int:
        """Inclusive on both ends, matching the classic roguelike convention."""
        return self._random.randint(low, high)

    def chance(self, probability: float) -> bool:
        return self._random.random() < probability

    def random(self) -> float:
        return self._random.random()

    def choice(self, seq: Sequence[T]) -> T:
        return self._random.choice(seq)

    def sample(self, seq: Sequence[T], k: int) -> list[T]:
        """Return ``k`` distinct elements from ``seq`` (order randomised)."""
        return self._random.sample(list(seq), k)

    def shuffle(self, seq: list) -> None:
        """Shuffle a list in place."""
        self._random.shuffle(seq)

    def weighted_index(self, weights: Sequence[int]) -> int:
        """Return an index into ``weights`` chosen proportionally to weight."""
        total = sum(weights)
        roll = self._random.randint(1, total)
        upto = 0
        for index, weight in enumerate(weights):
            upto += weight
            if roll <= upto:
                return index
        return len(weights) - 1  # pragma: no cover - only if weights are empty/0
