#!/usr/bin/env python3
"""Validate the editorial RSS feed.

This script does NOT search the web and does NOT publish news.
It only checks that feed.xml follows the editorial/publication rules in config.json.
"""

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


def fail(message):
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
        fail(f"Invalid config.json: {exc}")

    required_sections = (
        "feed",
        "publication",
        "editorial_language",
        "editorial_interests",
        "editorial_safety",
        "images",
    )
    for section in required_sections:
        if section not in config:
            fail(f"Missing config section: {section}")

    try:
        root = ET.parse(FEED_PATH).getroot()
    except Exception as exc:
        fail(f"Invalid feed.xml: {exc}")

    channel = root.find("channel")
    if channel is None:
        fail("Missing RSS channel")

    if (channel.findtext("language") or "").strip() != "tg":
        fail("RSS language must be tg")

    items = channel.findall("item")
    if len(items) > int(config["feed"].get("max_items", 120)):
        fail("feed.xml contains more than max_items")

    seen_guids = set()
    for index, item in enumerate(items, start=1):
        title = (item.findtext("title") or "").strip()
        description = item.findtext("description") or ""
        guid_node = item.find("guid")
        source_node = item.find("source")

        if not title:
            fail(f"Item {index}: missing title")
        if not description.strip():
            fail(f"Item {index}: missing description")
        if "⚡️" not in description:
            fail(f"Item {index}: description must use the approved lead format")

        # Public source URLs must not be exposed in item links or source attributes.
        if config["publication"].get("show_item_link") is False and item.find("link") is not None:
            fail(f"Item {index}: public item <link> is disabled")
        if source_node is None or not (source_node.text or "").strip():
            fail(f"Item {index}: source name is required")
        if config["publication"].get("show_source_url") is False and source_node is not None and "url" in source_node.attrib:
            fail(f"Item {index}: source URL must not be publicly exposed")

        if guid_node is None or not (guid_node.text or "").strip():
            fail(f"Item {index}: missing guid")
        guid = (guid_node.text or "").strip()
        if guid in seen_guids:
            fail(f"Item {index}: duplicate guid")
        seen_guids.add(guid)
        if guid_node.attrib.get("isPermaLink", "true").lower() != "false":
            fail(f"Item {index}: guid must use isPermaLink=false")
        if config["publication"].get("guid_must_not_be_source_url") and valid_url(guid):
            fail(f"Item {index}: guid must not expose the source URL")

        # Image compatibility: if an image is used, publish it in all common RSS forms.
        media_content = item.find("media:content", NS)
        media_thumb = item.find("media:thumbnail", NS)
        enclosure = item.find("enclosure")
        has_img_html = "<img " in description.lower()

        if media_content is not None:
            image_url = media_content.attrib.get("url", "")
            if not valid_url(image_url):
                fail(f"Item {index}: invalid media:content URL")
            if media_content.attrib.get("medium") != "image":
                fail(f"Item {index}: media:content medium must be image")
            if media_thumb is None or not valid_url(media_thumb.attrib.get("url", "")):
                fail(f"Item {index}: media:thumbnail is required when an image is used")
            if enclosure is None or not valid_url(enclosure.attrib.get("url", "")):
                fail(f"Item {index}: enclosure is required when an image is used")
            if not (enclosure.attrib.get("type", "").startswith("image/")):
                fail(f"Item {index}: enclosure type must be image/*")
            if not has_img_html:
                fail(f"Item {index}: HTML <img> is required for broad RSS/Telegram compatibility")
        elif media_thumb is not None or enclosure is not None or has_img_html:
            fail(f"Item {index}: incomplete image markup")

    print(f"OK: {len(items)} RSS items validated")


if __name__ == "__main__":
    main()
