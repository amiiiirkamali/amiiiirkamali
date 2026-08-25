"""Generate the animated **Pretty GitHub** profile assets.

Six SVG panels are rendered from `config.json` + live GitHub data:

    assets/identity.svg       ASCII portrait, animated wordmark, contact rail
    assets/signal.svg         live stats cards + language stack
    assets/contributions.svg  contribution calendar with orbital scanner
    assets/arsenal.svg        grouped tech stack with proficiency bars
    assets/trajectory.svg     career timeline
    assets/missions.svg       featured project grid

Data sources: GitHub REST (profile/repos), GraphQL (contribution calendar when
GITHUB_TOKEN is present) and a public HTML fallback for token-less runs.

    python scripts/generate.py            # live public data
    python scripts/generate.py --demo     # deterministic offline preview
    python scripts/generate.py --only signal missions
"""

from __future__ import annotations

import argparse
import html
import json
import os
import random
import re
import urllib.error
import urllib.request
from datetime import date, timedelta
from pathlib import Path
from xml.sax.saxutils import escape

try:  # Pillow is only required for the ASCII portrait.
    from PIL import Image, ImageEnhance, ImageOps
except ImportError:  # pragma: no cover - portrait degrades to the sigil panel.
    Image = ImageEnhance = ImageOps = None  # type: ignore[assignment]

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

# ---------------------------------------------------------------------------
# design tokens
# ---------------------------------------------------------------------------
OUTER = "#0b1d20"
BG = "#071416"
PANEL = "#0a2928"
PANEL_2 = "#0b2227"
SUNKEN = "#081d1f"
HAIR = "#168f82"
EDGE = "#1ca596"
EDGE_SOFT = "#176f68"
TRACK = "#203b40"
TEAL = "#43ead3"
MINT = "#83ffe8"
BLUE = "#4387ff"
PURPLE = "#9b6cff"
CYAN = "#32d8ef"
YELLOW = "#f2dc56"
ORANGE = "#ff6b48"
GREEN = "#56f73a"
TEXT = "#dcfff7"
MUTED = "#79aaa4"
PALETTE = [YELLOW, BLUE, PURPLE, GREEN, ORANGE, CYAN, TEAL]

W = 900  # every panel shares one canvas width so the README stacks cleanly

GLYPHS = {
    "A": ["01110", "10001", "10001", "11111", "10001", "10001", "10001"],
    "B": ["11110", "10001", "10001", "11110", "10001", "10001", "11110"],
    "C": ["01111", "10000", "10000", "10000", "10000", "10000", "01111"],
    "D": ["11110", "10001", "10001", "10001", "10001", "10001", "11110"],
    "E": ["11111", "10000", "10000", "11110", "10000", "10000", "11111"],
    "F": ["11111", "10000", "10000", "11110", "10000", "10000", "10000"],
    "G": ["01111", "10000", "10000", "10111", "10001", "10001", "01110"],
    "H": ["10001", "10001", "10001", "11111", "10001", "10001", "10001"],
    "I": ["11111", "00100", "00100", "00100", "00100", "00100", "11111"],
    "J": ["00111", "00010", "00010", "00010", "10010", "10010", "01100"],
    "K": ["10001", "10010", "10100", "11000", "10100", "10010", "10001"],
    "L": ["10000", "10000", "10000", "10000", "10000", "10000", "11111"],
    "M": ["10001", "11011", "10101", "10101", "10001", "10001", "10001"],
    "N": ["10001", "11001", "10101", "10011", "10001", "10001", "10001"],
    "O": ["01110", "10001", "10001", "10001", "10001", "10001", "01110"],
    "P": ["11110", "10001", "10001", "11110", "10000", "10000", "10000"],
    "Q": ["01110", "10001", "10001", "10001", "10101", "10010", "01101"],
    "R": ["11110", "10001", "10001", "11110", "10100", "10010", "10001"],
    "S": ["01111", "10000", "10000", "01110", "00001", "00001", "11110"],
    "T": ["11111", "00100", "00100", "00100", "00100", "00100", "00100"],
    "U": ["10001", "10001", "10001", "10001", "10001", "10001", "01110"],
    "V": ["10001", "10001", "10001", "10001", "10001", "01010", "00100"],
    "W": ["10001", "10001", "10001", "10101", "10101", "11011", "10001"],
    "X": ["10001", "10001", "01010", "00100", "01010", "10001", "10001"],
    "Y": ["10001", "10001", "01010", "00100", "00100", "00100", "00100"],
    "Z": ["11111", "00001", "00010", "00100", "01000", "10000", "11111"],
    "0": ["01110", "10011", "10101", "10101", "11001", "10001", "01110"],
    "1": ["00100", "01100", "00100", "00100", "00100", "00100", "01110"],
    "2": ["01110", "10001", "00001", "00010", "00100", "01000", "11111"],
    "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
    "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
    "5": ["11111", "10000", "10000", "11110", "00001", "00001", "11110"],
    "6": ["01110", "10000", "10000", "11110", "10001", "10001", "01110"],
    "7": ["11111", "00001", "00010", "00100", "01000", "01000", "01000"],
    "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    "9": ["01110", "10001", "10001", "01111", "00001", "00001", "01110"],
    " ": ["000", "000", "000", "000", "000", "000", "000"],
}


# ---------------------------------------------------------------------------
# text helpers
# ---------------------------------------------------------------------------
def load_config() -> dict:
    return json.loads((ROOT / "config.json").read_text(encoding="utf-8"))


def trim(value: object, size: int) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= size else text[: size - 1].rstrip() + "…"


