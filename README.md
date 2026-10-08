# Taman Pro — Plateforme d'annonces auto (Phase 1)

Plateforme d'achat-vente de voitures d'occasion au Maroc. Cette version couvre la **Phase 1 — Fondations** du plan directeur : dépôt d'annonces, recherche avancée, comptes utilisateurs. Les modules IA (prix, assistant, matching) viendront se brancher dessus.

## Fonctionnalités

- **Comptes** : inscription, connexion et déconnexion, modification du profil et du mot de passe
- **Annonces** : dépôt avec jusqu'à 10 photos, modification, suppression, marquage « vendue »
- **Recherche** : texte libre et filtres (marque, ville, carburant, boîte, prix, année, kilométrage), tri, pagination
- **Page annonce** : galerie photo, caractéristiques, contact du vendeur par téléphone ou WhatsApp (réservé aux membres connectés), conseils anti-arnaque, annonces similaires
- **Mes annonces** : tableau de bord avec statistiques (annonces en ligne, vendues, vues)
- **Estimation IA du prix** : bouton « Estimer le prix » dans le formulaire de dépôt — prix estimé, fourchette probable, comparaison avec le prix saisi et bouton « Utiliser ce prix » (`POST /api/estimate`)
- **API JSON** en lecture : `GET /api/listings` et `GET /api/listings/{id}`, prête pour la future app React Native (documentation interactive sur `/docs`)
- **Mobile-first** : interface pensée d'abord pour le smartphone

## Stack

FastAPI · SQLAlchemy 2 · Jinja2 · SQLite en développement (PostgreSQL en production) · bcrypt · sessions signées

## Lancer le projet (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt

python -m app.seed                      # (optionnel) 15 annonces de démo
uvicorn app.main:app --reload --port 8010
```

Ouvrir http://127.0.0.1:8010. Compte de démo : `demo@tamanpro.ma` / `demo1234`.

## Estimation du prix (IA)

Modèle **LightGBM** entraîné sur `cars_dataframe(in).csv` (~64 000 annonces exploitables après nettoyage). Le code est dans `app/pricing/` et les modèles entraînés dans `app/pricing/model/`.

```powershell
python -m app.pricing.train                   # réentraîner (≈ 1 min), ou : python -m app.pricing.train autre.csv
```

- **Caractéristiques utilisées** : marque, modèle, année, kilométrage, carburant, boîte, puissance fiscale, état, première main, ville.
- **Pas encore utilisées** : couleur, carrosserie et puissance (ch). Elles sont saisies et enregistrées avec l'annonce, mais le CSV ne contient pas ces colonnes. Si un futur CSV contient `Color`, `Body Type` ou `Horsepower`, le script d'entraînement les prend en compte automatiquement.
- **Précision** (sur 15 % des données gardées de côté) : erreur médiane de 9 %, 80 % des estimations à moins de 20 % du prix réel. La fourchette affichée contient le vrai prix dans environ 70 % des cas. Le détail est dans `app/pricing/model/meta.json`.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest
```

## Configuration (variables d'environnement)

| Variable | Défaut | Rôle |
|---|---|---|
| `DATABASE_URL` | `sqlite:///taman.db` | ex. `postgresql+psycopg://user:mdp@localhost/taman` (décommenter `psycopg` dans `requirements.txt`) |
| `SECRET_KEY` | générée dans `.secret_key` | clé de signature des sessions, **obligatoire en production** |
| `UPLOAD_DIR` | `uploads/` | dossier des photos |
| `HTTPS_ONLY` | `0` | mettre `1` en production (cookie de session envoyé uniquement en HTTPS) |

## Structure

```
app/
  main.py          application, middlewares, gestion des erreurs
  models.py        User, Listing, ListingPhoto
  forms.py         validation des formulaires
  search.py        filtres et recherche (partagés entre les pages et l'API)
  photos.py        upload (vérification du vrai format de l'image, 5 Mo max)
  security.py      mots de passe (bcrypt), CSRF, redirections sûres
  routers/         auth, listings, account, api
  templates/       pages HTML (Jinja2)
  static/          CSS, JS, images
tests/             tests de bout en bout (pytest)
```

## Sécurité en place

Mots de passe hachés avec bcrypt · jeton CSRF sur tous les formulaires · cookie de session `SameSite=Lax` · nouvelle session à chaque connexion · vérification du propriétaire avant toute modification · uploads validés par leur contenu et renommés aléatoirement · redirections `next` limitées au site.

## Prochaines étapes

- **Avant la mise en ligne** : migrations Alembic, limitation des tentatives de connexion, vérification de l'email et du téléphone, redimensionnement et compression des photos, stockage objet (S3 / MinIO)
- **Fonctionnalités** : favoris, messagerie interne, alertes de recherche
- **Phase 2** : afficher le badge « Bonne affaire / Prix juste / Trop cher » sur les cartes
