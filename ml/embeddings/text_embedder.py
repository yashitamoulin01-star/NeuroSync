from __future__ import annotations

import logging
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

ROOT = Path(__file__).parent.parent.parent


class TextEmbedder:
    """
    Text embedding extractor.
    Prefers DeBERTa [CLS] embeddings (768-d) when the fine-tuned model exists
    and prefer_deberta=True.  Falls back to sentence-transformers MiniLM (384-d).
    """

    def __init__(self, prefer_deberta: bool = False) -> None:
        self._prefer_deberta = prefer_deberta
        self._model    = None
        self._tokenizer = None
        self._device   = None
        self._dim: int = 384      # updated after model loads
        self._init()

    def _init(self) -> None:
        model_dir = ROOT / "models" / "deberta" / "best"
        if self._prefer_deberta and (model_dir / "model.pt").exists():
            self._load_deberta(model_dir)
        if self._model is None:
            self._load_minilm()

    def _load_deberta(self, model_dir: Path) -> None:
        try:
            import torch
            from ml.training.deberta_trainer import MultiTaskDeBERTa
            from transformers import AutoTokenizer

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model  = MultiTaskDeBERTa.from_pretrained(str(model_dir))
            model  = model.to(device)
            model.eval()

            data      = torch.load(model_dir / "model.pt", map_location="cpu")
            tokenizer = AutoTokenizer.from_pretrained(data.get("base_model_name", "microsoft/deberta-v3-base"))

            self._model     = model
            self._tokenizer = tokenizer
            self._device    = device
            self._dim       = model.deberta.config.hidden_size
            self._type      = "deberta"
            logger.info("TextEmbedder: DeBERTa loaded on %s (dim=%d)", device, self._dim)
        except Exception as exc:
            logger.debug("TextEmbedder: DeBERTa unavailable — %s", exc)

    def _load_minilm(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer("all-MiniLM-L6-v2")
            self._dim   = 384
            self._type  = "minilm"
            logger.info("TextEmbedder: MiniLM loaded (dim=384)")
        except Exception as exc:
            logger.warning("TextEmbedder: MiniLM unavailable — %s", exc)
            self._model = None
            self._dim   = 384
            self._type  = "zeros"

    def extract(self, text: str) -> np.ndarray:
        if not text or not text.strip():
            return np.zeros(self._dim, dtype=np.float32)

        if self._type == "deberta" and self._model is not None:
            return self._extract_deberta(text)
        if self._type == "minilm" and self._model is not None:
            return self._extract_minilm(text)
        return np.zeros(self._dim, dtype=np.float32)

    def _extract_deberta(self, text: str) -> np.ndarray:
        import torch
        try:
            enc = self._tokenizer(
                text, max_length=128, padding="max_length",
                truncation=True, return_tensors="pt",
            )
            enc = {k: v.to(self._device) for k, v in enc.items()}
            with torch.no_grad():
                out = self._model.deberta(**enc)
            return out.last_hidden_state[:, 0, :].squeeze(0).cpu().numpy().astype(np.float32)
        except Exception as exc:
            logger.debug("TextEmbedder._extract_deberta error: %s", exc)
            return np.zeros(self._dim, dtype=np.float32)

    def _extract_minilm(self, text: str) -> np.ndarray:
        try:
            return self._model.encode(text, convert_to_numpy=True).astype(np.float32)
        except Exception as exc:
            logger.debug("TextEmbedder._extract_minilm error: %s", exc)
            return np.zeros(self._dim, dtype=np.float32)

    @property
    def embedding_dim(self) -> int:
        return self._dim
