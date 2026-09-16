# Motivator McBot

A bot that posts motivational quotes rendered over a random photo from Unsplash.

![build](https://github.com/ahmedsaed/Motivator_McBot/actions/workflows/build.yml/badge.svg)

## How it works

1. Pulls a quote from [Quotable](https://github.com/lukePeavey/quotable), falling
   back to a built-in list when the API is unreachable.
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
| `POST_INTERVAL_SECONDS` | no | If set, keep running and post on this interval |

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
docker run --rm --env-file .env -v "$PWD/images:/app/images" motivator-mcbot --dry-run
```

Prebuilt multi-arch images (amd64 + arm64) are published to GHCR on every push
to `main`:

```bash
docker pull ghcr.io/ahmedsaed/motivator_mcbot:latest
```

The container runs as a non-root user and exits after a single post, which suits
a cron-style scheduler. Set `POST_INTERVAL_SECONDS` to make it a long-running
service instead.

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

### 2. Docker Compose on a server

```bash
git clone https://github.com/ahmedsaed/Motivator_McBot.git
cd Motivator_McBot
cp .env.example .env && $EDITOR .env
docker compose up -d
docker compose logs -f
```

`docker-compose.yml` sets `POST_INTERVAL_SECONDS` to 86400, so the container
stays up and posts once a day, restarting automatically if the host reboots.

To post on a precise schedule instead, drop `POST_INTERVAL_SECONDS` and let cron
run a one-shot container:

```cron
0 9 * * * cd /srv/Motivator_McBot && docker compose run --rm motivator >> /var/log/motivator.log 2>&1
```

### 3. systemd timer with a local checkout

For a server without Docker, use `run.sh` plus a timer:

```ini
# /etc/systemd/system/motivator.service
[Service]
Type=oneshot
WorkingDirectory=/srv/Motivator_McBot
ExecStart=/srv/Motivator_McBot/run.sh

# /etc/systemd/system/motivator.timer
[Timer]
OnCalendar=*-*-* 09:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

```bash
sudo systemctl enable --now motivator.timer
```

### Verifying a deployment

- `docker compose logs -f` (or the Actions run log) should end with
  `Response to tweet:` and a tweet id.
- A 401 means bad credentials; a 403 usually means the app is not set to Read
  and Write, or the access tokens predate that change.
- The most recent rendered image is written to `images/output_image.jpg`.

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
| `old-bot.js` / `bot-example.py` | Earlier versions, kept for reference |
