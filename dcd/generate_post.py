"""Generate one non-repetitive Digital Calm Daily Instagram post.

This intentionally favors evergreen guidance. If a topic would require current
fact-checking, the automation chooses a different evergreen topic instead.
"""

from __future__ import annotations

import datetime as dt
import difflib
import json
import os
import re
from pathlib import Path
from zoneinfo import ZoneInfo

import anthropic

HERE = Path(__file__).resolve().parent
HISTORY_PATH = HERE / "history.json"
CENTRAL = ZoneInfo("America/Chicago")

CATEGORY_BY_WEEKDAY = {
    0: "iPhone and Apple Tips",
    1: "AI Tips",
    2: "Scam and Cybersecurity",
    3: "Simple Tech How-Tos",
    4: "Digital Organization",
    5: "Useful Tech Tools",
    6: "Digital Confidence",
}

RECENTLY_USED_TOPICS = [
    "remove apps from the Home Screen and use the App Library",
    "turn a long email or message into a checklist with AI",
    "caller ID spoofing or don't trust caller ID",
    "scan paper into a PDF with the iPhone Notes app",
    "take a screenshot before changing a setting",
    "copy text from a photo with Live Text",
    "Text Replacement shortcuts on iPhone",
    "use iPhone Magnifier",
    "Back Tap on iPhone",
    "suspicious QR codes in unexpected packages",
    "lock an app with Face ID",
    "keep verification codes private",
    "merge duplicate photos",
    "close unused apps to speed up iPhone or save battery",
]

BASE_GUIDE = """
You write Digital Calm Daily, a faceless Instagram account for everyday adults,
especially older adults, who want technology to feel calmer and easier.

Create ONE post for the assigned category.

Editorial rules:
- Practical, useful, calm, friendly, and easy to understand.
- Never sound alarmist, salesy, condescending, or overly technical.
- The idea must be actionable in about 30-60 seconds.
- Favor evergreen tips. Do NOT make a current-events claim, breaking-news claim,
  product-launch claim, active scam-wave claim, or time-sensitive security claim.
- If a topic would need live verification, choose a different evergreen topic.
- Do not make unsupported security, privacy, battery, performance, health, or
  financial claims.
- Avoid absolute or overpromising language such as "every app", "always", "never",
  "guaranteed", "completely", or "no glasses required" unless literally and
  universally true. Prefer modest wording such as "many apps", "can help", or
  "may make text easier to read".
- For Apple/iPhone guidance, avoid version-specific menu paths unless the step is
  very stable; prefer tips that remain useful even if wording changes slightly.
- Do not repeat or lightly paraphrase a recent topic.
- Keep the account faceless.

Graphic rules:
- Headline: 3-6 words, maximum 42 characters.
- Supporting text: one or two short lines, maximum 105 characters total.
- Supporting text should explain the action, not repeat the headline.
- Supporting text must be accurate and modest; avoid universal claims.

Optional quick how-to Reel:
- Set create_quick_how_to_reel to true only when the same daily tip is clearer
  as a short visual sequence of 2-4 concrete actions.
- Good candidates include iPhone settings, simple app actions, AI prompts,
  digital organization, and useful-tool demonstrations.
- Set it to false for general encouragement, news, warnings, definitions, or
  any subject where a short demonstration would be forced or misleading.
- When true, reel_steps must contain 2-4 brief, accurate steps (maximum 58
  characters each) and reel_hook must be a useful 3-7 word promise.
- When false, return an empty reel_steps array and an empty reel_hook.

Caption rules:
- Start with: ⚡ TODAY’S 30-SECOND TECH WIN
- Use short paragraphs of 1-2 sentences.
- Put a blank line between every paragraph.
- Explain why the tip helps and exactly what to do.
- Use modest wording; do not overpromise.
- Near the end, include exactly: Save this tip for later.
- Then include exactly: Follow @DigitalCalmDaily for one simple 30-Second Tech Win every day.
- Do not include hashtags inside the caption field.

Hashtags:
- Return 5-8 relevant hashtags as a JSON array.
- Always include #DigitalCalmDaily and #TechMadeSimple.

Return ONLY valid JSON with these keys:
{
  "topic": "short plain-English topic description",
  "headline": "short graphic headline",
  "supporting_text": "exact on-image supporting text",
  "caption": "ready-to-post caption with real blank lines",
  "hashtags": ["#DigitalCalmDaily", "#TechMadeSimple", "..."],
  "visual_symbol": "one simple object or symbol that visually represents the tip",
  "create_quick_how_to_reel": true,
  "reel_hook": "short matching Reel hook",
  "reel_steps": ["First brief action", "Second brief action"]
}
""".strip()


