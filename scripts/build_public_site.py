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
    map_url,
    route_map_filename,
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
GITHUB_URL = "https://github.com/inzaikun/hokkaido-trip-plan"
PDF_URL = GITHUB_URL + "/raw/main/output/hokkaido-family-travel-guide.pdf"
PPTX_URL = GITHUB_URL + "/raw/main/output/hokkaido-family-travel-guide.pptx"
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
            f'<img src="{image_src(photo.image)}" alt="{esc(photo.place)}" loading="lazy">'
            f'<figcaption>{esc(photo.place)}</figcaption>'
            f"</figure>"
        )
    return (
        f'<div class="hero-photo quiet-placeholder" aria-label="{esc(day.hero)}">'
        f"<span>{esc(day.hero)}</span>"
        f"</div>"
    )


def first_time(day: Day) -> str:
    return day.timeline[0].time if day.timeline else "-"


def last_time(day: Day) -> str:
    return day.timeline[-1].time if day.timeline else "-"


def parse_duration_minutes(text: str) -> int:
    text = text.strip()
    total = 0
    hour_match = re.search(r"(\d+)時間", text)
    minute_match = re.search(r"(\d+)分", text)
    if hour_match:
        total += int(hour_match.group(1)) * 60
    if minute_match:
        total += int(minute_match.group(1))
    elif "一晩" in text:
        total += 0
    return total


def travel_minutes(day: Day) -> int:
    return sum(
        parse_duration_minutes(item.duration)
        for item in day.timeline
        if item.kind == "移動"
    )


def travel_time_label(minutes: int) -> str:
    if minutes <= 0:
        return "移動時間は当日調整"
    hours, mins = divmod(minutes, 60)
    if hours and mins:
        return f"走行 約{hours}時間{mins}分"
    if hours:
        return f"走行 約{hours}時間"
    return f"走行 約{mins}分"


def travel_load(day: Day) -> str:
    minutes = travel_minutes(day)
    if minutes >= 300:
        return "高"
    if minutes >= 180:
        return "中"
    return "低"


def meal_area(day: Day, meal: str) -> str:
    for restaurant in day.restaurants:
        if meal in restaurant.meal:
            return restaurant.area or restaurant.name
    for item in day.timeline:
        if meal in item.kind:
            return item.place
    return "当日選択"


def highlights(day: Day, limit: int = 3) -> list[str]:
    results: list[str] = []

    def add(place: str) -> None:
        place = place.strip()
        if place and place not in results:
            results.append(place)

    for photo in day.photos:
        add(photo.place)
        if len(results) >= limit:
            return results[:limit]
    for item in day.timeline:
        if item.kind == "観光":
            add(item.place)
            if len(results) >= limit:
                return results[:limit]
    for point in route_points(day, max_points=7):
        add(point["place"])
        if len(results) >= limit:
            return results[:limit]
    return results[:limit]


def compact_route(day: Day) -> list[dict[str, str]]:
    return route_points(day, max_points=7)


def render_route_line(day: Day) -> str:
    points = compact_route(day)
    if not points:
        return ""
    items = []
    for index, point in enumerate(points):
        leg = point.get("leg") or ""
        connector = ""
        if index < len(points) - 1:
            connector = (
                '<span class="route-arrow" aria-hidden="true">'
                '<span class="desktop-arrow">→</span><span class="mobile-arrow">↓</span>'
                "</span>"
            )
            if leg:
                connector += f'<small class="route-time">{esc(leg)}</small>'
        note = f'<em>{esc(point["note"])}</em>' if point.get("note") else ""
        items.append(
            '<li>'
            f'<strong>{esc(point["place"])}</strong>{note}'
            f"{connector}"
            "</li>"
        )
    return (
        '<div class="summary-route">'
        "<p>Today&apos;s Route</p>"
        f'<ol>{"".join(items)}</ol>'
        "</div>"
    )


