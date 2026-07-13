from __future__ import annotations

import math
import os
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from guidebook_common import route_geo_points, route_map_filename, value


TILE_SIZE = 256
MAP_SIZE = (1200, 820)
OSM_TILE_URL = "https://tile.openstreetmap.org/{z}/{x}/{y}.png"
USER_AGENT = "hokkaido-trip-plan/1.0 (family travel guide; https://github.com/inzaikun/hokkaido-trip-plan)"


def latlon_to_world(lat: float, lon: float, zoom: int) -> tuple[float, float]:
    sin_lat = math.sin(math.radians(max(min(lat, 85.05112878), -85.05112878)))
    scale = TILE_SIZE * (2**zoom)
    x = (lon + 180.0) / 360.0 * scale
    y = (0.5 - math.log((1 + sin_lat) / (1 - sin_lat)) / (4 * math.pi)) * scale
    return x, y


def pick_zoom(coords: list[tuple[float, float]], width: int, height: int) -> int:
    if len(coords) <= 1:
        return 11
    for zoom in range(12, 4, -1):
        pixels = [latlon_to_world(lat, lon, zoom) for lat, lon in coords]
        xs = [x for x, _y in pixels]
        ys = [y for _x, y in pixels]
        span_x = max(xs) - min(xs)
        span_y = max(ys) - min(ys)
        if span_x <= width * 0.68 and span_y <= height * 0.62:
            tile_cols = math.ceil((span_x + width * 0.42) / TILE_SIZE) + 2
            tile_rows = math.ceil((span_y + height * 0.48) / TILE_SIZE) + 2
            if tile_cols * tile_rows <= 42:
                return zoom
    return 5


def tile_path(cache_dir: Path, zoom: int, x: int, y: int) -> Path:
    return cache_dir / str(zoom) / str(x) / f"{y}.png"


