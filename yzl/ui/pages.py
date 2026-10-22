"""六个功能页。"""
from __future__ import annotations
import subprocess
import time
from pathlib import Path
from tkinter import filedialog
import customtkinter as ctk
from yzl.core import auth, launcher as lc, mods as mods_core, versions as vc
from yzl.core.config import Config
from yzl.ui import theme
from yzl.ui.widgets import Card, GradientButton, attach_gradient, tag

class Page(ctk.CTkFrame):
    def __init__(self, master, app):
        super().__init__(master, fg_color=theme.BG, corner_radius=0)
        self.app = app
    def on_show(self): pass

class HomePage(Page):
    def on_show(self):
        for w in self.winfo_children(): w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=28, pady=22)
        banner = Card(pad, corner_radius=20, border_width=0)
        banner.pack(fill="x", pady=(0,18))
        cv = ctk.CTkCanvas(banner, height=96, bg=theme.CARD, highlightthickness=0); cv.pack(fill="x")
        attach_gradient(cv, "#101A2E", "#151E3A", corner=0)
        name = (self.app.cfg.current_account() or {}).get("name", "玩家")
        cv.create_text(28,48,anchor="w",text=f"欢迎回来，{name}",fill="#FFFFFF",font=(theme.ui_font(),22,"bold"))
        cv.create_text(28,76,anchor="w",text="YZL 启动器 · 生电向 · 高性能 · 纯净启动",fill=theme.SUB,font=(theme.ui_font(),12))
        row = ctk.CTkFrame(pad, fg_color="transparent"); row.pack(fill="both", expand=True)
        left = Card(row, corner_radius=20); left.pack(side="left", fill="both", expand=True, padx=(0,12))
        ctk.CTkLabel(left, text="启动配置", text_color=theme.TEXT, font=(theme.ui_font(),16,"bold")).pack(anchor="w", padx=22, pady=(20,14))
        self.ver_menu = ctk.CTkOptionMenu(left, values=[], width=280, height=40, corner_radius=12, fg_color=theme.CARD_2, button_color=theme.CARD_2, button_hover_color=theme.BORDER, text_color=theme.TEXT, dropdown_fg_color=theme.CARD_2, dropdown_hover_color=theme.BORDER, font=(theme.ui_font(),13), dropdown_font=(theme.ui_font(),13))
        self.ver_menu.pack(anchor="w", padx=22, pady=4)
        ctk.CTkLabel(left, text="选择已安装版本", text_color=theme.SUB, font=(theme.ui_font(),11)).pack(anchor="w", padx=22, pady=(0,12))
        self.acc_menu = ctk.CTkOptionMenu(left, values=[], width=280, height=40, corner_radius=12, fg_color=theme.CARD_2, button_color=theme.CARD_2, button_hover_color=theme.BORDER, text_color=theme.TEXT, dropdown_fg_color=theme.CARD_2, dropdown_hover_color=theme.BORDER, font=(theme.ui_font(),13), dropdown_font=(theme.ui_font(),13))
        self.acc_menu.pack(anchor="w", padx=22, pady=4)
        ctk.CTkLabel(left, text="选择账户（离线模式）", text_color=theme.SUB, font=(theme.ui_font(),11)).pack(anchor="w", padx=22, pady=(0,16))
        self.launch_btn = GradientButton(left, text="启 动 游 戏", command=self._launch, width=300, height=64, corner=22, font_size=20)
        self.launch_btn.pack(anchor="w", padx=22, pady=8)
        quick = ctk.CTkFrame(left, fg_color="transparent"); quick.pack(anchor="w", padx=22, pady=(6,20))
        for text, cmd in (("打开游戏目录", self._open_gamedir), ("打开模组目录", self._open_modsdir)):
            ctk.CTkButton(quick, text=text, width=120, height=34, corner_radius=12, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12), command=cmd).pack(side="left", padx=(0,10))
        right = Card(row, width=320, corner_radius=20); right.pack(side="right", fill="y", padx=(12,0)); right.pack_propagate(False)
        ctk.CTkLabel(right, text="版本详情", text_color=theme.TEXT, font=(theme.ui_font(),16,"bold")).pack(anchor="w", padx=20, pady=(20,10))
        self.detail = ctk.CTkLabel(right, text="", text_color=theme.SUB, justify="left", anchor="w", font=(theme.ui_font(),12))
        self.detail.pack(anchor="w", padx=20, pady=4)
        ctk.CTkLabel(right, text="提示：1.21 及以上需要 Java 21；\n生电请优先安装 Fabric + Carpet。", text_color=theme.SUB, justify="left", anchor="w", font=(theme.ui_font(),11), fg_color=theme.CARD_2, corner_radius=10, padx=12, pady=10).pack(anchor="w", padx=20, pady=(18,12))
        self._refresh()
    def _refresh(self):
        cfg = self.app.cfg; local = vc.list_local_versions(cfg.game_dir())
        cur = cfg.get("current_version")
        if cur not in local:
            cur = local[0] if local else None
            if cur: cfg.set("current_version", cur)
        self.ver_menu.configure(values=local or ["（未安装版本）"]); self.ver_menu.set(cur or "（未安装版本）")
        accs = cfg.accounts(); labels = [f"{a['name']}（离线）" for a in accs] or ["（未添加账户）"]
        self.acc_menu.configure(values=labels)
        cur_acc = cfg.current_account()
        self.acc_menu.set(cur_acc["name"]+"（离线）" if cur_acc else "（未添加账户）")
        self._update_detail(cur)
    def _update_detail(self, vid):
        if not vid: self.detail.configure(text="尚未选择版本"); return
        try:
            data = vc.resolve_version(self.app.cfg.game_dir(), vid)
            parent = data.get("inheritsFrom") or vid
            pdata = vc.load_version_json(self.app.cfg.game_dir(), parent)
            jv = pdata.get("javaVersion", {}).get("majorVersion", "?")
            self.detail.configure(text=f"版本　　{data.get('id')}\n类型　　{data.get('type','release')}\n核心　　{parent}\nJava　　{'{0}'.format(jv)}\n内存　　{int(self.app.cfg.get('memory_mb'))} MB")
        except Exception: self.detail.configure(text="版本信息读取失败")
    def _launch(self):
        cfg = self.app.cfg
        if self.app._launching: self.app.notify("已在运行", "游戏进程正在运行中"); return
        vid = self.ver_menu.get(); acc_label = self.acc_menu.get()
        if not vid or vid.startswith("（"): self.app.notify("未选择版本", "请先到「版本管理」安装一个版本"); return
        if not acc_label or acc_label.startswith("（"): self.app.notify("未添加账户", "请先到「账户」添加一个离线账户"); return
        acc = next((a for a in cfg.accounts() if a["name"]==acc_label.replace("（离线）","")), None)
        if not acc: self.app.notify("账户无效", "请重新选择账户"); return
        try: spec = lc.build_launch_spec(cfg, vid, acc)
        except Exception as e: self.app.notify("无法启动", str(e)); return
        self.app._launching = True; self.app.switch("console"); self.app.clear_log()
        self.app.add_log(f"[YZL] 启动版本 {vid} · 内存 {cfg.get('memory_mb')}MB")
        self.app.add_log(f"[YZL] 游戏目录 {cfg.game_dir()}")
        self.app.add_log(f"[YZL] 启动命令:\n  {' '.join(spec.cmd[:24])} ...")
        def on_exit(rc): self.app._launching=False; self.app.add_log(f"[YZL] 游戏已退出（代码 {rc}）")
        try:
            proc = lc.launch(spec, on_line=self.app.add_log, on_exit=on_exit); self.app._proc = proc
        except Exception as e: self.app._launching=False; self.app.notify("启动失败", str(e))
    def _open_gamedir(self): d=self.app.cfg.game_dir(); d.mkdir(parents=True, exist_ok=True); _open_path(d)
    def _open_modsdir(self): d=self.app.cfg.game_dir()/"mods"; d.mkdir(parents=True, exist_ok=True); _open_path(d)