def render_summary_chips(day: Day) -> str:
    minutes = travel_minutes(day)
    chips = [
        ("出発", first_time(day)),
        ("終了予定", last_time(day)),
        ("移動負荷", travel_load(day)),
        ("走行", travel_time_label(minutes).replace("走行 ", "")),
        ("昼", meal_area(day, "昼食")),
        ("夜", meal_area(day, "夕食")),
    ]
    return (
        '<dl class="summary-chips">'
        + "".join(
            f"<div><dt>{esc(label)}</dt><dd>{esc(value)}</dd></div>"
            for label, value in chips
        )
        + "</dl>"
    )


def render_highlights(day: Day) -> str:
    items = highlights(day)
    if not items:
        return ""
    return (
        '<div class="highlights"><p>HIGHLIGHT</p><ul>'
        + "".join(f"<li>{esc(item)}</li>" for item in items)
        + "</ul></div>"
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
            f"<p>{render_text(item.detail)}</p>"
            f"<small>{esc(item.duration)}</small>"
            "</div>"
            "</li>"
        )
    return "\n".join(items)


def render_restaurant_cards(day: Day) -> str:
    if not day.restaurants:
        return '<p class="empty">候補はこれから追記します。</p>'
    rows = []
    for item in day.restaurants:
        rows.append(
            '<article class="restaurant-card">'
            f'<p>{esc(item.meal)} / {esc(item.area)}</p>'
            f"<h5>{esc(item.name)}</h5>"
            f"<span>{esc(item.memo)}</span>"
            f'<a href="{esc(map_url(item.name, item.area))}" target="_blank" rel="noreferrer">Google Mapsで見る</a>'
            "</article>"
        )
    return "\n".join(rows)


def render_side_trip(day: Day) -> str:
    spots = guide_spots(day, max_items=1)
    if not spots:
        return ""
    spot = spots[0]
    if spot["image"]:
        visual = f'<img src="{image_src(spot["image"])}" alt="{esc(spot["place"])}" loading="lazy">'
    else:
        visual = f'<div class="spot-placeholder" aria-label="{esc(spot["place"])}"></div>'
    return (
        '<section class="side-trip-card" aria-label="より道スポット">'
        "<h4>より道スポット</h4>"
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


def render_route_detail(day: Day) -> str:
    points = compact_route(day)
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
        '<section class="detail-section route-card">'
        '<div class="card-title-row"><h4>Today\'s Route</h4>'
        f'<a href="{esc(route_map_url(day))}" target="_blank" rel="noreferrer">Google Map</a></div>'
        '<div class="route-card-body">'
        f"{render_route_sketch(day)}"
        f'<ol class="route-map">{"".join(rows)}</ol>'
        "</div>"
        "</section>"
    )


def render_tip_list(day: Day) -> str:
    tips = todays_tips(day)
    if not tips:
        return '<p class="empty">当日の天候と体調に合わせて調整します。</p>'
    return (
        "<ul>"
        + "\n".join(f"<li>{esc(tip)}</li>" for tip in tips)
        + "</ul>"
    )


def render_photo_grid(day: Day) -> str:
    photos = [photo for photo in day.photos if photo.image][:4]
    if not photos:
        return '<p class="empty">写真は追加予定です。</p>'
    return (
        '<div class="photo-grid">'
        + "".join(
            "<figure>"
            f'<img src="{image_src(photo.image)}" alt="{esc(photo.place)}" loading="lazy">'
            "<figcaption>"
            f"<strong>{esc(photo.place)}</strong>"
            f"<span>{esc(short_text(photo.caption, 70))}</span>"
            f"<small>{esc(photo.credit)}</small>"
            "</figcaption>"
            "</figure>"
            for photo in photos
        )
        + "</div>"
    )


def render_nested_details(title: str, body: str, css_class: str = "", open_attr: bool = False) -> str:
    opened = " open" if open_attr else ""
    class_name = f' class="inner-detail {css_class}"' if css_class else ' class="inner-detail"'
    return f"<details{class_name}{opened}><summary>{esc(title)}</summary>{body}</details>"


