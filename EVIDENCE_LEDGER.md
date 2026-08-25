# InterviewIQ Evidence Ledger

Store only evidence that changes future decisions. Raw logs remain in their artifacts.

## EV-001 — Master instructions fully read

- Date: 2026-08-23
- Sources: the two user-supplied long-running multimodal project and external execution memory templates
- Method: complete bounded line-range reads, including sections 0–44 and 45–74
- Conclusion: resume-first, no-repeat, dependency-aware invalidation, evidence-first Late Fusion, atomic checkpoints, and exact next actions are authoritative project rules.

## EV-002 — No pre-existing root memory system

- Date: 2026-08-23
- Checks: current and ignored/hidden file inventories for all requested memory names plus common agent-rule names
- Result: no requested memory file or repository-local instruction file existed; root `.agents` and nested `.claude` directories were empty.
- Conclusion: initial bootstrap is creation, not migration. Existing reports must be preserved as historical/operational evidence.

## EV-003 — Repository baseline before memory bootstrap

- Branch/HEAD: `main` at `e0da106534bac20fed7f0ce39185b0194f8557f4`
- Upstream: `origin/main`, ahead 5, behind 0
- Porcelain state: 12 unstaged modified entries, 14 untracked entries, 0 staged entries
- Conclusion: the tree was already dirty. All pre-existing changes are protected and unrelated files were not modified by this bootstrap.

## EV-004 — Actual runtime architecture

- Primary source paths:
  - `frontend/src/pages/InterviewRoom.jsx`
  - `frontend/src/pages/Processing.jsx`
  - `frontend/src/pages/Report.jsx`
  - `backend/app/routers/interviews.py`
  - `backend/app/services/audio_analysis_service.py`
  - `backend/app/services/answer_content_service.py`
  - `InterviewIQ_AI/fusion/fusion_pipeline.py`
  - `InterviewIQ_AI/fusion/confidence_fusion.py`
  - `backend/app/ai_modules/fusion_engine.py`
- Conclusion: source confirms three distinct paths: persisted candidate real Audio/ASR/NLP without real Vision/fusion; real filesystem-only multimodal harness; legacy persisted mock fusion.

## EV-005 — CP-001 automated verification record

- Date: 2026-08-23, immediately preceding memory bootstrap
- Reported results:
  - focused retrieval/evidence: `9 passed`
  - full NLP pytest suite: `9 passed`
  - focused backend regressions: `16 passed`
  - full backend suite: `71 passed, 1 intentional real-model skip`
  - Fusion suite: `15 passed`
- Evidence limitation: exact stdout/commands were reported in the preceding execution but were not persisted in the workspace. Current pytest caches have no failures but are not sufficient proof of exact pass counts.
- Decision: retain CP-001 as reported verified evidence; do not pretend cache inspection independently reproduced it.

## EV-006 — DA-017 before/after real evidence

### Input identity

- MP4: `test_videos/Video_—_Strong_Baseline_Visu.mp4`
- MP4 SHA-256: `BD52FD39CC62EB0A818CDAE85D2B51F5F813B596ABE3864AF9F4B85C55A24044`
- Before extracted audio and after-run WAV share SHA-256: `3F28793F1A392E4598EA8A36D840AAB17DBEE8FCA9C984F4AD1F7D7D7254830C`
- Conclusion: before/after evidence used identical audio bytes.

### Before

- Artifact: `test_videos/nlp_result.json`
- SHA-256: `F13E386B1BE696D9845DD3420626FBBD556D18D2B18FCC39243DDB6A0072C7B3`
- Selected chunks: DA017-C03, DA017-C04
- Precision/Coverage/Harmonic-F/score: `0.0141695 / 0.0179003333 / 0.0158179040 / 1.5817904043`
- `nlp_stderr.log` does not show BGE loading, corroborating the old small-document bypass.

### After

- Artifact: `test_videos/da017_after_fix/fusion_after.json`
- SHA-256: `F2D387023AB9B85B1F5B61E38E5C551193AAB1B80A27099902819AD2B9F763D8`
- Real component status: Vision, ffmpeg, Audio, and NLP all returned code 0; overall status `success`; no component error.
- The embedded NLP stderr records real `BAAI/bge-m3` loading on CPU.
- Claim 0: BGE selected DA017-C01 at similarity `0.8564866627`; NLI E/N/C `0.679402 / 0.024493 / 0.296105`; `NEUTRAL`; claim score `0`.
- Claim 1: BGE selected DA017-C02 at similarity `0.7798359762`; NLI E/N/C `0.000967 / 0.000717 / 0.998316`; `CONTRADICTED`; claim score `-0.998316`.
- Precision/Coverage/Harmonic-F/score: `-0.499158 / 0.255774 / -0.499158 / -49.9158`.
- Vision remained `20.0147711175`, fearful/low, with sufficient evidence.
- Verdict: `PARTIAL PASS`. Retrieval/evidence selection is corrected; the downstream semantic verdict and final score are not.

### Timing caveat

The full-run artifact timestamp is about five minutes earlier than the latest `chunk_cap.py` and test edits. The artifact proves the core ranking behavior, while the exact latest dirty tree has not received another full-model run.

## EV-007 — Historical/component artifact hashes

- `PROJECT_STATUS_AUDIT_2026-08-04.md`: `BA4350ECA17C561D53522B89EDA7ED1DF58A8A0E3849FF2C12134E135D7A5EBE` — historical and superseded as current-state authority
- `PHASE_3A_REAL_AUDIO_IMPLEMENTATION_REPORT.md`: `A5A69079FCA0BCFCA4C315EBEFBFCBC0474A104BD69DC41AA19B1B05F0478F32` — historical Phase 3A evidence
- `InterviewIQ_AI/vision/reports/checkpoint_summary.json`: `29D5DB92B19BEED2BC631BB8613DE15ED0D6AD9DEE3F4C7687C1624C8C25BEAE` — component model-provenance evidence

## EV-008 — CP-002 memory validation

- Date: 2026-08-23
- Check 1: PowerShell `ConvertFrom-Json` parsed `EXECUTION_STATE.json` and returned the expected project/task/checkpoint fields.
- Check 2: Python `json.loads` independently parsed the same file.
- Check 3: all nine governance/memory files exist; `AGENTS.md` resolves to the existing canonical `AGENT_RULES.md` target.
- Check 4: Git shows the same 12 pre-existing unstaged modified entries and 14 pre-existing untracked entries, plus exactly the nine new memory/governance files.
- Check 5: `git diff --cached --name-only` is empty; nothing is staged.
- Product tests/models: intentionally not rerun because TASK-MEM-001 changed no product dependency and CP-001 remains valid under the no-repeat rule.
- Result: `PASS`; checkpoint `CP-002` is verified.

## EV-009 — CP-003 real NLI forensic diagnosis

- Date: 2026-08-23
- Scope: read-only NLI boundary only; no retrieval, Vision, Audio, ASR, full Fusion, production source, config, threshold, model, label, score, or reference-data change.
- Primary conclusion: **root-cause class D — NLI model multilingual capability / model behavior**. The defect is not owned by retrieval, stored RTL order, application preprocessing, truncation, class mapping, softmax, or premise/hypothesis direction.

### Authoritative source strings and storage

- Canonical file: `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/refdocs/reference_docs_250_FINAL_v1.json`, SHA-256 `BA062768EB02C6DBE16D90024C30B075AF98F85D08B9E946BB26862AAB250F07`.
- DA017-C01: `INNER JOIN يعيد الصفوف التي تحقق شرط الربط في كلا الجدولين فقط.`; 63 codepoints, 105 UTF-8 bytes, SHA-256 `7A8A451B925E057B6626F1FE6128E320622A738BCD33BB8ED531D5CF3871795D`.
- DA017-C02: `LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL.`; 108 codepoints, 185 UTF-8 bytes, SHA-256 `28D908401775AD5D50C629F421C11DEB6EA0EF1D4CB7AB0A22BDB75FC75D66BA`.
- Both are NFC, strict UTF-8, and in correct logical/codepoint order. Neither contains a bidi format/control, BOM, NBSP, zero-width character, newline, or common mojibake marker. Mixed Arabic/Latin may render visually reordered under the Unicode bidi algorithm, but the stored strings are not reversed or corrupted.
- `refdocs/loader.py` opens UTF-8 JSON and assigns `text=chunk_raw["text"]` unchanged; reference chunks bypass claim normalization.

### Preserved claims and preprocessing replay

- Before artifact: `test_videos/nlp_result.json`, SHA-256 `F13E386B1BE696D9845DD3420626FBBD556D18D2B18FCC39243DDB6A0072C7B3`.
  - raw LEFT: `الـ left join يُعيد كل الصفوف من الجدول الأيسر حتى إذا لم يكن هناك تطابق.`
  - NLI hypothesis: `ال left join يعيد كل الصفوف من الجدول الايسر حتى اذا لم يكن هناك تطابق.`; SHA-256 `AB642479A90DCDD797AC19D3E3762671CAE8CFA1BC508EFA8B34F0D9D7D54797`.
- After artifact: `test_videos/da017_after_fix/fusion_after.json`, SHA-256 `F2D387023AB9B85B1F5B61E38E5C551193AAB1B80A27099902819AD2B9F763D8`.
  - raw INNER: `الـ Inner Join يُعيد الصفوف المتطابقة بين الجدولين.`
  - NLI hypothesis: `ال Inner Join يعيد الصفوف المتطابقة بين الجدولين.`; SHA-256 `40B5E24A86ACFFE1B711323825A4C8250B02B402B4FADFEA4ECB3B9CD8332EAE`.
  - raw LEFT: `الـ Lift Join يُعيد كل الصفوف من الجدول الشمال حتى لو لا يوجد تطابق.`
  - NLI hypothesis: `ال Lift Join يعيد كل الصفوف من الجدول الشمال حتى لو لا يوجد تطابق.`; SHA-256 `F1E8A9DFAC9DA5C058FDACD2E1AEA2554C31543441437AB7517F88AE7E5FFECA`.
- `claims_raw` is the first exact replayable post-LLM boundary. `apply_glossary()` replay exactly equals both artifacts: it removed tatweel U+0640 and damma U+064F; on the before LEFT claim it also mapped U+0623/U+0625 alef variants to U+0627. It made zero glossary substitutions and no semantic change. ASR raw and normalized transcripts are identical with an empty normalization log; after-run `Lift` already exists in ASR and is not created by normalization or bidi display.

