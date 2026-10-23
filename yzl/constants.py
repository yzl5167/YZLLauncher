"""全局常量与路径工具。"""
from __future__ import annotations

import sys
from pathlib import Path

APP_NAME = "YZL启动器"
APP_VERSION = "1.3.8"
LAUNCHER_NAME = "YZL"
LAUNCHER_VERSION = APP_VERSION

# 主程序所在目录（打包后为 exe 所在目录）
def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent

def config_file() -> Path:
    return app_root() / "config.json"

def default_game_dir() -> Path:
    # 便携模式：启动器目录下的 .minecraft
    return app_root() / ".minecraft"
