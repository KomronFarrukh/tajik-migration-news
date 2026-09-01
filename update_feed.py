#!/usr/bin/env python3
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
CONFIG_PATH = ROOT / "config.json"
FEED_PATH = ROOT / "feed.xml"
MRSS = "http://search.yahoo.com/mrss/"
NS = {"media": MRSS}


def error(message):
    print("ERROR:", message)
    sys.exit(1)


def valid_url(value):
    try:
        parsed = urlparse(value or "")
        return parsed.scheme in ("http", "https") and bool(parsed.netloc)
    except Exception:
        return False


def main():
    try:
        config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        error(f"Invalid config.json: {exc}")

    for section in ("feed", "editorial_language", "editorial_interests", "editorial_safety", "images"):
        if section not in config:
            error(f"Missing config section: {section}")

    try:
        root = ET.parse(FEED_PATH).getroot()
    except Exception as exc:
        error(f"Invalid feed.xml: {exc}")

    if root.tag != "rss" or root.attrib.get("version") != "2.0":
        error("RSS 2.0 required")

    channel = root.find("channel")
    if channel is None:
        error("Missing channel")

    if (channel.findtext("language") or "").strip() != config["feed"]["language"]:
        error("Feed language differs from config")

    items = channel.findall("item")
    if len(items) > int(config["feed"].get("max_items", 120)):
        error("Too many feed items")

    seen_links = set()
    seen_guids = set()

    for i, item in enumerate(items, 1):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        guid = (item.findtext("guid") or "").strip()
        source = (item.findtext("source") or "").strip()
        description = (item.findtext("description") or "").strip()

        if not title or not source or not description:
            error(f"Item {i} has an empty required field")
        if not valid_url(link):
            error(f"Item {i} has an invalid link")
        if not guid:
            error(f"Item {i} has no guid")
        if link in seen_links or guid in seen_guids:
            error(f"Item {i} duplicates an existing item")
        seen_links.add(link)
        seen_guids.add(guid)

        media = item.findall("media:content", NS)
        image_enclosures = [x for x in item.findall("enclosure") if x.attrib.get("type", "").startswith("image/")]
        if len(media) > 1 or len(image_enclosures) > 1:
            error(f"Item {i} has more than one image")
        for node in media + image_enclosures:
            image_url = node.attrib.get("url", "")
            if image_url and not valid_url(image_url):
                error(f"Item {i} has an invalid image URL")

    print(f"OK: feed.xml validated ({len(items)} items)")
    print("No news was fetched or added by this script.")


if __name__ == "__main__":
    main()
