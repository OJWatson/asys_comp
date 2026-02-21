#!/usr/bin/env python3
"""Improved ASReview-style screening training pipeline.

Key upgrades over baseline:
- Multiple model/feature variants (incl. stronger calibrated linear SVM + word+char TF-IDF)
- Better imbalance handling via model choice + class weighting
- Validation-based threshold tuning for recall targets (0.90 and 0.95)
- Richer ranking-centric evaluation (PR summary, recall@k, WSS, workload-at-recall)
- Deterministic seeds + reproducible run metadata
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
import warnings
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.feature_extraction.text import TfidfVectorizer as TFIDF
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    f1_score,
    ndcg_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

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
            f"Could not find required column. Candidates={list(candidates)}; available={list(columns)}"
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


def screening_fraction_for_recall(y_true: np.ndarray, scores: np.ndarray, target_recall: float) -> float:
    n = len(y_true)
    n_pos = int(y_true.sum())
    if n == 0 or n_pos == 0:
        return float("nan")

    idx = np.argsort(-scores)
    recalls = np.cumsum(y_true[idx]) / n_pos
    reached = np.where(recalls >= target_recall)[0]
    if len(reached) == 0:
        return float("nan")
    return float((reached[0] + 1) / n)


def precision_at_recall_target(y_true: np.ndarray, scores: np.ndarray, target_recall: float) -> float:
    precision, recall, _ = precision_recall_curve(y_true, scores)
    mask = recall >= target_recall
    if not np.any(mask):
        return float("nan")
    return float(np.max(precision[mask]))


def max_f1_from_scores(y_true: np.ndarray, scores: np.ndarray) -> float:
    precision, recall, _ = precision_recall_curve(y_true, scores)
    denom = precision + recall
    f1 = np.where(denom > 0, 2 * precision * recall / denom, 0.0)
    return float(np.max(f1)) if len(f1) else float("nan")


def choose_threshold_for_recall(y_true: np.ndarray, scores: np.ndarray, target_recall: float) -> float:
    unique_thresholds = sorted(set(float(s) for s in scores), reverse=True)
    chosen = None
    for t in unique_thresholds:
        pred = (scores >= t).astype(int)
        rec = recall_score(y_true, pred, zero_division=0)
        if rec >= target_recall:
            chosen = t
            break

    if chosen is None:
        chosen = min(unique_thresholds) - 1e-12
    return float(chosen)


def build_model(model_name: str, random_state: int) -> Pipeline:
    if model_name == "lr_word_tfidf_balanced":
        return Pipeline(
            steps=[
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=1,
                        max_df=0.98,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=5000,
                        class_weight="balanced",
                        solver="liblinear",
                        C=2.0,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    if model_name == "cnb_word_tfidf":
        return Pipeline(
            steps=[
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=1,
                        max_df=0.98,
                        sublinear_tf=True,
                    ),
                ),
                ("clf", ComplementNB(alpha=0.5, norm=False)),
            ]
        )

    if model_name == "calibrated_svm_word_char":
        features = FeatureUnion(
            transformer_list=[
                (
                    "word",
                    TFIDF(
                        analyzer="word",
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=1,
                        max_df=0.98,
                        sublinear_tf=True,
                    ),
                ),
                (
                    "char",
                    TFIDF(
                        analyzer="char_wb",
                        lowercase=True,
                        ngram_range=(3, 5),
                        min_df=1,
                        sublinear_tf=True,
                    ),
                ),
            ]
        )
        base = LinearSVC(C=1.0, class_weight="balanced", random_state=random_state)
        calibrated = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=3)
        return Pipeline(steps=[("features", features), ("clf", calibrated)])

    raise ValueError(f"Unknown model_name={model_name}")


def evaluate_ranking_metrics(
    y_true: np.ndarray,
    scores: np.ndarray,
    *,
    default_threshold: float,
    tuned_thresholds: Dict[str, float],
) -> Dict[str, float]:
    y_pred_default = (scores >= default_threshold).astype(int)

    n_test_pos = int(y_true.sum())
    metrics: Dict[str, float] = {
        "accuracy@0.5": float(accuracy_score(y_true, y_pred_default)),
        "precision@0.5": float(precision_score(y_true, y_pred_default, zero_division=0)),
        "recall@0.5": float(recall_score(y_true, y_pred_default, zero_division=0)),
        "f1@0.5": float(f1_score(y_true, y_pred_default, zero_division=0)),
        "average_precision": float(average_precision_score(y_true, scores)) if n_test_pos > 0 else float("nan"),
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) > 1 else float("nan"),
        "r_precision": float(r_precision(y_true, scores)),
        "wss@90": float(wss_at_recall(y_true, scores, target_recall=0.90)),
        "wss@95": float(wss_at_recall(y_true, scores, target_recall=0.95)),
        "ndcg": float(ndcg_score(y_true.reshape(1, -1), scores.reshape(1, -1))) if n_test_pos > 0 else float("nan"),
        "brier": float(brier_score_loss(y_true, scores)),
        "max_f1_over_thresholds": float(max_f1_from_scores(y_true, scores)),
        "precision_at_recall_0.90": float(precision_at_recall_target(y_true, scores, 0.90)),
        "precision_at_recall_0.95": float(precision_at_recall_target(y_true, scores, 0.95)),
        "screening_fraction_at_recall_0.90": float(screening_fraction_for_recall(y_true, scores, 0.90)),
        "screening_fraction_at_recall_0.95": float(screening_fraction_for_recall(y_true, scores, 0.95)),
    }

    for label, t in tuned_thresholds.items():
        y_pred_t = (scores >= t).astype(int)
        metrics[f"precision@{label}"] = float(precision_score(y_true, y_pred_t, zero_division=0))
        metrics[f"recall@{label}"] = float(recall_score(y_true, y_pred_t, zero_division=0))
        metrics[f"f1@{label}"] = float(f1_score(y_true, y_pred_t, zero_division=0))
        metrics[f"positive_rate@{label}"] = float(np.mean(y_pred_t))

    for k in (10, 20, 30, 50):
        p_at_k, r_at_k = precision_recall_at_k(y_true, scores, k)
        metrics[f"precision@{k}"] = float(p_at_k)
        metrics[f"recall@{k}"] = float(r_at_k)

    rank_idx = np.argsort(-scores)
    ranked_true = y_true[rank_idx]
    positives_at = np.where(ranked_true == 1)[0]
    metrics["first_relevant_rank"] = float(int(positives_at[0] + 1) if len(positives_at) else np.nan)
    metrics["last_relevant_rank"] = float(int(positives_at[-1] + 1) if len(positives_at) else np.nan)

    return metrics


def build_markdown_table(rows: List[Dict[str, object]], columns: List[str]) -> str:
    header = "| " + " | ".join(columns) + " |"
    sep = "|" + "|".join(["---"] * len(columns)) + "|"
    body = []
    for row in rows:
        values = []
        for col in columns:
            v = row.get(col, "")
            if isinstance(v, float):
                if np.isnan(v):
                    values.append("nan")
                else:
                    values.append(f"{v:.4f}")
            else:
                values.append(str(v))
        body.append("| " + " | ".join(values) + " |")
    return "\n".join([header, sep] + body)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train improved ASReview-style ranking/classification models.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "screening_input.xlsx",
        help="Path to input spreadsheet (.xlsx)",
    )
    parser.add_argument(
        "--baseline-metrics",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "metrics.json",
        help="Path to baseline metrics JSON for comparison",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "improved",
        help="Directory for improved outputs",
    )
    parser.add_argument("--test-size", type=float, default=0.2)
    parser.add_argument("--val-size", type=float, default=0.2, help="Validation fraction from train+val pool")
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    random.seed(args.random_state)
    np.random.seed(args.random_state)

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
            f"Too few usable rows after cleaning ({len(clean)} of {original_n}). Check input columns/labels."
        )

    X = clean["_text"].values
    y = clean["_label"].astype(int).values

    values, counts = np.unique(y, return_counts=True)
    class_counts = {int(v): int(c) for v, c in zip(values, counts)}
    if len(class_counts) < 2:
        raise ValueError(f"Need both classes present after mapping. Got class_counts={class_counts}")

    idx_all = np.arange(len(clean))
    train_val_idx, test_idx = robust_split(
        idx_all=idx_all,
        y=y,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    y_train_val = y[train_val_idx]

    train_inner, val_inner = robust_split(
        idx_all=np.arange(len(train_val_idx)),
        y=y_train_val,
        test_size=args.val_size,
        random_state=args.random_state,
    )
    train_idx = train_val_idx[train_inner]
    val_idx = train_val_idx[val_inner]

    X_train, y_train = X[train_idx], y[train_idx]
    X_val, y_val = X[val_idx], y[val_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    model_names = [
        "lr_word_tfidf_balanced",
        "cnb_word_tfidf",
        "calibrated_svm_word_char",
    ]

    all_metrics: Dict[str, Dict[str, object]] = {}
    leaderboard_rows: List[Dict[str, object]] = []
    trained_models: Dict[str, Pipeline] = {}

    for model_name in model_names:
        model = build_model(model_name, random_state=args.random_state)
        model.fit(X_train, y_train)

        val_scores = model.predict_proba(X_val)[:, 1]
        test_scores = model.predict_proba(X_test)[:, 1]

        tuned_thresholds = {
            "thr_recall_0.90": choose_threshold_for_recall(y_val, val_scores, 0.90),
            "thr_recall_0.95": choose_threshold_for_recall(y_val, val_scores, 0.95),
        }

        model_metrics = evaluate_ranking_metrics(
            y_true=y_test,
            scores=test_scores,
            default_threshold=0.5,
            tuned_thresholds=tuned_thresholds,
        )

        model_metrics["threshold_recall_0.90"] = float(tuned_thresholds["thr_recall_0.90"])
        model_metrics["threshold_recall_0.95"] = float(tuned_thresholds["thr_recall_0.95"])
        model_metrics["n_train"] = int(len(train_idx))
        model_metrics["n_val"] = int(len(val_idx))
        model_metrics["n_test"] = int(len(test_idx))

        ranking = clean.iloc[test_idx].copy()
        ranking["score_include"] = test_scores
        ranking["pred_label@0.5"] = (test_scores >= 0.5).astype(int)
        ranking["true_label"] = y_test
        ranking = ranking.sort_values("score_include", ascending=False).reset_index(drop=False)
        ranking["rank"] = np.arange(1, len(ranking) + 1)

        ranking_path = args.output_dir / f"ranking_test_{model_name}.csv"
        metrics_path = args.output_dir / f"metrics_{model_name}.json"
        ranking.to_csv(ranking_path, index=False)
        with metrics_path.open("w", encoding="utf-8") as f:
            json.dump(model_metrics, f, indent=2)

        all_metrics[model_name] = model_metrics
        trained_models[model_name] = model

        leaderboard_rows.append(
            {
                "model": model_name,
                "average_precision": model_metrics["average_precision"],
                "wss@95": model_metrics["wss@95"],
                "recall@20": model_metrics["recall@20"],
                "recall@50": model_metrics["recall@50"],
                "precision@10": model_metrics["precision@10"],
                "recall@0.5": model_metrics["recall@0.5"],
                "precision@0.5": model_metrics["precision@0.5"],
            }
        )

    def _score_key(row: Dict[str, object]) -> Tuple[float, float, float, float]:
        ap = float(row["average_precision"])
        wss95 = float(row["wss@95"])
        r20 = float(row["recall@20"])
        r50 = float(row["recall@50"])
        return (
            -1e9 if np.isnan(ap) else ap,
            -1e9 if np.isnan(wss95) else wss95,
            -1e9 if np.isnan(r20) else r20,
            -1e9 if np.isnan(r50) else r50,
        )

    best_row = max(leaderboard_rows, key=_score_key)
    best_model_name = str(best_row["model"])
    best_model = trained_models[best_model_name]
    best_metrics = all_metrics[best_model_name]

    summary_df = pd.DataFrame(leaderboard_rows).sort_values(
        by=["average_precision", "wss@95", "recall@20"],
        ascending=False,
    )
    summary_csv = args.output_dir / "model_summary.csv"
    summary_df.to_csv(summary_csv, index=False)

    best_model_path = args.output_dir / "best_model.joblib"
    joblib.dump(best_model, best_model_path)

    best_metrics_path = args.output_dir / "metrics_best.json"
    with best_metrics_path.open("w", encoding="utf-8") as f:
        json.dump({"best_model": best_model_name, **best_metrics}, f, indent=2)

    all_metrics_path = args.output_dir / "metrics_by_model.json"
    with all_metrics_path.open("w", encoding="utf-8") as f:
        json.dump(all_metrics, f, indent=2)

    run_config = {
        "input": str(args.input.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "columns_detected": {"title": title_col, "abstract": abstract_col, "label": label_col},
        "label_mapping": {
            "include_tokens": ["i", "I", "include", "included", "1"],
            "exclude_tokens": ["e", "E", "exclude", "excluded", "0"],
        },
        "split": {
            "test_size": args.test_size,
            "val_size": args.val_size,
            "n_total_rows": int(original_n),
            "n_usable_rows": int(len(clean)),
            "n_dropped_rows": int(dropped),
            "n_train": int(len(train_idx)),
            "n_val": int(len(val_idx)),
            "n_test": int(len(test_idx)),
            "class_counts_usable": class_counts,
            "class_counts_train": {int(k): int(v) for k, v in zip(*np.unique(y_train, return_counts=True))},
            "class_counts_val": {int(k): int(v) for k, v in zip(*np.unique(y_val, return_counts=True))},
            "class_counts_test": {int(k): int(v) for k, v in zip(*np.unique(y_test, return_counts=True))},
        },
        "random_state": args.random_state,
        "models_tested": model_names,
        "selection_rule": "max(average_precision, then wss@95, then recall@20, then recall@50)",
        "best_model": best_model_name,
    }
    run_config_path = args.output_dir / "run_config_improved.json"
    with run_config_path.open("w", encoding="utf-8") as f:
        json.dump(run_config, f, indent=2)

    comparison_rows: List[Dict[str, object]] = []
    baseline_metrics = None
    if args.baseline_metrics.exists():
        with args.baseline_metrics.open("r", encoding="utf-8") as f:
            baseline_metrics = json.load(f)

    if baseline_metrics is not None:
        compare_keys = [
            "accuracy",
            "precision",
            "recall",
            "f1",
            "average_precision",
            "roc_auc",
            "r_precision",
            "wss@95",
            "precision@10",
            "recall@10",
            "precision@20",
            "recall@20",
            "precision@50",
            "recall@50",
        ]

        key_map_improved = {
            "accuracy": "accuracy@0.5",
            "precision": "precision@0.5",
            "recall": "recall@0.5",
            "f1": "f1@0.5",
        }

        for key in compare_keys:
            improved_key = key_map_improved.get(key, key)
            b_val = baseline_metrics.get(key, float("nan"))
            i_val = best_metrics.get(improved_key, float("nan"))
            b = float(b_val) if b_val is not None else float("nan")
            i = float(i_val) if i_val is not None else float("nan")
            delta = float(i - b) if not (np.isnan(i) or np.isnan(b)) else float("nan")
            comparison_rows.append(
                {
                    "metric": key,
                    "baseline": b,
                    "improved_best": i,
                    "delta": delta,
                }
            )

        comparison_df = pd.DataFrame(comparison_rows)
        comparison_csv = args.output_dir / "comparison_baseline_vs_improved.csv"
        comparison_df.to_csv(comparison_csv, index=False)

        comparison_md_rows = [
            {
                "metric": row["metric"],
                "baseline": row["baseline"],
                "improved_best": row["improved_best"],
                "delta": row["delta"],
            }
            for row in comparison_rows
        ]
        comparison_md = build_markdown_table(
            comparison_md_rows,
            columns=["metric", "baseline", "improved_best", "delta"],
        )
        (args.output_dir / "comparison_table.md").write_text(comparison_md + "\n", encoding="utf-8")

    leaderboard_md = build_markdown_table(
        leaderboard_rows,
        columns=[
            "model",
            "average_precision",
            "wss@95",
            "recall@20",
            "recall@50",
            "precision@10",
            "recall@0.5",
            "precision@0.5",
        ],
    )
    (args.output_dir / "leaderboard.md").write_text(leaderboard_md + "\n", encoding="utf-8")

    print("Improved training complete.")
    print(f"Best model: {best_model_name}")
    print(f"Output dir: {args.output_dir}")
    print("Key best metrics:")
    for key in [
        "average_precision",
        "roc_auc",
        "wss@95",
        "precision@10",
        "recall@20",
        "recall@50",
        "recall@0.5",
        "precision@0.5",
        "threshold_recall_0.90",
        "threshold_recall_0.95",
        "precision@thr_recall_0.90",
        "recall@thr_recall_0.90",
        "precision@thr_recall_0.95",
        "recall@thr_recall_0.95",
    ]:
        if key in best_metrics:
            print(f"  {key}: {best_metrics[key]:.4f}")

    print("Artifacts:")
    print(f"  {summary_csv}")
    print(f"  {best_metrics_path}")
    print(f"  {all_metrics_path}")
    print(f"  {best_model_path}")
    print(f"  {run_config_path}")


if __name__ == "__main__":
    main()
