"""Read-only audit of Circus Peanuts Instagram posts against publication ledgers.

Never publishes, refreshes credentials, or rewrites state. A failed audit does not
prove a missing post; it means the live post and matching receipt were not confirmed.
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

ROOT = Path(__file__).resolve().parents[1]
ZONE = ZoneInfo("America/Chicago")
API = "https://graph.instagram.com/v26.0"
ACCOUNT = "circuspeanutsdaily"


def report_date(value=None, now=None):
    if value:
        day = dt.date.fromisoformat(value)
        if day.isoformat() != value:
            raise ValueError("Audit date must be YYYY-MM-DD")
        return day
    return (now or dt.datetime.now(ZONE)).astimezone(ZONE).date() - dt.timedelta(days=1)


def instagram_get(path, token, params):
    response = requests.get(API + "/" + path, headers={"Authorization": "Bearer " + token},
                            params=params, timeout=45)
    if not response.ok:
        try:
            error = response.json().get("error", {})
        except (ValueError, AttributeError):
            error = {}
        code = error.get("code")
        if response.status_code == 401 or code == 190:
            raise RuntimeError("Circus Peanuts Instagram access has expired or been revoked "
                               f"(HTTP {response.status_code}, code {code}). "
                               "Reauthorize @circuspeanutsdaily through the existing Instagram Login "
                               "app and replace only GitHub Actions secret CIRCUS_IG_ACCESS_TOKEN. "
                               "No publication or token change was attempted.")
        raise RuntimeError(f"Circus Instagram read-only audit failed: HTTP {response.status_code}, code {code}")
    return response.json()


def live_media(token, user):
    if not token or not user.isdigit():
        raise RuntimeError("Circus-specific Instagram token or numeric user ID missing")
    account = instagram_get("me", token, {"fields": "user_id,username,id"})
    if account.get("username") != ACCOUNT or str(account.get("user_id") or account.get("id")) != user:
        raise RuntimeError("Instagram access belongs to a different account; Circus audit blocked")
    result = instagram_get(user + "/media", token, {
        "fields": "id,timestamp,permalink,caption,media_type,media_product_type", "limit": 100})
    if not isinstance(result.get("data"), list):
        raise RuntimeError("Instagram did not return a usable recent-media list")
    return result["data"]


def on_day(row, day):
    timestamp = row.get("timestamp")
    if not isinstance(timestamp, str):
        raise RuntimeError("Instagram recent media omitted a timestamp; cannot verify safely")
    return dt.datetime.fromisoformat(timestamp.replace("Z", "+00:00")).astimezone(ZONE).date() == day


def receipt_matches(receipt, media):
    return (receipt.get("state") == "published" and
            str(receipt.get("media_id", "")) == str(media.get("id", "")) and
            bool(receipt.get("permalink")) and bool(receipt.get("verified_at")))


def assess(day, image_ledger, reel_state, rows):
    """Return per-format results. Never infer missing posts merely from ledger gaps."""
    key = day.isoformat()
    images = []
    reels = []
    unidentified_reels = []
    for row in rows:
        if not on_day(row, day):
            continue
        if row.get("media_product_type") == "REELS":
            if "Circus reel · " + key in row.get("caption", ""):
                reels.append(row)
            else:
                unidentified_reels.append(row)
        elif row.get("media_type") in ("IMAGE", "CAROUSEL_ALBUM"):
            if "Morning coffee with Luna Grace." not in row.get("caption", ""):
                images.append(row)
        else:
            raise RuntimeError("Unexpected same-day Instagram media type; audit needs review")
    image_receipt = image_ledger.get(key, {})
    reel_receipt = reel_state.get("jobs", {}).get(key, {})
    if not isinstance(image_receipt, dict) or not isinstance(reel_receipt, dict):
        raise RuntimeError("Malformed Circus publishing ledger entries")

    def result(media, receipt, label):
        if len(media) > 1:
            return False, f"{label}: multiple matching live posts; review for duplicates before any recovery"
        if media:
            post = media[0]
            url = post.get("permalink", post.get("id", "unknown"))
            if receipt_matches(receipt, post):
                return True, f"{label}: CONFIRMED LIVE with matching verified ledger receipt — {url}"
            return False, f"{label}: LIVE ({url}) but missing or mismatched verified ledger receipt; reconcile, do not repost"
        return False, f"{label}: not confirmed in Instagram's latest 100 items; do not backfill without review"

    image = result(images, image_receipt, "Daily image")
    reel = result(reels, reel_receipt, "Evening Reel")
    if unidentified_reels and not reels:
        reel = (False, reel[1] + f" ({len(unidentified_reels)} unmarked same-day Reel(s) also need inspection)")
    return image, reel


def summarize(day, outcomes, problem=None):
    lines = [f"## Circus Peanuts publication audit — {day.isoformat()}", "",
             "Read-only check of the Instagram account AND repository receipts. "
             "A missing receipt is not proof that nothing was posted.", ""]
    if problem:
        lines.append("**Verification blocked:** " + str(problem))
    else:
        lines += ["- " + detail for _, detail in outcomes]
        lines.append("")
        lines.append("**Overall:** " + ("both live and ledger-verified" if all(ok for ok, _ in outcomes)
                                        else "attention required; no recovery attempted"))
    lines += ["", "This job never posts, backfills, purchases services, or alters any account.",
              "A GitHub Actions success on a skipped cron slot is not an Instagram publication receipt."]
    message = "\n".join(lines) + "\n"
    print(message)
    summary = os.getenv("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as stream:
            stream.write(message)


def main():
    day = report_date(os.getenv("AUDIT_DATE", "").strip())
    try:
        images = json.loads((ROOT / "circus/ledger.json").read_text(encoding="utf-8"))
        reels = json.loads((ROOT / "circus/reels/state.json").read_text(encoding="utf-8"))
        if not isinstance(images, dict) or not isinstance(reels, dict) or not isinstance(reels.get("jobs"), dict):
            raise RuntimeError("Circus ledgers are missing or malformed")
        rows = live_media(os.getenv("CIRCUS_IG_ACCESS_TOKEN", "").strip(),
                          os.getenv("CIRCUS_IG_USER_ID", "").strip())
        outcomes = assess(day, images, reels, rows)
        summarize(day, outcomes)
        if not all(ok for ok, _ in outcomes):
            raise SystemExit(2)
    except (RuntimeError, ValueError, requests.RequestException, OSError, KeyError) as exc:
        summarize(day, (), exc)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
