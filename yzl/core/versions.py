"""版本管理：清单、安装（含资源）、Fabric、本地版本。"""
from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from yzl.constants import app_root
from yzl.core import net
from yzl.core.net import NetError, ProgressCb, get_json

MANIFEST_CACHE = app_root() / ".cache" / "manifest.json"
MANIFEST_TTL = 3600  # 秒

CURRENT_ARCH = "x64"
_m = re.search(r"(x86_64|amd64|i386|i686|aarch64)", os.environ.get("PROCESSOR_ARCHITECTURE", "") or "")
if _m:
    CURRENT_ARCH = "x64" if _m.group(1) in ("x86_64", "amd64") else ("x86" if _m.group(1) in ("i386", "i686") else "arm64")

# 安装全局进度权重（合计 100）
P_JSON, P_CORE, P_LIBS, P_IDX, P_ASSETS = 4, 16, 40, 6, 34


@dataclass
class Library:
    path: str
    urls: list[str]
    sha1: Optional[str] = None
    size: Optional[int] = None
    classifier: Optional[str] = None
    is_natives: bool = False


def _maven_path(group: str, artifact: str, version: str, classifier: Optional[str] = None) -> str:
    fn = f"{artifact}-{version}" + (f"-{classifier}" if classifier else "") + ".jar"
    return f"{group.replace('.', '/')}/{artifact}/{version}/{fn}"


def _rule_matches(rule: dict) -> bool:
    os_ = rule.get("os", {}) or {}
    if "name" in os_ and os_["name"] != net.CURRENT_OS:
        return False
    if "arch" in os_ and os_["arch"] not in (CURRENT_ARCH, "x86" if CURRENT_ARCH == "x64" else CURRENT_ARCH):
        # 允许 x86 规则同时适配 x64（Java 兼容）
        if not (os_["arch"] == "x86" and CURRENT_ARCH in ("x86", "x64")):
            return False
    if "features" in rule and rule["features"]:
        return False  # 需要特殊 launcher 能力，跳过
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
    """把版本 JSON 中的一条库解析成可下载对象；不匹配当前平台返回 None。"""
    if not rules_allow(lib.get("rules")):
        return None
    name = lib.get("name", "")
    parts = name.split(":")
    if len(parts) == 3:
        group, artifact, version, classifier = parts[0], parts[1], parts[2], None
    elif len(parts) == 4:
        group, artifact, version, classifier = parts
    else:
        return None

    # 旧版 natives 声明：natives: {"windows": "natives-windows"}
    natives_map = lib.get("natives") or {}
    classifier = classifier or natives_map.get(net.CURRENT_OS)
    is_natives = bool(classifier and "natives" in classifier)

    dl = (lib.get("downloads") or {}).get("artifact")
    if dl:
        path = dl.get("path") or _maven_path(group, artifact, version, classifier)
        orig = dl.get("url")
        urls = net.library_urls("bmclapi", path, orig)  # 下载时按全局镜像再排
        return Library(path=path, urls=urls, sha1=dl.get("sha1"), size=dl.get("size"),
                       classifier=classifier, is_natives=is_natives)
    # 旧式：lib["url"] 为 maven 根
    base = lib.get("url") or "https://libraries.minecraft.net/"
    path = _maven_path(group, artifact, version, classifier)
    if "fabricmc.net" in base or "minecraftforge.net" in base:
        urls = net.maven_urls("bmclapi", base, path)
    else:
        urls = net.library_urls("bmclapi", path, base + path)
    return Library(path=path, urls=urls, sha1=lib.get("sha1"), size=lib.get("size"),
                   classifier=classifier, is_natives=is_natives)


def resolve_libraries(data: dict) -> list[Library]:
    out = []
    for lib in data.get("libraries", []):
        r = resolve_library(lib)
        if r:
            out.append(r)
    return out


# ---------------- 清单 ----------------

