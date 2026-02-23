# NLP Model Benchmark Report

## Protocol
- Input: `/home/kana/.openclaw/workspace/asys_comp_bench_clean/data/screening_input.xlsx`
- Lightweight stage: RepeatedStratifiedKFold(splits=5, repeats=3)
- Heavy stage: RepeatedStratifiedKFold(splits=3, repeats=1)
- Runtime control: max_total_runtime_seconds=5400.0
- Runtime control: per_model_runtime_seconds=900.0
- Usable rows: 300 / 300
- Class counts: {0: 257, 1: 43}

## Metrics
- AP, ROC-AUC, precision@k, recall@k, WSS@95
- Runtime notes: fit_seconds, score_seconds, estimated feature-space size

## Ranked results (higher AP first)
| model_id | display_name | cohort | model_source | dory_classifier | stage | lightweight | average_precision_mean | average_precision_std | roc_auc_mean | roc_auc_std | wss@95_mean | wss@95_std | precision@10_mean | precision@10_std | recall@10_mean | recall@10_std | precision@20_mean | precision@20_std | recall@20_mean | recall@20_std | precision@50_mean | precision@50_std | recall@50_mean | recall@50_std | fit_seconds_mean | fit_seconds_std | score_seconds_mean | score_seconds_std | n_features_mean | n_folds | rank |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| improved_calibrated_svm_word_char | Improved Calibrated SVM (word+char TF-IDF) | improved | core |  | lightweight | True | 0.568872 | 0.098562 | 0.820724 | 0.067060 | 0.315556 | 0.172340 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.313333 | 0.054989 | 0.732407 | 0.142557 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 1.052962 | 0.062132 | 0.220053 | 0.016958 | 130219.000000 | 15 | 1 |
| candidate_lr_word_char | Candidate LR (word+char TF-IDF) | candidate | core |  | lightweight | True | 0.568236 | 0.098111 | 0.821285 | 0.062474 | 0.312222 | 0.167908 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.306667 | 0.041690 | 0.716667 | 0.112074 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 1.067230 | 0.056971 | 0.227107 | 0.016178 | 130219.000000 | 15 | 2 |
| candidate_linear_svc_isotonic_word_char | Candidate Calibrated LinearSVC isotonic (word+char TF-IDF) | candidate | core |  | lightweight | True | 0.546887 | 0.105191 | 0.809167 | 0.072443 | 0.280000 | 0.210178 | 0.500000 | 0.084515 | 0.584259 | 0.111417 | 0.313333 | 0.054989 | 0.730556 | 0.134432 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 1.035507 | 0.030050 | 0.177125 | 0.017151 | 130219.000000 | 15 | 3 |
| candidate_sgd_word_char | Candidate SGD log-loss (word+char TF-IDF) | candidate | core |  | lightweight | True | 0.532220 | 0.113923 | 0.778054 | 0.076920 | 0.176667 | 0.172148 | 0.466667 | 0.089974 | 0.545370 | 0.117555 | 0.290000 | 0.054116 | 0.676852 | 0.134193 | 0.161333 | 0.014075 | 0.938889 | 0.072701 | 0.961744 | 0.022143 | 0.207688 | 0.015323 | 130219.000000 | 15 | 4 |
| candidate_calibrated_sgd_word_char | Candidate Calibrated SGD (word+char TF-IDF) | candidate | core |  | lightweight | True | 0.530617 | 0.130560 | 0.786808 | 0.086315 | 0.256667 | 0.196275 | 0.473333 | 0.096115 | 0.551852 | 0.115425 | 0.290000 | 0.060356 | 0.675000 | 0.143072 | 0.166667 | 0.009759 | 0.970370 | 0.050860 | 1.084482 | 0.092669 | 0.238523 | 0.019174 | 130219.000000 | 15 | 5 |
| candidate_lr_elasticnet_word_char | Candidate ElasticNet LR (word+char TF-IDF) | candidate | core |  | lightweight | True | 0.527398 | 0.115021 | 0.797000 | 0.056610 | 0.245556 | 0.153977 | 0.446667 | 0.091548 | 0.519444 | 0.101085 | 0.300000 | 0.032733 | 0.700926 | 0.095919 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 8.537974 | 1.701311 | 0.168740 | 0.015699 | 130219.000000 | 15 | 6 |
| candidate_lsa_lr | Candidate LSA+LR (SVD semantic projection) | candidate | core |  | lightweight | True | 0.501458 | 0.074465 | 0.796960 | 0.058421 | 0.254444 | 0.174854 | 0.440000 | 0.098561 | 0.512037 | 0.114755 | 0.310000 | 0.050709 | 0.723148 | 0.126148 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 3.322847 | 0.522292 | 0.059980 | 0.033067 | 54451.200000 | 15 | 7 |
| candidate_st_minilm_lr | Candidate MiniLM embedding + LR (sentence-transformers) | candidate | core |  | heavy | False | 0.489699 | 0.157465 | 0.823112 | 0.032456 | 0.250000 | 0.088882 | 0.500000 | 0.264575 | 0.346032 | 0.176982 | 0.400000 | 0.086603 | 0.555556 | 0.096225 | 0.260000 | 0.000000 | 0.907937 | 0.035741 | 6.315753 | 10.918065 | 1.517699 | 2.627326 | 384.000000 | 3 | 8 |
| baseline_lr_word_tfidf | Baseline LR (word TF-IDF) | baseline | core |  | lightweight | True | 0.471764 | 0.129379 | 0.785541 | 0.054056 | 0.257778 | 0.158473 | 0.386667 | 0.130201 | 0.452778 | 0.159727 | 0.290000 | 0.043095 | 0.676852 | 0.106355 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 0.161698 | 0.015045 | 0.037748 | 0.007054 | 10078.333333 | 15 | 9 |
| candidate_cnb_word_tfidf | Candidate ComplementNB (word TF-IDF) | candidate | core |  | lightweight | True | 0.289596 | 0.106415 | 0.595775 | 0.037975 | 0.077778 | 0.081569 | 0.246667 | 0.083381 | 0.285185 | 0.092109 | 0.183333 | 0.036187 | 0.425926 | 0.076554 | 0.150667 | 0.018310 | 0.876852 | 0.102717 | 0.211758 | 0.008846 | 0.034631 | 0.004189 | 54451.200000 | 15 | 10 |
| dory_adaboost_word_tfidf | Dory AdaBoost (word TF-IDF) | dory | dory | adaboost | heavy | False | 0.266221 | 0.037255 | 0.612498 | 0.009370 | 0.066667 | 0.094516 | 0.300000 | 0.000000 | 0.209524 | 0.008248 | 0.200000 | 0.050000 | 0.279365 | 0.072270 | 0.180000 | 0.020000 | 0.626984 | 0.049563 | 4.548996 | 0.026003 | 0.093639 | 0.009017 | 46903.000000 | 3 | 11 |
| dory_xgboost_word_tfidf | Dory XGBoost (word TF-IDF) | dory | dory | xgboost | heavy | False | 0.224369 | 0.052549 | 0.597194 | 0.006623 | -0.003333 | 0.045092 | 0.200000 | 0.100000 | 0.141270 | 0.073822 | 0.200000 | 0.050000 | 0.277778 | 0.059919 | 0.200000 | 0.000000 | 0.698413 | 0.027493 | 1.772528 | 0.178812 | 0.066861 | 0.007361 | 46903.000000 | 3 | 12 |
| candidate_mlp_lsa | Candidate MLP (TF-IDF→SVD dense) | candidate | core |  | heavy | False | 0.207975 | 0.031003 | 0.545274 | 0.101777 | -0.023333 | 0.030551 | 0.200000 | 0.100000 | 0.141270 | 0.073822 | 0.200000 | 0.000000 | 0.279365 | 0.010997 | 0.160000 | 0.052915 | 0.560317 | 0.196127 | 3.672928 | 0.099716 | 0.097963 | 0.007144 | 46903.000000 | 3 | 13 |
| dory_dynamic_nn_dense_lsa | Dory Dynamic-NN (TF-IDF→SVD dense) | dory | dory | dynamic-nn | heavy | False | 0.196653 | 0.037207 | 0.537626 | 0.056986 | -0.023333 | 0.037859 | 0.200000 | 0.000000 | 0.139683 | 0.005499 | 0.166667 | 0.057735 | 0.231746 | 0.077567 | 0.153333 | 0.030551 | 0.533333 | 0.091844 | 5.154105 | 0.150999 | 0.080508 | 0.001696 | 46903.000000 | 3 | 14 |
| candidate_st_minilm_mlp | Candidate MiniLM embedding + MLP | candidate | core |  | heavy | False | 0.161784 | 0.061038 | 0.450743 | 0.048400 | -0.043333 | 0.005774 | 0.066667 | 0.115470 | 0.044444 | 0.076980 | 0.133333 | 0.057735 | 0.184127 | 0.071481 | 0.126667 | 0.030551 | 0.439683 | 0.088619 | 0.107551 | 0.059932 | 0.001274 | 0.000102 | 384.000000 | 3 | 15 |
| dory_nn_2_layer_dense_lsa | Dory NN-2-layer (TF-IDF→SVD dense) | dory | dory | nn-2-layer | heavy | False | 0.143333 | 0.005774 | 0.500000 | 0.000000 | -0.050000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 5.874068 | 1.100180 | 0.082712 | 0.003880 | 46903.000000 | 3 | 16 |
| dory_warmstart_nn_dense_lsa | Dory Warmstart-NN (TF-IDF→SVD dense) | dory | dory | warmstart-nn | heavy | False | 0.143333 | 0.005774 | 0.500000 | 0.000000 | -0.050000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 0.000000 | 5.363809 | 0.104976 | 0.086094 | 0.012232 | 46903.000000 | 3 | 17 |

