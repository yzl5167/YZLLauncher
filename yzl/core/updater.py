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
    优先读仓库根 latest_version.txt（静态文件，不触发 GitHub API 限流，国内更稳）；
    读不到再回退 GitHub API。两者都失败抛 NetError（由调用方区分『连不上』与『已最新』）。"""
    tag: Optional[str] = None
    html_url = ""
    # 1) 优先：静态版本号文件（raw，无 API 限流）
    try:
        txt = net.http_text(
            f"https://raw.githubusercontent.com/{owner}/{repo}/main/latest_version.txt",
            timeout=15, tries=3)
        _t = (txt or "").strip().lower().lstrip("v")
        if _t and re.fullmatch(r"[\d.]+", _t):
            tag = _t
    except Exception:
        tag = None
    # 2) 回退：GitHub API latest release
    if not tag:
        data = net.get_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases/latest",
            timeout=20, tries=3)
        tag = str(data.get("tag_name", "")).lstrip("v")
        html_url = data.get("html_url") or ""
    if not tag:
        raise net.NetError("无法连接更新服务器（GitHub 在国内可能需要加速器）")
    if _parse(tag) <= _parse(APP_VERSION):
        return None
    return {
        "version": tag,
        "exe_url": f"https://github.com/{owner}/{repo}/releases/download/v{tag}/YZLLauncher.exe",
        "notes": "",
        "html_url": html_url or f"https://github.com/{owner}/{repo}/releases/tag/v{tag}",
    }


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
