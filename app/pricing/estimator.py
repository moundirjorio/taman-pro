"""Prédiction du prix à partir des caractéristiques saisies dans le formulaire d'annonce."""
import json
import math
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from .features import norm, price_range, resolve_model

MODEL_DIR = Path(__file__).resolve().parent / "model"

# Libellés affichés pour les caractéristiques non prises en compte par le modèle
FEATURE_LABELS = {"color": "couleur", "body_type": "carrosserie", "horsepower": "puissance (ch)"}


class EstimatorUnavailable(RuntimeError):
    pass


@dataclass
class Estimate:
    price_mad: int
    low_mad: int
    high_mad: int
    confidence: str  # haute | moyenne | faible
    comparables: int  # annonces du même modèle dans les données d'entraînement
    ignored: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def _load():
    try:
        import lightgbm as lgb
        import numpy as np
    except ImportError as exc:
        raise EstimatorUnavailable("lightgbm n'est pas installé (pip install -r requirements.txt).") from exc
    meta_path = MODEL_DIR / "meta.json"
    if not meta_path.exists():
        raise EstimatorUnavailable("Modèle absent : lancez « python -m app.pricing.train ».")
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    boosters = {name: lgb.Booster(model_file=str(MODEL_DIR / f"price_{name}.txt")) for name in ("mid", "low", "high")}
    index = {col: {v: i for i, v in enumerate(values)} for col, values in meta["vocab"].items()}
    return np, meta, boosters, index


def _round(value: float) -> int:
    step = 1000 if value >= 100_000 else 500
    return int(round(value / step) * step)


def estimate(car: dict) -> Estimate:
    """car : brand, model, year, mileage_km, fuel, gearbox, et en option fiscal_power, horsepower,
    condition, first_hand, city, color, body_type — avec les libellés du site."""
    np, meta, boosters, index = _load()

    model = resolve_model(car.get("brand"), car.get("model"), set(meta["vocab"]["model"]))
    values = {
        **car,
        "brand": norm(car.get("brand")),
        "model": model,
        "city": norm(car.get("city")),
        "color": norm(car.get("color")),
        "body_type": norm(car.get("body_type")),
        "first_hand": None if car.get("first_hand") is None else float(bool(car["first_hand"])),
    }
    row = np.full((1, len(meta["features"])), np.nan)
    for j, col in enumerate(meta["features"]):
        value = values.get(col)
        if value is None or value == "":
            continue
        if col in index:
            code = index[col].get(value)
            if code is not None:
                row[0, j] = code
        else:
            row[0, j] = float(value)

    mid, low, high = (math.exp(boosters[k].predict(row)[0]) for k in ("mid", "low", "high"))
    low, high = (float(v) for v in price_range(mid, low, high, meta["interval_widen"]))

    comparables = meta["model_counts"].get(model, 0) if model else 0
    if comparables >= 50:
        confidence = "haute"
    elif comparables >= 5 and values["brand"] in index["brand"]:
        confidence = "moyenne"
    else:
        confidence = "faible"

    ignored = [label for feat, label in FEATURE_LABELS.items()
               if car.get(feat) not in (None, "") and feat not in meta["features"]]
    return Estimate(price_mad=_round(mid), low_mad=_round(low), high_mad=_round(high),
                    confidence=confidence, comparables=comparables, ignored=ignored)


def model_info() -> dict:
    _, meta, _, _ = _load()
    return {k: meta[k] for k in ("trained_at", "source", "training_rows", "features", "metrics")}
