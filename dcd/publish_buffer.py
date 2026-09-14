"""Publish the prepared Digital Calm Daily image + caption through Buffer.

Required secret:
  DCD_BUFFER_API_KEY

Optional environment override:
  DCD_BUFFER_CHANNEL_ID

If no channel ID is provided, the script finds the Instagram channel whose name
looks like Digital Calm Daily.
"""

from __future__ import annotations

import json
import os
import re
import sys

import requests

API_URL = "https://api.buffer.com"


def gql(api_key: str, query: str) -> dict:
    response = requests.post(
        API_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={"query": query},
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()
    if data.get("errors"):
        raise RuntimeError(f"Buffer API error: {data['errors']}")
    return data


def normalized(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


def discover_channel(api_key: str) -> str:
    override = os.environ.get("DCD_BUFFER_CHANNEL_ID", "").strip()
    if override:
        return override

    account = gql(api_key, "query { account { organizations { id name } } }")
    organizations = account.get("data", {}).get("account", {}).get("organizations", [])
    matches = []

    for org in organizations:
        org_id = json.dumps(org["id"])
        result = gql(
            api_key,
            f"query {{ channels(input: {{ organizationId: {org_id} }}) {{ id name service }} }}",
        )
        channels = result.get("data", {}).get("channels", [])
        for channel in channels:
            service = normalized(str(channel.get("service", "")))
            name = normalized(str(channel.get("name", "")))
            if service == "instagram" and (
                "digitalcalmdaily" in name or name in {"dcd", "digitalcalm"}
            ):
                matches.append(channel)

    if len(matches) == 1:
        channel = matches[0]
        print(f"Using Buffer Instagram channel: {channel.get('name')} ({channel.get('id')})")
        return str(channel["id"])
    if not matches:
        raise RuntimeError(
            "Could not find a Buffer Instagram channel named Digital Calm Daily. "
            "Set DCD_BUFFER_CHANNEL_ID as a GitHub secret if the channel uses a different name."
        )
    raise RuntimeError(
        "More than one Digital Calm Daily Instagram channel matched. "
        "Set DCD_BUFFER_CHANNEL_ID explicitly."
    )


def publish(api_key: str, channel_id: str, image_url: str, caption: str) -> str:
    text = json.dumps(caption)
    channel = json.dumps(channel_id)
    image = json.dumps(image_url)

    query = f"""
mutation CreatePost {{
  createPost(input: {{
    text: {text}
    channelId: {channel}
    schedulingType: automatic
    mode: shareNow
    assets: [{{ image: {{ url: {image} }} }}]
  }}) {{
    ... on PostActionSuccess {{
      post {{ id text dueAt status assets {{ id mimeType }} }}
    }}
    ... on MutationError {{ message }}
  }}
}}
""".strip()

    result = gql(api_key, query)
    payload = result.get("data", {}).get("createPost") or {}
    if payload.get("message"):
        raise RuntimeError(f"Buffer rejected post: {payload['message']}")
    post = payload.get("post")
    if not post or not post.get("id"):
        raise RuntimeError(f"Unexpected Buffer response: {result}")
    print(json.dumps(post, indent=2))
    return str(post["id"])


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: publish_buffer.py IMAGE_URL CAPTION_FILE")

    api_key = os.environ.get("DCD_BUFFER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DCD_BUFFER_API_KEY is not configured")

    image_url = sys.argv[1]
    caption = open(sys.argv[2], encoding="utf-8").read()
    channel_id = discover_channel(api_key)
    post_id = publish(api_key, channel_id, image_url, caption)
    print(f"Published Buffer post: {post_id}")


if __name__ == "__main__":
    main()
