from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..config import LISTINGS_PER_PAGE, MAX_PHOTOS
from ..database import get_db
from ..deps import get_current_user, get_owned_listing, require_user
from ..forms import form_values, validate_listing
from ..models import Listing, ListingPhoto, User
from ..photos import delete_photo_file, save_photo, uploaded_photos
from ..search import parse_filters, search_listings
from ..security import check_csrf
from ..templating import flash, render

router = APIRouter()


def _listing_values(listing: Listing) -> dict[str, str]:
    return {
        "brand": listing.brand, "model": listing.model, "year": str(listing.year),
        "mileage_km": str(listing.mileage_km), "fuel": listing.fuel, "gearbox": listing.gearbox,
        "fiscal_power": str(listing.fiscal_power or ""), "horsepower": str(listing.horsepower or ""),
        "body_type": listing.body_type or "", "color": listing.color or "", "condition": listing.condition or "",
        "first_hand": "on" if listing.first_hand else "",
        "price_mad": str(listing.price_mad), "city": listing.city,
        "title": listing.title, "description": listing.description,
    }


def _form_page(request: Request, listing: Listing | None, values: dict, errors: dict, status_code: int = 200):
    return render(request, "listings/form.html", status_code=status_code,
                  listing=listing, values=values, errors=errors)


async def _store_photos(listing: Listing, uploads, start_position: int) -> list[str]:
    """Enregistre les photos ; en cas d'erreur, supprime celles déjà écrites et relance l'erreur."""
    saved: list[str] = []
    try:
        for i, upload in enumerate(uploads):
            filename = await save_photo(upload)
            saved.append(filename)
            listing.photos.append(ListingPhoto(filename=filename, position=start_position + i))
    except ValueError:
        for filename in saved:
            delete_photo_file(filename)
        raise
    return saved


@router.get("/")
def home(request: Request, db: Session = Depends(get_db), _: User | None = Depends(get_current_user)):
    filters = parse_filters(request.query_params)
    listings, total = search_listings(db, filters)
    pages = max((total + LISTINGS_PER_PAGE - 1) // LISTINGS_PER_PAGE, 1)
    return render(request, "listings/index.html", listings=listings, total=total,
                  filters=filters, pages=pages)


@router.get("/annonces/nouvelle")
def new_listing_page(request: Request, user: User = Depends(require_user)):
    return _form_page(request, None, {"city": user.city}, {})


@router.post("/annonces/nouvelle")
async def create_listing(request: Request, db: Session = Depends(get_db), user: User = Depends(require_user)):
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    data, errors = validate_listing(form)
    uploads = uploaded_photos(form)
    if len(uploads) > MAX_PHOTOS:
        errors["photos"] = f"{MAX_PHOTOS} photos maximum."
    if errors:
        return _form_page(request, None, form_values(form), errors, 422)

    listing = Listing(owner_id=user.id, **data)
    try:
        await _store_photos(listing, uploads, 0)
    except ValueError as exc:
        return _form_page(request, None, form_values(form), {"photos": str(exc)}, 422)

    db.add(listing)
    db.commit()
    flash(request, "Votre annonce est en ligne !")
    return RedirectResponse(f"/annonces/{listing.id}", status_code=303)


@router.get("/annonces/{listing_id:int}")
def listing_detail(listing_id: int, request: Request, db: Session = Depends(get_db),
                   user: User | None = Depends(get_current_user)):
    listing = db.scalar(
        select(Listing).where(Listing.id == listing_id)
        .options(selectinload(Listing.photos), selectinload(Listing.owner))
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Cette annonce n'existe pas ou a été supprimée.")

    is_owner = user is not None and user.id == listing.owner_id
    viewed = request.session.get("viewed", [])
    if not is_owner and listing_id not in viewed:
        listing.views += 1
        db.commit()
        request.session["viewed"] = (viewed + [listing_id])[-100:]

    similar = db.scalars(
        select(Listing)
        .where(Listing.status == "active", Listing.brand == listing.brand, Listing.id != listing.id)
        .options(selectinload(Listing.photos))
        .order_by(Listing.created_at.desc()).limit(4)
    ).all()
    return render(request, "listings/detail.html", listing=listing, is_owner=is_owner, similar=similar)


@router.get("/annonces/{listing_id:int}/modifier")
def edit_listing_page(listing_id: int, request: Request, db: Session = Depends(get_db),
                      user: User = Depends(require_user)):
    listing = get_owned_listing(db, listing_id, user)
    return _form_page(request, listing, _listing_values(listing), {})


@router.post("/annonces/{listing_id:int}/modifier")
async def update_listing(listing_id: int, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(require_user)):
    listing = get_owned_listing(db, listing_id, user)
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    data, errors = validate_listing(form)

    to_delete_ids = {int(v) for v in form.getlist("delete_photos") if isinstance(v, str) and v.isdigit()}
    to_delete = [p for p in listing.photos if p.id in to_delete_ids]
    uploads = uploaded_photos(form)
    if len(listing.photos) - len(to_delete) + len(uploads) > MAX_PHOTOS:
        errors["photos"] = f"{MAX_PHOTOS} photos maximum au total."
    if errors:
        return _form_page(request, listing, form_values(form), errors, 422)

    try:
        new_files = await _store_photos(listing, uploads, len(listing.photos))
    except ValueError as exc:
        db.rollback()
        return _form_page(request, listing, form_values(form), {"photos": str(exc)}, 422)

    for key, value in data.items():
        setattr(listing, key, value)
    removed_files = [p.filename for p in to_delete]
    for photo in to_delete:
        listing.photos.remove(photo)
    for position, photo in enumerate(listing.photos):
        photo.position = position

    try:
        db.commit()
    except Exception:
        db.rollback()
        for filename in new_files:
            delete_photo_file(filename)
        raise
    for filename in removed_files:
        delete_photo_file(filename)

    flash(request, "Annonce mise à jour.")
    return RedirectResponse(f"/annonces/{listing.id}", status_code=303)


@router.post("/annonces/{listing_id:int}/statut")
async def change_status(listing_id: int, request: Request, db: Session = Depends(get_db),
                        user: User = Depends(require_user)):
    listing = get_owned_listing(db, listing_id, user)
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    status = form.get("status")
    if status not in ("active", "sold"):
        raise HTTPException(status_code=400, detail="Statut invalide.")
    listing.status = status
    db.commit()
    flash(request, "Annonce marquée comme vendue." if status == "sold" else "Annonce remise en ligne.")
    back = "/mes-annonces" if form.get("back") == "list" else f"/annonces/{listing.id}"
    return RedirectResponse(back, status_code=303)


@router.post("/annonces/{listing_id:int}/supprimer")
async def delete_listing(listing_id: int, request: Request, db: Session = Depends(get_db),
                         user: User = Depends(require_user)):
    listing = get_owned_listing(db, listing_id, user)
    form = await request.form()
    check_csrf(request, form.get("csrf_token"))
    filenames = [p.filename for p in listing.photos]
    db.delete(listing)
    db.commit()
    for filename in filenames:
        delete_photo_file(filename)
    flash(request, "Annonce supprimée.")
    return RedirectResponse("/mes-annonces", status_code=303)
