import secrets

import bcrypt
from fastapi import HTTPException, Request


def hash_password(password: str) -> str:
    # bcrypt ne prend en compte que les 72 premiers octets
    return bcrypt.hashpw(password.encode()[:72], bcrypt.gensalt()).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode()[:72], password_hash.encode())
    except ValueError:
        return False


def get_csrf_token(request: Request) -> str:
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf"] = token
    return token


def check_csrf(request: Request, token: object) -> None:
    expected = request.session.get("csrf")
    if not expected or not isinstance(token, str) or not secrets.compare_digest(expected, token):
        raise HTTPException(status_code=400, detail="Session expirée ou formulaire invalide. Rechargez la page et réessayez.")


def safe_next_url(url: str | None, default: str = "/") -> str:
    # Évite les redirections ouvertes vers un autre site
    if url and url.startswith("/") and not url.startswith("//") and "\\" not in url:
        return url
    return default