def fetch_manifest(mirror: str = "bmclapi", force: bool = False) -> dict:
    if not force and MANIFEST_CACHE.exists():
        age = time.time() - MANIFEST_CACHE.stat().st_mtime
        if age < MANIFEST_TTL:
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
    """全部 Java 版版本（含远古版本），按发布时间排序。"""
    m = fetch_manifest(mirror)
    vs = list(m.get("versions", []))
    vs.sort(key=lambda v: v.get("releaseTime", ""), reverse=True)
    return vs


# ---------------- 本地版本 ----------------

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
    out = []
    for p in d.iterdir():
        if p.is_dir() and (p / f"{p.name}.json").exists():
            out.append(p.name)
    return sorted(out, key=lambda v: v.lower())


def version_json_path(game_dir: Path, vid: str) -> Path:
    return versions_dir(game_dir) / vid / f"{vid}.json"


def load_version_json(game_dir: Path, vid: str) -> dict:
    p = version_json_path(game_dir, vid)
    if not p.exists():
        raise NetError(f"版本 {vid} 未安装")
    return json.loads(p.read_text(encoding="utf-8"))


def resolve_version(game_dir: Path, vid: str) -> dict:
    """合并 inheritsFrom 父版本（Fabric 等场景）。"""
    data = load_version_json(game_dir, vid)
    parent_id = data.get("inheritsFrom")
    if not parent_id:
        return data
    parent = load_version_json(game_dir, parent_id)
    merged = dict(parent)
    merged["id"] = data.get("id", vid)
    merged["inheritsFrom"] = parent_id  # 保留继承标记，供启动引擎定位原版核心
    merged["libraries"] = parent.get("libraries", []) + data.get("libraries", [])
    if data.get("arguments"):
        pa = parent.get("arguments", {})
        ca = data.get("arguments", {})
        merged["arguments"] = {
            "game": pa.get("game", []) + ca.get("game", []),
            "jvm": pa.get("jvm", []) + ca.get("jvm", []),
        }
    for k in ("mainClass", "assetIndex", "assets", "javaVersion", "logging", "minimumLauncherVersion"):
        if data.get(k) is not None:
            merged[k] = data[k]
    return merged


# ---------------- 安装 ----------------

def _tasks_for_assets(index: dict, mirror: str, assets_dir: Path) -> list[tuple[list[str], Path, Optional[str], Optional[int]]]:
    tasks = []
    for obj in index.get("objects", {}).values():
        h = obj.get("hash", "")
        if not h:
            continue
        size = obj.get("size")
        dest = assets_dir / "objects" / h[:2] / h
        tasks.append((net.asset_object_urls(mirror, h), dest, h, size))
    return tasks


