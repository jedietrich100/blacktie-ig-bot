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
    absolute_image_path = ROOT / relative_image_path

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

    (HERE / "_today_caption.txt").write_text(caption, encoding="utf-8")
    (HERE / "_today_image_path.txt").write_text(relative_image_path, encoding="utf-8")
    (HERE / "_today_post.json").write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )

    print(f"Category: {data['category']}")
    print(f"Topic: {data['topic']}")
    print(f"Headline: {data['headline']}")
    print(f"Image: {relative_image_path}")


if __name__ == "__main__":
    main()
