"""配置持久化：读取/保存启动器设置与账户。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from yzl.constants import config_file, default_game_dir

DEFAULTS: dict[str, Any] = {
    "game_dir": None,          # None -> 便携目录
    "java_path": "",           # 空 -> 自动探测
    "memory_mb": 2048,
    "mirror": "bmclapi",       # mojang / bmclapi
    "width": 0,                # 0 -> 游戏默认
    "height": 0,
    "download_threads": 8,
    "jvm_args": "",          # 额外 JVM 启动参数（空格分隔）
    "auto_update": True,     # 启动时自动检查更新
    "accounts": [],            # [{name, uuid, type, access_token?, skin?}]
    "current_account": None,
    "current_version": None,   # 最近使用的版本 id
    "first_run": True,
    "microsoft_client_id": "00000000402b5328",
    "offline_skin": {},        # {name: skin_path} 离线本地皮肤
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
            pass  # 配置损坏时回退默认

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(
                json.dumps(self.data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass

    # ---- 便捷访问 ----
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default if default is not None else DEFAULTS.get(key))

    def set(self, key: str, value: Any) -> None:
        self.data[key] = value
        self.save()

    def game_dir(self) -> Path:
        gd = self.data.get("game_dir")
        return Path(gd) if gd else default_game_dir()

    def accounts(self) -> list[dict]:
        """返回账户列表；清洗掉旧版遗留的非 dict / 缺 name 的脏数据，避免后续 KeyError。"""
        accs = self.data.get("accounts", [])
        if not accs:
            return []
        cleaned = []
        for a in accs:
            if isinstance(a, dict) and isinstance(a.get("name"), str) and a["name"].strip():
                cleaned.append(a)
        return cleaned

    def current_account(self) -> Optional[dict]:
        """返回当前账户 dict；兼容旧数据把 current_account 存成名字字符串的情况。"""
        ca = self.data.get("current_account")
        name = None
        if isinstance(ca, str):
            name = ca
        elif isinstance(ca, dict):
            name = ca.get("name")
        if name is None and self.accounts():
            name = self.accounts()[0]["name"]
        if name is None:
            return None
        for a in self.accounts():
            if a.get("name") == name:
                return a
        return None
