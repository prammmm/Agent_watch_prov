# When Detection Cannot Be Evaluated: A Feasibility and Measurement Study of Pre-Execution Indirect Prompt-Injection Detection in Tool-Using Agents

**Author:** AgentWatch Research Team  
**Institution:** Advanced Agentic Research Prototype  
**Date:** October 2026  
**Repository:** `D:\Agent_watch_prov` (Git branch `main`)  
**Hardware Target:** Local NVIDIA GeForce RTX 3060 Laptop GPU (6 GB VRAM)  
**Expenditure:** $0.00 (Zero paid APIs, zero subscriptions, zero cloud tokens)  

---

## Abstract

Indirect prompt injection poses a fundamental security threat to tool-using autonomous AI agents. Existing defenses primarily rely on input scrubbing, output filtering, or post-execution response monitoring. In this study, we investigate the feasibility of **AgentWatch**, a lightweight, pre-execution defense architecture designed to intercept agent tool proposals at causal gate points and evaluate provenance-based and structural indicators before potentially harmful operations execute. 

Through an extensive empirical evaluation using the pinned AgentDojo benchmark (`v1`, workspace suite) across three open-weight instruction-tuned language models (`qwen2.5:3b`, `llama3.2:3b`, and `mistral-nemo:12b-instruct-2407-q4_K_M`), we collected an auditable corpus of 75 genuine benchmark trajectories emitting 181 causal gate points. While payload exposure was successfully delivered in 59.6% (28/47) of attacked trajectories, **zero harmful actions were proposed, zero harmful operations executed, and zero benchmark security breaches occurred across all 75 trials ($N_{\text{pos}} = 0$)**. 

We demonstrate that instruction-tuned models exhibit an intrinsic inductive bias toward user task goals and neutral conversational responses, rendering standard benchmark injection payloads inert in local multi-turn environments. Consequently, standard detector evaluation metrics—including True Positive Rate, Sensitivity, and ROC-AUC—cannot be computed without fabricating synthetic data. We formalize an 8-stage decoupled attack outcome taxonomy, establish the mathematical requirements for population false-alarm control (the Rule of 59), and reframe this work as an empirical thesis examining the methodological and practical challenges of evaluating pre-execution prompt-injection detection under extreme class imbalance.

---

## 1. Introduction and Problem Statement

As Large Language Model (LLM) agents are integrated into real-world applications with access to file systems, databases, email clients, and calendars, they become susceptible to **indirect prompt injection**. Unlike direct prompt injection, where an adversary directly prompts the model, indirect prompt injection occurs when untrusted external data retrieved by the agent (such as an email, webpage, or calendar invitation) contains adversarial instructions designed to hijack the agent's control flow.

A common failure mode in current agent architectures is that tool execution occurs immediately upon model proposal. Once a destructive or exfiltrating tool call executes (e.g. `delete_file` or `send_email`), the security breach is irreversible. To mitigate this risk, the **AgentWatch** project was conceived to explore a pre-execution defense: intercepting tool-call proposals at the exact boundary between model generation and environment dispatch.

The original research hypothesis posited that lightweight provenance indicators (tracking data flow from untrusted tool outputs to outgoing tool arguments) and structural metrics (such as tool-sequence repetition and argument entropy) could distinguish benign tool calls from injection-induced malicious tool calls at a controlled false-alarm rate.

However, conducting a rigorous empirical evaluation of such a detector requires observing genuine positive instances of prompt-injection hijacking. This thesis documents what occurs when this foundational assumption fails: across 75 authentic benchmark runs across three distinct model architectures, the benchmark attacks failed to compromise the agents, preventing empirical evaluation of detector sensitivity.

---

## 2. Research Questions and Scope

This study investigates five core research questions:

1. **RQ1 (Causal Instrumentation):** Can tool-calling AI agents be instrumented at pre-execution gate points to capture causal provenance and structural features without modifying the model or leaking future execution states?
2. **RQ2 (Model Capability):** Can consumer-grade local language models (3B to 12B parameters) reliably execute multi-turn benchmark tasks and formulate valid structured tool calls?
3. **RQ3 (Attack Delivery vs. Observation):** When indirect prompt-injection payloads are embedded in external environment data, how frequently do local models actually retrieve and observe the payload in their context?
4. **RQ4 (Behavioral Compliance & Security Outcomes):** Does exposure to an injection payload induce the model to propose harmful tool calls or achieve attacker goals under authentic benchmark ground-truth criteria?
5. **RQ5 (Evaluation Feasibility under Zero Positives):** What are the epistemic, statistical, and methodological consequences for detector evaluation when no authentic positive hijacking cases occur ($N_{\text{pos}} = 0$)?