def render_day(day: Day) -> str:
    return f"""
      <article class="day-card" id="day-{esc(day.date)}" data-date="{esc(day.date)}">
        <header class="day-summary">
          {render_photo(day)}
          <div class="summary-copy">
            <p class="day-label">DAY {esc(day.day)} / {formatted_date(day.date)}</p>
            <h3>{esc(day.title)}</h3>
            {render_route_line(day)}
            {render_summary_chips(day)}
            {render_highlights(day)}
          </div>
        </header>
        <details class="day-detail">
          <summary>詳細を見る</summary>
          <div class="day-detail-body">
            <section class="theme-card">
              <h4>今日のテーマ</h4>
              <p>{esc(today_theme(day))}</p>
            </section>
            {render_route_detail(day)}
            {render_nested_details(
                "時刻表",
                '<ol class="timeline">' + render_timeline(day) + "</ol>",
                "timeline-detail",
                True,
            )}
            {render_nested_details(
                "食事候補",
                '<div class="restaurant-grid">' + render_restaurant_cards(day) + "</div>" + render_side_trip(day),
                "meal-detail",
            )}
            {render_nested_details(
                "写真で見るスポット",
                render_photo_grid(day),
                "photo-detail",
            )}
            {render_nested_details(
                "注意点・雨天プラン",
                render_tip_list(day),
                "note-detail",
            )}
          </div>
        </details>
      </article>
"""


