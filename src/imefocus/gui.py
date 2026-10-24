"""图形界面：托盘图标 + 设置窗口。

窗口只负责渲染和改配置，所有判断都在 engine 里。事件从引擎线程来，
经队列交回 Tk 主线程，避免跨线程碰控件。
"""

from __future__ import annotations

import contextlib
import json
import queue
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from . import config
from .engine import Engine
from .rules import Action, Rules
from .tray import Tray

APP_TITLE = "ime-focus"
TASK_NAME = "ime-focus"
LOG_LIMIT = 300
POLL_MS = 150


def _pythonw() -> str:
    exe = Path(sys.executable)
    candidate = exe.with_name("pythonw.exe")
    return str(candidate if candidate.is_file() else exe)



class App:
    def __init__(self, root: tk.Tk, path: Path | None) -> None:
        self.root = root
        self.path = path or config.default_config_path()
        rules, interval = config.load(self.path)
        self._interval = interval
        self._queue: queue.Queue = queue.Queue()
        self._tray = None
        self._closing = False

        self.engine = Engine(rules, on_event=self._queue.put)

        self._build(rules)
        self._start_tray(rules.enabled)
        self.root.after(0, self._tick)

    # ---------- 界面 ----------

    def _build(self, rules: Rules) -> None:
        self.root.title(APP_TITLE)
        self.root.geometry("600x700+70+50")
        self.root.minsize(520, 460)
        self.root.protocol("WM_DELETE_WINDOW", self.quit)
        self.root.bind("<Unmap>", self._on_unmap)
        with contextlib.suppress(tk.TclError):
            self.root.iconphoto(True, tk.PhotoImage(data=_ICON_PNG_B64))

        style = ttk.Style()
        style.configure("Status.TLabel", font=("Segoe UI", 10, "bold"))

        top = ttk.Frame(self.root, padding=(10, 8, 10, 0))
        top.pack(fill="x")
        self.status = ttk.Label(top, text="启动中…", style="Status.TLabel")
        self.status.pack(side="left")
        self.toggle_btn = ttk.Button(top, width=7, command=self.toggle_enabled)
        self.toggle_btn.pack(side="right")

        opts = ttk.Frame(self.root, padding=(10, 2, 10, 0))
        opts.pack(fill="x")
        self.dry = tk.BooleanVar(value=False)
        ttk.Checkbutton(opts, text="试跑（只记录，不切键盘）", variable=self.dry,
                        command=self._on_dry).pack(side="left")
        self.autostart = tk.BooleanVar(value=self._autostart_on())
        ttk.Checkbutton(opts, text="开机自启", variable=self.autostart,
                        command=self._on_autostart).pack(side="right")

        ttk.Label(self.root, text="事件", padding=(10, 8, 10, 0)).pack(anchor="w")
        log_wrap = ttk.Frame(self.root, padding=(10, 0, 10, 0))
        log_wrap.pack(fill="both", expand=True)
        self.log = tk.Text(log_wrap, height=10, wrap="none", state="disabled",
                           font=("Consolas", 9), relief="solid", borderwidth=1)
        bar = ttk.Scrollbar(log_wrap, command=self.log.yview)
        self.log.configure(yscrollcommand=bar.set)
        bar.pack(side="right", fill="y")
        self.log.pack(side="left", fill="both", expand=True)
        for tag, color in (("to_en", "#1d4ed8"), ("restore", "#047857"), ("noop", "#6b7280")):
            self.log.tag_configure(tag, foreground=color)

        cfg = ttk.Frame(self.root, padding=(10, 6))
        cfg.pack(fill="x")
        self.only = self._labeled_text(cfg, "只在指定程序生效（逗号分隔，留空=全部）",
                                       rules.only_in, 0)
        self.ignore = self._labeled_text(cfg, "永不介入", rules.ignore, 1)

        foot = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        foot.pack(fill="x")
        ttk.Button(foot, text="保存配置", command=self.save).pack(side="left")
        ttk.Button(foot, text="清空日志", command=self.clear_log).pack(side="left", padx=6)
        ttk.Button(foot, text="自检", command=self.doctor).pack(side="right")

        self._refresh_status()
        self._append("等待焦点变化 —— 去点一个登录页的密码框试试", "noop")

    def _labeled_text(self, parent, label: str, values: tuple[str, ...], row: int) -> tk.Text:
        ttk.Label(parent, text=label).grid(row=row * 2, column=0, sticky="w")
        box = tk.Text(parent, height=2, wrap="word", relief="solid", borderwidth=1)
        box.grid(row=row * 2 + 1, column=0, sticky="ew", pady=(2, 6))
        box.insert("1.0", ", ".join(values))
        parent.columnconfigure(0, weight=1)
        return box

    # ---------- 状态 ----------

    def _refresh_status(self) -> None:
        state = self.engine.state
        if not self.engine.enabled:
            text = "已暂停"
        elif self.dry.get():
            text = "监视中 · 试跑"
        else:
            text = "监视中"
        if state != "idle":
            text += " · 已切英文"
        self.status.configure(text=text)
        self.toggle_btn.configure(text="暂停" if self.engine.enabled else "启用")

    def _tick(self) -> None:
        """主线程上跑一轮：UIA 必须在主线程，才不会和 STA 死锁。"""
        if not self._closing:
            self.engine.tick()
            try:
                while True:
                    event = self._queue.get_nowait()
                    tag = {Action.TO_EN: "to_en", Action.RESTORE: "restore"}.get(
                        event.action, "noop")
                    self._append(event.line(), tag)
                    self._refresh_status()
            except queue.Empty:
                pass
            self.root.after(self._interval, self._tick)

    def _append(self, line: str, tag: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n", tag)
        excess = int(self.log.index("end-1c").split(".")[0]) - LOG_LIMIT
        if excess > 0:
            self.log.delete("1.0", f"{excess + 1}.0")
        self.log.see("end")
        self.log.configure(state="disabled")

    # ---------- 操作 ----------

    def toggle_enabled(self) -> None:
        enabled = not self.engine.enabled
        self._apply_rules(self._collect_rules(enabled=enabled))
        self._refresh_status()

    def _on_dry(self) -> None:
        self.engine.update(dry_run=self.dry.get())
        self._refresh_status()

    def _collect_rules(self, *, enabled: bool | None = None) -> Rules:
        def items(box: tk.Text) -> tuple[str, ...]:
            raw = box.get("1.0", "end").replace("\n", ",")
            return tuple(part.strip() for part in raw.split(",") if part.strip())

        return Rules(
            enabled=self.engine.enabled if enabled is None else enabled,
            only_in=items(self.only),
            ignore=items(self.ignore),
        )

    def _apply_rules(self, new: Rules) -> None:
        self.engine.update(rules=new)
        self._icon_sync(new.enabled)

    def save(self) -> None:
        new = self._collect_rules()
        self._apply_rules(new)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = (
            f"enabled = {str(new.enabled).lower()}\n"
            f"interval_ms = {self._interval}\n"
            f"only_in = {json.dumps(list(new.only_in))}\n"
            f"ignore = {json.dumps(list(new.ignore))}\n"
        )
        self.path.write_text(body, encoding="utf-8")
        self._append(f"配置已保存到 {self.path}", "noop")

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def doctor(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "imefocus.cli", "doctor"],
            capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace",
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = (result.stdout or "") + (result.stderr or "")
        (messagebox.showinfo if result.returncode == 0 else messagebox.showwarning)(
            "自检结果", out.strip() or "无输出")

    # ---------- 开机自启 ----------

    def _autostart_on(self) -> bool:
        try:
            done = subprocess.run(
                ["schtasks", "/query", "/tn", TASK_NAME],
                capture_output=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            return done.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _on_autostart(self) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        if self.autostart.get():
            target = f'"{_pythonw()}" -m imefocus.cli gui --config "{self.path}"'
            args = ["schtasks", "/create", "/tn", TASK_NAME, "/tr", target,
                    "/sc", "onlogon", "/f"]
        else:
            args = ["schtasks", "/delete", "/tn", TASK_NAME, "/f"]
        try:
            done = subprocess.run(args, capture_output=True, text=True, timeout=20,
                                  encoding="utf-8", errors="replace", creationflags=flags)
        except (OSError, subprocess.SubprocessError) as exc:
            self._append(f"自启设置失败: {exc}", "noop")
            return
        if done.returncode != 0:
            self.autostart.set(not self.autostart.get())
            self._append(f"自启设置失败: {(done.stderr or done.stdout).strip()}", "noop")

    # ---------- 托盘 ----------

    def _start_tray(self, enabled: bool) -> None:
        self._tray = Tray(
            APP_TITLE,
            on_show=lambda: self.root.after(0, self.show),
            on_toggle=lambda: self.root.after(0, self.toggle_enabled),
            on_quit=lambda: self.root.after(0, self.quit),
        )
        if not self._tray.start():
            self._append(f"托盘不可用（{self._tray.error}），只用窗口", "noop")
            self._tray = None
            return
        self._tray.set_enabled(enabled)

    def _icon_sync(self, enabled: bool) -> None:
        if self._tray is not None:
            self._tray.set_enabled(enabled)

    def _on_unmap(self, event: tk.Event) -> None:
        if self._tray is not None and event.widget is self.root and self.root.state() == "iconic":
            self.root.withdraw()

    def show(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def quit(self) -> None:
        self._closing = True
        self.engine.stop()
        if self._tray is not None:
            with contextlib.suppress(Exception):
                self._tray.stop()
        self.root.destroy()


_ICON_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAYAAABzenr0AAAAXklEQVR4nO3OMQEAAAgDoC251a3g"
    "DxKg2TaJlwABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQIECBAgAABAgQI"
    "ECBAgAABAgQIEHAeWLwAAdH1rCIAAAAASUVORK5CYII="
)


def run(path: Path | None = None) -> int:
    root = tk.Tk()
    try:
        App(root, path)
    except Exception as exc:
        messagebox.showerror(APP_TITLE, f"启动失败: {exc}")
        root.destroy()
        return 1
    root.mainloop()
    return 0


def main() -> int:
    return run()
