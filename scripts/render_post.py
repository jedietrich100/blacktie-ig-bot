"""
Render a premium 1080x1350 Black Tie Intel Instagram card.

The template library provides the underlying visual texture. This renderer applies
one consistent "Luxury Executive" system on top: deeper contrast, cinematic
vignette, restrained gold accents, stronger typography, selective keyword
highlights, and a recognizable Black Tie Intel frame.

Usage:
    python3 scripts/render_post.py "<quote text>" "<theme label>" "<output_path>"
"""

import os
import random
import re
import sys

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

HERE = os.path.dirname(__file__)
TEMPLATES_DIR = os.path.join(HERE, "..", "assets", "templates")

SERIF_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
SANS = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"
SANS_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

W, H = 1080, 1350

# Black Tie Intel palette
GOLD = (205, 166, 84)
GOLD_SOFT = (177, 143, 75)
IVORY = (245, 242, 234)
MUTED = (174, 177, 181)
PANEL = (7, 10, 14, 188)
SHADOW = (0, 0, 0, 210)

STOPWORDS = {
    "about", "after", "again", "against", "before", "being", "between", "could",
    "does", "doing", "down", "during", "each", "from", "have", "having", "into",
    "itself", "just", "more", "most", "other", "over", "same", "some", "such",
    "than", "that", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "under", "until", "very", "what", "when", "where",
    "which", "while", "with", "would", "your", "still", "means", "made",
}

POWER_ROOTS = (
    "adapt", "advantage", "build", "clar", "courage", "decid", "decision",
    "disciplin", "execut", "focus", "future", "innov", "intellig", "leader",
    "momentum", "opportun", "protect", "risk", "secur", "strateg", "trust",
    "certainty", "design", "default", "action", "change", "technology",
    "automation", "founder", "signal", "leverage",
)


def normalize_word(word):
    return re.sub(r"[^a-z0-9'-]", "", word.lower())


def choose_highlights(text):
    """Pick 2-3 visually meaningful words without needing a second AI call."""
    scored = []
    seen = set()

    for index, token in enumerate(text.split()):
        clean = normalize_word(token)
        if not clean or clean in STOPWORDS or len(clean) < 5 or clean in seen:
            continue
        seen.add(clean)

        score = len(clean)
        if any(clean.startswith(root) or root in clean for root in POWER_ROOTS):
            score += 12

        # Favor words near the end slightly because they often carry the payoff.
        score += index * 0.15
        scored.append((score, clean))

    target = 2 if len(text.split()) <= 14 else 3
    return {word for _, word in sorted(scored, reverse=True)[:target]}


def wrap_text(text, font, draw, max_width):
    lines = []
    current = []

    for word in text.split():
        trial = " ".join(current + [word])
        if current and draw.textlength(trial, font=font) > max_width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)

    if current:
        lines.append(" ".join(current))
    return lines


def fit_quote(draw, text, max_width=760, max_height=520, start_size=86, min_size=46):
    for size in range(start_size, min_size - 1, -2):
        font = ImageFont.truetype(SERIF_BOLD, size)
        lines = wrap_text(text, font, draw, max_width)
        line_height = int(size * 1.27)
        total_height = line_height * len(lines)

        if len(lines) <= 5 and total_height <= max_height:
            return font, lines, line_height

    font = ImageFont.truetype(SERIF_BOLD, min_size)
    return font, wrap_text(text, font, draw, max_width), int(min_size * 1.27)


def draw_centered(draw, text, y, font, fill):
    width = draw.textlength(text, font=font)
    draw.text(((W - width) / 2, y), text, font=font, fill=fill)


def draw_spaced_center(draw, text, y, font, fill, spacing=5):
    chars = list(text)
    widths = [draw.textlength(ch, font=font) for ch in chars]
    total = sum(widths) + spacing * max(0, len(chars) - 1)
    x = (W - total) / 2

    for ch, width in zip(chars, widths):
        draw.text((x, y), ch, font=font, fill=fill)
        x += width + spacing


def add_luxury_treatment(img):
    """Darken the source template and add subtle cinematic depth."""
    img = img.resize((W, H), Image.Resampling.LANCZOS).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(0.58)
    img = ImageEnhance.Contrast(img).enhance(1.28)

    canvas = img.convert("RGBA")

    # Warm glow upper-right and cool shadow lower-left.
    glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    gd.ellipse((720, -180, 1260, 360), fill=(205, 166, 84, 42))
    gd.ellipse((-250, 900, 380, 1530), fill=(20, 35, 52, 80))
    glow = glow.filter(ImageFilter.GaussianBlur(95))
    canvas = Image.alpha_composite(canvas, glow)

    # Vertical vignette: transparent near the center, deeper at top/bottom.
    vignette = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    vd = ImageDraw.Draw(vignette)
    for y in range(H):
        distance = abs((y / H) - 0.5) * 2
        alpha = int(58 + 72 * distance)
        vd.line((0, y, W, y), fill=(0, 0, 0, alpha))
    canvas = Image.alpha_composite(canvas, vignette)

    return canvas


