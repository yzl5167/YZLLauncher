"""六个功能页：首页 / 版本管理 / 模组中心 / 光影中心 / 账户 / 设置 / 控制台。"""
from __future__ import annotations

import subprocess
import time
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk

from yzl.core import auth, javamgr, launcher as lc, mods as mods_core, versions as vc
from yzl.core import microsoft as ms_core, shaders as sh_core
from yzl.core.config import Config
from yzl.ui import theme
from yzl.ui.widgets import Card, GradientButton, attach_gradient, load_icon_photo, tag

LOADER_NAME = {
    "fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge",
    "quilt": "Quilt", "vanilla": "原版",
}


class Page(ctk.CTkFrame):
    def __init__(self, master, app) -> None:
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.app = app

    def on_show(self) -> None:  # pragma: no cover - 子类覆盖
        pass


# ---------------- 图标异步加载 ----------------
def async_set_icon(app, label: ctk.CTkLabel, url, size: int = 44, fallback_text: str = "◈") -> None:
    """后台下载图标并更新 label（无图标时显示占位字符）。"""

    def worker():
        return url

    def done(u):
        img = load_icon_photo(u, size) if u else None
        if img:
            label.configure(text="", image=img)
            label._img = img  # 持有引用防 GC
        else:
            label.configure(text=fallback_text)

    app.run_async(worker, done)


# ---------------- 版本选择弹窗（PCL 式自定义选版本） ----------------
class VersionPicker(ctk.CTkToplevel):
    def __init__(self, master, app, title: str, rows: list[dict]) -> None:
        """rows: [{version, desc, meta, size, extra, on_install}]"""
        super().__init__(master)
        self.app = app
        self.title(title)
        self.geometry("680x520")
        self.configure(fg_color=theme.BG)
        self.transient(master.winfo_toplevel())
        self.grab_set()
        self._photos = []

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(14, 10))
        ctk.CTkLabel(head, text=title, text_color=theme.TEXT,
                     font=(theme.ui_font(), 17, "bold")).pack(side="left")
        ctk.CTkButton(
            head, text="✕", width=34, height=28, corner_radius=9,
            fg_color="transparent", hover_color=theme.RED, text_color=theme.TEXT,
            font=(theme.ui_font(), 13), command=self.destroy,
        ).pack(side="right")

        box = ctk.CTkScrollableFrame(self, fg_color="transparent")
        box.pack(fill="both", expand=True, padx=12, pady=(0, 14))
        if not rows:
            ctk.CTkLabel(box, text="没有可用的版本", text_color=theme.SUB,
                         font=(theme.ui_font(), 13)).pack(pady=30)
        for r in rows:
            row = ctk.CTkFrame(box, fg_color=theme.CARD_2, corner_radius=10)
            row.pack(fill="x", pady=3)
            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=12, pady=8)
            ctk.CTkLabel(left, text=r["version"], text_color=theme.TEXT, anchor="w",
                         font=(theme.ui_font(), 13, "bold")).pack(anchor="w")
            meta = r.get("meta") or ""
            extra = r.get("extra") or ""
            sub = f"{meta}　{extra}"
            if sub.strip():
                ctk.CTkLabel(left, text=sub, text_color=theme.SUB, anchor="w",
                             font=(theme.ui_font(), 10)).pack(anchor="w", pady=(2, 0))
            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", padx=(4, 10))
            if r.get("badge"):
                tag(right, r["badge"], color=theme.GREEN).pack(side="left", padx=4)
            size = r.get("size")
            if size:
                ctk.CTkLabel(right, text=f"{size / 1048576:.1f}MB", text_color=theme.SUB,
                             font=(theme.ui_font(), 10)).pack(side="left", padx=8)
            ctk.CTkButton(
                right, text="安装", width=64, height=28, corner_radius=9,
                fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
                font=(theme.ui_font(), 11),
                command=lambda f=r["on_install"], w=row: self._do(f, w),
            ).pack(side="left")

    def _do(self, fn, widget) -> None:
        widget.configure(fg_color="#1E3A2F")
        self.app.run_async(fn)



