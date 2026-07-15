from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from urllib.parse import quote

from guidebook_common import hero_photo, route_points, short_text, todays_tips


ROOT = Path(__file__).resolve().parents[1]
ITINERARY_DIR = ROOT / "itinerary" / "days"
OUT = ROOT / "docs" / "index.html"
RAW_IMAGE_BASE = "https://raw.githubusercontent.com/inzaikun/hokkaido-trip-plan/main/images/"
COVER_IMAGE_NAME = "cover.png"
WEEKDAYS = ["月", "火", "水", "木", "金", "土", "日"]
FERRY_DATES = {"2026-07-31", "2026-08-11", "2026-08-12"}
ROUTE_SKIP_WORDS = (
    "SA",
    "PA",
    "候補",
    "船内",
    "客室",
    "朝食",
    "昼食",
    "夕食",
    "休憩",
    "知床自然センター",
    "フレペの滝",
    "オシンコシンの滝",
)


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


def clean_place(value: str) -> str:
    value = re.sub(r"\s+", " ", value).strip()
    value = value.replace("へ帰着", "")
    value = value.split("/", 1)[0].strip()
    value = value.replace("方面", "").strip()
    return value


def route_return_place(day: Day) -> str:
    for item in day.timeline:
        text = f"{item.place} {item.detail}"
        if any(word in text for word in ("帰着", "帰宅", "自宅到着")):
            return clean_place(item.place)
    return ""


def area_short(day: Day) -> str:
    parts = [part.strip() for part in re.split(r"[/／]", day.area) if part.strip()]
    if len(parts) <= 2:
        return " / ".join(parts)
    return f"{parts[0]} / {parts[-1]}"


def departure_item(day: Day) -> TimelineItem | None:
    for item in day.timeline:
        if item.kind == "移動":
            return item
    return day.timeline[0] if day.timeline else None


def arrival_item(day: Day) -> TimelineItem | None:
    for item in reversed(day.timeline):
        text = f"{item.place} {item.detail}"
        if any(word in text for word in ("帰着", "到着", "帰宅", "自宅到着")):
            return item
    for item in day.timeline:
        if item.kind == "移動" and "出港" in item.detail:
            return item
    for item in reversed(day.timeline):
        if item.kind in {"移動", "手続き"}:
            return item
    return day.timeline[-1] if day.timeline else None


def arrival_label(item: TimelineItem | None) -> str:
    if not item:
        return "到着"
    text = f"{item.place} {item.detail}"
    if "帰着" in text:
        return "帰着"
    if "帰宅" in text or "自宅到着" in text:
        return "帰宅"
    if "出港" in text:
        return "出港"
    return "到着"


def time_pair(day: Day) -> tuple[str, str, str]:
    start = departure_item(day)
    end = arrival_item(day)
    return (
        start.time if start else "-",
        end.time if end else "-",
        arrival_label(end),
    )


def highlights(day: Day, limit: int = 2) -> list[str]:
    results: list[str] = []

    def add(place: str) -> None:
        place = clean_place(place)
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
    return results[:limit]


def route_names(day: Day) -> list[str]:
    names: list[str] = []
    for point in route_points(day, max_points=8):
        place = clean_place(point["place"])
        if any(word in place for word in ROUTE_SKIP_WORDS):
            continue
        if place and place not in names:
            names.append(place)
    return_place = route_return_place(day)
    if return_place:
        if names and names[0] == return_place:
            if names[-1] != return_place:
                names.append(return_place)
        else:
            names = [name for name in names if name != return_place]
            names.append(return_place)
    if len(names) <= 5:
        return names
    first, last = names[0], names[-1]
    middle = names[1:-1]
    group_one = "・".join(middle[:2])
    group_two = "・".join(middle[2:4])
    route = [first, group_one, group_two, last]
    return [part for part in route if part]


def render_route(day: Day) -> str:
    names = route_names(day)
    if not names:
        return ""
    parts = []
    for index, name in enumerate(names):
        parts.append(f"<span>{esc(name)}</span>")
        if index < len(names) - 1:
            parts.append('<i aria-hidden="true">→</i>')
    return '<div class="route-flow" aria-label="今日のルート">' + "".join(parts) + "</div>"


