
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

START_URL = "https://www.cityofmobile.org/events/"

# 1) Tell Crawl4AI to start headless Chromium
browser_conf = BrowserConfig(headless=True, java_script_enabled=True)

# 2) Strategy: breadth-first 1 level deep, stay on domain,
#    only follow links that look like real event pages.
deep_strategy = BFSDeepCrawlStrategy(
    max_depth=1,                     # listing page (depth 0) ➜ event pages (depth 1)
    include_external=False,
    filter_chain=FilterChain(
        [URLPatternFilter(patterns=["*/events/*"])]  # “click into each event”
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
    start_dt  = soup.select_one("[itemprop='startDate']")
    location = soup.select_one("[itemprop='address']")
    desc_tag = soup.select_one("span[itemprop='description']")      # or soup.find(attrs={"itemprop": "description"})
    if desc_tag:
        description = desc_tag.get_text(" ", strip=True)
    else:
        description = None
    image_url = None
    # Try to find a main event image (adjust selector as needed for your site)
    img_tag = soup.select_one(".col-lg-9 img")
    if img_tag and img_tag.get("src"):
        src_string = img_tag["src"]
        image_url = src_string.split("file=")[1]

    return {
        "title": title,
        "date_time": start_dt.get_text(strip=True) if start_dt else None,
        "location": location.get_text(" ", strip=True) if location else None,
        "venue_name": location.get_text(" ", strip=True) if location else None,
        "description": description,
        "image_url": image_url,
        "page_url": url,
        "source_name": "City of Mobile"
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
            if "/events/" in res.url and res.success:
                events.append(parse_event(res.html, res.url))

        print(json.dumps(events, indent=2))
        with open("events.json", "w") as f:
            json.dump(events, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
