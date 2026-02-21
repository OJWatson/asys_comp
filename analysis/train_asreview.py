#!/usr/bin/env python3
"""Train a screening prioritization model with holdout evaluation and ranking metrics.

Dataset assumptions (robust to casing/whitespace/underscore differences):
- Text fields: Title, Abstract
- Label field: Final decision

Decision mapping:
- include: i/I/include/included/1 -> 1
- exclude: e/E/exclude/excluded/0 -> 0
"""

from __future__ import annotations

import argparse
import json
import math
import re
import warnings
from pathlib import Path
from typing import Dict, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    f1_score,
    ndcg_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline

INCLUDE_TOKENS = {"1", "i", "include", "included"}
EXCLUDE_TOKENS = {"0", "e", "exclude", "excluded"}


def normalize_col_name(name: object) -> str:
    s = str(name).strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"\s+", " ", s)
    return s


def find_column(columns: Sequence[str], candidates: Sequence[str], *, required: bool = True) -> Optional[str]:
    norm_to_orig: Dict[str, str] = {}
    for col in columns:
        norm_to_orig.setdefault(normalize_col_name(col), col)

    norm_candidates = [normalize_col_name(c) for c in candidates]

    for cand in norm_candidates:
        if cand in norm_to_orig:
            return norm_to_orig[cand]

    for cand in norm_candidates:
        cand_alt = cand[:-1] if cand.endswith("s") else f"{cand}s"
        if cand_alt in norm_to_orig:
            return norm_to_orig[cand_alt]

    scored = []
    for norm, orig in norm_to_orig.items():
        for cand in norm_candidates:
            if cand in norm or norm in cand:
                scored.append((abs(len(norm) - len(cand)), len(norm), orig))
                break
    if scored:
        scored.sort()
        return scored[0][2]

    if required:
        raise ValueError(
            f"Could not find required column. Candidates={list(candidates)}; "
            f"available={list(columns)}"
        )
    return None


def normalize_decision(value: object) -> float:
    if pd.isna(value):
        return np.nan

    if isinstance(value, (int, np.integer)):
        return float(value) if value in (0, 1) else np.nan

    if isinstance(value, float):
        if math.isnan(value):
            return np.nan
        if value in (0.0, 1.0):
            return float(int(value))

    s = str(value).strip().lower()
    if s == "":
        return np.nan

    if s in INCLUDE_TOKENS:
        return 1.0
    if s in EXCLUDE_TOKENS:
        return 0.0

    compact = re.sub(r"[^a-z0-9]+", "", s)
    if compact in INCLUDE_TOKENS:
        return 1.0
    if compact in EXCLUDE_TOKENS:
        return 0.0

    return np.nan


def precision_recall_at_k(y_true: np.ndarray, scores: np.ndarray, k: int) -> Tuple[float, float]:
    if k <= 0:
        return float("nan"), float("nan")

    k = min(k, len(y_true))
    idx = np.argsort(-scores)
    top_k = y_true[idx][:k]
    n_pos = int(y_true.sum())

    precision = float(top_k.mean()) if k > 0 else float("nan")
    recall = float(top_k.sum() / n_pos) if n_pos > 0 else float("nan")
    return precision, recall


def r_precision(y_true: np.ndarray, scores: np.ndarray) -> float:
    n_pos = int(y_true.sum())
    if n_pos <= 0:
        return float("nan")
    p_at_r, _ = precision_recall_at_k(y_true, scores, n_pos)
    return p_at_r


def wss_at_recall(y_true: np.ndarray, scores: np.ndarray, target_recall: float = 0.95) -> float:
    n = len(y_true)
    n_pos = int(y_true.sum())
    if n == 0 or n_pos == 0:
        return float("nan")

    idx = np.argsort(-scores)
    recalls = np.cumsum(y_true[idx]) / n_pos

    reached = np.where(recalls >= target_recall)[0]
    if len(reached) == 0:
        return float("nan")

    k = int(reached[0] + 1)
    return float(target_recall - (k / n))


def robust_split(
    idx_all: np.ndarray,
    y: np.ndarray,
    test_size: float,
    random_state: int,
) -> Tuple[np.ndarray, np.ndarray]:
    n = len(y)
    n_classes = len(np.unique(y))
    n_test = int(math.ceil(n * test_size)) if isinstance(test_size, float) else int(test_size)
    n_train = n - n_test
    min_class_n = int(min(np.bincount(y)))

    use_stratify = n_test >= n_classes and n_train >= n_classes and min_class_n >= 2
    stratify = y if use_stratify else None

    try:
        return train_test_split(
            idx_all,
            test_size=test_size,
            random_state=random_state,
            stratify=stratify,
        )
    except ValueError as e:
        warnings.warn(f"Falling back to non-stratified split due to split constraints: {e}")
        return train_test_split(
            idx_all,
            test_size=test_size,
            random_state=random_state,
            stratify=None,
        )


