from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..forms import form_values, validate_registration
from ..models import User
from ..security import check_csrf, hash_password, safe_next_url, verify_password
from ..templating import flash, render

router = APIRouter()


def _log_in(request: Request, user: User) -> None:
    # Nouvelle session à la connexion (protège contre la fixation de session)
    request.session.clear()
    request.session["user_id"] = user.id


@router.get("/register")
def register_page(request: Request, next: str = "/", user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return render(request, "auth/register.html", values={}, errors={}, next=safe_next_url(next))


@router.post("/register")
async def register(request: Request, db: Session = Depends(get_db), _: User | None = Depends(get_current_user)):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    next_url = safe_next_url(form.get("next"))
    data, errors = validate_registration(form)

    if "email" not in errors and db.scalar(select(User).where(User.email == data["email"])):
        errors["email"] = "Un compte existe déjà avec cet email."
    if errors:
        return render(request, "auth/register.html", status_code=422,
                      values=form_values(form), errors=errors, next=next_url)

    user = User(
        full_name=data["full_name"], email=data["email"], phone=data["phone"],
        city=data["city"], password_hash=hash_password(data["password"]),
    )
    db.add(user)
    db.commit()

    _log_in(request, user)
    flash(request, f"Bienvenue sur Taman Pro, {user.full_name.split()[0]} !")
    return RedirectResponse(next_url, status_code=303)


@router.get("/login")
def login_page(request: Request, next: str = "/", user: User | None = Depends(get_current_user)):
    if user:
        return RedirectResponse("/", status_code=303)
    return render(request, "auth/login.html", values={}, error=None, next=safe_next_url(next))


@router.post("/login")
async def login(request: Request, db: Session = Depends(get_db), _: User | None = Depends(get_current_user)):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    next_url = safe_next_url(form.get("next"))
    email = (form.get("email") or "").strip().lower()
    password = form.get("password") or ""

    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(password, user.password_hash):
        return render(request, "auth/login.html", status_code=401, values={"email": email},
                      error="Email ou mot de passe incorrect.", next=next_url)

    _log_in(request, user)
    flash(request, "Vous êtes connecté.")
    return RedirectResponse(next_url, status_code=303)


@router.post("/logout")
async def logout(request: Request):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    request.session.clear()
    flash(request, "Vous êtes déconnecté.")
    return RedirectResponse("/", status_code=303)
