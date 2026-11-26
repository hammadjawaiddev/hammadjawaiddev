#!/usr/bin/env python3
"""
Render the profile README as a stack of animated SVG cards — "Three Worlds".

Matched to avivashishta.com's design language: paper (#f3f3f1), ink (#111111)
and three colours — BUILD blue (#2f55ff), BRAND red (#ef3b2d), LEARN yellow
(#ffc81a) — with Instrument Serif, Geist and Geist Mono. The hero's ASCII
portrait comes from assets/portrait-prepped.png, a square, ridge-darkened
grayscale made from the photo the user supplied (assets/source-photo.jpg ->
assets/portrait-ink.png -> scripts/prep_portrait.py).

Every card is a standalone SVG shown through <img>, so it can only use what
GitHub allows there: an inline <style> block with CSS keyframes, SMIL
<animate>/<set>/<animateTransform> elements, and fonts subset with pyftsubset
and embedded as base64 WOFF data URIs. No JS, no external requests.

  python scripts/render_cards.py               # animated cards -> cards/
  python scripts/render_cards.py --fetch       # refresh data/contributions.json first
  python scripts/render_cards.py --fetch-only  # refresh the JSON and stop (CI step)
  STATIC=1 python scripts/render_cards.py     # final frame only, for screenshots
  CARDS_OUT=preview/cards STATIC=1 python scripts/render_cards.py

Each animated card ships a second, animation-free "final frame" layer that is
swapped in under prefers-reduced-motion, so CSS *and* SMIL motion both stop.
"""

from __future__ import annotations

import base64
import datetime
import html
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from html import escape
from pathlib import Path

from PIL import Image, ImageEnhance

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "contributions.json"
OUT = Path(os.environ.get("CARDS_OUT", "cards"))
if not OUT.is_absolute():
    OUT = ROOT / OUT
FONTS = ROOT / "fonts"
PREP_SOURCE = ROOT / "assets" / "portrait-prepped.png"
STATIC = os.environ.get("STATIC", "") == "1"
USERNAME = "hammadjawaiddev"

# ---- hand-set numbers (from the README / portfolio, like Avi's stats.json) --
BUILD_PROJECTS = "5"
BRAND_TOOLS = "15"
LEARN_MODE = "1"

# ---- brand tokens -----------------------------------------------------------
PAPER = "#f3f3f1"
PAPER_DEEP = "#e2e2de"
INK = "#111111"
INK_SOFT = "#3a3a3c"
MUTED = "#6e6e73"
RULE = "#dcdcd7"
TECH = "#2f55ff"        # BUILD blue / graph
STUDIO = "#ef3b2d"      # BRAND red
LEARN = "#ffc81a"       # LEARN yellow
W = 880                 # GitHub's README column at 100%

SERIF = "'Instrument Serif', Georgia, serif"
SANS = "Geist, system-ui, -apple-system, sans-serif"
MONO = "'Geist Mono', ui-monospace, SFMono-Regular, Menlo, monospace"

FONT_FILES = {
    "serif": ("Instrument Serif", "normal", 400, "serif-400.woff"),
    "serif-i": ("Instrument Serif", "italic", 400, "serif-italic.woff"),
    "sans": ("Geist", "normal", 400, "geist-400.woff"),
    "sans-b": ("Geist", "normal", 600, "geist-600.woff"),
    "mono": ("Geist Mono", "normal", 400, "geistmono-400.woff"),
}
# printable ASCII plus the arrows / dots actually used in the cards
UNICODES = "U+0020-007E,U+00B7,U+2019,U+2191,U+2192,U+2197"

