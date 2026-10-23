"""整合包导入：把拖入启动器的 .zip/.mrpack 整合包解压识别，纳入已安装版本。"""
from __future__ import annotations

import os
import shutil
import tempfile
import zipfile
from pathlib import Path
from typing import Callable, Optional

from yzl.core.versions import versions_dir


def import_pack(
    path: str,
    game_dir: Path,
    progress: Optional[Callable[[int, int], None]] = None,
) -> list[str]:
    """导入整合包；返回纳入已安装版本的 id 列表（未找到版本则返回空列表）。"""
    src = Path(path)
    if not src.is_file() or src.suffix.lower() not in (".zip", ".mrpack"):
        return []
    tmp = Path(tempfile.mkdtemp(prefix="yzl_pack_"))
    imported: list[str] = []
    try:
        with zipfile.ZipFile(src) as z:
            total = len(z.infolist())
            names = z.namelist()
            for i, member in enumerate(names):
                z.extract(member, tmp)
                if progress and total:
                    progress(i + 1, total)
        # 扫描解压后的 versions/<id>/<id>.json，复制进启动器的版本目录
        vdir = tmp / "versions"
        if vdir.is_dir():
            for name in sorted(os.listdir(vdir)):
                vp = vdir / name
                if not vp.is_dir():
                    continue
                if not (vp / f"{name}.json").is_file():
                    continue
                dest = versions_dir(game_dir) / name
                if dest.exists():
                    shutil.rmtree(dest, ignore_errors=True)
                shutil.copytree(vp, dest)
                imported.append(name)
        return imported
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