### Exact runtime path and configuration

- Live path: `fusion/fusion_pipeline.py` → `fusion/adapters/nlp_adapter.py` → `.venv_nlp` runner → `pipeline.evaluate_answer` → `nli/engine.py`.
- `pipeline.py` supplies the selected reference chunks and normalized `claim_text`; `build_claims_chunks_matrix` constructs `premise=chunk.text`, `hypothesis=claim`; tokenizer call is `(batch_p, batch_h, truncation=True, padding=True, max_length=256, return_tensors="pt")`.
- Cross-product order and transpose back to `[claim][chunk]` are correct. `assert_id2label` enforces `{0: entailment, 1: neutral, 2: contradiction}`; production computes `softmax(logits, dim=-1)` and uses that same order.
- Model ID: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`; local cached snapshot `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`; `DebertaV2ForSequenceClassification`; no adapter.
- Tokenizer: `DebertaV2TokenizerFast`, fast, case-sensitive; model/tokenizer max length 512; production max length 256; right padding/right truncation; pair form `[CLS] premise [SEP] hypothesis [SEP]`.
- Runtime: torch `2.2.2+cpu`, CPU, model parameters fp32, eval mode. Special IDs: PAD=0, CLS=1, SEP=2, UNK=3.
- Current config maps `0=entailment, 1=neutral, 2=contradiction`; raw-logit order below is always E/N/C.
- Reproducibility caveat: production resolves model and tokenizer separately by mutable model ID with no pinned revision, dtype, or tokenizer class; artifacts do not store the resolved revision/hash/device/dtype/token trace. The current snapshot is proven for CP-003, but cannot be proven retrospectively for an unpersisted supplemental replay.

### Exact tokenizer trace

- INNER pair: premise 23 tokens, hypothesis 14, pair 40 including 3 specials; no truncation and zero UNK.
  - premise tokens: `[▁I, NNER, ▁J, OIN, ▁يع, يد, ▁الصف, وف, ▁, التي, ▁ت, حقق, ▁شر, ط, ▁ال, ربط, ▁في, ▁كلا, ▁الجد, ولين, ▁ف, قط, .]`
  - hypothesis tokens: `[▁ال, ▁Inner, ▁Join, ▁يع, يد, ▁الصف, وف, ▁المت, طاب, قة, ▁بين, ▁الجد, ولين, .]`
- After LEFT/Lift pair: premise 40 tokens, hypothesis 22, pair 65 including 3 specials; no truncation and zero UNK.
  - premise tokens: `[▁, LEFT, ▁J, OIN, ▁يع, يد, ▁كل, ▁صف, وف, ▁الج, دول, ▁الأ, يسر, ▁مع, ▁الصف, وف, ▁المط, ابق, ة, ▁من, ▁الج, دول, ▁الأ, يمن, ،, ▁و, تمل, أ, ▁موا, ضع, ▁عد, م, ▁, التط, ابق, ▁ب, قيم, ▁, NULL, .]`
  - hypothesis tokens: `[▁ال, ▁Lift, ▁Join, ▁يع, يد, ▁كل, ▁الصف, وف, ▁من, ▁الج, دول, ▁ال, شمال, ▁ح, تى, ▁لو, ▁لا, ▁يو, جد, ▁تط, ابق, .]`
- Preserved before LEFT pair: premise 40, hypothesis 26, pair 69 including specials; no truncation/UNK. The tokens retain `LEFT`/`JOIN` in the premise and `left`/`join` in the hypothesis.
- Corrected after hypothesis (`Lift→LEFT`): premise 40, hypothesis 23, pair 66; no truncation/UNK. The tokenizer retains `LEFT` and `Join` on both sides.

### Exact production-shaped logits and probabilities

All six DA-017 chunks were batched in canonical order, matching the production matrix shape; softmax was independently recomputed from the raw logits.

- INNER + DA017-C01:
  - logits E/N/C: `1.378316641 / -1.944509983 / 0.547817469`
  - probabilities E/N/C: `0.679402053 / 0.024492977 / 0.296104938`
  - predicted class: entailment (the downstream verdict is neutral only because of existing policy thresholding).
- After LEFT/Lift + DA017-C02:
  - logits: `-2.336814404 / -2.635162354 / 4.602999210`
  - probabilities: `0.000966819 / 0.000717421 / 0.998315811`
  - predicted class: contradiction; this reproduces the real artifact.
- Preserved before correctly recognized `left join` + DA017-C02:
  - logits: `-1.809667349 / -1.500351191 / 3.003623009`
  - probabilities: `0.007968214 / 0.010856641 / 0.981175125`
  - predicted class: contradiction. This independently confirms that `Lift` is not the sole cause. The small difference from the user-supplied unpersisted `0.009605 / 0.012170 / 0.978225` does not change polarity or ownership.

### Controlled real-model diagnostics

Twenty-three bounded controls were run with the real local model; every pair was below 256 tokens and had zero UNK.

- Exact C02 self-entailment: `0.997029 E / 0.002652 N / 0.000319 C` — correct.
- C02 → exact first clause: `0.998453 / 0.001336 / 0.000211` — correct entailment.
- C02 → exact NULL/unmatched clause: `0.998432 / 0.001292 / 0.000277` — correct entailment.
- C02 → Arabic-only first clause: `0.998685 / 0.001093 / 0.000223` — correct entailment.
- C02 → generated direct Arabic negation: `0.000297 / 0.000610 / 0.999093` — correct contradiction.
- C02 → required unrelated English `Python is commonly used for data analysis.`: `0.007348 / 0.972105 / 0.020547` — correct neutral.
- Actual after `Lift`: `0.000967 / 0.000717 / 0.998316` — false contradiction.
- Actual before recognized `left`: `0.007968 / 0.010857 / 0.981175` — false contradiction.
- Correcting `Lift→LEFT`: `0.001694 / 0.001059 / 0.997247` — still false contradiction.
- Removing the leading Arabic article after correction: `0.001967 / 0.001427 / 0.996605` — still false contradiction.
- Symmetrically normalizing the reference plus corrected LEFT: `0.001985 / 0.001117 / 0.996897` — still false contradiction.
- Lowercasing the reference SQL tokens plus the before claim: `0.012299 / 0.015265 / 0.972436` — still false contradiction.
- Reversing the actual after pair: `0.000589 / 0.119188 / 0.880223` — still contradiction; production direction remains the correct NLI direction.
- Actual INNER + C01: `0.679405 / 0.024493 / 0.296102` — entailment is the largest class.
- Monolingual English controls: entailment `0.900327 E`, contradiction `0.978469 C`, neutral `0.977446 N` — all correct.
- Arabic C02 → diagnostic English entailment: `0.214744 / 0.013641 / 0.771615` — false contradiction.
- Arabic C02 → requested English contradiction wording: `0.446735 / 0.392952 / 0.160313` — false entailment, while a slightly different English contradiction produced `0.993549 C`. This phrase/cross-language sensitivity further supports class D.

### Root-cause elimination and owner

- A ruled out: canonical reference storage/codepoint order is correct; bidi anomaly is display-only.
- B ruled out as primary: production preprocessing is exactly replayed and semantics-preserving here; symmetric normalization does not repair the result.
- C ruled out as primary: important SQL terms survive, there are no unknowns or truncation, and corrected/case-normalized token variants remain wrong. Code-switching is part of the model's difficult input distribution, not a tokenizer-loss defect.
- E ruled out: direction, cross-product/transpose, id2label, logits, softmax axis, and class extraction are correct; positive and negative controls prove the mapping.
- F ruled out: the raw probability itself is semantically inverted at up to `0.998316 C`; threshold changes cannot fix polarity.
- G not selected: `Lift` and orthographic asymmetry can perturb confidence, but removing them does not change the false class; the single primary owner remains model behavior.
- **Selected D**: the current zero-shot checkpoint is brittle on semantically equivalent Arabic/code-switched SQL paraphrases and cross-language phrasing despite succeeding on exact/near-exact and monolingual controls.

### Candidate remediation order (not implemented)

1. Evaluate/train a representative Arabic/code-switched domain adapter through the existing `nli_adapter_path` hook, gated by held-out regressions.
2. Benchmark and, only if justified, configure a better validated multilingual checkpoint with pinned model/tokenizer provenance.
3. Consider a generic secondary semantic verifier only if one model/adapter cannot satisfy quality criteria; this has the largest logic/latency/calibration blast radius.

Result: forensic task `PASS`; the defect remains open with status `ROOT_CAUSE_VERIFIED_FIX_PENDING`. No remediation decision was made, so `DECISIONS.md` was intentionally unchanged.

## EV-010 — CP-003 checkpoint validation

- Date: 2026-08-23
- PowerShell `ConvertFrom-Json` parsed `EXECUTION_STATE.json` and returned task `TASK-NLI-FORENSIC-001`, status `VERIFIED_COMPLETE_AWAITING_FIX_AUTHORIZATION`, and checkpoint `CP-003`.
- Python `json.loads` independently parsed the state; all eight canonical rule/memory files read as strict UTF-8 with no replacement character; completed step IDs are unique; `tests_remaining` is empty; the exact resume instruction is non-empty.
- Cross-file checks found CP-003 in `CURRENT_TASK.md`/`PROJECT_MEMORY.md`, EV-009 in this ledger, and `ROOT_CAUSE_VERIFIED_FIX_PENDING` in `KNOWN_ISSUES.md`.
- `git diff --cached --name-only` is empty. Git porcelain retains the same 12 pre-existing modified and 14 pre-existing untracked product/evidence entries plus the nine root memory/governance files; no product path was added or changed by this forensic task.
- Product tests and multimodal models were intentionally not rerun because CP-003 changed memory only and performed the required isolated real NLI diagnostics. CP-001 retrieval and other upstream verification remain valid under dependency-aware no-repeat rules.
- Result: checkpoint `CP-003` is internally consistent and verified.

## EV-011 — CP-005 held-out dataset and unchanged current-model baseline

- Date: 2026-08-23
- Scope: Phase 1 measurement only. No training, adapter attachment, checkpoint replacement, threshold/config/scoring/reference/production change, staging, commit, or deployment action occurred.
- Dataset: `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/nli/evaluation/heldout_ar_codeswitch_v1.json`; ID `interviewiq-nli-ar-codeswitch-heldout-v1`; SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`.
- Predeclared contract: `baseline_metrics_contract_v1.json`; SHA-256 `01F2B3F6A5F8EFEE019C08972854E6D92D8DC53D999957C7B60AC45DB5D2A655`; status `PREDECLARED_BEFORE_INFERENCE`.
- Composition: 45 reviewed/unambiguous scored cases = 40 newly authored held-out discovery cases + 5 explicit pre-known DA-017 anchors; labels exactly 15 entailment/15 neutral/15 contradiction; ten question IDs spanning DA/DS/CS/SE; language styles MSA 10, Egyptian 9, Arabic-English code-switch 12, transliteration variant 5, and English diagnostic 9; all ten required difficulty types are represented.
- Validation: 45/45 unique IDs, normalized premise/hypothesis pairs, source IDs, and canonical byte-equal premises; no duplicate normalized hypothesis, unresolved source, ambiguous scored label, or broad rewrite. `do_not_train=true`; no evaluation case/path/ID is referenced in production source/config; the evaluation path is absent from fine-tuning source/config; both configured pilot pair files and the configured adapter checkpoint are absent, so no current configured training dataset contains an evaluation pair.
- Existing `gold_set_48.json` was not reused because it is DRAFT, DS-014-only, AI-drafted/not expert-verified, lacks the required slice/provenance contract, has two stale corrected labels, and has 15/48 premises drifted from current canonical chunks. Existing generic inference/metric functions were reused.
- Runtime: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`, resolved model commit `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`, `DebertaV2ForSequenceClassification`, `DebertaV2TokenizerFast`, torch `2.2.2+cpu`, CPU/fp32/eval, batch 8, max length 256, no adapter, premise=canonical evidence, hypothesis=candidate claim, label order E/N/C, argmax logits and softmax reporting. The artifact does not independently emit a tokenizer commit; the current cache contains tokenizer assets under the same sole snapshot.
- Aggregate: accuracy `37/45 = 0.822222`; macro F1 `0.818631`. Per-class precision/recall/F1/support: E `0.866667/0.866667/0.866667/15`; N `0.777778/0.933333/0.848485/15`; C `0.833333/0.666667/0.740741/15`.
- Confusion matrix, rows expected and columns predicted E/N/C: E `[13,0,2]`; N `[1,14,0]`; C `[1,4,10]`. False contradiction on true entailments is `2/15 = 13.3333%`; false entailment on true contradictions is `1/15 = 6.6667%`.
- Discovery only: accuracy `35/40 = 87.5%`, macro F1 `0.877348`, E→C `0/12`, C→E `0/14`. DA-017 anchors: accuracy `2/5 = 40%`, macro F1 `0.466667`; `041 PASS E→E`, `042 FAIL E→C`, `043 FAIL C→E`, `044 PASS N→N`, `045 FAIL E→C`.
- Eight failures: directions N→E 1, C→N 4, E→C 2, C→E 1. Supported overlapping observations are Arabic semantic paraphrase (2, both DA-017), Egyptian (1), code-switch (2), technical-term cases (3), near-neighbor concepts (2), neutral-vs-entailment (1), and contradiction-polarity errors (3). Negation produced no failure and is not claimed as a failure cluster.
- Language accuracy: Arabic transliteration 100%, MSA 90%, Egyptian 88.89%, Arabic-English code-switch 83.33%, English diagnostics against Arabic premises 55.56%. Weak difficulty slices are direct contradiction 40%, near-neighbor contradiction 60%, and ASR-like variation 66.67%; negation contradictions pass 5/5.
- Interpretation: the exact CP-003 E→C signature was not reproduced outside DA-017 among 40 discovery cases, so it is JOIN-phrase-localized in this first small set, but it is not a transient string anomaly because two realistic LEFT paraphrases fail and the inverse false statement flips to entailment. Broader cross-language/direct and near-neighbor contradiction weakness across four non-DA-017 concepts is systemic.
- Proposed target result: the unchanged model fails every predeclared proposed gate except false-entailment ≤10%; this is evidence for an experiment, not authorization or a production decision.
- Artifacts and final SHA-256 values: dataset validation `978184AD9C7E4D9E2F7321E6753D5660F18099B545034A7925E7D700623FBFFD`; full baseline `7FAFA2F8EF8B1C5BA70AD2AAED371A7780557F7D05E6690C7E8468234495BFC6`; failure analysis `A2712C3B679D3D0F88BF687503BCC0892EBD775A8F05BADBB071EFCCA3B59472`; independent baseline validation `3C13E7A20A151B80DE5616E84E02CFBF6EF3CC2792AE7AEEAA403F528FDAACB2`; engineering summary `9A997A6224282BD92C051DA737B2760D4A7741E527A1E3A079A42E238B5948D9`.
- Evidence-ranked next experiment, still unauthorized: freeze CP-005; create separate training-only cases excluding all ten evaluation question IDs; emphasize observed cross-language direct/near-neighbor contradictions and Arabic/code-switched paraphrase entailments; train exactly one LoRA adapter through the existing hook; A/B on the frozen baseline before considering production adoption.

## EV-012 — CP-005 checkpoint validation

- Date: 2026-08-23
- PowerShell `ConvertFrom-Json` parsed the state, dataset, metrics contract, and full baseline and returned task `TASK-NLI-BASELINE-001`, status `VERIFIED_COMPLETE_AWAITING_PHASE2_AUTHORIZATION`, checkpoint `CP-005`, 45 dataset cases, and 45 prediction rows.
- An independent strict-UTF-8/Python JSON audit passed every state and artifact invariant: unique completed-step IDs; empty `tests_remaining`; explicit Phase-2 gate; 45 unique IDs/pairs; 45 approved scored labels; balanced 15/15/15 classes; explicit 40/5 discovery-anchor split; predeclared contract; no production hard-code or current configured-training overlap; and cross-file CP-005/KI/EV markers.
- Deterministic recomputation from persisted probabilities/predictions reproduced 37 correct, confusion rows E/N/C `[[13,0,2],[1,14,0],[1,4,10]]`, all eight failure IDs, all 45 argmax labels, and probability sums within `2e-6`. The earlier tokenizer-only validation found maximum untruncated pair length 78/256, zero over-length pairs, and zero UNK tokens.
- Core embedded hashes still match: dataset `5AA127...DC18`, contract `01F2B3...A655`, baseline `7FAFA2...BFC6`, and failure analysis `A2712C...A572`. Final dataset-validation, baseline-validation, and summary hashes match EV-011.
- Independent read-only artifact review recomputed aggregate/discovery/anchor metrics, every language/difficulty slice, acceptance checks, failure directions, dataset/source distributions, and all five full DA-017 rows; no numerical, schema, label, or hash defect remains. The only non-blocking provenance caveat is that the artifact records model revision and tokenizer class/model ID but leaves `resolved_tokenizer_commit=null`; the current cache contains tokenizer assets under the same sole `8adb042d...` snapshot.
- Git preservation: porcelain has the original 12 protected tracked modifications, the prior 14 protected untracked product/evidence entries, the nine root memory/governance files, and exactly two CP-005 untracked directory entries (`data/nli/evaluation/` and `results/nli_baseline_cp005/`). `git diff --cached --name-only` is empty; nothing was staged, committed, tagged, pushed, reset, restored, cleaned, or stashed.
- Product source/config tests and heavy models were intentionally not rerun during checkpoint finalization: CP-005 already contains the required single real-model run, and finalization changed only evaluation artifacts and external memory. This follows dependency-aware no-repeat and FAST artifact reuse.
- Result: technical checkpoint `CP-005` is internally consistent and `PASS` for Phase 1 measurement. The current model does not pass the proposed remediation target, KI-001 remains open as `BASELINE_MEASURED_REMEDIATION_PENDING`, and remediation is stopped pending explicit Phase-2 authorization.

## EV-013 — CP-006 Phase 2A pinned checkpoint-control evaluation

- Date: 2026-08-23
- Scope: authorized experiment preparation and controlled inference only. No adapter was trained or created; no production NLI/model/config/threshold/scoring/retrieval/Fusion behavior changed; no checkpoint was promoted; and no data was created for training.
- Frozen input: CP-005 dataset `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/nli/evaluation/heldout_ar_codeswitch_v1.json`, ID `interviewiq-nli-ar-codeswitch-heldout-v1`, 45 scored cases, SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`.
- Reproducibility controls: exact authorized repository/model IDs and immutable revisions; exact snapshot model-file SHA-256; `DebertaV2TokenizerFast` identity plus vocabulary fingerprint `B700D1096679B9E6B06E34D5F6F5E1C5C8D94E24CF6EF6EDB31707D145608B12`; verified `0=entailment, 1=neutral, 2=contradiction`; premise=canonical evidence and hypothesis=candidate claim; max length 256; batch 8; CPU/fp32/eval/no-adapter execution; deterministic PyTorch settings; and one fresh process per checkpoint.
- Baseline control: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli@8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`; `DebertaV2ForSequenceClassification`; 278,811,651 parameters. The rerun exactly reproduces CP-005 labels, metrics, and persisted rounded probabilities, with maximum probability delta `0`.
- Candidate control: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7@b5113eb38ab63efdd7f280f8c144ea8b13f978ce`; `DebertaV2ForSequenceClassification`; 278,811,651 parameters; snapshot weight SHA-256 `7C8E29F1115986D032E92B0FBAA0BDEF1062A46F658B08705F237C05014A8541`.
- Leakage protection: preflight passes dataset SHA, unique IDs, duplicate normalized pair detection, and exclusion-control readiness for question IDs plus normalized premises, hypotheses, and pairs. No training manifest exists, recorded explicitly as `NO_TRAINING_MANIFEST_PRESENT`; this is not represented as proof that hypothetical future training data is clean. Any Phase 2B manifest must pass the hard exclusion gate before training.
- Baseline metrics: accuracy `37/45 = 0.822222`; macro F1 `0.818631`; per-class E/N/C F1 `0.866667/0.848485/0.740741`; confusion rows expected and columns predicted E/N/C `[[13,0,2],[1,14,0],[1,4,10]]`; false contradiction `2/15 = 13.3333%`; false entailment `1/15 = 6.6667%`; DA-017 `2/5`.
- Candidate metrics: accuracy `39/45 = 0.866667`; macro F1 `0.866270`; per-class E/N/C F1 `0.857143/0.875000/0.866667`; confusion `[[12,1,2],[1,14,0],[0,2,13]]`; false contradiction `2/15 = 13.3333%`; false entailment `0/15`; DA-017 `2/5`; discovery-only accuracy `37/40 = 0.925000` and macro F1 `0.926543`.
- Candidate corrections: `NLI-EVAL-023` C `N→C`, `NLI-EVAL-035` C `N→C`, and `NLI-EVAL-043` C `E→C`. New regression: correct INNER JOIN entailment `NLI-EVAL-041` changes `E→N`. Critical LEFT JOIN entailments `NLI-EVAL-042` and `NLI-EVAL-045` remain false contradictions.
- Candidate DA-017 rows: `041` expected E, predicted N, E/N/C `0.422111/0.467877/0.110012`, FAIL; `042` E→C `0.013753/0.137642/0.848605`, FAIL; `043` C→C `0.083939/0.413021/0.503041`, PASS; `044` N→N `0.000705/0.999076/0.000218`, PASS; `045` E→C `0.002853/0.010693/0.986455`, FAIL.
- Supported slice deltas: English diagnostic accuracy `0.5556→0.8889`, near-neighbor contradiction `0.6000→1.0000`, and direct contradiction `0.4000→0.6000` improve; Arabic-English code-switch `0.8333→0.7500` and natural-paraphrase entailment `0.8571→0.7143` regress. MSA remains `0.9000`, Egyptian remains `0.8889`, and transliteration remains `1.0000`.
- Resource controls: identical warmup excluded from timed 45-case inference. Baseline timed inference `3.624001 s` / `80.5333 ms per case`; candidate `3.676925 s` / `81.7095 ms per case`, a `1.46%` latency increase. Process peak working set is approximately `2.093 GB` for both. Load time is recorded but not used for selection because run order and OS caching bias it.
- Acceptance: candidate passes proposed overall accuracy, macro-F1, minimum-class-F1, and false-entailment gates; it fails the false-contradiction, DA-017 `5/5`, and minimum-supported-slice gates. Assessment is `MIXED_IMPROVEMENT_NOT_ACCEPTED_AS_REMEDIATION_WINNER`; automatic winner is `null`; production remains on the current checkpoint.
- Artifacts and SHA-256: experiment manifest `9177084603FAAA1B2B6D07B74B3F23E0B1A821A32146AAD9E232AE53D9E6238E`; preflight validation `E255C60D16FF879190FCF3F8E6D1C81F50903B3476046D3EF444DCE655B53FA9`; baseline control `78A33E6DE5660227B2A966B389B90133AEF664B3C421054E2A843702360DAC4A`; candidate control `462221DFFD6016414186D20301A3497819ABB0BF4EB38C674A2CBE81D6E3D541`; comparison JSON `908A1F72D426BCA7B54F867C823B1AFB9FAD59BC1480C7A9C9770961DF48BB55`; comparison report `8DDF94F807DD3DA51294926B24BEB70B39F7BFEF74E2C87F89AB5B1F4CAECB74`; validation artifact `7BB2DAB8FEE2292B4CA7F51D6992274EF50D05D233FEDA4964F4DAB459F21497`.
- Recommendation: no checkpoint winner and no promotion. Preserve both controls; targeted separate-data LoRA on the pinned current production base remains the evidence-ranked Phase 2B experiment, subject to explicit authorization and the recorded leakage gates.

