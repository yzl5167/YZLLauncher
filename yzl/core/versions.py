"""版本管理：清单、安装（含资源）、Fabric、本地版本。"""
from __future__ import annotations
import json, os, re, time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from yzl.constants import app_root
from yzl.core import net
from yzl.core.net import NetError, ProgressCb, get_json

MANIFEST_CACHE = app_root() / ".cache" / "manifest.json"
MANIFEST_TTL = 3600
CURRENT_ARCH = "x64"
_m = re.search(r"(x86_64|amd64|i386|i686|aarch64)", os.environ.get("PROCESSOR_ARCHITECTURE", "") or "")
if _m:
    CURRENT_ARCH = "x64" if _m.group(1) in ("x86_64", "amd64") else ("x86" if _m.group(1) in ("i386", "i686") else "arm64")

@dataclass
class Library:
    path: str
    urls: list[str]
    sha1: Optional[str] = None
    size: Optional[int] = None
    classifier: Optional[str] = None
    is_natives: bool = False

def _maven_path(group, artifact, version, classifier=None):
    fn = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + ".jar"
    return f"{group.replace('.', '/')}/{artifact}/{version}/{fn}"

def _rule_matches(rule: dict) -> bool:
    os_ = rule.get("os", {}) or {}
    if "name" in os_ and os_["name"] != net.CURRENT_OS:
        return False
    if "arch" in os_ and os_["arch"] not in (CURRENT_ARCH, "x86" if CURRENT_ARCH == "x64" else CURRENT_ARCH):
        if not (os_["arch"] == "x86" and CURRENT_ARCH in ("x86", "x64")):
            return False
    return True

def rules_allow(rules: Optional[list]) -> bool:
    if not rules:
        return True
    allow = False
    for r in rules:
        if _rule_matches(r):
            allow = r.get("action") == "allow"
    return allow

def resolve_library(lib: dict) -> Optional[Library]:
    if not rules_allow(lib.get("rules")):
        return None
    parts = lib.get("name", "").split(":")
    if len(parts) == 3:
        group, artifact, version, classifier = parts[0], parts[1], parts[2], None
    elif len(parts) == 4:
        group, artifact, version, classifier = parts
    else:
        return None
    natives_map = lib.get("natives") or {}
    classifier = classifier or natives_map.get(net.CURRENT_OS)
    is_natives = bool(classifier and "natives" in classifier)
    dl = (lib.get("downloads") or {}).get("artifact")
    if dl:
        path = dl.get("path") or _maven_path(group, artifact, version, classifier)
        orig = dl.get("url")
        urls = net.library_urls("bmclapi", path, orig)
        return Library(path=path, urls=urls, sha1=dl.get("sha1"), size=dl.get("size"), classifier=classifier, is_natives=is_natives)
    base = lib.get("url") or "https://libraries.minecraft.net/"
    path = _maven_path(group, artifact, version, classifier)
    if "fabricmc.net" in base or "minecraftforge.net" in base:
        urls = net.maven_urls("bmclapi", base, path)
    else:
        urls = net.library_urls("bmclapi", path, base + path)
    return Library(path=path, urls=urls, sha1=lib.get("sha1"), size=lib.get("size"), classifier=classifier, is_natives=is_natives)

def resolve_libraries(data: dict) -> list[Library]:
    out = []
    for lib in data.get("libraries", []):
        r = resolve_library(lib)
        if r:
            out.append(r)
    return out

def fetch_manifest(mirror: str = "bmclapi", force: bool = False) -> dict:
    if not force and MANIFEST_CACHE.exists():
        if time.time() - MANIFEST_CACHE.stat().st_mtime < MANIFEST_TTL:
            try:
                return json.loads(MANIFEST_CACHE.read_text(encoding="utf-8"))
            except Exception:
                pass
    data = get_json(net.manifest_url(mirror))
    try:
        MANIFEST_CACHE.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST_CACHE.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass
    return data

def all_versions(mirror: str = "bmclapi") -> list[dict]:
    vs = list(fetch_manifest(mirror).get("versions", []))
    vs.sort(key=lambda v: v.get("releaseTime", ""), reverse=True)
    return vs

def versions_dir(game_dir: Path) -> Path:
    return game_dir / "versions"
def libraries_dir(game_dir: Path) -> Path:
    return game_dir / "libraries"
def assets_dir(game_dir: Path) -> Path:
    return game_dir / "assets"
def natives_dir(game_dir: Path, vid: str) -> Path:
    return versions_dir(game_dir) / vid / "natives"

def list_local_versions(game_dir: Path) -> list[str]:
    d = versions_dir(game_dir)
    if not d.exists():
        return []
    return sorted([p.name for p in d.iterdir() if p.is_dir() and (p / f"{p.name}.json").exists()], key=str.lower)

def version_json_path(game_dir: Path, vid: str) -> Path:
    return versions_dir(game_dir) / vid / f"{vid}.json"

def load_version_json(game_dir: Path, vid: str) -> dict:
    p = version_json_path(game_dir, vid)
    if not p.exists():
        raise NetError(f"版本 {vid} 未安装")
    return json.loads(p.read_text(encoding="utf-8"))

def resolve_version(game_dir: Path, vid: str) -> dict:
    data = load_version_json(game_dir, vid)
    parent_id = data.get("inheritsFrom")
    if not parent_id:
        return data
    parent = load_version_json(game_dir, parent_id)
    merged = dict(parent)
    merged["id"] = data.get("id", vid)
    merged["inheritsFrom"] = parent_id
    merged["libraries"] = parent.get("libraries", []) + data.get("libraries", [])
    if data.get("arguments"):
        pa = parent.get("arguments", {})
        ca = data.get("arguments", {})
        merged["arguments"] = {"game": pa.get("game", []) + ca.get("game", []), "jvm": pa.get("jvm", []) + ca.get("jvm", [])}
    for k in ("mainClass", "assetIndex", "assets", "javaVersion", "logging", "minimumLauncherVersion"):
        if data.get(k) is not None:
            merged[k] = data[k]
    return merged

