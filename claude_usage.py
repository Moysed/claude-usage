#!/usr/bin/env python
"""
Claude Usage — a tiny always-on-top widget showing your Claude plan limits,
fronted by Clawd, the official Claude Code pixel-crab mascot.

Design is research-matched to Claude Code's own terminal theme:
  - Clawd body   = rgb(215,119,87) = #D77757   (the real clawd_body colour)
  - background   = warm near-black                (Clawd's habitat is the terminal)
  - accent       = #FBBC04  (Claude Code "chromeYellow")
  - type         = Inter (substitute for Anthropic's Styrene B) + a serif wordmark

Clawd scuttles back and forth and changes mood with how much of your limit
you've burned (happy < 50% · normal 50-79% · tired >= 80%).
Click him and he shuts his eyes, grins, and pops a few hearts. 🦀

Right-click the mascot to swap Clawd for your own image (PNG/GIF — animated
GIFs play). Your pick paces and bobs with the same mood-driven rhythm. The
path is remembered in ~/.claude-usage.json; right-click → "Reset to Clawd"
to bring the crab back.

Reads live usage exactly like Claude Code's /usage:
  GET https://api.anthropic.com/api/oauth/usage  (Bearer token from ~/.claude/.credentials.json)
The token is owned + refreshed by Claude Code; this widget only reads it, never
stores or transmits it. Stdlib only. Run:  pythonw claude_usage.py
"""

import json
import math
import os
import threading
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog

CREDS = os.path.expanduser("~/.claude/.credentials.json")
CONFIG = os.path.expanduser("~/.claude-usage.json")
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"
REFRESH_MS = 60_000     # auto-refresh every 1 minute
FRAME_MS = 70

# Claude Code terminal palette
BG = "#0d0b0a"          # warm near-black
FG = "#ece7e1"
DIM = "#8a8178"
TRACK = "#2a221d"
GREEN = "#22c55e"
AMBER = "#f59e0b"
RED = "#ef4444"
CORAL = "#d77757"       # official clawd_body
CORAL_HI = "#e8a07f"
DARK = "#a85e3f"
EYE = "#1a1208"
WHITE = "#f4efe9"
HEART = "#e0556b"
GOLD = "#fbbc04"        # Claude Code chromeYellow accent

UI_FONT = "Segoe UI"    # → Inter if installed (Styrene substitute); set in App
SERIF = "Georgia"       # nods to Anthropic's Copernicus serif wordmark


def color_for(pct: float) -> str:
    if pct >= 90:
        return RED
    if pct >= 70:
        return AMBER
    return GREEN


def mood_for(pct: float) -> str:
    if pct >= 80:
        return "tired"
    if pct >= 50:
        return "normal"
    return "happy"


# ── config (remembers your custom mascot image) ──────────────────────────────
def load_config() -> dict:
    try:
        with open(CONFIG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict) -> None:
    try:
        with open(CONFIG, "w", encoding="utf-8") as f:
            json.dump(cfg, f)
    except Exception:
        pass


# ── data ────────────────────────────────────────────────────────────────────
def read_token() -> str | None:
    try:
        with open(CREDS, encoding="utf-8") as f:
            return json.load(f)["claudeAiOauth"]["accessToken"]
    except Exception:
        return None


def fetch_usage() -> tuple[dict | None, str | None]:
    tok = read_token()
    if not tok:
        return None, "no credentials — log in via Claude Code"
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": "Bearer " + tok,
            "anthropic-beta": "oauth-2025-04-20",
            "User-Agent": "claude-usage-widget",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read()), None
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return None, "session expired — open Claude Code"
        return None, f"HTTP {e.code}"
    except Exception:
        return None, "offline — retrying"


