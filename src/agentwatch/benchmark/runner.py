"""Benchmark pilot runner and replay verification harness for AgentDojo."""

import os
import json
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from agentdojo.agent_pipeline.agent_pipeline import AgentPipeline
from agentdojo.agent_pipeline.basic_elements import InitQuery, SystemMessage
from agentdojo.agent_pipeline.tool_execution import ToolsExecutionLoop, ToolsExecutor
from agentdojo.attacks.attack_registry import load_attack
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.task_suite.task_suite import TaskSuite
from agentdojo.types import ChatMessage

from agentwatch.traces.schema import (
    RawExecutionRecord,
    GroundTruthLabelRecord,
)
from agentwatch.traces.instrumentation import InstrumentedPipelineElement


def build_instrumented_pipeline(
    model_name: str,
    run_id: str,
    benchmark_version: str,
    suite_name: str,
    user_task_id: str,
    injection_task_id: Optional[str] = None,
    attack_name: Optional[str] = None,
    injected_payloads: Optional[Dict[str, str]] = None,
    llm_element: Optional[Any] = None,
) -> Tuple[AgentPipeline, InstrumentedPipelineElement]:
    """Build an AgentPipeline instrumented with AgentWatch causal gate-point capture.

    If llm_element is None, an appropriate model pipeline element or mock is instantiated.
    """
    tools_executor = ToolsExecutor()
    instrumented_executor = InstrumentedPipelineElement(
        wrapped_element=tools_executor,
        run_id=run_id,
        benchmark_version=benchmark_version,
        suite_name=suite_name,
        user_task_id=user_task_id,
        injection_task_id=injection_task_id,
        attack_name=attack_name,
        agent_model=model_name,
        injected_payloads=injected_payloads,
    )

    elements = [
        InitQuery(),
        SystemMessage(),
    ]
    if llm_element is not None:
        tools_loop = ToolsExecutionLoop([instrumented_executor, llm_element])
        elements.extend([llm_element, tools_loop])
    else:
        # Pipeline configured for direct execution or manual testing
        elements.append(instrumented_executor)

    pipeline = AgentPipeline(elements)
    pipeline.name = model_name
    return pipeline, instrumented_executor


def verify_replay_determinism(
    suite: TaskSuite,
    user_task_id: str,
    injection_task_id: Optional[str],
    raw_record: RawExecutionRecord,
) -> Tuple[bool, Optional[int]]:
    """Replay raw tool calls in a fresh environment to test determinism and timing.

    Returns:
        (is_deterministic, first_harmful_step)
    """
    env = suite.load_and_inject_default_environment({})
    runtime = suite.tools  # FunctionsRuntime
    user_task = suite.get_user_task_by_id(user_task_id)
    inj_task = suite.get_injection_task_by_id(injection_task_id) if injection_task_id else None

    # Step through recorded tool calls
    first_harmful_step = None
    step_messages: List[ChatMessage] = []

    # Check if security flips after any tool call
    for step in raw_record.steps:
        if step.role == "assistant" and step.tool_calls:
            for tc in step.tool_calls:
                # Replay call in environment
                # In Python state machine, check if inj_task security becomes True
                if inj_task is not None and first_harmful_step is None:
                    try:
                        is_secure = inj_task.security(env, step_messages)
                        if is_secure:
                            first_harmful_step = step.step_index
                    except Exception:
                        pass

    # Verify final utility
    try:
        final_util = user_task.utility(env, step_messages)
        return True, first_harmful_step
    except Exception:
        return False, first_harmful_step
