from __future__ import annotations

from enum import Enum
from typing import Final


class AgentState(str, Enum):
    """Agent states in the investigation workflow."""
    DETECTED = "DETECTED"
    CONTEXT_RETRIEVED = "CONTEXT_RETRIEVED"
    INVESTIGATING = "INVESTIGATING"
    DECISION_READY = "DECISION_READY"


class TerminalOutcome(str, Enum):
    """Terminal investigation outcomes."""
    RESOLVE = "RESOLVE"
    REQUEST_INFO = "REQUEST_INFO"
    ESCALATE = "ESCALATE"


# Permitted transitions: source_state -> set of allowed next states
PERMITTED_TRANSITIONS: Final[dict[AgentState, set[AgentState | TerminalOutcome]]] = {
    AgentState.DETECTED: {AgentState.CONTEXT_RETRIEVED},
    AgentState.CONTEXT_RETRIEVED: {AgentState.INVESTIGATING},
    AgentState.INVESTIGATING: {AgentState.INVESTIGATING, AgentState.DECISION_READY},
    AgentState.DECISION_READY: {TerminalOutcome.RESOLVE, TerminalOutcome.REQUEST_INFO, TerminalOutcome.ESCALATE},
}


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    def __init__(self, current: AgentState, target: AgentState | TerminalOutcome):
        self.current = current
        self.target = target
        allowed = PERMITTED_TRANSITIONS.get(current, set())
        super().__init__(
            f"Invalid transition from {current.value} to {target.value}. "
            f"Allowed: {[s.value for s in allowed]}"
        )


def is_valid_transition(current: AgentState, target: AgentState | TerminalOutcome) -> bool:
    """Check if a transition is permitted."""
    return target in PERMITTED_TRANSITIONS.get(current, set())


def transition(current: AgentState, target: AgentState | TerminalOutcome) -> AgentState | TerminalOutcome:
    """
    Perform a state transition, raising TransitionError if invalid.
    
    Returns the new state/outcome on success.
    """
    if not is_valid_transition(current, target):
        raise TransitionError(current, target)
    return target