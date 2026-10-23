"""模组中心：Modrinth 搜索（全版本）+ 多加载器 + 兼容自动解析。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional, Sequence
from urllib.parse import quote

from yzl.core.net import NetError, get_json

API = "https://api.modrinth.com/v2"
HEADERS = {"User-Agent": "YZLLauncher/1.2 (Minecraft launcher)"}

# 支持的加载器（Modrinth loaders 枚举）
LOADERS = ["fabric", "forge", "neoforge", "quilt"]
LOADER_CN = {
    "fabric": "Fabric",
    "forge": "Forge",
    "neoforge": "NeoForge",
    "quilt": "Quilt",
}

# 生电向精选模组（slug 对应 Modrinth 项目；多数兼容 Fabric+Forge）
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


def search_mods(
    query: str,
    mc_version: Optional[str] = None,
    loaders: Sequence[str] = ("fabric",),
    limit: int = 20,
    offset: int = 0,
) -> list[ModInfo]:
    """全版本搜索：传入 mc_version 时按版本过滤，否则返回全部版本命中。
    不带 query 时返回该筛选条件下的全部项目（用于浏览全部模组库），offset 用于分页。"""
    facets = []
    if mc_version:
        facets.append([f"versions:{mc_version}"])
    if loaders:
        # Modrinth 将加载器归入 categories 维度
        facets.append([f"categories:{l}" for l in loaders])
    params = f"query={quote(query)}&facets={_fmt_facets(facets)}&limit={limit}&offset={offset}&index=relevance"
    url = f"{API}/search?{params}"
    data = get_json(url, timeout=20)
    hits = data.get("hits", [])
    out = []
    for h in hits:
        out.append(ModInfo(
            slug=h.get("slug", ""),
            title=h.get("title", "未知"),
            description=(h.get("description") or "")[:140],
            icon=h.get("icon_url"),
        ))
    return out


def _project_versions(slug: str) -> list[dict]:
    return get_json(f"{API}/project/{slug}/version", timeout=20)


def project_info(slug: str) -> dict:
    """项目详情（含 icon_url、作者、标题等）。"""
    return get_json(f"{API}/project/{slug}", timeout=20)


def all_mod_versions(
    slug: str,
    loaders: Optional[Sequence[str]] = None,
) -> list[ModFile]:
    """返回该模组全部版本（可按加载器过滤），每个含 game_versions / loaders。"""
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
        out.append(ModFile(
            version=v.get("version_number", ""),
            filename=primary.get("filename", ""),
            url=primary.get("url", ""),
            size=primary.get("size", 0),
            game_versions=v.get("game_versions") or [],
            loaders=ld,
            date=v.get("date_published", ""),
        ))
    out.sort(key=lambda m: _ts(m.date), reverse=True)
    return out


_versions_cache: dict = {}


def get_mod_versions(
    slug: str,
    mc_version: str,
    loaders: Sequence[str] = ("fabric",),
) -> list[ModFile]:
    """返回该模组中同时匹配 mc_version 与所选加载器的版本（按发布时间新→旧）。"""
    want_loaders = set(loaders)
    _ck = (slug, mc_version, tuple(loaders))
    _hit = _versions_cache.get(_ck)
    if _hit is not None:
        return _hit
    out: list[ModFile] = []
    for v in _project_versions(slug):
        gv = v.get("game_versions") or []
        ld = v.get("loaders") or []
        if mc_version not in gv:
            continue
        if not (want_loaders & set(ld)):
            continue
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        out.append(ModFile(
            version=v.get("version_number", ""),
            filename=primary.get("filename", ""),
            url=primary.get("url", ""),
            size=primary.get("size", 0),
            game_versions=gv,
            loaders=ld,
            date=v.get("date_published", ""),
        ))
    out.sort(key=lambda m: _ts(m.date), reverse=True)
    _versions_cache[_ck] = out
    return out


def _ts(iso: str) -> float:
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.timestamp()
    except Exception:
        return 0.0


def _compat_score(game_versions: list[str], mc_version: str) -> Optional[int]:
    """返回匹配优先级分数（越小越优先），不相关返回 None。"""
    if mc_version in game_versions:
        return 0
    minor = ".".join(mc_version.split(".")[:2])  # 1.21
    if minor in game_versions:
        return 1
    major = mc_version.split(".")[0]
    if any(g.startswith(major + ".") for g in game_versions):
        return 2
    # 同一大版本内的最接近小版本（如 1.20.x 找 1.20）
    if any(g.startswith("1.") for g in game_versions) and mc_version.startswith("1."):
        return 3
    return None


def pick_compatible(
    slug: str,
    mc_version: str,
    loaders: Sequence[str] = ("fabric",),
) -> Optional[ModFile]:
    """兼容自动解析：优先精确版本，其次同小版本/大版本的最新可用构建。"""
    want_loaders = set(loaders)
    scored: list[tuple[int, float, ModFile]] = []
    try:
        allv = _project_versions(slug)
    except Exception:
        return None
    for v in allv:
        gv = v.get("game_versions") or []
        ld = v.get("loaders") or []
        if not (want_loaders & set(ld)):
            continue
        score = _compat_score(gv, mc_version)
        if score is None:
            continue
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        scored.append((
            score,
            _ts(v.get("date_published", "")),
            ModFile(
                version=v.get("version_number", ""),
                filename=primary.get("filename", ""),
                url=primary.get("url", ""),
                size=primary.get("size", 0),
                game_versions=gv,
                loaders=ld,
                date=v.get("date_published", ""),
            ),
        ))
    if not scored:
        return None
    # 分数越小越优；同分取最新发布时间
    scored.sort(key=lambda x: (x[0], -x[1]))
    return scored[0][2]


def detect_loader(game_dir: Path, version_id: str) -> str:
    """根据已安装版本的 JSON 识别加载器（fabric/forge/neoforge/quilt/vanilla）。"""
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
    """取版本对应的原版 MC 版本号（Fabric/Forge 继承版返回其父版本）。"""
    from yzl.core import versions as vc
    try:
        data = vc.resolve_version(game_dir, version_id)
        parent = data.get("inheritsFrom")
        return parent or version_id
    except Exception:
        return version_id


def version_mods_dir(game_dir: Path, version_id: str) -> Path:
    """当前版本专属的模组目录 mods/{版本id}/。"""
    return game_dir / "mods" / (version_id or "")


def install_mod(
    mod: ModFile,
    game_dir: Path,
    version_id: str = "",
    progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """下载模组到「当前版本的模组文件夹」。有版本时装到 mods/{版本id}/，否则装到 mods/。"""
    from yzl.core.net import download_file

    mods_dir = version_mods_dir(game_dir, version_id) if version_id else game_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)
    dest = mods_dir / mod.filename
    if dest.exists():
        return dest
    ok = download_file(mod.url, dest, progress=progress)
    if not ok:
        raise NetError(f"模组下载失败: {mod.filename}")
    return dest


def prepare_mods(game_dir: Path, version_id: str) -> None:
    """启动前把当前版本的模组同步到游戏实际读取的 mods/ 根目录（不覆盖用户已放模组）。"""
    if not version_id:
        return
    src = version_mods_dir(game_dir, version_id)
    dest = game_dir / "mods"
    if not src.exists():
        return
    import shutil

    dest.mkdir(parents=True, exist_ok=True)
    for jar in src.glob("*.jar"):
        if not (dest / jar.name).exists():
            try:
                shutil.copy2(jar, dest / jar.name)
            except Exception:
                pass
