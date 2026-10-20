"""Generate today's Digital Calm Daily post and render its graphic."""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CENTRAL = ZoneInfo("America/Chicago")


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def main() -> None:
    raw = run([sys.executable, str(HERE / "generate_post.py")])
    data = json.loads(raw)

    today = dt.datetime.now(CENTRAL).strftime("%Y-%m-%d")
    relative_image_path = f"docs/dcd-posts/{today}.jpg"
    relative_caption_path = f"docs/dcd-posts/{today}.txt"
    relative_json_path = f"docs/dcd-posts/{today}.json"

    absolute_image_path = ROOT / relative_image_path
    absolute_caption_path = ROOT / relative_caption_path
    absolute_json_path = ROOT / relative_json_path

    run([
        sys.executable,
        str(HERE / "render_post.py"),
        data["headline"],
        data["supporting_text"],
        data["category"],
        data.get("visual_symbol", ""),
        str(absolute_image_path),
    ])

    hashtags = " ".join(data["hashtags"])
    caption = f"{data['caption'].strip()}\n\n{hashtags}\n"
    post_json = json.dumps(data, indent=2, ensure_ascii=False) + "\n"

    # Working files used by same-run publishing or Reel generation.
    (HERE / "_today_caption.txt").write_text(caption, encoding="utf-8")
    (HERE / "_today_image_path.txt").write_text(relative_image_path, encoding="utf-8")
    (HERE / "_today_post.json").write_text(post_json, encoding="utf-8")

    # Durable daily artifacts. These let an independent publisher retry later
    # without regenerating content or creating a duplicate topic.
    absolute_caption_path.write_text(caption, encoding="utf-8")
    absolute_json_path.write_text(post_json, encoding="utf-8")

    run([
        sys.executable,
        str(HERE / "render_reel.py"),
        str(HERE / "_today_post.json"),
    ])

    print(f"Category: {data['category']}")
    print(f"Topic: {data['topic']}")
    print(f"Headline: {data['headline']}")
    print(f"Image: {relative_image_path}")
    print(f"Caption: {relative_caption_path}")
    print(f"Post JSON: {relative_json_path}")
    reel_path = (HERE / "_today_reel_path.txt").read_text(encoding="utf-8").strip()
    print(f"Quick how-to Reel: {reel_path or 'not applicable'}")


if __name__ == "__main__":
    main()
