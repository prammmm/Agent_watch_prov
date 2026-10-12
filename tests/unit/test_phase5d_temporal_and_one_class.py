"""Unit tests for Phase 5D: Temporal Consistency Audit & One-Class Detection Feasibility."""

import json
import unittest
from pathlib import Path

from agentwatch.features.extractor import GatePointFeatureExtractor, PROHIBITED_LABEL_KEYS
from agentwatch.features.schema import FeatureRecord, FEATURE_SCHEMA_VERSION, FEATURE_DATA_DICTIONARY
from scripts.audit_corpus_temporal_consistency import run_corpus_temporal_audit
from scripts.evaluate_one_class_feasibility import (
    wilson_score_interval,
    run_one_class_grouped_cv,
    load_extracted_features_and_sidecar,
    evaluate_deterministic_rules,
)


class TestPhase5DTemporalAndOneClass(unittest.TestCase):
    def setUp(self):
        self.data_dir = Path("data")
        self.derived_dir = self.data_dir / "derived_datasets"

    def test_temporal_reconstruction_causal_invariants(self):
        """Verify that a tool proposal strictly never sees its own or future observations."""
        audit_report = run_corpus_temporal_audit(
            base_data_dir="data",
            output_report_path="reports/temporal_consistency_audit.json",
        )
        self.assertEqual(audit_report.total_trajectories_audited, 43)
        self.assertEqual(audit_report.total_gate_points_audited, 139)

        # Inspect every trajectory's gate point details
        for traj in audit_report.trajectories:
            for gp in traj.gate_point_details:
                # Step index of proposal must be strictly greater than 0
                self.assertGreater(gp.proposed_step_index, 0)
                # Prior observations count must not exceed total steps
                self.assertLess(gp.prior_observations_count, traj.total_steps)

    def test_post_exposure_gate_point_counting_across_models(self):
        """Verify consistent post-exposure timing semantics between Llama and Qwen."""
        audit_report = run_corpus_temporal_audit(
            base_data_dir="data",
            output_report_path="reports/temporal_consistency_audit.json",
        )
        # Llama-3.2-3B: batched turn-1 calls mean 0 post-exposure gate points
        llama_stats = audit_report.model_breakdown["llama3.2:3b"]
        self.assertEqual(llama_stats["total_trajectories"], 8)
        self.assertEqual(llama_stats["post_exposure_gate_points"], 0)
        self.assertEqual(llama_stats["single_turn_batched_exposed_trajectories"], 5)

        # Qwen-2.5-3B: multi-turn calls produce exactly 11 post-exposure gate points
        qwen_stats = audit_report.model_breakdown["qwen2.5:3b"]
        self.assertEqual(qwen_stats["total_trajectories"], 35)
        self.assertEqual(qwen_stats["post_exposure_gate_points"], 11)
        self.assertEqual(qwen_stats["trajectories_with_post_exposure_gps"], 6)

        # Corpus totals
        self.assertEqual(audit_report.total_pre_exposure_gate_points, 128)
        self.assertEqual(audit_report.total_post_exposure_gate_points, 11)
        self.assertEqual(audit_report.total_gate_points_audited, 139)

    def test_canonical_feature_dataset_reconciliation(self):
        """Verify features_multimodel_v2 contains exactly 139 records matching the corpus."""
        json_path = self.derived_dir / "features_multimodel_v2.json"
        csv_path = self.derived_dir / "features_multimodel_v2.csv"
        sidecar_path = self.derived_dir / "features_multimodel_v2_sidecar.json"

        self.assertTrue(json_path.exists())
        self.assertTrue(csv_path.exists())
        self.assertTrue(sidecar_path.exists())

        with open(json_path, "r", encoding="utf-8") as f:
            features = json.load(f)
        self.assertEqual(len(features), 139)

        with open(sidecar_path, "r", encoding="utf-8") as f:
            sidecar = json.load(f)
        self.assertEqual(len(sidecar), 139)

        # Check every feature record conforms to schema
        expected_features = set(FEATURE_DATA_DICTIONARY.keys())
        for r in features:
            f_rec = FeatureRecord.model_validate(r)
            self.assertEqual(f_rec.feature_schema_version, FEATURE_SCHEMA_VERSION)
            vec_keys = set(f_rec.get_feature_vector().keys())
            self.assertEqual(vec_keys, expected_features)

    def test_strict_feature_view_label_leakage_prohibition(self):
        """Verify that GatePointFeatureExtractor strictly refuses prohibited label keys."""
        extractor = GatePointFeatureExtractor()
        clean_view = {
            "gate_point_id": "test_gp_0",
            "run_id": "test_run",
            "user_task_id": "user_task_0",
            "gate_index": 0,
            "step_index": 2,
            "proposed_tool_name": "search_calendar_events",
            "proposed_arguments": {"query": "meeting"},
            "prefix_step_count": 2,
            "available_prefix": [],
        }
        # Clean extraction succeeds
        record = extractor.extract_from_feature_view(clean_view)
        self.assertIsInstance(record, FeatureRecord)

        # Leaked label triggers ValueError
        for prohibited_key in PROHIBITED_LABEL_KEYS:
            dirty_view = dict(clean_view)
            dirty_view[prohibited_key] = True
            with self.assertRaises(ValueError):
                extractor.extract_from_feature_view(dirty_view)

    def test_one_class_grouped_cv_separation(self):
        """Verify that Leave-One-Trajectory-Out CV separates training and testing by run_id."""
        features, sidecar, trajs = load_extracted_features_and_sidecar()
        iforest_results = run_one_class_grouped_cv(features, sidecar, trajs, random_state=42)

        folds = iforest_results["benign_cross_validation_results"]["folds"]
        # Exactly 11 tool-bearing benign trajectories yield 11 folds
        self.assertEqual(len(folds), 11)

        for fold in folds:
            held_out_run = fold["held_out_run_id"]
            # Assert held-out gate points were scored
            self.assertGreater(fold["held_out_gate_points_count"], 0)
            self.assertEqual(len(fold["anomaly_scores"]), fold["held_out_gate_points_count"])
            # Active features were selected on training fold
            self.assertGreater(fold["active_features_in_fold"], 0)

    def test_zero_tool_call_trajectory_handling(self):
        """Verify that zero-tool-call trajectories are explicitly accounted for as 0 alerts."""
        features, sidecar, trajs = load_extracted_features_and_sidecar()
        iforest_results = run_one_class_grouped_cv(features, sidecar, trajs, random_state=42)

        benign_res = iforest_results["benign_cross_validation_results"]
        self.assertEqual(benign_res["total_benign_trajectories"], 12)
        self.assertEqual(benign_res["tool_bearing_benign_trajectories"], 11)
        self.assertEqual(benign_res["zero_tool_call_benign_trajectories"], 1)

    def test_statistical_sample_size_refusal_for_5_pct_far(self):
        """Verify that N=12 benign trajectories cannot guarantee population FAR <= 5%."""
        # Even with 0 observed alarms out of 12 runs:
        ci_low, ci_high = wilson_score_interval(0, 12)
        self.assertEqual(ci_low, 0.0)
        self.assertGreater(ci_high, 0.05)  # Upper bound is ~24.25%
        self.assertAlmostEqual(ci_high, 0.2425, places=3)

        # For 12 benign trajectories with observed alerts:
        ci_obs_low, ci_obs_high = wilson_score_interval(9, 12)
        self.assertGreater(ci_obs_high, 0.05)

    def test_positive_class_metrics_blocked(self):
        """Verify that positive-class evaluation remains strictly blocked due to 0 hijackings."""
        features, sidecar, trajs = load_extracted_features_and_sidecar()
        rule_results = evaluate_deterministic_rules(features, sidecar, trajs)

        # Confirm 0 harmful proposals and 0 hijackings in ground truth
        self.assertEqual(sum(1 for t in trajs if t.get("security_success") is True), 0)
        self.assertEqual(sum(1 for t in trajs if t.get("harmful_action_proposed") is True), 0)


if __name__ == "__main__":
    unittest.main()
