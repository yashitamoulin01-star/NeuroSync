"""
Evidence Graph — organizes behavioral evidence into a connected structure.

Instead of treating every evidence item as independent, the graph represents
relationships between observations, enabling the backend to reason about
cross-modal agreement and contradiction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple

from backend.models.evidence import (
    BehavioralEvidence,
    EvidenceDimension,
    EvidencePolarity,
)


class EdgeType(str, Enum):
    REINFORCES  = "reinforces"   # same dimension, same polarity, different modalities
    SUPPORTS    = "supports"     # same dimension, same polarity, same modality
    CONTRADICTS = "contradicts"  # same dimension, opposing polarity


@dataclass
class EvidenceEdge:
    source_id:        str
    target_id:        str
    edge_type:        EdgeType
    shared_dimension: EvidenceDimension
    weight:           float  # 0–1 strength of relationship


@dataclass
class EvidenceGraph:
    nodes: Dict[str, BehavioralEvidence] = field(default_factory=dict)
    edges: List[EvidenceEdge] = field(default_factory=list)
    _built: bool = field(default=False, repr=False, init=False)

    def add_many(self, evidence_list: List[BehavioralEvidence]) -> "EvidenceGraph":
        for ev in evidence_list:
            self.nodes[ev.id] = ev
        return self

    def build(self) -> "EvidenceGraph":
        """Auto-detect support/contradiction relationships between all node pairs."""
        if self._built:
            return self
        ids = list(self.nodes.keys())
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                a = self.nodes[ids[i]]
                b = self.nodes[ids[j]]
                if a.dimension != b.dimension:
                    continue
                same_modality = bool(set(a.source_modalities) & set(b.source_modalities))
                if a.polarity == b.polarity:
                    etype  = EdgeType.SUPPORTS if same_modality else EdgeType.REINFORCES
                    weight = 0.6 if same_modality else 0.85
                else:
                    etype  = EdgeType.CONTRADICTS
                    weight = 0.9
                self.edges.append(
                    EvidenceEdge(a.id, b.id, etype, a.dimension, weight)
                )
        self._built = True
        return self

    # ── Query API ─────────────────────────────────────────────────────────────

    def evidence_for(self, dim: EvidenceDimension) -> List[BehavioralEvidence]:
        return [ev for ev in self.nodes.values() if ev.dimension == dim]

    def supporting(self, dim: EvidenceDimension) -> List[BehavioralEvidence]:
        return [ev for ev in self.evidence_for(dim)
                if ev.polarity == EvidencePolarity.POSITIVE]

    def opposing(self, dim: EvidenceDimension) -> List[BehavioralEvidence]:
        return [ev for ev in self.evidence_for(dim)
                if ev.polarity == EvidencePolarity.NEGATIVE]

    def contradictions(self) -> List[Tuple[BehavioralEvidence, BehavioralEvidence]]:
        return [
            (self.nodes[e.source_id], self.nodes[e.target_id])
            for e in self.edges if e.edge_type == EdgeType.CONTRADICTS
        ]

    def reinforcements(
        self, dim: EvidenceDimension
    ) -> List[Tuple[BehavioralEvidence, BehavioralEvidence]]:
        return [
            (self.nodes[e.source_id], self.nodes[e.target_id])
            for e in self.edges
            if e.edge_type == EdgeType.REINFORCES and e.shared_dimension == dim
        ]

    def conflict_score(self) -> float:
        """0–1: proportion of edge weight that is contradiction."""
        if not self.edges:
            return 0.0
        c     = sum(e.weight for e in self.edges if e.edge_type == EdgeType.CONTRADICTS)
        total = sum(e.weight for e in self.edges)
        return c / total if total > 0 else 0.0

    def cross_modal_agreement(self) -> float:
        """1.0 = full cross-modal agreement, 0.0 = full contradiction."""
        reinforce  = sum(e.weight for e in self.edges if e.edge_type == EdgeType.REINFORCES)
        contradict = sum(e.weight for e in self.edges if e.edge_type == EdgeType.CONTRADICTS)
        total = reinforce + contradict
        return reinforce / total if total > 0 else 1.0

    def summary(self) -> Dict:
        return {
            "node_count":            len(self.nodes),
            "edge_count":            len(self.edges),
            "conflict_score":        round(self.conflict_score(), 3),
            "cross_modal_agreement": round(self.cross_modal_agreement(), 3),
            "contradiction_count":   sum(1 for e in self.edges
                                         if e.edge_type == EdgeType.CONTRADICTS),
            "reinforcement_count":   sum(1 for e in self.edges
                                         if e.edge_type == EdgeType.REINFORCES),
        }