def text_width(text: str, size: float, bold: bool = False) -> float:
    """Cheap metric estimate — good enough to lay out chips and rails."""
    factor = 0.545 if bold else 0.505
    return len(text) * size * factor


def wrap(text: str, size: float, max_width: float, max_lines: int = 3) -> list[str]:
    words = " ".join(str(text or "").split()).split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if text_width(candidate, size) <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
        if len(lines) == max_lines:
            break
    if current and len(lines) < max_lines:
        lines.append(current)
    if len(lines) == max_lines and words:
        joined = " ".join(lines)
        if len(joined) < len(" ".join(words)):
            last = lines[-1]
            while last and text_width(last + "…", size) > max_width:
                last = last[:-1]
            lines[-1] = last.rstrip(" ,.") + "…"
    return lines


def chips(items: list[str], x: float, y: float, size: float = 8.0, accent: str = EDGE_SOFT,
          gap: float = 6.0, max_width: float | None = None) -> str:
    """Render a row of pill tags, dropping any that overflow max_width."""
    out, cursor = [], x
    for item in items:
        label = trim(item, 18)
        width = text_width(label, size, True) + 16
        if max_width is not None and cursor + width > x + max_width:
            break
        out.append(
            f'<g transform="translate({cursor:.1f} {y:.1f})">'
            f'<rect width="{width:.1f}" height="17" rx="8.5" fill="#0d3636" stroke="{accent}" stroke-opacity=".55"/>'
            f'<text x="{width / 2:.1f}" y="12" text-anchor="middle" class="chip">{escape(label)}</text></g>'
        )
        cursor += width + gap
    return "".join(out)


# ---------------------------------------------------------------------------
# GitHub data layer
# ---------------------------------------------------------------------------
def request_json(url: str, *, payload: dict | None = None) -> object:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "pretty-github-profile"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, headers=headers, data=data)
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def profile_data(username: str) -> dict:
    user = request_json(f"https://api.github.com/users/{username}")
    repos = request_json(f"https://api.github.com/users/{username}/repos?per_page=100&sort=updated")
    if not isinstance(user, dict) or not isinstance(repos, list):
        raise RuntimeError("Unexpected response from GitHub REST API")
    original = [repo for repo in repos if not repo.get("fork")]
    languages: dict[str, int] = {}
    for repo in original:
        language = repo.get("language")
        if language:
            languages[language] = languages.get(language, 0) + 1
    return {
        "public_repos": int(user.get("public_repos", len(repos))),
        "followers": int(user.get("followers", 0)),
        "following": int(user.get("following", 0)),
        "stars": sum(int(repo.get("stargazers_count", 0)) for repo in original),
        "forks": sum(int(repo.get("forks_count", 0)) for repo in original),
        "languages": sorted(languages.items(), key=lambda item: item[1], reverse=True)[:5],
    }


def contributions_graphql(username: str) -> dict | None:
    if not os.environ.get("GITHUB_TOKEN"):
        return None
    query = (
        "query($login:String!){user(login:$login){contributionsCollection{contributionCalendar"
        "{totalContributions weeks{contributionDays{date contributionCount contributionLevel}}}}}}"
    )
    result = request_json("https://api.github.com/graphql", payload={"query": query, "variables": {"login": username}})
    if not isinstance(result, dict) or result.get("errors"):
        return None
    try:
        calendar = result["data"]["user"]["contributionsCollection"]["contributionCalendar"]
        levels = {"NONE": 0, "FIRST_QUARTILE": 1, "SECOND_QUARTILE": 2, "THIRD_QUARTILE": 3, "FOURTH_QUARTILE": 4}
        days = [
            {"date": item["date"], "count": int(item["contributionCount"]), "level": levels.get(item["contributionLevel"], 0)}
            for week in calendar["weeks"]
            for item in week["contributionDays"]
        ]
        return {"total": int(calendar["totalContributions"]), "days": days}
    except (KeyError, TypeError):
        return None


