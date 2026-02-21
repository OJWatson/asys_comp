#!/usr/bin/env python3
"""Execute recommended ASReview next steps from ASREVIEW_IMPROVEMENT_REPORT.md.

Implements end-to-end:
1) Active-learning simulation loop with query/update iterations + stopping-policy evaluation.
2) Nested CV + seed sweeps for recall-threshold tuning stability.
3) Leakage-safe production ranking export.
4) Target-recall stopping diagnostics (statistical + SAFE-like surrogate checks).
5) Prior/seed strategy experiments (known relevant + known irrelevant templates).
"""

from __future__ import annotations

import argparse
import json
import math
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.stats import beta
from sklearn.calibration import CalibratedClassifierCV
from sklearn.feature_extraction.text import TfidfVectorizer as TFIDF
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import StratifiedKFold
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.svm import LinearSVC

INCLUDE_TOKENS = {"1", "i", "include", "included"}
EXCLUDE_TOKENS = {"0", "e", "exclude", "excluded"}


@dataclass(frozen=True)
class SeedStrategy:
    name: str
    n_pos: int
    n_neg: int
    random_extra: int = 0


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


def build_model(random_state: int, calibration_cv: int = 3) -> Pipeline:
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
    calibrated = CalibratedClassifierCV(estimator=base, method="sigmoid", cv=calibration_cv)
    return Pipeline(steps=[("features", features), ("clf", calibrated)])


