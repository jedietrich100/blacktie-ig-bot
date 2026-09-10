"""
Takes the day's quote + theme and overlays it onto a randomly chosen
template from assets/templates/. Outputs a final 1080x1350 PNG to
docs/posts/YYYY-MM-DD.png (docs/ is served via raw.githubusercontent.com
so Instagram's API can fetch it by URL).

Usage: python3 scripts/render_post.py "<quote text>" "<theme label>" "<output_path>"
"""

import sys
import os
import random
import textwrap
from PIL import Image, ImageDraw, ImageFont

TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "templates")
SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SERIF = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"

GOLD = (191, 155, 90)
OFFWHITE = (235, 233, 228)

W, H = 1080, 1350


def fit_font_size(draw, text, font_path, max_width, max_height, start_size=64, min_size=28):
    size = start_size
    while size > min_size:
        font = ImageFont.truetype(font_path, size)
        wrapped = wrap_text(text, font, draw, max_width)
        line_height = size * 1.35
        total_height = line_height * len(wrapped)
        if total_height <= max_height:
            widest = max(draw.textlength(line, font=font) for line in wrapped)
            if widest <= max_width:
                return font, wrapped, line_height
        size -= 2
    font = ImageFont.truetype(font_path, min_size)
    return font, wrap_text(text, font, draw, max_width), min_size * 1.35


def wrap_text(text, font, draw, max_width):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = f"{current} {word}".strip()
        if draw.textlength(trial, font=font) <= max_width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render(quote_text, theme_label, output_path, brand_name="BLACK TIE INTEL"):
    templates = [f for f in os.listdir(TEMPLATES_DIR) if f.endswith(".png")]
    chosen = random.choice(templates)
    img = Image.open(os.path.join(TEMPLATES_DIR, chosen)).convert("RGB")
    draw = ImageDraw.Draw(img)

    content_margin = 130
    max_text_width = W - (content_margin * 2)
    max_text_height = H * 0.5

    font, lines, line_height = fit_font_size(
        draw, quote_text, SERIF_BOLD, max_text_width, max_text_height,
        start_size=76, min_size=34,
    )

    total_text_height = line_height * len(lines)
    start_y = (H / 2) - (total_text_height / 2)

    # opening/closing quotation marks for visual flourish
    mark_font = ImageFont.truetype(SERIF_BOLD, 90)
    draw.text((content_margin - 10, start_y - 70), "\u201c", font=mark_font, fill=GOLD)

    y = start_y
    for line in lines:
        line_width = draw.textlength(line, font=font)
        x = (W - line_width) / 2
        draw.text((x, y), line, font=font, fill=OFFWHITE)
        y += line_height

    # theme label above the quote
    label_font = ImageFont.truetype(SANS, 30)
    label_text = theme_label.upper()
    label_width = draw.textlength(label_text, font=label_font)
    draw.text(((W - label_width) / 2, start_y - 170), label_text, font=label_font, fill=GOLD)

    # small rule under label
    rule_w = 60
    draw.line(
        [((W - rule_w) / 2, start_y - 120), ((W + rule_w) / 2, start_y - 120)],
        fill=GOLD, width=2,
    )

    # brand wordmark at bottom
    brand_font = ImageFont.truetype(SANS, 28)
    brand_width = draw.textlength(brand_name, font=brand_font)
    draw.text(((W - brand_width) / 2, H - 140), brand_name, font=brand_font, fill=GOLD)

    os.makedirs(os.path.dirname(output_path), exist_ok=img.convert("RGB").save(output_path, "JPEG", quality=95) 
    print(f"Rendered post using {chosen} -> {output_path}")
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: render_post.py '<quote>' '<theme label>' '<output_path>'")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2], sys.argv[3])
