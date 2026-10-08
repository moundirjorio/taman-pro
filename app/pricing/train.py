"""Entraînement du modèle d'estimation de prix : python -m app.pricing.train [chemin.csv]

Produit dans app/pricing/model/ :
  price_mid.txt / price_low.txt / price_high.txt   modèles LightGBM (prix médian et fourchette)
  meta.json                                        vocabulaire des catégories, métriques, volumes par modèle
"""
import csv
import json
import math
import random
import sys
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path

import lightgbm as lgb
import numpy as np

from .features import (
    CATEGORICAL, CSV_CONDITIONS, CSV_FUELS, CSV_GEARBOXES, NUMERIC, OPTIONAL_CSV_COLUMNS,
    model_key, norm, parse_int, parse_mileage, price_range,
)

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CSV = BASE_DIR.parent.parent / "cars_dataframe(in).csv"
MODEL_DIR = BASE_DIR / "model"

MIN_PRICE, MAX_PRICE = 5_000, 5_000_000
MIN_COUNT = {"model": 5, "city": 20}  # en dessous, la catégorie est traitée comme inconnue
LOW_Q, HIGH_Q = 0.15, 0.85  # fourchette affichée : 70 % des ventes y tombent

PARAMS = {
    "learning_rate": 0.05, "num_leaves": 63, "min_data_in_leaf": 20, "feature_fraction": 0.9,
    "bagging_fraction": 0.9, "bagging_freq": 1, "cat_smooth": 10, "max_cat_to_onehot": 8,
    "seed": 42, "verbose": -1,
}


def read_rows(path: Path) -> list[dict]:
    """Lit le CSV ; certaines lignes sont entièrement entourées de guillemets (double encodage)."""
    with path.open(encoding="utf-8", newline="") as f:
        lines = f.read().splitlines()
    header = next(csv.reader([lines[0]]))
    rows = []
    for line in lines[1:]:
        fields = next(csv.reader([line]), [])
        if len(fields) == 1:
            fields = next(csv.reader([fields[0]]), [])
        if len(fields) == len(header):
            rows.append(dict(zip(header, fields)))
    return rows


def to_record(row: dict, optional: dict[str, str]) -> dict | None:
    price = parse_int(row.get("Price"))
    year = parse_int(row.get("Year"))
    fuel = CSV_FUELS.get(norm(row.get("Fuel")))
    if price is None or not MIN_PRICE <= price <= MAX_PRICE or year is None or not 1980 <= year <= date.today().year + 1 or fuel is None:
        return None
    owner = norm(row.get("First Owner"))
    record = {
        "brand": norm(row["Brand"]),
        "model": model_key(row["Brand"], row["Model"]),
        "fuel": fuel,
        "gearbox": CSV_GEARBOXES.get(norm(row.get("Gearbox"))),
        "condition": CSV_CONDITIONS.get(norm(row.get("Condition"))),
        "city": norm(row.get("Location")) or None,
        "year": year,
        "mileage_km": parse_mileage(row.get("Mileage", "")),
        "fiscal_power": parse_int(row.get("Fiscal Power")),
        "first_hand": 1.0 if owner == "yes" else 0.0 if owner == "no" else None,
        "price": price,
    }
    for column, feature in optional.items():
        value = row.get(column)
        record[feature] = parse_int(value) if feature in NUMERIC else (norm(value) or None)
    return record


def build_vocab(records: list[dict], categorical: list[str]) -> dict[str, list[str]]:
    vocab = {}
    for col in categorical:
        counts = Counter(r[col] for r in records if r.get(col))
        vocab[col] = sorted(v for v, n in counts.items() if n >= MIN_COUNT.get(col, 1))
    return vocab


def encode(records: list[dict], features: list[str], vocab: dict[str, list[str]]) -> np.ndarray:
    index = {col: {v: i for i, v in enumerate(values)} for col, values in vocab.items()}
    X = np.full((len(records), len(features)), np.nan)
    for i, r in enumerate(records):
        for j, col in enumerate(features):
            value = r.get(col)
            if value is None:
                continue
            if col in index:
                code = index[col].get(value)
                if code is not None:
                    X[i, j] = code
            else:
                X[i, j] = value
    return X


def fit(X, y, cat_idx, objective: dict, X_val=None, y_val=None, rounds: int = 3000):
    params = {**PARAMS, **objective}
    train = lgb.Dataset(X, y, categorical_feature=cat_idx, free_raw_data=False)
    if X_val is None:
        return lgb.train(params, train, num_boost_round=rounds)
    valid = lgb.Dataset(X_val, y_val, reference=train)
    return lgb.train(params, train, num_boost_round=rounds, valid_sets=[valid],
                     callbacks=[lgb.early_stopping(100, verbose=False)])


