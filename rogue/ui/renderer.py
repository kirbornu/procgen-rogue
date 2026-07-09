"""Everything that puts glyphs on the console.

The renderer reads engine state and draws it; it never mutates the world.  It is
the one module that assumes a display exists, which keeps the rest of the game
testable head-less.
"""
from __future__ import annotations

import numpy as np
import tcod.console
import tcod.constants

from .. import config
from ..engine import Engine
from ..entity import Entity
from ..world import tiles
from .camera import Camera


class Renderer:
    def __init__(self, cfg: config.Config) -> None:
        self.cfg = cfg
        self.camera = Camera(cfg.screen_width, cfg.map_view_height)
        self.show_inventory = False

    def render(self, console: tcod.console.Console, engine: Engine) -> None:
        console.clear()
        self._render_map(console, engine)
        self._render_entities(console, engine)
        self._render_status(console, engine)
        self._render_log(console, engine)
        self._render_controls(console)
        if self.show_inventory:
            self._render_inventory(console, engine)
        if engine.game_over:
            self._render_center_banner(console, "You have died.  Press ESC to quit.")

    # --- map + fog of war --------------------------------------------------
    def _render_map(self, console: tcod.console.Console, engine: Engine) -> None:
        game_map = engine.game_map
        view_w = min(self.camera.view_width, game_map.width)
        view_h = min(self.camera.view_height, game_map.height)
        self.camera.center_on(
            engine.player.x, engine.player.y, game_map.width, game_map.height
        )

        x0, y0 = self.camera.x, self.camera.y
        x1, y1 = x0 + view_w, y0 + view_h

        tile_slice = game_map.tiles[x0:x1, y0:y1]
        visible_slice = game_map.visible[x0:x1, y0:y1]
        explored_slice = game_map.explored[x0:x1, y0:y1]

        # Lit -> bright, remembered -> dim, never-seen -> shroud.
        console.rgb[0:view_w, 0:view_h] = np.select(
            condlist=[visible_slice, explored_slice],
            choicelist=[tile_slice["light"], tile_slice["dark"]],
            default=tiles.SHROUD,
        )

    def _render_entities(self, console: tcod.console.Console, engine: Engine) -> None:
        game_map = engine.game_map
        # Draw low render-order first so the player ends up on top.
        for entity in sorted(game_map.entities, key=lambda e: e.render_order):
            if not game_map.in_bounds(entity.x, entity.y):
                continue
            if not game_map.visible[entity.x, entity.y]:
                continue  # hidden by the fog of war
            sx, sy = self.camera.to_screen(entity.x, entity.y)
            if self.camera.in_view(sx, sy):
                console.print(sx, sy, entity.char, fg=entity.color)

    # --- HUD ---------------------------------------------------------------
    def _render_status(self, console: tcod.console.Console, engine: Engine) -> None:
        row = self.cfg.status_row
        console.rgb[:, row]["bg"] = config.BLACK
        fighter = engine.player.fighter
        progress = engine.player.get("progress")
        inventory = engine.player.inventory

        bar_width = 20
        self._render_bar(console, 1, row, fighter.hp, fighter.max_hp, bar_width)

        stats = f" Gold {progress.gold}   Kills {progress.kills}   Sticks {len(inventory.items)}"
        console.print(1 + bar_width + 1, row, stats, fg=config.TEXT_COLOR)
        if engine.scouting:
            console.print(self.cfg.screen_width - 11, row, "[Scouting]", fg=config.TITLE_COLOR)

    def _render_bar(
        self,
        console: tcod.console.Console,
        x: int,
        y: int,
        value: int,
        maximum: int,
        width: int,
    ) -> None:
        fill = 0 if maximum <= 0 else int(width * value / maximum)
        console.draw_rect(x, y, width, 1, ch=ord(" "), bg=config.HP_BAR_EMPTY)
        if fill > 0:
            console.draw_rect(x, y, fill, 1, ch=ord(" "), bg=config.HP_BAR_FILLED)
        console.print(x + 1, y, f"HP {value}/{maximum}", fg=config.WHITE)

    def _render_log(self, console: tcod.console.Console, engine: Engine) -> None:
        first_row = self.cfg.log_row
        rows = self.cfg.controls_row - first_row  # leave the last row for hints
        for i, message in enumerate(engine.log.last(rows)):
            console.print(1, first_row + i, message.full_text[: self.cfg.screen_width - 2], fg=message.color)

    #: Always-on key hints, drawn along the bottom row.  Keeping the list here
    #: (paired key -> label) makes it the single place to update when bindings
    #: in ``input.py`` change.
    CONTROL_HINTS = [
        ("move", "arrows/hjkl"),
        (".", "wait"),
        ("r", "heal"),
        ("s", "scout"),
        ("i", "inventory"),
        ("q", "quit"),
    ]

    def _render_controls(self, console: tcod.console.Console) -> None:
        row = self.cfg.controls_row
        # A subtle bar so the hints read as a separate strip.
        console.draw_rect(0, row, self.cfg.screen_width, 1, ch=ord(" "), bg=config.WALL_DARK_BG)
        x = 1
        for key, label in self.CONTROL_HINTS:
            console.print(x, row, key, fg=config.TITLE_COLOR, bg=config.WALL_DARK_BG)
            x += len(key) + 1
            console.print(x, row, label, fg=config.TEXT_DIM, bg=config.WALL_DARK_BG)
            x += len(label) + 2
            if x >= self.cfg.screen_width:
                break

    # --- overlays ----------------------------------------------------------
    def _render_inventory(self, console: tcod.console.Console, engine: Engine) -> None:
        inventory = engine.player.inventory
        width, height = 40, 14
        x = (self.cfg.screen_width - width) // 2
        y = (self.cfg.map_view_height - height) // 2
        console.draw_frame(x, y, width, height, fg=config.TITLE_COLOR, bg=config.BLACK)
        console.print_box(x, y, width, 1, " Inventory ", fg=config.TITLE_COLOR, alignment=tcod.constants.CENTER)

        counts = inventory.tier_counts()
        if not counts:
            console.print(x + 2, y + 2, "(empty)", fg=config.TEXT_DIM)
        else:
            from ..items import STICK_TIER_NAMES

            line = 0
            for tier in sorted(counts):
                label = f"T{tier} {STICK_TIER_NAMES[tier]:<14} x{counts[tier]}"
                console.print(x + 2, y + 2 + line, label, fg=config.ITEM_COLOR)
                line += 1
        console.print(x + 2, y + height - 2, "Press 'i' to close", fg=config.TEXT_DIM)

    def _render_center_banner(self, console: tcod.console.Console, text: str) -> None:
        y = self.cfg.map_view_height // 2
        console.print_box(
            0, y, self.cfg.screen_width, 1, text, fg=config.TITLE_COLOR, alignment=tcod.constants.CENTER
        )
