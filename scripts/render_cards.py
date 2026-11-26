#!/usr/bin/env python3
"""
Render the GitHub profile README as a stack of animated SVG cards.

    python scripts/render_cards.py              # animated cards -> cards/
    python scripts/render_cards.py --fetch      # refresh data/contributions.json first
    python scripts/render_cards.py --fetch-only # refresh the JSON and stop (CI step 1)
    STATIC=1 python scripts/render_cards.py    # final-frame only (screenshot before push)
    CARDS_OUT=preview/cards STATIC=1 python scripts/render_cards.py

Because GitHub shows these through <img> tags, everything must be self-contained:
no scripts, no external fonts/images. Fonts are subset with pyftsubset and embedded
as base64 WOFF data URIs. Motion comes from an inline <style> block (CSS keyframes)
and SMIL <animate>/<animateTransform> elements. Every card carries a hidden
"final frame" layer that is swapped in under prefers-reduced-motion, so reduced
motion (and STATIC=1) shows a complete, unmoving card.

Design tokens were read from the live site (hammad-developer.vercel.app) and the
current README: #050508 background, #8b5cf6 violet, #4dd2ff cyan, #f5f5f7 white,
Space Grotesk (display) + Inter (body).
"""

from __future__ import annotations

import base64
import calendar
import html
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_FILE = ROOT / "data" / "contributions.json"
FONT_DIR = ROOT / "fonts"
PORTRAIT = ROOT / "assets" / "portrait.jpg"
OUT = Path(os.environ.get("CARDS_OUT", "cards"))
if not OUT.is_absolute():
    OUT = ROOT / OUT

STATIC = os.environ.get("STATIC", "") == "1"
USERNAME = "hammadjawaiddev"

# --------------------------------------------------------------------------
# Brand tokens (from the live site's style.css / tailwind.config.ts)
# --------------------------------------------------------------------------
C = {
    "bg": "#050508",
    "white": "#f5f5f7",
    "text": "#f2f2f5",
    "muted": "#b9b9c6",
    "dim": "#6e6e7a",
    "violet": "#8b5cf6",
    "cyan": "#4dd2ff",
    "border": "rgba(255,255,255,0.09)",
    "cell0": "#191921",
    "levels": ["#191921", "#2c2059", "#49309c", "#6b45dc", "#8b5cf6", "#4dd2ff"],
}

PROFILE = {
    "name": "HAMMAD JAWAID",
    "eyebrow": "// INSIDE THE MIND OF  ·  2026",
    "line1": "Full-stack developer. Modern interfaces, powerful backends",
    "line2": "and databases, end to end.",
    "location": "KARACHI, PAKISTAN",
    "status": "AVAILABLE FOR WORK",
}

TILES = [
    {"slug": "portfolio", "index": "01", "kicker": "EXPLORE", "title": "PORTFOLIO",
     "sub": "Step inside the work", "href": "https://hammad-developer.vercel.app/",
     "accent": C["violet"]},
    {"slug": "hire", "index": "02", "kicker": "COLLABORATE", "title": "HIRE ME",
     "sub": "Open to projects", "href": "https://hammad-developer.vercel.app/hire.html",
     "accent": C["cyan"]},
    {"slug": "email", "index": "03", "kicker": "CONNECT", "title": "SAY HELLO",
     "sub": "Inbox is always open", "href": "mailto:droidhammad2006@gmail.com",
     "accent": C["violet"]},
]

FEATURED = [
    {"slug": "physiosync", "name": "PhysioSync",
     "desc": "Physiotherapy clinic — calm, conversion-first, fast on any device.",
     "tags": ["CLINIC", "3D ANATOMY", "EN / URDU"],
     "href": "https://physiosync-pk.vercel.app/"},
    {"slug": "ctrlzone", "name": "CTRL ZONE",
     "desc": "Gaming-peripherals store — cart, checkout, orders and a full admin panel.",
     "tags": ["PHP", "MYSQL", "PHPMailer"],
     "href": "http://ctrlzone.infinityfreeapp.com/"},
    {"slug": "pathseeker", "name": "PathSeeker",
     "desc": "Career discovery that turns one broad question into a tailored path.",
     "tags": ["CAREER", "DISCOVERY"],
     "href": "https://careerpassporttw.vercel.app/"},
    {"slug": "furshield", "name": "FurShield",
     "desc": "Pet care for owners, vets and shelters — health timelines, documents, adoption.",
     "tags": ["PET CARE", "RECORDS"],
     "href": "https://furshiel.vercel.app/"},
    {"slug": "campuscoin", "name": "Campus Coin",
     "desc": "Student budget tracker — log a spend or import a CSV, then chart and warn.",
     "tags": ["REACT", "EXPRESS", "MONGODB"],
     "href": "https://campuscoin-sable.vercel.app/"},
]