## Combo sweep matrix
| model_id | cohort | stage | status | n_folds_planned | n_folds_completed | runtime_seconds | reason |
|---|---|---|---|---|---|---|---|
| candidate_mlp_lsa | candidate | heavy | succeeded | 3 | 3 | 11.323718 |  |
| candidate_st_minilm_lr | candidate | heavy | succeeded | 3 | 3 | 23.510696 |  |
| candidate_st_minilm_mlp | candidate | heavy | succeeded | 3 | 3 | 0.338206 |  |
| dory_adaboost_word_tfidf | dory | heavy | succeeded | 3 | 3 | 13.934677 |  |
| dory_dynamic_nn_dense_lsa | dory | heavy | succeeded | 3 | 3 | 15.712771 |  |
| dory_nn_2_layer_dense_lsa | dory | heavy | succeeded | 3 | 3 | 17.879453 |  |
| dory_warmstart_nn_dense_lsa | dory | heavy | succeeded | 3 | 3 | 16.362610 |  |
| dory_xgboost_word_tfidf | dory | heavy | succeeded | 3 | 3 | 5.527706 |  |
| baseline_lr_word_tfidf | baseline | lightweight | succeeded | 15 | 15 | 3.032179 |  |
| candidate_calibrated_sgd_word_char | candidate | lightweight | succeeded | 15 | 15 | 19.883726 |  |
| candidate_cnb_word_tfidf | candidate | lightweight | succeeded | 15 | 15 | 3.734799 |  |
| candidate_linear_svc_isotonic_word_char | candidate | lightweight | succeeded | 15 | 15 | 18.225778 |  |
| candidate_lr_elasticnet_word_char | candidate | lightweight | succeeded | 15 | 15 | 130.639313 |  |
| candidate_lr_word_char | candidate | lightweight | succeeded | 15 | 15 | 19.454153 |  |
| candidate_lsa_lr | candidate | lightweight | succeeded | 15 | 15 | 50.784318 |  |
| candidate_sgd_word_char | candidate | lightweight | succeeded | 15 | 15 | 17.578552 |  |
| improved_calibrated_svm_word_char | improved | lightweight | succeeded | 15 | 15 | 19.132652 |  |

## Blocked / failed models
| model_id | status | reason |
|---|---|---|
| asreview_nemo | blocked | ASReview Nemo is unavailable: no `nemo` classifier entry point is registered, ASReview 2.2 does not expose a `nemo` extra, and no Nemo extension module is importable. |

## Key findings
- Top model by AP: Improved Calibrated SVM (word+char TF-IDF) (AP 0.569 ± 0.099, WSS@95 0.316).
- Runner-up: Candidate LR (word+char TF-IDF) (AP 0.568 ± 0.098).
- Best Dory model: Dory AdaBoost (word TF-IDF) (AP 0.266, WSS@95 0.067).
- Best Dory vs best non-Dory AP gap: -0.303 (Dory AdaBoost (word TF-IDF) vs Improved Calibrated SVM (word+char TF-IDF)).
- Best neural model: Candidate MLP (TF-IDF→SVD dense) (AP 0.208, recall@20 0.279, precision@20 0.200).
- Fastest training model: Candidate MiniLM embedding + MLP (0.108s mean fit time/fold).
- Combo sweep status: attempted=17, succeeded=17, failed=0, skipped=0.
