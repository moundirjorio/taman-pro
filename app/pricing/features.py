"""Normalisation des caractéristiques, partagée entre l'entraînement et la prédiction.

Les libellés du CSV (anglais : « Petrol », « Manual »…) sont convertis vers ceux du site
(« Essence », « Manuelle »…) pour que le modèle reçoive les mêmes valeurs dans les deux cas.
"""
import re
import unicodedata

import numpy as np

CSV_FUELS = {"diesel": "Diesel", "petrol": "Essence", "hybrid": "Hybride", "electrique": "Électrique", "lpg": "GPL"}
CSV_GEARBOXES = {"manual": "Manuelle", "automatic": "Automatique"}
CSV_CONDITIONS = {
    "new": "Neuf", "excellent": "Excellent", "very good": "Très bon", "good": "Bon",
    "fair": "Correct", "damaged": "Endommagé", "for parts": "Pour pièces",
}

# Caractéristiques catégorielles et numériques, dans l'ordre attendu par le modèle.
# color, body_type et horsepower ne sont utilisées que si le CSV d'entraînement contient
# les colonnes correspondantes (voir OPTIONAL_CSV_COLUMNS) : la liste réelle est enregistrée
# avec le modèle dans meta.json.
CATEGORICAL = ["brand", "model", "fuel", "gearbox", "condition", "city", "color", "body_type"]
NUMERIC = ["year", "mileage_km", "fiscal_power", "horsepower", "first_hand"]
OPTIONAL_CSV_COLUMNS = {"Color": "color", "Body Type": "body_type", "Horsepower": "horsepower"}


def norm(value: str | None) -> str:
    """« Citroën C-Elysée » -> « citroen c elysee »"""
    if not value:
        return ""
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", value).strip()


def compact(value: str | None) -> str:
    """Clé sans espaces, pour que « RAV4 » corresponde à « RAV 4 » et « i10 » à « i 10 »."""
    return norm(value).replace(" ", "")


def model_key(brand: str | None, model: str | None) -> str:
    return f"{compact(brand)}|{compact(model)}"


def resolve_model(brand: str | None, model: str | None, known: set[str]) -> str | None:
    """Retrouve le modèle dans le vocabulaire appris malgré les variantes d'écriture du site.

    ex. Mercedes « GLA » -> « Classe GLA », Opel « Crossland » -> « Crossland X ».
    """
    key = model_key(brand, model)
    if key in known:
        return key
    b, m = compact(brand), compact(model)
    if not m:
        return None
    for candidate in (f"{b}|classe{m}", f"{b}|serie{m}"):
        if candidate in known:
            return candidate
    prefixed = sorted(k for k in known if k.startswith(f"{b}|{m}"))
    return min(prefixed, key=len) if prefixed else None


def parse_int(value) -> float | None:
    """« 8 CV » -> 8, « Plus de 41 CV » -> 41, « 120 000 » -> 120000."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    digits = re.findall(r"\d+", str(value).replace(" ", "").replace(" ", "").replace("\xa0", ""))
    return float(digits[0]) if digits else None


def parse_mileage(value: str) -> float | None:
    """Tranche « 120 000 - 129 999 » -> milieu de la tranche (125 000)."""
    bounds = [parse_int(part) for part in str(value).split("-")]
    bounds = [b for b in bounds if b is not None]
    if not bounds:
        return None
    return sum(bounds) / len(bounds) if len(bounds) == 2 else bounds[0]


MIN_HALF_WIDTH = 0.03  # fourchette d'au moins ±3 %


def price_range(mid, low, high, widen: float):
    """Fourchette centrée (en log) sur le prix estimé, de la largeur donnée par les modèles quantiles.

    Les trois modèles étant entraînés séparément, le quantile haut peut tomber sous le prix médian :
    on garde donc leur écart, pas leurs bornes.
    """
    half = widen * np.maximum((np.log(high) - np.log(low)) / 2, MIN_HALF_WIDTH)
    return mid * np.exp(-half), mid * np.exp(half)
