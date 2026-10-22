"""网络下载：多镜像、并发、进度回调、断点校验。"""
from __future__ import annotations
import hashlib, os, platform, socket
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Callable, Optional, Sequence
import requests

UA = "YZLLauncher/1.0"
MIRROR_BMCLAPI = "https://bmclapi2.bangbang93.com"
ProgressCb = Callable[[str, int, int], None]
_OS = platform.system().lower()
CURRENT_OS = "windows" if _OS == "windows" else ("osx" if _OS == "darwin" else "linux")

class NetError(RuntimeError):
    pass

def _session() -> requests.Session:
    socket.setdefaulttimeout(20)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    return s

def get_json(url: str, timeout: int = 30, tries: int = 3) -> dict:
    last = None
    for i in range(tries):
        try:
            r = _session().get(url, timeout=timeout)
            r.raise_for_status()
            return r.json()
        except Exception as e:
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

def download_file(url, dest, sha1=None, size=None, progress=None, timeout=60) -> bool:
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
    import time as _t
    deadline = _t.time() + 240
    try:
        with _session().get(url, stream=True, timeout=timeout) as r:
            r.raise_for_status()
            total = size or int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if _t.time() > deadline:
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

def download_with_fallback(urls, dest, sha1=None, size=None, progress=None) -> bool:
    for u in urls:
        if u and download_file(u, dest, sha1, size, progress):
            return True
    raise NetError(f"所有镜像均失败: {dest.name}")

class ParallelDownloader:
    def __init__(self, workers: int = 8) -> None:
        self.workers = max(2, min(32, workers))
    def run(self, tasks, progress=None):
        total = len(tasks); done = 0; failed = 0
        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            futures = {ex.submit(download_with_fallback, urls, dest, sha1, size): i for i, (urls, dest, sha1, size) in enumerate(tasks)}
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

def manifest_url(mirror):
    if mirror == "bmclapi":
        return f"{MIRROR_BMCLAPI}/mc/game/version_manifest_v2.json"
    return "https://launchermeta.mojang.com/mc/game/version_manifest_v2.json"
def version_json_urls(mirror, vid, orig=None):
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/versions/{vid}/{vid}.json")
    if orig:
        urls.append(orig)
    return urls
def version_jar_urls(mirror, vid, orig=None):
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/versions/{vid}/{vid}.jar")
    if orig:
        urls.append(orig)
    return urls
def asset_index_urls(mirror, index_id, orig=None):
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/assets/indexes/{index_id}.json")
    if orig:
        urls.append(orig)
    return urls
def asset_object_urls(mirror, h):
    if mirror == "bmclapi":
        return [f"{MIRROR_BMCLAPI}/assets/{h}", f"https://resources.download.minecraft.net/{h[:2]}/{h}"]
    return [f"https://resources.download.minecraft.net/{h[:2]}/{h}", f"{MIRROR_BMCLAPI}/assets/{h}"]
def library_urls(mirror, path, orig=None):
    urls = []
    if mirror == "bmclapi":
        urls.append(f"{MIRROR_BMCLAPI}/libraries/{path}")
    if orig:
        urls.append(orig)
    if not urls:
        urls.append(f"https://libraries.minecraft.net/{path}")
    return urls
def maven_urls(mirror, base, path):
    urls = []
    if mirror == "bmclapi" and "fabricmc.net" in base:
        urls.append(f"{MIRROR_BMCLAPI}/maven/{path}")
    urls.append(base.rstrip("/") + "/" + path)
    return urls