def draw_frame(draw):
    # Main luxury frame.
    draw.rounded_rectangle(
        (42, 42, W - 42, H - 42),
        radius=28,
        outline=(*GOLD_SOFT, 190),
        width=2,
    )

    # Short corner accents add visual energy without clutter.
    accent = 78
    for x1, y1, x2, y2 in (
        (42, 125, 42, 125 + accent),
        (W - 42, H - 125 - accent, W - 42, H - 125),
        (125, 42, 125 + accent, 42),
        (W - 125 - accent, H - 42, W - 125, H - 42),
    ):
        draw.line((x1, y1, x2, y2), fill=(*GOLD, 235), width=4)


def draw_quote_lines(draw, lines, font, line_height, start_y, highlights):
    """Center each line and render selected key words in gold."""
    space_width = draw.textlength(" ", font=font)

    for line_index, line in enumerate(lines):
        tokens = line.split()
        token_widths = [draw.textlength(token, font=font) for token in tokens]
        line_width = sum(token_widths) + space_width * max(0, len(tokens) - 1)
        x = (W - line_width) / 2
        y = start_y + line_index * line_height

        for token, token_width in zip(tokens, token_widths):
            clean = normalize_word(token)
            fill = GOLD if clean in highlights else IVORY

            # Restrained shadow for mobile readability.
            draw.text((x + 2, y + 3), token, font=font, fill=SHADOW)
            draw.text((x, y), token, font=font, fill=fill)
            x += token_width + space_width


def render(quote_text, theme_label, output_path, brand_name="BLACK TIE INTEL"):
    templates = [f for f in os.listdir(TEMPLATES_DIR) if f.lower().endswith(".png")]
    if not templates:
        raise RuntimeError(f"No templates found in {TEMPLATES_DIR}")

    chosen = random.choice(templates)
    img = Image.open(os.path.join(TEMPLATES_DIR, chosen))
    canvas = add_luxury_treatment(img)

    # Frosted-dark quote panel keeps every background legible.
    panel_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    pd = ImageDraw.Draw(panel_layer)
    pd.rounded_rectangle(
        (100, 320, W - 100, 1055),
        radius=34,
        fill=PANEL,
        outline=(*GOLD_SOFT, 92),
        width=2,
    )
    canvas = Image.alpha_composite(canvas, panel_layer)

    draw = ImageDraw.Draw(canvas)
    draw_frame(draw)

    # Brand lockup.
    brand_font = ImageFont.truetype(SANS_BOLD, 31)
    tagline_font = ImageFont.truetype(SANS, 17)
    draw_spaced_center(draw, brand_name, 92, brand_font, GOLD, spacing=4)
    draw_centered(draw, "DISCERN  •  ANALYZE  •  STAY AHEAD", 145, tagline_font, MUTED)

    # Theme badge.
    theme_font = ImageFont.truetype(SANS_BOLD, 22)
    theme_text = theme_label.upper()
    theme_width = draw.textlength(theme_text, font=theme_font)
    badge_x1 = (W - theme_width) / 2 - 28
    badge_x2 = (W + theme_width) / 2 + 28
    draw.rounded_rectangle(
        (badge_x1, 235, badge_x2, 285),
        radius=25,
        fill=(8, 10, 13, 215),
        outline=(*GOLD, 175),
        width=2,
    )
    draw_centered(draw, theme_text, 246, theme_font, GOLD)

    # Quote.
    quote_font, lines, line_height = fit_quote(draw, quote_text)
    total_height = len(lines) * line_height
    start_y = 600 - total_height / 2

    mark_font = ImageFont.truetype(SERIF_BOLD, 138)
    draw.text((145, 356), "“", font=mark_font, fill=(*GOLD, 235))

    highlights = choose_highlights(quote_text)
    draw_quote_lines(draw, lines, quote_font, line_height, start_y, highlights)

    # Signature separator and footer.
    draw.line((360, 955, 720, 955), fill=(*GOLD_SOFT, 135), width=2)
    footer_font = ImageFont.truetype(SANS_BOLD, 18)
    draw_centered(draw, "INTELLIGENCE FOR BETTER DECISIONS", 985, footer_font, MUTED)

    bottom_font = ImageFont.truetype(SANS, 18)
    draw_centered(draw, "@BLACKTIE_INTEL", H - 112, bottom_font, GOLD_SOFT)

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    canvas.convert("RGB").save(output_path, "JPEG", quality=95, optimize=True)

    print(
        f"Rendered Luxury Executive post using {chosen}; "
        f"highlighted={sorted(highlights)} -> {output_path}"
    )
    return output_path


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: render_post.py '<quote>' '<theme label>' '<output_path>'")
        sys.exit(1)
    render(sys.argv[1], sys.argv[2], sys.argv[3])
