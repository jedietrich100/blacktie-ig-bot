"""Render a branded Digital Calm Daily square Instagram graphic.

The design intentionally uses a small family of layouts so the feed feels
recognizable without looking mechanically identical every day. Topic-specific
symbols are derived from the generator's visual_symbol field when possible.
"""

from __future__ import annotations

import math
import re
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = H = 1080
BG = (247, 244, 236)
NAVY = (24, 42, 61)
TEAL = (77, 148, 149)
BLUE = (126, 163, 190)
PALE = (232, 239, 236)
SAND = (239, 236, 222)
WHITE = (255, 255, 255)
MUTED = (89, 105, 119)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

CATEGORY_LABELS = {
    "iphone and apple tips": "iPHONE TIP",
    "ai tips": "AI TIP",
    "scam and cybersecurity": "SCAM & SAFETY",
    "simple tech how-tos": "QUICK HOW-TO",
    "digital organization": "DIGITAL ORGANIZATION",
    "useful tech tools": "USEFUL TECH TOOL",
    "digital confidence": "DIGITAL CONFIDENCE",
}


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


def text_width(draw: ImageDraw.ImageDraw, text: str, fnt) -> int:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        test = word if not line else f"{line} {word}"
        if text_width(draw, test, fnt) <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def fitted_lines(
    draw: ImageDraw.ImageDraw,
    text: str,
    max_width: int,
    max_lines: int,
    start_size: int,
    min_size: int,
    bold: bool = False,
):
    path = FONT_BOLD if bold else FONT_REG
    for size in range(start_size, min_size - 1, -2):
        fnt = font(path, size)
        lines = wrap_text(draw, text, fnt, max_width)
        if len(lines) <= max_lines:
            return fnt, lines
    fnt = font(path, min_size)
    return fnt, wrap_text(draw, text, fnt, max_width)[:max_lines]


def draw_centered_lines(draw, lines, fnt, center_x, start_y, fill, spacing):
    y = start_y
    for line in lines:
        w = text_width(draw, line, fnt)
        draw.text((center_x - w / 2, y), line, font=fnt, fill=fill)
        y += spacing
    return y


def category_label(category: str) -> str:
    return CATEGORY_LABELS.get(category.lower(), "30-SECOND TECH WIN")


def draw_brand(draw: ImageDraw.ImageDraw, category: str) -> None:
    # Compact brand tile.
    draw.rounded_rectangle((76, 62, 226, 202), radius=28, fill=NAVY)
    small = font(FONT_BOLD, 22)
    for idx, word in enumerate(("DIGITAL", "CALM", "DAILY")):
        w = text_width(draw, word, small)
        draw.text((151 - w / 2, 84 + idx * 34), word, font=small, fill=WHITE if idx != 1 else (154, 215, 205))

    series = font(FONT_BOLD, 25)
    draw.text((258, 79), "30-SECOND TECH WIN", font=series, fill=NAVY)
    sub = font(FONT_REG, 22)
    draw.text((258, 121), "Simple tech. Less stress.", font=sub, fill=MUTED)

    label = category_label(category)
    label_font = font(FONT_BOLD, 20)
    label_w = text_width(draw, label, label_font)
    pill_x2 = 1004
    pill_x1 = pill_x2 - label_w - 44
    draw.rounded_rectangle((pill_x1, 78, pill_x2, 126), radius=24, fill=PALE)
    draw.text((pill_x1 + 22, 90), label, font=label_font, fill=NAVY)


