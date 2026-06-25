"""
Phase 4 — Behavioral Classifiers
Trains RandomForest, GradientBoosting, and LogisticRegression for each of the
five behavioral targets, selects the best by validation macro-F1, refits on
train+val, evaluates on the held-out test set, and saves artefacts.

Outputs (all under models/classifiers/):
  scaler.joblib
  <target>_clf.pkl            — best model per target
  <target>_feature_importance.json / .png
  <target>_confusion_matrix.png
  metrics.json                — full numeric report
  validation_report.md        — human-readable summary
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import joblib
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_fscore_support,
)
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent.parent
EXPORTS_DIR = ROOT / "data" / "exports" / "sklearn"
MODELS_DIR = ROOT / "models" / "classifiers"

# (column_index, name, {int: label_string})
TARGETS: list[tuple[int, str, dict[int, str]]] = [
    (0, "confidence",            {0: "low",     1: "medium",   2: "high"}),
    (1, "stress",                {0: "calm",    1: "moderate", 2: "high"}),
    (2, "hesitation",            {0: "low",     1: "medium",   2: "high"}),
    (3, "eye_contact",           {0: "stable",  1: "nervous",  2: "avoidant"}),
    (4, "communication_quality", {0: "strong",  1: "clear",    2: "hesitant", 3: "weak"}),
]

FEATURE_NAMES = [f"f_{i:02d}" for i in range(44)]

SEVERE_IMBALANCE_THRESHOLD = 50.0


# ── Model factories ───────────────────────────────────────────────────────────

def _make_candidates() -> dict[str, object]:
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=200,
            max_depth=None,
            class_weight="balanced",
            n_jobs=-1,
            random_state=42,
        ),
        "gradient_boosting": GradientBoostingClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            subsample=0.8,
            random_state=42,
        ),
        "logistic_regression": LogisticRegression(
            max_iter=1000,
            class_weight="balanced",
            C=1.0,
            solver="lbfgs",
            random_state=42,
        ),
    }


# ── Metrics helpers ───────────────────────────────────────────────────────────

def _compute_metrics(y_true: np.ndarray, y_pred: np.ndarray,
                     class_names: dict[int, str]) -> dict:
    labels = sorted(class_names)
    prec, rec, f1, support = precision_recall_fscore_support(
        y_true, y_pred, labels=labels, average=None, zero_division=0
    )
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "macro_f1": float(f1_score(y_true, y_pred, average="macro", zero_division=0)),
        "weighted_f1": float(f1_score(y_true, y_pred, average="weighted", zero_division=0)),
        "per_class": {
            class_names[labels[i]]: {
                "precision": float(prec[i]),
                "recall":    float(rec[i]),
                "f1":        float(f1[i]),
                "support":   int(support[i]),
            }
            for i in range(len(labels))
        },
        "confusion_matrix": confusion_matrix(y_true, y_pred, labels=labels).tolist(),
    }


# ── Visualisations (matplotlib optional) ─────────────────────────────────────

def _save_feature_importance(model, model_name: str, target: str,
                              out_dir: Path) -> None:
    if model_name == "logistic_regression":
        coef = model.coef_
        imp = np.abs(coef).mean(axis=0) if coef.ndim > 1 else np.abs(coef[0])
    elif hasattr(model, "feature_importances_"):
        imp = model.feature_importances_
    else:
        return

    top_idx = np.argsort(imp)[::-1][:20]
    importance = {FEATURE_NAMES[i]: float(imp[i]) for i in top_idx}
    (out_dir / f"{target}_feature_importance.json").write_text(
        json.dumps(importance, indent=2), encoding="utf-8"
    )

    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        names  = list(importance.keys())
        values = list(importance.values())
        fig, ax = plt.subplots(figsize=(10, 6))
        ax.barh(names[::-1], values[::-1], color="steelblue")
        ax.set_xlabel("Importance")
        ax.set_title(f"Top-20 Feature Importance — {target} ({model_name})")
        plt.tight_layout()
        fig.savefig(out_dir / f"{target}_feature_importance.png", dpi=120)
        plt.close(fig)
        logger.info("  Saved feature importance chart: %s", target)
    except Exception as exc:
        logger.debug("matplotlib unavailable, skipping chart: %s", exc)


def _save_confusion_matrix_chart(cm_data: list[list[int]],
                                  class_names: dict[int, str],
                                  target: str, out_dir: Path) -> None:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        cm_arr = np.array(cm_data)
        labels = [class_names[i] for i in sorted(class_names)]
        fig, ax = plt.subplots(figsize=(6, 5))
        im = ax.imshow(cm_arr, interpolation="nearest", cmap="Blues")
        fig.colorbar(im)
        ax.set(
            xticks=range(len(labels)), yticks=range(len(labels)),
            xticklabels=labels, yticklabels=labels,
            xlabel="Predicted", ylabel="True",
            title=f"Confusion Matrix — {target}",
        )
        thresh = cm_arr.max() / 2.0
        for i in range(len(labels)):
            for j in range(len(labels)):
                ax.text(j, i, cm_arr[i, j], ha="center", va="center",
                        color="white" if cm_arr[i, j] > thresh else "black",
                        fontsize=9)
        plt.tight_layout()
        fig.savefig(out_dir / f"{target}_confusion_matrix.png", dpi=120)
        plt.close(fig)
    except Exception as exc:
        logger.debug("matplotlib unavailable, skipping confusion matrix chart: %s", exc)


# ── Main training pipeline ────────────────────────────────────────────────────

def train() -> dict:
    """
    Full Phase 4 training pipeline.
    - Loads sklearn numpy exports
    - Fits StandardScaler on train split
    - Trains 3 candidate models per target, selects by validation macro-F1
    - Refits winner on train+val, evaluates on held-out test
    - Saves models, metrics.json, and validation_report.md
    Returns the full report dict.
    """
    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load data ──────────────────────────────────────────────────────────────
    logger.info("Loading numpy arrays from %s", EXPORTS_DIR)
    X_train = np.load(EXPORTS_DIR / "X_train.npy").astype(np.float32)
    X_val   = np.load(EXPORTS_DIR / "X_val.npy").astype(np.float32)
    X_test  = np.load(EXPORTS_DIR / "X_test.npy").astype(np.float32)
    Y_train = np.load(EXPORTS_DIR / "Y_train.npy")
    Y_val   = np.load(EXPORTS_DIR / "Y_val.npy")
    Y_test  = np.load(EXPORTS_DIR / "Y_test.npy")
    logger.info("Loaded — train: %d  val: %d  test: %d", len(X_train), len(X_val), len(X_test))

    # ── Scale ──────────────────────────────────────────────────────────────────
    scaler = StandardScaler()
    X_train_s    = scaler.fit_transform(X_train)
    X_val_s      = scaler.transform(X_val)
    X_test_s     = scaler.transform(X_test)
    X_trainval_s = np.vstack([X_train_s, X_val_s])
    joblib.dump(scaler, MODELS_DIR / "scaler.joblib")
    logger.info("StandardScaler fitted and saved.")

    report = {
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "n_train": int(len(X_train)),
        "n_val":   int(len(X_val)),
        "n_test":  int(len(X_test)),
        "n_features": int(X_train.shape[1]),
        "classifiers": {},
    }

    # ── Per-target training ────────────────────────────────────────────────────
    for col_idx, target, class_names in TARGETS:
        logger.info("=" * 60)
        logger.info("TARGET: %s (col %d, %d classes)", target, col_idx, len(class_names))

        y_train    = Y_train[:, col_idx]
        y_val      = Y_val[:, col_idx]
        y_test     = Y_test[:, col_idx]
        y_trainval = np.concatenate([y_train, y_val])

        # Class imbalance stats
        classes, counts = np.unique(y_train, return_counts=True)
        class_counts = {int(c): int(n) for c, n in zip(classes, counts)}
        imbalance_ratio = float(max(counts)) / float(max(min(counts), 1))

        if imbalance_ratio > SEVERE_IMBALANCE_THRESHOLD:
            logger.warning(
                "  SEVERE IMBALANCE for %s: %.0f:1 — classifier will likely predict majority class",
                target, imbalance_ratio
            )

        # ── Candidate evaluation ───────────────────────────────────────────────
        candidates = _make_candidates()
        best_name: str | None = None
        best_val_f1 = -1.0
        candidate_results: dict[str, dict] = {}

        for model_name, model in candidates.items():
            logger.info("  Fitting %s ...", model_name)
            t0 = time.time()
            model.fit(X_train_s, y_train)
            elapsed = time.time() - t0

            train_pred = model.predict(X_train_s)
            val_pred   = model.predict(X_val_s)

            train_acc = float(accuracy_score(y_train, train_pred))
            val_acc   = float(accuracy_score(y_val, val_pred))
            val_f1    = float(f1_score(y_val, val_pred, average="macro", zero_division=0))

            candidate_results[model_name] = {
                "train_accuracy": round(train_acc, 4),
                "val_accuracy":   round(val_acc, 4),
                "val_macro_f1":   round(val_f1, 4),
                "fit_seconds":    round(elapsed, 2),
            }
            logger.info(
                "    %-26s  train_acc=%.4f  val_acc=%.4f  val_macro_f1=%.4f  (%.1fs)",
                model_name, train_acc, val_acc, val_f1, elapsed
            )

            if val_f1 > best_val_f1:
                best_val_f1 = val_f1
                best_name = model_name

        # ── Refit best on train+val ────────────────────────────────────────────
        logger.info(
            "  Winner: %s (val_macro_f1=%.4f). Refitting on train+val...",
            best_name, best_val_f1
        )
        final_models = _make_candidates()
        final_model = final_models[best_name]
        final_model.fit(X_trainval_s, y_trainval)

        # ── Test evaluation ────────────────────────────────────────────────────
        test_pred    = final_model.predict(X_test_s)
        test_metrics = _compute_metrics(y_test, test_pred, class_names)
        logger.info(
            "  Test — acc=%.4f  macro_f1=%.4f  weighted_f1=%.4f",
            test_metrics["accuracy"], test_metrics["macro_f1"], test_metrics["weighted_f1"]
        )

        # ── Save model ─────────────────────────────────────────────────────────
        model_path = MODELS_DIR / f"{target}_clf.pkl"
        joblib.dump(final_model, model_path)
        logger.info("  Saved model: %s", model_path.name)

        # ── Visualisations ─────────────────────────────────────────────────────
        _save_feature_importance(final_model, best_name, target, MODELS_DIR)
        _save_confusion_matrix_chart(test_metrics["confusion_matrix"], class_names,
                                     target, MODELS_DIR)

        report["classifiers"][target] = {
            "best_model":      best_name,
            "model_path":      str(model_path.relative_to(ROOT)),
            "n_classes":       len(class_names),
            "class_names":     {str(k): v for k, v in class_names.items()},
            "class_counts":    class_counts,
            "imbalance_ratio": round(imbalance_ratio, 1),
            "severe_imbalance": imbalance_ratio > SEVERE_IMBALANCE_THRESHOLD,
            "candidates":      candidate_results,
            "test_metrics":    test_metrics,
        }

    # ── Save artefacts ─────────────────────────────────────────────────────────
    metrics_path = MODELS_DIR / "metrics.json"
    metrics_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    logger.info("metrics.json saved.")

    _write_validation_report(report)

    logger.info("Phase 4 training complete.")
    return report


# ── Validation report ─────────────────────────────────────────────────────────

def _write_validation_report(report: dict) -> None:
    lines = [
        "# Phase 4 — Behavioral Classifier Validation Report",
        "",
        f"**Trained at:** {report['trained_at']}  ",
        f"**Samples:** Train {report['n_train']:,} | Val {report['n_val']:,} | Test {report['n_test']:,}  ",
        f"**Features:** {report['n_features']}",
        "",
        "---",
        "",
    ]

    for _, target, _ in TARGETS:
        info = report["classifiers"][target]
        tm   = info["test_metrics"]

        lines += [
            f"## {target.replace('_', ' ').title()}",
            "",
            f"| | |",
            f"|---|---|",
            f"| Best model | `{info['best_model']}` |",
            f"| Classes | {info['n_classes']} ({', '.join(info['class_names'].values())}) |",
            f"| Imbalance ratio | {info['imbalance_ratio']}:1 |",
            f"| Test accuracy | {tm['accuracy']:.4f} |",
            f"| Test macro F1 | {tm['macro_f1']:.4f} |",
            f"| Test weighted F1 | {tm['weighted_f1']:.4f} |",
            "",
        ]

        if info["severe_imbalance"]:
            lines.append(
                f"> **WARNING — Severe imbalance ({info['imbalance_ratio']}:1).** "
                "Accuracy is misleading; macro-F1 is near zero for minority classes. "
                "More labeled samples for minority classes required before this classifier is useful."
            )
            lines.append("")

        lines.append("**Per-class performance on test set:**")
        lines.append("")
        lines.append("| Class | Precision | Recall | F1 | Support |")
        lines.append("|-------|-----------|--------|-----|---------|")
        for cls_name, m in tm["per_class"].items():
            lines.append(
                f"| {cls_name} | {m['precision']:.3f} | {m['recall']:.3f} | {m['f1']:.3f} | {m['support']:,} |"
            )

        lines += [
            "",
            "**Candidate comparison (validation macro F1):**",
            "",
            "| Model | Val Acc | Val Macro F1 | Train Acc | Fit (s) |",
            "|-------|---------|--------------|-----------|---------|",
        ]
        for mn, mr in info["candidates"].items():
            winner = " ✓" if mn == info["best_model"] else ""
            lines.append(
                f"| `{mn}`{winner} | {mr['val_accuracy']:.4f} | {mr['val_macro_f1']:.4f} | {mr['train_accuracy']:.4f} | {mr['fit_seconds']} |"
            )
        lines.append("")
        lines.append("---")
        lines.append("")

    lines += [
        "## Summary",
        "",
        "| Target | Best Model | Test Acc | Macro F1 | Severe Imbalance |",
        "|--------|-----------|----------|----------|-----------------|",
    ]
    for _, target, _ in TARGETS:
        info = report["classifiers"][target]
        tm   = info["test_metrics"]
        flag = "YES ⚠" if info["severe_imbalance"] else "No"
        lines.append(
            f"| {target} | `{info['best_model']}` | {tm['accuracy']:.4f} | {tm['macro_f1']:.4f} | {flag} |"
        )

    out = MODELS_DIR / "validation_report.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Validation report saved: %s", out)


# ── CLI entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%H:%M:%S",
    )
    result = train()
    print("\n" + "=" * 60)
    print("PHASE 4 COMPLETE")
    print("=" * 60)
    for _, target, _ in TARGETS:
        info = result["classifiers"][target]
        tm   = info["test_metrics"]
        warn = "  [!] SEVERE IMBALANCE" if info["severe_imbalance"] else ""
        print(
            f"  {target:26s}  best={info['best_model']:25s}"
            f"  test_acc={tm['accuracy']:.4f}  macro_f1={tm['macro_f1']:.4f}{warn}"
        )
    print(f"\nArtefacts saved to: {MODELS_DIR}")
