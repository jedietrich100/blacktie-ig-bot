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
    "The Future of Power": (
        "Power is being redesigned—by systems that can see, decide, move, and scale.",
        "#FutureOfPower #AI #Robotics #StrategicIntelligence",
    ),
    "Tomorrow's World": (
        "The future becomes real when it changes how an ordinary day feels.",
        "#TomorrowsWorld #FutureCities #EmergingTechnology",
    ),
    "Autonomous Intelligence": (
        "The next AI question is not only what it knows, but what we allow it to do.",
        "#AIAgents #AutonomousAI #Trust #ArtificialIntelligence",
    ),
    "Global Intel": (
        "The most important shifts rarely respect borders—or arrive from only one direction.",
        "#GlobalIntel #TechnologyTrends #WorldInMotion",
    ),
    "The Human Question": (
        "As machines gain capability, human judgment becomes more—not less—consequential.",
        "#HumanFuture #TechnologyAndSociety #AI",
    ),
    "Signals": (
        "The edge often begins as a faint signal most people dismiss as noise.",
        "#Signals #EmergingTech #WhatToWatch",
    ),
    "The Long View": (
        "Headlines describe the moment. Direction reveals what the moment is becoming.",
        "#TheLongView #Future #AChangeInDirection",
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
        "Worth watching. What’s your read?\n\n"
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