# ---- Avi's exact keyframe set ----------------------------------------------
BASE_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:none}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes grow{from{transform:scaleY(0)}to{transform:scaleY(1)}}
@keyframes pop{0%{opacity:0;transform:scale(.3)}70%{opacity:1;transform:scale(1.15)}100%{opacity:1;transform:none}}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.25}}
@keyframes nudge{0%,100%{transform:none}50%{transform:translateX(4px)}}
@keyframes nudgeup{0%,100%{transform:none}50%{transform:translate(3px,-3px)}}
.r{opacity:0;animation:rise .8s cubic-bezier(.2,.7,.2,1) both;transform-box:fill-box}
.f{opacity:0;animation:fade .9s ease-out both}
.g{transform-box:fill-box;transform-origin:bottom;transform:scaleY(0);animation:grow .8s cubic-bezier(.2,.7,.2,1) both}
.p{opacity:0;transform-box:fill-box;transform-origin:center;animation:pop .4s ease-out both}
.live{animation:pulse 1.6s ease-in-out infinite}
.n{transform-box:fill-box;animation:nudge 1.8s ease-in-out infinite}
.nu{transform-box:fill-box;animation:nudgeup 1.8s ease-in-out infinite}
@keyframes tilein{0%{opacity:0;transform:translateY(90px) scale(.6) rotate(-9deg)}55%{opacity:1;transform:translateY(-10px) scale(1.05) rotate(2deg)}75%{transform:translateY(3px) scale(.98) rotate(-.8deg)}90%{transform:translateY(-1px) scale(1.01) rotate(.2deg)}100%{opacity:1;transform:none}}
@keyframes slidein{from{opacity:0;transform:translateX(-26px)}to{opacity:1;transform:none}}
@keyframes arrowin{0%{opacity:0;transform:translateX(-30px)}60%{opacity:1;transform:translateX(6px)}100%{opacity:1;transform:none}}
@keyframes roll{from{transform:translateY(60px)}to{transform:none}}
@keyframes sheen{0%{transform:translateX(-260px) skewX(-20deg)}22%,100%{transform:translateX(420px) skewX(-20deg)}}
@keyframes ring{0%{opacity:.7;transform:scale(.2)}100%{opacity:0;transform:scale(2.4)}}
.ti{opacity:0;transform-box:fill-box;transform-origin:50% 60%;animation:tilein 1.1s cubic-bezier(.2,.8,.2,1) both}
.sl{opacity:0;transform-box:fill-box;animation:slidein .6s cubic-bezier(.2,.7,.2,1) both}
.ai{opacity:0;transform-box:fill-box;animation:arrowin .7s cubic-bezier(.2,.7,.2,1) both}
.ro{transform-box:fill-box;animation:roll .8s cubic-bezier(.15,.8,.2,1) both}
.sh{animation:sheen 5s ease-in-out infinite}
.rg{opacity:0;transform-box:fill-box;transform-origin:center;animation:ring 1s ease-out both}
"""

ALL_ANIM = ".r,.f,.g,.p,.live,.n,.nu,.ti,.sl,.ai,.ro,.rg,.sh"
END_CSS = (ALL_ANIM + "{animation:none!important;opacity:1!important;transform:none!important}"
           ".sh,.rg{display:none}")
LAYER_CSS = """
.static-layer{display:none}
.static-layer .r,.static-layer .f,.static-layer .g,.static-layer .p,
.static-layer .live,.static-layer .n,.static-layer .nu,.static-layer .ti,
.static-layer .sl,.static-layer .ai,.static-layer .ro,.static-layer .sh,
.static-layer .rg{animation:none!important;opacity:1!important;transform:none!important}
.static-layer .sh,.static-layer .rg{display:none}
@media (prefers-reduced-motion:reduce){
  """ + ALL_ANIM + """{animation:none!important;opacity:1!important;transform:none!important}
  .sh,.rg{display:none}
  .anim-layer{display:none}
  .static-layer{display:inline}
  animate,animateTransform,set{display:none}
}
"""

# ---- fonts ------------------------------------------------------------------
_SUBSET_CACHE: dict[str, str] = {}


def subset_font(filename: str) -> str:
    """Re-subset a committed WOFF with pyftsubset, return a base64 data URI."""
    if filename in _SUBSET_CACHE:
        return _SUBSET_CACHE[filename]
    src = FONTS / filename
    with tempfile.TemporaryDirectory() as td:
        dst = Path(td) / filename
        exe = shutil.which("pyftsubset")
        if not exe:
            cand = Path(sys.executable).parent / "pyftsubset"
            exe = str(cand) if cand.exists() else None
        cmd = [exe] if exe else [sys.executable, "-m", "fontTools.subset"]
        cmd += [str(src), f"--unicodes={UNICODES}", "--flavor=woff",
                "--layout-features=*", "--no-hinting", f"--output-file={dst}"]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
        b64 = base64.b64encode(dst.read_bytes()).decode("ascii")
    _SUBSET_CACHE[filename] = b64
    return b64


def font_face(keys) -> str:
    out = []
    for k in keys:
        fam, style, weight, fn = FONT_FILES[k]
        out.append(f"@font-face{{font-family:'{fam}';font-style:{style};font-weight:{weight};"
                   f"src:url(data:font/woff;base64,{subset_font(fn)}) format('woff')}}")
    return "".join(out)


GAP = 12
BOTTOM = 12
COL = W / 3


def d(s) -> str:
    return f'style="animation-delay:{s:.2f}s"'


def wrap(text, n):
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > n:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    return lines + [line] if line else lines


def text_lines(x, y, lines, lh, attrs):
    return "".join(f'<text x="{x}" y="{y + i * lh}" {attrs}>{escape(l)}</text>'
                   for i, l in enumerate(lines))


def shell(w, h, css, body, label):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.3f}" height="{h}" '
            f'viewBox="0 0 {w:.3f} {h}" role="img" aria-label="{escape(label)}">'
            f'<title>{escape(label)}</title><style>{css}</style>{body}</svg>')


def build(name, w, h, body_fn, fonts, label, *, left=0, right=0, bottom=BOTTOM):
    """Two layers when animated; a single frozen final frame in STATIC mode."""
    # In STATIC mode even the @keyframes definitions are dropped: the final
    # frame is a plain, screenshot-safe SVG with no animation machinery at all.
    css = font_face(fonts) + (END_CSS if STATIC else BASE_CSS + LAYER_CSS)
    W2, H2 = w + left + right, h + bottom

    def place(body):
        return f'<g transform="translate({left:.3f} 0)">{body}</g>' if left else body

    if STATIC:
        content = shell(W2, H2, css, place(body_fn(True)), label)
    else:
        content = shell(W2, H2, css,
                        f'<g class="anim-layer">{place(body_fn(False))}</g>'
                        f'<g class="static-layer">{place(body_fn(True))}</g>', label)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / name).write_text(content, encoding="utf-8")
    print(f"  {name:<32} {len(content):>8,} bytes")


# ---- contribution data ------------------------------------------------------
GRAPHQL = """query($login:String!){
  user(login:$login){
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}"""


def normalize(raw: dict) -> dict:
    cal = raw["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [{"date": x["date"], "count": int(x["contributionCount"])}
            for w in cal["weeks"] for x in w["contributionDays"]]
    days.sort(key=lambda x: x["date"])
    total = int(cal["totalContributions"])
    active = [x for x in days if x["count"] > 0]

    # streaks
    longest = run = 0
    longest_end = days[0]["date"]
    for x in days:
        run = run + 1 if x["count"] > 0 else 0
        if run > longest:
            longest, longest_end = run, x["date"]
    current = 0
    for x in reversed(days):
        if x["count"] > 0:
            current += 1
        elif x is days[-1]:
            continue
        else:
            break

    # 12 calendar months ending with the last day in the calendar
    end = datetime.date.fromisoformat(days[-1]["date"])
    y, m = end.year, end.month
    keys = []
    for _ in range(12):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()
    monthly = [{"month": k, "total": sum(x["count"] for x in days
                                         if x["date"].startswith(k))} for k in keys]

    best = max(days, key=lambda x: (x["count"], x["date"]))
    q = max((x["count"] for x in active), default=1)
    for x in days:
        x["level"] = 0 if x["count"] == 0 else min(5, 1 + math.ceil(4 * x["count"] / q))
    return {
        "username": USERNAME,
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "range": {"from": days[0]["date"], "to": days[-1]["date"]},
        "total_contributions": total,
        "active_days": len(active),
        "avg_per_active_day": round(total / len(active), 1) if active else 0,
        "current_streak": {"length": current, "start": "", "end": days[-1]["date"]},
        "longest_streak": {"length": longest, "start": "", "end": longest_end},
        "best_day": {"date": best["date"], "count": best["count"]},
        "monthly": monthly,
        "days": days,
    }


def fetch_contributions() -> None:
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        payload = json.dumps({"query": GRAPHQL, "variables": {"login": USERNAME}}).encode()
        req = urllib.request.Request(
            "https://api.github.com/graphql", data=payload,
            headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                     "User-Agent": "profile-card-renderer"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = json.load(resp)
    else:
        q = GRAPHQL.replace("$login:String!", "").replace("$login", f'"{USERNAME}"')
        raw = json.loads(subprocess.check_output(
            ["gh", "api", "graphql", "-f", f"query={q}"], text=True))
    if "errors" in raw:
        raise RuntimeError(f"GraphQL error: {raw['errors']}")
    DATA.parent.mkdir(parents=True, exist_ok=True)
    DATA.write_text(json.dumps(normalize(raw), indent=2) + "\n", encoding="utf-8")
    print(f"refreshed {DATA.relative_to(ROOT)}")


# ---- ASCII portrait from the user's photo -----------------------------------
# Same sampling constants as Avi's scripts/make_ascii_svg.py.
ASCII_COLS, ASCII_ROWS = 180, 96
RAMP = " .`:-=+*cs#%@"      # bright/sparse -> dark/dense
ASCII_GAMMA = 1.18          # >1 brightens mids so the face reads as sparse chars
WHITE_FLOOR = 0.86          # above this luminance the paper is left blank
FADE_FROM = 0.80            # shoulders dissolve into the paper at the bottom


def portrait_rows():
    """Sample the prepared portrait into 96 rows that print in like a terminal.

    Every row MUST stay exactly ASCII_COLS characters wide. The hero uses
    textLength="800" with lengthAdjust="spacing"; trimming trailing spaces makes
    short rows stretch sideways and warps the face.
    """
    im = ImageEnhance.Contrast(
        Image.open(PREP_SOURCE).convert("L")).enhance(1.05)
    small = im.resize((ASCII_COLS, ASCII_ROWS), Image.LANCZOS)
    px = small.load()
    rows = []
    for y in range(ASCII_ROWS):
        fade = min(1.0, max(0.0, (y / ASCII_ROWS - FADE_FROM) / (1 - FADE_FROM)))
        line = []
        for x in range(ASCII_COLS):
            lum = (px[x, y] / 255.0) ** ASCII_GAMMA
            lum = lum + (1 - lum) * fade          # soften the bottom edge
            if lum >= WHITE_FLOOR:
                line.append(" ")
                continue
            idx = int((1 - lum) * (len(RAMP) - 1) + .5)
            line.append(RAMP[max(0, min(len(RAMP) - 1, idx))])
        rows.append("".join(line))                # never rstrip
    return rows


# ---- 1 · hero ----------------------------------------------------------------
def hero_body(static: bool):
    sfx = "S" if static else "A"
    h = 420
    cell_w = 800 / ASCII_COLS
    cell_h = cell_w * 15 / 8
    art_top = 30 + 20 * .35
    portrait = []
    for i, line in enumerate(portrait_rows()):
        y = art_top + i * cell_h + cell_h * .74
        portrait.append(
            f'<text class="f" style="animation-delay:{0.25 + i * 0.018:.3f}s;'
            f'animation-duration:.35s" xml:space="preserve" x="20" y="{y:.2f}" '
            f'fill="{INK}" font-size="7.2" textLength="800" lengthAdjust="spacing">'
            f'{escape(line)}</text>')
    shine_smil = "" if static else (
        '<animateTransform attributeName="gradientTransform" type="translate" '
        'values="-600 0;600 0;600 0" keyTimes="0;.45;1" dur="7s" begin="1.6s" '
        'repeatCount="indefinite"/>')
    return f'''
<defs>
  <linearGradient id="shine{sfx}" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="600" y2="0">
    <stop offset="0" stop-color="{INK}"/><stop offset=".42" stop-color="{INK}"/>
    <stop offset=".5" stop-color="{TECH}"/><stop offset=".58" stop-color="{INK}"/>
    <stop offset="1" stop-color="{INK}"/>{shine_smil}
  </linearGradient>
</defs>
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<g class="f" {d(0)}>
  <rect class="live" x="48" y="49" width="8" height="8" rx="2" fill="{TECH}"/>
  <text x="66" y="57" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">FULLSTACK DEVELOPER  ·  KARACHI, PAKISTAN</text>
</g>
<text class="r" {d(0.15)} x="44" y="190" font-family="{SERIF}" font-size="116" letter-spacing="-2.5" fill="{INK}">Hammad</text>
<text class="r" {d(0.3)} x="44" y="290" font-family="{SERIF}" font-style="italic" font-size="116" letter-spacing="-2.5" fill="url(#shine{sfx})">Jawaid</text>
<g class="r" {d(0.55)}>
  {text_lines(48, 338, ["I build modern interfaces, powerful backends", "and databases, end to end."], 27, f'font-family="{SANS}" font-size="18" fill="{INK_SOFT}"')}
</g>
<g class="f" {d(0.8)}>
  <text x="48" y="396" font-family="{MONO}" font-size="13" fill="{INK}">hammad-developer.vercel.app</text>
  <text class="nu" x="281" y="396" font-family="{MONO}" font-size="13" fill="{TECH}">&#8599;</text>
</g>
<g transform="translate(520 46) scale(0.41) translate(-20 -37)" font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace">
  {''.join(portrait)}
</g>'''


# ---- 2 · blue contribution graph -------------------------------------------
BLUE = [PAPER_DEEP, "#c8d3ff", "#94a8ff", "#6280ff", TECH, "#1a3be0"]


def level_for(c, q):
    return 0 if c == 0 else min(5, 1 + math.ceil(4 * c / q))


def heatmap_body(data, static: bool):
    days = data["days"]
    first = datetime.date.fromisoformat(days[0]["date"])
    lead = (first.weekday() + 1) % 7
    cell, step, gx, gy = 12, 15, 44, 96
    q = max((x["count"] for x in days), default=1)
    cells, months, seen = [], [], set()
    for i, day in enumerate(days):
        k = i + lead
        col, row = divmod(k, 7)
        dt = datetime.date.fromisoformat(day["date"])
        if dt.day <= 7 and (dt.year, dt.month) not in seen and row == 0:
            seen.add((dt.year, dt.month))
            months.append((col, dt.strftime("%b")))
        delay = 1.0 + col * 0.03 + row * 0.02
        cells.append(
            f'<rect class="p" style="animation-delay:{delay:.2f}s" x="{gx + col * step}" '
            f'y="{gy + row * step}" width="{cell}" height="{cell}" rx="3" '
            f'fill="{BLUE[level_for(day["count"], q)]}"><title>{day["date"]}: '
            f'{day["count"]} contribution{"s" if day["count"] != 1 else ""}</title></rect>')
    ncols = (len(days) + lead + 6) // 7
    right = gx + ncols * step - 3
    labels = "".join(
        f'<text x="{gx + col * step}" y="{gy + 7 * step + 16}" font-family="{MONO}" '
        f'font-size="11" fill="{MUTED}">{m}</text>'
        for col, m in months if col < ncols - 12)
    legend_x = right - len(BLUE) * 14
    legend = "".join(
        f'<rect x="{legend_x + i * 14}" y="{gy + 7 * step + 6}" width="11" height="11" '
        f'rx="2.5" fill="{c}"/>' for i, c in enumerate(BLUE))
    h = gy + 7 * step + 44
    return h, f'''
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="r" {d(0.8)} x="42" y="62" font-family="{SERIF}" font-size="34" fill="{INK}">Every day, <tspan font-style="italic" fill="{TECH}">in blue</tspan></text>
<text class="f" {d(0.8)} x="{right}" y="60" text-anchor="end" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">REFRESHED DAILY</text>
{''.join(cells)}
<g class="f" {d(2.4)}>{labels}
<text x="{legend_x - 8}" y="{gy + 7 * step + 16}" text-anchor="end" font-family="{MONO}" font-size="11" fill="{MUTED}">less</text>
{legend}
<text x="{legend_x + len(BLUE) * 14 + 2}" y="{gy + 7 * step + 16}" font-family="{MONO}" font-size="11" fill="{MUTED}">more</text></g>'''


# ---- 3 · monthly bars --------------------------------------------------------
def activity_body(data, static: bool):
    h = 340
    monthly = data["monthly"][-12:]
    best = max(monthly[:-1] or monthly, key=lambda m: m["total"])
    top = best["total"] or 1
    x0, x1, base, maxh, gap = 40, 600, 292, 140, 10
    bw = (x1 - x0 - gap * (len(monthly) - 1)) / len(monthly)
    bars = []
    for i, m in enumerate(monthly):
        partial = i == len(monthly) - 1
        is_best = m is best
        bh = max(4, round(m["total"] / top * maxh))
        x = x0 + i * (bw + gap)
        fill = TECH if is_best else ("#c9c9c4" if partial else INK)
        label = datetime.date.fromisoformat(m["month"] + "-01").strftime("%b")
        bars.append(
            f'<rect class="g" style="animation-delay:{2.2 + i * 0.07:.2f}s" x="{x:.1f}" '
            f'y="{base - bh}" width="{bw:.1f}" height="{bh}" rx="4" fill="{fill}">'
            f'<title>{label}: {m["total"]:,}</title></rect>'
            f'<text class="f" style="animation-delay:{2.2 + i * 0.07:.2f}s" '
            f'x="{x + bw / 2:.1f}" y="{base + 22}" text-anchor="middle" '
            f'font-family="{MONO}" font-size="11" fill="{MUTED}">{label}</text>')
        if is_best:
            bars.append(
                f'<text class="p" style="animation-delay:3.2s" x="{x + bw / 2:.1f}" '
                f'y="{base - bh - 10}" text-anchor="middle" font-family="{MONO}" '
                f'font-size="11" fill="{TECH}">{m["total"]:,}</text>')
    cs = data["current_streak"]["length"]
    ls = data["longest_streak"]["length"]
    streak_note = "current streak, and the longest" if cs >= ls else f"current streak, longest {ls}"
    total_days = len(data["days"])
    stats = [
        (f'{cs} <tspan font-style="italic">days</tspan>', streak_note),
        (f'{data["active_days"]}<tspan fill="#8e8e93"> / {total_days}</tspan>', "days with a commit"),
        (f'{data["best_day"]["count"]}', "on the busiest day"),
    ]
    side = []
    for i, (big, small) in enumerate(stats):
        y = 104 + i * 92
        side.append(f'<g class="r" {d(2.6 + i * 0.15)}>'
                    f'<text x="650" y="{y}" font-family="{SERIF}" font-size="40" fill="{INK}">{big}</text>'
                    f'<text x="650" y="{y + 24}" font-family="{SANS}" font-size="13" fill="{MUTED}">{small}</text></g>')
        if i < 2:
            side.append(f'<rect class="f" {d(2.6)} x="650" y="{y + 44}" width="190" height="1" fill="{RULE}"/>')
    return h, f'''
<rect width="{W}" height="{h}" rx="14" fill="{PAPER}"/>
<text class="f" {d(1.9)} x="40" y="58" font-family="{MONO}" font-size="12" letter-spacing="1" fill="{MUTED}">THE LAST 12 MONTHS ON GITHUB</text>
<text class="r" {d(2.0)} x="38" y="114" font-family="{SERIF}" font-size="52" fill="{INK}">{data["total_contributions"]:,} <tspan font-style="italic">contributions</tspan></text>
{''.join(bars)}
{''.join(side)}'''


# ---- 4 · three world tiles ---------------------------------------------------
TILE_W, TILE_H = 880 / 3 - 8, 210


def count_up(num, word, x, y, attrs, begin, static, dur=1.1, frames=18):
    m = re.match(r"([\d.]+)(.*)", num)
    val, suf = float(m.group(1)), m.group(2)
    dec = len(m.group(1).split(".")[1]) if "." in m.group(1) else 0
    tail = f' <tspan font-style="italic">{escape(word)}</tspan>'
    if static:
        return f'<text x="{x}" y="{y}" {attrs}>{escape(num)}{tail}</text>'
    out = []
    for i in range(frames + 1):
        e = 1 - (1 - i / frames) ** 3
        txt = num if i == frames else f"{val * e:.{dec}f}{suf}"
        on = begin + dur * i / frames
        off = "" if i == frames else (
            f'<set attributeName="opacity" to="0" '
            f'begin="{begin + dur * (i + 1) / frames:.3f}s"/>')
        out.append(f'<text x="{x}" y="{y}" {attrs} opacity="0">{escape(txt)}{tail}'
                   f'<set attributeName="opacity" to="1" begin="{on:.3f}s"/>{off}</text>')
    return "".join(out)


def tile_body(cfg, delay, pos, static: bool):
    sfx = "S" if static else "A"
    name, label, color, on, num, word, blurb = cfg
    lines = wrap(blurb, 34)
    blurb_svg = "".join(
        f'<text class="r" {d(delay + 0.75 + i * 0.1)} x="24" y="{150 + i * 20}" '
        f'font-family="{SANS}" font-size="14" fill="{on}" opacity=".92">{escape(l)}</text>'
        for i, l in enumerate(lines))
    return f'''
<defs>
  <clipPath id="card{sfx}"><rect width="{TILE_W}" height="{TILE_H}" rx="14"/></clipPath>
  <clipPath id="slot{sfx}"><rect x="0" y="62" width="{TILE_W}" height="62"/></clipPath>
  <linearGradient id="gl{sfx}" x1="0" x2="1"><stop offset="0" stop-color="#fff" stop-opacity="0"/>
    <stop offset=".5" stop-color="#fff" stop-opacity=".35"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient>
</defs>
<g class="ti" {d(delay)}>
  <g clip-path="url(#card{sfx})">
    <rect width="{TILE_W}" height="{TILE_H}" fill="{color}"/>
    <circle class="rg" {d(delay + 0.5)} cx="{TILE_W - 40}" cy="{TILE_H - 40}" r="60" fill="none" stroke="{on}" stroke-opacity=".5" stroke-width="2"/>
    <rect class="sh" style="animation-delay:{delay + 1.4:.2f}s" x="0" y="-20" width="90" height="{TILE_H + 40}" fill="url(#gl{sfx})" transform="translate(-260 0)"/>
  </g>
  <text class="sl" {d(delay + 0.35)} x="24" y="38" font-family="{MONO}" font-size="12" letter-spacing="1.2" fill="{on}">{label}</text>
  <g class="ai" {d(delay + 0.5)}><text class="n" style="animation-delay:{delay + 1.3:.2f}s" x="250" y="38" font-family="{MONO}" font-size="14" fill="{on}">&#8594;</text></g>
  <g clip-path="url(#slot{sfx})"><g class="ro" {d(delay + 0.45)}>
    {count_up(num, word, 22, 112, f'font-family="{SERIF}" font-size="44" fill="{on}"', delay + 0.45, static)}
  </g></g>
  {blurb_svg}
</g>'''


# ---- 5 · section title -------------------------------------------------------
def title_body(theme, static: bool):
    fg = "#e6edf3" if theme == "dark" else INK
    return (f'<text class="r" {d(4.4)} x="2" y="46" font-family="{SERIF}" '
            f'font-size="34" fill="{fg}">What I\'m '
            f'<tspan font-style="italic">coding</tspan></text>')


# ---- 6 · featured project cards ---------------------------------------------
REPO_W, REPO_H = 880 / 3 - 8, 176
FEATURED = [
    ("physiosync", "PhysioSync", "Physiotherapy clinic - calm, conversion-first, with 3D anatomy and EN/URDU.", "CLINIC  ·  live", TECH),
    ("ctrlzone", "CTRL ZONE", "Gaming store: browse, cart, checkout, order history and a full admin panel.", "PHP  ·  MySQL  ·  live", STUDIO),
    ("pathseeker", "PathSeeker", "Career discovery that turns one broad question into a tailored path.", "CAREER  ·  live", LEARN),
    ("furshield", "FurShield", "Pet care for owners, vets and shelters: health timelines, documents, adoption.", "PET CARE  ·  live", TECH),
    ("campuscoin", "Campus Coin", "Student budget tracker - log a spend or import a CSV, then chart and warn.", "REACT  ·  EXPRESS  ·  live", STUDIO),
    ("more-work", "More work", "Every experiment, landing page and side quest lives in the portfolio.", "PORTFOLIO  ·  all work", LEARN),
]


def repo_body(i, name, desc, meta, color, static: bool):
    delay = 4.6 + i * 0.12
    return f'''
<rect width="{REPO_W}" height="{REPO_H}" rx="14" fill="{PAPER}"/>
<g class="r" {d(delay)}>
  <rect x="24" y="30" width="8" height="8" rx="2" fill="{color}"/>
  <text x="40" y="39" font-family="{SANS}" font-weight="600" font-size="18" fill="{INK}">{escape(name)}</text>
  {text_lines(24, 72, wrap(desc, 34), 21, f'font-family="{SANS}" font-size="14" fill="{INK_SOFT}"')}
  <text x="24" y="{REPO_H - 24}" font-family="{MONO}" font-size="12" fill="{MUTED}">{escape(meta)}</text>
</g>'''


# ---- preview page ------------------------------------------------------------
def write_preview(card_names, rel):
    """A screenshot-friendly page laid out exactly like the README."""
    def img(n, width="100%"):
        return f'<img src="{rel}/{n}" alt="{escape(n)}" style="width:{width}">'
    row = lambda ns: ('<div class="row">' + "".join(img(n, "33.333%") for n in ns)
                      + "</div>")
    tiles = ["build.svg", "brand.svg", "learn.svg"]
    repos = [n for n in card_names if n.startswith("repo-")]
    blocks = [img("hero.svg"), img("heatmap.svg"), img("activity.svg"),
              row(tiles), img("title-coding-light.svg"),
              row(repos[:3]), row(repos[3:6])]
    label = "STATIC=1 - FINAL FRAME" if STATIC else "ANIMATED"
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Three Worlds - {"STATIC final frame" if STATIC else "animated"}</title>
<style>
body{{margin:0;background:{PAPER};font:12px ui-monospace,monospace;color:{MUTED}}}
.wrap{{max-width:880px;margin:0 auto;padding:24px 0 60px}}
.bar{{padding:8px 2px 18px;letter-spacing:2px}}
img{{display:block;width:100%;height:auto}}
.row{{display:flex}} .row img{{width:33.333%}}
</style></head><body><div class="wrap">
<div class="bar">PROFILE CARDS &nbsp;·&nbsp; {label}</div>
{''.join(blocks)}</div></body></html>'''
    (ROOT / "preview.html").write_text(page, encoding="utf-8")


def main():
    args = sys.argv[1:]
    if "--fetch-only" in args:
        fetch_contributions()
        return
    if "--fetch" in args:
        fetch_contributions()
    if not DATA.exists():
        raise SystemExit(f"Missing {DATA}. Run with --fetch once.")
    data = json.loads(DATA.read_text(encoding="utf-8"))

    print(f"Rendering {'STATIC final-frame' if STATIC else 'animated'} cards -> {OUT.relative_to(ROOT)}/")
    names = []

    def emit(name, w, h, fn, fonts, label, **kw):
        build(name, w, h, fn, fonts, label, **kw)
        names.append(name)

    emit("hero.svg", W, 420, hero_body, ["serif", "serif-i", "sans", "mono"],
         "Hammad Jawaid. Fullstack developer in Karachi. I build modern interfaces, powerful backends and databases, end to end.")

    emit("heatmap.svg", W, heatmap_body(data, False)[0],
         lambda static: heatmap_body(data, static)[1], ["serif", "serif-i", "mono"],
         f'Contribution graph: {data["total_contributions"]:,} contributions in the last year')

    emit("activity.svg", W, activity_body(data, False)[0],
         lambda static: activity_body(data, static)[1],
         ["serif", "serif-i", "sans", "mono"],
         f'{data["total_contributions"]:,} contributions in the last year, '
         f'{data["current_streak"]["length"]}-day streak')

    tiles = [
        ("build", "BUILD", TECH, "#ffffff", BUILD_PROJECTS, "projects",
         "Five live products, from a physiotherapy clinic to a full-stack store.", 3.1, 0),
        ("brand", "BRAND", STUDIO, "#ffffff", BRAND_TOOLS, "tools",
         "HTML to Vercel: the stack I actually ship with, verified in my repos.", 3.35, 1),
        ("learn", "LEARN", LEARN, INK, LEARN_MODE, "at a time",
         "One project at a time: idea, interface, API, database, deploy.", 3.6, 2),
    ]
    for name, label, color, on, num, word, blurb, delay, pos in tiles:
        cfg = (name, label, color, on, num, word, blurb)
        emit(f"{name}.svg", TILE_W, TILE_H,
             lambda static, cfg=cfg, delay=delay, pos=pos: tile_body(cfg, delay, pos, static),
             ["serif", "serif-i", "sans", "mono"],
             f"{label}: {num} {word}. {blurb}",
             left=4 * pos, right=8 - 4 * pos)

    for theme in ("dark", "light"):
        emit(f"title-coding-{theme}.svg", W, 64,
             lambda static, theme=theme: title_body(theme, static),
             ["serif", "serif-i"], "What I'm coding", bottom=0)

    for i, (slug, title, desc, meta, color) in enumerate(FEATURED):
        emit(f"repo-{slug}.svg", REPO_W, REPO_H,
             lambda static, i=i, title=title, desc=desc, meta=meta, color=color:
                 repo_body(i, title, desc, meta, color, static),
             ["sans", "sans-b", "mono"], f"{title}: {desc}",
             left=4 * (i % 3), right=8 - 4 * (i % 3))

    write_preview(names, os.path.relpath(OUT, ROOT).replace(os.sep, "/"))
    print(f"\nWrote {len(names)} cards + preview.html")
    if STATIC:
        print("STATIC=1: final-frame SVGs. Re-run without STATIC=1 before committing.")


if __name__ == "__main__":
    main()
