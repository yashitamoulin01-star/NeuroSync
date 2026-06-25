"""
Unit tests for the Behavioral State Machine — Phase 3.
"""

from __future__ import annotations

import pytest

from backend.reasoning.state_machine.behavioral_state import (
    BehavioralState,
    StateTransitionResult,
    next_state,
)


def _next(current: BehavioralState, elapsed: float = 90.0,
          confidence: float = 0.65, stress: float = 0.30,
          communication: float = 0.60, engagement: float = 0.55,
          pattern: str = "stable") -> StateTransitionResult:
    return next_state(current, elapsed, confidence, stress,
                      communication, engagement, pattern)


class TestWarmingUpTransitions:

    def test_stays_warming_up_before_threshold(self):
        result = _next(BehavioralState.WARMING_UP, elapsed=20.0)
        # Should still be in warming_up or settling — NOT confident
        assert result.current != BehavioralState.CONFIDENT

    def test_transitions_to_settling_after_45s(self):
        result = _next(BehavioralState.WARMING_UP, elapsed=60.0)
        assert result.current != BehavioralState.WARMING_UP

    def test_state_changed_flag(self):
        result = _next(BehavioralState.WARMING_UP, elapsed=60.0)
        assert result.changed is True


class TestSettlingTransitions:

    def test_settles_to_confident_high_confidence_low_stress(self):
        result = _next(BehavioralState.SETTLING, elapsed=90.0,
                       confidence=0.75, stress=0.20)
        assert result.current == BehavioralState.CONFIDENT

    def test_does_not_transition_low_confidence(self):
        result = _next(BehavioralState.SETTLING, elapsed=90.0,
                       confidence=0.40, stress=0.60)
        assert result.current != BehavioralState.CONFIDENT


class TestStressedTransitions:

    def test_stressed_state_high_stress(self):
        result = _next(BehavioralState.CONFIDENT, elapsed=120.0,
                       confidence=0.35, stress=0.75, pattern="deteriorating")
        assert result.current == BehavioralState.STRESSED

    def test_recovery_from_stressed(self):
        result = _next(BehavioralState.STRESSED, elapsed=150.0,
                       confidence=0.62, stress=0.25, pattern="recovering")
        assert result.current == BehavioralState.RECOVERING


class TestReturnType:

    def test_returns_state_transition_result(self):
        result = _next(BehavioralState.STABLE)
        assert isinstance(result, StateTransitionResult)
        assert isinstance(result.current, BehavioralState)
        assert isinstance(result.changed, bool)
        assert isinstance(result.reason, str)

    def test_no_change_when_stable(self):
        result = _next(BehavioralState.STABLE, elapsed=200.0,
                       confidence=0.68, stress=0.28, pattern="stable")
        assert result.current == BehavioralState.STABLE
        assert result.changed is False