def download_tile(cache_dir: Path, zoom: int, x: int, y: int) -> Image.Image | None:
    max_tile = 2**zoom
    if x < 0 or x >= max_tile or y < 0 or y >= max_tile:
        return None
    path = tile_path(cache_dir, zoom, x, y)
    if path.exists():
        try:
            return Image.open(path).convert("RGB")
        except Exception:
            path.unlink(missing_ok=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        OSM_TILE_URL.format(z=zoom, x=x, y=y),
        headers={"User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=12) as response:
            path.write_bytes(response.read())
        return Image.open(path).convert("RGB")
    except Exception:
        return None


def draw_fallback_background(draw: ImageDraw.ImageDraw, width: int, height: int) -> None:
    draw.rectangle((0, 0, width, height), fill=(213, 234, 240))
    draw.rounded_rectangle((52, 48, width - 52, height - 58), radius=42, fill=(238, 233, 208), outline=(152, 180, 157), width=3)
    for i in range(-height, width, 56):
        draw.line((i, height, i + height, 0), fill=(221, 226, 205), width=2)
    for x, y, r in ((280, 210, 82), (890, 190, 110), (720, 620, 96), (380, 650, 74)):
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(219, 232, 206), outline=(191, 213, 184), width=2)


def render_tile_background(
    output: Image.Image,
    cache_dir: Path,
    coords: list[tuple[float, float]],
    zoom: int,
) -> tuple[bool, float, float]:
    width, height = output.size
    center_lat = sum(lat for lat, _lon in coords) / len(coords)
    center_lon = sum(lon for _lat, lon in coords) / len(coords)
    center_x, center_y = latlon_to_world(center_lat, center_lon, zoom)
    top_left_x = center_x - width / 2
    top_left_y = center_y - height / 2
    min_tile_x = math.floor(top_left_x / TILE_SIZE)
    max_tile_x = math.floor((top_left_x + width) / TILE_SIZE)
    min_tile_y = math.floor(top_left_y / TILE_SIZE)
    max_tile_y = math.floor((top_left_y + height) / TILE_SIZE)

    pasted = 0
    for tile_x in range(min_tile_x, max_tile_x + 1):
        for tile_y in range(min_tile_y, max_tile_y + 1):
            tile = download_tile(cache_dir, zoom, tile_x, tile_y)
            if tile is None:
                continue
            px = int(tile_x * TILE_SIZE - top_left_x)
            py = int(tile_y * TILE_SIZE - top_left_y)
            output.paste(tile, (px, py))
            pasted += 1
    return pasted > 0, top_left_x, top_left_y


def fit_fallback_projection(coords: list[tuple[float, float]], width: int, height: int):
    lats = [lat for lat, _lon in coords]
    lons = [lon for _lat, lon in coords]
    min_lat, max_lat = min(lats), max(lats)
    min_lon, max_lon = min(lons), max(lons)
    if max_lat - min_lat < 0.04:
        pad = (0.04 - (max_lat - min_lat)) / 2
        min_lat -= pad
        max_lat += pad
    if max_lon - min_lon < 0.04:
        pad = (0.04 - (max_lon - min_lon)) / 2
        min_lon -= pad
        max_lon += pad
    lat_pad = max((max_lat - min_lat) * 0.22, 0.04)
    lon_pad = max((max_lon - min_lon) * 0.22, 0.04)
    min_lat -= lat_pad
    max_lat += lat_pad
    min_lon -= lon_pad
    max_lon += lon_pad

    def project(lat: float, lon: float) -> tuple[float, float]:
        x = 70 + (lon - min_lon) / (max_lon - min_lon) * (width - 140)
        y = 72 + (max_lat - lat) / (max_lat - min_lat) * (height - 144)
        return x, y

    return project


def load_font(size: int, bold: bool = False):
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def marker_label_position(index: int, point_count: int) -> tuple[int, int]:
    if index == 0:
        return 12, 10
    if index == point_count - 1:
        return 12, -28
    offsets = [(12, -26), (14, 10), (-78, -26), (-78, 8)]
    return offsets[index % len(offsets)]


def render_route_map(day, root: Path, force: bool | None = None) -> Path:
    maps_dir = root / "maps"
    output_path = maps_dir / route_map_filename(day)
    force = force if force is not None else os.environ.get("FORCE_ROUTE_MAPS") == "1"
    if output_path.exists() and not force:
        return output_path

    maps_dir.mkdir(parents=True, exist_ok=True)
    geo_points = route_geo_points(day, max_points=8)
    if not geo_points:
        return output_path

    coords = [(float(point["lat"]), float(point["lon"])) for point in geo_points]
    width, height = MAP_SIZE
    image = Image.new("RGB", MAP_SIZE, (213, 234, 240))
    draw = ImageDraw.Draw(image)
    zoom = pick_zoom(coords, width, height)
    cache_dir = maps_dir / "_tile-cache"
    has_tiles, top_left_x, top_left_y = render_tile_background(image, cache_dir, coords, zoom)
    draw = ImageDraw.Draw(image)

    if has_tiles:
        overlay = Image.new("RGBA", MAP_SIZE, (255, 255, 255, 0))
        overlay_draw = ImageDraw.Draw(overlay)
        overlay_draw.rectangle((0, 0, width, height), fill=(255, 250, 240, 28))
        image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
        draw = ImageDraw.Draw(image)

        def project(lat: float, lon: float) -> tuple[float, float]:
            px, py = latlon_to_world(lat, lon, zoom)
            return px - top_left_x, py - top_left_y

    else:
        draw_fallback_background(draw, width, height)
        project = fit_fallback_projection(coords, width, height)

    pixels = [project(lat, lon) for lat, lon in coords]
    shadow = [(x + 3, y + 3) for x, y in pixels]
    if len(pixels) > 1:
        draw.line(shadow, fill=(255, 255, 255), width=16, joint="curve")
        draw.line(pixels, fill=(21, 99, 139), width=9, joint="curve")
        draw.line(pixels, fill=(64, 163, 183), width=4, joint="curve")

    font_num = load_font(24, bold=True)
    font_label = load_font(20, bold=True)
    font_small = load_font(17)
    for index, (point, (x, y)) in enumerate(zip(geo_points, pixels)):
        is_edge = index in {0, len(pixels) - 1}
        fill = (214, 91, 75) if is_edge else (255, 255, 255)
        outline = (214, 91, 75) if is_edge else (21, 99, 139)
        r = 21
        draw.ellipse((x - r, y - r, x + r, y + r), fill=(255, 255, 255), outline=(255, 255, 255), width=8)
        draw.ellipse((x - r, y - r, x + r, y + r), fill=fill, outline=outline, width=4)
        text = str(index + 1)
        bbox = draw.textbbox((0, 0), text, font=font_num)
        draw.text((x - (bbox[2] - bbox[0]) / 2, y - (bbox[3] - bbox[1]) / 2 - 1), text, fill=(255, 255, 255) if is_edge else (21, 99, 139), font=font_num)
        dx, dy = marker_label_position(index, len(pixels))
        label = str(point["place"])
        label = label[:13] + "…" if len(label) > 14 else label
        lb = draw.textbbox((0, 0), label, font=font_label)
        lx, ly = x + dx, y + dy
        draw.rounded_rectangle((lx - 8, ly - 6, lx + (lb[2] - lb[0]) + 8, ly + 26), radius=8, fill=(255, 255, 255), outline=(200, 216, 224), width=1)
        draw.text((lx, ly), label, fill=(31, 52, 66), font=font_label)

    title = f"DAY {value(day, 'day', '')}  Today's Map"
    draw.rounded_rectangle((28, 24, 390, 82), radius=12, fill=(255, 255, 255), outline=(197, 216, 225), width=2)
    draw.text((48, 42), title, fill=(15, 51, 68), font=load_font(24, bold=True))
    draw.rounded_rectangle((width - 352, height - 42, width - 22, height - 10), radius=8, fill=(255, 255, 255))
    credit = "Map data © OpenStreetMap contributors"
    draw.text((width - 338, height - 36), credit, fill=(69, 86, 96), font=font_small)

    image.save(output_path, quality=92)
    return output_path
