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
| `TZ` | no | Timezone for log timestamps |
| `POST_INTERVAL_SECONDS` | no | Keep running and post every N seconds. Prefer a real scheduler — see [Scheduling](#scheduling) |

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
docker compose run --rm motivator --dry-run   # renders, posts nothing
```

The container posts once and exits, so the schedule comes from the host — see
[Scheduling](#scheduling) below.

### 3. Local checkout without Docker

Use `./setup.sh` to create the venv, then point the units in
[Scheduling](#scheduling) at `run.sh` instead of `docker compose`:

```ini
ExecStart=/srv/Motivator_McBot/run.sh
```

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

The container posts once and exits. Drive it from a scheduler that understands
timezones rather than `POST_INTERVAL_SECONDS`, which just sleeps between posts
and drifts away from any wall-clock time you had in mind.

Set `TZ` in `docker-compose.yml` to keep log timestamps readable (it defaults to
`Africa/Cairo`). `TZ` does not decide when the bot posts; the host scheduler does.

### systemd timer

`OnCalendar` takes an IANA timezone, so daylight saving is handled for you. Egypt
switches between UTC+2 and UTC+3, which would shift a hardcoded UTC cron by an
hour twice a year.

```ini
# /etc/systemd/system/motivator.service
[Unit]
Description=Motivator McBot
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
WorkingDirectory=/srv/Motivator_McBot
ExecStart=/usr/bin/docker compose run --rm motivator
```

```ini
# /etc/systemd/system/motivator.timer
[Unit]
Description=Post a motivational quote at 08:00 Cairo time

[Timer]
OnCalendar=*-*-* 08:00:00 Africa/Cairo
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
systemd-analyze calendar "*-*-* 08:00:00 Africa/Cairo"   # check before enabling
sudo systemctl daemon-reload
sudo systemctl enable --now motivator.timer
systemctl list-timers motivator.timer
```

Run `systemd-analyze calendar` first: the timezone suffix needs a recent systemd,
and that command prints the next elapse if your version supports it. If it errors,
set the host timezone with `timedatectl set-timezone Africa/Cairo` and use a bare
`OnCalendar=*-*-* 08:00:00`. `Persistent=true` runs a missed post on the next
boot — drop it if you would rather skip.

### cron

`CRON_TZ` must be at the top of the crontab, before the job line. It is supported
by cronie and Vixie cron (Debian, Ubuntu, RHEL).

```cron
CRON_TZ=Africa/Cairo
0 8 * * * cd /srv/Motivator_McBot && docker compose run --rm motivator >> /var/log/motivator.log 2>&1
```

If you previously ran `docker compose up -d` with `POST_INTERVAL_SECONDS` set,
run `docker compose down` first or the old container keeps posting alongside the
timer. The same goes for the `post.yml` workflow — disable it from the Actions
tab if the server is doing the posting.

## Notes on the X API

X retired the v1.1 `media/upload` endpoint in March 2025 and Tweepy still targets
it, so the bot uploads media through the v2 endpoint directly and only falls back
to Tweepy's v1.1 path if that fails. Posting itself goes through Tweepy's v2
client. The free API tier allows a limited number of posts per month, which is
ample for one post a day.

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
