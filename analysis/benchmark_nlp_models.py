#!/usr/bin/env python3
"""Benchmark baseline/improved/new NLP models for abstract screening.

This script is intentionally self-contained and uses reproducible,
lightweight defaults so it can run in constrained environments.

Outputs are written to analysis/outputs/benchmarks/ by default.
"""

from __future__ import annotations

import argparse
import json
import math
import platform
import re
import sys
import time
from dataclasses import dataclass
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix
from sklearn.calibration import CalibratedClassifierCV
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import NotFittedError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.pipeline import FeatureUnion, Pipeline
from sklearn.preprocessing import Normalizer
from sklearn.svm import LinearSVC

INCLUDE_TOKENS = {"1", "i", "include", "included"}
EXCLUDE_TOKENS = {"0", "e", "exclude", "excluded"}

DORY_DOCS_CLASSIFIERS = ["adaboost", "dynamic-nn", "nn-2-layer", "warmstart-nn", "xgboost"]
DORY_DOCS_FEATURE_EXTRACTORS = [
    "doc2vec",
    "gtr-t5-large",
    "labse",
    "multilingual-e5-large",
    "mxbai",
    "sbert",
    "xlm-roberta-large",
]
DORY_BENCHMARK_CLASSIFIERS = ["xgboost", "adaboost"]


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    cohort: str
    lightweight: bool
    builder_key: str
    notes: str
    model_source: str
    dory_classifier: Optional[str] = None


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


def _word_tfidf_vectorizer() -> TfidfVectorizer:
    return TfidfVectorizer(
        analyzer="word",
        lowercase=True,
        strip_accents="unicode",
        ngram_range=(1, 2),
        min_df=1,
        max_df=0.98,
        sublinear_tf=True,
    )


