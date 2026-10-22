"""模组中心：Modrinth 搜索（全版本）+ 多加载器 + 兼容自动解析。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Sequence
from urllib.parse import quote

from yzl.core.net import NetError, get_json

API = "https://api.modrinth.com/v2"
LOADERS = ["fabric", "forge", "neoforge", "quilt"]
LOADER_CN = {"fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge", "quilt": "Quilt"}

CURATED = [
    ("fabric-api", "Fabric API", "大量模组的核心前置库（Fabric）"),
    ("carpet", "Carpet", "生电必备：假人、tick 控制、规则开关"),
    ("lithium", "Lithium", "通用性能优化，不改红石行为"),
    ("starlight", "Starlight", "重写光照引擎，区块加载大幅提速"),
    ("sodium", "Sodium", "渲染优化，帧率显著提升"),
    ("krypton", "Krypton", "网络栈优化，多人更流畅"),
    ("ferrite-core", "FerriteCore", "内存占用优化"),
    ("modernfix", "ModernFix", "综合性能与加载修复"),
    ("spark", "Spark", "性能诊断：TPS/卡顿分析"),
    ("malilib", "MaLiLib", "输入辅助库（miniHUD/tweakeroo 前置）"),
]


@dataclass
class ModInfo:
    slug: str
    title: str
    description: str
    icon: Optional[str] = None


@dataclass
class ModFile:
    version: str
    filename: str
    url: str
    size: int
    game_versions: list[str] = None  # type: ignore[assignment]
    loaders: list[str] = None  # type: ignore[assignment]
    date: str = ""


def _fmt_facets(facets: Sequence[Sequence[str]]) -> str:
    return quote(json.dumps([list(f) for f in facets], separators=(",", ":")))


def search_mods(query: str, mc_version: Optional[str] = None, loaders: Sequence[str] = ("fabric",), limit: int = 20) -> list[ModInfo]:
    facets = []
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    if loaders:
        facets.append([f"categories:{l}" for l in loaders])
    params = f"query={quote(query)}&facets={_fmt_facets(facets)}&limit={limit}&index=relevance"
    url = f"{API}/search?{params}"
    data = get_json(url, timeout=20)
    hits = data.get("hits", [])
    out = []
    for h in hits:
        out.append(ModInfo(slug=h.get("slug", ""), title=h.get("title", "未知"), description=(h.get("description") or "")[:140], icon=h.get("icon_url")))
    return out


def _project_versions(slug: str) -> list[dict]:
    return get_json(f"{API}/project/{slug}/version", timeout=20)


def project_info(slug: str) -> dict:
    return get_json(f"{API}/project/{slug}", timeout=20)


def all_mod_versions(slug: str, loaders: Optional[Sequence[str]] = None) -> list[ModFile]:
    want = set(loaders) if loaders else None
    out: list[ModFile] = []
    for v in _project_versions(slug):
        ld = v.get("loaders") or []
        if want is not None and not (want & set(ld)):
            continue
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        out.append(ModFile(version=v.get("version_number", ""), filename=primary.get("filename", ""), url=primary.get("url", ""), size=primary.get("size", 0), game_versions=v.get("game_versions") or [], loaders=ld, date=v.get("date_published", "")))
    out.sort(key=lambda m: _ts(m.date), reverse=True)
    return out


def get_mod_versions(slug: str, mc_version: str, loaders: Sequence[str] = ("fabric",)) -> list[ModFile]:
    want = set(loaders)
    out: list[ModFile] = []
    for v in _project_versions(slug):
        gv = v.get("game_versions") or []
        ld = v.get("loaders") or []
        if mc_version not in gv or not (want & set(ld)):
            continue
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        out.append(ModFile(version=v.get("version_number", ""), filename=primary.get("filename", ""), url=primary.get("url", ""), size=primary.get("size", 0), game_versions=gv, loaders=ld, date=v.get("date_published", "")))
    out.sort(key=lambda m: _ts(m.date), reverse=True)
    return out


def _ts(iso: str) -> float:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0.0


def _compat_score(game_versions: list[str], mc_version: str) -> Optional[int]:
    if mc_version in game_versions:
        return 0
    minor = ".".join(mc_version.split(".")[:2])
    if minor in game_versions:
        return 1
    major = mc_version.split(".")[0]
    if any(g.startswith(major + ".") for g in game_versions):
        return 2
    if any(g.startswith("1.") for g in game_versions) and mc_version.startswith("1."):
        return 3
    return None


def pick_compatible(slug: str, mc_version: str, loaders: Sequence[str] = ("fabric",)) -> Optional[ModFile]:
    want = set(loaders)
    scored: list[tuple[int, float, ModFile]] = []
    try:
        allv = _project_versions(slug)
    except Exception:
        return None
    for v in allv:
        gv = v.get("game_versions") or []
        ld = v.get("loaders") or []
        if not (want & set(ld)):
            continue
        score = _compat_score(gv, mc_version)
        if score is None:
            continue
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        scored.append((score, _ts(v.get("date_published", "")), ModFile(version=v.get("version_number", ""), filename=primary.get("filename", ""), url=primary.get("url", ""), size=primary.get("size", 0), game_versions=gv, loaders=ld, date=v.get("date_published", ""))))
    if not scored:
        return None
    scored.sort(key=lambda x: (x[0], -x[1]))
    return scored[0][2]


def detect_loader(game_dir: Path, version_id: str) -> str:
    from yzl.core import versions as vc
    try:
        data = vc.resolve_version(game_dir, version_id)
    except Exception:
        return "vanilla"
    mc = ",".join(l.get("name", "") for l in data.get("libraries", []))
    if "fabricmc" in mc or "net.fabricmc" in data.get("mainClass", ""):
        return "fabric"
    if "neoforge" in mc or "net.neoforged" in data.get("mainClass", ""):
        return "neoforge"
    if "forge" in mc or "net.minecraftforge" in data.get("mainClass", ""):
        return "forge"
    if "quiltmc" in mc:
        return "quilt"
    return "vanilla"


def base_mc_version(game_dir: Path, version_id: str) -> str:
    from yzl.core import versions as vc
    try:
        data = vc.resolve_version(game_dir, version_id)
        return data.get("inheritsFrom") or version_id
    except Exception:
        return version_id


def install_mod(mod: ModFile, game_dir: Path, progress: Optional[Callable[[int, int], None]] = None) -> Path:
    from yzl.core.net import download_file
    mods_dir = game_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    dest = mods_dir / mod.filename
    if dest.exists():
        return dest
    ok = download_file(mod.url, dest, progress=progress)
    if not ok:
        raise NetError(f"模组下载失败: {mod.filename}")
    return dest
