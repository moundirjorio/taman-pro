from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    # Stocké en UTC "naïf" (SQLite ne conserve pas le fuseau)
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(20))
    city: Mapped[str] = mapped_column(String(60))
    password_hash: Mapped[str] = mapped_column(String(100))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    listings: Mapped[list["Listing"]] = relationship(
        back_populates="owner", cascade="all, delete-orphan"
    )


class Listing(Base):
    __tablename__ = "listings"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(120))
    brand: Mapped[str] = mapped_column(String(40), index=True)
    model: Mapped[str] = mapped_column(String(60))
    year: Mapped[int] = mapped_column(Integer, index=True)
    mileage_km: Mapped[int] = mapped_column(Integer)
    fuel: Mapped[str] = mapped_column(String(20))
    gearbox: Mapped[str] = mapped_column(String(20))
    fiscal_power: Mapped[int | None] = mapped_column(Integer, nullable=True)
    horsepower: Mapped[int | None] = mapped_column(Integer, nullable=True)
    body_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(20), nullable=True)
    first_hand: Mapped[bool] = mapped_column(Boolean, default=False)
    price_mad: Mapped[int] = mapped_column(Integer, index=True)
    city: Mapped[str] = mapped_column(String(60), index=True)
    description: Mapped[str] = mapped_column(Text)

    status: Mapped[str] = mapped_column(String(10), default="active", index=True)  # active | sold
    views: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    owner: Mapped[User] = relationship(back_populates="listings")
    photos: Mapped[list["ListingPhoto"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
        order_by="ListingPhoto.position",
    )

    @property
    def cover(self) -> "ListingPhoto | None":
        return self.photos[0] if self.photos else None


class ListingPhoto(Base):
    __tablename__ = "listing_photos"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(64))
    position: Mapped[int] = mapped_column(Integer, default=0)

    listing: Mapped[Listing] = relationship(back_populates="photos")

    @property
    def url(self) -> str:
        return f"/uploads/{self.filename}"
