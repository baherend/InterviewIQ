# InterviewIQ Known Issues

Only current, evidence-backed issues belong here. Historical audit findings are not imported without revalidation.

## KI-001 — Correct LEFT JOIN evidence is falsely contradicted by NLI

- Status: `LORA_FAILURE_DIAGNOSED_REMEDIATION_DESIGN_PENDING`
- Area: NLP Precision/NLI boundary
- Severity: high for Answer Content Score correctness
- Evidence: `test_videos/da017_after_fix/fusion_after.json` (EV-006), the exact real-model forensic replay/control matrix (EV-009), the frozen CP-005 dataset/baseline artifacts (EV-011/EV-012), the pinned Phase 2A checkpoint-control evaluation (EV-013/EV-014), Phase 2B preparation controls (EV-015/EV-016), CP-008 candidate-corpus/preflight evidence (EV-017/EV-018), CP-009 training/evaluation (EV-020/EV-021), and the CP-010 failure diagnosis/validation (EV-022/EV-023)
- Root-cause classification: **D — NLI model multilingual capability / model behavior**.
- Current fact: BGE correctly selects DA017-C02, but zero-shot mDeBERTa outputs E/N/C `0.000967 / 0.000717 / 0.998316` for the factually correct claim and marks it `CONTRADICTED`.
- Direct elimination: reference UTF-8/codepoint order is correct; production uses evidence as premise and claim as hypothesis; id2label/softmax/matrix mapping is correct; the pair has no truncation or UNK and preserves LEFT/JOIN; normalization is semantics-preserving for these strings.
- `Lift Join` is a verified upstream ASR/decomposition defect in the after artifact, but it is not the primary NLI cause. Replacing `Lift→LEFT` still yields `0.997247 C`; replaying the preserved earlier correctly recognized `left join` yields `0.981175 C`; symmetric reference normalization yields `0.996897 C`.
- Controls: exact/near-exact Arabic entailments, a direct Arabic contradiction, and monolingual English entailment/contradiction/neutral pairs classify correctly. The failure is phrase-sensitive on Arabic/code-switched SQL paraphrases and cross-language variants, which owns the false polarity at the model-behavior layer.
- CP-005 baseline: accuracy `37/45 = 0.822222`, macro F1 `0.818631`, false contradiction `2/15 = 13.3333%`, and false entailment `1/15 = 6.6667%`. Discovery-only accuracy is `35/40 = 87.5%`; the DA-017 anchors pass only `2/5` (`041 PASS`, `042 FAIL E→C`, `043 FAIL C→E`, `044 PASS`, `045 FAIL E→C`).
- CP-006 checkpoint control: pinned candidate `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7@b5113eb38ab63efdd7f280f8c144ea8b13f978ce` improves accuracy to `39/45 = 0.866667`, macro F1 to `0.866270`, and false entailment to `0/15`, but leaves false contradiction at `2/15 = 13.3333%` and DA-017 at `2/5`. It fixes three contradiction cases but regresses the correct INNER JOIN entailment `NLI-EVAL-041` from E to N. It therefore is a useful control, not a remediation winner; production remains unchanged.
- CP-007 preparation: a 600-example, balanced-label, question-split corpus specification and fail-closed CP-005 exclusion policy are frozen with a single targeted LoRA configuration, rollback, and predeclared CP-005/DA-017/slice/latency/Coverage gates. Zero examples and zero adapter checkpoints exist. The legacy training path is blocked until the reviewed corpus and stronger provenance/schema/leakage preflight exist.
- CP-008 data authoring: 600 deterministic candidates now exist from 50 non-protected reference question families, split 480/120 by complete question ID with exact CP-007 distributions. Automated exact/provenance/split gates pass, but the corpus is not training-ready: 0/600 human approved, 600/600 pending two independent reviews, 190 ambiguity-flagged, and 0/600 accepted for training. No model was loaded and no adapter/training/production action occurred.
- Phase 2C external review clarification: the user attested that all 600 unchanged records completed external manual two-pass review and adjudication and approved the frozen corpus for training. No data/project files changed during review; the attestation is stored separately without inventing reviewer identities or per-case comments. Exactly one pinned LoRA training and post-training CP-005 evaluation are authorized; production promotion remains forbidden.
- CP-009 LoRA result: the one authorized adapter completed five epochs/150 steps and reached internal-dev macro F1 `1.0`, but frozen CP-005 accuracy stayed `37/45`, macro F1 was only `0.820639`, false contradictions worsened to `3/15`, and DA-017 worsened to `1/5`. It created two regressions on baseline-correct cases (`NLI-EVAL-037`, `041`). Latency/memory pass; semantic acceptance fails; adapter promotion is rejected.
- CP-010 diagnosis: question-level splitting excluded evaluation concepts but did not isolate the deterministic authoring grammar. The same 12-slot schedule, wrappers, mutation operators, and donor-neutral construction occur in train and dev; `semantic_family_ids` encode questions but not template/transformation families. Label-correlated markers occur in `170/200` entailments, `150/200` contradictions, and `180/200` neutrals, at nearly identical train/dev rates.
- Corpus realism diagnosis: `153/180` nominal paraphrase entailments contain the full normalized premise; all 90 direct contradictions explicitly negate the premise; 180/200 neutrals announce an independent fact. This makes the corpus structurally valid and label-reviewed but too easy/template-like to support the observed generalization claim. No training record contains a JOIN relation.
- Behavior diagnosis: LoRA predicted E/N/C shifts `15/18/12 -> 11/20/14`, entailment recall falls `13/15 -> 11/15`, and false contradictions rise `2 -> 3`. It fixes `007/035`, regresses `037/041`, and leaves six failures. `041` becomes a `0.988097` contradiction; `042/045` remain high-confidence false contradictions; only the easy donor-like DA-017 neutral passes.
- Root-cause conclusion: the primary failure is authoring-template/distribution shortcut learning plus missing natural relational/dialectal reasoning, not label imbalance, exact CP-005 leakage, or failed optimization. Base-family capability/calibration remains a contributor because CP-006 also failed the critical false-contradiction/DA-017 objective.
- Scope of weakness: no discovery case reproduced the exact DA-017 E→C pattern, so that signature is JOIN-localized in this first 40-case discovery set. Four non-DA-017 concepts still produced cross-language/direct or near-neighbor contradiction errors, so the broader multilingual/domain weakness is systemic rather than a single transient string defect.
- Runtime provenance risk: CP-006 now controls evaluation provenance with immutable model revisions, tokenizer identity/fingerprint, model-file hash, CPU/fp32 mode, max length, label mapping, and deterministic settings. Production loading still uses a mutable model ID and was intentionally not changed by Phase 2A.
- Impact: real score changed from `1.5818` to `-49.9158`; CP-001 cannot be called fully fixed.
- Do not retry: reverting BGE relevance selection; selecting a wrong chunk with higher NLI entailment; rerunning CP-003 Unicode/tokenizer/label/direction diagnostics or the unchanged CP-005 baseline without dependency invalidation; training on the held-out set; hard-coding JOIN rules; changing label mapping; tuning thresholds against a raw false polarity; or rerunning the same CP-009 adapter configuration/corpus merely because internal dev was perfect.
- Evidence-ranked next action: CP-010 diagnosis is complete. If explicitly authorized, perform Phase 2E design only: define generator/template-family isolation, independently authored natural language, unmarked relational contrasts, a separate model-selection diagnostic, and a pre-registered one-variable comparison between revised-data LoRA and a semantic-verifier/cascade. Do not create data, train a second adapter, tune on CP-005, or promote/change production without separate authorization.
- Closure criteria: an explicitly authorized generic remediation is evaluated on representative held-out multilingual/domain cases; affected regression suites pass; model/tokenizer provenance is pinned/recorded; and correct evidence receives a defensible NLI/verdict without a question-specific rule or threshold concealment.

