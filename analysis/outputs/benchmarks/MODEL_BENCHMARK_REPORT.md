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
| improved_calibrated_svm_word_char | Improved Calibrated SVM (word+char TF-IDF) | improved | True | 0.568872 | 0.098562 | 0.820724 | 0.067060 | 0.315556 | 0.172340 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.313333 | 0.054989 | 0.732407 | 0.142557 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 1.292449 | 0.164598 | 0.248913 | 0.033679 | 130219.000000 | 15 | 1 |
| candidate_lr_word_char | Candidate LR (word+char TF-IDF) | candidate | True | 0.568236 | 0.098111 | 0.821285 | 0.062474 | 0.312222 | 0.167908 | 0.493333 | 0.096115 | 0.576852 | 0.128035 | 0.306667 | 0.041690 | 0.716667 | 0.112074 | 0.169333 | 0.010328 | 0.985185 | 0.039096 | 1.356380 | 0.149336 | 0.258563 | 0.032130 | 130219.000000 | 15 | 2 |
| candidate_sgd_word_char | Candidate SGD log-loss (word+char TF-IDF) | candidate | True | 0.532220 | 0.113923 | 0.778054 | 0.076920 | 0.176667 | 0.172148 | 0.466667 | 0.089974 | 0.545370 | 0.117555 | 0.290000 | 0.054116 | 0.676852 | 0.134193 | 0.161333 | 0.014075 | 0.938889 | 0.072701 | 1.220706 | 0.124526 | 0.242136 | 0.031818 | 130219.000000 | 15 | 3 |
| candidate_lsa_lr | Candidate LSA+LR (SVD semantic projection) | candidate | True | 0.501458 | 0.074465 | 0.796960 | 0.058421 | 0.254444 | 0.174854 | 0.440000 | 0.098561 | 0.512037 | 0.114755 | 0.310000 | 0.050709 | 0.723148 | 0.126148 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 3.246094 | 0.328826 | 0.055398 | 0.005862 | 54451.200000 | 15 | 4 |
| baseline_lr_word_tfidf | Baseline LR (word TF-IDF) | baseline | True | 0.471764 | 0.129379 | 0.785541 | 0.054056 | 0.257778 | 0.158473 | 0.386667 | 0.130201 | 0.452778 | 0.159727 | 0.290000 | 0.043095 | 0.676852 | 0.106355 | 0.168000 | 0.010142 | 0.977778 | 0.046004 | 0.197524 | 0.023699 | 0.044131 | 0.008838 | 10078.333333 | 15 | 5 |
| candidate_cnb_word_tfidf | Candidate ComplementNB (word TF-IDF) | candidate | True | 0.289596 | 0.106415 | 0.595775 | 0.037975 | 0.077778 | 0.081569 | 0.246667 | 0.083381 | 0.285185 | 0.092109 | 0.183333 | 0.036187 | 0.425926 | 0.076554 | 0.150667 | 0.018310 | 0.876852 | 0.102717 | 0.297070 | 0.019286 | 0.042259 | 0.003321 | 54451.200000 | 15 | 6 |

## Blocked models
| model_id | reason |
|---|---|
| asreview_nemo | No ASReview Nemo extension detected. ASReview core classifiers available are typically logistic/nb/rf/svm unless extra classifier plugins are installed. |

## Key findings
- Top model by AP: Improved Calibrated SVM (word+char TF-IDF) (AP 0.569 ± 0.099, WSS@95 0.316).
- Runner-up: Candidate LR (word+char TF-IDF) (AP 0.568 ± 0.098).
- Fastest training model: Baseline LR (word TF-IDF) (0.198s mean fit time/fold).
