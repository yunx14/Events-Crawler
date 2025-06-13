
# uss-alabama-events.py
"""
Scrape all current event pages on bellingrath.org with Crawl4AI.
Requires:  pip install crawl4ai beautifulsoup4 lxml
Run with:  python -m asyncio bellingrath_events_scraper.py
"""

import asyncio, json, re
from bs4 import BeautifulSoup
from crawl4ai import (
    AsyncWebCrawler,
    BrowserConfig,
    CacheMode,
    CrawlerRunConfig,
)
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter

START_URL = "https://www.ussalabama.com/events/"

# 1) Tell Crawl4AI to start headless Chromium
browser_conf = BrowserConfig(headless=True, java_script_enabled=True)

# 2) Strategy: breadth-first 1 level deep, stay on domain,
#    only follow links that look like real event pages.
deep_strategy = BFSDeepCrawlStrategy(
    max_depth=1,                     # listing page (depth 0) ➜ event pages (depth 1)
    include_external=False,
    filter_chain=FilterChain(
        [URLPatternFilter(patterns=["*/event/*"])]  # “click into each event”
    ),
)

run_conf = CrawlerRunConfig(
    cache_mode=CacheMode.BYPASS,      # always get fresh pages
    deep_crawl_strategy=deep_strategy,
    stream=False,                     # collect everything, then return
)

# -----------------------------------------------------------
# Helper to pull data out of a single event page with Soup
# -----------------------------------------------------------
def parse_event(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "lxml")

    neat_text = lambda sel: soup.select_one(sel).get_text(" ", strip=True) if soup.select_one(sel) else None

    title         = neat_text("h1")
    datetime_blk  = neat_text("h2") or neat_text("header h2")  # covers most Tribe-Events themes
    date  = soup.select_one(".tribe-events-start-date")
    time = soup.select_one(".tribe-events-start-time")
    location = soup.select_one(".tribe-venue")
    # Grab paragraphs until we hit the “Details” or “Related” headings
    # description_parts = []
    # for p in soup.select(".tribe-events-single-event-description p"):
    #     if re.search(r"\bDetails\b|\bRelated\b", p.get_text(), flags=re.I):
    #         break
    #     description_parts.append(p.get_text(" ", strip=True))
    # description   = " ".join(description_parts).strip() or None
    desc_div = soup.select_one(".tribe-events-single-event-description")

    # Tribe’s Details section is usually in <div class="tribe-events-meta-group">
    # Fallback to simple text searches if the theme is customised.
    categories = [a.get_text(strip=True) for a in soup.select("a[rel='tag']")] or None
    phone      = re.search(r"\b\d{3}[.\-\s]?\d{3}[.\-\s]?\d{4}\b", soup.get_text())  # quick & dirty
    email      = re.search(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", soup.get_text())

    organiser_tag = soup.find(lambda t: t.name in ("strong", "h3", "h4") and re.search("organizer", t.get_text(), re.I))
    organiser     = organiser_tag.get_text(" ", strip=True) if organiser_tag else None

    tickets_link = None
    ticket_candidate = soup.select_one("a[href*='agileticketing'], a[href*='tickets'], a[href*='prod5.agileticketing']")
    if ticket_candidate:
        tickets_link = ticket_candidate["href"]

    image_url = None
    # Try to find a main event image (adjust selector as needed for your site)
    img_tag = soup.select_one("div.tribe-events-event-image img")
    if img_tag and img_tag.get("src"):
        image_url = img_tag["src"]

    return {
        "title": title,
        "date_time": datetime_blk,
        "date": date.get_text(strip=True) if date else None,
        "time": time.get_text(strip=True) if time else None,
        "location": location.get_text(strip=True) if location else None,
        "description": desc_div.get_text(separator="\n", strip=True) if desc_div else None,
        "categories": categories,
        "organiser": organiser,
        "phone": phone.group(0) if phone else None,
        "email": email.group(0) if email else None,
        "tickets_url": tickets_link,
        "image_url": image_url,
        "page_url": url,
    }

# -----------------------------------------------------------
# Main async runner
# -----------------------------------------------------------
async def main():
    async with AsyncWebCrawler(config=browser_conf) as crawler:
        # Deep-crawl: listing page + every /event/ page
        results = await crawler.arun(START_URL, config=run_conf)

        # If stream=False the deep crawl returns a list of CrawlResult objects
        events = []
        for res in results:
            if "/event/" in res.url and res.success:
                events.append(parse_event(res.html, res.url))

        print(json.dumps(events, indent=2))
        with open("events.json", "w") as f:
            json.dump(events, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
