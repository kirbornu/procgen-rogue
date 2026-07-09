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
from .input import Command, dispatch
from .ui.renderer import Renderer


def run(seed: Optional[int] = None, cfg: config.Config = config.DEFAULT) -> None:
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
                command = dispatch(event, engine.player)

                if command is Command.QUIT:
                    return
                if command is Command.TOGGLE_INVENTORY:
                    renderer.show_inventory = not renderer.show_inventory
                elif isinstance(command, Action) and not renderer.show_inventory:
                    engine.handle_player_action(command)
