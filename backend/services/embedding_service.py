"""
Embedding extraction + caching service.
Coordinates modality embedders (statistical + real models) and stores .npy files.

Extraction priority:
  audio → AST(wav) > statistical(jsonl)
  face  → ViT(mp4) > statistical(jsonl)
  text  → MiniLM(transcript) > TF-IDF fallback
"""

from __future__ import annotations

import logging
import numpy as np
from pathlib import Path
from typing import Dict, Optional

from backend.core.config import settings
from backend.services.dataset_service import dataset_service

logger = logging.getLogger(__name__)


class EmbeddingService:
    def __init__(self):
        self.base = Path(settings.DATASET_DIR) / "embeddings" / "sessions"
        self.base.mkdir(parents=True, exist_ok=True)

    # ── Cache I/O ─────────────────────────────────────────────────────────────

    def status(self, session_id: str) -> Dict[str, bool]:
        d = self.base / session_id
        return {m: (d / f"{m}.npy").exists() for m in ["face", "audio", "text"]}

    def save(self, session_id: str, modality: str, emb: np.ndarray,
             model_id: str = "statistical") -> None:
        d = self.base / session_id
        d.mkdir(parents=True, exist_ok=True)
        np.save(str(d / f"{modality}.npy"), emb)
        self._update_meta(session_id, modality, emb, model_id)

    def load(self, session_id: str, modality: str) -> Optional[np.ndarray]:
        p = self.base / session_id / f"{modality}.npy"
        return np.load(str(p)) if p.exists() else None

    def load_all(self, session_id: str) -> Dict[str, Optional[np.ndarray]]:
        return {m: self.load(session_id, m) for m in ["face", "audio", "text"]}

    def _update_meta(self, session_id: str, modality: str,
                     emb: np.ndarray, model_id: str) -> None:
        import json, time
        meta_path = self.base / session_id / "embedding_meta.json"
        meta = {}
        if meta_path.exists():
            try:
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
            except Exception:
                pass
        meta[modality] = {
            "model_id": model_id,
            "shape": list(emb.shape),
            "dtype": str(emb.dtype),
            "extracted_at": time.time(),
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)

    # ── Extraction ────────────────────────────────────────────────────────────

    def extract_and_cache(self, session_id: str,
                          force: bool = False,
                          use_real_models: bool = False) -> Dict[str, bool]:
        """
        Extract face, audio, and text embeddings for a session.
        use_real_models=True: tries ViT/AST/DeBERTa if models are available.
        """
        session_path = dataset_service.get_session_path(session_id)
        if not session_path:
            return {"error": "session_not_found"}

        exist = self.status(session_id)
        results: Dict[str, bool] = {}

        # ── Audio ─────────────────────────────────────────────────────────────
        if not exist["audio"] or force:
            results["audio"] = self._extract_audio(session_id, session_path, use_real_models)

        # ── Face ──────────────────────────────────────────────────────────────
        if not exist["face"] or force:
            results["face"] = self._extract_face(session_id, session_path, use_real_models)

        # ── Text ──────────────────────────────────────────────────────────────
        if not exist["text"] or force:
            results["text"] = self._extract_text(session_id, session_path, use_real_models)

        return results

    def _extract_audio(self, session_id: str, session_path: Path,
                       use_real: bool) -> bool:
        try:
            if use_real:
                from ml.embeddings.ast_embedder import ASTEmbedder
                embedder = ASTEmbedder()
                raw_wav = (Path(settings.DATASET_DIR) / "raw" / "sessions"
                           / session_id / "audio.wav")
                audio_jsonl = session_path / "audio_metrics.jsonl"
                emb = embedder.extract_best(
                    wav_path=raw_wav if raw_wav.exists() else None,
                    jsonl_path=audio_jsonl if audio_jsonl.exists() else None,
                )
                model_id = "ast" if embedder.is_ast_available and raw_wav.exists() else "statistical"
            else:
                from ml.embeddings.audio_embedder import AudioEmbedder
                src = session_path / "audio_metrics.jsonl"
                if not src.exists():
                    return False
                emb = AudioEmbedder().extract_from_jsonl(str(src))
                model_id = "statistical"

            self.save(session_id, "audio", emb, model_id)
            return True
        except Exception as e:
            logger.error("Audio embedding failed for %s: %s", session_id, e)
            return False

    def _extract_face(self, session_id: str, session_path: Path,
                      use_real: bool) -> bool:
        try:
            if use_real:
                from ml.embeddings.vit_embedder import ViTEmbedder
                embedder = ViTEmbedder()
                raw_video = (Path(settings.DATASET_DIR) / "raw" / "sessions"
                             / session_id / "video.mp4")
                face_jsonl = session_path / "face_metrics.jsonl"
                emb = embedder.extract_best(
                    video_path=raw_video if raw_video.exists() else None,
                    jsonl_path=face_jsonl if face_jsonl.exists() else None,
                )
                model_id = "vit" if embedder.is_vit_available and raw_video.exists() else "statistical"
            else:
                from ml.embeddings.face_embedder import FaceEmbedder
                src = session_path / "face_metrics.jsonl"
                if not src.exists():
                    return False
                emb = FaceEmbedder().extract_from_jsonl(str(src))
                model_id = "statistical"

            self.save(session_id, "face", emb, model_id)
            return True
        except Exception as e:
            logger.error("Face embedding failed for %s: %s", session_id, e)
            return False

    def _extract_text(self, session_id: str, session_path: Path,
                      use_real: bool) -> bool:
        try:
            transcript_path = session_path / "transcript.txt"
            if not transcript_path.exists():
                return False

            text = transcript_path.read_text(encoding="utf-8")
            from ml.embeddings.text_embedder import TextEmbedder
            embedder = TextEmbedder(prefer_deberta=use_real)
            emb = embedder.extract(text)
            model_id = "deberta" if (use_real and embedder._prefer_deberta) else "minilm"
            self.save(session_id, "text", emb, model_id)
            return True
        except Exception as e:
            logger.error("Text embedding failed for %s: %s", session_id, e)
            return False

    def batch_extract(self, force: bool = False,
                      use_real_models: bool = False) -> Dict[str, Dict[str, bool]]:
        sessions = dataset_service.list_sessions()
        return {
            s["session_id"]: self.extract_and_cache(
                s["session_id"], force=force, use_real_models=use_real_models
            )
            for s in sessions
        }

    def index(self) -> list[dict]:
        """Return metadata for all cached embeddings."""
        import json
        results = []
        for session_dir in self.base.iterdir():
            if not session_dir.is_dir():
                continue
            meta_path = session_dir / "embedding_meta.json"
            if meta_path.exists():
                with open(meta_path, encoding="utf-8") as f:
                    meta = json.load(f)
                results.append({"session_id": session_dir.name, **meta})
        return results


embedding_service = EmbeddingService()
