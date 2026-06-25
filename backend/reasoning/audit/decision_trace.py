"""
Decision Trace — reconstructable audit trail for every reasoning window.

Every recommendation becomes an audit trail.
Every conclusion is traceable back to its supporting observations.

This is the difference between a black-box model and an explainable system.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class DecisionTrace:
    """Full audit record for a single reasoning window."""
    trace_id:             str   = field(default_factory=lambda: str(uuid.uuid4())[:8])
    session_id:           str   = ""
    window_index:         int   = 0
    timestamp:            float = field(default_factory=time.time)
    elapsed_seconds:      float = 0.0

    # Evidence summary
    evidence_count:       int         = 0
    conflict_count:       int         = 0
    modalities_active:    List[str]   = field(default_factory=list)

    # Behavioral state
    behavioral_state:     str = "warming_up"
    segment:              str = "introduction"
    pattern:              str = ""
    state_changed:        bool = False
    state_change_reason:  str = ""

    # Scores
    raw_scores:           Dict[str, float] = field(default_factory=dict)
    calibrated_scores:    Dict[str, float] = field(default_factory=dict)
    reliability:          str              = "insufficient"
    prediction_confidence: float           = 0.0
    signal_quality:       str              = "poor"

    # Rules
    rules_fired:          List[str] = field(default_factory=list)
    rule_notes:           List[str] = field(default_factory=list)

    # Temporal
    trends:               Dict[str, str] = field(default_factory=dict)

    # Insights
    insights:             List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "trace_id":             self.trace_id,
            "session_id":           self.session_id,
            "window_index":         self.window_index,
            "timestamp":            self.timestamp,
            "elapsed_seconds":      round(self.elapsed_seconds, 1),
            "evidence_count":       self.evidence_count,
            "conflict_count":       self.conflict_count,
            "modalities_active":    self.modalities_active,
            "behavioral_state":     self.behavioral_state,
            "segment":              self.segment,
            "pattern":              self.pattern,
            "state_changed":        self.state_changed,
            "state_change_reason":  self.state_change_reason,
            "raw_scores":           {k: round(v, 3) for k, v in self.raw_scores.items()},
            "calibrated_scores":    {k: round(v, 3) for k, v in self.calibrated_scores.items()},
            "reliability":          self.reliability,
            "prediction_confidence":round(self.prediction_confidence, 3),
            "signal_quality":       self.signal_quality,
            "rules_fired":          self.rules_fired,
            "rule_notes":           self.rule_notes,
            "trends":               self.trends,
            "insights":             self.insights,
        }
