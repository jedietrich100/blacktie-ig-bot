"""
Publishes an already-public image URL to Instagram using the Instagram API
with Instagram Login (graph.instagram.com endpoints – no Facebook Page needed).

Two-step flow per Meta's docs:
  1. POST /{ig_user_id}/media        -> create a media container from image_url + caption
  2. POST /{ig_user_id}/media_publish -> publish that container

Usage: python3 scripts/publish_instagram.py "<image_url>" "<caption>"
Requires env vars: IG_USER_ID, IG_ACCESS_TOKEN
"""

import os
import sys
import time
import requests

GRAPH_VERSION = "v21.0"
BASE_URL = f"https://graph.instagram.com/{GRAPH_VERSION}"

def create_container(ig_user_id, access_token, image_url, caption):
    resp = requests.post(
        f"{BASE_URL}/{ig_user_id}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": access_token,
        },
        timeout=30,
    )
    print("INSTAGRAM RESPONSE:", resp.status_code, resp.text)
    resp.raise_for_status()
    return resp.json()["id"]

def wait_until_ready(container_id, access_token, max_attempts=10, delay=3):
    for _ in range(max_attempts):
        resp = requests.get(
            f"{BASE_URL}/{container_id}",
            params={"fields": "status_code", "access_token": access_token},
            timeout=30,
        )
        resp.raise_for_status()
        status = resp.json().get("status_code")
        if status == "FINISHED":
            return True
        if status == "ERROR":
            raise RuntimeError(f"Media container {container_id} failed processing")
        time.sleep(delay)
    raise TimeoutError(f"Media container {container_id} not ready after {max_attempts} checks")

def publish_container(ig_user_id, access_token, container_id):
    resp = requests.post(
        f"{BASE_URL}/{ig_user_id}/media_publish",
        data={
            "creation_id": container_id,
            "access_token": access_token,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()

def main():
    if len(sys.argv) < 3:
        print("Usage: python3 scripts/publish_instagram.py <image_url> <caption>")
        sys.exit(1)

    image_url = sys.argv[1]
    caption = sys.argv[2]

    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["IG_ACCESS_TOKEN"]

    container_id = create_container(ig_user_id, access_token, image_url, caption)
    wait_until_ready(container_id, access_token)
    result = publish_container(ig_user_id, access_token, container_id)
    print("Published:", result)

if __name__ == "__main__":
    main()
