"""光影中心：Modrinth 光影包（shader）搜索 + 精选 + 安装到 shaderpacks。"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote

from yzl.core.net import NetError, get_json

API = "https://api.modrinth.com/v2"

# 精选光影包（slug 对应 Modrinth shader 项目）
CURATED = [
    ("bsl-shaders", "BSL Shaders", "经典全能光影，画质与性能均衡，可调性强"),
    ("complementary-shaders", "Complementary Shaders", "口碑极佳的高画质光影，分 V4/V5"),
    ("complimentary-reimagined", "Complementary Reimagined", "Complementary 高画质重制版"),
    ("makeup-ultra-fast-shaders", "MakeUp Ultra Fast", "低配优化，帧率流畅的轻量光影"),
    ("solas-shader", "Solas Shader", "现代风格，色彩鲜艳通透"),
    ("phos-shader", "Phos Shader", "轻量唯美，性能友好"),
    ("seus", "SEUS", "经典写实光影系列"),
    ("iris", "Iris Shaders", "Fabric 光影加载器（前置模组）"),
]


@dataclass
class ShaderInfo:
    slug: str
    title: str
    description: str
    icon: Optional[str] = None


@dataclass
class ShaderFile:
    version: str
    filename: str
    url: str
    size: int
    mc_version: str = ""


def project_info(slug: str) -> dict:
    """光影项目详情（含 icon_url）。"""
    return get_json(f"{API}/project/{slug}", timeout=20)


def search_shaders(query: str, limit: int = 20, offset: int = 0) -> list[ShaderInfo]:
    facets = quote(json.dumps([["project_type:shader"]], separators=(",", ":")))
    url = f"{API}/search?query={quote(query)}&facets={facets}&limit={limit}&offset={offset}&index=relevance"
    data = get_json(url, timeout=20)
    hits = data.get("hits", [])
    return [
        ShaderInfo(
            slug=h.get("slug", ""),
            title=h.get("title", "未知"),
            description=(h.get("description") or "")[:140],
            icon=h.get("icon_url"),
        )
        for h in hits
    ]


def get_shader_files(slug: str, mc_version: Optional[str] = None) -> list[ShaderFile]:
    """光影包版本（zip 资源包）。传入 mc_version 时优先匹配兼容版本。"""
    url = f"{API}/project/{slug}/version"
    data = get_json(url, timeout=20)
    out: list[ShaderFile] = []
    for v in data:
        files = v.get("files") or []
        if not files:
            continue
        primary = next((f for f in files if f.get("primary")), files[0])
        gv = v.get("game_versions") or []
        mc = mc_version if mc_version in gv else (gv[0] if gv else "")
        out.append(ShaderFile(
            version=v.get("version_number", ""),
            filename=primary.get("filename", ""),
            url=primary.get("url", ""),
            size=primary.get("size", 0),
            mc_version=mc,
        ))
    return out[:8]


def install_shader(
    file: ShaderFile,
    game_dir: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Path:
    """下载到 {game_dir}/shaderpacks/。返回目标路径。"""
    from yzl.core.net import download_file

    d = game_dir / "shaderpacks"
    d.mkdir(parents=True, exist_ok=True)
    dest = d / file.filename
    if dest.exists():
        return dest
    ok = download_file(file.url, dest, progress=progress)
    if not ok:
        raise NetError(f"光影下载失败: {file.filename}")
    return dest
