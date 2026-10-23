"""内置自动更新：启动时检查 GitHub Release，若有新版则下载新 exe 并就地替换重启。"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable, Optional

from yzl.constants import APP_VERSION
from yzl.core import net

OWNER, REPO = "yzl5167", "YZLLauncher"


def _parse(v: str) -> tuple:
    return tuple(int(x) for x in re.findall(r"\d+", v or "")[:3])


def check_latest(owner: str = OWNER, repo: str = REPO) -> Optional[dict]:
    """查询最新 Release；若高于当前版本则返回更新信息，否则返回 None。
    网络/接口失败时抛 NetError（由调用方区分『连不上』与『已最新』），
    不再静默当作已最新，避免国内访问 GitHub API 失败时误导用户以为没有更新。"""
    data = net.get_json(
        f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
        timeout=25, tries=4)
    tag = str(data.get("tag_name", "")).lstrip("v")
    if not tag or _parse(tag) <= _parse(APP_VERSION):
        return None
    exe_url = None
    for a in data.get("assets", []):
        if a.get("name") == "YZLLauncher.exe":
            exe_url = a.get("browser_download_url")
            break
    return {"version": tag, "exe_url": exe_url, "notes": data.get("body") or "",
            "html_url": data.get("html_url") or ""}


def download_update(exe_url: str, progress: Optional[Callable[[int, int], None]] = None) -> Path:
    """把新版 exe 下载到临时目录。"""
    if not exe_url:
        raise net.NetError("发布中没有找到可执行文件")
    dest = Path(tempfile.gettempdir()) / "YZLLauncher_new.exe"
    if not net.download_file(exe_url, dest, progress=progress):
        raise net.NetError("更新包下载失败")
    return dest


def apply_update(new_exe: Path) -> None:
    """退出当前进程，删除旧 exe，把新版移动到原位并重启（Windows 打包版）。"""
    if not getattr(sys, "frozen", False):
        raise RuntimeError("仅打包版本支持在线更新")
    cur = Path(sys.executable)
    bat = cur.with_name("_yzl_update.bat")
    script = (
        "@echo off\r\n"
        "timeout /t 2 /nobreak >nul\r\n"
        f'del /q "{cur}"\r\n'
        f'move /y "{new_exe}" "{cur}"\r\n'
        f'start "" "{cur}"\r\n'
        'del "%~f0"\r\n'
    )
    bat.write_text(script, encoding="gbk", errors="replace")
    # DETACHED_PROCESS：脱离父进程，等待主程序退出后再替换
    subprocess.Popen([str(bat)], creationflags=0x00000008, close_fds=True,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