def load_history() -> list[dict]:
    try:
        return json.loads(HISTORY_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_history(history: list[dict]) -> None:
    HISTORY_PATH.write_text(json.dumps(history[-120:], indent=2, ensure_ascii=False) + "\n")


def clean_json_text(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def similarity(a: str, b: str) -> float:
    a = re.sub(r"[^a-z0-9 ]+", " ", a.lower())
    b = re.sub(r"[^a-z0-9 ]+", " ", b.lower())
    a = " ".join(a.split())
    b = " ".join(b.split())
    return difflib.SequenceMatcher(None, a, b).ratio()


def validate(data: dict, recent: list[dict]) -> None:
    required = {
        "topic", "headline", "supporting_text", "caption", "hashtags",
        "visual_symbol", "create_quick_how_to_reel", "reel_hook", "reel_steps",
    }
    missing = required - set(data)
    if missing:
        raise ValueError(f"Missing fields: {sorted(missing)}")

    headline = str(data["headline"]).strip()
    supporting = str(data["supporting_text"]).strip()
    caption = str(data["caption"]).strip()
    hashtags = data["hashtags"]
    make_reel = data["create_quick_how_to_reel"]
    reel_hook = str(data["reel_hook"]).strip()
    reel_steps = data["reel_steps"]

    if not headline or len(headline) > 42:
        raise ValueError("Headline length invalid")
    if not supporting or len(supporting) > 105:
        raise ValueError("Supporting text length invalid")
    if not isinstance(hashtags, list) or not 5 <= len(hashtags) <= 8:
        raise ValueError("Need 5-8 hashtags")
    if not isinstance(make_reel, bool):
        raise ValueError("create_quick_how_to_reel must be true or false")
    if not isinstance(reel_steps, list):
        raise ValueError("reel_steps must be an array")
    if make_reel:
        if not reel_hook or len(reel_hook) > 48:
            raise ValueError("Reel hook length invalid")
        if not 2 <= len(reel_steps) <= 4:
            raise ValueError("A quick how-to Reel needs 2-4 steps")
        if any(not str(step).strip() or len(str(step).strip()) > 58 for step in reel_steps):
            raise ValueError("Each Reel step must be 1-58 characters")
    elif reel_hook or reel_steps:
        raise ValueError("Non-Reel posts must use an empty reel_hook and reel_steps")
    if "#DigitalCalmDaily" not in hashtags or "#TechMadeSimple" not in hashtags:
        raise ValueError("Required hashtags missing")
    if "Save this tip for later." not in caption:
        raise ValueError("Save CTA missing")
    if "Follow @DigitalCalmDaily for one simple 30-Second Tech Win every day." not in caption:
        raise ValueError("Follow CTA missing")

    claim_text = f"{supporting} {caption}".lower()
    blocked_claims = [
        "every app",
        "no glasses required",
        "guaranteed",
        "completely secure",
        "completely safe",
    ]
    for phrase in blocked_claims:
        if phrase in claim_text:
            raise ValueError(f"Overbroad or unsupported claim: {phrase}")

    candidate = f"{data['topic']} {headline}"
    for item in recent[-35:]:
        prior = f"{item.get('topic', '')} {item.get('headline', '')}"
        if prior.strip() and similarity(candidate, prior) >= 0.67:
            raise ValueError(f"Too similar to recent post: {prior}")


def generate_post() -> dict:
    now = dt.datetime.now(CENTRAL)
    category = CATEGORY_BY_WEEKDAY[now.weekday()]
    history = load_history()
    recent = history[-35:]

    recent_block = "\n".join(
        f"- {item.get('date', '')}: {item.get('topic', '')} | {item.get('headline', '')}"
        for item in recent
    ) or "- none yet"
    blocked_block = "\n".join(f"- {x}" for x in RECENTLY_USED_TOPICS)

    client = anthropic.Anthropic()
    last_error = None

    for attempt in range(1, 4):
        extra = ""
        if last_error:
            extra = f"\n\nThe previous attempt was rejected because: {last_error}. Choose a substantially different idea."

        prompt = f"""
{BASE_GUIDE}

TODAY'S CATEGORY: {category}
TODAY'S CENTRAL-TIME DATE: {now:%Y-%m-%d}

Do not use these recently covered ideas or close variants:
{blocked_block}

Recent generated posts to avoid repeating:
{recent_block}
{extra}
""".strip()

        message = client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1400,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = "".join(block.text for block in message.content if block.type == "text")
        try:
            data = json.loads(clean_json_text(raw))
            data["category"] = category
            validate(data, recent)
        except Exception as exc:  # retry with explicit feedback
            last_error = str(exc)
            continue

        record = {
            "date": now.strftime("%Y-%m-%d"),
            "category": category,
            "topic": data["topic"],
            "headline": data["headline"],
        }
        history.append(record)
        save_history(history)
        return data

    raise RuntimeError(f"Unable to generate a sufficiently fresh post after 3 attempts: {last_error}")


def main() -> None:
    print(json.dumps(generate_post(), ensure_ascii=False))


if __name__ == "__main__":
    main()
