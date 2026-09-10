"""
Build today's Black Tie Intel post assets.

The GitHub Actions workflow handles committing the finished JPEG and publishing
it to Instagram after the public image URL is verified.
"""

import datetime
import json
import os
import subprocess
import sys

HERE = os.path.dirname(__file__)

THEME_CAPTIONS = {
    "Motivation & Mindset": (
        "Momentum is rarely dramatic. It is built in the decisions nobody applauds.",
        "#Mindset #Discipline #Momentum",
    ),
    "Cybersecurity Insight": (
        "Good security starts before the alert.",
        "#Cybersecurity #DigitalRisk #SecurityAwareness",
    ),
    "AI & Technology": (
        "The advantage goes to people who turn new technology into better judgment.",
        "#ArtificialIntelligence #Technology #AI",
    ),
    "Leadership & Strategy": (
        "Strategy becomes visible when a real decision has to be made.",
        "#Leadership #Strategy #DecisionMaking",
    ),
    "Future of Work & Innovation": (
        "Change rewards the people who prepare before adaptation becomes urgent.",
        "#FutureOfWork #Innovation #Technology",
    ),
    "Founder & Entrepreneur Grind": (
        "Building well is quieter than the internet makes it look.",
        "#Entrepreneurship #Founders #Business",
    ),
    "Reflection & Reset": (
        "Perspective is productive, too.",
        "#Reflection #Perspective #Reset",
    ),
}


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout)
        print(result.stderr, file=sys.stderr)
        raise RuntimeError(f"Command failed: {' '.join(cmd)}")
    return result.stdout.strip()


def build_caption(quote, theme):
    context_line, theme_tags = THEME_CAPTIONS.get(
        theme,
        ("Think clearly. Decide deliberately. Stay ahead.", "#Strategy #Business"),
    )

    return (
        f"{quote}\n\n"
        f"{context_line}\n\n"
        "What’s your read?\n\n"
        f"#BlackTieIntel {theme_tags}"
    )


def main():
    quote_json = run([sys.executable, os.path.join(HERE, "generate_quote.py")])
    data = json.loads(quote_json)
    quote, theme = data["quote"], data["theme"]

    today_str = datetime.datetime.utcnow().strftime("%Y-%m-%d")
    relative_image_path = f"docs/posts/{today_str}.jpg"
    absolute_image_path = os.path.join(HERE, "..", relative_image_path)

    run(
        [
            sys.executable,
            os.path.join(HERE, "render_post.py"),
            quote,
            theme,
            absolute_image_path,
        ]
    )

    caption = build_caption(quote, theme)

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
