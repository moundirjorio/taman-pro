MODELS: dict[str, list[str]] = {
    "Dacia": ["Logan", "Sandero", "Sandero Stepway", "Duster", "Lodgy", "Dokker", "Jogger", "Spring"],
    "Renault": ["Clio", "Mégane", "Symbol", "Kangoo", "Captur", "Kadjar", "Express", "Austral", "Arkana", "Talisman"],
    "Peugeot": ["206", "207", "208", "2008", "301", "308", "3008", "5008", "508", "Partner", "Rifter"],
    "Citroën": ["C3", "C3 Aircross", "C4", "C-Elysée", "C5 Aircross", "Berlingo"],
    "Volkswagen": ["Polo", "Golf", "Jetta", "Passat", "T-Roc", "Tiguan", "Touareg", "Caddy"],
    "Toyota": ["Yaris", "Corolla", "C-HR", "RAV4", "Hilux", "Land Cruiser", "Prado"],
    "Hyundai": ["i10", "i20", "Accent", "Elantra", "Creta", "Kona", "Tucson", "Santa Fe"],
    "Kia": ["Picanto", "Rio", "Ceed", "Stonic", "Seltos", "Sportage", "Sorento"],
    "Fiat": ["Panda", "Punto", "Tipo", "500", "Doblo", "Fiorino"],
    "Mercedes-Benz": ["Classe A", "Classe C", "Classe E", "Classe S", "GLA", "GLC", "GLE", "Vito"],
    "BMW": ["Série 1", "Série 3", "Série 5", "X1", "X3", "X5", "X6"],
    "Audi": ["A3", "A4", "A5", "A6", "Q3", "Q5", "Q7"],
    "Ford": ["Fiesta", "Focus", "EcoSport", "Kuga", "Ranger", "Transit"],
    "Skoda": ["Fabia", "Octavia", "Superb", "Kamiq", "Karoq", "Kodiaq"],
    "Seat": ["Ibiza", "Leon", "Arona", "Ateca"],
    "Nissan": ["Micra", "Juke", "Qashqai", "X-Trail", "Navara"],
    "Suzuki": ["Celerio", "Swift", "Dzire", "Vitara", "Jimny"],
    "Mitsubishi": ["Attrage", "ASX", "Outlander", "Pajero", "L200"],
    "Opel": ["Corsa", "Astra", "Insignia", "Crossland", "Grandland", "Mokka"],
    "BYD": ["Dolphin", "Atto 3", "Seal", "Song Plus", "Han"],
    "Chery": ["Arrizo 5", "Tiggo 2 Pro", "Tiggo 4 Pro", "Tiggo 7 Pro", "Tiggo 8 Pro"],
    "MG": ["MG4", "MG5", "ZS", "HS", "RX5"],
}

BRANDS: list[str] = sorted(
    list(MODELS) + [
        "Alfa Romeo", "Chevrolet", "Cupra", "Geely", "Haval", "Honda", "Jeep",
        "Land Rover", "Mazda", "Porsche", "Tesla", "Volvo",
    ],
    key=str.lower,
) + ["Autre"]

CITIES: list[str] = sorted([
    "Agadir", "Béni Mellal", "Berrechid", "Casablanca", "Dakhla", "El Jadida", "Errachidia",
    "Essaouira", "Fès", "Guelmim", "Ifrane", "Kénitra", "Khémisset", "Khouribga", "Laâyoune",
    "Larache", "Marrakech", "Meknès", "Mohammedia", "Nador", "Ouarzazate", "Oujda", "Rabat",
    "Safi", "Salé", "Settat", "Tanger", "Taza", "Témara", "Tétouan",
]) + ["Autre"]

FUELS = ["Diesel", "Essence", "Hybride", "Électrique", "GPL"]
GEARBOXES = ["Manuelle", "Automatique"]
CONDITIONS = ["Neuf", "Excellent", "Très bon", "Bon", "Correct", "Endommagé", "Pour pièces"]
BODY_TYPES = ["Citadine", "Berline", "Break", "SUV", "4x4", "Monospace", "Coupé", "Cabriolet", "Pick-up", "Utilitaire"]
COLORS = ["Blanc", "Noir", "Gris", "Argent", "Bleu", "Rouge", "Beige", "Marron", "Vert", "Jaune", "Orange", "Autre"]

SORTS = {
    "recent": "Plus récentes",
    "price_asc": "Prix croissant",
    "price_desc": "Prix décroissant",
    "km_asc": "Kilométrage le plus bas",
    "year_desc": "Année la plus récente",
}

MIN_YEAR = 1980
