"""A simple, colourised, de-duplicating message log."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

from . import config


@dataclass
class Message:
    text: str
    color: tuple = config.TEXT_COLOR
    count: int = 1

    @property
    def full_text(self) -> str:
        if self.count > 1:
            return f"{self.text} (x{self.count})"
        return self.text


@dataclass
class MessageLog:
    messages: List[Message] = field(default_factory=list)

    def add(self, text: str, color: tuple = config.TEXT_COLOR, *, stack: bool = True) -> None:
        """Append a message.  Identical consecutive messages stack as '(xN)'."""
        if stack and self.messages and self.messages[-1].text == text:
            self.messages[-1].count += 1
        else:
            self.messages.append(Message(text, color))

    def last(self, count: int) -> List[Message]:
        return self.messages[-count:]