def render_page(days: list[Day]) -> str:
    nav_items = "\n".join(
        f'<a href="#day-{esc(day.date)}"><strong>Day {esc(day.day)}</strong><span>{formatted_date(day.date)}</span></a>'
        for day in days
    )
    day_sections = "\n".join(render_day(day) for day in days)
    style = """
    :root {
      color-scheme: light;
      --ink: #172026;
      --muted: #5f6f78;
      --line: #d7e2e4;
      --paper: #faf7ef;
      --surface: #ffffff;
      --mist: #eaf3f2;
      --navy: #123846;
      --lake: #176f82;
      --forest: #3f7451;
      --sun: #b9772a;
      --berry: #9a4753;
      --shadow: 0 14px 34px rgba(18, 56, 70, 0.08);
    }

    * { box-sizing: border-box; }

    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", "YuGothic", "Noto Sans JP", sans-serif;
      color: var(--ink);
      background: var(--paper);
      line-height: 1.68;
      overflow-x: hidden;
    }

    a {
      color: var(--lake);
      text-decoration-thickness: 1px;
      text-underline-offset: 3px;
    }

    img { max-width: 100%; }

    .skip-link {
      position: absolute;
      left: 12px;
      top: -44px;
      z-index: 20;
      padding: 8px 12px;
      background: var(--navy);
      color: #fff;
    }

    .skip-link:focus { top: 12px; }

    .top-nav {
      position: sticky;
      top: 0;
      z-index: 10;
      display: flex;
      align-items: center;
      gap: 12px;
      padding: 10px clamp(14px, 4vw, 48px);
      border-bottom: 1px solid rgba(215, 226, 228, 0.9);
      background: rgba(250, 247, 239, 0.92);
      backdrop-filter: blur(12px);
    }

    .brand {
      flex: 0 0 auto;
      color: var(--navy);
      font-weight: 900;
      text-decoration: none;
    }

    .top-nav .nav-links {
      display: flex;
      align-items: center;
      gap: 6px;
      margin-left: auto;
      overflow-x: auto;
      scrollbar-width: none;
    }

    .top-nav .nav-links::-webkit-scrollbar { display: none; }

    .top-nav a:not(.brand),
    .hero-links a,
    .detail-link {
      flex: 0 0 auto;
      padding: 7px 10px;
      border: 1px solid rgba(23, 111, 130, 0.28);
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.76);
      color: var(--navy);
      font-size: 0.88rem;
      font-weight: 800;
      text-decoration: none;
    }

    .hero {
      display: grid;
      align-items: end;
      min-height: min(560px, 72vh);
      padding: clamp(42px, 9vw, 92px) clamp(18px, 5vw, 72px) 30px;
      background:
        linear-gradient(180deg, rgba(9, 33, 42, 0.12), rgba(9, 33, 42, 0.82)),
        url(\"""" + image_src(COVER_IMAGE_NAME) + """\") center/cover;
      color: #fff;
    }

    .hero-grid {
      display: grid;
      grid-template-columns: minmax(0, 1.12fr) minmax(280px, 0.88fr);
      gap: clamp(20px, 4vw, 44px);
      align-items: end;
      width: min(1180px, 100%);
    }

    .eyebrow {
      margin: 0 0 10px;
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0;
    }

    h1 {
      max-width: 820px;
      margin: 0;
      font-size: clamp(2.2rem, 6vw, 4.75rem);
      line-height: 1.04;
      letter-spacing: 0;
    }

    .hero-lead {
      max-width: 760px;
      margin: 14px 0 0;
      font-size: clamp(1rem, 2vw, 1.18rem);
    }

    .overview-panel {
      display: grid;
      gap: 10px;
      padding: 18px;
      border: 1px solid rgba(255, 255, 255, 0.34);
      border-radius: 8px;
      background: rgba(7, 30, 37, 0.42);
      color: #fff;
    }

    .overview-panel dl {
      display: grid;
      gap: 8px;
      margin: 0;
    }

    .overview-panel dl > div {
      display: grid;
      grid-template-columns: 88px minmax(0, 1fr);
      gap: 10px;
      align-items: baseline;
    }

    .overview-panel dt {
      color: rgba(255, 255, 255, 0.72);
      font-size: 0.86rem;
      font-weight: 900;
    }

    .overview-panel dd {
      margin: 0;
      font-weight: 800;
    }

    .hero-links {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 4px;
    }

    .hero-links a {
      color: #fff;
      border-color: rgba(255, 255, 255, 0.44);
      background: rgba(255, 255, 255, 0.14);
    }

    main {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 34px 0 72px;
    }

    .section-kicker {
      margin: 0 0 5px;
      color: var(--lake);
      font-size: 0.84rem;
      font-weight: 900;
      letter-spacing: 0;
    }

    .section-title {
      margin: 0;
      color: var(--navy);
      font-size: clamp(1.45rem, 3vw, 2.25rem);
      line-height: 1.2;
      letter-spacing: 0;
    }

    .lead {
      max-width: 860px;
      margin: 10px 0 0;
      color: var(--muted);
    }

    .day-nav-wrap {
      position: sticky;
      top: 53px;
      z-index: 8;
      margin: 24px 0 28px;
      padding: 10px 0;
      background: linear-gradient(180deg, var(--paper) 0%, rgba(250, 247, 239, 0.9) 78%, rgba(250, 247, 239, 0) 100%);
    }

    .day-nav {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      padding-bottom: 5px;
      scrollbar-width: thin;
    }

    .day-nav a {
      flex: 0 0 auto;
      min-width: 90px;
      padding: 8px 10px;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--navy);
      text-decoration: none;
    }

    .day-nav strong,
    .day-nav span {
      display: block;
      white-space: nowrap;
    }

    .day-nav strong {
      color: var(--lake);
      font-size: 0.78rem;
    }

    .day-nav span {
      font-size: 0.9rem;
      font-weight: 900;
    }

    .days {
      display: grid;
      gap: 18px;
      margin-top: 18px;
    }

    .day-card {
      scroll-margin-top: 120px;
      overflow: clip;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
      box-shadow: var(--shadow);
    }

    .day-card.is-current {
      border-color: rgba(23, 111, 130, 0.75);
      box-shadow: 0 0 0 3px rgba(23, 111, 130, 0.16), var(--shadow);
    }

    .day-summary {
      display: grid;
      grid-template-columns: minmax(230px, 34%) minmax(0, 1fr);
      gap: clamp(16px, 3vw, 26px);
      padding: clamp(16px, 3vw, 26px);
    }

    .hero-photo {
      min-height: 245px;
      margin: 0;
      border-radius: 8px;
      overflow: hidden;
      background: var(--mist);
      position: relative;
    }

    .hero-photo img {
      width: 100%;
      height: 100%;
      min-height: 245px;
      object-fit: cover;
      display: block;
    }

    .hero-photo figcaption {
      position: absolute;
      left: 10px;
      bottom: 10px;
      max-width: calc(100% - 20px);
      padding: 4px 8px;
      border-radius: 4px;
      background: rgba(18, 56, 70, 0.74);
      color: #fff;
      font-size: 0.84rem;
      font-weight: 800;
    }

    .quiet-placeholder {
      min-height: 190px;
      display: grid;
      place-items: center;
      padding: 18px;
      color: var(--lake);
      text-align: center;
      font-weight: 900;
    }

    .day-label {
      margin: 0 0 7px;
      color: var(--lake);
      font-size: 0.86rem;
      font-weight: 900;
    }

    .summary-copy h3 {
      margin: 0;
      color: var(--navy);
      font-size: clamp(1.35rem, 3vw, 2.15rem);
      line-height: 1.22;
      letter-spacing: 0;
    }

    .route-copy {
      margin: 9px 0 0;
      color: var(--muted);
      font-weight: 800;
    }

    .summary-route {
      margin-top: 14px;
      padding: 12px;
      border: 1px solid rgba(23, 111, 130, 0.18);
      border-radius: 8px;
      background: #f5fbfa;
    }

    .summary-route p,
    .highlights p {
      margin: 0 0 7px;
      color: var(--lake);
      font-size: 0.78rem;
      font-weight: 900;
      letter-spacing: 0;
    }

    .summary-route ol {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .summary-route li {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      min-width: 0;
      color: var(--navy);
      font-weight: 900;
    }

    .summary-route li strong {
      overflow-wrap: anywhere;
    }

    .summary-route em {
      padding: 1px 6px;
      border-radius: 4px;
      background: #f1e5cf;
      color: #7c531e;
      font-size: 0.72rem;
      font-style: normal;
    }

    .route-arrow {
      color: var(--forest);
      font-weight: 900;
    }

    .mobile-arrow { display: none; }

    .route-time {
      color: var(--muted);
      font-size: 0.72rem;
      font-weight: 800;
    }

    .summary-chips {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 8px;
      margin: 14px 0 0;
    }

    .summary-chips div {
      min-width: 0;
      padding: 8px 9px;
      border: 1px solid rgba(215, 226, 228, 0.9);
      border-radius: 6px;
      background: #fff;
    }

    .summary-chips dt {
      color: var(--muted);
      font-size: 0.75rem;
      font-weight: 900;
    }

    .summary-chips dd {
      margin: 1px 0 0;
      color: var(--ink);
      font-size: 0.94rem;
      font-weight: 900;
      overflow-wrap: anywhere;
    }

    .highlights {
      margin-top: 14px;
    }

    .highlights ul {
      display: flex;
      flex-wrap: wrap;
      gap: 7px;
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .highlights li {
      padding: 4px 8px;
      border-radius: 6px;
      background: #eef6ee;
      color: var(--forest);
      font-weight: 900;
      font-size: 0.9rem;
    }

    .day-detail {
      border-top: 1px solid var(--line);
    }

    .day-detail > summary {
      cursor: pointer;
      padding: 13px clamp(16px, 3vw, 26px);
      color: var(--navy);
      font-weight: 900;
      list-style-position: inside;
    }

    .day-detail[open] > summary {
      border-bottom: 1px solid var(--line);
      background: #fbf9f3;
    }

    .day-detail-body {
      display: grid;
      gap: 14px;
      padding: clamp(16px, 3vw, 26px);
    }

    .theme-card,
    .route-card,
    .inner-detail {
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fffdf8;
    }

    .theme-card {
      padding: 16px;
    }

    .theme-card h4,
    .card-title-row h4 {
      margin: 0 0 8px;
      color: var(--lake);
      font-family: Georgia, "Times New Roman", serif;
      font-size: 1.16rem;
    }

    .theme-card p {
      margin: 0;
      color: var(--ink);
    }

    .route-card {
      padding: 16px;
    }

    .card-title-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 12px;
    }

    .card-title-row h4 { margin: 0; }

    .card-title-row a,
    .restaurant-card a,
    .side-trip-card a {
      flex: 0 0 auto;
      border-radius: 6px;
      padding: 4px 9px;
      background: var(--lake);
      color: #fff;
      font-size: 0.78rem;
      font-weight: 900;
      text-decoration: none;
    }

    .route-card-body {
      display: grid;
      grid-template-columns: minmax(280px, 1.1fr) minmax(210px, 0.9fr);
      gap: 16px;
      align-items: stretch;
    }

    .sketch-map {
      min-height: 240px;
      overflow: hidden;
      border-radius: 8px;
      border: 1px solid rgba(23, 111, 130, 0.18);
      background: #d9ebef;
    }

    .sketch-map img {
      display: block;
      width: 100%;
      height: 100%;
      min-height: 240px;
      object-fit: cover;
    }

    .route-map {
      margin: 0;
      padding: 0;
      list-style: none;
    }

    .route-point {
      position: relative;
      display: grid;
      gap: 4px;
      padding-left: 26px;
    }

    .route-point::before {
      content: "";
      position: absolute;
      left: 4px;
      top: 0.48em;
      width: 12px;
      height: 12px;
      border: 3px solid var(--lake);
      border-radius: 50%;
      background: var(--surface);
      box-shadow: 0 0 0 4px #e8f3f4;
    }

    .route-point > span {
      width: fit-content;
      padding: 1px 8px;
      border-radius: 4px;
      color: #fff;
      background: var(--sun);
      font-size: 0.75rem;
      font-weight: 900;
    }

    .route-leg {
      min-height: 20px;
      display: grid;
      grid-template-columns: 2px minmax(0, 1fr);
      gap: 12px;
      margin: 3px 0 4px 9px;
      color: var(--muted);
      font-size: 0.78rem;
      font-weight: 800;
    }

    .route-leg i {
      display: block;
      width: 2px;
      min-height: 100%;
      background: repeating-linear-gradient(to bottom, var(--lake), var(--lake) 5px, transparent 5px, transparent 10px);
    }

    .inner-detail {
      overflow: hidden;
    }

    .inner-detail > summary {
      cursor: pointer;
      padding: 12px 14px;
      color: var(--navy);
      font-weight: 900;
      list-style-position: inside;
    }

    .inner-detail[open] > summary {
      border-bottom: 1px solid var(--line);
      background: #f8fbf8;
    }

    .timeline {
      display: grid;
      gap: 0;
      margin: 0;
      padding: 12px 14px;
      list-style: none;
    }

    .timeline li {
      display: grid;
      grid-template-columns: 78px 62px minmax(0, 1fr);
      gap: 12px;
      padding: 11px 0;
      border-top: 1px solid var(--line);
    }

    .timeline li:first-child {
      border-top: 0;
      padding-top: 0;
    }

    .timeline time {
      color: var(--ink);
      font-weight: 900;
      overflow-wrap: anywhere;
    }

    .tag {
      align-self: start;
      min-width: 52px;
      padding: 2px 7px;
      border-radius: 6px;
      text-align: center;
      color: #fff;
      font-size: 0.78rem;
      font-weight: 800;
    }

    .move { background: #3e7fa8; }
    .see { background: var(--forest); }
    .food { background: var(--sun); }
    .rest { background: var(--lake); }
    .prep { background: var(--berry); }
    .other { background: var(--muted); }

    .timeline strong {
      display: block;
      color: var(--navy);
    }

    .timeline p {
      margin: 3px 0;
      color: var(--muted);
    }

    .timeline small {
      color: var(--lake);
      font-weight: 900;
    }

    .restaurant-grid,
    .photo-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      padding: 12px 14px;
    }

    .restaurant-card {
      display: grid;
      gap: 5px;
      padding: 12px;
      border: 1px solid rgba(215, 226, 228, 0.9);
      border-radius: 8px;
      background: #fff;
    }

    .restaurant-card p,
    .restaurant-card h5,
    .restaurant-card span {
      margin: 0;
    }

    .restaurant-card p {
      color: var(--berry);
      font-size: 0.8rem;
      font-weight: 900;
    }

    .restaurant-card h5 {
      color: var(--navy);
      font-size: 1rem;
      line-height: 1.35;
    }

    .restaurant-card span {
      color: var(--muted);
      font-size: 0.92rem;
    }

    .restaurant-card a {
      justify-self: start;
      margin-top: 3px;
    }

    .side-trip-card {
      margin: 0 14px 14px;
      padding: 12px;
      border: 1px solid rgba(23, 111, 130, 0.16);
      border-radius: 8px;
      background: #f7f1e7;
    }

    .side-trip-card h4 {
      margin: 0 0 8px;
      color: var(--lake);
    }

    .side-trip-card figure,
    .photo-grid figure {
      margin: 0;
      overflow: hidden;
      border-radius: 8px;
      background: #fff;
    }

    .side-trip-card img,
    .photo-grid img {
      display: block;
      width: 100%;
      aspect-ratio: 16 / 9;
      object-fit: cover;
    }

    .side-trip-card figcaption,
    .photo-grid figcaption {
      display: grid;
      gap: 4px;
      padding: 10px;
    }

    .side-trip-card figcaption span,
    .photo-grid figcaption span,
    .photo-grid small {
      color: var(--muted);
      font-size: 0.88rem;
      line-height: 1.5;
    }

    .spot-meta {
      display: grid;
      gap: 3px;
      margin: 0 0 5px;
    }

    .spot-meta div {
      display: grid;
      grid-template-columns: 72px minmax(0, 1fr);
      gap: 8px;
    }

    .spot-meta dt {
      color: var(--lake);
      font-weight: 900;
    }

    .spot-meta dd {
      margin: 0;
    }

    .spot-placeholder {
      width: 100%;
      aspect-ratio: 16 / 9;
      background: linear-gradient(135deg, #e7f2f2, #f7f1e7);
    }

    .note-detail ul {
      margin: 0;
      padding: 12px 14px 12px 2em;
      color: var(--ink);
    }

    .note-detail li + li { margin-top: 6px; }

    .empty {
      margin: 0;
      padding: 12px 14px;
      color: var(--muted);
    }

    footer {
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
      padding: 26px 0 44px;
      color: var(--muted);
      font-size: 0.92rem;
    }

    @media (max-width: 920px) {
      .hero-grid,
      .day-summary,
      .route-card-body {
        grid-template-columns: 1fr;
      }

      .hero {
        min-height: auto;
      }

      .overview-panel {
        background: rgba(7, 30, 37, 0.5);
      }
    }

    @media (max-width: 680px) {
      body {
        font-size: 16px;
      }

      .top-nav {
        gap: 8px;
      }

      .brand {
        max-width: 7em;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .top-nav a:not(.brand) {
        padding: 6px 8px;
        font-size: 0.82rem;
      }

      .hero {
        padding: 34px 16px 24px;
      }

      .hero-grid {
        gap: 18px;
      }

      .overview-panel dl > div {
        grid-template-columns: 78px minmax(0, 1fr);
      }

      main {
        width: min(100% - 20px, 1180px);
        padding-top: 24px;
      }

      .day-nav-wrap {
        top: 49px;
        margin-top: 18px;
      }

      .day-summary {
        padding: 14px;
      }

      .hero-photo,
      .hero-photo img {
        min-height: 172px;
      }

      .summary-route ol {
        display: grid;
        gap: 4px;
      }

      .summary-route li {
        display: grid;
        grid-template-columns: minmax(0, 1fr);
        gap: 2px;
      }

      .desktop-arrow { display: none; }
      .mobile-arrow { display: inline; }

      .summary-route .route-time {
        display: none;
      }

      .restaurant-grid,
      .photo-grid {
        grid-template-columns: 1fr;
      }

      .summary-chips {
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }

      .day-detail > summary {
        padding: 12px 14px;
      }

      .day-detail-body {
        padding: 14px;
      }

      .timeline {
        padding: 10px 12px;
      }

      .timeline li {
        grid-template-columns: 68px minmax(0, 1fr);
        gap: 8px;
      }

      .timeline .tag {
        justify-self: start;
      }

      .timeline li > div {
        grid-column: 1 / -1;
      }
    }

    @media (prefers-reduced-motion: reduce) {
      html { scroll-behavior: auto; }
    }
    """
    script = """
    (function () {
      var cards = Array.from(document.querySelectorAll(".day-card[data-date]"));
      if (!cards.length) return;
      var today = new Date();
      var iso = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0") + "-" + String(today.getDate()).padStart(2, "0");
      var target = cards.find(function (card) { return card.dataset.date === iso; }) || cards[0];
      target.classList.add("is-current");
      var link = document.getElementById("today-link");
      if (link) link.setAttribute("href", "#" + target.id);
    }());
    """

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>北海道家族旅行ガイド 2026</title>
  <style>
{style}
  </style>
