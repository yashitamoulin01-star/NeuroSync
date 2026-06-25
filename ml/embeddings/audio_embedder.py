from __future__ import annotations

import json
import logging

import numpy as np

logger = logging.getLogger(__name__)

_DIM = 16   # number of statistical audio features per timestep, aggregated


class AudioEmbedder:
    """Statistical audio embedding from JSONL metric files."""

    def extract_from_jsonl(self, jsonl_path: str) -> np.ndarray:
        try:
            rows = []
            with open(jsonl_path, encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        rows.append(json.loads(line))
            if not rows:
                return np.zeros(_DIM, dtype=np.float32)

            keys = ["pitch_mean", "pitch_variance", "speaking_pace", "pause_ratio",
                    "energy_level", "vocal_stability", "voice_stress_score"]
            mat = []
            for row in rows:
                vec = [float(row.get(k, 0.0)) for k in keys]
                mat.append(vec)

            arr = np.array(mat, dtype=np.float32)
            mean = arr.mean(axis=0)
            std  = arr.std(axis=0)
            feat = np.concatenate([mean, std])[:_DIM]
            pad  = _DIM - len(feat)
            if pad > 0:
                feat = np.pad(feat, (0, pad))
            return feat.astype(np.float32)
        except Exception as exc:
            logger.debug("AudioEmbedder error: %s", exc)
            return np.zeros(_DIM, dtype=np.float32)