# ================= 首页 =================
class HomePage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=28, pady=22)

        # 顶部横幅
        banner = Card(pad, corner_radius=20, border_width=0)
        banner.pack(fill="x", pady=(0, 18))
        cv = ctk.CTkCanvas(banner, height=96, bg=theme.CARD, highlightthickness=0)
        cv.pack(fill="x")
        attach_gradient(cv, "#101A2E", "#151E3A", corner=0)
        name = (self.app.cfg.current_account() or {}).get("name", "玩家")
        cv.create_text(28, 48, anchor="w", text=f"欢迎回来，{name}",
                       fill="#FFFFFF", font=(theme.ui_font(), 22, "bold"))
        cv.create_text(28, 76, anchor="w", text="YZL 启动器 · 生电向 · 高性能 · 纯净启动",
                       fill=theme.SUB, font=(theme.ui_font(), 12))

        row = ctk.CTkFrame(pad, fg_color="transparent")
        row.pack(fill="both", expand=True)

        # 左：启动区
        left = Card(row, corner_radius=20)
        left.pack(side="left", fill="both", expand=True, padx=(0, 12))
        ctk.CTkLabel(left, text="启动配置", text_color=theme.TEXT,
                     font=(theme.ui_font(), 16, "bold")).pack(anchor="w", padx=22, pady=(20, 14))

        self.ver_menu = ctk.CTkOptionMenu(
            left, values=[], width=280, height=40, corner_radius=12,
            fg_color=theme.CARD_2, button_color=theme.CARD_2, button_hover_color=theme.BORDER,
            text_color=theme.TEXT, dropdown_fg_color=theme.CARD_2,
            dropdown_hover_color=theme.BORDER, font=(theme.ui_font(), 13),
            dropdown_font=(theme.ui_font(), 13),
        )
        self.ver_menu.pack(anchor="w", padx=22, pady=4)
        ctk.CTkLabel(left, text="选择已安装版本", text_color=theme.SUB,
                     font=(theme.ui_font(), 11)).pack(anchor="w", padx=22, pady=(0, 12))

        self.acc_menu = ctk.CTkOptionMenu(
            left, values=[], width=280, height=40, corner_radius=12,
            fg_color=theme.CARD_2, button_color=theme.CARD_2, button_hover_color=theme.BORDER,
            text_color=theme.TEXT, dropdown_fg_color=theme.CARD_2,
            dropdown_hover_color=theme.BORDER, font=(theme.ui_font(), 13),
            dropdown_font=(theme.ui_font(), 13),
        )
        self.acc_menu.pack(anchor="w", padx=22, pady=4)
        ctk.CTkLabel(left, text="选择账户（离线 / 正版）", text_color=theme.SUB,
                     font=(theme.ui_font(), 11)).pack(anchor="w", padx=22, pady=(0, 16))

        self.launch_btn = GradientButton(
            left, text="启 动 游 戏", command=self._launch,
            width=300, height=64, corner=22, font_size=20,
        )
        self.launch_btn.pack(anchor="w", padx=22, pady=8)

        quick = ctk.CTkFrame(left, fg_color="transparent")
        quick.pack(anchor="w", padx=22, pady=(6, 20))
        for text, cmd in (("打开游戏目录", self._open_gamedir), ("打开模组目录", self._open_modsdir)):
            ctk.CTkButton(
                quick, text=text, width=120, height=34, corner_radius=12,
                fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT,
                font=(theme.ui_font(), 12), command=cmd,
            ).pack(side="left", padx=(0, 10))

        # 右：版本详情
        right = Card(row, width=320, corner_radius=20)
        right.pack(side="right", fill="y", padx=(12, 0))
        right.pack_propagate(False)
        ctk.CTkLabel(right, text="版本详情", text_color=theme.TEXT,
                     font=(theme.ui_font(), 16, "bold")).pack(anchor="w", padx=20, pady=(20, 10))
        self.detail = ctk.CTkLabel(
            right, text="", text_color=theme.SUB, justify="left", anchor="w",
            font=(theme.ui_font(), 12),
        )
        self.detail.pack(anchor="w", padx=20, pady=4)
        self.java_status = ctk.CTkLabel(
            right, text="", text_color=theme.GREEN, justify="left", anchor="w",
            font=(theme.ui_font(), 12),
        )
        self.java_status.pack(anchor="w", padx=20, pady=(6, 4))
        self.java_dl_btn = ctk.CTkButton(
            right, text="⬇ 下载所需 Java", width=180, height=34, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN,
            font=(theme.ui_font(), 12), command=self._dl_needed_java,
        )
        self.java_dl_btn.pack(anchor="w", padx=20, pady=(0, 6))
        ctk.CTkLabel(
            right, text="提示：1.21+ 需要 Java 21；新版（25.x/26.x）需要 Java 25；\n生电请优先安装 Fabric + Carpet。",
            text_color=theme.SUB, justify="left", anchor="w",
            font=(theme.ui_font(), 11), fg_color=theme.CARD_2, corner_radius=10,
            padx=12, pady=10,
        ).pack(anchor="w", padx=20, pady=(12, 12))

        self._refresh()

    def _refresh(self) -> None:
        cfg = self.app.cfg
        local = vc.list_local_versions(cfg.game_dir())
        cur = cfg.get("current_version")
        if cur not in local:
            cur = local[0] if local else None
            if cur:
                cfg.set("current_version", cur)
        self.ver_menu.configure(values=local or ["（未安装版本）"])
        self.ver_menu.set(cur or "（未安装版本）")

        accs = cfg.accounts()
        labels = [f"{a['name']}（{'正版' if a.get('type') == 'microsoft' else '离线'}）" for a in accs] or ["（未添加账户）"]
        self.acc_menu.configure(values=labels)
        cur_acc = cfg.current_account()
        self.acc_menu.set(
            f"{cur_acc['name']}（{'正版' if cur_acc.get('type') == 'microsoft' else '离线'}）"
            if cur_acc else "（未添加账户）"
        )

        self._update_detail(cur)

    def _update_detail(self, vid: str | None) -> None:
        if not vid:
            self.detail.configure(text="尚未选择版本")
            return
        try:
            data = vc.resolve_version(self.app.cfg.game_dir(), vid)
            parent = data.get("inheritsFrom") or vid
            pdata = vc.load_version_json(self.app.cfg.game_dir(), parent)
            jv = pdata.get("javaVersion", {}).get("majorVersion", "?")
            self.detail.configure(
                text=f"版本　　{data.get('id')}\n"
                     f"类型　　{data.get('type', 'release')}\n"
                     f"核心　　{parent}\n"
                     f"Java　　{'{0}'.format(jv)}\n"
                     f"内存　　{int(self.app.cfg.get('memory_mb'))} MB",
            )
            self._update_java_status(parent)
        except Exception:
            self.detail.configure(text="版本信息读取失败")

    def _update_java_status(self, parent_id: str) -> None:
        """首页显示当前版本所需 Java 的就绪状态，并提供一键下载。"""
        try:
            gd = self.app.cfg.game_dir()
            need = javamgr.required_java(parent_id, gd)
            self._java_need = need
            if javamgr.list_installed().get(need):
                self.java_status.configure(text=f"所需 Java {need} ✓ 已就绪", text_color=theme.GREEN)
                self.java_dl_btn.pack_forget()
            else:
                self.java_status.configure(text=f"缺少 Java {need}（点下方按钮自动下载）", text_color=theme.AMBER)
                self.java_dl_btn.pack(anchor="w", padx=20, pady=(0, 6))
        except Exception:
            self.java_status.configure(text="", text_color=theme.SUB)
            self.java_dl_btn.pack_forget()

    def _dl_needed_java(self) -> None:
        need = getattr(self, "_java_need", None)
        if not need:
            self.app.notify("无需下载", "当前版本所需 Java 已就绪")
            return
        self.app.set_status(f"正在下载 Java {need}…", 0.05)

        def work():
            return javamgr.download(need, progress=lambda d, t: self.app.set_status(
                f"正在下载 Java {need} {int(d / t * 100) if t else 0}%", d / t if t else 0.05))

        def done(folder):
            self.app.clear_progress()
            self.app.show_success("Java 已装好", f"Java {need} 已就绪，现在可以点「启动游戏」了")
            self._refresh()

        def err(e):
            self.app.clear_progress()
            self.app.show_error("Java 下载失败", f"Java {need} 下载失败：\n{str(e)}")

        self.app.run_async(work, done, err)

    def _launch(self) -> None:
        cfg = self.app.cfg
        try:
            self._launch_inner(cfg)
        except Exception as e:  # noqa: BLE001 - 保证任何启动错误都不静默
            import traceback
            self._log_error("".join(traceback.format_exc()))
            self.app.clear_progress()
            self.app.show_error("启动异常", f"{str(e)}\n\n详情已写入 yzl_error.log")

    def _log_error(self, tb: str) -> None:
        try:
            import datetime
            from yzl.constants import app_root
            with open(app_root() / "yzl_error.log", "a", encoding="utf-8") as f:
                f.write(f"\n===== {datetime.datetime.now()} =====\n{tb}\n")
        except Exception:
            pass

    def _launch_inner(self, cfg) -> None:
        if self.app._launching:
            self.app.notify("已在运行", "游戏进程正在运行中")
            return
        vid = self.ver_menu.get()
        acc_label = self.acc_menu.get()
        if not vid or vid.startswith("（"):
            self.app.notify("未选择版本", "请先到「版本管理」安装一个版本")
            return
        if not acc_label or acc_label.startswith("（"):
            self.app.notify("未添加账户", "请先到「账户」添加一个账户")
            return
        acc = next(
            (a for a in cfg.accounts()
             if f"{a['name']}（{'正版' if a.get('type') == 'microsoft' else '离线'}）" == acc_label),
            None,
        )
        if not acc:
            self.app.notify("账户无效", "请重新选择账户")
            return
        # Java 自动确保：缺失则自动下载所需版本（Java 8/17/21 等）
        parent_id = vid
        try:
            parent_id = (vc.resolve_version(cfg.game_dir(), vid) or {}).get("inheritsFrom") or vid
        except Exception:
            pass
        gd = cfg.game_dir()
        jpath = lc.find_java(cfg.get("java_path") or "", mc_version=parent_id, game_dir=gd)
        if not jpath:
            need = javamgr.required_java(parent_id, gd)
            self.app.set_status(f"正在自动下载 Java {need}（{parent_id} 需要）…", 0.05)

            def work():
                return javamgr.ensure(
                    parent_id, auto_download=True, game_dir=gd,
                    progress=lambda d, t: self.app.set_status(
                        f"正在下载 Java {need} {int(d / t * 100) if t else 0}%", d / t if t else 0.05))

            def done(j):
                if j:
                    self._do_launch(cfg, vid, acc)
                else:
                    self.app.clear_progress()
                    self.app.show_error("Java 下载失败",
                                        f"无法自动下载 Java {need}。\n请到「设置 → 内置 Java 版本」手动下载，或手动指定 Java 路径。")

            self.app.run_async(work, done)
            return
        self._do_launch(cfg, vid, acc)

    def _do_launch(self, cfg, vid, acc) -> None:
        self.app.set_status(f"正在准备启动 {vid}…", 0.85)
        try:
            spec = lc.build_launch_spec(cfg, vid, acc)
        except Exception as e:  # noqa: BLE001
            import traceback
            self._log_error(f"[build_launch_spec] {vid}: {e}\n{traceback.format_exc()}")
            self.app.clear_progress()
            self.app.show_error("无法启动", f"{vid} 启动失败：\n{str(e)}")
            return
        self.app._launching = True
        self.app.switch("console")
        self.app.clear_log()
        self.app.add_log(f"[YZL] 启动版本 {vid} · 内存 {cfg.get('memory_mb')}MB")
        self.app.add_log(f"[YZL] 游戏目录 {cfg.game_dir()}")
        self.app.add_log("[YZL] 启动命令:")
        for part in spec.cmd:
            self.app.add_log(f"  {part}")
        self.app.set_status("正在启动游戏…", 0.98)

        def on_exit(rc: int) -> None:
            self.app._launching = False
            self.app.clear_progress()
            self.app.add_log(f"[YZL] 游戏已退出（代码 {rc}）")

        try:
            proc = lc.launch(spec, on_line=self.app.add_log, on_exit=on_exit)
            self.app._proc = proc
            self.app.set_status("游戏运行中…", 1.0)
        except Exception as e:  # noqa: BLE001
            import traceback
            self._log_error(f"[launch] {vid}: {e}\n{traceback.format_exc()}")
            self.app._launching = False
            self.app.clear_progress()
            self.app.show_error("启动失败", str(e))

    def _open_gamedir(self) -> None:
        d = self.app.cfg.game_dir()
        d.mkdir(parents=True, exist_ok=True)
        _open_path(d)

    def _open_modsdir(self) -> None:
        d = self.app.cfg.game_dir() / "mods"
        d.mkdir(parents=True, exist_ok=True)
        _open_path(d)


