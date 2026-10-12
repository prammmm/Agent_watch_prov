"""Unit tests for Phase 6A: 12B Model Capability and Controlled Experiment Validation."""

import json
import unittest
from pathlib import Path

from agentwatch.traces.integrity import verify_run_integrity
from agentwatch.traces.schema import RawExecutionRecord, GroundTruthLabelRecord


class TestPhase6AExperiment(unittest.TestCase):
    def setUp(self):
        self.repo_root = Path("D:/Agent_watch_prov")
        self.phase6a_dir = self.repo_root / "data" / "phase6a_collection"
        self.manifest_path = self.phase6a_dir / "manifests" / "phase6a_predeclared_manifest.json"
        self.summary_path = self.phase6a_dir / "manifests" / "phase6a_execution_summary.json"

    def test_predeclared_manifest_structure(self):
        """Verify that predeclared manifest exists and declares exactly 32 planned runs."""
        self.assertTrue(self.manifest_path.exists())
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["total_planned_budget"], 32)
        self.assertEqual(len(manifest["planned_runs"]), 32)
        self.assertIn("mistral-nemo:12b-instruct-2407-q4_K_M", manifest["models"])
        self.assertIn("qwen2.5:3b", manifest["models"])

    def test_execution_summary_completeness(self):
        """Verify that all 32 planned runs were executed and recorded."""
        self.assertTrue(self.summary_path.exists())
        with open(self.summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)
        self.assertEqual(summary["total_executed"], 32)
        self.assertEqual(len(summary["runs"]), 32)

    def test_run_trace_and_label_integrity(self):
        """Verify that raw trace and label files exist and satisfy schema integrity."""
        with open(self.summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        for r in summary["runs"]:
            raw_path = Path(r["raw_file"])
            label_path = Path(r["label_file"])
            self.assertTrue(raw_path.exists(), f"Raw file missing: {raw_path}")
            self.assertTrue(label_path.exists(), f"Label file missing: {label_path}")

            # Verify integrity
            integrity = verify_run_integrity(raw_path, label_path)
            self.assertTrue(integrity.is_valid, f"Integrity failed for {r['run_id']}: {integrity.errors}")

    def test_zero_harmful_actions_and_zero_hijackings(self):
        """Verify that across all 32 runs, exactly zero harmful actions and hijackings occurred."""
        with open(self.summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        for r in summary["runs"]:
            self.assertFalse(r["harmful_action_proposed"], f"Unexpected harmful proposal in {r['run_id']}")
            self.assertFalse(r["harmful_action_executed"], f"Unexpected harmful execution in {r['run_id']}")
            if r["security_success"] is not None:
                self.assertFalse(r["security_success"], f"Unexpected security success in {r['run_id']}")

    def test_matched_task_condition_balance(self):
        """Verify that both models have exactly 8 benign and 8 attacked trials across the 4 tasks."""
        with open(self.summary_path, "r", encoding="utf-8") as f:
            summary = json.load(f)

        counts = {}
        for r in summary["runs"]:
            key = (r["agent_model"], r["user_task_id"], r["condition"])
            counts[key] = counts.get(key, 0) + 1

        # Each model * task * condition should have exactly 2 repetitions
        for key, count in counts.items():
            self.assertEqual(count, 2, f"Expected 2 repetitions for {key}, got {count}")


if __name__ == "__main__":
    unittest.main()
