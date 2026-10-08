# Scraper d'annonces auto (Maroc)

Collecte les annonces de voitures d'occasion publiques de **Avito.ma**, **Moteur.ma**, **Wandaloo.com** et **Kifal Auto** dans un seul CSV structuré (`marketplace_listings.csv`).

```powershell
..\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python scrape_marketplaces.py --max-pages 3          # échantillon rapide
python scrape_marketplaces.py                        # tout (très long, voir plus bas)
python scrape_marketplaces.py --sites wandaloo kifal # seulement certains sites
```

Relancer la commande **reprend** là où elle s'est arrêtée : les annonces déjà présentes dans le CSV ne sont pas re-téléchargées. Ctrl+C arrête proprement, sans perdre ce qui a déjà été écrit. `--fresh` repart d'un fichier vide.

## Colonnes

| Colonne | Contenu |
|---|---|
| `source`, `ad_id`, `url` | site, identifiant de l'annonce sur ce site, lien |
| `brand`, `model`, `version` | marque, modèle, finition |
| `year`, `mileage_km` | année-modèle, kilométrage (entier) |
| `fuel`, `gearbox` | Diesel / Essence / Hybride / Hybride rechargeable / Électrique / GPL ; Manuelle / Automatique |
| `fiscal_power_cv`, `horsepower_ch` | puissance fiscale (CV), puissance réelle (ch) |
| `body_type`, `color`, `condition` | carrosserie, couleur, état |
| `doors`, `origin`, `first_owner` | portes ; WW au Maroc / Dédouanée / Importée neuve / Non dédouanée ; Oui / Non |
| `city`, `sector`, `seller_type` | ville, quartier, Particulier / Professionnel |
| `price_mad` | prix en MAD (vide si « prix non spécifié ») |
| `equipment` | équipements séparés par `; ` |
| `published_at` | date de publication (AAAA-MM-JJ) |
| `duplicate_of` | rempli si la même voiture (marque, modèle, année, km, prix) est déjà dans le CSV depuis un autre site : à exclure pour l'entraînement |

Ce que chaque site fournit (une case vide = information absente du site, pas un bug) :

| | Avito | Moteur.ma | Wandaloo | Kifal |
|---|---|---|---|---|
| état, portes, quartier | ✓ | portes | état | — |
| carrosserie | — | parfois | ✓ (segment) | ✓ |
| couleur | — | parfois | ✓ | — |
| puissance (ch) | — | — | ✓ | ✓ |

## Volume et durée

Avito compte environ **135 000** annonces auto, Moteur.ma environ 120 000. Il faut une requête par annonce (la page de liste ne donne ni la marque ni le modèle), espacées de 2 s par site, donc un crawl complet d'Avito prend **plusieurs jours**. Les sites tournent en parallèle et le script reprend où il s'est arrêté : on peut le lancer chaque nuit. `--delay 1` divise le temps par deux, mais ne descendez pas en dessous.

Les annonces Moteur.ma qui sont des reprises d'Avito (photos hébergées sur avito.ma) sont ignorées par défaut, puisqu'elles sont déjà collectées depuis Avito. `--include-reposts` les garde.

## Règles respectées

- `robots.txt` de chaque site (y compris `Crawl-delay`). **MarocAnnonces** l'interdit à tous les robots non-moteurs de recherche, donc il n'est pas collecté.
- Requêtes séquentielles par site. Si un site répond 403 ou limite le débit, le script s'arrête pour ce site, sans chercher à contourner.
- Aucune connexion à un compte. **Ni nom ni téléphone de vendeur** n'est enregistré.
- AutoCaz n'est pas pris en charge : c'est une application JavaScript sans annonces dans le HTML.

Ces données restent la propriété des sites. Gardez-les pour l'entraînement du modèle et l'analyse, sans les republier.

## Ajouter un site

Créer `scrapers/<site>.py` avec `parse_list` (URL des annonces d'une page de liste) et `parse_ad` (dict de champs), exposer `SITE = Site(...)`, puis l'ajouter dans `scrapers/__init__.py`. La normalisation (carburant, boîte, nombres, dates, marques) est faite pour tous les sites dans `common.finalize`.
