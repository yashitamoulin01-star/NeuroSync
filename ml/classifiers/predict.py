"""
Phase 4 inference — loads trained behavioral classifiers and predicts
all five behavioral labels for a given 44-dimensional feature vector.

Usage:
    from ml.classifiers.predict import BehavioralPredictor

    predictor = BehavioralPredictor()

    # Single sample
    result = predictor.predict(np.array([...], dtype=np.float32))
    # {'confidence': {'label': 'high', 'class_id': 2, 'probabilities': {...}}, ...}

    # Batch
    result = predictor.predict(X)   # X shape (N, 44)
"""

from __future__ import annotations

from pathlib import Path
import numpy as np
import joblib

ROOT       = Path(__file__).parent.parent.parent
MODELS_DIR = ROOT / "models" / "classifiers"

TARGETS: list[tuple[str, dict[int, str]]] = [
    ("confidence",            {0: "low",     1: "medium",   2: "high"}),
    ("stress",                {0: "calm",    1: "moderate", 2: "high"}),
    ("hesitation",            {0: "low",     1: "medium",   2: "high"}),
    ("eye_contact",           {0: "stable",  1: "nervous",  2: "avoidant"}),
    ("communication_quality", {0: "strong",  1: "clear",    2: "hesitant", 3: "weak"}),
]


class BehavioralPredictor:
    """
    Loads scaler + all five classifiers once, then predicts on demand.
    Thread-safe for read-only inference (sklearn models are stateless after fit).
    """

    def __init__(self, models_dir: Path | str = MODELS_DIR) -> None:
        models_dir = Path(models_dir)
        self._scaler = joblib.load(models_dir / "scaler.joblib")
        self._models = {
            target: joblib.load(models_dir / f"{target}_clf.pkl")
            for target, _ in TARGETS
        }
        self._class_names = {target: names for target, names in TARGETS}

    # ── Public API ─────────────────────────────────────────────────────────────

    def predict(self, features: np.ndarray) -> dict:
        """
        Predict behavioral labels.

        Args:
            features: shape (44,) for a single sample or (N, 44) for a batch.

        Returns:
            Single sample  → dict[target, {label, class_id, probabilities}]
            Batch (N > 1)  → dict[target, {labels, class_ids, probabilities}]
        """
        single = features.ndim == 1
        X = features.reshape(1, -1) if single else features
        X_s = self._scaler.transform(X.astype(np.float32))

        out: dict = {}
        for target, class_names in TARGETS:
            model  = self._models[target]
            preds  = model.predict(X_s)
            # Use model.classes_ to guarantee correct probability column mapping
            classes = list(model.classes_)
            probs  = model.predict_proba(X_s)   # (N, n_classes)

            if single:
                pred_id = int(preds[0])
                out[target] = {
                    "label":    class_names.get(pred_id, str(pred_id)),
                    "class_id": pred_id,
                    "probabilities": {
                        class_names.get(int(c), str(c)): float(p)
                        for c, p in zip(classes, probs[0])
                    },
                }
            else:
                out[target] = {
                    "labels":    [class_names.get(int(p), str(p)) for p in preds],
                    "class_ids": [int(p) for p in preds],
                    "probabilities": [
                        {
                            class_names.get(int(c), str(c)): float(p)
                            for c, p in zip(classes, row)
                        }
                        for row in probs
                    ],
                }

        return out

    def predict_from_list(self, features: list[float]) -> dict:
        """Convenience wrapper — accepts a plain Python list."""
        return self.predict(np.array(features, dtype=np.float32))

    def predict_json(self, features: list[float]) -> str:
        """Returns JSON string — useful for API responses."""
        import json
        return json.dumps(self.predict_from_list(features))

    # ── Diagnostics ────────────────────────────────────────────────────────────

    def model_info(self) -> dict:
        """Return loaded model types per target."""
        return {
            target: type(model).__name__
            for target, model in self._models.items()
        }

    @classmethod
    def is_ready(cls, models_dir: Path | str = MODELS_DIR) -> bool:
        """Return True only if all required model files exist on disk."""
        models_dir = Path(models_dir)
        required = [models_dir / "scaler.joblib"] + [
            models_dir / f"{t}_clf.pkl" for t, _ in TARGETS
        ]
        return all(p.exists() for p in required)


# ── CLI smoke test ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import json, sys

    if not BehavioralPredictor.is_ready():
        print("Models not found. Run behavioral_classifiers.py first.")
        sys.exit(1)

    predictor = BehavioralPredictor()
    print("Loaded models:", predictor.model_info())

    rng   = np.random.default_rng(0)
    dummy = rng.uniform(0, 10, size=(44,)).astype(np.float32)
    result = predictor.predict(dummy)

    print("\nSingle-sample prediction:")
    for target, info in result.items():
        prob_str = "  ".join(f"{k}={v:.3f}" for k, v in info["probabilities"].items())
        print(f"  {target:26s}  → {info['label']:10s}  [{prob_str}]")
