from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import Listing, User


class LoginRequired(Exception):
    def __init__(self, next_url: str):
        self.next_url = next_url


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    user = None
    user_id = request.session.get("user_id")
    if user_id is not None:
        user = db.get(User, user_id)
        if user is None:
            request.session.pop("user_id", None)
    request.state.user = user
    return user


def require_user(request: Request, user: User | None = Depends(get_current_user)) -> User:
    if user is None:
        next_url = request.url.path + (f"?{request.url.query}" if request.url.query else "")
        raise LoginRequired(next_url)
    return user


def get_owned_listing(db: Session, listing_id: int, user: User) -> Listing:
    listing = db.get(Listing, listing_id)
    if listing is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    if listing.owner_id != user.id:
        raise HTTPException(status_code=403, detail="Vous ne pouvez modifier que vos propres annonces.")
    return listing
