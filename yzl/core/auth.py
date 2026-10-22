"""账户：离线账户。"""
from __future__ import annotations
import uuid

def offline_uuid(name: str) -> str:
    return str(uuid.uuid3(uuid.NAMESPACE_URL, "OfflinePlayer:" + name))

def make_offline_account(name: str) -> dict:
    return {"name": name.strip(), "uuid": offline_uuid(name.strip()), "type": "offline"}
