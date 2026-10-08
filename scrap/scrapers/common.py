"""Shared pieces: polite HTTP client, CSV schema, value normalisation, crawl loop."""
from __future__ import annotations

import csv
import logging
import re
import threading
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests

log = logging.getLogger("scraper")

USER_AGENT = "TamanProResearchBot/2.0 (student project; public car ads only)"

# One row per ad. Seller names and phone numbers are deliberately never collected.
FIELDS = [
    "source", "ad_id", "url", "title", "brand", "model", "version", "year", "mileage_km",
    "fuel", "gearbox", "fiscal_power_cv", "horsepower_ch", "body_type", "color", "condition",
    "doors", "origin", "first_owner", "city", "sector", "seller_type", "price_mad",
    "equipment", "published_at", "image_url", "description", "duplicate_of", "scraped_at",
]


class Blocked(Exception):
    """The site refused us (403/401 or persistent 429): stop this source, never try to get around it."""


# --------------------------------------------------------------------------- HTTP

class Fetcher:
    """One per site: honours robots.txt (incl. Crawl-delay), waits between requests, retries transient errors."""

    def __init__(self, base_url: str, delay: float, timeout: float = 20.0, retries: int = 3):
        self.base_url = base_url.rstrip("/")
        self.host = urlparse(base_url).hostname or ""
        self.timeout = timeout
        self.retries = retries
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "fr-MA,fr;q=0.9",
        })
        self.robots = self._load_robots()
        self.delay = max(delay, self.robots.crawl_delay(USER_AGENT) or 0) if self.robots else delay
        self._last = 0.0

    def _load_robots(self) -> RobotFileParser | None:
        url = f"{self.base_url}/robots.txt"
        try:
            r = self.session.get(url, timeout=self.timeout)
        except requests.RequestException as exc:
            log.warning("[%s] robots.txt unreachable (%s): assuming allowed", self.host, exc)
            return None
        if r.status_code in (401, 403):
            raise Blocked(f"robots.txt returned {r.status_code}")
        parser = RobotFileParser(url)
        # A missing robots.txt (404, or an HTML error page) means no restriction
        is_robots = r.ok and "html" not in r.headers.get("Content-Type", "")
        parser.parse(r.text.splitlines() if is_robots else [])
        return parser

    def allowed(self, url: str) -> bool:
        return self.robots is None or self.robots.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> str | None:
        if not self.allowed(url):
            log.info("[%s] robots.txt disallows %s", self.host, url)
            return None
        r = None
        for attempt in range(1, self.retries + 1):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.session.get(url, timeout=self.timeout)
            except requests.RequestException as exc:
                log.warning("[%s] %s (attempt %d): %s", self.host, url, attempt, exc)
                time.sleep(self.delay * attempt)
                continue
            if r.status_code == 200:
                r.encoding = r.encoding if r.encoding and r.encoding.lower() != "iso-8859-1" else "utf-8"
                return r.text
            if r.status_code in (401, 403):
                raise Blocked(f"HTTP {r.status_code} on {url}")
            if r.status_code == 404 or r.status_code == 410:
                return None
            if r.status_code == 429 or r.status_code >= 500:
                backoff = int(r.headers.get("Retry-After", "0") or 0) or 30 * attempt
                log.warning("[%s] HTTP %d, waiting %ds", self.host, r.status_code, backoff)
                time.sleep(backoff)
                continue
            log.warning("[%s] HTTP %d on %s", self.host, r.status_code, url)
            return None
        if r is not None and r.status_code == 429:
            raise Blocked("rate limited (HTTP 429) repeatedly")
        return None


# --------------------------------------------------------------------------- normalisation

def clean(value) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return "" if text.lower() in {"n/a", "na", "-", "--", "null", "none", "non renseigné", "nc"} else text


def to_int(value) -> int | str:
    """'161,000 km' / '89 517' / '90.000 DH' / '6 CV' / 'Plus de 41 CV' -> int; '' if no digits."""
    if isinstance(value, (int, float)):
        return int(value)
    digits = re.sub(r"\D", "", clean(value))
    return int(digits) if digits else ""


