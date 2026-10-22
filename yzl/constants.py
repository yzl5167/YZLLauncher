"""全局常量与路径工具。"""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "YZL启动器"
APP_VERSION = "1.2.0"
LAUNCHER_NAME = "YZL"
LAUNCHER_VERSION = APP_VERSION


def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def config_file() -> Path:
    return app_root() / "config.json"


def default_game_dir() -> Path:
    return app_root() / ".minecraft"
