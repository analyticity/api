"""
Train RandomForest classifier and regressor for accident danger prediction.

Enhancements over the baseline:
  - TimeSeriesSplit cross-validation (no future-data leakage)
  - GridSearchCV hyperparameter tuning on the training split
  - Extended evaluation: ROC-AUC, Avg-Precision, MAE, RMSE, R², feature importances

Usage (from api/TrafficJamsBackend/):
    python scripts/train_model.py                # full grid search (~27 combos × 5 folds)
    python scripts/train_model.py --quick        # small grid, faster iteration
    python scripts/train_model.py --cv-folds 3   # fewer CV folds
    python scripts/train_model.py --eps 150 --min-samples 4

Outputs written to --output-dir (default: models/):
    classifier.joblib  — best classifier pipeline after tuning
    regressor.joblib   — best regressor pipeline after tuning
    metadata.json      — best params, CV scores, test metrics, feature importances
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
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    average_precision_score,
    classification_report,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
    roc_auc_score,
)
from sklearn.inspection import permutation_importance
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ─── Paths ────────────────────────────────────────────────────────────────────

_SCRIPT_DIR = Path(__file__).parent
DEFAULT_ACCIDENTS_CSV = (_SCRIPT_DIR / ".." / "accidents_data.csv").resolve()
DEFAULT_OUTPUT_DIR    = (_SCRIPT_DIR / ".." / "models").resolve()

# ─── Feature columns ──────────────────────────────────────────────────────────
# Only features knowable BEFORE an accident — safe to use at inference time.
# `accident_type` and `cause_primary` are deliberately excluded: both are
# attributes recorded AFTER the event (data leakage) and at inference the API
# has no way to supply them, so they always collapse to "unknown".

CATEGORICAL_FEATURES = [
    "road_type_code",       # street / secondary / …
    "weather_condition",    # clear / rain / snow / …
    "road_surface",         # dry / wet / ice / …
    "light_condition",      # daylight / dark / …
    "road_condition",       # normal / slippery / …
]
NUMERIC_FEATURES = [
    "hour",            # 0–23
    "day_of_week",     # 0 Mon – 6 Sun
    "month",           # 1–12
    "is_weekend",      # binary
    "is_night",        # binary (hour < 6 or hour >= 22)
    "road_number_int", # numeric part of road ref, e.g. "I/43" → 43
]
ALL_FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

# ─── Hyperparameter grids ─────────────────────────────────────────────────────

_CLF_GRID_FULL = {
    "model__n_estimators":     [100, 200, 300],
    "model__max_depth":        [8, 12, None],
    "model__min_samples_leaf": [3, 5, 10],
}
_CLF_GRID_QUICK = {
    "model__n_estimators":     [100, 200],
    "model__max_depth":        [8, 12],
    "model__min_samples_leaf": [5],
}
# HistGradientBoostingRegressor with Gamma loss models the right-skewed
# strictly-positive damage_czk target directly — no log1p / expm1 round-trip,
# so predictions are not biased toward the geometric mean.
_REG_GRID_FULL = {
    "model__learning_rate":    [0.05, 0.1],
    "model__max_iter":         [200, 400],
    "model__max_leaf_nodes":   [15, 31],
    "model__min_samples_leaf": [10, 20],
}
_REG_GRID_QUICK = {
    "model__learning_rate":    [0.1],
    "model__max_iter":         [200],
    "model__max_leaf_nodes":   [31],
    "model__min_samples_leaf": [20],
}


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
    dt = pd.to_datetime(df["first_seen"], utc=True, errors="coerce")
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


# ─── Evaluation helpers ───────────────────────────────────────────────────────

def _grid_size(param_grid: dict) -> int:
    size = 1
    for v in param_grid.values():
        size *= len(v)
    return size


def _print_feature_importances(
    pipeline: Pipeline,
    top_n: int = 10,
    *,
    X_eval: pd.DataFrame | None = None,
    y_eval: pd.Series | None = None,
    scoring: str | None = None,
) -> list[dict]:
    """Show top feature importances.

    Tree-based estimators expose ``feature_importances_`` directly. For
    HistGradientBoosting (which does not), fall back to permutation importance
    on the held-out evaluation set.
    """
    model = pipeline.named_steps["model"]
    if hasattr(model, "feature_importances_"):
        importances = model.feature_importances_
    else:
        if X_eval is None or y_eval is None:
            print("  (feature importances unavailable)")
            return []
        result = permutation_importance(
            pipeline, X_eval, y_eval,
            n_repeats=10, random_state=42, n_jobs=-1, scoring=scoring,
        )
        importances = result.importances_mean

    ranked = sorted(zip(ALL_FEATURES, importances), key=lambda x: x[1], reverse=True)[:top_n]
    print(f"\n  Top {top_n} feature importances:")
    max_imp = max((i for _, i in ranked), default=0.0) or 1.0
    for name, imp in ranked:
        bar = "█" * max(0, int((imp / max_imp) * 30))
        print(f"    {name:<22} {imp:>8.4f}  {bar}")
    return [{"feature": n, "importance": round(float(i), 6)} for n, i in ranked]


# ─── Tuning functions ─────────────────────────────────────────────────────────

def tune_classifier(
    base_pipeline: Pipeline,
    param_grid: dict,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    cv: TimeSeriesSplit,
) -> tuple[Pipeline, dict]:
    """Run GridSearchCV on training data, evaluate best estimator on held-out test set."""
    n_combos = _grid_size(param_grid)
    log.info("Classifier GridSearchCV: %d combinations × %d folds = %d fits …",
             n_combos, cv.n_splits, n_combos * cv.n_splits)

    gs = GridSearchCV(
        base_pipeline, param_grid,
        scoring="roc_auc", cv=cv, n_jobs=-1, verbose=1, refit=True,
    )
    gs.fit(X_train, y_train)
    best = gs.best_estimator_

    cv_std = gs.cv_results_["std_test_score"][gs.best_index_]
    log.info("Best params : %s", gs.best_params_)
    log.info("CV ROC-AUC  : %.4f ± %.4f", gs.best_score_, cv_std)

    y_pred  = best.predict(X_test)
    y_proba = best.predict_proba(X_test)[:, 1]
    roc_auc  = roc_auc_score(y_test, y_proba)
    avg_prec = average_precision_score(y_test, y_proba)

    print("\n── Classifier ────────────────────────────────────────────────")
    print(f"  Best params    : {gs.best_params_}")
    print(f"  CV  ROC-AUC    : {gs.best_score_:.4f} ± {cv_std:.4f}")
    print(f"  Test ROC-AUC   : {roc_auc:.4f}")
    print(f"  Test Avg-Prec  : {avg_prec:.4f}")
    print()
    print(classification_report(y_test, y_pred, target_names=["isolated", "dangerous"]))
    importances = _print_feature_importances(best)

    return best, {
        "best_params":          gs.best_params_,
        "cv_roc_auc_mean":      round(float(gs.best_score_), 4),
        "cv_roc_auc_std":       round(float(cv_std), 4),
        "test_roc_auc":         round(roc_auc, 4),
        "test_avg_precision":   round(avg_prec, 4),
        "feature_importances":  importances,
    }


def tune_regressor(
    base_pipeline: Pipeline,
    param_grid: dict,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    cv: TimeSeriesSplit,
) -> tuple[Pipeline, dict]:
    """Run GridSearchCV on training data, evaluate best estimator on held-out test set."""
    n_combos = _grid_size(param_grid)
    log.info("Regressor GridSearchCV: %d combinations × %d folds = %d fits …",
             n_combos, cv.n_splits, n_combos * cv.n_splits)

    gs = GridSearchCV(
        base_pipeline, param_grid,
        scoring="neg_mean_absolute_error", cv=cv, n_jobs=-1, verbose=1, refit=True,
    )
    gs.fit(X_train, y_train)
    best = gs.best_estimator_

    cv_std = gs.cv_results_["std_test_score"][gs.best_index_]
    log.info("Best params : %s", gs.best_params_)

    y_pred = best.predict(X_test)
    mae  = mean_absolute_error(y_test, y_pred)
    rmse = np.sqrt(mean_squared_error(y_test, y_pred))
    r2   = r2_score(y_test, y_pred)

    print("\n── Regressor ─────────────────────────────────────────────────")
    print(f"  Best params  : {gs.best_params_}")
    print(f"  CV  MAE      : {-gs.best_score_:>12,.0f} CZK  ± {abs(cv_std):,.0f}")
    print(f"  Test MAE     : {mae:>12,.0f} CZK")
    print(f"  Test RMSE    : {rmse:>12,.0f} CZK")
    print(f"  Test R²      : {r2:.4f}")
    importances = _print_feature_importances(
        best, X_eval=X_test, y_eval=y_test, scoring="neg_mean_absolute_error",
    )

    return best, {
        "best_params":         gs.best_params_,
        "cv_mae_czk_mean":     round(float(-gs.best_score_), 2),
        "cv_mae_czk_std":      round(float(abs(cv_std)), 2),
        "test_mae_czk":        round(mae, 2),
        "test_rmse_czk":       round(rmse, 2),
        "test_r2":             round(r2, 4),
        "feature_importances": importances,
    }


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train classifier + regressor with GridSearchCV tuning")
    parser.add_argument("--accidents-csv", type=Path, default=DEFAULT_ACCIDENTS_CSV)
    parser.add_argument("--eps", type=float, default=30.0,
                        help="DBSCAN eps radius in metres (default: 30)")
    parser.add_argument("--min-samples", type=int, default=3,
                        help="DBSCAN min_samples to form a cluster (default: 3)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--train-ratio", type=float, default=0.8,
                        help="Fraction of data used for training, sorted by time (default: 0.8)")
    parser.add_argument("--cv-folds", type=int, default=5,
                        help="Number of TimeSeriesSplit folds for cross-validation (default: 5)")
    parser.add_argument("--quick", action="store_true",
                        help="Use a smaller parameter grid for faster iteration")
    return parser.parse_args()


# ─── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    args = parse_args()

    if not args.accidents_csv.exists():
        log.error("Accidents CSV not found: %s", args.accidents_csv)
        sys.exit(1)

    if args.quick:
        log.info("Quick mode — using reduced parameter grids")

    # ── 1. Load + DBSCAN labels ───────────────────────────────────────────────
    df = load_accidents(args.accidents_csv)
    labels = run_dbscan(df, args.eps, args.min_samples)
    df["cluster_label"] = labels
    df["is_dangerous"]  = (labels != -1).astype(int)
    pct = df["is_dangerous"].mean() * 100
    log.info("Class balance: %.1f%% dangerous, %.1f%% noise", pct, 100 - pct)

    # ── 2. Feature engineering ────────────────────────────────────────────────
    df = engineer_features(df)

    # ── 3. Time-based train / test split ─────────────────────────────────────
    # Sort by first_seen — test set is always the most recent data.
    # Random splits would leak future information into the training fold.
    df = df.sort_values("first_seen").reset_index(drop=True)
    split_idx = int(len(df) * args.train_ratio)
    train_df, test_df = df.iloc[:split_idx], df.iloc[split_idx:]
    log.info("Split: %d train / %d test rows", len(train_df), len(test_df))

    X_train, X_test = train_df[ALL_FEATURES], test_df[ALL_FEATURES]

    # TimeSeriesSplit respects temporal order within the training folds
    cv = TimeSeriesSplit(n_splits=args.cv_folds)
    clf_grid = _CLF_GRID_QUICK if args.quick else _CLF_GRID_FULL
    reg_grid = _REG_GRID_QUICK if args.quick else _REG_GRID_FULL

    # ── 4. Classifier — is this location dangerous? ───────────────────────────
    clf_base = build_pipeline(
        RandomForestClassifier(class_weight="balanced", n_jobs=-1, random_state=42)
    )
    clf_pipeline, clf_metrics = tune_classifier(
        clf_base, clf_grid,
        X_train, train_df["is_dangerous"],
        X_test,  test_df["is_dangerous"],
        cv,
    )

    # ── 5. Regressor — how severe is the material damage? ────────────────────
    # Gamma loss requires strictly positive targets; drop rows where damage is
    # missing or zero. The model is trained directly on damage_czk so its
    # output is already in CZK — no log/expm1 inversion bias.
    reg_train = train_df[train_df["damage_czk"].notna() & (train_df["damage_czk"] > 0)]
    reg_test  = test_df[test_df["damage_czk"].notna()  & (test_df["damage_czk"]  > 0)]
    y_reg_train = reg_train["damage_czk"].astype(float)
    y_reg_test  = reg_test["damage_czk"].astype(float)
    log.info("Regressor data: %d train / %d test rows (positive damage only)",
             len(reg_train), len(reg_test))

    reg_base = build_pipeline(
        HistGradientBoostingRegressor(loss="gamma", random_state=42)
    )
    reg_pipeline, reg_metrics = tune_regressor(
        reg_base, reg_grid,
        reg_train[ALL_FEATURES], y_reg_train,
        reg_test[ALL_FEATURES],  y_reg_test,
        cv,
    )

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
        "cv_folds":           args.cv_folds,
        "quick_mode":         args.quick,
        "features":           ALL_FEATURES,
        "classifier":         clf_metrics,
        "regressor":          reg_metrics,
    }
    meta_path.write_text(json.dumps(metadata, indent=2, default=str))

    print(f"\n✓ Models saved to {args.output_dir.resolve()}")
    print(f"  classifier.joblib  ({clf_path.stat().st_size // 1024} KB)")
    print(f"  regressor.joblib   ({reg_path.stat().st_size // 1024} KB)")
    print(f"  metadata.json")


if __name__ == "__main__":
    main()