# ================= 版本管理 =================
class VersionsPage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=24, pady=18)

        head = ctk.CTkFrame(pad, fg_color="transparent")
        head.pack(fill="x", pady=(0, 14))
        ctk.CTkLabel(head, text="版本管理", text_color=theme.TEXT,
                     font=(theme.ui_font(), 20, "bold")).pack(side="left")
        ctk.CTkButton(
            head, text="↻ 刷新", width=90, height=34, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 12), command=self._load_all,
        ).pack(side="right")

        body = ctk.CTkFrame(pad, fg_color="transparent")
        body.pack(fill="both", expand=True)

        # 已安装
        left = Card(body, width=300, corner_radius=18)
        left.pack(side="left", fill="y", padx=(0, 14))
        left.pack_propagate(False)
        ctk.CTkLabel(left, text="已安装", text_color=theme.TEXT,
                     font=(theme.ui_font(), 15, "bold")).pack(anchor="w", padx=16, pady=(14, 8))
        self.local_box = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.local_box.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # 在线版本
        right = Card(body, corner_radius=18)
        right.pack(side="right", fill="both", expand=True)
        top = ctk.CTkFrame(right, fg_color="transparent")
        top.pack(fill="x", padx=16, pady=(14, 8))
        ctk.CTkLabel(top, text="在线版本（全部 Java 版历史版本）", text_color=theme.TEXT,
                     font=(theme.ui_font(), 15, "bold")).pack(side="left")
        self.filter = ctk.CTkSegmentedButton(
            top, values=["全部", "正式版", "快照", "远古"], height=30, corner_radius=10,
            fg_color=theme.CARD_2, selected_color=theme.BORDER, selected_hover_color=theme.BORDER,
            text_color=theme.SUB, font=(theme.ui_font(), 12), command=lambda _: self._render_online(),
        )
        self.filter.pack(side="right")
        self.search = ctk.CTkEntry(
            right, placeholder_text="搜索版本号…", height=34, corner_radius=10,
            fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 12),
        )
        self.search.pack(fill="x", padx=16, pady=(0, 8))
        self.search.bind("<KeyRelease>", lambda e: self._render_online())
        self.online_box = ctk.CTkScrollableFrame(right, fg_color="transparent")
        self.online_box.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._load_local()
        self._load_all()

    def _load_local(self) -> None:
        for w in self.local_box.winfo_children():
            w.destroy()
        for vid in sorted(vc.list_local_versions(self.app.cfg.game_dir()), key=str.lower):
            row = ctk.CTkFrame(self.local_box, fg_color=theme.CARD_2, corner_radius=10)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=vid, text_color=theme.TEXT, anchor="w",
                         font=(theme.ui_font(), 12)).pack(side="left", padx=10, pady=8)
            ctk.CTkButton(
                row, text="启动", width=52, height=26, corner_radius=8,
                fg_color=theme.CARD_2, hover_color=theme.CYAN,
                text_color=theme.CYAN, font=(theme.ui_font(), 11),
                command=lambda v=vid: self._launch_version(v),
            ).pack(side="right", padx=(2, 8), pady=6)
            ctk.CTkButton(
                row, text="删", width=34, height=26, corner_radius=8,
                fg_color=theme.CARD_2, hover_color=theme.RED,
                text_color=theme.SUB, font=(theme.ui_font(), 11),
                command=lambda v=vid: self._delete_version(v),
            ).pack(side="right", pady=6)

    def _launch_version(self, vid: str) -> None:
        self.app.cfg.set("current_version", vid)
        self.app.switch("home")

    def _delete_version(self, vid: str) -> None:
        import shutil
        shutil.rmtree(vc.versions_dir(self.app.cfg.game_dir()) / vid, ignore_errors=True)
        self._load_local()

    def _load_all(self) -> None:
        self.app.set_status("正在获取版本清单…", 0.05)

        def fn():
            return vc.all_versions("bmclapi")

        def done(versions: list[dict]) -> None:
            self._all = versions
            self._render_online()
            self.app.clear_progress()

        self.app.run_async(fn, done)

    def _render_online(self) -> None:
        if not hasattr(self, "_all") or not self._all:
            return
        f = self.filter.get()
        kw = self.search.get().strip().lower()
        items = []
        for v in self._all:
            vid = v.get("id", "")
            typ = v.get("type", "release")
            if f == "正式版" and typ != "release":
                continue
            if f == "快照" and typ not in ("snapshot", "old_beta", "old_alpha"):
                continue
            if f == "远古" and typ not in ("old_beta", "old_alpha"):
                continue
            if kw and kw not in vid.lower():
                continue
            items.append(v)
            if len(items) >= 90:
                break
        for w in self.online_box.winfo_children():
            w.destroy()
        local = vc.list_local_versions(self.app.cfg.game_dir())
        for v in items:
            vid = v.get("id", "")
            row = ctk.CTkFrame(self.online_box, fg_color=theme.CARD_2, corner_radius=10)
            row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=vid, text_color=theme.TEXT, anchor="w",
                         font=(theme.ui_font(), 12)).pack(side="left", padx=10, pady=8)
            tag(row, v.get("type", ""), color=theme.CYAN if v.get("type") == "release" else theme.AMBER
                if v.get("type") == "snapshot" else theme.SUB).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=(v.get("releaseTime") or "")[:10], text_color=theme.SUB,
                         font=(theme.ui_font(), 10)).pack(side="left", padx=6)
            if vid in local:
                tag(row, "已安装", color=theme.GREEN).pack(side="right", padx=8)
            else:
                ctk.CTkButton(
                    row, text="安装", width=54, height=26, corner_radius=8,
                    fg_color=theme.CARD_2, hover_color=theme.CYAN,
                    text_color=theme.CYAN, font=(theme.ui_font(), 11),
                    command=lambda v=vid: self._install_version(v, fabric=False),
                ).pack(side="right", padx=(2, 8), pady=6)
                ctk.CTkButton(
                    row, text="装Fabric", width=70, height=26, corner_radius=8,
                    fg_color=theme.CARD_2, hover_color=theme.VIOLET,
                    text_color=theme.VIOLET, font=(theme.ui_font(), 11),
                    command=lambda v=vid: self._install_version(v, fabric=True),
                ).pack(side="right", pady=6)

    def _install_version(self, vid: str, fabric: bool) -> None:
        cfg = self.app.cfg

        def progress(stage: str, done: int, total: int) -> None:
            self.app.set_status(f"正在安装 {vid} · {stage} {done}%", done / 100)

        def work():
            vc.install_version(cfg.game_dir(), vid, cfg.get("mirror"), progress)
            if fabric:
                vc.install_fabric(cfg.game_dir(), vid, cfg.get("mirror"), progress)

        def done(_):
            self.app.clear_progress()
            self.app.show_success("安装完成", f"版本 {vid} 已安装成功" + ("（含 Fabric）" if fabric else ""))
            self._load_local()
            self._render_online()

        self.app.run_async(work, done)


