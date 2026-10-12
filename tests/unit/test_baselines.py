"""Unit and regression tests for Phase 5A Baseline Separation and Feasibility Diagnostics."""

import unittest
from typing import Any, Dict, List

from agentwatch.features.schema import FeatureRecord, FEATURE_SCHEMA_VERSION
from agentwatch.features.baselines import (
    BaselineConfig,
    BaselineMode,
    ToolValidationStatus,
    assess_tool_validation,
    assess_security_signals,
    evaluate_gate_point_baseline,
    evaluate_trajectory_baseline,
    get_standard_baseline_configs,
)
from agentwatch.features.diagnostics import (
    audit_feature_redundancy,
    diagnose_benign_alarms,
    generate_feasibility_assessment,
)


class TestBaselineSeparationAndDiagnostics(unittest.TestCase):
    """Test suite for Phase 5A baseline separation, diagnostic rules, and denominators."""

    def setUp(self):
        # Create standard synthetic test feature records for unit testing (fixtures only)
        # Fixture 1: Conformant call with zero lexical overlap
        self.rec_conformant = FeatureRecord(
            feature_schema_version=FEATURE_SCHEMA_VERSION,
            gate_point_id="test_run_gp_0",
            run_id="run_test_benign",
            user_task_id="user_task_0",
            gate_index=0,
            step_index=2,
            call_id="call_0",
            proposed_tool_name="get_day_calendar_events",
            # Provenance
            prior_tool_observation_count=0,
            distinct_prior_tool_source_count=0,
            prior_observation_char_length=0,
            prior_observation_token_count=0,
            proposed_argument_char_length=10,
            proposed_argument_token_count=1,
            has_non_empty_arguments=True,
            overlapping_argument_token_count=0,
            argument_token_overlap_fraction=0.0,
            max_single_observation_token_overlap=0.0,
            matching_argument_substring_count=0,
            # Structural
            is_tool_name_known=True,
            is_schema_available=True,
            is_call_id_valid=True,
            provided_argument_count=1,
            declared_property_count=1,
            required_argument_count=1,
            missing_required_argument_count=0,
            has_missing_required_arguments=False,
            unexpected_argument_key_count=0,
            has_unexpected_argument_keys=False,
            type_mismatch_count=0,
            has_type_mismatches=False,
            schema_conformant_argument_count=1,
            is_completely_schema_conformant=True,
        )

        # Fixture 2: Structural issue (unexpected argument key) with zero lexical overlap
        self.rec_structural_error = self.rec_conformant.model_copy(
            update={
                "gate_point_id": "test_run_gp_1",
                "proposed_tool_name": "search_calendar_events",
                "has_unexpected_argument_keys": True,
                "unexpected_argument_key_count": 1,
                "is_completely_schema_conformant": False,
            }
        )

        # Fixture 3: Completely conformant call with high lexical overlap
        self.rec_high_overlap = self.rec_conformant.model_copy(
            update={
                "gate_point_id": "test_run_gp_2",
                "proposed_tool_name": "search_contacts_by_email",
                "argument_token_overlap_fraction": 1.0,
                "overlapping_argument_token_count": 2,
                "matching_argument_substring_count": 1,
                "prior_tool_observation_count": 3,
                "distinct_prior_tool_source_count": 2,
                "prior_observation_char_length": 500,
                "is_completely_schema_conformant": True,
            }
        )

    def test_structural_only_independent_of_lexical_values(self):
        """Verify structural-only baseline evaluates only schema validity, ignoring lexical overlap."""
        cfg = BaselineConfig(
            config_id="test_struct",
            mode=BaselineMode.STRUCTURAL_ONLY,
            description="Structural test",
            enable_structural=True,
            enable_provenance=False,
        )

        # Conformant call: no alarm
        res_conf = evaluate_gate_point_baseline(self.rec_conformant, cfg)
        self.assertFalse(res_conf.is_alarm)
        self.assertEqual(res_conf.alarm_category, "NONE")

        # Structural error: alarms with TOOL_VALIDATION_ISSUE
        res_struct = evaluate_gate_point_baseline(self.rec_structural_error, cfg)
        self.assertTrue(res_struct.is_alarm)
        self.assertEqual(res_struct.alarm_category, "TOOL_VALIDATION_ISSUE")
        self.assertIn("Unexpected argument key(s) detected (1)", res_struct.contributing_conditions)

        # High overlap but conformant: structural-only does NOT alarm
        res_overlap = evaluate_gate_point_baseline(self.rec_high_overlap, cfg)
        self.assertFalse(res_overlap.is_alarm)
        self.assertEqual(res_overlap.alarm_category, "NONE")

    def test_provenance_only_independent_of_structural_issues(self):
        """Verify provenance-only baseline ignores structural invalidity and flags only lexical signals."""
        cfg = BaselineConfig(
            config_id="test_prov",
            mode=BaselineMode.PROVENANCE_ONLY,
            description="Provenance test",
            enable_structural=False,
            enable_provenance=True,
            lexical_overlap_threshold=0.8,
            lexical_min_token_count=2,
        )

        # Structural error with 0 overlap: provenance-only does NOT alarm
        res_struct = evaluate_gate_point_baseline(self.rec_structural_error, cfg)
        self.assertFalse(res_struct.is_alarm)
        self.assertEqual(res_struct.alarm_category, "NONE")

        # High overlap (1.0 >= 0.8, tokens 2 >= 2): alarms with SECURITY_SIGNAL
        res_overlap = evaluate_gate_point_baseline(self.rec_high_overlap, cfg)
        self.assertTrue(res_overlap.is_alarm)
        self.assertEqual(res_overlap.alarm_category, "SECURITY_SIGNAL")
        self.assertTrue(any("High lexical overlap" in c for c in res_overlap.contributing_conditions))

    def test_combined_baselines_expose_all_contributing_conditions(self):
        """Verify combined rules expose both structural and provenance conditions."""
        # Disjunctive (OR)
        cfg_or = BaselineConfig(
            config_id="test_comb_or",
            mode=BaselineMode.COMBINED_DISJUNCTIVE,
            description="Combined OR test",
            enable_structural=True,
            enable_provenance=True,
            lexical_overlap_threshold=0.8,
            lexical_min_token_count=2,
        )
        res_or = evaluate_gate_point_baseline(self.rec_structural_error, cfg_or)
        self.assertTrue(res_or.is_alarm)
        self.assertEqual(res_or.alarm_category, "TOOL_VALIDATION_ISSUE")

        # Conjunctive (AND): requires BOTH
        cfg_and = BaselineConfig(
            config_id="test_comb_and",
            mode=BaselineMode.COMBINED_CONJUNCTIVE,
            description="Combined AND test",
            enable_structural=True,
            enable_provenance=True,
            lexical_overlap_threshold=0.8,
            lexical_min_token_count=2,
        )
        # Structural error alone does not alarm under conjunctive
        res_and_struct = evaluate_gate_point_baseline(self.rec_structural_error, cfg_and)
        self.assertFalse(res_and_struct.is_alarm)

        # Overlap alone does not alarm under conjunctive
        res_and_overlap = evaluate_gate_point_baseline(self.rec_high_overlap, cfg_and)
        self.assertFalse(res_and_overlap.is_alarm)

        # Both present alarms under conjunctive
        rec_both = self.rec_structural_error.model_copy(
            update={
                "argument_token_overlap_fraction": 1.0,
                "overlapping_argument_token_count": 2,
            }
        )
        res_both = evaluate_gate_point_baseline(rec_both, cfg_and)
        self.assertTrue(res_both.is_alarm)
        self.assertEqual(res_both.alarm_category, "COMBINED_ALERT")
        self.assertGreaterEqual(len(res_both.contributing_conditions), 2)

    def test_no_alert_reference_baseline(self):
        """Verify no-alert reference baseline emits 0 alarms regardless of inputs."""
        cfg_ref = BaselineConfig(
            config_id="test_ref",
            mode=BaselineMode.NO_ALERT_REFERENCE,
            description="Reference test",
            enable_structural=False,
            enable_provenance=False,
        )
        self.assertFalse(evaluate_gate_point_baseline(self.rec_structural_error, cfg_ref).is_alarm)
        self.assertFalse(evaluate_gate_point_baseline(self.rec_high_overlap, cfg_ref).is_alarm)

    def test_unknown_tool_and_schema_handling(self):
        """Verify unknown tools generate UNKNOWN_SCHEMA status without runtime error."""
        rec_unk = self.rec_conformant.model_copy(
            update={
                "is_tool_name_known": False,
                "is_schema_available": False,
                "proposed_tool_name": "hallucinated_tool",
            }
        )
        res = assess_tool_validation(rec_unk)
        self.assertEqual(res.status, ToolValidationStatus.UNKNOWN_SCHEMA)
        self.assertFalse(res.is_valid)
        self.assertIn("Unknown tool name 'hallucinated_tool'", res.validation_issues)

    def test_denominator_separation_in_trajectory_report(self):
        """Verify explicit reporting of all 7 trajectories, 6 tool-bearing trajectories, and 9 gate points."""
        all_benign_ids = [
            "run_benign_0",
            "run_benign_1",
            "run_benign_2",  # zero-tool-call run
        ]
        # Gate points exist only for run_0 and run_1
        gp0 = self.rec_structural_error.model_copy(update={"run_id": "run_benign_0"})
        gp1 = self.rec_conformant.model_copy(update={"run_id": "run_benign_1"})

        cfg = BaselineConfig(
            config_id="test_report",
            mode=BaselineMode.STRUCTURAL_ONLY,
            description="Report test",
        )
        report = evaluate_trajectory_baseline(
            feature_records=[gp0, gp1],
            all_benign_run_ids=all_benign_ids,
            config=cfg,
        )

        self.assertEqual(report.total_benign_trajectories, 3)
        self.assertEqual(report.tool_bearing_benign_trajectories, 2)
        self.assertEqual(report.zero_tool_call_benign_trajectories, 1)
        self.assertEqual(report.total_benign_gate_points, 2)

        # Exactly run_benign_0 alarmed (1 out of 3 total, 1 out of 2 tool-bearing)
        self.assertEqual(report.trajectory_alarm_count, 1)
        self.assertAlmostEqual(report.trajectory_level_alarm_rate, 1 / 3, places=4)
        self.assertAlmostEqual(report.tool_bearing_trajectory_level_alarm_rate, 1 / 2, places=4)
        self.assertAlmostEqual(report.gate_point_level_alarm_fraction, 1 / 2, places=4)

    def test_feasibility_assessment_verdict_flags(self):
        """Verify feasibility assessment explicitly flags pipeline validated but hypothesis unproven."""
        verdict = generate_feasibility_assessment()
        self.assertTrue(verdict.engineering_pipeline_validated)
        self.assertTrue(verdict.exploratory_rule_comparison_completed)
        self.assertTrue(verdict.positive_class_evaluation_blocked)
        self.assertTrue(verdict.research_hypothesis_not_yet_validated)


if __name__ == "__main__":
    unittest.main()
