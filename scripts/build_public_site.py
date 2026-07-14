from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote

from guidebook_common import (
    guide_spots,
    hero_photo,
    meal_recommendations,
    route_map_filename,
    route_map_points,
    route_map_url,
    route_points,
    short_text,
    today_theme,
    todays_tips,
)
from route_map_renderer import render_route_map


ROOT = Path(__file__).resolve().parents[1]
ITINERARY_DIR = ROOT / "itinerary" / "days"
OUT = ROOT / "docs" / "index.html"
RAW_IMAGE_BASE = "https://raw.githubusercontent.com/inzaikun/hokkaido-trip-plan/main/images/"
RAW_MAP_BASE = "https://raw.githubusercontent.com/inzaikun/hokkaido-trip-plan/main/maps/"
COVER_IMAGE_NAME = "cover.png"
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]


@dataclass(frozen=True)
class TimelineItem:
    time: str
    kind: str
    place: str
    detail: str
    duration: str


@dataclass(frozen=True)
class Restaurant:
    meal: str
    name: str
    area: str
    memo: str


@dataclass(frozen=True)
class Photo:
    place: str
    image: str
    caption: str
    credit: str


@dataclass(frozen=True)
class Day:
    date: str
    day: str
    title: str
    area: str
    hero: str
    summary: str
    timeline: list[TimelineItem]
    restaurants: list[Restaurant]
    photos: list[Photo]
    notes: list[str]


def esc(value: str) -> str:
    return html.escape(value, quote=True)


def clean_cell(value: str) -> str:
    return value.strip().replace("<br>", "\n")


def parse_table(text: str) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [clean_cell(cell) for cell in line.strip("|").split("|")]
        if all(set(cell) <= {"-", ":", " "} for cell in cells):
            continue
        rows.append(cells)
    return rows


def section(text: str, name: str) -> str:
    pattern = rf"^## {re.escape(name)}\s*$"
    matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
    if not matches:
        return ""
    start = matches[0].end()
    next_match = re.search(r"^## .+$", text[start:], flags=re.MULTILINE)
    end = start + next_match.start() if next_match else len(text)
    return text[start:end].strip()


def parse_meta(raw: str, path: Path) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in raw.splitlines()[1:24]:
        if not line.strip():
            continue
        if line.startswith("## "):
            break
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
    meta.setdefault("date", path.stem)
    meta.setdefault("day", "")
    meta.setdefault("title", path.stem)
    meta.setdefault("area", "")
    meta.setdefault("hero", meta["title"])
    return meta


def parse_day(path: Path) -> Day:
    raw = path.read_text(encoding="utf-8")
    meta = parse_meta(raw, path)
    timeline_rows = parse_table(section(raw, "Timeline"))
    restaurant_rows = parse_table(section(raw, "Restaurants"))
    photo_rows = parse_table(section(raw, "Photos"))
    notes = [
        line.strip()[2:].strip()
        for line in section(raw, "Notes").splitlines()
        if line.strip().startswith("- ")
    ]

    return Day(
        date=meta["date"],
        day=meta["day"],
        title=meta["title"],
        area=meta["area"],
        hero=meta["hero"],
        summary=section(raw, "Summary").replace("\n", " ").strip(),
        timeline=[
            TimelineItem(row[0], row[1], row[2], row[3], row[4])
            for row in timeline_rows[1:]
            if len(row) >= 5
        ],
        restaurants=[
            Restaurant(row[0], row[1], row[2], row[3])
            for row in restaurant_rows[1:]
            if len(row) >= 4
        ],
        photos=[
            Photo(row[0], row[1], row[2], row[3])
            for row in photo_rows[1:]
            if len(row) >= 4
        ],
        notes=notes,
    )


def formatted_date(value: str) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{parsed.month}/{parsed.day}（{WEEKDAYS[parsed.weekday()]}）"


def image_src(image_name: str) -> str:
    return RAW_IMAGE_BASE + quote(image_name)


def kind_class(kind: str) -> str:
    mapping = {
        "移動": "move",
        "観光": "see",
        "昼食": "food",
        "夕食": "food",
        "朝食": "food",
        "休憩": "rest",
        "手続き": "prep",
        "準備": "prep",
    }
    return mapping.get(kind, "other")


def render_text(value: str) -> str:
    return "<br>".join(esc(part) for part in value.splitlines())


