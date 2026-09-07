"""
Calls the Claude API to generate today's quote based on Config/themes.json.
Also checks a running history log to avoid repeating a quote.

Usage: python3 scripts/generate_quote.py
Requires env var: ANTHROPIC_API_KEY
Prints JSON to stdout: {"quote": "...", "theme": "...", "day": "monday"}
"""

import os
import sys
import json
import datetime

import anthropic

HERE = os.path.dirname(__file__)
THEMES_PATH = os.path.join(HERE, "..", "Config", "themes.json")
HISTORY_PATH = os.path.join(HERE, "..", "Config", "quote_history.json")


def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH) as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_PATH, "w") as f:
        json.dump(history[-200:], f, indent=2)  # keep last 200 to avoid unbounded growth


def main():
    with open(THEMES_PATH) as f:
        themes = json.load(f)

    today = datetime.datetime.utcnow().strftime("%A").lower()
    day_config = themes[today]
    history = load_history()
    recent_quotes = [h["quote"] for h in history[-30:]]  # avoid repeats from last ~month

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env automatically

    avoid_block = ""
    if recent_quotes:
        avoid_block = (
            "\n\nDo not repeat or closely rephrase any of these recent quotes:\n- "
            + "\n- ".join(recent_quotes)
        )

    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=200,
        messages=[
            {
                "role": "user",
                "content": day_config["prompt"] + avoid_block,
            }
        ],
    )

    quote_text = "".join(
        block.text for block in message.content if block.type == "text"
    ).strip().strip('"')

    result = {
        "day": today,
        "theme": day_config["theme"],
        "quote": quote_text,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    history.append({"quote": quote_text, "day": today, "date": result["generated_at"]})
    save_history(history)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
