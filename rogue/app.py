"""The application shell: opens a tcod window and runs the main loop.

This is the boundary between the pure game (engine + world) and the outside
world (a display and a keyboard).  It stays deliberately thin so the interesting
logic lives in testable modules.
"""
from __future__ import annotations

from typing import Optional

import tcod.console
import tcod.context
import tcod.event

from . import config
from .actions import Action
from .engine import Engine
from .input import Command, InvCommand, dispatch, dispatch_inventory
from .ui.renderer import Renderer


def run(seed: Optional[int] = None, cfg: config.Config = config.DEFAULT) -> None:
    # Noise-cave generation is pure Python and takes a few seconds; tell the
    # player something is happening before the window opens.
    print("Generating cave...", flush=True)
    engine = Engine(cfg=cfg, seed=seed)
    renderer = Renderer(cfg)
    # order="F" makes console.rgb indexable as [x, y], matching the map arrays.
    console = tcod.console.Console(cfg.screen_width, cfg.screen_height, order="F")

    with tcod.context.new(
        columns=cfg.screen_width,
        rows=cfg.screen_height,
        title="procgen-rogue",
        vsync=True,
    ) as context:
        while True:
            renderer.render(console, engine)
            context.present(console)

            for event in tcod.event.wait():
                context.convert_event(event)

                if renderer.show_inventory:
                    _handle_inventory(event, engine, renderer)
                    continue

                command = dispatch(event, engine.player)
                if command is Command.QUIT:
                    return
                if command is Command.TOGGLE_INVENTORY:
                    renderer.open_inventory(engine)
                elif isinstance(command, Action):
                    engine.handle_player_action(command)


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