def render_photo(day: Day) -> str:
    photo = hero_photo(day)
    if photo:
        return (
            f'<figure class="hero-photo">'
            f'<img src="{image_src(photo.image)}" alt="{esc(photo.place)}">'
            f'<figcaption>{esc(photo.place)}</figcaption>'
            f"</figure>"
        )
    return (
        f'<div class="hero-photo placeholder">'
        f'<span>{esc(day.hero)}</span>'
        f'<small>写真準備中</small>'
        f"</div>"
    )


def render_timeline(day: Day) -> str:
    items = []
    for item in day.timeline:
        items.append(
            "<li>"
            f'<time>{esc(item.time)}</time>'
            f'<span class="tag {kind_class(item.kind)}">{esc(item.kind)}</span>'
            "<div>"
            f"<strong>{esc(item.place)}</strong>"
            f'<p title="{esc(item.detail)}">{render_text(short_text(item.detail, 86))}</p>'
            f"<small>{esc(item.duration)}</small>"
            "</div>"
            "</li>"
        )
    return "\n".join(items)


def render_restaurants(day: Day) -> str:
    if not day.restaurants:
        return '<p class="empty">候補はこれから追記します。</p>'
    rows = []
    for item in day.restaurants:
        rows.append(
            "<li>"
            f'<span>{esc(item.meal)}</span>'
            f"<strong>{esc(item.name)}</strong>"
            f"<p>{esc(item.area)} / {esc(item.memo)}</p>"
            "</li>"
        )
    return "\n".join(rows)


def render_side_trip(day: Day) -> str:
    spots = guide_spots(day, max_items=1)
    if not spots:
        return ""
    spot = spots[0]
    if spot["image"]:
        visual = f'<img src="{image_src(spot["image"])}" alt="{esc(spot["place"])}">'
    else:
        visual = f'<div class="spot-placeholder">{esc(spot["place"])}</div>'
    return (
        '<section class="side-trip-card">'
        "<h3>より道スポット</h3>"
        "<figure>"
        f"{visual}"
        "<figcaption>"
        f"<strong>{esc(spot['place'])}</strong>"
        f"<span>{esc(short_text(spot['caption'], 64))}</span>"
        '<dl class="spot-meta">'
        f"<div><dt>駐車場</dt><dd>{esc(spot['parking'])}</dd></div>"
        f"<div><dt>滞在</dt><dd>{esc(spot['stay'])}</dd></div>"
        f'<div><dt>地図</dt><dd><a href="{esc(spot["map_url"])}" target="_blank" rel="noreferrer">Google Map</a></dd></div>'
        "</dl>"
        "</figcaption>"
        "</figure>"
        "</section>"
    )


def map_src(image_name: str) -> str:
    return RAW_MAP_BASE + quote(image_name)


def render_route_sketch(day: Day) -> str:
    render_route_map(day, ROOT)
    image_name = route_map_filename(day)
    return (
        '<div class="sketch-map" aria-label="簡易ルートマップ">'
        f'<img src="{map_src(image_name)}" alt="{esc(day.area)}のルート地図" loading="lazy">'
        "</div>"
    )


def render_route(day: Day) -> str:
    points = route_points(day, max_points=8)
    if not points:
        return ""
    rows = []
    for index, point in enumerate(points):
        note = f'<span>{esc(point["note"])}</span>' if point.get("note") else ""
        leg = point.get("leg") or ""
        connector = ""
        if index < len(points) - 1:
            connector = f'<div class="route-leg"><i></i><span>{esc(leg)}</span></div>'
        rows.append(
            '<li class="route-point">'
            f'<strong>{esc(point["place"])}</strong>{note}'
            f"{connector}"
            "</li>"
        )
    return (
        '<section class="route-card">'
        '<div class="card-title-row"><h3>Today\'s Map</h3>'
        f'<a href="{esc(route_map_url(day))}" target="_blank" rel="noreferrer">Google Map</a></div>'
        '<div class="route-card-body">'
        f"{render_route_sketch(day)}"
        f'<ol class="route-map">{"".join(rows)}</ol>'
        "</div>"
        "</section>"
    )


def render_theme(day: Day) -> str:
    return (
        '<section class="theme-card">'
        "<h3>Today's Theme</h3>"
        f"<p>{esc(today_theme(day))}</p>"
        "</section>"
    )


