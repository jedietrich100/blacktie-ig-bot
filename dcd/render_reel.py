"""Render an optional branded quick how-to Reel for today's DCD post."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CENTRAL = ZoneInfo("America/Chicago")

W, H = 720, 1280
BG = (247, 244, 236)
NAVY = (24, 42, 61)
TEAL = (77, 148, 149)
BLUE = (126, 163, 190)
PALE = (232, 239, 236)
WHITE = (255, 255, 255)
MUTED = (89, 105, 119)

FONT_BOLD = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
FONT_REG = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


def wrap(draw: ImageDraw.ImageDraw, text: str, fnt, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = word if not current else f"{current} {word}"
        if draw.textbbox((0, 0), candidate, font=fnt)[2] <= width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def fitted(draw: ImageDraw.ImageDraw, text: str, width: int, max_lines: int, start: int, minimum: int):
    for size in range(start, minimum - 1, -2):
        fnt = font(FONT_BOLD, size)
        lines = wrap(draw, text, fnt, width)
        if len(lines) <= max_lines:
            return fnt, lines
    fnt = font(FONT_BOLD, minimum)
    return fnt, wrap(draw, text, fnt, width)[:max_lines]


def centered(draw: ImageDraw.ImageDraw, lines: list[str], fnt, start_y: int, color=NAVY, gap=14):
    y = start_y
    for line in lines:
        box = draw.textbbox((0, 0), line, font=fnt)
        draw.text(((W - (box[2] - box[0])) / 2, y), line, font=fnt, fill=color)
        y += fnt.size + gap
    return y


def base_slide(label: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((42, 38, 190, 168), radius=28, fill=NAVY)
    tile_font = font(FONT_BOLD, 21)
    for index, word in enumerate(("DIGITAL", "CALM", "DAILY")):
        box = draw.textbbox((0, 0), word, font=tile_font)
        draw.text((116 - (box[2] - box[0]) / 2, 59 + index * 31), word,
                  font=tile_font, fill=WHITE if index != 1 else (154, 215, 205))
    draw.text((218, 61), "QUICK HOW-TO", font=font(FONT_BOLD, 27), fill=NAVY)
    draw.text((218, 104), "Simple tech. Less stress.", font=font(FONT_REG, 22), fill=MUTED)
    draw.rounded_rectangle((42, 205, 678, 1162), radius=44, fill=WHITE)
    draw.text((55, 1200), "@DigitalCalmDaily", font=font(FONT_BOLD, 21), fill=MUTED)
    draw.rounded_rectangle((535, 1199, 668, 1230), radius=15, fill=PALE)
    label_font = font(FONT_BOLD, 14)
    draw.text((551, 1206), label[:14].upper(), font=label_font, fill=NAVY)
    return img, draw


def render_hook(post: dict, path: Path) -> None:
    img, draw = base_slide("30-SECOND WIN")
    draw.ellipse((255, 310, 465, 520), fill=PALE)
    draw.rounded_rectangle((316, 346, 404, 490), radius=18, outline=NAVY, width=8)
    draw.line((342, 460, 378, 460), fill=TEAL, width=7)
    fnt, lines = fitted(draw, post["reel_hook"], 550, 3, 62, 46)
    y = centered(draw, lines, fnt, 590)
    draw.rounded_rectangle((270, y + 25, 450, y + 36), radius=6, fill=TEAL)
    sub = font(FONT_REG, 31)
    sub_lines = wrap(draw, post["headline"], sub, 520)
    centered(draw, sub_lines, sub, y + 75, MUTED, 10)
    img.save(path, "JPEG", quality=94)


def render_step(number: int, step: str, total: int, path: Path) -> None:
    img, draw = base_slide(f"STEP {number} OF {total}")
    draw.ellipse((275, 305, 445, 475), fill=PALE)
    number_font = font(FONT_BOLD, 82)
    text = str(number)
    box = draw.textbbox((0, 0), text, font=number_font)
    draw.text(((W - (box[2] - box[0])) / 2, 334), text, font=number_font, fill=TEAL)
    fnt, lines = fitted(draw, step, 550, 4, 58, 42)
    centered(draw, lines, fnt, 570)
    draw.rounded_rectangle((105, 880, 615, 955), radius=36, fill=PALE)
    prompt = "Pause here if you need a moment"
    prompt_font = font(FONT_REG, 23)
    pbox = draw.textbbox((0, 0), prompt, font=prompt_font)
    draw.text(((W - (pbox[2] - pbox[0])) / 2, 903), prompt, font=prompt_font, fill=MUTED)
    img.save(path, "JPEG", quality=94)


def render_cta(path: Path) -> None:
    img, draw = base_slide("SAVE THIS TIP")
    draw.ellipse((260, 335, 460, 535), fill=PALE)
    draw.line((320, 430, 350, 462), fill=TEAL, width=12)
    draw.line((350, 462, 410, 390), fill=NAVY, width=12)
    fnt, lines = fitted(draw, "You did it", 520, 2, 70, 52)
    y = centered(draw, lines, fnt, 610)
    follow = "Follow for one simple tech win every day."
    sub = font(FONT_REG, 31)
    centered(draw, wrap(draw, follow, sub, 520), sub, y + 55, MUTED, 10)
    img.save(path, "JPEG", quality=94)


def encode(slides: list[tuple[Path, float]], output: Path) -> None:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required to render a Reel")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as manifest:
        manifest_path = Path(manifest.name)
        for slide, duration in slides:
            manifest.write(f"file '{slide.as_posix()}'\n")
            manifest.write(f"duration {duration}\n")
        manifest.write(f"file '{slides[-1][0].as_posix()}'\n")
    try:
        subprocess.run([
            "ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0",
            "-i", str(manifest_path), "-vf", "fps=30,format=yuv420p",
            "-c:v", "libx264", "-preset", "medium", "-crf", "23",
            "-movflags", "+faststart", str(output),
        ], check=True)
    finally:
        manifest_path.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: render_reel.py POST_JSON")
    post = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    marker = HERE / "_today_reel_path.txt"
    if not post.get("create_quick_how_to_reel"):
        marker.write_text("", encoding="utf-8")
        print("This daily message does not need a quick how-to Reel.")
        return

    today = dt.datetime.now(CENTRAL).strftime("%Y-%m-%d")
    relative_video = f"docs/dcd-reels/{today}.mp4"
    relative_caption = f"docs/dcd-reels/{today}.txt"
    output = ROOT / relative_video
    steps = [str(step).strip() for step in post["reel_steps"]]

    with tempfile.TemporaryDirectory(prefix="dcd-reel-") as tmp:
        tmp_path = Path(tmp)
        slides: list[tuple[Path, float]] = []
        hook = tmp_path / "00-hook.jpg"
        render_hook(post, hook)
        slides.append((hook, 2.0))
        for index, step in enumerate(steps, start=1):
            slide = tmp_path / f"{index:02d}-step.jpg"
            render_step(index, step, len(steps), slide)
            slides.append((slide, 2.25))
        cta = tmp_path / "99-cta.jpg"
        render_cta(cta)
        slides.append((cta, 1.75))
        encode(slides, output)

    hashtags = " ".join(post["hashtags"])
    numbered = "\n".join(f"{i}. {step}" for i, step in enumerate(steps, start=1))
    caption = (
        f"⚡ QUICK HOW-TO\n\n{post['headline']}\n\n{numbered}\n\n"
        "Save this tip for later.\n\n"
        "Follow @DigitalCalmDaily for one simple 30-Second Tech Win every day.\n\n"
        f"{hashtags}\n"
    )
    caption_path = ROOT / relative_caption
    caption_path.write_text(caption, encoding="utf-8")
    marker.write_text(relative_video, encoding="utf-8")
    print(f"Reel: {relative_video}")


if __name__ == "__main__":
    main()
