"""Causal Gate-Point Representation.

Defines the detector input view strictly available immediately before
a proposed tool call:
    GatePoint = (available_prefix, proposed_tool_call)

Guarantees causal isolation: future observations and current call results
are strictly excluded. Ground-truth labels and attack metadata remain separate.
"""

from typing import Any, Dict, List
from pydantic import BaseModel, Field
from agentwatch.traces.schema import RawStep, RawToolCall


class CausalGatePoint(BaseModel):
    """Causal pre-execution decision point presented to a monitor."""
    run_id: str = Field(description="Opaque trajectory run identifier")
    gate_index: int = Field(description="Order index of this gate point in the trajectory")
    step_index: int = Field(description="Index of the step emitting this proposed call")
    available_prefix: List[RawStep] = Field(description="Interaction history strictly prior to this tool call")
    proposed_tool_call: RawToolCall = Field(description="The proposed action awaiting gate decision")
    tool_namespace: Dict[str, Any] = Field(default_factory=dict, description="Metadata of available tools schema")

    def get_feature_view(self) -> Dict[str, Any]:
        """Return the dictionary view accessible to detector models.

        Contains NO ground-truth labels, attack targets, or future observations.
        """
        return {
            "run_id": self.run_id,
            "gate_index": self.gate_index,
            "step_index": self.step_index,
            "proposed_tool_name": self.proposed_tool_call.tool_name,
            "proposed_arguments": self.proposed_tool_call.arguments,
            "prefix_step_count": len(self.available_prefix),
            "prefix_messages": [step.model_dump() for step in self.available_prefix],
        }