def build_active_learning_model(random_state: int) -> Pipeline:
    return Pipeline(
        steps=[
            (
                "tfidf",
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


def prepare_data(input_path: Path) -> Tuple[pd.DataFrame, np.ndarray, np.ndarray, Dict[str, str]]:
    df = pd.read_excel(input_path)

    title_col = find_column(df.columns, ["Title", "Titles"])
    abstract_col = find_column(df.columns, ["Abstract", "Abstracts"])
    label_col = find_column(df.columns, ["Final decision", "Final_decision", "Decision"])

    title = df[title_col].fillna("").astype(str).str.strip()
    abstract = df[abstract_col].fillna("").astype(str).str.strip()
    text = (title + " " + abstract).str.strip()
    y = df[label_col].map(normalize_decision)

    prepared = df.copy()
    prepared["_title"] = title
    prepared["_abstract"] = abstract
    prepared["_text"] = text
    prepared["_label"] = y

    valid_mask = prepared["_text"].str.len().gt(0) & prepared["_label"].notna()
    clean = prepared.loc[valid_mask].copy().reset_index(drop=True)
    clean["_label"] = clean["_label"].astype(int)

    X = clean["_text"].values
    y_arr = clean["_label"].values

    return clean, X, y_arr, {"title": title_col, "abstract": abstract_col, "label": label_col}


def expected_remaining_upper_bound(
    recent_labels: np.ndarray,
    n_unscreened: int,
    confidence: float = 0.95,
) -> float:
    # Jeffreys prior Beta(0.5, 0.5); upper credible bound on relevance prevalence.
    s = int(recent_labels.sum())
    n = int(len(recent_labels))
    if n == 0:
        return float(n_unscreened)
    p_upper = float(beta.ppf(confidence, s + 0.5, (n - s) + 0.5))
    return float(p_upper * n_unscreened)


def trailing_nonrelevant_count(screened_labels: List[int]) -> int:
    c = 0
    for v in reversed(screened_labels):
        if v == 0:
            c += 1
        else:
            break
    return c


def pick_initial_seeds(
    y: np.ndarray,
    strategy: SeedStrategy,
    rng: np.random.Generator,
) -> List[int]:
    pos_idx = np.where(y == 1)[0]
    neg_idx = np.where(y == 0)[0]

    if len(pos_idx) < strategy.n_pos:
        raise ValueError(f"Strategy {strategy.name}: insufficient positives for n_pos={strategy.n_pos}")
    if len(neg_idx) < strategy.n_neg:
        raise ValueError(f"Strategy {strategy.name}: insufficient negatives for n_neg={strategy.n_neg}")

    chosen_pos = rng.choice(pos_idx, size=strategy.n_pos, replace=False).tolist() if strategy.n_pos > 0 else []
    chosen_neg = rng.choice(neg_idx, size=strategy.n_neg, replace=False).tolist() if strategy.n_neg > 0 else []

    selected = set(chosen_pos + chosen_neg)
    if strategy.random_extra > 0:
        remaining = np.array(sorted(set(np.arange(len(y))) - selected))
        extra = rng.choice(remaining, size=min(strategy.random_extra, len(remaining)), replace=False).tolist()
        selected.update(extra)

    return sorted(selected)


def summarize_policy(
    trace_df: pd.DataFrame,
    policy_name: str,
    trigger_mask: pd.Series,
    total_pos: int,
) -> Dict[str, float]:
    if trigger_mask.any():
        row = trace_df.loc[trigger_mask].iloc[0]
    else:
        row = trace_df.iloc[-1]

    recall_val = float(row["recall"])
    screened_fraction = float(row["screened_fraction"])
    docs_screened = int(row["docs_screened"])
    wss95 = 0.95 - screened_fraction if recall_val >= 0.95 else float("nan")
    return {
        "policy": policy_name,
        "docs_screened": docs_screened,
        "screened_fraction": screened_fraction,
        "recall": recall_val,
        "positives_found": int(round(recall_val * total_pos)),
        "wss@95_if_reached": float(wss95),
    }


def run_active_learning_simulation(
    X: np.ndarray,
    y: np.ndarray,
    strategy: SeedStrategy,
    random_state: int,
    *,
    batch_size: int = 5,
    safe_window: int = 50,
    safe_upper_remaining_threshold: float = 1.0,
    no_hit_window: int = 50,
) -> Tuple[pd.DataFrame, Dict[str, float], pd.DataFrame]:
    rng = np.random.default_rng(random_state)
    n = len(y)
    total_pos = int(y.sum())

    screened: List[int] = pick_initial_seeds(y, strategy, rng)
    initial_seed_count = len(screened)
    screened_set = set(screened)
    screened_labels: List[int] = [int(y[i]) for i in screened]

    trace_rows: List[Dict[str, float]] = []

    while len(screened) < n:
        train_idx = np.array(sorted(screened_set))
        unlabeled_idx = np.array(sorted(set(range(n)) - screened_set))

        if len(np.unique(y[train_idx])) < 2:
            # Safety fallback: if no class diversity, random query.
            query_idx = rng.choice(unlabeled_idx, size=min(batch_size, len(unlabeled_idx)), replace=False)
            query_scores = np.full(len(query_idx), np.nan)
        else:
            model = build_active_learning_model(random_state=random_state)
            model.fit(X[train_idx], y[train_idx])
            unlabeled_scores = model.predict_proba(X[unlabeled_idx])[:, 1]
            order = np.argsort(-unlabeled_scores)
            take = order[: min(batch_size, len(order))]
            query_idx = unlabeled_idx[take]
            query_scores = unlabeled_scores[take]

        for i, q in enumerate(query_idx):
            screened.append(int(q))
            screened_set.add(int(q))
            screened_labels.append(int(y[q]))

            docs_screened = len(screened)
            positives_found = int(sum(screened_labels))
            recall_now = positives_found / total_pos if total_pos > 0 else float("nan")
            screened_fraction = docs_screened / n

            recent = np.array(screened_labels[-safe_window:], dtype=int)
            trailing_nonrel = trailing_nonrelevant_count(screened_labels)
            n_unscreened = n - docs_screened
            expected_rem_upper = expected_remaining_upper_bound(recent, n_unscreened=n_unscreened, confidence=0.95)

            trace_rows.append(
                {
                    "strategy": strategy.name,
                    "seed": random_state,
                    "step": docs_screened - initial_seed_count,
                    "docs_screened": docs_screened,
                    "screened_fraction": screened_fraction,
                    "positives_found": positives_found,
                    "recall": recall_now,
                    "latest_label": int(y[q]),
                    "latest_score": float(query_scores[i]) if i < len(query_scores) and not np.isnan(query_scores[i]) else np.nan,
                    "trailing_nonrelevant": trailing_nonrel,
                    "expected_remaining_upper_95": expected_rem_upper,
                    "safe_like_trigger": int(expected_rem_upper <= safe_upper_remaining_threshold),
                    "no_hit_window_trigger": int(trailing_nonrel >= no_hit_window),
                    "target_recall_90_trigger": int(recall_now >= 0.90),
                    "target_recall_95_trigger": int(recall_now >= 0.95),
                }
            )

    trace_df = pd.DataFrame(trace_rows)
    if trace_df.empty:
        raise RuntimeError("Active-learning trace is empty; simulation failed.")

    policy_rows = []
    policy_rows.append(
        summarize_policy(trace_df, "oracle_target_recall_95", trace_df["target_recall_95_trigger"] == 1, total_pos)
    )
    policy_rows.append(
        summarize_policy(trace_df, "oracle_target_recall_90", trace_df["target_recall_90_trigger"] == 1, total_pos)
    )
    policy_rows.append(
        summarize_policy(trace_df, "no_hit_window_50", trace_df["no_hit_window_trigger"] == 1, total_pos)
    )
    policy_rows.append(
        summarize_policy(trace_df, "safe_like_upper_remaining<=1", trace_df["safe_like_trigger"] == 1, total_pos)
    )
    policy_rows.append(
        summarize_policy(
            trace_df,
            "safe_like_and_no_hit_50",
            (trace_df["safe_like_trigger"] == 1) & (trace_df["no_hit_window_trigger"] == 1),
            total_pos,
        )
    )
    policy_df = pd.DataFrame(policy_rows)

    def first_docs_at_recall(target: float) -> int:
        met = trace_df.loc[trace_df["recall"] >= target, "docs_screened"]
        return int(met.iloc[0]) if len(met) else int(trace_df["docs_screened"].max())

    docs95 = first_docs_at_recall(0.95)
    docs90 = first_docs_at_recall(0.90)

    summary = {
        "strategy": strategy.name,
        "seed": random_state,
        "n_docs": n,
        "n_pos": total_pos,
        "initial_seed_count": initial_seed_count,
        "docs_to_recall_0.90": docs90,
        "docs_to_recall_0.95": docs95,
        "screen_frac_to_recall_0.90": docs90 / n,
        "screen_frac_to_recall_0.95": docs95 / n,
        "wss@90": 0.90 - (docs90 / n),
        "wss@95": 0.95 - (docs95 / n),
        "first_relevant_screened_rank": int(np.where(np.array(screened_labels) == 1)[0][0] + 1),
    }

    return trace_df, summary, policy_df


def run_active_learning_suite(
    X: np.ndarray,
    y: np.ndarray,
    output_dir: Path,
    seeds: Sequence[int],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strategies = [
        SeedStrategy(name="asreview_prior_1p1n", n_pos=1, n_neg=1),
        SeedStrategy(name="asreview_prior_2p10n", n_pos=2, n_neg=10),
        SeedStrategy(name="random_12_no_prior", n_pos=0, n_neg=0, random_extra=12),
    ]

    trace_parts: List[pd.DataFrame] = []
    summary_rows: List[Dict[str, float]] = []
    policy_parts: List[pd.DataFrame] = []

    for strategy in strategies:
        for seed in seeds:
            trace_df, summary, policy_df = run_active_learning_simulation(X, y, strategy, seed)
            trace_parts.append(trace_df)
            summary_rows.append(summary)
            policy_df = policy_df.copy()
            policy_df["strategy"] = strategy.name
            policy_df["seed"] = seed
            policy_parts.append(policy_df)

    traces = pd.concat(trace_parts, ignore_index=True)
    runs = pd.DataFrame(summary_rows)
    policy = pd.concat(policy_parts, ignore_index=True)

    strategy_summary = (
        runs.groupby("strategy", as_index=False)
        .agg(
            runs=("seed", "count"),
            docs_to_recall_0_90_mean=("docs_to_recall_0.90", "mean"),
            docs_to_recall_0_90_std=("docs_to_recall_0.90", "std"),
            docs_to_recall_0_95_mean=("docs_to_recall_0.95", "mean"),
            docs_to_recall_0_95_std=("docs_to_recall_0.95", "std"),
            wss90_mean=("wss@90", "mean"),
            wss95_mean=("wss@95", "mean"),
            first_relevant_rank_mean=("first_relevant_screened_rank", "mean"),
        )
        .sort_values("docs_to_recall_0_95_mean")
    )

    policy_summary = (
        policy.groupby(["strategy", "policy"], as_index=False)
        .agg(
            docs_screened_mean=("docs_screened", "mean"),
            docs_screened_std=("docs_screened", "std"),
            recall_mean=("recall", "mean"),
            screened_fraction_mean=("screened_fraction", "mean"),
            wss95_if_reached_mean=("wss@95_if_reached", "mean"),
        )
        .sort_values(["strategy", "docs_screened_mean"])
    )

    traces.to_csv(output_dir / "active_learning_traces.csv", index=False)
    runs.to_csv(output_dir / "active_learning_runs.csv", index=False)
    strategy_summary.to_csv(output_dir / "prior_strategy_summary.csv", index=False)
    policy.to_csv(output_dir / "stopping_policy_outcomes_by_run.csv", index=False)
    policy_summary.to_csv(output_dir / "stopping_policy_summary.csv", index=False)

    return traces, runs, strategy_summary, policy_summary


def run_nested_cv_threshold_seed_sweep(
    X: np.ndarray,
    y: np.ndarray,
    output_dir: Path,
    seeds: Sequence[int],
    *,
    outer_splits: int = 5,
    inner_splits: int = 3,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    detail_rows: List[Dict[str, float]] = []

    for seed in seeds:
        outer_cv = StratifiedKFold(n_splits=outer_splits, shuffle=True, random_state=seed)
        for fold_idx, (train_idx, test_idx) in enumerate(outer_cv.split(X, y), start=1):
            X_train, y_train = X[train_idx], y[train_idx]
            X_test, y_test = X[test_idx], y[test_idx]

            inner_cv = StratifiedKFold(n_splits=inner_splits, shuffle=True, random_state=seed + fold_idx * 13)
            thresholds_90 = []
            thresholds_95 = []

            for inner_train, inner_val in inner_cv.split(X_train, y_train):
                binc_inner = np.bincount(y_train[inner_train], minlength=2)
                calibration_cv_inner = max(2, min(3, int(np.min(binc_inner))))
                model_inner = build_model(random_state=seed + fold_idx, calibration_cv=calibration_cv_inner)
                model_inner.fit(X_train[inner_train], y_train[inner_train])
                val_scores = model_inner.predict_proba(X_train[inner_val])[:, 1]
                thresholds_90.append(choose_threshold_for_recall(y_train[inner_val], val_scores, 0.90))
                thresholds_95.append(choose_threshold_for_recall(y_train[inner_val], val_scores, 0.95))

            thr90 = float(np.median(thresholds_90))
            thr95 = float(np.median(thresholds_95))

            binc_outer = np.bincount(y_train, minlength=2)
            calibration_cv_outer = max(2, min(3, int(np.min(binc_outer))))
            model_outer = build_model(random_state=seed + fold_idx + 1000, calibration_cv=calibration_cv_outer)
            model_outer.fit(X_train, y_train)
            test_scores = model_outer.predict_proba(X_test)[:, 1]

            pred90 = (test_scores >= thr90).astype(int)
            pred95 = (test_scores >= thr95).astype(int)

            detail_rows.append(
                {
                    "seed": seed,
                    "outer_fold": fold_idx,
                    "n_train": int(len(train_idx)),
                    "n_test": int(len(test_idx)),
                    "ap": float(average_precision_score(y_test, test_scores)),
                    "roc_auc": float(roc_auc_score(y_test, test_scores)),
                    "threshold_recall_0.90": thr90,
                    "threshold_recall_0.95": thr95,
                    "precision@thr90": float(precision_score(y_test, pred90, zero_division=0)),
                    "recall@thr90": float(recall_score(y_test, pred90, zero_division=0)),
                    "f1@thr90": float(f1_score(y_test, pred90, zero_division=0)),
                    "positive_rate@thr90": float(np.mean(pred90)),
                    "precision@thr95": float(precision_score(y_test, pred95, zero_division=0)),
                    "recall@thr95": float(recall_score(y_test, pred95, zero_division=0)),
                    "f1@thr95": float(f1_score(y_test, pred95, zero_division=0)),
                    "positive_rate@thr95": float(np.mean(pred95)),
                }
            )

    details = pd.DataFrame(detail_rows)

    summary = pd.DataFrame(
        {
            "metric": [
                "ap",
                "roc_auc",
                "threshold_recall_0.90",
                "threshold_recall_0.95",
                "precision@thr90",
                "recall@thr90",
                "precision@thr95",
                "recall@thr95",
                "positive_rate@thr90",
                "positive_rate@thr95",
            ],
            "mean": [
                details["ap"].mean(),
                details["roc_auc"].mean(),
                details["threshold_recall_0.90"].mean(),
                details["threshold_recall_0.95"].mean(),
                details["precision@thr90"].mean(),
                details["recall@thr90"].mean(),
                details["precision@thr95"].mean(),
                details["recall@thr95"].mean(),
                details["positive_rate@thr90"].mean(),
                details["positive_rate@thr95"].mean(),
            ],
            "std": [
                details["ap"].std(),
                details["roc_auc"].std(),
                details["threshold_recall_0.90"].std(),
                details["threshold_recall_0.95"].std(),
                details["precision@thr90"].std(),
                details["recall@thr90"].std(),
                details["precision@thr95"].std(),
                details["recall@thr95"].std(),
                details["positive_rate@thr90"].std(),
                details["positive_rate@thr95"].std(),
            ],
        }
    )

    per_seed = (
        details.groupby("seed", as_index=False)
        .agg(
            ap_mean=("ap", "mean"),
            roc_auc_mean=("roc_auc", "mean"),
            thr90_mean=("threshold_recall_0.90", "mean"),
            thr95_mean=("threshold_recall_0.95", "mean"),
            recall_thr90_mean=("recall@thr90", "mean"),
            recall_thr95_mean=("recall@thr95", "mean"),
            precision_thr90_mean=("precision@thr90", "mean"),
            precision_thr95_mean=("precision@thr95", "mean"),
        )
        .sort_values("seed")
    )

    details.to_csv(output_dir / "nested_cv_seed_sweep_details.csv", index=False)
    summary.to_csv(output_dir / "nested_cv_seed_sweep_summary.csv", index=False)
    per_seed.to_csv(output_dir / "nested_cv_seed_sweep_per_seed.csv", index=False)

    return details, summary


def export_leakage_safe_ranking(
    clean_df: pd.DataFrame,
    X: np.ndarray,
    y: np.ndarray,
    output_dir: Path,
    random_state: int,
) -> pd.DataFrame:
    model = build_model(random_state=random_state)
    model.fit(X, y)
    scores = model.predict_proba(X)[:, 1]

    rec_col = find_column(clean_df.columns, ["rec_number", "rec number"], required=False)

    queue = pd.DataFrame(
        {
            "queue_rank": np.arange(1, len(clean_df) + 1),
            "score_include": scores,
            "title": clean_df["_title"].astype(str).values,
            "abstract": clean_df["_abstract"].astype(str).values,
        }
    )
    if rec_col is not None:
        queue["record_id"] = clean_df[rec_col].values

    queue = queue.sort_values("score_include", ascending=False).reset_index(drop=True)
    queue["queue_rank"] = np.arange(1, len(queue) + 1)

    q1, q2 = queue["score_include"].quantile([0.33, 0.67]).tolist()
    queue["priority_bucket"] = np.where(
        queue["score_include"] >= q2,
        "high",
        np.where(queue["score_include"] >= q1, "medium", "low"),
    )

    sensitive_patterns = ["decision", "include", "exclude", "label", "true_label", "pred"]
    removed_sensitive_cols = [
        c
        for c in clean_df.columns
        if any(p in normalize_col_name(c) for p in sensitive_patterns) and c not in {"_title", "_abstract"}
    ]

    queue_path = output_dir / "production_ranking_leakage_safe.csv"
    queue.to_csv(queue_path, index=False)

    manifest = {
        "description": "Leakage-safe production ranking export for screening queue.",
        "included_columns": list(queue.columns),
        "removed_sensitive_columns": removed_sensitive_cols,
        "n_records": int(len(queue)),
        "score_range": {
            "min": float(queue["score_include"].min()),
            "max": float(queue["score_include"].max()),
            "mean": float(queue["score_include"].mean()),
        },
        "priority_bucket_counts": {k: int(v) for k, v in queue["priority_bucket"].value_counts().to_dict().items()},
    }
    (output_dir / "production_ranking_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return queue


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    cols = [str(c) for c in df.columns]
    header = "| " + " | ".join(cols) + " |"
    sep = "|" + "|".join(["---"] * len(cols)) + "|"
    rows = []
    for _, row in df.iterrows():
        vals = []
        for c in df.columns:
            v = row[c]
            if isinstance(v, (float, np.floating)):
                vals.append(f"{float(v):.4f}")
            else:
                vals.append(str(v))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep] + rows)


def write_execution_summary(
    output_dir: Path,
    columns_detected: Dict[str, str],
    nested_summary: pd.DataFrame,
    strategy_summary: pd.DataFrame,
    policy_summary: pd.DataFrame,
    report_path: Path,
) -> None:
    def metric_line(metric_name: str) -> str:
        row = nested_summary.loc[nested_summary["metric"] == metric_name]
        if row.empty:
            return f"- {metric_name}: n/a"
        m = float(row.iloc[0]["mean"])
        s = float(row.iloc[0]["std"])
        return f"- {metric_name}: {m:.4f} ± {s:.4f}"

    best_strategy = strategy_summary.iloc[0]
    worst_strategy = strategy_summary.iloc[-1]
    docs_gain = float(worst_strategy["docs_to_recall_0_95_mean"] - best_strategy["docs_to_recall_0_95_mean"])

    lines = [
        "# NEXT_STEPS Execution Report",
        "",
        "## Implemented next recommended steps",
        "1. Added active-learning simulation (query/update loop) with run-level traces and policy-based stop evaluation.",
        "2. Added nested CV + seed sweeps for threshold stability at recall targets (0.90/0.95).",
        "3. Added leakage-safe production ranking export + manifest of removed sensitive fields.",
        "4. Added target-recall stopping diagnostics, including SAFE-like statistical upper-bound checks.",
        "5. Added ASReview prior/seed strategy experiments (known relevant + known irrelevant templates).",
        "",
        "## Data/config",
        f"- Columns detected: {columns_detected}",
        f"- Output directory: `{output_dir}`",
        "",
        "## Nested CV + seed sweep results",
        metric_line("ap"),
        metric_line("roc_auc"),
        metric_line("threshold_recall_0.90"),
        metric_line("threshold_recall_0.95"),
        metric_line("recall@thr90"),
        metric_line("recall@thr95"),
        metric_line("precision@thr90"),
        metric_line("precision@thr95"),
        "",
        "## Prior strategy simulation results",
        f"- Best strategy by workload to 95% recall: **{best_strategy['strategy']}**",
        f"- Mean docs to 95% recall (best): {best_strategy['docs_to_recall_0_95_mean']:.2f}",
        f"- Mean docs to 95% recall (worst): {worst_strategy['docs_to_recall_0_95_mean']:.2f}",
        f"- Improvement: {docs_gain:.2f} fewer docs screened to reach 95% recall",
        "",
        "### Strategy table",
        dataframe_to_markdown(strategy_summary),
        "",
        "## Stopping diagnostics summary",
        dataframe_to_markdown(policy_summary),
        "",
        "## Generated artifacts",
        "- `analysis/outputs/next_steps/active_learning_traces.csv`",
        "- `analysis/outputs/next_steps/active_learning_runs.csv`",
        "- `analysis/outputs/next_steps/prior_strategy_summary.csv`",
        "- `analysis/outputs/next_steps/stopping_policy_outcomes_by_run.csv`",
        "- `analysis/outputs/next_steps/stopping_policy_summary.csv`",
        "- `analysis/outputs/next_steps/nested_cv_seed_sweep_details.csv`",
        "- `analysis/outputs/next_steps/nested_cv_seed_sweep_summary.csv`",
        "- `analysis/outputs/next_steps/nested_cv_seed_sweep_per_seed.csv`",
        "- `analysis/outputs/next_steps/production_ranking_leakage_safe.csv`",
        "- `analysis/outputs/next_steps/production_ranking_manifest.json`",
        "",
        "## What remains",
        "- Validate stopping-policy choices with domain stakeholders before operational use.",
        "- Add external validation on an independent screening dataset.",
        "- Integrate simulation diagnostics into CI/regression tracking if this workflow is productized.",
    ]

    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute ASReview next recommended improvements.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "screening_input.xlsx",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "next_steps",
    )
    parser.add_argument(
        "--report-path",
        type=Path,
        default=Path(__file__).resolve().parent / "NEXT_STEPS_EXECUTION_REPORT.md",
    )
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument(
        "--seeds",
        type=int,
        nargs="+",
        default=[11, 19, 42, 77, 2026],
        help="Seed sweep values used for active-learning and nested-CV runs.",
    )
    args = parser.parse_args()

    random.seed(args.random_state)
    np.random.seed(args.random_state)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    clean_df, X, y, columns_detected = prepare_data(args.input)

    traces, runs, strategy_summary, policy_summary = run_active_learning_suite(
        X=X,
        y=y,
        output_dir=args.output_dir,
        seeds=args.seeds,
    )

    nested_details, nested_summary = run_nested_cv_threshold_seed_sweep(
        X=X,
        y=y,
        output_dir=args.output_dir,
        seeds=args.seeds,
        outer_splits=5,
        inner_splits=3,
    )

    queue = export_leakage_safe_ranking(
        clean_df=clean_df,
        X=X,
        y=y,
        output_dir=args.output_dir,
        random_state=args.random_state,
    )

    run_meta = {
        "input": str(args.input.resolve()),
        "output_dir": str(args.output_dir.resolve()),
        "report_path": str(args.report_path.resolve()),
        "columns_detected": columns_detected,
        "n_records": int(len(clean_df)),
        "n_positives": int(y.sum()),
        "n_negatives": int((y == 0).sum()),
        "seeds": list(args.seeds),
        "active_learning_runs": int(len(runs)),
        "active_learning_trace_rows": int(len(traces)),
        "nested_cv_rows": int(len(nested_details)),
        "production_queue_rows": int(len(queue)),
    }
    (args.output_dir / "run_meta_next_steps.json").write_text(json.dumps(run_meta, indent=2), encoding="utf-8")

    write_execution_summary(
        output_dir=args.output_dir,
        columns_detected=columns_detected,
        nested_summary=nested_summary,
        strategy_summary=strategy_summary,
        policy_summary=policy_summary,
        report_path=args.report_path,
    )

    print("Next-step execution complete.")
    print(f"Output dir: {args.output_dir}")
    print(f"Report: {args.report_path}")


if __name__ == "__main__":
    main()
