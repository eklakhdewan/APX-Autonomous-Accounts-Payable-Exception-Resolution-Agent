from __future__ import annotations

import pytest
from apx.agent.state_machine import (
    AgentState, TerminalOutcome, PERMITTED_TRANSITIONS,
    is_valid_transition, transition, TransitionError
)


class TestAgentStateMachine:
    """Test the bounded agent state machine."""
    
    def test_initial_state_is_detected(self):
        """Initial state must be DETECTED."""
        assert AgentState.DETECTED.value == "DETECTED"
    
    def test_valid_transitions(self):
        """Test all valid transitions."""
        assert is_valid_transition(AgentState.DETECTED, AgentState.CONTEXT_RETRIEVED)
        assert is_valid_transition(AgentState.CONTEXT_RETRIEVED, AgentState.INVESTIGATING)
        assert is_valid_transition(AgentState.INVESTIGATING, AgentState.INVESTIGATING)
        assert is_valid_transition(AgentState.INVESTIGATING, AgentState.DECISION_READY)
        assert is_valid_transition(AgentState.DECISION_READY, TerminalOutcome.RESOLVE)
        assert is_valid_transition(AgentState.DECISION_READY, TerminalOutcome.REQUEST_INFO)
        assert is_valid_transition(AgentState.DECISION_READY, TerminalOutcome.ESCALATE)
    
    def test_invalid_transitions_rejected(self):
        """Test that invalid transitions are rejected."""
        invalid_transitions = [
            (AgentState.DETECTED, AgentState.INVESTIGATING),
            (AgentState.DETECTED, AgentState.DECISION_READY),
            (AgentState.DETECTED, TerminalOutcome.RESOLVE),
            (AgentState.DETECTED, TerminalOutcome.ESCALATE),
            (AgentState.CONTEXT_RETRIEVED, AgentState.DETECTED),
            (AgentState.CONTEXT_RETRIEVED, AgentState.DECISION_READY),
            (AgentState.CONTEXT_RETRIEVED, TerminalOutcome.RESOLVE),
            (AgentState.INVESTIGATING, AgentState.DETECTED),
            (AgentState.INVESTIGATING, AgentState.CONTEXT_RETRIEVED),
            (AgentState.INVESTIGATING, TerminalOutcome.RESOLVE),
            (AgentState.INVESTIGATING, TerminalOutcome.REQUEST_INFO),
            (AgentState.DECISION_READY, AgentState.INVESTIGATING),
            (AgentState.DECISION_READY, AgentState.CONTEXT_RETRIEVED),
        ]
        
        for current, target in invalid_transitions:
            assert not is_valid_transition(current, target), f"Transition {current} -> {target} should be invalid"
    
    def test_transition_raises_error_on_invalid(self):
        """Test that transition() raises TransitionError for invalid transitions."""
        with pytest.raises(TransitionError) as exc_info:
            transition(AgentState.DETECTED, AgentState.DECISION_READY)
        
        assert "Invalid transition" in str(exc_info.value)
        assert "DETECTED" in str(exc_info.value)
        assert "DECISION_READY" in str(exc_info.value)
    
    def test_transition_returns_target_on_valid(self):
        """Test that transition() returns target on valid transition."""
        result = transition(AgentState.DETECTED, AgentState.CONTEXT_RETRIEVED)
        assert result == AgentState.CONTEXT_RETRIEVED
        
        result = transition(AgentState.DECISION_READY, TerminalOutcome.RESOLVE)
        assert result == TerminalOutcome.RESOLVE
    
    def test_terminal_outcomes_are_terminal(self):
        """Terminal outcomes should have no outgoing transitions."""
        for outcome in TerminalOutcome:
            assert len(PERMITTED_TRANSITIONS.get(outcome, set())) == 0
    
    def test_all_states_defined(self):
        """All expected states should be defined."""
        assert AgentState.DETECTED in AgentState
        assert AgentState.CONTEXT_RETRIEVED in AgentState
        assert AgentState.INVESTIGATING in AgentState
        assert AgentState.DECISION_READY in AgentState
        
        assert TerminalOutcome.RESOLVE in TerminalOutcome
        assert TerminalOutcome.REQUEST_INFO in TerminalOutcome
        assert TerminalOutcome.ESCALATE in TerminalOutcome
    
    def test_transition_table_is_complete(self):
        """All states should have defined transitions."""
        for state in AgentState:
            assert state in PERMITTED_TRANSITIONS
            assert len(PERMITTED_TRANSITIONS[state]) > 0