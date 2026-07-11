from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.util import Inches, Pt
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
ITINERARY_DIR = ROOT / "itinerary" / "days"
IMAGES_DIR = ROOT / "images"
OUTPUT_DIR = ROOT / "output"
PPTX_PATH = OUTPUT_DIR / "hokkaido-family-travel-guide.pptx"
PDF_PATH = OUTPUT_DIR / "hokkaido-family-travel-guide.pdf"
PLACEHOLDER_DIR = OUTPUT_DIR / "_placeholders"

JP_FONT = "Yu Gothic"
EN_FONT = "Aptos"

NAVY = RGBColor(20, 55, 83)
BLUE = RGBColor(44, 115, 160)
SKY = RGBColor(226, 241, 248)
SAND = RGBColor(245, 238, 220)
CORAL = RGBColor(216, 99, 82)
INK = RGBColor(34, 43, 52)
MUTED = RGBColor(102, 112, 122)
WHITE = RGBColor(255, 255, 255)
PALE = RGBColor(248, 250, 252)


@dataclass
class TimelineItem:
    time: str
    type: str
    place: str
    detail: str
    duration: str


@dataclass
class Restaurant:
    meal: str
    name: str
    area: str
    memo: str


@dataclass
class DayPlan:
    date: str
    day: str
    title: str
    area: str
    hero: str
    summary: str
    timeline: list[TimelineItem]
    restaurants: list[Restaurant]
    notes: list[str]


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


def parse_day(path: Path) -> DayPlan:
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

    summary = section(raw, "Summary").replace("\n", " ").strip()

    timeline_rows = parse_table(section(raw, "Timeline").splitlines())
    timeline = [
        TimelineItem(*row[:5])
        for row in timeline_rows[1:]
        if len(row) >= 5
    ]

    restaurant_rows = parse_table(section(raw, "Restaurants").splitlines())
    restaurants = [
        Restaurant(*row[:4])
        for row in restaurant_rows[1:]
        if len(row) >= 4
    ]

    notes = [
        line.strip()[2:].strip()
        for line in section(raw, "Notes").splitlines()
        if line.strip().startswith("- ")
    ]

    return DayPlan(
        date=meta.get("date", path.stem),
        day=meta.get("day", ""),
        title=meta.get("title", path.stem),
        area=meta.get("area", ""),
        hero=meta.get("hero", meta.get("title", path.stem)),
        summary=summary,
        timeline=timeline,
        restaurants=restaurants,
        notes=notes,
    )


def load_days() -> list[DayPlan]:
    return [parse_day(path) for path in sorted(ITINERARY_DIR.glob("*.md"))]


def add_textbox(slide, x, y, w, h, text, font_size=18, color=INK, bold=False, align=PP_ALIGN.LEFT):
    box = slide.shapes.add_textbox(x, y, w, h)
    tf = box.text_frame
    tf.clear()
    tf.margin_left = Inches(0.08)
    tf.margin_right = Inches(0.08)
    tf.margin_top = Inches(0.04)
    tf.margin_bottom = Inches(0.04)
    p = tf.paragraphs[0]
    p.alignment = align
    run = p.add_run()
    run.text = text
    run.font.name = JP_FONT
    run.font.size = Pt(font_size)
    run.font.bold = bold
    run.font.color.rgb = color
    return box


def add_label(slide, x, y, text, fill=CORAL, color=WHITE):
    shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(1.45), Inches(0.36))
    shape.fill.solid()
    shape.fill.fore_color.rgb = fill
    shape.line.fill.background()
    tf = shape.text_frame
    tf.clear()
    tf.vertical_anchor = MSO_ANCHOR.MIDDLE
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = text
    r.font.name = JP_FONT
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = color
    return shape


def image_candidates(day: DayPlan) -> list[Path]:
    names = [day.date, day.hero, day.area, day.title]
    normalized: list[str] = []
    for name in names:
        for part in re.split(r"[/／ ]+", name):
            if part:
                normalized.append(part)
    candidates: list[Path] = []
    for name in names + normalized:
        for ext in (".jpg", ".jpeg", ".png", ".webp"):
            candidates.append(IMAGES_DIR / f"{name}{ext}")
    return candidates


