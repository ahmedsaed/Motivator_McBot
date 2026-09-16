#!/usr/bin/env python3
"""Download the quotable dataset and write the filtered subset the bot uses.

The api.quotable.io service is defunct, but the data behind it is still
maintained as a plain JSON file. This fetches that file and applies the same
filters the bot used to send as query parameters, so the bot can pick quotes
locally with no network call.

    python scripts/fetch_quotes.py                       # defaults below
    python scripts/fetch_quotes.py --tags wisdom,life    # a different subset
    python scripts/fetch_quotes.py --max-length 280      # allow longer quotes
"""

import argparse
import json
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://raw.githubusercontent.com/quotable-io/data/master/data/quotes.json"
SOURCE_REPO = "https://github.com/quotable-io/data"

# These mirror the query string the bot used against api.quotable.io:
#   ?tags=inspirational|success|motivational|leadership&maxLength=220
DEFAULT_TAGS = ("inspirational", "success", "motivational", "leadership")
DEFAULT_MAX_LENGTH = 220
DEFAULT_OUTPUT = Path(__file__).resolve().parent.parent / "data" / "quotes.json"


def slugify(tag):
    """'Famous Quotes' -> 'famous-quotes', matching the API's tag slugs."""
    return re.sub(r"[^a-z0-9]+", "-", tag.lower()).strip("-")


def fetch(url):
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def select(quotes, tags, max_length):
    wanted = {slugify(tag) for tag in tags}
    seen = set()
    selected = []

    for quote in quotes:
        content = (quote.get("content") or "").strip()
        if not content or len(content) > max_length:
            continue
        if wanted and not wanted & {slugify(t) for t in quote.get("tags", [])}:
            continue
        if content in seen:
            continue
        seen.add(content)
        selected.append({"content": content, "author": quote.get("author", "")})

    selected.sort(key=lambda q: q["content"])
    return selected


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--tags",
        default=",".join(DEFAULT_TAGS),
        help="comma-separated tag slugs to keep; empty string keeps every tag",
    )
    parser.add_argument("--max-length", type=int, default=DEFAULT_MAX_LENGTH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--source", default=SOURCE_URL)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    tags = [t.strip() for t in args.tags.split(",") if t.strip()]

    print(f"Downloading {args.source}")
    quotes = fetch(args.source)
    print(f"  {len(quotes)} quotes in the source dataset")

    selected = select(quotes, tags, args.max_length)
    print(f"  {len(selected)} match tags={tags or 'any'} max_length={args.max_length}")

    if not selected:
        print("Refusing to write an empty quote file", file=sys.stderr)
        return 1

    payload = {
        "source": SOURCE_REPO,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "filters": {"tags": tags, "max_length": args.max_length},
        "quotes": selected,
    }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    print(f"Wrote {len(selected)} quotes to {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