class VersionsPage(Page):
    def on_show(self):
        for w in self.winfo_children(): w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent"); pad.pack(fill="both", expand=True, padx=24, pady=18)
        head = ctk.CTkFrame(pad, fg_color="transparent"); head.pack(fill="x", pady=(0,14))
        ctk.CTkLabel(head, text="版本管理", text_color=theme.TEXT, font=(theme.ui_font(),20,"bold")).pack(side="left")
        ctk.CTkButton(head, text="↻ 刷新", width=90, height=34, corner_radius=12, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12), command=self._load_all).pack(side="right")
        body = ctk.CTkFrame(pad, fg_color="transparent"); body.pack(fill="both", expand=True)
        left = Card(body, width=300, corner_radius=18); left.pack(side="left", fill="y", padx=(0,14)); left.pack_propagate(False)
        ctk.CTkLabel(left, text="已安装", text_color=theme.TEXT, font=(theme.ui_font(),15,"bold")).pack(anchor="w", padx=16, pady=(14,8))
        self.local_box = ctk.CTkScrollableFrame(left, fg_color="transparent"); self.local_box.pack(fill="both", expand=True, padx=10, pady=(0,10))
        right = Card(body, corner_radius=18); right.pack(side="right", fill="both", expand=True)
        top = ctk.CTkFrame(right, fg_color="transparent"); top.pack(fill="x", padx=16, pady=(14,8))
        ctk.CTkLabel(top, text="在线版本（全部 Java 版历史版本）", text_color=theme.TEXT, font=(theme.ui_font(),15,"bold")).pack(side="left")
        self.filter = ctk.CTkSegmentedButton(top, values=["全部","正式版","快照","远古"], height=30, corner_radius=10, fg_color=theme.CARD_2, selected_color=theme.BORDER, selected_hover_color=theme.BORDER, text_color=theme.SUB, font=(theme.ui_font(),12), command=lambda _: self._render_online())
        self.filter.pack(side="right")
        self.search = ctk.CTkEntry(right, placeholder_text="搜索版本号…", height=34, corner_radius=10, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12))
        self.search.pack(fill="x", padx=16, pady=(0,8)); self.search.bind("<KeyRelease>", lambda e: self._render_online())
        self.online_box = ctk.CTkScrollableFrame(right, fg_color="transparent"); self.online_box.pack(fill="both", expand=True, padx=10, pady=(0,8))
        self._load_local(); self._load_all()
    def _load_local(self):
        for w in self.local_box.winfo_children(): w.destroy()
        for vid in sorted(vc.list_local_versions(self.app.cfg.game_dir()), key=str.lower):
            row = ctk.CTkFrame(self.local_box, fg_color=theme.CARD_2, corner_radius=10); row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=vid, text_color=theme.TEXT, anchor="w", font=(theme.ui_font(),12)).pack(side="left", padx=10, pady=8)
            ctk.CTkButton(row, text="启动", width=52, height=26, corner_radius=8, fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN, font=(theme.ui_font(),11), command=lambda v=vid: self._launch_version(v)).pack(side="right", padx=(2,8), pady=6)
            ctk.CTkButton(row, text="删", width=34, height=26, corner_radius=8, fg_color=theme.CARD_2, hover_color=theme.RED, text_color=theme.SUB, font=(theme.ui_font(),11), command=lambda v=vid: self._delete_version(v)).pack(side="right", pady=6)
    def _launch_version(self, vid): self.app.cfg.set("current_version", vid); self.app.switch("home")
    def _delete_version(self, vid):
        import shutil; shutil.rmtree(vc.versions_dir(self.app.cfg.game_dir())/vid, ignore_errors=True); self._load_local()
    def _load_all(self):
        self.app.set_status("正在获取版本清单…", 0.05)
        def fn(): return vc.all_versions("bmclapi")
        def done(versions): self._all = versions; self._render_online(); self.app.clear_progress()
        self.app.run_async(fn, done)
    def _render_online(self):
        if not hasattr(self, "_all") or not self._all: return
        f = self.filter.get(); kw = self.search.get().strip().lower()
        items = []
        for v in self._all:
            vid = v.get("id",""); typ = v.get("type","release")
            if f=="正式版" and typ!="release": continue
            if f=="快照" and typ not in ("snapshot","old_beta","old_alpha"): continue
            if f=="远古" and typ not in ("old_beta","old_alpha"): continue
            if kw and kw not in vid.lower(): continue
            items.append(v)
            if len(items)>=90: break
        for w in self.online_box.winfo_children(): w.destroy()
        local = vc.list_local_versions(self.app.cfg.game_dir())
        for v in items:
            vid = v.get("id","")
            row = ctk.CTkFrame(self.online_box, fg_color=theme.CARD_2, corner_radius=10); row.pack(fill="x", pady=3)
            ctk.CTkLabel(row, text=vid, text_color=theme.TEXT, anchor="w", font=(theme.ui_font(),12)).pack(side="left", padx=10, pady=8)
            tag(row, v.get("type",""), color=theme.CYAN if v.get("type")=="release" else theme.AMBER if v.get("type")=="snapshot" else theme.SUB).pack(side="left", padx=4)
            ctk.CTkLabel(row, text=(v.get("releaseTime") or "")[:10], text_color=theme.SUB, font=(theme.ui_font(),10)).pack(side="left", padx=6)
            if vid in local: tag(row, "已安装", color=theme.GREEN).pack(side="right", padx=8)
            else:
                ctk.CTkButton(row, text="安装", width=54, height=26, corner_radius=8, fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN, font=(theme.ui_font(),11), command=lambda v=vid: self._install_version(v, False)).pack(side="right", padx=(2,8), pady=6)
                ctk.CTkButton(row, text="装Fabric", width=70, height=26, corner_radius=8, fg_color=theme.CARD_2, hover_color=theme.VIOLET, text_color=theme.VIOLET, font=(theme.ui_font(),11), command=lambda v=vid: self._install_version(v, True)).pack(side="right", pady=6)
    def _install_version(self, vid, fabric):
        cfg = self.app.cfg
        def progress(stage, done, total):
            pct = done/total if total else 0; self.app.set_status(f"正在安装 {vid} · {stage} {done}/{total}", pct)
        def work():
            vc.install_version(cfg.game_dir(), vid, cfg.get("mirror"), progress)
            if fabric: vc.install_fabric(cfg.game_dir(), vid, cfg.get("mirror"), progress)
        def done(_):
            self.app.clear_progress(); self.app.notify("安装完成", f"{vid}" + ("（含 Fabric）" if fabric else "")); self._load_local(); self._render_online()
        self.app.run_async(work, done)

