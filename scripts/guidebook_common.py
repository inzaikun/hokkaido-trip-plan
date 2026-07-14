from __future__ import annotations

import math
import re
from urllib.parse import quote_plus


MOVE_WORDS = ("移動",)
SKIP_ROUTE_KINDS = {"朝食", "準備"}

PLACE_COORDS: dict[str, tuple[float, float]] = {
    "千葉県印西市": (35.832, 140.146),
    "仙台": (38.268, 140.869),
    "仙台市内": (38.268, 140.869),
    "仙台城跡": (38.252, 140.856),
    "瑞鳳殿": (38.250, 140.866),
    "仙台港": (38.267, 141.020),
    "仙台港フェリーターミナル": (38.267, 141.020),
    "中郷SA": (36.812, 140.735),
    "中郷SA / PA候補": (36.812, 140.735),
    "守谷SA": (35.964, 140.005),
    "守谷SA / PA候補": (35.964, 140.005),
    "苫小牧": (42.634, 141.605),
    "苫小牧市内": (42.634, 141.605),
    "苫小牧港": (42.637, 141.625),
    "船内": (42.637, 141.625),
    "洞爺湖": (42.568, 140.817),
    "洞爺湖湖畔": (42.568, 140.817),
    "洞爺湖温泉街": (42.565, 140.819),
    "洞爺湖汽船": (42.565, 140.819),
    "Green stay Toya": (42.591, 140.823),
    "キャンプ場": (42.591, 140.823),
    "有珠山": (42.543, 140.842),
    "有珠山ロープウェイ": (42.544, 140.858),
    "昭和新山": (42.543, 140.864),
    "サイロ展望台": (42.623, 140.802),
    "壮瞥": (42.552, 140.886),
    "中山峠": (42.845, 141.086),
    "札幌": (43.062, 141.355),
    "札幌市内": (43.062, 141.355),
    "HOTEL MYSTAYS Sapporo Aspen": (43.070, 141.350),
    "北海道大学": (43.074, 141.342),
    "富良野": (43.342, 142.383),
    "富良野市内": (43.342, 142.383),
    "ファーム富田": (43.418, 142.427),
    "美瑛": (43.588, 142.467),
    "層雲峡": (43.726, 142.948),
    "Sounkyo Auto Camp": (43.719, 142.977),
    "コテージ": (43.719, 142.977),
    "黒岳ロープウェイ": (43.724, 142.949),
    "層雲峡温泉街": (43.725, 142.948),
    "銀河・流星の滝": (43.724, 142.970),
    "大函": (43.728, 142.992),
    "層雲峡散策": (43.726, 142.948),
    "北見": (43.804, 143.895),
    "阿寒湖": (43.434, 144.097),
    "摩周湖候補": (43.583, 144.532),
    "阿寒・摩周": (43.486, 144.438),
    "中標津": (43.555, 144.971),
    "Shinrin Koen Camp": (43.555, 144.971),
    "羅臼": (44.021, 145.190),
    "知床峠": (44.075, 145.122),
    "知床五湖": (44.125, 145.080),
    "ウトロ": (44.064, 144.995),
    "フレペの滝遊歩道": (44.073, 145.014),
    "オシンコシンの滝": (44.032, 144.914),
    "標津": (43.660, 145.132),
    "野付半島": (43.587, 145.335),
    "尾岱沼": (43.570, 145.241),
    "野付半島ネイチャーセンター": (43.584, 145.314),
    "釧路湿原": (43.105, 144.430),
    "達古武湖": (43.073, 144.515),
    "釧路町": (42.996, 144.466),
    "釧路市内": (42.984, 144.381),
    "細岡展望台候補": (43.104, 144.456),
    "弟子屈": (43.485, 144.459),
    "足寄": (43.244, 143.553),
    "道の駅": (43.244, 143.555),
    "帯広": (42.923, 143.197),
    "帯広市内": (42.923, 143.197),
}


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


