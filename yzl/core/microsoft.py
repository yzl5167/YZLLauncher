"""微软正版账号：设备码授权 + XBL/XSTS + Minecraft 登录 + 官方皮肤上传。"""
from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

import requests

DEFAULT_CLIENT_ID = "00000000402b5328"
AUTHORITY = "https://login.microsoftonline.com/consumers/oauth2/v2.0"
XBL_CONTRACT = {"x-xbl-contract-version": "1"}


class MicrosoftError(RuntimeError):
    pass


def _post_json(url: str, json_body: dict, headers: Optional[dict] = None) -> dict:
    r = requests.post(url, json=json_body, headers=headers or {}, timeout=30)
    try:
        return r.json()
    except Exception:
        raise MicrosoftError(f"请求失败({r.status_code}): {r.text[:200]}")


def start_device_code(client_id: str = DEFAULT_CLIENT_ID) -> dict:
    data = _post_json(f"{AUTHORITY}/devicecode", {"client_id": client_id, "scope": "XboxLive.signin offline_access"})
    if "device_code" not in data:
        raise MicrosoftError(f"获取设备码失败: {data.get('error_description', data)}")
    return data


def poll_token(client_id: str, device_code: str, interval: int = 5, timeout: int = 900, cancel: Optional[Callable[[], bool]] = None) -> str:
    deadline = time.time() + timeout
    while True:
        if cancel and cancel():
            raise MicrosoftError("已取消登录")
        if time.time() > deadline:
            raise MicrosoftError("登录超时，请重试")
        r = requests.post(f"{AUTHORITY}/token", data={"client_id": client_id, "grant_type": "urn:ietf:params:oauth:grant-type:device_code", "device_code": device_code}, timeout=30).json()
        err = r.get("error")
        if err == "authorization_pending":
            time.sleep(max(interval, 1))
            continue
        if err == "authorization_declined":
            raise MicrosoftError("你在网页上拒绝了登录")
        if err == "expired_token":
            raise MicrosoftError("设备码已过期，请重新登录")
        if "access_token" in r:
            return r["access_token"]
        raise MicrosoftError(f"登录失败: {r.get('error_description', r)}")


def _xbl_authenticate(ms_token: str) -> tuple[str, str]:
    body = {"RelyingParty": "http://auth.xboxlive.com", "TokenType": "JWT", "Properties": {"AuthMethod": "RPS", "SiteName": "user.auth.xboxlive.com", "RpsTicket": f"d={ms_token}"}}
    data = _post_json("https://user.auth.xboxlive.com/user/authenticate", body, XBL_CONTRACT)
    if "Token" not in data:
        raise MicrosoftError("Xbox 认证失败")
    return data["Token"], data["DisplayClaims"]["xui"][0]["uhs"]


def _xsts_authorize(xbl_token: str) -> tuple[str, str]:
    body = {"RelyingParty": "rp://api.minecraftservices.com/", "TokenType": "JWT", "Properties": {"SandboxId": "RETAIL", "UserTokens": [xbl_token]}}
    data = _post_json("https://xsts.auth.xboxlive.com/xsts/authorize", body, XBL_CONTRACT)
    if "Token" not in data:
        err = data.get("XErr", "")
        if err == "2148916233":
            raise MicrosoftError("该微软账号没有绑定 Minecraft Java 版")
        raise MicrosoftError(f"XSTS 认证失败 (XErr={err})")
    return data["Token"], data["DisplayClaims"]["xui"][0]["uhs"]


def _mc_login(xsts_token: str, uhs: str) -> str:
    data = _post_json("https://api.minecraftservices.com/authentication/login_with_xbox", {"identityToken": f"XBL3.0 x={uhs};{xsts_token}"})
    if "access_token" not in data:
        raise MicrosoftError("Minecraft 登录失败")
    return data["access_token"]


def get_profile(access_token: str) -> dict:
    r = requests.get("https://api.minecraftservices.com/minecraft/profile", headers={"Authorization": f"Bearer {access_token}"}, timeout=30)
    if r.status_code == 404:
        raise MicrosoftError("该账号没有 Minecraft Java 版角色")
    return r.json()


def login_ms(ms_token: str, cancel=None, progress=None) -> tuple[str, dict]:
    if progress:
        progress("正在连接 Xbox…")
    xbl, uhs = _xbl_authenticate(ms_token)
    if progress:
        progress("正在验证 Xbox Live…")
    xsts, uhs2 = _xsts_authorize(xbl)
    if progress:
        progress("正在登录 Minecraft…")
    mc_token = _mc_login(xsts, uhs2)
    profile = get_profile(mc_token)
    return mc_token, profile


def upload_skin(access_token: str, png: Path, variant: str = "classic") -> dict:
    if not png.exists():
        raise MicrosoftError(f"皮肤文件不存在: {png}")
    with open(png, "rb") as f:
        data = f.read()
    if not data:
        raise MicrosoftError("皮肤文件为空")
    r = requests.put("https://api.minecraftservices.com/minecraft/profile/skins", headers={"Authorization": f"Bearer {access_token}"}, params={"variant": variant}, files={"file": (png.name, data, "image/png")}, timeout=60)
    if r.status_code not in (200, 201):
        raise MicrosoftError(f"皮肤上传失败({r.status_code}): {r.text[:200]}")
    return r.json()