def _word_char_features() -> FeatureUnion:
    return FeatureUnion(
        transformer_list=[
            (
                "word",
                _word_tfidf_vectorizer(),
            ),
            (
                "char",
                TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    ngram_range=(3, 5),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def _norm_dist_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _collect_asreview_entry_points() -> Tuple[Dict[str, List[Dict[str, str]]], Dict[str, metadata.EntryPoint], Dict[str, metadata.EntryPoint]]:
    tracked_groups = {
        "asreview.models",
        "asreview.models.classifiers",
        "asreview.models.feature_extractors",
        "asreview.models.queriers",
        "asreview.models.balancers",
        # backward-compat groups used by old installs
        "asreview.classifiers",
        "asreview.feature_extractors",
        "asreview.query_strategies",
        "asreview.models.classifiers",
    }

    grouped: Dict[str, List[Dict[str, str]]] = {}
    dory_classifier_eps: Dict[str, metadata.EntryPoint] = {}
    dory_feature_eps: Dict[str, metadata.EntryPoint] = {}

    for dist in metadata.distributions():
        dist_name = dist.metadata.get("Name", "")
        dist_name_norm = _norm_dist_name(dist_name)

        for ep in dist.entry_points:
            if ep.group not in tracked_groups:
                continue

            rec = {
                "name": ep.name,
                "value": ep.value,
                "distribution": dist_name,
            }
            grouped.setdefault(ep.group, []).append(rec)

            is_dory = dist_name_norm == "asreview-dory" or ep.value.startswith("asreviewcontrib.dory")
            if is_dory and ep.group == "asreview.models.classifiers":
                dory_classifier_eps[ep.name] = ep
            if is_dory and ep.group == "asreview.models.feature_extractors":
                dory_feature_eps[ep.name] = ep

    for group, rows in grouped.items():
        rows.sort(key=lambda r: (r["name"], r["distribution"], r["value"]))

    return grouped, dory_classifier_eps, dory_feature_eps


def _dory_probe_kwargs(classifier_name: str) -> Dict[str, Any]:
    if classifier_name == "xgboost":
        return {
            "n_estimators": 40,
            "max_depth": 6,
            "learning_rate": 0.2,
            "verbosity": 0,
            "random_state": 42,
        }
    if classifier_name == "adaboost":
        return {
            "n_estimators": 40,
            "learning_rate": 0.8,
            "random_state": 42,
        }
    if classifier_name in {"dynamic-nn", "nn-2-layer", "warmstart-nn"}:
        return {
            "epochs": 1,
            "batch_size": 4,
            "verbose": 0,
            "random_state": 42,
        }
    return {"random_state": 42}


def _probe_dory_classifier(classifier_name: str, dory_classifier_eps: Dict[str, metadata.EntryPoint]) -> Dict[str, Any]:
    probe: Dict[str, Any] = {
        "classifier": classifier_name,
        "status": "blocked",
        "probe": "sparse_tfidf_fit_predict_proba",
    }

    ep = dory_classifier_eps.get(classifier_name)
    if ep is None:
        probe.update(
            {
                "reason": "No ASReview Dory classifier entry point detected in this environment.",
                "blocker_type": "missing_entry_point",
            }
        )
        return probe

    probe["entry_point"] = ep.value

    try:
        classifier_cls = ep.load()
    except Exception as exc:
        probe.update(
            {
                "reason": f"Failed to load classifier entry point: {type(exc).__name__}: {exc}",
                "blocker_type": "entry_point_load_error",
            }
        )
        return probe

    kwargs = _dory_probe_kwargs(classifier_name)
    probe["probe_kwargs"] = kwargs

    try:
        estimator = classifier_cls(**kwargs)
    except Exception as exc:
        probe.update(
            {
                "reason": f"Failed to instantiate classifier: {type(exc).__name__}: {exc}",
                "blocker_type": "instantiation_error",
            }
        )
        return probe

    X_probe = csr_matrix(
        np.asarray(
            [
                [1.0, 0.0, 0.0, 0.1],
                [0.8, 0.2, 0.0, 0.2],
                [0.0, 1.0, 0.2, 0.0],
                [0.0, 0.9, 0.1, 0.0],
                [0.0, 0.0, 1.0, 0.4],
                [0.1, 0.0, 0.8, 0.5],
            ],
            dtype=float,
        )
    )
    y_probe = np.asarray([0, 0, 1, 1, 1, 0], dtype=int)

    try:
        estimator.fit(X_probe, y_probe)
        y_hat = estimator.predict_proba(X_probe)
        y_hat = np.asarray(y_hat)
        if y_hat.ndim != 2 or y_hat.shape[1] < 2:
            raise RuntimeError(f"Unexpected predict_proba shape: {y_hat.shape}")

        probe.update(
            {
                "status": "available",
                "reason": "Entry point loads and sparse TF-IDF probe fit/predict succeeds.",
            }
        )
        return probe
    except Exception as exc:
        probe.update(
            {
                "reason": f"Sparse TF-IDF probe failed: {type(exc).__name__}: {exc}",
                "blocker_type": "probe_fit_error",
            }
        )
        return probe


def detect_environment_model_options() -> Dict[str, Any]:
    installed = sorted(dist.metadata["Name"] for dist in metadata.distributions() if dist.metadata.get("Name"))
    installed_norm = {_norm_dist_name(name) for name in installed}

    asreview_dists = [name for name in installed if "asreview" in name.lower()]

    entry_point_groups, dory_classifier_eps, dory_feature_eps = _collect_asreview_entry_points()

    dory_classifiers_detected = sorted(dory_classifier_eps.keys())
    dory_feature_extractors_detected = sorted(dory_feature_eps.keys())

    dory_query_strategies_detected: List[str] = []
    for row in entry_point_groups.get("asreview.models.queriers", []):
        if row["value"].startswith("asreviewcontrib.dory"):
            dory_query_strategies_detected.append(row["name"])

    asreview_ai_model_configs: List[Dict[str, Any]] = []
    try:
        from asreview.models.models import AI_MODEL_CONFIGURATIONS

        for cfg in AI_MODEL_CONFIGURATIONS:
            cfg_val = cfg.get("value")
            required_ext = list(cfg.get("extensions", []))
            missing_ext = [ext for ext in required_ext if _norm_dist_name(ext) not in installed_norm]
            status = "available" if not missing_ext else "blocked"

            asreview_ai_model_configs.append(
                {
                    "name": cfg.get("name"),
                    "label": cfg.get("label"),
                    "type": cfg.get("type"),
                    "classifier": getattr(cfg_val, "classifier", None),
                    "feature_extractor": getattr(cfg_val, "feature_extractor", None),
                    "required_extensions": required_ext,
                    "missing_extensions": missing_ext,
                    "status": status,
                }
            )
    except Exception:
        asreview_ai_model_configs = []

    dory_probe_results = [_probe_dory_classifier(name, dory_classifier_eps) for name in DORY_DOCS_CLASSIFIERS]
    dory_probe_by_name = {row["classifier"]: row for row in dory_probe_results}

    dory_version = None
    try:
        dory_version = metadata.version("asreview-dory")
    except Exception:
        dory_version = None

    dory_status = {
        "status": "available" if dory_version else "blocked",
        "version": dory_version,
        "reason": "ASReview Dory distribution detected." if dory_version else "ASReview Dory distribution not installed.",
        "docs_source": "https://github.com/asreview/asreview-dory",
        "docs_classifier_names": DORY_DOCS_CLASSIFIERS,
        "docs_feature_extractor_names": DORY_DOCS_FEATURE_EXTRACTORS,
        "entry_point_classifiers": dory_classifiers_detected,
        "entry_point_feature_extractors": dory_feature_extractors_detected,
        "entry_point_query_strategies": dory_query_strategies_detected,
        "runnable_classifier_probes": dory_probe_results,
    }

    possible_nemo_ep = []
    for rows in entry_point_groups.values():
        for row in rows:
            name = str(row.get("name", ""))
            if "nemo" in name.lower():
                possible_nemo_ep.append(name)

    nemo_candidate_modules = [
        "asreview_nemo",
        "asreviewcontrib.classifiers.nemo",
        "asreviewcontrib.models.nemo",
        "asreview_models.nemo",
        "nemo_toolkit",
    ]

    available_modules = []
    for module_name in nemo_candidate_modules:
        try:
            __import__(module_name)
            available_modules.append(module_name)
        except Exception:
            pass

    if possible_nemo_ep or available_modules:
        nemo_status: Dict[str, Any] = {
            "status": "available",
            "reason": "Detected Nemo-like extension/module in current environment.",
            "entry_points": sorted(possible_nemo_ep),
            "modules": sorted(available_modules),
        }
    else:
        nemo_status = {
            "status": "blocked",
            "reason": (
                "No ASReview Nemo extension detected. ASReview core classifiers available are typically "
                "logistic/nb/rf/svm unless extra classifier plugins are installed."
            ),
            "entry_points": [],
            "modules_checked": nemo_candidate_modules,
            "modules_available": [],
            "blocker_type": "missing_dependency",
        }

    feasible_dory_for_benchmark = [
        p["classifier"]
        for p in dory_probe_results
        if p.get("status") == "available" and p.get("classifier") in DORY_BENCHMARK_CLASSIFIERS
    ]

    return {
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "installed_asreview_related_packages": asreview_dists,
        "entry_points": entry_point_groups,
        "asreview_ai_model_configs": asreview_ai_model_configs,
        "dory": dory_status,
        "dory_feasible_benchmark_classifiers": feasible_dory_for_benchmark,
        "nemo": nemo_status,
        "stronger_heavy_model_candidates": [
            {
                "name": "sentence-transformers/all-MiniLM-L6-v2 + linear classifier",
                "status": "not_enabled",
                "reason": "Not included in default benchmark to keep install/runtime lightweight and reproducible.",
            },
            {
                "name": "transformer cross-encoder rerankers",
                "status": "not_enabled",
                "reason": "GPU/large-model dependency footprint exceeds default repo constraints.",
            },
            {
                "name": "dory sentence-transformer feature extractors (labse/mxbai/sbert/gtr/e5/xlm-roberta)",
                "status": "not_enabled",
                "reason": "Transformer embeddings require additional model downloads and significantly higher runtime/compute.",
            },
        ],
        "dory_probe_index": dory_probe_by_name,
    }


def build_model(spec: ModelSpec, random_state: int, y_train: np.ndarray) -> Pipeline:
    min_class = int(np.min(np.bincount(y_train, minlength=2)))
    calibration_cv = max(2, min(3, min_class))

    if spec.builder_key == "baseline_lr_word_tfidf":
        return Pipeline(
            steps=[
                (
                    "tfidf",
                    TfidfVectorizer(
                        lowercase=True,
                        strip_accents="unicode",
                        ngram_range=(1, 2),
                        min_df=2,
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

    if spec.builder_key == "improved_calibrated_svm_word_char":
        return Pipeline(
            steps=[
                ("features", _word_char_features()),
                (
                    "clf",
                    CalibratedClassifierCV(
                        estimator=LinearSVC(C=1.0, class_weight="balanced", random_state=random_state),
                        method="sigmoid",
                        cv=calibration_cv,
                    ),
                ),
            ]
        )

    if spec.builder_key == "candidate_lr_word_char":
        return Pipeline(
            steps=[
                ("features", _word_char_features()),
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

    if spec.builder_key == "candidate_lsa_lr":
        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("svd", TruncatedSVD(n_components=128, random_state=random_state)),
                ("norm", Normalizer(copy=False)),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=5000,
                        class_weight="balanced",
                        solver="liblinear",
                        random_state=random_state,
                    ),
                ),
            ]
        )

    if spec.builder_key == "candidate_sgd_word_char":
        return Pipeline(
            steps=[
                ("features", _word_char_features()),
                (
                    "clf",
                    SGDClassifier(
                        loss="log_loss",
                        alpha=1e-5,
                        penalty="l2",
                        max_iter=2000,
                        class_weight="balanced",
                        random_state=random_state,
                    ),
                ),
            ]
        )

    if spec.builder_key == "candidate_cnb_word_tfidf":
        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("clf", ComplementNB(alpha=0.5, norm=False)),
            ]
        )

    if spec.builder_key == "dory_xgboost_word_tfidf":
        from asreviewcontrib.dory.classifiers.xgboost import XGBoost

        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                (
                    "clf",
                    XGBoost(
                        n_estimators=120,
                        max_depth=6,
                        learning_rate=0.2,
                        verbosity=0,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    if spec.builder_key == "dory_adaboost_word_tfidf":
        from asreviewcontrib.dory.classifiers.adaboost import AdaBoost

        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                (
                    "clf",
                    AdaBoost(
                        n_estimators=120,
                        learning_rate=0.8,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    raise ValueError(f"Unknown builder key: {spec.builder_key}")


def extract_probabilities(model: Pipeline, X_test: np.ndarray) -> np.ndarray:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X_test)[:, 1]

    if hasattr(model, "decision_function"):
        decision = model.decision_function(X_test)
        decision = np.asarray(decision, dtype=float)
        # Fallback calibration proxy for models without predict_proba.
        return 1.0 / (1.0 + np.exp(-decision))

    raise RuntimeError("Model has neither predict_proba nor decision_function")


def estimate_feature_count(model: Pipeline) -> Optional[int]:
    try:
        if "tfidf" in model.named_steps:
            vec = model.named_steps["tfidf"]
            vocab = getattr(vec, "vocabulary_", None)
            return int(len(vocab)) if vocab is not None else None

        if "features" in model.named_steps:
            feats = model.named_steps["features"]
            if hasattr(feats, "transformer_list"):
                total = 0
                found_any = False
                for _name, transformer in feats.transformer_list:
                    vocab = getattr(transformer, "vocabulary_", None)
                    if vocab is not None:
                        total += len(vocab)
                        found_any = True
                if found_any:
                    return int(total)
    except NotFittedError:
        return None
    except Exception:
        return None

    return None


def evaluate_fold_metrics(y_true: np.ndarray, scores: np.ndarray) -> Dict[str, float]:
    out = {
        "average_precision": float(average_precision_score(y_true, scores)),
        "roc_auc": float(roc_auc_score(y_true, scores)) if len(np.unique(y_true)) > 1 else float("nan"),
        "wss@95": float(wss_at_recall(y_true, scores, target_recall=0.95)),
    }

    for k in (10, 20, 50):
        p_at_k, r_at_k = precision_recall_at_k(y_true, scores, k)
        out[f"precision@{k}"] = float(p_at_k)
        out[f"recall@{k}"] = float(r_at_k)

    return out


def build_specs(env_info: Dict[str, Any]) -> List[ModelSpec]:
    specs = [
        ModelSpec(
            model_id="baseline_lr_word_tfidf",
            display_name="Baseline LR (word TF-IDF)",
            cohort="baseline",
            lightweight=True,
            builder_key="baseline_lr_word_tfidf",
            notes="Current baseline from analysis/train_asreview.py",
            model_source="core",
        ),
        ModelSpec(
            model_id="improved_calibrated_svm_word_char",
            display_name="Improved Calibrated SVM (word+char TF-IDF)",
            cohort="improved",
            lightweight=True,
            builder_key="improved_calibrated_svm_word_char",
            notes="Current improved best from analysis/train_asreview_improved.py",
            model_source="core",
        ),
        ModelSpec(
            model_id="candidate_lr_word_char",
            display_name="Candidate LR (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_lr_word_char",
            notes="Adds character n-grams to linear baseline while retaining calibration-friendly LR.",
            model_source="core",
        ),
        ModelSpec(
            model_id="candidate_lsa_lr",
            display_name="Candidate LSA+LR (SVD semantic projection)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_lsa_lr",
            notes="Low-dimensional semantic projection can improve signal-to-noise on small corpora.",
            model_source="core",
        ),
        ModelSpec(
            model_id="candidate_sgd_word_char",
            display_name="Candidate SGD log-loss (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_sgd_word_char",
            notes="Fast linear online learner suitable for frequent reruns.",
            model_source="core",
        ),
        ModelSpec(
            model_id="candidate_cnb_word_tfidf",
            display_name="Candidate ComplementNB (word TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_cnb_word_tfidf",
            notes="Strong sparse-text baseline for imbalance, included for comparison.",
            model_source="core",
        ),
    ]

    dory_probe = env_info.get("dory_probe_index", {})

    if dory_probe.get("xgboost", {}).get("status") == "available":
        specs.append(
            ModelSpec(
                model_id="dory_xgboost_word_tfidf",
                display_name="Dory XGBoost (word TF-IDF)",
                cohort="dory",
                lightweight=False,
                builder_key="dory_xgboost_word_tfidf",
                notes=(
                    "ASReview Dory classifier via entry point `xgboost`, benchmarked with core TF-IDF "
                    "to keep protocol comparable."
                ),
                model_source="dory",
                dory_classifier="xgboost",
            )
        )

    if dory_probe.get("adaboost", {}).get("status") == "available":
        specs.append(
            ModelSpec(
                model_id="dory_adaboost_word_tfidf",
                display_name="Dory AdaBoost (word TF-IDF)",
                cohort="dory",
                lightweight=False,
                builder_key="dory_adaboost_word_tfidf",
                notes=(
                    "ASReview Dory classifier via entry point `adaboost`, benchmarked with core TF-IDF "
                    "for fair comparison against existing sparse pipelines."
                ),
                model_source="dory",
                dory_classifier="adaboost",
            )
        )

    return specs


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
                if np.isnan(float(v)):
                    vals.append("nan")
                else:
                    vals.append(f"{float(v):.6f}")
            else:
                vals.append(str(v))
        rows.append("| " + " | ".join(vals) + " |")
    return "\n".join([header, sep] + rows)


def run_benchmark(
    *,
    input_path: Path,
    output_dir: Path,
    n_splits: int,
    n_repeats: int,
    random_state: int,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_excel(input_path)
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
    clean = prepared.loc[valid_mask].copy().reset_index(drop=True)
    clean["_label"] = clean["_label"].astype(int)

    if len(clean) < max(20, n_splits * 2):
        raise ValueError(
            f"Too few usable rows after cleaning ({len(clean)} of {original_n}) for CV benchmark."
        )

    X = clean["_text"].values
    y_arr = clean["_label"].values

    class_counts = {
        int(k): int(v) for k, v in zip(*np.unique(y_arr, return_counts=True))
    }
    if len(class_counts) < 2:
        raise ValueError(f"Need both classes after mapping; got class_counts={class_counts}")

    env_info = detect_environment_model_options()
    specs = build_specs(env_info)

    cv = RepeatedStratifiedKFold(
        n_splits=n_splits,
        n_repeats=n_repeats,
        random_state=random_state,
    )
    fold_splits = list(cv.split(X, y_arr))

    fold_rows: List[Dict[str, Any]] = []

    for spec in specs:
        for fold_idx, (train_idx, test_idx) in enumerate(fold_splits, start=1):
            X_train = X[train_idx]
            y_train = y_arr[train_idx]
            X_test = X[test_idx]
            y_test = y_arr[test_idx]

            t0 = time.perf_counter()
            model = build_model(spec, random_state=random_state + fold_idx, y_train=y_train)
            model.fit(X_train, y_train)
            fit_seconds = time.perf_counter() - t0

            t1 = time.perf_counter()
            y_scores = extract_probabilities(model, X_test)
            score_seconds = time.perf_counter() - t1

            metrics = evaluate_fold_metrics(y_test, y_scores)
            feature_count = estimate_feature_count(model)

            fold_rows.append(
                {
                    "model_id": spec.model_id,
                    "display_name": spec.display_name,
                    "cohort": spec.cohort,
                    "model_source": spec.model_source,
                    "dory_classifier": spec.dory_classifier or "",
                    "lightweight": spec.lightweight,
                    "fold": fold_idx,
                    "n_train": int(len(train_idx)),
                    "n_test": int(len(test_idx)),
                    "fit_seconds": float(fit_seconds),
                    "score_seconds": float(score_seconds),
                    "n_features": float(feature_count) if feature_count is not None else float("nan"),
                    **metrics,
                }
            )

    fold_df = pd.DataFrame(fold_rows)
    fold_path = output_dir / "model_benchmark_fold_metrics.csv"
    fold_df.to_csv(fold_path, index=False)

    agg_map = {
        "average_precision": ["mean", "std"],
        "roc_auc": ["mean", "std"],
        "wss@95": ["mean", "std"],
        "precision@10": ["mean", "std"],
        "recall@10": ["mean", "std"],
        "precision@20": ["mean", "std"],
        "recall@20": ["mean", "std"],
        "precision@50": ["mean", "std"],
        "recall@50": ["mean", "std"],
        "fit_seconds": ["mean", "std"],
        "score_seconds": ["mean", "std"],
        "n_features": ["mean"],
        "fold": ["count"],
    }

    grouped = fold_df.groupby(
        ["model_id", "display_name", "cohort", "model_source", "dory_classifier", "lightweight"],
        as_index=False,
        dropna=False,
    ).agg(agg_map)
    grouped.columns = [
        c[0] if c[1] == "" else f"{c[0]}_{c[1]}" for c in grouped.columns.to_flat_index()
    ]
    grouped = grouped.rename(columns={"fold_count": "n_folds"})

    grouped = grouped.sort_values(
        by=["average_precision_mean", "wss@95_mean", "recall@20_mean", "roc_auc_mean"],
        ascending=False,
    ).reset_index(drop=True)
    grouped["rank"] = np.arange(1, len(grouped) + 1)

    summary_path = output_dir / "model_benchmark_summary.csv"
    grouped.to_csv(summary_path, index=False)

    nemo_status = env_info.get("nemo", {})
    blocked_models: List[Dict[str, Any]] = []
    if nemo_status.get("status") != "available":
        blocked_models.append(
            {
                "model_id": "asreview_nemo",
                "display_name": "ASReview Nemo",
                "cohort": "candidate",
                "model_source": "nemo",
                "status": "blocked",
                "reason": nemo_status.get("reason", "Unavailable in environment."),
                "blocker_type": nemo_status.get("blocker_type", "unavailable"),
            }
        )

    dory_probe = env_info.get("dory_probe_index", {})
    benchmarked_dory = {s.dory_classifier for s in specs if s.dory_classifier}
    for classifier_name in DORY_DOCS_CLASSIFIERS:
        probe = dory_probe.get(classifier_name)
        if classifier_name in benchmarked_dory:
            continue

        if probe is None:
            blocked_models.append(
                {
                    "model_id": f"dory_{classifier_name}",
                    "display_name": f"Dory {classifier_name}",
                    "cohort": "dory",
                    "model_source": "dory",
                    "status": "blocked",
                    "reason": "No probe result available for this Dory classifier.",
                    "blocker_type": "probe_missing",
                }
            )
            continue

        if probe.get("status") != "available":
            blocked_models.append(
                {
                    "model_id": f"dory_{classifier_name}",
                    "display_name": f"Dory {classifier_name}",
                    "cohort": "dory",
                    "model_source": "dory",
                    "status": "blocked",
                    "reason": probe.get("reason", "Unavailable in environment."),
                    "blocker_type": probe.get("blocker_type", "unavailable"),
                }
            )

    availability = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "environment": {
            k: v for k, v in env_info.items() if k != "dory_probe_index"
        },
        "evaluated_models": [
            {
                "model_id": s.model_id,
                "display_name": s.display_name,
                "cohort": s.cohort,
                "model_source": s.model_source,
                "dory_classifier": s.dory_classifier,
                "lightweight": s.lightweight,
                "notes": s.notes,
            }
            for s in specs
        ],
        "blocked_models": blocked_models,
    }
    availability_path = output_dir / "environment_model_availability.json"
    availability_path.write_text(json.dumps(availability, indent=2), encoding="utf-8")

    top = grouped.iloc[0].to_dict()
    second = grouped.iloc[1].to_dict() if len(grouped) > 1 else None

    key_findings = [
        (
            f"Top model by AP: {top['display_name']} "
            f"(AP {top['average_precision_mean']:.3f} ± {top['average_precision_std']:.3f}, "
            f"WSS@95 {top['wss@95_mean']:.3f})."
        )
    ]

    if second is not None:
        key_findings.append(
            (
                f"Runner-up: {second['display_name']} "
                f"(AP {second['average_precision_mean']:.3f} ± {second['average_precision_std']:.3f})."
            )
        )

    dory_rows = grouped[grouped["cohort"] == "dory"].copy()
    non_dory_rows = grouped[grouped["cohort"] != "dory"].copy()
    if not dory_rows.empty:
        best_dory = dory_rows.sort_values("average_precision_mean", ascending=False).iloc[0].to_dict()
        key_findings.append(
            (
                f"Best Dory model: {best_dory['display_name']} "
                f"(AP {best_dory['average_precision_mean']:.3f}, WSS@95 {best_dory['wss@95_mean']:.3f})."
            )
        )

        if not non_dory_rows.empty:
            best_non_dory = non_dory_rows.sort_values("average_precision_mean", ascending=False).iloc[0].to_dict()
            ap_gap = float(best_dory["average_precision_mean"] - best_non_dory["average_precision_mean"])
            key_findings.append(
                (
                    f"Best Dory vs best current non-Dory AP gap: {ap_gap:+.3f} "
                    f"({best_dory['display_name']} vs {best_non_dory['display_name']})."
                )
            )

    fastest = grouped.sort_values("fit_seconds_mean", ascending=True).iloc[0].to_dict()
    key_findings.append(
        (
            f"Fastest training model: {fastest['display_name']} "
            f"({fastest['fit_seconds_mean']:.3f}s mean fit time/fold)."
        )
    )

    summary_json = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "input": str(input_path),
        "split_protocol": {
            "method": "RepeatedStratifiedKFold",
            "n_splits": n_splits,
            "n_repeats": n_repeats,
            "random_state": random_state,
            "n_total_rows": int(original_n),
            "n_usable_rows": int(len(clean)),
            "n_dropped_rows": int(original_n - len(clean)),
            "class_counts": class_counts,
        },
        "metrics_reported": [
            "average_precision",
            "roc_auc",
            "wss@95",
            "precision@10",
            "recall@10",
            "precision@20",
            "recall@20",
            "precision@50",
            "recall@50",
            "fit_seconds",
            "score_seconds",
            "n_features",
        ],
        "summary_rows": grouped.to_dict(orient="records"),
        "dory_models_benchmarked": sorted(
            [s.model_id for s in specs if s.model_source == "dory"]
        ),
        "key_findings": key_findings,
        "blocked_models": blocked_models,
    }
    summary_json_path = output_dir / "model_benchmark_summary.json"
    summary_json_path.write_text(json.dumps(summary_json, indent=2), encoding="utf-8")

    report_lines = [
        "# NLP Model Benchmark Report",
        "",
        "## Protocol",
        f"- Input: `{input_path}`",
        f"- Split: RepeatedStratifiedKFold (splits={n_splits}, repeats={n_repeats}, random_state={random_state})",
        f"- Usable rows: {len(clean)} / {original_n}",
        f"- Class counts: {class_counts}",
        "",
        "## Metrics",
        "- AP, ROC-AUC, precision@k, recall@k, WSS@95",
        "- Runtime notes: fit_seconds, score_seconds, estimated feature-space size",
        "",
        "## Ranked results (higher AP first)",
        dataframe_to_markdown(grouped),
        "",
        "## Dory benchmark context",
        "- ASReview Dory docs reference: https://github.com/asreview/asreview-dory",
        "- Dory classifiers are verified by installed entry points and sparse TF-IDF probe runs before inclusion.",
        "",
    ]

    if blocked_models:
        report_lines.extend(
            [
                "## Blocked models",
                "| model_id | reason |",
                "|---|---|",
            ]
        )
        for b in blocked_models:
            report_lines.append(f"| {b['model_id']} | {b['reason']} |")
        report_lines.append("")

    report_lines.extend(["## Key findings"] + [f"- {k}" for k in key_findings])
    report_lines.append("")

    report_path = output_dir / "MODEL_BENCHMARK_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "summary_csv": str(summary_path),
        "summary_json": str(summary_json_path),
        "fold_csv": str(fold_path),
        "availability_json": str(availability_path),
        "report_md": str(report_path),
        "winner": top.get("model_id"),
        "dory_models_benchmarked": summary_json["dory_models_benchmarked"],
        "blocked_models": blocked_models,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark baseline/improved/new NLP screening models.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "data" / "screening_input.xlsx",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent / "outputs" / "benchmarks",
    )
    parser.add_argument("--n-splits", type=int, default=5)
    parser.add_argument("--n-repeats", type=int, default=3)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    result = run_benchmark(
        input_path=args.input,
        output_dir=args.output_dir,
        n_splits=args.n_splits,
        n_repeats=args.n_repeats,
        random_state=args.random_state,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