def fmt_reset(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        secs = int((dt - datetime.now(timezone.utc)).total_seconds())
        if secs <= 0:
            return "resetting…"
        d, rem = divmod(secs, 86400)
        h, rem = divmod(rem, 3600)
        m = rem // 60
        if d:
            return f"resets in {d}d {h}h"
        if h:
            return f"resets in {h}h {m}m"
        return f"resets in {m}m"
    except Exception:
        return ""


def make_clawd_icon(size: int = 32) -> tk.PhotoImage:
    """A little pixel Clawd crab icon (coral on black), no image deps."""
    g = [[BG] * size for _ in range(size)]

    def box(x0, y0, x1, y1, c):
        for y in range(max(0, y0), min(size, y1)):
            for x in range(max(0, x0), min(size, x1)):
                g[y][x] = c

    box(8, 13, 24, 24, CORAL)            # body
    box(6, 15, 26, 22, CORAL)
    box(2, 6, 8, 12, CORAL)              # left claw
    box(4, 8, 8, 10, BG)                 #   pincer
    box(24, 6, 30, 12, CORAL)            # right claw
    box(24, 8, 28, 10, BG)               #   pincer
    box(6, 12, 9, 16, CORAL)             # arms
    box(23, 12, 26, 16, CORAL)
    for lx in (9, 13, 18, 22):           # legs
        box(lx, 24, lx + 2, 28, DARK)
    box(11, 15, 14, 19, WHITE)           # eyes
    box(18, 15, 21, 19, WHITE)
    box(12, 16, 14, 18, EYE)
    box(19, 16, 21, 18, EYE)
    img = tk.PhotoImage(width=size, height=size)
    img.put("{" + "} {".join(" ".join(r) for r in g) + "}")
    return img


# ── Clawd mascot ──────────────────────────────────────────────────────────────
class Mascot(tk.Canvas):
    H = 70
    PX = 4
    SW = 18

    def __init__(self, parent):
        super().__init__(parent, height=self.H, bg=BG, highlightthickness=0,
                         cursor="hand2")
        self.mood = "happy"
        self.x = 50.0
        self.dir = 1
        self.phase = 0.0
        self.love_until = 0.0
        self.hearts: list[list[float]] = []   # [x, y, age]
        self.frames: list[tk.PhotoImage] = []  # custom image (1+ frames for GIF)
        self.frame_i = 0
        self.frame_t = 0
        self.img_path: str | None = None
        self.bind("<Button-1>", self._poke)
        self.bind("<Button-3>", self._menu)   # right-click → swap image
        self.after(FRAME_MS, self._tick)
        path = load_config().get("mascot_image")
        if path and os.path.exists(path):
            self.set_image(path)

    def set_mood(self, mood: str):
        self.mood = mood

    # ── custom image ─────────────────────────────────────────────────────────
    def set_image(self, path: str) -> bool:
        """Load a PNG/GIF as the mascot (all GIF frames if animated).
        Scaled down to fit the strip. Returns True on success."""
        frames: list[tk.PhotoImage] = []
        try:
            i = 0
            while True:
                try:
                    fr = tk.PhotoImage(file=path, format=f"gif -index {i}")
                except tk.TclError:
                    if i == 0:                       # not a (multi-frame) gif
                        fr = tk.PhotoImage(file=path)
                    else:
                        break                        # ran past the last frame
                f = max(1, math.ceil(fr.height() / (self.H - 8)))
                if f > 1:
                    fr = fr.subsample(f, f)
                frames.append(fr)
                i += 1
                if i > 240:                          # safety cap
                    break
        except Exception:
            return False
        if not frames:
            return False
        self.frames, self.frame_i, self.img_path = frames, 0, path
        return True

    def clear_image(self):
        self.frames, self.img_path = [], None

    def _menu(self, e):
        m = tk.Menu(self, tearoff=0, bg=BG, fg=FG,
                    activebackground=CORAL, activeforeground=BG)
        m.add_command(label="Choose image…", command=self._choose)
        if self.frames:
            m.add_command(label="Reset to Clawd", command=self._reset)
        m.tk_popup(e.x_root, e.y_root)

    def _choose(self):
        path = filedialog.askopenfilename(
            title="Pick a mascot image",
            filetypes=[("Images", "*.png *.gif"), ("All files", "*.*")])
        if path and self.set_image(path):
            cfg = load_config(); cfg["mascot_image"] = path; save_config(cfg)

    def _reset(self):
        self.clear_image()
        cfg = load_config(); cfg.pop("mascot_image", None); save_config(cfg)

    def _poke(self, _e=None):
        """Clicked → grin with eyes shut + pop hearts."""
        self.love_until = time.monotonic() + 2.4
        for dx in (-6, 0, 7):
            self.hearts.append([self.x + dx, self.H - 30, 0.0])

    def _speed(self):
        if time.monotonic() < self.love_until:
            return 0.0                       # stand still and beam
        return {"happy": 2.6, "normal": 1.6, "tired": 0.7}[self.mood]

    def _tick(self):
        w = self.winfo_width() or 240
        m = (self.frames[0].width() / 2 if self.frames
             else self.SW * self.PX / 2) + 2
        self.x += self.dir * self._speed()
        if self.x > w - m:
            self.x, self.dir = w - m, -1
        elif self.x < m:
            self.x, self.dir = m, 1
        self.phase += 0.28 if self.mood != "tired" else 0.13
        for hb in self.hearts:               # float hearts up
            hb[1] -= 1.6
            hb[2] += 1
        self.hearts = [h for h in self.hearts if h[2] < 34]
        if len(self.frames) > 1:             # advance animated GIF (~every 3 ticks)
            self.frame_t += 1
            if self.frame_t >= 3:
                self.frame_t = 0
                self.frame_i = (self.frame_i + 1) % len(self.frames)
        self._draw()
        self.after(FRAME_MS, self._tick)

    def _heart(self, hx, hy, c):
        pts = ((1, 0), (3, 0), (0, 1), (1, 1), (2, 1), (3, 1), (4, 1),
               (0, 2), (1, 2), (2, 2), (3, 2), (4, 2), (1, 3), (2, 3), (3, 3), (2, 4))
        s = 2
        for px, py in pts:
            self.create_rectangle(hx + px * s, hy + py * s,
                                  hx + (px + 1) * s, hy + (py + 1) * s,
                                  fill=c, outline="")

    def _draw(self):
        self.delete("all")
        PX = self.PX
        love = time.monotonic() < self.love_until
        happy = self.mood == "happy" or love
        tired = self.mood == "tired" and not love
        bob = math.sin(self.phase) * (3 if happy else 1.6 if not tired else 0.8)

        if self.frames:                       # custom image replaces Clawd
            fr = self.frames[self.frame_i]
            self.create_image(self.x, self.H - fr.height() / 2 - 2 + bob,
                              image=fr, anchor="center")
            for hx, hy, age in self.hearts:   # clicks still pop hearts
                self._heart(hx, hy, HEART if int(age) % 6 < 3 else CORAL_HI)
            return

        ox = self.x - self.SW * PX / 2
        oy = (self.H - 13 * PX) + bob

        def R(gx, gy, gw, gh, c):
            self.create_rectangle(ox + gx * PX, oy + gy * PX,
                                  ox + (gx + gw) * PX, oy + (gy + gh) * PX,
                                  fill=c, outline="")

        # legs (scuttle) — under the body
        for i, lx in enumerate((5, 7, 10, 12)):
            lift = 1 if math.sin(self.phase * 2 + i * 1.7) > 0 else 0
            R(lx, 10 + lift, 1, 2, DARK)

        # claws — raised when happy/love, drooped when tired
        ch = 0 if happy else 2 if not tired else 4
        R(2, ch + 3, 2, 3, CORAL)                          # left arm
        R(0, ch, 3, 3, CORAL); R(2, ch + 1, 1, 1, BG)      # left claw + pincer
        R(14, ch + 3, 2, 3, CORAL)                         # right arm
        R(15, ch, 3, 3, CORAL); R(15, ch + 1, 1, 1, BG)    # right claw + pincer

        # body shell
        R(4, 4, 10, 6, CORAL)
        R(5, 3, 8, 1, CORAL)
        R(5, 9, 8, 1, DARK)
        for cx, cy in ((4, 4), (13, 4), (4, 9), (13, 9)):
            R(cx, cy, 1, 1, BG)               # round corners

        # eyes
        if love:                              # ^ ^ squeezed-happy
            for ex in (6, 10):
                R(ex, 6, 1, 1, EYE); R(ex + 1, 5, 1, 1, EYE); R(ex + 2, 6, 1, 1, EYE)
        elif tired:                           # half-closed + sweat
            R(6, 6, 2, 1, EYE); R(10, 6, 2, 1, EYE)
            R(14, 4, 1, 1, GOLD)              # (kept subtle)
            R(3, 5, 1, 1, "#7dd3fc")          # sweat drop
        else:
            R(6, 5, 2, 2, WHITE); R(10, 5, 2, 2, WHITE)
            R(7, 5, 1, 1, EYE); R(11, 5, 1, 1, EYE)
            if happy:
                R(6, 5, 1, 1, GOLD); R(10, 5, 1, 1, GOLD)   # glint

        # mouth
        if love:
            for mx, my in ((6, 8), (7, 9), (8, 9), (9, 9), (10, 9), (11, 8)):
                R(mx, my, 1, 1, EYE)          # big grin
        elif happy:
            for mx, my in ((7, 8), (8, 9), (9, 9), (10, 8)):
                R(mx, my, 1, 1, EYE)
        elif tired:
            R(8, 8, 2, 2, EYE)                # open pant
        else:
            R(8, 8, 2, 1, EYE)

        # sparkle when happy/love
        if happy:
            sy = 1 + math.sin(self.phase * 1.6)
            R(16, sy, 1, 1, GOLD); R(15, sy + 1, 3, 1, GOLD); R(16, sy + 2, 1, 1, GOLD)

        # floating hearts (from a click)
        for hx, hy, age in self.hearts:
            self._heart(hx, hy, HEART if int(age) % 6 < 3 else CORAL_HI)


# ── bars ────────────────────────────────────────────────────────────────────
class Bar(tk.Frame):
    def __init__(self, parent, label):
        super().__init__(parent, bg=BG)
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text=label, bg=BG, fg=FG,
                 font=(UI_FONT, 9, "bold"), anchor="w").pack(side="left")
        self.pct = tk.Label(top, text="–", bg=BG, fg=FG,
                            font=(UI_FONT, 9, "bold"), anchor="e")
        self.pct.pack(side="right")
        self.canvas = tk.Canvas(self, height=6, bg=TRACK, highlightthickness=0)
        self.canvas.pack(fill="x", pady=(2, 0))
        self.reset = tk.Label(self, text="", bg=BG, fg=DIM,
                             font=(UI_FONT, 7), anchor="w")
        self.reset.pack(fill="x")
        self.canvas.bind("<Configure>", lambda e: self._redraw())
        self._pct = 0.0

    def set(self, pct, reset_text):
        self._pct = 0.0 if pct is None else float(pct)
        self.pct.config(text="–" if pct is None else f"{self._pct:.0f}%",
                        fg=DIM if pct is None else color_for(self._pct))
        self.reset.config(text=reset_text)
        self._redraw()

    def _redraw(self):
        self.canvas.delete("fill")
        w = self.canvas.winfo_width()
        fill = max(0, min(1, self._pct / 100)) * w
        if fill > 0:
            self.canvas.create_rectangle(0, 0, fill, 6, width=0,
                                         fill=color_for(self._pct), tags="fill")


