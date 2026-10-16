"""Publish Black Tie Intel's generated post through its Buffer Instagram channel.

Requires BUFFER_API_KEY in the environment. Channel discovery only accepts the
Instagram account named blacktie_intel, so a different account cannot be posted to.
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
from dcd.publish_buffer import gql, normalized, publish  # noqa: E402


def discover_blacktie_channel(api_key: str) -> str:
    account = gql(api_key, "query { account { organizations { id name } } }")
    organizations = account.get("data", {}).get("account", {}).get("organizations", [])
    matches = []

    for organization in organizations:
        org_id = json.dumps(organization["id"])
        result = gql(
            api_key,
            f"query {{ channels(input: {{ organizationId: {org_id} }}) {{ id name service }} }}",
        )
        for channel in result.get("data", {}).get("channels", []):
            if (
                normalized(str(channel.get("service", ""))) == "instagram"
                and normalized(str(channel.get("name", ""))) == "blacktieintel"
            ):
                matches.append(channel)

    if len(matches) != 1:
        raise RuntimeError(
            f"Expected one Black Tie Intel Instagram channel in Buffer; found {len(matches)}"
        )
    channel = matches[0]
    print(f"Using Buffer Instagram channel: {channel['name']} ({channel['id']})")
    return str(channel["id"])


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: publish_blacktie_buffer.py IMAGE_URL CAPTION_FILE")
    api_key = os.environ.get("BUFFER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("BUFFER_API_KEY is not configured")
    image_url = sys.argv[1]
    caption = pathlib.Path(sys.argv[2]).read_text(encoding="utf-8")
    channel_id = discover_blacktie_channel(api_key)
    post_id = publish(api_key, channel_id, image_url, caption)
    print(f"Published Black Tie Intel Buffer post: {post_id}")


if __name__ == "__main__":
    main()
