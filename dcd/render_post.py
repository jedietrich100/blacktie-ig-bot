"""Render a consistent Digital Calm Daily square Instagram graphic."""

from __future__ import annotations

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W = H = 1080
BG = (247, 244, 236)
NAVY = (24, 42, 61)
TEAL = (77, 148, 149)
BLUE = (126, 163, 190)
PALE = (232, 239, 236)
WHITE = (255, 255, 255)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt, max_width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    line = ""
    for word in words:
        test = word if not line else f"{line} {word}"
        box = draw.textbbox((0, 0), test, font=fnt)
        if box[2] - box[0] <= max_width:
            line = test
        else:
            if line:
                lines.append(line)
            line = word
    if line:
        lines.append(line)
    return lines


def draw_icon(draw: ImageDraw.ImageDraw, category: str, cx: int, cy: int) -> None:
    """Simple faceless line icons. No words."""
    c = category.lower()
    stroke = 8

    if "iphone" in c or "apple" in c:
        draw.rounded_rectangle((cx-70, cy-105, cx+70, cy+105), radius=24, outline=NAVY, width=stroke)
        draw.line((cx-20, cy+78, cx+20, cy+78), fill=NAVY, width=stroke)
    elif "ai" in c:
        for angle, radius in [(0, 90), (math.pi/2, 78), (math.pi/4, 54)]:
            x = cx + math.cos(angle) * radius
            y = cy + math.sin(angle) * radius
            r = 14
            draw.ellipse((x-r, y-r, x+r, y+r), fill=TEAL)
        draw.line((cx-90, cy, cx+90, cy), fill=NAVY, width=stroke)
        draw.line((cx, cy-90, cx, cy+90), fill=NAVY, width=stroke)
        draw.line((cx-60, cy-60, cx+60, cy+60), fill=BLUE, width=stroke)
    elif "scam" in c or "cyber" in c:
        pts = [(cx, cy-105), (cx+82, cy-65), (cx+68, cy+45), (cx, cy+105), (cx-68, cy+45), (cx-82, cy-65)]
        draw.polygon(pts, outline=NAVY)
        draw.line((cx-35, cy, cx-8, cy+28), fill=TEAL, width=stroke)
        draw.line((cx-8, cy+28, cx+48, cy-40), fill=TEAL, width=stroke)
    elif "organization" in c:
        draw.rounded_rectangle((cx-100, cy-65, cx+100, cy+70), radius=18, outline=NAVY, width=stroke)
        draw.rectangle((cx-82, cy-98, cx-10, cy-65), fill=TEAL)
        for y in (-28, 10, 48):
            draw.line((cx-62, cy+y, cx+60, cy+y), fill=BLUE, width=7)
    elif "tool" in c:
        draw.rounded_rectangle((cx-105, cy-50, cx+105, cy+70), radius=18, outline=NAVY, width=stroke)
        draw.arc((cx-42, cy-103, cx+42, cy-35), 180, 360, fill=TEAL, width=stroke)
        draw.line((cx-65, cy+10, cx+65, cy+10), fill=BLUE, width=8)
    elif "confidence" in c:
        draw.ellipse((cx-95, cy-95, cx+95, cy+95), outline=NAVY, width=stroke)
        draw.line((cx-48, cy+2, cx-12, cy+40), fill=TEAL, width=stroke)
        draw.line((cx-12, cy+40, cx+60, cy-48), fill=TEAL, width=stroke)
    else:
        # Simple how-to steps icon
        for idx, y in enumerate((cy-62, cy, cy+62), start=1):
            draw.ellipse((cx-92, y-22, cx-48, y+22), fill=TEAL)
            draw.line((cx-25, y, cx+92, y), fill=NAVY, width=8)


def render(headline: str, supporting_text: str, category: str, output_path: str) -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    # Calm visual frame and accent shapes.
    draw.rounded_rectangle((70, 70, 1010, 1010), radius=48, fill=WHITE)
    draw.ellipse((785, 55, 1035, 305), fill=PALE)
    draw.ellipse((55, 790, 250, 985), fill=(239, 242, 232))

    draw_icon(draw, category, 870, 205)

    headline_font = font(FONT_BOLD, 78)
    support_font = font(FONT_REG, 42)

    headline_lines = wrap_text(draw, headline, headline_font, 760)
    y = 260
    for line in headline_lines:
        draw.text((145, y), line, font=headline_font, fill=NAVY)
        y += 96

    draw.rounded_rectangle((145, y+30, 300, y+42), radius=6, fill=TEAL)
    y += 92

    support_lines = wrap_text(draw, supporting_text, support_font, 780)
    for line in support_lines:
        draw.text((145, y), line, font=support_font, fill=NAVY)
        y += 62

    # Decorative three-dot cadence marker, no extra text.
    dot_y = 890
    for i, color in enumerate((TEAL, BLUE, NAVY)):
        x = 145 + i * 32
        draw.ellipse((x, dot_y, x+14, dot_y+14), fill=color)

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out, "JPEG", quality=94, optimize=True)


def main() -> None:
    if len(sys.argv) != 5:
        raise SystemExit("Usage: render_post.py HEADLINE SUPPORTING_TEXT CATEGORY OUTPUT_PATH")
    render(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])


if __name__ == "__main__":
    main()
