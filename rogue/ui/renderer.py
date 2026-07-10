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
from ..bonuses import UPGRADE_STEP, BonusType, format_bonus
from ..engine import Engine
from ..entity import Entity
from ..world import tiles
from .camera import Camera

from importlib import import_module
lang = import_module(f"rogue.lang.{config.Config.language}")
lbl = lang.UI_LABELS


class Renderer:
    def __init__(self, cfg: config.Config) -> None:
        self.cfg = cfg
        self.camera = Camera(cfg.screen_width, cfg.map_view_height)
        self.show_inventory = False
        self.inv_cursor = 0
        self.shop_cursor = 0

    # --- shop modal state -------------------------------------------------
    def move_shop_cursor(self, delta: int, engine: Engine) -> None:
        rows = engine.shop_rows()
        if not rows:
            self.shop_cursor = 0
            return
        self.shop_cursor = (self.shop_cursor + delta) % len(rows)

    def selected_shop_row(self, engine: Engine):
        rows = engine.shop_rows()
        if 0 <= self.shop_cursor < len(rows):
            return rows[self.shop_cursor]
        return None

    # --- inventory modal state --------------------------------------------
    def open_inventory(self, engine: Engine) -> None:
        self.show_inventory = True
        self.inv_cursor = 0

    def _inventory_items(self, engine: Engine):
        inventory = engine.player.inventory
        return inventory.items if inventory is not None else []

    def move_inventory_cursor(self, delta: int, engine: Engine) -> None:
        count = len(self._inventory_items(engine))
        if count == 0:
            self.inv_cursor = 0
            return
        self.inv_cursor = (self.inv_cursor + delta) % count

    def selected_item(self, engine: Engine):
        items = self._inventory_items(engine)
        if 0 <= self.inv_cursor < len(items):
            return items[self.inv_cursor]
        return None

    def render(self, console: tcod.console.Console, engine: Engine) -> None:
        console.clear()
        self._render_map(console, engine)
        self._render_entities(console, engine)
        self._render_status(console, engine)
        self._render_log(console, engine)
        self._render_controls(console)
        if engine.shop is not None:
            self._render_shop(console, engine)
        elif self.show_inventory:
            self._render_inventory(console, engine)
        if engine.game_over:
            self._render_center_banner(console, lbl['die'])

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

        equipment = engine.player.get("equipment")
        using = f"{len(equipment.equipped)}/{equipment.capacity}" if equipment else "0/0"
        stats = (
            f" {lbl['depth']} {engine.depth}   {lbl['gold']} {progress.gold}   {lbl['kills']} {progress.kills}"
            f"   {lbl['items']} {len(inventory.items)}   {lbl['using']} {using}"
        )
        console.print(1 + bar_width + 1, row, stats, fg=config.TEXT_COLOR)
        if engine.scouting:
            console.print(self.cfg.screen_width - 11, row, lbl['scouting'], fg=config.TITLE_COLOR)

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
        console.print(x + 1, y, f"{lbl['hp']} {value}/{maximum}", fg=config.WHITE)

    def _render_log(self, console: tcod.console.Console, engine: Engine) -> None:
        first_row = self.cfg.log_row
        rows = self.cfg.controls_row - first_row  # leave the last row for hints
        for i, message in enumerate(engine.log.last(rows)):
            console.print(1, first_row + i, message.full_text[: self.cfg.screen_width - 2], fg=message.color)

    #: Always-on key hints, drawn along the bottom row.  Keeping the list here
    #: (paired key -> label) makes it the single place to update when bindings
    #: in ``input.py`` change.
    CONTROL_HINTS = lang.CONTROL_HINTS

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
        items = self._inventory_items(engine)
        equipment = engine.player.get("equipment")
        width, height = 64, 30
        left_w = 40  # width of the item column; the rest is the character sheet
        x = (self.cfg.screen_width - width) // 2
        y = (self.cfg.screen_height - height) // 2
        console.draw_frame(x, y, width, height, fg=config.TITLE_COLOR, bg=config.BLACK)
        console.print_box(
            x, y, width, 1, lbl['inv'], fg=config.TITLE_COLOR, alignment=tcod.constants.CENTER
        )
        for yy in range(y + 1, y + height - 1):  # column divider
            console.print(x + left_w, yy, "│", fg=config.TEXT_DIM)

        # Left column: item list | separator | selected-item detail.
        list_top = y + 2
        footer_row = y + height - 2
        detail_lines = len(BonusType) + 1
        detail_top = footer_row - detail_lines
        separator_row = detail_top - 1
        list_rows = separator_row - list_top
        text_w = left_w - 3

        if not items:
            console.print(x + 2, list_top, lbl['empty'], fg=config.TEXT_DIM)
        else:
            self.inv_cursor = max(0, min(self.inv_cursor, len(items) - 1))
            top = max(0, min(self.inv_cursor - list_rows + 1, len(items) - list_rows))
            for row, index in enumerate(range(top, min(len(items), top + list_rows))):
                item = items[index]
                selected = index == self.inv_cursor
                equipped = equipment is not None and equipment.is_equipped(item)
                text = f"{'>' if selected else ' '}{'*' if equipped else ' '} {item.display_name}"
                fg = config.WHITE if selected else item.color
                bg = config.WALL_DARK_BG if selected else config.BLACK
                console.print(x + 2, list_top + row, text[:text_w], fg=fg, bg=bg)

        console.draw_rect(x + 1, separator_row, left_w - 1, 1, ch=ord("-"), fg=config.TEXT_DIM)
        selected_item = self.selected_item(engine)
        if selected_item is not None:
            equipped = equipment is not None and equipment.is_equipped(selected_item)
            state = "equipped" if equipped else "in pack"
            console.print(
                x + 2, detail_top, f"{selected_item.name} ({state})"[:text_w], fg=selected_item.color
            )
            for i, line in enumerate(selected_item.bonus_lines()):
                console.print(x + 4, detail_top + 1 + i, line[:text_w], fg=config.TEXT_COLOR)

        # Right column: the character sheet (effective stats).
        console.print(x + left_w + 2, y + 2, lbl['character'], fg=config.TITLE_COLOR)
        for i, (label, value) in enumerate(engine.character_sheet()):
            console.print(x + left_w + 2, y + 4 + i, f"{label:<10}{value}", fg=config.TEXT_COLOR)

        console.print(
            x + 2, footer_row, lbl['inv_hints'], fg=config.TEXT_DIM
        )

    def _render_shop(self, console: tcod.console.Console, engine: Engine) -> None:
        rows = engine.shop_rows()
        self.shop_cursor = max(0, min(self.shop_cursor, max(0, len(rows) - 1)))
        progress = engine.player.get("progress")
        gold = progress.gold if progress else 0

        width, height = 60, 34
        x = (self.cfg.screen_width - width) // 2
        y = (self.cfg.screen_height - height) // 2
        console.draw_frame(x, y, width, height, fg=config.MERCHANT_COLOR, bg=config.BLACK)
        console.print_box(
            x, y, width, 1, f" {lbl['merch_title']} {gold} ", fg=config.MERCHANT_COLOR,
            alignment=tcod.constants.CENTER,
        )

        num_upgrades = len(BonusType)
        footer_row = y + height - 2

        # Upgrades section (always fully visible).
        console.print(x + 2, y + 2, lbl['upgrade_title'], fg=config.TITLE_COLOR)
        for i, (kind, btype) in enumerate(rows[:num_upgrades]):
            cost = engine.upgrade_cost(btype)
            owned = engine.player.get("upgrades").count(btype)
            label = f"{format_bonus(btype, UPGRADE_STEP[btype]):<16} {cost:>6}{lbl['upgrade_row']}{owned}"
            self._shop_line(console, x, y + 3 + i, width, label, i == self.shop_cursor, gold >= cost)

        sep = y + 3 + num_upgrades
        console.draw_rect(x + 1, sep, width - 2, 1, ch=ord("-"), fg=config.TEXT_DIM)
        console.print(x + 2, sep, lbl['sell_title'], fg=config.TITLE_COLOR)

        # Sell section (scrolls if the pack is large).
        sell_top = sep + 1
        sell_rows = footer_row - sell_top
        sell_items = rows[num_upgrades:]
        if not sell_items:
            console.print(x + 2, sell_top, lbl['sell_nothing'], fg=config.TEXT_DIM)
        else:
            sel = self.shop_cursor - num_upgrades  # -1 if cursor is in upgrades
            top = 0
            if sel >= 0:
                top = max(0, min(sel - sell_rows + 1, len(sell_items) - sell_rows))
            for r, index in enumerate(range(top, min(len(sell_items), top + sell_rows))):
                _, item = sell_items[index]
                price = self.cfg.sell_price_per_level * item.level
                label = f"{item.display_name:<28} +{price}g"
                self._shop_line(
                    console, x, sell_top + r, width, label,
                    (num_upgrades + index) == self.shop_cursor, True,
                )

        console.print(
            x + 2, footer_row, lbl['merch_hints'], fg=config.TEXT_DIM
        )

    def _shop_line(self, console, x, row, width, text, selected, affordable) -> None:
        if selected:
            fg, bg = config.WHITE, config.WALL_DARK_BG
        elif not affordable:
            fg, bg = config.TEXT_DIM, config.BLACK
        else:
            fg, bg = config.TEXT_COLOR, config.BLACK
        cursor = ">" if selected else " "
        console.print(x + 2, row, f"{cursor} {text}"[: width - 3], fg=fg, bg=bg)

    def _render_center_banner(self, console: tcod.console.Console, text: str) -> None:
        y = self.cfg.map_view_height // 2
        console.print_box(
            0, y, self.cfg.screen_width, 1, text, fg=config.TITLE_COLOR, alignment=tcod.constants.CENTER
        )
