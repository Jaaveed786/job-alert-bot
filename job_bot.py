"""All India Job Updates - automatic Telegram job poster.
Fetches jobs (Adzuna API + RSS feeds), removes duplicates, tags them,
and posts to your Telegram channel. Run on a schedule (GitHub Actions).
"""
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

import hashlib
import html
import json
import os
import re
import sys
import time
from pathlib import Path

# Ensure UTF-8 output handling for terminals and consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import feedparser
import requests

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
CHANNEL = os.getenv("CHANNEL", "@indiajobupdates_official")
ADZUNA_ID = os.getenv("ADZUNA_APP_ID", "")
ADZUNA_KEY = os.getenv("ADZUNA_APP_KEY", "")
DRY_RUN = os.getenv("DRY_RUN", "0") == "1"
MAX_POSTS = int(os.getenv("MAX_POSTS", "8"))      # per run
SEEN_FILE = Path("seen.json")
SOURCES_FILE = Path("sources.json")
HEADERS = {"User-Agent": "Mozilla/5.0 (JobUpdatesBot)"}

KEYWORDS = {
    "govt": ["recruitment", "vacancy", "vacancies", "notification", "sarkari", "ssc", "upsc",
             "railway", "rrb", "ibps", "psc", "bank po", "government", "govt", "police",
             "anganwadi", "drdo", "isro", "sbi"],
    "walkin": ["walk-in", "walk in", "walkin"],
    "internship": ["intern", "internship"],
    "fresher": ["fresher", "freshers", "graduate trainee", "entry level", "entry-level",
                "trainee", "0-1 year", "0 to 1 year", "0-2 year"],
}
IT_WORDS = ["developer", "software", "engineer", "data ", "python", "java", "devops", "qa ",
            "tester", "analyst", "cloud", "machine learning", "full stack", "frontend", "backend"]
EXP_RE = re.compile(r"\b([2-9]|1\d)\s*\+?\s*(?:-|to)?\s*\d*\s*(?:years|yrs|year)\b", re.I)
EMOJI = {"govt": "🏛", "walkin": "🚶", "internship": "🎓", "fresher": "🎓", "experienced": "💼"}
PRIORITY = ["govt", "walkin", "internship", "fresher", "experienced"]


