# NLP Model Benchmark Report

## Protocol
- Input: `/home/kana/.openclaw/workspace/asys_comp/data/screening_input.xlsx`
- Split: RepeatedStratifiedKFold (splits=5, repeats=3, random_state=42)
- Usable rows: 300 / 300
- Class counts: {0: 257, 1: 43}

## Metrics
- AP, ROC-AUC, precision@k, recall@k, WSS@95
- Runtime notes: fit_seconds, score_seconds, estimated feature-space size

## Ranked results (higher AP first)
| model_id | display_name | cohort | lightweight | average_precision_mean | average_precision_std | roc_auc_mean | roc_auc_std | wss@95_mean | wss@95_std | precision@10_mean | precision@10_std | recall@10_mean | recall@10_std | precision@20_mean | precision@20_std | recall@20_mean | recall@20_std | precision@50_mean | precision@50_std | recall@50_mean | recall@50_std | fit_seconds_mean | fit_seconds_std | score_seconds_mean | score_seconds_std | n_features_mean | n_folds | rank |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| improved_calibrated_svm_word_char | Improved Calibrated SVM (word+char TF-IDF) | improved | True | 0.568872 | 0.098562 | 0.820724 | 0.067060 | 0.315556 | 0.172340 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.313333 | 0.054989 | 0.732407 | 0.142557 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 1.047006 | 0.023800 | 0.217301 | 0.016589 | 130219.000000 | 15 | 1 |
| candidate_lr_word_char | Candidate LR (word+char TF-IDF) | candidate | True | 0.568236 | 0.098111 | 0.821285 | 0.062474 | 0.312222 | 0.167908 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.306667 | 0.041690 | 0.716667 | 0.112074 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 1.008455 | 0.028931 | 0.216456 | 0.015053 | 130219.000000 | 15 | 2 |
| candidate_linear_svc_isotonic_word_char | Candidate Calibrated LinearSVC isotonic (word+char TF-IDF) | candidate | True | 0.546887 | 0.105191 | 0.809167 | 0.072443 | 0.280000 | 0.210178 | 0.500000 | 0.084515 | 0.584259 | 0.111417 | 0.313333 | 0.054989 | 0.730556 | 0.134432 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 1.019621 | 0.024592 | 0.179209 | 0.023711 | 130219.000000 | 15 | 3 |
| candidate_sgd_word_char | Candidate SGD log-loss (word+char TF-IDF) | candidate | True | 0.532220 | 0.113923 | 0.778054 | 0.076920 | 0.176667 | 0.172148 | 0.466667 | 0.089974 | 0.545370 | 0.117555 | 0.290000 | 0.054116 | 0.676852 | 0.134193 | 0.161333 | 0.014075 | 0.938889 | 0.072701 | 1.006594 | 0.026242 | 0.211510 | 0.017151 | 130219.000000 | 15 | 4 |
| candidate_calibrated_sgd_word_char | Candidate Calibrated SGD (word+char TF-IDF) | candidate | True | 0.530617 | 0.130560 | 0.786808 | 0.086315 | 0.256667 | 0.196275 | 0.473333 | 0.096115 | 0.551852 | 0.115425 | 0.290000 | 0.060356 | 0.675000 | 0.143072 | 0.166667 | 0.009759 | 0.970370 | 0.050860 | 1.039111 | 0.049190 | 0.227930 | 0.014914 | 130219.000000 | 15 | 5 |
| candidate_lr_elasticnet_word_char | Candidate ElasticNet LR (word+char TF-IDF) | candidate | True | 0.527398 | 0.115021 | 0.797000 | 0.056610 | 0.245556 | 0.153977 | 0.446667 | 0.091548 | 0.519444 | 0.101085 | 0.300000 | 0.032733 | 0.700926 | 0.095919 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 8.099051 | 1.645458 | 0.169205 | 0.017471 | 130219.000000 | 15 | 6 |
| candidate_lsa_lr | Candidate LSA+LR (SVD semantic projection) | candidate | True | 0.501458 | 0.074465 | 0.796960 | 0.058421 | 0.254444 | 0.174854 | 0.440000 | 0.098561 | 0.512037 | 0.114755 | 0.310000 | 0.050709 | 0.723148 | 0.126148 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 2.692514 | 0.078647 | 0.051867 | 0.010961 | 54451.200000 | 15 | 7 |
| baseline_lr_word_tfidf | Baseline LR (word TF-IDF) | baseline | True | 0.471764 | 0.129379 | 0.785541 | 0.054056 | 0.257778 | 0.158473 | 0.386667 | 0.130201 | 0.452778 | 0.159727 | 0.290000 | 0.043095 | 0.676852 | 0.106355 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 0.167271 | 0.012886 | 0.040499 | 0.007607 | 10078.333333 | 15 | 8 |
| candidate_cnb_word_tfidf | Candidate ComplementNB (word TF-IDF) | candidate | True | 0.289596 | 0.106415 | 0.595775 | 0.037975 | 0.077778 | 0.081569 | 0.246667 | 0.083381 | 0.285185 | 0.092109 | 0.183333 | 0.036187 | 0.425926 | 0.076554 | 0.150667 | 0.018310 | 0.876852 | 0.102717 | 0.221057 | 0.005357 | 0.036400 | 0.003388 | 54451.200000 | 15 | 9 |

## Blocked models
| model_id | reason |
|---|---|
| candidate_st_minilm_lr | Missing optional dependency module(s): sentence_transformers. Install optional heavy NLP dependencies to enable this model. |
| asreview_nemo | ASReview Nemo is unavailable: no `nemo` classifier entry point is registered, ASReview 2.2 does not expose a `nemo` extra, and no Nemo extension module is importable. |

## Key findings
- Top model by AP: Improved Calibrated SVM (word+char TF-IDF) (AP 0.569 ± 0.099, WSS@95 0.316).
- Runner-up: Candidate LR (word+char TF-IDF) (AP 0.568 ± 0.098).
- Fastest training model: Baseline LR (word TF-IDF) (0.167s mean fit time/fold).
- Blocked model slots recorded: 2 (see environment_model_availability.json).
