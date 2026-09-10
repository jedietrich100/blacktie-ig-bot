"""
Publishes an already-public image URL to Instagram using the Instagram API
with Instagram Login (graph.instagram.com endpoints – no Facebook Page needed).

Flow:
  1. Validate the access token and resolve the connected Instagram professional ID
  2. POST /{ig_user_id}/media         -> create a media container
  3. Poll /{container_id}             -> wait for FINISHED
  4. POST /{ig_user_id}/media_publish -> publish the container

Usage: python3 scripts/publish_instagram.py "<image_url>" "<caption>"
Requires env vars: IG_USER_ID, IG_ACCESS_TOKEN
"""

import os
import sys
import time
import requests

GRAPH_VERSION = "v26.0"
BASE_URL = f"https://graph.instagram.com/{GRAPH_VERSION}"
TRANSIENT_CODES = {429, 500, 502, 503, 504}


def resolve_ig_user_id(access_token, configured_id):
    """Validate the token and prefer the professional account ID returned by /me."""
    resp = requests.get(
        f"{BASE_URL}/me",
        params={
            "fields": "user_id,username,id",
            "access_token": access_token,
        },
        timeout=30,
    )
    print("ACCOUNT CHECK:", resp.status_code, resp.text)
    resp.raise_for_status()
    payload = resp.json()

    resolved_id = str(payload.get("user_id") or payload.get("id") or "").strip()
    if not resolved_id:
        raise RuntimeError("Instagram account check succeeded but returned no account ID")

    configured_id = str(configured_id or "").strip()
    if configured_id and configured_id != resolved_id:
        print(
            "Configured IG_USER_ID differs from the account ID returned by the token; "
            "using the token-resolved professional account ID."
        )

    username = payload.get("username")
    if username:
        print(f"Connected Instagram account: @{username}")

    return resolved_id


def create_container(ig_user_id, access_token, image_url, caption):
    # Give Meta several minutes to recover from transient code-2/5xx failures.
    delays = [15, 30, 60, 90, 120]
    for attempt in range(len(delays) + 1):
        resp = requests.post(
            f"{BASE_URL}/{ig_user_id}/media",
            data={
                "image_url": image_url,
                "caption": caption,
                "access_token": access_token,
            },
            timeout=60,
        )

        print("INSTAGRAM CREATE RESPONSE:", resp.status_code, resp.text)

        if resp.status_code not in TRANSIENT_CODES:
            resp.raise_for_status()
            return resp.json()["id"]

        if attempt == len(delays):
            resp.raise_for_status()

        delay = delays[attempt]
        print(f"Temporary Instagram error; retrying in {delay} seconds...")
        time.sleep(delay)


def wait_until_ready(container_id, access_token, max_attempts=30, delay=3):
    for _ in range(max_attempts):
        resp = requests.get(
            f"{BASE_URL}/{container_id}",
            params={
                "fields": "status_code,status",
                "access_token": access_token,
            },
            timeout=30,
        )
        resp.raise_for_status()
        payload = resp.json()
        status = payload.get("status_code")
        print("CONTAINER STATUS:", status, payload.get("status", ""))

        if status == "FINISHED":
            return True
        if status in ("ERROR", "EXPIRED"):
            raise RuntimeError(
                f"Media container {container_id} failed processing: {payload.get('status', status)}"
            )
        time.sleep(delay)

    raise TimeoutError(
        f"Media container {container_id} not ready after {max_attempts} checks"
    )


def publish_container(ig_user_id, access_token, container_id):
    resp = requests.post(
        f"{BASE_URL}/{ig_user_id}/media_publish",
        data={
            "creation_id": container_id,
            "access_token": access_token,
        },
        timeout=60,
    )
    print("INSTAGRAM PUBLISH RESPONSE:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/publish_instagram.py <image_url> <caption>")
        sys.exit(1)

    image_url = sys.argv[1]
    caption = sys.argv[2]

    configured_id = os.environ.get("IG_USER_ID", "")
    access_token = os.environ["IG_ACCESS_TOKEN"]

    ig_user_id = resolve_ig_user_id(access_token, configured_id)
    container_id = create_container(ig_user_id, access_token, image_url, caption)
    wait_until_ready(container_id, access_token)
    result = publish_container(ig_user_id, access_token, container_id)
    print("Published:", result)


if __name__ == "__main__":
    main()
