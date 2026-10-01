# Circus Peanuts Daily

An isolated, direct Instagram publisher for @circuspeanutsdaily. Black Tie and Digital Calm Daily are not imported or changed.

## Content and schedule

Gentle, lighthearted observational jokes in a cream-and-orange branded 1080×1350 JPEG. The curated bank contains 60 distinct jokes; one is selected sequentially each day, so a joke cannot recur within 60 days. Captions and rendered images are retained by Chicago calendar date.

Scheduled for noon America/Chicago, with daylight-saving handling (17:00 UTC during CDT, 18:00 UTC during CST). GitHub Actions can delay or occasionally miss scheduled jobs; this is not an exact-time guarantee. The October 1, 2026 merge triggers the launch post once; later-date workflow edits do not publish outside the schedule.

## Configuration

- Dedicated existing secrets: `CIRCUS_IG_ACCESS_TOKEN`, `CIRCUS_IG_USER_ID`
- Enabled by default for launch. Set the repository variable `CIRCUS_ENABLED=false` to pause only Circus; set it to `true` to resume
- Manual workflow dispatch previews by default; publishing must be explicitly selected, with Circus enabled
- All publishing requires the main branch and the exact expected repository and Instagram username/account ID

## Safety and verification

Before any publication the runner authenticates @circuspeanutsdaily and checks the account's latest 100 posts by Chicago calendar date. If today's feed already has a post, it skips publishing. Ledger validation rejects corrupt or mismatched state. Only Circus asset/state paths are committed.

The persistent phases are prepared, submitting, container_created, publishing and published. Every mutation is preceded by a persisted guard; the returned creation ID is saved immediately. A timed-out or uncertain publish is never automatically retried. Investigate the account and stored IDs before any manual recovery; never delete/reset uncertain state to force a retry.

Publication is verified by its Instagram media ID, username and permalink. The token is sent only to the Instagram Graph API in an Authorization header, is never written to files, and is never printed. Logs suppress raw HTTP exceptions.

## Tests

`pip install -r circus/requirements.txt`

`python -m unittest discover -s circus -p 'test_*.py' -v`

`python circus/daily.py` renders a preview without network requests or repository writes unless CIRCUS_PUBLISH=true.
