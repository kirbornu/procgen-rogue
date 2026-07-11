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

    #: Width of the HP bar in the status line.
    BAR_WIDTH = 20

    def render(self, console: tcod.console.Console, engine: Engine) -> None:
        console.clear()
        # The whole HUD is laid out from the console's *current* size, so the
        # game scales with the window and the status / hint bars grow taller
        # when their (localised) text is too long for one row.
        layout = self._compute_layout(console, engine)
        self.camera.view_width = console.width
        self.camera.view_height = layout["map_h"]

        self._render_map(console, engine)
        self._render_entities(console, engine)
        if engine.tutorial:
            self._render_tutorial_help(console, engine)
        self._render_status(console, engine, layout)
        self._render_log(console, engine, layout)
        self._render_controls(console, layout)
        if engine.shop is not None:
            self._render_shop(console, engine)
        elif self.show_inventory:
            self._render_inventory(console, engine)
        if engine.game_over:
            self._render_center_banner(console, lbl['die'])

    # --- responsive HUD layout --------------------------------------------
    def _compute_layout(self, console: tcod.console.Console, engine: Engine) -> dict:
        w, h = console.width, console.height
        control_lines = self._wrap_controls(w)
        status_lines = self._status_lines(engine, w)
        controls_rows = max(1, len(control_lines))
        status_rows = max(1, len(status_lines))
        log_rows = max(1, self.cfg.log_height)
        map_h = max(1, h - status_rows - log_rows - controls_rows)
        status_top = map_h
        log_top = status_top + status_rows
        controls_top = h - controls_rows
        return {
            "w": w,
            "h": h,
            "map_h": map_h,
            "status_top": status_top,
            "status_rows": status_rows,
            "status_lines": status_lines,
            "log_top": log_top,
            "log_rows": max(0, controls_top - log_top),
            "controls_top": controls_top,
            "control_lines": control_lines,
        }

    def _wrap_controls(self, width: int) -> list:
        """Pack the key hints into as many rows as the width needs."""
        budget = max(1, width - 2)
        rows, row, x = [], [], 0
        for key, label in self.CONTROL_HINTS:
            seg = len(key) + 1 + len(label)
            if row and x + seg > budget:
                rows.append(row)
                row, x = [], 0
            row.append((key, label))
            x += seg + 2
        if row:
            rows.append(row)
        return rows or [[]]

    def _status_lines(self, engine: Engine, width: int) -> list:
        """The status groups packed into as many rows as needed."""
        player = engine.player
        progress = player.get("progress")
        equipment = player.get("equipment")
        using = f"{len(equipment.equipped)}/{equipment.capacity}" if equipment else "0/0"
        groups = [
            f"{lbl['depth']} {engine.depth}",
            f"{lbl['gold']} {progress.gold}",
            f"{lbl['kills']} {progress.kills}",
            f"{lbl['items']} {len(player.inventory.items)}",
            f"{lbl['using']} {using}",
        ]
        if engine.scouting:
            groups.append(lbl['scouting'])
        first_w = max(1, width - (self.BAR_WIDTH + 2) - 1)  # row 0 shares the HP bar
        rest_w = max(1, width - 2)
        return self._pack_groups(groups, first_w, rest_w)

    @staticmethod
    def _pack_groups(groups: list, first_w: int, rest_w: int) -> list:
        sep = "   "
        lines, cur = [], ""
        for group in groups:
            width = first_w if not lines else rest_w
            candidate = group if not cur else f"{cur}{sep}{group}"
            if cur and len(candidate) > width:
                lines.append(cur)
                cur = group
            else:
                cur = candidate
        if cur:
            lines.append(cur)
        return lines or [""]

    # --- main menu ----------------------------------------------------------
    #: Menu rows, in order. The app maps the cursor index onto these actions.
    MENU_ITEMS = ("play", "tutorial", "language", "exit")

    def menu_labels(self, has_save: bool) -> list:
        menu = lang.MENU
        return [
            menu['continue'] if has_save else menu['play'],
            menu['tutorial'],
            f"{menu['language']}: {menu['lang_name']}",
            menu['exit'],
        ]

    def render_menu(self, console: tcod.console.Console, cursor: int, has_save: bool) -> None:
        """Draw the main menu; ``has_save`` swaps Play for Continue."""
        console.clear()
        menu = lang.MENU
        w, h = console.width, console.height
        center = tcod.constants.CENTER
        title_y = h // 3
        console.print_box(0, title_y, w, 1, menu['title'], fg=config.TITLE_COLOR, alignment=center)
        for i, label in enumerate(self.menu_labels(has_save)):
            selected = i == cursor
            text = f"> {label} <" if selected else label
            fg = config.WHITE if selected else config.TEXT_COLOR
            console.print_box(0, title_y + 3 + i * 2, w, 1, text, fg=fg, alignment=center)
        console.print_box(0, h - 2, w, 1, menu['hints'], fg=config.TEXT_DIM, alignment=center)

    def render_generating(self, console: tcod.console.Console) -> None:
        """A one-frame banner while the (slow) cave generation runs."""
        console.clear()
        console.print_box(
            0, console.height // 2, console.width, 1,
            lang.MENU['generating'], fg=config.TITLE_COLOR,
            alignment=tcod.constants.CENTER,
        )

    def _render_tutorial_help(self, console: tcod.console.Console, engine: Engine) -> None:
        """The how-to-play text, drawn beside the little tutorial room."""
        x = engine.game_map.width + 4  # the room hugs the top-left corner
        for i, line in enumerate(lang.TUTORIAL['help']):
            fg = config.TITLE_COLOR if i == 0 else config.TEXT_COLOR
            console.print(x, 1 + i, line, fg=fg)

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
    def _render_status(self, console: tcod.console.Console, engine: Engine, layout: dict) -> None:
        top = layout["status_top"]
        w = layout["w"]
        for i in range(layout["status_rows"]):
            console.rgb[:, top + i]["bg"] = config.BLACK

        fighter = engine.player.fighter
        self._render_bar(console, 1, top, fighter.hp, fighter.max_hp, self.BAR_WIDTH)

        lines = layout["status_lines"]
        stats_x = self.BAR_WIDTH + 3
        console.print(stats_x, top, lines[0][: max(0, w - stats_x)], fg=config.TEXT_COLOR)
        for i, line in enumerate(lines[1:], start=1):
            console.print(1, top + i, line[: w - 1], fg=config.TEXT_COLOR)

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

    def _render_log(self, console: tcod.console.Console, engine: Engine, layout: dict) -> None:
        first_row = layout["log_top"]
        rows = layout["log_rows"]
        w = layout["w"]
        for i, message in enumerate(engine.log.last(rows)):
            console.print(1, first_row + i, message.full_text[: w - 2], fg=message.color)

    #: Always-on key hints, drawn along the bottom.  Keeping the list here
    #: (paired key -> label) makes it the single place to update when bindings
    #: in ``input.py`` change.
    CONTROL_HINTS = lang.CONTROL_HINTS

    def _render_controls(self, console: tcod.console.Console, layout: dict) -> None:
        w = layout["w"]
        for r, hints in enumerate(layout["control_lines"]):
            row = layout["controls_top"] + r
            # A subtle bar so the hints read as a separate strip.
            console.draw_rect(0, row, w, 1, ch=ord(" "), bg=config.WALL_DARK_BG)
            x = 1
            for key, label in hints:
                console.print(x, row, key, fg=config.TITLE_COLOR, bg=config.WALL_DARK_BG)
                x += len(key) + 1
                console.print(x, row, label, fg=config.TEXT_DIM, bg=config.WALL_DARK_BG)
                x += len(label) + 2

    # --- overlays ----------------------------------------------------------
    def _render_inventory(self, console: tcod.console.Console, engine: Engine) -> None:
        items = self._inventory_items(engine)
        equipment = engine.player.get("equipment")
        width, height = 64, 30
        left_w = 40  # width of the item column; the rest is the character sheet
        x = (console.width - width) // 2
        y = (console.height - height) // 2
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
        x = (console.width - width) // 2
        y = (console.height - height) // 2
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
        console.print_box(
            0, console.height // 2, console.width, 1, text,
            fg=config.TITLE_COLOR, alignment=tcod.constants.CENTER,
        )