def short_text(text: str, limit: int = 84) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= limit:
        return text
    clipped = text[:limit]
    for mark in ("。", "、", "・", " "):
        pos = clipped.rfind(mark)
        if pos >= max(24, limit // 2):
            return clipped[:pos].rstrip("、。・ ") + "…"
    return clipped.rstrip("、。・ ") + "…"


def route_points(day, max_points: int = 7) -> list[dict[str, str]]:
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


def coordinate_for(place: str, day=None) -> tuple[float, float] | None:
    clean = clean_place(place)
    if clean in PLACE_COORDS:
        return PLACE_COORDS[clean]
    for part in re.split(r"[/／]", clean):
        part = clean_place(part)
        if part in PLACE_COORDS:
            return PLACE_COORDS[part]
    for key, coords in PLACE_COORDS.items():
        if key in clean or clean in key:
            return coords
    area = value(day, "area", "") if day is not None else ""
    if "キャンプ場" in clean and "層雲峡" in area:
        return PLACE_COORDS["Sounkyo Auto Camp"]
    if "キャンプ場" in clean and "洞爺湖" in area:
        return PLACE_COORDS["Green stay Toya"]
    return None


def route_map_filename(day) -> str:
    date = value(day, "date", "route")
    safe = re.sub(r"[^0-9A-Za-z_-]+", "-", str(date)).strip("-") or "route"
    return f"route-{safe}.png"


def route_geo_points(day, max_points: int = 7) -> list[dict[str, str | float | bool]]:
    points = route_points(day, max_points=max_points)
    if not points:
        return []

    coords: list[tuple[float, float] | None] = [coordinate_for(point["place"], day) for point in points]
    known_flags = [coord is not None for coord in coords]
    known = [coord for coord in coords if coord is not None]
    if not known:
        return []

    for index, coord in enumerate(coords):
        if coord is not None:
            continue
        previous = next((coords[i] for i in range(index - 1, -1, -1) if coords[i] is not None), None)
        following = next((coords[i] for i in range(index + 1, len(coords)) if coords[i] is not None), None)
        if previous and following:
            coords[index] = ((previous[0] + following[0]) / 2, (previous[1] + following[1]) / 2)
        else:
            coords[index] = previous or following or known[0]

    result: list[dict[str, str | float | bool]] = []
    for point, coord, is_known in zip(points, coords, known_flags):
        if coord is None:
            continue
        result.append(
            {
                **point,
                "lat": round(coord[0], 6),
                "lon": round(coord[1], 6),
                "known": is_known,
            }
        )
    return result


def route_map_points(day, max_points: int = 7) -> list[dict[str, str | float]]:
    points = route_points(day, max_points=max_points)
    if not points:
        return []

    coords: list[tuple[float, float] | None] = [coordinate_for(point["place"], day) for point in points]
    known = [coord for coord in coords if coord is not None]
    if not known:
        count = max(len(points) - 1, 1)
        return [
            {**point, "x": round(14 + index * (72 / count), 1), "y": round(18 + (index % 3) * 28, 1), "known": False}
            for index, point in enumerate(points)
        ]

    for index, coord in enumerate(coords):
        if coord is not None:
            continue
        previous = next((coords[i] for i in range(index - 1, -1, -1) if coords[i] is not None), None)
        following = next((coords[i] for i in range(index + 1, len(coords)) if coords[i] is not None), None)
        if previous and following:
            coords[index] = ((previous[0] + following[0]) / 2, (previous[1] + following[1]) / 2)
        else:
            coords[index] = previous or following or known[0]

    concrete = [coord for coord in coords if coord is not None]
    mean_lat = sum(lat for lat, _lon in concrete) / len(concrete)
    scale_x = max(math.cos(math.radians(mean_lat)), 0.55)
    projected = [(lon * scale_x, lat) for lat, lon in concrete]
    xs = [x for x, _y in projected]
    ys = [y for _x, y in projected]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    if max_x - min_x < 0.025:
        center = (min_x + max_x) / 2
        min_x, max_x = center - 0.0125, center + 0.0125
    if max_y - min_y < 0.025:
        center = (min_y + max_y) / 2
        min_y, max_y = center - 0.0125, center + 0.0125

    pad = 13.0
    seen: dict[tuple[int, int], int] = {}
    mapped: list[dict[str, str | float]] = []
    placed: list[tuple[float, float]] = []
    for point, (proj_x, lat), coord in zip(points, projected, coords):
        x = pad + ((proj_x - min_x) / (max_x - min_x)) * (100 - pad * 2)
        y = pad + ((max_y - lat) / (max_y - min_y)) * (100 - pad * 2)
        key = (round(proj_x, 4), round(lat, 4))
        duplicate_index = seen.get(key, 0)
        seen[key] = duplicate_index + 1
        if duplicate_index:
            angle = duplicate_index * 2.4 + 0.8
            radius = 12.0 + duplicate_index * 3.0
            x += math.cos(angle) * radius
            y += math.sin(angle) * radius
        for attempt in range(8):
            if not any(math.hypot(x - px, y - py) < 14.0 for px, py in placed):
                break
            angle = (len(placed) + attempt + 1) * 1.7
            radius = 6.0 + attempt * 1.8
            x += math.cos(angle) * radius
            y += math.sin(angle) * radius
        x = max(6, min(94, x))
        y = max(6, min(94, y))
        placed.append((x, y))
        mapped.append(
            {
                **point,
                "x": round(x, 1),
                "y": round(y, 1),
                "known": bool(coord),
            }
        )
    return mapped


def today_theme(day) -> str:
    summary = re.sub(r"\s+", " ", value(day, "summary", "")).strip()
    title = value(day, "title", "")
    area = value(day, "area", "")
    if len(summary) < 70:
        summary = (
            f"{summary} {title}をテーマに、{area}の見どころを無理なく巡ります。"
            "移動と休憩のリズムを整えながら、家族で写真を残したい景色を楽しむ一日です。"
        )
    if len(summary) > 115:
        clipped = summary[:115]
        last_period = clipped.rfind("。")
        last_comma = clipped.rfind("、")
        cut_at = last_period if last_period >= 60 else last_comma
        if cut_at >= 60:
            summary = clipped[:cut_at].rstrip("、。") + "。"
        else:
            summary = clipped[:112].rstrip("、。") + "。"
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


def todays_tips(day, max_items: int = 3) -> list[str]:
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


def route_map_url(day) -> str:
    points = route_points(day, max_points=8)
    if not points:
        return map_url(value(day, "area", "北海道"), "北海道")
    places = [clean_place(point["place"]) for point in points if point.get("place")]
    places = [place for index, place in enumerate(places) if place and place not in places[:index]]
    if len(places) < 2:
        return map_url(places[0], value(day, "area", "")) if places else map_url(value(day, "area", "北海道"), "")
    origin = quote_plus(places[0])
    destination = quote_plus(places[-1])
    waypoints = "|".join(quote_plus(place) for place in places[1:-1])
    url = f"https://www.google.com/maps/dir/?api=1&origin={origin}&destination={destination}&travelmode=driving"
    if waypoints:
        url += f"&waypoints={waypoints}"
    return url


def stay_time_for(day, place: str) -> str:
    clean = clean_place(place)
    for item in value(day, "timeline", []):
        item_place = clean_place(value(item, "place", ""))
        if clean in item_place or item_place in clean:
            duration = value(item, "duration", "")
            return duration if duration and duration != "-" else "30〜60分"
    return "30〜60分"


def guide_spots(day, max_items: int = 2) -> list[dict[str, str]]:
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
