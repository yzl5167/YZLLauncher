"""应用外壳：启动画面 + 主窗口（自定义标题栏、侧边导航、全局状态栏）。"""
from __future__ import annotations

import queue
import threading
from typing import Callable, Optional

import customtkinter as ctk

from yzl import constants
from yzl.core.config import Config
from yzl.core import updater
from yzl.ui import theme
from yzl.ui.pages import (
    AccountsPage,
    ConsolePage,
    HomePage,
    ModsPage,
    SettingsPage,
    ShadersPage,
    VersionsPage,
)
from yzl.ui.widgets import Card, attach_gradient, draw_gradient, nav_button, tag

W, H = 1140, 720
NAV_W = 210
TITLE_H = 56
STATUS_H = 30


class App:
    def __init__(self) -> None:
        ctk.set_appearance_mode("dark")
        self.cfg = Config()
        self.pages: dict[str, ctk.CTkFrame] = {}
        self.current: Optional[str] = None
        self._evq: queue.Queue = queue.Queue()
        self._progress: Optional[tuple[str, int, int]] = None
        self._proc = None
        self._launching = False

        self.root = ctk.CTk()
        self.root.title("YZL 启动器")
        self.root.overrideredirect(True)
        self.root.configure(fg_color=theme.BG)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw - W) // 2}+{max(0, (sh - H) // 2 - 20)}")
        self.root.minsize(W, H)

        self._build_shell()
        self._build_pages()
        self._select("home")
        self._poll()

        # 启动画面
        self.splash = ctk.CTkToplevel(self.root)
        self.splash.overrideredirect(True)
        self.splash.configure(fg_color=theme.BG)
        self.splash.geometry(f"520x300+{self.root.winfo_x() + (W - 520) // 2}+{self.root.winfo_y() + (H - 300) // 2}")
        self._draw_splash()
        self.splash.after(2200, self._close_splash)
        self._check_update()

    # ---------------- 自动更新 ----------------
    def _check_update(self) -> None:
        def work():
            try:
                return updater.check_latest()
            except Exception:
                return None  # 启动时后台静默，避免连不上更新服务器就弹窗打扰

        def done(info):
            if info and info.get("exe_url"):
                self._offer_update(info)

        self.run_async(work, done)

    def _offer_update(self, info: dict) -> None:
        dlg = ctk.CTkToplevel(self.root)
        dlg.title("发现新版本")
        dlg.geometry("500x330")
        dlg.configure(fg_color=theme.BG)
        dlg.transient(self.root)
        dlg.grab_set()
        ctk.CTkLabel(dlg, text=f"发现新版本 v{info.get('version', '')}",
                     text_color=theme.CYAN, font=(theme.ui_font(), 19, "bold")).pack(pady=(28, 6))
        notes = (info.get("notes") or "点击更新即可在线升级到最新版。").strip()
        ctk.CTkLabel(dlg, text=notes[:320], text_color=theme.SUB, justify="left", wraplength=440,
                     font=(theme.ui_font(), 11)).pack(padx=28, pady=6)
        btns = ctk.CTkFrame(dlg, fg_color="transparent")
        btns.pack(pady=20)
        ctk.CTkButton(btns, text="更新并重启", width=120, height=38,
                      fg_color=theme.CYAN, hover_color=theme.GREEN, text_color="#0B101D",
                      font=(theme.ui_font(), 13, "bold"),
                      command=lambda: (dlg.destroy(), self._do_update(info["exe_url"]))).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="稍后", width=90, height=38,
                      fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB,
                      font=(theme.ui_font(), 12), command=dlg.destroy).pack(side="left", padx=8)

    def _do_update(self, exe_url: str) -> None:
        def work():
            return updater.download_update(exe_url, progress=lambda d, t: self.set_status(
                f"下载更新 {d / t if t else '…'}", d / t if t else 0.2))

        def done(path) -> None:
            self.clear_progress()
            self.notify("更新完成", "正在替换并重启…")
            self.root.after(400, lambda: (updater.apply_update(path), self.root.destroy()))

        def err(e) -> None:
            self.clear_progress()
            self.notify("更新失败", str(e))

        self.run_async(work, done, err)

    # ---- 手动检查启动器更新（设置页按钮触发）----
    def check_update_manual(self) -> None:
        self.set_status("正在检查更新…", 0.1)

        def work():
            return updater.check_latest()

        def done(info):
            self.clear_progress()
            if info and info.get("exe_url"):
                self._offer_update(info)
            else:
                self.show_info("已是最新版本", f"当前 v{constants.APP_VERSION} 已是最新版")

        def err(e):
            self.clear_progress()
            self.show_error("检查更新失败", f"无法连接更新服务器：\n{str(e)}")

        self.run_async(work, done, err)

    # ---------------- 界面骨架 ----------------
    def _build_shell(self) -> None:
        self.titlebar = ctk.CTkFrame(self.root, height=TITLE_H, fg_color=theme.CARD, corner_radius=0)
        self.titlebar.pack(fill="x")
        self.titlebar.pack_propagate(False)

        ctk.CTkLabel(
            self.titlebar, text="◆  YZL 启动器", text_color=theme.TEXT,
            font=(theme.ui_font(), 16, "bold"), anchor="w",
        ).pack(side="left", padx=(20, 6), pady=12)
        ctk.CTkLabel(
            self.titlebar, text=f"Your Zone Launcher · v{constants.APP_VERSION}", text_color=theme.SUB,
            font=(theme.ui_font(), 11),
        ).pack(side="left", pady=12)

        # 窗口控制
        ctk.CTkButton(
            self.titlebar, text="—", width=40, height=30, corner_radius=10,
            fg_color="transparent", hover_color=theme.CARD_2, text_color=theme.TEXT,
            font=(theme.ui_font(), 16), command=self.root.iconify,
        ).pack(side="right", padx=(4, 8), pady=12)
        ctk.CTkButton(
            self.titlebar, text="✕", width=40, height=30, corner_radius=10,
            fg_color="transparent", hover_color=theme.RED, text_color=theme.TEXT,
            font=(theme.ui_font(), 15), command=self._quit,
        ).pack(side="right", pady=12)

        # 拖动窗口
        self.titlebar.bind("<Button-1>", self._drag_start)
        self.titlebar.bind("<B1-Motion>", self._drag_move)
        for c in self.titlebar.winfo_children():
            c.bind("<Button-1>", self._drag_start, add="+")
            c.bind("<B1-Motion>", self._drag_move, add="+")

        body = ctk.CTkFrame(self.root, fg_color=theme.BG, corner_radius=0)
        body.pack(fill="both", expand=True)

        # 左侧导航
        self.nav = ctk.CTkFrame(body, width=NAV_W, fg_color=theme.CARD, corner_radius=0)
        self.nav.pack(side="left", fill="y")
        self.nav.pack_propagate(False)

        logo = ctk.CTkCanvas(self.nav, width=NAV_W, height=86, bg=theme.CARD, highlightthickness=0)
        logo.pack(pady=(10, 6))
        attach_gradient(logo, theme.GRAD_TOP, theme.GRAD_BOT, corner=14, x0=20, y0=20, h=46)
        logo.create_text(NAV_W / 2, 43, text="YZL", fill="#FFFFFF",
                         font=(theme.ui_font(), 22, "bold"))

        self._nav_btns: dict[str, ctk.CTkButton] = {}
        items = [
            ("home", "🏠  首页"),
            ("versions", "📦  版本管理"),
            ("mods", "🧩  模组中心"),
            ("shaders", "🌅  光影中心"),
            ("accounts", "👤  账户"),
            ("settings", "⚙️  设置"),
            ("console", "🖥️  控制台"),
        ]
        for key, label in items:
            b = nav_button(self.nav, label, lambda k=key: self._select(k))
            b.pack(fill="x", padx=14, pady=3)
            self._nav_btns[key] = b
        ctk.CTkLabel(
            self.nav, text="YZL · Your Zone", text_color=theme.SUB,
            font=(theme.ui_font(), 10),
        ).pack(side="bottom", pady=14)

        # 内容区
        self.content = ctk.CTkFrame(body, fg_color=theme.BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)

        # 状态栏（安装/下载进度）
        self.statusbar = ctk.CTkFrame(self.root, height=STATUS_H, fg_color=theme.CARD, corner_radius=0)
        self.statusbar.pack(fill="x")
        self.statusbar.pack_propagate(False)
        self.status_label = ctk.CTkLabel(
            self.statusbar, text="就绪", text_color=theme.SUB,
            font=(theme.ui_font(), 11), anchor="w",
        )
        self.status_label.pack(side="left", padx=16, pady=4)
        self.progress = ctk.CTkProgressBar(
            self.statusbar, width=240, height=8, corner_radius=4,
            fg_color=theme.CARD_2, progress_color=theme.CYAN,
        )
        self.progress.pack(side="right", padx=16, pady=4)
        self.progress.set(0)

        self.toast: Optional[ctk.CTkLabel] = None

    def _build_pages(self) -> None:
        makers = {
            "home": HomePage,
            "versions": VersionsPage,
            "mods": ModsPage,
            "shaders": ShadersPage,
            "accounts": AccountsPage,
            "settings": SettingsPage,
            "console": ConsolePage,
        }
        for key, cls in makers.items():
            page = cls(self.content, app=self)
            page.pack(fill="both", expand=True)
            page.pack_forget()
            self.pages[key] = page

    def _select(self, key: str) -> None:
        if self.current and self.current != key:
            self.pages[self.current].pack_forget()
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        for k, b in self._nav_btns.items():
            b.configure(fg_color=theme.CARD_2 if k == key else "transparent",
                        text_color=theme.CYAN if k == key else theme.TEXT)
        page = self.pages[key]
        # 页面缓存：首次 on_show 构建，之后切页仅 on_reshow 刷新动态部分，避免整页重建卡顿
        if getattr(page, "_first_show", True):
            page._first_show = False
            page.on_show()
        else:
            page.on_reshow()

    def switch(self, key: str) -> None:
        self._select(key)

    # ---------------- 拖拽 / 退出 ----------------
    def _drag_start(self, e) -> None:
        self._dx, self._dy = e.x_root - self.root.winfo_x(), e.y_root - self.root.winfo_y()

    def _drag_move(self, e) -> None:
        self.root.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _quit(self) -> None:
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
            except Exception:
                pass
        self.cfg.save()
        self.root.destroy()

    # ---------------- 启动画面 ----------------
    def _draw_splash(self) -> None:
        cv = ctk.CTkCanvas(self.splash, width=520, height=300, bg=theme.BG, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        draw_gradient(cv, 520, 300, "#0A0E1A", "#101A30", corner=0)
        cv.create_text(260, 110, text="YZL", fill=theme.CYAN, font=(theme.ui_font(), 72, "bold"))
        cv.create_text(260, 178, text="Your Zone Launcher", fill=theme.SUB, font=(theme.ui_font(), 16))
        bar = ctk.CTkProgressBar(
            self.splash, width=280, height=6, corner_radius=3,
            fg_color=theme.CARD_2, progress_color=theme.GRAD_BOT,
        )
        bar.place(x=120, y=236)

        def anim(i: int = 0) -> None:
            try:
                bar.set(min(1.0, i / 100))
                if i < 100:
                    self.splash.after(12, lambda: anim(i + 1))
            except Exception:
                pass

        anim()

    def _close_splash(self) -> None:
        try:
            self.splash.destroy()
        except Exception:
            pass

    # ---------------- 公共接口 ----------------
    def notify(self, title: str, msg: str = "") -> None:
        if self.toast:
            self.toast.destroy()
        card = Card(self.root, corner_radius=14)
        self.toast = ctk.CTkLabel(
            card, text=f"{title}\n{msg}", text_color=theme.TEXT, justify="left",
            font=(theme.ui_font(), 13), fg_color="transparent", padx=22, pady=14,
        )
        self.toast.pack()
        card.place(relx=0.5, x=-0, y=TITLE_H + 12, anchor="n")
        card.lift()
        card.after(3600, card.destroy)

    # ---- PCL 式模态反馈：下载/安装完成或出错时弹醒目对话框 ----
    def show_success(self, title: str, msg: str = "") -> None:
        self._show_dialog("✓ 完成", title, msg, theme.GREEN)

    def show_error(self, title: str, msg: str = "") -> None:
        self._show_dialog("✕ 出错了", title, msg, theme.RED)

    def show_info(self, title: str, msg: str = "") -> None:
        self._show_dialog("ℹ 提示", title, msg, theme.CYAN)

    def _show_dialog(self, head: str, title: str, msg: str, color: str) -> None:
        def _open() -> None:
            try:
                dlg = ctk.CTkToplevel(self.root)
                dlg.title(title)
                dlg.configure(fg_color=theme.BG)
                dlg.transient(self.root)
                dlg.grab_set()
                w, h = 540, 330
                x = self.root.winfo_x() + (W - w) // 2
                y = self.root.winfo_y() + (H - h) // 2
                dlg.geometry(f"{w}x{h}+{max(0,x)}+{max(0,y)}")
                ctk.CTkLabel(dlg, text=head, text_color=color,
                             font=(theme.ui_font(), 24, "bold")).pack(pady=(34, 6))
                ctk.CTkLabel(dlg, text=title, text_color=theme.TEXT,
                             font=(theme.ui_font(), 16, "bold")).pack(pady=(0, 8))
                ctk.CTkLabel(dlg, text=msg or "", text_color=theme.SUB, justify="left",
                             wraplength=460, font=(theme.ui_font(), 12)).pack(padx=34, pady=4)
                ctk.CTkButton(
                    dlg, text="确定", width=120, height=40, corner_radius=12,
                    fg_color=color, hover_color=theme.GREEN, text_color="#0B101D",
                    font=(theme.ui_font(), 13, "bold"), command=dlg.destroy,
                ).pack(pady=24)
            except Exception:
                try:
                    import traceback
                    from yzl.constants import app_root
                    with open(app_root() / "yzl_error.log", "a", encoding="utf-8") as f:
                        f.write(f"\n[show_dialog]{traceback.format_exc()}\n")
                except Exception:
                    pass
        self._evq.put(_open)


    def set_status(self, text: str, progress: Optional[float] = None) -> None:
        def _set() -> None:
            self.status_label.configure(text=text)
            if progress is not None:
                self.progress.set(min(1.0, max(0.0, progress)))
        self._evq.put(_set)

    def clear_progress(self) -> None:
        def _clear() -> None:
            self.status_label.configure(text="就绪")
            self.progress.set(0)
        self._evq.put(_clear)

    def run_async(self, fn: Callable, on_done: Optional[Callable] = None,
                  on_error: Optional[Callable] = None) -> None:
        def worker() -> None:
            try:
                result = fn()
                if on_done:
                    self._evq.put(lambda: on_done(result))
            except Exception as e:  # noqa: BLE001
                if on_error:
                    self._evq.put(lambda: on_error(e))
                else:
                    self._evq.put(lambda: self.notify("操作失败", str(e)))
                self._evq.put(self.clear_progress)
        threading.Thread(target=worker, daemon=True).start()

    def add_log(self, line: str) -> None:
        self._evq.put(lambda: self.pages["console"].append(line))

    def clear_log(self) -> None:
        self._evq.put(lambda: self.pages["console"].clear())

    def _poll(self) -> None:
        try:
            while True:
                fn = self._evq.get_nowait()
                try:
                    fn()
                except Exception:
                    pass
        except queue.Empty:
            pass
        self.root.after(100, self._poll)


def run() -> None:
    app = App()
    app.root.mainloop()
