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
from importlib.util import find_spec
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, TransformerMixin
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


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    cohort: str
    lightweight: bool
    builder_key: str
    notes: str
    required_modules: Tuple[str, ...] = ()


class SentenceTransformerEncoder(BaseEstimator, TransformerMixin):
    """Light wrapper for sentence-transformers embeddings with process-local cache."""

    _MODEL_CACHE: Dict[str, Any] = {}
    _EMBED_CACHE: Dict[Tuple[str, str], np.ndarray] = {}

    def __init__(
        self,
        model_name: str = "sentence-transformers/all-MiniLM-L6-v2",
        batch_size: int = 32,
        normalize_embeddings: bool = True,
    ) -> None:
        self.model_name = model_name
        self.batch_size = int(batch_size)
        self.normalize_embeddings = bool(normalize_embeddings)
        self.n_features_out_: Optional[int] = None

    def fit(self, X: Sequence[str], y: Optional[np.ndarray] = None) -> "SentenceTransformerEncoder":
        return self

    def _get_model(self) -> Any:
        model = self._MODEL_CACHE.get(self.model_name)
        if model is None:
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(self.model_name)
            self._MODEL_CACHE[self.model_name] = model
        return model

    def transform(self, X: Sequence[str]) -> np.ndarray:
        texts = [str(x) for x in X]
        if not texts:
            return np.zeros((0, self.n_features_out_ or 0), dtype=np.float32)

        model = self._get_model()

        cache_keys = [(self.model_name, txt) for txt in texts]
        missing_texts = [txt for key, txt in zip(cache_keys, texts) if key not in self._EMBED_CACHE]

        if missing_texts:
            try:
                missing_emb = model.encode(
                    missing_texts,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    normalize_embeddings=self.normalize_embeddings,
                    convert_to_numpy=True,
                )
            except TypeError:
                missing_emb = model.encode(
                    missing_texts,
                    batch_size=self.batch_size,
                    show_progress_bar=False,
                    convert_to_numpy=True,
                )

            for txt, vec in zip(missing_texts, missing_emb):
                self._EMBED_CACHE[(self.model_name, txt)] = np.asarray(vec, dtype=np.float32)

        arr = np.vstack([self._EMBED_CACHE[key] for key in cache_keys]).astype(np.float32)
        self.n_features_out_ = int(arr.shape[1]) if arr.ndim == 2 else None
        return arr


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


