from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import require_user
from ..forms import form_values, validate_password, validate_profile
from ..models import Listing, User
from ..security import check_csrf, hash_password, verify_password
from ..templating import flash, render

router = APIRouter()


@router.get("/mes-annonces")
def my_listings(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    listings = db.scalars(
        select(Listing).where(Listing.owner_id == user.id)
        .options(selectinload(Listing.photos))
        .order_by(Listing.created_at.desc())
    ).all()
    stats = {
        "active": sum(1 for l in listings if l.status == "active"),
        "sold": sum(1 for l in listings if l.status == "sold"),
        "views": sum(l.views for l in listings),
    }
    return render(request, "account/my_listings.html", listings=listings, stats=stats)


def _account_page(request: Request, user: User, status_code: int = 200, **ctx):
    ctx.setdefault("values", {"full_name": user.full_name, "phone": user.phone, "city": user.city})
    ctx.setdefault("errors", {})
    ctx.setdefault("pw_errors", {})
    return render(request, "account/account.html", status_code=status_code, **ctx)


@router.get("/compte")
def account_page(request: Request, user: User = Depends(require_user)):
    return _account_page(request, user)


@router.post("/compte")
async def update_account(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    data, errors = validate_profile(form)
    if errors:
        return _account_page(request, user, 422, values=form_values(form), errors=errors)

    user.full_name, user.phone, user.city = data["full_name"], data["phone"], data["city"]
    db.commit()
    flash(request, "Profil mis à jour.")
    return RedirectResponse("/compte", status_code=303)


@router.post("/compte/mot-de-passe")
async def change_password(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    errors: dict[str, str] = {}
    if not verify_password(form.get("current_password") or "", user.password_hash):
        errors["current_password"] = "Mot de passe actuel incorrect."
    else:
        validate_password(form.get("new_password") or "", form.get("password_confirm") or "", errors, field="new_password")
    if errors:
        return _account_page(request, user, 422, pw_errors=errors)

    user.password_hash = hash_password(form.get("new_password"))
    db.commit()
    flash(request, "Mot de passe modifié.")
    return RedirectResponse("/compte", status_code=303)
