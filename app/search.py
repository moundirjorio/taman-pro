from dataclasses import asdict, dataclass
from urllib.parse import urlencode

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .config import LISTINGS_PER_PAGE
from .constants import SORTS
from .models import Listing

ORDERINGS = {
    "recent": [Listing.created_at.desc()],
    "price_asc": [Listing.price_mad.asc(), Listing.created_at.desc()],
    "price_desc": [Listing.price_mad.desc(), Listing.created_at.desc()],
    "km_asc": [Listing.mileage_km.asc(), Listing.created_at.desc()],
    "year_desc": [Listing.year.desc(), Listing.created_at.desc()],
}


@dataclass
class Filters:
    q: str = ""
    brand: str = ""
    city: str = ""
    fuel: str = ""
    gearbox: str = ""
    price_min: int | None = None
    price_max: int | None = None
    year_min: int | None = None
    year_max: int | None = None
    km_max: int | None = None
    sort: str = "recent"
    page: int = 1

    def params(self, exclude: tuple[str, ...] = (), **overrides) -> dict:
        """Filtres non vides, pour reconstruire les URLs (pagination, tri)."""
        values = {**asdict(self), **overrides}
        return {
            k: v for k, v in values.items()
            if k not in exclude and v not in ("", None) and not (k == "page" and v == 1)
        }

    def query_string(self, **overrides) -> str:
        return urlencode(self.params(**overrides))

    @property
    def active_count(self) -> int:
        fields = ("brand", "fuel", "gearbox", "price_min", "price_max", "year_min", "year_max", "km_max")
        return sum(1 for f in fields if getattr(self, f) not in ("", None))


def _int(value: str | None) -> int | None:
    raw = (value or "").replace(" ", "").replace(" ", "")
    return int(raw) if raw.isdigit() else None


def parse_filters(params) -> Filters:
    sort = params.get("sort", "recent")
    return Filters(
        q=(params.get("q") or "").strip()[:100],
        brand=(params.get("brand") or "").strip(),
        city=(params.get("city") or "").strip(),
        fuel=(params.get("fuel") or "").strip(),
        gearbox=(params.get("gearbox") or "").strip(),
        price_min=_int(params.get("price_min")),
        price_max=_int(params.get("price_max")),
        year_min=_int(params.get("year_min")),
        year_max=_int(params.get("year_max")),
        km_max=_int(params.get("km_max")),
        sort=sort if sort in SORTS else "recent",
        page=max(_int(params.get("page")) or 1, 1),
    )


def search_listings(db: Session, f: Filters, per_page: int = LISTINGS_PER_PAGE) -> tuple[list[Listing], int]:
    stmt = select(Listing).where(Listing.status == "active")

    if f.q:
        escaped = f.q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        like = f"%{escaped}%"
        stmt = stmt.where(or_(
            Listing.title.ilike(like, escape="\\"),
            Listing.brand.ilike(like, escape="\\"),
            Listing.model.ilike(like, escape="\\"),
        ))
    if f.brand:
        stmt = stmt.where(Listing.brand == f.brand)
    if f.city:
        stmt = stmt.where(Listing.city == f.city)
    if f.fuel:
        stmt = stmt.where(Listing.fuel == f.fuel)
    if f.gearbox:
        stmt = stmt.where(Listing.gearbox == f.gearbox)
    if f.price_min is not None:
        stmt = stmt.where(Listing.price_mad >= f.price_min)
    if f.price_max is not None:
        stmt = stmt.where(Listing.price_mad <= f.price_max)
    if f.year_min is not None:
        stmt = stmt.where(Listing.year >= f.year_min)
    if f.year_max is not None:
        stmt = stmt.where(Listing.year <= f.year_max)
    if f.km_max is not None:
        stmt = stmt.where(Listing.mileage_km <= f.km_max)

    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = db.scalars(
        stmt.options(selectinload(Listing.photos))
        .order_by(*ORDERINGS[f.sort])
        .offset((f.page - 1) * per_page)
        .limit(per_page)
    ).all()
    return list(items), total
