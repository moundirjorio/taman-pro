"""Avito.ma — Next.js site: every page embeds its data as JSON in <script id="__NEXT_DATA__">."""
import json
import re

from .common import Site, unique

LIST_URL = "https://www.avito.ma/fr/maroc/voitures_d_occasion-%C3%A0_vendre"
NEXT_DATA = re.compile(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.S)


def _next_data(html: str) -> dict:
    match = NEXT_DATA.search(html)
    return json.loads(match.group(1)) if match else {}


def _props(html: str) -> dict:
    return _next_data(html).get("props", {}).get("pageProps", {}).get("componentProps", {}) or {}


def list_url(page: int) -> str:
    return LIST_URL if page == 1 else f"{LIST_URL}?o={page}"


def parse_list(html: str, page_url: str):
    ads = (_props(html).get("ads") or {}).get("ads") or []
    entries = []
    for ad in ads:
        if not ad.get("href") or "voitures_d_occasion" not in ad["href"]:
            continue  # sponsored blocks / other categories mixed into the results
        entries.append((str(ad.get("listId") or ad.get("id")), ad["href"], {}))
    return unique(entries)


def parse_ad(html: str, url: str, partial: dict):
    ad = (_props(html).get("adInfo") or {}).get("ad")
    if not ad:
        return None
    params = ad.get("params") or {}
    values = {p.get("key"): p.get("value") for group in ("primary", "secondary") for p in params.get(group) or []}
    equipment = [p.get("label") for p in params.get("extra") or [] if str(p.get("value")) in ("1", "true", "True")]
    location = ad.get("location") or {}
    images = ad.get("images") or []
    seller_type = (ad.get("seller") or {}).get("type") or ""
    return {
        "title": ad.get("subject"),
        "brand": values.get("brand"),
        "model": values.get("model"),
        "year": values.get("regdate"),
        "mileage_km": values.get("mileage_exact") or values.get("mileage"),
        "fuel": values.get("fuel"),
        "gearbox": values.get("bv"),
        "fiscal_power_cv": values.get("pfiscale"),
        "condition": values.get("auto_condition"),
        "doors": values.get("doors"),
        "origin": values.get("v_origin"),
        "first_owner": values.get("first_owner"),
        "city": ((location.get("city") or {}).get("name")),
        "sector": ((location.get("area") or {}).get("name")),
        "seller_type": "Professionnel" if seller_type in ("shop", "store", "pro") else "Particulier" if seller_type else "",
        "price_mad": (ad.get("price") or {}).get("value"),
        "equipment": "; ".join(equipment),
        "published_at": ad.get("listTime"),
        "image_url": ((images[0].get("paths") or {}).get("standard")) if images else "",
        "description": ad.get("description"),
    }


SITE = Site("avito", "https://www.avito.ma", [(list_url, {})], parse_list, parse_ad)
