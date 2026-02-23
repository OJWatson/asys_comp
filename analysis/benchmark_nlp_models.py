#!/usr/bin/env python3
"""Benchmark baseline/improved/new NLP models for abstract screening.

This script is intentionally self-contained and uses reproducible,
lightweight defaults while supporting optional heavier staged models.

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
from scipy.sparse import csr_matrix, issparse
from sklearn.base import BaseEstimator, TransformerMixin
from sklearn.calibration import CalibratedClassifierCV
from sklearn.decomposition import TruncatedSVD
from sklearn.exceptions import NotFittedError
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.metrics import average_precision_score, roc_auc_score
from sklearn.model_selection import RepeatedStratifiedKFold
from sklearn.naive_bayes import ComplementNB
from sklearn.neural_network import MLPClassifier
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
DORY_NEURAL_CLASSIFIERS = {"dynamic-nn", "nn-2-layer", "warmstart-nn"}


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    display_name: str
    cohort: str
    stage: str
    builder_key: str
    notes: str
    model_source: str = "core"
    dory_classifier: Optional[str] = None
    required_modules: Tuple[str, ...] = ()

    @property
    def lightweight(self) -> bool:
        return self.stage == "lightweight"


class DenseMatrixTransformer(BaseEstimator, TransformerMixin):
    """Convert sparse feature matrices to dense float32 arrays."""

    def fit(self, X: Any, y: Optional[np.ndarray] = None) -> "DenseMatrixTransformer":
        return self

    def transform(self, X: Any) -> np.ndarray:
        if issparse(X):
            X = X.toarray()
        return np.asarray(X, dtype=np.float32)


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


def _norm_dist_name(name: str) -> str:
    return name.strip().lower().replace("_", "-")


def _collect_asreview_entry_points() -> Tuple[Dict[str, List[Dict[str, str]]], Dict[str, Any], Dict[str, Any]]:
    tracked_groups = {
        "asreview.models",
        "asreview.models.classifiers",
        "asreview.models.feature_extractors",
        "asreview.models.queriers",
        "asreview.models.balancers",
    }

    grouped: Dict[str, List[Dict[str, str]]] = {}
    dory_classifier_eps: Dict[str, Any] = {}
    dory_feature_eps: Dict[str, Any] = {}

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
    if classifier_name in DORY_NEURAL_CLASSIFIERS:
        return {
            "epochs": 1,
            "batch_size": 4,
            "verbose": 0,
        }
    return {"random_state": 42}


def _probe_dory_classifier(classifier_name: str, dory_classifier_eps: Dict[str, Any]) -> Dict[str, Any]:
    probe: Dict[str, Any] = {
        "classifier": classifier_name,
        "status": "blocked",
        "probe": "mini_fit_predict_proba",
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

    if classifier_name in DORY_NEURAL_CLASSIFIERS:
        X_probe = np.asarray(
            [
                [1.0, 0.0, 0.0, 0.1],
                [0.8, 0.2, 0.0, 0.2],
                [0.0, 1.0, 0.2, 0.0],
                [0.0, 0.9, 0.1, 0.0],
                [0.0, 0.0, 1.0, 0.4],
                [0.1, 0.0, 0.8, 0.5],
            ],
            dtype=np.float32,
        )
        probe["input_representation"] = "dense"
    else:
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
        probe["input_representation"] = "sparse"

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
                "reason": "Entry point loads and mini probe fit/predict succeeds.",
            }
        )
        return probe
    except Exception as exc:
        probe.update(
            {
                "reason": f"Probe failed: {type(exc).__name__}: {exc}",
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
    available_modules = [m for m in nemo_candidate_modules if is_module_available(m)]

    available_classifiers = [r["name"] for r in entry_point_groups.get("asreview.models.classifiers", [])]
    nemo_classifier_present = any(name.lower() == "nemo" for name in available_classifiers)

    if nemo_classifier_present or possible_nemo_ep or available_modules:
        nemo_status: Dict[str, Any] = {
            "status": "available",
            "reason": "Detected Nemo-like classifier/module in current environment.",
            "entry_points": sorted(possible_nemo_ep),
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
                "available_classifiers": available_classifiers,
            },
        }

    sentence_transformers_available = is_module_available("sentence_transformers")

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
        "dory": dory_status,
        "dory_probe_index": dory_probe_by_name,
        "nemo": nemo_status,
        "stronger_heavy_model_candidates": [
            {
                "name": "sentence-transformers/all-MiniLM-L6-v2 + linear / mlp",
                "status": "available" if sentence_transformers_available else "blocked",
                "reason": (
                    "Dependency import check passed."
                    if sentence_transformers_available
                    else "Install optional heavy NLP deps to enable embedding-based benchmark paths."
                ),
                "required_modules": ["sentence_transformers"],
            },
            {
                "name": "ASReview Dory extension models (xgboost/adaboost/dynamic-nn/nn-2-layer/warmstart-nn)",
                "status": "available" if dory_version else "blocked",
                "reason": (
                    "asreview-dory detected in environment."
                    if dory_version
                    else "asreview-dory not installed; Dory extension classifiers unavailable."
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


def build_specs() -> List[ModelSpec]:
    return [
        ModelSpec(
            model_id="baseline_lr_word_tfidf",
            display_name="Baseline LR (word TF-IDF)",
            cohort="baseline",
            stage="lightweight",
            builder_key="baseline_lr_word_tfidf",
            notes="Current baseline from analysis/train_asreview.py",
        ),
        ModelSpec(
            model_id="improved_calibrated_svm_word_char",
            display_name="Improved Calibrated SVM (word+char TF-IDF)",
            cohort="improved",
            stage="lightweight",
            builder_key="improved_calibrated_svm_word_char",
            notes="Current improved best from analysis/train_asreview_improved.py",
        ),
        ModelSpec(
            model_id="candidate_lr_word_char",
            display_name="Candidate LR (word+char TF-IDF)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_lr_word_char",
            notes="Adds character n-grams to linear baseline while retaining calibration-friendly LR.",
        ),
        ModelSpec(
            model_id="candidate_calibrated_sgd_word_char",
            display_name="Candidate Calibrated SGD (word+char TF-IDF)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_calibrated_sgd_word_char",
            notes="Calibrated margin-based linear model; good compromise between speed and rank quality.",
        ),
        ModelSpec(
            model_id="candidate_lr_elasticnet_word_char",
            display_name="Candidate ElasticNet LR (word+char TF-IDF)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_lr_elasticnet_word_char",
            notes="Elastic-net regularization can improve robustness on sparse noisy terms.",
        ),
        ModelSpec(
            model_id="candidate_linear_svc_isotonic_word_char",
            display_name="Candidate Calibrated LinearSVC isotonic (word+char TF-IDF)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_linear_svc_isotonic_word_char",
            notes="Alternative calibration strategy for high-recall ranking stability.",
        ),
        ModelSpec(
            model_id="candidate_lsa_lr",
            display_name="Candidate LSA+LR (SVD semantic projection)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_lsa_lr",
            notes="Low-dimensional semantic projection can improve signal-to-noise on small corpora.",
        ),
        ModelSpec(
            model_id="candidate_sgd_word_char",
            display_name="Candidate SGD log-loss (word+char TF-IDF)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_sgd_word_char",
            notes="Fast linear online learner suitable for frequent reruns.",
        ),
        ModelSpec(
            model_id="candidate_cnb_word_tfidf",
            display_name="Candidate ComplementNB (word TF-IDF)",
            cohort="candidate",
            stage="lightweight",
            builder_key="candidate_cnb_word_tfidf",
            notes="Strong sparse-text baseline for imbalance, included for comparison.",
        ),
        ModelSpec(
            model_id="candidate_mlp_lsa",
            display_name="Candidate MLP (TF-IDF→SVD dense)",
            cohort="candidate",
            stage="heavy",
            builder_key="candidate_mlp_lsa",
            notes="Practical neural baseline on dense semantic projection.",
        ),
        ModelSpec(
            model_id="candidate_st_minilm_lr",
            display_name="Candidate MiniLM embedding + LR (sentence-transformers)",
            cohort="candidate",
            stage="heavy",
            builder_key="candidate_st_minilm_lr",
            notes="Embedding path for stronger semantic matching when heavier dependencies are available.",
            required_modules=("sentence_transformers",),
        ),
        ModelSpec(
            model_id="candidate_st_minilm_mlp",
            display_name="Candidate MiniLM embedding + MLP",
            cohort="candidate",
            stage="heavy",
            builder_key="candidate_st_minilm_mlp",
            notes="Neural baseline over MiniLM dense embeddings.",
            required_modules=("sentence_transformers",),
        ),
        ModelSpec(
            model_id="dory_xgboost_word_tfidf",
            display_name="Dory XGBoost (word TF-IDF)",
            cohort="dory",
            stage="heavy",
            builder_key="dory_xgboost_word_tfidf",
            notes="ASReview Dory XGBoost benchmarked on sparse TF-IDF for direct comparability.",
            model_source="dory",
            dory_classifier="xgboost",
            required_modules=("asreviewcontrib.dory",),
        ),
        ModelSpec(
            model_id="dory_adaboost_word_tfidf",
            display_name="Dory AdaBoost (word TF-IDF)",
            cohort="dory",
            stage="heavy",
            builder_key="dory_adaboost_word_tfidf",
            notes="ASReview Dory AdaBoost benchmarked on sparse TF-IDF for direct comparability.",
            model_source="dory",
            dory_classifier="adaboost",
            required_modules=("asreviewcontrib.dory",),
        ),
        ModelSpec(
            model_id="dory_dynamic_nn_dense_lsa",
            display_name="Dory Dynamic-NN (TF-IDF→SVD dense)",
            cohort="dory",
            stage="heavy",
            builder_key="dory_dynamic_nn_dense_lsa",
            notes="Dory dynamic neural net on dense semantic projection (feasible CPU baseline).",
            model_source="dory",
            dory_classifier="dynamic-nn",
            required_modules=("asreviewcontrib.dory",),
        ),
        ModelSpec(
            model_id="dory_nn_2_layer_dense_lsa",
            display_name="Dory NN-2-layer (TF-IDF→SVD dense)",
            cohort="dory",
            stage="heavy",
            builder_key="dory_nn_2_layer_dense_lsa",
            notes="Dory two-layer neural net on dense semantic projection.",
            model_source="dory",
            dory_classifier="nn-2-layer",
            required_modules=("asreviewcontrib.dory",),
        ),
        ModelSpec(
            model_id="dory_warmstart_nn_dense_lsa",
            display_name="Dory Warmstart-NN (TF-IDF→SVD dense)",
            cohort="dory",
            stage="heavy",
            builder_key="dory_warmstart_nn_dense_lsa",
            notes="Dory warm-start neural net on dense semantic projection.",
            model_source="dory",
            dory_classifier="warmstart-nn",
            required_modules=("asreviewcontrib.dory",),
        ),
    ]


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

    if spec.builder_key == "candidate_cnb_word_tfidf":
        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("clf", ComplementNB(alpha=0.5, norm=False)),
            ]
        )

    if spec.builder_key == "candidate_mlp_lsa":
        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("svd", TruncatedSVD(n_components=256, random_state=random_state)),
                ("norm", Normalizer(copy=False)),
                (
                    "clf",
                    MLPClassifier(
                        hidden_layer_sizes=(128, 64),
                        activation="relu",
                        alpha=1e-4,
                        learning_rate_init=1e-3,
                        max_iter=220,
                        early_stopping=True,
                        random_state=random_state,
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

    if spec.builder_key == "candidate_st_minilm_mlp":
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
                    MLPClassifier(
                        hidden_layer_sizes=(256, 64),
                        activation="relu",
                        alpha=1e-4,
                        learning_rate_init=1e-3,
                        max_iter=220,
                        early_stopping=True,
                        random_state=random_state,
                    ),
                ),
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
                        n_estimators=160,
                        max_depth=6,
                        learning_rate=0.15,
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
                        n_estimators=160,
                        learning_rate=0.8,
                        random_state=random_state,
                    ),
                ),
            ]
        )

    if spec.builder_key == "dory_dynamic_nn_dense_lsa":
        from asreviewcontrib.dory.classifiers.neural_networks import DynamicNNClassifier

        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("svd", TruncatedSVD(n_components=256, random_state=random_state)),
                ("norm", Normalizer(copy=False)),
                ("dense", DenseMatrixTransformer()),
                (
                    "clf",
                    DynamicNNClassifier(
                        epochs=10,
                        batch_size=16,
                        verbose=0,
                    ),
                ),
            ]
        )

    if spec.builder_key == "dory_nn_2_layer_dense_lsa":
        from asreviewcontrib.dory.classifiers.neural_networks import NN2LayerClassifier

        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("svd", TruncatedSVD(n_components=256, random_state=random_state)),
                ("norm", Normalizer(copy=False)),
                ("dense", DenseMatrixTransformer()),
                (
                    "clf",
                    NN2LayerClassifier(
                        epochs=10,
                        batch_size=16,
                        verbose=0,
                    ),
                ),
            ]
        )

    if spec.builder_key == "dory_warmstart_nn_dense_lsa":
        from asreviewcontrib.dory.classifiers.neural_networks import WarmStartNNClassifier

        return Pipeline(
            steps=[
                ("tfidf", _word_tfidf_vectorizer()),
                ("svd", TruncatedSVD(n_components=256, random_state=random_state)),
                ("norm", Normalizer(copy=False)),
                ("dense", DenseMatrixTransformer()),
                (
                    "clf",
                    WarmStartNNClassifier(
                        epochs=10,
                        batch_size=16,
                        verbose=0,
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
        return 1.0 / (1.0 + np.exp(-decision))

    raise RuntimeError("Model has neither predict_proba nor decision_function")


def estimate_feature_count(model: Pipeline) -> Optional[int]:
    try:
        if "tfidf" in model.named_steps:
            vec = model.named_steps["tfidf"]
            vocab = getattr(vec, "vocabulary_", None)
            if vocab is not None:
                return int(len(vocab))

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

        if "svd" in model.named_steps:
            n_components = getattr(model.named_steps["svd"], "n_components", None)
            if n_components is not None:
                return int(n_components)

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


def _stage_splits(
    spec: ModelSpec,
    *,
    lightweight_splits: int,
    lightweight_repeats: int,
    heavy_splits: int,
    heavy_repeats: int,
) -> Tuple[int, int]:
    if spec.stage == "lightweight":
        return int(lightweight_splits), int(lightweight_repeats)
    return int(heavy_splits), int(heavy_repeats)


def _status_row(spec: ModelSpec) -> Dict[str, Any]:
    return {
        "model_id": spec.model_id,
        "display_name": spec.display_name,
        "cohort": spec.cohort,
        "model_source": spec.model_source,
        "dory_classifier": spec.dory_classifier or "",
        "stage": spec.stage,
        "lightweight": spec.lightweight,
        "status": "pending",
        "reason": "",
        "blocker_type": "",
        "n_folds_planned": 0,
        "n_folds_completed": 0,
        "runtime_seconds": 0.0,
    }


def _round_or_nan(v: float, digits: int = 6) -> float:
    if isinstance(v, float) and math.isnan(v):
        return float("nan")
    return round(float(v), digits)


def run_benchmark(
    *,
    input_path: Path,
    output_dir: Path,
    lightweight_splits: int,
    lightweight_repeats: int,
    heavy_splits: int,
    heavy_repeats: int,
    random_state: int,
    disable_heavy_stage: bool,
    max_heavy_models: Optional[int],
    max_total_runtime_seconds: Optional[float],
    per_model_runtime_seconds: Optional[float],
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

    if len(clean) < max(20, lightweight_splits * 2):
        raise ValueError(
            f"Too few usable rows after cleaning ({len(clean)} of {original_n}) for CV benchmark."
        )

    X = clean["_text"].values
    y_arr = clean["_label"].values

    class_counts = {int(k): int(v) for k, v in zip(*np.unique(y_arr, return_counts=True))}
    if len(class_counts) < 2:
        raise ValueError(f"Need both classes after mapping; got class_counts={class_counts}")

    env_info = detect_environment_model_options()
    all_specs = build_specs()

    combo_rows: List[Dict[str, Any]] = []
    for spec in all_specs:
        row = _status_row(spec)

        if spec.stage == "heavy" and disable_heavy_stage:
            row.update(
                {
                    "status": "skipped",
                    "reason": "Heavy stage disabled via runtime controls.",
                    "blocker_type": "heavy_stage_disabled",
                }
            )
            combo_rows.append(row)
            continue

        missing = [m for m in spec.required_modules if not is_module_available(m)]
        if missing:
            row.update(
                {
                    "status": "skipped",
                    "reason": (
                        "Missing optional dependency module(s): "
                        + ", ".join(missing)
                        + ". Install optional heavy NLP dependencies to enable this model."
                    ),
                    "blocker_type": "missing_optional_dependency",
                }
            )
            combo_rows.append(row)
            continue

        if spec.model_source == "dory" and spec.dory_classifier:
            probe = (env_info.get("dory_probe_index") or {}).get(spec.dory_classifier)
            if probe is None:
                row.update(
                    {
                        "status": "skipped",
                        "reason": "No Dory probe result found for this classifier.",
                        "blocker_type": "dory_probe_missing",
                    }
                )
                combo_rows.append(row)
                continue
            if probe.get("status") != "available":
                row.update(
                    {
                        "status": "skipped",
                        "reason": probe.get("reason", "Unavailable in environment."),
                        "blocker_type": probe.get("blocker_type", "dory_probe_blocked"),
                    }
                )
                combo_rows.append(row)
                continue

        row["status"] = "queued"
        combo_rows.append(row)

    queued_heavy_idx = [i for i, r in enumerate(combo_rows) if r["status"] == "queued" and r["stage"] == "heavy"]
    if max_heavy_models is not None and max_heavy_models >= 0 and len(queued_heavy_idx) > max_heavy_models:
        for idx in queued_heavy_idx[max_heavy_models:]:
            combo_rows[idx].update(
                {
                    "status": "skipped",
                    "reason": f"Skipped by runtime control: max_heavy_models={max_heavy_models}.",
                    "blocker_type": "max_heavy_models_limit",
                }
            )

    splits_cache: Dict[Tuple[int, int], List[Tuple[np.ndarray, np.ndarray]]] = {}
    all_fold_rows: List[Dict[str, Any]] = []
    benchmark_start = time.perf_counter()

    for combo_row in combo_rows:
        if combo_row["status"] != "queued":
            continue

        spec = next(s for s in all_specs if s.model_id == combo_row["model_id"])

        elapsed_total = time.perf_counter() - benchmark_start
        if max_total_runtime_seconds is not None and elapsed_total > max_total_runtime_seconds:
            combo_row.update(
                {
                    "status": "skipped",
                    "reason": (
                        f"Skipped by runtime control: total runtime budget exceeded "
                        f"({elapsed_total:.1f}s > {max_total_runtime_seconds:.1f}s)."
                    ),
                    "blocker_type": "total_runtime_budget_exceeded",
                }
            )
            continue

        n_splits, n_repeats = _stage_splits(
            spec,
            lightweight_splits=lightweight_splits,
            lightweight_repeats=lightweight_repeats,
            heavy_splits=heavy_splits,
            heavy_repeats=heavy_repeats,
        )
        cache_key = (n_splits, n_repeats)
        if cache_key not in splits_cache:
            cv = RepeatedStratifiedKFold(n_splits=n_splits, n_repeats=n_repeats, random_state=random_state)
            splits_cache[cache_key] = list(cv.split(X, y_arr))

        fold_splits = splits_cache[cache_key]
        combo_row["n_folds_planned"] = int(len(fold_splits))

        model_fold_rows: List[Dict[str, Any]] = []
        model_start = time.perf_counter()

        try:
            for fold_idx, (train_idx, test_idx) in enumerate(fold_splits, start=1):
                if per_model_runtime_seconds is not None and (time.perf_counter() - model_start) > per_model_runtime_seconds:
                    raise TimeoutError(
                        f"Per-model runtime budget exceeded ({per_model_runtime_seconds:.1f}s)."
                    )

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

                model_fold_rows.append(
                    {
                        "model_id": spec.model_id,
                        "display_name": spec.display_name,
                        "cohort": spec.cohort,
                        "model_source": spec.model_source,
                        "dory_classifier": spec.dory_classifier or "",
                        "stage": spec.stage,
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

            combo_row.update(
                {
                    "status": "succeeded",
                    "reason": "",
                    "blocker_type": "",
                    "n_folds_completed": int(len(model_fold_rows)),
                    "runtime_seconds": float(time.perf_counter() - model_start),
                }
            )
            all_fold_rows.extend(model_fold_rows)

        except Exception as exc:
            combo_row.update(
                {
                    "status": "failed",
                    "reason": f"{type(exc).__name__}: {exc}",
                    "blocker_type": "runtime_failure",
                    "n_folds_completed": int(len(model_fold_rows)),
                    "runtime_seconds": float(time.perf_counter() - model_start),
                }
            )

    combo_df = pd.DataFrame(combo_rows).sort_values(["stage", "cohort", "model_id"]).reset_index(drop=True)
    combo_csv = output_dir / "model_combo_attempt_matrix.csv"
    combo_json = output_dir / "model_combo_attempt_matrix.json"
    combo_df.to_csv(combo_csv, index=False)
    combo_json.write_text(json.dumps(combo_df.to_dict(orient="records"), indent=2), encoding="utf-8")

    if not all_fold_rows:
        raise RuntimeError("No model completed successfully; benchmark has no fold metrics.")

    fold_df = pd.DataFrame(all_fold_rows)
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
        ["model_id", "display_name", "cohort", "model_source", "dory_classifier", "stage", "lightweight"],
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

    status_counts = combo_df["status"].value_counts().to_dict()
    combo_counts = {
        "attempted": int(status_counts.get("succeeded", 0) + status_counts.get("failed", 0)),
        "succeeded": int(status_counts.get("succeeded", 0)),
        "failed": int(status_counts.get("failed", 0)),
        "skipped": int(status_counts.get("skipped", 0)),
    }

    blocked_models = []
    for row in combo_rows:
        if row["status"] in {"skipped", "failed"}:
            blocked_models.append(
                {
                    "model_id": row["model_id"],
                    "display_name": row["display_name"],
                    "cohort": row["cohort"],
                    "model_source": row["model_source"],
                    "stage": row["stage"],
                    "status": row["status"],
                    "reason": row["reason"],
                    "blocker_type": row["blocker_type"],
                }
            )

    nemo_status = env_info.get("nemo", {})
    if nemo_status.get("status") != "available":
        blocked_models.append(
            {
                "model_id": "asreview_nemo",
                "display_name": "ASReview Nemo",
                "cohort": "candidate",
                "model_source": "nemo",
                "stage": "heavy",
                "status": "blocked",
                "reason": nemo_status.get("reason", "Unavailable in environment."),
                "blocker_type": nemo_status.get("blocker_type", "unavailable"),
            }
        )

    availability = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "environment": {k: v for k, v in env_info.items() if k != "dory_probe_index"},
        "declared_models": [
            {
                "model_id": s.model_id,
                "display_name": s.display_name,
                "cohort": s.cohort,
                "model_source": s.model_source,
                "dory_classifier": s.dory_classifier,
                "stage": s.stage,
                "lightweight": s.lightweight,
                "notes": s.notes,
                "required_modules": list(s.required_modules),
            }
            for s in all_specs
        ],
        "evaluated_models": [
            {
                "model_id": r["model_id"],
                "display_name": r["display_name"],
                "cohort": r["cohort"],
                "model_source": r["model_source"],
                "stage": r["stage"],
                "n_folds": r["n_folds"],
            }
            for r in grouped.to_dict(orient="records")
        ],
        "combo_matrix_counts": combo_counts,
        "combo_matrix_path": str(combo_csv),
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
                    f"Best Dory vs best non-Dory AP gap: {ap_gap:+.3f} "
                    f"({best_dory['display_name']} vs {best_non_dory['display_name']})."
                )
            )

    neural_mask = grouped["model_id"].astype(str).str.contains("nn|mlp", case=False, regex=True)
    neural_rows = grouped[neural_mask].copy()
    if not neural_rows.empty:
        best_neural = neural_rows.sort_values("average_precision_mean", ascending=False).iloc[0].to_dict()
        key_findings.append(
            (
                f"Best neural model: {best_neural['display_name']} "
                f"(AP {best_neural['average_precision_mean']:.3f}, "
                f"recall@20 {best_neural['recall@20_mean']:.3f}, "
                f"precision@20 {best_neural['precision@20_mean']:.3f})."
            )
        )

    fastest = grouped.sort_values("fit_seconds_mean", ascending=True).iloc[0].to_dict()
    key_findings.append(
        (
            f"Fastest training model: {fastest['display_name']} "
            f"({fastest['fit_seconds_mean']:.3f}s mean fit time/fold)."
        )
    )

    key_findings.append(
        (
            "Combo sweep status: "
            f"attempted={combo_counts['attempted']}, "
            f"succeeded={combo_counts['succeeded']}, "
            f"failed={combo_counts['failed']}, "
            f"skipped={combo_counts['skipped']}."
        )
    )

    summary_json = {
        "generated_at": pd.Timestamp.utcnow().isoformat(),
        "input": str(input_path),
        "split_protocol": {
            "method": "RepeatedStratifiedKFold",
            "lightweight": {
                "n_splits": lightweight_splits,
                "n_repeats": lightweight_repeats,
            },
            "heavy": {
                "n_splits": heavy_splits,
                "n_repeats": heavy_repeats,
                "disabled": disable_heavy_stage,
                "max_heavy_models": max_heavy_models,
            },
            "runtime_controls": {
                "max_total_runtime_seconds": max_total_runtime_seconds,
                "per_model_runtime_seconds": per_model_runtime_seconds,
            },
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
        "combo_matrix_counts": combo_counts,
        "combo_matrix": combo_df.to_dict(orient="records"),
        "dory_models_benchmarked": sorted(
            [r["model_id"] for r in grouped.to_dict(orient="records") if str(r.get("cohort")) == "dory"]
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
        (
            "- Lightweight stage: "
            f"RepeatedStratifiedKFold(splits={lightweight_splits}, repeats={lightweight_repeats})"
        ),
        (
            "- Heavy stage: "
            + (
                "disabled"
                if disable_heavy_stage
                else f"RepeatedStratifiedKFold(splits={heavy_splits}, repeats={heavy_repeats})"
            )
        ),
        f"- Runtime control: max_total_runtime_seconds={max_total_runtime_seconds}",
        f"- Runtime control: per_model_runtime_seconds={per_model_runtime_seconds}",
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
        "## Combo sweep matrix",
        dataframe_to_markdown(
            combo_df[
                [
                    "model_id",
                    "cohort",
                    "stage",
                    "status",
                    "n_folds_planned",
                    "n_folds_completed",
                    "runtime_seconds",
                    "reason",
                ]
            ]
        ),
        "",
    ]

    if blocked_models:
        report_lines.extend(
            [
                "## Blocked / failed models",
                "| model_id | status | reason |",
                "|---|---|---|",
            ]
        )
        for b in blocked_models:
            report_lines.append(f"| {b['model_id']} | {b['status']} | {b['reason']} |")
        report_lines.append("")

    report_lines.extend(["## Key findings"] + [f"- {k}" for k in key_findings])
    report_lines.append("")

    report_path = output_dir / "MODEL_BENCHMARK_REPORT.md"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return {
        "summary_csv": str(summary_path),
        "summary_json": str(summary_json_path),
        "fold_csv": str(fold_path),
        "combo_csv": str(combo_csv),
        "combo_json": str(combo_json),
        "availability_json": str(availability_path),
        "report_md": str(report_path),
        "winner": top.get("model_id"),
        "combo_matrix_counts": combo_counts,
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
    parser.add_argument("--lightweight-splits", type=int, default=5)
    parser.add_argument("--lightweight-repeats", type=int, default=3)
    parser.add_argument("--heavy-splits", type=int, default=3)
    parser.add_argument("--heavy-repeats", type=int, default=1)
    parser.add_argument("--random-state", type=int, default=42)
    parser.add_argument("--disable-heavy-stage", action="store_true")
    parser.add_argument(
        "--max-heavy-models",
        type=int,
        default=8,
        help="Max number of heavy-stage models to execute. Set <0 for unlimited.",
    )
    parser.add_argument(
        "--max-total-runtime-seconds",
        type=float,
        default=5400.0,
        help="Total runtime budget in seconds for the benchmark run.",
    )
    parser.add_argument(
        "--per-model-runtime-seconds",
        type=float,
        default=900.0,
        help="Runtime budget in seconds per model across all its folds.",
    )
    args = parser.parse_args()

    max_heavy_models = None if args.max_heavy_models is not None and args.max_heavy_models < 0 else args.max_heavy_models
    max_total_runtime_seconds = (
        None if args.max_total_runtime_seconds is not None and args.max_total_runtime_seconds <= 0 else args.max_total_runtime_seconds
    )
    per_model_runtime_seconds = (
        None if args.per_model_runtime_seconds is not None and args.per_model_runtime_seconds <= 0 else args.per_model_runtime_seconds
    )

    result = run_benchmark(
        input_path=args.input,
        output_dir=args.output_dir,
        lightweight_splits=args.lightweight_splits,
        lightweight_repeats=args.lightweight_repeats,
        heavy_splits=args.heavy_splits,
        heavy_repeats=args.heavy_repeats,
        random_state=args.random_state,
        disable_heavy_stage=args.disable_heavy_stage,
        max_heavy_models=max_heavy_models,
        max_total_runtime_seconds=max_total_runtime_seconds,
        per_model_runtime_seconds=per_model_runtime_seconds,
    )
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
