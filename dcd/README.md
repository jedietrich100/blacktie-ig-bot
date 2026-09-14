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

## One-time connection required

Add a GitHub Actions repository secret named:

`DCD_BUFFER_API_KEY`

Use a personal API key from Buffer API settings. The publisher will automatically look for the Instagram channel named Digital Calm Daily.

Optional: if automatic channel discovery ever finds the wrong account, add:

`DCD_BUFFER_CHANNEL_ID`

The existing `ANTHROPIC_API_KEY` secret used by the Black Tie Intel workflow is reused for content generation. No API keys are stored in the repository.

Until `DCD_BUFFER_API_KEY` exists, the workflow exits safely without generating or publishing anything.
