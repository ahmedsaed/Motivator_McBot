"""Motivator McBot — posts a motivational quote rendered over a random photo.

Configuration comes from environment variables (see .env.example). A legacy
``config.py`` module is still honoured so existing local checkouts keep working.
"""

import argparse
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from random import choice

import requests
import tweepy
from PIL import Image, ImageDraw, ImageEnhance, ImageFont, ImageStat
from requests_oauthlib import OAuth1Session

log = logging.getLogger("motivator")

# Maximum tweet length
MAX_LENGTH = 280

# X retired the v1.1 media/upload endpoint in March 2025; v2 is the supported
# route. Tweepy still targets v1.1, so we upload here and fall back to tweepy.
MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"

QUOTE_API_URL = "https://api.quotable.io/random"
UNSPLASH_API_URL = "https://api.unsplash.com/photos/random"

IMAGE_SIZE = (1200, 600)
TEXT_COLOR = "#D5CEA3"
STROKE_COLOR = "#3C2A21"
HTTP_TIMEOUT = 20

FONT_CANDIDATES = (
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "C:\\Windows\\Fonts\\arialbd.ttf",
    "arial.ttf",
)


@dataclass
class Settings:
    """Credentials and tunables, resolved from the environment."""

    api_key: str = ""
    api_secret: str = ""
    access_token: str = ""
    access_token_secret: str = ""
    unsplash_api_key: str = ""
    image_query: str = "mountains lake nature"
    font_path: str = ""
    output_path: Path = Path("images/output_image.jpg")

    @classmethod
    def from_env(cls):
        legacy = _legacy_config()

        def value(*names, default=""):
            for name in names:
                found = os.environ.get(name) or legacy.get(name)
                if found:
                    return found
            return default

        return cls(
            api_key=value("API_KEY"),
            api_secret=value("API_SECRET"),
            access_token=value("ACCESS_TOKEN"),
            access_token_secret=value("ACCESS_TOKEN_SECRET"),
            # UNSPASH_API_KEY is the original (misspelled) name, kept for
            # backwards compatibility with existing config.py files.
            unsplash_api_key=value("UNSPLASH_API_KEY", "UNSPASH_API_KEY"),
            image_query=value("IMAGE_QUERY", default="mountains lake nature"),
            font_path=value("FONT_PATH"),
            output_path=Path(value("OUTPUT_PATH", default="images/output_image.jpg")),
        )

    def missing_credentials(self):
        required = {
            "API_KEY": self.api_key,
            "API_SECRET": self.api_secret,
            "ACCESS_TOKEN": self.access_token,
            "ACCESS_TOKEN_SECRET": self.access_token_secret,
        }
        return sorted(name for name, val in required.items() if not val)


def _legacy_config():
    """Read the old config.py module if one is present."""
    try:
        import config
    except ImportError:
        return {}
    return {name: getattr(config, name) for name in dir(config) if name.isupper()}


def get_hard_coded_quote():
    # Offline fallback for when the quote API is unreachable.
    quotes_data = [
        "People will throw stones at you. Don't throw them back. Collect them all and build an empire",
        "Nothing is impossible, the word itself says I'm possible",
        "I may not be there yet, but I am closer than I was yesterday",
        "I may not be the best... but I sure am trying my best",
        "There's about to be a shift in your life. Get ready for your blessings. You've been through enough and a breakthrough is on the way",
        "Fight for your dreams and your dreams will fight for you",
        "Don't quit. Suffer now and live the rest of your life as a champion",
        "no matter your current circumstances if you can imagine something better for yourself you can create it",
        "Being upset will not solve any problem, but getting UP and SET your way to your goals will",
        "Being negative only causes depression. So hold your head up high, put a smile on your face & go live a positive life",
        "Things turn out best for the people who make the best of the way things turn out",
        "Life is not about winning, it's about not giving up",
        "Every king was once a crying baby. Every great building was once a blueprint",
        "Do not live your life full of WHAT IF's. rather, live your life full of WHY NOT's",
        "Perseverance is not a long race; it is many short races one after another",
        "A pessimist sees the difficulty in every opportunity; an optimist sees the opportunity in every difficulty",
        "Some people want it to happen, some wish it would happen, others make it happen",
        "When you truly believe in what you are doing, it shows. And it pays. Winners in life are those who are excited about where they are going",
        "Not everything that is faced can be changed, but nothing can be changed until it is faced",
        "It does not matter how many times you get knocked down, but how many times you get up",
        "When there's something you really want, fight for it. Don't give up no matter how hopeless it seems",
        "The sun is a daily reminder that we too can rise again from the darkness, that we too can shine our own light",
        "The difference between who you are and who you want to be is what you do",
        "Success is finding satisfaction in giving a little more than you take",
        "What defines us is how well we rise after we fall",
        "Success is where preparation and opportunity meet",
        "Every champion was once a contender that didn't give up",
        "Live your vision and demand your success",
        "Success is the child of drudgery and perseverance. It cannot be coaxed or bribed; pay the price and it is yours",
        "To succeed you have to believe in something with such passion that it becomes a reality",
        "Dream big, it's the first step to success",
        "Success is sweet and sweeter if long delayed and gotten through many struggles and defeats",
        "You deserve to be successful and happy, smile :)",
        "Our greatest glory is not in never falling, but in rising every time we fall",
        "The key to success is to focus our conscious mind on things we desire not things we fear",
        "Success comes from knowing that you did your best to become the best that you are capable of becoming",
        "The harder you work for something, the greater you'll feel when you achieve it",
        "The difference between a successful person and others is not a lack of strength, not a lack of knowledge, but rather a lack of will",
        "Man needs his difficulties because they are necessary to enjoy success",
        "The secret of success is to do the common thing uncommonly well",
        "Success is how high you bounce when you hit bottom",
        "Success isn't measured by money or power or social rank. Success is measured by your discipline and inner peace",
        "Success is not final, failure is not fatal: it is the courage to continue that counts",
    ]

    return choice(quotes_data)