class ModsPage(Page):
    def on_show(self):
        for w in self.winfo_children(): w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent"); pad.pack(fill="both", expand=True, padx=24, pady=18)
        head = ctk.CTkFrame(pad, fg_color="transparent"); head.pack(fill="x", pady=(0,12))
        ctk.CTkLabel(head, text="模组中心", text_color=theme.TEXT, font=(theme.ui_font(),20,"bold")).pack(side="left")
        ctk.CTkLabel(head, text="数据来源 Modrinth · 需 Fabric 版本", text_color=theme.SUB, font=(theme.ui_font(),11)).pack(side="left", padx=12, pady=6)
        ctk.CTkButton(head, text="📂 打开模组目录", width=110, height=34, corner_radius=12, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12), command=lambda: _open_path(self.app.cfg.game_dir()/"mods")).pack(side="right")
        search_row = ctk.CTkFrame(pad, fg_color="transparent"); search_row.pack(fill="x", pady=(0,12))
        self.mc_label = ctk.CTkLabel(search_row, text="", text_color=theme.CYAN, font=(theme.ui_font(),12)); self.mc_label.pack(side="left", padx=(0,12))
        self.mod_search = ctk.CTkEntry(search_row, placeholder_text="搜索模组（如 lithium / carpet）…", height=36, corner_radius=10, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12))
        self.mod_search.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(search_row, text="搜索", width=80, height=36, corner_radius=10, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN, font=(theme.ui_font(),12), command=self._search).pack(side="left", padx=(10,0))
        self.list_box = ctk.CTkScrollableFrame(pad, fg_color="transparent"); self.list_box.pack(fill="both", expand=True)
        self._curated()
    def _mc_version(self):
        cfg = self.app.cfg; v = cfg.get("current_version") or ""
        if "fabric" in v:
            try: return vc.load_version_json(cfg.game_dir(), v).get("inheritsFrom") or "1.21.1"
            except Exception: return "1.21.1"
        return v or "1.21.1"
    def _curated(self):
        self.mc_label.configure(text=f"当前适配版本：{self._mc_version()}（Fabric）")
        for w in self.list_box.winfo_children(): w.destroy()
        for slug, title, desc in mods_core.CURATED: self._add_card(slug, title, desc)
    def _search(self):
        q = self.mod_search.get().strip()
        if not q: self._curated(); return
        self.app.set_status("正在搜索模组…", 0.1)
        def work(): return mods_core.search_mods(q, self._mc_version())
        def done(mods):
            self.app.clear_progress()
            for w in self.list_box.winfo_children(): w.destroy()
            if not mods:
                ctk.CTkLabel(self.list_box, text="没有找到适配该版本的模组", text_color=theme.SUB, font=(theme.ui_font(),13)).pack(pady=20); return
            for m in mods: self._add_card(m.slug, m.title, m.description)
        self.app.run_async(work, done)
    def _add_card(self, slug, title, desc):
        card = Card(self.list_box, corner_radius=14); card.pack(fill="x", pady=4)
        inner = ctk.CTkFrame(card, fg_color="transparent"); inner.pack(fill="x", padx=14, pady=10)
        ctk.CTkLabel(inner, text=title, text_color=theme.TEXT, anchor="w", font=(theme.ui_font(),14,"bold")).pack(anchor="w")
        ctk.CTkLabel(inner, text=desc or "（无简介）", text_color=theme.SUB, anchor="w", font=(theme.ui_font(),11), wraplength=560, justify="left").pack(anchor="w", pady=(4,0))
        ctk.CTkButton(inner, text="安装", width=74, height=30, corner_radius=10, fg_color=theme.CARD_2, hover_color=theme.GREEN, text_color=theme.GREEN, font=(theme.ui_font(),12), command=lambda s=slug: self._install(slug=s, title=title)).pack(anchor="e", pady=(4,0))
    def _install(self, slug, title):
        mc = self._mc_version(); self.app.set_status(f"正在获取 {title} 版本…", 0.1)
        def work():
            files = mods_core.get_mod_versions(slug, mc, "fabric")
            if not files: raise RuntimeError(f"{title} 没有适配 {mc} 的 Fabric 版本")
            f = files[0]; self.app.set_status(f"正在下载 {f.filename}", 0.2)
            def p(done, total): self.app.set_status(f"正在下载 {f.filename}", done/total if total else 0.2)
            mods_core.install_mod(f, self.app.cfg.game_dir(), p); return f.filename
        def done(fname): self.app.clear_progress(); self.app.notify("模组已安装", f"{title} → mods/{fname}\n（Fabric 版本，重启游戏生效）")
        self.app.run_async(work, done)

