from __future__ import annotations

import json
import re
from pathlib import Path

from guidebook_common import guide_spots, meal_recommendations, route_points, today_theme, todays_tips


ROOT = Path(__file__).resolve().parents[1]
ITINERARY_DIR = ROOT / "itinerary" / "days"
OUT = ROOT / "web" / "app" / "itinerary-data.ts"


def clean_cell(value: str) -> str:
    return value.strip().replace("<br>", "\n")


def parse_table(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [clean_cell(c) for c in line.strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} for c in cells):
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


def parse_day(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    for line in raw.splitlines()[1:20]:
        if not line.strip():
            continue
        if line.startswith("## "):
            break
        if ":" in line:
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()

    timeline_rows = parse_table(section(raw, "Timeline").splitlines())
    restaurants_rows = parse_table(section(raw, "Restaurants").splitlines())
    photo_rows = parse_table(section(raw, "Photos").splitlines())
    notes = [
        line.strip()[2:].strip()
        for line in section(raw, "Notes").splitlines()
        if line.strip().startswith("- ")
    ]

    day = {
        "date": meta.get("date", path.stem),
        "day": meta.get("day", ""),
        "title": meta.get("title", path.stem),
        "area": meta.get("area", ""),
        "hero": meta.get("hero", meta.get("title", path.stem)),
        "summary": section(raw, "Summary").replace("\n", " ").strip(),
        "timeline": [
            {
                "time": row[0],
                "type": row[1],
                "place": row[2],
                "detail": row[3],
                "duration": row[4],
            }
            for row in timeline_rows[1:]
            if len(row) >= 5
        ],
        "photos": [
            {
                "place": row[0],
                "image": row[1],
                "caption": row[2],
                "credit": row[3],
            }
            for row in photo_rows[1:]
            if len(row) >= 4
        ],
        "restaurants": [
            {
                "meal": row[0],
                "name": row[1],
                "area": row[2],
                "memo": row[3],
            }
            for row in restaurants_rows[1:]
            if len(row) >= 4
        ],
        "notes": notes,
    }
    day["route"] = route_points(day)
    day["todayTheme"] = today_theme(day)
    day["mealRecommendations"] = meal_recommendations(day)
    day["todaysTips"] = todays_tips(day)
    day["guideSpots"] = guide_spots(day)
    return day


def main() -> None:
    days = [parse_day(path) for path in sorted(ITINERARY_DIR.glob("*.md"))]
    payload = {
        "title": "北海道家族旅行ガイド",
        "period": "2026年7月31日 - 8月12日",
        "updated": "旅のしおり最新版",
        "days": days,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        "export const itinerary = "
        + json.dumps(payload, ensure_ascii=False, indent=2)
        + " as const;\n",
        encoding="utf-8",
    )
    print(f"Generated {OUT}")


if __name__ == "__main__":
    main()
