from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
IMAGES_DIR = ROOT / "images"
ATTRIBUTION = IMAGES_DIR / "ATTRIBUTION.md"
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "hokkaido-trip-plan/1.0 (family travel guide; https://github.com/inzaikun/hokkaido-trip-plan)"


ASSETS = [
    {
        "file": "洞爺湖.jpg",
        "place": "洞爺湖",
        "caption": "カルデラ湖と中島を望む、洞爺湖滞在のメイン風景",
        "queries": ["Lake Toya Hokkaido Nakajima", "Lake Toya view Hokkaido"],
    },
    {
        "file": "サイロ展望台.jpg",
        "place": "サイロ展望台",
        "caption": "洞爺湖を高台から見下ろす定番の写真スポット",
        "queries": ["Silo observatory Lake Toya", "Lake Toya observatory Hokkaido"],
    },
    {
        "file": "有珠山ロープウェイ.jpg",
        "place": "有珠山ロープウェイ",
        "caption": "有珠山と昭和新山、洞爺湖をまとめて楽しめる展望エリア",
        "queries": ["Usuzan Ropeway Hokkaido", "Mount Usu ropeway Lake Toya"],
    },
    {
        "file": "昭和新山.jpg",
        "place": "昭和新山",
        "caption": "洞爺湖周辺ジオパークを象徴する火山風景",
        "queries": ["Showa Shinzan Hokkaido", "Shōwa-shinzan Mount Usu"],
    },
    {
        "file": "美瑛.jpg",
        "place": "美瑛",
        "caption": "丘の連なりと畑の色が印象的な、富良野から層雲峡への寄り道候補",
        "queries": ["Biei hills Hokkaido", "Patchwork road Biei Hokkaido"],
    },
    {
        "file": "黒岳ロープウェイ.jpg",
        "place": "黒岳ロープウェイ",
        "caption": "層雲峡から大雪山の展望へ上がる自然満喫スポット",
        "queries": ["Kurodake Ropeway Sounkyo", "Mount Kurodake ropeway Hokkaido"],
    },
    {
        "file": "銀河・流星の滝.jpg",
        "place": "銀河・流星の滝",
        "caption": "層雲峡らしい柱状節理と滝を短時間で楽しめる名所",
        "title": "File:Sounkyo1.jpg",
        "queries": ["Ginga Ryusei waterfalls Sounkyo", "Sounkyo waterfall Hokkaido"],
    },
    {
        "file": "摩周湖.jpg",
        "place": "摩周湖",
        "caption": "道東移動中に天候が良ければ立ち寄りたい展望湖",
        "queries": ["Lake Mashu Hokkaido", "Mashu Lake observatory"],
    },
    {
        "file": "阿寒湖.jpg",
        "place": "阿寒湖",
        "caption": "道東の湖畔休憩に組み込みやすい自然スポット",
        "title": "File:Lake Akan and Mount Oakan - 2005.jpg",
        "queries": ["Lake Akan Hokkaido", "Akan lake Hokkaido"],
    },
    {
        "file": "知床五湖.jpg",
        "place": "知床五湖",
        "caption": "知床連山と原生林を陸路で味わう世界自然遺産のハイライト",
        "title": "File:140829 Ichiko of Shiretoko Goko Lakes Hokkaido Japan01s5.jpg",
        "queries": ["Shiretoko Five Lakes Hokkaido", "Shiretoko Goko lakes"],
    },
    {
        "file": "知床峠.jpg",
        "place": "知床峠",
        "caption": "羅臼岳や国後島方面を望む、知床横断道路の展望地点",
        "queries": ["Shiretoko Pass Hokkaido", "Shiretoko-toge pass"],
    },
    {
        "file": "オシンコシンの滝.jpg",
        "place": "オシンコシンの滝",
        "caption": "駐車場から短時間で見られる、知床帰路の滝スポット",
        "queries": ["Oshinkoshin Falls Hokkaido", "Oshin Koshin waterfall"],
    },
    {
        "file": "野付半島.jpg",
        "place": "野付半島",
        "caption": "海と湿原、トドワラの風景が広がる道東らしい自然ドライブ",
        "title": "File:Withered Oak Trees in Notsuke peninsula.JPG",
        "queries": ["Notsuke Peninsula Hokkaido", "Todowara Notsuke Peninsula"],
    },
    {
        "file": "釧路湿原.jpg",
        "place": "釧路湿原",
        "caption": "広い湿原を展望台や湖畔から眺める自然予備日の候補",
        "title": "File:Kushirositsugen Hosooka Tenboudai01.jpg",
        "queries": ["Kushiro Shitsugen National Park", "Kushiro wetland Hokkaido"],
    },
    {
        "file": "達古武湖.jpg",
        "place": "達古武湖",
        "caption": "釧路湿原の水辺を近くに感じられる、静かな湖畔スポット",
        "queries": ["Lake Takkobu Hokkaido", "Takkobu lake Kushiro"],
    },
    {
        "file": "十勝平野.jpg",
        "place": "十勝平野",
        "caption": "帯広周辺で感じたい、十勝らしい広い畑と空",
        "title": "File:Mount Tokachi 06.JPG",
        "queries": ["Tokachi plain Hokkaido", "Tokachi fields Hokkaido"],
    },
    {
        "file": "帯広.jpg",
        "place": "帯広",
        "caption": "十勝グルメと市街休憩を楽しむ、移動負荷を下げる宿泊地",
        "queries": ["Obihiro Hokkaido city", "Obihiro station Hokkaido"],
    },
    {
        "file": "苫小牧港.jpg",
        "place": "苫小牧港",
        "caption": "北海道から仙台へ戻るフェリー出港地",
        "queries": ["Tomakomai port ferry Hokkaido", "Tomakomai ferry terminal"],
    },
    {
        "file": "太平洋フェリー.jpg",
        "place": "太平洋フェリー",
        "caption": "仙台と北海道を結ぶ船旅のイメージ",
        "title": "File:Ishikari(3rd), JAPAN.jpg",
        "queries": ["Taiheiyo Ferry Tomakomai", "Taiheiyo Ferry Hokkaido"],
    },
]