def strip_accents(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()


def norm_fuel(value) -> str:
    v = strip_accents(clean(value))
    if not v:
        return ""
    if "hybrid" in v:
        return "Hybride rechargeable" if "rechargeable" in v or "plug" in v or "phev" in v else "Hybride"
    for key, label in (("diesel", "Diesel"), ("essence", "Essence"), ("petrol", "Essence"),
                       ("electri", "Électrique"), ("gpl", "GPL"), ("lpg", "GPL")):
        if key in v:
            return label
    return clean(value).capitalize()


def norm_gearbox(value) -> str:
    v = strip_accents(clean(value))
    if v.startswith("auto") or "bva" in v or "robot" in v:
        return "Automatique"
    if v.startswith("manu") or "bvm" in v:
        return "Manuelle"
    return clean(value).capitalize()


def norm_yes_no(value) -> str:
    v = strip_accents(clean(value))
    if v in {"oui", "yes", "1", "true", "premiere"} or v.startswith("1"):
        return "Oui"
    if v in {"non", "no", "0", "false"}:
        return "Non"
    return ""


def norm_origin(value) -> str:
    v = strip_accents(clean(value))
    if not v:
        return ""
    if "pas encore" in v or "non dedouan" in v or "not yet" in v:
        return "Non dédouanée"
    if v in {"ded", "dedouanee", "dedouane"} or "dedouan" in v or "customs-cleared" in v:
        return "Dédouanée"
    if v.startswith("ww") or "ww au maroc" in v or "in morocco" in v:
        return "WW au Maroc"
    if "import" in v:
        return "Importée neuve"
    return clean(value)


def norm_seller(value) -> str:
    v = strip_accents(clean(value))
    if not v:
        return ""
    if any(k in v for k in ("pro", "shop", "store", "concession", "garage", "agence")):
        return "Professionnel"
    if any(k in v for k in ("part", "private", "individual")):
        return "Particulier"
    return clean(value)


ACRONYMS = {"BMW", "MG", "DS", "BYD", "KGM", "GWM", "GAC", "JAC", "DFSK", "BAIC", "VW", "GMC", "AMG"}
BRAND_ALIASES = {"mercedes": "Mercedes-Benz", "mercedes benz": "Mercedes-Benz", "citroen": "Citroën", "skoda": "Škoda",
                 "volkswagen vw": "Volkswagen", "land rover": "Land Rover", "alfa romeo": "Alfa Romeo"}


def tidy_case(value: str, acronyms: set[str] = frozenset()) -> str:
    """'TARRACO' -> 'Tarraco', 'LAND ROVER' -> 'Land Rover'; keeps 'BMW', 'CR-V', 'X1', 'e-208'."""
    words = []
    for word in clean(value).split(" "):
        if word.upper() in acronyms:
            words.append(word.upper())
        elif word.isalpha() and word.isupper() and len(word) >= 4:
            words.append(word.capitalize())
        else:
            words.append(word)
    return " ".join(words)


def norm_brand(value) -> str:
    text = clean(value)
    alias = BRAND_ALIASES.get(strip_accents(text).replace("-", " "))
    if alias:
        return alias
    if text.isupper() and text.upper() not in ACRONYMS:
        return " ".join(w if w in ACRONYMS else w.capitalize() for w in text.split(" "))
    return tidy_case(text, ACRONYMS)


def year_or_blank(value) -> int | str:
    y = to_int(value)
    return y if isinstance(y, int) and 1950 <= y <= datetime.now().year + 1 else ""


def text_lines(node) -> list[str]:
    """Visible text of a BeautifulSoup node as a list of non-empty lines."""
    return [line for line in (clean(s) for s in node.stripped_strings) if line]


def value_after(lines: list[str], *labels: str) -> str:
    """Value of the first line that follows one of `labels` (case, accents and trailing ':' ignored)."""
    wanted = {strip_accents(l).rstrip(" :") for l in labels}
    for i, line in enumerate(lines[:-1]):
        if strip_accents(line).rstrip(" :") in wanted:
            return lines[i + 1]
    return ""


FRENCH_MONTHS = {m: i for i, m in enumerate(
    ["janvier", "fevrier", "mars", "avril", "mai", "juin", "juillet", "aout", "septembre", "octobre", "novembre", "decembre"], 1)}


def norm_date(value) -> str:
    """'2026-10-08T10:58:35Z' / 'Oct 08, 2026' / '6 octobre 2026' / '08/10/2026' -> '2026-10-08'."""
    text = clean(value)
    if not text:
        return ""
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text[:10]
    for fmt in ("%b %d, %Y", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.match(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", strip_accents(text))
    if m and m.group(2) in FRENCH_MONTHS:
        return f"{m.group(3)}-{FRENCH_MONTHS[m.group(2)]:02d}-{int(m.group(1)):02d}"
    return text  # relative dates ("il y a 2 heures") are kept as written


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def finalize(record: dict) -> dict:
    """Fill every column, normalise the shared ones and drop obviously invalid values."""
    row = {f: record.get(f, "") for f in FIELDS}
    for f in FIELDS:
        if isinstance(row[f], str):
            row[f] = clean(row[f])
    row["brand"] = norm_brand(row["brand"])
    row["model"] = tidy_case(row["model"])
    row["fuel"] = norm_fuel(row["fuel"])
    row["gearbox"] = norm_gearbox(row["gearbox"])
    row["first_owner"] = norm_yes_no(row["first_owner"])
    row["origin"] = norm_origin(row["origin"])
    row["seller_type"] = norm_seller(row["seller_type"])
    row["year"] = year_or_blank(row["year"])
    row["published_at"] = norm_date(row["published_at"])
    for f in ("mileage_km", "price_mad", "fiscal_power_cv", "horsepower_ch", "doors"):
        row[f] = to_int(row[f])
    if isinstance(row["price_mad"], int) and row["price_mad"] < 1000:
        row["price_mad"] = ""  # "Appeler pour le prix", placeholder 1 DH, etc.
    if isinstance(row["fiscal_power_cv"], int) and not 1 <= row["fiscal_power_cv"] <= 99:
        row["fiscal_power_cv"] = ""
    if isinstance(row["horsepower_ch"], int) and not 20 <= row["horsepower_ch"] <= 2000:
        row["horsepower_ch"] = ""
    row["scraped_at"] = row["scraped_at"] or now_iso()
    return row


# --------------------------------------------------------------------------- output

class CsvSink:
    """Thread-safe CSV appender; remembers which ads are already in the file so runs can resume."""

    def __init__(self, path, fresh: bool = False):
        self.path = path
        self.lock = threading.Lock()
        self.seen: set[tuple[str, str]] = set()
        self.fingerprints: dict[tuple, tuple[str, str]] = {}
        exists = path.exists() and path.stat().st_size > 0 and not fresh
        if exists:
            with path.open(encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                if reader.fieldnames != FIELDS:
                    backup = path.with_suffix(".old.csv")
                    log.warning("%s has an older column layout: moved to %s", path.name, backup.name)
                    f.close()
                    path.replace(backup)
                    exists = False
                else:
                    for r in reader:
                        self.seen.add((r["source"], r["ad_id"]))
                        fp = self.fingerprint(r)
                        if fp and not r.get("duplicate_of"):
                            self.fingerprints.setdefault(fp, (r["source"], r["ad_id"]))
        self.file = path.open("a" if exists else "w", encoding="utf-8-sig" if not exists else "utf-8", newline="")
        self.writer = csv.DictWriter(self.file, fieldnames=FIELDS)
        if not exists:
            self.writer.writeheader()
        self.counts: dict[str, int] = {}

    def has(self, source: str, ad_id: str) -> bool:
        with self.lock:
            return (source, str(ad_id)) in self.seen

    @staticmethod
    def fingerprint(row: dict) -> tuple | None:
        """Same car, same mileage, same price: the ad was cross-posted (Moteur.ma republishes Avito ads, dealers post everywhere)."""
        if not (row.get("brand") and row.get("year") and row.get("mileage_km") not in ("", None)):
            return None
        return (strip_accents(str(row["brand"])), re.sub(r"\W", "", strip_accents(str(row["model"]))),
                str(row["year"]), str(row["mileage_km"]), str(row.get("price_mad", "")))

    def write(self, row: dict) -> None:
        with self.lock:
            key = (row["source"], str(row["ad_id"]))
            if key in self.seen:
                return
            self.seen.add(key)
            fp = self.fingerprint(row)
            if fp:
                first = self.fingerprints.setdefault(fp, (row["source"], str(row["ad_id"])))
                if first[0] != row["source"]:
                    row["duplicate_of"] = f"{first[0]}:{first[1]}"
            self.writer.writerow(row)
            self.file.flush()
            self.counts[row["source"]] = self.counts.get(row["source"], 0) + 1

    def close(self) -> None:
        self.file.close()


# --------------------------------------------------------------------------- crawl loop

Feed = tuple[Callable[[int], str], dict]  # (page number -> listing URL, values shared by every ad of that listing)


@dataclass
class Site:
    name: str
    base_url: str
    feeds: list[Feed]
    # (html, page_url) -> [(ad_id, ad_url, partial_record)]; partial_record["_skip"] = listed but not collected
    parse_list: Callable[[str, str], list[tuple[str, str, dict]]]
    # (html, ad_url, partial_record) -> record dict, or None if the page is not a usable ad
    parse_ad: Callable[[str, str, dict], dict | None]
    min_delay: float = 1.0


def crawl(site: Site, sink: CsvSink, delay: float, max_pages: int, max_ads: int,
          stop: threading.Event) -> None:
    try:
        fetcher = Fetcher(site.base_url, max(delay, site.min_delay))
    except Blocked as exc:
        log.error("[%s] blocked before start: %s", site.name, exc)
        return
    log.info("[%s] start (%.1fs between requests)", site.name, fetcher.delay)
    stats = {"written": 0, "skipped": 0}

    def budget_left() -> bool:
        return not stop.is_set() and (max_ads <= 0 or stats["written"] < max_ads)

    try:
        for list_url, feed_values in site.feeds:
            page, empty_pages, seen_on_feed = 1, 0, set()
            while budget_left() and (max_pages <= 0 or page <= max_pages):
                url = list_url(page)
                html = fetcher.get(url)
                entries = site.parse_list(html, url) if html else []
                # Some sites keep serving the last page (or sponsored ads) past the end: stop when nothing is new
                fresh = [e for e in entries if e[0] not in seen_on_feed]
                seen_on_feed.update(e[0] for e in entries)
                if not fresh:
                    empty_pages += 1
                    if empty_pages >= 2:
                        break
                    page += 1
                    continue
                empty_pages = 0
                # "_skip": listed but deliberately not collected (e.g. Moteur.ma reposts of Avito ads)
                wanted = [e for e in fresh if not e[2].get("_skip")]
                new = [e for e in wanted if not sink.has(site.name, e[0])]
                stats["skipped"] += len(wanted) - len(new)
                for ad_id, ad_url, partial in new:
                    if not budget_left():
                        break
                    ad_html = fetcher.get(ad_url)
                    if not ad_html:
                        continue
                    try:
                        record = site.parse_ad(ad_html, ad_url, {**feed_values, **partial})
                    except Exception as exc:  # one malformed page must not stop the crawl
                        log.warning("[%s] could not parse %s: %s", site.name, ad_url, exc)
                        continue
                    if record:
                        record = {**feed_values, **partial, **{k: v for k, v in record.items() if v not in (None, "")}}
                        sink.write(finalize({"source": site.name, "ad_id": ad_id, "url": ad_url, **record}))
                        stats["written"] += 1
                log.info("[%s] %s -> %d ads, %d new, %d written in total", site.name, url, len(fresh), len(new), stats["written"])
                page += 1
    except Blocked as exc:
        log.error("[%s] stopped, the site refused access: %s", site.name, exc)
    log.info("[%s] done: %d new ads written, %d were already in the CSV", site.name, stats["written"], stats["skipped"])


def unique(entries: Iterable[tuple[str, str, dict]]) -> list[tuple[str, str, dict]]:
    seen, out = set(), []
    for e in entries:
        if e[0] and e[0] not in seen:
            seen.add(e[0])
            out.append(e)
    return out
