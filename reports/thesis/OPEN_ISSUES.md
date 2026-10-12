# AgentWatch: Open Issues and Research Bottlenecks

**Document Version:** 1.0.0  
**Date:** 2026-10-12  
**Milestone:** Phase 6B Thesis Evidence Synthesis  
**Status:** Active Research Tracking  
**Repository Location:** `D:\Agent_watch_prov`  

This document tracks unresolved methodological questions, experimental bottlenecks, and open technical challenges identified during the AgentWatch investigation.

---

## 1. Primary Research Blockers

### Issue 1: Positive-Case Acquisition Bottleneck in Zero-Cost Local Environments
- **Description:** Across 75 authentic benchmark runs and 47 attacked trials spanning three open-weight models (3B to 12B), zero attacks resulted in harmful tool proposals or executed security breaches ($N_{\text{pos}} = 0$).
- **Impact:** Positive-class detection metrics (TPR, Sensitivity, Precision, F1-Score, ROC-AUC) cannot be computed. Evaluating the core hypothesis—that lightweight provenance features detect indirect prompt-injection hijacking—is blocked.
- **Root Cause:** Modern instruction-tuned models exhibit a strong inductive bias prioritizing system prompts and user task goals over unverified instructions embedded in tool observations (such as calendar entries). Furthermore, small-to-medium models frequently fail to complete multi-step tasks, terminating early before attacker instructions can be parsed into actionable tool invocations.
- **Resolution Strategy:** Investigating stronger attack formulations (e.g. adaptive prompt optimization, multi-turn conversational hijacking) or evaluating larger frontier models (e.g. 70B open-weights or API models) if budget/hardware allows in future research.

### Issue 2: Sample Size Deficit for Trajectory-Level False-Alarm Control
- **Description:** A statistically defensible claim of population per-trajectory False Alarm Rate $\text{FAR} \le 5\%$ with 95% confidence requires $N \ge 59$ independent, false-alarm-free benign trajectories ($k=0$) under the one-sided binomial upper bound.
- **Impact:** The repository currently has $N = 28$ benign runs (with only 12 in the segregated historical development set, where 1 false alarm was observed).
- **Status:** `POPULATION_FAR_5_PERCENT_ESTABLISHED` remains **False**. Future evaluation requires collecting an independent test split of $\ge 59$ benign trajectories.

---

## 2. Technical and Methodological Open Questions

### Issue 3: Post-Exposure Decision Truncation
- **Description:** In 21 of the 28 runs where models observed the injected payload (75.0%), the agent immediately emitted a final user-facing text message rather than a tool call, terminating the trajectory.
- **Analysis:** This truncation limits the causal observation window. The model observed the attack, but because it had already finished its perceived task (or errored), it never faced another tool-calling decision point. Only 7 runs across the repository provided a genuine post-exposure tool-calling opportunity.
- **Implication:** Benchmark tasks must be selected or designed specifically to require tool operations *after* reading untrusted data (e.g. reading an email and then requiring an action on the basis of that email).

### Issue 4: Benign Task Utility Floor
- **Description:** Overall benign task utility across the repository is 39.3% (11/28), and on complex tasks like `user_task_4`, benign utility is only 14.3% (1/7).
- **Analysis:** When an agent cannot reliably solve the primary benign task, its failure to execute a secondary injection attack cannot be unambiguously attributed to security alignment. An agent that cannot write calendar events for benign users is unlikely to write calendar events for attackers.
- **Future Need:** Evaluating prompt-injection security requires benchmark tasks where base model capability is sufficiently high ($> 80\%$ benign utility) so that attack execution failure reflects true robustness rather than model incompetence.
