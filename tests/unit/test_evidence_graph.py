"""
Unit tests for the Evidence Graph — Phase 3 reasoning component.
"""

from __future__ import annotations

import pytest

from backend.models.evidence import (
    BehavioralEvidence,
    EvidenceDimension,
    EvidencePolarity,
)
from backend.reasoning.graph.evidence_graph import EdgeType, EvidenceGraph


def _ev(id: str, dim: EvidenceDimension, polarity: EvidencePolarity,
        modalities: list | None = None, contribution: float = 0.2) -> BehavioralEvidence:
    return BehavioralEvidence(
        id=id, dimension=dim, polarity=polarity,
        description=f"test evidence {id}",
        source_modalities=modalities or ["face"],
        contribution=contribution,
    )


class TestEvidenceGraphBuild:

    def test_empty_graph(self):
        g = EvidenceGraph().build()
        assert g.nodes == {}
        assert g.edges == []

    def test_single_node(self):
        ev = _ev("e1", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE)
        g = EvidenceGraph().add_many([ev]).build()
        assert len(g.nodes) == 1
        assert len(g.edges) == 0   # no edges with one node

    def test_reinforcing_edges_different_modalities(self):
        """Same dim, same polarity, DIFFERENT modalities → REINFORCES."""
        ev1 = _ev("e1", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE, ["face"])
        ev2 = _ev("e2", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE, ["audio"])
        g = EvidenceGraph().add_many([ev1, ev2]).build()
        edge_types = {e.edge_type for e in g.edges}
        assert EdgeType.REINFORCES in edge_types

    def test_contradicting_edges(self):
        """Same dim, opposing polarity → CONTRADICTS."""
        ev1 = _ev("e1", EvidenceDimension.STRESS, EvidencePolarity.POSITIVE, ["face"])
        ev2 = _ev("e2", EvidenceDimension.STRESS, EvidencePolarity.NEGATIVE, ["audio"])
        g = EvidenceGraph().add_many([ev1, ev2]).build()
        edge_types = {e.edge_type for e in g.edges}
        assert EdgeType.CONTRADICTS in edge_types

    def test_supports_same_modality(self):
        """Same dim, same polarity, SAME modality → SUPPORTS (not REINFORCES)."""
        ev1 = _ev("e1", EvidenceDimension.ENGAGEMENT, EvidencePolarity.POSITIVE, ["face"])
        ev2 = _ev("e2", EvidenceDimension.ENGAGEMENT, EvidencePolarity.POSITIVE, ["face"])
        g = EvidenceGraph().add_many([ev1, ev2]).build()
        edge_types = {e.edge_type for e in g.edges}
        assert EdgeType.SUPPORTS in edge_types
        assert EdgeType.REINFORCES not in edge_types

    def test_different_dims_no_edges(self):
        """Different dimensions do not produce edges."""
        ev1 = _ev("e1", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE, ["face"])
        ev2 = _ev("e2", EvidenceDimension.STRESS,     EvidencePolarity.POSITIVE, ["face"])
        g = EvidenceGraph().add_many([ev1, ev2]).build()
        assert len(g.edges) == 0


class TestEvidenceGraphConflictScore:

    def test_no_conflicts_gives_zero(self):
        ev1 = _ev("e1", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE, ["face"])
        ev2 = _ev("e2", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE, ["audio"])
        g = EvidenceGraph().add_many([ev1, ev2]).build()
        assert g.conflict_score() == 0.0

    def test_contradictions_increase_conflict(self):
        evs = [
            _ev("e1", EvidenceDimension.CONFIDENCE, EvidencePolarity.POSITIVE, ["face"]),
            _ev("e2", EvidenceDimension.CONFIDENCE, EvidencePolarity.NEGATIVE, ["audio"]),
            _ev("e3", EvidenceDimension.STRESS,     EvidencePolarity.POSITIVE, ["face"]),
            _ev("e4", EvidenceDimension.STRESS,     EvidencePolarity.NEGATIVE, ["audio"]),
        ]
        g = EvidenceGraph().add_many(evs).build()
        assert g.conflict_score() > 0.0

    def test_conflict_score_bounded(self):
        evs = [
            _ev(f"e{i}", EvidenceDimension.CONFIDENCE,
                EvidencePolarity.POSITIVE if i % 2 == 0 else EvidencePolarity.NEGATIVE,
                ["face" if i % 2 == 0 else "audio"])
            for i in range(10)
        ]
        g = EvidenceGraph().add_many(evs).build()
        score = g.conflict_score()
        assert 0.0 <= score <= 1.0


class TestEvidenceGraphQuery:

    def test_evidence_for_dimension(self):
        ev1 = _ev("e1", EvidenceDimension.CONFIDENCE,  EvidencePolarity.POSITIVE, ["face"])
        ev2 = _ev("e2", EvidenceDimension.STRESS,      EvidencePolarity.NEGATIVE, ["audio"])
        ev3 = _ev("e3", EvidenceDimension.CONFIDENCE,  EvidencePolarity.NEGATIVE, ["audio"])
        g = EvidenceGraph().add_many([ev1, ev2, ev3]).build()
        conf_evs = g.evidence_for(EvidenceDimension.CONFIDENCE)
        assert len(conf_evs) == 2

    def test_summary_keys(self):
        ev = _ev("e1", EvidenceDimension.ENGAGEMENT, EvidencePolarity.POSITIVE)
        g = EvidenceGraph().add_many([ev]).build()
        s = g.summary()
        assert "node_count" in s
        assert "edge_count" in s
        assert "conflict_score" in s
        assert "cross_modal_agreement" in s
