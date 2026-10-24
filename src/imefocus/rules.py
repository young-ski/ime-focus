"""判断逻辑：纯函数，不碰 COM，方便测试。

状态机只有两个状态：``idle``（用户原本的布局）和 ``en``（我们切过去的英文）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

IDLE = "idle"
EN = "en"


class Action(str, Enum):
    TO_EN = "to_en"
    RESTORE = "restore"
    NOOP = "noop"


@dataclass(frozen=True)
class FocusInfo:
    hwnd: int = 0
    process: str = ""
    class_name: str = ""
    is_password: bool = False
    is_editable: bool = False


@dataclass(frozen=True)
class Rules:
    enabled: bool = True
    only_in: tuple[str, ...] = field(default_factory=tuple)
    ignore: tuple[str, ...] = field(default_factory=tuple)

    def ignored(self, process: str) -> bool:
        return process.lower() in {p.lower() for p in self.ignore}

    def allowed(self, process: str) -> bool:
        if not self.only_in:
            return True
        return process.lower() in {p.lower() for p in self.only_in}


@dataclass(frozen=True)
class Decision:
    action: Action
    reason: str


def decide(info: FocusInfo, state: str, rules: Rules) -> Decision:
    """给定当前焦点和状态，返回该做什么。"""
    if not rules.enabled:
        return Decision(Action.NOOP, "disabled")
    if not info.hwnd:
        return Decision(Action.NOOP, "no focus")
    if rules.ignored(info.process):
        return Decision(Action.NOOP, f"ignored: {info.process}")
    if not rules.allowed(info.process):
        return Decision(Action.NOOP, f"not allowed: {info.process}")

    if info.is_password:
        if state == EN:
            return Decision(Action.NOOP, "password field, already english")
        return Decision(Action.TO_EN, "password field")

    if state == EN:
        return Decision(Action.RESTORE, "left password field")

    return Decision(Action.NOOP, "nothing to do")
