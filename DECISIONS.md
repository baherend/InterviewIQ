# InterviewIQ Decisions

Use new IDs in the form `ADR-YYYYMMDD-NNN`. Historical source/comments refer to D20–D110, but the original `decisions.md` is absent from the repository and Git history. Those legacy decisions may be described only as reconstructed invariants backed by current code, artifacts, or explicit user instructions.

## ADR-20260823-001 — External memory is the resume authority

- Status: active
- Decision: maintain the root memory/checkpoint files defined in `AGENT_RULES.md`, with `EXECUTION_STATE.json` as the exact resume pointer.
- Reason: the project spans long sessions and large multimodal context; chat history is not a reliable execution ledger.
- Consequence: every meaningful verified milestone receives an atomic external checkpoint and an exact next action.

## ADR-20260823-002 — Resume verified work instead of restarting

- Status: active
- Decision: skip completed verified steps unless explicit dependency-aware invalidation applies.
- Reason: repeated model runs are costly and may be nondeterministic; repetition also obscures which change caused an outcome.
- Consequence: checkpoints record verification and invalidation scope, not just completion.

## ADR-20260823-003 — Preserve independent modality evidence until Late Fusion

- Status: active
- Decision: Vision, acoustic Audio, ASR/Text, and document/reference processing remain independent until structured outputs are aligned and fused.
- Reason: preserve provenance, prevent modality contamination, and make disagreement/auditing possible.
- Consequence: a modality may affect fusion reliability but cannot rewrite another modality's observation.

## ADR-20260823-004 — Separate technical correctness from delivery confidence

- Status: active; reconstructed from current real Fusion code and master architecture instructions
- Decision: do not blend Answer Content Score, raw emotion-model confidence, and behavioral/delivery confidence into one opaque score by default.
- Reason: they represent different constructs with different evidence quality and calibration status.
- Consequence: the current real harness reports technical correctness separately; any future combined product score requires explicit requirements, validation data, calibration, and a new decision.

## ADR-20260823-005 — BGE selects relevant evidence; NLI classifies that relationship

- Status: active; reconstructed from explicit DA-017 task intent and current working-tree code
- Decision: BGE-M3 supplies relevance ranking for every non-empty reference document. NLI supplies entailment/neutral/contradiction for the selected relevant evidence. All probabilities used for one verdict must come from the same claim/chunk cell.
- Rejected: letting maximum NLI entailment choose relevance; independently taking entailment from one chunk and contradiction from another; DA-017-specific mappings; threshold hacks.
- Reason: DA-017 real diagnostics proved the old NLI-only selector chose semantically wrong JOIN chunks. Same-cell alignment preserves provenance and the prior D110 invariant.
- Consequence: `k` remains a compute cap, not a relevance threshold. The open NLI false contradiction is a downstream issue and must not be hidden by reverting retrieval.

## ADR-20260823-006 — Preserve current runtime-path distinctions until explicitly unified

- Status: active
- Decision: document the candidate path, real Fusion harness, and legacy mock endpoint separately; do not silently merge or relabel them during unrelated work.
- Reason: they differ in authentication, persistence, real/mock models, fusion formula, and report semantics.
- Consequence: unification requires its own task, migration/compatibility plan, security review, tests, and acceptance criteria.

## ADR-20260823-007 — Memory bootstrap makes no product-code changes

- Status: completed
- Decision: this bootstrap may create/review governance and memory files only.
- Reason: the user explicitly requested agreement on the operating model before the first implementation task.
- Consequence: all pre-existing source, data, artifacts, and dirty changes remain untouched.

## ADR-20260823-008 — Do not promote the CP-009 LoRA adapter

- Status: active
- Decision: retain `checkpoints/nli-lora-phase2c-v1` as experiment evidence only; do not attach or promote it in production.
- Evidence: CP-009 completed the one authorized configuration and achieved internal-dev macro F1 `1.0`, but frozen CP-005 remained `37/45`, false contradictions worsened `2→3`, DA-017 worsened `2/5→1/5`, and baseline-correct cases `NLI-EVAL-037` and `041` regressed. Only latency/memory and a subset of semantic gates passed.
- Rejected: promotion based on perfect internal dev; a second unapproved training run; CP-005-guided hyperparameter tuning; threshold changes that conceal false polarity.
- Reason: the held-out evidence fails the conjunctive acceptance contract and shows a generalization/data-authoring-template gap. Internal-dev performance is not sufficient production evidence.
- Consequence: production remains on the unchanged base. Any next phase begins with separately authorized analysis/design of corpus coverage and template shortcuts, not another automatic training run.

## ADR-20260829-009 — Build the backend from the repository root

- Status: active
- Decision: keep backend and AI source in their existing repository locations;
  use the repository root as Docker build context and copy them into
  `/app/backend` and `/app/InterviewIQ_AI` respectively.
- Rejected: duplicating `audio`/`fusion` under backend; retaining a backend-only
  context; copying local virtual environments or checkpoints into the image.
- Reason: backend configuration derives the repository root from
  `backend/app/config.py`, and multiple services import tracked AI packages.
  Preserving that layout is the smallest cross-machine architecture.
- Consequence: source imports and startup work in a clean image. Large model
  artifacts remain externally managed and missing models yield typed
  unavailable states instead of import-time crashes.
- Build-context boundary: the root context whitelists only `backend` and
  `InterviewIQ_AI`, then removes machine-local environments, secrets, caches,
  outputs, training/checkpoint work, archives, datasets in binary formats, and
  media. Compose container storage and PostgreSQL URLs are fixed to container
  semantics rather than inheriting native Windows/SQLite path values.