def load_json(path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def key_for(link):
    link = re.sub(r"[?#].*$", "", link.strip().lower())
    return hashlib.sha1(link.encode()).hexdigest()


def clean(text, limit=0):
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = re.sub(r"\s+", " ", html.unescape(text)).strip()
    return text[:limit] if limit else text


def fetch_adzuna(queries):
    if not (ADZUNA_ID and ADZUNA_KEY):
        print("Adzuna keys missing - skipping API jobs")
        return []
    jobs = []
    for q in queries:
        try:
            r = requests.get(
                "https://api.adzuna.com/v1/api/jobs/in/search/1",
                params={"app_id": ADZUNA_ID, "app_key": ADZUNA_KEY, "results_per_page": 15,
                        "what": q["what"], "where": q.get("where", ""), "max_days_old": 2,
                        "sort_by": "date", "content-type": "application/json"},
                headers=HEADERS, timeout=20)
            r.raise_for_status()
            for j in r.json().get("results", []):
                jobs.append({
                    "title": clean(j.get("title")),
                    "company": clean((j.get("company") or {}).get("display_name")),
                    "location": clean((j.get("location") or {}).get("display_name")),
                    "link": j.get("redirect_url", ""),
                    "text": clean(j.get("description"), 400),
                    "hint": q.get("hint", ""),
                })
        except Exception as e:
            print("Adzuna error:", q["what"], e)
    return jobs


def fetch_rss(feeds):
    jobs = []
    for f in feeds:
        url = f.get("url", "")
        if not f.get("enabled", True) or not url.startswith("http"):
            continue
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            r.raise_for_status()
            parsed = feedparser.parse(r.content)
            for e in parsed.entries[:15]:
                jobs.append({
                    "title": clean(e.get("title")),
                    "company": f.get("name", ""),
                    "location": "",
                    "link": e.get("link", ""),
                    "text": clean(e.get("summary"), 400),
                    "hint": f.get("hint", ""),
                })
        except Exception as e:
            print("RSS error:", f.get("name"), e)
    return jobs


def classify(job):
    blob = f'{job["title"]} {job["text"]} {job["company"]}'.lower() + " "
    tags = set()
    if job.get("hint"):
        tags.add(job["hint"])
    for tag, words in KEYWORDS.items():
        if any(w in blob for w in words):
            tags.add(tag)
    if EXP_RE.search(blob) and "fresher" not in tags and "internship" not in tags:
        tags.add("experienced")
    if not tags & {"govt", "walkin", "internship", "fresher", "experienced"}:
        tags.add("experienced")
    is_it = any(w in blob for w in IT_WORDS)
    tags.add("it" if is_it else "nonit")
    primary = next(t for t in PRIORITY if t in tags)
    return primary, tags


def format_post(job, primary, tags, affiliate_links=None):
    esc = lambda s: html.escape(s or "")
    lines = [f'{EMOJI[primary]} <b>{esc(job["title"])}</b>']
    if job["company"]:
        lines.append(f'🏢 {esc(job["company"])}')
    if job["location"]:
        lines.append(f'📍 {esc(job["location"])}')
    lines.append(f'🔗 <a href="{html.escape(job["link"], quote=True)}">Apply / Details</a>')

    if affiliate_links:
        if "it" in tags and affiliate_links.get("udemy"):
            lines.append(f'💡 <b>Prep Tip:</b> <a href="{html.escape(affiliate_links["udemy"], quote=True)}">Top Placement &amp; Tech Prep Courses</a>')
        elif affiliate_links.get("amazon_aptitude"):
            lines.append(f'💡 <b>Prep Tip:</b> <a href="{html.escape(affiliate_links["amazon_aptitude"], quote=True)}">Best Aptitude &amp; Reasoning Prep Book</a>')

    names = {"govt": "#Govt", "walkin": "#WalkIn", "internship": "#Internship",
             "fresher": "#Fresher", "experienced": "#Experienced", "it": "#IT", "nonit": "#NonIT"}
    lines.append(" ".join(names[t] for t in names if t in tags))
    lines.append("⚠️ Never pay money for a job. Verify before applying.")
    return "\n".join(lines)


def format_deal(deal):
    esc = lambda s: html.escape(s or "")
    lines = [
        f'📚 <b>{esc(deal["title"])}</b>',
        f'💡 {esc(deal.get("text", ""))}',
        f'🔗 <a href="{html.escape(deal["link"], quote=True)}">Check Details &amp; Access Here</a>',
        deal.get("tag", "#PlacementPrep #Fresher"),
        "⚠️ Verified learning & career preparation resource.",
    ]
    return "\n".join(lines)


def send(text):
    if DRY_RUN:
        print("-----\n" + text)
        return True
    for _ in range(3):
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
                          json={"chat_id": CHANNEL, "text": text, "parse_mode": "HTML"}, timeout=20)
        if r.status_code == 429:
            time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
            continue
        if r.ok:
            return True
        print("Telegram error:", r.status_code, r.text[:200])
        return False
    return False


def main():
    if not BOT_TOKEN and not DRY_RUN:
        raise SystemExit("BOT_TOKEN missing")
    src = load_json(SOURCES_FILE, {})
    seen = load_json(SEEN_FILE, [])
    seen_set = set(seen)
    affiliate_links = src.get("affiliate_links", {})
    deals = src.get("placement_deals", [])

    jobs = fetch_adzuna(src.get("adzuna_queries", [])) + fetch_rss(src.get("rss", []))
    fresh, batch_keys = [], set()
    for j in jobs:
        if not j["title"] or not j["link"]:
            continue
        k = key_for(j["link"])
        if k in seen_set or k in batch_keys:
            continue
        batch_keys.add(k)
        primary, tags = classify(j)
        fresh.append((k, primary, tags, j))
    print(f"Fetched {len(jobs)}, new {len(fresh)}")

    # round-robin across categories so the channel stays varied
    buckets = {p: [x for x in fresh if x[1] == p] for p in PRIORITY}
    order = []
    while any(buckets.values()):
        for p in PRIORITY:
            if buckets[p]:
                order.append(buckets[p].pop(0))

    posted = 0
    for k, primary, tags, j in order[:MAX_POSTS]:
        if send(format_post(j, primary, tags, affiliate_links)):
            seen.append(k)
            posted += 1
            SEEN_FILE.write_text(json.dumps(seen[-5000:]), encoding="utf-8")
            time.sleep(3)  # stay under Telegram rate limits

    # Optionally post 1 placement prep deal if configured
    if deals and posted > 0:
        # Rotate deal based on hour/day
        deal_idx = int(time.time() / 14400) % len(deals)
        deal = deals[deal_idx]
        deal_key = key_for(deal["link"] + "_" + str(int(time.time() / 86400)))
        if deal_key not in seen_set:
            time.sleep(3)
            if send(format_deal(deal)):
                seen.append(deal_key)
                posted += 1
                SEEN_FILE.write_text(json.dumps(seen[-5000:]), encoding="utf-8")

    print("Posted", posted)


if __name__ == "__main__":
    main()
