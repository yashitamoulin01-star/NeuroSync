# Responsible AI Policy — NeuroSync Platform

**Version:** 1.2 | **Effective:** 2026-06-24 | **Owner:** Engineering & Ethics Review Board

---

## Purpose

This document describes the principles governing the design, deployment, and use of AI within the NeuroSync platform. It applies to all users, operators, and organizations deploying NeuroSync in any context.

For the full in-application governance policy, see the [Governance page](/governance) or `frontend/src/app/governance/page.tsx`.

---

## Core Principles

**Human decisions, AI evidence.** NeuroSync produces behavioral evidence. It does not make hiring decisions. Every consequential employment decision remains with a qualified human reviewer. The platform is a decision-support tool, not a decision-making system.

**Explainability over accuracy theater.** Every score links to the specific timestamp and signal that produced it. Reasoning chains, evidence weights, and contradiction flags are inspectable. Reliability tiers (insufficient / low / medium / high) are attached to every output. Uncertain outputs are flagged, not silently presented as conclusions.

**No silent certainty.** A score of "confidence: 68%" means something different across a 2-minute session with noisy audio versus a 15-minute session with clear signals. NeuroSync makes this visible through reliability tiers rather than presenting a precise-looking number without context.

**Local inference only.** All AI processing runs on the operator's infrastructure. Candidate data — audio, video, transcripts, behavioral scores — never leaves the operator's server. There are no cloud AI calls, no telemetry transmissions, and no external API dependencies at inference time.

**Continuous model governance.** Production model changes require passing 10 golden test scenarios at ≥95% pass rate, an ECE calibration check, a regression gate against the current production version, and manual approval. No model is deployed automatically.

---

## What NeuroSync Measures

NeuroSync measures behavioral signals observable in speech, voice, and facial expression during a structured session:

- **Confidence** — language assertiveness, vocal energy, hesitation frequency
- **Engagement** — response depth, active presence markers, topic consistency
- **Communication** — clarity, pace, structure, filler word rate
- **Consistency** — cross-modal alignment between verbal and physiological signals
- **Composure** — inverse of detected stress markers (vocal jitter, facial tension)

These are behavioral observations from a single session or series of sessions. They are not personality assessments, intelligence tests, or predictions of job performance.

---

## Mandatory Constraints

- NeuroSync scores must not be used as the sole basis for any hiring, promotion, demotion, or adverse employment decision.
- All sessions triggering a high-severity flag require independent human review before any action is taken.
- Operators must inform candidates that AI-assisted behavioral analysis is being used before the session begins.
- Scores must be interpreted in the context of the full session evidence, not as isolated numbers.
- Operators are responsible for compliance with applicable employment law and data protection regulations in their jurisdiction.

---

## Known Limitations

| Limitation | Status |
|------------|--------|
| Demographic parity testing | Not yet performed. Training labels contain no demographic metadata. |
| Cross-accent Whisper accuracy | Not benchmarked. Accuracy degrades with non-standard accents. |
| Lighting robustness (face analysis) | Not benchmarked. Performance degrades in low or uneven lighting. |
| Neurodivergence accommodation | Not assessed. Scoring models are calibrated on standard behavioral baselines. |

These are genuine gaps. Operators should apply additional human judgment in contexts where these limitations are likely to affect scoring quality.

Full known limitations: [KNOWN_LIMITATIONS.md](./KNOWN_LIMITATIONS.md)

---

## Data Governance

- Session data is stored in a local SQLite database on the operator's infrastructure.
- Audio is processed in memory and not persisted by default (`DATASET_AUTO_SAVE=False`).
- Video frames are stored locally and are never transmitted externally.
- Candidates have the right to request access, export, and erasure of their data through the Candidate Portal.
- GDPR Art. 17 (right to erasure) and Art. 20 (right to portability) are supported.

---

## Responsible Disclosure

If you identify a potential ethical concern, bias risk, or security vulnerability in NeuroSync, please report it privately to the engineering team before any public disclosure.