def draw_phone(draw, cx, cy, s=1.0):
    w, h = int(130*s), int(210*s)
    stroke = max(5, int(8*s))
    draw.rounded_rectangle((cx-w//2, cy-h//2, cx+w//2, cy+h//2), radius=int(22*s), outline=NAVY, width=stroke)
    draw.line((cx-int(18*s), cy+int(78*s), cx+int(18*s), cy+int(78*s)), fill=NAVY, width=stroke)


def draw_shield(draw, cx, cy, s=1.0):
    pts = [
        (cx, cy-int(105*s)), (cx+int(82*s), cy-int(62*s)),
        (cx+int(68*s), cy+int(42*s)), (cx, cy+int(105*s)),
        (cx-int(68*s), cy+int(42*s)), (cx-int(82*s), cy-int(62*s)),
    ]
    draw.line(pts + [pts[0]], fill=NAVY, width=max(5, int(8*s)), joint="curve")
    draw.line((cx-int(38*s), cy, cx-int(8*s), cy+int(30*s)), fill=TEAL, width=max(5, int(8*s)))
    draw.line((cx-int(8*s), cy+int(30*s), cx+int(50*s), cy-int(42*s)), fill=TEAL, width=max(5, int(8*s)))


def draw_checklist(draw, cx, cy, s=1.0):
    stroke = max(5, int(7*s))
    draw.rounded_rectangle((cx-int(105*s), cy-int(92*s), cx+int(105*s), cy+int(92*s)), radius=int(18*s), outline=NAVY, width=stroke)
    for off in (-48, 0, 48):
        y = cy + int(off*s)
        draw.line((cx-int(74*s), y, cx-int(56*s), y+int(18*s)), fill=TEAL, width=stroke)
        draw.line((cx-int(56*s), y+int(18*s), cx-int(30*s), y-int(14*s)), fill=TEAL, width=stroke)
        draw.line((cx-int(8*s), y, cx+int(68*s), y), fill=BLUE, width=stroke)


def draw_folder(draw, cx, cy, s=1.0):
    stroke = max(5, int(7*s))
    draw.rounded_rectangle((cx-int(110*s), cy-int(58*s), cx+int(110*s), cy+int(72*s)), radius=int(18*s), outline=NAVY, width=stroke)
    draw.rounded_rectangle((cx-int(92*s), cy-int(92*s), cx-int(18*s), cy-int(54*s)), radius=int(10*s), fill=TEAL)
    for off in (-18, 18):
        y = cy + int(off*s)
        draw.line((cx-int(62*s), y, cx+int(62*s), y), fill=BLUE, width=stroke)


def draw_bell(draw, cx, cy, s=1.0):
    stroke = max(5, int(7*s))
    box = (cx-int(82*s), cy-int(92*s), cx+int(82*s), cy+int(70*s))
    draw.arc(box, 200, 340, fill=NAVY, width=stroke)
    draw.arc(box, 20, 160, fill=NAVY, width=stroke)
    draw.line((cx-int(72*s), cy+int(34*s), cx+int(72*s), cy+int(34*s)), fill=NAVY, width=stroke)
    draw.ellipse((cx-int(13*s), cy+int(45*s), cx+int(13*s), cy+int(71*s)), fill=TEAL)


def draw_text_icon(draw, cx, cy, s=1.0):
    big = font(FONT_BOLD, max(48, int(104*s)))
    small = font(FONT_REG, max(30, int(54*s)))
    draw.text((cx-int(92*s), cy-int(80*s)), "Aa", font=big, fill=NAVY)
    draw.line((cx-int(92*s), cy+int(40*s), cx+int(92*s), cy+int(40*s)), fill=TEAL, width=max(5, int(8*s)))
    draw.text((cx-int(55*s), cy+int(50*s)), "Text", font=small, fill=BLUE)


def draw_sparkle(draw, cx, cy, s=1.0):
    stroke = max(5, int(7*s))
    r = int(100*s)
    draw.line((cx-r, cy, cx+r, cy), fill=NAVY, width=stroke)
    draw.line((cx, cy-r, cx, cy+r), fill=NAVY, width=stroke)
    d = int(70*s)
    draw.line((cx-d, cy-d, cx+d, cy+d), fill=TEAL, width=stroke)
    draw.line((cx-d, cy+d, cx+d, cy-d), fill=BLUE, width=stroke)
    for dx, dy in ((88, -68), (-88, 72)):
        rr = int(14*s)
        draw.ellipse((cx+int(dx*s)-rr, cy+int(dy*s)-rr, cx+int(dx*s)+rr, cy+int(dy*s)+rr), fill=TEAL)


def draw_clock(draw, cx, cy, s=1.0):
    stroke = max(5, int(7*s))
    r = int(92*s)
    draw.ellipse((cx-r, cy-r, cx+r, cy+r), outline=NAVY, width=stroke)
    draw.line((cx, cy, cx, cy-int(48*s)), fill=TEAL, width=stroke)
    draw.line((cx, cy, cx+int(42*s), cy+int(28*s)), fill=BLUE, width=stroke)


def draw_key(draw, cx, cy, s=1.0):
    stroke = max(5, int(8*s))
    r = int(50*s)
    draw.ellipse((cx-int(82*s)-r, cy-r, cx-int(82*s)+r, cy+r), outline=NAVY, width=stroke)
    draw.line((cx-int(32*s), cy, cx+int(108*s), cy), fill=NAVY, width=stroke)
    draw.line((cx+int(55*s), cy, cx+int(55*s), cy+int(35*s)), fill=TEAL, width=stroke)
    draw.line((cx+int(88*s), cy, cx+int(88*s), cy+int(28*s)), fill=TEAL, width=stroke)


def draw_magnifier(draw, cx, cy, s=1.0):
    stroke = max(5, int(8*s))
    r = int(70*s)
    draw.ellipse((cx-r-int(22*s), cy-r-int(22*s), cx+r-int(22*s), cy+r-int(22*s)), outline=NAVY, width=stroke)
    draw.line((cx+int(28*s), cy+int(28*s), cx+int(108*s), cy+int(108*s)), fill=TEAL, width=stroke)


def draw_symbol(draw: ImageDraw.ImageDraw, symbol: str, category: str, cx: int, cy: int, s: float = 1.0) -> None:
    text = f"{symbol} {category}".lower()
    if re.search(r"text|font|type|read", text):
        draw_text_icon(draw, cx, cy, s)
    elif re.search(r"bell|notification|alert", text):
        draw_bell(draw, cx, cy, s)
    elif re.search(r"shield|security|scam|privacy|lock", text):
        draw_shield(draw, cx, cy, s)
    elif re.search(r"checklist|list|steps|to-do|todo", text):
        draw_checklist(draw, cx, cy, s)
    elif re.search(r"folder|file|organize|organization", text):
        draw_folder(draw, cx, cy, s)
    elif re.search(r"magnif|search|zoom", text):
        draw_magnifier(draw, cx, cy, s)
    elif re.search(r"clock|timer|time|calendar", text):
        draw_clock(draw, cx, cy, s)
    elif re.search(r"key|password|passcode|code", text):
        draw_key(draw, cx, cy, s)
    elif re.search(r"ai|spark|magic|assistant", text):
        draw_sparkle(draw, cx, cy, s)
    else:
        draw_phone(draw, cx, cy, s)


def support_box(draw, supporting_text, x1, y1, x2, y2):
    draw.rounded_rectangle((x1, y1, x2, y2), radius=30, fill=PALE)
    fnt, lines = fitted_lines(draw, supporting_text, x2-x1-70, 3, 40, 32, bold=False)
    line_h = max(46, fnt.size + 10)
    total_h = line_h * len(lines)
    y = y1 + (y2-y1-total_h)/2
    for line in lines:
        draw.text((x1+35, y), line, font=fnt, fill=NAVY)
        y += line_h


def render(headline: str, supporting_text: str, category: str, symbol: str, output_path: str) -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    draw_brand(draw, category)

    # Main canvas.
    draw.rounded_rectangle((72, 238, 1008, 978), radius=52, fill=WHITE)

    category_key = category.lower()
    ordered = list(CATEGORY_LABELS)
    variant = ordered.index(category_key) % 4 if category_key in ordered else 0

    # Keep every layout on a consistent grid while moving the visual emphasis.
    if variant == 0:
        # Headline left, visual right.
        draw.rounded_rectangle((740, 312, 940, 512), radius=42, fill=PALE)
        draw_symbol(draw, symbol, category, 840, 412, 0.72)
        hfont, hlines = fitted_lines(draw, headline, 560, 3, 74, 58, bold=True)
        y = 322
        for line in hlines:
            draw.text((118, y), line, font=hfont, fill=NAVY)
            y += hfont.size + 14
        draw.rounded_rectangle((118, y+18, 250, y+30), radius=6, fill=TEAL)
        support_box(draw, supporting_text, 118, 690, 940, 882)

    elif variant == 1:
        # Visual left, headline right.
        draw.rounded_rectangle((118, 322, 372, 576), radius=48, fill=SAND)
        draw_symbol(draw, symbol, category, 245, 449, 0.86)
        hfont, hlines = fitted_lines(draw, headline, 510, 3, 72, 56, bold=True)
        y = 330
        for line in hlines:
            draw.text((420, y), line, font=hfont, fill=NAVY)
            y += hfont.size + 14
        draw.rounded_rectangle((420, y+18, 552, y+30), radius=6, fill=TEAL)
        support_box(draw, supporting_text, 118, 690, 940, 882)

    elif variant == 2:
        # Centered icon and headline for warning/confidence topics.
        draw.ellipse((440, 292, 640, 492), fill=PALE)
        draw_symbol(draw, symbol, category, 540, 392, 0.70)
        hfont, hlines = fitted_lines(draw, headline, 800, 2, 74, 58, bold=True)
        y = draw_centered_lines(draw, hlines, hfont, 540, 535, NAVY, hfont.size + 14)
        draw.rounded_rectangle((474, y+12, 606, y+24), radius=6, fill=TEAL)
        support_box(draw, supporting_text, 118, 748, 940, 898)

    else:
        # Large headline with a smaller topic symbol anchored at lower right.
        hfont, hlines = fitted_lines(draw, headline, 790, 3, 78, 60, bold=True)
        y = 330
        for line in hlines:
            draw.text((118, y), line, font=hfont, fill=NAVY)
            y += hfont.size + 15
        draw.rounded_rectangle((118, y+18, 250, y+30), radius=6, fill=TEAL)
        support_box(draw, supporting_text, 118, 645, 720, 872)
        draw.rounded_rectangle((758, 650, 940, 872), radius=42, fill=PALE)
        draw_symbol(draw, symbol, category, 849, 761, 0.68)

    # Quiet footer signature.
    footer = font(FONT_BOLD, 22)
    draw.text((92, 1015), "@DigitalCalmDaily", font=footer, fill=MUTED)
    draw.ellipse((946, 1018, 958, 1030), fill=TEAL)
    draw.ellipse((968, 1018, 980, 1030), fill=BLUE)
    draw.ellipse((990, 1018, 1002, 1030), fill=NAVY)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=95, optimize=True)


def main() -> None:
    if len(sys.argv) != 6:
        raise SystemExit("Usage: render_post.py HEADLINE SUPPORTING_TEXT CATEGORY VISUAL_SYMBOL OUTPUT_PATH")
    render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5])


if __name__ == "__main__":
    main()
