"""
Generate one original Black Tie Intel insight for today's editorial theme.

The prompt is intentionally strict: the image renderer works best with a short
single-sentence thought that has one clear tension and a memorable landing.
A minority of posts receive a subtle global perspective so the brand feels
world-aware without turning every post into geopolitical commentary.
"""

import datetime
import json
import os
import random
import re
import sys
import time
import unicodedata

import anthropic

HERE = os.path.dirname(__file__)
THEMES_PATH = os.path.join(HERE, "..", "Config", "themes.json")
HISTORY_PATH = os.path.join(HERE, "..", "Config", "quote_history.json")

MODEL = "claude-sonnet-5"
# One bounded application retry loop; SDK retries are disabled below.
TOKEN_BUDGETS = (256, 512, 512)
RETRY_DELAYS = (2, 4)
REQUEST_TIMEOUT = 30.0

STYLE_GUIDE = """
Black Tie Intel voice requirements:
- Return exactly ONE sentence and only the quote text.
- Aim for 9-18 words; never exceed 20 words.
- Make it sharp enough to stop a fast Instagram scroll.
- Prefer a useful tension, contrast, or unexpected insight over a generic slogan.
- Use confident, sophisticated language for curious people who want to understand where the world is going.
- The final few words should land with impact.
- Avoid clichés, motivational filler, buzzword soup, and constructions like "X isn't just Y".
- Never write generic advice about mindset, hustle, leadership, productivity, cybersecurity hygiene, or entrepreneurship.
- The reader should think: "I did not see it that way, and this may actually matter."
- Favor concrete forces and human consequences over vague words such as innovation, change, success, and future.
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
    text = text.strip('"“”').strip()
    return text


def quote_key(text):
    """Catch literal repeats despite case, spacing, or punctuation changes."""
    text = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.findall(r"\w+", text))


def response_summary(message):
    """Only emit bounded metadata, never prompts, quote text, or raw responses."""
    stop = getattr(message, "stop_reason", None)
    known_stops = {"end_turn", "max_tokens", "stop_sequence", "tool_use",
                   "pause_turn", "refusal", "model_context_window_exceeded"}
    blocks = getattr(message, "content", None)
    if not isinstance(blocks, list):
        blocks = []
    types = [getattr(block, "type", None) for block in blocks]
    usage = getattr(message, "usage", None)
    summary = {
        "stop_reason": stop if isinstance(stop, str) and stop in known_stops else "unknown",
        "content_blocks": len(blocks),
        "text_blocks": types.count("text"),
        "thinking_blocks": types.count("thinking"),
        "other_blocks": sum(kind not in ("text", "thinking") for kind in types),
    }
    for name in ("input_tokens", "output_tokens"):
        value = getattr(usage, name, None)
        if type(value) is int and 0 <= value <= 100_000_000:
            summary[name] = value
    return summary


def validate_quote(message, recent_quotes):
    blocks = getattr(message, "content", None)
    if not isinstance(blocks, list):
        return None, "invalid_content"
    parts = []
    for block in blocks:
        kind = getattr(block, "type", None)
        if not isinstance(kind, str):
            return None, "invalid_content"
        if kind == "text":
            value = getattr(block, "text", None)
            if not isinstance(value, str):
                return None, "invalid_content"
            parts.append(value)
        elif kind not in {"thinking", "redacted_thinking"}:
            return None, "unsupported_content"
    text = "".join(parts)
    quote = clean_quote(text)
    if not quote or not any(char.isalnum() for char in quote):
        return None, "empty_text"
    if "\n" in text.strip() or "\r" in text.strip():
        return None, "multiple_lines"
    if len(quote.split()) > 20:
        return None, "too_many_words"
    if quote_key(quote) in {quote_key(previous) for previous in recent_quotes}:
        return None, "duplicate_quote"
    return quote, None


def generate_quote(client, prompt, recent_quotes, sleep=None):
    """Retry generation only; no partial result or fallback may reach publishing."""
    if sleep is None:
        sleep = time.sleep
    for attempt, max_tokens in enumerate(TOKEN_BUDGETS, start=1):
        summary = {"attempt": attempt, "max_attempts": len(TOKEN_BUDGETS),
                   "max_tokens": max_tokens}
        retryable = True
        try:
            message = client.messages.create(
                model=MODEL, max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIConnectionError:
            reason = "connection_error"
        except anthropic.APIStatusError as error:
            status = error.status_code
            # Never include the SDK exception string/body/headers in logs.
            summary["http_status"] = status if type(status) is int else None
            retryable = type(status) is int and (status in {408, 409, 429} or 500 <= status <= 599)
            reason = "api_status_error"
        except anthropic.APIError:
            reason, retryable = "api_error", False
        else:
            summary.update(response_summary(message))
            if summary["stop_reason"] == "max_tokens":
                reason = "truncated_response"
            elif summary["stop_reason"] != "end_turn":
                reason, retryable = "incomplete_or_refused_response", False
            else:
                quote, reason = validate_quote(message, recent_quotes)
                if reason is None:
                    return quote
                if reason == "unsupported_content":
                    retryable = False

        summary["reason"] = reason
        summary["retrying"] = retryable and attempt < len(TOKEN_BUDGETS)
        print("QUOTE_GENERATION: " + json.dumps(summary, sort_keys=True), file=sys.stderr)
        if not summary["retrying"]:
            raise RuntimeError(f"Quote generation stopped after {attempt} attempt(s): {reason}") from None
        sleep(RETRY_DELAYS[attempt - 1])


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

    # Most posts should feel internationally aware; the explicit Global Intel
    # day always receives this lens.
    use_global_lens = day_config["theme"] == "Global Intel" or random.random() < 0.65
    global_block = f"\n\n{GLOBAL_LENS_GUIDE}" if use_global_lens else ""

    prompt = (
        f"{day_config['prompt']}\n\n"
        f"{STYLE_GUIDE}"
        f"{global_block}"
        f"{avoid_block}"
    )

    with anthropic.Anthropic(max_retries=0, timeout=REQUEST_TIMEOUT) as client:
        quote_text = generate_quote(client, prompt, recent_quotes)

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

