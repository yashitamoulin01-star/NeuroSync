from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class ASTEmbedder:
    """
    Audio Spectrogram Transformer embedder.
    Uses MIT/ast-finetuned-audioset-10-10-0.4593 when available,
    falls back to statistical audio embedder otherwise.
    """

    def __init__(self) -> None:
        self._model    = None
        self._processor = None
        self._is_ast_available = False
        self._try_load()

    def _try_load(self) -> None:
        try:
            from transformers import AutoFeatureExtractor, ASTModel
            self._processor = AutoFeatureExtractor.from_pretrained(
                "MIT/ast-finetuned-audioset-10-10-0.4593"
            )
            self._model = ASTModel.from_pretrained(
                "MIT/ast-finetuned-audioset-10-10-0.4593"
            )
            self._model.eval()
            self._is_ast_available = True
            logger.info("ASTEmbedder loaded")
        except Exception as exc:
            logger.debug("ASTEmbedder: AST model unavailable — %s", exc)

    @property
    def is_ast_available(self) -> bool:
        return self._is_ast_available

    def extract_best(
        self,
        wav_path: Optional[Path] = None,
        jsonl_path: Optional[Path] = None,
    ) -> np.ndarray:
        if self._is_ast_available and wav_path and wav_path.exists():
            return self._from_wav(wav_path)
        if jsonl_path and jsonl_path.exists():
            from ml.embeddings.audio_embedder import AudioEmbedder
            return AudioEmbedder().extract_from_jsonl(str(jsonl_path))
        return np.zeros(768, dtype=np.float32)

    def _from_wav(self, wav_path: Path) -> np.ndarray:
        import torch
        try:
            import soundfile as sf
            audio, sr = sf.read(str(wav_path))
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            inputs = self._processor(audio, sampling_rate=sr, return_tensors="pt")
            with torch.no_grad():
                out = self._model(**inputs)
            return out.last_hidden_state.mean(dim=1).squeeze(0).numpy().astype(np.float32)
        except Exception as exc:
            logger.debug("ASTEmbedder._from_wav error: %s", exc)
            return np.zeros(768, dtype=np.float32)
