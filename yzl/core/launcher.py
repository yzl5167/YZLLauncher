"""启动引擎：解析版本参数、构建命令、拉起 Java 进程。"""
from __future__ import annotations

import glob
import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from yzl.constants import LAUNCHER_NAME, LAUNCHER_VERSION
from yzl.core import versions
from yzl.core.config import Config
from yzl.core.net import CURRENT_OS
from yzl.core.versions import (
    assets_dir,
    libraries_dir,
    natives_dir,
    resolve_version,
    versions_dir,
)

TOKEN = re.compile(r"\$\{([^}]+)\}")

# 推荐 JVM 参数（PCL/HMCL 同款思路）
RECOMMENDED_JVM = [
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+UseG1GC",
    "-XX:G1NewSizePercent=20",
    "-XX:G1ReservePercent=20",
    "-XX:MaxGCPauseMillis=50",
    "-XX:G1HeapRegionSize=32M",
]


class LaunchError(RuntimeError):
    pass


def find_java(custom: str = "", mc_version: str = "") -> Optional[str]:
    """优先返回内置的适配版本 Java；其次系统检测。"""
    if custom and Path(custom).exists():
        return custom
    if mc_version:
        try:
            from yzl.core import javamgr
            b = javamgr.builtin_java(mc_version)
            if b:
                return b
        except Exception:
            pass
    if CURRENT_OS == "windows":
        exe = "java.exe"
        roots = [
            os.environ.get("JAVA_HOME", ""),
            r"C:\Program Files\Java",
            r"C:\Program Files\Eclipse Adoptium",
            r"C:\Program Files\Microsoft",
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs"),
        ]
        for root in roots:
            if not root:
                continue
            for p in glob.glob(os.path.join(root, "*", "bin", exe)) + glob.glob(os.path.join(root, "bin", exe)):
                return p
        # PATH 兜底
        for p in os.environ.get("PATH", "").split(os.pathsep):
            cand = os.path.join(p, exe)
            if os.path.exists(cand):
                return cand
        return None
    # linux / mac
    for p in ("/usr/bin/java", "/usr/local/bin/java", "/opt/java/bin/java"):
        if os.path.exists(p):
            return p
    return None


def _classpath_sep() -> str:
    return ";" if CURRENT_OS == "windows" else ":"


@dataclass
class LaunchSpec:
    cmd: list[str] = field(default_factory=list)
    game_dir: Path = None  # type: ignore[assignment]
    version_id: str = ""
    env: dict = field(default_factory=dict)
    workdir: Path = None  # type: ignore[assignment]


