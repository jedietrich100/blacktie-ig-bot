# Digital Calm Daily automation

This folder is isolated from the other brands in this repository.

## Content generation

The `digital-calm-daily.yml` workflow generates the day's graphic, caption, JSON,
and optional vertical how-to Reel at 11:00 UTC. It reuses existing daily assets
instead of generating duplicates. Finished content is committed under
`docs/dcd-posts/` and, when applicable, `docs/dcd-reels/`.

The existing `ANTHROPIC_API_KEY` secret is used for generation. No publishing
credentials or new paid services are required by this change.

## Publishing ownership

Image publishing is handled separately through the connected Metricool account.
Reels are also handed to the connected Metricool publisher for Instagram
`@digitalcalmdaily`, brand `6968914`, at 17:30 America/Chicago. That publisher
must be enabled separately; this repository does not contain a Metricool API key
and GitHub Actions does not invoke the Metricool connector.

The former Buffer Reel workflow is retired. It has no scheduled triggers, no
publishing credentials, and no publishing step. Manual dispatch only explains
the handoff and cannot submit a Reel. The historical Buffer scripts and receipt
records are retained for diagnosis, not as an alternate live publisher. Do not
invoke the low-level Buffer scripts to retry content.

## Required duplicate protection

- Use only the current Central calendar day's committed MP4 and exact caption.
  A day without an optional Reel is not a failure and must not use an older one.
- Read fresh `reel_history.json` and `reel_ledger.json`, including all prior
  provider attempts. Missing or malformed state blocks publication.
- Check the matching Metricool date range and account for published, scheduled,
  draft, pending, or failed entries before creating anything. Match the exact
  caption and source video. An existing pending/published receipt is reconciled,
  never reposted. A failed/uncertain result requires reconciliation first.
- Persist a durable, SHA-conditional reservation in `reel_ledger.json` before
  calling Metricool. Re-read after a conflict and never overwrite another owner.
- Make only one create request. A timeout, interrupted call, missing receipt,
  or receipt-write failure leaves the reservation blocking another submission.
- Record the Metricool receipt and original Buffer attempt without clearing
  historical reservations. Add an accepted date to `reel_history.json` only
  after a valid provider receipt. Acceptance is not proof of Instagram delivery.
- Check the same receipt after its due time. Report a verified Instagram
  permalink when published, or the exact provider error. Do not automatically
  recreate failed posts, backfill earlier dates, or retry the separate image.

Historical Buffer reservations remain intentionally blocking. Migrations and
recoveries must preserve their receipt, source asset, caption hash, and evidence.

## Tests

Run `python -m unittest discover -s dcd/tests -v` after installing `requests`.
Network requests are mocked; Git integration tests use temporary local repos.
Do not invoke a publishing script as a test. The retirement test additionally
checks that the legacy workflow has no scheduled trigger or publishing step.