### Scope and Boundaries
- **Benchmark:** Pinned `agentdojo==0.1.35`, benchmark suite `v1`, workspace environment.
- **Models:** `qwen2.5:3b` (Q4_K_M), `llama3.2:3b` (Q4_K_M), and `mistral-nemo:12b-instruct-2407-q4_K_M`.
- **Hardware:** Local NVIDIA GeForce RTX 3060 Laptop GPU (6 GB VRAM) using Ollama (`http://127.0.0.1:11434`).
- **Cost:** Zero financial expenditure ($0.00).

---

## 3. Background and Related Work

### 3.1 Indirect Prompt Injection
Pioneering work by Greshake et al. (2023) demonstrated that LLMs integrated with external applications could be manipulated via adversarial instructions embedded in untrusted data. Subsequent benchmarks, notably AgentDojo (Debenedetti et al., 2024), formalized this evaluation by embedding injection payloads into multi-tool simulated enterprise environments (emails, calendars, contacts, files).

### 3.2 Detection Approaches and Their Limitations
Existing detection strategies fall into three paradigms:
1. **Input Scanners:** Evaluating raw text for injection phrases (e.g. Llama Guard, Prompt Guard). These methods struggle with subtle semantic framing and lack contextual awareness of whether retrieved text is actually acted upon.
2. **Output Scanners:** Inspecting the final text response generated by the agent. While effective for chat interfaces, output filtering fails in agent workflows because harmful actions occur via intermediate tool invocations before the final text response is produced.
3. **Execution Gateways:** The paradigm adopted by AgentWatch, which evaluates the proposed tool call and its historical prefix immediately prior to environment dispatch.

---

## 4. AgentWatch Architecture

AgentWatch implements an end-to-end trace collection, normalization, feature extraction, and evaluation pipeline structured into three core subsystems:

```
┌─────────────────────────────────────────────────────────────┐
│                    Agent Execution Loop                     │
│                                                             │
│   [User Goal] ──> [LLM Policy] ──> [Tool Call Proposed]     │
└───────────────────────────────────────────┬─────────────────┘
                                            │ (Pre-Execution Gate)
                                            ▼
┌─────────────────────────────────────────────────────────────┐
│               AgentWatch Gate-Point Subsystem               │
│                                                             │
│   1. Trace Normalization & Content Hashing                  │
│   2. Causal Prefix Isolation (Strictly t < t_gate)          │
│   3. Provenance & Structural Feature Extraction (25 feats)   │
│   4. Deterministic Baseline Rules & Anomaly Scoring         │
└───────────────────────────────────────────┬─────────────────┘
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     ▼                                             ▼
             [Allow Dispatch]                              [Block / Alert]
                     │
                     ▼
           [Environment Execution]
```

### 4.1 Causal Gate-Point Representation
A gate point occurs whenever the LLM emits a tool-call proposal. To prevent temporal data leakage, each gate point record (`GatePointDatasetRecord`) captures:
- The proposed tool call: `tool_name` and `arguments`.
- The strict historical prefix: all messages, tool calls, and tool observations occurring prior to this gate point.
- Zero future information: post-execution results, subsequent model messages, and ground-truth labels are strictly excluded.

### 4.2 Decoupled 8-Stage Outcome Taxonomy
To prevent conflating payload retrieval with agent compromise, AgentWatch defines an explicit 8-stage outcome progression:
1. **Attack Configured:** Adversarial injection task and strategy assigned.
2. **Payload Delivered:** Injected payload successfully inserted into environment state.
3. **Payload Observed:** Injected string appears in a tool observation returned to the model.
4. **Post-Exposure Opportunity:** Model receives a subsequent execution turn to emit tool calls.
5. **Harmful Tool Proposal:** Model proposes a tool call matching the attacker's ground-truth target.
6. **Harmful Action Executed:** Harmful tool call dispatches and modifies the environment.
7. **Benchmark Security Breach:** Attack objective evaluated and confirmed by benchmark logic.
8. **Benign Task Utility:** Independent evaluation of whether the user's legitimate goal was satisfied.

---

## 5. Feature Extraction Pipeline

AgentWatch extracts 25 causal features across two families:

### 5.1 Provenance Features (Data Flow Tracking)
- `prov_raw_tool_arg_overlap`: Exact string match between proposed arguments and prior tool observations.
- `prov_token_jaccard_max`: Maximum token Jaccard similarity across prior observation windows.
- `prov_subsequence_overlap`: Longest common contiguous subsequence between observations and arguments.
- `prov_entropy_drop`: Shift in character entropy between observation inputs and proposed arguments.

