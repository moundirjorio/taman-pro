import os
import re
import tempfile
import uuid

# Base et dossier d'upload isolés, configurés avant l'import de l'application
_tmp = tempfile.mkdtemp(prefix="taman-tests-")
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp}/test.db".replace("\\", "/")
os.environ["UPLOAD_DIR"] = os.path.join(_tmp, "uploads")
os.environ["SECRET_KEY"] = "test-secret"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

CSRF_RE = re.compile(r'name="csrf_token" value="([^"]+)"')
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

LISTING = {
    "brand": "Dacia", "model": "Duster", "year": "2020", "mileage_km": "76000",
    "fuel": "Diesel", "gearbox": "Manuelle", "fiscal_power": "6", "price_mad": "165000",
    "condition": "Très bon", "body_type": "SUV", "color": "Blanc",
    "city": "Rabat", "title": "", "description": "Très bon état, entretien suivi, carnet à jour.",
}


def csrf(client: TestClient, path: str = "/") -> str:
    return CSRF_RE.search(client.get(path).text).group(1)


def register(client: TestClient, email: str | None = None) -> str:
    email = email or f"user-{uuid.uuid4().hex[:8]}@test.ma"
    r = client.post("/register", data={
        "csrf_token": csrf(client, "/register"), "full_name": "Test User", "email": email,
        "phone": "06 12 34 56 78", "city": "Rabat", "password": "motdepasse", "password_confirm": "motdepasse",
    }, follow_redirects=False)
    assert r.status_code == 303, r.text
    return email


def create_listing(client: TestClient, photos: int = 1, **overrides) -> int:
    files = [("photos", (f"p{i}.png", PNG, "image/png")) for i in range(photos)]
    r = client.post("/annonces/nouvelle", data={"csrf_token": csrf(client), **LISTING, **overrides},
                    files=files or None, follow_redirects=False)
    assert r.status_code == 303, r.text
    return int(r.headers["location"].rsplit("/", 1)[1])


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def other_client():
    with TestClient(app) as c:
        yield c