def make_placeholder(label: str, path: Path, size=(1600, 900)) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", size, (228, 241, 248))
    draw = ImageDraw.Draw(img)
    for i in range(0, size[0], 80):
        draw.line((i, 0, i - 600, size[1]), fill=(210, 230, 240), width=6)
    try:
        font_big = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 84)
        font_small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Unicode.ttf", 34)
    except Exception:
        font_big = ImageFont.load_default()
        font_small = ImageFont.load_default()
    title = label
    subtitle = "写真を images フォルダに追加"
    tw = draw.textbbox((0, 0), title, font=font_big)
    sw = draw.textbbox((0, 0), subtitle, font=font_small)
    draw.rounded_rectangle((120, 260, 1480, 640), radius=36, fill=(255, 255, 255), outline=(44, 115, 160), width=4)
    draw.text(((size[0] - (tw[2] - tw[0])) / 2, 350), title, fill=(20, 55, 83), font=font_big)
    draw.text(((size[0] - (sw[2] - sw[0])) / 2, 470), subtitle, fill=(102, 112, 122), font=font_small)
    img.save(path)
    return path


def hero_image(day: DayPlan) -> Path:
    for path in image_candidates(day):
        if path.exists():
            return path
    safe = re.sub(r"[^0-9A-Za-zぁ-んァ-ヶ一-龠ー_-]+", "_", day.hero)[:50] or day.date
    return make_placeholder(day.hero, PLACEHOLDER_DIR / f"{day.date}_{safe}.png")


def add_picture_cover(slide, image_path: Path, x, y, w, h):
    slide.shapes.add_picture(str(image_path), x, y, width=w, height=h)


def style_background(slide, color=RGBColor(255, 255, 255)):
    bg = slide.background
    fill = bg.fill
    fill.solid()
    fill.fore_color.rgb = color


def add_timeline(slide, items: list[TimelineItem], start_y=Inches(1.55), max_items=8):
    y = start_y
    for item in items[:max_items]:
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, Inches(0.55), y, Inches(7.0), Inches(0.55))
        card.fill.solid()
        card.fill.fore_color.rgb = PALE
        card.line.color.rgb = RGBColor(222, 228, 234)
        add_textbox(slide, Inches(0.68), y + Inches(0.08), Inches(0.9), Inches(0.28), item.time, 9.5, BLUE, True, PP_ALIGN.CENTER)
        add_textbox(slide, Inches(1.55), y + Inches(0.08), Inches(0.75), Inches(0.28), item.type, 9.5, CORAL, True, PP_ALIGN.CENTER)
        add_textbox(slide, Inches(2.28), y + Inches(0.07), Inches(1.35), Inches(0.30), item.place, 9.0, NAVY, True)
        add_textbox(slide, Inches(3.55), y + Inches(0.06), Inches(3.35), Inches(0.34), item.detail, 8.3, INK)
        add_textbox(slide, Inches(6.95), y + Inches(0.08), Inches(0.45), Inches(0.28), item.duration, 8.3, MUTED, False, PP_ALIGN.RIGHT)
        y += Inches(0.62)


def add_restaurants(slide, restaurants: list[Restaurant], x=Inches(7.82), y=Inches(4.65)):
    add_textbox(slide, x, y, Inches(4.75), Inches(0.32), "レストラン候補", 15, NAVY, True)
    y += Inches(0.42)
    for r in restaurants[:4]:
        card = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, Inches(4.75), Inches(0.48))
        card.fill.solid()
        card.fill.fore_color.rgb = RGBColor(255, 255, 255)
        card.line.color.rgb = RGBColor(226, 232, 240)
        add_textbox(slide, x + Inches(0.08), y + Inches(0.06), Inches(0.62), Inches(0.25), r.meal, 8.5, CORAL, True)
        add_textbox(slide, x + Inches(0.70), y + Inches(0.05), Inches(1.70), Inches(0.25), r.name, 8.5, NAVY, True)
        add_textbox(slide, x + Inches(2.35), y + Inches(0.05), Inches(2.15), Inches(0.25), r.memo, 7.5, MUTED)
        y += Inches(0.55)