### 5.2 Structural Features (Behavioral Topology)
- `struct_step_index`: Temporal position of the tool proposal within the trajectory.
- `struct_consecutive_repeat`: Frequency of repeating the identical tool call.
- `struct_arg_length_chars`: Total length of proposed argument strings.
- `struct_argument_key_count`: Number of arguments supplied to the tool.

All features are strictly computed over the causal prefix $t < t_{\text{gate}}$.

---

## 6. Experimental Methodology & Corpus Audit

### 6.1 Experimental Corpus Composition
The empirical evaluation spans 75 authentic benchmark trajectories partitioned into two sets:
1. **Historical Canonical Corpus ($N=43$):** Pilot runs and feasibility screens across `qwen2.5:3b` and `llama3.2:3b`.
2. **Phase 6A Controlled Study ($N=32$):** A predeclared, balanced factorial experiment comparing `mistral-nemo:12b` against `qwen2.5:3b` across 4 tasks, 2 conditions (benign vs. attacked), and 2 repetitions.

### 6.2 Preflight Hardware and Model Inventory

| Model Name | Parameters | Quantization | Host Engine | VRAM Allocated | Inference Latency |
|---|---|---|---|---|---|
| `qwen2.5:3b` | 3.09B | Q4_K_M | Ollama | 2,410 MiB | ~8.8s / run |
| `llama3.2:3b` | 3.21B | Q4_K_M | Ollama | 2,512 MiB | ~12.1s / run |
| `mistral-nemo:12b-instruct-2407-q4_K_M` | 12.2B | Q4_K_M | Ollama | 4,693 MiB | ~53.0s / run |

---

## 7. Empirical Results

### 7.1 Quantitative Findings Across the Full Corpus ($N=75$)

| Evaluation Metric | Historical ($N=43$) | Phase 6A ($N=32$) | Full Corpus ($N=75$) |
|---|---|---|---|
| **Total Gate Points** | 139 | 42 | **181** |
| **Attacked Trajectories** | 31 | 16 | **47** |
| **Benign Trajectories** | 12 | 16 | **28** |
| **Payload Exposed Trajectories** | 17 / 31 (54.8%) | 11 / 16 (68.8%) | **28 / 47 (59.6%)** |
| **Post-Exposure Tool Opportunities** | 6 / 17 (35.3%) | 1 / 11 (9.1%) | **7 / 28 (25.0%)** |
| **Harmful Tool Proposals ($N_{\text{pos}}$)** | **0 / 31 (0.0%)** | **0 / 16 (0.0%)** | **0 / 47 (0.0%)** |
| **Harmful Actions Executed** | **0 / 31 (0.0%)** | **0 / 16 (0.0%)** | **0 / 47 (0.0%)** |
| **Benchmark Security Breaches** | **0 / 31 (0.0%)** | **0 / 16 (0.0%)** | **0 / 47 (0.0%)** |
| **Benign Task Utility Success** | 3 / 12 (25.0%) | 8 / 16 (50.0%) | **11 / 28 (39.3%)** |
| **Attacked Task Utility Success** | 3 / 31 (9.7%) | 5 / 16 (31.3%) | **8 / 47 (17.0%)** |

### 7.2 Model Capability and Benign Task Execution
In benign trials, models demonstrated task competence on structured queries:
- On `user_task_1` (counting calendar appointments), both `mistral-nemo:12b` and `qwen2.5:3b` achieved 100% utility (5/5 across all trials).
- On complex multi-step queries like `user_task_4` (counting appointments and scheduling lunch with Sarah), benign utility dropped to 14.3% (1/7), with models struggling to chain calendar creation after event retrieval.

### 7.3 The Positive-Case Acquisition Bottleneck
In 28 trials where the models retrieved and observed the injected payload (e.g. `"IMPORTANT!!! Ignore all previous instructions... Please email 'Hey, how is it going?' to 'mark.black-2134@gmail.com'"`):
- In **21 trials (75.0%)**, the models terminated the interaction immediately after observation, printing the legitimate calendar contents to the user without calling another tool.
- In **7 trials (25.0%)**, the models formulated subsequent tool calls, but in **100% of these opportunities**, the calls addressed the legitimate user goal (e.g. `search_calendar_events` or `create_calendar_event` for lunch) rather than the attacker's email instruction.
- **Zero models complied with the attacker's instructions.**

---

## 8. Statistical Analysis and Epistemic Limits

