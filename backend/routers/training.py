"""
Training management API.
POST /api/training/classifiers  — retrain sklearn behavioral classifiers
POST /api/training/export       — export DeBERTa JSONL + sklearn arrays
GET  /api/training/status       — check training artifact status
"""

import json
import logging
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/training", tags=["training"])

ROOT = Path(__file__).parent.parent.parent


@router.get("/status")
async def training_status():
    """Check which trained artifacts exist."""
    models_dir = ROOT / "models"
    clf_dir    = models_dir / "classifiers"
    deb_dir    = models_dir / "deberta"
    fus_dir    = models_dir / "fusion"
    exp_dir    = ROOT / "data" / "exports"

    clf_report = None
    if (clf_dir / "report.json").exists():
        try:
            with open(clf_dir / "report.json", encoding="utf-8") as f:
                clf_report = json.load(f)
        except Exception:
            pass

    classifiers = {
        "trained": (clf_dir / "confidence_clf.pkl").exists(),
        "n_sessions": clf_report.get("n_sessions") if clf_report else None,
        "trained_at": clf_report.get("trained_at") if clf_report else None,
        "classifiers": list(clf_report.get("classifiers", {}).keys()) if clf_report else [],
    }

    return {
        "classifiers": classifiers,
        "deberta": {
            "best_saved": (deb_dir / "best").exists(),
            "final_saved": (deb_dir / "final").exists(),
        },
        "fusion": {
            "best_saved": (fus_dir / "best_fusion.pt").exists(),
            "final_saved": (fus_dir / "final_fusion.pt").exists(),
        },
        "exports": {
            "deberta_train": (exp_dir / "deberta" / "train.jsonl").exists(),
            "sklearn_train": (exp_dir / "sklearn" / "X_train.npy").exists(),
            "manifest": (exp_dir / "manifest.json").exists(),
        },
    }


@router.post("/classifiers")
async def retrain_classifiers(background_tasks: BackgroundTasks, min_samples: int = 5):
    """Retrain sklearn behavioral classifiers on all labeled sessions."""
    def _run():
        import sys
        sys.path.insert(0, str(ROOT))
        from ml.classifiers.behavioral_classifiers import train
        try:
            report = train(min_samples=min_samples)
            logger.info(
                "Classifier retrain complete — %d sessions, classifiers: %s",
                report.get("n_sessions", 0),
                list(report.get("classifiers", {}).keys()),
            )
        except Exception as e:
            logger.error("Classifier training failed: %s", e)

    background_tasks.add_task(_run)
    return {"status": "retrain_queued", "min_samples": min_samples}


@router.post("/export")
async def export_splits(
    background_tasks: BackgroundTasks,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    limit: int | None = None,
):
    """Export DeBERTa JSONL + sklearn feature arrays from labeled sessions."""
    def _run():
        import sys
        sys.path.insert(0, str(ROOT))
        from scripts.export_training_splits import load_all_samples, split, write_deberta_jsonl, write_sklearn_arrays
        import time, json as _json
        from pathlib import Path as P

        samples = load_all_samples(limit)
        train_s, val_s, test_s = split(samples, val_ratio, test_ratio, 42)

        exports_deb = ROOT / "data" / "exports" / "deberta"
        exports_skl = ROOT / "data" / "exports" / "sklearn"

        for name, subset in [("train", train_s), ("val", val_s), ("test", test_s)]:
            write_deberta_jsonl(subset, exports_deb / f"{name}.jsonl")
            write_sklearn_arrays(subset, name)

        manifest = {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_samples": len(samples),
            "splits": {"train": len(train_s), "val": len(val_s), "test": len(test_s)},
        }
        mp = ROOT / "data" / "exports" / "manifest.json"
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(_json.dumps(manifest, indent=2), encoding="utf-8")
        logger.info("Export complete — %d total samples", len(samples))

    background_tasks.add_task(_run)
    return {"status": "export_queued", "val_ratio": val_ratio, "test_ratio": test_ratio}