## KI-002 — Real candidate flow is not yet fully multimodal or Late-Fused

- Status: `OPEN_VERIFIED`
- Area: product architecture
- Evidence: current frontend/backend routing and service code (EV-004)
- Current fact: candidate flow persists real Audio/ASR/content results but never invokes real Vision or real delivery-confidence fusion.
- Impact: the main report cannot represent the complete target multimodal architecture.
- Closure criteria: an explicitly scoped integration design binds real Vision and aligned modality evidence to the same persisted answer segment, defines failure/conflict semantics, persists results, and passes security/product/E2E acceptance tests.

## KI-003 — Three divergent analysis/fusion paths can be confused

- Status: `OPEN_VERIFIED`
- Area: architecture/API/product semantics
- Evidence: EV-004
- Current fact: candidate per-question real partial pipeline, public real filesystem-only harness, and legacy persisted random 35/30/35 fusion coexist.
- Impact: labels, scores, authentication, persistence, and reliability differ by route; direct legacy API use can create apparently real persisted mock results.
- Closure criteria: product ownership chooses the supported path; mock/engineering routes are removed, isolated, or explicitly gated; schemas and migration behavior are defined and tested.

## KI-004 — Fusion harness is unauthenticated and not database-persisted

- Status: `OPEN_VERIFIED`
- Area: security/persistence
- Evidence: `backend/app/routers/interviews.py` endpoints `analysis-questions` and `analyze` have no auth dependency and do not take a database session.
- Impact: expensive model execution and uploaded media processing are exposed by a public route in the shown app; results exist only as local artifacts.
- Closure criteria: define intended exposure, add appropriate auth/authorization/rate/size controls and persistence or explicitly development-only gating, then test ownership and failure behavior.