def render_main_photo(day: Day) -> str:
    photo = hero_photo(day)
    if not photo:
        return ""
    return (
        '<figure class="main-photo">'
        f'<img src="{image_src(photo.image)}" alt="{esc(photo.place)}" loading="lazy">'
        f"<figcaption>{esc(photo.place)}</figcaption>"
        "</figure>"
    )


def meal_summary(day: Day, meal: str) -> str:
    timeline_item = next((item for item in day.timeline if meal in item.kind), None)
    restaurant = next((item for item in day.restaurants if meal in item.meal), None)
    if timeline_item:
        place = clean_place(timeline_item.place)
        detail = timeline_item.detail
        if "海鮮" in detail:
            return f"{place}で海鮮"
        if "豚丼" in detail:
            return f"{place}で豚丼"
        if "牛たん" in detail:
            return f"{place}で牛たん"
        return place or short_text(detail, 24)
    if restaurant:
        return restaurant.area or restaurant.name
    return "当日決定"


def restaurant_groups(day: Day) -> list[Restaurant]:
    results: list[Restaurant] = []
    for meal in ("昼食", "夕食"):
        count = 0
        for restaurant in day.restaurants:
            if meal in restaurant.meal:
                results.append(restaurant)
                count += 1
            if count >= 2:
                break
    return results


def render_restaurants(day: Day) -> str:
    restaurants = restaurant_groups(day)
    if not restaurants:
        return '<p class="empty">食事候補は当日選びます。</p>'
    return (
        '<div class="restaurant-list">'
        + "".join(
            '<article class="restaurant-item">'
            f"<p>{esc(item.meal)} / {esc(item.area)}</p>"
            f"<strong>{esc(item.name)}</strong>"
            f"<span>{esc(short_text(item.memo, 42))}</span>"
            "</article>"
            for item in restaurants
        )
        + "</div>"
    )


def render_timeline(day: Day) -> str:
    items = []
    for item in day.timeline:
        items.append(
            "<li>"
            f"<time>{esc(item.time)}</time>"
            f'<span class="tag {kind_class(item.kind)}">{esc(item.kind)}</span>'
            "<div>"
            f"<strong>{esc(item.place)}</strong>"
            f"<p>{esc(short_text(item.detail, 42))}</p>"
            f"<small>{esc(item.duration)}</small>"
            "</div>"
            "</li>"
        )
    return '<ol class="timeline">' + "".join(items) + "</ol>"


def notes_for(day: Day) -> list[str]:
    tips = []
    for note in day.notes:
        if note not in tips:
            tips.append(note)
    for tip in todays_tips(day):
        if tip not in tips:
            tips.append(tip)
    return tips[:3]


def render_notes(day: Day) -> str:
    notes = notes_for(day)
    if not notes:
        return '<p class="empty">天候と体調に合わせて無理せず調整します。</p>'
    return "<ul>" + "".join(f"<li>{esc(short_text(note, 62))}</li>" for note in notes) + "</ul>"


def is_ferry_day(day: Day) -> bool:
    return day.date in FERRY_DATES


def render_ferry_teaser(day: Day) -> str:
    if not is_ferry_day(day):
        return ""
    return """
      <section class="ferry-guide" aria-label="太平洋フェリー きたかみ">
        <p class="section-mini">船旅ガイド</p>
        <h4>太平洋フェリー きたかみ</h4>
        <p>2019年就航。白を基調にした船内で、夜は光の演出も楽しめます。</p>
        <div class="ferry-columns">
          <div>
            <strong>船内で楽しめること</strong>
            <ul><li>展望大浴場</li><li>キッズエリア</li><li>プロジェクションマッピング</li></ul>
          </div>
          <div>
            <strong>あると便利</strong>
            <ul><li>コインランドリー</li><li>エレベーター</li><li>授乳室</li></ul>
          </div>
        </div>
        <small>出典: 太平洋フェリー公式・きたかみ</small>
      </section>
    """


def render_ferry_detail(day: Day) -> str:
    if not is_ferry_day(day):
        return render_notes(day)
    return (
        '<div class="ferry-detail">'
        "<h4>船内設備を見る</h4>"
        "<p>バイキングレストラン「グリーンプラネット」、展望通路、展望大浴場、キッズエリア、コインランドリー、授乳室、エレベーター2基を覚えておけば十分です。</p>"
        "<h4>注意点</h4>"
        + render_notes(day)
        + "<small>出典: 太平洋フェリー公式・きたかみ</small>"
        "</div>"
    )