# ================= 模组中心 =================
class ModsPage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=24, pady=18)

        head = ctk.CTkFrame(pad, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(head, text="模组中心", text_color=theme.TEXT,
                     font=(theme.ui_font(), 20, "bold")).pack(side="left")
        ctk.CTkLabel(head, text="数据来源 Modrinth · 全版本 · 可自选加载器与版本",
                     text_color=theme.SUB, font=(theme.ui_font(), 11)).pack(side="left", padx=12, pady=6)
        ctk.CTkButton(
            head, text="📂 打开模组目录", width=110, height=34, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 12), command=lambda: _open_path(self.app.cfg.game_dir() / "mods"),
        ).pack(side="right")

        # 目标版本 + 加载器（版本固定跟随「首页当前所选版本」，自动适配，无需手动选）
        cfg = self.app.cfg
        cur_base = mods_core.base_mc_version(cfg.game_dir(), cfg.get("current_version") or "")
        if not cur_base:
            cur_base = "1.21.1"
        self._mc_version = cur_base

        ctrl = ctk.CTkFrame(pad, fg_color="transparent")
        ctrl.pack(fill="x", pady=(0, 10))
        ctk.CTkLabel(ctrl, text=f"当前版本 {cur_base}", text_color=theme.CYAN,
                     font=(theme.ui_font(), 13, "bold")).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(ctrl, text="加载器", text_color=theme.SUB,
                     font=(theme.ui_font(), 12)).pack(side="left", padx=(0, 8))
        auto_loader = mods_core.detect_loader(cfg.game_dir(), cfg.get("current_version") or "")
        self.loader_menu = ctk.CTkSegmentedButton(
            ctrl, values=["Fabric", "Forge", "NeoForge", "Quilt"], height=34, corner_radius=10,
            fg_color=theme.CARD_2, selected_color=theme.VIOLET, selected_hover_color=theme.VIOLET,
            text_color=theme.SUB, font=(theme.ui_font(), 12),
        )
        default_loader = {"fabric": "Fabric", "forge": "Forge", "neoforge": "NeoForge", "quilt": "Quilt",
                          "vanilla": "Fabric"}.get(auto_loader, "Fabric")
        self.loader_menu.set(default_loader)
        self.loader_menu.pack(side="left", padx=(0, 16))

        # 搜索
        search_row = ctk.CTkFrame(pad, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, 12))
        self.mod_search = ctk.CTkEntry(
            search_row, placeholder_text="搜索模组（如 lithium / carpet / sodium）…", height=36, corner_radius=10,
            fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 12),
        )
        self.mod_search.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            search_row, text="🔍 搜索", width=96, height=36, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
            font=(theme.ui_font(), 12), command=self._search,
        ).pack(side="left", padx=(10, 0))
        ctk.CTkButton(
            search_row, text="精选", width=66, height=36, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB,
            font=(theme.ui_font(), 12), command=self._curated,
        ).pack(side="left", padx=(8, 0))

        self.list_box = ctk.CTkScrollableFrame(pad, fg_color="transparent")
        self.list_box.pack(fill="both", expand=True)
        self._curated()

    def _loader(self) -> str:
        return self.loader_menu.get().lower()

    def _mc(self) -> str:
        return getattr(self, "_mc_version", "") or ""

    def _curated(self) -> None:
        for w in self.list_box.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.list_box,
            text=f"精选生电模组 · 适配 {self._mc()} · {self._loader()}（点「选择版本」可自选具体版本）",
            text_color=theme.SUB, font=(theme.ui_font(), 11),
        ).pack(anchor="w", padx=6, pady=(0, 6))
        for slug, title, desc in mods_core.CURATED:
            self._add_mod_card(slug, title, desc, fetch_icon=False)

    def _search(self) -> None:
        q = self.mod_search.get().strip()
        if not q:
            self._curated()
            return
        self.app.set_status(f"正在搜索模组（{self._mc()}·{self._loader()}）…", 0.1)

        def work():
            return mods_core.search_mods(q, self._mc(), (self._loader(),))

        def done(mods):
            self.app.clear_progress()
            for w in self.list_box.winfo_children():
                w.destroy()
            if not mods:
                ctk.CTkLabel(self.list_box, text="没有找到适配该版本/加载器的模组（试试切换加载器）",
                             text_color=theme.SUB, font=(theme.ui_font(), 13)).pack(pady=20)
                return
            for m in mods:
                self._add_mod_card(m.slug, m.title, m.description, m.icon)

        self.app.run_async(work, done)

    def _add_mod_card(self, slug: str, title: str, desc: str, icon: str | None = None,
                      fetch_icon: bool = True) -> None:
        card = Card(self.list_box, corner_radius=14)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        # 图标
        icon_label = ctk.CTkLabel(
            inner, text="◈", width=48, height=48, corner_radius=10,
            fg_color=theme.CARD_2, text_color=theme.CYAN,
            font=(theme.ui_font(), 20),
        )
        icon_label.pack(side="left", padx=(0, 12))
        body = ctk.CTkFrame(inner, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(body, text=title, text_color=theme.TEXT, anchor="w",
                     font=(theme.ui_font(), 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(body, text=desc or "（无简介）", text_color=theme.SUB, anchor="w",
                     font=(theme.ui_font(), 11), wraplength=460, justify="left").pack(anchor="w", pady=(4, 0))
        ctk.CTkButton(
            inner, text="选择版本 ▸", width=100, height=32, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
            font=(theme.ui_font(), 12),
            command=lambda s=slug, t=title: self._pick_version(s, t),
        ).pack(side="right", anchor="s", padx=(8, 0))

        if icon:
            async_set_icon(self.app, icon_label, icon, 40)
        elif fetch_icon:
            def _fetch():
                try:
                    return mods_core.project_info(slug).get("icon_url")
                except Exception:
                    return None
            def _done(u):
                async_set_icon(self.app, icon_label, u, 40)
            self.app.run_async(_fetch, _done)

    def _pick_version(self, slug: str, title: str) -> None:
        loader = self._loader()
        mc = self._mc()
        self.app.set_status(f"正在获取 {title} 的版本列表…", 0.1)

        def work():
            return mods_core.all_mod_versions(slug, (loader,))

        def done(files):
            self.app.clear_progress()
            for w in self.list_box.winfo_children():
                w.destroy()
            if not files:
                ctk.CTkLabel(self.list_box, text=f"{title} 没有适配 {loader} 的版本（试试切换加载器）",
                             text_color=theme.SUB, font=(theme.ui_font(), 13)).pack(pady=20)
                return
            head = ctk.CTkFrame(self.list_box, fg_color="transparent")
            head.pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(head, text=f"选择 {title} 的版本 · {loader}", text_color=theme.TEXT,
                         font=(theme.ui_font(), 13, "bold")).pack(side="left")
            ctk.CTkButton(
                head, text="◀ 返回", width=72, height=28, corner_radius=8,
                fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB,
                font=(theme.ui_font(), 11), command=self._curated,
            ).pack(side="right")
            for f in files[:40]:
                row = ctk.CTkFrame(self.list_box, fg_color=theme.CARD_2, corner_radius=10)
                row.pack(fill="x", pady=3)
                left = ctk.CTkFrame(row, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True, padx=10, pady=8)
                ctk.CTkLabel(left, text=f.version, text_color=theme.TEXT, anchor="w",
                             font=(theme.ui_font(), 12, "bold")).pack(anchor="w")
                gv = ",".join(f.game_versions or [])[:46]
                ld = "/".join(LOADER_NAME.get(x, x) for x in (f.loaders or []))[:30]
                ctk.CTkLabel(left, text=f"MC {gv} · {ld}", text_color=theme.SUB, anchor="w",
                             font=(theme.ui_font(), 10)).pack(anchor="w", pady=(2, 0))
                right = ctk.CTkFrame(row, fg_color="transparent")
                right.pack(side="right", padx=(4, 10))
                if mc in (f.game_versions or []):
                    tag(right, "✓适配", color=theme.GREEN).pack(side="left", padx=4)
                ctk.CTkLabel(right, text=f"{f.size / 1048576:.1f}MB", text_color=theme.SUB,
                             font=(theme.ui_font(), 10)).pack(side="left", padx=6)
                ctk.CTkButton(
                    right, text="下载", width=58, height=26, corner_radius=8,
                    fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
                    font=(theme.ui_font(), 11),
                    command=lambda mf=f: self._install_file(mf, title),
                ).pack(side="left")

        self.app.run_async(work, done)

    def _install_file(self, f, title: str) -> None:
        vid = self.app.cfg.get("current_version") or ""
        base = mods_core.base_mc_version(self.app.cfg.game_dir(), vid)

        def work():
            def p(done: int, total: int) -> None:
                self.app.set_status(f"正在下载 {f.filename}", done / total if total else 0.2)
            return mods_core.install_mod(f, self.app.cfg.game_dir(), base, p)

        def done(path: Path) -> None:
            self.app.clear_progress()
            self.app.show_success("模组已下载", f"{title}\n已保存到 mods/{base}/{path.name}\n已适配 {base}，启动游戏自动加载")

        self.app.run_async(work, done)


# ================= 光影中心 =================
class ShadersPage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=24, pady=18)

        head = ctk.CTkFrame(pad, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(head, text="光影中心", text_color=theme.TEXT,
                     font=(theme.ui_font(), 20, "bold")).pack(side="left")
        ctk.CTkLabel(head, text="数据来源 Modrinth · 下载光影包到 shaderpacks",
                     text_color=theme.SUB, font=(theme.ui_font(), 11)).pack(side="left", padx=12, pady=6)
        ctk.CTkButton(
            head, text="📂 打开光影目录", width=110, height=34, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 12), command=lambda: _open_path(self.app.cfg.game_dir() / "shaderpacks"),
        ).pack(side="right")

        search_row = ctk.CTkFrame(pad, fg_color="transparent")
        search_row.pack(fill="x", pady=(0, 12))
        self.shader_search = ctk.CTkEntry(
            search_row, placeholder_text="搜索光影（如 BSL / Complementary / SEUS）…", height=36, corner_radius=10,
            fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 12),
        )
        self.shader_search.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            search_row, text="🔍 搜索", width=96, height=36, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
            font=(theme.ui_font(), 12), command=self._search,
        ).pack(side="left", padx=(10, 0))
        ctk.CTkButton(
            search_row, text="精选", width=66, height=36, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB,
            font=(theme.ui_font(), 12), command=self._curated,
        ).pack(side="left", padx=(8, 0))

        self.list_box = ctk.CTkScrollableFrame(pad, fg_color="transparent")
        self.list_box.pack(fill="both", expand=True)
        self._curated()

    def _curated(self) -> None:
        for w in self.list_box.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.list_box, text="精选光影包（点「选择版本」可自选具体版本）",
            text_color=theme.SUB, font=(theme.ui_font(), 11),
        ).pack(anchor="w", padx=6, pady=(0, 6))
        for slug, title, desc in sh_core.CURATED:
            self._add_card(slug, title, desc, fetch_icon=False)

    def _search(self) -> None:
        q = self.shader_search.get().strip()
        if not q:
            self._curated()
            return
        self.app.set_status("正在搜索光影…", 0.1)

        def work():
            return sh_core.search_shaders(q)

        def done(shaders):
            self.app.clear_progress()
            for w in self.list_box.winfo_children():
                w.destroy()
            if not shaders:
                ctk.CTkLabel(self.list_box, text="没有找到光影包", text_color=theme.SUB,
                             font=(theme.ui_font(), 13)).pack(pady=20)
                return
            for s in shaders:
                self._add_card(s.slug, s.title, s.description, s.icon)

        self.app.run_async(work, done)

    def _add_card(self, slug: str, title: str, desc: str, icon: str | None = None,
                  fetch_icon: bool = True) -> None:
        card = Card(self.list_box, corner_radius=14)
        card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=12, pady=10)
        icon_label = ctk.CTkLabel(
            inner, text="◈", width=48, height=48, corner_radius=10,
            fg_color=theme.CARD_2, text_color=theme.PINK,
            font=(theme.ui_font(), 20),
        )
        icon_label.pack(side="left", padx=(0, 12))
        body = ctk.CTkFrame(inner, fg_color="transparent")
        body.pack(side="left", fill="x", expand=True)
        ctk.CTkLabel(body, text=title, text_color=theme.TEXT, anchor="w",
                     font=(theme.ui_font(), 14, "bold")).pack(anchor="w")
        ctk.CTkLabel(body, text=desc or "（无简介）", text_color=theme.SUB, anchor="w",
                     font=(theme.ui_font(), 11), wraplength=460, justify="left").pack(anchor="w", pady=(4, 0))
        ctk.CTkButton(
            inner, text="选择版本 ▸", width=100, height=32, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
            font=(theme.ui_font(), 12),
            command=lambda s=slug, t=title: self._pick_version(s, t),
        ).pack(side="right", anchor="s", padx=(8, 0))

        if icon:
            async_set_icon(self.app, icon_label, icon, 40)
        elif fetch_icon:
            def _fetch():
                try:
                    return sh_core.project_info(slug).get("icon_url")
                except Exception:
                    return None
            def _done(u):
                async_set_icon(self.app, icon_label, u, 40)
            self.app.run_async(_fetch, _done)

    def _pick_version(self, slug: str, title: str) -> None:
        mc = mods_core.base_mc_version(self.app.cfg.game_dir(), self.app.cfg.get("current_version") or "")
        self.app.set_status(f"正在获取 {title} 的版本列表…", 0.1)

        def work():
            return sh_core.get_shader_files(slug)

        def done(files):
            self.app.clear_progress()
            for w in self.list_box.winfo_children():
                w.destroy()
            if not files:
                ctk.CTkLabel(self.list_box, text=f"{title} 暂时没有可用版本",
                             text_color=theme.SUB, font=(theme.ui_font(), 13)).pack(pady=20)
                return
            head = ctk.CTkFrame(self.list_box, fg_color="transparent")
            head.pack(fill="x", pady=(0, 6))
            ctk.CTkLabel(head, text=f"选择 {title} 的版本", text_color=theme.TEXT,
                         font=(theme.ui_font(), 13, "bold")).pack(side="left")
            ctk.CTkButton(
                head, text="◀ 返回", width=72, height=28, corner_radius=8,
                fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB,
                font=(theme.ui_font(), 11), command=self._curated,
            ).pack(side="right")
            for f in files[:40]:
                row = ctk.CTkFrame(self.list_box, fg_color=theme.CARD_2, corner_radius=10)
                row.pack(fill="x", pady=3)
                left = ctk.CTkFrame(row, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True, padx=10, pady=8)
                ctk.CTkLabel(left, text=f.version, text_color=theme.TEXT, anchor="w",
                             font=(theme.ui_font(), 12, "bold")).pack(anchor="w")
                ctk.CTkLabel(left, text=f"MC {f.mc_version}", text_color=theme.SUB, anchor="w",
                             font=(theme.ui_font(), 10)).pack(anchor="w", pady=(2, 0))
                right = ctk.CTkFrame(row, fg_color="transparent")
                right.pack(side="right", padx=(4, 10))
                if mc and mc in (f.mc_version or ""):
                    tag(right, "✓适配", color=theme.GREEN).pack(side="left", padx=4)
                ctk.CTkLabel(right, text=f"{f.size / 1048576:.1f}MB", text_color=theme.SUB,
                             font=(theme.ui_font(), 10)).pack(side="left", padx=6)
                ctk.CTkButton(
                    right, text="下载", width=58, height=26, corner_radius=8,
                    fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
                    font=(theme.ui_font(), 11),
                    command=lambda mf=f: self._install_file(mf, title),
                ).pack(side="left")

        self.app.run_async(work, done)

    def _install_file(self, f, title: str) -> None:
        def work():
            def p(done: int, total: int) -> None:
                self.app.set_status(f"正在下载 {f.filename}", done / total if total else 0.2)
            return sh_core.install_shader(f, self.app.cfg.game_dir(), p)

        def done(path: Path) -> None:
            self.app.clear_progress()
            self.app.show_success("光影已下载", f"{title}\n已保存到 shaderpacks/{path.name}\n游戏内需先装 Iris/Oculus 光影加载器")

        self.app.run_async(work, done)


