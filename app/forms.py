"""Validation des formulaires HTML (messages d'erreur en français, affichés champ par champ)."""
import re
from datetime import date

from starlette.datastructures import FormData

from .constants import BODY_TYPES, BRANDS, CITIES, COLORS, CONDITIONS, FUELS, GEARBOXES, MIN_YEAR

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE_RE = re.compile(r"^(?:\+212|00212|0)([5-7]\d{8})$")


def form_values(form: FormData) -> dict[str, str]:
    """Valeurs texte du formulaire, pour le pré-remplir en cas d'erreur."""
    return {k: v for k, v in form.items() if isinstance(v, str) and k not in ("csrf_token", "password", "password_confirm", "current_password", "new_password")}


def _text(form: FormData, key: str) -> str:
    value = form.get(key)
    return value.strip() if isinstance(value, str) else ""


def _int(form: FormData, key: str) -> int | None:
    raw = re.sub(r"[\s  .]", "", _text(form, key))
    return int(raw) if raw.isdigit() else None


def normalize_phone(raw: str) -> str | None:
    match = PHONE_RE.match(re.sub(r"[\s.\-()]", "", raw))
    return "0" + match.group(1) if match else None


def validate_profile(form: FormData) -> tuple[dict, dict]:
    data, errors = {}, {}

    full_name = _text(form, "full_name")
    if not 2 <= len(full_name) <= 120:
        errors["full_name"] = "Indiquez votre nom (2 à 120 caractères)."
    data["full_name"] = full_name

    phone = normalize_phone(_text(form, "phone"))
    if phone is None:
        errors["phone"] = "Numéro marocain invalide (ex : 06 12 34 56 78)."
    data["phone"] = phone

    city = _text(form, "city")
    if city not in CITIES:
        errors["city"] = "Choisissez une ville."
    data["city"] = city

    return data, errors


def validate_password(password: str, confirm: str, errors: dict, field: str = "password") -> None:
    if len(password) < 8:
        errors[field] = "Le mot de passe doit contenir au moins 8 caractères."
    elif password != confirm:
        errors["password_confirm"] = "Les deux mots de passe ne correspondent pas."


def validate_registration(form: FormData) -> tuple[dict, dict]:
    data, errors = validate_profile(form)

    email = _text(form, "email").lower()
    if not EMAIL_RE.match(email) or len(email) > 255:
        errors["email"] = "Adresse email invalide."
    data["email"] = email

    password = form.get("password") or ""
    validate_password(password, form.get("password_confirm") or "", errors)
    data["password"] = password

    return data, errors


def validate_listing(form: FormData) -> tuple[dict, dict]:
    data, errors = {}, {}
    max_year = date.today().year + 1

    brand = _text(form, "brand")
    if brand not in BRANDS:
        errors["brand"] = "Choisissez une marque."
    data["brand"] = brand

    model = _text(form, "model")
    if not 1 <= len(model) <= 60:
        errors["model"] = "Indiquez le modèle."
    data["model"] = model

    year = _int(form, "year")
    if year is None or not MIN_YEAR <= year <= max_year:
        errors["year"] = f"Année entre {MIN_YEAR} et {max_year}."
    data["year"] = year

    mileage = _int(form, "mileage_km")
    if mileage is None or mileage > 1_500_000:
        errors["mileage_km"] = "Kilométrage invalide."
    data["mileage_km"] = mileage

    fuel = _text(form, "fuel")
    if fuel not in FUELS:
        errors["fuel"] = "Choisissez un carburant."
    data["fuel"] = fuel

    gearbox = _text(form, "gearbox")
    if gearbox not in GEARBOXES:
        errors["gearbox"] = "Choisissez une boîte de vitesses."
    data["gearbox"] = gearbox

    fiscal_power = None
    if _text(form, "fiscal_power"):
        fiscal_power = _int(form, "fiscal_power")
        if fiscal_power is None or not 1 <= fiscal_power <= 60:
            errors["fiscal_power"] = "Puissance fiscale entre 1 et 60 CV."
    data["fiscal_power"] = fiscal_power

    horsepower = None
    if _text(form, "horsepower"):
        horsepower = _int(form, "horsepower")
        if horsepower is None or not 30 <= horsepower <= 2000:
            errors["horsepower"] = "Puissance entre 30 et 2 000 ch."
    data["horsepower"] = horsepower

    for key, choices, message in (
        ("body_type", BODY_TYPES, "Choisissez une carrosserie."),
        ("color", COLORS, "Choisissez une couleur."),
        ("condition", CONDITIONS, "Indiquez l'état du véhicule."),
    ):
        value = _text(form, key)
        if value not in choices:
            errors[key] = message
        data[key] = value

    data["first_hand"] = form.get("first_hand") == "on"

    price = _int(form, "price_mad")
    if price is None or not 5_000 <= price <= 20_000_000:
        errors["price_mad"] = "Prix entre 5 000 et 20 000 000 MAD."
    data["price_mad"] = price

    city = _text(form, "city")
    if city not in CITIES:
        errors["city"] = "Choisissez une ville."
    data["city"] = city

    title = _text(form, "title") or f"{brand} {model} {year or ''}".strip()
    if not 5 <= len(title) <= 120:
        errors["title"] = "Titre entre 5 et 120 caractères."
    data["title"] = title

    description = _text(form, "description")
    if not 20 <= len(description) <= 5000:
        errors["description"] = "Description entre 20 et 5 000 caractères : état, entretien, options…"
    data["description"] = description

    return data, errors