# Stagger: hero first, then the tile row, chart, repo cards, then the graph.
DELAY = {
    "hero": 0.00,
    "tiles": (0.45, 0.58, 0.71),
    "chart": 0.95,
    "repos": 1.25,
    "graph": 2.15,
}

# --------------------------------------------------------------------------
# Contribution data
# --------------------------------------------------------------------------
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
    days = [{"date": d["date"], "count": int(d["contributionCount"])}
            for w in cal["weeks"] for d in w["contributionDays"]]
    days.sort(key=lambda d: d["date"])

    end = date.fromisoformat(days[-1]["date"])
    y, m = end.year, end.month
    keys = []
    for _ in range(12):
        keys.append(f"{y:04d}-{m:02d}")
        m -= 1
        if m == 0:
            m, y = 12, y - 1
    keys.reverse()
    months = [{"key": k, "label": calendar.month_abbr[int(k[5:7])].upper(),
               "count": sum(d["count"] for d in days if d["date"].startswith(k))}
              for k in keys]

    longest = run = 0
    for d in days:
        run = run + 1 if d["count"] > 0 else 0
        longest = max(longest, run)
    current = 0
    for d in reversed(days):
        if d["count"] > 0:
            current += 1
        elif d is days[-1]:      # today may still be empty, don't break a streak for it
            continue
        else:
            break

    active = sum(1 for d in days if d["count"] > 0)
    busiest = max(days, key=lambda d: (d["count"], d["date"]))
    return {
        "username": USERNAME,
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "from": days[0]["date"], "to": days[-1]["date"],
        "totalContributions": int(cal["totalContributions"]),
        "streak": {"current": current, "longest": longest},
        "activeDays": active,
        "busiestDay": {"date": busiest["date"], "count": busiest["count"]},
        "months": months,
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
    else:  # fall back to the gh CLI (already authenticated on many machines / runners)
        q = GRAPHQL.replace("$login:String!", "").replace("$login", f'"{USERNAME}"')
        raw = json.loads(subprocess.check_output(
            ["gh", "api", "graphql", "-f", f"query={q}"], text=True))
    if "errors" in raw:
        raise RuntimeError(f"GraphQL error: {raw['errors']}")
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(normalize(raw), indent=2) + "\n", encoding="utf-8")
    print(f"refreshed {DATA_FILE.relative_to(ROOT)}")


def load_data() -> dict:
    if not DATA_FILE.exists():
        raise SystemExit(f"Missing {DATA_FILE}. Run with --fetch once, or add it.")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# Fonts: instantiate a static weight, subset with pyftsubset, embed base64 WOFF
# --------------------------------------------------------------------------
UNICODES = ("U+0020-007E,U+00B7,U+00D7,U+2013,U+2014,U+2019,U+2022,"
            "U+2026,U+2192,U+2197,U+25B8")


