"""轮询逻辑：CLI 和 GUI 共用。

``tick()`` 由调用方按自己的节奏驱动（GUI 用 Tk 的 ``after``，CLI 用 sleep 循环）。
UIA 调用必须发生在主线程：自己的窗口属于主线程的 STA，从别的线程调用会被
marshal 回主线程，主线程没有泵消息时就会死锁。
"""

from __future__ import annotations

import time
from dataclasses import dataclass

from . import win
from .rules import EN, IDLE, Action, FocusInfo, Rules, decide

MIN_INTERVAL_MS = 40


@dataclass(frozen=True)
class Event:
    at: float
    info: FocusInfo
    action: Action
    reason: str
    forced: bool = False

    @property
    def clock(self) -> str:
        return time.strftime("%H:%M:%S", time.localtime(self.at))

    @property
    def where(self) -> str:
        return f"{self.info.process or '?'}  {self.info.class_name or '-'}"

    def line(self) -> str:
        if self.action is Action.NOOP:
            return f"[{self.clock}] {self.where}  --  {self.reason}"
        return f"[{self.clock}] {self.where}  ->  {self.action.value}  ({self.reason})"


class Engine:
    def __init__(
        self,
        rules: Rules,
        *,
        dry_run: bool = False,
        emit_noop: bool = False,
        on_event=None,
    ) -> None:
        self._rules = rules
        self._dry_run = dry_run
        self._emit_noop = emit_noop
        self._on_event = on_event
        self._restore_hkl = 0
        self._last_key: tuple[str, bool] | None = None
        self.state = IDLE
        self.last = FocusInfo()

    @property
    def dry_run(self) -> bool:
        return self._dry_run

    @property
    def enabled(self) -> bool:
        return self._rules.enabled

    def update(self, *, rules: Rules | None = None, dry_run: bool | None = None) -> None:
        if rules is not None:
            self._rules = rules
        if dry_run is not None:
            self._dry_run = dry_run

    def tick(self) -> None:
        """跑一轮，间隔由调用方掌握。"""
        try:
            self._step()
        except Exception as exc:
            self._emit(FocusInfo(), Action.NOOP, f"错误: {exc}")

    def stop(self) -> None:
        if self.state == EN:
            self._restore()

    def _emit(self, info: FocusInfo, action: Action, reason: str, force: bool = False) -> None:
        if self._on_event is not None:
            self._on_event(Event(time.time(), info, action, reason, force))

    def _restore(self) -> None:
        if self._restore_hkl and (hwnd := win.user32.GetForegroundWindow()):
            win.user32.PostMessageW(hwnd, win.WM_INPUTLANGCHANGEREQUEST, 0, self._restore_hkl)
        self.state = IDLE

    def _step(self) -> None:
        info = win.focused()
        self.last = info
        decision = decide(info, self.state, self._rules)
        action, note = decision.action, decision.reason

        if action is not Action.NOOP:
            if self._dry_run:
                self.state = EN if action is Action.TO_EN else IDLE
            elif action is Action.TO_EN:
                self._restore_hkl = win.current_layout(info.hwnd) or self._restore_hkl
                if win.activate_layout(info.hwnd, win.EN_US_KLID):
                    self.state = EN
                else:
                    action, note = Action.NOOP, "美式键盘不可用"
            else:
                self._restore()

        key = (info.process, info.is_password)
        if action is not Action.NOOP or (self._emit_noop and key != self._last_key):
            self._emit(info, action, note)
        self._last_key = key
