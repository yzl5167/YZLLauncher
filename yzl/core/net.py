"""网络下载：多镜像、并发、进度回调、断点校验。"""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional, Sequence

import requests

UA = "YZLLauncher/1.0 (+https://github.com/yzl-launcher)"
MIRROR_BMCLAPI = "https://bmclapi2.bangbang93.com"

ProgressCb = Callable[[str, int, int], None]  # (阶段, 完成数, 总数)

_OS = platform.system().lower()  # windows / linux / darwin
CURRENT_OS = "windows" if _OS == "windows" else ("osx" if _OS == "darwin" else "linux")


class NetError(RuntimeError):
    pass


def _session() -> requests.Session:
    import socket

    socket.setdefaulttimeout(20)  # 防止个别坏连接挂死整个下载批
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    return s


# ---------------- 下载源自动测速 ----------------
_MIRROR_CACHE = {"t": 0.0, "mirror": "bmclapi"}


def fastest_mirror(timeout: int = 3) -> str:
    """测量候选镜像延迟，返回最快的（bmclapi 国内 / mojang 官方）。结果缓存 5 分钟。"""
    import time as _t

    now = _t.time()
    if now - _MIRROR_CACHE["t"] < 300:
        return _MIRROR_CACHE["mirror"]
    lat = {}
    probes = (
        ("bmclapi", f"{MIRROR_BMCLAPI}/mc/game/version_manifest_v2.json"),
        ("mojang", "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"),
    )
    for m, url in probes:
        try:
            s = _t.time()
            requests.head(url, timeout=timeout)
            lat[m] = _t.time() - s
        except Exception:
            lat[m] = 999.0
    best = min(lat, key=lat.get)
    _MIRROR_CACHE.update({"t": now, "mirror": best})
    return best


def effective_mirror(mirror: str) -> str:
    """把 'auto' 解析为当前最快的镜像；非法值回退 bmclapi（国内加速）。"""
    if mirror == "auto":
        return fastest_mirror()
    return mirror if mirror in ("bmclapi", "mojang") else "bmclapi"


def get_json(url: str, timeout: int = 30, tries: int = 3) -> dict:
    last: Optional[Exception] = None
    for i in range(tries):
        try:
            r = _session().get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:  # noqa: BLE001
            last = e
            if i == tries - 1:
                break
    raise NetError(f"请求失败: {url} ({last})")


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def download_file(
    url: str,
    dest: Path,
    sha1: Optional[str] = None,
    size: Optional[int] = None,
    progress: Optional[Callable[[int, int], None]] = None,
    timeout: int = 60,
) -> bool:
    """下载到临时文件后原子落盘；已存在且校验通过则直接返回 True。"""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        ok = True
        if size and dest.stat().st_size != size:
            ok = False
        if ok and sha1:
            try:
                ok = _sha1(dest) == sha1
            except Exception:
                ok = False
        if ok:
            return True
    tmp = dest.with_suffix(dest.suffix + ".part")
    import time as _time

    deadline = _time.time() + 240  # 单文件总时限，防止慢速连接拖死整批
    try:
        with _session().get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total = size or int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if _time.time() > deadline:
                        raise TimeoutError("下载超时")
                    if not chunk:
                        continue
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total or done)
        if sha1 and _sha1(tmp) != sha1:
            tmp.unlink(missing_ok=True)
            return False
        tmp.replace(dest)
        return True
    except Exception:
        tmp.unlink(missing_ok=True)
        return False


def download_with_fallback(
    urls: Sequence[str],
    dest: Path,
    sha1: Optional[str] = None,
    size: Optional[int] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> bool:
    last_err: Optional[str] = None
    for u in urls:
        if u and download_file(u, dest, sha1, size, progress):
            return True
        last_err = f"所有镜像均失败"
    raise NetError(f"{last_err}: {dest.name}")


class ParallelDownloader:
    """并发下载一组 (urls, dest, sha1, size)。"""

    def __init__(self, workers: int = 8) -> None:
        self.workers = max(2, min(32, workers))

    def run(
        self,
        tasks: Sequence[tuple[Sequence[str], Path, Optional[str], Optional[int]]],
        progress: Optional[ProgressCb] = None,
    ) -> tuple[int, int]:
        total = len(tasks)
        done = 0
        failed = 0
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futures = {
                ex.submit(download_with_fallback, urls, dest, sha1, size): i
                for i, (urls, dest, sha1, size) in enumerate(tasks)
            }
            for fut in as_completed(futures):
                done += 1
                try:
                    if not fut.result():
                        failed += 1
                except Exception:
                    failed += 1
                if progress:
                    progress("下载", done, total)
        return done - failed, failed


# ---------------- 镜像 URL 构造 ----------------

def manifest_url(mirror: str) -> str:
    if mirror == "bmclapi":
        return f"{MIRROR_BMCLAPI}/mc/game/version_manifest_v2.json"
    return "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"


def version_json_urls(mirror: str, vid: str, orig: Optional[str] = None) -> list[str]:
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/versions/{vid}/{vid}.json")
    if orig:
        urls.append(orig)
    return urls


def version_jar_urls(mirror: str, vid: str, orig: Optional[str] = None) -> list[str]:
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/versions/{vid}/{vid}.jar")
    if orig:
        urls.append(orig)
    return urls


def asset_index_urls(mirror: str, index_id: str, orig: Optional[str] = None) -> list[str]:
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/assets/indexes/{index_id}.json")
    if orig:
        urls.append(orig)
    return urls


def asset_object_urls(mirror: str, h: str) -> list[str]:
    if mirror == "bmclapi":
        return [f"{MIRROR_BMCLAPI}/assets/{h}", f"https://resources.download.minecraft.net/{h[:2]}/{h}"]
    return [f"https://resources.download.minecraft.net/{h[:2]}/{h}", f"{MIRROR_BMCLAPI}/assets/{h}"]


def library_urls(mirror: str, path: str, orig: Optional[str] = None) -> list[str]:
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/libraries/{path}")
    if orig:
        urls.append(orig)
    if not urls:
        urls.append(f"https://libraries.minecraft.net/{path}")
    return urls


def maven_urls(mirror: str, base: str, path: str) -> list[str]:
    """Fabric/Forge 等第三方 maven 库。"""
    urls = []
    if mirror == "bmclapi" and "fabricmc.net" in base:
        urls.append(f"{MIRROR_BMCLAPI}/maven/{path}")
    urls.append(base.rstrip("/") + "/" + path)
    return urls
