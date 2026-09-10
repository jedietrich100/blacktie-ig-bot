"""
Orchestrates the daily generation step (everything EXCEPT the git commit/push
and the Instagram publish call, which are handled by the GitHub Actions
workflow so the image URL is guaranteed to be live before publishing).

Produces:
  - docs/posts/YYYY-MM-DD.png   (the rendered image)
  - scripts/_today_caption.txt  (caption text, read by the workflow)
  - scripts/_today_image_path.txt (relative path, read by the workflow)

Usage: python3 scripts/run_daily.py
"""

import json
import subprocess
import datetime
import os
import sys

HERE = os.path.dirname(__file__)


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def main():
    quote_json = run([sys.executable, os.path.join(HERE, "generate_quote.py")])
    data = json.loads(quote_json)
    quote, theme = data["quote"], data["theme"]

    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    relative_image_path = f"docs/posts/{today_str}.jpg"
    absolute_image_path = os.path.join(HERE, "..", relative_image_path)

    run([
        sys.executable,
        os.path.join(HERE, "render_post.py"),
        quote,
        theme,
        absolute_image_path,
    ])

    caption = f"{quote}\n\n— Black Tie Intel | {theme}"

    with open(os.path.join(HERE, "_today_caption.txt"), "w") as f:
        f.write(caption)
    with open(os.path.join(HERE, "_today_image_path.txt"), "w") as f:
        f.write(relative_image_path)

    print(f"Day: {data['day']}")
    print(f"Theme: {theme}")
    print(f"Quote: {quote}")
    print(f"Image: {relative_image_path}")


if __name__ == "__main__":
    main()
