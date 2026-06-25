"""
Universal Interview Capture Layer (UICL).

Every interview source — browser meeting, desktop app, uploaded recording,
webcam, RTSP camera, virtual camera — is reduced to one normalized behavioral
stream before it reaches the MBA engine. The engine never learns where media
originated (Volume 2B / Volume 4 §Platform Independence).

Components:
  models.py        source types, capability negotiation
  base.py          CaptureAdapter ABC (the source contract)
  synchronizer.py  TimestampNormalizer (source clock → session-relative clock)
  normalizer.py    InputNormalizer (unified stream → per-modality services + fusion)
  registry.py      source discovery for the Universal Meeting Launcher
"""

from backend.capture import sources  # noqa: F401  (registers built-in source descriptors)