def render_foldout(title: str, body: str, open_attr: bool = False) -> str:
    opened = " open" if open_attr else ""
    return f'<details class="foldout"{opened}><summary>{esc(title)}</summary>{body}</details>'


def short_day_title(day: Day) -> str:
    title = day.title
    replacements = {
        "知床五湖と知床峠を巡る世界自然遺産デー": "知床の大自然を巡る日",
        "印西から仙台観光、フェリーで北海道へ": "仙台観光とフェリーの日",
        "仙台港到着、そのまま印西へ帰宅": "仙台港から印西へ帰る日",
    }
    return replacements.get(title, short_text(title, 24))


def render_day_card(day: Day) -> str:
    start, end, end_label = time_pair(day)
    day_highlights = highlights(day)
    return f"""
      <article class="day-card" id="day-{esc(day.date)}" data-date="{esc(day.date)}">
        <div class="day-card-top">
          <p>DAY {esc(day.day)}</p>
          <span>{formatted_date(day.date)}</span>
        </div>
        <h3>{esc(short_day_title(day))}</h3>
        <p class="area-line">{esc(area_short(day))}</p>
        <dl class="time-mini">
          <div><dt>出発</dt><dd>{esc(start)}</dd></div>
          <div><dt>{esc(end_label)}</dt><dd>{esc(end)}</dd></div>
        </dl>
        <ul class="highlight-mini">
          {"".join(f"<li>{esc(item)}</li>" for item in day_highlights)}
        </ul>
        <a class="select-day" href="#detail-{esc(day.date)}" data-select-day="{esc(day.date)}">この日を見る</a>
      </article>
    """


def render_day_detail(day: Day, is_default: bool = False) -> str:
    start, end, end_label = time_pair(day)
    hidden = "" if is_default else " hidden"
    return f"""
      <article class="day-panel" id="detail-{esc(day.date)}" data-day-panel="{esc(day.date)}"{hidden}>
        <div class="panel-heading">
          <p>DAY {esc(day.day)} / {formatted_date(day.date)}</p>
          <h2>{esc(day.title)}</h2>
        </div>
        {render_main_photo(day)}
        <div class="priority-grid">
          <div><span>出発</span><strong>{esc(start)}</strong></div>
          <div><span>{esc(end_label)}</span><strong>{esc(end)}</strong></div>
        </div>
        <section class="simple-section">
          <h3>今日のルート</h3>
          {render_route(day)}
        </section>
        <section class="simple-section">
          <h3>今日の予定</h3>
          <p>{esc(short_text(day.summary, 80))}</p>
        </section>
        <div class="meal-summary">
          <section><h3>昼食</h3><p>{esc(meal_summary(day, "昼食"))}</p></section>
          <section><h3>夕食</h3><p>{esc(meal_summary(day, "夕食"))}</p></section>
        </div>
        {render_ferry_teaser(day)}
        <div class="foldouts">
          {render_foldout("詳しい時刻表", render_timeline(day))}
          {render_foldout("食事候補", render_restaurants(day))}
          {render_foldout("船内設備を見る" if is_ferry_day(day) else "注意点・雨天時", render_ferry_detail(day))}
        </div>
      </article>
    """


