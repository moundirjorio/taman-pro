from datetime import datetime, timezone

from fastapi import Request
from fastapi.templating import Jinja2Templates

from .config import BASE_DIR, MAX_PHOTOS
from .constants import BODY_TYPES, BRANDS, CITIES, COLORS, CONDITIONS, FUELS, GEARBOXES, MODELS, SORTS
from .security import get_csrf_token

templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))


def fmt_number(value: int | None) -> str:
    if value is None:
        return ""
    return f"{value:,}".replace(",", " ")


def fmt_mad(value: int | None) -> str:
    return f"{fmt_number(value)} MAD" if value is not None else ""


def timeago(dt: datetime) -> str:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    seconds = int((now - dt).total_seconds())
    if seconds < 60:
        return "à l'instant"
    minutes = seconds // 60
    if minutes < 60:
        return f"il y a {minutes} min"
    hours = minutes // 60
    if hours < 24:
        return f"il y a {hours} h"
    days = hours // 24
    if days < 30:
        return f"il y a {days} j"
    return f"le {dt:%d/%m/%Y}"


def whatsapp_number(phone: str) -> str:
    # 06XXXXXXXX -> 2126XXXXXXXX (format wa.me)
    return "212" + phone[1:] if phone.startswith("0") else phone


templates.env.filters.update(num=fmt_number, mad=fmt_mad, timeago=timeago, wa=whatsapp_number)
templates.env.globals.update(
    BRANDS=BRANDS, CITIES=CITIES, FUELS=FUELS, GEARBOXES=GEARBOXES,
    CONDITIONS=CONDITIONS, BODY_TYPES=BODY_TYPES, COLORS=COLORS,
    MODELS=MODELS, SORTS=SORTS, MAX_PHOTOS=MAX_PHOTOS,
)


def flash(request: Request, message: str, category: str = "success") -> None:
    request.session.setdefault("flashes", []).append({"message": message, "category": category})


def render(request: Request, name: str, status_code: int = 200, **context):
    return templates.TemplateResponse(
        request,
        name,
        {
            "user": getattr(request.state, "user", None),
            "csrf_token": get_csrf_token(request),
            "flashes": request.session.pop("flashes", []),
            **context,
        },
        status_code=status_code,
    )
