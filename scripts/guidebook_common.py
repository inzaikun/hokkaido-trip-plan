from __future__ import annotations

import re
from urllib.parse import quote_plus


MOVE_WORDS = ("移動",)
SKIP_ROUTE_KINDS = {"朝食", "準備"}


def value(obj, name: str, default=""):
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def clean_place(place: str) -> str:
    place = re.sub(r"\s+", " ", place).strip()
    if "へ帰着" in place:
        place = place.split("/", 1)[0].strip()
    place = place.replace("周辺", "").strip()
    place = place.replace("方面", "").strip()
    return place or "立ち寄り地"


def split_move(place: str) -> tuple[str, str] | None:
    if "→" not in place:
        return None
    start, end = [clean_place(part) for part in place.split("→", 1)]
    if not start or not end:
        return None
    return start, end


def compact_duration(duration: str, detail: str = "") -> str:
    duration = duration.strip()
    if duration and duration != "-":
        return duration
    match = re.search(r"(約?\d+時間(?:\d+分)?|約?\d+分)", detail)
    return match.group(1) if match else ""


def route_points(day, max_points: int = 9) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []

    def add(place: str, note: str = "", kind: str = "", leg: str = "") -> None:
        place = clean_place(place)
        if not place:
            return
        if "へ帰着" in place and points:
            base = place.split("へ帰着", 1)[0]
            if base and base in points[-1]["place"]:
                points[-1]["place"] = place
                points[-1]["kind"] = kind or points[-1].get("kind", "")
                return
        if points and points[-1]["place"] == place:
            if note and not points[-1].get("note"):
                points[-1]["note"] = note
            if kind in {"観光", "手続き"} or (kind and not points[-1].get("kind")):
                points[-1]["kind"] = kind
            return
        points.append({"place": place, "note": note, "kind": kind, "leg": leg})

    for item in value(day, "timeline", []):
        kind = value(item, "kind", value(item, "type", ""))
        place = value(item, "place", "")
        detail = value(item, "detail", "")
        duration = compact_duration(value(item, "duration", ""), detail)

        move = split_move(place)
        if kind in MOVE_WORDS and move:
            start, end = move
            add(start, kind=kind)
            if points:
                points[-1]["leg"] = duration
            add(end, kind=kind)
            continue

        if kind in SKIP_ROUTE_KINDS:
            continue
        if kind == "昼食":
            add(place, "昼食", kind)
        elif kind == "夕食" and len(points) < 5:
            add(place, "夕食", kind)
        elif kind in {"観光", "手続き"} or "帰着" in place:
            add(place, kind=kind)

    if len(points) <= max_points:
        return points

    area_parts = [clean_place(part) for part in re.split(r"[/／]", value(day, "area", "")) if part.strip()]
    important = []
    for index, point in enumerate(points):
        in_area = any(part and (part in point["place"] or point["place"] in part) for part in area_parts)
        keep = (
            index == 0
            or index == len(points) - 1
            or point.get("note")
            or point.get("kind") in {"観光", "手続き"}
            or in_area
            or "帰着" in point["place"]
        )
        if keep:
            important.append(point)
    if len(important) <= max_points:
        return important
    return important[: max_points - 1] + [important[-1]]


def today_theme(day) -> str:
    summary = re.sub(r"\s+", " ", value(day, "summary", "")).strip()
    title = value(day, "title", "")
    area = value(day, "area", "")
    if len(summary) < 100:
        summary = (
            f"{summary} {title}をテーマに、{area}の見どころを無理なく巡ります。"
            "移動、休憩、食事のリズムを整えながら、家族で写真を残したい景色を楽しむ一日です。"
        )
    if len(summary) > 150:
        clipped = summary[:150]
        last_period = clipped.rfind("。")
        last_comma = clipped.rfind("、")
        cut_at = last_period if last_period >= 90 else last_comma
        if cut_at >= 90:
            summary = clipped[:cut_at].rstrip("、。") + "。"
        else:
            summary = clipped[:147].rstrip("、。") + "。"
    return summary


def first_restaurant(day, meal_words: tuple[str, ...]):
    for restaurant in value(day, "restaurants", []):
        meal = value(restaurant, "meal", "")
        if any(word in meal for word in meal_words):
            return restaurant
    restaurants = value(day, "restaurants", [])
    return restaurants[0] if restaurants else None


def budget_for(restaurant, label: str) -> str:
    text = " ".join(
        [
            value(restaurant, "name", ""),
            value(restaurant, "area", ""),
            value(restaurant, "memo", ""),
            label,
        ]
    )
    if any(word in text for word in ("海鮮", "漁協", "港", "炉端")):
        return "目安 1,500〜3,000円"
    if any(word in text for word in ("牛たん", "豚丼", "焼肉", "串鳥")):
        return "目安 1,200〜2,800円"
    if any(word in text for word in ("カフェ", "軽食", "ソフト", "甘味")):
        return "目安 700〜1,500円"
    if any(word in text for word in ("キャンプ", "バンガロー", "コテージ", "簡単調理")):
        return "食材費中心"
    if "フェリー" in text or "船内" in text:
        return "目安 1,500〜3,000円"
    return "目安 1,000〜2,500円"


