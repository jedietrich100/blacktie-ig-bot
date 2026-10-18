"""Publish one immutable daily asset, with durable intent and fail-closed recovery.

The workflow serializes all Black Tie publication with one concurrency group.
Never retry an ambiguous publish result. Only Meta's explicit 9007/2207027
rejection permits a bounded retry of the same container after reconciliation.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import urllib.error
import urllib.parse
import urllib.request

BASE_URL = "https://graph.instagram.com/v26.0"
EXPECTED_ID = "17841434445662205"
EXPECTED_USERNAME = "blacktie_intel"
LEDGER = "Config/instagram_publish_ledger.json"
PUBLISH_DELAYS = (5, 10, 20, 40, 60)


class PublishError(RuntimeError):
    pass


class ApiError(PublishError):
    def __init__(self, status, code=None, subcode=None):
        self.status, self.code, self.subcode = status, code, subcode
        super().__init__(f"Instagram HTTP {status}; code={code}; subcode={subcode}")


def api_request(method, path, token, params=None, data=None):
    """Keep credentials in headers and never emit raw responses or request URLs."""
    url = BASE_URL + "/" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url, method=method,
        data=urllib.parse.urlencode(data).encode() if data is not None else None,
        headers={"Authorization": "Bearer " + token},
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read(2_000_001)
    except urllib.error.HTTPError as error:
        try:
            payload = json.loads(error.read(100_000)).get("error", {})
        except (ValueError, AttributeError):
            payload = {}
        raise ApiError(error.code, payload.get("code"), payload.get("error_subcode")) from None
    except (OSError, urllib.error.URLError):
        raise PublishError("Instagram request outcome is unknown; no automatic resubmission") from None
    if len(raw) > 2_000_000:
        raise PublishError("Instagram response exceeded safety limit")
    try:
        payload = json.loads(raw)
    except ValueError:
        raise PublishError("Instagram returned an unreadable response") from None
    if not isinstance(payload, dict) or "error" in payload:
        raise PublishError("Instagram returned an unexpected response")
    return payload


def timestamp(value):
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError()
        return parsed.astimezone(dt.timezone.utc)
    except (AttributeError, TypeError, ValueError):
        raise PublishError("Cannot validate media timestamp") from None


def validate_media(row, caption, day):
    if not re.fullmatch(r"\d+", str(row.get("id", ""))):
        raise PublishError("Missing published media ID")
    if row.get("caption", "").strip() != caption.strip():
        raise PublishError("Published caption does not match the reserved content")
    if timestamp(row.get("timestamp")).date() < dt.date.fromisoformat(day):
        raise PublishError("Published media predates the reserved daily post")
    if not re.fullmatch(r"https://www\.instagram\.com/(?:p|reel|tv)/[\w-]+/?", row.get("permalink", "")):
        raise PublishError("No verified Instagram permalink")
    return {key: row[key] for key in ("id", "permalink", "timestamp")}


def scan_media(token, caption, day):
    """Read complete recent pages through the target day; never guess on truncation."""
    target = dt.date.fromisoformat(day)
    after = None
    seen_cursors = set()
    matches, other_today = [], []
    previous_stamp = None
    for _ in range(20):
        params = {"fields": "id,caption,timestamp,permalink", "limit": 100}
        if after:
            params["after"] = after
        payload = api_request("GET", EXPECTED_ID + "/media", token, params=params)
        rows = payload.get("data")
        if not isinstance(rows, list):
            raise PublishError("Cannot inspect recent Instagram media")
        reached_older = False
        for row in rows:
            stamp = timestamp(row.get("timestamp"))
            if previous_stamp is not None and stamp > previous_stamp:
                raise PublishError("Recent-media ordering is ambiguous")
            previous_stamp = stamp
            if stamp.date() < target:
                reached_older = True
            elif row.get("caption", "").strip() == caption.strip():
                matches.append(validate_media(row, caption, day))
            elif stamp.date() == target:
                other_today.append(row.get("id"))
        paging = payload.get("paging", {})
        if reached_older or not paging.get("next"):
            if len(matches) > 1:
                raise PublishError("Multiple matching posts already exist; refusing further publication")
            return (matches[0] if matches else None), other_today
        after = paging.get("cursors", {}).get("after")
        if not rows or not isinstance(after, str) or not after or after in seen_cursors:
            raise PublishError("Recent-media pagination is incomplete")
        seen_cursors.add(after)
    raise PublishError("Recent-media scan limit reached; refusing to publish")


def container_status(token, container_id):
    payload = api_request("GET", container_id, token, params={"fields": "status_code,status"})
    status = payload.get("status_code")
    if status not in {"IN_PROGRESS", "FINISHED", "PUBLISHED", "ERROR", "EXPIRED"}:
        raise PublishError("Unknown media-container status")
    print(f"CONTAINER_STATUS: {container_id} {status}", flush=True)
    return status


def write_ledger(path, ledger):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(ledger, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temp.replace(path)


def commit_ledger(path):
    """Every pre-publication checkpoint must reach origin before the next POST."""
    branch = "main"
    subprocess.run(["git", "config", "user.name", "blacktie-bot"], check=True)
    subprocess.run(["git", "config", "user.email", "actions@users.noreply.github.com"], check=True)
    subprocess.run(["git", "add", "--", str(path)], check=True)
    if subprocess.run(["git", "diff", "--cached", "--quiet"]).returncode == 0:
        return
    subprocess.run(["git", "commit", "-m", "Black Tie: checkpoint publication state"], check=True)
    for attempt in range(3):
        subprocess.run(["git", "pull", "--rebase", "origin", branch], check=True)
        if subprocess.run(["git", "push", "origin", f"HEAD:{branch}"]).returncode == 0:
            return
        time.sleep(2 * (attempt + 1))
    raise PublishError("Ledger checkpoint did not reach origin; publication stopped")


def publish_once(image_url, caption, day, token, ledger_path=LEDGER,
                 checkpoint=commit_ledger, existing_container=None, sleep=time.sleep):
    if not token or not caption.strip():
        raise PublishError("Missing token or caption")
    dt.date.fromisoformat(day)
    account = api_request("GET", "me", token, params={"fields": "user_id,username,id"})
    account_id = str(account.get("user_id") or account.get("id") or "")
    if account_id != EXPECTED_ID or account.get("username") != EXPECTED_USERNAME:
        raise PublishError("Token does not resolve to the expected Black Tie account")
    print("ACCOUNT_VERIFIED: @" + EXPECTED_USERNAME, flush=True)
    path = Path(ledger_path)
    ledger = json.loads(path.read_text()) if path.exists() else {}
    if not isinstance(ledger, dict):
        raise PublishError("Invalid publication ledger")
    digest = hashlib.sha256(caption.encode()).hexdigest()
    identity = {"account_id": EXPECTED_ID, "image_url": image_url, "caption_sha256": digest}
    entry = ledger.get(day)
    if entry is not None:
        if not isinstance(entry, dict) or any(entry.get(k) != v for k, v in identity.items()):
            raise PublishError("Daily content differs from its durable reservation")
        if existing_container and entry.get("container_id") != existing_container:
            raise PublishError("Recovery container differs from its durable reservation")
    else:
        if existing_container:
            raise PublishError("Existing recovery container requires a trusted durable reservation")
        entry = {**identity, "status": "prepared"}
        if existing_container:
            entry["container_id"] = existing_container
        ledger[day] = entry

    def save(status=None, **values):
        if status:
            entry["status"] = status
        entry.update(values)
        entry["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
        write_ledger(path, ledger)
        if checkpoint:
            checkpoint(path)

    def reconcile():
        found, other = scan_media(token, caption, day)
        if found:
            if entry.get("media_id") and entry["media_id"] != found["id"]:
                raise PublishError("Receipt and feed media IDs disagree")
            save("published", media_id=found["id"], permalink=found["permalink"],
                 published_at=found["timestamp"])
            print("PUBLISHED_MEDIA_ID: " + found["id"], flush=True)
            print("PUBLISHED_PERMALINK: " + found["permalink"], flush=True)
            return found
        if other:
            raise PublishError("Black Tie already has other media for this date; refusing another post")
        return None

    found = reconcile()
    if found:
        return found
    if entry["status"] not in {"prepared", "ready_retry"}:
        raise PublishError("Prior outcome needs reconciliation; no automatic resubmission")
    save()
    if not entry.get("container_id"):
        save("creating")
        created = api_request("POST", EXPECTED_ID + "/media", token,
                              data={"image_url": image_url, "caption": caption})
        container_id = str(created.get("id", ""))
        if not re.fullmatch(r"\d+", container_id):
            raise PublishError("Container creation outcome is unknown")
        save("prepared", container_id=container_id)
    container_id = entry["container_id"]

    for attempt in range(len(PUBLISH_DELAYS) + 1):
        found = reconcile()
        if found:
            return found
        for poll in range(30):
            status = container_status(token, container_id)
            if status != "IN_PROGRESS":
                break
            if poll < 29:
                sleep(3)
        if status == "PUBLISHED":
            # The public feed can lag the container. Never re-submit this ID.
            for _ in range(3):
                sleep(5)
                found = reconcile()
                if found:
                    return found
            save("unknown")
            raise PublishError("Container is published but its media receipt is not yet visible")
        if status in {"ERROR", "EXPIRED"}:
            save("blocked", container_status=status)
            raise PublishError("Container cannot be published; preserve content for manual reconciliation")
        if status != "FINISHED":
            raise PublishError("Container readiness timed out without publishing")
        # Refresh the feed immediately before reserving this exact publish attempt.
        found = reconcile()
        if found:
            return found
        save("publishing", publish_attempt=entry.get("publish_attempt", 0) + 1)
        try:
            result = api_request("POST", EXPECTED_ID + "/media_publish", token,
                                 data={"creation_id": container_id})
        except ApiError as error:
            if error.status == 400 and error.code == 9007 and error.subcode == 2207027:
                save("ready_retry", last_error="9007/2207027")
                if attempt < len(PUBLISH_DELAYS):
                    sleep(PUBLISH_DELAYS[attempt])
                    continue
                raise PublishError("Publish readiness retry budget exhausted; same container preserved") from None
            save("unknown")
            found = reconcile()
            if found:
                return found
            raise PublishError("Publish failed; outcome preserved for reconciliation, not retried") from None
        except PublishError:
            save("unknown")
            found = reconcile()
            if found:
                return found
            raise
        media_id = str(result.get("id", ""))
        if not re.fullmatch(r"\d+", media_id):
            save("unknown")
            raise PublishError("Publish response has no valid media ID; do not resubmit")
        save("published_unverified", media_id=media_id)
        confirmed = api_request("GET", media_id, token,
                                params={"fields": "id,caption,permalink,timestamp"})
        if str(confirmed.get("id")) != media_id:
            raise PublishError("Published media readback ID differs")
        receipt = validate_media(confirmed, caption, day)
        save("published", permalink=receipt["permalink"], published_at=receipt["timestamp"])
        print("PUBLISHED_MEDIA_ID: " + media_id, flush=True)
        print("PUBLISHED_PERMALINK: " + receipt["permalink"], flush=True)
        return receipt
    raise PublishError("No publication result")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("image_url")
    parser.add_argument("caption")
    parser.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    parser.add_argument("--ledger", default=LEDGER)
    parser.add_argument("--commit-ledger", action="store_true")
    parser.add_argument("--existing-container")
    args = parser.parse_args()
    try:
        publish_once(args.image_url, args.caption, args.date, os.environ.get("IG_ACCESS_TOKEN", ""),
                     args.ledger, commit_ledger, args.existing_container)
    except (PublishError, ValueError, OSError, subprocess.CalledProcessError) as error:
        # Custom errors contain no request headers, raw API body, or credentials.
        print("STOP: " + (str(error) if isinstance(error, PublishError) else type(error).__name__), flush=True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
