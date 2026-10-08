"""Moteur.ma — server-rendered HTML; the specs are label/value cells of a table."""
import re

from bs4 import BeautifulSoup

from .common import Site, clean, unique

BASE = "https://www.moteur.ma"
LIST_URL = f"{BASE}/fr/voiture/achat-voiture-occasion"
AD_LINK = re.compile(r"/fr/voiture/achat-voiture-occasion/detail-annonce/(\d+)/[^\"'?#]+\.html")


def list_url(page: int) -> str:
    return f"{LIST_URL}/" if page == 1 else f"{LIST_URL}?page={page}"


# Moteur.ma republishes Avito ads (their photos come from content.avito.ma). Those are already
# collected from Avito itself, so they are skipped here unless INCLUDE_AVITO_REPOSTS is set.
INCLUDE_AVITO_REPOSTS = False


def parse_list(html: str, page_url: str):
    soup = BeautifulSoup(html, "html.parser")
    entries = []
    for card in soup.select(".ad-col"):
        link = card.find("a", href=AD_LINK)
        if not link:
            continue
        image = card.find("img")
        repost = image is not None and "avito.ma" in (image.get("src") or image.get("data-src") or "")
        match = AD_LINK.search(link["href"])
        entries.append((match.group(1), BASE + match.group(0), {"_skip": repost and not INCLUDE_AVITO_REPOSTS}))
    if not soup.select(".ad-col"):  # layout changed: fall back to every ad link on the page
        entries = [(m.group(1), BASE + m.group(0), {}) for m in AD_LINK.finditer(html)]
    return unique(entries)


def _cell_pairs(table) -> dict[str, str]:
    """{label: value} from rows laid out as <td>label</td><td>value</td>…; ✓/✗ icons become Oui/Non."""
    pairs = {}
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        for label_cell, value_cell in zip(cells[0::2], cells[1::2]):
            label = clean(label_cell.get_text(" ")).rstrip(" :")
            if value_cell.find("i", class_="fa-check"):
                value = "Oui"
            elif value_cell.find("i", class_="fa-times"):
                value = "Non"
            else:
                value = clean(value_cell.get_text(" "))
            if label:
                pairs[label] = value
    return pairs


def parse_ad(html: str, url: str, partial: dict):
    soup = BeautifulSoup(html, "html.parser")
    title = soup.select_one(".ad-hero-title")
    if not title:
        return None
    specs = {}
    for table in soup.select("table"):
        specs.update(_cell_pairs(table))

    meta = {}
    for item in soup.select(".ad-detail-meta__item"):
        icon = item.find("i")
        if icon:
            meta[" ".join(icon.get("class", []))] = clean(item.get_text(" "))

    description = ""
    heading = soup.find(lambda t: t.name in ("h3", "h4") and "Spécifications rapides" in t.get_text())
    if heading and heading.find_next_sibling("div"):
        description = heading.find_next_sibling("div").get_text("\n", strip=True)

    options = []
    heading = soup.find(lambda t: t.name in ("h3", "h4") and t.get_text(strip=True).lower() == "options")
    if heading:
        for icon in heading.find_next("div").select("i.fa-check"):
            label = clean(icon.parent.get_text(" "))
            if label and label != "État du véhicule":
                options.append(label)

    image = soup.select_one("#full-gallery img")
    price = soup.select_one(".ad-hero-price-col")
    origin = "Importée neuve" if specs.get("Importation neuve") == "Oui" else ""
    customs = specs.get("Statut de douane", "")
    return {
        "title": title.get_text(" "),
        "brand": specs.get("Marque"),
        "model": specs.get("Modèle"),
        "year": specs.get("Année"),
        "mileage_km": specs.get("Kilométrage"),
        "fuel": specs.get("Motorisation"),
        "gearbox": specs.get("Transmission"),
        "fiscal_power_cv": specs.get("Puissance fiscale"),
        "body_type": specs.get("Carrosserie"),
        "color": specs.get("Couleur"),
        "doors": specs.get("Nombre de portes"),
        "origin": origin or (customs if customs != "Non" else ""),
        "first_owner": specs.get("Premier propriétaire"),
        "city": meta.get("fa fa-map-marker"),
        "price_mad": price.get_text(" ") if price else "",
        "equipment": "; ".join(dict.fromkeys(options)),
        "published_at": meta.get("fa fa-calendar"),
        "image_url": image.get("src") or image.get("data-src") if image else "",
        "description": description,
    }


SITE = Site("moteur", BASE, [(list_url, {})], parse_list, parse_ad)
