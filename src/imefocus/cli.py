"""命令行入口。"""

from __future__ import annotations

import argparse
import contextlib
import sys
import time
from pathlib import Path

from . import __version__, config, rules, win
from . import engine as engine_mod


def _setup_console() -> None:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def cmd_doctor() -> int:
    print("ime-focus doctor\n")
    ok = True
    try:
        win._uia()
        print("  [ok]   UI Automation 可用")
    except Exception as exc:
        print(f"  [fail] UI Automation 不可用: {exc}")
        ok = False

    layouts = win.installed_layouts()
    print(f"  [info] 已装键盘布局: {', '.join(hex(x) for x in layouts) or '无'}")
    if win.activate_layout(win.user32.GetForegroundWindow(), win.EN_US_KLID):
        print("  [ok]   美式键盘 (00000409) 可用")
    else:
        print("  [fail] 没装美式键盘（设置 → 时间和语言 → 添加语言 → 英语(美国)）")
        ok = False

    info = win.focused()
    print(f"  [info] 当前焦点: {info.process or '?'} / {info.class_name or '-'}")

    print("\n结论:", "可以运行" if ok else "先修上面标 fail 的项")
    return 0 if ok else 1


def cmd_run(args: argparse.Namespace) -> int:
    loaded, interval = config.load(args.config)
    loaded = rules.Rules(
        enabled=loaded.enabled and not args.no_config,
        only_in=loaded.only_in,
        ignore=loaded.ignore,
    )
    print(f"ime-focus {__version__}  间隔 {interval}ms"
          f"{'  [dry-run]' if args.dry_run else ''}")
    print("Ctrl+C 退出\n")

    engine = engine_mod.Engine(
        loaded,
        dry_run=args.dry_run,
        emit_noop=args.verbose,
        on_event=lambda ev: print(ev.line(), flush=True),
    )
    try:
        while True:
            engine.tick()
            time.sleep(interval / 1000)
    except KeyboardInterrupt:
        print("\n退出中…")
    finally:
        engine.stop()
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="imefocus", description="密码框自动切英文键盘")
    parser.add_argument("--version", action="version", version=f"ime-focus {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="常驻监视焦点")
    run.add_argument("--dry-run", action="store_true", help="只打印判断，不动键盘")
    run.add_argument("--verbose", "-v", action="store_true", help="连 noop 也打印")
    run.add_argument("--no-config", action="store_true", help="忽略配置里的 enabled")
    run.add_argument("--config", type=Path, default=None, help="配置文件路径")
    run.set_defaults(func=cmd_run)

    doctor = sub.add_parser("doctor", help="环境自检")
    doctor.set_defaults(func=lambda _a: cmd_doctor())

    gui = sub.add_parser("gui", help="打开图形界面（托盘 + 设置窗口）")
    gui.add_argument("--config", type=Path, default=None, help="配置文件路径")
    gui.set_defaults(func=cmd_gui)
    return parser


def cmd_gui(args: argparse.Namespace) -> int:
    from . import gui as gui_mod

    return gui_mod.run(args.config)


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    if sys.platform != "win32":
        print("ime-focus 只支持 Windows")
        return 1
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
