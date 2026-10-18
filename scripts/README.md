# Black Tie daily publication

Run the offline safety tests with:

    python3 -m unittest discover -s scripts/tests -v

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
