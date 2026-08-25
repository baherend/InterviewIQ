# InterviewIQ Project Specification

Status: current architecture baseline; business requirements marked `NEEDS CONFIRMATION` remain open  
Baseline date: 2026-08-23

## 1. Identity and goal

- Project: InterviewIQ
- Domain: multimodal interview practice/assessment platform
- Current users visible in source: candidates/students, interviewers, organization administrators, and system administrators
- Inferred technical goal: collect one answer per persisted interview question and produce traceable technical-content and delivery evidence for reporting.
- Product success criteria, intended deployment environment, hiring/non-hiring use policy, latency budget, and cost budget: **NEEDS CONFIRMATION**.

## 2. Target architecture and invariants

The target architecture is modular Late Fusion:

```text
uploaded answer media
  -> modality-specific preprocessing
  -> independent Vision / acoustic Audio / ASR+Text pipelines
  -> structured evidence with provenance, timestamps, confidence, and sufficiency
  -> interview/question/segment plus temporal/entity alignment
  -> Late Fusion and explicit conflict handling
  -> reasoning, verification, persistence, and auditable report
```

The system must preserve modality independence, observation/interpretation separation, source provenance, missing-evidence states, and explicit conflicts. A canonical cross-modal evidence object is a target interface; it is not yet implemented consistently across the repository.

## 3. Actual runtime topology

### A. Current candidate path

`frontend/src/pages/InterviewRoom.jsx` records a fresh media segment for each server-persisted `InterviewQuestion`. `backend/app/routers/interviews.py` binds each upload to an `AnswerSegment`, validates the echoed question/index, and queues processing.

The current path performs and persists:

- real audio extraction and emotion classification;
- real Silero-VAD/faster-whisper ASR;
- deterministic vocal-delivery DSP;
- real transcript-based content scoring through Groq decomposition, glossary normalization, BGE-M3 retrieval, mDeBERTa NLI, and Precision/Coverage/Harmonic-F scoring;
- read-only Report/History rendering from persisted rows.

It does **not** currently run real Vision or real cross-modal Late Fusion, and it does not populate the legacy interview final score/verdict from the real per-question results.

### B. Standalone real multimodal Fusion harness

`frontend/src/pages/FusionTest.jsx` calls unauthenticated `GET /api/interviews/analysis-questions` and `POST /api/interviews/analyze`. The backend runs `InterviewIQ_AI/fusion/fusion_pipeline.py` out of process.

The same uploaded video fans out to independent real Vision, Audio, and NLP subprocesses. The harness writes filesystem artifacts and returns a cleaned response, but does not persist results to the database. It combines vocal-delivery and visual-behavioral scalar scores as delivery confidence; technical correctness remains separate and is gated for presentation by question/transcript lexical overlap.

### C. Legacy persisted mock path

`POST /api/interviews/analyze/{interview_id}` still calls random mock Vision/Audio/NLP modules, applies `0.35 / 0.30 / 0.35` fusion, and persists legacy `Result` plus interview score/verdict. No current frontend caller was found. This path must not be confused with the real harness or the current candidate path.

## 4. Modality pipelines

### Vision

- Source: `InterviewIQ_AI/vision/vision_module.py`
- Input: video frames/windows
- Runtime: OpenCV, MTCNN face detection, Swin-T + LoRA + TCN/temporal attention
- Evidence: window times/frame indices, face visibility, class probabilities, aggregate behavioral metrics, reliability, sufficiency, warnings, and checkpoint metadata
- Current use: standalone Fusion harness only
- Scientific status: experimental; not validated as a hiring-fitness measure

### Audio acoustics and delivery

- Sources: `InterviewIQ_AI/audio/audio_emotion_package/audio_module.py`, `InterviewIQ_AI/audio/audio_confidence.py`, `backend/app/services/audio_analysis_service.py`
- Emotion model: Arabic Wav2Vec2-XLSR + BiLSTM; maximum softmax is uncalibrated model certainty, not candidate performance
- Delivery DSP: speaking rate, pause control, volume stability, and speech continuity with sufficiency gating
- Current use: candidate path and Fusion harness

### ASR and text content

- Source: `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/src/interview_iq/pipeline.py`
- ASR: Silero VAD + faster-whisper `large-v3`, Arabic, CPU/int8 in current config
- Decomposition: external Groq chat model configured by environment; therefore the content pipeline is not fully local
- Retrieval: `BAAI/bge-m3`; every non-empty document is relevance-ranked in the current dirty working tree; `k=10` remains an NLI compute cap only for documents with more than ten chunks
- NLI: zero-shot base mDeBERTa by default; premise=reference chunk and hypothesis=claim for Precision
- Scoring: mean claim verdict score plus key-point Coverage through Harmonic F; negative Precision bypasses Coverage; score scale is 100
- Thresholds are explicitly pre-calibration defaults

### Documents and structured data

- Static scoring source: `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/refdocs/reference_docs_250_FINAL_v1.json` with 250 reference documents
- Candidate questions map through `Question.nlp_reference_id`; unmapped questions produce typed `NO_REFERENCE_DOCUMENT`, not a fabricated score
- Persistence: SQLAlchemy/Alembic models for `Interview`, `InterviewQuestion`, `AnswerSegment`, `AudioAnalysis`, `AnswerContentAnalysis`, and legacy `Result`
- Database implementation is environment-driven; Docker declares PostgreSQL while tests use SQLite. Active deployment topology is **UNKNOWN**.

## 5. Alignment and fusion

Verified structural alignment exists at user/interview/question/answer-segment/reference-document level. Candidate content scoring reuses the transcript persisted for the same segment and uses foreign-key reference mapping.

Missing alignment capabilities:

- no shared Vision-window/ASR-word cross-modal timeline join;
- no claim-to-word timestamp spans;
- no speaker diarization or audio-visual speaker association;
- no persistent face identity/track across frames;
- no entity-level conflict resolution beyond structural question/segment binding.

Real delivery confidence in `InterviewIQ_AI/fusion/confidence_fusion.py` uses nominal `0.60` vocal DSP and `0.40` visual behavioral weights, excludes insufficient modalities, and renormalizes the remainder. It does not fuse audio emotion confidence or technical score.

## 6. Interfaces and outputs

- Fusion raw JSON preserves preflight checks, component execution, raw component outputs, question/answer match, technical evaluation, visual/audio analysis, delivery confidence, warnings/errors, and artifact paths.
- Candidate database/report output preserves per-question audio/content analysis and aggregate summaries; reports do not rerun models.
- Absence or failure must remain explicit (`null`, typed status, reason, warning); never replace unavailable evidence with zero or a random value.

## 7. Runtime and operational constraints

- Local Windows runtime uses separate Python environments per modality plus ffmpeg.
- FastAPI `BackgroundTasks` is non-durable; a backend restart can strand processing until manual retry.
- The current Docker build does not package/mount the AI trees, dedicated environments, or checkpoints needed by the real pipelines.
- Nginx's shown proxy timeout is shorter than the Fusion process timeout.
- Model downloads/caches, external Groq availability, CPU latency, and local checkpoint availability affect reproducibility.
- Uploaded media, transcripts, reference documents, and model output are untrusted data and may contain sensitive information.

## 8. Verification requirements

Every substantial task must define task-specific acceptance criteria. At minimum, verification should distinguish:

- component unit tests vs mocked integration tests;
- real-model component runs vs real all-modality runs;
- modality quality vs fusion quality vs end-to-end product behavior;
- evidence-selection correctness vs downstream NLI/scoring correctness;
- current candidate path vs standalone harness vs legacy mock path.
