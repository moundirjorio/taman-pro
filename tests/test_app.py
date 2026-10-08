import pytest

from .conftest import LISTING, PNG, create_listing, csrf, register


def test_home_page(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "TAMAN" in r.text


def test_register_logout_login(client):
    email = register(client)
    assert "Mes annonces" in client.get("/").text

    client.post("/logout", data={"csrf_token": csrf(client)})
    assert "Mes annonces" not in client.get("/").text

    r = client.post("/login", data={"csrf_token": csrf(client, "/login"), "email": email, "password": "faux"})
    assert r.status_code == 401

    r = client.post("/login", data={"csrf_token": csrf(client, "/login"), "email": email.upper(), "password": "motdepasse"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "Mes annonces" in client.get("/").text


def test_register_validation_and_duplicate(client, other_client):
    email = register(client)
    r = other_client.post("/register", data={
        "csrf_token": csrf(other_client, "/register"), "full_name": "X", "email": email,
        "phone": "123", "city": "Atlantis", "password": "court", "password_confirm": "court",
    })
    assert r.status_code == 422
    assert "Un compte existe déjà" in r.text
    assert "Numéro marocain invalide" in r.text


def test_new_listing_requires_login(client):
    r = client.get("/annonces/nouvelle", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"].startswith("/login?next=")


def test_create_view_search_listing(client):
    register(client)
    listing_id = create_listing(client, photos=2, model="Jogger", year="2022")

    page = client.get(f"/annonces/{listing_id}").text
    assert "Dacia Jogger 2022" in page  # titre automatique
    assert "165 000 MAD" in page

    photo_url = page.split('data-gallery-main')[0].rsplit('src="', 1)[1].split('"')[0]
    assert client.get(photo_url).content == PNG

    assert "Dacia Jogger 2022" in client.get("/?q=jogger").text
    assert "Dacia Jogger 2022" not in client.get("/?q=jogger&price_max=100000").text

    api = client.get("/api/listings", params={"q": "Jogger"}).json()
    assert api["total"] >= 1 and api["items"][0]["model"] == "Jogger"
    assert len(client.get(f"/api/listings/{listing_id}").json()["photos"]) == 2


def test_listing_validation(client):
    register(client)
    r = client.post("/annonces/nouvelle", data={"csrf_token": csrf(client), **LISTING, "year": "1900", "price_mad": "abc"})
    assert r.status_code == 422
    assert "Année entre" in r.text and "Prix entre" in r.text


def test_rejects_non_image_upload(client):
    register(client)
    r = client.post("/annonces/nouvelle", data={"csrf_token": csrf(client), **LISTING},
                    files=[("photos", ("virus.png", b"MZ not an image", "image/png"))])
    assert r.status_code == 422
    assert "pas une image JPEG" in r.text


def test_csrf_required(client):
    register(client)
    r = client.post("/annonces/nouvelle", data={"csrf_token": "faux", **LISTING})
    assert r.status_code == 400


def test_only_owner_can_edit_or_delete(client, other_client):
    register(client)
    listing_id = create_listing(client)

    register(other_client)
    assert other_client.get(f"/annonces/{listing_id}/modifier").status_code == 403
    r = other_client.post(f"/annonces/{listing_id}/supprimer", data={"csrf_token": csrf(other_client)})
    assert r.status_code == 403
    assert client.get(f"/annonces/{listing_id}").status_code == 200


def test_edit_status_delete(client):
    register(client)
    listing_id = create_listing(client, photos=2)
    photo_id = client.get(f"/annonces/{listing_id}/modifier").text.split('name="delete_photos" value="')[1].split('"')[0]

    r = client.post(f"/annonces/{listing_id}/modifier", data={
        "csrf_token": csrf(client), **LISTING, "price_mad": "150000", "title": "Duster révisé", "delete_photos": photo_id,
    }, follow_redirects=False)
    assert r.status_code == 303
    data = client.get(f"/api/listings/{listing_id}").json()
    assert data["price_mad"] == 150000 and data["title"] == "Duster révisé" and len(data["photos"]) == 1

    client.post(f"/annonces/{listing_id}/statut", data={"csrf_token": csrf(client), "status": "sold"})
    assert client.get(f"/api/listings/{listing_id}").json()["status"] == "sold"
    assert "Duster révisé" not in client.get("/?q=révisé").text  # les annonces vendues sortent de la recherche

    client.post(f"/annonces/{listing_id}/supprimer", data={"csrf_token": csrf(client)})
    assert client.get(f"/annonces/{listing_id}").status_code == 404


def test_account_update_and_password(client):
    email = register(client)
    r = client.post("/compte", data={"csrf_token": csrf(client), "full_name": "Nouveau Nom", "phone": "+212 7 00 11 22 33", "city": "Fès"},
                    follow_redirects=False)
    assert r.status_code == 303
    assert "0700112233" in client.get("/compte").text

    r = client.post("/compte/mot-de-passe", data={"csrf_token": csrf(client), "current_password": "motdepasse",
                                                  "new_password": "nouveau-mdp", "password_confirm": "nouveau-mdp"},
                    follow_redirects=False)
    assert r.status_code == 303
    client.post("/logout", data={"csrf_token": csrf(client)})
    r = client.post("/login", data={"csrf_token": csrf(client, "/login"), "email": email, "password": "nouveau-mdp"},
                    follow_redirects=False)
    assert r.status_code == 303


def test_open_redirect_blocked(client):
    email = register(client)
    client.post("/logout", data={"csrf_token": csrf(client)})
    r = client.post("/login", data={"csrf_token": csrf(client, "/login"), "email": email, "password": "motdepasse",
                                    "next": "//evil.example"}, follow_redirects=False)
    assert r.headers["location"] == "/"


def test_new_listing_fields_are_saved(client):
    register(client)
    listing_id = create_listing(client, horsepower="115", color="Gris")
    data = client.get(f"/api/listings/{listing_id}").json()
    assert (data["body_type"], data["color"], data["condition"], data["horsepower"]) == ("SUV", "Gris", "Très bon", 115)

    r = client.post("/annonces/nouvelle", data={"csrf_token": csrf(client), **LISTING, "body_type": "Fusée"})
    assert r.status_code == 422 and "Choisissez une carrosserie" in r.text


ESTIMATE = {"brand": "Dacia", "model": "Duster", "year": 2020, "mileage_km": 76000, "fuel": "Diesel",
            "gearbox": "Manuelle", "fiscal_power": 6, "condition": "Très bon", "city": "Rabat", "color": "Blanc"}


def test_estimate_price(client):
    pytest.importorskip("lightgbm")
    r = client.post("/api/estimate", json=ESTIMATE)
    assert r.status_code == 200, r.text
    est = r.json()
    assert 60_000 < est["price_mad"] < 400_000
    assert est["low_mad"] <= est["price_mad"] <= est["high_mad"]
    assert est["confidence"] == "haute" and est["comparables"] > 50
    assert "couleur" in est["ignored"]

    older = client.post("/api/estimate", json={**ESTIMATE, "year": 2010, "mileage_km": 250000}).json()
    assert older["price_mad"] < est["price_mad"]

    # Variantes d'écriture du site retrouvées dans les données (« GLA » -> « Classe GLA »)
    gla = client.post("/api/estimate", json={**ESTIMATE, "brand": "Mercedes-Benz", "model": "GLA",
                                              "gearbox": "Automatique"}).json()
    assert gla["comparables"] > 0 and gla["price_mad"] > est["price_mad"]


def test_estimate_validation(client):
    r = client.post("/api/estimate", json={**ESTIMATE, "fuel": "Charbon"})
    assert r.status_code == 422
