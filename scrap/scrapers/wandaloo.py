"""Wandaloo.com (used-car section) — server-rendered HTML with <p class="param">/<p class="value"> pairs.

The ad page has no body type, so the listing is walked segment by segment ("categorie" filter) and
each ad is tagged with the segment it was listed under.
"""
import re

from bs4 import BeautifulSoup

from .common import Site, clean, unique

BASE = "https://www.wandaloo.com"
AD_LINK = re.compile(r"https://www\.wandaloo\.com/occasion/[a-z0-9-]+/(\d+)\.html")
SEGMENTS = {
    11: "Micro-citadine", 1: "Citadine", 2: "Compacte", 3: "Familiale", 4: "Monospace", 5: "Routière",
    6: "Luxe", 7: "4x4 / SUV", 8: "Coupé", 9: "Cabriolet", 10: "Ludospace",
}


def _list_url(category: int):
    def build(page: int) -> str:
        return (f"{BASE}/occasion/?marque=0&modele=0&budget=0&categorie={category}&moteur=0&transmission=0"
                f"&vendeur=0&abonne=0&equipement=-&ville=0&mo=za&pg={page}")
    return build


def parse_list(html: str, page_url: str):
    return unique((m.group(1), m.group(0), {}) for m in AD_LINK.finditer(html))


def _pairs(soup) -> dict[str, str]:
    pairs = {}
    for label in soup.select("p.param, p.titre"):
        value = label.find_next_sibling("p")
        if not value or label.find("a"):
            continue
        icon = value.find("img")
        if icon and "oui-" in icon.get("src", ""):
            text = "Oui"
        elif icon and "non-" in icon.get("src", ""):
            text = "Non"
        else:
            text = clean(value.get_text(" "))
        pairs.setdefault(clean(label.get_text(" ")), text)
    return pairs


def parse_ad(html: str, url: str, partial: dict):
    soup = BeautifulSoup(html, "html.parser")
    details = soup.select_one("#details")
    if not details:
        return None
    for hidden in details.select(".hidden"):
        hidden.decompose()
    specs = _pairs(soup)

    brand = model = ""
    for link in soup.select("ol li a[href*='marque=']"):
        modele = re.search(r"modele=(\d+)", link["href"])
        if re.search(r"marque=[1-9]", link["href"]):
            if modele and modele.group(1) != "0":
                model = clean(link.get_text(" "))
            else:
                brand = clean(link.get_text(" "))

    bullets = [clean(li.get_text(" ")) for li in details.select("ul.detail li")]
    published = next((b.split(":", 1)[1] for b in bullets if b.lower().startswith("publié")), "")
    equipment = [label for label, value in specs.items() if value == "Oui"
                 and label not in ("1ère main", "Dédouanée")]
    info = soup.select_one("p.information")
    image = soup.select_one(".popup-gallery img")
    return {
        "title": details.select_one("h3").get_text(" ") if details.select_one("h3") else "",
        "brand": brand,
        "model": model,
        "version": details.select_one("h4").get_text(" ") if details.select_one("h4") else "",
        "year": specs.get("Mise en circulation") or specs.get("Modèle"),
        "mileage_km": specs.get("Kilométrage"),
        "fuel": specs.get("Carburant") or specs.get("Motorisation"),
        "gearbox": specs.get("Transmision") or specs.get("Transmission"),
        "fiscal_power_cv": specs.get("Puissance fiscale"),
        "horsepower_ch": specs.get("Puissance dynamique"),
        "color": specs.get("Couleur extérieure"),
        "condition": specs.get("Etat du véhicule"),
        "origin": "Dédouanée" if specs.get("Dédouanée") == "Oui" else "",
        "first_owner": specs.get("1ère main") or ("Oui" if specs.get("Main", "").lower().startswith("premi") else ""),
        "city": specs.get("Ville"),
        "seller_type": specs.get("Vendeur"),
        "price_mad": details.select_one("p.prix").get_text(" ") if details.select_one("p.prix") else "",
        "equipment": "; ".join(equipment),
        "published_at": published,
        "image_url": image.get("src") if image else "",
        "description": info.get_text("\n", strip=True).replace("\\'", "'") if info else "",
    }


FEEDS = [(_list_url(cid), {"body_type": label}) for cid, label in SEGMENTS.items()]
FEEDS.append((_list_url(0), {}))  # ads without a segment; the ones already collected are skipped
SITE = Site("wandaloo", BASE, FEEDS, parse_list, parse_ad)