def contributions_html(username: str) -> dict:
    url = f"https://github.com/users/{username}/contributions"
    request = urllib.request.Request(
        url, headers={"User-Agent": "pretty-github-profile", "X-Requested-With": "XMLHttpRequest"}
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        source = response.read().decode("utf-8", errors="replace")

    tips: dict[str, int] = {}
    for match in re.finditer(r'<tool-tip[^>]*for="([^"]+)"[^>]*>(.*?)</tool-tip>', source, re.I | re.S):
        label = html.unescape(re.sub(r"<[^>]+>", " ", match.group(2)))
        count = re.search(r"(?:No|([\d,]+))\s+contribution", label)
        if count:
            tips[match.group(1)] = int((count.group(1) or "0").replace(",", ""))

    days = []
    for match in re.finditer(r'<td\b([^>]*ContributionCalendar-day[^>]*)>', source, re.I):
        attrs = dict(re.findall(r'([\w:-]+)="([^"]*)"', match.group(1)))
        iso = attrs.get("data-date")
        if not iso:
            continue
        count = attrs.get("data-count")
        days.append({
            "date": iso,
            "count": int(count) if count is not None else tips.get(attrs.get("id", ""), 0),
            "level": int(attrs.get("data-level", "0")),
        })
    if not days:
        raise RuntimeError("GitHub contribution calendar markup could not be parsed")
    total_match = re.search(r"([\d,]+)\s+contributions?\s+in\s+the\s+last\s+year", html.unescape(source), re.I)
    total = int(total_match.group(1).replace(",", "")) if total_match else sum(day["count"] for day in days)
    return {"total": total, "days": sorted(days, key=lambda item: item["date"])}


def streaks(days: list[dict]) -> tuple[int, int]:
    """Return (current streak, longest streak) in days."""
    ordered = sorted(days, key=lambda item: item["date"])
    longest = run = 0
    for item in ordered:
        run = run + 1 if int(item.get("count", 0)) > 0 else 0
        longest = max(longest, run)
    current = 0
    for item in reversed(ordered):
        if int(item.get("count", 0)) > 0:
            current += 1
        elif current or item is ordered[-1]:
            break
    return current, longest


def demo_data() -> tuple[dict, dict]:
    rng = random.Random(430)
    end = date.today()
    start = end - timedelta(days=370)
    days = []
    for offset in range(371):
        iso = start + timedelta(days=offset)
        active = rng.random() > (0.69 if offset < 190 else 0.5)
        level = rng.choices([1, 2, 3, 4], weights=[44, 30, 18, 8])[0] if active else 0
        days.append({"date": iso.isoformat(), "count": rng.randint(level, level * 4) if level else 0, "level": level})
    profile = {
        "public_repos": 19,
        "followers": 11,
        "following": 14,
        "stars": 14,
        "forks": 6,
        "languages": [["Python", 11], ["C++", 3], ["Dart", 2], ["C", 1], ["HTML", 1]],
    }
    return profile, {"total": sum(day["count"] for day in days), "days": days}


# ---------------------------------------------------------------------------
# shared chrome
# ---------------------------------------------------------------------------
def base_style() -> str:
    return (
        ".title{font:700 22px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:__TEXT__}"
        ".display{font:700 28px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:__TEXT__}"
        ".label{font:700 9px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:__TEAL__;letter-spacing:1.6px}"
        ".sub{font:700 9px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:__MUTED__;letter-spacing:1.4px}"
        ".body{font:11px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:__MUTED__}"
        ".mono{font:10px ui-monospace,Consolas,monospace;fill:__MUTED__}"
        ".chip{font:700 8px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:__TEXT__}"
        ".rise{animation:rise .6s cubic-bezier(.32,.72,0,1) both}"
        ".fade{animation:fade .7s ease both}"
        ".bar{transform-origin:left;animation:grow .9s cubic-bezier(.32,.72,0,1) both}"
        ".pulse{animation:pulse 3.2s ease-in-out infinite}"
        "@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}"
        "@keyframes fade{from{opacity:0}to{opacity:1}}"
        "@keyframes grow{from{transform:scaleX(0)}to{transform:scaleX(1)}}"
        "@keyframes pulse{0%,100%{opacity:.35}50%{opacity:1}}"
        "@media(prefers-reduced-motion:reduce){*{animation:none!important}}"
    ).replace("__TEXT__", TEXT).replace("__TEAL__", TEAL).replace("__MUTED__", MUTED)


def gradient_defs(seed: str) -> str:
    return (
        f'<linearGradient id="shell" x1="0" y1="0" x2="1" y2="1">'
        f'<stop stop-color="#0b625b"/><stop offset=".55" stop-color="#0c3b3d"/><stop offset="1" stop-color="#2d4f88"/>'
        f'</linearGradient>'
        f'<linearGradient id="sheen" x1="0" y1="0" x2="1" y2="0">'
        f'<stop stop-color="{TEAL}" stop-opacity="0"/><stop offset=".5" stop-color="{TEAL}" stop-opacity=".55"/>'
        f'<stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></linearGradient>'
        f'<radialGradient id="aura"><stop stop-color="{TEAL}" stop-opacity=".2"/>'
        f'<stop offset="1" stop-color="{TEAL}" stop-opacity="0"/></radialGradient>'
        f'<!-- {escape(seed)} -->'
    )


def frame(height: int, *, panel_fill: str = PANEL) -> str:
    """Outer bezel + inner panel shared by every card."""
    return (
        f'<rect width="{W}" height="{height}" rx="24" fill="{OUTER}"/>'
        f'<rect x="6" y="6" width="{W - 12}" height="{height - 12}" rx="20" fill="url(#shell)" stroke="{HAIR}"/>'
        f'<rect x="22" y="22" width="{W - 44}" height="{height - 44}" rx="18" fill="{panel_fill}" stroke="{EDGE}"/>'
    )


def header(title: str, label: str, right: str = "") -> str:
    right_node = f'<text x="{W - 46}" y="56" text-anchor="end" class="label">{escape(right)}</text>' if right else ""
    return (
        f'<text x="46" y="58" class="title">{escape(title)}</text>'
        f'<text x="47" y="76" class="label">{escape(label)}</text>'
        f'<rect x="46" y="86" width="{W - 92}" height="1" fill="url(#sheen)"/>'
        f"{right_node}"
    )


def svg_open(height: int, aria: str, extra_defs: str = "", extra_css: str = "") -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{height}" viewBox="0 0 {W} {height}" '
        f'role="img" aria-label="{escape(aria)}">'
        f'<defs>{gradient_defs(aria)}{extra_defs}<style>{base_style()}{extra_css}</style></defs>'
    )


# ---------------------------------------------------------------------------
# panel 1 — identity
# ---------------------------------------------------------------------------
def portrait_lines(cfg: dict, cols: int = 60, max_rows: int = 44) -> list[str] | None:
    path = ROOT / cfg.get("photo", "")
    if Image is None or not cfg.get("photo") or not path.exists():
        return None
    with Image.open(path) as source:
        image = ImageOps.autocontrast(ImageEnhance.Contrast(ImageOps.grayscale(source)).enhance(1.25))
        rows = min(max_rows, max(1, round(image.height / image.width * cols * 0.78)))
        small = image.resize((cols, rows), Image.Resampling.LANCZOS)
        pixels = list(small.getdata())
    low, high = min(pixels), max(pixels)
    ramp = " .`:-=+*cs#%@"
    lines = []
    for row in range(rows):
        chars = []
        for value in pixels[row * cols : (row + 1) * cols]:
            normalized = (value - low) / max(1, high - low)
            chars.append(ramp[min(len(ramp) - 1, int((1.0 - normalized) * len(ramp)))])
        lines.append("".join(chars))
    return lines


