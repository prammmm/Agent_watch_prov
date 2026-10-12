"""Unit tests for Canonical Run Registry and Corpus Reconciliation."""

import unittest
from pathlib import Path

from agentwatch.traces.canonical_registry import (
    build_canonical_corpus_registry,
    CanonicalRunEntry,
    CanonicalCorpusAudit,
)


class TestCanonicalRegistry(unittest.TestCase):
    def test_canonical_corpus_reconciliation(self):
        """Verify the canonical corpus across all partitions reconciles exactly."""
        audit = build_canonical_corpus_registry(base_repo_dir=".")

        # Totals across all 4 partitions
        self.assertEqual(audit.total_runs_inspected, 35)
        self.assertEqual(audit.canonical_runs_count, 35)
        self.assertEqual(audit.excluded_runs_count, 0)
        self.assertEqual(len(audit.duplicate_run_ids), 0)
        self.assertEqual(len(audit.content_hash_duplicates), 0)

        # Gate point count
        self.assertEqual(audit.total_gate_points, 119)
        self.assertEqual(audit.pre_exposure_gate_points, 108)
        self.assertEqual(audit.post_exposure_gate_points, 11)

        # Trajectory partitions
        self.assertEqual(audit.partition_breakdown["pilot_runs"]["trajectories"], 10)
        self.assertEqual(audit.partition_breakdown["pilot_runs"]["gate_points"], 18)
        self.assertEqual(audit.partition_breakdown["collection_study"]["trajectories"], 4)
        self.assertEqual(audit.partition_breakdown["collection_study"]["gate_points"], 5)
        self.assertEqual(audit.partition_breakdown["phase4a_collection"]["trajectories"], 7)
        self.assertEqual(audit.partition_breakdown["phase4a_collection"]["gate_points"], 53)
        self.assertEqual(audit.partition_breakdown["phase5b_collection"]["trajectories"], 14)
        self.assertEqual(audit.partition_breakdown["phase5b_collection"]["gate_points"], 43)

        # Security outcomes are strictly decoupled and verified
        self.assertEqual(audit.harmful_actions_proposed, 0)
        self.assertEqual(audit.harmful_actions_executed, 0)
        self.assertEqual(audit.successful_hijackings, 0)
        self.assertEqual(audit.security_resisted, 25)

    def test_zero_tool_call_runs_are_canonical(self):
        """Verify zero-tool-call trajectories are recognized as canonical runs."""
        audit = build_canonical_corpus_registry(base_repo_dir=".")
        zero_tool_runs = [e for e in audit.runs if e.is_zero_tool_call]

        self.assertEqual(len(zero_tool_runs), 2)
        zero_run_ids = {e.run_id for e in zero_tool_runs}
        self.assertTrue(any("user_task_2" in r for r in zero_run_ids))
        self.assertTrue(any("user_task_4" in r for r in zero_run_ids))

        for entry in zero_tool_runs:
            self.assertTrue(entry.is_canonical)
            self.assertTrue(entry.integrity_valid)
            self.assertEqual(entry.step_count, 0)
            self.assertEqual(entry.gate_point_count, 0)

    def test_multimodel_corpus_with_phase5c(self):
        """Verify expanded multi-model corpus including Phase 5C runs."""
        audit = build_canonical_corpus_registry(
            base_repo_dir=".",
            additional_partitions=["phase5c_collection"],
        )
        self.assertEqual(audit.total_runs_inspected, 43)
        self.assertEqual(audit.canonical_runs_count, 43)
        self.assertEqual(audit.total_gate_points, 139)
        self.assertEqual(audit.partition_breakdown["phase5c_collection"]["trajectories"], 8)
        self.assertEqual(audit.partition_breakdown["phase5c_collection"]["gate_points"], 20)

        # Multi-model representation
        models = {e.agent_model for e in audit.runs}
        self.assertEqual(models, {"qwen2.5:3b", "llama3.2:3b"})

        # Security outcomes remain 0 across both models
        self.assertEqual(audit.harmful_actions_proposed, 0)
        self.assertEqual(audit.harmful_actions_executed, 0)
        self.assertEqual(audit.successful_hijackings, 0)


if __name__ == "__main__":
    unittest.main()

