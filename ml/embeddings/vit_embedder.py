from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class ViTEmbedder:
    """
    Vision Transformer face embedder.
    Extracts frame-level ViT features from a video file when available,
    falls back to statistical face embedder otherwise.
    """

    def __init__(self) -> None:
        self._model    = None
        self._processor = None
        self._is_vit_available = False
        self._try_load()

    def _try_load(self) -> None:
        try:
            from transformers import ViTModel, ViTFeatureExtractor
            self._processor = ViTFeatureExtractor.from_pretrained("google/vit-base-patch16-224")
            self._model     = ViTModel.from_pretrained("google/vit-base-patch16-224")
            self._model.eval()
            self._is_vit_available = True
            logger.info("ViTEmbedder loaded")
        except Exception as exc:
            logger.debug("ViTEmbedder: ViT unavailable — %s", exc)

    @property
    def is_vit_available(self) -> bool:
        return self._is_vit_available

    def extract_best(
        self,
        video_path: Optional[Path] = None,
        jsonl_path: Optional[Path] = None,
    ) -> np.ndarray:
        if self._is_vit_available and video_path and video_path.exists():
            return self._from_video(video_path)
        if jsonl_path and jsonl_path.exists():
            from ml.embeddings.face_embedder import FaceEmbedder
            return FaceEmbedder().extract_from_jsonl(str(jsonl_path))
        return np.zeros(768, dtype=np.float32)

    def _from_video(self, video_path: Path) -> np.ndarray:
        import torch
        try:
            import cv2
            cap = cv2.VideoCapture(str(video_path))
            frames = []
            frame_skip = max(1, int(cap.get(cv2.CAP_PROP_FPS) or 1) // 2)
            i = 0
            while len(frames) < 8:
                ret, frame = cap.read()
                if not ret:
                    break
                if i % frame_skip == 0:
                    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    frames.append(rgb)
                i += 1
            cap.release()

            if not frames:
                return np.zeros(768, dtype=np.float32)

            inputs = self._processor(images=frames, return_tensors="pt")
            with torch.no_grad():
                out = self._model(**inputs)
            # Mean pool [CLS] tokens across sampled frames
            cls = out.last_hidden_state[:, 0, :]
            return cls.mean(dim=0).numpy().astype(np.float32)
        except Exception as exc:
            logger.debug("ViTEmbedder._from_video error: %s", exc)
            return np.zeros(768, dtype=np.float32)
