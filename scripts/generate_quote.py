"""
Generate one original Black Tie Intel quote for today's editorial theme.

The prompt is intentionally strict: the image renderer works best with a short
single-sentence thought that has one clear tension and a memorable landing.
A minority of posts receive a subtle global perspective so the brand feels
world-aware without turning every post into geopolitical commentary.
"""

import datetime
import json
import os
import random

import anthropic

HERE = os.path.dirname(__file__)
THEMES_PATH = os.path.join(HERE, "..", "Config", "themes.json")
HISTORY_PATH = os.path.join(HERE, "..", "Config", "quote_history.json")

STYLE_GUIDE = """
Black Tie Intel voice requirements:
- Return exactly ONE sentence and only the quote text.
- Aim for 9-18 words; never exceed 20 words.
- Make it sharp enough to stop a fast Instagram scroll.
- Prefer a useful tension, contrast, or unexpected insight over a generic slogan.
- Use confident, sophisticated language suitable for executives, founders, and informed professionals.
- The final few words should land with impact.
- Avoid clichés, motivational filler, buzzword soup, and constructions like "X isn't just Y".
- No attribution, quotation marks, hashtags, emojis, labels, preamble, or explanation.
""".strip()

GLOBAL_LENS_GUIDE = """
Subtle global lens for this post:
- Widen the perspective beyond one company, city, or market.
- You may hint at international competition, interconnected systems, cross-border change, global technology, or broader strategic context.
- Keep it timeless and executive, not newsy or political.
- Do not name countries, politicians, wars, parties, or current events unless the day's base theme explicitly requires it.
- Do not use the words "global" or "world" just to force the concept; the perspective should feel natural.
""".strip()


def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH) as f:
            return json.load(f)
    return []


def save_history(history):
    with open(HISTORY_PATH, "w") as f:
        json.dump(history[-200:], f, indent=2)


def clean_quote(text):
    text = " ".join(text.strip().split())
    text = text.strip('"“”')
    return text


def main():
    with open(THEMES_PATH) as f:
        themes = json.load(f)

    today = datetime.datetime.utcnow().strftime("%A").lower()
    day_config = themes[today]
    history = load_history()
    recent_quotes = [h["quote"] for h in history[-40:]]

    avoid_block = ""
    if recent_quotes:
        avoid_block = (
            "\n\nDo not repeat, paraphrase, or reuse the central idea of these recent posts:\n- "
            + "\n- ".join(recent_quotes)
        )

    # About one in three posts gets the broader international/connected-systems
    # perspective. This keeps the global identity present but understated.
    use_global_lens = random.random() < 0.35
    global_block = f"\n\n{GLOBAL_LENS_GUIDE}" if use_global_lens else ""

    prompt = (
        f"{day_config['prompt']}\n\n"
        f"{STYLE_GUIDE}"
        f"{global_block}"
        f"{avoid_block}"
    )

    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-5",
        max_tokens=100,
        messages=[{"role": "user", "content": prompt}],
    )

    quote_text = clean_quote(
        "".join(block.text for block in message.content if block.type == "text")
    )

    word_count = len(quote_text.split())
    if not quote_text or word_count > 24 or "\n" in quote_text:
        raise RuntimeError(f"Generated quote failed format check: {quote_text!r}")

    result = {
        "day": today,
        "theme": day_config["theme"],
        "quote": quote_text,
        "global_lens": use_global_lens,
        "generated_at": datetime.datetime.utcnow().isoformat() + "Z",
    }

    history.append(
        {
            "quote": quote_text,
            "day": today,
            "date": result["generated_at"],
            "global_lens": use_global_lens,
        }
    )
    save_history(history)

    print(json.dumps(result))


if __name__ == "__main__":
    main()
