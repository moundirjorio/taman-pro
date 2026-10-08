#!/usr/bin/env python3
"""Collect public used-car ads from Moroccan marketplaces into one structured CSV.

Sites: Avito.ma, Moteur.ma, Wandaloo.com, Kifal Auto. Each site has its own parser (scrapers/), so
every row has the same columns: brand, model, year, mileage, fuel, gearbox, fiscal power, horsepower,
body type, color, condition, city, price… (see scrapers/common.py:FIELDS).

Polite by design: robots.txt is honoured (including Crawl-delay), requests to a given site are
sequential and spaced out, nothing is logged into, and a site that refuses access is left alone.
Seller names and phone numbers are never stored.

Examples:
  python scrape_marketplaces.py                         # every site, every page (hours: run it overnight)
  python scrape_marketplaces.py --max-pages 3           # quick sample
  python scrape_marketplaces.py --sites moteur kifal    # only some sites
Re-running continues where it stopped: ads already in the CSV are skipped.
"""
from __future__ import annotations

import argparse
import logging
import sys
import threading
from pathlib import Path

from scrapers import SITES, moteur
from scrapers.common import CsvSink, crawl

HERE = Path(__file__).resolve().parent


def main() -> int:
    parser = argparse.ArgumentParser(description="Structured scraper for Moroccan car-ad sites")
    parser.add_argument("--sites", nargs="+", choices=sorted(SITES), default=sorted(SITES), help="sites to crawl (default: all)")
    parser.add_argument("--output", type=Path, default=HERE / "marketplace_listings.csv", help="CSV file (appended to, so runs can resume)")
    parser.add_argument("--max-pages", type=int, default=0, help="listing pages per site and feed (0 = all)")
    parser.add_argument("--max-ads", type=int, default=0, help="new ads per site (0 = no limit)")
    parser.add_argument("--delay", type=float, default=2.0, help="seconds between two requests to the same site (min 1)")
    parser.add_argument("--fresh", action="store_true", help="start a new CSV instead of resuming")
    parser.add_argument("--include-reposts", action="store_true",
                        help="also collect Moteur.ma ads that are reposts of Avito ads (skipped by default)")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()
    if args.delay < 1:
        parser.error("--delay must be at least 1 second")

    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    for noisy in ("urllib3", "charset_normalizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")

    moteur.INCLUDE_AVITO_REPOSTS = args.include_reposts
    sink = CsvSink(args.output, fresh=args.fresh)
    stop = threading.Event()
    # Sites are independent hosts, so they are crawled in parallel (each one stays sequential)
    threads = [threading.Thread(target=crawl, name=name, daemon=True,
                                args=(SITES[name], sink, args.delay, args.max_pages, args.max_ads, stop))
               for name in args.sites]
    for t in threads:
        t.start()
    try:
        while any(t.is_alive() for t in threads):
            for t in threads:
                t.join(timeout=0.5)
    except KeyboardInterrupt:
        logging.info("Stopping after the current requests… (Ctrl+C again to force)")
        stop.set()
        for t in threads:
            t.join(timeout=60)
    finally:
        sink.close()

    total = sum(sink.counts.values())
    summary = ", ".join(f"{k}: {v}" for k, v in sorted(sink.counts.items())) or "none"
    logging.info("Added %d ads (%s). %s now holds %d ads.", total, summary, args.output.name, len(sink.seen))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