class AccountsPage(Page):
    def on_show(self):
        for w in self.winfo_children(): w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent"); pad.pack(fill="both", expand=True, padx=24, pady=18)
        ctk.CTkLabel(pad, text="账户管理", text_color=theme.TEXT, font=(theme.ui_font(),20,"bold")).pack(anchor="w", pady=(0,16))
        card = Card(pad, width=480, corner_radius=18); card.pack(anchor="w"); card.pack_propagate(False)
        ctk.CTkLabel(card, text="添加离线账户", text_color=theme.TEXT, font=(theme.ui_font(),15,"bold")).pack(anchor="w", padx=18, pady=(16,10))
        row = ctk.CTkFrame(card, fg_color="transparent"); row.pack(fill="x", padx=18, pady=(0,16))
        self.name_entry = ctk.CTkEntry(row, placeholder_text="玩家名", height=40, corner_radius=12, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),13))
        self.name_entry.pack(side="left", fill="x", expand=True)
        ctk.CTkButton(row, text="＋ 添加", width=90, height=40, corner_radius=12, fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN, font=(theme.ui_font(),13), command=self._add).pack(side="left", padx=(10,0))
        ctk.CTkLabel(pad, text="已保存账户", text_color=theme.TEXT, font=(theme.ui_font(),15,"bold")).pack(anchor="w", pady=(22,10))
        self.list_card = Card(pad, corner_radius=18); self.list_card.pack(fill="x"); self._render()
    def _render(self):
        for w in self.list_card.winfo_children(): w.destroy()
        accs = self.app.cfg.accounts(); cur = self.app.cfg.current_account()
        if not accs:
            ctk.CTkLabel(self.list_card, text="还没有账户，先在上方添加一个吧", text_color=theme.SUB, font=(theme.ui_font(),12)).pack(padx=18, pady=18); return
        for a in accs:
            row = ctk.CTkFrame(self.list_card, fg_color=theme.CARD_2, corner_radius=12); row.pack(fill="x", padx=12, pady=4)
            ctk.CTkLabel(row, text=a["name"], text_color=theme.TEXT, anchor="w", font=(theme.ui_font(),13,"bold")).pack(side="left", padx=12, pady=10)
            if cur and a["name"]==cur["name"]: tag(row, "当前使用", color=theme.GREEN).pack(side="left", padx=6)
            ctk.CTkLabel(row, text=a["uuid"][:18]+"…", text_color=theme.SUB, font=(theme.ui_font(),10)).pack(side="left", padx=8)
            ctk.CTkButton(row, text="使用", width=54, height=28, corner_radius=9, fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN, font=(theme.ui_font(),11), command=lambda n=a["name"]: self._use(n)).pack(side="right", padx=(2,10), pady=8)
            ctk.CTkButton(row, text="删除", width=54, height=28, corner_radius=9, fg_color=theme.CARD_2, hover_color=theme.RED, text_color=theme.RED, font=(theme.ui_font(),11), command=lambda n=a["name"]: self._del(n)).pack(side="right", pady=8)
    def _add(self):
        name = self.name_entry.get().strip()
        if not name: self.app.notify("名字为空", "请输入玩家名"); return
        cfg = self.app.cfg; accs = cfg.accounts()
        if any(a["name"]==name for a in accs): self.app.notify("已存在", "该账户已存在"); return
        accs.append(auth.make_offline_account(name)); cfg.set("accounts", accs); cfg.set("current_account", name)
        self.name_entry.delete(0, "end"); self._render(); self.app.notify("已添加", f"账户 {name}（离线）")
    def _use(self, name): self.app.cfg.set("current_account", name); self._render()
    def _del(self, name):
        cfg = self.app.cfg; accs = [a for a in cfg.accounts() if a["name"]!=name]
        cfg.set("accounts", accs)
        if cfg.get("current_account")==name: cfg.set("current_account", accs[0]["name"] if accs else None)
        self._render()

