"""
Run this ONCE (locally or in a manual workflow step) to generate a set of
branded background templates for Black Tie Intel. These are saved to
assets/templates/ and reused every day — the daily job only overlays text,
it never regenerates backgrounds. This keeps the pipeline free, fast, and
independent of any image-gen API.

Usage: python3 scripts/generate_templates.py
"""

from PIL import Image, ImageDraw
import os
import math
import random

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "assets", "templates")
os.makedirs(OUT_DIR, exist_ok=True)

W, H = 1080, 1350  # Instagram 4:5 portrait — takes up more feed real estate than square

# Black Tie Intel palette: near-black base, charcoal accents, muted gold highlight
BLACK = (10, 10, 12)
CHARCOAL = (24, 24, 28)
GOLD = (191, 155, 90)
GOLD_DIM = (110, 90, 55)


def vertical_gradient(draw, top_color, bottom_color, w, h, y_offset=0, height=None):
    height = height or h
    for y in range(height):
        t = y / height
        r = int(top_color[0] * (1 - t) + bottom_color[0] * t)
        g = int(top_color[1] * (1 - t) + bottom_color[1] * t)
        b = int(top_color[2] * (1 - t) + bottom_color[2] * t)
        draw.line([(0, y + y_offset), (w, y + y_offset)], fill=(r, g, b))


def add_gold_frame(draw, w, h, margin=48, width=2):
    draw.rectangle(
        [margin, margin, w - margin, h - margin],
        outline=GOLD_DIM,
        width=width,
    )


def add_corner_ticks(draw, w, h, margin=48, tick=36, width=2):
    # subtle luxury-brand corner accents
    corners = [
        (margin, margin, 1, 1),
        (w - margin, margin, -1, 1),
        (margin, h - margin, 1, -1),
        (w - margin, h - margin, -1, -1),
    ]
    for x, y, dx, dy in corners:
        draw.line([(x, y), (x + tick * dx, y)], fill=GOLD, width=width)
        draw.line([(x, y), (x, y + tick * dy)], fill=GOLD, width=width)


def template_solid(name):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    add_gold_frame(d, W, H)
    add_corner_ticks(d, W, H)
    img.save(os.path.join(OUT_DIR, f"{name}.png"))


def template_gradient(name):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    vertical_gradient(d, CHARCOAL, BLACK, W, H)
    add_gold_frame(d, W, H)
    add_corner_ticks(d, W, H)
    img.save(os.path.join(OUT_DIR, f"{name}.png"))


def template_split(name):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, W, int(H * 0.38)], fill=CHARCOAL)
    d.line([(0, int(H * 0.38)), (W, int(H * 0.38))], fill=GOLD_DIM, width=2)
    add_gold_frame(d, W, H)
    add_corner_ticks(d, W, H)
    img.save(os.path.join(OUT_DIR, f"{name}.png"))


def template_radial(name):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    cx, cy = W // 2, int(H * 0.4)
    max_r = int(math.hypot(W, H))
    for r in range(max_r, 0, -6):
        t = r / max_r
        color = tuple(int(BLACK[i] * (1 - t) + CHARCOAL[i] * t) for i in range(3))
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    add_gold_frame(d, W, H)
    add_corner_ticks(d, W, H)
    img.save(os.path.join(OUT_DIR, f"{name}.png"))


def template_diagonal(name):
    img = Image.new("RGB", (W, H), BLACK)
    d = ImageDraw.Draw(img)
    d.polygon([(0, 0), (W, 0), (W, H * 0.55), (0, H * 0.75)], fill=CHARCOAL)
    add_gold_frame(d, W, H)
    add_corner_ticks(d, W, H)
    img.save(os.path.join(OUT_DIR, f"{name}.png"))


if __name__ == "__main__":
    template_solid("tpl_solid")
    template_gradient("tpl_gradient")
    template_split("tpl_split")
    template_radial("tpl_radial")
    template_diagonal("tpl_diagonal")
    print(f"Generated 5 templates in {OUT_DIR}")