def main(csv_path: Path = DEFAULT_CSV) -> None:
    rows = read_rows(csv_path)
    optional = {c: f for c, f in OPTIONAL_CSV_COLUMNS.items() if rows and c in rows[0]}
    records = [r for r in (to_record(row, optional) for row in rows) if r]
    # Les doublons exacts fausseraient l'évaluation (même annonce dans l'entraînement et le test)
    records = list({tuple(sorted((k, str(v)) for k, v in r.items())): r for r in records}.values())
    print(f"{len(rows)} lignes lues, {len(records)} annonces exploitables (prix renseigné, sans doublon)")

    categorical = [c for c in CATEGORICAL if c in records[0]]
    numeric = [c for c in NUMERIC if c in records[0]]
    features = categorical + numeric
    cat_idx = list(range(len(categorical)))

    random.Random(42).shuffle(records)
    split = int(len(records) * 0.85)
    train_r, valid_r = records[:split], records[split:]
    vocab = build_vocab(train_r, categorical)
    X_tr, X_va = encode(train_r, features, vocab), encode(valid_r, features, vocab)
    y_tr = np.log([r["price"] for r in train_r])
    y_va_price = np.array([r["price"] for r in valid_r])
    y_va = np.log(y_va_price)

    objectives = {
        "mid": {"objective": "regression"},
        "low": {"objective": "quantile", "alpha": LOW_Q},
        "high": {"objective": "quantile", "alpha": HIGH_Q},
    }
    rounds, preds = {}, {}
    for name, obj in objectives.items():
        booster = fit(X_tr, y_tr, cat_idx, obj, X_va, y_va)
        rounds[name] = booster.best_iteration or booster.current_iteration()
        preds[name] = np.exp(booster.predict(X_va, num_iteration=rounds[name]))

    # Les modèles quantiles sont trop optimistes : on élargit la fourchette jusqu'à couvrir
    # réellement HIGH_Q - LOW_Q des prix de validation
    target = HIGH_Q - LOW_Q
    widen = 1.0
    while widen < 3:
        low, high = price_range(preds["mid"], preds["low"], preds["high"], widen)
        if np.mean((y_va_price >= low) & (y_va_price <= high)) >= target:
            break
        widen += 0.05
    preds["low"], preds["high"] = low, high

    ape = np.abs(preds["mid"] - y_va_price) / y_va_price
    metrics = {
        "validation_rows": len(valid_r),
        "mae_mad": round(float(np.mean(np.abs(preds["mid"] - y_va_price)))),
        "median_abs_pct_error": round(float(np.median(ape)) * 100, 1),
        "mean_abs_pct_error": round(float(np.mean(ape)) * 100, 1),
        "within_10_pct": round(float(np.mean(ape <= 0.10)) * 100, 1),
        "within_20_pct": round(float(np.mean(ape <= 0.20)) * 100, 1),
        "interval_widen": round(widen, 2),
        "interval_coverage_pct": round(float(np.mean((y_va_price >= preds["low"]) & (y_va_price <= preds["high"]))) * 100, 1),
        "r2_log": round(1 - float(np.sum((np.log(preds["mid"]) - y_va) ** 2) / np.sum((y_va - y_va.mean()) ** 2)), 3),
    }
    print("Validation :", json.dumps(metrics, ensure_ascii=False))

    # Modèle final réentraîné sur toutes les données avec le nombre d'itérations trouvé
    vocab = build_vocab(records, categorical)
    X_all = encode(records, features, vocab)
    y_all = np.log([r["price"] for r in records])
    MODEL_DIR.mkdir(exist_ok=True)
    for name, obj in objectives.items():
        booster = fit(X_all, y_all, cat_idx, obj, rounds=max(math.ceil(rounds[name] * 1.1), 50))
        booster.save_model(str(MODEL_DIR / f"price_{name}.txt"))

    meta = {
        "trained_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": csv_path.name,
        "training_rows": len(records),
        "features": features,
        "categorical": categorical,
        "vocab": vocab,
        "interval_widen": round(widen, 2),
        "model_counts": dict(Counter(r["model"] for r in records)),
        "metrics": metrics,
    }
    (MODEL_DIR / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    print(f"Modèles enregistrés dans {MODEL_DIR}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CSV)