def render_page(days: list[Day]) -> str:
    day_cards = "\n".join(render_day_card(day) for day in days)
    day_panels = "\n".join(render_day_detail(day) for day in days)
    date_nav = "\n".join(
        f'<a href="#detail-{esc(day.date)}" data-select-day="{esc(day.date)}">{formatted_date(day.date).split("（", 1)[0]}</a>'
        for day in days
    )
    style = """
    :root {
      color-scheme: light;
      --ink: #14212a;
      --muted: #65737c;
      --line: #dce4e7;
      --paper: #f6f8f7;
      --surface: #ffffff;
      --blue: #123f57;
      --green: #39745b;
      --orange: #b8752a;
    }

    * { box-sizing: border-box; }

    html { scroll-behavior: smooth; }

    body {
      margin: 0;
      color: var(--ink);
      background: var(--paper);
      font-family: -apple-system, BlinkMacSystemFont, "Hiragino Sans", "Yu Gothic", "YuGothic", "Noto Sans JP", sans-serif;
      font-size: 16px;
      line-height: 1.6;
      overflow-x: hidden;
    }

    a { color: inherit; }

    img {
      display: block;
      max-width: 100%;
    }

    .app-nav {
      position: sticky;
      top: 0;
      z-index: 20;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      min-height: 54px;
      padding: 8px clamp(14px, 4vw, 40px);
      border-bottom: 1px solid var(--line);
      background: rgba(255, 255, 255, 0.94);
      backdrop-filter: blur(10px);
    }

    .app-nav strong {
      color: var(--blue);
      font-size: 0.98rem;
    }

    .app-nav div {
      display: flex;
      gap: 8px;
      overflow-x: auto;
      scrollbar-width: none;
    }

    .app-nav div::-webkit-scrollbar { display: none; }

    .nav-pill,
    .hero-actions a,
    .select-day {
      min-height: 44px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      padding: 9px 13px;
      border-radius: 6px;
      border: 1px solid var(--line);
      background: var(--surface);
      color: var(--blue);
      font-weight: 800;
      text-decoration: none;
      white-space: nowrap;
    }

    .hero {
      min-height: min(620px, 100svh);
      display: grid;
      align-items: end;
      padding: 72px clamp(18px, 5vw, 72px) 28px;
      background:
        linear-gradient(180deg, rgba(5, 25, 35, 0.04), rgba(5, 25, 35, 0.66)),
        url(\"""" + image_src(COVER_IMAGE_NAME) + """\") center/cover;
      color: #fff;
    }

    .hero-inner {
      width: min(760px, 100%);
    }

    .hero h1 {
      margin: 0;
      font-size: clamp(2rem, 8.6vw, 4.5rem);
      line-height: 1.02;
      letter-spacing: 0;
      overflow-wrap: anywhere;
    }

    .hero-date {
      margin: 12px 0 0;
      font-size: clamp(1.1rem, 4vw, 1.55rem);
      font-weight: 900;
    }

    .hero-route {
      margin: 6px 0 0;
      font-weight: 800;
    }

    .hero-note {
      max-width: 38em;
      margin: 12px 0 0;
    }

    .hero-actions {
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
      margin-top: 18px;
    }

    .hero-actions a {
      color: #fff;
      border-color: rgba(255, 255, 255, 0.42);
      background: rgba(255, 255, 255, 0.14);
    }

    main {
      width: min(1120px, calc(100% - 28px));
      margin: 0 auto;
      padding: 28px 0 64px;
    }

    .section-label {
      margin: 0 0 4px;
      color: var(--green);
      font-size: 0.82rem;
      font-weight: 900;
    }

    .section-title {
      margin: 0;
      color: var(--blue);
      font-size: clamp(1.45rem, 5vw, 2.2rem);
      line-height: 1.2;
    }

    .lead {
      max-width: 42em;
      margin: 8px 0 0;
      color: var(--muted);
    }

    .date-rail {
      position: sticky;
      top: 54px;
      z-index: 15;
      display: flex;
      gap: 8px;
      overflow-x: auto;
      margin: 20px 0 22px;
      padding: 8px 0;
      background: linear-gradient(180deg, var(--paper), rgba(246, 248, 247, 0.86));
      scrollbar-width: none;
    }

    .date-rail::-webkit-scrollbar { display: none; }

    .date-rail a {
      min-width: 64px;
      min-height: 44px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      border: 1px solid var(--line);
      border-radius: 6px;
      background: var(--surface);
      color: var(--blue);
      font-weight: 900;
      text-decoration: none;
    }

    .date-rail a.active,
    .day-card.active {
      border-color: rgba(57, 116, 91, 0.75);
      background: #f4faf6;
    }

    .day-list {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
      gap: 10px;
      margin-top: 14px;
    }

    .day-card {
      display: grid;
      gap: 8px;
      padding: 14px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }

    .day-card-top {
      display: flex;
      justify-content: space-between;
      gap: 10px;
      color: var(--green);
      font-size: 0.88rem;
      font-weight: 900;
    }

    .day-card-top p,
    .day-card h3,
    .area-line,
    .time-mini,
    .highlight-mini {
      margin: 0;
    }

    .day-card h3 {
      color: var(--blue);
      font-size: 1.08rem;
      line-height: 1.3;
    }

    .area-line {
      color: var(--muted);
      font-size: 0.92rem;
      font-weight: 700;
    }

    .time-mini {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 8px;
    }

    .time-mini div {
      padding: 8px;
      border-radius: 6px;
      background: #f6f8f7;
    }

    .time-mini dt {
      color: var(--muted);
      font-size: 0.75rem;
      font-weight: 900;
    }

    .time-mini dd {
      margin: 0;
      color: var(--ink);
      font-size: 1.05rem;
      font-weight: 900;
    }

    .highlight-mini {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      min-height: 28px;
      padding: 0;
      list-style: none;
    }

    .highlight-mini li {
      padding: 2px 7px;
      border-radius: 5px;
      background: #eef5f0;
      color: var(--green);
      font-size: 0.82rem;
      font-weight: 900;
    }

    .select-day {
      align-self: end;
      margin-top: 2px;
    }

    .selected-day {
      margin-top: 34px;
    }

    .day-panel {
      padding: clamp(16px, 4vw, 28px);
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--surface);
    }

    .panel-heading p {
      margin: 0 0 4px;
      color: var(--green);
      font-weight: 900;
    }

    .panel-heading h2 {
      margin: 0;
      color: var(--blue);
      font-size: clamp(1.6rem, 6vw, 2.45rem);
      line-height: 1.2;
    }

    .main-photo {
      position: relative;
      overflow: hidden;
      margin: 16px 0 0;
      border-radius: 8px;
      background: #eef2f3;
    }

    .main-photo img {
      width: 100%;
      max-height: 360px;
      object-fit: cover;
    }

    .main-photo figcaption {
      position: absolute;
      left: 10px;
      bottom: 10px;
      max-width: calc(100% - 20px);
      padding: 4px 8px;
      border-radius: 4px;
      background: rgba(18, 63, 87, 0.75);
      color: #fff;
      font-size: 0.84rem;
      font-weight: 800;
    }

    .priority-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
      margin-top: 16px;
    }

    .priority-grid div {
      padding: 12px;
      border-radius: 8px;
      background: #f3f7f5;
    }

    .priority-grid span {
      display: block;
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 900;
    }

    .priority-grid strong {
      display: block;
      color: var(--blue);
      font-size: 1.8rem;
      line-height: 1.1;
    }

    .simple-section,
    .meal-summary,
    .ferry-guide,
    .foldouts {
      margin-top: 18px;
    }

    .simple-section h3,
    .meal-summary h3,
    .ferry-guide h4 {
      margin: 0 0 6px;
      color: var(--blue);
      font-size: 1rem;
    }

    .simple-section p,
    .meal-summary p,
    .ferry-guide p {
      margin: 0;
      color: var(--ink);
    }

    .route-flow {
      display: flex;
      flex-wrap: wrap;
      gap: 6px 8px;
      align-items: center;
      color: var(--blue);
      font-weight: 900;
    }

    .route-flow span {
      max-width: 100%;
      overflow-wrap: anywhere;
    }

    .route-flow i {
      color: var(--green);
      font-style: normal;
    }

    .meal-summary {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }

    .meal-summary section {
      padding: 12px;
      border-radius: 8px;
      background: #f8f4ee;
    }

    .ferry-guide {
      padding: 14px;
      border: 1px solid #dce4e7;
      border-radius: 8px;
      background: #f7fbfc;
    }

    .section-mini {
      margin: 0 0 4px;
      color: var(--green);
      font-size: 0.8rem;
      font-weight: 900;
    }

    .ferry-columns {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
      margin-top: 10px;
    }

    .ferry-columns strong,
    .ferry-detail h4 {
      display: block;
      margin: 0 0 4px;
      color: var(--blue);
    }

    .ferry-columns ul,
    .ferry-detail ul {
      margin: 0;
      padding-left: 1.2em;
    }

    .ferry-guide small,
    .ferry-detail small {
      display: block;
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.78rem;
    }

    .foldouts {
      display: grid;
      gap: 10px;
    }

    .foldout {
      overflow: hidden;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }

    .foldout summary {
      min-height: 48px;
      cursor: pointer;
      padding: 12px 14px;
      color: var(--blue);
      font-weight: 900;
    }

    .timeline {
      display: grid;
      gap: 0;
      margin: 0;
      padding: 0 14px 12px;
      list-style: none;
    }

    .timeline li {
      display: grid;
      grid-template-columns: 68px 54px minmax(0, 1fr);
      gap: 9px;
      padding: 11px 0;
      border-top: 1px solid var(--line);
    }

    .timeline time {
      color: var(--ink);
      font-weight: 900;
    }

    .tag {
      align-self: start;
      padding: 2px 6px;
      border-radius: 5px;
      color: #fff;
      font-size: 0.76rem;
      font-weight: 900;
      text-align: center;
    }

    .move { background: #467d9d; }
    .see { background: var(--green); }
    .food { background: var(--orange); }
    .rest { background: var(--blue); }
    .prep { background: #8c5b62; }
    .other { background: var(--muted); }

    .timeline strong {
      display: block;
      color: var(--blue);
    }

    .timeline p,
    .timeline small {
      margin: 2px 0 0;
      color: var(--muted);
    }

    .restaurant-list {
      display: grid;
      gap: 8px;
      padding: 0 14px 14px;
    }

    .restaurant-item {
      padding: 10px 0;
      border-top: 1px solid var(--line);
    }

    .restaurant-item p,
    .restaurant-item span {
      margin: 0;
      color: var(--muted);
      font-size: 0.9rem;
    }

    .restaurant-item strong {
      display: block;
      color: var(--ink);
      font-size: 1rem;
    }

    .foldout > ul,
    .ferry-detail {
      margin: 0;
      padding: 0 14px 14px;
    }

    .foldout > ul {
      padding-left: 2em;
    }

    .foldout li + li {
      margin-top: 6px;
    }

    .empty {
      margin: 0;
      padding: 0 14px 14px;
      color: var(--muted);
    }

    footer {
      width: min(1120px, calc(100% - 28px));
      margin: 0 auto;
      padding: 24px 0 42px;
      color: var(--muted);
      font-size: 0.88rem;
    }

    @media (max-width: 760px) {
      .app-nav strong {
        max-width: 8em;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .hero {
        padding: 62px 18px 24px;
      }

      main {
        width: min(100% - 20px, 1120px);
        padding-top: 22px;
      }

      .day-list {
        grid-template-columns: 1fr;
      }

      .day-card {
        gap: 7px;
        padding: 13px;
      }

      .priority-grid,
      .meal-summary,
      .ferry-columns {
        grid-template-columns: 1fr;
      }

      .main-photo img {
        max-height: 240px;
      }

      .route-flow {
        display: grid;
        gap: 3px;
      }

      .route-flow i {
        transform: rotate(90deg);
        width: fit-content;
      }

      .timeline li {
        grid-template-columns: 64px minmax(0, 1fr);
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
      var cards = Array.from(document.querySelectorAll("[data-date]"));
      var selectedSection = document.querySelector("[data-selected-day-section]");
      var panels = Array.from(document.querySelectorAll("[data-day-panel]"));
      var links = Array.from(document.querySelectorAll("[data-select-day]"));
      var navLinks = Array.from(document.querySelectorAll(".date-rail a"));
      if (!panels.length) return;

      function tripTargetDate() {
        var today = new Date();
        var iso = today.getFullYear() + "-" + String(today.getMonth() + 1).padStart(2, "0") + "-" + String(today.getDate()).padStart(2, "0");
        return panels.some(function (panel) { return panel.dataset.dayPanel === iso; }) ? iso : panels[0].dataset.dayPanel;
      }

      function selectDay(day, shouldScroll) {
        panels.forEach(function (panel) {
          panel.hidden = panel.dataset.dayPanel !== day;
        });
        if (selectedSection) selectedSection.hidden = false;
        cards.forEach(function (card) {
          card.classList.toggle("active", card.dataset.date === day);
        });
        navLinks.forEach(function (link) {
          link.classList.toggle("active", link.dataset.selectDay === day);
        });
        var todayLink = document.getElementById("today-link");
        if (todayLink) todayLink.setAttribute("href", "#detail-" + day);
        if (shouldScroll) {
          var panel = document.querySelector('[data-day-panel="' + day + '"]');
          if (panel) panel.scrollIntoView({ behavior: shouldScroll === "smooth" ? "smooth" : "auto", block: "start" });
        }
      }

      function resetSelection() {
        panels.forEach(function (panel) { panel.hidden = true; });
        if (selectedSection) selectedSection.hidden = true;
        cards.forEach(function (card) { card.classList.remove("active"); });
        navLinks.forEach(function (link) { link.classList.remove("active"); });
      }

      var targetDate = tripTargetDate();
      links.forEach(function (link) {
        if (link.id === "today-link" || link.dataset.selectToday === "true") {
          link.dataset.selectDay = targetDate;
          link.setAttribute("href", "#detail-" + targetDate);
        }
      });

      links.forEach(function (link) {
        link.addEventListener("click", function (event) {
          event.preventDefault();
          selectDay(link.dataset.selectDay, "smooth");
          history.replaceState(null, "", "#detail-" + link.dataset.selectDay);
        });
      });

      var initial = location.hash.replace("#detail-", "");
      if (panels.some(function (panel) { return panel.dataset.dayPanel === initial; })) {
        selectDay(initial, "auto");
      } else {
        resetSelection();
      }
    }());
    """

    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>北海道 家族旅行 2026</title>
  <style>
{style}
  </style>
