"""One-day recovery of the exact original October 18 Black Tie post."""
import datetime as dt
import hashlib
from pathlib import Path
import os
import urllib.request

from publish_instagram import PublishError, commit_ledger, publish_once

DAY = "2026-10-18"
ASSET_COMMIT = "59c6ae61964109837559182cd8a64916ece89a8b"
IMAGE_URL = ("https://raw.githubusercontent.com/jedietrich100/blacktie-ig-bot/"
             + ASSET_COMMIT + "/docs/posts/" + DAY + ".jpg")
IMAGE_BLOB = "117eaf09e36161d09be69c61963fa556a3cff439"
CONTAINER = "18107224811148189"
CAPTION = (
    "The quietest infrastructure decisions this year will outlive every headline written about them.\n\n"
    "Headlines describe the moment. Direction reveals what the moment is becoming.\n\n"
    "Worth watching. What’s your read?\n\n"
    "#BlackTieIntel #TheLongView #Future #AChangeInDirection"
)


def main():
    if dt.datetime.now(dt.timezone.utc).date().isoformat() != DAY:
        raise PublishError("This one-day recovery has expired")
    if Path("docs/posts/" + DAY + ".caption.txt").read_text(encoding="utf-8") != CAPTION:
        raise PublishError("The preserved caption does not match the original")
    with urllib.request.urlopen(IMAGE_URL, timeout=30) as response:
        image = response.read(8_000_001)
    if len(image) > 8_000_000 or not image.startswith(b"\xff\xd8\xff"):
        raise PublishError("The preserved public image is not a valid JPEG")
    blob = hashlib.sha1(b"blob " + str(len(image)).encode() + b"\x00" + image).hexdigest()
    if blob != IMAGE_BLOB:
        raise PublishError("The original image failed immutable-content verification")
    print("ORIGINAL_ASSETS_VERIFIED: " + ASSET_COMMIT, flush=True)
    publish_once(IMAGE_URL, CAPTION, DAY, os.environ.get("IG_ACCESS_TOKEN", ""),
                 checkpoint=commit_ledger, existing_container=CONTAINER)


if __name__ == "__main__":
    try:
        main()
    except PublishError as error:
        print("STOP: " + str(error), flush=True)
        raise SystemExit(1) from None