def build_pptx(days: list[DayPlan]):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    prs = Presentation()
    prs.slide_width = Inches(13.333)
    prs.slide_height = Inches(7.5)
    blank = prs.slide_layouts[6]

    cover = prs.slides.add_slide(blank)
    style_background(cover, SAND)
    add_textbox(cover, Inches(0.7), Inches(0.62), Inches(3.0), Inches(0.35), "HOKKAIDO FAMILY TRAVEL GUIDE", 12, BLUE, True)
    add_textbox(cover, Inches(0.68), Inches(1.45), Inches(6.1), Inches(1.0), "北海道家族旅行\nガイドブック", 33, NAVY, True)
    add_textbox(cover, Inches(0.78), Inches(3.1), Inches(5.2), Inches(0.48), "2026年7月31日 - 8月12日", 18, INK, True)
    add_textbox(cover, Inches(0.78), Inches(3.72), Inches(5.6), Inches(0.75), "仙台からフェリーで北海道へ。洞爺湖、札幌、層雲峡、道東方面をめぐる家族旅行。", 15, INK)
    add_label(cover, Inches(0.78), Inches(4.78), "初回版")
    cover_img = hero_image(days[0])
    add_picture_cover(cover, cover_img, Inches(7.05), Inches(0.75), Inches(5.55), Inches(5.95))

    for day in days:
        slide = prs.slides.add_slide(blank)
        style_background(slide, RGBColor(255, 255, 255))
        add_picture_cover(slide, hero_image(day), Inches(7.72), Inches(0), Inches(5.61), Inches(4.25))
        add_label(slide, Inches(0.55), Inches(0.38), f"DAY {day.day}")
        add_textbox(slide, Inches(0.55), Inches(0.82), Inches(6.7), Inches(0.60), f"{day.date}  {day.title}", 22, NAVY, True)
        add_textbox(slide, Inches(0.58), Inches(1.35), Inches(6.55), Inches(0.42), day.area, 13, BLUE, True)
        add_textbox(slide, Inches(0.58), Inches(1.88), Inches(6.65), Inches(0.98), day.summary, 12.3, INK)
        add_textbox(slide, Inches(0.58), Inches(3.12), Inches(6.7), Inches(0.32), "この日の流れ", 15, NAVY, True)
        add_timeline(slide, day.timeline, start_y=Inches(3.55), max_items=5)
        add_restaurants(slide, day.restaurants)
        if day.notes:
            add_textbox(slide, Inches(7.82), Inches(6.78), Inches(4.6), Inches(0.25), "MEMO  " + " / ".join(day.notes[:2]), 7.8, MUTED)

        slide2 = prs.slides.add_slide(blank)
        style_background(slide2, RGBColor(252, 252, 250))
        add_label(slide2, Inches(0.55), Inches(0.35), f"DAY {day.day}")
        add_textbox(slide2, Inches(0.55), Inches(0.78), Inches(6.8), Inches(0.42), "時刻ベース詳細スケジュール", 22, NAVY, True)
        add_timeline(slide2, day.timeline, start_y=Inches(1.45), max_items=10)
        add_picture_cover(slide2, hero_image(day), Inches(8.05), Inches(0.55), Inches(4.55), Inches(2.55))
        add_restaurants(slide2, day.restaurants, x=Inches(8.05), y=Inches(3.35))

    prs.save(PPTX_PATH)


def register_pdf_font() -> str:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/ヒラギノ角ゴシック W3.ttc",
        "/System/Library/Fonts/Hiragino Sans GB.ttc",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            pdfmetrics.registerFont(TTFont("GuideJP", candidate))
            return "GuideJP"
    return "Helvetica"


