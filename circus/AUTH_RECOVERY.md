# Restore @circuspeanutsdaily Instagram publishing (Circus only)

## Current blocker: HTTP 401 / Instagram code 190
Instagram invalidated the credential after a password or security-session change.
It **cannot be repaired by replaying the old token**, changing cron schedules,
rerunning failed publishing jobs, or changing a repository variable.

The workflows deliberately require a token scoped to **@circuspeanutsdaily**;
do not substitute credentials from Digital Calm Daily, Black Tie, or any other account.

## Only owner-authentication step

1. In the existing Meta developer app configured for **Instagram API with Instagram Login**,
   complete the official Instagram Business Login consent flow while signed in as
   **@circuspeanutsdaily**. The account must be a professional account. Request
   at least the current Instagram Login permissions instagram_business_basic
   and instagram_business_content_publish.
2. Through the developer app's **authorized** exchange flow, obtain a new,
   appropriately long-lived Instagram access token for that same account.
   A revoked or expired token cannot be refreshed in place.
3. As the repository owner, replace **only** GitHub Actions repository secret
   CIRCUS_IG_ACCESS_TOKEN at:
   https://github.com/jedietrich100/blacktie-ig-bot/settings/secrets/actions
   Keep CIRCUS_IG_USER_ID unchanged **only if** the newly authorized
   account's user_id still matches the expected Circus account.
   Do not paste tokens into repository files, issues, chat messages or logs.
   These credentials cannot be read or written using the available GitHub
   connector, so owner authorization and a secret update are required.

Instagram Login does not require a linked Facebook Page; do not reactivate
a deactivated Facebook profile just to attempt an unrelated Facebook Login flow.

## Validation after the secret has been replaced

1. Run **Circus Peanuts Publication Audit** manually in GitHub Actions for the
   prior Chicago date. It makes only authenticated GET requests. It checks
   the actual recent Instagram media and matches daily image and evening
   Reel IDs to the independently persisted verified ledgers.
2. Examine each date after October 10 with the read-only audit before deciding
   whether a gap reflects a missing post, an unrecorded live post, or an
   unverifiable outcome. The audit never backfills.
3. Scheduled daily and evening production resume on their normal same-day
   windows. Duplicate, wrong-account, and uncertain-submission locks remain
   enabled. A genuinely published post has a durable Instagram media ID,
   verified permalink and verified_at receipt.
4. The audit runs automatically at **09:17 UTC daily** (3:17 AM CST / 4:17 AM
   CDT), auditing the previous Chicago day. If either post lacks a matching
   verified live receipt, it fails with a plain-English Actions summary
   and opens an owner-assigned GitHub issue with a link to the run.
   A skipped or green workflow by itself does not prove publication.

No payment or paid AI generation is enabled. The Reel configuration keeps
paid_generation_enabled=false and max_paid_calls_per_day=0.
No other account or brand is targeted by the auditor or the Circus workflows.
