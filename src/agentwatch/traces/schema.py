"""Phase 2 Data Models and Serialization Contracts.

Extends AgentWatch trace representations with explicit schema versioning,
normalized trace projections, bidirectional call-to-result linking,
and strict causal integrity guarantees.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


SCHEMA_VERSION = "2.0.0"
RUN_MANIFEST_VERSION = "2.0.0"


class RawToolCall(BaseModel):
    """Represents a proposed tool call emitted by an agent."""
    call_id: str = Field(description="Unique identifier of the tool call")
    tool_name: str = Field(description="Function or tool name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Parsed arguments dictionary")


class RawToolResult(BaseModel):
    """Represents an observation returned by the environment runtime."""
    call_id: str = Field(description="Matching tool call identifier")
    output: Any = Field(description="Tool return value or error message")
    error: Optional[str] = Field(default=None, description="Exception string if execution failed")


class RawStep(BaseModel):
    """Represents an individual interaction step in the agent trajectory."""
    step_index: int = Field(description="0-indexed step counter")
    role: str = Field(description="Role: system, user, assistant, tool")
    content: Optional[str] = Field(default=None, description="Textual content if any")
    tool_calls: List[RawToolCall] = Field(default_factory=list, description="Proposed tool calls if role is assistant")
    tool_results: List[RawToolResult] = Field(default_factory=list, description="Tool execution outputs if role is tool")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class RawExecutionRecord(BaseModel):
    """Complete, immutable raw trace of an agent execution."""
    schema_version: str = Field(default=SCHEMA_VERSION, description="Data contract schema version")
    run_id: str = Field(description="Opaque unique run identifier")
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    benchmark_version: str = Field(description="Benchmark suite version, e.g., 'v1'")
    suite_name: str = Field(description="Task suite name, e.g., 'workspace'")
    user_task_id: str = Field(description="User task identifier")
    injection_task_id: Optional[str] = Field(default=None, description="Injection task identifier if attacked")
    attack_name: Optional[str] = Field(default=None, description="Attack strategy identifier if attacked")
    agent_model: str = Field(description="Model or agent identifier")
    steps: List[RawStep] = Field(default_factory=list, description="Ordered interaction history")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution environment metadata")


class GroundTruthLabelRecord(BaseModel):
    """Decoupled ground-truth outcome record linked by run_id.

    Maintains clean separation between:
    1. Attack assignment (injected)
    2. Malicious payload exposure (exposure_detected)
    3. Harmful action proposed (harmful_action_proposed)
    4. Harmful action executed (harmful_action_executed)
    5. Final benchmark security outcome (security_success)
    6. User task utility outcome (utility_success)
    """
    schema_version: str = Field(default=SCHEMA_VERSION, description="Data contract schema version")
    run_id: str = Field(description="Link to RawExecutionRecord.run_id")
    utility_success: bool = Field(description="Benchmark utility verification boolean")
    security_success: Optional[bool] = Field(default=None, description="Benchmark security breach boolean (None for benign)")
    injected: bool = Field(description="Whether this was an attacked execution")
    exposure_detected: bool = Field(default=False, description="Whether injection payload was exposed in tool outputs")
    harmful_action_proposed: bool = Field(default=False, description="Whether agent proposed any action fulfilling attacker goal")
    harmful_action_executed: bool = Field(default=False, description="Whether runtime executed any action fulfilling attacker goal")
    first_harmful_step: Optional[int] = Field(default=None, description="Step index of first harmful action if deterministically verified")
    harmful_timing_verified: bool = Field(default=False, description="Whether first_harmful_step was experimentally verified")
    # Granular Phase 5E Attack-Outcome Taxonomy Extensions
    post_exposure_decision_occurred: bool = Field(default=False, description="Whether model issued tool proposal strictly after observing payload")
    benchmark_confirmed_success: bool = Field(default=False, description="Whether benchmark ground-truth security check confirms breach")
    ambiguous_match_count: int = Field(default=0, description="Count of ambiguous or partial harmful matches requiring manual review")
    trace_evidence_events: List[str] = Field(default_factory=list, description="Ordered references to trace step events supporting outcome classification")



class LinkedToolInvocation(BaseModel):
    """Bidirectional link between a proposed tool call and its runtime result.

    Preserves causal separation: the result is recorded here for post-hoc analysis,
    while gate points only expose the call and its prefix history.
    """
    call_id: str = Field(description="Unique tool call identifier")
    tool_name: str = Field(description="Tool function name")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool invocation arguments")
    call_step_index: int = Field(description="Step index where call was proposed by assistant")
    result_step_index: Optional[int] = Field(default=None, description="Step index where tool result was observed (None if missing)")
    output: Optional[Any] = Field(default=None, description="Observed output string/data")
    error: Optional[str] = Field(default=None, description="Runtime execution error if failed")
    is_executed: bool = Field(default=False, description="Whether the tool runtime returned an observation")


class NormalizedTrace(BaseModel):
    """Clean, structured projection reconstructed from RawExecutionRecord."""
    schema_version: str = Field(default=SCHEMA_VERSION, description="Data contract schema version")
    run_id: str = Field(description="Opaque unique run identifier")
    user_task_id: str = Field(description="User task identifier")
    injection_task_id: Optional[str] = Field(default=None)
    attack_name: Optional[str] = Field(default=None)
    agent_model: str = Field(description="Model identifier")
    total_steps: int = Field(description="Total interaction steps recorded")
    tool_invocations: List[LinkedToolInvocation] = Field(default_factory=list, description="Linked proposed tool calls and results")
    gate_point_count: int = Field(default=0, description="Total causal gate points captured")
    is_cleanly_terminated: bool = Field(default=True, description="Whether trajectory terminated normally")


class GatePointDatasetRecord(BaseModel):
    """Phase 3 Gate-Point Dataset View.

    Represents one decision point for a proposed tool call awaiting monitor intervention.
    Strictly isolates pre-execution features from labels, future observations, and attack details.
    """
    schema_version: str = Field(default=SCHEMA_VERSION, description="Dataset schema version")
    gate_point_id: str = Field(description="Unique identifier: {run_id}_gp_{gate_index}")
    run_id: str = Field(description="Reference to originating trajectory run_id")
    user_task_id: str = Field(description="Benchmark user task identifier")
    gate_index: int = Field(description="Order index of this gate point in trajectory")
    step_index: int = Field(description="Step index of the assistant turn proposing this call")
    proposed_tool_name: str = Field(description="Proposed function name")
    proposed_arguments: Dict[str, Any] = Field(default_factory=dict, description="Proposed tool arguments")
    prefix_step_count: int = Field(description="Number of interaction steps preceding this decision")
    available_prefix: List[Dict[str, Any]] = Field(description="Sanitized pre-execution interaction messages")
    # Post-hoc evaluation & execution references (strictly separated from pre-execution monitor view)
    call_id: str = Field(description="Matching tool call identifier")
    is_executed: bool = Field(description="Whether the call was executed by runtime")
    result_step_index: Optional[int] = Field(default=None, description="Step index where observation occurred")
    has_execution_error: bool = Field(default=False, description="Whether execution returned an error")
    # Ground-truth annotations (evaluation only)
    trajectory_injected: bool = Field(description="Whether originating trajectory was an attacked task")
    exposure_prior_to_call: bool = Field(description="Whether payload appeared in an observation strictly prior to this call")
    is_harmful_action: bool = Field(default=False, description="Whether this specific call constitutes harmful attacker action")
    security_breached_at_or_before: bool = Field(default=False, description="Whether trajectory had been breached at or before this point")

    def get_feature_view(self) -> Dict[str, Any]:
        """Return the pre-execution feature dictionary presented to a detector.

        Guarantees that post-hoc labels, future observations, execution results,
        and attack metadata are strictly excluded.
        """
        return {
            "gate_point_id": self.gate_point_id,
            "run_id": self.run_id,
            "user_task_id": self.user_task_id,
            "gate_index": self.gate_index,
            "step_index": self.step_index,
            "proposed_tool_name": self.proposed_tool_name,
            "proposed_arguments": self.proposed_arguments,
            "prefix_step_count": self.prefix_step_count,
            "available_prefix": self.available_prefix,
        }



class TrajectoryDatasetRecord(BaseModel):
    """Phase 3 Trajectory Dataset View.

    Represents one complete trajectory execution for statistical analysis of false alarms and outcomes.
    """
    schema_version: str = Field(default=SCHEMA_VERSION, description="Dataset schema version")
    run_id: str = Field(description="Opaque unique run identifier")
    user_task_id: str = Field(description="Benchmark user task identifier")
    injection_task_id: Optional[str] = Field(default=None, description="Injection task identifier if attacked")
    attack_name: Optional[str] = Field(default=None, description="Attack strategy identifier if attacked")
    agent_model: str = Field(description="Agent model name")
    total_steps: int = Field(description="Total interaction steps recorded")
    total_proposed_calls: int = Field(description="Total proposed tool calls emitted")
    total_gate_points: int = Field(description="Total gate points captured")
    total_executed_calls: int = Field(description="Total tool calls returned with observations")
    # 6-Dimensional Outcome Labels
    injected: bool = Field(description="Attack assigned to trajectory")
    exposure_detected: bool = Field(description="Malicious payload observed anywhere in trajectory")
    harmful_action_proposed: bool = Field(default=False, description="Harmful action proposed by agent")
    harmful_action_executed: bool = Field(default=False, description="Harmful action executed by environment")
    security_success: Optional[bool] = Field(default=None, description="Benchmark security breach boolean (None for benign)")
    utility_success: bool = Field(description="Benchmark utility verification boolean")
    # Verification and Integrity
    raw_hash: str = Field(description="SHA-256 hash of authoritative raw record")
    normalized_hash: str = Field(description="SHA-256 hash of normalized trace")
    is_deterministic: bool = Field(default=True, description="Whether trace reconstruction is deterministic")