EXISTING = [
    {
        "file": "cover.png",
        "place": "北海道ドライブ風景",
        "caption": "表紙写真",
        "source": "User-provided image",
        "license": "User approved for this guide",
        "author": "User-provided",
        "url": "",
    },
    {
        "file": "北海道大学.jpg",
        "place": "北海道大学",
        "caption": "札幌駅近くで緑を感じられる、散策向きのキャンパス",
        "source": "User-provided image",
        "license": "User-provided for this guide",
        "author": "User-provided",
        "url": "",
    },
    {
        "file": "ファーム富田.jpg",
        "place": "ファーム富田",
        "caption": "富良野らしい花畑を楽しむ、移動日の華やかな寄り道",
        "source": "User-provided image",
        "license": "User-provided for this guide",
        "author": "User-provided",
        "url": "",
    },
    {
        "file": "仙台城跡.jpg",
        "place": "仙台城跡",
        "caption": "伊達政宗ゆかりの城跡",
        "source": "Wikimedia Commons",
        "license": "Free license listed on Wikimedia Commons",
        "author": "",
        "url": "https://commons.wikimedia.org/wiki/File:Waki-yagura_of_Sendai_Castle_20220910b.jpg",
    },
    {
        "file": "瑞鳳殿.jpg",
        "place": "瑞鳳殿",
        "caption": "伊達政宗公の霊屋",
        "source": "Wikimedia Commons",
        "license": "Free license listed on Wikimedia Commons",
        "author": "",
        "url": "https://commons.wikimedia.org/wiki/File:Zuiho-den06s3200.jpg",
    },
]


def request_json(params: dict[str, str]) -> dict:
    url = COMMONS_API + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def clean_html(value: str) -> str:
    text = re.sub(r"<[^>]+>", "", value or "")
    return re.sub(r"\s+", " ", text).strip()


def file_page_url(title: str) -> str:
    return "https://commons.wikimedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_"))


