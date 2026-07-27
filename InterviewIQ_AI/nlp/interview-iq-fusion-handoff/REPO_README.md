# Interview IQ — NLP Module (Answer Correctness Evaluation)

**Version:** v1.0 — Phase 1 scaffold

## Overview

NLP module for the Interview IQ multi-modal technical interview evaluation system (Arabic).

**Single academic deliverable:** Answer Correctness Evaluation — scoring a candidate's answer against a per-question reference document.

**Scope:** 250 fixed questions across five tracks (DA, DS, CS, SE, GN), 50 per track.  
Each question has a Reference Document split into chunks (one fact per line, Modern Standard Arabic, technical terms in Latin script).

## Architecture

```
ASR → Claim Decomposition → BGE-M3 Top-k Chunk Cap → NLI (mDeBERTa LoRA) → Dual-Channel Scoring
```

See `PROJECT_EXECUTION_PLAN.md` for the full locked architecture and decision log.

## Key Constraints

- **Zero LLM at Runtime** — all inference is local (Decomposition + Embedding + NLI).
- **CPU-First development** — every CLI runs end-to-end on CPU with `tests/fixtures/` before any Kaggle GPU run.
- **Splits at Question-ID level** — never at the example level.
- **DS-014 (gold_set_48.json)** — evaluation only, never in any training premise pool.

## Repo Layout

```
configs/                YAML configs for every pipeline stage
data/                   Small local data only (large files → Kaggle Datasets)
src/interview_iq/       Main package
src/interview_iq/cli/   Entry-point scripts (python -m interview_iq.cli.run_*)
tests/                  pytest suite + CPU-friendly fixtures
kaggle/runners/         Thin Runner notebooks (clone + pip + one CLI line, zero logic)
```

## Usage

```bash
pip install -r requirements.txt
# Phase 3+: place data files per FILE_PLACEMENT.md, then:
python -m interview_iq.cli.validate_data
```

## Phases

See `PROJECT_EXECUTION_PLAN.md` §6 for the full 11-phase roadmap.

---

*Linguistic Confidence Module is permanently out of scope (D20).*
