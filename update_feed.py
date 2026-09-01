#!/usr/bin/env python3
import json, re, urllib.parse, urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime, format_datetime

ROOT = Path(__file__).resolve().parent
CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
FEED_PATH = ROOT / "feed.xml"

def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 TajikMigrationRSS/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()

def norm(s):
    return re.sub(r"\s+", " ", (s or "")).strip()

def relevant(title, description):
    text = (title + " " + description).lower()
    return any(k.lower() in text for k in CONFIG["relevance_keywords"])

def google_news_url(query):
    q = urllib.parse.quote(query)
    return f"https://news.google.com/rss/search?q={q}&hl=ru&gl=RU&ceid=RU:ru"

def load_existing():
    existing = {}
    if not FEED_PATH.exists():
        return existing
    try:
        root = ET.parse(FEED_PATH).getroot()
        for item in root.findall("./channel/item"):
            link = norm(item.findtext("link"))
            if link:
                existing[link] = {
                    "title": norm(item.findtext("title")),
                    "link": link,
                    "guid": norm(item.findtext("guid")) or link,
                    "pubDate": norm(item.findtext("pubDate")),
                    "description": norm(item.findtext("description")),
                    "categories": [norm(x.text) for x in item.findall("category") if norm(x.text)],
                    "source": norm(item.findtext("source"))
                }
    except Exception:
        pass
    return existing

def collect():
    found = {}
    for search in CONFIG["searches"]:
        try:
            root = ET.fromstring(fetch(google_news_url(search["query"])))
        except Exception as e:
            print("WARN", search["query"], e)
            continue
        for item in root.findall("./channel/item"):
            title = norm(item.findtext("title"))
            link = norm(item.findtext("link"))
            desc = norm(re.sub("<[^>]+>", " ", item.findtext("description") or ""))
            pub = norm(item.findtext("pubDate"))
            source = norm(item.findtext("source"))
            if not title or not link or not relevant(title, desc):
                continue
            found[link] = {
                "title": title,
                "link": link,
                "guid": link,
                "pubDate": pub,
                "description": desc or f"Новая публикация по теме миграции. Источник: {source or 'Google News'}.",
                "categories": [search["country"], search["topic"]],
                "source": source or "Google News"
            }
    return found

def date_key(item):
    try:
        return parsedate_to_datetime(item["pubDate"]).timestamp()
    except Exception:
        return 0

def write_feed(items):
    rss = ET.Element("rss", {"version": "2.0"})
    ch = ET.SubElement(rss, "channel")
    ET.SubElement(ch, "title").text = CONFIG["feed"]["title"]
    ET.SubElement(ch, "link").text = "https://news.google.com/"
    ET.SubElement(ch, "description").text = CONFIG["feed"]["description"]
    ET.SubElement(ch, "language").text = CONFIG["feed"]["language"]
    ET.SubElement(ch, "lastBuildDate").text = format_datetime(datetime.now(timezone.utc))
    ET.SubElement(ch, "ttl").text = "180"

    for x in sorted(items.values(), key=date_key, reverse=True)[:CONFIG["feed"]["max_items"]]:
        it = ET.SubElement(ch, "item")
        ET.SubElement(it, "title").text = x["title"]
        ET.SubElement(it, "link").text = x["link"]
        ET.SubElement(it, "guid", {"isPermaLink": "true"}).text = x.get("guid") or x["link"]
        if x.get("pubDate"):
            ET.SubElement(it, "pubDate").text = x["pubDate"]
        for c in x.get("categories", []):
            ET.SubElement(it, "category").text = c
        ET.SubElement(it, "source").text = x.get("source") or "Источник"
        ET.SubElement(it, "description").text = x.get("description") or ""

    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write(FEED_PATH, encoding="utf-8", xml_declaration=True)

existing = load_existing()
new = collect()
existing.update(new)
write_feed(existing)
print(f"Feed updated: {len(existing)} unique items")