## KI-005 — Cross-modal temporal/entity alignment is absent

- Status: `OPEN_VERIFIED`
- Area: multimodal evidence architecture
- Current fact: Vision has window timestamps and ASR has word timestamps, but fusion uses whole-answer scalar scores. Claims have no word spans; no diarization, face tracking, lip sync, or audio-visual speaker association exists.
- Impact: cross-modal agreement/conflict cannot be audited at event/claim/entity level.
- Closure criteria: define a canonical evidence/alignment contract and implement/test only the alignment level required by product acceptance criteria.

## KI-006 — Scores and thresholds are not scientifically calibrated for product use

- Status: `OPEN_VERIFIED`
- Area: evaluation/model governance
- Current fact: visual and vocal scores label themselves experimental; audio max-softmax is uncalibrated; NLP thresholds are pre-calibration defaults; no repository evidence validates a combined hiring-fitness construct.
- Impact: numeric outputs may look more authoritative than their evidence supports.
- Closure criteria: user defines intended use and quality metrics; representative labeled evaluation and calibration are completed; limitations and human-review policy are enforced in UI/API.

## KI-007 — Deployment path does not package the real AI runtime

- Status: `PARTIALLY_RESOLVED`
- Area: infrastructure
- Current fact: the backend Docker image now contains all tracked
  `InterviewIQ_AI` source, ffmpeg, and automatic migrations, and the complete
  stack starts from a clean source tree. Dedicated heavy AI environments and
  the two >100 MB checkpoints remain externally managed; background jobs are
  still non-durable.
- Impact: web/API/database deployment is reproducible and missing models fail
  explicitly, but the standard image does not perform full real-model inference
  and restart-safe background processing is still absent.
- Closure criteria: deployment target is confirmed, dependencies/artifacts are packaged securely, timeouts align, durable job/recovery semantics are defined, and deployment smoke/E2E tests pass.

## KI-008 — Documentation provenance and duplication gaps

- Status: `OPEN_VERIFIED`
- Area: documentation/governance
- Current fact: old audits/runbooks contain stale claims; the NLP README and handoff manifest are duplicate; code/docs cite a missing legacy `decisions.md` and missing plans; some model/provider details are stale.
- Impact: future work can reconstruct the wrong state or rely on unverifiable decision IDs.
- Closure criteria: a separate documentation task designates canonical module docs, links historical evidence, removes duplication/stale assertions, and does not invent missing legacy decision text.

## KI-009 — Dirty working tree contains uncommitted source and evidence

- Status: `OPEN_OPERATIONAL_RISK`
- Area: repository safety/reproducibility
- Current fact: baseline before memory bootstrap had 12 modified and 14 untracked entries, including the CP-001 fix and its artifacts; nothing is staged.
- Impact: unrelated edits can be overwritten or accidentally mixed; the latest source is not represented by HEAD.
- Closure criteria: only when the user explicitly requests repository hygiene, review ownership of every path and use narrow, recoverable operations. Do not clean or stage automatically.