# ── app ─────────────────────────────────────────────────────────────────────
class App(tk.Tk):
    def __init__(self):
        super().__init__()
        global UI_FONT
        fams = set(tkfont.families())
        if "Inter" in fams:
            UI_FONT = "Inter"

        self.title("Claude Usage")
        self.configure(bg=BG)
        self.attributes("-topmost", True)
        self.geometry("260x290")
        self.resizable(False, False)
        self._icon = make_clawd_icon(32)
        self.iconphoto(True, self._icon)
        self.after(60, self._style_titlebar)

        head = tk.Frame(self, bg=BG)
        head.pack(fill="x", padx=12, pady=(9, 2))
        tk.Label(head, text="Claude", bg=BG, fg=FG,
                 font=(SERIF, 13, "italic")).pack(side="left")       # serif wordmark
        self.plan = tk.Label(head, text="", bg=BG, fg=CORAL,
                            font=(UI_FONT, 8, "bold"))
        self.plan.pack(side="left", padx=(6, 0), pady=(5, 0))
        close = tk.Label(head, text="✕", bg=BG, fg=DIM,
                        font=(UI_FONT, 10, "bold"), cursor="hand2")
        close.pack(side="right")
        close.bind("<Button-1>", lambda e: self.destroy())

        self.mascot = Mascot(self)
        self.mascot.pack(fill="x", padx=6)

        body = tk.Frame(self, bg=BG)
        body.pack(fill="both", expand=True, padx=12)
        self.five = Bar(body, "5-hour");  self.five.pack(fill="x", pady=3)
        self.week = Bar(body, "Week");    self.week.pack(fill="x", pady=3)
        self.opus = Bar(body, "Week · Opus")
        self.sonnet = Bar(body, "Week · Sonnet")

        self.status = tk.Label(self, text="loading…", bg=BG, fg=DIM,
                              font=(UI_FONT, 7), anchor="w", cursor="hand2")
        self.status.pack(fill="x", padx=12, pady=(2, 7))
        self.status.bind("<Button-1>", lambda e: self.refresh())

        for w in (head, self.plan):
            w.bind("<Button-1>", self._press)
            w.bind("<B1-Motion>", self._drag)

        self.refresh()

    def _press(self, e):
        self._dx, self._dy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()

    def _drag(self, e):
        self.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _style_titlebar(self):
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            for attr, val in ((20, 1), (35, 0x000A0B0D), (36, 0x00E1E7EC)):
                ctypes.windll.dwmapi.DwmSetWindowAttribute(
                    hwnd, attr, ctypes.byref(ctypes.c_int(val)), 4)
        except Exception:
            pass

    def refresh(self):
        self.status.config(text="refreshing…")
        threading.Thread(target=self._work, daemon=True).start()

    def _work(self):
        data, err = fetch_usage()
        self.after(0, lambda: self._apply(data, err))

    def _apply(self, data, err):
        if err:
            self.status.config(text=err, fg=RED if "expired" in err else DIM)
        elif data:
            self.plan.config(text="MAX")
            fh = data.get("five_hour") or {}
            wk = data.get("seven_day") or {}
            self.five.set(fh.get("utilization"), fmt_reset(fh.get("resets_at")))
            self.week.set(wk.get("utilization"), fmt_reset(wk.get("resets_at")))
            self._opt(self.opus, data.get("seven_day_opus"))
            self._opt(self.sonnet, data.get("seven_day_sonnet"))
            worst = max(fh.get("utilization") or 0, wk.get("utilization") or 0)
            self.mascot.set_mood(mood_for(worst))
            now = datetime.now().strftime("%H:%M:%S")
            self.status.config(text=f"updated {now} · click to refresh", fg=DIM)
        self.after(REFRESH_MS, self.refresh)

    def _opt(self, bar, val):
        if val and val.get("utilization") is not None:
            bar.set(val.get("utilization"), fmt_reset(val.get("resets_at")))
            if not bar.winfo_ismapped():
                bar.pack(fill="x", pady=3)
                self.geometry("260x%d" % (290 + 34 * self._extra()))
        elif bar.winfo_ismapped():
            bar.pack_forget()

    def _extra(self):
        return sum(1 for b in (self.opus, self.sonnet) if b.winfo_ismapped())


if __name__ == "__main__":
    App().mainloop()
