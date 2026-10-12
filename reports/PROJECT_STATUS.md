  # AgentWatch: Project Status

## Project Overview
- **Project Name:** AgentWatch
- **Research Goal:** Investigate whether lightweight provenance-based and structural features can detect indirect prompt-injection hijacking of tool-using AI agents before a harmful tool call, at a controlled per-trajectory false-positive rate, and determine whether learned features provide measurable improvement.
- **Primary Benchmark:** AgentDojo
- **Hardware Target:** Local NVIDIA GeForce RTX 3060 Laptop GPU (6,144 MiB / 6 GB VRAM, Compute Capability 8.6, Driver 616.92) for local ML workloads.
- **Repository Location:** `D:\Agent_watch_prov`

## Phase Roadmap & Status Summary

| Phase | Description | Status | Latest Report |
|---|---|---|---|
| **Phase 0** | Workspace & Environment Audit | **COMPLETED** | [Phase 0 Part 0.4](file:///D:/Agent_watch_prov/reports/build_reports/phase_00_part_04_report.md) |
| **Phase 1** | Minimal AgentDojo Integration | **COMPLETED** (Reconciled & Audited) | [Phase 1 Closure & Phase 2 Prep](file:///D:/Agent_watch_prov/reports/build_reports/phase_01_closure_and_phase_02_preparation.md) |
| **Phase 2** | Raw Logging and Data Contracts | **COMPLETED** (Validated & Tested) | [Phase 2 Completion](file:///D:/Agent_watch_prov/reports/build_reports/phase_02_completion.md) |
| **Phase 3** | Ground Truth and Causal Gate Points | **COMPLETED** (Dataset Built, Audited & Collection Study Run) | [Phase 3 Collection Study](file:///D:/Agent_watch_prov/reports/build_reports/phase_03_zero_cost_collection_study.md) |
| **Phase 4A** | Post-Exposure Coverage & Positive-Case Discovery | **COMPLETED** (Audit, Leakage Tests, Phase 4A Collection) | [Phase 4A Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_04a_post_exposure_coverage_and_positive_case_discovery.md) |
| **Phase 4B** | Provenance & Structural Feature Extraction | **COMPLETED** (25 Features Extracted, Negative Calibration) | [Phase 4B Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_04b_provenance_and_structural_feature_extraction.md) |
| **Phase 5A** | Baseline Separation & Feasibility Checkpoint | **COMPLETED** (Tool Validation vs Security Separated) | [Phase 5A Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_05a_baseline_separation_and_feasibility_checkpoint.md) |
| **Phase 5B** | Targeted Positive-Case Acquisition & Feasibility Gate | **COMPLETED** (14 Runs, Rigorous GT Matcher, Infeasibility Confirmed) | [Phase 5B Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_05b_targeted_positive_case_acquisition.md) |
| **Phase 5C** | Corpus Reconciliation & Alternative Local Model Feasibility | **COMPLETED** (Corpus Reconciled, Llama 3.2 3B Evaluated) | [Phase 5C Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_05c_corpus_reconciliation_and_alternative_model_feasibility.md) |
| **Phase 5D** | Temporal Consistency Audit & One-Class Feasibility | **COMPLETED** (Temporal Audit, v2 Features, One-Class LOTO-CV) | [Phase 5D Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_05d_temporal_audit_and_one_class_feasibility.md) |
| **Phase 5E** | Authentic Positive Acquisition & Evaluation Readiness | **COMPLETED** (8-Stage Taxonomy, Attack Matrix, Locked Protocol) | [Phase 5E Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_05e_authentic_positive_case_acquisition.md) |
| **Phase 6A** | 12B Local Model Capability & Attack Feasibility | **COMPLETED** (32 Controlled Runs, Mistral Nemo 12B vs Qwen 3B, Infeasibility Confirmed) | [Phase 6A Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_06a_12b_model_capability_and_attack_feasibility.md) |
| **Phase 6B** | Evidence Audit, Thesis Synthesis & Package Preparation | **COMPLETED** (Corpus Audit, Task Reconciliation, Full Thesis Package) | [Phase 6B Report](file:///D:/Agent_watch_prov/reports/build_reports/phase_06b_thesis_synthesis_and_evidence_audit.md) |
| Phase 7 | Final Research Archive & Distribution | Not Started | - |

## Current Implementation Status
- **Current Phase:** Phase 6B — Evidence Audit, Thesis Synthesis & Package Preparation (Completed)
- **Current Part:** Milestone Build Completed; Transition to Phase 7
- **Git Branch:** `main`
- **GPU Verification:** NVIDIA GeForce RTX 3060 Laptop GPU (6,144 MiB / 6 GB VRAM, Driver 616.92, PyTorch 2.7.1+cu118).
- **Benchmark & Package Versions:** Pinned `agentdojo==0.1.35`, benchmark suite `v1` (`workspace`). Local models `qwen2.5:3b`, `llama3.2:3b`, and `mistral-nemo:12b-instruct-2407-q4_K_M` hosted via Ollama daemon (`http://127.0.0.1:11434`) with zero cloud cost ($0.00).
- **Phase 6B Evidence Audit & Task Reconciliation:**
  - Audited all 75 genuine benchmark trajectories and 181 gate points across all 6 repository partitions.
  - Resolved qualitative task description error in Phase 6A narrative: `user_task_1` and `user_task_5` verified as 100% genuine calendar queries in manifests, code, and raw traces.
  - Recomputed authoritative numbers directly from raw records: 47 attacked runs, 28 benign runs, 28 payload exposures, 7 post-exposure tool opportunities, 0 harmful tool proposals, 0 harmful actions executed, 0 security breaches ($N_{\text{pos}} = 0$).
  - Authored full thesis research package under `reports/thesis/` (`THESIS_DRAFT.md`, `RESULTS_EVIDENCE_LEDGER.md`, `CLAIMS_AND_LIMITATIONS.md`, `REPRODUCIBILITY_GUIDE.md`, `OPEN_ISSUES.md`).
- **Definitive Research Determination (Decisions 019 & 020):**
  - Evaluating detector sensitivity (TPR, ROC-AUC) remains strictly blocked because $N_{\text{pos}} = 0$ across all 75 genuine runs and 3 distinct model architectures.
  - Formally reframed AgentWatch as an empirical research thesis on the methodological and practical challenges of pre-execution prompt-injection detection under extreme class imbalance and real-world instruction-tuned model robustness.
- **Scientific Feasibility Verdict:**
  - `CANONICAL_MULTIMODEL_CORPUS_VALIDATED`: True
  - `EXPOSURE_TIMING_VALIDATED`: True
  - `MULTIMODEL_FEATURE_EXTRACTION_VALIDATED`: True
  - `EVALUATION_PROTOCOL_LOCKED`: True
  - `POPULATION_FAR_5_PERCENT_ESTABLISHED`: False (Mathematically unachievable at $N=28$; $N \ge 59$ required)
  - `POSITIVE_CLASS_DETECTION_EVALUATION_READY`: False (0 positive ground-truth hijackings; positive metrics remain strictly blocked)
  - `RESEARCH_HYPOTHESIS_VALIDATED`: False (Hypothesis remains unproven without authentic positive cases).
- **Test Status:** 78/78 unit and integration tests passing (`tests.unit.test_phase6a_experiment`, `tests.unit.test_phase5e_taxonomy_and_readiness`, `tests.unit.test_phase5d_temporal_and_one_class`, `tests.unit.test_canonical_registry`, `tests.unit.test_phase5b_acquisition`, `tests.unit.test_ground_truth_matcher`, `tests.unit.test_baselines`, `tests.unit.test_features`, `tests.unit.test_device`, `tests.integration.test_pilot_integration`).

## Decision Log Reference
Key architectural and methodological decisions are tracked in [DECISION_LOG.md](file:///D:/Agent_watch_prov/reports/DECISION_LOG.md) (Decisions 001 through 020).

## Next Approved Implementation Step
- Proceed to Phase 7: Final research archiving, cryptographic sealing of the repository, and formal package distribution.