class SettingsPage(Page):
    def on_show(self):
        for w in self.winfo_children(): w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent"); pad.pack(fill="both", expand=True, padx=24, pady=18)
        ctk.CTkLabel(pad, text="设置", text_color=theme.TEXT, font=(theme.ui_font(),20,"bold")).pack(anchor="w", pady=(0,16))
        card = Card(pad, width=640, corner_radius=18); card.pack(anchor="w"); card.pack_propagate(False)
        inner = ctk.CTkFrame(card, fg_color="transparent"); inner.pack(fill="x", padx=20, pady=18)
        cfg = self.app.cfg
        def row(label):
            r = ctk.CTkFrame(inner, fg_color="transparent"); r.pack(fill="x", pady=7)
            ctk.CTkLabel(r, text=label, text_color=theme.TEXT, width=140, anchor="w", font=(theme.ui_font(),13)).pack(side="left"); return r
        r = row("内存分配")
        self.mem_label = ctk.CTkLabel(r, text=f"{cfg.get('memory_mb')} MB", text_color=theme.CYAN, font=(theme.ui_font(),13)); self.mem_label.pack(side="right")
        self.mem_slider = ctk.CTkSlider(r, from_=1024, to=8192, number_of_steps=28, width=300, fg_color=theme.CARD_2, progress_color=theme.CYAN, button_color=theme.CYAN, command=lambda v: self.mem_label.configure(text=f"{int(v)} MB")); self.mem_slider.set(cfg.get("memory_mb")); self.mem_slider.pack(side="right", padx=(0,16))
        r = row("Java 路径")
        self.java_entry = ctk.CTkEntry(r, height=34, corner_radius=10, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12)); self.java_entry.insert(0, cfg.get("java_path") or ""); self.java_entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        ctk.CTkButton(r, text="浏览", width=56, height=32, corner_radius=10, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN, font=(theme.ui_font(),12), command=self._pick_java).pack(side="left")
        ctk.CTkButton(r, text="自动检测", width=76, height=32, corner_radius=10, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN, font=(theme.ui_font(),12), command=self._auto_java).pack(side="left", padx=(6,0))
        r = row("游戏目录")
        self.dir_entry = ctk.CTkEntry(r, height=34, corner_radius=10, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12)); self.dir_entry.insert(0, str(cfg.game_dir())); self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0,8))
        ctk.CTkButton(r, text="浏览", width=56, height=32, corner_radius=10, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.CYAN, font=(theme.ui_font(),12), command=self._pick_dir).pack(side="left")
        r = row("下载源")
        self.mirror_menu = ctk.CTkOptionMenu(r, values=["bmclapi（国内加速）","mojang（官方）"], width=220, height=34, corner_radius=10, fg_color=theme.CARD_2, button_color=theme.CARD_2, button_hover_color=theme.BORDER, text_color=theme.TEXT, dropdown_fg_color=theme.CARD_2, dropdown_hover_color=theme.BORDER, font=(theme.ui_font(),12), dropdown_font=(theme.ui_font(),12)); self.mirror_menu.set("bmclapi（国内加速）" if cfg.get("mirror")=="bmclapi" else "mojang（官方）"); self.mirror_menu.pack(side="left")
        r = row("窗口分辨率")
        self.w_entry = ctk.CTkEntry(r, width=90, height=32, corner_radius=10, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12)); self.w_entry.insert(0, str(cfg.get("width") or "")); self.w_entry.pack(side="left")
        ctk.CTkLabel(r, text="×", text_color=theme.SUB).pack(side="left", padx=6)
        self.h_entry = ctk.CTkEntry(r, width=90, height=32, corner_radius=10, fg_color=theme.CARD_2, border_color=theme.BORDER, text_color=theme.TEXT, font=(theme.ui_font(),12)); self.h_entry.insert(0, str(cfg.get("height") or "")); self.h_entry.pack(side="left")
        ctk.CTkLabel(r, text="（留空=游戏默认）", text_color=theme.SUB, font=(theme.ui_font(),10)).pack(side="left", padx=8)
        r = row("下载线程")
        self.th_label = ctk.CTkLabel(r, text=f"{cfg.get('download_threads')}", text_color=theme.CYAN, font=(theme.ui_font(),13)); self.th_label.pack(side="right")
        self.th_slider = ctk.CTkSlider(r, from_=2, to=16, number_of_steps=14, width=300, fg_color=theme.CARD_2, progress_color=theme.CYAN, button_color=theme.CYAN, command=lambda v: self.th_label.configure(text=f"{int(v)}")); self.th_slider.set(cfg.get("download_threads")); self.th_slider.pack(side="right", padx=(0,16))
        btns = ctk.CTkFrame(pad, fg_color="transparent"); btns.pack(anchor="w", pady=(18,0))
        ctk.CTkButton(btns, text="💾 保存设置", width=140, height=40, corner_radius=12, fg_color=theme.CARD_2, hover_color=theme.CYAN, text_color=theme.CYAN, font=(theme.ui_font(),14,"bold"), command=self._save).pack(side="left")
        ctk.CTkLabel(btns, text="提示：1.21 版本需要 Java 21；自动检测会优先使用已安装的 JDK。", text_color=theme.SUB, font=(theme.ui_font(),11)).pack(side="left", padx=16)
    def _pick_java(self):
        p = filedialog.askopenfilename(title="选择 java 可执行文件", filetypes=[("Java","*.exe"),("所有文件","*")])
        if p: self.java_entry.delete(0,"end"); self.java_entry.insert(0, p)
    def _auto_java(self):
        j = lc.find_java(self.java_entry.get())
        if j: self.java_entry.delete(0,"end"); self.java_entry.insert(0, j); self.app.notify("已检测到 Java", j)
        else: self.app.notify("未找到 Java", "请手动指定 Java 路径")
    def _pick_dir(self):
        p = filedialog.askdirectory(title="选择游戏目录")
        if p: self.dir_entry.delete(0,"end"); self.dir_entry.insert(0, p)
    def _save(self):
        cfg = self.app.cfg
        cfg.set("memory_mb", int(self.mem_slider.get())); cfg.set("java_path", self.java_entry.get().strip()); cfg.set("game_dir", self.dir_entry.get().strip() or None); cfg.set("mirror", "bmclapi" if "bmclapi" in self.mirror_menu.get() else "mojang")
        try:
            cfg.set("width", int(self.w_entry.get().strip() or 0)); cfg.set("height", int(self.h_entry.get().strip() or 0))
        except ValueError: self.app.notify("分辨率无效", "请输入整数"); return
        cfg.set("download_threads", int(self.th_slider.get())); self.app.notify("已保存", "设置已写入 config.json")

