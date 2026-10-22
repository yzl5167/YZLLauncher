"""UI 主题：配色与字体。"""
from __future__ import annotations
import tkinter.font as tkfont

BG = "#0A0E1A"
CARD = "#111827"
CARD_2 = "#182136"
BORDER = "#243352"
TEXT = "#EAF0FF"
SUB = "#8FA0C0"
CYAN = "#22D3EE"
VIOLET = "#8B5CF6"
PINK = "#F472B6"
GREEN = "#34D399"
AMBER = "#FBBF24"
RED = "#F87171"
GRAD_TOP = "#22D3EE"
GRAD_BOT = "#8B5CF6"
_cached_font = None

def ui_font() -> str:
    global _cached_font
    if _cached_font:
        return _cached_font
    try:
        families = set(tkfont.families())
    except Exception:
        families = set()
    for name in ("Microsoft YaHei UI", "Microsoft YaHei", "PingFang SC", "Segoe UI", "Noto Sans CJK SC", "DejaVu Sans"):
        if name in families:
            _cached_font = name
            return name
    _cached_font = "TkDefaultFont"
    return _cached_font
