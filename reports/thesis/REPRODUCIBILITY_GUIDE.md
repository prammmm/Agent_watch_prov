# AgentWatch: Reproducibility Guide

**Document Version:** 1.0.0  
**Date:** 2026-10-12  
**Milestone:** Phase 6B Thesis Evidence Synthesis  
**Scope:** Complete Local Hardware, Software & Execution Blueprint  
**Repository Location:** `D:\Agent_watch_prov`  

This guide provides end-to-end instructions for reproducing the entire AgentWatch empirical experimental corpus, data processing pipeline, feature extraction, and automated regression test suite on local hardware under zero cloud expenditure ($0.00).

---

## 1. System Requirements & Hardware Specification

The experiment was designed and executed on a single consumer laptop without cloud compute or paid APIs:

| Component | Specification |
|---|---|
| **Operating System** | Microsoft Windows 11 Home / Pro (x86_64) |
| **Processor** | Intel Core i7 / AMD Ryzen (8+ physical cores recommended) |
| **System Memory (RAM)** | 16 GB DDR4 / DDR5 minimum |
| **GPU Hardware** | NVIDIA GeForce RTX 3060 Laptop GPU (6,144 MiB / 6 GB GDDR6 VRAM) |
| **CUDA Driver** | NVIDIA Driver Version 616.92 |
| **CUDA Capability** | Compute Capability 8.6 |
| **Storage Requirement** | ~20 GB free space on local SSD (for Ollama model blobs and raw traces) |

---

## 2. Software Environment & Pinned Dependencies

### 2.1 Python Environment
- Python Version: **Python 3.11** (`C:\Users\Param\AppData\Local\Programs\Python\Python311\python.exe`)
- Virtual Environment / PYTHONPATH: `src/` and repository root added to `PYTHONPATH`.

### 2.2 Pinned Package Dependencies
Key library versions pinned in `pyproject.toml` and `requirements.txt`:

```text
agentdojo==0.1.35
pydantic>=2.0.0
openai>=1.0.0
numpy>=1.24.0
scikit-learn>=1.3.0
pandas>=2.0.0
torch==2.7.1+cu118
```

### 2.3 Local Model Inference Server (Ollama)
Local models are hosted via the open-source Ollama runtime:
- Storage path: `D:\ollama_models`
- Ollama Server Command:
  ```powershell
  $env:OLLAMA_MODELS="D:\ollama_models"
  ollama serve
  ```
- Endpoint: `http://127.0.0.1:11434` (OpenAI-compatible `/v1` endpoint enabled)

### 2.4 Model Pull & Digests
Pull the three exact model configurations tested:
```bash
ollama pull qwen2.5:3b
ollama pull llama3.2:3b
ollama pull mistral-nemo:12b-instruct-2407-q4_K_M
```

Verified SHA-256 model manifest IDs:
- `mistral-nemo:12b-instruct-2407-q4_K_M`: `daf673741712` (7.5 GB, 22/41 GPU layers offloaded, 4,693 MiB VRAM)
- `qwen2.5:3b`: `d7202dd941db` (1.9 GB, 100% GPU offload, 2,410 MiB VRAM)
- `llama3.2:3b`: `a80c4f17acd5` (2.0 GB, 100% GPU offload, 2,512 MiB VRAM)

---

## 3. Directory Layout

The repository is structured to separate raw traces, normalized features, and decoupled ground-truth labels:

```
D:\Agent_watch_prov\
├── data\
│   ├── pilot_runs\               # Phase 2 pilot calibration runs (10 runs)
│   ├── collection_study\         # Phase 3 attack collection screen (4 runs)
│   ├── phase4a_collection\       # Phase 4A coverage audit runs (7 runs)
│   ├── phase5b_collection\       # Phase 5B targeted acquisition runs (14 runs)
│   ├── phase5c_collection\       # Phase 5C alternative model runs (8 runs)
│   ├── phase6a_collection\       # Phase 6A controlled 32-run study (32 runs)
│   │   ├── raw\                  # Full multi-turn execution traces
│   │   ├── labels\               # Decoupled 8-stage ground-truth outcome records
│   │   └── manifests\            # Predeclared manifest and execution summary
│   └── derived_datasets\         # Canonical multimodal datasets (v1 and v2)
├── src\
│   └── agentwatch\
│       ├── benchmark\            # AgentDojo pilot harness and ground-truth matcher
│       ├── features\             # 25-feature causal extractor (v1 and v2)
│       ├── traces\               # Raw schema, normalizer, and integrity checks
│       └── utils\                # Hardware device and logging utilities
├── tests\
│   ├── unit\                     # 77 unit tests covering schema, features, matcher
│   └── integration\              # 1 integration test validating AgentDojo harness
├── scripts\                      # Audit and experiment runners
└── reports\
    ├── thesis\                   # Thesis synthesis and evidence ledgers
    └── build_reports\            # Phase 0 through Phase 6B engineering build reports
```

---

## 4. Execution & Replication Commands

### 4.1 Running the Automated Test Suite (78 Tests)
Execute all unit and integration tests:
```powershell
$env:PYTHONPATH="D:\Agent_watch_prov\src;D:\Agent_watch_prov"
C:\Users\Param\AppData\Local\Programs\Python\Python311\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
Expected result: `Ran 78 tests in ~6s, OK`.

### 4.2 Recomputing All Corpus Statistics Directly from Primary Records
Audit all 75 raw traces and decoupled labels:
```powershell
$env:PYTHONPATH="D:\Agent_watch_prov\src;D:\Agent_watch_prov"
C:\Users\Param\AppData\Local\Programs\Python\Python311\python.exe scripts/audit_corpus_evidence.py
```

### 4.3 Auditing Post-Exposure Chronology
Audit exposure steps and verify post-exposure tool call occurrences:
```powershell
$env:PYTHONPATH="D:\Agent_watch_prov\src;D:\Agent_watch_prov"
C:\Users\Param\AppData\Local\Programs\Python\Python311\python.exe scripts/audit_post_exposure_events.py
```

### 4.4 Re-running the Controlled Phase 6A Experiment
To execute the 32-run controlled study matrix:
```powershell
$env:PYTHONPATH="D:\Agent_watch_prov\src;D:\Agent_watch_prov"
C:\Users\Param\AppData\Local\Programs\Python\Python311\python.exe scripts/run_phase6a_experiment.py
```
*Note: Requires Ollama running locally. Re-running will verify existing records or generate fresh runs if raw files are cleared.*
