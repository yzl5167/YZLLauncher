"""自绘组件：渐变按钮、圆角渐变卡片等。"""
from __future__ import annotations
import math
import tkinter as tk
from typing import Callable, Optional
import customtkinter as ctk
from yzl.ui import theme

def lerp_color(c1: str, c2: str, t: float) -> str:
    def ch(c):
        c = c.lstrip("#")
        return tuple(int(c[i:i+2], 16) for i in (0, 2, 4))
    a, b = ch(c1), ch(c2)
    rgb = tuple(round(a[i] + (b[i]-a[i])*t) for i in range(3))
    return "#%02x%02x%02x" % rgb

def draw_gradient(canvas, w, h, c1, c2, corner=0, x0=0, y0=0):
    canvas.delete("gradient")
    corner = min(corner, h//2, w//2)
    for y in range(h):
        if y < corner:
            inset = corner - math.sqrt(max(0.0, corner*corner - (corner-y)**2))
        elif y >= h-corner:
            yy = h-1-y
            inset = corner - math.sqrt(max(0.0, corner*corner - (corner-yy)**2))
        else:
            inset = 0
        xa, xb = x0+inset, x0+w-inset
        if xb > xa:
            canvas.create_line(xa, y0+y, xb, y0+y, fill=lerp_color(c1, c2, y/max(1, h-1)), tags="gradient")

def attach_gradient(canvas, c1, c2, corner=0, x0=0, y0=0, h=None):
    def redraw(_e=None):
        w, hh = canvas.winfo_width(), h or canvas.winfo_height()
        if w > 2 and hh > 2:
            draw_gradient(canvas, w-x0*2, hh-y0*2, c1, c2, corner, x0, y0)
    canvas.bind("<Configure>", redraw)
    canvas.after(30, redraw)

class GradientButton(tk.Canvas):
    def __init__(self, master, text, command=None, width=300, height=68, corner=20, c1=theme.GRAD_TOP, c2=theme.GRAD_BOT, font_size=20, text_color="#FFFFFF", bold=True):
        super().__init__(master, width=width, height=height, bg=theme.BG, highlightthickness=0, bd=0)
        self.command = command
        self.w, self.h = width, height
        self.corner = corner
        self.c1, self.c2 = c1, c2
        self.text = text
        self.font_size = font_size
        self.text_color = text_color
        self.bold = bold
        self._hover = False
        self._pressed = False
        self.bind("<Button-1>", self._on_click)
        self.bind("<Enter>", lambda e: self._set_hover(True))
        self.bind("<Leave>", lambda e: self._set_hover(False))
        self.bind("<ButtonPress-1>", lambda e: self._set_pressed(True))
        self.bind("<ButtonRelease-1>", lambda e: self._set_pressed(False))
        self.redraw()
    def _set_hover(self, v):
        if v != self._hover:
            self._hover = v; self.redraw()
    def _set_pressed(self, v):
        if v != self._pressed:
            self._pressed = v; self.redraw()
    def _on_click(self, _e):
        if self.command:
            self.command()
    def redraw(self):
        c1, c2 = self.c1, self.c2
        if self._hover:
            c1 = lerp_color(c1, "#FFFFFF", 0.12); c2 = lerp_color(c2, "#FFFFFF", 0.12)
        if self._pressed:
            c1 = lerp_color(c1, "#000000", 0.18); c2 = lerp_color(c2, "#000000", 0.18)
        draw_gradient(self, self.w, self.h, c1, c2, self.corner)
        weight = "bold" if self.bold else "normal"
        self.create_text(self.w/2, self.h/2, text=self.text, fill=self.text_color, font=(theme.ui_font(), self.font_size, weight), tags="gradient")

class Card(ctk.CTkFrame):
    def __init__(self, master, **kw):
        kw.setdefault("fg_color", theme.CARD); kw.setdefault("corner_radius", 18)
        kw.setdefault("border_width", 1); kw.setdefault("border_color", theme.BORDER)
        super().__init__(master, **kw)

def tag(master, text, color=theme.CYAN, bg=theme.CARD_2, size=11):
    return ctk.CTkLabel(master, text=text, text_color=color, font=(theme.ui_font(), size), fg_color=bg, corner_radius=8, padx=8, pady=2)

def nav_button(master, text, command, selected=False):
    return ctk.CTkButton(master, text=text, command=command, anchor="w", font=(theme.ui_font(), 14), fg_color=theme.CARD_2 if selected else "transparent", hover_color=theme.CARD_2, text_color=theme.CYAN if selected else theme.TEXT, corner_radius=12, height=44, border_width=0)
