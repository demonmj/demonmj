#!/usr/bin/env python3
"""Generate the terminal-style profile SVGs for the GitHub profile README.

Outputs (in assets/):
  contributions.svg  ->  `$ ./contributions.sh`  contribution heatmap
  whoami.svg         ->  `$ whoami`              ASCII portrait + streak stats + monthly bars
  links.svg          ->  `$ ./links.sh`          tagline + about lines

Data comes from the GitHub GraphQL API (needs GITHUB_TOKEN; the Actions token is enough).
Run with --demo to render with sample data (no network needed).
Settings live in terminal-profile.json at the repo root.
"""
from __future__ import annotations

import datetime as dt
import html
import io
import json
import os
import random
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"
CONFIG = json.loads((ROOT / "terminal-profile.json").read_text(encoding="utf-8"))

# ---------- theme (GitHub dark) ----------
BG = "#0d1117"
PANEL = "#0d1117"
BORDER = "#30363d"
TEXT = "#e6edf3"
MUTED = "#7d8590"
GREEN = "#3fb950"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MONO = "ui-monospace,SFMono-Regular,'SF Mono',Menlo,Consolas,'Liberation Mono','DejaVu Sans Mono',monospace"
W = 840  # README column width


def esc(s: str) -> str:
    return html.escape(str(s), quote=True)


# ---------- data ----------
QUERY = """
query($login: String!) {
  user(login: $login) {
    name login avatarUrl(size: 400)
    contributionsCollection {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount weekday } }
      }
    }
  }
}"""


def fetch(login: str) -> dict:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is not set (use --demo for sample data)")
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": login}}).encode(),
        headers={"Authorization": f"bearer {token}", "Content-Type": "application/json",
                 "User-Agent": "terminal-profile"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if payload.get("errors"):
        sys.exit(f"GraphQL error: {payload['errors']}")
    u = payload["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    weeks = [[(d["date"], d["contributionCount"], d["weekday"]) for d in w["contributionDays"]]
             for w in cal["weeks"]]
    return {"login": u["login"], "name": u["name"] or u["login"], "avatar": u["avatarUrl"],
            "total": cal["totalContributions"], "weeks": weeks}


def demo(login: str) -> dict:
    rnd = random.Random(7)
    today = dt.date.today()
    start = today - dt.timedelta(days=364)
    start -= dt.timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    weeks, week, d = [], [], start
    while d <= today:
        busy = 0.55 + 0.35 * abs(((d - start).days % 120) - 60) / 60
        c = 0 if rnd.random() > busy else int(rnd.expovariate(1 / 5)) + 1
        week.append((d.isoformat(), c, (d.weekday() + 1) % 7))
        if len(week) == 7:
            weeks.append(week); week = []
        d += dt.timedelta(days=1)
    if week:
        weeks.append(week)
    total = sum(c for w in weeks for _, c, _ in w)
    return {"login": login, "name": login, "avatar": None, "total": total, "weeks": weeks}


def stats(data: dict) -> dict:
    days = [(dt.date.fromisoformat(d), c) for w in data["weeks"] for d, c, _ in w]
    days.sort()
    today = days[-1][0]
    # current streak (today may still be empty)
    cur, i = 0, len(days) - 1
    if days[i][1] == 0:
        i -= 1
    cur_end = days[i][0] if i >= 0 else today
    while i >= 0 and days[i][1] > 0:
        cur += 1; i -= 1
    cur_start = cur_end - dt.timedelta(days=cur - 1) if cur else None
    # longest streak
    best, best_rng, run, run_start = 0, None, 0, None
    for d, c in days:
        if c > 0:
            if run == 0:
                run_start = d
            run += 1
            if run > best:
                best, best_rng = run, (run_start, d)
        else:
            run = 0
    active = sum(1 for _, c in days if c > 0)
    best_day = max(days, key=lambda x: x[1])
    # last 12 calendar months
    months = []
    y, m = today.year, today.month
    for _ in range(12):
        months.append((y, m)); m -= 1
        if m == 0:
            y, m = y - 1, 12
    months.reverse()
    per = {k: 0 for k in months}
    for d, c in days:
        if (d.year, d.month) in per:
            per[(d.year, d.month)] += c
    return {
        "total": data["total"], "cur": cur, "cur_rng": (cur_start, cur_end) if cur else None,
        "best": best, "best_rng": best_rng, "active": active, "span": len(days),
        "best_day": best_day, "avg": data["total"] / max(len(days), 1),
        "months": [(dt.date(y, m, 1).strftime("%b"), per[(y, m)]) for y, m in months],
    }


def fmt_rng(r) -> str:
    if not r:
        return "—"
    a, b = r
    return f"{a.strftime('%b %-d')} – {b.strftime('%b %-d')}" if os.name != "nt" else \
        f"{a.strftime('%b')} {a.day} – {b.strftime('%b')} {b.day}"


# ---------- svg helpers ----------
def svg_open(h: int, extra_css: str = "") -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" '
            f'role="img" font-family="{MONO}">\n<style>\n'
            ".fade{opacity:0;animation:fade .5s ease-out forwards}"
            "@keyframes fade{to{opacity:1}}"
            ".cur{animation:blink 1.1s steps(1) infinite}@keyframes blink{50%{opacity:0}}"
            f"{extra_css}"
            "@media (prefers-reduced-motion:reduce){.fade,.grow{animation:none;opacity:1;transform:none}.cur{animation:none}}"
            "\n</style>\n")