def build_launch_spec(cfg: Config, version_id: str, account: dict) -> LaunchSpec:
    game_dir = cfg.game_dir()
    data = resolve_version(game_dir, version_id)

    # 继承自父版本（Fabric）时，父版本的核心文件即游戏本体
    parent_id = data.get("inheritsFrom") or version_id
    parent = resolve_version(game_dir, parent_id)

    jar = versions_dir(game_dir) / parent_id / f"{parent_id}.jar"
    if not jar.exists():
        raise LaunchError(f"游戏核心缺失: {parent_id}.jar")

    libs = versions.resolve_libraries(data)
    cp_parts = []
    for lib in libs:
        p = libraries_dir(game_dir) / lib.path
        if p.exists():
            cp_parts.append(str(p))
    cp_parts.append(str(jar))
    classpath = _classpath_sep().join(cp_parts)

    assets_root = assets_dir(game_dir)
    index_id = parent.get("assetIndex", {}).get("id") or parent.get("assets") or "legacy"
    natives = natives_dir(game_dir, parent_id)
    natives.mkdir(parents=True, exist_ok=True)

    tokens = {
        "auth_player_name": account.get("name", "Steve"),
        "auth_uuid": (account.get("uuid", "") or "").replace("-", ""),
        "auth_access_token": account.get("access_token") or account.get("uuid", "0") or "0",
        "auth_session": account.get("access_token") or account.get("uuid", "0") or "0",
        "version_name": data.get("id", version_id),
        "version_type": data.get("type", "release"),
        "game_directory": str(game_dir),
        "game_assets": str(assets_root / "virtual" / "legacy"),
        "assets_root": str(assets_root),
        "assets_index_name": index_id,
        "user_type": "msa" if account.get("type") == "microsoft" else "legacy",
        "natives_directory": str(natives),
        "launcher_name": LAUNCHER_NAME,
        "launcher_version": LAUNCHER_VERSION,
        "classpath": classpath,
        "resolution_width": str(cfg.get("width") or ""),
        "resolution_height": str(cfg.get("height") or ""),
    }

    def sub(text: str) -> str:
        def rep(m):
            key = m.group(1)
            return tokens.get(key, "")
        return TOKEN.sub(rep, text)

    memory = int(cfg.get("memory_mb") or 2048)
    java = find_java(cfg.get("java_path") or "", mc_version=parent_id)
    if not java:
        from yzl.core import javamgr
        raise LaunchError(f"未找到 Java！{parent_id} 需要 Java {javamgr.required_java(parent_id)}，"
                          f"可在「设置 → 内置 Java 版本」自动下载")

    jvm: list[str] = [java, f"-Xmx{memory}M", "-Xms{0}M".format(max(256, memory // 8))]
    jvm += RECOMMENDED_JVM
    if CURRENT_OS == "windows":
        jvm.append("-Dfile.encoding=UTF-8")

    args = data.get("arguments") or {}
    if args:
        for item in args.get("jvm", []):
            vals = _resolve_arg_item(item)
            jvm.extend([sub(v) for v in vals])
        # 去掉 -cp 占位后补真实 classpath（部分 JSON 自带 -cp ${classpath}）
        jvm = _inject_classpath(jvm, classpath)
        game_args = []
        for item in args.get("game", []):
            game_args.extend([sub(v) for v in _resolve_arg_item(item)])
    else:
        # 旧版（<1.13）：minecraftArguments 字符串
        legacy = data.get("minecraftArguments", "")
        legacy = legacy.replace("${auth_access_token}", tokens["auth_access_token"]) \
                       .replace("${auth_session}", tokens["auth_session"]) \
                       .replace("${auth_player_name}", tokens["auth_player_name"]) \
                       .replace("${auth_uuid}", tokens["auth_uuid"]) \
                       .replace("${version_name}", tokens["version_name"]) \
                       .replace("${game_directory}", tokens["game_directory"]) \
                       .replace("${game_assets}", tokens["game_assets"]) \
                       .replace("${assets_root}", tokens["assets_root"]) \
                       .replace("${assets_index_name}", tokens["assets_index_name"]) \
                       .replace("${user_type}", tokens["user_type"]) \
                       .replace("${natives_directory}", tokens["natives_directory"]) \
                       .replace("${launcher_name}", tokens["launcher_name"]) \
                       .replace("${launcher_version}", tokens["launcher_version"]) \
                       .replace("${classpath}", classpath) \
                       .replace("${resolution_width}", tokens["resolution_width"]) \
                       .replace("${resolution_height}", tokens["resolution_height"])
        game_args = [a for a in legacy.split(" ") if a]

    main_class = data.get("mainClass") or "net.minecraft.client.main.Main"
    # 旧版主类在 classpath 中的 launchwrapper 处理
    if main_class == "net.minecraft.launchwrapper.Launch":
        game_args.insert(0, "--tweakClass net.minecraft.launchwrapper.VanillaTweaker".split(" "))
        # flatten
        flat = []
        for g in game_args:
            if isinstance(g, list):
                flat.extend(g)
            else:
                flat.append(g)
        game_args = flat

    # 分辨率参数（旧版已内嵌，新版追加）
    if args:
        if cfg.get("width") and cfg.get("height"):
            game_args += ["--width", str(cfg.get("width")), "--height", str(cfg.get("height"))]

    cmd = jvm + [main_class] + game_args
    # 启动前把当前版本（原版号）的模组同步到游戏 mods/ 根目录
    try:
        from yzl.core import mods as mods_core
        mods_core.prepare_mods(game_dir, parent_id)
    except Exception:
        pass
    spec = LaunchSpec(cmd=cmd, game_dir=game_dir, version_id=version_id)
    spec.workdir = game_dir
    spec.env = dict(os.environ)
    return spec


def _resolve_arg_item(item) -> list[str]:
    if isinstance(item, str):
        return [item]
    if isinstance(item, dict):
        if versions.rules_allow(item.get("rules")):
            v = item.get("value")
            return v if isinstance(v, list) else [v]
    return []


def _inject_classpath(jvm: list[str], classpath: str) -> list[str]:
    """确保 -cp 后跟真实 classpath，且不重复注入。"""
    out: list[str] = []
    i = 0
    while i < len(jvm):
        arg = jvm[i]
        if arg == "-cp":
            out.append(arg)
            nxt = jvm[i + 1] if i + 1 < len(jvm) else ""
            out.append(nxt if nxt else classpath)
            i += 2
            continue
        out.append(arg)
        i += 1
    return out


def launch(
    spec: LaunchSpec,
    on_line: Optional[Callable[[str], None]] = None,
    on_exit: Optional[Callable[[int], None]] = None,
) -> subprocess.Popen:
    spec.workdir.mkdir(parents=True, exist_ok=True)
    creationflags = subprocess.CREATE_NO_WINDOW if CURRENT_OS == "windows" else 0
    proc = subprocess.Popen(
        spec.cmd,
        cwd=str(spec.workdir),
        env=spec.env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=creationflags,
        bufsize=1,
    )

    def _reader():
        try:
            for line in proc.stdout:
                if on_line:
                    on_line(line.rstrip("\n"))
        finally:
            rc = proc.wait()
            if on_exit:
                on_exit(rc)

    import threading

    threading.Thread(target=_reader, daemon=True).start()
    return proc