def _tasks_for_assets(index: dict, mirror: str, adir: Path):
    tasks = []
    for obj in index.get("objects", {}).values():
        h = obj.get("hash", "")
        if not h:
            continue
        dest = adir / "objects" / h[:2] / h
        tasks.append((net.asset_object_urls(mirror, h), dest, h, obj.get("size")))
    return tasks

def install_version(game_dir, vid, mirror="bmclapi", progress=None, with_assets=True, cancel=None) -> None:
    manifest = fetch_manifest(mirror)
    meta = next((v for v in manifest.get("versions", []) if v["id"] == vid), None)
    if meta is None:
        raise NetError(f"清单中找不到版本 {vid}")
    vdir = versions_dir(game_dir) / vid
    vdir.mkdir(parents=True, exist_ok=True)
    if progress:
        progress("版本JSON", 0, 1)
    vj_dest = version_json_path(game_dir, vid)
    net.download_with_fallback(net.version_json_urls(mirror, vid, meta.get("url")), vj_dest)
    data = json.loads(vj_dest.read_text(encoding="utf-8"))
    if progress:
        progress("版本JSON", 1, 1)
    if progress:
        progress("游戏核心", 0, 1)
    client = (data.get("downloads") or {}).get("client") or {}
    jar_dest = vdir / f"{vid}.jar"
    net.download_with_fallback(net.version_jar_urls(mirror, vid, client.get("url")), jar_dest, client.get("sha1"), client.get("size"))
    if progress:
        progress("游戏核心", 1, 1)
    libs = resolve_libraries(data)
    if progress:
        progress("库文件", 0, len(libs))
    ParallelPool().download_libs(libs, game_dir, progress)
    extract_natives(libs, game_dir, vid)
    ai = data.get("assetIndex") or {}
    index_id = ai.get("id") or data.get("assets") or "legacy"
    if progress:
        progress("资源索引", 0, 1)
    index_dest = assets_dir(game_dir) / "indexes" / f"{index_id}.json"
    net.download_with_fallback(net.asset_index_urls(mirror, index_id, ai.get("url")), index_dest)
    if progress:
        progress("资源索引", 1, 1)
    if with_assets:
        try:
            index = json.loads(index_dest.read_text(encoding="utf-8"))
        except Exception:
            index = {}
        tasks = _tasks_for_assets(index, mirror, assets_dir(game_dir))
        total = len(tasks)
        if progress:
            progress("资源文件", 0, total)
        for i, (urls, dest, h, size) in enumerate(tasks):
            if cancel and cancel():
                return
            net.download_with_fallback(urls, dest, h, size)
            if progress:
                progress("资源文件", i + 1, total)
    if progress:
        progress("完成", 1, 1)

class ParallelPool:
    def download_libs(self, libs, game_dir, progress=None) -> None:
        tasks = [(l.urls, libraries_dir(game_dir) / l.path, l.sha1, l.size) for l in libs]
        if not tasks:
            return
        if len(tasks) >= 6:
            d = net.ParallelDownloader(8)
            if progress:
                d.run(tasks, lambda st, done, total: progress("库文件", done, total))
            else:
                d.run(tasks)
        else:
            for i, (urls, dest, sha1, size) in enumerate(tasks):
                net.download_with_fallback(urls, dest, sha1, size)
                if progress:
                    progress("库文件", i + 1, len(tasks))

def extract_natives(libs, game_dir, vid) -> None:
    import zipfile
    nat_libs = [l for l in libs if l.is_natives]
    if not nat_libs:
        return
    ndir = natives_dir(game_dir, vid)
    ndir.mkdir(parents=True, exist_ok=True)
    for lib in nat_libs:
        src = libraries_dir(game_dir) / lib.path
        if not src.exists():
            continue
        try:
            with zipfile.ZipFile(src) as z:
                for member in z.namelist():
                    if member.endswith((".RSA", ".SF", ".DSA", "/")):
                        continue
                    name = Path(member).name
                    if not name or ".." in member:
                        continue
                    with z.open(member) as sf, open(ndir / name, "wb") as df:
                        df.write(sf.read())
        except Exception:
            pass

def fabric_loaders(mc_id: str) -> list[dict]:
    return get_json(f"https://meta.fabricmc.net/v2/versions/loader/{mc_id}")
def fabric_profile(mc_id: str, loader: str) -> dict:
    return get_json(f"https://meta.fabricmc.net/v2/versions/loader/{mc_id}/{loader}/profile/json")

def install_fabric(game_dir, mc_id, mirror="bmclapi", progress=None, cancel=None) -> str:
    if mc_id not in list_local_versions(game_dir):
        raise NetError("请先安装原版版本")
    loaders = fabric_loaders(mc_id)
    if not loaders:
        raise NetError("Fabric 不支持该版本")
    loader = loaders[0]["loader"]["version"]
    if progress:
        progress("Fabric配置", 0, 1)
    profile = fabric_profile(mc_id, loader)
    vid = profile.get("id") or f"fabric-loader-{loader}-{mc_id}"
    vdir = versions_dir(game_dir) / vid
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{vid}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    if progress:
        progress("Fabric配置", 1, 1)
    libs = resolve_libraries(profile)
    if progress:
        progress("Fabric库", 0, len(libs))
    ParallelPool().download_libs(libs, game_dir, progress)
    if progress:
        progress("完成", 1, 1)
    return vid
