"""配置读取：TOML，缺省值可用。"""

from __future__ import annotations

import os
from pathlib import Path

import tomllib

from .rules import Rules

DEFAULT_INTERVAL_MS = 120
MIN_INTERVAL_MS = 40


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    base = Path(appdata) if appdata else Path.home() / ".config"
    return base / "ime-focus" / "config.toml"


def load(path: Path | None = None) -> tuple[Rules, int]:
    """返回 (规则, 轮询间隔毫秒)。文件不存在时给默认值。"""
    path = path or default_config_path()
    data: dict = {}
    if path.is_file():
        with path.open("rb") as fh:
            data = tomllib.load(fh)

    def _strs(key: str) -> tuple[str, ...]:
        value = data.get(key) or []
        if not isinstance(value, list):
            raise SystemExit(f"配置项 {key} 应该是字符串数组")
        return tuple(str(v) for v in value)

    rules = Rules(
        enabled=bool(data.get("enabled", True)),
        only_in=_strs("only_in"),
        ignore=_strs("ignore"),
    )
    interval = int(data.get("interval_ms", DEFAULT_INTERVAL_MS))
    interval = max(MIN_INTERVAL_MS, interval)
    return rules, interval
