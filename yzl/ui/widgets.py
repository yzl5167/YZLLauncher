"""通用 UI 组件：卡片、渐变按钮、徽标、图标加载缓存。"""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

import customtkinter as ctk
from PIL import Image

from yzl import theme


def _sys_font() -> str:
    import sys
    if sys.platform.startswith("win"):
        return "Microsoft YaHei UI"
    if sys.platform == "darwin":
        return "PingFang SC"
    return "Noto Sans CJK SC"


def icon_path(url: str) -> Optional[Path]:
    """把远程图标缓存到本地 .cache/icons，返回本地路径（失败返回 None）。"""
    try:
        from yzl.core.net import get_bytes
        from yzl.constants import app_root
        cache = app_root() / ".cache" / "icons"
        cache.mkdir(parents=True, exist_ok=True)
        name = hashlib.sha1(url.encode()).hexdigest() + ".png"
        dest = cache / name
        if dest.exists():
            return dest
        data = get_bytes(url, timeout=15)
        if not data:
            return None
        dest.write_bytes(data)
        return dest
    except Exception:
        return None


def load_icon_photo(url: str, size: int) -> Optional[ctk.CTkImage]:
    """下载并缩放图标为 PhotoImage，失败返回 None。"""
    p = icon_path(url)
    if not p:
        return None
    try:
        img = Image.open(p)
        img = img.resize((size, size), Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
    except Exception:
        return None


class Card(ctk.CTkFrame):
    def __init__(self, master, *a, **kw):
        kw.setdefault("fg_color", theme.CARD)
        kw.setdefault("border_color", theme.BORDER)
        kw.setdefault("border_width", 1)
        super().__init__(master, *a, **kw)


def tag(master, text, color="#8A97B5") -> ctk.CTkLabel:
    return ctk.CTkLabel(
        master, text=text, text_color=color, corner_radius=8,
        fg_color=theme.CARD_2, font=(_sys_font(), 10),
        padx=8, pady=2,
    )


class GradientButton(ctk.CTkButton):
    def __init__(self, master, text="", command=None, width=160, height=44, corner=14, font_size=15, **kw):
        super().__init__(
            master, text=text, command=command, width=width, height=height,
            corner_radius=corner, font=(_sys_font(), font_size),
            fg_color="#1E2A46", hover_color="#294066", text_color="#FFFFFF",
            **kw,
        )


class ProgressBar(ctk.CTkFrame):
    def __init__(self, master, width=300, height=10, color=theme.CYAN):
        super().__init__(master, fg_color=theme.CARD_2, width=width, height=height, corner_radius=height // 2)
        self._fill = ctk.CTkFrame(self, fg_color=color, corner_radius=height // 2, width=0)
        self._fill.pack(side="left", fill="y")
        self._pct = 0.0
        self._width = width

    def set(self, pct: float) -> None:
        self._pct = max(0.0, min(1.0, pct))
        try:
            w = int(self._width * self._pct)
            self._fill.configure(width=max(w, 2))
        except Exception:
            pass

    def get(self) -> float:
        return self._pct


def attach_gradient(canvas, c1: str, c2: str, corner: int = 16) -> None:
    """给 CTkCanvas 画一条渐变背景。"""
    try:
        canvas.update_idletasks()
        w = max(canvas.winfo_width(), 1)
        h = max(canvas.winfo_height(), 1)
        canvas.delete("all")
        r = int(corner)
        canvas.create_rectangle(0, 0, w, h, fill=c1, outline="")
        steps = 48
        for i in range(steps):
            f = i / steps
            col = _blend(c1, c2, f)
            canvas.create_rectangle(0, int(h * i / steps), w, int(h * (i + 1) / steps), fill=col, outline="")
        canvas.create_rectangle(0, 0, w, h, outline=c2, width=1)
    except Exception:
        pass


def _blend(a: str, b: str, f: float) -> str:
    def _c(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))

    ca, cb = _c(a), _c(b)
    col = tuple(int(ca[i] + (cb[i] - ca[i]) * f) for i in range(3))
    return "#%02x%02x%02x" % col