## EV-014 — CP-006 checkpoint and artifact validation

- Date: 2026-08-23
- Strict UTF-8/JSON validation passes for `EXECUTION_STATE.json`, the immutable experiment manifest, preflight, both full model results, comparison JSON, validation JSON, and the referenced CP-005 artifacts.
- The completed-artifact audit independently verifies the frozen dataset hash, exact model and tokenizer controls, label mapping, probability sums/argmax labels, all aggregate/class/slice/anchor metrics, both confusion matrices, acceptance gates, baseline parity with CP-005, and the absence of an automatic winner. Result: `PASS`.
- Focused checkpoint-control tests pass `16/16`; the complete current NLP suite passes `25/25`. Tests cover manifest immutability, leakage exclusions and duplicate detection, metrics parity, fake inference, comparison logic, and report contracts.
- Checkpoint consistency: CP-006 is recorded in `EXECUTION_STATE.json`, `CURRENT_TASK.md`, and `PROJECT_MEMORY.md`; KI-001 remains open as `CHECKPOINT_CONTROL_EVALUATED_REMEDIATION_PENDING`; EV-013 records the real evaluation; completed-step IDs are unique; `tests_remaining` is empty; and the exact Phase 2B next step/resume instruction is non-empty.
- Git preservation: `git diff --cached --name-only` is empty. Existing unrelated dirty-worktree changes remain untouched; no staging, commit, tag, push, reset, restore, clean, stash, checkpoint promotion, training, or production mutation occurred.
- Result: technical checkpoint `CP-006 — Phase 2A checkpoint control evaluation complete` is internally consistent and `PASS`. KI-001 remains unresolved; no remediation winner was selected; further work stops pending explicit Phase 2B authorization.