def build_model(min_df: int = 2, random_state: int = 42) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
                TfidfVectorizer(
                    lowercase=True,
                    strip_accents="unicode",
                    ngram_range=(1, 2),
                    min_df=min_df,
                    max_df=0.95,
                ),
            ),
            (
                "clf",
                LogisticRegression(
                    max_iter=2000,
                    class_weight="balanced",
                    solver="liblinear",
                    random_state=random_state,
                ),
            ),
        ]
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Train and evaluate screening model on an Excel dataset.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "screening_input.xlsx",
        help="Path to input spreadsheet (.xlsx)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs",
        help="Directory for outputs",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(args.input)
    original_n = len(df)

    title_col = find_column(df.columns, ["Title", "Titles"])
    abstract_col = find_column(df.columns, ["Abstract", "Abstracts"])
    label_col = find_column(df.columns, ["Final decision", "Final_decision", "Decision"])

    title = df[title_col].fillna("").astype(str).str.strip()
    abstract = df[abstract_col].fillna("").astype(str).str.strip()
    text = (title + " " + abstract).str.strip()

    y = df[label_col].map(normalize_decision)

    prepared = df.copy()
    prepared["_text"] = text
    prepared["_label"] = y

    valid_mask = prepared["_text"].str.len().gt(0) & prepared["_label"].notna()
    clean = prepared.loc[valid_mask].copy()

    dropped = int(original_n - len(clean))
    if len(clean) < 10:
        raise ValueError(
            f"Too few usable rows after cleaning ({len(clean)} of {original_n}). "
            "Check input columns/labels."
        )

    X = clean["_text"].values
    y = clean["_label"].astype(int).values

    values, counts = np.unique(y, return_counts=True)
    class_counts = {int(v): int(c) for v, c in zip(values, counts)}
    if len(class_counts) < 2:
        raise ValueError(f"Need both classes present after mapping. Got class_counts={class_counts}")

    idx_all = np.arange(len(clean))
    train_idx, test_idx = robust_split(
        idx_all=idx_all,
        y=y,
        test_size=args.test_size,
        random_state=args.random_state,
    )

    X_train, X_test = X[train_idx], X[test_idx]
    y_train, y_test = y[train_idx], y[test_idx]

    model = build_model(min_df=2, random_state=args.random_state)
    try:
        model.fit(X_train, y_train)
    except ValueError as e:
        msg = str(e).lower()
        if "empty vocabulary" in msg or "no terms remain" in msg:
            warnings.warn(f"Retrying with min_df=1 after vectorizer pruning issue: {e}")
            model = build_model(min_df=1, random_state=args.random_state)
            model.fit(X_train, y_train)
        else:
            raise

    y_score = model.predict_proba(X_test)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)

    n_test_pos = int(y_test.sum())
    metrics = {
        "n_total_rows": int(original_n),
        "n_usable_rows": int(len(clean)),
        "n_dropped_rows": dropped,
        "train_size": int(len(train_idx)),
        "test_size": int(len(test_idx)),
        "class_counts_usable": class_counts,
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "average_precision": float(average_precision_score(y_test, y_score)) if n_test_pos > 0 else float("nan"),
        "roc_auc": float(roc_auc_score(y_test, y_score)) if len(np.unique(y_test)) > 1 else float("nan"),
        "r_precision": float(r_precision(y_test, y_score)),
        "wss@95": float(wss_at_recall(y_test, y_score, target_recall=0.95)),
        "ndcg": float(ndcg_score(y_test.reshape(1, -1), y_score.reshape(1, -1))) if n_test_pos > 0 else float("nan"),
    }

    for k in (10, 20, 50):
        p_at_k, r_at_k = precision_recall_at_k(y_test, y_score, k)
        metrics[f"precision@{k}"] = float(p_at_k)
        metrics[f"recall@{k}"] = float(r_at_k)

    test_rows = clean.iloc[test_idx].copy()
    test_rows["score_include"] = y_score
    test_rows["pred_label"] = y_pred
    test_rows["true_label"] = y_test
    ranking = test_rows.sort_values("score_include", ascending=False).reset_index(drop=False)
    ranking["rank"] = np.arange(1, len(ranking) + 1)

    metrics_path = args.output_dir / "metrics.json"
    ranking_path = args.output_dir / "ranking_test.csv"
    model_path = args.output_dir / "model.joblib"
    config_path = args.output_dir / "run_config.json"

    with metrics_path.open("w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    ranking.to_csv(ranking_path, index=False)
    joblib.dump(model, model_path)

    run_config = {
        "input": str(args.input.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "columns_detected": {
            "title": title_col,
            "abstract": abstract_col,
            "label": label_col,
        },
        "label_mapping": {
            "include_tokens": ["i", "I", "include", "included", "1"],
            "exclude_tokens": ["e", "E", "exclude", "excluded", "0"],
        },
        "test_size": args.test_size,
        "random_state": args.random_state,
    }
    with config_path.open("w", encoding="utf-8") as f:
        json.dump(run_config, f, indent=2)

    print("Training complete.")
    print(f"Input: {args.input}")
    print(f"Output dir: {args.output_dir}")
    print(f"Detected columns: title='{title_col}', abstract='{abstract_col}', label='{label_col}'")
    print("Key metrics:")
    for key in [
        "accuracy",
        "precision",
        "recall",
        "f1",
        "average_precision",
        "roc_auc",
        "r_precision",
        "wss@95",
        "ndcg",
    ]:
        print(f"  {key}: {metrics[key]:.4f}")

    print("Artifacts:")
    print(f"  {metrics_path}")
    print(f"  {ranking_path}")
    print(f"  {model_path}")
    print(f"  {config_path}")


if __name__ == "__main__":
    main()
