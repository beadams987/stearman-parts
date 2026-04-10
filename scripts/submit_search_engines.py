#!/usr/bin/env python3
"""Submit sitemap to search engines.

Pings Google and Bing with the sitemap URL and prints instructions
for manual verification via Search Console / Webmaster Tools.

Usage:
    python submit_search_engines.py
"""

from __future__ import annotations

import urllib.request
import urllib.error

SITEMAP_URL = "https://stearmanhq.com/sitemap.xml"


def ping_search_engine(name: str, ping_url: str) -> None:
    """Send a GET request to notify a search engine of the sitemap."""
    try:
        req = urllib.request.Request(ping_url, headers={"User-Agent": "StearmanParts/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            print(f"  {name}: {resp.status} {resp.reason}")
    except urllib.error.URLError as e:
        print(f"  {name}: Failed — {e}")


def main() -> None:
    print(f"Submitting sitemap: {SITEMAP_URL}\n")

    ping_search_engine(
        "Google",
        f"https://www.google.com/ping?sitemap={SITEMAP_URL}",
    )
    ping_search_engine(
        "Bing",
        f"https://www.bing.com/ping?sitemap={SITEMAP_URL}",
    )

    print("\n" + "=" * 60)
    print("Manual verification steps:")
    print("=" * 60)
    print()
    print("Google Search Console:")
    print("  1. Go to https://search.google.com/search-console")
    print("  2. Add property: https://stearmanhq.com")
    print("  3. Verify ownership (DNS TXT record or HTML file)")
    print("  4. Submit sitemap: Sitemaps → Add → sitemap.xml")
    print()
    print("Bing Webmaster Tools:")
    print("  1. Go to https://www.bing.com/webmasters")
    print("  2. Add site: https://stearmanhq.com")
    print("  3. Verify ownership")
    print("  4. Submit sitemap: Sitemaps → Submit sitemap")
    print()


if __name__ == "__main__":
    main()