## EV-015 — CP-007 Phase 2B LoRA preparation controls

- Date: 2026-08-23
- Scope: preparation only. No training examples, model load, training run, adapter checkpoint, adapter evaluation, production model/config/inference/scoring/threshold/retrieval/Fusion change, or promotion occurred.
- Inherited boundary: CP-005 remains frozen at SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`; CP-006 remains `NO_REMEDIATION_WINNER`; base and tokenizer revision for the proposed experiment is `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`.
- Corpus specification: target 600 cases from at least 40 independent non-protected question IDs; approximately 480 train / 120 dev by complete question ID; labels exactly 200 entailment / 200 contradiction / 200 neutral.
- Language targets: MSA 150, Egyptian 150, Arabic/English code-switch 180, transliteration variants 60, and English diagnostics 60; technical terminology is a cross-cutting minimum of 360, including at least 120 code-switched and 90 Egyptian technical cases.
- Difficulty targets: paraphrase entailment 180, domain-entailment preservation 20, near-neighbor contradiction 110, direct contradiction 90, neutral technical 120, and semantically adjacent neutral 80. Every case requires the requested eight fields plus split/source/group controls, two independent reviewers, and adjudication; AI-only labels are rejected.
- Leakage boundary: the exclusion policy loads all 45 frozen CP-005 cases, verifies `do_not_train=true`, protects all ten source question IDs and all five DA-017 anchors, and rejects evaluation-file reuse, case/ID/premise/hypothesis/pair overlap after conservative normalization, training duplicates, train/dev question overlap, paired-group splitting, mutable sources, and unresolved provenance. Human semantic-family review additionally rejects translations, dialect/code-switch conversions, paraphrases, operator/entity substitutions, and other CP-005 derivatives not caught by exact normalization.
- Existing hooks: optional `adapter_path` enters at `pipeline.evaluate_answer`; `gold_eval.load_adapter` calls `PeftModel.from_pretrained` and asserts non-empty `peft_config`; `nli.finetune.run_finetune` provides training orchestration; CLI hooks exist for fine-tuning and adapter evaluation.
- Supported LoRA shape: r 16, alpha 32, `query_proj` + `value_proj`, dropout 0.1, bias none, `SEQ_CLS`. The prepared single-run contract retains learning rate `2e-4`, five epochs, train/eval batch 16/32, warmup 0.06, weight decay 0.01, seed 42, and sets max length 256.
- Blocking readiness gaps: legacy configured pilot files are absent; existing exclusion covers DS-014 only; loaders do not enforce the new fields/review/semantic gate; the base loader is mutable; current training tokenization defaults to 128; focused LoRA preflight tests are absent; and no corpus or checkpoint exists.
- Predeclared conjunctive gates: CP-005 ≥39/45, macro F1 ≥0.85, all class F1 ≥0.80, false contradiction 0/15, false entailment ≤1/15, neutral ≥14/15 and F1 ≥0.80, DA-017 5/5, zero regressions among baseline-correct cases, supported slices ≥70%, code-switch ≥10/12, natural-paraphrase entailment ≥6/7, near-neighbor contradiction ≥4/5, direct contradiction ≥3/5, CPU latency ≤1.15x, peak working set ≤1.10x, and separate Coverage/scoring regression PASS. Passing does not authorize production.
- Rollback: omit `adapter_path` and reload the pinned base; retain artifacts for audit. A future deployed rollback, if ever applicable, also requires exact CP-005 baseline parity.
- Preparation artifacts and SHA-256: corpus spec `1B8ED30FA4521F6824B321981968E597246924178DF7F7348D7E735036BAD228`; exclusion policy `5AB2584E8241A7D78351E55D2EED777ABB23702208EDA2DDA85B6E47FF95C112`; manifest `047297845D7A42B6334A0C8FD98D69727D6F1141B06C51E5217453B44FF96110`; report `404EC84CE77F96E0F7990FB891E61E86CE7BF26093B2DF049315F1CD0E5F97A2`; preparation validation `BDA82B6886C0F80CC21B7A51FCB4523A54D654121010938F18E1E939BBE9AB45`.
- Result: preparation `PASS`; KI-001 remains unresolved as `LORA_PREPARATION_COMPLETE_DATA_PENDING`. Exact next step is separately authorized data authoring and preflight only, stopping again before model loading or training.

## EV-016 — CP-007 checkpoint validation

- Date: 2026-08-23
- Strict UTF-8/JSON parsing passes for `EXECUTION_STATE.json`, both preparation controls, the preparation manifest/validation, the CP-005 frozen dataset, and the CP-006 comparison.
- All five preparation artifact SHA-256 values match EV-015. CP-005 still has the recorded SHA, 45 cases, and `do_not_train=true`; the policy's ten source IDs and five DA-017 anchor IDs exactly match the frozen dataset.
- Corpus-spec arithmetic passes independently: label, mutually exclusive language-style, and difficulty targets each sum to 600; all requested record fields are present; examples-created remains zero.
- Cross-file checkpoint checks pass: CP-007 appears in state/task/memory; KI-001 is `LORA_PREPARATION_COMPLETE_DATA_PENDING`; EV-015 exists; 25 completed step IDs are unique; `tests_remaining` is empty; and the data-authoring-only next step is non-empty.
- Filesystem boundary: `data/nli/training/` contains exactly the two preparation controls, not a corpus; `checkpoints/nli-lora-phase2b-v1` does not exist; no model or adapter was loaded; no production/training implementation file was changed by CP-007.
- Git preservation: `git diff --cached --name-only` is empty and the protected pre-existing dirty worktree remains untouched. Nothing was staged, committed, tagged, pushed, reset, restored, cleaned, stashed, trained, evaluated, or promoted.
- Pytest/model suites were not rerun because CP-007 changed only declarative JSON/Markdown preparation and external-memory files; the directly affected strict parsing, hashes, arithmetic, hook-presence, boundary, and cross-file validations pass.
- Result: `CP-007 — Phase 2B Preparation Complete` is internally consistent and `PASS`. Work stops pending explicit Phase 2B Data Authoring authorization; training remains separately unauthorized.

## EV-017 — CP-008 Phase 2B candidate-corpus authoring

- Date: 2026-08-23
- Scope: data authoring and preflight only. The authoring utility imports only Python standard-library modules and records `nli_model_loaded=false`, `inference_run=false`, `lora_training_run=false`, `adapter_checkpoint_created=false`, and `production_behavior_changed=false`. No model, inference, training, adapter, checkpoint promotion, scoring, threshold, retrieval, Vision, Audio, or Fusion change occurred.
- Approved source: `InterviewIQ_AI/nlp/interview-iq-fusion-handoff/data/refdocs/reference_docs_250_FINAL_v1.json`, SHA-256 `BA062768EB02C6DBE16D90024C30B075AF98F85D08B9E946BB26862AAB250F07`. Authoring uses its `documents[].question`, canonical `chunks`, and `key_points`. The separately configured `data/questions/questions_250.json` is absent, so no source claim is made for it.
- Corpus inventory: 600 unique candidate cases from 50 source questions across DA 13, DS 13, CS 12, and SE 12; all CP-005 protected question IDs plus legacy evaluation ID `DS-014` are excluded. Every case has the requested `case_id`, `premise`, `hypothesis`, `label`, `language_style`, `difficulty_type`, `source`, and `rationale`, plus split, pair-group, semantic-family, and technical-domain controls.
- Split: 480 train cases from 40 complete question IDs and 120 dev cases from 10 complete question IDs. Question-ID overlap, semantic-family overlap, and pair-group overlap are all zero.
- Labels: exactly 200 entailment, 200 contradiction, and 200 neutral.
- Styles: exactly 150 MSA, 150 Egyptian Arabic, 180 Arabic/English code-switch, 60 Arabic transliteration variants, and 60 English diagnostics.
- Difficulties: exactly 180 paraphrase entailment, 20 domain-entailment preservation, 110 near-neighbor contradiction, 90 direct contradiction, 120 technical neutral, and 80 semantically adjacent neutral. All 600 records are technical-domain cases, exceeding the minimum of 360.
- Quality process: targeted spot-checking found and corrected a small set of awkward or insufficiently definite near-neighbor mutations before final freezing. Broad corpus rewriting was avoided. Two consecutive final generations produced identical hashes.
- Review boundary: all 600 are AI-authored candidates. Review-ledger summary is human approved `0`, human review pending `600`, ambiguity flagged `190`, and accepted for training `0`. Every record requires two independent qualified reviewers and adjudication on disagreement or ambiguity. The corpus is explicitly `training_ready=false`.
- Frozen artifacts and SHA-256: corpus `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`; review ledger `676B20BBA54D7D7DAF3A1DE7386871324137CB28BBAAFFDF93A6B0792828FDA3`; split manifest `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`; preflight validation `3FFCAA422B135F2390F23A1450EC8D54237D68DDC30B438CAB15C8924C3A790B`; quality report `F1E0A8F3C3F1E5D41C01EAAE5EAF591EAD273E4F8880F142D2CFB37C8D2E268F`; deterministic authoring utility `A7A9D30BF1B49F2A5D7AED81602C05D4AA071AF53C955EAFE354BCC074AAF9E8`.

## EV-018 — CP-008 corpus preflight and checkpoint validation

- Date: 2026-08-23
- Integrated preflight status is `PARTIAL_PASS_HUMAN_REVIEW_REQUIRED`: structural and exact leakage controls pass; human semantic review does not pass; `training_ready=false`.
- CP-005 boundary: frozen evaluation SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18` and `do_not_train=true` are verified. Protected question-ID hits, evaluation-premise hits, evaluation-hypothesis hits, and normalized evaluation-pair hits are all zero.
- Conservative semantic screen: token-Jaccard threshold is `0.8`; hits are zero and maximum observed similarity is `0.346154`. This automated screen does not replace the mandatory two-reviewer semantic-family gate.
- Duplicate and split integrity: 600 unique case IDs, 600 unique normalized premise/hypothesis pairs, zero duplicate pair count, and zero cross-split question IDs, semantic families, or pair groups.
- Provenance: all 600 records resolve to the frozen reference corpus; unresolved/noncanonical count is zero. The missing standalone question-bank path is explicitly reported rather than silently substituted.
- Independent PowerShell audit parses the final JSON artifacts and independently recomputes the 600 record count, all required fields, unique IDs/pairs, exact label/style/difficulty distributions, 480/120 split, 50 question IDs, frozen hashes, and closed review gate. Result: `PASS` for structure and exact leakage controls.
- Git/authorization boundary: staged diff remains empty. No model was loaded, no inference or LoRA training was run, no adapter checkpoint exists, and no production behavior changed.
- Checkpoint result: `CP-008 — Phase 2B Training Corpus Created` is recorded with task status `AWAITING_TRAINING_AUTHORIZATION`, but it is a deliberate `PARTIAL PASS` pending mandatory human review. Resuming CP-008 does not authorize training. Exact next step is two independent reviews and adjudication, minimal corrections/exclusions, renewed preflight, and new frozen hashes before a separate training authorization can be requested.