def prompt(y: int, cmd: str, user: str, host: str) -> str:
    """Centered bold prompt line with a blinking block cursor."""
    full = f"{user}@{host} ~ $ {cmd}"
    cw = 8.4  # ~char width at 14px for centering the cursor
    x_end = W / 2 + len(full) * cw / 2
    return (f'<text x="{W/2}" y="{y}" text-anchor="middle" font-size="14" font-weight="700" fill="{TEXT}">'
            f'<tspan fill="{GREEN}">{esc(user)}@{esc(host)}</tspan><tspan fill="{MUTED}"> ~ $ </tspan>{esc(cmd)}</text>'
            f'<rect class="cur" x="{x_end + 4:.1f}" y="{y-12}" width="8" height="15" fill="{TEXT}"/>\n')


def window(x, y, w, h, title) -> str:
    dots = "".join(f'<circle cx="{x+16+i*13}" cy="{y+14}" r="4" fill="{c}"/>'
                   for i, c in enumerate(["#ff5f57", "#febc2e", "#28c840"]))
    return (f'<rect x="{x+.5}" y="{y+.5}" width="{w-1}" height="{h-1}" rx="8" fill="{PANEL}" stroke="{BORDER}"/>'
            f'<line x1="{x}" y1="{y+28}" x2="{x+w}" y2="{y+28}" stroke="{BORDER}"/>{dots}'
            f'<text x="{x+w/2}" y="{y+18}" text-anchor="middle" font-size="10.5" fill="{MUTED}">{esc(title)}</text>\n')


# ---------- 1. contributions ----------
def contributions_svg(data, user, host) -> str:
    weeks = data["weeks"][-53:]
    cell, gap = 11, 3
    step = cell + gap
    gx = (W - len(weeks) * step + gap) / 2 + 6
    gy = 68
    h = gy + 7 * step + 46
    mx = max((c for w in weeks for _, c, _ in w), default=0) or 1
    q = sorted(c for w in weeks for _, c, _ in w if c > 0)
    cuts = [q[int(len(q) * f)] for f in (0.25, 0.5, 0.75)] if q else [1, 2, 3]

    def level(c):
        if c == 0:
            return 0
        return 1 + sum(c > t for t in cuts)

    out = [svg_open(h), f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>\n',
           prompt(30, "./contributions.sh", user, host)]
    # month labels
    last = None
    for wi, w in enumerate(weeks):
        m = dt.date.fromisoformat(w[0][0]).strftime("%b")
        if m != last and wi < len(weeks) - 2:
            out.append(f'<text x="{gx + wi*step}" y="{gy-8}" font-size="10" fill="{MUTED}">{m}</text>')
            last = m
    for lbl, row in (("Mon", 1), ("Wed", 3), ("Fri", 5)):
        out.append(f'<text x="{gx-8}" y="{gy + row*step + 9}" text-anchor="end" font-size="10" fill="{MUTED}">{lbl}</text>')
    out.append("\n")
    for wi, w in enumerate(weeks):
        delay = wi * 0.025
        cells = []
        for d, c, wd in w:
            cells.append(f'<rect x="{gx + wi*step}" y="{gy + wd*step}" width="{cell}" height="{cell}" rx="2" '
                         f'fill="{LEVELS[level(c)]}"><title>{c} on {d}</title></rect>')
        out.append(f'<g class="fade" style="animation-delay:{delay:.3f}s">{"".join(cells)}</g>\n')
    out.append(f'<text x="{gx}" y="{gy + 7*step + 18}" font-size="11.5" font-weight="700" fill="{TEXT}">'
               f'{data["total"]:,} contributions in the last year</text>')
    # legend
    lx = gx + len(weeks) * step - gap - 5 * step - 70
    out.append(f'<text x="{lx}" y="{gy + 7*step + 18}" font-size="10" fill="{MUTED}">Less</text>')
    for i, c in enumerate(LEVELS):
        out.append(f'<rect x="{lx + 30 + i*step}" y="{gy + 7*step + 9}" width="{cell}" height="{cell}" rx="2" fill="{c}"/>')
    out.append(f'<text x="{lx + 30 + 5*step + 4}" y="{gy + 7*step + 18}" font-size="10" fill="{MUTED}">More</text>')
    out.append("\n</svg>\n")
    return "".join(out)


