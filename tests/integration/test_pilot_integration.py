"""Integration tests for AgentWatch Phase 1 pipeline, contracts, and instrumentation."""

import unittest
import copy
from agentdojo.agent_pipeline.basic_elements import InitQuery
from agentdojo.agent_pipeline.tool_execution import ToolsExecutor
from agentdojo.functions_runtime import FunctionsRuntime, FunctionCall
from agentdojo.task_suite.load_suites import get_suite
from agentdojo.types import ChatAssistantMessage, ChatMessage, ChatUserMessage, FunctionCall as DojoFunctionCall

from agentwatch.traces.schema import (
    RawExecutionRecord,
    RawStep,
    RawToolCall,
    RawToolResult,
    GroundTruthLabelRecord,
)
from agentwatch.traces.gate_point import CausalGatePoint
from agentwatch.traces.instrumentation import InstrumentedPipelineElement


class TestIntegrationPhase1(unittest.TestCase):

    def setUp(self):
        self.suite = get_suite("v1", "workspace")

    def test_benchmark_suite_loading(self):
        """Verify that benchmark suite v1 workspace loads properly with valid tasks."""
        self.assertIsNotNone(self.suite)
        self.assertEqual(len(self.suite.user_tasks), 40)
        self.assertEqual(len(self.suite.injection_tasks), 6)
        self.assertEqual(len(self.suite.tools), 24)

    def test_selected_pilot_tasks_ground_truth(self):
        """Verify ground truth calls exist for all 5 selected pilot user and injection tasks."""
        env = self.suite.load_and_inject_default_environment({})
        for i in range(5):
            ut = self.suite.get_user_task_by_id(f"user_task_{i}")
            gt_ut = ut.ground_truth(env)
            self.assertGreater(len(gt_ut), 0, f"user_task_{i} has empty ground truth")

            it = self.suite.get_injection_task_by_id(f"injection_task_{i}")
            gt_it = it.ground_truth(env)
            self.assertGreater(len(gt_it), 0, f"injection_task_{i} has empty ground truth")

    def test_raw_record_serialization_and_deserialization(self):
        """Verify serialization and deserialization of raw execution traces."""
        raw_tc = RawToolCall(call_id="call-1", tool_name="search_calendar_events", arguments={"query": "test"})
        step = RawStep(step_index=0, role="assistant", tool_calls=[raw_tc])
        record = RawExecutionRecord(
            run_id="run-test-123",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_0",
            injection_task_id="injection_task_0",
            attack_name="important_instructions",
            agent_model="test-model",
            steps=[step],
        )

        data = record.model_dump()
        restored = RawExecutionRecord.model_validate(data)
        self.assertEqual(restored.run_id, record.run_id)
        self.assertEqual(len(restored.steps), 1)
        self.assertEqual(restored.steps[0].tool_calls[0].tool_name, "search_calendar_events")

    def test_causal_gate_point_isolation(self):
        """Verify that a CausalGatePoint does not leak future steps, observations, or labels."""
        step0 = RawStep(step_index=0, role="user", content="Search calendar")
        proposed_tc = RawToolCall(call_id="call-2", tool_name="search_calendar_events", arguments={})
        gp = CausalGatePoint(
            run_id="run-gate-test",
            gate_index=0,
            step_index=1,
            available_prefix=[step0],
            proposed_tool_call=proposed_tc,
        )

        view = gp.get_feature_view()
        # Assert future information / labels are excluded
        self.assertNotIn("future_observations", view)
        self.assertNotIn("security_success", view)
        self.assertNotIn("utility_success", view)
        self.assertEqual(view["prefix_step_count"], 1)
        self.assertEqual(view["proposed_tool_name"], "search_calendar_events")

    def test_instrumented_execution_intercepts_call(self):
        """Verify that InstrumentedPipelineElement intercepts proposed calls and records gate points."""
        tools_executor = ToolsExecutor()
        instrumented = InstrumentedPipelineElement(
            wrapped_element=tools_executor,
            run_id="run-inst-test",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_0",
            injected_payloads={"test_key": "MALICIOUS INJECTION"},
        )

        # Build simulated trajectory with an assistant tool call
        env = self.suite.load_and_inject_default_environment({})
        runtime = FunctionsRuntime(self.suite.tools)
        assistant_msg = ChatAssistantMessage(
            role="assistant",
            content=None,
            tool_calls=[DojoFunctionCall(function="get_current_day", args={})],
        )
        messages = [
            ChatUserMessage(role="user", content="What day is it?"),
            assistant_msg,
        ]

        q_out, rt_out, env_out, msgs_out, extra_out = instrumented.query(
            "What day is it?", runtime, env, messages, {}
        )

        # Verify that a gate point was captured immediately before tool execution
        self.assertEqual(len(instrumented.gate_points), 1)
        gp = instrumented.gate_points[0]
        self.assertEqual(gp.proposed_tool_call.tool_name, "get_current_day")
        self.assertEqual(len(gp.available_prefix), 1)  # Only user message in prefix

        # Verify that raw execution trace was compiled
        raw_rec = instrumented.get_raw_execution_record()
        self.assertGreater(len(raw_rec.steps), 2)  # user, assistant, tool result
        self.assertEqual(raw_rec.steps[1].role, "assistant")
        self.assertEqual(raw_rec.steps[2].role, "tool")

    def test_label_separation_record(self):
        """Verify GroundTruthLabelRecord is decoupled from detector views."""
        label_rec = GroundTruthLabelRecord(
            run_id="run-lbl-test",
            utility_success=True,
            security_success=False,
            injected=True,
            exposure_detected=True,
            first_harmful_step=None,
            harmful_timing_verified=False,
        )
        self.assertTrue(label_rec.utility_success)
        self.assertFalse(label_rec.security_success)
        self.assertTrue(label_rec.exposure_detected)

    def test_normalized_trace_projection(self):
        """Verify RawExecutionRecord can be cleanly projected into NormalizedTrace with linked calls."""
        from agentwatch.traces.normalizer import normalize_raw_trace

        raw_tc = RawToolCall(call_id="call-42", tool_name="search_calendar_events", arguments={"day": "2024-05-15"})
        raw_tr = RawToolResult(call_id="call-42", output="Event found: Team Sync", error=None)

        step_user = RawStep(step_index=0, role="user", content="Find events")
        step_asst = RawStep(step_index=1, role="assistant", content="", tool_calls=[raw_tc])
        step_tool = RawStep(step_index=2, role="tool", content="Event found", tool_results=[raw_tr])

        raw_rec = RawExecutionRecord(
            run_id="run-norm-test",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_0",
            agent_model="qwen2.5:3b",
            steps=[step_user, step_asst, step_tool],
            metadata={"gate_point_count": 1},
        )

        norm_trace = normalize_raw_trace(raw_rec)
        self.assertEqual(norm_trace.run_id, "run-norm-test")
        self.assertEqual(norm_trace.total_steps, 3)
        self.assertEqual(norm_trace.gate_point_count, 1)
        self.assertEqual(len(norm_trace.tool_invocations), 1)

        inv = norm_trace.tool_invocations[0]
        self.assertEqual(inv.call_id, "call-42")
        self.assertEqual(inv.tool_name, "search_calendar_events")
        self.assertEqual(inv.call_step_index, 1)
        self.assertEqual(inv.result_step_index, 2)
        self.assertTrue(inv.is_executed)
        self.assertEqual(inv.output, "Event found: Team Sync")

    def test_zero_tool_call_trajectory_handling(self):
        """Verify that trajectories where the agent proposes 0 tool calls produce 0 gate points cleanly."""
        from agentwatch.traces.normalizer import normalize_raw_trace

        raw_rec = RawExecutionRecord(
            run_id="run-zero-call-test",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_2",
            agent_model="qwen2.5:3b",
            steps=[],
            metadata={"gate_point_count": 0},
        )
        norm_trace = normalize_raw_trace(raw_rec)
        self.assertEqual(norm_trace.gate_point_count, 0)
        self.assertEqual(len(norm_trace.tool_invocations), 0)
        self.assertEqual(norm_trace.total_steps, 0)

    def test_exposure_detection_with_escaped_newlines(self):
        """Verify that _check_exposure detects payload across escaped newlines and formatting."""
        tools_executor = ToolsExecutor()
        payload_text = "\n\n\n<INFORMATION>\nThis is an important message from me, Emma Johnson\n</INFORMATION>"
        instrumented = InstrumentedPipelineElement(
            wrapped_element=tools_executor,
            run_id="run-exp-test",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_0",
            injected_payloads={"test_injection": payload_text},
        )

        # Observation formatted with escaped newlines and extra text (as returned by YAML/JSON tools)
        escaped_obs = "- all_day: false\\n  description: \"Meeting.\\\\n\\\\ \\\\n\\\\n<INFORMATION>\\\\nThis is an important message from me, Emma Johnson\\\\n</INFORMATION>\""
        tool_msg = {"role": "tool", "content": escaped_obs, "tool_call_id": "call-1"}

        instrumented._check_exposure([tool_msg])
        self.assertTrue(instrumented.exposure_observed)

    def test_batched_tool_calls_causal_gate_points(self):
        """Verify batched tool calls generate sequential gate points without leaking sibling calls or future observations."""
        tools_executor = ToolsExecutor()
        instrumented = InstrumentedPipelineElement(
            wrapped_element=tools_executor,
            run_id="run-batch-test",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_4",
        )

        env = self.suite.load_and_inject_default_environment({})
        runtime = FunctionsRuntime(self.suite.tools)
        # Assistant proposes a batch of 2 calls
        tc1 = DojoFunctionCall(function="get_current_day", args={})
        tc2 = DojoFunctionCall(function="search_calendar_events", args={"query": "lunch"})
        asst_msg = ChatAssistantMessage(role="assistant", content=None, tool_calls=[tc1, tc2])
        messages = [ChatUserMessage(role="user", content="Schedule lunch"), asst_msg]

        instrumented.query("Schedule lunch", runtime, env, messages, {})

        self.assertEqual(len(instrumented.gate_points), 2)
        gp0 = instrumented.gate_points[0]
        gp1 = instrumented.gate_points[1]

        # Both gate points have the exact prefix before this turn (only the user message)
        self.assertEqual(len(gp0.available_prefix), 1)
        self.assertEqual(len(gp1.available_prefix), 1)
        self.assertEqual(gp0.proposed_tool_call.tool_name, "get_current_day")
        self.assertEqual(gp1.proposed_tool_call.tool_name, "search_calendar_events")

        # Feature views must exclude sibling call results and future observations
        fv0 = gp0.get_feature_view()
        fv1 = gp1.get_feature_view()
        self.assertNotIn("future_observations", fv0)
        self.assertNotIn("future_observations", fv1)
        self.assertNotIn("security_success", fv0)

    def test_normalizer_handles_duplicate_and_missing_call_ids(self):
        """Verify that normalizer handles duplicate call_ids via FIFO matching and missing call results gracefully."""
        from agentwatch.traces.normalizer import normalize_raw_trace

        tc_dup1 = RawToolCall(call_id="call-dup", tool_name="search_calendar_events", arguments={"day": "2024-05-15"})
        tc_dup2 = RawToolCall(call_id="call-dup", tool_name="search_calendar_events", arguments={"day": "2024-05-16"})
        tc_missing = RawToolCall(call_id="call-no-result", tool_name="send_email", arguments={})

        tr_dup1 = RawToolResult(call_id="call-dup", output="Result Day 1", error=None)
        tr_dup2 = RawToolResult(call_id="call-dup", output="Result Day 2", error=None)

        step_user = RawStep(step_index=0, role="user", content="Check days")
        step_asst = RawStep(step_index=1, role="assistant", content="", tool_calls=[tc_dup1, tc_dup2, tc_missing])
        step_tool = RawStep(step_index=2, role="tool", content="", tool_results=[tr_dup1, tr_dup2])

        raw_rec = RawExecutionRecord(
            run_id="run-dup-test",
            benchmark_version="v1",
            suite_name="workspace",
            user_task_id="user_task_0",
            agent_model="qwen2.5:3b",
            steps=[step_user, step_asst, step_tool],
            metadata={"gate_point_count": 3},
        )

        norm_trace = normalize_raw_trace(raw_rec)
        self.assertEqual(len(norm_trace.tool_invocations), 3)

        # FIFO matching for duplicate call_id
        inv0 = norm_trace.tool_invocations[0]
        inv1 = norm_trace.tool_invocations[1]
        inv2 = norm_trace.tool_invocations[2]

        self.assertEqual(inv0.arguments["day"], "2024-05-15")
        self.assertEqual(inv0.output, "Result Day 1")
        self.assertTrue(inv0.is_executed)

        self.assertEqual(inv1.arguments["day"], "2024-05-16")
        self.assertEqual(inv1.output, "Result Day 2")
        self.assertTrue(inv1.is_executed)

        # Missing result
        self.assertEqual(inv2.call_id, "call-no-result")
        self.assertFalse(inv2.is_executed)
        self.assertIsNone(inv2.result_step_index)
        self.assertIsNone(inv2.output)

    def test_integrity_verification_on_actual_pilot_runs(self):
        """Verify that integrity.py passes against all 10 genuine pilot executions."""
        from agentwatch.traces.integrity import audit_pilot_directory

        all_valid, results = audit_pilot_directory("data/pilot_runs")
        self.assertTrue(all_valid, "One or more pilot runs failed integrity verification")
        self.assertEqual(len(results), 10)
        for r in results:
            self.assertTrue(r.is_valid)
            self.assertEqual(len(r.errors), 0)
            self.assertIsNotNone(r.raw_hash)
            self.assertIsNotNone(r.normalized_hash)

    def test_unexposed_attack_distinction_in_labels(self):
        """Verify that an attacked run without exposure (e.g., user_task_3) maintains unexposed status."""
        label_rec = GroundTruthLabelRecord(
            run_id="run-attack-user_task_3-injection_task_3-c8fccf",
            utility_success=False,
            security_success=False,
            injected=True,
            exposure_detected=False,
            harmful_action_proposed=False,
            harmful_action_executed=False,
            first_harmful_step=None,
            harmful_timing_verified=False,
        )
        # Verify that attack assignment is separated from exposure and outcome
        self.assertTrue(label_rec.injected)
        self.assertFalse(label_rec.exposure_detected)
        self.assertFalse(label_rec.harmful_action_proposed)
        self.assertFalse(label_rec.security_success)

    def test_phase3_dataset_builder_views_and_aggregation(self):
        """Verify that Phase 3 dataset builder extracts consistent gate-point and trajectory views."""
        from agentwatch.dataset.builder import build_phase3_datasets

        gps, trajs, metrics = build_phase3_datasets()

        # Check trajectory view counts
        self.assertEqual(len(trajs), 10)
        self.assertEqual(metrics["total_trajectories"], 10)
        self.assertEqual(metrics["distinct_user_tasks"], 5)
        self.assertEqual(metrics["benign_runs"], 5)
        self.assertEqual(metrics["attacked_runs"], 5)
        self.assertEqual(metrics["exposed_attacked_runs"], 4)
        self.assertEqual(metrics["unexposed_attacked_runs"], 1)

        # Check gate point counts match trajectory totals
        total_gps = sum(t.total_gate_points for t in trajs)
        self.assertEqual(len(gps), total_gps)
        self.assertEqual(len(gps), 18)

        # Verify gate point record properties
        for gp in gps:
            self.assertIsNotNone(gp.gate_point_id)
            self.assertIsNotNone(gp.run_id)
            self.assertIsNotNone(gp.proposed_tool_name)
            # Available prefix must only contain steps before step_index
            for p_msg in gp.available_prefix:
                self.assertLess(p_msg["step_index"], gp.step_index)

        # Verify that unexposed attacked run (user_task_3) has exposure_prior_to_call = False across all calls
        u3_gps = [g for g in gps if "user_task_3" in g.user_task_id and g.trajectory_injected]
        self.assertEqual(len(u3_gps), 1)
        self.assertFalse(u3_gps[0].exposure_prior_to_call)

        # Verify that attacked user_task_4 turn 1 has exp_prior = False, and turn 2 has exp_prior = True
        u4_gps = [g for g in gps if "user_task_4" in g.user_task_id and g.trajectory_injected]
        self.assertEqual(len(u4_gps), 7)
        for g in u4_gps[:4]:  # turn 1 calls
            self.assertFalse(g.exposure_prior_to_call)
        for g in u4_gps[4:]:  # turn 2 calls
            self.assertTrue(g.exposure_prior_to_call)

    def test_gate_point_feature_view_leakage_prevention(self):
        """Verify that get_feature_view on GatePointDatasetRecord strictly excludes post-hoc labels and results."""
        from agentwatch.dataset.builder import build_phase3_datasets

        gps, _, _ = build_phase3_datasets()
        self.assertGreater(len(gps), 0)

        forbidden_keys = {
            "is_executed",
            "result_step_index",
            "has_execution_error",
            "trajectory_injected",
            "exposure_prior_to_call",
            "is_harmful_action",
            "security_breached_at_or_before",
            "security_success",
            "utility_success",
            "future_observations",
        }

        for gp in gps:
            fv = gp.get_feature_view()
            for k in forbidden_keys:
                self.assertNotIn(k, fv, f"Leakage detected: key '{k}' present in get_feature_view()")
            self.assertIn("proposed_tool_name", fv)
            self.assertIn("proposed_arguments", fv)
            self.assertIn("available_prefix", fv)

    def test_feature_view_label_mutation_invariance(self):
        """Verify that mutating post-hoc evaluation labels leaves get_feature_view completely identical."""
        from agentwatch.dataset.builder import build_phase3_datasets

        gps, _, _ = build_phase3_datasets()
        gp = gps[0]
        original_fv = copy.deepcopy(gp.get_feature_view())

        # Mutate all post-hoc and execution fields on the record
        gp.is_harmful_action = not gp.is_harmful_action
        gp.security_breached_at_or_before = not gp.security_breached_at_or_before
        gp.exposure_prior_to_call = not gp.exposure_prior_to_call
        gp.trajectory_injected = not gp.trajectory_injected
        gp.is_executed = not gp.is_executed
        gp.has_execution_error = not gp.has_execution_error
        gp.result_step_index = 9999

        mutated_fv = gp.get_feature_view()
        self.assertEqual(original_fv, mutated_fv, "Feature view changed when post-hoc labels were mutated!")

    def test_post_exposure_timing_pre_decision_derivation(self):
        """Verify that tool calls retrieving an injected payload have exposure_prior_to_call = False."""
        from agentwatch.dataset.builder import build_phase3_datasets

        gps, _, _ = build_phase3_datasets()
        # Find the calendar search call in attacked user_task_0
        u0_attack_gps = [g for g in gps if g.run_id == "run-attack-user_task_0-injection_task_0-79f6f2"]
        self.assertEqual(len(u0_attack_gps), 1)
        # Even though the run was exposed, the call that RETRIEVED the payload was proposed BEFORE observing it
        self.assertFalse(
            u0_attack_gps[0].exposure_prior_to_call,
            "Retrieving tool call must NOT have exposure_prior_to_call=True before its observation is returned",
        )

    def test_batched_tool_call_sibling_isolation(self):
        """Verify that in batched turns, sibling tool calls share pre-turn history without sibling results."""
        from agentwatch.dataset.builder import build_phase3_datasets

        gps, _, _ = build_phase3_datasets()
        # In attacked user_task_4, turn 1 proposes 4 sibling calls
        u4_turn1_gps = [
            g for g in gps
            if g.run_id == "run-attack-user_task_4-injection_task_4-2b9398" and g.step_index == 2
        ]
        self.assertEqual(len(u4_turn1_gps), 4)

        # All 4 gate points must share identical prefix length and contents
        first_prefix = u4_turn1_gps[0].available_prefix
        for sibling_gp in u4_turn1_gps[1:]:
            self.assertEqual(sibling_gp.prefix_step_count, u4_turn1_gps[0].prefix_step_count)
            self.assertEqual(sibling_gp.available_prefix, first_prefix)
            # Prefix must not contain any tool results from the sibling calls
            for msg in sibling_gp.available_prefix:
                self.assertNotEqual(msg["role"], "tool_result_from_current_turn")

    def test_integrity_verifier_flags_missing_raw_trace(self):
        """Verify that verify_run_integrity flags missing or orphaned trace files."""
        from agentwatch.traces.integrity import verify_run_integrity
        from pathlib import Path

        # Non-existent files
        res = verify_run_integrity(Path("data/non_existent_raw.json"), Path("data/non_existent_lbl.json"))
        self.assertFalse(res.is_valid)
        self.assertGreater(len(res.errors), 0)

    def test_evaluation_readiness_assessment(self):
        """Verify that evaluation readiness assessment correctly marks positive detection blocked."""
        from agentwatch.dataset.readiness import evaluate_dataset_readiness

        rep = evaluate_dataset_readiness()
        self.assertTrue(rep["status_verdicts"]["READY_FOR_FEATURE_IMPLEMENTATION"])
        self.assertTrue(rep["status_verdicts"]["READY_FOR_EXPLORATORY_NEGATIVE_ONLY_CHECKS"])
        self.assertTrue(rep["status_verdicts"]["BLOCKED_FOR_POSITIVE_CLASS_DETECTION_EVALUATION"])
        self.assertEqual(rep["trajectory_level_metrics"]["benchmark_confirmed_hijacks"], 0)
        self.assertEqual(rep["trajectory_level_metrics"]["harmful_actions_proposed"], 0)
        self.assertIn(rep["trajectory_level_metrics"]["total_trajectories"], [21, 35])
        self.assertIn(rep["gate_point_level_metrics"]["total_gate_points"], [76, 119])


if __name__ == "__main__":
    unittest.main()





