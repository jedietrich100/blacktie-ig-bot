# Digital Calm Daily automation

This folder is isolated from the existing Black Tie Intel bot.

## What it does

- Runs every day at 9:45 AM America/Chicago.
- Rotates categories by weekday:
  - Monday: iPhone and Apple Tips
  - Tuesday: AI Tips
  - Wednesday: Scam and Cybersecurity
  - Thursday: Simple Tech How-Tos
  - Friday: Digital Organization
  - Saturday: Useful Tech Tools
  - Sunday: Digital Confidence
- Keeps a rolling topic history and rejects near-duplicate ideas.
- Avoids time-sensitive claims unless they can be verified; the unattended bot therefore favors evergreen guidance.
- Creates a consistent faceless Digital Calm Daily graphic locally with Pillow.
- Preserves clean Instagram paragraph spacing.
- Sends the finished image and caption to Buffer with `shareNow`.
- Decides whether the day's message genuinely benefits from a short visual
  walkthrough. When it does, it creates a matching vertical quick how-to Reel.
- Publishes applicable Reels at 5:30 PM America/Chicago through Buffer. Topics
  that are better as a single graphic do not create or publish a Reel.
- Prevents a second run from publishing the same daily graphic or Reel twice.

## One-time connection required

Add a GitHub Actions repository secret named:

`DCD_BUFFER_API_KEY`

Use a personal API key from Buffer API settings. The publisher will automatically look for the Instagram channel named Digital Calm Daily.

Optional: if automatic channel discovery ever finds the wrong account, add:

`DCD_BUFFER_CHANNEL_ID`

The existing `ANTHROPIC_API_KEY` secret used by the Black Tie Intel workflow is reused for content generation. No API keys are stored in the repository.

Until `DCD_BUFFER_API_KEY` exists, the workflow exits safely without generating or publishing anything.

## Reel backup attempts and duplicate protection

- Scheduled attempts run at 5:30, 5:40 and 5:50 PM Chicago. They may start late;
  scheduled submissions are allowed only from 5:30 through 5:59 PM that same day.
  The cutoff is checked again after preparation and immediately before submission.
- Jobs share one concurrency group and refresh `main` before reading state.
- The tracked `reel_history.json` retains accepted dates. The tracked
  `reel_ledger.json` records a durable reservation before the Buffer request, then
  the returned Buffer post ID. Missing or invalid state blocks publishing.
- A timeout, interrupted request, or failed receipt write leaves a blocking
  reservation. Backup attempts never blindly repeat that Buffer request. A Git
  persistence failure before the reservation reaches the remote prevents submission.
- Buffer acceptance does not confirm final Instagram delivery. For an uncertain
  result, inspect the correct channel's Sent and Queue views and the matching
  caption/video before reconciling the ledger. Retain the reservation while the
  outcome is uncertain; do not delete it just to trigger another attempt.
- The existing explicit manual workflow-dispatch path is unchanged. It uses
  today's files and the same durable guards. It is not a previous-day backfill.
  Direct execution of the low-level `publish_buffer_reel.py` bypasses these guards
  and must not be used for retries.

Run offline tests with `python -m unittest discover -s dcd/tests -v` after installing
`requests`. Tests mock all Buffer/network requests; Git integration tests use only
temporary local repositories. Do not invoke either publishing script as a test.
