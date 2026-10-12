# AgentDojo Integration Feasibility Assessment

**Document Version:** 1.0  
**Date:** 2026-10-11  
**Project:** AgentWatch (Phase 0, Part 0.3)  
**Primary Repository:** [ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo)  
**Documentation:** [agentdojo.spylab.ai](https://agentdojo.spylab.ai)  

---

## 1. Executive Summary

This feasibility assessment examines the primary source code, package distributions, execution interfaces, and benchmark contracts of **AgentDojo** for integration into **AgentWatch**.

AgentWatch requires:
1. Recording genuine agent executions (messages, tool calls, tool results, outcomes).
2. Constructing causal pre-execution gate points `(prefix, proposed_tool_call)` before any proposed tool call is executed.
3. Distinguishing ground-truth security and utility outcomes from detector inputs.
4. Investigating the feasibility and timing of identifying the first harmful tool action (`t_harm`).

---

## 2. Versioning & Package Specifications

- **Package Name:** `agentdojo` (PyPI: [pypi.org/project/agentdojo](https://pypi.org/project/agentdojo/))
- **Latest PyPI Package Version:** `0.1.35`
- **Benchmark Version Distinction:**
  - *Package Version:* `0.1.35` (defines the framework runtime, CLI, task loaders, and defenses).
  - *Benchmark Suite Version:* `v1` (and incremental updates `v1.1`, `v1.2.x`, `v1.3`). Suites are organized under `src/agentdojo/default_suites/v1/` (e.g. `workspace`, `slack`, `travel`, `banking`).
  - *Decision:* Pin package version `agentdojo==0.1.35` and benchmark suite `v1` explicitly in manifests.
- **Python Compatibility:**
  - PyPI metadata specifies `requires-python = ">=3.10"`.
  - Python 3.11 is fully supported and matches our verified GPU environment (`PyTorch 2.7.1+cu118`).
- **License:** MIT License (confirmed in upstream repository).
- **Core Dependencies:**
  - `pydantic[email]>=2.7.1`, `deepdiff>=8.6.1`, `rich>=13.7.1`, `tenacity>=8.2.3`, `pyyaml>=6.0.1`.
  - Model providers: `anthropic>=0.47.0`, `openai>=1.59.7`, `google-genai>=1.15.0`, `cohere>=5.3.4`.

---

## 3. Architecture & Execution Harness

### 3.1 Pipeline Structure
In AgentDojo, an agent is constructed as an `AgentPipeline` composed of `BasePipelineElement` stages:
```python
class BasePipelineElement(abc.ABC):
    @abc.abstractmethod
    def query(
        self,
        query: str,
        runtime: FunctionsRuntime,
        env: Env = EmptyEnv(),
        messages: Sequence[ChatMessage] = [],
        extra_args: dict = {},
    ) -> tuple[str, FunctionsRuntime, Env, Sequence[ChatMessage], dict]:
        ...
```
Typical elements in an execution pipeline:
- `InitQuery`: Injects the initial user task prompt into `messages`.
- `SystemMessage`: Inserts system instructions and tool definitions.
- `LLM`: Subclasses like `OpenAILLM`, `AnthropicLLM`, `GoogleLLM` query the model and produce assistant tool-call messages.
- `ToolsExecutionLoop`: Loops between the LLM and `ToolsExecutor` until the model generates a final non-tool response or reaches a step limit.
- `ToolsExecutor`: Dispatches proposed tool calls to `FunctionsRuntime` and appends `ChatToolResultMessage` to `messages`.

### 3.2 Available Hooks for Pre-Execution Causal Gate Points
In standard AgentDojo:
- `ToolsExecutor` takes `messages[-1]` (which is a `ChatAssistantMessage` containing `tool_calls`) and executes them immediately on `FunctionsRuntime`.
- **Causal Gate-Point Hook:** AgentDojo's pipeline architecture is explicitly designed to support custom elements inheriting from `BasePipelineElement`. We can wrap or subclass `ToolsExecutor` or insert a gatekeeper element into `ToolsExecutionLoop` immediately preceding `ToolsExecutor`:
  $$\text{GatePoint} = (\text{messages}_{< t}, \text{proposed\_tool\_call}_t)$$
  This guarantees that:
  1. The detector receives only the interaction history strictly before the tool call.
  2. The tool execution result (which does not exist yet) and future observations cannot leak into the detector.

---

## 4. Benchmark Tasks & Ground-Truth Mechanisms

### 4.1 Task Suites
AgentDojo provides 4 standard suites under `v1`:
1. `workspace`: Productivity environment (email client, calendar, Google Drive/files).
2. `slack`: Team messaging environment.
3. `travel`: Travel booking, flight, and hotel reservation environment.
4. `banking`: E-banking transactions and account management.

Each suite contains:
- `user_tasks`: Tasks defining standard utility objectives (e.g. "Send an email to Bob summarizing today's meetings").
- `injection_tasks`: Adversarial objectives inserted via injection vectors in untrusted data (e.g. "Exfiltrate password to attacker URL", "Transfer money to account X").

### 4.2 Utility & Security Evaluation
- **Utility:** Evaluated via `user_task.utility(env, messages) -> bool`. Checks whether the user's intended task was completed in the environment state.
- **Security:** Evaluated via `injection_task.security(env, messages) -> bool`. Checks whether the attacker's objective was achieved in the environment state.
- **Ground Truth Pipeline (`GroundTruthPipeline`):** AgentDojo executes tasks without attacks to determine the expected reference trajectory and candidate injection points that the agent will actually observe during legitimate execution.

---

## 5. Exposure, Outcome Labeling, and `t_harm` Analysis

### 5.1 Exposure Labeling
- **Definition:** Did untrusted injected text appear in an observation (tool result) received by the agent?
- **Ground Truth:** Injected strings are injected via placeholders or specific data fields. However, simple substring matching of injection text has limitations:
  1. Tools may truncate, paginate, or reformat text (e.g. JSON escaping, HTML strip).
  2. The LLM may observe a tool result containing the injection without attending to or acting on it.
- **AgentWatch Protocol:** Track explicit provenance from the tool return value: record the exact tool output string returned by `FunctionsRuntime`, and mark exposure when the injected payload (or known signature key) appears within that output.

### 5.2 Outcome Distinction
We can rigorously distinguish 4 states:
1. **Benign Success:** Utility = True, Security = N/A (no injection present).
2. **Benign Failure:** Utility = False, Security = N/A (agent failed normal task).
3. **Robust Defense / Ignored Injection:** Attacked run; Injection Exposed = True, but Security = False (adversarial goal not achieved).
4. **Successful Hijacking:** Attacked run; Security = True (adversarial goal achieved).

### 5.3 Harmful-Action Timing (`t_harm`) Feasibility
Can we determine the exact step $t_{\text{harm}}$ of the first harmful action?
- **Benchmark Reality:** AgentDojo's standard `injection_task.security(env, messages)` is evaluated *once at the end of the entire run* on the final environment state. It does **not** natively emit an action-level timestamp or step index $t_{\text{harm}}$.
- **Replay Feasibility Investigation:**
  - Because AgentDojo environments are Python state machines (`FunctionsRuntime` with mock databases/APIs), we can re-evaluate `injection_task.security(env_t, messages_{:t})` incrementally after each tool call.
  - *Determinism test:* Can we reproduce identical state transitions by replaying tool calls sequentially from step 1 to $k$? If the environment transitions deterministically without external network side-effects, the step $t$ where `security` flips from `False` to `True` is the true first harmful tool call $t_{\text{harm}}$.
  - *Precaution:* If an environment uses stochastic mocking or if an action is a precursor (e.g., reading a private file) rather than the terminal exploit (exfiltrating the file), $t_{\text{harm}}$ must be clearly defined (terminal security violation vs. unauthorized exfiltration action). We will not assume $t_{\text{harm}}$ exists until replaying and validating it deterministically in Phase 3.

---

## 6. Model Providers & Cost Policy for Pilot

- **Supported Providers:**
  - OpenAI (`gpt-4o-mini`, `gpt-4o`)
  - Anthropic (`claude-3-5-sonnet`, `claude-3-haiku`)
  - Google GenAI (`gemini-1.5-flash`, `gemini-1.5-pro`)
  - Cohere
  - Local / HuggingFace models (supported via pipeline elements or local API-compatible endpoints).
- **Pilot Strategy:**
  - For Phase 1 minimal pilot: Select a fast, low-cost model (e.g. `gpt-4o-mini` or `gemini-1.5-flash`) or local compatible endpoint.
  - Pilot size: 5 attacked tasks and 5 benign comparison tasks in the `workspace` suite.
  - Estimate: Total ~10-20 trajectories $\times$ ~5-10 turns $\approx$ 100K-200K tokens $\approx$ under $0.10 USD.
  - Redaction rule: API keys must always be loaded via environment variables (`OPENAI_API_KEY`, `GEMINI_API_KEY`) and never logged to disk or manifest files.

---

## 7. Known Benchmark Limitations & Published Findings

1. **Synthetic mock environments:** While benchmark tasks are realistic (calendar, email, banking), they operate on simulated Python data structures rather than live internet services.
2. **Deterministic vs. Adaptive attacks:** AgentDojo includes basic prompt injections and adaptive attacks. For the pilot, standard benchmark injections (`tool_knowledge` or baseline injection tasks) must be used.
3. **No native pre-execution interception hook:** Upstream benchmark runs agents end-to-end and checks security at the end. AgentWatch must introduce an instrumented execution wrapper around `ToolsExecutor` to capture causal gate points.

---

## 8. Summary of Integration Plan

| Component | Upstream Status | AgentWatch Strategy |
|---|---|---|
| **Package** | `agentdojo==0.1.35` on PyPI | Pin in project `pyproject.toml` / `requirements.txt`. |
| **Runtime** | Python >= 3.10 | Standardize on verified Python 3.11 with RTX 3060 CUDA support. |
| **Gate Point Hook** | Missing in upstream runner | Implement `InstrumentedToolsExecutor` inheriting from `BasePipelineElement`. |
| **Raw Trace Logging** | Upstream logs rich text tables | Implement `AgentWatchRawLogger` emitting append-only structured JSON records. |
| **Outcome Labels** | Provided at trajectory end | Capture native `utility` and `security` bools; link via opaque run ID. |
| **$t_{\text{harm}}$ Timing** | Not emitted directly | Investigate incremental environment replaying in Phase 3 before committing to $t_{\text{harm}}$. |

---

## 9. Primary Sources & References
- AgentDojo Repository: [https://github.com/ethz-spylab/agentdojo](https://github.com/ethz-spylab/agentdojo)
- AgentDojo Documentation: [https://agentdojo.spylab.ai](https://agentdojo.spylab.ai)
- PyPI Package: [https://pypi.org/project/agentdojo/](https://pypi.org/project/agentdojo/)
- Paper: "AgentDojo: A Dynamic Environment to Evaluate Attacks and Defenses on AI Agents" (Debenedetti et al., NeurIPS 2024 / arXiv:2406.13314).
