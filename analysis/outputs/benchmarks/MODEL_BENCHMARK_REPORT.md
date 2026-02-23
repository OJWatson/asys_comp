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
| model_id | display_name | cohort | model_source | dory_classifier | lightweight | average_precision_mean | average_precision_std | roc_auc_mean | roc_auc_std | wss@95_mean | wss@95_std | precision@10_mean | precision@10_std | recall@10_mean | recall@10_std | precision@20_mean | precision@20_std | recall@20_mean | recall@20_std | precision@50_mean | precision@50_std | recall@50_mean | recall@50_std | fit_seconds_mean | fit_seconds_std | score_seconds_mean | score_seconds_std | n_features_mean | n_folds | rank |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| improved_calibrated_svm_word_char | Improved Calibrated SVM (word+char TF-IDF) | improved | core |  | True | 0.568872 | 0.098562 | 0.820724 | 0.067060 | 0.315556 | 0.172340 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.313333 | 0.054989 | 0.732407 | 0.142557 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 0.979566 | 0.031886 | 0.205956 | 0.014138 | 130219.000000 | 15 | 1 |
| candidate_lr_word_char | Candidate LR (word+char TF-IDF) | candidate | core |  | True | 0.568236 | 0.098111 | 0.821285 | 0.062474 | 0.312222 | 0.167908 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.306667 | 0.041690 | 0.716667 | 0.112074 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 0.987512 | 0.083464 | 0.215102 | 0.011253 | 130219.000000 | 15 | 2 |
| candidate_sgd_word_char | Candidate SGD log-loss (word+char TF-IDF) | candidate | core |  | True | 0.532220 | 0.113923 | 0.778054 | 0.076920 | 0.176667 | 0.172148 | 0.466667 | 0.089974 | 0.545370 | 0.117555 | 0.290000 | 0.054116 | 0.676852 | 0.134193 | 0.161333 | 0.014075 | 0.938889 | 0.072701 | 0.934978 | 0.022703 | 0.194534 | 0.013378 | 130219.000000 | 15 | 3 |
| candidate_lsa_lr | Candidate LSA+LR (SVD semantic projection) | candidate | core |  | True | 0.501458 | 0.074465 | 0.796960 | 0.058421 | 0.254444 | 0.174854 | 0.440000 | 0.098561 | 0.512037 | 0.114755 | 0.310000 | 0.050709 | 0.723148 | 0.126148 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 2.693550 | 0.114693 | 0.046808 | 0.001829 | 54451.200000 | 15 | 4 |
| baseline_lr_word_tfidf | Baseline LR (word TF-IDF) | baseline | core |  | True | 0.471764 | 0.129379 | 0.785541 | 0.054056 | 0.257778 | 0.158473 | 0.386667 | 0.130201 | 0.452778 | 0.159727 | 0.290000 | 0.043095 | 0.676852 | 0.106355 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 0.156333 | 0.015838 | 0.035964 | 0.006552 | 10078.333333 | 15 | 5 |
| dory_adaboost_word_tfidf | Dory AdaBoost (word TF-IDF) | dory | dory | adaboost | False | 0.293373 | 0.110578 | 0.643491 | 0.073933 | 0.077778 | 0.124828 | 0.253333 | 0.106010 | 0.296296 | 0.124411 | 0.230000 | 0.049281 | 0.533333 | 0.102708 | 0.157333 | 0.014864 | 0.914815 | 0.068014 | 3.972883 | 0.074959 | 0.058088 | 0.003530 | 54451.200000 | 15 | 6 |
| candidate_cnb_word_tfidf | Candidate ComplementNB (word TF-IDF) | candidate | core |  | True | 0.289596 | 0.106415 | 0.595775 | 0.037975 | 0.077778 | 0.081569 | 0.246667 | 0.083381 | 0.285185 | 0.092109 | 0.183333 | 0.036187 | 0.425926 | 0.076554 | 0.150667 | 0.018310 | 0.876852 | 0.102717 | 0.208788 | 0.004836 | 0.033389 | 0.002332 | 54451.200000 | 15 | 7 |
| dory_xgboost_word_tfidf | Dory XGBoost (word TF-IDF) | dory | dory | xgboost | False | 0.262482 | 0.063477 | 0.592182 | 0.044155 | 0.053333 | 0.094112 | 0.200000 | 0.100000 | 0.232407 | 0.119069 | 0.193333 | 0.062297 | 0.447222 | 0.138810 | 0.150667 | 0.012799 | 0.877778 | 0.078075 | 1.591427 | 0.155996 | 0.040327 | 0.004244 | 54451.200000 | 15 | 8 |

## Dory benchmark context
- ASReview Dory docs reference: https://github.com/asreview/asreview-dory
- Dory classifiers are verified by installed entry points and sparse TF-IDF probe runs before inclusion.

## Blocked models
| model_id | reason |
|---|---|
| asreview_nemo | No ASReview Nemo extension detected. ASReview core classifiers available are typically logistic/nb/rf/svm unless extra classifier plugins are installed. |
| dory_dynamic-nn | Sparse TF-IDF probe failed: TypeError: Sparse data was passed for X, but dense data is required. Use '.toarray()' to convert to a dense numpy array. |
| dory_nn-2-layer | Sparse TF-IDF probe failed: TypeError: Sparse data was passed for X, but dense data is required. Use '.toarray()' to convert to a dense numpy array. |
| dory_warmstart-nn | Sparse TF-IDF probe failed: TypeError: Sparse data was passed for X, but dense data is required. Use '.toarray()' to convert to a dense numpy array. |

## Key findings
- Top model by AP: Improved Calibrated SVM (word+char TF-IDF) (AP 0.569 ± 0.099, WSS@95 0.316).
- Runner-up: Candidate LR (word+char TF-IDF) (AP 0.568 ± 0.098).
- Best Dory model: Dory AdaBoost (word TF-IDF) (AP 0.293, WSS@95 0.078).
- Best Dory vs best current non-Dory AP gap: -0.275 (Dory AdaBoost (word TF-IDF) vs Improved Calibrated SVM (word+char TF-IDF)).
- Fastest training model: Baseline LR (word TF-IDF) (0.156s mean fit time/fold).