</head>
<body>
  <a class="skip-link" href="#days">日別一覧へ移動</a>
  <nav class="top-nav" aria-label="ページ内ナビゲーション">
    <a class="brand" href="#overview">北海道ガイド</a>
    <div class="nav-links">
      <a href="#overview">概要</a>
      <a href="#days">DAY一覧</a>
      <a id="today-link" href="#day-{esc(days[0].date)}">今日</a>
      <a href="{esc(PDF_URL)}">PDF</a>
      <a href="{esc(PPTX_URL)}">PowerPoint</a>
    </div>
  </nav>

  <header class="hero" id="overview">
    <div class="hero-grid">
      <div>
        <p class="eyebrow">HOKKAIDO FAMILY TRAVEL GUIDE</p>
        <h1>北海道家族旅行ガイド 2026</h1>
        <p class="hero-lead">フェリーで北の大地へ。湖畔、花畑、峡谷、知床の森をめぐる13日間を、旅の前にも旅の途中にも読みやすくまとめました。</p>
      </div>
      <aside class="overview-panel" aria-label="旅行全体サマリ">
        <dl>
          <div><dt>期間</dt><dd>2026年7月31日 - 8月12日 / 13日間</dd></div>
          <div><dt>ルート</dt><dd>印西 → 仙台港 → 苫小牧 → 道央 → 道東 → 苫小牧 → 仙台 → 印西</dd></div>
          <div><dt>宿泊地</dt><dd>フェリー → 洞爺湖 → 札幌 → 層雲峡 → 中標津 → 帯広 → フェリー</dd></div>
        </dl>
        <div class="hero-links" aria-label="成果物リンク">
          <a id="hero-today-link" href="#day-{esc(days[0].date)}" onclick="document.getElementById('today-link')?.click(); return false;">今日の予定を見る</a>
          <a href="#days">全日程を見る</a>
          <a href="{esc(PDF_URL)}">PDF</a>
          <a href="{esc(PPTX_URL)}">PowerPoint</a>
          <a href="{esc(GITHUB_URL)}">GitHub</a>
        </div>
      </aside>
    </div>
  </header>

  <main>
    <section aria-labelledby="summary-title">
      <p class="section-kicker">TRIP SUMMARY</p>
      <h2 class="section-title" id="summary-title">まず全体像をつかむ</h2>
      <p class="lead">日別カードは、出発・到着、主なルート、食事エリア、ハイライトだけを先に確認できます。詳しい時刻表や写真、メモは必要な日だけ開いて見られます。</p>
    </section>

    <section class="day-nav-wrap" aria-label="日付を選ぶ">
      <nav class="day-nav" aria-label="日別リンク">
        {nav_items}
      </nav>
    </section>

    <section id="days">
      <p class="section-kicker">DAY BY DAY</p>
      <h2 class="section-title">日別サマリ一覧</h2>
      {day_sections}
    </section>
  </main>

  <footer>
    <p>北海道家族旅行ガイド 2026 / inzaikun/hokkaido-trip-plan</p>
  </footer>
  <script>{script}</script>
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