def build_pdf(days: list[DayPlan]):
    font = register_pdf_font()
    page_size = landscape(A4)
    doc = SimpleDocTemplate(
        str(PDF_PATH),
        pagesize=page_size,
        leftMargin=14 * mm,
        rightMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=10 * mm,
        title="北海道家族旅行ガイド",
    )
    base = ParagraphStyle("base", fontName=font, fontSize=9.2, leading=12.2, textColor=colors.HexColor("#222B34"), wordWrap="CJK")
    h1 = ParagraphStyle("h1", parent=base, fontSize=20, leading=25, textColor=colors.HexColor("#143753"), spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=base, fontSize=13, leading=17, textColor=colors.HexColor("#2C73A0"), spaceBefore=8, spaceAfter=5)
    center = ParagraphStyle("center", parent=base, alignment=TA_CENTER)

    def p(text, style=base):
        return Paragraph(str(text).replace("&", "&amp;"), style)

    def pdf_table(rows, widths, header=colors.HexColor("#E2F1F8"), size=7.8):
        body = ParagraphStyle(f"tbl{size}", parent=base, fontSize=size, leading=size + 2.6, wordWrap="CJK")
        data = [[Paragraph(str(c).replace("&", "&amp;"), body) for c in row] for row in rows]
        tbl = Table(data, colWidths=widths, repeatRows=1)
        tbl.setStyle(TableStyle([
            ("FONTNAME", (0, 0), (-1, -1), font),
            ("BACKGROUND", (0, 0), (-1, 0), header),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#B8C2CC")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl

    story = [
        Spacer(1, 28),
        Paragraph("北海道家族旅行ガイドブック", ParagraphStyle("title", parent=h1, alignment=TA_CENTER, fontSize=30, leading=36)),
        Paragraph("2026年7月31日 - 8月12日", ParagraphStyle("sub", parent=center, fontSize=14, leading=18, textColor=colors.HexColor("#66707A"))),
        Spacer(1, 18),
        p("初回版: 7月31日と8月5日の2日分を完成形に近いデザインで作成", center),
        PageBreak(),
    ]

    for day in days:
        story += [
            Paragraph(f"DAY {day.day}  {day.date}", h2),
            Paragraph(day.title, h1),
            p(day.area),
            Spacer(1, 4),
            p(day.summary),
            Paragraph("時刻ベース詳細スケジュール", h2),
            pdf_table(
                [["Time", "Type", "Place", "Detail", "Duration"]] + [[i.time, i.type, i.place, i.detail, i.duration] for i in day.timeline],
                [24 * mm, 22 * mm, 42 * mm, 132 * mm, 26 * mm],
                size=7.2,
            ),
            Paragraph("レストラン候補", h2),
            pdf_table(
                [["Meal", "Name", "Area", "Memo"]] + [[r.meal, r.name, r.area, r.memo] for r in day.restaurants],
                [28 * mm, 66 * mm, 46 * mm, 106 * mm],
                header=colors.HexColor("#F5EEDC"),
                size=8.0,
            ),
        ]
        if day.notes:
            story.append(Paragraph("メモ", h2))
            for note in day.notes:
                story.append(p(f"・{note}"))
        story.append(PageBreak())

    doc.build(story)


def convert_pptx_to_pdf_if_possible() -> bool:
    soffice = shutil.which("libreoffice") or shutil.which("soffice")
    if not soffice:
        return False
    try:
        subprocess.run(
            [soffice, "--headless", "--convert-to", "pdf", "--outdir", str(OUTPUT_DIR), str(PPTX_PATH)],
            check=True,
            timeout=120,
        )
        converted = OUTPUT_DIR / "hokkaido-family-travel-guide.pdf"
        return converted.exists()
    except Exception:
        return False


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    PLACEHOLDER_DIR.mkdir(parents=True, exist_ok=True)
    days = load_days()
    if not days:
        raise SystemExit("No itinerary day files found under itinerary/days")
    build_pptx(days)
    if not convert_pptx_to_pdf_if_possible():
        build_pdf(days)
    print(f"Generated: {PPTX_PATH}")
    print(f"Generated: {PDF_PATH}")


if __name__ == "__main__":
    main()