def render_recommendations(day: Day) -> str:
    items = []
    for rec in meal_recommendations(day)[:2]:
        items.append(
            '<article class="meal-card">'
            f'<p class="meal-label">{esc(rec["label"])}</p>'
            f'<h4>{esc(rec["name"])}</h4>'
            f'<p class="stars" aria-label="おすすめ度5">{esc(rec["stars"])}</p>'
            f'<dl><div><dt>予算</dt><dd>{esc(rec["budget"])}</dd></div>'
            f'<div><dt>人気メニュー</dt><dd>{esc(rec["popular"])}</dd></div></dl>'
            f'<p>{esc(short_text(rec["memo"], 48))}</p>'
            "</article>"
        )
    if not items:
        return ""
    return '<section class="meal-recs"><h3>ごはん候補</h3>' + "".join(items) + "</section>"


def render_tips(day: Day) -> str:
    tips = todays_tips(day)
    if not tips:
        return ""
    return (
        '<section class="tips-card">'
        "<h3>Today's Tips</h3>"
        "<ul>"
        + "\n".join(f"<li>{esc(tip)}</li>" for tip in tips)
        + "</ul>"
        "</section>"
    )


def render_day(day: Day) -> str:
    return f"""
      <article class="day" id="day-{esc(day.date)}">
        <header class="day-header">
          <div>
            <p class="day-label">DAY {esc(day.day)} / {formatted_date(day.date)}</p>
            <h2>{esc(day.title)}</h2>
            <p class="area">{esc(day.area)}</p>
          </div>
          {render_photo(day)}
        </header>
        <div class="guide-intro">
          {render_route(day)}
          {render_theme(day)}
        </div>
        <div class="day-layout">
          <section class="timeline-wrap">
            <h3>時刻ベース詳細スケジュール</h3>
            <ol class="timeline">
              {render_timeline(day)}
            </ol>
          </section>
          <aside class="side-panel">
            {render_recommendations(day)}
            {render_side_trip(day)}
            {render_tips(day)}
          </aside>
        </div>
      </article>
"""


