"""Publish a prepared Digital Calm Daily MP4 as an Instagram Reel through Buffer."""

from __future__ import annotations

import json
import os
import sys

from publish_buffer import discover_channel, gql


def publish_reel(api_key: str, channel_id: str, video_url: str, caption: str) -> str:
    text = json.dumps(caption)
    channel = json.dumps(channel_id)
    video = json.dumps(video_url)
    query = f"""
mutation CreatePost {{
  createPost(input: {{
    text: {text}
    channelId: {channel}
    schedulingType: automatic
    mode: shareNow
    assets: [{{ video: {{ url: {video} }} }}]
    metadata: {{ instagram: {{ type: reel, shouldShareToFeed: true }} }}
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
        raise RuntimeError(f"Buffer rejected Reel: {payload['message']}")
    post = payload.get("post")
    if not post or not post.get("id"):
        raise RuntimeError(f"Unexpected Buffer response: {result}")
    print(json.dumps(post, indent=2))
    return str(post["id"])


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: publish_buffer_reel.py VIDEO_URL CAPTION_FILE")
    api_key = os.environ.get("DCD_BUFFER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DCD_BUFFER_API_KEY is not configured")
    channel_id = discover_channel(api_key)
    caption = open(sys.argv[2], encoding="utf-8").read()
    post_id = publish_reel(api_key, channel_id, sys.argv[1], caption)
    print(f"Published Buffer Reel: {post_id}")


if __name__ == "__main__":
    main()
