# Motivator McBot

A bot that posts motivational quotes rendered over a random photo from Unsplash.

![build](https://github.com/ahmedsaed/Motivator_McBot/actions/workflows/build.yml/badge.svg)

## How it works

1. Picks a quote from the bundled dataset in [`data/quotes.json`](data/quotes.json).
2. Pulls a random landscape photo from Unsplash (or a solid colour if no key is set).
3. Renders the quote over the photo with Pillow and posts it to X/Twitter.

## Configuration

Every setting is an environment variable — see [`.env.example`](.env.example).
The four X credentials are required; everything else is optional.

| Variable | Required | Purpose |
| --- | --- | --- |
| `API_KEY`, `API_SECRET` | yes | X app consumer keys |
| `ACCESS_TOKEN`, `ACCESS_TOKEN_SECRET` | yes | X user access tokens |
| `UNSPLASH_API_KEY` | no | Background photos; omit for a solid colour |
| `IMAGE_QUERY` | no | Unsplash search terms (default `mountains lake nature`) |
| `FONT_PATH` | no | Override the bold sans font used for rendering |
| `OUTPUT_PATH` | no | Where the rendered image is written |
| `QUOTES_FILE` | no | Path to the quote dataset (default `data/quotes.json`) |
| `QUOTE_API_URL` | no | Fetch quotes from a remote API, using the dataset as fallback |
| `TZ` | no | Timezone for `POST_AT` and log timestamps |
| `POST_AT` | no | `HH:MM` local time to post daily; the container schedules itself |
| `POST_INTERVAL_SECONDS` | no | Post every N seconds instead of at a set time — see [Scheduling](#scheduling) |

An existing `config.py` from the original version is still read, so old checkouts
keep working without changes.

### Getting credentials

1. Create a project and app at the [X developer portal](https://developer.x.com/en/portal/dashboard).
2. Set the app's User authentication settings to **Read and Write**.
3. Generate the consumer keys and the access token/secret. Regenerate the access
   tokens if you changed permissions after creating them — otherwise posting
   fails with a 403.
4. Optionally register an app at [Unsplash](https://unsplash.com/developers) for
   the background photos.

## Quotes

Quotes come from a local dataset, so a normal run makes no quote-related network
call at all. The bot previously used `api.quotable.io`, which is
[defunct](https://github.com/lukePeavey/quotable/issues/271) — its data lives on
at [quotable-io/data](https://github.com/quotable-io/data).

[`data/quotes.json`](data/quotes.json) holds 181 quotes, the same selection the
old API query asked for (`inspirational`, `success`, `motivational` and
`leadership`, no longer than 220 characters). Regenerate or re-filter it with:

```bash
python scripts/fetch_quotes.py                             # the defaults above
python scripts/fetch_quotes.py --tags wisdom,life          # 559 quotes
python scripts/fetch_quotes.py --tags "" --max-length 280  # everything that fits
```

At one post a day, 181 quotes cycle in about six months. Widen `--tags` if you
want a longer rotation — `--tags ""` keeps all 2127 quotes in the source dataset.

If the dataset is missing or unreadable the bot falls back to a small built-in
list, so it always has something to post. Setting `QUOTE_API_URL` makes it try
that URL first and fall back to the dataset.

## Running locally

```bash
./setup.sh                          # creates .venv, installs deps, copies .env
$EDITOR .env                        # fill in credentials
./.venv/bin/python bot.py --dry-run # renders images/output_image.jpg, posts nothing
./.venv/bin/python bot.py           # posts for real
```

`--dry-run` needs no credentials, which makes it a useful smoke test.

## Running with Docker

```bash
docker build -t motivator-mcbot .
docker run --rm --env-file .env -v motivator-images:/app/images motivator-mcbot --dry-run
```

Prebuilt multi-arch images (amd64 + arm64) are published to GHCR on every push
to `main`:

```bash
docker pull ghcr.io/ahmedsaed/motivator_mcbot:latest
```

The container runs as a non-root user and exits after a single post, which suits
a cron-style scheduler. Set `POST_INTERVAL_SECONDS` to make it a long-running
service instead.

Rendered images go to a named volume rather than a bind mount. Docker creates a
missing bind-mount directory owned by root, which the unprivileged container user
cannot write to. If you would rather have the images on the host filesystem,
create the directory with matching ownership first:

```bash
mkdir -p images && sudo chown 10001:10001 images
```

then swap the volume line in `docker-compose.yml` for `./images:/app/images`.
Without that `chown` the bot logs a warning and writes to a temp file inside the
container instead of failing.

## Deployment

Three options, cheapest first.

### 1. GitHub Actions (no server)

The [`post.yml`](.github/workflows/post.yml) workflow runs the bot on a cron
schedule using GitHub's runners.

1. Go to **Settings → Secrets and variables → Actions** and add `API_KEY`,
   `API_SECRET`, `ACCESS_TOKEN`, `ACCESS_TOKEN_SECRET`, and optionally
   `UNSPLASH_API_KEY`.
2. Open the **Actions** tab, select **Post a quote**, and click **Run workflow**
   with *dry run* ticked to confirm everything is wired up.
3. Leave it enabled and it posts daily at 09:00 UTC. Edit the `cron:` line to
   change the time.

Scheduled workflows are best-effort — GitHub can delay them under load — and
they are disabled automatically after 60 days of repository inactivity. Good
enough for a quote bot, not for anything time-critical.

Actions cron is UTC only and has no notion of daylight saving, so a fixed local
time drifts by an hour twice a year. If that matters, schedule from a server
instead — see [Scheduling](#scheduling).

### 2. Docker Compose on a server

```bash
git clone https://github.com/ahmedsaed/Motivator_McBot.git
cd Motivator_McBot
cp .env.example .env && $EDITOR .env
docker compose run --rm motivator --once --dry-run   # check it works
docker compose up -d                                 # start the scheduler
docker compose logs -f
```

The container schedules itself and posts daily at `POST_AT` — see
[Scheduling](#scheduling).

### 3. Local checkout without Docker

Use `./setup.sh` to create the venv, then run the bot with the same flags:

```bash
POST_AT=08:00 TZ=Africa/Cairo ./.venv/bin/python bot.py
```

`run.sh` is a thin cron wrapper for the same thing if you would rather schedule
it from the host.

### Verifying a deployment

- `docker compose logs -f` (or the Actions run log) should end with
  `Response to tweet:` and a tweet id.
- A 401 means bad credentials; a 403 usually means the app is not set to Read
  and Write, or the access tokens predate that change.
- The most recent rendered image is in the `images` volume; copy it out with
  `docker compose cp motivator:/app/images/output_image.jpg .`
- `Couldn't write ... falling back to /tmp` means the output directory is not
  writable by the container user; see the bind-mount note above.

## Scheduling

The container schedules itself. Set `POST_AT` to a `HH:MM` local time and `TZ`
to your zone, and it posts once a day at that time, sleeping in between — no
host cron, no systemd, no Docker socket. This is what `docker-compose.yml` does
by default (08:00 `Africa/Cairo`).

```yaml
environment:
  TZ: Africa/Cairo
  POST_AT: "08:00"
restart: unless-stopped
```

```bash
docker compose up -d
docker compose logs -f     # "Next post at 2026-09-17 08:00 EEST"
```

`restart: unless-stopped` brings the scheduler back after a reboot or a crash.
On start it logs the next post time, so you can confirm the schedule without
waiting for it.

The time is a **local wall-clock** time: the bot posts at 08:00 whether or not
daylight saving is in effect, so the real interval is 23 or 25 hours across a
DST change rather than 24. Egypt switches between UTC+2 and UTC+3, which is
exactly the case a fixed UTC schedule gets wrong.

A missed post is skipped, not caught up — if the host is down at 08:00 the bot
posts at 08:00 the next day.

### One-off runs

`--once` posts immediately and exits, ignoring `POST_AT`, which is what you want
for a smoke test on a machine whose compose file sets a schedule:

```bash
docker compose run --rm motivator --once --dry-run   # renders, posts nothing
docker compose run --rm motivator --once             # posts right now
```

### Other options

`POST_INTERVAL_SECONDS` posts every N seconds instead of at a set time. It
drifts relative to the clock, so prefer `POST_AT` unless you genuinely want a
fixed interval.

To drive the schedule from the host instead, leave `POST_AT` unset and run
`docker compose run --rm motivator --once` from cron (`CRON_TZ=Africa/Cairo` at
the top of the crontab) or a systemd timer
(`OnCalendar=*-*-* 08:00:00 Africa/Cairo`; check your systemd accepts the
timezone suffix with `systemd-analyze calendar` first).

## Notes on the X API

X retired the v1.1 `media/upload` endpoint in March 2025 and Tweepy still targets
it, so the bot uploads media through the v2 endpoint directly and only falls back
to Tweepy's v1.1 path if that fails. Posting itself goes through Tweepy's v2
client. The free API tier allows a limited number of posts per month, which is
ample for one post a day.

`POST /2/media/upload` returns 503 for some accounts. The bot retries four
times with a growing delay (2s, 4s, 8s) and then fails the run — it does not
fall back to v1.1, which X retired, and it does not post without the image.

If posting fails, `--check` probes the API without posting anything:

```bash
docker compose run --rm motivator --check
```

It calls `GET /2/users/me` and then attempts a media upload, printing the status
and body of each. A 503 on both is not media-specific: X replaced its tiered
plans with pay-per-use in February 2026, and persistent 503s across v2 endpoints
have been reported by accounts whose plan or billing is not in a working state.
A 200 on `users/me` with a 503 on the upload narrows the problem to the media
endpoint. A 401 means the keys are wrong; a 403 means the app lacks the access.

## Repository layout

| Path | Purpose |
| --- | --- |
| `bot.py` | The bot |
| `Dockerfile` | Container image |
| `docker-compose.yml` | Server deployment |
| `.github/workflows/build.yml` | Smoke test + multi-arch image build |
| `.github/workflows/post.yml` | Scheduled posting |
| `setup.sh` / `run.sh` | Local venv setup and cron wrapper |
| `scripts/fetch_quotes.py` | Rebuilds `data/quotes.json` from the upstream dataset |
| `data/quotes.json` | The bundled quote dataset |
| `old-bot.js` / `bot-example.py` | Earlier versions, kept for reference |
