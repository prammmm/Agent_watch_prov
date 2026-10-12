"""Instrumented Execution Wrapper for AgentDojo.

Intercepts tool execution in AgentDojo pipelines to construct causal gate points,
records complete raw trajectories, detects injection exposure, and logs traces
with zero secret leakage.
"""

import copy
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from agentdojo.agent_pipeline.base_pipeline_element import BasePipelineElement
from agentdojo.functions_runtime import EmptyEnv, Env, FunctionsRuntime
from agentdojo.types import ChatAssistantMessage, ChatMessage, ChatToolResultMessage

from agentwatch.traces.schema import (
    RawExecutionRecord,
    RawStep,
    RawToolCall,
    RawToolResult,
    GroundTruthLabelRecord,
)
from agentwatch.traces.gate_point import CausalGatePoint


class InstrumentedPipelineElement(BasePipelineElement):
    """Pipeline element that intercepts assistant messages and tool executions

    to capture causal gate points and record execution traces.
    """

    def __init__(
        self,
        wrapped_element: BasePipelineElement,
        run_id: str,
        benchmark_version: str,
        suite_name: str,
        user_task_id: str,
        injection_task_id: Optional[str] = None,
        attack_name: Optional[str] = None,
        agent_model: str = "unknown",
        injected_payloads: Optional[Dict[str, str]] = None,
    ):
        super().__init__()
        self.wrapped_element = wrapped_element
        self.name = getattr(wrapped_element, "name", "instrumented")
        self.run_id = run_id
        self.benchmark_version = benchmark_version
        self.suite_name = suite_name
        self.user_task_id = user_task_id
        self.injection_task_id = injection_task_id
        self.attack_name = attack_name
        self.agent_model = agent_model
        self.injected_payloads = injected_payloads or {}

        self.recorded_steps: List[RawStep] = []
        self.gate_points: List[CausalGatePoint] = []
        self.exposure_observed: bool = False
        self._gate_counter: int = 0

    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> Tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        """Intercept before and after execution of the wrapped element."""
        # 1. Inspect existing messages and check if a proposed tool call is pending
        if len(messages) > 0:
            last_msg = messages[-1]
            if last_msg.get("role") == "assistant":
                tool_calls = last_msg.get("tool_calls")
                if tool_calls is not None:
                    # Capture causal gate points for each proposed tool call
                    prefix_steps = self._convert_messages_to_steps(messages[:-1])
                    for tc in tool_calls:
                        call_id = getattr(tc, "id", None) or str(uuid.uuid4())
                        raw_tc = RawToolCall(
                            call_id=call_id,
                            tool_name=tc.function,
                            arguments=copy.deepcopy(tc.args),
                        )
                        gp = CausalGatePoint(
                            run_id=self.run_id,
                            gate_index=self._gate_counter,
                            step_index=len(prefix_steps),
                            available_prefix=copy.deepcopy(prefix_steps),
                            proposed_tool_call=raw_tc,
                        )
                        self.gate_points.append(gp)
                        self._gate_counter += 1

        # 2. Execute the wrapped element (e.g. ToolsExecutor or pipeline)
        query_out, runtime_out, env_out, messages_out, extra_out = self.wrapped_element.query(
            query, runtime, env, messages, extra_args
        )

        # 3. Synchronize full trace and check for exposure in newly produced observations
        self.recorded_steps = self._convert_messages_to_steps(messages_out)
        self._check_exposure(messages_out)

        return query_out, runtime_out, env_out, messages_out, extra_out

    def _convert_messages_to_steps(self, messages: Sequence[ChatMessage]) -> List[RawStep]:
        """Convert AgentDojo ChatMessage objects to immutable RawStep objects."""
        steps: List[RawStep] = []
        for idx, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content")
            tool_calls: List[RawToolCall] = []
            tool_results: List[RawToolResult] = []

            if role == "assistant" and msg.get("tool_calls"):
                for tc in msg.get("tool_calls", []):
                    call_id = getattr(tc, "id", None) or str(uuid.uuid4())
                    tool_calls.append(
                        RawToolCall(
                            call_id=call_id,
                            tool_name=tc.function,
                            arguments=copy.deepcopy(tc.args),
                        )
                    )

            if role == "tool":
                call_id = msg.get("tool_call_id") or f"call-{idx}"
                tool_results.append(
                    RawToolResult(
                        call_id=call_id,
                        output=str(content),
                        error=msg.get("error"),
                    )
                )

            steps.append(
                RawStep(
                    step_index=idx,
                    role=role,
                    content=str(content) if content is not None else None,
                    tool_calls=tool_calls,
                    tool_results=tool_results,
                )
            )
        return steps

    def _check_exposure(self, messages: Sequence[ChatMessage]) -> None:
        """Check if any payload string appeared inside tool output messages.

        Normalizes escaped characters (e.g. \\n, \\') and whitespace so that YAML/JSON
        serialized observation strings match payload content reliably.
        """
        if not self.injected_payloads:
            return

        import re

        def _normalize(text: str) -> str:
            text = text.replace('\\\\n', '\n').replace('\\n', '\n').replace('\\\'', '\'')
            text = text.replace("''", "'")
            return re.sub(r'\s+', ' ', text).strip()

        for msg in messages:
            if msg.get("role") == "tool":
                obs_norm = _normalize(str(msg.get("content", "")))
                for key, payload in self.injected_payloads.items():
                    p_norm = _normalize(payload)
                    # Check both exact normalized payload and primary marker lines
                    if p_norm in obs_norm:
                        self.exposure_observed = True
                        return
                    marker = p_norm[:40] if len(p_norm) >= 40 else p_norm
                    if marker in obs_norm:
                        self.exposure_observed = True
                        return

    def get_raw_execution_record(self) -> RawExecutionRecord:
        """Compile the raw execution record for this trajectory."""
        return RawExecutionRecord(
            run_id=self.run_id,
            benchmark_version=self.benchmark_version,
            suite_name=self.suite_name,
            user_task_id=self.user_task_id,
            injection_task_id=self.injection_task_id,
            attack_name=self.attack_name,
            agent_model=self.agent_model,
            steps=copy.deepcopy(self.recorded_steps),
            metadata={"gate_point_count": len(self.gate_points)},
        )