class ConsolePage(Page):
    def on_show(self):
        for w in self.winfo_children(): w.destroy()
        pad = ctk.CTkFrame(self, fg_color="transparent"); pad.pack(fill="both", expand=True, padx=24, pady=18)
        head = ctk.CTkFrame(pad, fg_color="transparent"); head.pack(fill="x", pady=(0,12))
        ctk.CTkLabel(head, text="控制台", text_color=theme.TEXT, font=(theme.ui_font(),20,"bold")).pack(side="left")
        ctk.CTkButton(head, text="清空", width=70, height=32, corner_radius=10, fg_color=theme.CARD_2, hover_color=theme.BORDER, text_color=theme.SUB, font=(theme.ui_font(),12), command=self.clear).pack(side="right")
        card = Card(pad, corner_radius=16); card.pack(fill="both", expand=True)
        self.text = ctk.CTkTextbox(card, fg_color="#0B101D", text_color="#C7D6F0", font=("Consolas",12), wrap="none", corner_radius=12, border_width=0, state="disabled")
        self.text.pack(fill="both", expand=True, padx=10, pady=10); self._lines = 0
    def append(self, line):
        try:
            self.text.configure(state="normal"); self.text.insert("end", line+"\n"); self._lines += 1
            if self._lines > 3000: self.text.delete("1.0","200.0"); self._lines = 3000
            self.text.see("end"); self.text.configure(state="disabled")
        except Exception: pass
    def clear(self):
        try:
            self.text.configure(state="normal"); self.text.delete("1.0","end"); self._lines = 0; self.text.configure(state="disabled")
        except Exception: pass

def _open_path(p):
    import sys, subprocess as sp
    try:
        if sys.platform.startswith("win"): sp.Popen(["explorer", str(p)])
        elif sys.platform == "darwin": sp.Popen(["open", str(p)])
        else: sp.Popen(["xdg-open", str(p)])
    except Exception: pass
