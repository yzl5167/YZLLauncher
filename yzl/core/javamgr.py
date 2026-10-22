"""Java 全版本管理：按 Minecraft 版本自动选择所需 Java，并从 Adoptium 下载 JDK 到启动器 java/ 目录。"""
from __future__ import annotations

import re
import zipfile
from pathlib import Path
from typing import Callable, Optional

from yzl.constants import app_root
from yzl.core import net
from yzl.core.net import CURRENT_OS, NetError

ADOPTIUM = "https://api.adoptium.net/v3/assets/latest"
SUPPORTED = (8, 17, 21)  # 覆盖 1.16 及以下 / 1.17-1.20.4 / 1.20.5+


def _nums(mc: str) -> list[int]:
    return [int(x) for x in re.findall(r"\d+", mc or "")]


def required_java(mc_version: str) -> int:
    """根据 Minecraft 版本返回需要的 Java 大版本。"""
    p = _nums(mc_version)
    if not p:
        return 21
    if p[0] == 1 and len(p) >= 2:
        minor = p[1]
        if minor <= 16:
            return 8
        if minor == 17:
            return 17
        if minor < 20 or (minor == 20 and (len(p) < 3 or p[2] < 5)):
            return 17
        return 21
    return 21


def java_dir() -> Path:
    d = app_root() / "java"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _find_java_exe(folder: Path) -> Optional[Path]:
    """在 jdk 目录（含一层子目录）里找 bin/java 可执行文件。"""
    if not folder.exists():
        return None
    exe_name = "java.exe" if CURRENT_OS == "windows" else "java"
    bases = [folder]
    for child in folder.iterdir():
        if child.is_dir():
            bases.append(child)
    for base in bases:
        cand = base / "bin" / exe_name
        if cand.exists():
            return cand
    return None


def list_installed() -> dict[int, Optional[str]]:
    """返回 {java 大版本: java 可执行文件路径或 None}。"""
    out: dict[int, Optional[str]] = {}
    for maj in SUPPORTED:
        exe = _find_java_exe(java_dir() / f"jdk-{maj}")
        out[maj] = str(exe) if exe else None
    return out


def builtin_java(mc_version: str) -> Optional[str]:
    """返回内置的、适配该 MC 版本的 Java 路径；未装返回 None。"""
    maj = required_java(mc_version)
    exe = _find_java_exe(java_dir() / f"jdk-{maj}")
    return str(exe) if exe else None


def adoptium_asset(major: int) -> dict:
    os_map = {"windows": "windows", "osx": "mac", "linux": "linux"}
    url = f"{ADOPTIUM}/{major}/hotspot?os={os_map[CURRENT_OS]}&arch=x64&image_type=jdk"
    data = net.get_json(url, timeout=30)
    assets = data if isinstance(data, list) else (data or {}).get("assets", [])
    if not assets:
        raise NetError(f"没有找到 Java {major} 的下载包")
    pkg = assets[0]["binary"]["package"]
    return {"link": pkg.get("link", ""), "name": pkg.get("name", f"jdk-{major}.zip"),
            "size": pkg.get("size", 0)}


def _safe_extract(zip_path: Path, dest: Path) -> None:
    with zipfile.ZipFile(zip_path) as z:
        for member in z.infolist():
            name = member.filename
            if name.startswith(("/", "\\")) or ".." in name.split("/"):
                continue
            target = dest / name
            if member.is_dir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(member) as srcf, open(target, "wb") as dstf:
                    dstf.write(srcf.read())


def download(major: int, progress: Optional[Callable[[int, int], None]] = None) -> Path:
    """下载并解压 Adoptium JDK 到 java/jdk-{major}/，返回目录。"""
    folder = java_dir() / f"jdk-{major}"
    if _find_java_exe(folder):
        return folder
    a = adoptium_asset(major)
    tmp_zip = java_dir() / f"jdk-{major}.zip"
    ok = net.download_file(a["link"], tmp_zip, size=a["size"] or None, progress=progress)
    if not ok:
        tmp_zip.unlink(missing_ok=True)
        raise NetError(f"Java {major} 下载失败")
    try:
        _safe_extract(tmp_zip, java_dir())
    except Exception as e:
        raise NetError(f"Java {major} 解压失败: {e}")
    finally:
        tmp_zip.unlink(missing_ok=True)
    # 整理：把唯一顶层子目录收拢到 jdk-{major}/ 下，避免嵌套
    folder.mkdir(parents=True, exist_ok=True)
    for child in java_dir().iterdir():
        if child.is_dir() and child != folder and child.name.startswith("jdk"):
            target = folder / child.name
            if not target.exists():
                try:
                    child.rename(target)
                except Exception:
                    pass
    if not _find_java_exe(folder):
        raise NetError("Java 解压后未找到 java 可执行文件")
    return folder


def ensure(mc_version: str, auto_download: bool = True,
           progress: Optional[Callable[[int, int], None]] = None) -> Optional[str]:
    """确保有适配 mc_version 的内置 Java，返回 java 路径；失败返回 None。"""
    exe = builtin_java(mc_version)
    if exe:
        return exe
    if auto_download:
        try:
            download(required_java(mc_version), progress=progress)
            return builtin_java(mc_version)
        except Exception:
            return None
    return None