def subset_font(src: Path, weight: int, family: str, tmp: Path) -> str:
    from fontTools.ttLib import TTFont
    from fontTools.varLib.instancer import instantiateVariableFont

    instanced = tmp / f"{src.stem}-{weight}.ttf"
    font = TTFont(src)
    if "fvar" in font:
        limits = {"wght": weight}
        for axis in font["fvar"].axes:
            if axis.axisTag != "wght":
                limits[axis.axisTag] = axis.defaultValue
        font = instantiateVariableFont(font, limits, inplace=True)
    font.save(instanced)

    woff = tmp / f"{src.stem}-{weight}.woff"
    exe = shutil.which("pyftsubset")
    if not exe:
        candidate = Path(sys.executable).parent / "pyftsubset"
        exe = str(candidate) if candidate.exists() else None
    cmd = [exe] if exe else [sys.executable, "-m", "fontTools.subset"]
    cmd += [str(instanced), f"--unicodes={UNICODES}", "--flavor=woff",
            "--layout-features=*", "--no-hinting", f"--output-file={woff}"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

    b64 = base64.b64encode(woff.read_bytes()).decode("ascii")
    print(f"  subset {family}: {woff.stat().st_size:,} bytes -> {len(b64):,} b64 chars")
    return (f"@font-face{{font-family:'{family}';"
            f"src:url(data:font/woff;base64,{b64}) format('woff');"
            f"font-weight:{weight};font-style:normal;font-display:block}}")


def build_font_css() -> str:
    with tempfile.TemporaryDirectory() as td:
        tmp = Path(td)
        return "".join([
            subset_font(FONT_DIR / "SpaceGrotesk-Variable.ttf", 700, "SG", tmp),
            subset_font(FONT_DIR / "Inter-Variable.ttf", 400, "IN", tmp),
        ])


# --------------------------------------------------------------------------
# Motion CSS. Reduced motion swaps the whole animated layer for the final frame.
# --------------------------------------------------------------------------
MOTION_CSS = """
@keyframes rise{from{opacity:0;transform:translateY(16px)}to{opacity:1;transform:translateY(0)}}
@keyframes fade{from{opacity:0}to{opacity:1}}
@keyframes pop{from{opacity:0;transform:scale(.9)}to{opacity:1;transform:scale(1)}}
@keyframes sweep{0%{transform:translateX(-320px)}100%{transform:translateX(1320px)}}
@keyframes breathe{0%,100%{opacity:.4}50%{opacity:1}}
@keyframes blink{0%,49%{opacity:1}50%,100%{opacity:0}}
.a{transform-box:fill-box;transform-origin:center}
.static-layer{display:none}
@media (prefers-reduced-motion:reduce){
  .a{animation:none!important;opacity:1!important;transform:none!important}
  .anim-layer{display:none}
  .static-layer{display:inline}
  animate,animateTransform,set{display:none}
}
"""


def esc(s) -> str:
    return html.escape(str(s), quote=False)


class R:
    """Per-card renderer: hands out staggered delays and suppresses motion in static mode."""

    def __init__(self, base: float, static: bool):
        self.base, self.static, self.n = base, static, 0

    def _delay(self, delay=None) -> float:
        if delay is not None:
            return delay
        d = self.base + self.n * 0.055
        self.n += 1
        return d

    def a(self, kind="rise", dur=0.62, delay=None) -> str:
        if self.static:
            return ""
        return (' class="a" style="animation:%s %ss cubic-bezier(.2,.8,.2,1) both;'
                'animation-delay:%.2fs"' % (kind, dur, self._delay(delay)))

    def pulse(self, delay: float, dur=2.8, lo="0.35", hi="1") -> str:
        if self.static:
            return ""
        return (f'<animate attributeName="opacity" values="{lo};{hi};{lo}" '
                f'dur="{dur}s" begin="{delay:.2f}s" repeatCount="indefinite"/>')

    def rotate(self, cx, cy, delay: float, dur=22) -> str:
        if self.static:
            return ""
        return (f'<animateTransform attributeName="transform" type="rotate" '
                f'from="0 {cx} {cy}" to="360 {cx} {cy}" dur="{dur}s" '
                f'begin="{delay:.2f}s" repeatCount="indefinite"/>')

    def grow(self, final_y: float, final_h: float, baseline: float, delay: float,
             dur=0.85) -> str:
        """One-shot SMIL that grows a bar from the baseline and freezes on the final frame."""
        if self.static:
            return ""
        return (f'<animate attributeName="height" from="0" to="{final_h:.1f}" '
                f'dur="{dur}s" begin="{delay:.2f}s" fill="freeze"/>'
                f'<animate attributeName="y" from="{baseline}" to="{final_y:.1f}" '
                f'dur="{dur}s" begin="{delay:.2f}s" fill="freeze"/>')


# --------------------------------------------------------------------------
# Small SVG element helpers
# --------------------------------------------------------------------------
def text(x, y, s, *, size=16, family="IN", weight=400, fill=None, ls=0,
         anchor=None, opacity=None, a="") -> str:
    attrs = [f'x="{x}"', f'y="{y}"', f'font-family="{family}"', f'font-size="{size}"',
             f'font-weight="{weight}"', f'fill="{fill or C["text"]}"']
    if ls:
        attrs.append(f'letter-spacing="{ls}"')
    if anchor:
        attrs.append(f'text-anchor="{anchor}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    return f'<text {" ".join(attrs)}{a}>{esc(s)}</text>'


def rect(x, y, w, h, *, rx=0, fill="none", stroke=None, sw=1, opacity=None,
         a="", extra="") -> str:
    attrs = [f'x="{x}"', f'y="{y}"', f'width="{w}"', f'height="{h}"']
    if rx:
        attrs.append(f'rx="{rx}"')
    attrs.append(f'fill="{fill}"')
    if stroke:
        attrs.append(f'stroke="{stroke}"')
        attrs.append(f'stroke-width="{sw}"')
    if opacity is not None:
        attrs.append(f'opacity="{opacity}"')
    return f'<rect {" ".join(attrs)}{a}{extra}/>'


def pill(x, y, label, color, a="") -> str:
    w = int(len(label) * 7.2 + 26)
    return (f'<g{a}>'
            + rect(x, y, w, 26, rx=13, fill=color, opacity=.14)
            + rect(x, y, w, 26, rx=13, fill="none", stroke=color, opacity=.5)
            + text(x + 13, y + 17, label, size=11, fill=color, ls=1)
            + "</g>")


def base_defs(w, h) -> str:
    return f'''
<linearGradient id="panel" x1="0" x2="1" y1="0" y2="1">
  <stop offset="0" stop-color="#121219"/><stop offset=".52" stop-color="#09090e"/>
  <stop offset="1" stop-color="#07070b"/></linearGradient>
<linearGradient id="brand" x1="0" x2="1"><stop offset="0" stop-color="{C['violet']}"/>
  <stop offset="1" stop-color="{C['cyan']}"/></linearGradient>
<linearGradient id="brandv" x1="0" x2="0" y1="0" y2="1">
  <stop offset="0" stop-color="{C['cyan']}"/><stop offset="1" stop-color="{C['violet']}"/></linearGradient>
<linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="#ffffff" stop-opacity="0"/>
  <stop offset=".5" stop-color="#ffffff" stop-opacity=".55"/>
  <stop offset="1" stop-color="#ffffff" stop-opacity="0"/></linearGradient>
<radialGradient id="glowv"><stop offset="0" stop-color="{C['violet']}" stop-opacity=".30"/>
  <stop offset="1" stop-color="{C['violet']}" stop-opacity="0"/></radialGradient>
<radialGradient id="glowc"><stop offset="0" stop-color="{C['cyan']}" stop-opacity=".20"/>
  <stop offset="1" stop-color="{C['cyan']}" stop-opacity="0"/></radialGradient>
<pattern id="grid" width="32" height="32" patternUnits="userSpaceOnUse">
  <path d="M32 0H0V32" fill="none" stroke="#ffffff" stroke-opacity=".035" stroke-width="1"/></pattern>
<clipPath id="clip"><rect x="0" y="0" width="{w}" height="{h}" rx="20"/></clipPath>'''


def frame(w, h, r: R, accent=None) -> str:
    accent = accent or C["violet"]
    sweep = "" if r.static else (
        f'<rect x="0" y="0" width="260" height="{h}" fill="url(#fade)" opacity=".13" '
        f'style="animation:sweep 7s linear infinite"/>')
    return (f'<g clip-path="url(#clip)">'
            + rect(0, 0, w, h, fill="url(#panel)")
            + rect(0, 0, w, h, fill="url(#grid)")
            + f'<ellipse cx="{w*.12:.0f}" cy="0" rx="{w*.42:.0f}" ry="{h*.95:.0f}" fill="url(#glowv)"/>'
            + f'<ellipse cx="{w*.93:.0f}" cy="{h}" rx="{w*.36:.0f}" ry="{h*.85:.0f}" fill="url(#glowc)"/>'
            + sweep
            + rect(1, 1, w - 2, h - 2, rx=19, fill="none", stroke="#ffffff", opacity=.09)
            + f'<path d="M24 1 H{w-24}" stroke="url(#brand)" stroke-width="2" opacity=".85"/>'
            + "</g>")


# --------------------------------------------------------------------------
# Cards
# --------------------------------------------------------------------------
PORTRAIT_URI = ""
if PORTRAIT.exists():
    mime = "image/png" if PORTRAIT.suffix == ".png" else "image/jpeg"
    PORTRAIT_URI = (f"data:{mime};base64,"
                    + base64.b64encode(PORTRAIT.read_bytes()).decode("ascii"))


def hero(static: bool):
    w, h = 1200, 340
    r = R(DELAY["hero"], static)
    cx, cy, rad = 1010, 180, 100
    defs = base_defs(w, h) + (
        f'<clipPath id="portrait"><circle cx="{cx}" cy="{cy}" r="{rad-6}"/></clipPath>')
    b = [frame(w, h, r)]

    b.append(text(56, 58, PROFILE["eyebrow"], size=13, family="IN", weight=400,
                  fill=C["cyan"], ls=3, a=r.a("fade")))
    b.append(text(56, 158, "HAMMAD", size=86, family="SG", weight=700,
                  fill=C["white"], ls=2, a=r.a("rise")))
    b.append(text(56, 246, "JAWAID", size=86, family="SG", weight=700,
                  fill="url(#brand)", ls=2, a=r.a("rise")))
    b.append(text(57, 288, PROFILE["line1"], size=17, family="IN", weight=400,
                  fill=C["muted"], a=r.a("rise")))
    b.append(text(57, 312, PROFILE["line2"], size=17, family="IN", weight=400,
                  fill=C["muted"], a=r.a("rise")))

    # status pill
    b.append(rect(842, 24, 300, 38, rx=19, fill="#161622", stroke=C["violet"],
                  opacity=.65, a=r.a("pop")))
    b.append(f'<circle cx="866" cy="43" r="5" fill="{C["cyan"]}"'
             + (f'>{r.pulse(0.35)}</circle>' if not static else '/>'))
    b.append(text(882, 48, PROFILE["status"], size=12, family="IN", weight=400,
                  fill=C["white"], ls=2, a=r.a("fade")))
    b.append(text(1142, 320, PROFILE["location"], size=11, family="IN", weight=400,
                  fill=C["dim"], ls=2, anchor="end", a=r.a("fade")))

    # portrait (optional) with a slowly rotating dashed brand ring
    ring = (f'<g>{"" if static else r.rotate(cx, cy, 0.20)}'
            f'<circle cx="{cx}" cy="{cy}" r="{rad+8}" fill="none" '
            f'stroke="url(#brand)" stroke-width="2" stroke-dasharray="5 12" opacity=".65"/>'
            f'</g>')
    b.append(ring)
    b.append(f'<circle cx="{cx}" cy="{cy}" r="{rad}" fill="#14141f" '
             f'stroke="#ffffff" stroke-opacity=".12"/>')
    if PORTRAIT_URI:
        b.append(f'<image href="{PORTRAIT_URI}" xlink:href="{PORTRAIT_URI}" '
                 f'x="{cx-rad+6}" y="{cy-rad+6}" width="{2*(rad-6)}" height="{2*(rad-6)}" '
                 f'preserveAspectRatio="xMidYMid slice" clip-path="url(#portrait)"'
                 + r.a("pop") + '/>')
    else:
        b.append(text(cx, cy + 20, "HJ", size=64, family="SG", weight=700,
                      fill="url(#brand)", anchor="middle", a=r.a("pop")))
    b.append(text(56, 330, "BUILD  /  SHIP  /  REPEAT", size=10, family="IN",
                  fill=C["dim"], ls=3, a=r.a("fade")))
    return w, h, defs, "".join(b), "HAMMAD JAWAID — full-stack developer, available for work, Karachi"


def tile(cfg, static: bool, base: float):
    w, h = 380, 190
    r = R(base, static)
    accent = cfg["accent"]
    defs = base_defs(w, h)
    b = [frame(w, h, r, accent)]
    b.append(text(28, 42, f'{cfg["index"]} / {cfg["kicker"]}', size=10, family="IN",
                  fill=C["dim"], ls=2, a=r.a("fade")))
    b.append(text(28, 108, cfg["title"], size=30, family="SG", weight=700,
                  fill=C["white"], ls=1, a=r.a("rise")))
    b.append(text(28, 140, cfg["sub"], size=13, family="IN", fill=C["muted"],
                  a=r.a("rise")))
    b.append(f'<circle cx="336" cy="46" r="7" fill="{accent}"'
             + (f'>{r.pulse(base + 0.4)}</circle>' if not static else '/>'))
    b.append(text(350, 162, "↗", size=22, family="SG", weight=700, fill=accent,
                  anchor="end", a=r.a("pop")))
    b.append(f'<path d="M28 164 H352" stroke="#ffffff" stroke-opacity=".08"/>')
    return (w, h, defs, "".join(b),
            f'{cfg["title"]} — {cfg["sub"]}')


def chart(static: bool, data: dict):
    w, h = 1200, 430
    r = R(DELAY["chart"], static)
    defs = base_defs(w, h)
    b = [frame(w, h, r)]
    b.append(text(56, 56, "CONTRIBUTIONS", size=27, family="SG", weight=700,
                  fill=C["white"], ls=1, a=r.a("rise")))
    b.append(text(56, 80, "COMMITS, PULL REQUESTS, ISSUES AND REVIEWS — LAST 12 MONTHS",
                  size=11, family="IN", fill=C["dim"], ls=2, a=r.a("fade")))
    b.append(text(1144, 58, f'{data["totalContributions"]:,} TOTAL',
                  size=13, family="IN", fill=C["cyan"], ls=2, anchor="end",
                  a=r.a("fade")))

    stats = [
        ("STREAK", f'{data["streak"]["current"]} days',
         f'best {data["streak"]["longest"]} days', C["violet"]),
        ("ACTIVE DAYS", f'{data["activeDays"]}',
         f'of {len(data["days"])} days', C["cyan"]),
        ("BUSIEST DAY", f'{data["busiestDay"]["count"]}',
         data["busiestDay"]["date"], C["violet"]),
    ]
    for i, (label, value, note, accent) in enumerate(stats):
        x = 56 + i * 366
        b.append(f'<g{r.a("rise")}>'
                 + rect(x, 100, 342, 84, rx=14, fill="#ffffff", opacity=.035)
                 + rect(x, 100, 342, 84, rx=14, fill="none", stroke="#ffffff", opacity=.08)
                 + rect(x, 100, 3, 84, rx=2, fill=accent)
                 + text(x + 20, 126, label, size=11, family="IN", fill=C["dim"], ls=2)
                 + text(x + 20, 160, value, size=26, family="SG", weight=700, fill=C["white"])
                 + text(x + 322, 160, note, size=11, family="IN", fill=C["muted"],
                        anchor="end")
                 + "</g>")

    baseline, max_h, x0, x1 = 392, 140, 56, 1144
    for f in (0.25, 0.5, 0.75, 1.0):
        yy = baseline - max_h * f
        b.append(f'<path d="M{x0} {yy:.0f} H{x1}" stroke="#ffffff" stroke-opacity=".055"/>')
    b.append(f'<path d="M{x0} {baseline} H{x1}" stroke="#ffffff" stroke-opacity=".16"/>')

    months = data["months"]
    peak = max(m["count"] for m in months) or 1
    bar_w = 66
    gap = (x1 - x0 - bar_w * len(months)) / (len(months) - 1)
    for i, m in enumerate(months):
        bh = max(3.0, (m["count"] / peak) * max_h)
        bx = x0 + i * (bar_w + gap)
        by = baseline - bh
        delay = DELAY["chart"] + 0.30 + i * 0.045
        b.append('<rect ' + " ".join([
            f'x="{bx:.1f}"', f'y="{by:.1f}"', f'width="{bar_w}"', f'height="{bh:.1f}"',
            'rx="6"', 'fill="url(#brandv)"', 'opacity=".95"',
        ]) + f'>{r.grow(by, bh, baseline, delay)}</rect>')
        b.append(text(bx + bar_w / 2, by - 9, str(m["count"]), size=11, family="IN",
                      fill=C["muted"], anchor="middle", a=r.a("fade", delay=delay + 0.25)))
        b.append(text(bx + bar_w / 2, baseline + 22, m["label"], size=11, family="IN",
                      fill=C["dim"], ls=1, anchor="middle",
                      a=r.a("fade", delay=delay + 0.20)))
    b.append(text(1144, 80, f'{data["from"]}  →  {data["to"]}', size=10, family="IN",
                  fill=C["dim"], ls=1, anchor="end", a=r.a("fade")))
    return w, h, defs, "".join(b), (
        f'Contributions per month: {data["totalContributions"]} total, '
        f'{data["streak"]["current"]} day streak, {data["activeDays"]} active days, '
        f'busiest {data["busiestDay"]["date"]}')


def repo(cfg, i: int, static: bool):
    w, h = 1200, 200
    base = DELAY["repos"] + i * 0.15
    r = R(base, static)
    defs = base_defs(w, h)
    b = [frame(w, h, r)]
    accent = C["violet"] if i % 2 == 0 else C["cyan"]
    b.append(text(56, 126, f"{i+1:02d}", size=54, family="SG", weight=700,
                  fill="url(#brand)", a=r.a("pop")))
    b.append(f'<path d="M148 40 V160" stroke="#ffffff" stroke-opacity=".10"/>')
    b.append(text(178, 84, cfg["name"], size=36, family="SG", weight=700,
                  fill=C["white"], a=r.a("rise")))
    b.append(text(179, 116, cfg["desc"], size=16, family="IN", fill=C["muted"],
                  a=r.a("rise")))
    x = 178
    for tag in cfg["tags"]:
        b.append(pill(x, 142, tag, accent, a=r.a("pop")))
        x += int(len(tag) * 7.2 + 26) + 8
    b.append(f'<circle cx="1040" cy="61" r="4" fill="{accent}"'
             + (f'>{r.pulse(base + 0.35)}</circle>' if not static else '/>'))
    b.append(rect(1018, 42, 126, 38, rx=19, fill="#ffffff", opacity=.045,
                  a=r.a("pop")))
    b.append(text(1096, 66, "LIVE  ↗", size=12, family="IN", fill=C["white"], ls=1,
                  anchor="middle", a=r.a("fade")))
    b.append(text(1144, 172, f'{i+1:02d} / {len(FEATURED):02d}', size=11, family="IN",
                  fill=C["dim"], ls=2, anchor="end", a=r.a("fade")))
    return w, h, defs, "".join(b), (
        f'{cfg["name"]} — {cfg["desc"]} Tags: {", ".join(cfg["tags"])}')


def graph(static: bool, data: dict):
    w, h = 1200, 300
    r = R(DELAY["graph"], static)
    defs = base_defs(w, h)
    b = [frame(w, h, r)]
    b.append(text(56, 56, "CONTRIBUTION GRAPH", size=27, family="SG", weight=700,
                  fill=C["white"], ls=1, a=r.a("rise")))
    b.append(text(1144, 56, f'{data["totalContributions"]:,} CONTRIBUTIONS',
                  size=12, family="IN", fill=C["cyan"], ls=2, anchor="end",
                  a=r.a("fade")))

    days = data["days"]
    first = date.fromisoformat(days[0]["date"])
    offset = (first.weekday() + 1) % 7          # Sunday-first columns, like GitHub
    cell, step, x0, y0 = 16, 20, 56, 100
    cols = min(53, math.ceil((offset + len(days)) / 7))
    counts = [d["count"] for d in days if d["count"] > 0]
    q = max(counts) if counts else 1

    by_col: dict[int, list[str]] = {}
    month_marks: dict[int, str] = {}
    prev_month = None
    for j, d in enumerate(days):
        col = (offset + j) // 7
        row = (offset + j) % 7
        if col >= cols:
            continue
        lvl = 0 if d["count"] == 0 else min(5, 1 + math.ceil(4 * d["count"] / q))
        x, y = x0 + col * step, y0 + row * step
        by_col.setdefault(col, []).append(
            rect(x, y, cell, cell, rx=3, fill=C["levels"][lvl]))
        mk = d["date"][:7]
        if mk != prev_month:
            month_marks[col] = calendar.month_abbr[int(mk[5:7])].upper()
            prev_month = mk

    for col in range(cols):
        delay = DELAY["graph"] + col * 0.012
        group_a = "" if static else (
            ' class="a" style="animation:fade .4s ease-out both;'
            f'animation-delay:{delay:.2f}s"')
        b.append(f'<g{group_a}>' + "".join(by_col.get(col, [])) + "</g>")
    last_label_col = -10
    for col, label in month_marks.items():
        if col < 2 or col - last_label_col < 4:   # skip the partial first month / collisions
            continue
        last_label_col = col
        b.append(text(x0 + col * step, y0 - 10, label, size=9, family="IN",
                      fill=C["dim"], ls=1, a=r.a("fade", delay=DELAY["graph"] + col * 0.012)))

    lx = x0 + cols * step - 5 * 20
    b.append(text(lx - 14, 270, "LESS", size=10, family="IN", fill=C["dim"], ls=1,
                  anchor="end", a=r.a("fade")))
    for k in range(5):
        b.append(rect(lx + k * 20, 256, 14, 14, rx=3, fill=C["levels"][k + 1],
                      a=r.a("fade", delay=DELAY["graph"] + 0.5 + k * 0.05)))
    b.append(text(lx + 108, 270, "MORE", size=10, family="IN", fill=C["dim"], ls=1,
                  a=r.a("fade")))
    b.append(text(56, 288, "ONE SQUARE = ONE DAY  ·  UPDATED DAILY BY GITHUB ACTIONS",
                  size=10, family="IN", fill=C["dim"], ls=2, a=r.a("fade")))
    return w, h, defs, "".join(b), (
        "Contribution graph in violet and cyan — one square per day over the last year")


# --------------------------------------------------------------------------
# Assembly
# --------------------------------------------------------------------------
def shell(w, h, defs, css, body, title) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" '
            f'xmlns:xlink="http://www.w3.org/1999/xlink" '
            f'viewBox="0 0 {w} {h}" width="{w}" height="{h}">'
            f'<title>{esc(title)}</title><defs>{defs}</defs>'
            f'<style>{css}</style>{body}</svg>')


def write_card(name, fn, css, manifest) -> None:
    if STATIC:
        w, h, defs, body, alt = fn(True)
        svg = shell(w, h, defs, css, body, alt)
    else:
        w, h, defs, animated, alt = fn(False)
        _, _, _, final, _ = fn(True)
        svg = shell(w, h, defs, css,
                    f'<g class="anim-layer">{animated}</g>'
                    f'<g class="static-layer">{final}</g>', alt)
    (OUT / name).write_text(svg, encoding="utf-8")
    manifest.append((name, alt, w))
    print(f"  {name:<28} {len(svg):>8,} bytes")


def write_preview(manifest, css_rel) -> None:
    tile_imgs = "".join(
        f'<a href="{esc(t["href"])}"><img src="{css_rel}/tile-{t["slug"]}.svg" '
        f'alt="{esc(t["title"])}" width="32.5%"></a>' for t in TILES)
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Profile cards — {"STATIC final frame" if STATIC else "animated"}</title>
<style>
:root{{color-scheme:dark}}
body{{margin:0;background:#050508;color:#f2f2f5;font:14px Inter,Arial,sans-serif}}
.bar{{padding:16px 24px;color:#b9b9c6;background:#0d0d13;border-bottom:1px solid rgba(255,255,255,.09);
font:12px ui-monospace,monospace;letter-spacing:2px;position:sticky;top:0;z-index:2}}
.wrap{{max-width:1200px;margin:0 auto;padding:28px 20px 90px}}
img{{display:block;width:100%;height:auto;margin:0 0 20px;border-radius:20px}}
.row{{display:flex;gap:1.25%;margin:0 0 20px}}
.row a{{display:block;width:32.5%}} .row img{{width:100%;margin:0}}
.note{{color:#6e6e7a;text-align:center;margin-top:30px;font-size:12px;letter-spacing:1px}}
</style></head><body>
<div class="bar">PROFILE CARDS &nbsp;·&nbsp; {"STATIC=1 — FINAL FRAME" if STATIC else "ANIMATED"}</div>
<div class="wrap">
<img src="{css_rel}/hero.svg" alt="{esc(manifest[0][1])}">
<div class="row">{tile_imgs}</div>
{''.join(f'<img src="{css_rel}/{name}" alt="{esc(alt)}">' for name, alt, _ in manifest[1:] if not name.startswith("tile-"))}
<div class="note">{"Screenshot this page, then re-run without STATIC=1 before pushing." if STATIC else "Cards animate top to bottom. Reduced-motion users see the final frame."}</div>
</div></body></html>'''
    (ROOT / "preview.html").write_text(page, encoding="utf-8")


def main() -> None:
    args = sys.argv[1:]
    if "--fetch-only" in args:
        fetch_contributions()
        return
    if "--fetch" in args:
        fetch_contributions()
    data = load_data()

    OUT.mkdir(parents=True, exist_ok=True)
    print(f"Rendering {'STATIC final-frame' if STATIC else 'animated'} cards -> {OUT.relative_to(ROOT)}/")
    font_css = build_font_css()
    css = font_css if STATIC else font_css + MOTION_CSS

    manifest: list[tuple[str, str, int]] = []
    write_card("hero.svg", hero, css, manifest)
    for i, t in enumerate(TILES):
        write_card(f'tile-{t["slug"]}.svg',
                   lambda static, t=t, i=i: tile(t, static, DELAY["tiles"][i]),
                   css, manifest)
    write_card("contributions.svg", lambda static: chart(static, data), css, manifest)
    for i, cfg in enumerate(FEATURED):
        write_card(f'repo-{cfg["slug"]}.svg',
                   lambda static, cfg=cfg, i=i: repo(cfg, i, static), css, manifest)
    write_card("graph.svg", lambda static: graph(static, data), css, manifest)

    rel = os.path.relpath(OUT, ROOT).replace(os.sep, "/")
    write_preview(manifest, rel)
    print(f"\nWrote {len(manifest)} cards + preview.html")
    if STATIC:
        print("STATIC=1: these are final-frame SVGs. Run without STATIC=1 before committing.")


if __name__ == "__main__":
    main()