# ---------- 2. whoami ----------
RAMP = " .:-=+*#%@"


def portrait_image(data):
    from PIL import Image
    for cand in [os.environ.get("PORTRAIT_PATH", "")] + [str(ASSETS / f"portrait.{e}") for e in ("png", "jpg", "jpeg")]:
        if cand and Path(cand).is_file():
            return Image.open(cand)
    if data.get("avatar"):
        with urllib.request.urlopen(urllib.request.Request(data["avatar"], headers={"User-Agent": "terminal-profile"}), timeout=30) as r:
            return Image.open(io.BytesIO(r.read()))
    return None


def ascii_rows(img, cols, rows):
    """Subject-aware ASCII: brightness x distance from the background colour (median of the border)."""
    import statistics
    from PIL import Image, ImageFilter, ImageOps
    im = img.convert("RGB").resize((160, 160))
    w, h = im.size
    px = im.load()
    border = [px[x, y] for x in range(w) for y in (0, 1, h - 2, h - 1)] + \
             [px[x, y] for y in range(h) for x in (0, 1, w - 2, w - 1)]
    bg = tuple(statistics.median(c[i] for c in border) for i in range(3))
    mask = Image.new("L", (w, h))
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            dist = ((r - bg[0]) ** 2 + (g - bg[1]) ** 2 + (b - bg[2]) ** 2) ** 0.5
            lum = (r * 299 + g * 587 + b * 114) / 1000
            mp[x, y] = int(min(255, dist) * (0.45 + 0.55 * lum / 255))
    mask = ImageOps.autocontrast(mask, cutoff=1).filter(ImageFilter.UnsharpMask(radius=2, percent=150, threshold=2))
    p = mask.resize((cols, rows)).tobytes()
    n = len(RAMP)
    return ["".join(RAMP[min(n - 1, p[r * cols + c] * n // 256)] for c in range(cols)) for r in range(rows)]


def whoami_svg(data, st, user, host) -> str:
    pw, gap = 404, 32
    h = 480
    lx, rx, top = 0, pw + gap, 52
    ph = h - top - 4
    css = (".grow{transform-box:fill-box;transform-origin:50% 100%;transform:scaleY(0);"
           "animation:grow .7s cubic-bezier(.2,.8,.2,1) forwards}@keyframes grow{to{transform:scaleY(1)}}")
    out = [svg_open(h, css), f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>\n',
           prompt(30, "whoami", user, host)]

    # left: ascii portrait
    out.append(window(lx, top, pw, ph, "~/portrait.ascii"))
    img = portrait_image(data)
    cols, rows = 64, 34
    area_w, lh = pw - 28, 10.4
    if img is not None:
        lines = ascii_rows(img, cols, rows)
        out.append(f'<g font-size="{lh*0.98:.2f}" fill="#c9d1d9">')
        for i, line in enumerate(lines):
            out.append(f'<text class="fade" style="animation-delay:{i*0.03:.2f}s" x="{lx+14}" y="{top+40+(i+1)*lh:.2f}" '
                       f'textLength="{area_w}" lengthAdjust="spacingAndGlyphs" xml:space="preserve">{esc(line)}</text>')
        out.append("</g>\n")
    out.append(f'<text x="{lx+14}" y="{top+ph-10}" font-size="10" fill="{MUTED}">{esc(data["name"])} · @{esc(data["login"])}</text>\n')

    # right: stats
    sw = W - rx
    out.append(window(rx, top, sw, ph, "~/stats.json"))
    cards = [
        ("current streak", f'{st["cur"]}', "days", fmt_rng(st["cur_rng"]), GREEN),
        ("longest streak", f'{st["best"]}', "days", fmt_rng(st["best_rng"]), TEXT),
        ("contributions", f'{st["total"]:,}', "", "last 365 days", TEXT),
        ("active days", f'{st["active"]}', f'/ {st["span"]}', f'{st["active"]/max(st["span"],1):.0%} of days', TEXT),
        ("best day", f'{st["best_day"][1]}', "", st["best_day"][0].strftime("%b %d, %Y"), TEXT),
        ("avg / day", f'{st["avg"]:.1f}', "", "contributions", TEXT),
    ]
    cw = (sw - 36) / 2
    for i, (label, big, unit, sub, color) in enumerate(cards):
        cx = rx + 18 + (i % 2) * cw
        cy = top + 50 + (i // 2) * 62
        out.append(f'<g class="fade" style="animation-delay:{0.15 + i*0.12:.2f}s">'
                   f'<text x="{cx}" y="{cy}" font-size="10.5" fill="{MUTED}">$ {esc(label)}</text>'
                   f'<text x="{cx}" y="{cy+24}" font-size="22" font-weight="700" fill="{color}">{esc(big)}'
                   f'<tspan font-size="11" font-weight="400" fill="{MUTED}"> {esc(unit)}</tspan></text>'
                   f'<text x="{cx}" y="{cy+39}" font-size="10" fill="{MUTED}">{esc(sub)}</text></g>')
    out.append("\n")
    # monthly bars
    by = top + 50 + 3 * 62 + 6
    out.append(f'<text x="{rx+18}" y="{by}" font-size="10.5" fill="{MUTED}">$ contributions / month</text>')
    months = st["months"]
    mmax = max((c for _, c in months), default=0) or 1
    peak = max(range(len(months)), key=lambda i: months[i][1])
    chart_top, chart_h = by + 14, ph - (by - top) - 58
    bw_total = sw - 36
    bstep = bw_total / len(months)
    bw = bstep * 0.62
    for i, (mname, c) in enumerate(months):
        bh = max(2, c / mmax * chart_h)
        x = rx + 18 + i * bstep + (bstep - bw) / 2
        y = chart_top + chart_h - bh
        fill = "#56d364" if i == peak else "#238636"
        out.append(f'<rect class="grow" style="animation-delay:{0.5 + i*0.06:.2f}s" x="{x:.1f}" y="{y:.1f}" '
                   f'width="{bw:.1f}" height="{bh:.1f}" rx="2" fill="{fill}"><title>{mname}: {c}</title></rect>')
        out.append(f'<text x="{x + bw/2:.1f}" y="{chart_top + chart_h + 14}" text-anchor="middle" font-size="9" fill="{MUTED}">{mname[0]}</text>')
    pk = months[peak]
    out.append(f'<text x="{rx+sw-18}" y="{by}" text-anchor="end" font-size="10" fill="{MUTED}">peak: {pk[0]} · {pk[1]:,}</text>')
    out.append("\n</svg>\n")
    return "".join(out)


# ---------- 3. links ----------
def links_svg(user, host) -> str:
    lines = CONFIG.get("lines", [])
    h = 92 + 22 * len(lines)
    out = [svg_open(h), f'<rect width="{W}" height="{h}" rx="10" fill="{BG}"/>\n',
           prompt(30, "./links.sh", user, host),
           f'<text class="fade" x="{W/2}" y="60" text-anchor="middle" font-size="13" font-weight="700" fill="{TEXT}">'
           f'{esc(CONFIG.get("tagline", ""))}</text>\n']
    for i, (k, v) in enumerate(lines):
        out.append(f'<text class="fade" style="animation-delay:{0.2 + i*0.15:.2f}s" x="{W/2}" y="{88 + i*22}" '
                   f'text-anchor="middle" font-size="12" fill="{MUTED}"><tspan fill="{GREEN}">{esc(k)}</tspan>'
                   f' → <tspan fill="#c9d1d9">{esc(v)}</tspan></text>\n')
    out.append("</svg>\n")
    return "".join(out)


def main():
    login = os.environ.get("USERNAME_OVERRIDE") or CONFIG["username"]
    host = CONFIG.get("host", "github")
    user = CONFIG.get("prompt_user", login)
    data = demo(login) if "--demo" in sys.argv else fetch(login)
    st = stats(data)
    ASSETS.mkdir(exist_ok=True)
    (ASSETS / "contributions.svg").write_text(contributions_svg(data, user, host), encoding="utf-8")
    (ASSETS / "whoami.svg").write_text(whoami_svg(data, st, user, host), encoding="utf-8")
    (ASSETS / "links.svg").write_text(links_svg(user, host), encoding="utf-8")
    print(f"ok: {data['total']} contributions, streak {st['cur']}d, longest {st['best']}d")


if __name__ == "__main__":
    main()
