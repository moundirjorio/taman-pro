"""Données de démonstration : python -m app.seed"""
import random
from datetime import timedelta

from sqlalchemy import select

from .database import SessionLocal, create_schema
from .models import Listing, User, utcnow
from .security import hash_password

DEMO_EMAIL = "demo@tamanpro.ma"
DEMO_PASSWORD = "demo1234"

CARS = [
    ("Dacia", "Logan", 2019, 98_000, "Diesel", "Manuelle", 6, 82_000),
    ("Dacia", "Sandero Stepway", 2021, 54_000, "Diesel", "Manuelle", 6, 128_000),
    ("Dacia", "Duster", 2020, 76_000, "Diesel", "Manuelle", 6, 165_000),
    ("Renault", "Clio", 2018, 112_000, "Diesel", "Manuelle", 6, 105_000),
    ("Renault", "Mégane", 2017, 140_000, "Diesel", "Automatique", 6, 120_000),
    ("Peugeot", "208", 2020, 61_000, "Essence", "Manuelle", 6, 135_000),
    ("Peugeot", "3008", 2019, 89_000, "Diesel", "Automatique", 8, 245_000),
    ("Volkswagen", "Golf", 2016, 165_000, "Diesel", "Manuelle", 7, 145_000),
    ("Hyundai", "Tucson", 2021, 45_000, "Diesel", "Automatique", 8, 275_000),
    ("Toyota", "Yaris", 2022, 28_000, "Hybride", "Automatique", 6, 195_000),
    ("Kia", "Picanto", 2019, 70_000, "Essence", "Manuelle", 5, 89_000),
    ("Mercedes-Benz", "Classe C", 2017, 130_000, "Diesel", "Automatique", 9, 310_000),
    ("Citroën", "C3", 2018, 95_000, "Diesel", "Manuelle", 6, 99_000),
    ("Fiat", "Tipo", 2020, 68_000, "Diesel", "Manuelle", 6, 118_000),
    ("BYD", "Atto 3", 2024, 12_000, "Électrique", "Automatique", None, 360_000),
]
BODY_TYPES = {
    "Logan": "Berline", "Sandero Stepway": "Citadine", "Duster": "SUV", "Clio": "Citadine", "Mégane": "Berline",
    "208": "Citadine", "3008": "SUV", "Golf": "Berline", "Tucson": "SUV", "Yaris": "Citadine", "Picanto": "Citadine",
    "Classe C": "Berline", "C3": "Citadine", "Tipo": "Berline", "Atto 3": "SUV",
}
COLORS = ["Blanc", "Noir", "Gris", "Argent", "Bleu", "Rouge"]
CITIES = ["Casablanca", "Rabat", "Marrakech", "Tanger", "Fès", "Agadir", "Kénitra", "Mohammedia"]
DESCRIPTIONS = [
    "Voiture en très bon état, entretien régulier chez le concessionnaire, carnet à jour. Climatisation, vitres électriques, radar de recul. Visite technique valide.",
    "Véhicule dédouané, jamais accidenté. Pneus neufs, vidange récente. Dispo pour essai et inspection par votre mécanicien.",
    "Première main, toutes factures disponibles. Écran tactile, Bluetooth, régulateur de vitesse. Prix légèrement négociable.",
]


def main() -> None:
    create_schema()
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == DEMO_EMAIL))
        if user:
            print(f"Déjà initialisé. Connexion : {DEMO_EMAIL} / {DEMO_PASSWORD}")
            return

        user = User(full_name="Compte Démo", email=DEMO_EMAIL, phone="0612345678",
                    city="Casablanca", password_hash=hash_password(DEMO_PASSWORD))
        db.add(user)
        rng = random.Random(42)
        for i, (brand, model, year, km, fuel, gearbox, cv, price) in enumerate(CARS):
            db.add(Listing(
                owner=user, brand=brand, model=model, year=year, mileage_km=km, fuel=fuel,
                gearbox=gearbox, fiscal_power=cv, body_type=BODY_TYPES[model], color=rng.choice(COLORS),
                condition=rng.choice(["Excellent", "Très bon", "Bon"]), first_hand=rng.random() < 0.4, price_mad=price,
                city=rng.choice(CITIES), title=f"{brand} {model} {year}",
                description=rng.choice(DESCRIPTIONS), views=rng.randint(5, 300),
                created_at=utcnow() - timedelta(hours=i * 7 + rng.randint(0, 6)),
            ))
        db.commit()
        print(f"{len(CARS)} annonces créées. Connexion : {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
