"""
Train RandomForest classifier and regressor for accident danger prediction.

Usage (from api/TrafficJamsBackend/):
    python scripts/train_model.py
    python scripts/train_model.py --accidents-csv ../../police_data.csv
    python scripts/train_model.py --eps 150 --min-samples 4 --output-dir models/

Outputs written to --output-dir (default: models/):
    classifier.joblib  — predicts whether a location is dangerous (binary)
    regressor.joblib   — predicts total material damage in CZK (log-scale target)
    metadata.json      — training timestamp, metrics, and DBSCAN params used
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from sklearn.cluster import DBSCAN
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import classification_report, mean_absolute_error, r2_score, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).parent
DEFAULT_ACCIDENTS_CSV = (_SCRIPT_DIR / ".." / "accidents_data.csv").resolve()
DEFAULT_OUTPUT_DIR = (_SCRIPT_DIR / ".." / "models").resolve()

# ─── Feature columns ──────────────────────────────────────────────────────────
# Only features knowable BEFORE an accident — safe to use at inference time.

CATEGORICAL_FEATURES = [
    "road_type_code",       # street / freeway / …
    "weather_condition",    # clear / rain / snow / …
    "road_surface",         # dry / wet / ice / …
    "light_condition",      # daylight / dark / …
    "road_condition",       # normal / slippery / …
    "accident_type",        # collision / animal / …
    "cause_primary",        # driver error / speed / …
]
NUMERIC_FEATURES = [
    "hour",           # 0–23
    "day_of_week",    # 0 Mon – 6 Sun
    "month",          # 1–12
    "is_weekend",     # binary
    "is_night",       # binary  (hour < 6 or hour >= 22)
    "road_number_int",# numeric part of road ref, e.g. "I/43" → 43
]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES


# ─── Data loading ─────────────────────────────────────────────────────────────

def _latlon_to_utm(lats: np.ndarray, lons: np.ndarray) -> np.ndarray:
    """Project WGS84 lat/lon to a metric UTM CRS. Returns Nx2 array in metres."""
    center_lon = float(np.mean(lons))
    center_lat = float(np.mean(lats))
    zone = int((center_lon + 180) / 6) + 1
    epsg = 32600 + zone if center_lat >= 0 else 32700 + zone
    transformer = Transformer.from_crs("EPSG:4326", f"EPSG:{epsg}", always_xy=True)
    xs, ys = transformer.transform(lons, lats)
    return np.column_stack([xs, ys])


def load_accidents(csv_path: Path) -> pd.DataFrame:
    """Load accidents CSV and decode lat/lng from the EWKB hex geometry column."""
    log.info("Loading accidents from %s", csv_path)
    df = pd.read_csv(csv_path)
    log.info("  %d rows loaded", len(df))
    lats, lngs = [], []
    for hex_str in df["location_geog"]:
        try:
            geom = shapely.from_wkb(bytes.fromhex(str(hex_str)))
            lats.append(float(geom.y))
            lngs.append(float(geom.x))
        except Exception:
            lats.append(np.nan)
            lngs.append(np.nan)
    df["lat"] = lats
    df["lng"] = lngs
    df = df.dropna(subset=["lat", "lng"]).reset_index(drop=True)
    log.info("  %d rows with valid coordinates", len(df))
    return df


def run_dbscan(df: pd.DataFrame, eps_meters: float, min_samples: int) -> np.ndarray:
    """Run DBSCAN on metric coordinates. Returns label array (-1 = noise)."""
    coords_m = _latlon_to_utm(df["lat"].values, df["lng"].values)
    db = DBSCAN(eps=eps_meters, min_samples=min_samples, algorithm="ball_tree", metric="euclidean", n_jobs=-1)
    labels = db.fit_predict(coords_m)
    n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
    n_noise = int(np.sum(labels == -1))
    log.info("DBSCAN: %d clusters, %d noise, %d cluster members", n_clusters, n_noise, len(labels) - n_noise)
    return labels


# ─── Feature engineering ──────────────────────────────────────────────────────

def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    """Derive all model features in-place on a copy of df."""
    df = df.copy()
    dt = pd.to_datetime(df["event_time"], utc=True, errors="coerce")
    df["hour"]           = dt.dt.hour
    df["day_of_week"]    = dt.dt.dayofweek           # 0 = Mon, 6 = Sun
    df["month"]          = dt.dt.month
    df["is_weekend"]     = (dt.dt.dayofweek >= 5).astype(int)
    df["is_night"]       = ((dt.dt.hour < 6) | (dt.dt.hour >= 22)).astype(int)
    df["road_number_int"] = (
        df["road_number"].astype(str).str.extract(r"(\d+)", expand=False).astype(float)
    )
    # Ensure all categorical columns exist and have no NaN
    for col in CATEGORICAL_FEATURES:
        if col in df.columns:
            df[col] = df[col].fillna("unknown").astype(str)
        else:
            df[col] = "unknown"
    return df


# ─── Pipeline builder ─────────────────────────────────────────────────────────

def build_pipeline(estimator) -> Pipeline:
    """Wrap an estimator with categorical encoding + numeric imputation."""
    preprocessor = ColumnTransformer(
        transformers=[
            ("cat", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1), CATEGORICAL_FEATURES),
            ("num", SimpleImputer(strategy="median"), NUMERIC_FEATURES),
        ],
        remainder="drop",
    )
    return Pipeline([("prep", preprocessor), ("model", estimator)])



# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train classifier + regressor for accident danger prediction")
    parser.add_argument("--accidents-csv", type=Path, default=DEFAULT_ACCIDENTS_CSV,
                        help=f"Path to police_data.csv (default: {DEFAULT_ACCIDENTS_CSV})")
    parser.add_argument("--eps", type=float, default=100.0,
                        help="DBSCAN eps radius in metres (default: 100)")
    parser.add_argument("--min-samples", type=int, default=3,
                        help="DBSCAN min_samples to form a cluster (default: 3)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR,
                        help=f"Directory to write model files (default: {DEFAULT_OUTPUT_DIR})")
    parser.add_argument("--train-ratio", type=float, default=0.8,
                        help="Fraction of data (sorted by time) used for training (default: 0.8)")
    return parser.parse_args()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if not args.accidents_csv.exists():
        log.error("Accidents CSV not found: %s", args.accidents_csv)
        sys.exit(1)

    # ── 1. Load raw data and assign DBSCAN labels ──────────────────────────────
    df = load_accidents(args.accidents_csv)
    labels = run_dbscan(df, args.eps, args.min_samples)
    df["cluster_label"] = labels
    df["is_dangerous"] = (labels != -1).astype(int)
    pct = df["is_dangerous"].mean() * 100
    log.info("Class balance: %.1f%% dangerous (cluster member), %.1f%% isolated (noise)", pct, 100 - pct)

    # ── 2. Engineer features ───────────────────────────────────────────────────
    df = engineer_features(df)

    # ── 3. Time-based train / test split ──────────────────────────────────────
    # Sort by event_time so the test set is always the most recent accidents.
    # Random split would leak future data into the training set.
    df = df.sort_values("event_time").reset_index(drop=True)
    split_idx = int(len(df) * args.train_ratio)
    train_df = df.iloc[:split_idx]
    test_df  = df.iloc[split_idx:]
    log.info("Split: %d train / %d test rows", len(train_df), len(test_df))

    X_train = train_df[ALL_FEATURES]
    X_test  = test_df[ALL_FEATURES]

    # ── 4. Classification — is this location dangerous? ────────────────────────
    log.info("Training RandomForestClassifier …")
    y_clf_train = train_df["is_dangerous"]
    y_clf_test  = test_df["is_dangerous"]

    # class_weight="balanced" compensates for typical ~70% noise / ~30% cluster imbalance
    clf_pipeline = build_pipeline(
        RandomForestClassifier(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        )
    )
    clf_pipeline.fit(X_train, y_clf_train)

    y_clf_pred  = clf_pipeline.predict(X_test)
    y_clf_proba = clf_pipeline.predict_proba(X_test)[:, 1]
    roc_auc = roc_auc_score(y_clf_test, y_clf_proba)

    print("\n── Classifier ────────────────────────────────────────")
    print(classification_report(y_clf_test, y_clf_pred, target_names=["isolated", "dangerous"]))
    print(f"ROC-AUC: {roc_auc:.4f}")

    # ── 5. Regression — how bad is the material damage? ───────────────────────
    log.info("Training RandomForestRegressor …")
    # Drop rows with missing damage so the regressor has a clean target
    reg_train = train_df[train_df["damage_czk"].notna()]
    reg_test  = test_df[test_df["damage_czk"].notna()]

    # Log-transform because damage_czk is heavily right-skewed
    y_reg_train = np.log1p(reg_train["damage_czk"].astype(float))
    y_reg_test  = np.log1p(reg_test["damage_czk"].astype(float))

    reg_pipeline = build_pipeline(
        RandomForestRegressor(
            n_estimators=200,
            max_depth=12,
            min_samples_leaf=5,
            n_jobs=-1,
            random_state=42,
        )
    )
    reg_pipeline.fit(reg_train[ALL_FEATURES], y_reg_train)

    y_reg_pred_log = reg_pipeline.predict(reg_test[ALL_FEATURES])
    mae = mean_absolute_error(np.expm1(y_reg_test), np.expm1(y_reg_pred_log))
    r2  = r2_score(y_reg_test, y_reg_pred_log)

    print("\n── Regressor ─────────────────────────────────────────")
    print(f"MAE: {mae:>12,.0f} CZK   (on original scale)")
    print(f"R²:  {r2:>12.4f}         (on log scale)")

    # ── 6. Save models and metadata ───────────────────────────────────────────
    args.output_dir.mkdir(parents=True, exist_ok=True)

    clf_path  = args.output_dir / "classifier.joblib"
    reg_path  = args.output_dir / "regressor.joblib"
    meta_path = args.output_dir / "metadata.json"

    joblib.dump(clf_pipeline, clf_path)
    joblib.dump(reg_pipeline, reg_path)

    metadata = {
        "trained_at":         datetime.now(timezone.utc).isoformat(),
        "n_train_samples":    len(train_df),
        "n_test_samples":     len(test_df),
        "dbscan_eps_meters":  args.eps,
        "dbscan_min_samples": args.min_samples,
        "clf_roc_auc":        round(roc_auc, 4),
        "reg_mae_czk":        round(mae, 2),
        "reg_r2_log_scale":   round(r2, 4),
        "features":           ALL_FEATURES,
    }
    meta_path.write_text(json.dumps(metadata, indent=2))

    print(f"\n✓ Models saved to {args.output_dir.resolve()}")
    print(f"  classifier.joblib  ({clf_path.stat().st_size // 1024} KB)")
    print(f"  regressor.joblib   ({reg_path.stat().st_size // 1024} KB)")
    print(f"  metadata.json")


if __name__ == "__main__":
    main()
