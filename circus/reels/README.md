# Circus Peanuts Evening Reels

Owner-authorized daily **silent** branded Reels for **@circuspeanutsdaily**.
Target: **6 PM America/Chicago**, with backups every 20 minutes through 11:40 PM.
GitHub scheduling can be delayed; exact publication time is not guaranteed.
The local gate permits only that calendar day's 6 PM–midnight window, including
rechecks immediately before submission. Wrong dates and unknown crons are rejected.

## Active free configuration

- `publishing_enabled=true`.
- `paid_generation_enabled=false`, `max_paid_calls_per_day=0`.
- No provider API key is supplied by the workflow; no AI billing is enabled.
- Repository variable `CIRCUS_REELS_ENABLED` is no longer a prerequisite. Its old
  value does not block this authorized schedule.
- 98 curated everyday-humor scripts across seven existing brand pillars.
  Unused scripts are selected first; the oldest published script may rotate only
  after at least 90 days. At the normal one-per-day pace the library cycles in 98 days.
  Full history is retained. Uncertain, incomplete, or unpublished jobs never age out
  of duplicate protection. The one-Reel-per-day guard is independent of rotation.
- Free production uses the cream/orange layout, exact existing candy mascot,
  gentle camera movement, and three readable text scenes. No narration or paid
  generated backgrounds are promised. No RSS fetches occur in this free route.
- The existing noon image workflow and its ledger are unchanged. Both use
  `concurrency.group=circus-peanuts-daily`, `cancel-in-progress=false`.

## Verification and triggers

Scheduled events are the only production publishing trigger. Manual dispatch
always renders a silent, network-free format preview and never posts.
Code/configuration pushes to main run tests, render a preview, and check the exact
Instagram account with a read-only API call. They never publish. State-only commits
and finished-media commits do not trigger this validation workflow.

The credential check verifies `CIRCUS_IG_ACCESS_TOKEN` and numeric
`CIRCUS_IG_USER_ID` resolve to the configured account. It does not claim to verify
Reel ingestion, every permission, or eventual publication. The first real scheduled
Reel must finish container processing and return a verified Instagram permalink.
The implementation uses Instagram Login; it does not require Facebook reactivation,
Buffer, or Metricool.

Local verification:

```sh
pip install Pillow requests
python -m unittest discover -s circus/tests -v
python circus/reels/pipeline.py --preview --output preview/circus-reel
```

FFmpeg/ffprobe and DejaVu fonts are required. The hosted workflow installs FFmpeg.
Tests simulate 400 production days to verify continuous rotation, cooldowns, and
recent duplicate checks; they also cover all evening cron slots across daylight-saving
transitions, unpaid execution, account isolation, and uncertain submissions.

## Publication safeguards

1. Refresh main and check today's durable job before producing content. Already
   published days return without account calls, regeneration, or resubmission.
2. Check the target account before reserving new production content.
3. Validate allowed pillar, scene/script lengths, valid hashtags, brand hashtag,
   and exact/near duplicates within the applicable evergreen cooldown.
4. Render 1080×1920 H.264/AAC MP4; reject outside 8–40 seconds, oversized media,
   overflowing scene text, or excessive scene duration. No unlicensed music is added.
5. Persist the script and finished media; use an immutable commit-pinned public
   MP4 URL for Instagram ingestion. Actions must retain permission to push to main.
6. Recheck account/date/window, reconcile the day's Reel marker, and reserve
   container creation and publication durably before external POST requests.
7. Reuse ready assets and a known container; never blindly retry an uncertain
   `creating_container` or `submitting` job. Noon FEED images are not treated as Reels.
8. Persist the actual media ID and verified permalink. Optional later insights mark
   unsupported metrics unavailable rather than inventing zeros.

Structural validation is not an editorial classifier. The saved bank is curated
warm, faceless humor: pets, travel, technology, marriage, aging, errands, and ordinary
absurdities. No personal owner details, politics, cruelty, medical or financial advice,
news claims, or real-person allegations. Future bank edits require editorial review.
Phone UI overlays, live ingestion, and live account receipts require actual live review.

## Pause and recovery

To pause production entirely, disable **Circus Peanuts Evening Reel** in GitHub
Actions. Set `publishing_enabled=false` to stop publication while retaining render
work; this setting alone still allows scheduled content reservation/rendering.
Manual preview remains safe even when publishing is enabled.

Inspect `state.json`, artifacts, and the actual Instagram account before resolving
uncertain jobs. Never reset history to force a retry. When the marked Reel already
exists, reconciliation records it without posting again. Preserve failed or
uncertain reservations until their external outcomes are known.

The old paid generation implementation remains disabled. Any future narrated AI
rollout needs separate explicit spending approval, provider billing controls, model
access validation, restoring the encrypted key mapping, an approved request limit,
and reviewed production assets. A complete AI generation uses nine provider requests;
the request count is not a dollar cap. Paid generation and its external API shapes
have not been exercised by this free rollout.