def render_page(days: list[Day]) -> str:
    nav_items = "\n".join(
        f'<a href="#day-{esc(day.date)}"><strong>Day {esc(day.day)}</strong><span>{formatted_date(day.date)}</span><em>{esc(day.area)}</em></a>'
        for day in days
    )
    day_sections = "\n".join(render_day(day) for day in days)

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>北海道家族旅行ガイド 2026</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172026;
      --muted: #66717c;
      --line: #d7e0e7;
      --paper: #f7f4ee;
      --surface: #ffffff;
      --mist: #e7f1f4;
      --lake: #146b7c;
      --forest: #3f6b45;
      --berry: #9b3d4e;
      --sun: #c47a24;
      --sky: #3e7fa8;
    }}

    * {{ box-sizing: border-box; }}

    html {{ scroll-behavior: smooth; }}

    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", "YuGothic", "Noto Sans JP", sans-serif;
      color: var(--ink);
      background: var(--paper);
      line-height: 1.7;
    }}

    a {{
      color: var(--lake);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }}

    .hero {{
      min-height: 58vh;
      display: grid;
      align-items: end;
      padding: 46px clamp(18px, 5vw, 72px);
      background:
        linear-gradient(180deg, rgba(11, 40, 47, 0.14), rgba(11, 40, 47, 0.78)),
        url("{image_src(COVER_IMAGE_NAME)}") center/cover;
      color: #fff;
    }}

    .hero > div {{
      max-width: 980px;
    }}

    .hero h1 {{
      margin: 0;
      max-width: 980px;
      font-size: clamp(2.2rem, 6vw, 5rem);
      line-height: 1.04;
      letter-spacing: 0;
    }}

    .hero p {{
      max-width: 820px;
      margin: 16px 0 0;
      font-size: clamp(1rem, 2vw, 1.25rem);
    }}

    main {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 42px 0 72px;
    }}

    .section-title {{
      margin: 0 0 16px;
      font-size: clamp(1.45rem, 3vw, 2.25rem);
      line-height: 1.2;
      letter-spacing: 0;
    }}

    .lead {{
      max-width: 860px;
      margin: 0;
      color: var(--muted);
    }}

    .toc {{
      margin: 34px 0;
      padding: 28px 0;
      border-top: 1px solid var(--line);
      border-bottom: 1px solid var(--line);
    }}

    .day-nav {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 18px;
    }}

    .day-nav a {{
      min-height: 92px;
      padding: 12px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      text-decoration: none;
    }}

    .day-nav strong,
    .day-nav span,
    .day-nav em {{
      display: block;
    }}

    .day-nav strong {{
      color: var(--lake);
      font-size: 0.9rem;
    }}

    .day-nav span {{
      color: var(--ink);
      font-weight: 800;
    }}

    .day-nav em {{
      margin-top: 4px;
      color: var(--muted);
      font-size: 0.85rem;
      font-style: normal;
    }}

    .day {{
      margin-top: 28px;
      padding: clamp(18px, 3vw, 30px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }}

    .day-header {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) minmax(260px, 390px);
      gap: 24px;
      align-items: stretch;
    }}

    .day-label {{
      margin: 0 0 10px;
      color: var(--lake);
      font-weight: 800;
      letter-spacing: 0;
    }}

    .day h2 {{
      margin: 0;
      font-size: clamp(1.55rem, 3vw, 2.4rem);
      line-height: 1.2;
      letter-spacing: 0;
    }}

    .area {{
      margin: 10px 0 0;
      color: var(--muted);
      font-weight: 700;
    }}

    .hero-photo {{
      min-height: 220px;
      margin: 0;
      border-radius: 8px;
      overflow: hidden;
      background: var(--mist);
      position: relative;
    }}

    .hero-photo img {{
      width: 100%;
      height: 100%;
      min-height: 220px;
      object-fit: cover;
      display: block;
    }}

    .hero-photo figcaption {{
      position: absolute;
      left: 12px;
      bottom: 12px;
      padding: 4px 8px;
      border-radius: 4px;
      background: rgba(23, 32, 38, 0.72);
      color: #fff;
      font-size: 0.9rem;
      font-weight: 700;
    }}

    .placeholder {{
      display: grid;
      place-items: center;
      text-align: center;
      color: var(--lake);
    }}

    .placeholder span {{
      display: block;
      font-size: 1.35rem;
      font-weight: 900;
    }}

    .placeholder small {{
      display: block;
      color: var(--muted);
      font-weight: 700;
    }}

    .guide-intro {{
      display: grid;
      grid-template-columns: minmax(0, 1.22fr) minmax(260px, 0.78fr);
      gap: 18px;
      margin-top: 22px;
      align-items: stretch;
    }}

    .route-card,
    .theme-card,
    .meal-card,
    .tips-card {{
      border-radius: 8px;
      border: 1px solid rgba(20, 107, 124, 0.18);
      background: linear-gradient(180deg, #fff, #fbfaf6);
      box-shadow: 0 12px 26px rgba(23, 32, 38, 0.06);
    }}

    .route-card,
    .theme-card {{
      padding: 18px;
    }}

    .card-title-row {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }}

    .card-title-row h3 {{
      margin: 0;
    }}

    .card-title-row a {{
      flex: 0 0 auto;
      border-radius: 999px;
      padding: 4px 10px;
      background: var(--lake);
      color: #fff;
      font-size: 0.78rem;
      font-weight: 900;
      text-decoration: none;
    }}

    .route-card h3,
    .theme-card h3,
    .meal-recs h3,
    .tips-card h3,
    .side-trip-card h3 {{
      display: inline-flex;
      align-items: center;
      gap: 8px;
      margin-bottom: 12px;
      color: var(--lake);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 1.22rem;
    }}

    .route-card-body {{
      display: grid;
      grid-template-columns: minmax(260px, 1.15fr) minmax(180px, 0.85fr);
      gap: 16px;
      align-items: stretch;
    }}

    .sketch-map {{
      min-height: 240px;
      overflow: hidden;
      border-radius: 8px;
      border: 1px solid rgba(20, 107, 124, 0.18);
      background: #d5eaf0;
    }}

    .sketch-map img {{
      display: block;
      width: 100%;
      height: 100%;
      min-height: 240px;
      object-fit: cover;
    }}

    .route-map {{
      margin: 0;
      padding: 0;
      list-style: none;
    }}

    .route-point {{
      position: relative;
      display: grid;
      grid-template-columns: minmax(0, 1fr);
      gap: 4px;
      padding-left: 26px;
    }}

    .route-point::before {{
      content: "";
      position: absolute;
      left: 4px;
      top: 0.48em;
      width: 12px;
      height: 12px;
      border: 3px solid var(--lake);
      border-radius: 999px;
      background: var(--surface);
      box-shadow: 0 0 0 4px #e8f3f4;
    }}

    .route-point strong {{
      font-size: 1rem;
    }}

    .route-point > span {{
      width: fit-content;
      padding: 1px 8px;
      border-radius: 999px;
      color: #fff;
      background: var(--sun);
      font-size: 0.75rem;
      font-weight: 900;
    }}

    .route-leg {{
      min-height: 20px;
      display: grid;
      grid-template-columns: 2px minmax(0, 1fr);
      gap: 12px;
      margin: 3px 0 4px 9px;
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 800;
    }}

    .route-leg i {{
      display: block;
      width: 2px;
      min-height: 100%;
      background: repeating-linear-gradient(to bottom, var(--lake), var(--lake) 5px, transparent 5px, transparent 10px);
    }}

    .theme-card p {{
      margin: 0;
      font-size: 1rem;
      line-height: 1.75;
    }}

    .day-layout {{
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(260px, 0.65fr);
      gap: 22px;
      margin-top: 24px;
      align-items: start;
    }}

    h3 {{
      margin: 0 0 14px;
      font-size: 1.15rem;
      letter-spacing: 0;
    }}

    .timeline {{
      display: grid;
      gap: 6px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}

    .timeline li {{
      display: grid;
      grid-template-columns: 72px 64px minmax(0, 1fr);
      gap: 12px;
      padding: 10px 0;
      border-top: 1px solid var(--line);
    }}

    .timeline li:first-child {{
      border-top: 0;
      padding-top: 0;
    }}

    .timeline time {{
      font-weight: 900;
      color: var(--ink);
      overflow-wrap: anywhere;
    }}

    .tag {{
      align-self: start;
      min-width: 54px;
      padding: 2px 7px;
      border-radius: 999px;
      text-align: center;
      color: #fff;
      font-size: 0.78rem;
      font-weight: 800;
    }}

    .move {{ background: var(--sky); }}
    .see {{ background: var(--forest); }}
    .food {{ background: var(--sun); }}
    .rest {{ background: var(--lake); }}
    .prep {{ background: var(--berry); }}
    .other {{ background: var(--muted); }}

    .timeline strong {{
      display: block;
      font-size: 1rem;
    }}

    .timeline p {{
      margin: 3px 0;
      color: var(--muted);
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
    }}

    .timeline small {{
      color: var(--lake);
      font-weight: 800;
    }}

    .side-panel {{
      display: grid;
      gap: 14px;
    }}

    .side-panel section {{
      padding: 0;
    }}

    .restaurants {{
      display: grid;
      gap: 12px;
      margin: 0;
      padding: 0;
      list-style: none;
    }}

    .restaurants li {{
      padding-top: 12px;
      border-top: 1px solid rgba(63, 107, 69, 0.18);
    }}

    .restaurants li:first-child {{ border-top: 0; padding-top: 0; }}

    .restaurants span {{
      display: inline-block;
      margin-bottom: 3px;
      color: var(--berry);
      font-size: 0.84rem;
      font-weight: 900;
    }}

    .restaurants strong {{
      display: block;
    }}

    .restaurants p,
    .empty {{
      margin: 3px 0 0;
      color: var(--muted);
    }}

    .notes ul {{
      margin: 0;
      padding-left: 1.1em;
      color: var(--muted);
    }}

    .notes li + li {{
      margin-top: 6px;
    }}

    .meal-recs {{
      display: grid;
      gap: 12px;
    }}

    .meal-card {{
      padding: 13px;
      background: #fffaf0;
    }}

    .meal-card h4 {{
      margin: 2px 0 2px;
      font-size: 0.98rem;
    }}

    .meal-label {{
      margin: 0;
      color: var(--berry);
      font-weight: 900;
      font-size: 0.86rem;
    }}

    .stars {{
      margin: 0 0 5px;
      color: #d27d22;
      letter-spacing: 0;
      font-weight: 900;
      font-size: 0.82rem;
    }}

    .meal-card dl,
    .spot-meta {{
      display: grid;
      gap: 4px;
      margin: 0 0 5px;
    }}

    .meal-card dl div,
    .spot-meta div {{
      display: grid;
      grid-template-columns: 76px minmax(0, 1fr);
      gap: 8px;
    }}

    .meal-card dt,
    .spot-meta dt {{
      color: var(--lake);
      font-weight: 900;
    }}

    .meal-card dd,
    .spot-meta dd {{
      margin: 0;
      color: var(--ink);
    }}

    .meal-card p:last-child {{
      margin: 8px 0 0;
      color: var(--muted);
    }}

    .side-trip-card {{
      padding: 14px;
      border-radius: 8px;
      border: 1px solid rgba(20, 107, 124, 0.18);
      background: #f8f2e8;
    }}

    .side-trip-card figure {{
      margin: 0;
      overflow: hidden;
      border-radius: 8px;
      background: var(--surface);
    }}

    .side-trip-card img {{
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
    }}

    .side-trip-card figcaption {{
      display: grid;
      gap: 5px;
      padding: 11px;
    }}

    .side-trip-card figcaption strong {{
      color: var(--ink);
      line-height: 1.35;
    }}

    .side-trip-card figcaption span {{
      display: -webkit-box;
      -webkit-line-clamp: 2;
      -webkit-box-orient: vertical;
      overflow: hidden;
      color: var(--muted);
      font-size: 0.9rem;
      line-height: 1.55;
    }}

    .tips-card {{
      padding: 14px;
      background: #f4f8ef;
    }}

    .tips-card ul {{
      margin: 0;
      padding-left: 1.1em;
      color: var(--ink);
    }}

    .tips-card li + li {{
      margin-top: 6px;
    }}

    .spot-placeholder {{
      width: 100%;
      aspect-ratio: 16 / 10;
      display: grid;
      place-items: center;
      padding: 14px;
      background: var(--mist);
      color: var(--lake);
      text-align: center;
      font-weight: 900;
    }}

    footer {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 26px 0 44px;
      color: var(--muted);
      font-size: 0.94rem;
    }}

    @media (max-width: 900px) {{
      .day-nav,
      .day-header,
      .guide-intro,
      .day-layout,
      .route-card-body {{
        grid-template-columns: 1fr;
      }}

    }}

    @media (max-width: 620px) {{
      .hero {{
        min-height: 46vh;
        padding: 34px 18px;
      }}

      main {{
        width: min(100% - 20px, 1180px);
      }}

      .timeline li {{
        grid-template-columns: 64px minmax(0, 1fr);
      }}

      .timeline .tag {{
        grid-column: 2;
        justify-self: start;
      }}

      .timeline li > div {{
        grid-column: 1 / -1;
      }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div>
      <h1>北海道家族旅行ガイド 2026</h1>
      <p>フェリーで北の大地へ。湖、花畑、峡谷、知床の森をつなぐ13日間を、移動時間と食事候補まで読める家族旅行ガイドにまとめました。</p>
    </div>
  </header>

  <main>
    <section>
      <h2 class="section-title">旅のハイライト</h2>
      <p class="lead">仙台港から船で渡り、洞爺湖の湖畔、札幌の街歩き、富良野・美瑛の花と丘、層雲峡の峡谷、道東の湖と知床へ。読むだけで旅の流れが浮かぶよう、1日ごとの見どころと動き方を整理しています。</p>
    </section>

    <section class="toc">
      <h2 class="section-title">DAY別ガイド目次</h2>
      <p class="lead">気になる日を選ぶと、ルート、見どころ、食事候補、時刻入りスケジュールへ移動します。</p>
      <nav class="day-nav" aria-label="日別リンク">
        {nav_items}
      </nav>
    </section>

    <section id="days">
      <h2 class="section-title">13日間の詳細ガイド</h2>
      {day_sections}
    </section>
  </main>

  <footer>
    <p>北海道家族旅行ガイド 2026 / inzaikun/hokkaido-trip-plan</p>
  </footer>
</body>
</html>
"""


def main() -> None:
    days = [parse_day(path) for path in sorted(ITINERARY_DIR.glob("*.md"))]
    if not days:
        raise SystemExit("No itinerary day files found.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render_page(days), encoding="utf-8")
    print(f"Generated {OUT} from {len(days)} day files")


if __name__ == "__main__":
    main()
