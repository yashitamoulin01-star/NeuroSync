"""
Dataset management API.
List sessions, stats, trigger embedding extraction, export datasets.
"""

import json
from typing import Optional

from fastapi import APIRouter, HTTPException, BackgroundTasks

from backend.services.dataset_service import dataset_service
from backend.services.embedding_service import embedding_service

router = APIRouter(prefix="/api/dataset", tags=["dataset"])


@router.get("/stats")
async def get_stats():
    return dataset_service.get_stats()


@router.get("/sessions")
async def list_sessions(
    label_status: Optional[str] = None,
    limit: int = 200,
    offset: int = 0,
):
    return {"sessions": dataset_service.list_sessions(label_status=label_status, limit=limit, offset=offset)}


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    path = dataset_service.get_session_path(session_id)
    if not path:
        raise HTTPException(404, "Session not found in dataset")
    with open(path / "metadata.json", encoding="utf-8") as f:
        meta = json.load(f)
    return {"metadata": meta, "embeddings": embedding_service.status(session_id)}


@router.post("/sessions/{session_id}/embeddings")
async def extract_embeddings(
    session_id: str,
    background_tasks: BackgroundTasks,
    force: bool = False,
):
    if not dataset_service.get_session_path(session_id):
        raise HTTPException(404, "Session not found in dataset")
    background_tasks.add_task(embedding_service.extract_and_cache, session_id, force)
    return {"status": "queued", "session_id": session_id}


@router.post("/embeddings/batch")
async def batch_embeddings(background_tasks: BackgroundTasks, force: bool = False):
    sessions = dataset_service.list_sessions()
    for s in sessions:
        background_tasks.add_task(embedding_service.extract_and_cache, s["session_id"], force)
    return {"status": "queued", "count": len(sessions)}


@router.get("/export/status")
async def export_status():
    """Check if export outputs exist."""
    from pathlib import Path
    from backend.core.config import settings
    base = Path(settings.DATASET_DIR)
    manifest = base / "exports" / "manifest.json"
    if manifest.exists():
        import json
        with open(manifest, encoding="utf-8") as f:
            return {"status": "ready", "manifest": json.load(f)}
    return {"status": "not_exported"}


@router.post("/export")
async def export_dataset(
    background_tasks: BackgroundTasks,
    val_ratio: float = 0.1,
    test_ratio: float = 0.1,
    limit: Optional[int] = None,
):
    """Generate train/val/test splits and export DeBERTa JSONL + fusion numpy arrays."""
    def _run():
        import sys
        from pathlib import Path
        root = Path(__file__).parent.parent.parent
        sys.path.insert(0, str(root))
        from scripts.export_training_splits import load_all_samples, split, write_deberta_jsonl, write_fusion_arrays
        import json, time
        from pathlib import Path as P

        samples = load_all_samples(limit)
        train_s, val_s, test_s = split(samples, val_ratio, test_ratio, 42)

        exports_deb = root / "data" / "exports" / "deberta"
        exports_fus = root / "data" / "exports" / "fusion"

        for name, subset in [("train", train_s), ("val", val_s), ("test", test_s)]:
            write_deberta_jsonl(subset, exports_deb / f"{name}.jsonl")
            write_fusion_arrays(subset, name)

        manifest = {
            "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "total_samples": len(samples),
            "splits": {"train": len(train_s), "val": len(val_s), "test": len(test_s)},
        }
        mp = root / "data" / "exports" / "manifest.json"
        mp.parent.mkdir(parents=True, exist_ok=True)
        mp.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    background_tasks.add_task(_run)
    return {"status": "export_queued", "val_ratio": val_ratio, "test_ratio": test_ratio}
