# Claude Usage Widget

Tiny always-on-top window showing your Claude plan limits — the same numbers as Claude Code's `/usage`.

![rows: 5-hour · Week · (Week·Opus / Week·Sonnet when active)]

## What it shows
- A **Claude-coral mascot** that paces back and forth and changes mood with the
  worst of your 5-hour / weekly utilisation:
  - **< 50%** happy (brisk pacing + sparkle)
  - **50–79%** normal (steady amble)
  - **≥ 80%** tired (slow shuffle, droopy eyes, sweat drop)
- **5-hour** — % of the rolling 5-hour limit used + when it resets
- **Week** — % of the 7-day limit used + when it resets
- **Week · Opus / Week · Sonnet** — per-model weekly bars (shown only when the API reports them)

Bar colour: green < 70% · amber 70–89% · red ≥ 90%. Mascot + window icon are
drawn in code (Tkinter vectors) — no image files, still stdlib-only.

## Use your own mascot
**Right-click the mascot** → **Choose image…** to swap Clawd for your own
picture. PNG and GIF work (animated GIFs play); your image paces and bobs with
the same mood-driven rhythm. The choice is remembered in `~/.claude-usage.json`.
Right-click → **Reset to Clawd** brings the crab back. Still stdlib-only — Tk
loads PNG/GIF natively, no `pip install`.

## Run
```
Double-click  start.vbs        (silent, no console)
```
or from a terminal:
```
pythonw claude_usage.py        # no console
python  claude_usage.py        # with console (for debugging)
```

- Click the status line to refresh now (auto-refreshes every 60s).
- Drag the header to move it. Click ✕ to close.

## Auto-start at login (optional)
Press `Win+R` → `shell:startup` → drop a shortcut to `start.vbs` there.

## How it works
- Reads the live usage from `GET https://api.anthropic.com/api/oauth/usage`
  (the endpoint Claude Code's `/usage` uses) with the OAuth access token from
  `~/.claude/.credentials.json`.
- The token is owned + refreshed by Claude Code. This widget only **reads** it
  fresh on each poll — it never stores, logs, or sends it anywhere else.
- Stdlib only (tkinter + urllib). No `pip install` needed.

## Notes / limits
- If you see **"session expired — open Claude Code"**, the token lapsed — open
  Claude Code once to refresh it (the widget can't re-auth on its own).
- "offline — retrying" just means a failed poll; it retries on the next tick.
- Undocumented endpoint: if Anthropic changes it, the widget may need a tweak.