def generate_random_color():
    # Generate a random color for when no background photo is available.
    return "#" + "".join(choice("0123456789ABCDEF") for _ in range(6))


def fetch_quote():
    """Fetch a quote, falling back to the built-in list if the API is down."""
    params = {
        "tags": "inspirational|success|motivational|leadership",
        "maxLength": 220,
    }

    log.info("Fetching quote")
    try:
        response = requests.get(QUOTE_API_URL, params=params, timeout=HTTP_TIMEOUT)
        response.raise_for_status()
        quote = response.json()["content"]
        log.info("Quote fetched successfully")
        return quote
    except (requests.RequestException, ValueError, KeyError) as error:
        log.warning("Couldn't fetch quote (%s); using built-in list", error)
        return get_hard_coded_quote()


def fetch_background_image(settings):
    """Return (image_url, photographer_name) from Unsplash, or (None, None)."""
    if not settings.unsplash_api_key:
        log.info("No Unsplash API key set; using a solid colour background")
        return None, None

    log.info("Fetching background image")
    params = {"query": settings.image_query, "orientation": "landscape"}
    headers = {"Authorization": f"Client-ID {settings.unsplash_api_key}"}

    try:
        response = requests.get(
            UNSPLASH_API_URL, params=params, headers=headers, timeout=HTTP_TIMEOUT
        )
        response.raise_for_status()
        data = response.json()
        return data["urls"]["regular"], data["user"]["name"]
    except (requests.RequestException, ValueError, KeyError) as error:
        log.warning("Couldn't fetch image from Unsplash: %s", error)
        return None, None


def load_font(font_path, size):
    """Load a bold sans font, trying the configured path then known locations."""
    for candidate in (font_path, *FONT_CANDIDATES):
        if not candidate:
            continue
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue

    log.warning("No TrueType font found; falling back to Pillow's default")
    return ImageFont.load_default(size=size)


def wrap_text(draw, text, font, max_width):
    """Greedily wrap text to lines no wider than max_width."""
    lines = []
    current = ""

    for word in text.split():
        candidate = f"{current} {word}".strip()
        width = draw.textbbox((0, 0), candidate, font=font)[2]
        if width <= max_width or not current:
            current = candidate
        else:
            lines.append(current)
            current = word

    if current:
        lines.append(current)

    return lines


def fit_text(draw, text, font_path, max_width, max_height, stroke_width):
    """Pick the largest font size at which the wrapped quote fits the canvas."""
    for size in range(80, 23, -2):
        font = load_font(font_path, size)
        lines = wrap_text(draw, text, font, max_width)
        wrapped = "\n".join(lines)
        box = draw.multiline_textbbox(
            (0, 0), wrapped, font=font, align="center", stroke_width=stroke_width
        )
        if box[2] - box[0] <= max_width and box[3] - box[1] <= max_height:
            return wrapped, font, box

    # Nothing fit — render at the smallest size and let it overflow slightly.
    font = load_font(font_path, 24)
    wrapped = "\n".join(wrap_text(draw, text, font, max_width))
    box = draw.multiline_textbbox(
        (0, 0), wrapped, font=font, align="center", stroke_width=stroke_width
    )
    return wrapped, font, box


def build_background(background_image_url):
    """Return a canvas holding either the downloaded photo or a flat colour."""
    width, height = IMAGE_SIZE
    canvas = Image.new("RGB", (width, height))

    if background_image_url:
        try:
            response = requests.get(background_image_url, timeout=HTTP_TIMEOUT)
            response.raise_for_status()
            background = Image.open(BytesIO(response.content)).convert("RGB")
            canvas.paste(background.resize((width, height)), (0, 0))
            return canvas
        except (requests.RequestException, OSError) as error:
            log.warning("Couldn't download background image: %s", error)

    ImageDraw.Draw(canvas).rectangle(
        [(0, 0), (width, height)], fill=generate_random_color()
    )
    return canvas