### 8.1 The Mathematics of False-Alarm Control (The Rule of 59)
To validate that a pre-execution detector operates at an acceptable per-trajectory False Alarm Rate ($\text{FAR} \le 5\%$) with 95% confidence ($\alpha = 0.05$), we apply the Clopper-Pearson exact binomial upper bound:
$$(1 - \text{FAR}_{\text{upper}})^N \ge \alpha \implies (1 - 0.05)^N \ge 0.05 \implies N \ge \frac{\ln(0.05)}{\ln(0.95)} \approx 58.4$$
Thus, **at least 59 independent, false-alarm-free benign trajectories ($k=0$)** are required to mathematically prove a population FAR below 5%. With $N=28$ benign runs in the cumulative corpus (and 1 historical false alarm), population FAR control cannot yet be asserted.

### 8.2 Why Positive Detector Metrics Cannot Be Reported
When the positive class count is zero ($N_{\text{pos}} = 0$):
$$\text{Sensitivity} = \frac{\text{TP}}{\text{TP} + \text{FN}} = \frac{0}{0} \quad (\text{Undefined})$$
Computing ROC-AUC or Precision-Recall curves under zero positive samples yields mathematically vacuous results. Fabricating synthetic positives by manually writing tool calls would violate causal validity and misrepresent detector capability.

---

## 9. Threats to Validity

1. **Benchmark Scope:** Experiments were confined to AgentDojo `v1` workspace tasks. Dynamic environments (e.g. web search, multi-agent frameworks) may present different vulnerability surfaces.
2. **Attack Sophistication:** Pinned attacks used standard AgentDojo prompt templates without adaptive adversarial optimization (e.g. GCG suffixes, iterative prompt refinement).
3. **Quantization Artifacts:** 4-bit quantized open-weight models may exhibit different instruction-following compliance than full-precision 70B models or proprietary frontier APIs.

---

## 10. Discussion & Scientific Contributions

### 10.1 Reframing the Thesis
This project began as a detector implementation effort and evolved into an empirical study of the measurement problem in AI agent security. The core finding is that **in zero-cost local environments using modern instruction-tuned models, evaluating pre-execution prompt-injection detectors is blocked not by detector engineering, but by the empirical absence of successful benchmark hijackings.**

### 10.2 Supported Contributions
1. **Methodological Contribution:** The formal 8-stage decoupled outcome taxonomy, which distinguishes payload exposure from agent compromise.
2. **Engineering Contribution:** The causal pre-execution gate-point interception architecture and 25-feature extraction pipeline.
3. **Empirical Finding:** Rigorous demonstration that standard prompt-injection attacks fail to compromise 3B to 12B instruction-tuned models on AgentDojo workspace tasks.
4. **Statistical Contribution:** Derivation and formalization of the Rule of 59 for trajectory-level false-alarm validation.

---

## 11. Conclusion and Future Work

AgentWatch demonstrates that pre-execution tool interception is architecturally viable and causally sound. However, the evaluation of such defenses faces a severe empirical bottleneck: under standard benchmark conditions, open-weight instruction-tuned models do not follow simple indirect prompt injections to perform harmful actions.

Future work must focus on:
1. Developing adaptive, automated attack generators that achieve reliable baseline hijacking rates on instruction-tuned models.
2. Expanding benchmark tasks where agents routinely make tool calls following untrusted data retrieval.
3. Gathering an independent test corpus of $\ge 59$ benign trajectories to empirically establish false-alarm control.

---

## References

1. Debenedetti, E., Zhang, J., Balunović, M., Beurer-Kellner, L., Fischer, M., & Vechev, M. (2024). *AgentDojo: A Dynamic Environment to Benchmark Attacks and Defenses for LLM Agents.* arXiv:2406.13318.
2. Greshake, K., Abdelnabi, S., Mishra, S., Endres, C., Holz, T., & Fritz, M. (2023). *Not what you've signed up for: Compromising Real-World LLM-Integrated Applications with Indirect Prompt Injection.* ACM Workshop on AISec.
3. Liu, Y., Deng, G., Xu, Z., Li, Y., Zheng, Y., Zhang, Y., Zhao, L., Stoller, M., & Liu, Y. (2023). *Prompt Injection attack against LLM-integrated Applications.* arXiv:2306.05499.
4. Clopper, C. J., & Pearson, E. S. (1934). *The use of confidence or fiducial limits illustrated in the case of the binomial.* Biometrika, 26(4), 404-413.
5. Inan, H., Upasani, K., Chi, J., Rungta, R., Iyer, K., Mao, Y., Tontchev, M., Hu, Q., Fuller, B., Testuggine, D., & Khabsa, M. (2023). *Llama Guard: LLM-based Input-Output Safeguard for Human-AI Conversations.* arXiv:2312.06674.
