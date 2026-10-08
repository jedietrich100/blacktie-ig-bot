# Circus Peanuts Evening Reels

Adds one optional daily Reel for **@circuspeanutsdaily**, targeting **6 PM America/Chicago**.
The existing noon image workflow, its ledger, and other brands are untouched.
GitHub Actions runs may be delayed; this is a target window, not a guarantee of an exact time.

## Status and activation

Implementation is ready for offline preview. **Scheduled jobs, paid AI generation, and Reel publishing are OFF by default.**
The AI calls and real Reel publishing have not been exercised with production credentials.
The included preview is silent, uses curated humor, and demonstrates layout and pacing only.

Before activation:

1. Obtain the owner's explicit AI spending approval. Configure provider billing controls.
   The code limits paid request COUNT; it does **not** claim to enforce a dollar cap.
2. Set the repository secret `CIRCUS_OPENAI_API_KEY` using GitHub's encrypted secret UI.
   Never put a key in code, a PR, captions, chat, or workflow logs.
3. Reuse `CIRCUS_IG_ACCESS_TOKEN` and `CIRCUS_IG_USER_ID`. The publisher verifies the
   exact username and account ID before sending a Reel. Instagram Login is used;
   no Facebook Page, Buffer, Metricool, or cross-posting is involved.
4. In `config.json`, set `paid_generation_enabled` to true and `max_paid_calls_per_day`
   to 9. One complete production needs nine requests: script, editorial review,
   three images, three scene voices, and one visual review. No paid automatic retries.
5. Run a credentialed production canary within the scheduled window and inspect its
   images, narration, script, account, and actual Instagram receipt. The automatic
   editorial and visual reviewers are imperfect; they cannot guarantee quality or retention.
6. Set `publishing_enabled` true and repository variable `CIRCUS_REELS_ENABLED=true`
   when ready to activate. To pause, set the variable false. Manual dispatch always
   creates a free, local format preview; it never publishes or incurs AI charges.

If paid generation stays false, enabled scheduled jobs can render the seven-item
curated reserve as silent Reels. They never repeat the reserve after it is exhausted.
This fallback is not described as fresh AI-generated content.

## Production flow

1. Fetch recent RSS topic titles from four niche-specific feeds.
2. Compare feed mention counts to up to seven previous days, deduplicate sources,
   and identify timely inspiration. “Rising feed mentions” is an internal feed signal,
   not a claim to know Instagram-wide trends or search volume. On feed failure,
   fresh evergreen humor remains an allowed script choice.
3. Generate three hook candidates, a chosen hook, setup, punchline, three background
   prompts, caption, and three to five relevant hashtags in strict JSON.
4. Independently review the script for warm humor, a payoff, and brand boundaries.
   Source titles are untrusted data. Do not copy article prose or turn the page into news.
5. Generate three photo-style background scenes and three scene-specific narration clips.
   Use the approved mascot as the palette reference; composite the **exact existing mascot**
   afterward. Its identity does not depend on the image model reproducing it.
6. Independently inspect all three backgrounds through vision before rendering.
7. Render 1080×1920 H.264/AAC MP4s with gentle camera movement and scene text that
   appears with its matching narration. Technical checks reject oversized, long, or malformed output.
   This is animated still-image video, not generative character animation. No unlicensed music is added.
8. Commit the finished media; use immutable commit-pinned MP4 URLs for Instagram ingestion.
9. Verify account, reconcile the day-specific Reel marker, create and poll a Reel
   container, reserve submission durably, publish once, and save the actual permalink.
10. Collect available insights on later days at approximately 24 hours and seven days.
    `views`, `reach`, `saved`, `shares`, and average Reel watch time are requested
    independently; unsupported metrics or missing insights permissions are marked unavailable.

## Editorial identity

Warm, faceless, everyday-life humor: marriage, aging, technology, travel, pets,
errands, and ordinary absurdities. Clever, mischievous, occasionally sarcastic;
never cruel or political. Cream/orange/red/black palette, peanut candy mascot
with sunglasses and hat, **SMILE · LAUGH · REPEAT**. No personal owner details.
No medical or financial advice, fabricated statistics, copied jokes, or allegations.

## Duplicate and spending protection

- Shared account concurrency group with the existing Circus image workflow.
- Fresh main checkout and durable generation/paid-request/publication reservations.
- Exact and near-duplicate script checks; seven evergreen scripts tracked by index.
- Daily request ceiling is reserved before each paid POST, including uncertain failures.
- One Reel per Chicago calendar day. The noon photo is not treated as the Reel.
- Once `creating_container` or `submitting` is recorded, no blind POST retries.
- Each published Reel has a `Circus reel · YYYY-MM-DD` marker for reconciliation.
- Stale dates, wrong daylight-saving cron slots, and starts after the 6 PM window are blocked.
- Ready assets and container IDs are reused. Failed generation remains for inspection,
  instead of restarting expensive work. Git persistence failure blocks external submission.

## Recovery

Inspect `state.json`, the run artifacts, and the actual Instagram account before
changing uncertain states. If an existing marked Reel is visible, reconciliation
records it without publishing again. For an uncertain container creation, inspect
Meta diagnostics before clearing the reservation. Never reset all history.
If a generated job failed, inspect files and provider usage; repair the specific job
and preserve `paid_calls`. A known unsubmitted job can be moved to ready only after
all its media checks pass and its pinned commit is recorded.

## Testing and local preview

```sh
pip install Pillow requests
python -m unittest discover -s circus/tests -v
python circus/reels/pipeline.py --preview --output preview/circus-reel
```

FFmpeg/ffprobe and DejaVu fonts are required. The workflow installs FFmpeg.
Preview makes no HTTP calls, writes no durable state, and needs no credentials.

## Retention experiments

Start with one daily Reel; preserve the noon image. After at least two weeks of
comparable results, review the available insights in `state.json`. Test one variable
at a time: first-line specificity, setup length, punchline timing, or scene style.
Use shares/reach and saves/reach alongside watch time; raw views alone are insufficient.
The system records metrics; it does not automatically rewrite production prompts
from a small sample or promise viral performance. Expansion to multiple daily Reels
requires an explicit rollout change to the one-per-day guard and slot-specific ledgers.

## API references

- https://developers.openai.com/api/docs/guides/structured-outputs
- https://developers.openai.com/api/reference/resources/images/methods/edit
- https://developers.openai.com/api/docs/guides/text-to-speech
- https://www.postman.com/meta/workspace/instagram/documentation/23987686-9386f468-7714-490f-9bfc-9442db5c8f00

API request shapes were checked against current documentation. Model access,
credentials, production media ingestion, and account insights still need live verification.