## EV-019 — External human-review attestation and Phase 2C authorization

- Date: 2026-08-23
- The user explicitly clarified that the Phase 2B review occurred externally: a human reviewer manually checked all 600 examples, two review passes completed, disagreements were adjudicated, ambiguous cases were resolved or excluded, and the corpus was approved for training.
- The user explicitly confirmed no dataset record, label, corpus file, split, or project file changed during review. The frozen CP-008 corpus SHA-256 remains `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`; split SHA-256 remains `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`; review-ledger SHA-256 remains `676B20BBA54D7D7DAF3A1DE7386871324137CB28BBAAFFDF93A6B0792828FDA3`.
- The original CP-008 ledger is preserved rather than rewritten with identities or per-case comments that were not supplied. The separate durable attestation is `results/nli_phase2c_training_cp009/external_human_review_attestation_v1.json`, SHA-256 `408B040F252F2E61252F867C744AB346BB112D8D73190E0B173BC091060CB64D`.
- Authorization permits exactly one LoRA adapter on `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli@8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` using the frozen 480/120 corpus split, followed by one CP-005 evaluation. No second configuration, production promotion, production pipeline/scoring/threshold/retrieval/Fusion change, or deployment is authorized.
- State transition: CP-008 remains the last verified checkpoint while Phase 2C preflight/training is in progress. CP-009 may be created only after real training and evaluation complete.

## EV-020 — CP-009 immutable preflight and one real LoRA training run