def popular_menu_for(restaurant) -> str:
    text = " ".join([value(restaurant, "name", ""), value(restaurant, "memo", "")])
    if "牛たん" in text:
        return "牛たん定食"
    if "豚丼" in text:
        return "豚丼"
    if "オムカレー" in text:
        return "富良野オムカレー"
    if "串鳥" in text or "焼鳥" in text:
        return "串焼き・焼鳥"
    if any(word in text for word in ("海鮮", "漁協", "港", "炉端")):
        return "海鮮丼・焼き魚"
    if any(word in text for word in ("カフェ", "ソフト", "甘味")):
        return "軽食・スイーツ"
    if any(word in text for word in ("キャンプ", "バンガロー", "コテージ", "簡単調理")):
        return "簡単キャンプ飯"
    if "フェリー" in text or "船内" in text:
        return "船内レストラン定食"
    return "現地の定番メニュー"


def meal_recommendations(day) -> list[dict[str, str]]:
    results = []
    for label, words in (("おすすめランチ", ("昼食", "ランチ")), ("おすすめ夕食", ("夕食",))):
        restaurant = first_restaurant(day, words)
        if not restaurant:
            continue
        results.append(
            {
                "label": label,
                "name": value(restaurant, "name", "候補未設定"),
                "area": value(restaurant, "area", ""),
                "memo": value(restaurant, "memo", ""),
                "stars": "★★★★★",
                "budget": budget_for(restaurant, label),
                "popular": popular_menu_for(restaurant),
            }
        )
    return results


def todays_tips(day, max_items: int = 5) -> list[str]:
    tips: list[str] = []

    def add(text: str) -> None:
        if text and text not in tips:
            tips.append(text)

    for note in value(day, "notes", []):
        add(note)
        if len(tips) >= max_items:
            return tips

    joined = " ".join(
        f"{value(item, 'place', '')} {value(item, 'detail', '')}"
        for item in value(day, "timeline", [])
    )
    if any(word in joined for word in ("給油", "長距離", "眠気")):
        add("長距離区間は早めの給油と休憩を入れると安心。")
    if "トイレ" in joined:
        add("トイレ休憩は道の駅やPAでこまめに確保。")
    if any(word in joined for word in ("鹿", "動物", "ヒグマ", "野生")):
        add("野生動物の飛び出しに注意して、夕方は速度を控えめに。")
    if any(word in joined for word in ("雨", "天候", "霧", "風")):
        add("雨や霧の日は展望系を短縮し、屋内休憩を増やす。")
    if any(word in joined for word in ("湖畔", "夕日", "花火", "展望")):
        add("夕方の光がきれいな場所は、短時間でも写真休憩を。")
    if "フェリー" in joined or "船内" in joined:
        add("船内バッグは先に分けて、乗船後に慌てない。")

    return tips[:max_items]


def map_url(place: str, area: str = "") -> str:
    query = f"{clean_place(place)} {area}".strip()
    return "https://www.google.com/maps/search/?api=1&query=" + quote_plus(query)


def stay_time_for(day, place: str) -> str:
    clean = clean_place(place)
    for item in value(day, "timeline", []):
        item_place = clean_place(value(item, "place", ""))
        if clean in item_place or item_place in clean:
            duration = value(item, "duration", "")
            return duration if duration and duration != "-" else "30〜60分"
    return "30〜60分"


def guide_spots(day, max_items: int = 4) -> list[dict[str, str]]:
    spots: list[dict[str, str]] = []
    for photo in value(day, "photos", []):
        place = value(photo, "place", "")
        spots.append(
            {
                "place": place,
                "image": value(photo, "image", ""),
                "caption": value(photo, "caption", ""),
                "credit": value(photo, "credit", ""),
                "parking": "周辺駐車場を現地確認",
                "stay": stay_time_for(day, place),
                "map_url": map_url(place, value(day, "area", "")),
            }
        )

    if not spots:
        for item in value(day, "timeline", []):
            kind = value(item, "kind", value(item, "type", ""))
            if kind != "観光":
                continue
            place = value(item, "place", "")
            spots.append(
                {
                    "place": place,
                    "image": "",
                    "caption": value(item, "detail", ""),
                    "credit": "写真準備中",
                    "parking": "駐車場・停車場所を現地確認",
                    "stay": value(item, "duration", "") or "30〜60分",
                    "map_url": map_url(place, value(day, "area", "")),
                }
            )
            if len(spots) >= max_items:
                break
    return spots[:max_items]
