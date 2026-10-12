# Build Report: Phase 0, Part 0.3 — AgentDojo Feasibility Assessment

## A. Build Identification
- **Phase & Part Number:** Phase 0, Part 0.3
- **Build Date & Time:** 2026-10-11 19:05:30 IST
- **Objective & Scope:** Perform an exhaustive technical investigation of the official AgentDojo repository, PyPI package releases, execution architecture, pipeline contracts, ground-truth evaluation, and causal pre-execution gate-point hooks. Document all findings in `docs/agentdojo_feasibility.md`.
- **Acceptance Criteria:**
  1. Pin exact package version and benchmark version with clear distinction between them.
  2. Inspect supported Python runtimes and dependencies against our verified environment.
  3. Determine how user tasks, injection tasks, utility, and security outcomes are evaluated.
  4. Verify pipeline architecture and identify causal pre-execution gate-point hooks (`BasePipelineElement`).
  5. Analyze exposure labeling and feasibility of identifying harmful-action timing ($t_{\text{harm}}$).
  6. Inspect licensing (MIT) and benchmark limitations.
  7. Produce `docs/agentdojo_feasibility.md` and this mandatory build report.

## B. Changes Implemented
- **Files Created:**
  - `docs/agentdojo_feasibility.md` — Detailed technical feasibility assessment covering upstream architecture, contracts, pipeline elements, hooks, evaluation, and cost estimates.
  - `reports/build_reports/phase_00_part_03_report.md` — This mandatory build report.
- **Files Modified:**
  - `reports/PROJECT_STATUS.md` — Updated with Part 0.3 completion.
  - `reports/DECISION_LOG.md` — Added Decision 003.

## C. Dependency and Environment Audit Findings
- **Package Release:** `agentdojo==0.1.35` on PyPI (36 releases total; latest is 0.1.35).
- **Benchmark Suite Version:** `v1` (suites: `workspace`, `slack`, `travel`, `banking`).
- **Python Compatibility:** Package requires `>=3.10`. Confirmed compatible with our verified `Python 3.11` runtime.
- **License:** MIT License.
- **Dependencies Verified:** `pydantic>=2.7.1`, `deepdiff>=8.6.1`, `rich>=13.7.1`, `tenacity>=8.2.3`, `pyyaml>=6.0.1`, `openai>=1.59.7`, `anthropic>=0.47.0`, `google-genai>=1.15.0`.

## D. Architecture & Hook Findings
- **Causal Gate-Point Representation:**
  - Upstream AgentDojo does not provide a built-in pre-execution hook in its command-line runner.
  - However, AgentDojo pipelines are composed of modular `BasePipelineElement` instances (`query(query, runtime, env, messages)`).
  - An `InstrumentedToolsExecutor` can be inserted immediately before tool execution in the pipeline. It intercepts `messages[-1]` (the proposed tool call) and the preceding prefix `messages[:-1]`, recording the gate point before executing the tool.
  - This guarantees strict causal isolation without data leakage.
- **Exposure Labeling:**
  - Provenance must be captured directly from `FunctionsRuntime` outputs. Injected payload strings can be detected in observations, but formatting/truncation effects must be tracked.
- **Harmful-Action Timing ($t_{\text{harm}}$):**
  - Upstream evaluates `injection_task.security(env, messages)` only at the end of the entire trajectory.
  - Incremental replay feasibility must be verified in Phase 3 before assigning step-level $t_{\text{harm}}$ labels. We will not fabricate $t_{\text{harm}}$ labels.

## E. Tests and Validation
- **Queries & Inspections Executed:**
  - PyPI metadata queries (`agentdojo` releases, versions, requirements).
  - Source code inspection of `benchmark.py`, `logging.py`, `base_pipeline_element.py`.
  - Upstream documentation review on `agent_pipeline`, `task_suite`, `FunctionsRuntime`.
  - Re-verified existing tests (`tests.unit.test_device` 4/4 passing).

## F. Problems and Unresolved Issues
- Upstream AgentDojo CLI is designed for end-to-end benchmarking rather than step-by-step gatekeeper monitoring. An instrumented execution wrapper (`InstrumentedToolsExecutor`) is required and will be implemented in Phase 1 / Phase 2.
- $t_{\text{harm}}$ timing cannot be assumed to be given by AgentDojo out-of-the-box; it requires incremental state verification or defensible proxy definitions.

## G. Next Steps
- **Next Part:** **Phase 0, Part 0.4: Document blockers, decisions, dependencies, and acceptance criteria.**
- **Prerequisites for Part 0.4:** User approval of this report. In Part 0.4, we will finalize all Phase 0 findings, establish explicit exit criteria for Phase 0, and lay out the exact requirements and dependency lockfile for Phase 1.

## H. Build Verdict
**PASS:** All acceptance criteria for Phase 0, Part 0.3 have been met. Verified primary sources, documented upstream architecture, identified causal gate-point hooks, and produced `docs/agentdojo_feasibility.md`.
