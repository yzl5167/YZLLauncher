"""应用外壳：启动画面 + 主窗口。"""
from __future__ import annotations
import queue
import threading
from typing import Callable, Optional
import customtkinter as ctk
from yzl.core.config import Config
from yzl.ui import theme
from yzl.ui.pages import AccountsPage, ConsolePage, HomePage, ModsPage, SettingsPage, VersionsPage
from yzl.ui.widgets import Card, attach_gradient, nav_button, tag, draw_gradient

W, H = 1140, 720
NAV_W = 210
TITLE_H = 56
STATUS_H = 30

class App:
    def __init__(self):
        ctk.set_appearance_mode("dark")
        self.cfg = Config()
        self.pages = {}
        self.current = None
        self._evq = queue.Queue()
        self._proc = None
        self._launching = False
        self.root = ctk.CTk()
        self.root.title("YZL 启动器")
        self.root.overrideredirect(True)
        self.root.configure(fg_color=theme.BG)
        sw, sh = self.root.winfo_screenwidth(), self.root.winfo_screenheight()
        self.root.geometry(f"{W}x{H}+{(sw-W)//2}+{max(0,(sh-H)//2-20)}")
        self.root.minsize(W, H)
        self._build_shell()
        self._build_pages()
        self._select("home")
        self._poll()
        self.splash = ctk.CTkToplevel(self.root)
        self.splash.overrideredirect(True)
        self.splash.configure(fg_color=theme.BG)
        self.splash.geometry(f"520x300+{self.root.winfo_x()+(W-520)//2}+{self.root.winfo_y()+(H-300)//2}")
        self._draw_splash()
        self.splash.after(2200, self._close_splash)

    def _build_shell(self):
        self.titlebar = ctk.CTkFrame(self.root, height=TITLE_H, fg_color=theme.CARD, corner_radius=0)
        self.titlebar.pack(fill="x"); self.titlebar.pack_propagate(False)
        ctk.CTkLabel(self.titlebar, text="◆  YZL 启动器", text_color=theme.TEXT, font=(theme.ui_font(),16,"bold"), anchor="w").pack(side="left", padx=(20,6), pady=12)
        ctk.CTkLabel(self.titlebar, text="Your Zone Launcher · v1.0.0", text_color=theme.SUB, font=(theme.ui_font(),11)).pack(side="left", pady=12)
        ctk.CTkButton(self.titlebar, text="—", width=40, height=30, corner_radius=10, fg_color="transparent", hover_color=theme.CARD_2, text_color=theme.TEXT, font=(theme.ui_font(),16), command=self.root.iconify).pack(side="right", padx=(4,8), pady=12)
        ctk.CTkButton(self.titlebar, text="✕", width=40, height=30, corner_radius=10, fg_color="transparent", hover_color=theme.RED, text_color=theme.TEXT, font=(theme.ui_font(),15), command=self._quit).pack(side="right", pady=12)
        self.titlebar.bind("<Button-1>", self._drag_start)
        self.titlebar.bind("<B1-Motion>", self._drag_move)
        for c in self.titlebar.winfo_children():
            c.bind("<Button-1>", self._drag_start, add="+")
            c.bind("<B1-Motion>", self._drag_move, add="+")
        body = ctk.CTkFrame(self.root, fg_color=theme.BG, corner_radius=0)
        body.pack(fill="both", expand=True)
        self.nav = ctk.CTkFrame(body, width=NAV_W, fg_color=theme.CARD, corner_radius=0)
        self.nav.pack(side="left", fill="y"); self.nav.pack_propagate(False)
        logo = ctk.CTkCanvas(self.nav, width=NAV_W, height=86, bg=theme.CARD, highlightthickness=0)
        logo.pack(pady=(10,6))
        attach_gradient(logo, theme.GRAD_TOP, theme.GRAD_BOT, corner=14, x0=20, y0=20, h=46)
        logo.create_text(NAV_W/2, 43, text="YZL", fill="#FFFFFF", font=(theme.ui_font(),22,"bold"))
        self._nav_btns = {}
        items = [("home","🏠  首页"),("versions","📦  版本管理"),("mods","🧩  模组中心"),("accounts","👤  账户"),("settings","⚙️  设置"),("console","🖥️  控制台")]
        for key, label in items:
            b = nav_button(self.nav, label, lambda k=key: self._select(k))
            b.pack(fill="x", padx=14, pady=3)
            self._nav_btns[key] = b
        ctk.CTkLabel(self.nav, text="YZL · Your Zone", text_color=theme.SUB, font=(theme.ui_font(),10)).pack(side="bottom", pady=14)
        self.content = ctk.CTkFrame(body, fg_color=theme.BG, corner_radius=0)
        self.content.pack(side="left", fill="both", expand=True)
        self.statusbar = ctk.CTkFrame(self.root, height=STATUS_H, fg_color=theme.CARD, corner_radius=0)
        self.statusbar.pack(fill="x"); self.statusbar.pack_propagate(False)
        self.status_label = ctk.CTkLabel(self.statusbar, text="就绪", text_color=theme.SUB, font=(theme.ui_font(),11), anchor="w")
        self.status_label.pack(side="left", padx=16, pady=4)
        self.progress = ctk.CTkProgressBar(self.statusbar, width=240, height=8, corner_radius=4, fg_color=theme.CARD_2, progress_color=theme.CYAN)
        self.progress.pack(side="right", padx=16, pady=4); self.progress.set(0)
        self.toast = None

    def _build_pages(self):
        makers = {"home":HomePage,"versions":VersionsPage,"mods":ModsPage,"accounts":AccountsPage,"settings":SettingsPage,"console":ConsolePage}
        for key, cls in makers.items():
            page = cls(self.content, app=self)
            page.pack(fill="both", expand=True); page.pack_forget()
            self.pages[key] = page

    def _select(self, key):
        if self.current:
            self.pages[self.current].pack_forget()
        self.current = key
        self.pages[key].pack(fill="both", expand=True)
        for k, b in self._nav_btns.items():
            b.configure(fg_color=theme.CARD_2 if k==key else "transparent", text_color=theme.CYAN if k==key else theme.TEXT)
        self.pages[key].on_show()

    def switch(self, key): self._select(key)

    def _drag_start(self, e): self._dx, self._dy = e.x_root-self.root.winfo_x(), e.y_root-self.root.winfo_y()
    def _drag_move(self, e): self.root.geometry(f"+{e.x_root-self._dx}+{e.y_root-self._dy}")

    def _quit(self):
        if self._proc and self._proc.poll() is None:
            try: self._proc.terminate()
            except Exception: pass
        self.cfg.save(); self.root.destroy()

    def _draw_splash(self):
        cv = ctk.CTkCanvas(self.splash, width=520, height=300, bg=theme.BG, highlightthickness=0)
        cv.pack(fill="both", expand=True)
        draw_gradient(cv, 520, 300, "#0A0E1A", "#101A30", corner=0)
        cv.create_text(260,110,text="YZL",fill=theme.CYAN,font=(theme.ui_font(),72,"bold"))
        cv.create_text(260,178,text="Your Zone Launcher",fill=theme.SUB,font=(theme.ui_font(),16))
        bar = ctk.CTkProgressBar(self.splash, width=280, height=6, corner_radius=3, fg_color=theme.CARD_2, progress_color=theme.GRAD_BOT)
        bar.place(x=120, y=236)
        def anim(i=0):
            try:
                bar.set(min(1.0, i/100))
                if i < 100: self.splash.after(12, lambda: anim(i+1))
            except Exception: pass
        anim()
    def _close_splash(self):
        try: self.splash.destroy()
        except Exception: pass

    def notify(self, title, msg=""):
        if self.toast:
            try: self.toast.destroy()
            except Exception: pass
        card = Card(self.root, corner_radius=14)
        self.toast = ctk.CTkLabel(card, text=f"{title}\n{msg}", text_color=theme.TEXT, justify="left", font=(theme.ui_font(),13), fg_color="transparent", padx=22, pady=14)
        self.toast.pack()
        card.place(relx=0.5, y=TITLE_H+12, anchor="n"); card.lift()
        card.after(3600, card.destroy)

    def set_status(self, text, progress=None):
        def _set():
            self.status_label.configure(text=text)
            if progress is not None: self.progress.set(min(1.0, max(0.0, progress)))
        self._evq.put(_set)
    def clear_progress(self):
        def _clear():
            self.status_label.configure(text="就绪"); self.progress.set(0)
        self._evq.put(_clear)
    def run_async(self, fn, on_done=None, on_error=None):
        def worker():
            try:
                result = fn()
                if on_done: self._evq.put(lambda: on_done(result))
            except Exception as e:
                if on_error: self._evq.put(lambda: on_error(e))
                else: self._evq.put(lambda: self.notify("操作失败", str(e)))
                self._evq.put(self.clear_progress)
        threading.Thread(target=worker, daemon=True).start()
    def add_log(self, line): self._evq.put(lambda: self.pages["console"].append(line))
    def clear_log(self): self._evq.put(lambda: self.pages["console"].clear())
    def _poll(self):
        try:
            while True:
                fn = self._evq.get_nowait()
                try: fn()
                except Exception: pass
        except queue.Empty: pass
        self.root.after(100, self._poll)

def run():
    app = App()
    app.root.mainloop()