def install_version(
    game_dir: Path,
    vid: str,
    mirror: str = "bmclapi",
    progress: Optional[ProgressCb] = None,
    with_assets: bool = True,
    cancel: Optional[Callable[[], bool]] = None,
) -> None:
    """安装一个原版版本：JSON + 客户端jar + 库 + 资源索引 + 资源对象。
    progress 回调传 (阶段, 全局完成百分比 0-100, 100)，供 UI 平滑显示。"""
    mirror = net.effective_mirror(mirror)
    manifest = fetch_manifest(mirror)
    meta = next((v for v in manifest.get("versions", []) if v["id"] == vid), None)
    if meta is None:
        raise NetError(f"清单中找不到版本 {vid}")

    vdir = versions_dir(game_dir) / vid
    vdir.mkdir(parents=True, exist_ok=True)

    # 1) 版本 JSON
    if progress:
        progress("版本JSON", 0, 100)
    vj_urls = net.version_json_urls(mirror, vid, meta.get("url"))
    vj_dest = version_json_path(game_dir, vid)
    net.download_with_fallback(vj_urls, vj_dest)
    data = json.loads(vj_dest.read_text(encoding="utf-8"))
    if progress:
        progress("版本JSON", P_JSON, 100)

    # 2) 客户端 jar（按字节平滑走 P_CORE 权重）
    client = (data.get("downloads") or {}).get("client") or {}
    jar_urls = net.version_jar_urls(mirror, vid, client.get("url"))
    jar_dest = vdir / f"{vid}.jar"
    core_cb = None
    if progress:
        core_cb = lambda d, t: progress(
            "游戏核心", P_JSON + int(P_CORE * (d / t if t else 0)), 100)
    net.download_with_fallback(jar_urls, jar_dest, client.get("sha1"), client.get("size"), progress=core_cb)
    if progress:
        progress("游戏核心", P_JSON + P_CORE, 100)

    if cancel and cancel():
        return

    # 3) 库文件（全局 20% → 60%）
    libs = resolve_libraries(data)
    ParallelPool().download_libs(libs, game_dir, progress, base=P_JSON + P_CORE, span=P_LIBS)
    base = P_JSON + P_CORE + P_LIBS

    # 4) natives 解压（仅旧版需要）
    extract_natives(libs, game_dir, vid)

    if cancel and cancel():
        return

    # 5) 资源索引
    ai = data.get("assetIndex") or {}
    index_id = ai.get("id") or data.get("assets") or "legacy"
    if progress:
        progress("资源索引", base, 100)
    index_dest = assets_dir(game_dir) / "indexes" / f"{index_id}.json"
    net.download_with_fallback(net.asset_index_urls(mirror, index_id, ai.get("url")), index_dest)
    if progress:
        progress("资源索引", base + P_IDX, 100)
    base += P_IDX

    # 6) 资源对象（体积大，可取消；60% → 100%）
    if with_assets:
        try:
            index = json.loads(index_dest.read_text(encoding="utf-8"))
        except Exception:
            index = {}
        tasks = _tasks_for_assets(index, mirror, assets_dir(game_dir))
        total = len(tasks)
        if progress:
            progress("资源文件", base, 100)
        # 资源对象多是千级小文件，串行极慢 → 并发下载提速
        if total >= 4:
            net.ParallelDownloader(_threads()).run(
                tasks,
                lambda st, d, t: progress(
                    "资源文件", base + int(P_ASSETS * (d / t if t else 0)), 100),
            )
        else:
            done = 0
            for urls, dest, h, size in tasks:
                if cancel and cancel():
                    return
                net.download_with_fallback(urls, dest, h, size)
                done += 1
                if progress:
                    progress("资源文件", base + int(P_ASSETS * (done / total if total else 0)), 100)
    if progress:
        progress("完成", 100, 100)


def missing_assets(game_dir: Path, index: dict) -> list[str]:
    """返回资产索引中尚未下载到本地的对象 hash 列表（用于启动前完整性检查）。"""
    ad = assets_dir(game_dir)
    missing = []
    for obj in index.get("objects", {}).values():
        h = obj.get("hash", "")
        if not h:
            continue
        if not (ad / "objects" / h[:2] / h).exists():
            missing.append(h)
    return missing


