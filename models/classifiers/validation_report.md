# Phase 4 — Behavioral Classifier Validation Report

**Trained at:** 2026-06-11T13:10:09Z  
**Samples:** Train 59,432 | Val 7,428 | Test 7,428  
**Features:** 44

---

## Confidence

| | |
|---|---|
| Best model | `gradient_boosting` |
| Classes | 3 (low, medium, high) |
| Imbalance ratio | 2.2:1 |
| Test accuracy | 0.9786 |
| Test macro F1 | 0.9770 |
| Test weighted F1 | 0.9786 |

**Per-class performance on test set:**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| low | 0.987 | 0.990 | 0.988 | 2,721 |
| medium | 0.974 | 0.977 | 0.976 | 3,247 |
| high | 0.972 | 0.962 | 0.967 | 1,460 |

**Candidate comparison (validation macro F1):**

| Model | Val Acc | Val Macro F1 | Train Acc | Fit (s) |
|-------|---------|--------------|-----------|---------|
| `random_forest` | 0.9737 | 0.9711 | 0.9998 | 65.86 |
| `gradient_boosting` ✓ | 0.9759 | 0.9734 | 0.9833 | 504.33 |
| `logistic_regression` | 0.9676 | 0.9638 | 0.9721 | 3.68 |

---

## Stress

| | |
|---|---|
| Best model | `random_forest` |
| Classes | 3 (calm, moderate, high) |
| Imbalance ratio | 2.5:1 |
| Test accuracy | 0.9837 |
| Test macro F1 | 0.9838 |
| Test weighted F1 | 0.9837 |

**Per-class performance on test set:**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| calm | 0.981 | 0.983 | 0.982 | 2,133 |
| moderate | 0.985 | 0.982 | 0.984 | 3,748 |
| high | 0.983 | 0.988 | 0.985 | 1,547 |

**Candidate comparison (validation macro F1):**

| Model | Val Acc | Val Macro F1 | Train Acc | Fit (s) |
|-------|---------|--------------|-----------|---------|
| `random_forest` ✓ | 0.9825 | 0.9826 | 0.9991 | 57.95 |
| `gradient_boosting` | 0.9817 | 0.9817 | 0.9880 | 426.18 |
| `logistic_regression` | 0.9794 | 0.9791 | 0.9829 | 3.81 |

---

## Hesitation

| | |
|---|---|
| Best model | `random_forest` |
| Classes | 3 (low, medium, high) |
| Imbalance ratio | 1.5:1 |
| Test accuracy | 1.0000 |
| Test macro F1 | 1.0000 |
| Test weighted F1 | 1.0000 |

**Per-class performance on test set:**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| low | 1.000 | 1.000 | 1.000 | 2,853 |
| medium | 1.000 | 1.000 | 1.000 | 2,601 |
| high | 1.000 | 1.000 | 1.000 | 1,974 |

**Candidate comparison (validation macro F1):**

| Model | Val Acc | Val Macro F1 | Train Acc | Fit (s) |
|-------|---------|--------------|-----------|---------|
| `random_forest` ✓ | 1.0000 | 1.0000 | 1.0000 | 16.1 |
| `gradient_boosting` | 1.0000 | 1.0000 | 1.0000 | 309.36 |
| `logistic_regression` | 1.0000 | 1.0000 | 1.0000 | 0.36 |

---

## Eye Contact

| | |
|---|---|
| Best model | `random_forest` |
| Classes | 3 (stable, nervous, avoidant) |
| Imbalance ratio | 19807.3:1 |
| Test accuracy | 1.0000 |
| Test macro F1 | 1.0000 |
| Test weighted F1 | 1.0000 |

> **WARNING — Severe imbalance (19807.3:1).** Accuracy is misleading; macro-F1 is near zero for minority classes. More labeled samples for minority classes required before this classifier is useful.

**Per-class performance on test set:**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| stable | 1.000 | 1.000 | 1.000 | 7,426 |
| nervous | 1.000 | 1.000 | 1.000 | 1 |
| avoidant | 1.000 | 1.000 | 1.000 | 1 |

**Candidate comparison (validation macro F1):**

| Model | Val Acc | Val Macro F1 | Train Acc | Fit (s) |
|-------|---------|--------------|-----------|---------|
| `random_forest` ✓ | 1.0000 | 1.0000 | 1.0000 | 4.77 |
| `gradient_boosting` | 1.0000 | 1.0000 | 1.0000 | 36.12 |
| `logistic_regression` | 1.0000 | 1.0000 | 1.0000 | 0.54 |

---

## Communication Quality

| | |
|---|---|
| Best model | `random_forest` |
| Classes | 4 (strong, clear, hesitant, weak) |
| Imbalance ratio | 2.8:1 |
| Test accuracy | 0.9996 |
| Test macro F1 | 0.9997 |
| Test weighted F1 | 0.9996 |

**Per-class performance on test set:**

| Class | Precision | Recall | F1 | Support |
|-------|-----------|--------|-----|---------|
| strong | 0.999 | 1.000 | 0.999 | 2,041 |
| clear | 1.000 | 0.999 | 0.999 | 2,997 |
| hesitant | 1.000 | 1.000 | 1.000 | 1,306 |
| weak | 1.000 | 1.000 | 1.000 | 1,084 |

**Candidate comparison (validation macro F1):**

| Model | Val Acc | Val Macro F1 | Train Acc | Fit (s) |
|-------|---------|--------------|-----------|---------|
| `random_forest` ✓ | 0.9999 | 0.9998 | 1.0000 | 25.76 |
| `gradient_boosting` | 0.9996 | 0.9996 | 1.0000 | 461.01 |
| `logistic_regression` | 0.9997 | 0.9998 | 0.9993 | 2.76 |

---

## Summary

| Target | Best Model | Test Acc | Macro F1 | Severe Imbalance |
|--------|-----------|----------|----------|-----------------|
| confidence | `gradient_boosting` | 0.9786 | 0.9770 | No |
| stress | `random_forest` | 0.9837 | 0.9838 | No |
| hesitation | `random_forest` | 1.0000 | 1.0000 | No |
| eye_contact | `random_forest` | 1.0000 | 1.0000 | YES ⚠ |
| communication_quality | `random_forest` | 0.9996 | 0.9997 | No |