- Date: 2026-08-23
- Human-review evidence: external user attestation SHA-256 `408B040F252F2E61252F867C744AB346BB112D8D73190E0B173BC091060CB64D` approves all 600 unchanged records after two manual passes and adjudication. Reviewer identities/per-case comments were not supplied and were not invented.
- Frozen inputs: corpus SHA `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`; split SHA `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`; CP-005 SHA `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`; base/tokenizer revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`.
- Preflight PASS independently checks 600 records, 480/120 complete-question split, 200/200/200 labels, unique IDs/pairs, zero CP-005 question/premise/hypothesis/pair overlap, zero train/dev question/family/group overlap, all pinned snapshot-file hashes, tokenizer fingerprint, E/N/C mapping, available CPU/memory/disk, and absent adapter output. Maximum untruncated training pair length is 126/256 with zero truncation and zero UNK.
- Exactly one configuration ran: LoRA r16, alpha32, query/value projections, dropout0.1, bias none, SEQ_CLS; lr `2e-4`; five epochs; seed42; max_length256; CPU/fp32; per-device batch4 with gradient accumulation4 for effective batch16; dynamic padding; CP-005 excluded from training/selection.
- The run completed 150 optimizer steps. Epoch train losses are `0.7177`, `0.1140`, `0.0348`, `0.0184`, `0.0091`; aggregate train loss is `0.1788166922`. Dev macro F1 is `0.991665` after epoch1 and `1.0` from epoch2 onward; best selected checkpoint is step60.
- Final selected-weight dev metrics are accuracy/macro-F1 `1.0/1.0`, eval loss `0.0134292`. Trainable parameters are `592,131 / 279,403,782 = 0.2119%`.
- Runtime: model load `2.061s`; training wall `862.211s`; sampled peak training RSS `2,877,673,472` bytes; process peak working set `2,877,677,568` bytes. CPU-only deterministic algorithms were enabled.
- Adapter artifacts: weights SHA `E5972EF2A75D29FE2FBFACE9B9F0F6F1502006A3C7DD167049969D759BB8AC6A`; config SHA `140CE9F7B179826B3D85F616AD41AEE10461091B0EB27991644DD9B4323526C9`; trainer state SHA `09B23A463AA01687CB465EB45E963A30B0246133FD42A8D63DC75F0D472A65AA`; tokenizer config SHA `395EB8AAB070D3597FEDF180A87FD9476E561C7A1E2609771B867127F0E1D35C`.
- Experiment artifacts: immutable manifest SHA `6E55057D089067CBFEEE26D6EE1E242415CDCE4B89CFEC063C6BB12DFBF37878`; preflight SHA `E36E75732E0CCE61ED17764BE70A2CF26129B4DE8D4CD3A4245712DA52E6C02F`; training metrics SHA `7F751A8CEC937D303FE2B64DFC34720461DD9F9E1FDB894580179BA0E3C3C240`; environment SHA `72E02A43CE8867933149946DA5172DCE1E26572AB4EEADA2F29C7AA9C685822F`; training log SHA `E941EA7EDD4F533A6A928C8996929DBA92960829F3A59DDE02F1C286860F7C6A`.
- PEFT attempted non-mutating remote `config.json` HEAD lookups while saving epoch/final adapters despite local model loading; restricted proxy rejected them and PEFT explicitly continued with the already loaded local config. Base weights/tokenizer were loaded with the pinned local revision, and all snapshot hashes had passed before training.

## EV-021 — CP-009 frozen CP-005 adapter evaluation and acceptance

- Date: 2026-08-23
- The adapter attached successfully to a freshly loaded pinned base in a separate CPU/fp32 offline process. Evaluation reused frozen CP-005 once with premise/hypothesis direction, E/N/C mapping, max_length256, batch8, deterministic settings, and no threshold. No baseline rerun was needed; the frozen CP-005 baseline artifact was reused.
- Adapter overall: `37/45 = 0.822222` accuracy; macro F1 `0.820639`; E/N/C F1 `0.846154/0.857143/0.758621`; confusion rows expected / columns predicted E,N,C `[[11,1,3],[0,15,0],[0,4,11]]`.
- Critical rates: false contradiction `3/15 = 20%` versus baseline `2/15`; false entailment `0/15` versus baseline `1/15`; neutral `15/15` versus baseline `14/15`; DA-017 `1/5` versus baseline `2/5`.
- DA-017 rows: `041 E→C` probabilities `0.004440/0.007463/0.988097` FAIL; `042 E→C` `0.002799/0.032130/0.965071` FAIL; `043 C→N` `0.127469/0.672373/0.200158` FAIL; `044 N→N` `0.007729/0.978797/0.013473` PASS; `045 E→C` `0.000785/0.015610/0.983605` FAIL.
- Changed predictions: fixes `NLI-EVAL-007` and `035`; new regressions on baseline-correct `037` and `041`; `043` moves from false entailment to false neutral. Net correct count is unchanged.
- Language accuracy: code-switch 75%, MSA 90%, transliteration 100%, Egyptian 88.89%, English diagnostic 66.67%. Key difficulty accuracy: direct contradiction 40%, natural paraphrase entailment 57.14%, near-neighbor contradiction 80%, negation contradiction 100%, adjacent neutral 100%.
- Evaluation resources: `3.7074s` for 45 cases, `82.3858ms/case`, sampled lifecycle peak RSS `2,185,248,768` bytes, process peak working set `2,221,363,200` bytes. Both latency and memory gates pass.
- Acceptance PASS only for false entailment, neutral correctness/F1, latency, memory, and adapter attachment. It FAILS ≥39 correct, accuracy, macro F1, minimum class F1, zero false contradiction, DA-017 5/5, zero baseline-correct regressions, and ≥70% supported-slice accuracy. Overall: `FAIL_DO_NOT_PROMOTE`.
- Comparison SHA is `207B9AD75416F9B0A77680352D7A96C9D2D8685271C4F6333BCA050D19AC26D1`; adapter-evaluation SHA `C05B1FEFDC3160C6D3D2695125B1A3E71A2C6D7462E7844C659D38C9B7C5005F`; report SHA `7863A12552945B299191E9FBD9349C7686362CAFBD61879AC5C07D7719AC1C69`; artifact-hash manifest SHA `35874579D99CC1EC78BE4342A60CAFA08CEA6DFE247AEE6CE226203426DF3B10`; completed-validation SHA `79FA254D87F2E0F4163DC9E924FED5AE89AA659CEDDEEA4E23BA2F52DA6AEE97`.
- Independent completed-artifact audit PASS recomputes 45 rows, probability sums/argmax, 37 correct, confusion matrix, five epoch logs, 150 steps, LoRA config, adapter attachment, and every recorded file hash. Staged diff remains empty; no second adapter, promotion, or production mutation occurred.
- Interpretation: perfect internal dev with no frozen-held-out gain and new regressions is evidence of a generalization/data-authoring-template gap, not failed optimization. The adapter is preserved only as experiment evidence. Phase 2D diagnosis/design requires separate authorization; no further training starts.

## EV-022 — CP-010 LoRA failure diagnosis

- Date: 2026-08-23
- Scope: artifact-only analysis of frozen CP-005/CP-006/CP-009 evidence and the unchanged 600-record corpus. No model was loaded, no inference/training ran, no dataset or adapter changed, and no production/scoring/threshold/retrieval/Fusion action occurred.
- Frozen inputs verified: CP-005 dataset SHA `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`; corpus SHA `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`; split SHA `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`; baseline result SHA `7FAFA2F8EF8B1C5BA70AD2AAED371A7780557F7D05E6690C7E8468234495BFC6`; adapter evaluation SHA `C05B1FEFDC3160C6D3D2695125B1A3E71A2C6D7462E7844C659D38C9B7C5005F`.
- Generalization gap: training and CP-005 are each exactly label-balanced, training/evaluation question overlap is zero, and exact leakage controls remain valid. Those conditions reject label imbalance and record leakage but do not establish a representative internal dev set.
- Generator/template evidence: all 50 questions use the same 12-record schedule and helper functions in both splits. Exclusive label markers cover `170/200` E, `150/200` C, and `180/200` N, with train/dev rates E `85%/85%`, C `75%/75%`, N `89.4%/92.5%`. `semantic_family_ids` contain question families only and cannot detect shared template/transformation families.
- Difficulty evidence: `153/180` `paraphrase_entailment` records retain the entire normalized premise; all 90 direct contradictions have explicit negation markers; 180/200 neutral hypotheses announce a separate/independent fact. Mean premise/hypothesis token-Jaccard is E `0.765996`, C `0.671227`, N `0.011000`.
- Concept evidence: the 600 records contain zero JOIN-term pairs. Numeric Egyptian/code-switch coverage mostly consists of deterministic wrappers around canonical text, not natural independent formulations of relational semantics.
- Independent all-case transition computation: 2 fixed (`007`, `035`), 2 new regressions (`037`, `041`), 6 unchanged failures (`009`, `018`, `023`, `042`, `043`, `045`), and 35 unchanged correct. `043` changes false E→false N. Predicted E/N/C counts move `15/18/12 -> 11/20/14`; mean output probability shifts E `-0.076967`, N `+0.042667`, C `+0.034300`.
- Boundary interpretation: entailment recall worsens `13/15 -> 11/15`; contradiction recall improves `10/15 -> 11/15` while precision falls `10/12 -> 11/14`; false contradictions worsen `2 -> 3`. Average entropy rises, so overconfidence is not global, but mean max-confidence on errors rises `0.830853 -> 0.867238` and critical false contradictions remain extreme.
- DA-017: `041` newly regresses E→C at `0.988097 C`; `042` remains E→C at `0.965071 C`; `043` moves C from false E to false N; `044` remains easy N; `045` remains E→C at `0.983605 C`. Result falls `2/5 -> 1/5`.
- Root-cause ranking: shared authoring-template shortcuts, natural-reasoning mismatch, contradiction-boundary over-broadening, and absent JOIN/natural dialectal paraphrase coverage are high confidence; base-family capacity/calibration is medium. Label imbalance, exact CP-005 leakage, and failed optimization are rejected by evidence.
- Decision: current adapter remains `REJECTED_FOR_PROMOTION_EVALUATION_ONLY`; LoRA is `PAUSE_CONDITIONAL_NOT_ABANDONED`. Do not repeat the current corpus/config. A semantic-verifier/cascade is a controlled future comparison candidate, not a selected production architecture.
- Artifacts: `results/nli_phase2d_diagnosis_cp010/lora_failure_diagnosis_v1.json` SHA `C2BC1BC9CB153A40E367F063E865AAE4D2E2A3D017E154960469F89B7CCB20C9`; `lora_failure_diagnosis_v1.md` SHA `29BCEDCE48C967ED21F41FB2D88AE2322DEC071E986DE1FC716EF60CA16EF7AA`; analysis utility SHA `13E74A6FFD09DE5196D49028FD9ED0405B646575D9279C08119B856AA10FA9B6`.
- Exact next step, only if authorized: Phase 2E design-only specification of a template-independent corpus/diagnostic protocol and a pre-registered revised-LoRA versus semantic-verifier/cascade comparison. No data authoring, training, CP-005 tuning, or production change begins.

## EV-023 — CP-010 diagnosis and checkpoint validation

- Date: 2026-08-23
- Independent validator result: `PASS`; artifact SHA-256 `E9D17F553004847AA92E33B8994D1871B750A397CB83C39889423C440EF48880`.
- Frozen dependency audit: all eight CP-005/CP-006/CP-009/corpus/split hashes match their recorded identities; strict JSON and UTF-8 parse; CP-005 `do_not_train` and the no-action diagnosis scope remain intact.
- Independent corpus recomputation: 600 records, balanced `200/200/200`; exclusive marker counts E/C/N `170/150/180`; nominal paraphrase containment `153/180`; JOIN-term records zero.
- Independent transition recomputation: fixed `007/035`, regressions `037/041`, unchanged failures `009/018/023/042/043/045`, unchanged correct 35; predicted E/N/C counts baseline `15/18/12`, LoRA `11/20/14`.
- Report audit: all-case table, generalization analysis, DA-017 deep analysis, root-cause ranking, prerequisites, approach decision, and exact next step are present. Machine evidence SHA is `C2BC1BC9CB153A40E367F063E865AAE4D2E2A3D017E154960469F89B7CCB20C9`; report SHA is `29BCEDCE48C967ED21F41FB2D88AE2322DEC071E986DE1FC716EF60CA16EF7AA`; analysis utility SHA is `13E74A6FFD09DE5196D49028FD9ED0405B646575D9279C08119B856AA10FA9B6`; validation utility SHA is `AFCC2473A0EB86893C01B02B390FDB259EC0D3D38374086D44FEBCEB6B72E09E`.
- External-memory audit: CP-010 markers agree across `EXECUTION_STATE.json`, `CURRENT_TASK.md`, `PROJECT_MEMORY.md`, `KNOWN_ISSUES.md`, and EV-022. Task is complete, `tests_remaining` is empty, and next step is Phase 2E design-only pending explicit authorization.
- Authorization boundary: no model/inference/training/data/adapter/production action occurred. The CP-009 adapter remains evaluation-only and rejected for promotion.

## EV-024 — CP-011 Fusion Analysis frontend redesign and live validation

- Date: 2026-08-24
- Scope: frontend-only redesign of `frontend/src/pages/FusionTest.jsx` and `frontend/src/components/AIReportSummary.jsx`. No backend source, API contract, model, NLP pipeline, database schema, scoring, threshold, retrieval, or Fusion logic was modified.
- Dynamic component evidence: `FusionTest` passes the unchanged response as `<AIReportSummary result={result} />`. The summary derives presentation-only technical, communication, visual, and overall labels while rendering no raw score values.
- Hierarchy evidence: browser QA with the real DA-017 response shows `Interview Assessment` and `Overall performance — Needs Improvement` in the dominant hero region, followed by Candidate Strengths and Areas To Improve. `Detailed Evaluation` contains exactly Technical Answer, Communication, and Visual Evidence cards.
- Clutter-removal evidence: the rendered report contains none of `Model classifications`, `Audio model output`, `Vision model output`, `Engineering status`, `/100`, `model_confidence`, or `predicted_class`. Warnings/limitations and transcript remain in `FusionTest`.
- Build evidence: `npm.cmd run build` PASS under Vite `5.4.21`; 2,534 modules transformed and output emitted. The only warning is the existing `>500 kB` chunk-size advisory.
- Live same-video evidence: POSTing existing `test_videos/Video_—_Strong_Baseline_Visu.mp4` with `question_id=DA-017` to the unchanged `/api/interviews/analyze` endpoint returned HTTP `200` in `180.459942s`. The response has `status=success`, `question_id=DA-017`, a 207-character transcript, four warnings, and existing Vision/Audio/NLP/confidence/fusion sections.
- Browser route evidence: `/fusion-test` loads the existing question selector, video chooser, browser recording, and analyze control without an API-contract change.
- Validation-only response and preview files were kept outside the repository in the system temp directory; the temporary render script was removed.

## EV-025 — CP-011 checkpoint and repository-boundary validation

- Date: 2026-08-24
- PowerShell `ConvertFrom-Json` and Python `json.loads` both parse `EXECUTION_STATE.json`; Python strict UTF-8 reads find CP-011 in the state, current task, project memory, and evidence ledger.
- State audit PASS: active task `TASK-FUSION-REPORT-UI-001`, status `VERIFIED_COMPLETE_FRONTEND_ONLY`, last/technical checkpoint `CP-011`, unique completed-step IDs, zero remaining tests, exact next step present, and exactly two product files recorded for this task.
- Scoped `git diff --check` PASS for the two frontend files and four memory files; cached/staged diff remains empty. The pre-existing dirty repository outside this task was preserved.
- Final source SHA-256: `frontend/src/pages/FusionTest.jsx` = `DD003FC9078D5A7BF080E10B5EF0548A9AEE7CBB5FFA2B4300372CB0DA92CD03`; `frontend/src/components/AIReportSummary.jsx` = `7B5AD992600A93487563C6439F3D567CB78A9D4E26DA025AD0EE404224CE52A3`.
- Source audit confirms `<AIReportSummary result={result} />` is the first result child (line 212), ahead of warnings (line 217), and removed clutter labels are absent from `FusionTest`. The temporary validation script is absent.
- Final production build PASS after all source edits: 2,534 modules transformed; only the existing large-chunk advisory remains.

## EV-026 — CP-012 dynamic report refinement and variation validation

- Date: 2026-08-24
- Scope: frontend-only refinement of `frontend/src/components/AIReportSummary.jsx` and `frontend/src/pages/FusionTest.jsx`. No backend/API/database/model/NLP/scoring/threshold/retrieval/Fusion code or configuration changed.
- Interpretation implementation: `getTechnicalNarrative`, `getCommunicationNarrative`, `getVisualEvidenceNarrative`, and `getRecommendations` return structured level/summary/recommendation evidence. Overall presentation excludes limited visual evidence and uses `Strong Performance`, `Moderate Performance`, or `Developing`.
- Real DA-017 result reused from verified CP-011 because the endpoint contract and all analysis dependencies are unchanged. It contains technical `0.139761`, vocal `80.92`, speaking rate `137.255`, pause control `1.0`, volume stability `0.5336`, speech continuity `0.5053`, visual `20.0148`, and three sufficient source windows.
- Real-result interpretation: overall `Developing`; candidate strengths = balanced pace and effective pauses; development areas = direct definition/technical structure plus smoother transitions; Technical Answer `Developing`; Communication `Moderate`; Visual Evidence Analysis `Limited Evidence`. Three windows trigger short-sample wording even though the backend minimum sufficiency flag is true.
- Four-profile in-memory SSR validation PASS using the actual component: real DA-017, strong, fast-delivery, and unstable-delivery profiles render four distinct HTML reports. Strong produces `Strong Performance` and no priority development area; fast produces `Moderate Performance` with speed-specific advice; unstable produces flow-specific advice and limited visual evidence.
- Forbidden narrative audit PASS: no successful-capture, pipeline-completed, fixed camera-position, fixed lighting, `Needs Improvement`, model-classification, predicted-class, or `/100` text exists in the two report source files.
- Final source SHA-256 before memory-only closeout: `FusionTest.jsx` = `54AB177588E4D88666D3774D182B1DD44ADB9A2B43CB33F0BE37B51A2AFDCE27`; `AIReportSummary.jsx` = `2EDA66FB300EBFA51884315632959FF3C85B92776027D14AA626983A0A7B0431`.

## EV-027 — CP-012 build, browser, and checkpoint validation

- Date: 2026-08-24
- Final production build PASS: Vite `5.4.21`, 2,534 modules transformed, bundle emitted; only the existing `>500 kB` advisory remains.
- In-app browser real-response QA PASS: the first viewport visibly contains `AI Interview Evaluation Report`, candidate-level summary, dominant `Developing` verdict, Candidate Strengths, and Development Areas. Detailed cards use Technical Answer, Communication, and Visual Evidence Analysis.
- Alternate browser QA PASS: the fast profile renders `Moderate Performance` with relatively-fast-pace explanation and speed-specific recommendation; the strong profile renders `Strong Performance`, three candidate strengths, and no priority development area.
- `/fusion-test` route QA PASS: interviewer-facing workspace text and unchanged question/video/upload/record/analyze controls render; the selected question loads after the existing request; browser console error list is empty.
- Temporary SSR script was deleted, validation tabs were finalized, and the task-owned preview server was stopped. The preserved response and generated static previews remain only in the system temp directory, outside the repository.
- Checkpoint audit PASS: `EXECUTION_STATE.json` parses with CP-012 as last/technical checkpoint; completed step IDs are unique; `tests_remaining` is empty; CP-012 markers agree across state/task/memory/ledger; both source hashes match EV-026; scoped `git diff --check` passes; staged diff is empty; temporary script and port 8899 server are absent.

## EV-028 — CP-013 semantic hierarchy implementation and live DA-004 validation

- Date: 2026-08-24
- Scope: frontend-only refinement. Net product change is `frontend/src/components/AIReportSummary.jsx`; `frontend/src/pages/FusionTest.jsx` was inspected and its existing upload/record/analyze contract was preserved. No backend source, API contract, database, model, NLP, Audio, Vision, scoring, threshold, retrieval, or Fusion behavior changed.
- Implementation evidence: `getOverallAssessment`, `getTechnicalAssessment`, `getCommunicationAssessment`, `getVisualEvidenceAssessment`, and `getDevelopmentRecommendations` each return `level`, `color`, `summary`, and `recommendation`. Semantic colors map Strong to green, Moderate to amber, Developing to blue, and Limited Evidence to slate.
- Hero evidence: `AI Interview Evaluation Report` appears once. `Candidate assessment summary`, the generic overall-summary paragraph, and the hero explanatory footnote are absent. The title is followed immediately by a semantic overall-performance badge.
- Dynamic SSR validation PASS: Strong, Moderate, and Developing profiles render expected green/amber/blue overall classes and three distinct Development Areas outputs. Raw/debug labels, `/100`, and the removed kicker remain absent.
- Live DA-004 evidence: the preserved ten-second source MP4 SHA-256 is `091EE35B8FACC49062422970B926F1EC95FDF426EF1EC2ECC8D94A11E73B1A9A`. POST to the unchanged `/api/interviews/analyze` contract with `question_id=DA-004` returned HTTP 200 in 199.86 seconds. The response reports `status=success`, valid question alignment, a transcript, four warnings, and all Vision/Audio/NLP/confidence/fusion sections.
- Actual DA-004 presentation: amber `Moderate Performance`; three candidate strengths; one technical development priority; Technical Answer `Moderate`; Communication `Strong`; Visual Evidence Analysis `Limited Evidence` because the ten-second response provides three visual windows.
- Browser QA PASS at 1440×900: title computed size 48px, verdict 30px, amber verdict color `rgb(253, 230, 138)`, hero height 252px, followed by Candidate Strengths and Development Areas. The clean `/fusion-test` route has one question selector, one upload input, one analyze button, and no console errors.
- Validation cleanup: the endpoint-created upload duplicate was removed only after its SHA-256 matched the preserved source; the source remains. The response is retained only in the system temp directory and no preview fixture remains in source.

## EV-029 — CP-013 final build and repository-boundary validation

- Date: 2026-08-24
- Final production build PASS: Vite `5.4.21`, 2,534 modules transformed, output emitted; only the existing `>500 kB` advisory remains.
- Final source SHA-256: `frontend/src/components/AIReportSummary.jsx` = `08B6969180044857E4996950E0B17E335466CFCF8CADA4166DC7EB6D7B09B6BF`; preserved `frontend/src/pages/FusionTest.jsx` = `8567D8B6DB8B969AEF970AF6B7AF04D0BA493A6F6FD4263C1018F7E2839049CE`.
- Scoped `git diff --check` PASS; staged diff remains empty. The pre-existing dirty repository outside this task was preserved.
- Source audit confirms no `CP013_DA004_PREVIEW`, `cp013-preview`, duplicate kicker, generic hero summary binding, or CP-012 helper names remain. Final 25-check audit PASS verifies strict JSON, CP-013 task/checkpoint/step markers, unique step IDs, empty `tests_remaining`, exact next step/resume instruction, EV-028/EV-029 presence, all five helper names, semantic palette, both source hashes, validation-upload cleanup, and preserved source video.

## EV-030 — CP-014 Fusion report terminology update and validation

- Date: 2026-08-24
- Scope: presentation-only edit to `frontend/src/components/AIReportSummary.jsx`. No dynamic assessment function, generated text, threshold, scoring, result contract, backend/API/database, NLP, Audio, Vision, or Fusion behavior changed.
- UI change: the first detailed card is `Content Answer`; Content Answer, Communication, and Visual Evidence Analysis all display `DEVELOPMENT FOCUS` when their existing dynamic recommendation is present.
- SSR validation PASS: all three expected card titles render, `DEVELOPMENT FOCUS` appears exactly three times, and `Technical Answer`, `Suggested focus`, and `Evidence note` are absent.
- Production build PASS: Vite `5.4.21` transformed 2,534 modules and emitted the bundle; only the existing `>500 kB` advisory remains.
- Final `AIReportSummary.jsx` SHA-256: `6496E1C838FCE5F46384392DF83F1520B770490CE0741EB86227785D4904D1FA`.
- Scoped `git diff --check` PASS and staged diff is empty. The pre-existing dirty repository outside this task was preserved.

## EV-031 — CP-015 dynamic evaluation status text colors

- Date: 2026-08-24
- Scope: status-text styling only in `frontend/src/components/AIReportSummary.jsx`. No title, status label, narrative, recommendation, threshold, scoring, result contract, icon/card styling, backend/API/database, NLP, Audio, Vision, or Fusion behavior changed.
- Implementation: `getEvaluationStatusTextColor` receives semantic `dimension`, dynamic `level`, and the existing fallback color. It never compares card titles or card positions.
- Content Answer SSR: Developing and Limited Evidence render `text-rose-300`; Moderate renders `text-amber-200`; Strong renders `text-emerald-300`.
- Communication SSR: Moderate renders `text-amber-200`.
- Visual Evidence Analysis SSR: Limited Evidence renders `text-blue-200`.
- Isolation evidence: Content Developing retains the pre-existing blue icon class while its status text is rose; Visual Limited Evidence retains the pre-existing slate icon class while its status text is blue.
- Production build PASS: Vite `5.4.21` transformed 2,534 modules and emitted the bundle; only the existing `>500 kB` advisory remains.
- Final `AIReportSummary.jsx` SHA-256: `ACC7FA4D9E3BD7FCE859D5D30AD3D1F1EE7F0C7D96286F7CB4906712555DDF6E`.
- Scoped `git diff --check` PASS and staged diff is empty. The pre-existing dirty repository outside this task was preserved.

## EV-032 — CP-016 collapsible Evaluation Notes interaction

- Date: 2026-08-24
- Scope: frontend-only presentation change to `frontend/src/pages/FusionTest.jsx`. No warning content/source, backend/API/database, scoring, NLP, Audio, Vision, or Fusion logic changed.
- Implementation: the conditional `result.warnings?.length > 0` boundary remains. Its content is now a native `<details data-testid="evaluation-notes">` without an `open` attribute, with a `<summary>` titled `Evaluation Notes` and a `ChevronDown` using `group-open:rotate-180`.
- Collapsed-state browser evidence: `open` attribute is null and both dynamic fixture messages are not visible; the snapshot exposes only `Evaluation Notes` for the block.
- Expanded-state browser evidence: after one unique-summary click, `open=""` and both distinct `result.warnings` messages are visible. After a second click, `open` returns to null and both messages are hidden.
- Clean-route evidence: after removing the temporary fixture and loading `/fusion-test`, no Evaluation Notes block is synthesized without a result, one analyze button remains, and console error output is empty.
- Styling evidence: neutral `border-white/10`, `bg-white/[0.025]`, small gray note text, and compact spacing replace the dominant yellow alert surface while preserving the existing dark glass language.
- Production build PASS: Vite `5.4.21` transformed 2,534 modules and emitted the bundle; only the existing `>500 kB` advisory remains.
- Final `FusionTest.jsx` SHA-256: `8D4F4F51FA6EB041BE68AE83FBECDEF4C991C6F582AD90F16D3273A61C07474C`.
- Source audit confirms `Warnings and limitations`, `CP016_NOTES_PREVIEW`, `cp016-preview`, and fixture strings are absent. Scoped `git diff --check` passes and staged diff is empty.

## EV-033 — CP-017 THEQA frontend branding verification

- Date: 2026-08-24
- Scope: frontend presentation only; no backend, API, database, internal variable/package/folder identifier, scoring, NLP, Audio, Vision, retrieval, or Fusion change.
- Changed product files and SHA-256:
  - `frontend/index.html`: `2C370771959F839670773970DFE0926E81E2B76B5D7905847B4631652D5CD2D3`
  - `frontend/src/components/Navbar.jsx`: `8D223BB37F64F709BD0C6FEB846A769F9F6F1F5122A97D1A69C1ECDE143E7597`
  - `frontend/src/pages/Landing.jsx`: `C6C2BF6B8661A5BACDE46667DE71F5C441A20F68DE5F7048241B545924700030`
  - `frontend/src/routes/guards.jsx`: `3EBD86CEC349A750A0FBE952D97B3B32BE2BB8B7D133F0D2CA520276D2640841`
- UI-source audit: case-insensitive search across `.jsx`, `.js`, `.html`, `.css`, `.ts`, and `.tsx` finds zero remaining `InterviewIQ` occurrences. The excluded package manifests retain only the required internal package name `interviewiq-frontend`.
- Built-bundle audit: zero `InterviewIQ` occurrences in `frontend/dist` after the production build.
- Build evidence: Vite 5.4.21 transformed 2,534 modules successfully; only the existing bundle-size advisory remains.
- Browser landing evidence: global navigation exposes `THEQA` and `AI Interview Assessment Platform`; the hero, landing body, CTA, and footer use the new brand. Visual review confirms the two-line navbar lockup remains readable in the existing dark glass style.
- Browser report-route evidence: `/fusion-test` inherits the new navbar identity; `document.title` equals `THEQA — AI Interview Assessment Platform`; console error log is empty.
- Result: `PASS`; checkpoint `CP-017` is verified.

## EV-034 — CP-018 landing statistics removal and alignment

- Date: 2026-08-24
- Scope: `frontend/src/pages/Landing.jsx` presentation only; no backend, API, database, model, scoring, NLP, Audio, Vision, retrieval, or Fusion change.
- Implementation: removed the single `{ label: 'Score Dimensions', value: '10', suffix: '+' }` record. The remaining data records are byte-for-text unchanged. The grid changed from `max-w-4xl grid-cols-2 md:grid-cols-4 gap-6` to centered `max-w-3xl grid-cols-3 gap-4 sm:gap-6`.
- Source evidence: `Score Dimensions` is absent; `AI Modules`, `Questions Bank`, and `Interview Tracks` each remain once in the statistics data with values `3`, `30+`, and `6`.
- Browser DOM evidence: exactly the three required statistic labels/values render; `Score Dimensions` count is zero and `10+` count is zero.
- Browser layout evidence at 1280×720: three cells are 240px wide with centers at 373.5, 637.5, and 901.5px, producing equal 264px gaps. Screenshot review confirms a centered, balanced three-item row.
- Browser console errors: zero.
- Production build: Vite 5.4.21 transformed 2,534 modules successfully; only the existing bundle-size advisory remains.
- Final `frontend/src/pages/Landing.jsx` SHA-256: `5EE7A763C500BDB06029ADAE74CF76CB981454AF228781801A4BAD7997DB4EE2`.
- Result: `PASS`; checkpoint `CP-018` is verified.

## EV-035 — CP-019 landing CTA behavior verification

- Date: 2026-08-25
- Scope: `frontend/src/components/Navbar.jsx` and `frontend/src/pages/Landing.jsx` CTA presentation/navigation only; no authentication, backend, API, assessment, report, database, model, scoring, NLP, Audio, Vision, retrieval, or Fusion logic change.
- Source evidence: desktop and mobile navbar links both read `Sign Up` with `to="/register"`; the guest hero primary link reads `Direct Assessment` with `to="/fusion-test"`; `Get Started` and `Start Free Interview` are absent from the affected components. The authenticated dashboard CTA and lower `Create Free Account` link remain unchanged.
- Browser navbar evidence: one visible `Sign Up` link has `href="/register"`; clicking it opens `http://127.0.0.1:5174/register`, where the `Create Account` heading and account-creation form render.
- Browser hero evidence: one visible `Direct Assessment` link has `href="/fusion-test"`; clicking it opens `http://127.0.0.1:5174/fusion-test`, where the `Fusion Analysis` workspace, technical-question selector, video input, recording control, and disabled pre-input analyze control render.
- Browser console errors: zero.
- Production build: Vite 5.4.21 transformed 2,534 modules successfully; only the existing bundle-size advisory remains.
- Final SHA-256 values: `frontend/src/components/Navbar.jsx` `380FF9A92B6A3443AC69106A6D53F5552418B478900A7A84E6B850C573ED2AC2`; `frontend/src/pages/Landing.jsx` `1CE32D7D0BAA7D845F8E9D9E5B601B5C333CA8DF4975F39931466F204B86E02A`.
- Result: `PASS`; checkpoint `CP-019` is verified.