def ensure_assets(
    game_dir: Path,
    parent_id: str,
    mirror: str = "bmclapi",
    progress: Optional[ProgressCb] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> None:
    """确保版本所需的资源对象已全部就绪；缺失部分自动补下。
    用于解决『资源文件没下完就启动 → MC 加载纹理 NoSuchFileException 崩溃』的问题。
    progress 回调传 (已完成对象数, 总缺失数)。"""
    mirror = net.effective_mirror(mirror)
    data = load_version_json(game_dir, parent_id)
    ai = data.get("assetIndex") or {}
    index_id = ai.get("id") or data.get("assets") or "legacy"
    index_dest = assets_dir(game_dir) / "indexes" / f"{index_id}.json"
    if not index_dest.exists():
        net.download_with_fallback(net.asset_index_urls(mirror, index_id, ai.get("url")), index_dest)
    try:
        index = json.loads(index_dest.read_text(encoding="utf-8"))
    except Exception:
        index = {}
    tasks = []
    for obj in index.get("objects", {}).values():
        h = obj.get("hash", "")
        if not h:
            continue
        dest = assets_dir(game_dir) / "objects" / h[:2] / h
        if dest.exists():
            continue
        tasks.append((net.asset_object_urls(mirror, h), dest, h, obj.get("size")))
    total = len(tasks)
    if total == 0:
        return
    # 并发补全资源对象（多为千级小文件，并发明显提速）
    if total >= 4:
        net.ParallelDownloader(_threads()).run(
            tasks,
            lambda st, d, t: progress(d, t) if progress else None,
        )
    else:
        done = 0
        for urls, dest, h, size in tasks:
            if cancel and cancel():
                raise NetError("资源下载已取消")
            net.download_with_fallback(urls, dest, h, size)
            done += 1
            if progress:
                progress(done, total)


def _threads(default: int = 12) -> int:
    """读取配置的下载线程数（默认 12），限制在合理范围，用于并发下载提速。"""
    try:
        cfg = json.loads((app_root() / "config.json").read_text(encoding="utf-8"))
        t = int(cfg.get("download_threads") or default)
    except Exception:
        t = default
    return max(4, min(24, t))


class ParallelPool:
    """串行/并发混合：按数量决定并发。progress 传全局 0-100 百分比。"""

    def download_libs(self, libs: list[Library], game_dir: Path, progress=None,
                      base: int = 0, span: int = 40) -> None:
        tasks = []
        for lib in libs:
            dest = libraries_dir(game_dir) / lib.path
            tasks.append((lib.urls, dest, lib.sha1, lib.size))
        if not tasks:
            return
        n = len(tasks)
        if n >= 6:
            d = net.ParallelDownloader(_threads())
            if progress:
                d.run(tasks, lambda st, done, total: progress(
                    "库文件", base + int(span * (done / total if total else 0)), 100))
            else:
                d.run(tasks)
        else:
            for i, (urls, dest, sha1, size) in enumerate(tasks):
                net.download_with_fallback(urls, dest, sha1, size)
                if progress:
                    progress("库文件", base + int(span * ((i + 1) / n)), 100)


def extract_natives(libs: list[Library], game_dir: Path, vid: str) -> None:
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
                    # 跳过签名与目录，防路径穿越
                    if member.endswith((".RSA", ".SF", ".DSA", "/")):
                        continue
                    name = Path(member).name
                    if not name or ".." in member:
                        continue
                    target = ndir / name
                    with z.open(member) as srcf, open(target, "wb") as dstf:
                        dstf.write(srcf.read())
        except Exception:
            pass


# ---------------- Fabric ----------------

def fabric_loaders(mc_id: str) -> list[dict]:
    return get_json(f"https://meta.fabricmc.net/v2/versions/loader/{mc_id}")


def fabric_profile(mc_id: str, loader: str) -> dict:
    return get_json(f"https://meta.fabricmc.net/v2/versions/loader/{mc_id}/{loader}/profile/json")


def install_fabric(
    game_dir: Path,
    mc_id: str,
    mirror: str = "bmclapi",
    progress: Optional[ProgressCb] = None,
    cancel: Optional[Callable[[], bool]] = None,
) -> str:
    """安装 Fabric Loader，返回 Fabric 版本 id。需先装好原版。"""
    mirror = net.effective_mirror(mirror)
    if mc_id not in list_local_versions(game_dir):
        raise NetError("请先安装原版版本")

    loaders = fabric_loaders(mc_id)
    if not loaders:
        raise NetError("Fabric 不支持该版本")
    loader = loaders[0]["loader"]["version"]

    if progress:
        progress("Fabric配置", 0, 100)
    profile = fabric_profile(mc_id, loader)
    vid = profile.get("id") or f"fabric-loader-{loader}-{mc_id}"
    vdir = versions_dir(game_dir) / vid
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{vid}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    if progress:
        progress("Fabric配置", 50, 100)

    libs = resolve_libraries(profile)
    ParallelPool().download_libs(libs, game_dir, progress, base=50, span=50)
    if progress:
        progress("完成", 100, 100)
    return vid


def install_loader(
    game_dir: Path,
    mc_id: str,
    loader: str,
    mirror: str = "bmclapi",
    progress: Optional[ProgressCb] = None,
    java: Optional[str] = None,
) -> str:
    """按加载器安装：vanilla / fabric / quilt / neoforge / forge。返回最终版本 id。"""
    loader = (loader or "").strip().lower()
    if loader in ("", "vanilla", "原版"):
        install_version(game_dir, mc_id, mirror, progress)
        return mc_id
    if loader == "fabric":
        return install_fabric(game_dir, mc_id, mirror, progress)
    if loader == "quilt":
        return _install_quilt(game_dir, mc_id, progress)
    if loader in ("neoforge", "forge"):
        return _install_installer(game_dir, mc_id, loader, progress, java)
    raise NetError(f"不支持的加载器: {loader}")


def _install_quilt(
    game_dir: Path, mc_id: str, progress: Optional[ProgressCb] = None,
) -> str:
    """安装 Quilt Loader（用 Quilt meta 生成版本 json），返回版本 id。"""
    if mc_id not in list_local_versions(game_dir):
        raise NetError("请先安装原版版本")
    if progress:
        progress("Quilt配置", 0, 100)
    vers = get_json(f"https://meta.quiltmc.org/v3/versions/loader/{mc_id}")
    if not vers:
        raise NetError("Quilt 不支持该版本")
    lv = vers[0]["loader"]["version"]
    profile = get_json(f"https://meta.quiltmc.org/v3/versions/loader/{mc_id}/{lv}/profile/json")
    vid = profile.get("id") or f"quilt-loader-{lv}-{mc_id}"
    vdir = versions_dir(game_dir) / vid
    vdir.mkdir(parents=True, exist_ok=True)
    (vdir / f"{vid}.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
    if progress:
        progress("Quilt配置", 40, 100)
    libs = resolve_libraries(profile)
    ParallelPool().download_libs(libs, game_dir, progress, base=50, span=50)
    if progress:
        progress("完成", 100, 100)
    return vid


def _loader_version(mc_id: str, loader: str) -> str:
    """获取该 mc 版本对应加载器推荐/最新版本号。"""
    if loader == "forge":
        data = get_json("https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json")
        promos = data.get("promos") or {}
        return (promos.get(f"{mc_id}-forge-recommended")
                or promos.get(f"{mc_id}-forge-latest")
                or "")
    data = get_json(f"https://neoforged.net/api/mc/{mc_id}")
    if isinstance(data, list) and data:
        return str(data[0].get("version") or "")
    if isinstance(data, dict):
        vs = data.get("versions") or []
        if vs:
            return str(vs[0].get("version") or "")
    return ""


def _install_installer(
    game_dir: Path, mc_id: str, loader: str,
    progress: Optional[ProgressCb] = None, java: Optional[str] = None,
) -> str:
    """下载官方 installer jar 并运行 --installClient，完成 Forge / NeoForge 安装。"""
    import subprocess
    import tempfile
    if not java or not Path(java).is_file():
        raise NetError(f"安装 {loader} 需要 Java，请先在设置中确认 Java 路径")
    if progress:
        progress("获取版本", 5, 100)
    ver = _loader_version(mc_id, loader)
    if not ver:
        raise NetError(f"{loader} 暂不支持版本 {mc_id}")
    if loader == "forge":
        url = (f"https://maven.minecraftforge.net/net/minecraftforge/forge/"
               f"{mc_id}-{ver}/forge-{mc_id}-{ver}-installer.jar")
    else:
        url = (f"https://maven.neoforged.net/releases/net/neoforged/neoforge/"
               f"{ver}/neoforge-{ver}-installer.jar")
    if progress:
        progress("下载安装器", 10, 100)
    tmp = Path(tempfile.gettempdir()) / f"{loader}_{mc_id}_{ver}_installer.jar"
    net.download_file(
        url, tmp,
        progress=lambda d, t: progress(
            "下载安装器", 10 + int(55 * (d / t if t else 0)), 100))
    if progress:
        progress("运行安装器", 70, 100)
    r = subprocess.run(
        [java, "-jar", str(tmp), "--installClient", str(game_dir)],
        capture_output=True, text=True, timeout=300)
    tmp.unlink(missing_ok=True)
    if r.returncode != 0:
        raise NetError(f"{loader} 安装失败：{(r.stdout or r.stderr)[-300:]}")
    if progress:
        progress("完成", 100, 100)
    return f"{loader}-{mc_id}-{ver}"