def setup_image(quote, background_image_url, output_path, font_path=""):
    """Render the quote over the background and save it to output_path."""
    width, height = IMAGE_SIZE
    canvas = build_background(background_image_url)

    # Darken bright photos so the light text keeps its contrast.
    brightness = sum(ImageStat.Stat(canvas).mean[:3]) / 3
    if brightness > 110:
        canvas = ImageEnhance.Brightness(canvas).enhance(110 / brightness)

    draw = ImageDraw.Draw(canvas)
    stroke_width = 5
    text, font, box = fit_text(
        draw,
        quote,
        font_path,
        max_width=int(width * 0.9),
        max_height=int(height * 0.8),
        stroke_width=stroke_width,
    )

    # multiline_textbbox is measured from the anchor, so subtract its offset.
    x = (width - (box[2] - box[0])) / 2 - box[0]
    y = (height - (box[3] - box[1])) / 2 - box[1]

    draw.multiline_text(
        (x, y),
        text,
        font=font,
        fill=TEXT_COLOR,
        align="center",
        stroke_width=stroke_width,
        stroke_fill=STROKE_COLOR,
    )

    return save_canvas(canvas, output_path)


def save_canvas(canvas, output_path):
    """Save the canvas, falling back to a temp file if the target is unwritable.

    A bind-mounted directory is commonly owned by root while the container runs
    as an unprivileged user, and failing to keep a local copy is not a good
    enough reason to skip the post.
    """
    fallback = Path(tempfile.gettempdir()) / "motivator_output.jpg"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.save(output_path, quality=90)
        log.info("Image written to %s", output_path)
        return output_path
    except OSError as error:
        if output_path.resolve() == fallback.resolve():
            raise
        log.warning(
            "Couldn't write %s (%s); falling back to %s", output_path, error, fallback
        )

    canvas.save(fallback, quality=90)
    log.info("Image written to %s", fallback)
    return fallback


def upload_media(settings, image_path):
    """Upload the image via the X v2 media endpoint, falling back to v1.1."""
    oauth = OAuth1Session(
        client_key=settings.api_key,
        client_secret=settings.api_secret,
        resource_owner_key=settings.access_token,
        resource_owner_secret=settings.access_token_secret,
    )

    try:
        with open(image_path, "rb") as handle:
            response = oauth.post(
                MEDIA_UPLOAD_URL,
                files={"media": handle},
                data={"media_category": "tweet_image"},
                timeout=60,
            )
        if response.ok:
            payload = response.json()
            payload = payload.get("data", payload)
            media_id = payload.get("id") or payload.get("media_id_string")
            if media_id:
                log.info("Uploaded media via v2 endpoint (id=%s)", media_id)
                return media_id
        log.warning(
            "v2 media upload failed (%s): %s", response.status_code, response.text[:200]
        )
    except requests.RequestException as error:
        log.warning("v2 media upload errored: %s", error)

    log.info("Falling back to the v1.1 media upload endpoint")
    auth = tweepy.OAuth1UserHandler(
        consumer_key=settings.api_key,
        consumer_secret=settings.api_secret,
        access_token=settings.access_token,
        access_token_secret=settings.access_token_secret,
    )
    return tweepy.API(auth).media_upload(str(image_path)).media_id


def post_tweet(settings, body, image_path):
    log.info("Tweeting:\n%s", body)

    client = tweepy.Client(
        consumer_key=settings.api_key,
        consumer_secret=settings.api_secret,
        access_token=settings.access_token,
        access_token_secret=settings.access_token_secret,
    )

    media_id = upload_media(settings, image_path)
    return client.create_tweet(text=body, media_ids=[media_id])


def build_tweet_body(quote, photographer):
    credit = f"\n\nPhoto by {photographer} on Unsplash" if photographer else ""
    body = f"{quote}{credit}\n\n#MotivationalQuotes"

    if len(body) > MAX_LENGTH:
        overflow = len(body) - MAX_LENGTH
        quote = quote[: max(0, len(quote) - overflow - 1)].rstrip() + "…"
        body = f"{quote}{credit}\n\n#MotivationalQuotes"

    return body


def run_once(settings, dry_run=False):
    quote = fetch_quote()
    background_image_url, photographer = fetch_background_image(settings)

    image_path = setup_image(
        quote, background_image_url, settings.output_path, settings.font_path
    )
    body = build_tweet_body(quote, photographer)

    if dry_run:
        log.info("Dry run — not posting. Tweet would have been:\n%s", body)
        return None

    response = post_tweet(settings, body, image_path)
    log.info("Response to tweet: %s", response)
    return response


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="render the image and print the tweet without posting it",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="where to write the rendered image (default: images/output_image.jpg)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("POST_INTERVAL_SECONDS", "0")),
        help="if set, keep running and post every N seconds instead of exiting",
    )
    return parser.parse_args(argv)


def main(argv=None):
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        stream=sys.stdout,
    )

    args = parse_args(argv)
    settings = Settings.from_env()
    if args.output:
        settings.output_path = args.output

    if not args.dry_run:
        missing = settings.missing_credentials()
        if missing:
            log.error("Missing required credentials: %s", ", ".join(missing))
            return 1

    while True:
        try:
            run_once(settings, dry_run=args.dry_run)
        except Exception:
            log.exception("Run failed")
            if not args.interval:
                return 1

        if not args.interval:
            return 0

        log.info("Sleeping %s seconds until the next post", args.interval)
        time.sleep(args.interval)


if __name__ == "__main__":
    sys.exit(main())
