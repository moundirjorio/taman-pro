"""API JSON — base pour la future app mobile (React Native)."""
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..constants import BODY_TYPES, COLORS, CONDITIONS, FUELS, GEARBOXES, MIN_YEAR
from ..database import get_db
from ..models import Listing
from ..pricing.estimator import EstimatorUnavailable, estimate
from ..search import parse_filters, search_listings

router = APIRouter(prefix="/api", tags=["api"])


class ListingOut(BaseModel):
    id: int
    title: str
    brand: str
    model: str
    year: int
    mileage_km: int
    fuel: str
    gearbox: str
    fiscal_power: int | None
    horsepower: int | None
    body_type: str | None
    color: str | None
    condition: str | None
    first_hand: bool
    price_mad: int
    city: str
    status: str
    created_at: datetime
    photos: list[str]
    url: str


class ListingDetailOut(ListingOut):
    description: str
    seller_name: str
    views: int


class ListingPage(BaseModel):
    total: int
    page: int
    items: list[ListingOut]


def _to_out(listing: Listing, model=ListingOut, **extra):
    return model(
        **{f: getattr(listing, f) for f in ListingOut.model_fields if f not in ("photos", "url")},
        photos=[p.url for p in listing.photos],
        url=f"/annonces/{listing.id}",
        **extra,
    )


@router.get("/listings", response_model=ListingPage)
def list_listings(request: Request, db: Session = Depends(get_db)):
    """Mêmes filtres que la page d'accueil : q, brand, city, fuel, gearbox, price_min, price_max, year_min, year_max, km_max, sort, page."""
    filters = parse_filters(request.query_params)
    items, total = search_listings(db, filters)
    return ListingPage(total=total, page=filters.page, items=[_to_out(l) for l in items])


@router.get("/listings/{listing_id}", response_model=ListingDetailOut)
def get_listing(listing_id: int, db: Session = Depends(get_db)):
    listing = db.scalar(
        select(Listing).where(Listing.id == listing_id)
        .options(selectinload(Listing.photos), selectinload(Listing.owner))
    )
    if listing is None:
        raise HTTPException(status_code=404, detail="Annonce introuvable.")
    return _to_out(listing, ListingDetailOut, description=listing.description,
                   seller_name=listing.owner.full_name, views=listing.views)


class EstimateIn(BaseModel):
    brand: str = Field(min_length=1, max_length=40)
    model: str = Field(min_length=1, max_length=60)
    year: int = Field(ge=MIN_YEAR, le=date.today().year + 1)
    mileage_km: int = Field(ge=0, le=1_500_000)
    fuel: Literal[tuple(FUELS)]
    gearbox: Literal[tuple(GEARBOXES)]
    fiscal_power: int | None = Field(default=None, ge=1, le=60)
    horsepower: int | None = Field(default=None, ge=30, le=2000)
    condition: Literal[tuple(CONDITIONS)] | None = None
    body_type: Literal[tuple(BODY_TYPES)] | None = None
    color: Literal[tuple(COLORS)] | None = None
    first_hand: bool | None = None
    city: str | None = Field(default=None, max_length=60)


class EstimateOut(BaseModel):
    price_mad: int
    low_mad: int
    high_mad: int
    confidence: Literal["haute", "moyenne", "faible"]
    comparables: int
    ignored: list[str]


@router.post("/estimate", response_model=EstimateOut)
async def estimate_price(car: EstimateIn):
    """Estimation du prix du marché (MAD) à partir des caractéristiques du véhicule."""
    try:
        result = await run_in_threadpool(estimate, car.model_dump())
    except EstimatorUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return EstimateOut(**vars(result))
