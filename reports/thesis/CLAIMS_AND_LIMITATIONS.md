# AgentWatch: Claims and Limitations

**Document Version:** 1.0.0  
**Date:** 2026-10-12  
**Milestone:** Phase 6B Thesis Evidence Synthesis  
**Scope:** Rigorous Epistemic Boundary Analysis  
**Repository Location:** `D:\Agent_watch_prov`  

This document delineates the exact epistemic boundary of the AgentWatch project: what the collected empirical evidence demonstrably establishes, what it does not establish, and the formal methodological limitations of this research.

---

## 1. What the Empirical Evidence Establishes

1. **Instrumentation & Causal Gate-Point Viability:**
   - Pre-execution tool call interception is functionally viable without modifying core agent reasoning loops.
   - The causal gate-point representation (`GatePointDatasetRecord`) successfully isolates pre-execution tool proposals from subsequent execution effects, ensuring that post-execution outcomes cannot leak into detector features.

2. **Decoupled 8-Stage Outcome Taxonomy:**
   - Indirect prompt injection cannot be treated as a single binary variable. Separating:
     $$\text{Configured} \to \text{Delivered} \to \text{Observed} \to \text{Opportunity} \to \text{Proposal} \to \text{Execution} \to \text{Security Breach} \to \text{Utility}$$
     prevents conflating payload delivery with agent compromise.

3. **Empirical Absence of Positive Cases in Tested Configurations ($N_{\text{pos}} = 0$):**
   - Across 75 authentic benchmark trajectories (47 attacked) spanning three distinct instruction-tuned model architectures (`qwen2.5:3b`, `llama3.2:3b`, `mistral-nemo:12b`), **zero harmful tool calls were proposed**, **zero harmful actions executed**, and **zero benchmark security breaches occurred**.
   - When models observe indirect prompt-injection instructions embedded in tool outputs (e.g., calendar descriptions), they exhibit an inductive bias toward fulfilling the user's primary goal, returning neutral conversational responses, or halting in loops. They do not execute attacker exfiltration instructions under the tested conditions.

4. **Zero-Cost Local Reproducibility:**
   - Full end-to-end multi-turn benchmark evaluation with structured tool calling is reproducible on consumer workstation hardware (NVIDIA RTX 3060 Laptop GPU, 6 GB VRAM) under zero cloud expenditure ($0.00).

5. **Statistical Requirement for False-Alarm Rate Control:**
   - Demonstrating a population trajectory-level False Alarm Rate $\text{FAR} \le 5\%$ with 95% confidence requires observing at least $N = 59$ independent, false-alarm-free benign trajectories ($k=0$) under the one-sided binomial upper bound.

---

## 2. What the Empirical Evidence Does NOT Establish

1. **Does NOT Validate the Core Detection Hypothesis:**
   - The central research question—whether lightweight provenance and structural features can detect prompt-injection hijacking before tool execution—remains **unproven**. Because no authentic positive hijacking events occurred ($N_{\text{pos}} = 0$), the detector's discriminative ability cannot be empirically demonstrated.

2. **Does NOT Prove General LLM Resistance to Prompt Injection:**
   - The absence of positive cases in this study cannot be generalized to claim that instruction-tuned language models are inherently safe or immune to prompt injection.
   - Resistance was observed only under specific pinned configurations: AgentDojo `v1` workspace tasks, simple out-of-the-box attack strategies (`injecagent`, `direct`, `system_message`), and local quantized open-weight models (3B to 12B). Adaptive, multi-step, or jailbreak-enhanced attacks on larger frontier models may succeed where these configurations did not.

3. **Does NOT Establish a Population FAR $\le 5\%$:**
   - The total benign sample across all historical phases is $N = 28$ ($N=12$ in historical canonical development), which is statistically insufficient to prove a population upper bound of 5% (requiring $N \ge 59$).
   - One historical benign trajectory triggered an alert under provenance baselines (an 8.3% sample false alarm rate in the initial development split).

4. **Does NOT Provide Meaningful Supervised Detection Metrics:**
   - Positive-class metrics—including Sensitivity, Recall, Precision, F1-Score, ROC-AUC, and Precision-Recall AUC—are mathematically undefined or uninformative when the true positive denominator is zero.
   - Fabricating synthetic positive examples to compute artificial ROC curves is strictly prohibited by scientific integrity standards.

---

## 3. Methodological and Experimental Limitations

### 3.1 Benchmark & Attack Constraints
- **Pinned Benchmark:** All experiments were conducted using `agentdojo==0.1.35`, suite `v1`, workspace environment. Outcomes may differ on other suites (e.g. `slack`, `banking`) or more recent benchmark releases.
- **Fixed Attack Templates:** Attacks relied on standard AgentDojo injected payloads (e.g. instructing the agent to email `mark.black-2134@gmail.com` or delete files). Adaptive adversarial optimization (e.g. GCG, automated jailbreak rewriting, or semantic obfuscation) was not evaluated.

### 3.2 Model Scale and Quantization
- **Model Scope:** Limited to locally runnable open-weight models: `qwen2.5:3b` (Q4_K_M), `llama3.2:3b` (Q4_K_M), and `mistral-nemo:12b-instruct-2407-q4_K_M`.
- **Quantization Effects:** 4-bit quantization may affect instruction-following fidelity or safety alignment, though both 3B and 12B models exhibited identical zero-hijacking behavior.

### 3.3 Task Complexity and Post-Exposure Opportunities
- **Truncated Chains:** In 21 of the 28 exposed runs (75.0%), the agent terminated immediately after receiving the observation containing the injection payload (e.g. by printing the calendar summary to the user), leaving no subsequent tool-call decision step. Only 7 trajectories across the entire repository contained a genuine post-exposure tool-call decision opportunity.
- **Benign Utility Ceilings:** The models achieved 39.3% benign utility across all tasks. When an agent cannot reliably solve complex multi-turn benign tasks (e.g. `user_task_4` utility was 14.3%), its failure to execute a multi-step attack may reflect task-execution limitations rather than intentional injection defense.

---

## 4. Locked Readiness Protocol Status

Under the locked evaluation protocol (`docs/LOCKED_EVALUATION_PROTOCOL.md`), the formal status flags remain locked:

- `CANONICAL_MULTIMODEL_CORPUS_VALIDATED`: **True**
- `EXPOSURE_TIMING_VALIDATED`: **True**
- `MULTIMODEL_FEATURE_EXTRACTION_VALIDATED`: **True**
- `EVALUATION_PROTOCOL_LOCKED`: **True**
- `POPULATION_FAR_5_PERCENT_ESTABLISHED`: **False** ($N=28 < 59$; 1 sample alert observed in development)
- `POSITIVE_CLASS_DETECTION_EVALUATION_READY`: **False** ($N_{\text{pos}} = 0$; positive evaluation strictly blocked)
- `RESEARCH_HYPOTHESIS_VALIDATED`: **False** (Hypothesis unproven due to absent authentic positive cases)