def is_module_available(module_name: str) -> bool:
    try:
        return find_spec(module_name) is not None
    except Exception:
        return False


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

    if spec.builder_key == "candidate_calibrated_sgd_word_char":
        return Pipeline(
            steps=[
                ("features", _word_char_features()),
                (
                    "clf",
                    CalibratedClassifierCV(
                        estimator=SGDClassifier(
                            loss="modified_huber",
                            alpha=5e-6,
                            penalty="l2",
                            max_iter=3000,
                            class_weight="balanced",
                            random_state=random_state,
                        ),
                        method="sigmoid",
                        cv=calibration_cv,
                    ),
                ),
            ]
        )

    if spec.builder_key == "candidate_lr_elasticnet_word_char":
        return Pipeline(
            steps=[
                ("features", _word_char_features()),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=5000,
                        class_weight="balanced",
                        solver="saga",
                        penalty="elasticnet",
                        l1_ratio=0.15,
                        C=3.0,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    if spec.builder_key == "candidate_linear_svc_isotonic_word_char":
        return Pipeline(
            steps=[
                ("features", _word_char_features()),
                (
                    "clf",
                    CalibratedClassifierCV(
                        estimator=LinearSVC(C=0.75, class_weight="balanced", random_state=random_state),
                        method="isotonic",
                        cv=calibration_cv,
                    ),
                ),
            ]
        )

    if spec.builder_key == "candidate_st_minilm_lr":
        return Pipeline(
            steps=[
                (
                    "embeddings",
                    SentenceTransformerEncoder(
                        model_name="sentence-transformers/all-MiniLM-L6-v2",
                        batch_size=32,
                        normalize_embeddings=True,
                    ),
                ),
                (
                    "clf",
                    LogisticRegression(
                        max_iter=4000,
                        class_weight="balanced",
                        solver="lbfgs",
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

        if "embeddings" in model.named_steps:
            emb = model.named_steps["embeddings"]
            n_out = getattr(emb, "n_features_out_", None)
            if n_out is not None:
                return int(n_out)
    except NotFittedError:
        return None
    except Exception:
        return None

    return None


def detect_environment_model_options() -> Dict[str, Any]:
    installed = sorted(dist.metadata["Name"] for dist in metadata.distributions() if dist.metadata.get("Name"))
    installed_norm = {name.lower() for name in installed}

    def _has_dist(prefix: str) -> List[str]:
        p = prefix.lower()
        return [name for name in installed if p in name.lower()]

    asreview_dists = _has_dist("asreview")

    entry_point_groups: Dict[str, List[str]] = {}
    entry_point_records: List[Dict[str, str]] = []
    try:
        eps = metadata.entry_points()
        groups = [
            "asreview.models",
            "asreview.models.classifiers",
            "asreview.models.feature_extractors",
            "asreview.models.queriers",
            "asreview.models.balancers",
        ]
        for group in groups:
            try:
                selected = list(eps.select(group=group))
            except Exception:
                selected = [ep for ep in eps if getattr(ep, "group", "") == group]
            if selected:
                entry_point_groups[group] = sorted(ep.name for ep in selected)
                for ep in selected:
                    entry_point_records.append(
                        {
                            "group": group,
                            "name": ep.name,
                            "module": getattr(ep, "module", "") or "",
                            "dist": getattr(getattr(ep, "dist", None), "name", "") or "",
                        }
                    )
    except Exception:
        entry_point_groups = {}
        entry_point_records = []

    asreview_metadata: Dict[str, Any] = {}
    try:
        meta = metadata.metadata("asreview")
        asreview_metadata = {
            "version": meta.get("Version"),
            "provided_extras": sorted(meta.get_all("Provides-Extra") or []),
        }
    except Exception:
        asreview_metadata = {}

    asreview_ai_model_configs: List[Dict[str, Any]] = []
    try:
        from asreview.models.models import AI_MODEL_CONFIGURATIONS

        for cfg in AI_MODEL_CONFIGURATIONS:
            cfg_val = cfg.get("value")
            required_ext = list(cfg.get("extensions", []))
            missing_ext = [ext for ext in required_ext if ext.lower() not in installed_norm]
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

    possible_nemo_ep = sorted(
        {
            ep["name"]
            for ep in entry_point_records
            if "nemo" in ep["name"].lower() or "nemo" in ep["module"].lower()
        }
    )

    nemo_candidate_modules = [
        "asreview_nemo",
        "asreviewcontrib.classifiers.nemo",
        "asreviewcontrib.models.nemo",
        "asreview_models.nemo",
        "nemo_toolkit",
    ]
    available_modules = [m for m in nemo_candidate_modules if is_module_available(m)]

    available_classifiers = entry_point_groups.get("asreview.models.classifiers", [])
    nemo_classifier_present = any(name.lower() == "nemo" for name in available_classifiers)
    nemo_extra_declared = "nemo" in set(asreview_metadata.get("provided_extras", []))

    nemo_status: Dict[str, Any]
    if nemo_classifier_present or possible_nemo_ep or available_modules:
        nemo_status = {
            "status": "available",
            "reason": "Detected Nemo-like classifier/module in current environment.",
            "entry_points": possible_nemo_ep,
            "modules": sorted(available_modules),
            "blocker_type": None,
        }
    else:
        nemo_status = {
            "status": "blocked",
            "reason": (
                "ASReview Nemo is unavailable: no `nemo` classifier entry point is registered, "
                "ASReview 2.2 does not expose a `nemo` extra, and no Nemo extension module is importable."
            ),
            "entry_points": [],
            "modules_checked": nemo_candidate_modules,
            "modules_available": [],
            "blocker_type": "missing_extension_distribution",
            "diagnostics": {
                "asreview_version": asreview_metadata.get("version"),
                "asreview_provided_extras": asreview_metadata.get("provided_extras", []),
                "nemo_extra_declared": nemo_extra_declared,
                "available_classifiers": available_classifiers,
            },
        }

    sentence_transformers_available = is_module_available("sentence_transformers")
    asreview_dory_installed = "asreview-dory" in installed_norm

    return {
        "python": {
            "version": sys.version,
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "installed_asreview_related_packages": asreview_dists,
        "asreview_metadata": asreview_metadata,
        "entry_points": entry_point_groups,
        "asreview_ai_model_configs": asreview_ai_model_configs,
        "nemo": nemo_status,
        "stronger_heavy_model_candidates": [
            {
                "name": "sentence-transformers/all-MiniLM-L6-v2 + linear classifier",
                "status": "available" if sentence_transformers_available else "blocked",
                "reason": (
                    "Dependency import check passed."
                    if sentence_transformers_available
                    else "Install optional heavy NLP deps to enable embedding-based benchmark path."
                ),
                "required_modules": ["sentence_transformers"],
            },
            {
                "name": "ASReview Dory extension models (elas_l2 / elas_h3)",
                "status": "available" if asreview_dory_installed else "blocked",
                "reason": (
                    "asreview-dory detected in environment."
                    if asreview_dory_installed
                    else "asreview-dory not installed; heavy transformer feature extractors unavailable."
                ),
                "required_packages": ["asreview-dory"],
            },
            {
                "name": "transformer cross-encoder rerankers",
                "status": "blocked",
                "reason": "GPU/large-model dependency footprint exceeds default repo constraints.",
            },
        ],
    }


def build_executable_specs(specs: Sequence[ModelSpec]) -> Tuple[List[ModelSpec], List[Dict[str, Any]]]:
    executable: List[ModelSpec] = []
    blocked: List[Dict[str, Any]] = []

    for spec in specs:
        if not spec.required_modules:
            executable.append(spec)
            continue

        missing = [m for m in spec.required_modules if not is_module_available(m)]
        if not missing:
            executable.append(spec)
            continue

        blocked.append(
            {
                "model_id": spec.model_id,
                "display_name": spec.display_name,
                "cohort": spec.cohort,
                "status": "blocked",
                "reason": (
                    "Missing optional dependency module(s): "
                    + ", ".join(missing)
                    + ". Install optional heavy NLP dependencies to enable this model."
                ),
                "blocker_type": "missing_optional_dependency",
                "missing_modules": missing,
            }
        )

    return executable, blocked


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


def build_specs() -> List[ModelSpec]:
    return [
        ModelSpec(
            model_id="baseline_lr_word_tfidf",
            display_name="Baseline LR (word TF-IDF)",
            cohort="baseline",
            lightweight=True,
            builder_key="baseline_lr_word_tfidf",
            notes="Current baseline from analysis/train_asreview.py",
        ),
        ModelSpec(
            model_id="improved_calibrated_svm_word_char",
            display_name="Improved Calibrated SVM (word+char TF-IDF)",
            cohort="improved",
            lightweight=True,
            builder_key="improved_calibrated_svm_word_char",
            notes="Current improved best from analysis/train_asreview_improved.py",
        ),
        ModelSpec(
            model_id="candidate_lr_word_char",
            display_name="Candidate LR (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_lr_word_char",
            notes="Adds character n-grams to linear baseline while retaining calibration-friendly LR.",
        ),
        ModelSpec(
            model_id="candidate_calibrated_sgd_word_char",
            display_name="Candidate Calibrated SGD (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_calibrated_sgd_word_char",
            notes="Calibrated margin-based linear model; good compromise between speed and rank quality.",
        ),
        ModelSpec(
            model_id="candidate_lr_elasticnet_word_char",
            display_name="Candidate ElasticNet LR (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_lr_elasticnet_word_char",
            notes="Elastic-net regularization can improve robustness on sparse noisy terms.",
        ),
        ModelSpec(
            model_id="candidate_linear_svc_isotonic_word_char",
            display_name="Candidate Calibrated LinearSVC isotonic (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_linear_svc_isotonic_word_char",
            notes="Alternative calibration strategy for high-recall ranking stability.",
        ),
        ModelSpec(
            model_id="candidate_lsa_lr",
            display_name="Candidate LSA+LR (SVD semantic projection)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_lsa_lr",
            notes="Low-dimensional semantic projection can improve signal-to-noise on small corpora.",
        ),
        ModelSpec(
            model_id="candidate_sgd_word_char",
            display_name="Candidate SGD log-loss (word+char TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_sgd_word_char",
            notes="Fast linear online learner suitable for frequent reruns.",
        ),
        ModelSpec(
            model_id="candidate_cnb_word_tfidf",
            display_name="Candidate ComplementNB (word TF-IDF)",
            cohort="candidate",
            lightweight=True,
            builder_key="candidate_cnb_word_tfidf",
            notes="Strong sparse-text baseline for imbalance, included for comparison.",
        ),
        ModelSpec(
            model_id="candidate_st_minilm_lr",
            display_name="Candidate MiniLM embedding + LR (sentence-transformers)",
            cohort="candidate",
            lightweight=False,
            builder_key="candidate_st_minilm_lr",
            notes="Optional embedding path for stronger semantic matching when heavier dependencies are available.",
            required_modules=("sentence_transformers",),
        ),
    ]


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

    all_specs = build_specs()
    env_info = detect_environment_model_options()
    specs, blocked_models = build_executable_specs(all_specs)

    if not specs:
        raise RuntimeError("No executable model specs found for benchmark run.")

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

    grouped = fold_df.groupby(["model_id", "display_name", "cohort", "lightweight"], as_index=False).agg(agg_map)
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
    if nemo_status.get("status") != "available":
        blocked_models.append(
            {
                "model_id": "asreview_nemo",
                "display_name": "ASReview Nemo",
                "cohort": "candidate",
                "status": "blocked",
                "reason": nemo_status.get("reason", "Unavailable in environment."),
                "blocker_type": nemo_status.get("blocker_type", "unavailable"),
            }
        )

    availability = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "environment": env_info,
        "evaluated_models": [
            {
                "model_id": s.model_id,
                "display_name": s.display_name,
                "cohort": s.cohort,
                "lightweight": s.lightweight,
                "notes": s.notes,
                "required_modules": list(s.required_modules),
            }
            for s in specs
        ],
        "declared_models": [
            {
                "model_id": s.model_id,
                "display_name": s.display_name,
                "cohort": s.cohort,
                "lightweight": s.lightweight,
                "notes": s.notes,
                "required_modules": list(s.required_modules),
            }
            for s in all_specs
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

    fastest = grouped.sort_values("fit_seconds_mean", ascending=True).iloc[0].to_dict()
    key_findings.append(
        (
            f"Fastest training model: {fastest['display_name']} "
            f"({fastest['fit_seconds_mean']:.3f}s mean fit time/fold)."
        )
    )

    if blocked_models:
        key_findings.append(
            f"Blocked model slots recorded: {len(blocked_models)} (see environment_model_availability.json)."
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