def search_commons(query: str) -> list[dict]:
    data = request_json(
        {
            "action": "query",
            "generator": "search",
            "gsrnamespace": "6",
            "gsrsearch": query,
            "gsrlimit": "12",
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": "1800",
            "format": "json",
        }
    )
    return list(data.get("query", {}).get("pages", {}).values())


def fetch_title(title: str) -> dict:
    data = request_json(
        {
            "action": "query",
            "titles": title,
            "prop": "imageinfo",
            "iiprop": "url|mime|size|extmetadata",
            "iiurlwidth": "1800",
            "format": "json",
        }
    )
    pages = list(data.get("query", {}).get("pages", {}).values())
    if not pages:
        raise RuntimeError(f"Image title not found: {title}")
    return pages[0]


def score_candidate(page: dict, query: str) -> int:
    title = page.get("title", "").lower()
    info = (page.get("imageinfo") or [{}])[0]
    metadata = info.get("extmetadata", {})
    license_name = clean_html(metadata.get("LicenseShortName", {}).get("value", "")).lower()
    mime = info.get("mime", "")
    width = int(info.get("width") or 0)
    height = int(info.get("height") or 0)
    if not mime.startswith("image/") or mime.endswith("svg+xml"):
        return -999
    if "logo" in title or "map" in title or "svg" in title:
        return -50
    if not any(word in license_name for word in ("cc", "public domain", "pd", "free")):
        return -60
    score = min(width, 2200) // 120 + min(height, 1400) // 120
    for token in re.findall(r"[a-z0-9]+", query.lower()):
        if len(token) > 3 and token in title:
            score += 8
    if any(word in title for word in ("view", "lake", "falls", "ropeway", "pass", "peninsula", "wetland", "field")):
        score += 8
    return score


def choose_image(asset: dict) -> dict:
    if asset.get("title"):
        return fetch_title(asset["title"])
    best: tuple[int, dict] | None = None
    for query in asset["queries"]:
        for page in search_commons(query):
            score = score_candidate(page, query)
            if best is None or score > best[0]:
                best = (score, page)
    if best is None or best[0] < 0:
        raise RuntimeError(f"No suitable image found for {asset['file']}")
    return best[1]


def download_image(url: str, output: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=40) as response:
        data = response.read()
    tmp = output.with_suffix(".download")
    tmp.write_bytes(data)
    with Image.open(tmp) as image:
        image = image.convert("RGB")
        image.thumbnail((1800, 1200))
        image.save(output, quality=90)
    tmp.unlink(missing_ok=True)


def metadata_for(asset: dict, page: dict) -> dict:
    info = (page.get("imageinfo") or [{}])[0]
    metadata = info.get("extmetadata", {})
    return {
        "file": asset["file"],
        "place": asset["place"],
        "caption": asset["caption"],
        "source": "Wikimedia Commons",
        "license": clean_html(metadata.get("LicenseShortName", {}).get("value", "")),
        "author": clean_html(metadata.get("Artist", {}).get("value", "")),
        "url": file_page_url(page.get("title", "")),
    }


def write_attribution(rows: list[dict]) -> None:
    lines = [
        "# 画像クレジット",
        "",
        "このフォルダの写真は旅行ガイドの挿絵として利用します。差し替える場合は、同じファイル名で置き換えるか、各日程Markdownの `Photos` セクションの `Image` を更新してください。",
        "",
        "| File | Place | Caption | Source | License | Author | URL |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {file} | {place} | {caption} | {source} | {license} | {author} | {url} |".format(
                **{key: str(value).replace("|", "/") for key, value in row.items()}
            )
        )
    ATTRIBUTION.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    rows = list(EXISTING)
    for asset in ASSETS:
        page = choose_image(asset)
        info = (page.get("imageinfo") or [{}])[0]
        url = info.get("thumburl") or info.get("url")
        if not url:
            raise RuntimeError(f"No download URL for {asset['file']}")
        output = IMAGES_DIR / asset["file"]
        download_image(url, output)
        row = metadata_for(asset, page)
        rows.append(row)
        print(f"{asset['file']}: {row['url']} ({row['license']})")
    write_attribution(rows)


if __name__ == "__main__":
    main()