# ================= 账户 =================
class AccountsPage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=24, pady=18)
        ctk.CTkLabel(pad, text="账户管理", text_color=theme.TEXT,
                     font=(theme.ui_font(), 20, "bold")).pack(anchor="w", pady=(0, 16))

        # ---- 微软正版登录 ----
        ms_card = Card(pad, corner_radius=18)
        ms_card.pack(anchor="w", fill="x", pady=(0, 14))
        inner = ctk.CTkFrame(ms_card, fg_color="transparent")
        inner.pack(fill="x", padx=18, pady=16)
        ctk.CTkLabel(inner, text="微软正版账号登录", text_color=theme.TEXT,
                     font=(theme.ui_font(), 15, "bold")).pack(anchor="w")
        ctk.CTkLabel(inner, text="登录后进入正版验证服务器，可多人联机、领取披风、上传皮肤。",
                     text_color=theme.SUB, font=(theme.ui_font(), 11), justify="left").pack(anchor="w", pady=(4, 10))
        row = ctk.CTkFrame(inner, fg_color="transparent")
        row.pack(fill="x")
        self.ms_btn = ctk.CTkButton(
            row, text="🔑  使用微软账号登录", width=190, height=40, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN,
            font=(theme.ui_font(), 13, "bold"), command=self._ms_login,
        )
        self.ms_btn.pack(side="left")
        self.ms_state = ctk.CTkLabel(row, text="未登录正版账号", text_color=theme.SUB,
                                     font=(theme.ui_font(), 11))
        self.ms_state.pack(side="left", padx=16)

        # ---- 离线账户 ----
        card = Card(pad, width=520, corner_radius=18)
        card.pack(anchor="w")
        card.pack_propagate(False)
        ctk.CTkLabel(card, text="添加离线账户", text_color=theme.TEXT,
                     font=(theme.ui_font(), 15, "bold")).pack(anchor="w", padx=18, pady=(16, 10))
        row = ctk.CTkFrame(card, fg_color="transparent")
        row.pack(fill="x", padx=18, pady=(0, 16))
        self.name_entry = ctk.CTkEntry(
            row, placeholder_text="玩家名", height=40, corner_radius=12,
            fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT,
            font=(theme.ui_font(), 13),
        )
        self.name_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(
            row, text="＋ 添加", width=90, height=40, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN,
            font=(theme.ui_font(), 13), command=self._add,
        ).pack(side="left", padx=(10, 0))

        # ---- 换皮肤 ----
        sk_card = Card(pad, width=560, corner_radius=18)
        sk_card.pack(anchor="w", pady=(14, 0))
        sk_card.pack_propagate(False)
        ctk.CTkLabel(sk_card, text="换皮肤", text_color=theme.TEXT,
                     font=(theme.ui_font(), 15, "bold")).pack(anchor="w", padx=18, pady=(16, 8))
        ctk.CTkLabel(sk_card, text="正版账号：直接上传到 Mojang 官方；离线账号：保存为本地皮肤。",
                     text_color=theme.SUB, font=(theme.ui_font(), 11), justify="left").pack(anchor="w", padx=18, pady=(0, 10))
        sk_row = ctk.CTkFrame(sk_card, fg_color="transparent")
        sk_row.pack(fill="x", padx=18, pady=(0, 14))
        self.skin_variant = ctk.CTkSegmentedButton(
            sk_row, values=["经典(Steve)", "细长(Alex)"], height=34, corner_radius=10,
            fg_color=theme.CARD_2, selected_color=theme.BORDER, selected_hover_color=theme.BORDER,
            text_color=theme.SUB, font=(theme.ui_font(), 12),
        )
        self.skin_variant.set("经典(Steve)")
        self.skin_variant.pack(side="left", padx=(0, 10))
        ctk.CTkButton(
            sk_row, text="选择皮肤图片…", width=130, height=36, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
            font=(theme.ui_font(), 12), command=self._pick_skin,
        ).pack(side="left", padx=(0, 10))
        self.skin_apply = ctk.CTkButton(
            sk_row, text="上传/应用", width=96, height=36, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
            font=(theme.ui_font(), 12), command=self._apply_skin,
        )
        self.skin_apply.pack(side="left")
        self.skin_label = ctk.CTkLabel(sk_row, text="", text_color=theme.SUB,
                                       font=(theme.ui_font(), 10))
        self.skin_label.pack(side="left", padx=10)
        self._skin_path: str | None = None

        # ---- 已保存账户 ----
        ctk.CTkLabel(pad, text="已保存账户", text_color=theme.TEXT,
                     font=(theme.ui_font(), 15, "bold")).pack(anchor="w", pady=(22, 10))
        self.list_card = Card(pad, corner_radius=18)
        self.list_card.pack(fill="x")
        self._render()

    def _current(self) -> dict | None:
        return self.app.cfg.current_account()

    def _render(self) -> None:
        for w in self.list_card.winfo_children():
            w.destroy()
        accs = self.app.cfg.accounts()
        cur = self.app.cfg.current_account()
        # 更新正版状态提示
        if cur and cur.get("type") == "microsoft":
            self.ms_state.configure(text=f"已登录：{cur['name']}（正版）", text_color=theme.GREEN)
        else:
            self.ms_state.configure(text="未登录正版账号", text_color=theme.SUB)
        if not accs:
            ctk.CTkLabel(self.list_card, text="还没有账户，先添加一个吧",
                         text_color=theme.SUB, font=(theme.ui_font(), 12)).pack(padx=18, pady=18)
            return
        for a in accs:
            row = ctk.CTkFrame(self.list_card, fg_color=theme.CARD_2, corner_radius=12)
            row.pack(fill="x", padx=12, pady=4)
            typ = "正版" if a.get("type") == "microsoft" else "离线"
            ctk.CTkLabel(row, text=a["name"], text_color=theme.TEXT, anchor="w",
                         font=(theme.ui_font(), 13, "bold")).pack(side="left", padx=12, pady=10)
            tag(row, typ, color=theme.CYAN if typ == "正版" else theme.SUB).pack(side="left", padx=4)
            if cur and a["name"] == cur["name"]:
                tag(row, "当前使用", color=theme.GREEN).pack(side="left", padx=6)
            ctk.CTkLabel(row, text=(a.get("uuid") or "")[:18] + "…", text_color=theme.SUB,
                         font=(theme.ui_font(), 10)).pack(side="left", padx=8)
            ctk.CTkButton(
                row, text="使用", width=54, height=28, corner_radius=9,
                fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN,
                font=(theme.ui_font(), 11),
                command=lambda n=a["name"]: self._use(n),
            ).pack(side="right", padx=(2, 10), pady=8)
            ctk.CTkButton(
                row, text="删除", width=54, height=28, corner_radius=9,
                fg_color=theme.CARD_2, hover_color=theme.RED, text_color=theme.RED,
                font=(theme.ui_font(), 11),
                command=lambda n=a["name"]: self._del(n),
            ).pack(side="right", pady=8)

    # ---- 微软登录 ----
    def _ms_login(self) -> None:
        if self.app._launching:
            return
        cfg = self.app.cfg
        client_id = cfg.get("microsoft_client_id")
        cancel = {"flag": False}
        dlg = ctk.CTkToplevel(self)
        dlg.title("微软登录")
        dlg.geometry("520x300")
        dlg.configure(fg_color=theme.BG)
        dlg.transient(self.winfo_toplevel())
        dlg.grab_set()
        msg = ctk.CTkLabel(dlg, text="正在获取设备码…", text_color=theme.TEXT, wraplength=440,
                           font=(theme.ui_font(), 13))
        msg.pack(padx=20, pady=(28, 8))
        code_label = ctk.CTkLabel(dlg, text="", text_color=theme.CYAN,
                                  font=(theme.ui_font(), 26, "bold"))
        code_label.pack(pady=8)
        url_label = ctk.CTkLabel(dlg, text="", text_color=theme.SUB, wraplength=460,
                                 font=(theme.ui_font(), 12))
        url_label.pack(padx=20)
        ctk.CTkButton(
            dlg, text="取消", width=100, height=34, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.RED, text_color=theme.RED,
            font=(theme.ui_font(), 12),
            command=lambda: (cancel.__setitem__("flag", True), dlg.destroy()),
        ).pack(pady=(18, 12))

        def work():
            dc = ms_core.start_device_code(client_id)
            self._evq_show(dlg, msg, code_label, url_label, dc)
            token = ms_core.poll_token(client_id, dc["device_code"], dc.get("interval", 5), cancel=lambda: cancel["flag"])
            mc_token, profile = ms_core.login_ms(token)
            uuid = profile.get("id", "")
            return {"name": profile.get("name", "玩家"), "uuid": uuid,
                    "type": "microsoft", "access_token": mc_token,
                    "skins": profile.get("skins", [])}

        def done(acc):
            try:
                dlg.destroy()
            except Exception:
                pass
            self._save_ms_account(acc)

        def err(e):
            try:
                dlg.destroy()
            except Exception:
                pass
            self.app.notify("微软登录失败", str(e))

        self.app.run_async(work, done, err)

    def _evq_show(self, dlg, msg, code_label, url_label, dc) -> None:
        def show():
            msg.configure(text="请在弹出的微软页面完成登录：")
            code_label.configure(text=dc.get("user_code", "?????"))
            uri = dc.get("verification_uri", "https://www.microsoft.com/link")
            url_label.configure(text=f"① 访问  {uri}\n② 输入上方代码，点击「取消」可中止。")
            try:
                _open_url(uri)
            except Exception:
                pass
        self.app._evq.put(show)

    def _save_ms_account(self, acc: dict) -> None:
        cfg = self.app.cfg
        accs = [a for a in cfg.accounts() if not (a.get("type") == "microsoft" and a["name"] == acc["name"])]
        accs.append(acc)
        cfg.set("accounts", accs)
        cfg.set("current_account", acc["name"])
        self._render()
        self.app.notify("正版登录成功", f"已登录 {acc['name']}（正版）")

    # ---- 离线 ----
    def _add(self) -> None:
        name = self.name_entry.get().strip()
        if not name:
            self.app.notify("名字为空", "请输入玩家名")
            return
        cfg = self.app.cfg
        accs = cfg.accounts()
        if any(a["name"] == name for a in accs):
            self.app.notify("已存在", "该账户已存在")
            return
        accs.append(auth.make_offline_account(name))
        cfg.set("accounts", accs)
        cfg.set("current_account", name)
        self.name_entry.delete(0, "end")
        self._render()
        self.app.notify("已添加", f"账户 {name}（离线）")

    def _use(self, name: str) -> None:
        self.app.cfg.set("current_account", name)
        self._render()

    def _del(self, name: str) -> None:
        cfg = self.app.cfg
        accs = [a for a in cfg.accounts() if a["name"] != name]
        cfg.set("accounts", accs)
        if cfg.get("current_account") == name:
            cfg.set("current_account", accs[0]["name"] if accs else None)
        self._render()

    # ---- 换皮肤 ----
    def _pick_skin(self) -> None:
        p = filedialog.askopenfilename(
            title="选择皮肤图片（64×32 或 64×64 PNG）",
            filetypes=[("PNG 图片", "*.png"), ("所有文件", "*")],
        )
        if p:
            self._skin_path = p
            self.skin_label.configure(text=Path(p).name)

    def _apply_skin(self) -> None:
        if not self._skin_path:
            self.app.notify("未选择皮肤", "请先选择皮肤图片")
            return
        cur = self._current()
        if not cur:
            self.app.notify("未选择账户", "请先选择/添加账户")
            return
        variant = "slim" if "细长" in self.skin_variant.get() else "classic"
        if cur.get("type") == "microsoft":
            self._upload_ms_skin(cur, Path(self._skin_path), variant)
        else:
            self._save_local_skin(cur, Path(self._skin_path))

    def _upload_ms_skin(self, acc: dict, png: Path, variant: str) -> None:
        def work():
            return ms_core.upload_skin(acc.get("access_token", ""), png, variant)

        def done(_):
            self.app.notify("正版皮肤已更新", f"{acc['name']} 皮肤已上传到 Mojang（下次进入服务器生效）")

        self.app.run_async(work, done)

    def _save_local_skin(self, acc: dict, png: Path) -> None:
        cfg = self.app.cfg
        skins_dir = cfg.game_dir() / "skins"
        skins_dir.mkdir(parents=True, exist_ok=True)
        dest = skins_dir / f"{acc['name']}.png"
        import shutil
        shutil.copyfile(png, dest)
        offline = dict(cfg.get("offline_skin") or {})
        offline[acc["name"]] = str(dest)
        cfg.set("offline_skin", offline)
        self.app.notify("本地皮肤已保存", f"{acc['name']} → skins/{dest.name}\n（离线皮肤需配合 CustomSkinLoader 模组在游戏内生效）")


