"""命令行入口。"""

from __future__ import annotations

import argparse
import contextlib
import sys
import time
from pathlib import Path

from . import __version__, config, rules, win


def _setup_console() -> None:
    with contextlib.suppress(Exception):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)


def _stamp() -> str:
    return time.strftime("%H:%M:%S")


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
    cfg_path = args.config
    loaded, interval = config.load(cfg_path)
    loaded = rules.Rules(
        enabled=loaded.enabled and not args.no_config,
        only_in=loaded.only_in,
        ignore=loaded.ignore,
    )
    print(f"ime-focus {__version__}  间隔 {interval}ms"
          f"{'  [dry-run]' if args.dry_run else ''}")
    print("Ctrl+C 退出\n")

    state = rules.IDLE
    restore_hkl = 0
    last_key: tuple[str, bool] | None = None

    def restore() -> None:
        if state == rules.EN and restore_hkl:
            hwnd = win.user32.GetForegroundWindow()
            if hwnd:
                win.user32.PostMessageW(
                    hwnd, win.WM_INPUTLANGCHANGEREQUEST, 0, restore_hkl
                )

    try:
        while True:
            info = win.focused()
            decision = rules.decide(info, state, loaded)
            key = (info.process, info.is_password)

            if decision.action is not rules.Action.NOOP:
                if decision.action is rules.Action.TO_EN:
                    if not args.dry_run:
                        restore_hkl = win.current_layout(info.hwnd) or restore_hkl
                        if not win.activate_layout(info.hwnd, win.EN_US_KLID):
                            print("  美式键盘不可用，跳过（跑 imefocus doctor）")
                            time.sleep(interval / 1000)
                            continue
                    state = rules.EN
                else:
                    if not args.dry_run:
                        restore_hkl and win.user32.PostMessageW(
                            info.hwnd, win.WM_INPUTLANGCHANGEREQUEST, 0, restore_hkl
                        )
                    state = rules.IDLE

                print(f"[{_stamp()}] {info.process or '?'}  {info.class_name or '-'}"
                      f"  -> {decision.action.value}  ({decision.reason})")
            elif args.verbose and key != last_key:
                print(f"[{_stamp()}] {info.process or '?'}  {info.class_name or '-'}"
                      f"  -> noop  ({decision.reason})")

            last_key = key
            time.sleep(interval / 1000)
    except KeyboardInterrupt:
        print("\n退出中…")
        if state == rules.EN:
            restore()
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
    return parser


def main(argv: list[str] | None = None) -> int:
    _setup_console()
    if sys.platform != "win32":
        print("ime-focus 只支持 Windows")
        return 1
    args = build_parser().parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
