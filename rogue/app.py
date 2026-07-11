"""The application shell: opens a tcod window and runs the main loop.

This is the boundary between the pure game (engine + world) and the outside
world (a display and a keyboard).  It owns the top-level flow - main menu,
the game session and the tutorial - while the interesting logic stays in
testable modules.

The console is rebuilt from the window each frame, so the game scales when the
window is resized.  The language switch persists the choice in the environment
and asks ``main`` to relaunch the process (the localisation is bound at import).

Session rules: Esc during the tutorial discards it (a fresh one is built next
time); Esc during the game returns to the menu but the game is kept and "Play"
becomes "Continue" until the app closes.
"""
from __future__ import annotations

import enum
from typing import Optional

import tcod.console
import tcod.context
import tcod.event

from . import config
from .actions import Action
from .engine import Engine
from .input import (
    Command,
    InvCommand,
    MenuCommand,
    ShopCommand,
    dispatch,
    dispatch_inventory,
    dispatch_menu,
    dispatch_shop,
)
from .ui.renderer import Renderer
from .world.tutorial import generate_tutorial

#: Returned by :func:`run` to ask ``main`` to relaunch in another language.
RESTART = "restart"


class State(enum.Enum):
    MENU = enum.auto()
    GAME = enum.auto()
    TUTORIAL = enum.auto()


class App:
    """Owns the window, the menu state and the live engine(s)."""

    def __init__(self, seed: Optional[int], cfg: config.Config) -> None:
        self.cfg = cfg
        self.seed = seed
        self.renderer = Renderer(cfg)
        self.state = State.MENU
        self.menu_cursor = 0
        #: The persistent game session; survives trips back to the menu.
        self.game: Optional[Engine] = None
        #: The tutorial session; thrown away every time it is left.
        self.tutorial: Optional[Engine] = None
        #: Set to the new language code when a relaunch is requested.
        self.restart_lang: Optional[str] = None

    # --- helpers ------------------------------------------------------------
    @property
    def engine(self) -> Optional[Engine]:
        if self.state is State.GAME:
            return self.game
        if self.state is State.TUTORIAL:
            return self.tutorial
        return None

    @property
    def has_save(self) -> bool:
        return self.game is not None and not self.game.game_over

    def _to_menu(self) -> None:
        engine = self.engine
        if engine is not None:
            engine.close_shop()
        if self.state is State.TUTORIAL:
            self.tutorial = None  # tutorial progress resets every visit
        self.renderer.show_inventory = False
        self.renderer.shop_cursor = 0
        self.state = State.MENU

    def _start_game(self, console: tcod.console.Console, context: tcod.context.Context) -> None:
        if not self.has_save:
            # Cave generation is pure Python and takes a few seconds; show a
            # banner so the window doesn't look frozen.
            self.renderer.render_generating(console)
            context.present(console)
            self.game = Engine(cfg=self.cfg, seed=self.seed)
        self.state = State.GAME

    def _start_tutorial(self) -> None:
        self.tutorial = Engine(cfg=self.cfg, generator=generate_tutorial, tutorial=True)
        self.state = State.TUTORIAL

    def _cycle_language(self) -> None:
        langs = config.LANGUAGES
        current = self.cfg.language
        index = langs.index(current) if current in langs else 0
        self.restart_lang = langs[(index + 1) % len(langs)]

    # --- main loop ----------------------------------------------------------
    def run(self) -> Optional[str]:
        with tcod.context.new(
            columns=self.cfg.screen_width,
            rows=self.cfg.screen_height,
            title="procgen-rogue",
            vsync=True,
        ) as context:
            while True:
                # Rebuild the console to match the (possibly resized) window.
                console = context.new_console(
                    min_columns=self.cfg.screen_width,
                    min_rows=self.cfg.screen_height,
                    order="F",
                )
                if self.state is State.MENU:
                    self.renderer.render_menu(console, self.menu_cursor, self.has_save)
                else:
                    self.renderer.render(console, self.engine)
                context.present(console)

                for event in tcod.event.wait():
                    context.convert_event(event)
                    if isinstance(event, tcod.event.Quit):
                        return None  # window close exits the app
                    if self.state is State.MENU:
                        outcome = self._handle_menu(event, console, context)
                        if outcome == "quit":
                            return None
                        if outcome == RESTART:
                            return self.restart_lang
                    else:
                        self._handle_session(event)

    def _handle_menu(
        self, event: tcod.event.Event, console: tcod.console.Console, context: tcod.context.Context
    ) -> Optional[str]:
        items = self.renderer.MENU_ITEMS
        command = dispatch_menu(event)
        if command is MenuCommand.QUIT:
            return "quit"
        if command is MenuCommand.UP:
            self.menu_cursor = (self.menu_cursor - 1) % len(items)
        elif command is MenuCommand.DOWN:
            self.menu_cursor = (self.menu_cursor + 1) % len(items)
        elif command is MenuCommand.SELECT:
            choice = items[self.menu_cursor]
            if choice == "play":
                self._start_game(console, context)
            elif choice == "tutorial":
                self._start_tutorial()
            elif choice == "language":
                self._cycle_language()
                return RESTART
            else:  # exit
                return "quit"
        return None

    def _handle_session(self, event: tcod.event.Event) -> None:
        engine = self.engine
        if engine is None:  # pragma: no cover - defensive
            self.state = State.MENU
            return

        if engine.shop is not None:
            _handle_shop(event, engine, self.renderer)
            return
        if self.renderer.show_inventory:
            _handle_inventory(event, engine, self.renderer)
            return

        command = dispatch(event, engine.player)
        if command is Command.MENU:
            self._to_menu()
        elif command is Command.TOGGLE_INVENTORY:
            self.renderer.open_inventory(engine)
        elif isinstance(command, Action):
            engine.handle_player_action(command)


def run(seed: Optional[int] = None, cfg: config.Config = config.DEFAULT) -> Optional[str]:
    """Run the app; returns a language code if a relaunch was requested."""
    return App(seed, cfg).run()


def _handle_inventory(event: tcod.event.Event, engine: Engine, renderer: Renderer) -> None:
    command = dispatch_inventory(event)
    if command is InvCommand.CLOSE:
        renderer.show_inventory = False
    elif command is InvCommand.UP:
        renderer.move_inventory_cursor(-1, engine)
    elif command is InvCommand.DOWN:
        renderer.move_inventory_cursor(1, engine)
    elif command is InvCommand.EQUIP:
        item = renderer.selected_item(engine)
        if item is not None:
            engine.toggle_equip(item)


def _handle_shop(event: tcod.event.Event, engine: Engine, renderer: Renderer) -> None:
    command = dispatch_shop(event)
    if command is ShopCommand.CLOSE:
        engine.close_shop()
        renderer.shop_cursor = 0
    elif command is ShopCommand.UP:
        renderer.move_shop_cursor(-1, engine)
    elif command is ShopCommand.DOWN:
        renderer.move_shop_cursor(1, engine)
    elif command is ShopCommand.SELECT:
        row = renderer.selected_shop_row(engine)
        if row is not None:
            kind, payload = row
            if kind == "upgrade":
                engine.buy_upgrade(payload)
            else:
                engine.sell_item(payload)
