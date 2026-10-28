# Black Tie daily publication

Run the offline safety tests with:

    python3 -m unittest discover -s scripts/tests -v

Quote generation retains the existing model, theme prompt, style guide, and
global-lens selection. It allows at most three API requests, with output budgets
of 256, 512, and 512 tokens, a 30-second SDK request timeout, and two backoffs
(2 and 4 seconds). SDK automatic retries are disabled so they cannot multiply
that budget. Empty or invalid text, truncated responses, recent literal
duplicates (normalized for case/spacing/punctuation), connection failures, and
HTTP 408/409/429/5xx responses may retry. Refusals, unexpected stop reasons or
content block types, and other API errors stop immediately. Only completed `end_turn` text can pass;
the existing editorial prompt's 20-word limit is enforced. No canned fallback,
partial text, or failed attempt is saved to history or passed to the renderer.

`QUOTE_GENERATION` diagnostics go to stderr and survive a successful retry.
They include only attempt/budget, allowlisted stop reason, block counts, numeric
token usage, HTTP status, and a fixed failure category; never raw responses,
prompts, credentials, or SDK exception bodies. The October 28, 2026 empty-text failure did
not log the API stop reason, so truncation cannot be established retroactively.

The daily workflow checks out current `main` after acquiring the shared
`blacktie-daily-instagram-post` concurrency group. An existing daily JPEG and
caption are reused together; partial existing assets cause a stop rather than
regeneration. The image URL is pinned to the commit that last changed that JPEG.

`Config/instagram_publish_ledger.json` records immutable per-date content,
container IDs, in-flight requests, and verified media IDs/permalinks. Every
publication intent is committed and pushed before the corresponding API write.
The API verifies both the account username and professional account ID.

Only HTTP 400 / code 9007 / subcode 2207027 is retried, up to six attempts in a
run, always with the same container and fresh feed/container checks. Timeouts,
ambiguous errors, missing receipts, and previous in-flight states never cause
blind resubmission. A matching feed post reconciles a lost success receipt.
Partial feed pagination, invalid timestamps, mismatched content, or another post
for the target day stop publication. Reconcile an uncertain outcome before any
manual recovery; never delete its ledger entry to force a retry.

The October 18 recovery uses the original container and verifies the original
JPEG against its Git blob ID plus its exact caption. It is date-limited and
shares the normal publication lock. It never runs the generator.