# ================= 设置 =================
class SettingsPage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=24, pady=18)
        ctk.CTkLabel(pad, text="设置", text_color=theme.TEXT,
                     font=(theme.ui_font(), 20, "bold")).pack(anchor="w", pady=(0, 16))

        card = Card(pad, width=640, corner_radius=18)
        card.pack(anchor="w")
        card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent")
        inner.pack(fill="x", padx=20, pady=18)

        cfg = self.app.cfg

        def row(label: str) -> ctk.CTkFrame:
            r = ctk.CTkFrame(inner, fg_color="transparent")
            r.pack(fill="x", pady=7)
            ctk.CTkLabel(r, text=label, text_color=theme.TEXT, width=140, anchor="w",
                         font=(theme.ui_font(), 13)).pack(side="left")
            return r

        # 内存
        r = row("内存分配")
        self.mem_label = ctk.CTkLabel(r, text=f"{cfg.get('memory_mb')} MB", text_color=theme.CYAN,
                                      font=(theme.ui_font(), 13))
        self.mem_label.pack(side="right")
        self.mem_slider = ctk.CTkSlider(
            r, from_=1024, to=8192, number_of_steps=28, width=300,
            fg_color=theme.CARD_2, progress_color=theme.CYAN, button_color=theme.CYAN,
            command=lambda v: self.mem_label.configure(text=f"{int(v)} MB"),
        )
        self.mem_slider.set(cfg.get("memory_mb"))
        self.mem_slider.pack(side="right", padx=(0, 16))

        # Java
        r = row("Java 路径")
        self.java_entry = ctk.CTkEntry(
            r, height=34, corner_radius=10, fg_color=theme.CARD_2,
            border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(), 12),
        )
        self.java_entry.insert(0, cfg.get("java_path") or "")
        self.java_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(r, text="浏览", width=56, height=32, corner_radius=10,
                      fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
                      font=(theme.ui_font(), 12), command=self._pick_java).pack(side="left")
        ctk.CTkButton(r, text="自动检测", width=76, height=32, corner_radius=10,
                      fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
                      font=(theme.ui_font(), 12), command=self._auto_java).pack(side="left", padx=(6, 0))

        # 游戏目录
        r = row("游戏目录")
        self.dir_entry = ctk.CTkEntry(
            r, height=34, corner_radius=10, fg_color=theme.CARD_2,
            border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(), 12),
        )
        self.dir_entry.insert(0, str(cfg.game_dir()))
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        ctk.CTkButton(r, text="浏览", width=56, height=32, corner_radius=10,
                      fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
                      font=(theme.ui_font(), 12), command=self._pick_dir).pack(side="left")

        # 内置 Java 版本（按 MC 版本自动匹配 8/17/21）
        jcard = ctk.CTkFrame(inner, fg_color=theme.CARD_2, corner_radius=12)
        jcard.pack(fill="x", pady=(10, 2))
        jtop = ctk.CTkFrame(jcard, fg_color="transparent")
        jtop.pack(fill="x", padx=14, pady=(10, 6))
        ctk.CTkLabel(jtop, text="内置 Java 版本", text_color=theme.TEXT,
                     font=(theme.ui_font(), 13, "bold")).pack(side="left")
        ctk.CTkLabel(jtop, text="自动按游戏版本选择（1.16↔8 · 1.17-1.20.4↔17 · 1.20.5+↔21 · 新版25.x/26.x↔25）",
                     text_color=theme.SUB, font=(theme.ui_font(), 10)).pack(side="left", padx=10)
        ctk.CTkButton(jtop, text="刷新", width=60, height=28, corner_radius=9,
                      fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN,
                      font=(theme.ui_font(), 11), command=self._refresh_java).pack(side="right")
        self._java_frame = ctk.CTkFrame(jcard, fg_color="transparent")
        self._java_frame.pack(fill="x", padx=8, pady=(0, 10))
        self._refresh_java()

        # 下载源
        r = row("下载源")
        self.mirror_menu = ctk.CTkOptionMenu(
            r, values=["bmclapi（国内加速）", "mojang（官方）"], width=220, height=34, corner_radius=10,
            fg_color=theme.CARD_2, button_color=theme.CARD_2, button_hover_color=theme.BORDER,
            text_color=theme.TEXT, dropdown_fg_color=theme.CARD_2, dropdown_hover_color=theme.BORDER,
            font=(theme.ui_font(), 12), dropdown_font=(theme.ui_font(), 12),
        )
        self.mirror_menu.set("bmclapi（国内加速）" if cfg.get("mirror") == "bmclapi" else "mojang（官方）")
        self.mirror_menu.pack(side="left")

        # 分辨率
        r = row("窗口分辨率")
        self.w_entry = ctk.CTkEntry(r, width=90, height=32, corner_radius=10,
                                    fg_color=theme.CARD_2, border_color=theme.BORDER,
                                    text_color=theme.TEXT, font=(theme.ui_font(), 12))
        self.w_entry.insert(0, str(cfg.get("width") or ""))
        self.w_entry.pack(side="left")
        ctk.CTkLabel(r, text="×", text_color=theme.SUB).pack(side="left", padx=6)
        self.h_entry = ctk.CTkEntry(r, width=90, height=32, corner_radius=10,
                                    fg_color=theme.CARD_2, border_color=theme.BORDER,
                                    text_color=theme.TEXT, font=(theme.ui_font(), 12))
        self.h_entry.insert(0, str(cfg.get("height") or ""))
        self.h_entry.pack(side="left")
        ctk.CTkLabel(r, text="（留空=游戏默认）", text_color=theme.SUB,
                     font=(theme.ui_font(), 10)).pack(side="left", padx=8)

        # 下载线程
        r = row("下载线程")
        self.th_label = ctk.CTkLabel(r, text=f"{cfg.get('download_threads')}", text_color=theme.CYAN,
                                     font=(theme.ui_font(), 13))
        self.th_label.pack(side="right")
        self.th_slider = ctk.CTkSlider(
            r, from_=2, to=16, number_of_steps=14, width=300,
            fg_color=theme.CARD_2, progress_color=theme.CYAN, button_color=theme.CYAN,
            command=lambda v: self.th_label.configure(text=f"{int(v)}"),
        )
        self.th_slider.set(cfg.get("download_threads"))
        self.th_slider.pack(side="right", padx=(0, 16))

        btns = ctk.CTkFrame(pad, fg_color="transparent")
        btns.pack(anchor="w", pady=(18, 0))
        ctk.CTkButton(
            btns, text="💾 保存设置", width=140, height=40, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN,
            font=(theme.ui_font(), 14, "bold"), command=self._save,
        ).pack(side="left")
        ctk.CTkButton(
            btns, text="↻ 检查启动器更新", width=140, height=40, corner_radius=12,
            fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN,
            font=(theme.ui_font(), 13, "bold"), command=self.app.check_update_manual,
        ).pack(side="left", padx=(10, 0))
        ctk.CTkLabel(btns, text="自动按版本选 Java（1.16↔8·1.17-1.20.4↔17·1.20.5+↔21·新版25.x↔25）",
                     text_color=theme.SUB, font=(theme.ui_font(), 11)).pack(side="left", padx=16)

    def _refresh_java(self) -> None:
        for w in self._java_frame.winfo_children():
            w.destroy()
        inst = javamgr.list_installed()
        for maj in javamgr.SUPPORTED:
            line = ctk.CTkFrame(self._java_frame, fg_color="transparent")
            line.pack(fill="x", padx=6, pady=2)
            ctk.CTkLabel(line, text=f"Java {maj}", width=70, anchor="w",
                         text_color=theme.TEXT, font=(theme.ui_font(), 12)).pack(side="left")
            if inst.get(maj):
                tag(line, "已就绪", color=theme.GREEN).pack(side="left", padx=6)
                ctk.CTkLabel(line, text=Path(inst[maj]).name, text_color=theme.SUB,
                             font=(theme.ui_font(), 10)).pack(side="left", padx=4)
            else:
                tag(line, "未安装", color=theme.SUB).pack(side="left", padx=6)
                ctk.CTkButton(line, text="下载", width=56, height=26, corner_radius=8,
                              fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN,
                              font=(theme.ui_font(), 11),
                              command=lambda m=maj: self._download_java(m)).pack(side="right", padx=(6, 0))

    def _download_java(self, maj: int) -> None:
        self.app.set_status(f"正在获取 Java {maj}…", 0.1)

        def work():
            def p(done: int, total: int) -> None:
                self.app.set_status(f"下载 Java {maj}", done / total if total else 0.2)
            return javamgr.download(maj, p)

        def done(folder) -> None:
            self.app.clear_progress()
            self.app.show_success("Java 已装好", f"Java {maj} 已安装，启动对应版本会自动使用")
            self._refresh_java()

        self.app.run_async(work, done)

    def _pick_java(self) -> None:
        p = filedialog.askopenfilename(
            title="选择 java 可执行文件",
            filetypes=[("Java", "*.exe"), ("所有文件", "*")],
        )
        if p:
            self.java_entry.delete(0, "end")
            self.java_entry.insert(0, p)

    def _auto_java(self) -> None:
        j = lc.find_java(self.java_entry.get())
        if j:
            self.java_entry.delete(0, "end")
            self.java_entry.insert(0, j)
            self.app.notify("已检测到 Java", j)
        else:
            self.app.notify("未找到 Java", "请手动指定 Java 路径")

    def _pick_dir(self) -> None:
        p = filedialog.askdirectory(title="选择游戏目录")
        if p:
            self.dir_entry.delete(0, "end")
            self.dir_entry.insert(0, p)

    def _save(self) -> None:
        cfg = self.app.cfg
        cfg.set("memory_mb", int(self.mem_slider.get()))
        cfg.set("java_path", self.java_entry.get().strip())
        cfg.set("game_dir", self.dir_entry.get().strip() or None)
        cfg.set("mirror", "bmclapi" if "bmclapi" in self.mirror_menu.get() else "mojang")
        try:
            cfg.set("width", int(self.w_entry.get().strip() or 0))
            cfg.set("height", int(self.h_entry.get().strip() or 0))
        except ValueError:
            self.app.notify("分辨率无效", "请输入整数")
            return
        cfg.set("download_threads", int(self.th_slider.get()))
        self.app.notify("已保存", "设置已写入 config.json")