</head>
<body>
  <nav class="app-nav" aria-label="ページ内ナビゲーション">
    <strong>北海道 家族旅行</strong>
    <div>
      <a class="nav-pill" id="today-link" href="#detail-{esc(days[0].date)}" data-select-day="{esc(days[0].date)}">今日</a>
      <a class="nav-pill" href="#days">日程一覧</a>
    </div>
  </nav>

  <header class="hero" id="top">
    <div class="hero-inner">
      <h1>北海道 家族旅行<br>2026</h1>
      <p class="hero-date">7/31 - 8/12</p>
      <p class="hero-route">印西 → 仙台 → 北海道 → 苫小牧</p>
      <p class="hero-note">今日はどこへ行くか、何時に出るか、食事と注意点をすぐ見られる家族用ガイドです。</p>
      <div class="hero-actions">
        <a href="#detail-{esc(days[0].date)}" data-select-day="{esc(days[0].date)}" data-select-today="true">今日の予定を見る</a>
        <a href="#days">日程一覧</a>
      </div>
    </div>
  </header>

  <main>
    <section aria-labelledby="overview-title">
      <p class="section-label">旅の概要</p>
      <h2 class="section-title" id="overview-title">旅の流れ</h2>
      <p class="lead">仙台からフェリーで北海道へ渡り、洞爺湖、札幌、富良野・美瑛、層雲峡、道東、知床、帯広をめぐります。</p>
    </section>

    <nav class="date-rail" aria-label="日付を選ぶ">
      {date_nav}
    </nav>

    <section id="days" aria-labelledby="days-title">
      <p class="section-label">日程一覧</p>
      <h2 class="section-title" id="days-title">日別サマリ</h2>
      <div class="day-list">
        {day_cards}
      </div>
    </section>

    <section class="selected-day" aria-live="polite" aria-labelledby="selected-title" data-selected-day-section hidden>
      <p class="section-label">選択中の日程</p>
      <h2 class="section-title" id="selected-title">選択した日の詳細</h2>
      {day_panels}
    </section>
  </main>

  <footer>
    <p>家族で見返すための北海道旅行ガイド</p>
  </footer>
  <script>{script}</script>
</body>
</html>
"""


def normalize_output(text: str) -> str:
    return "\n".join(line.rstrip() for line in text.splitlines()) + "\n"


def main() -> None:
    days = [parse_day(path) for path in sorted(ITINERARY_DIR.glob("*.md"))]
    if not days:
        raise SystemExit("No itinerary day files found.")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(normalize_output(render_page(days)), encoding="utf-8")
    print(f"Generated {OUT} from {len(days)} day files")


if __name__ == "__main__":
    main()
