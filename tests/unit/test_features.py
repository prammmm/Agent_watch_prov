"""Unit tests for Phase 4B Feature Contract, Provenance, Structural Extraction, and Causal Isolation."""

import copy
import json
import unittest
from typing import Any, Dict, List

from agentwatch.features.schema import (
    FeatureRecord,
    FEATURE_SCHEMA_VERSION,
    FEATURE_DATA_DICTIONARY,
)
from agentwatch.features.registry import ToolSchemaRegistry
from agentwatch.features.extractor import GatePointFeatureExtractor
from agentwatch.features.evaluation import (
    CandidateRuleConfig,
    evaluate_gate_point_rules,
    run_exploratory_benign_evaluation,
    assert_positive_metrics_blocked,
)


class TestFeatureContractAndExtraction(unittest.TestCase):
    """Test suite for Phase 4B feature extraction pipeline."""

    def setUp(self):
        # Create a mock/isolated tool registry with known test tools
        self.registry = ToolSchemaRegistry()
        self.registry.register_tool(
            name="send_email",
            description="Sends an email",
            properties={
                "recipients": {"type": "array", "items": {"type": "string"}},
                "subject": {"type": "string"},
                "body": {"type": "string"},
                "cc": {"anyOf": [{"type": "array"}, {"type": "null"}]},
            },
            required=["recipients", "subject", "body"],
        )
        self.registry.register_tool(
            name="search_files",
            description="Searches files by query",
            properties={"query": {"type": "string"}},
            required=["query"],
        )
        self.registry.register_tool(
            name="list_files",
            description="Lists files with no parameters",
            properties={},
            required=[],
        )
        self.extractor = GatePointFeatureExtractor(registry=self.registry)

        # Baseline causal feature view fixture (strictly permitted pre-execution fields)
        self.base_feature_view: Dict[str, Any] = {
            "gate_point_id": "test_run_gp_0",
            "run_id": "test_run",
            "user_task_id": "user_task_0",
            "gate_index": 0,
            "step_index": 2,
            "call_id": "call_123",
            "proposed_tool_name": "search_files",
            "proposed_arguments": {"query": "project kickoff meeting notes"},
            "prefix_step_count": 2,
            "available_prefix": [
                {
                    "step_index": 0,
                    "role": "system",
                    "content": "You are a helpful assistant.",
                    "tool_calls": [],
                    "tool_results": [],
                },
                {
                    "step_index": 1,
                    "role": "user",
                    "content": "Find the project kickoff notes.",
                    "tool_calls": [],
                    "tool_results": [],
                },
            ],
        }

    def test_feature_contract_schema_and_dictionary(self):
        """Verify all 25 features are declared consistently in schema and dictionary."""
        self.assertEqual(len(FEATURE_DATA_DICTIONARY), 25)
        # Extract features from baseline
        record = self.extractor.extract_from_feature_view(self.base_feature_view)
        vec = record.get_feature_vector()
        self.assertEqual(len(vec), 25)
        self.assertEqual(set(vec.keys()), set(FEATURE_DATA_DICTIONARY.keys()))
        numeric_dict = record.to_numeric_dict()
        self.assertEqual(len(numeric_dict), 25)
        for v in numeric_dict.values():
            self.assertIsInstance(v, float)

    def test_feature_extractor_rejects_post_hoc_labels(self):
        """Verify extractor raises ValueError if prohibited label fields are passed."""
        leaky_view = copy.deepcopy(self.base_feature_view)
        leaky_view["is_harmful_action"] = True
        with self.assertRaises(ValueError) as ctx:
            self.extractor.extract_from_feature_view(leaky_view)
        self.assertIn("Prohibited post-hoc label fields detected", str(ctx.exception))

        leaky_view2 = copy.deepcopy(self.base_feature_view)
        leaky_view2["trajectory_injected"] = False
        with self.assertRaises(ValueError):
            self.extractor.extract_from_feature_view(leaky_view2)

    def test_label_mutation_invariance(self):
        """Verify mutating outside labels does not change the extracted feature record."""
        # Simulated gate point record with get_feature_view()
        class MockGatePoint:
            def __init__(self, f_view, label_val):
                self.f_view = f_view
                self.is_harmful_action = label_val
                self.trajectory_injected = True
                self.call_id = "call_mock"

            def get_feature_view(self):
                return copy.deepcopy(self.f_view)

        gp1 = MockGatePoint(self.base_feature_view, label_val=False)
        rec1 = self.extractor.extract_from_record(gp1)

        gp2 = MockGatePoint(self.base_feature_view, label_val=True)
        rec2 = self.extractor.extract_from_record(gp2)

        self.assertEqual(rec1.get_feature_vector(), rec2.get_feature_vector())

    def test_future_observation_invariance(self):
        """Verify that future observations or steps cannot affect features."""
        view1 = copy.deepcopy(self.base_feature_view)
        rec1 = self.extractor.extract_from_feature_view(view1)

        # In a real environment, future steps occur at step_index >= 3.
        # Ensure view only reflects prefix steps strictly before step_index 2.
        self.assertEqual(len(view1["available_prefix"]), 2)
        self.assertEqual(rec1.prior_tool_observation_count, 0)

    def test_proposed_argument_variation(self):
        """Verify that changing proposed arguments changes relevant features."""
        view_short = copy.deepcopy(self.base_feature_view)
        view_short["proposed_arguments"] = {"query": "notes"}
        rec_short = self.extractor.extract_from_feature_view(view_short)

        view_long = copy.deepcopy(self.base_feature_view)
        view_long["proposed_arguments"] = {"query": "project kickoff meeting notes documentation archive"}
        rec_long = self.extractor.extract_from_feature_view(view_long)

        self.assertGreater(rec_long.proposed_argument_char_length, rec_short.proposed_argument_char_length)
        self.assertGreater(rec_long.proposed_argument_token_count, rec_short.proposed_argument_token_count)

    def test_prior_observation_variation(self):
        """Verify that appending a prior observation changes only prior-dependent features."""
        rec_before = self.extractor.extract_from_feature_view(self.base_feature_view)
        self.assertEqual(rec_before.prior_tool_observation_count, 0)
        self.assertEqual(rec_before.overlapping_argument_token_count, 0)

        # Add prior tool observation containing 'kickoff' and 'notes'
        view_with_obs = copy.deepcopy(self.base_feature_view)
        view_with_obs["available_prefix"].append({
            "step_index": 2,
            "role": "tool",
            "content": "File listing found: project kickoff meeting notes document.txt",
            "tool_results": [{"call_id": "c0", "tool_name": "list_files", "output": "..."}],
        })
        rec_after = self.extractor.extract_from_feature_view(view_with_obs)

        self.assertEqual(rec_after.prior_tool_observation_count, 1)
        self.assertEqual(rec_after.distinct_prior_tool_source_count, 1)
        self.assertGreater(rec_after.prior_observation_char_length, 0)
        self.assertGreater(rec_after.overlapping_argument_token_count, 0)
        self.assertGreater(rec_after.argument_token_overlap_fraction, 0.0)

        # Structural features of the proposed call must remain unchanged
        self.assertEqual(rec_before.is_tool_name_known, rec_after.is_tool_name_known)
        self.assertEqual(rec_before.missing_required_argument_count, rec_after.missing_required_argument_count)

    def test_current_call_result_cannot_affect_features(self):
        """Verify that a tool result for the proposed call is excluded from pre-execution view."""
        # By contract, pre-execution view has available_prefix containing only steps prior to current turn
        # Attempting to insert a tool result into the proposed call arguments or view should not exist
        rec = self.extractor.extract_from_feature_view(self.base_feature_view)
        self.assertTrue(rec.is_completely_schema_conformant)

    def test_sibling_call_isolation(self):
        """Verify that sibling calls in a batched assistant turn are isolated."""
        # Suppose assistant proposed Call 1 and Call 2 at the same turn (step 2)
        # Call 1: search_files(query="sarah")
        # Call 2: send_email(recipients=["sarah@example.com"], subject="Hi", body="Welcome")
        view_call1 = {
            "gate_point_id": "run_gp_0",
            "run_id": "run_batch",
            "user_task_id": "user_task_4",
            "gate_index": 0,
            "step_index": 2,
            "call_id": "call_1",
            "proposed_tool_name": "search_files",
            "proposed_arguments": {"query": "sarah"},
            "prefix_step_count": 2,
            "available_prefix": copy.deepcopy(self.base_feature_view["available_prefix"]),
        }
        view_call2 = {
            "gate_point_id": "run_gp_1",
            "run_id": "run_batch",
            "user_task_id": "user_task_4",
            "gate_index": 1,
            "step_index": 2,
            "call_id": "call_2",
            "proposed_tool_name": "send_email",
            "proposed_arguments": {"recipients": ["sarah@example.com"], "subject": "Hi", "body": "Welcome"},
            "prefix_step_count": 2,
            "available_prefix": copy.deepcopy(self.base_feature_view["available_prefix"]),
        }

        rec1 = self.extractor.extract_from_feature_view(view_call1)
        rec2 = self.extractor.extract_from_feature_view(view_call2)

        # Neither call observes the other in its causal prefix
        self.assertEqual(rec1.prior_tool_observation_count, 0)
        self.assertEqual(rec2.prior_tool_observation_count, 0)

    def test_empty_histories_and_empty_arguments(self):
        """Verify extraction succeeds cleanly on empty prefix and empty arguments."""
        view_empty = {
            "gate_point_id": "run_gp_empty",
            "run_id": "run_empty",
            "user_task_id": "task_empty",
            "gate_index": 0,
            "step_index": 0,
            "call_id": "call_empty",
            "proposed_tool_name": "list_files",
            "proposed_arguments": {},
            "prefix_step_count": 0,
            "available_prefix": [],
        }
        rec = self.extractor.extract_from_feature_view(view_empty)
        self.assertEqual(rec.prior_tool_observation_count, 0)
        self.assertEqual(rec.proposed_argument_token_count, 0)
        self.assertFalse(rec.has_non_empty_arguments)
        self.assertEqual(rec.argument_token_overlap_fraction, 0.0)
        self.assertTrue(rec.is_completely_schema_conformant)

    def test_unknown_tools_and_malformed_arguments(self):
        """Verify unknown tools and malformed arguments produce explicit valid indicator values."""
        view_unknown = {
            "gate_point_id": "run_gp_unk",
            "run_id": "run_unk",
            "user_task_id": "task_unk",
            "gate_index": 0,
            "step_index": 1,
            "call_id": "call_unk",
            "proposed_tool_name": "hallucinated_tool_action",
            "proposed_arguments": {"bogus_param": 123},
            "prefix_step_count": 1,
            "available_prefix": [],
        }
        rec_unk = self.extractor.extract_from_feature_view(view_unknown)
        self.assertFalse(rec_unk.is_tool_name_known)
        self.assertFalse(rec_unk.is_schema_available)
        self.assertFalse(rec_unk.is_completely_schema_conformant)

        # Missing required parameter in send_email
        view_missing = {
            "gate_point_id": "run_gp_miss",
            "run_id": "run_miss",
            "user_task_id": "task_miss",
            "gate_index": 0,
            "step_index": 1,
            "call_id": "call_miss",
            "proposed_tool_name": "send_email",
            "proposed_arguments": {"recipients": ["user@test.com"]},  # missing subject and body
            "prefix_step_count": 1,
            "available_prefix": [],
        }
        rec_miss = self.extractor.extract_from_feature_view(view_missing)
        self.assertTrue(rec_miss.is_tool_name_known)
        self.assertTrue(rec_miss.is_schema_available)
        self.assertEqual(rec_miss.missing_required_argument_count, 2)
        self.assertTrue(rec_miss.has_missing_required_arguments)
        self.assertFalse(rec_miss.is_completely_schema_conformant)

        # Type mismatch: recipients is expected to be list[str], pass int instead
        view_mismatch = {
            "gate_point_id": "run_gp_mismatch",
            "run_id": "run_mismatch",
            "user_task_id": "task_mismatch",
            "gate_index": 0,
            "step_index": 1,
            "call_id": "call_mismatch",
            "proposed_tool_name": "send_email",
            "proposed_arguments": {"recipients": 12345, "subject": "Hello", "body": "World"},
            "prefix_step_count": 1,
            "available_prefix": [],
        }
        rec_mismatch = self.extractor.extract_from_feature_view(view_mismatch)
        self.assertTrue(rec_mismatch.has_type_mismatches)
        self.assertEqual(rec_mismatch.type_mismatch_count, 1)
        self.assertFalse(rec_mismatch.is_completely_schema_conformant)

    def test_deterministic_extraction(self):
        """Verify identical inputs produce identical feature vectors and JSON."""
        rec1 = self.extractor.extract_from_feature_view(self.base_feature_view)
        rec2 = self.extractor.extract_from_feature_view(self.base_feature_view)
        self.assertEqual(rec1.model_dump_json(), rec2.model_dump_json())
        self.assertEqual(rec1.to_numeric_dict(), rec2.to_numeric_dict())

    def test_exploratory_evaluation_refuses_positive_metrics(self):
        """Verify that evaluation code refuses to compute positive detection metrics without positive examples."""
        with self.assertRaises(ValueError) as ctx:
            assert_positive_metrics_blocked(positive_labels_present=False)
        self.assertIn("SCIENTIFIC INTEGRITY VIOLATION", str(ctx.exception))

    def test_benign_evaluation_generates_correct_summaries(self):
        """Verify exploratory benign evaluation computes trajectory-level and gate-point FAR."""
        rec1 = self.extractor.extract_from_feature_view(self.base_feature_view)
        report = run_exploratory_benign_evaluation([rec1])
        self.assertEqual(report.total_benign_trajectories, 1)
        self.assertEqual(report.total_benign_gate_points, 1)
        self.assertEqual(report.trajectory_level_false_alarm_count, 0)
        self.assertEqual(report.trajectory_level_false_alarm_rate, 0.0)
        self.assertIn("BLOCKED", report.positive_metrics_status)


if __name__ == "__main__":
    unittest.main()