## EV-036 — CP-020 authentication input icon alignment verification

- Date: 2026-08-25
- Scope: `frontend/src/pages/Login.jsx` and `frontend/src/pages/Register.jsx` presentation only; no authentication handler, backend, API, route, validation, navigation, or theme change.
- Baseline browser evidence: all six icon-bearing auth inputs computed to 16px left padding. Each icon occupied the 14px-to-30px horizontal interval, so the placeholder/value start at 16px overlapped the icon by 14px. Icons were already vertically centered within 0.01px.
- Implementation: changed only the six input class tokens from `input-field pl-10` to `input-field !pl-11`, making 44px left padding authoritative against the shared CSS padding shorthand. Existing 16px icon declarations and `absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-500` classes remain unchanged.
- Browser Sign In evidence: both email and password inputs compute to 44px left padding, 14px post-icon gap, 16×16 icons, and 0.0078125px vertical-center delta in empty and entered-value states; entered-value state was confirmed by `:placeholder-shown=false` for both controls.
- Browser Create Account evidence: name, email, password, and confirmation inputs compute to the same 44px padding, 14px gap, 16×16 icon size, and 0.0078125px vertical-center delta before and after sample entry; rendered password-strength feedback confirms controlled input state updated.
- Browser console errors: zero on both authentication routes.
- Source boundary: zero-context Git diff contains exactly six class-token substitutions in the two authorized components. Form state, submission handlers, error handling, API calls, navigation, routes, labels, and dark-theme classes are unchanged.
- Production build: Vite 5.4.21 transformed 2,534 modules successfully; only the existing bundle-size advisory remains.
- Final SHA-256 values: `frontend/src/pages/Login.jsx` `28526B0778890EDCBE01C063D59B8E561172521589075700ACDC59334FA6336C`; `frontend/src/pages/Register.jsx` `0129E1C59A5574BE51C4485E0F0F697FC1CCF01177655F55D9935B67143AAFB9`.
- Result: `PASS`; checkpoint `CP-020` is verified.