# ================= 控制台 =================
class ConsolePage(Page):
    def on_show(self) -> None:
        for w in self.winfo_children():
            w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=24, pady=18)
        head = ctk.CTkFrame(pad, fg_color="transparent")
        head.pack(fill="x", pady=(0, 12))
        ctk.CTkLabel(head, text="控制台", text_color=theme.TEXT,
                     font=(theme.ui_font(), 20, "bold")).pack(side="left")
        ctk.CTkButton(
            head, text="清空", width=70, height=32, corner_radius=10,
            fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB,
            font=(theme.ui_font(), 12), command=self.clear,
        ).pack(side="right")
        card = Card(pad, corner_radius=16)
        card.pack(fill="both", expand=True)
        self.text = ctk.CTkTextbox(
            card, fg_color="#0B101D", text_color="#C7D6F0",
            font=("Consolas", 12), wrap="none", corner_radius=12,
            border_width=0, state="disabled",
        )
        self.text.pack(fill="both", expand=True, padx=10, pady=10)
        self._lines = 0

    def append(self, line: str) -> None:
        try:
            self.text.configure(state="normal")
            self.text.insert("end", line + "\n")
            self._lines += 1
            if self._lines > 3000:
                self.text.delete("1.0", "200.0")
                self._lines = 3000
            self.text.see("end")
            self.text.configure(state="disabled")
        except Exception:
            pass

    def clear(self) -> None:
        try:
            self.text.configure(state="normal")
            self.text.delete("1.0", "end")
            self._lines = 0
            self.text.configure(state="disabled")
        except Exception:
            pass


def _open_url(url: str) -> None:
    import webbrowser
    try:
        webbrowser.open(url)
    except Exception:
        pass


def _open_path(p: Path) -> None:
    import sys
    import subprocess as sp
    try:
        if sys.platform.startswith("win"):
            sp.Popen(["explorer", str(p)])
        elif sys.platform == "darwin":
            sp.Popen(["open", str(p)])
        else:
            sp.Popen(["xdg-open", str(p)])
    except Exception:
        pass
