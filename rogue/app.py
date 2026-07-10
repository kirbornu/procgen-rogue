"""The application shell: opens a tcod window and runs the main loop.

This is the boundary between the pure game (engine + world) and the outside
world (a display and a keyboard).  It owns the top-level flow - main menu,
the game session and the tutorial - while the interesting logic stays in
testable modules.

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
        self.console = tcod.console.Console(cfg.screen_width, cfg.screen_height, order="F")
        self.state = State.MENU
        self.menu_cursor = 0
        #: The persistent game session; survives trips back to the menu.
        self.game: Optional[Engine] = None
        #: The tutorial session; thrown away every time it is left.
        self.tutorial: Optional[Engine] = None

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
        """Return to the menu, resetting any open overlays."""
        engine = self.engine
        if engine is not None:
            engine.close_shop()
        if self.state is State.TUTORIAL:
            self.tutorial = None  # tutorial progress resets every visit
        self.renderer.show_inventory = False
        self.renderer.shop_cursor = 0
        self.state = State.MENU

    def _start_game(self, context: tcod.context.Context) -> None:
        if not self.has_save:
            # Cave generation is pure Python and takes a few seconds; show a
            # banner so the window doesn't look frozen.
            self.renderer.render_generating(self.console)
            context.present(self.console)
            self.game = Engine(cfg=self.cfg, seed=self.seed)
        self.state = State.GAME

    def _start_tutorial(self) -> None:
        self.tutorial = Engine(cfg=self.cfg, generator=generate_tutorial, tutorial=True)
        self.state = State.TUTORIAL

    # --- main loop ----------------------------------------------------------
    def run(self) -> None:
        with tcod.context.new(
            columns=self.cfg.screen_width,
            rows=self.cfg.screen_height,
            title="procgen-rogue",
            vsync=True,
        ) as context:
            while True:
                if self.state is State.MENU:
                    self.renderer.render_menu(self.console, self.menu_cursor, self.has_save)
                else:
                    self.renderer.render(self.console, self.engine)
                context.present(self.console)

                for event in tcod.event.wait():
                    context.convert_event(event)
                    if isinstance(event, tcod.event.Quit):
                        return  # window close always exits the app
                    if self.state is State.MENU:
                        if self._handle_menu(event, context) == "quit":
                            return
                    else:
                        self._handle_session(event)

    def _handle_menu(self, event: tcod.event.Event, context: tcod.context.Context) -> Optional[str]:
        command = dispatch_menu(event)
        if command is MenuCommand.QUIT:
            return "quit"
        if command is MenuCommand.UP:
            self.menu_cursor = (self.menu_cursor - 1) % 3
        elif command is MenuCommand.DOWN:
            self.menu_cursor = (self.menu_cursor + 1) % 3
        elif command is MenuCommand.SELECT:
            if self.menu_cursor == 0:
                self._start_game(context)
            elif self.menu_cursor == 1:
                self._start_tutorial()
            else:
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


def run(seed: Optional[int] = None, cfg: config.Config = config.DEFAULT) -> None:
    App(seed, cfg).run()


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