def ascii_lines(word: str, alphabet: str, scale_x: int = 2, scale_y: int = 2) -> list[str]:
    clean = "".join(char for char in word.upper() if char in GLYPHS)[:8] or "DEV"
    rows = []
    for row in range(7):
        chunks = []
        for char_index, char in enumerate(clean):
            glyph = GLYPHS[char][row]
            chunk = "".join(
                (alphabet[(cell_index + row + char_index) % len(alphabet)] * scale_x) if bit == "1" else (" " * scale_x)
                for cell_index, bit in enumerate(glyph)
            )
            chunks.append(chunk)
        rows.extend(["   ".join(chunks)] * scale_y)
    return rows


def sigil(cfg: dict) -> str:
    """Fallback artwork when no portrait image is available."""
    initials = "".join(part[0] for part in str(cfg["name"]).split()[:2]).upper()
    rings = "".join(
        f'<circle cx="167" cy="216" r="{34 + index * 22}" fill="none" stroke="{PALETTE[index % len(PALETTE)]}" '
        f'stroke-opacity=".38" stroke-dasharray="{6 + index * 3} {10 + index * 2}">'
        f'<animateTransform attributeName="transform" type="rotate" from="{index * 40} 167 216" '
        f'to="{index * 40 + (360 if index % 2 == 0 else -360)} 167 216" dur="{16 + index * 6}s" repeatCount="indefinite"/>'
        f"</circle>"
        for index in range(5)
    )
    return (
        f'{rings}<circle cx="167" cy="216" r="30" fill="{PANEL_2}" stroke="{TEAL}"/>'
        f'<text x="167" y="224" text-anchor="middle" class="display" fill="{MINT}">{escape(initials)}</text>'
        f'<text x="167" y="330" text-anchor="middle" class="mono">portrait offline · add assets/profile-source.png</text>'
    )


