"""配置持久化：读取/保存启动器设置与账户。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from yzl.constants import config_file, default_game_dir

DEFAULTS: dict[str, Any] = {
    "game_dir": None,
    "java_path": "",
    "memory_mb": 2048,
    "mirror": "bmclapi",
    "width": 0,
    "height": 0,
    "download_threads": 8,
    "accounts": [],
    "current_account": None,
    "current_version": None,
    "first_run": True,
    "microsoft_client_id": "00000000402b5328",
    "offline_skin": {},
}


class Config:
    def __init__(self) -> None:
        self.data: dict[str, Any] = dict(DEFAULTS)
        self.path: Path = config_file()
        self.load()

    def load(self) -> None:
        try:
            if self.path.exists():
                raw = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(raw, dict):
                    self.data.update(raw)
        except Exception:
            pass

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def game_dir(self) -> Path:
        gd = self.data.get("game_dir")
        return Path(gd) if gd else default_game_dir()

    def accounts(self) -> list[dict]:
        return self.data.get("accounts", [])

    def current_account(self) -> Optional[dict]:
        ca = self.data.get("current_account")
        if ca is None and self.accounts():
            ca = self.accounts()[0]
        return ca
