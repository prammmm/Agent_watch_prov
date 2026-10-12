"""Run Canonical Corpus Audit and Generate Canonical Reports."""

import json
from pathlib import Path
from agentwatch.traces.canonical_registry import build_canonical_corpus_registry


def main():
    print("=== EXECUTING CANONICAL CORPUS AUDIT ===")
    audit = build_canonical_corpus_registry()

    out_file = Path("reports/canonical_corpus_audit.json")
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(audit.model_dump_json(indent=2))

    print(f"\nAudit completed successfully. Canonical report saved to {out_file}")
    print("\n--- Partition Breakdown ---")
    for p_name, counts in audit.partition_breakdown.items():
        print(f"  {p_name:<22}: {counts['trajectories']} trajectories, {counts['gate_points']} gate points")

    print("\n--- Consolidated Reconciled Totals ---")
    print(f"  Total Authentic Trajectories: {audit.total_trajectories}")
    print(f"    - Benign:                  {audit.benign_trajectories}")
    print(f"    - Attacked:                {audit.attacked_trajectories}")
    print(f"        - Payload Delivered:   {audit.payload_delivered_trajectories}")
    print(f"        - Payload Observed:    {audit.payload_observed_trajectories}")
    print(f"        - Unexposed:           {audit.unexposed_attacked_trajectories}")
    print(f"  Total Gate Points:           {audit.total_gate_points}")
    print(f"    - Pre-Exposure GPs:        {audit.pre_exposure_gate_points}")
    print(f"    - Post-Exposure GPs:       {audit.post_exposure_gate_points}")
    print(f"  Outcomes:")
    print(f"    - Harmful Proposed:        {audit.harmful_actions_proposed}")
    print(f"    - Harmful Executed:        {audit.harmful_actions_executed}")
    print(f"    - Successful Hijacks:      {audit.successful_hijackings}")
    print(f"    - Security Resisted:       {audit.security_resisted}")
    print(f"    - Utility Successes:       {audit.utility_successes}")
    print(f"    - Utility Failures:        {audit.utility_failures}")
    print(f"  Duplicate Run IDs Detected:  {len(audit.duplicate_run_ids)}")
    print(f"  Content Duplicates Detected: {len(audit.content_hash_duplicates)}")
    print(f"  Integrity / Excluded Runs:   {audit.excluded_runs_count}")


if __name__ == "__main__":
    main()