def identity_svg(cfg: dict) -> str:
    height = 400
    portrait = portrait_lines(cfg)
    portrait_defs, portrait_body = [], []
    char_w, line_h, font_size = 4.0, 5.3, 5.9
    px, py = 47.0, 104.0
    for row, raw in enumerate(portrait or []):
        text = raw.rstrip()
        if not text.strip():
            continue
        left = len(text) - len(text.lstrip())
        segment = text[left:]
        x = px + left * char_w
        y = py + row * line_h
        width = len(segment) * char_w
        begin = row * 0.038
        portrait_defs.append(
            f'<clipPath id="prow-{row}"><rect x="{x:.1f}" y="{y - 4.8:.1f}" width="{width:.1f}" height="{line_h + 1:.1f}">'
            f'<animate attributeName="width" from="0" to="{width:.1f}" begin="{begin:.3f}s" dur=".32s" fill="freeze"/>'
            f"</rect></clipPath>"
        )
        portrait_body.append(
            f'<g clip-path="url(#prow-{row})"><text x="{x:.1f}" y="{y:.1f}" textLength="{width:.1f}" '
            f'lengthAdjust="spacing" xml:space="preserve">{escape(segment)}</text></g>'
            f'<rect x="{x:.1f}" y="{y - 4.8:.1f}" width="{char_w:.1f}" height="{line_h:.1f}" fill="{MINT}" opacity="0">'
            f'<set attributeName="opacity" to=".9" begin="{begin:.3f}s"/>'
            f'<animate attributeName="x" from="{x:.1f}" to="{x + width:.1f}" begin="{begin:.3f}s" dur=".32s" fill="freeze"/>'
            f'<set attributeName="opacity" to="0" begin="{begin + .32:.3f}s"/></rect>'
        )
    art = "".join(portrait_body) if portrait else sigil(cfg)

    wordmark = cfg.get("wordmark") or str(cfg["name"]).split()[0]
    phase_a = "".join(
        f'<text x="0" y="{16 + row * 12.6:.1f}" textLength="516" lengthAdjust="spacingAndGlyphs" '
        f'xml:space="preserve">{escape(line)}</text>'
        for row, line in enumerate(ascii_lines(wordmark, "$s+"))
    )
    phase_b = "".join(
        f'<text x="0" y="{16 + row * 12.6:.1f}" textLength="516" lengthAdjust="spacingAndGlyphs" '
        f'xml:space="preserve">{escape(line)}</text>'
        for row, line in enumerate(ascii_lines(wordmark, "#*="))
    )

    contact = " · ".join(
        part for part in [
            cfg.get("email"),
            str(cfg.get("website", "")).replace("https://", ""),
            str(cfg.get("github", "")).replace("https://", ""),
        ] if part
    )
    skill_row = chips(cfg.get("skills", [])[:6], 306, 318, accent=EDGE, max_width=552)

    css = (
        f".pascii{{font:700 {font_size}px ui-monospace,Consolas,monospace;fill:{MINT}}}"
        f".ascii{{font:700 10px ui-monospace,Consolas,monospace;fill:{MINT};letter-spacing:.4px}}"
        f".name{{font:700 21px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:{TEXT}}}"
        ".pa{animation:pa 3.4s cubic-bezier(.32,.72,0,1) infinite}"
        ".pb{animation:pb 3.4s cubic-bezier(.32,.72,0,1) infinite}"
        "@keyframes pa{0%,42%{opacity:1}58%,92%{opacity:0}100%{opacity:1}}"
        "@keyframes pb{0%,42%{opacity:0}58%,92%{opacity:1}100%{opacity:0}}"
    )
    defs = "".join(portrait_defs) + (
        '<clipPath id="type"><rect x="0" y="0" width="524" height="200">'
        '<animate attributeName="width" from="0" to="524" dur="2.4s" calcMode="spline" '
        'keySplines=".32 .72 0 1" fill="freeze"/></rect></clipPath>'
    )

    return (
        svg_open(height, f"Animated ASCII identity for {cfg['name']}", defs, css)
        + frame(height, panel_fill=BG)
        + f'<circle cx="200" cy="210" r="185" fill="url(#aura)"/>'
        # terminal bar
        + '<circle cx="46" cy="46" r="5" fill="#ff665d"/><circle cx="64" cy="46" r="5" fill="#f5c451"/>'
          '<circle cx="82" cy="46" r="5" fill="#46d468"/>'
        + f'<text x="450" y="50" text-anchor="middle" class="mono">{escape(cfg["username"].lower())}'
          f'@github: ~$ ./pretty-github --render identity</text>'
        + f'<circle cx="836" cy="46" r="4" fill="{GREEN}" class="pulse"/>'
        + f'<text x="828" y="50" text-anchor="end" class="sub">OPEN TO WORK</text>'
        + f'<rect x="42" y="62" width="{W - 84}" height="1" fill="url(#sheen)"/>'
        # portrait card
        + f'<rect x="42" y="74" width="250" height="286" rx="20" fill="{SUNKEN}" stroke="{EDGE_SOFT}"/>'
        + f'<text x="58" y="94" class="label">PORTRAIT.ASCII / @{escape(cfg["username"].upper())}</text>'
        + f'<g class="pascii">{art}</g>'
        # wordmark card
        + f'<rect x="306" y="74" width="552" height="190" rx="20" fill="{SUNKEN}" stroke="{EDGE_SOFT}"/>'
        + f'<g transform="translate(320 82)" clip-path="url(#type)" class="ascii">'
          f'<g class="pa">{phase_a}</g><g class="pb">{phase_b}</g></g>'
        + f'<rect x="319" y="80" width="6" height="14" fill="{MINT}" opacity="0">'
          f'<set attributeName="opacity" to="1" begin="0s"/>'
          f'<animate attributeName="x" from="319" to="843" dur="2.4s" calcMode="spline" '
          f'keySplines=".32 .72 0 1" fill="freeze"/><set attributeName="opacity" to="0" begin="2.4s"/></rect>'
        # identity block
        + f'<text x="306" y="292" class="name">{escape(cfg["name"])}</text>'
        + f'<text x="306" y="308" class="body">{escape(trim(cfg["role"], 62))} · {escape(cfg["location"])}</text>'
        + skill_row
        + f'<text x="306" y="352" class="mono" font-size="9">{escape(trim(contact, 92))}</text>'
        + f'<text x="306" y="368" class="mono" font-size="9">{escape(trim(cfg.get("education", ""), 92))}</text>'
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# panel 2 — signal
# ---------------------------------------------------------------------------
def metric_card(x: float, y: float, label: str, value: str, color: str, ratio: float, delay: float) -> str:
    width, bar = 260.0, 216.0
    filled = max(14.0, bar * max(0.0, min(1.0, ratio)) ** 0.6)
    # NOTE: the animation must live on an INNER <g> that has no positional
    # "transform" attribute of its own. If a single <g> carries both
    # transform="translate(x y)" AND a CSS animation that sets `transform`
    # (like .rise does), the CSS transform *replaces* the attribute instead
    # of composing with it, so the card snaps to (0,0) once the animation
    # runs — which is exactly the "card jumped to the corner" bug.
    return (
        f'<g transform="translate({x:.0f} {y:.0f})">'
        f'<g class="rise" style="animation-delay:{delay:.2f}s">'
        f'<rect width="{width:.0f}" height="100" rx="18" fill="{PANEL_2}" stroke="{EDGE}" stroke-opacity=".7"/>'
        f'<rect x="0" y="0" width="{width:.0f}" height="100" rx="18" fill="none" stroke="{color}" stroke-opacity=".18"/>'
        f'<text x="22" y="28" class="label">{escape(label)}</text>'
        f'<text x="22" y="66" class="metric" fill="{color}">{escape(value)}</text>'
        f'<rect x="22" y="80" width="{bar:.0f}" height="7" rx="4" fill="{TRACK}"/>'
        f'<rect x="22" y="80" width="{filled:.0f}" height="7" rx="4" fill="{color}" class="bar" '
        f'style="animation-delay:{delay + .1:.2f}s"/></g></g>'
    )


def signal_svg(cfg: dict, profile: dict, contribution: dict) -> str:
    height = 580
    current, longest = streaks(contribution["days"])
    metrics = [
        ("CONTRIBUTIONS", contribution["total"], PURPLE),
        ("STARS EARNED", profile["stars"], TEAL),
        ("REPOSITORIES", profile["public_repos"], BLUE),
        ("FOLLOWERS", profile["followers"], CYAN),
        ("CURRENT STREAK", current, GREEN),
        ("LONGEST STREAK", longest, ORANGE),
    ]
    peak = max(1, max(int(value) for _, value, _ in metrics))
    cards = "".join(
        metric_card(
            42 + (index % 3) * 278,
            100 + (index // 3) * 116,
            label,
            f"{value:,}",
            color,
            int(value) / peak,
            index * 0.08,
        )
        for index, (label, value, color) in enumerate(metrics)
    )

    languages = profile.get("languages") or [(skill, 1) for skill in cfg.get("skills", [])[:5]]
    total = max(1, sum(int(count) for _, count in languages))
    rows = []
    for index, (language, count) in enumerate(languages[:5]):
        y = 400 + index * 26
        share = int(count) / total
        color = PALETTE[index % len(PALETTE)]
        rows.append(
            f'<circle cx="52" cy="{y - 4}" r="5" fill="{color}"/>'
            f'<text x="70" y="{y}" class="lang">{escape(str(language))}</text>'
            f'<text x="250" y="{y}" text-anchor="end" class="pct" fill="{color}">{round(share * 100)}%</text>'
            f'<rect x="270" y="{y - 11}" width="{W - 316}" height="9" rx="5" fill="{TRACK}"/>'
            f'<rect x="270" y="{y - 11}" width="{max(14, int((W - 316) * share)):d}" height="9" rx="5" fill="{color}" '
            f'class="bar" style="animation-delay:{.5 + index * .08:.2f}s"/>'
        )

    css = (
        f".metric{{font:700 30px 'Trebuchet MS','Segoe UI',Verdana,sans-serif}}"
        f".lang{{font:700 12px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:{TEXT}}}"
        ".pct{font:700 11px ui-monospace,Consolas,monospace}"
    )
    return (
        svg_open(height, f"Profile signal and language stack for {cfg['username']}", "", css)
        + frame(height)
        + header("Profile Signal", f"LIVE GITHUB TELEMETRY / @{cfg['username'].upper()}", "> SIGNAL.SCAN")
        + cards
        + f'<rect x="46" y="352" width="{W - 92}" height="1" fill="url(#sheen)"/>'
        + f'<text x="46" y="382" class="title">Language Stack</text>'
        + f'<text x="{W - 46}" y="382" text-anchor="end" class="label">REPOSITORY-WEIGHTED</text>'
        + "".join(rows)
        + f'<text x="46" y="546" class="mono">{escape(trim(cfg["status"], 70))}</text>'
        + f'<text x="{W - 46}" y="546" text-anchor="end" class="mono">auto-refreshed daily via GitHub Actions</text>'
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# panel 3 — contributions
# ---------------------------------------------------------------------------
def calendar_layout(days: list[dict]) -> tuple[list[tuple[dict, int, int]], int]:
    if not days:
        return [], 53
    parsed = sorted(((date.fromisoformat(item["date"]), item) for item in days), key=lambda pair: pair[0])
    origin = parsed[0][0] - timedelta(days=(parsed[0][0].weekday() + 1) % 7)
    placed = [(item, (current - origin).days // 7, (current.weekday() + 1) % 7) for current, item in parsed]
    return placed, max(col for _, col, _ in placed) + 1


def contributions_svg(cfg: dict, contribution: dict) -> str:
    height = 330
    placed, weeks = calendar_layout(contribution["days"][-371:])
    cell, gap = 10, 3
    pitch = cell + gap
    grid_width = weeks * pitch - gap
    grid_x = (W - grid_width) // 2 + 12
    grid_y = 122
    colors = ["#102f30", "#15504c", "#167b70", "#1aae9b", TEAL]

    nodes = []
    months = []
    seen_months: set[str] = set()
    for item, col, row in placed:
        level = min(4, int(item.get("level", 0)))
        delay = ((col + row) % 18) * 0.025
        nodes.append(
            f'<rect x="{grid_x + col * pitch}" y="{grid_y + row * pitch}" width="{cell}" height="{cell}" rx="2" '
            f'fill="{colors[level]}" class="cell" style="animation-delay:{delay:.3f}s">'
            f'<title>{escape(item["date"])}: {item.get("count", 0)} contributions</title></rect>'
        )
        stamp = date.fromisoformat(item["date"])
        key = f"{stamp.year}-{stamp.month}"
        if key not in seen_months and stamp.day <= 7 and col < weeks - 1:
            seen_months.add(key)
            months.append(
                f'<text x="{grid_x + col * pitch}" y="{grid_y - 8}" class="mono" font-size="9">'
                f'{stamp.strftime("%b").upper()}</text>'
            )

    weekdays = "".join(
        f'<text x="{grid_x - 10}" y="{grid_y + index * pitch + 9}" text-anchor="end" class="mono" font-size="8">{name}</text>'
        for index, name in ((1, "MON"), (3, "WED"), (5, "FRI"))
    )
    legend = "".join(f'<rect x="{712 + i * 14}" y="52" width="10" height="10" rx="2" fill="{color}"/>' for i, color in enumerate(colors))
    current, longest = streaks(contribution["days"])
    busiest = max(contribution["days"], key=lambda item: int(item.get("count", 0)), default={"date": "—", "count": 0})
    stats = (
        f'<text x="46" y="238" class="mono">CURRENT STREAK <tspan fill="{GREEN}">{current}d</tspan>'
        f'   ·   LONGEST <tspan fill="{ORANGE}">{longest}d</tspan>'
        f'   ·   PEAK DAY <tspan fill="{TEAL}">{escape(str(busiest.get("date", "—")))}</tspan>'
        f' ({busiest.get("count", 0)})</text>'
    )

    css = (
        ".cell{animation:cellIn .55s cubic-bezier(.32,.72,0,1) both}"
        ".ship{animation:travel 13s cubic-bezier(.65,0,.35,1) infinite}"
        ".shotA{animation:shoot 1.7s cubic-bezier(.32,.72,0,1) infinite}"
        ".shotB{animation:shoot 1.7s .72s cubic-bezier(.32,.72,0,1) infinite}"
        "@keyframes cellIn{from{opacity:0;transform:translateY(5px)}to{opacity:1;transform:translateY(0)}}"
        "@keyframes travel{0%,100%{transform:translateX(0)}50%{transform:translateX(700px)}}"
        "@keyframes shoot{0%{opacity:0;transform:translateY(0) scaleY(.4)}18%{opacity:1}"
        "75%,100%{opacity:0;transform:translateY(-58px) scaleY(1)}}"
    )
    return (
        svg_open(height, f"Contribution activity for {cfg['username']}", "", css)
        + frame(height)
        + header("Contribution Activity", f"{contribution['total']:,} CONTRIBUTIONS IN THE LAST YEAR")
        + f'<text x="674" y="62" class="mono">LESS</text>{legend}'
        + f'<text x="{W - 46}" y="62" text-anchor="end" class="mono">MORE</text>'
        + "".join(months) + weekdays + "".join(nodes)
        + stats
        + f'<path d="M66 272H834" stroke="#174541" stroke-dasharray="2 7"/>'
        + '<g class="ship"><g transform="translate(74 276)">'
          f'<g class="shotA"><rect x="12" y="-21" width="3" height="14" rx="2" fill="{MINT}"/>'
          f'<circle cx="13.5" cy="-24" r="3" fill="{MINT}"/></g>'
          f'<g class="shotB"><rect x="12" y="-21" width="3" height="14" rx="2" fill="{BLUE}"/>'
          f'<circle cx="13.5" cy="-24" r="3" fill="{BLUE}"/></g>'
          f'<path d="M13 0L25 27l-12-6-12 6z" fill="{MINT}" stroke="#d9fff8"/>'
          f'<path d="M13 9L18 23H8z" fill="{BLUE}"/>'
          f'<path d="M5 24l-4 9 9-6M21 24l4 9-9-6" fill="none" stroke="{TEAL}" stroke-width="2"/>'
          f'<path d="M9 29l4 10 4-10" fill="{ORANGE}" opacity=".85"/></g></g>'
        + f'<text x="{W - 46}" y="300" text-anchor="end" class="label">ORBITAL COMMIT SCAN / LIVE</text>'
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# panel 4 — arsenal (grouped stack)
# ---------------------------------------------------------------------------
def arsenal_svg(cfg: dict) -> str:
    groups = cfg.get("stack", [])[:6]
    height = 690
    card_w, card_h = 400, 170
    cards = []
    for index, group in enumerate(groups):
        x = 42 + (index % 2) * (card_w + 16)
        y = 100 + (index // 2) * (card_h + 16)
        accent = group.get("accent", PALETTE[index % len(PALETTE)])
        rows = []
        for item_index, item in enumerate(group.get("items", [])[:5]):
            iy = 52 + item_index * 23
            level = max(0, min(100, int(item.get("level", 50))))
            rows.append(
                f'<text x="18" y="{iy}" class="skill">{escape(str(item.get("name", "")))}</text>'
                f'<rect x="150" y="{iy - 9}" width="190" height="8" rx="4" fill="{TRACK}"/>'
                f'<rect x="150" y="{iy - 9}" width="{round(190 * level / 100)}" height="8" rx="4" fill="{accent}" '
                f'class="bar" style="animation-delay:{index * .09 + item_index * .06:.2f}s"/>'
                f'<text x="384" y="{iy}" text-anchor="end" class="pct" fill="{accent}">{level}</text>'
            )
        # same fix as metric_card: keep the positional transform on an outer
        # <g> and put class="rise" on an inner <g> so the CSS animation
        # doesn't blow away the translate(x y) placement.
        cards.append(
            f'<g transform="translate({x} {y})">'
            f'<g class="rise" style="animation-delay:{index * .09:.2f}s">'
            f'<rect width="{card_w}" height="{card_h}" rx="18" fill="{PANEL_2}" stroke="{EDGE}" stroke-opacity=".6"/>'
            f'<rect width="4" height="{card_h}" rx="2" fill="{accent}" opacity=".85"/>'
            f'<text x="18" y="28" class="label" fill="{accent}">{escape(str(group.get("group", "")))}</text>'
            f'<circle cx="378" cy="23" r="4" fill="{accent}" class="pulse"/>'
            f'<rect x="18" y="36" width="{card_w - 36}" height="1" fill="{EDGE}" opacity=".25"/>'
            f'{"".join(rows)}</g></g>'
        )

    css = (
        f".skill{{font:700 11px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:{TEXT}}}"
        ".pct{font:700 9px ui-monospace,Consolas,monospace}"
    )
    return (
        svg_open(height, f"Technology arsenal for {cfg['name']}", "", css)
        + frame(height)
        + header("Arsenal", "TOOLING GROUPED BY DOMAIN · SELF-ASSESSED DEPTH", "> STACK.MAP")
        + "".join(cards)
        + f'<text x="46" y="662" class="mono">{escape(trim(cfg.get("education", ""), 54))}</text>'
        + f'<text x="{W - 46}" y="662" text-anchor="end" class="mono">{escape(trim(cfg["role"], 52))}</text>'
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# panel 5 — trajectory (career timeline)
# ---------------------------------------------------------------------------
def trajectory_svg(cfg: dict) -> str:
    roles = cfg.get("experience", [])[:5]
    height = 470
    rail_top, step = 104, 66
    rows = []
    for index, role in enumerate(roles):
        y = rail_top + index * step
        accent = role.get("accent", PALETTE[index % len(PALETTE)])
        node_y = y + 18
        rows.append(
            f'<g class="rise" style="animation-delay:{index * .1:.2f}s">'
            f'<circle cx="64" cy="{node_y}" r="9" fill="{PANEL_2}" stroke="{accent}" stroke-width="2"/>'
            f'<circle cx="64" cy="{node_y}" r="3.5" fill="{accent}"/>'
            f'<text x="92" y="{y + 16}" class="role">{escape(trim(role.get("role", ""), 46))}'
            f'<tspan fill="{accent}"> @ {escape(trim(role.get("org", ""), 30))}</tspan></text>'
            f'<text x="{W - 46}" y="{y + 16}" text-anchor="end" class="mono" fill="{accent}">'
            f'{escape(str(role.get("period", "")))}</text>'
            f'<text x="92" y="{y + 33}" class="body">{escape(trim(role.get("note", ""), 108))}</text>'
            f'{chips(role.get("tags", []), 92, y + 41, accent=accent, max_width=520)}</g>'
        )

    css = f".role{{font:700 13px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:{TEXT}}}"
    return (
        svg_open(height, f"Career trajectory for {cfg['name']}", "", css)
        + frame(height)
        + header("Trajectory", "ROLES · BANKING, PRODUCT AND HARDWARE ENGINEERING", "> CAREER.LOG")
        + f'<path d="M64 {rail_top + 10}V{rail_top + (len(roles) - 1) * step + 18}" stroke="{EDGE}" '
          f'stroke-opacity=".4" stroke-dasharray="3 6"/>'
        + "".join(rows)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# panel 6 — missions (project grid)
# ---------------------------------------------------------------------------
def missions_svg(cfg: dict) -> str:
    projects = cfg.get("projects", [])[:9]
    height = 620
    card_w, card_h = 260, 150
    cards = []
    for index, project in enumerate(projects):
        x = 42 + (index % 3) * (card_w + 18)
        y = 100 + (index // 3) * (card_h + 16)
        accent = project.get("accent", PALETTE[index % len(PALETTE)])
        note_lines = "".join(
            f'<text x="18" y="{78 + line_index * 14}" class="body">{escape(line)}</text>'
            for line_index, line in enumerate(wrap(project.get("note", ""), 10.5, 212, 3))
        )
        # same fix again: outer <g> for translate(x y), inner <g class="rise">
        # for the fade/rise animation.
        cards.append(
            f'<g transform="translate({x} {y})">'
            f'<g class="rise" style="animation-delay:{index * .07:.2f}s">'
            f'<rect width="{card_w}" height="{card_h}" rx="18" fill="{PANEL_2}" stroke="{EDGE}" stroke-opacity=".6"/>'
            f'<rect width="4" height="{card_h}" rx="2" fill="{accent}" opacity=".9"/>'
            f'<text x="18" y="26" class="idx" fill="{accent}">{index + 1:02d}</text>'
            f'<circle cx="{card_w - 20}" cy="21" r="4" fill="{accent}" opacity=".8"/>'
            f'<text x="18" y="47" class="proj">{escape(trim(project.get("name", ""), 26))}</text>'
            f'<text x="18" y="61" class="mono" font-size="9">{escape(trim(project.get("link", ""), 34))}</text>'
            f'{note_lines}'
            f'{chips(project.get("tags", []), 18, 120, size=7.5, accent=accent, gap=5, max_width=228)}</g></g>'
        )

    css = (
        f".proj{{font:700 13px 'Trebuchet MS','Segoe UI',Verdana,sans-serif;fill:{TEXT}}}"
        ".idx{font:700 9px ui-monospace,Consolas,monospace;letter-spacing:1px}"
    )
    return (
        svg_open(height, f"Featured project missions by {cfg['name']}", "", css)
        + frame(height)
        + header("Missions", "PRODUCTION SYSTEMS · PLATFORMS · RESEARCH", "> PROJECT.INDEX")
        + "".join(cards)
        + "</svg>"
    )


# ---------------------------------------------------------------------------
# entrypoint
# ---------------------------------------------------------------------------
BUILDERS = ("identity", "signal", "contributions", "arsenal", "trajectory", "missions")


def main() -> int:
    parser = argparse.ArgumentParser(description="Render the Pretty GitHub profile assets.")
    parser.add_argument("--demo", action="store_true", help="use deterministic offline data")
    parser.add_argument("--only", nargs="+", choices=BUILDERS, help="render a subset of panels")
    args = parser.parse_args()

    cfg = load_config()
    username = os.environ.get("GH_USERNAME") or os.environ.get("GITHUB_REPOSITORY_OWNER") or cfg["username"]
    cfg["username"] = username

    static_only = set(args.only or BUILDERS) <= {"identity", "arsenal", "trajectory", "missions"}
    if args.demo or static_only:
        profile, contribution = demo_data()
    else:
        try:
            profile = profile_data(username)
            contribution = contributions_graphql(username) or contributions_html(username)
        except (urllib.error.URLError, RuntimeError, OSError) as exc:
            raise SystemExit(f"GitHub data request failed: {exc}. Use --demo for an offline preview.")

    renderers = {
        "identity": lambda: identity_svg(cfg),
        "signal": lambda: signal_svg(cfg, profile, contribution),
        "contributions": lambda: contributions_svg(cfg, contribution),
        "arsenal": lambda: arsenal_svg(cfg),
        "trajectory": lambda: trajectory_svg(cfg),
        "missions": lambda: missions_svg(cfg),
    }
    ASSETS.mkdir(exist_ok=True)
    for name in args.only or BUILDERS:
        (ASSETS / f"{name}.svg").write_text(renderers[name](), encoding="utf-8")
        print(f"  · assets/{name}.svg")
    print(f"Pretty GitHub assets generated for @{username}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())