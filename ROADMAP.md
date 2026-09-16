# Roadmap

Where this project goes next, and why.

The goal for Motivator McBot was never "use the X API" — it was to build something
that **feels alive, runs on its own, and is visible to other people**. X was one way
to get all three. It no longer is, at least not for free. This is the record of what
was tried, what it costs, and what the alternatives are.

## Why X stopped being an option

X deprecated the Free access tier: it "no longer includes general access to API
endpoints". In February 2026 the tiered plans were replaced by pay-per-usage credits,
and X's current pricing documentation describes no free allowance at all.

That was confirmed against the live API with `python bot.py --check`, which posts
nothing:

| Call | Result |
| --- | --- |
| `GET /2/users/me` | `200` — OAuth 2.0 credentials are correct |
| `POST /2/media/upload` | `403` — most likely a token minted without `media.write` |
| `POST /2/tweets` | `402 credits depleted` |

The `402` is the decisive one. It is X stating outright that no free quota covers
posting, which contradicts advice from the assistant in the developer console
claiming the project's Free package included a monthly allowance.

### What it would cost

| Item | Cost |
| --- | --- |
| `Post: Create` | $0.015 per request |
| `Post: Create (with URL)` | **$0.200 per request** |
| One post per day | ~$0.46/month, ~$5.50/year |

Media upload does not appear in X's price table, so it seems not to be billed
separately; treat the figure above as a floor and watch the console on the first
few runs.

The thirteen-fold jump for a post containing a URL is worth remembering. The tweet
body is deliberately plain text — adding a link back to the photographer, which
Unsplash's guidelines encourage, would cost $6/month instead of $0.46.

### The code is ready either way

Nothing in this repository needs to change to post to X. OAuth 2.0 authentication
works, the scheduler works, the image renders. It needs two things from outside the
code: credits on the account, and a refresh token minted with the `media.write`
scope (`python scripts/authorize.py` asks for it).

## What is worth building instead

Almost none of this project is X-specific. The quote dataset, the image rendering,
the DST-correct scheduler, the container and the CI are all platform-agnostic. Only
the publishing step knows what X is. So "make it free" means changing where it
publishes, not rebuilding it.

### 1. A self-updating GitHub profile README (recommended)

A profile README is the page people land on after finding you through your code.
An image that changes every day, dated, reads as *something is running* in a way a
static README does not — and it reaches the audience that makes a personal project
worth having.

- The scheduled workflow already renders the image
- Commit `quote.png` to a repository instead of uploading it to X
- Embed it in the profile repository (`ahmedsaed/ahmedsaed`)

No API, no tokens, no credits, no terms of service that can be withdrawn.

One side effect: a daily commit appears on the contribution graph. Some people like
that the graph looks alive; others consider it padding. Committing to a separate
repository keeps the graph human.

### 2. A permanent home on GitHub Pages

Today's quote on a page, an archive of every previous day, and an RSS feed. This
gives a URL that can go in a bio, and the archive is where "alive" becomes real —
an unbroken run of 200 days is a more interesting artifact than any single post.
RSS lets anyone follow it without an account on anything.

### 3. Keep X, for about a coffee a year

$5.50/year for the original design, with the code already written. Buy credits at
console.x.com, re-run `scripts/authorize.py` for a token with `media.write`, and
set a spending limit.

### Other free destinations, and why they lost

Bluesky (free, `atproto`), Mastodon (free, `Mastodon.py`), a Telegram channel and a
Discord webhook are all free and all support images. They were considered and set
aside: they are not platforms this account uses, and none offers the visibility X
would have. They remain easy to add if that changes — the publishing step is the
only part that would differ.

## Making it feel alive rather than scheduled

A cron job that emits the same layout daily reads as a cron job. Cheap variation
makes it read as presence:

- Pick the palette from the season, or from the weather in Cairo
- Put the streak on the image — day 1 and day 200 should not look identical
- Vary the crop and typography so no two days look stamped from one template

## Suggested order

1. Publish to a repository file and embed it in the profile README
2. Add the Pages archive and RSS feed
3. Add the variation above, which is what separates presence from automation
4. Optionally add X back later, by funding credits and re-adding the publisher

Step 1 is mostly rewiring: the publisher becomes "commit a file" rather than "call
an API", and the existing workflow does the rest.
