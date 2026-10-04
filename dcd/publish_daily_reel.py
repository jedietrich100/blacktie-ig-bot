"""Publish today's optional DCD Reel once; stop on uncertain Buffer outcomes."""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from zoneinfo import ZoneInfo

import requests

from publish_buffer import discover_channel
from publish_buffer_reel import publish_reel

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("America/Chicago")
HISTORY_PATH = "dcd/reel_history.json"
LEDGER_PATH = "dcd/reel_ledger.json"


def now() -> dt.datetime:
    return dt.datetime.now(ZONE)


def publication_allowed(event: str, current: dt.datetime, today: str) -> bool:
    local = current.astimezone(ZONE)
    if local.date().isoformat() != today:
        return False
    if event == "workflow_dispatch":
        return True  # Preserve the existing explicitly requested manual path.
    return event == "schedule" and local.hour == 17 and local.minute >= 30


def git(*args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def refresh_main() -> None:
    if git("branch", "--show-current") != "main":
        raise RuntimeError("Reel publishing requires a fresh main checkout")
    git("pull", "--ff-only", "origin", "main")


def read_state() -> tuple[list[str], dict]:
    history_path = ROOT / HISTORY_PATH
    ledger_path = ROOT / LEDGER_PATH
    # Both files are tracked; missing/corrupt state must never look empty.
    history = json.loads(history_path.read_text(encoding="utf-8"))
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    if not isinstance(history, list) or not all(isinstance(day, str) for day in history):
        raise RuntimeError("Invalid Reel publication history; publishing blocked")
    if not isinstance(ledger, dict) or not all(isinstance(entry, dict) for entry in ledger.values()):
        raise RuntimeError("Invalid Reel submission ledger; publishing blocked")
    return history, ledger


def persist(history: list[str], ledger: dict, message: str) -> None:
    (ROOT / HISTORY_PATH).write_text(json.dumps(history[-120:], indent=2) + "\n", encoding="utf-8")
    (ROOT / LEDGER_PATH).write_text(json.dumps(ledger, indent=2) + "\n", encoding="utf-8")
    git("config", "user.name", "digital-calm-daily-bot")
    git("config", "user.email", "actions@users.noreply.github.com")
    git("add", HISTORY_PATH, LEDGER_PATH)
    if not git("diff", "--cached", "--name-only"):
        raise RuntimeError("Expected a durable Reel state change; refusing to continue")
    git("commit", "-m", message)
    # Retry Git persistence only. Never retry createPost after an uncertain reply.
    for attempt in range(3):
        git("pull", "--rebase", "origin", "main")
        try:
            git("push", "origin", "HEAD:main")
            return
        except subprocess.CalledProcessError:
            if attempt == 2:
                raise
            time.sleep(3)


def verify_video(video_url: str) -> None:
    for attempt in range(6):
        try:
            response = requests.get(video_url, timeout=30)
            if response.ok and response.content[4:8] == b"ftyp":
                return
        except requests.RequestException:
            pass
        if attempt < 5:
            time.sleep(5)
    raise RuntimeError("Reel MP4 is not publicly reachable; no submission made")


def main() -> None:
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    today = now().date().isoformat()
    if not publication_allowed(event, now(), today):
        print("Skipping outside today's Reel publishing window")
        return
    api_key = os.environ.get("DCD_BUFFER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DCD_BUFFER_API_KEY is not configured")

    # Concurrency serializes jobs; refreshing main prevents stale event SHAs from
    # hiding the receipt/reservation written by an earlier queued attempt.
    refresh_main()
    history, ledger = read_state()
    if today in history:
        print("Today's Reel was already submitted; skipping")
        return
    entry = ledger.get(today)
    if entry is not None:
        if entry.get("state") == "submitted" and entry.get("buffer_post_id"):
            history.append(today)
            persist(history, ledger, "DCD Reel: reconcile accepted submission " + today)
            print("Today's Reel has a Buffer receipt; history reconciled")
            return
        if entry.get("state") != "deferred":
            raise RuntimeError("Prior Reel submission needs reconciliation; refusing a blind duplicate retry")

    video_path = ROOT / "docs" / "dcd-reels" / (today + ".mp4")
    caption_path = video_path.with_suffix(".txt")
    if not video_path.is_file() or not caption_path.is_file():
        print("Today's message did not call for a quick how-to Reel")
        return
    caption = caption_path.read_text(encoding="utf-8")
    if not caption.strip():
        raise RuntimeError("Today's Reel caption is empty")
    video_commit = git("rev-parse", "HEAD")
    relative_video = video_path.relative_to(ROOT).as_posix()
    video_url = f"https://raw.githubusercontent.com/{os.environ['GITHUB_REPOSITORY']}/{video_commit}/{relative_video}"
    verify_video(video_url)
    channel_id = discover_channel(api_key)
    if not publication_allowed(event, now(), today):
        print("Skipping publication: Reel window closed during preparation")
        return

    # A durable reservation MUST reach origin before Buffer can receive a POST.
    # A timeout, crash, cancellation, or receipt-write failure leaves this state
    # blocking subsequent jobs until the actual Buffer result is reconciled.
    entry = {
        "state": "submitting",
        "channel_id": channel_id,
        "video_url": video_url,
        "caption_sha256": hashlib.sha256(caption.encode("utf-8")).hexdigest(),
        "reserved_at": now().isoformat(),
        "run_id": os.environ.get("GITHUB_RUN_ID"),
    }
    ledger[today] = entry
    persist(history, ledger, "DCD Reel: reserve submission " + today)
    if not publication_allowed(event, now(), today):
        # No Buffer mutation happened, so this reservation is safe to release.
        entry["state"] = "deferred"
        persist(history, ledger, "DCD Reel: defer outside publishing window " + today)
        print("Skipping publication: Reel window closed before submission")
        return

    try:
        post_id = publish_reel(api_key, channel_id, video_url, caption)
        if not post_id:
            raise RuntimeError("Buffer returned no post ID")
    except Exception as error:
        raise RuntimeError("Buffer outcome is uncertain; reservation retained. Inspect Buffer before any retry") from error
    entry.update(state="submitted", buffer_post_id=post_id, accepted_at=now().isoformat())
    history.append(today)
    persist(history, ledger, "DCD Reel: record accepted submission " + today)
    print("Buffer accepted today's Reel:", post_id)
    # Acceptance is not a claim that Instagram has finished publishing it.
    with open(os.environ.get("GITHUB_STEP_SUMMARY", os.devnull), "a", encoding="utf-8") as summary:
        summary.write("Digital Calm Daily Reel accepted by Buffer. Post ID: " + post_id + "\n")


if __name__ == "__main__":
    main()
