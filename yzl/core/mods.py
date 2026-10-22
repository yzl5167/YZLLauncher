"""模组中心：Modrinth 搜索 + 一键安装。"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from yzl.core.net import NetError, get_json

API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "YZLLauncher/1.0"}
CURATED = [
    ("fabric-api", "Fabric API", "大量模组的核心前置库"),
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
    slug: str; title: str; description: str; icon: Optional[str] = None

@dataclass
class ModFile:
    version: str; filename: str; url: str; size: int

def search_mods(query: str, mc_version: str = "1.21.1", limit: int = 20) -> list[ModInfo]:
    import json
    from urllib.parse import quote
    facets = json.dumps([[f"versions:{mc_version}"], ["project_type:mod"], ["categories:fabric"]], separators=(",", ":"))
    url = f"{API}/search?query={quote(query)}&facets={quote(facets)}&limit={limit}&index=relevance"
    hits = get_json(url, timeout=20).get("hits", [])
    return [ModInfo(slug=h.get("slug", ""), title=h.get("title", "未知"), description=(h.get("description") or "")[:120], icon=h.get("icon_url")) for h in hits]

def get_mod_versions(slug: str, mc_version: str, loader: str = "fabric") -> list[ModFile]:
    import json
    from urllib.parse import quote
    params = f"game_versions={quote(json.dumps([mc_version]))}&loaders={quote(json.dumps([loader]))}"
    data = get_json(f"{API}/project/{slug}/version?{params}", timeout=20)
    out = []
    for v in data[:6]:
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        out.append(ModFile(version=v.get("version_number", ""), filename=primary.get("filename", ""), url=primary.get("url", ""), size=primary.get("size", 0)))
    return out

def install_mod(mod: ModFile, game_dir: Path, progress=None) -> Path:
    from yzl.core.net import download_file
    mods_dir = game_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    dest = mods_dir / mod.filename
    if dest.exists():
        return dest
    if not download_file(mod.url, dest, progress=progress):
        raise NetError(f"模组下载失败: {mod.filename}")
    return dest
