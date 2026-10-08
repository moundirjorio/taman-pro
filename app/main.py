from contextlib import asynccontextmanager
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from .config import BASE_DIR, HTTPS_ONLY, SECRET_KEY, SESSION_MAX_AGE, UPLOAD_DIR
from .database import SessionLocal, create_schema
from .deps import LoginRequired
from .models import User
from .routers import account, api, auth, listings
from .templating import flash, render

UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Suffisant pour la Phase 1 ; passer à Alembic dès que le schéma évolue en production
    create_schema()
    yield


app = FastAPI(title="Taman Pro", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    session_cookie="taman_session",
    max_age=SESSION_MAX_AGE,
    same_site="lax",
    https_only=HTTPS_ONLY,
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "app" / "static"), name="static")
app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(auth.router)
app.include_router(listings.router)
app.include_router(account.router)
app.include_router(api.router)


@app.exception_handler(LoginRequired)
async def login_required_handler(request: Request, exc: LoginRequired):
    flash(request, "Connectez-vous pour continuer.", "info")
    return RedirectResponse(f"/login?next={quote(exc.next_url)}", status_code=303)


@app.exception_handler(StarletteHTTPException)
async def html_error_handler(request: Request, exc: StarletteHTTPException):
    if request.url.path.startswith("/api") or exc.status_code < 400:
        return await http_exception_handler(request, exc)
    if not hasattr(request.state, "user"):
        # Erreur levée avant les dépendances (ex. URL inconnue) : on charge l'utilisateur pour l'en-tête
        with SessionLocal() as db:
            user_id = request.session.get("user_id")
            request.state.user = db.get(User, user_id) if user_id is not None else None
    messages = {404: "Page introuvable.", 403: "Accès refusé."}
    detail = exc.detail if isinstance(exc.detail, str) and exc.detail not in ("Not Found", "Forbidden") else messages.get(exc.status_code, "Une erreur est survenue.")
    return render(request, "error.html", status_code=exc.status_code, code=exc.status_code, detail=detail)
