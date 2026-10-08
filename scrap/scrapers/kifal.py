"""Kifal Auto (occasion.kifal.ma) — server-rendered HTML with schema.org microdata and label/value rows."""
import re
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .common import Site, clean, unique

BASE = "https://occasion.kifal.ma"
AD_LINK = re.compile(r"https://occasion\.kifal\.ma/annonce/[^\"'\s]+?_(VEH[0-9A-Z]+)\.htm")
HORSEPOWER = re.compile(r"(\d{2,4})\s*(?:ch|cv din|hp)\b", re.I)


def list_url(page: int) -> str:
    return f"{BASE}/annonces" if page == 1 else f"{BASE}/annonces?page={page}"


def parse_list(html: str, page_url: str):
    return unique((m.group(1), m.group(0), {}) for m in AD_LINK.finditer(html))


def parse_ad(html: str, url: str, partial: dict):
    soup = BeautifulSoup(html, "html.parser")
    micro = {el["itemprop"]: clean(el.get("content") or el.get_text(" ")) for el in soup.select("[itemprop]")}
    if not micro.get("name"):
        return None

    rows = {}
    for row in soup.select("div.d-flex.justify-content-between.border-bottom"):
        spans = row.find_all("span", recursive=False)
        if len(spans) >= 2:
            rows[clean(spans[0].get_text(" ")).rstrip(" :")] = clean(spans[1].get_text(" "))

    # Icon strip under the photos: fuel / gearbox / city, each a column with an icon and a <p>
    strip = {}
    pane = soup.select_one("#tab-1")
    for col in pane.select("div.text-center") if pane else []:
        icon, text = col.find("i"), col.find("p")
        if icon and text:
            strip[" ".join(icon.get("class", []))] = clean(text.get_text(" "))
    gearbox = next((v for k, v in strip.items() if "cog" in k or "gear" in k), "")
    city = next((v for k, v in strip.items() if "map" in k or "location" in k), "")
    if not city:  # fallback: the city is part of the ad URL (…_CASABLANCA_7781_VEH….htm)
        parts = unquote(url).rsplit("/", 1)[-1].split("_")
        city = parts[-3] if len(parts) >= 4 else ""

    description = ""
    heading = soup.find(lambda t: t.name == "div" and clean(t.get_text(" ")) == "Description de l'annonce")
    if heading and heading.find_next("div", class_="justify-content"):
        description = heading.find_next("div", class_="justify-content").get_text("\n", strip=True)

    version = rows.get("la finition", "")
    hp = HORSEPOWER.search(version)
    image = soup.find("meta", property="og:image")
    return {
        "title": micro.get("name"),
        "brand": micro.get("brand"),
        "model": micro.get("model"),
        "version": version,
        "year": micro.get("productionYear") or rows.get("Année"),
        "mileage_km": micro.get("mileageFromOdometer") or rows.get("Kilométrage"),
        "fuel": micro.get("fuelType"),
        "gearbox": gearbox,
        "fiscal_power_cv": rows.get("Puissance fiscale"),
        "horsepower_ch": hp.group(1) if hp else "",
        "body_type": micro.get("vehicleBodyType") or rows.get("Type de voiture"),
        "origin": rows.get("Origine"),
        "first_owner": rows.get("Première main"),
        "city": city.title(),
        "seller_type": "Professionnel",  # Kifal sells on behalf of owners, as an intermediary
        "price_mad": micro.get("price"),
        "image_url": image.get("content") if image else "",
        "description": description,
    }


SITE = Site("kifal", BASE, [(list_url, {})], parse_list, parse_ad)
