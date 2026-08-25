# InterviewIQ Project Memory

This file stores durable, high-signal knowledge. Exact execution position lives in `EXECUTION_STATE.json`; current scope lives in `CURRENT_TASK.md`; reasons live in `DECISIONS.md`.

## Durable architecture knowledge

- InterviewIQ is a long-running multimodal system whose target is evidence-first Late Fusion.
- The repository currently has three distinct execution paths: a persisted per-question candidate path, a real filesystem-only Fusion harness, and a legacy persisted mock path. Their outputs and formulas are not interchangeable.
- The candidate path currently persists real Audio/ASR/content analysis but not real Vision or real Late Fusion.
- The real Fusion harness runs Vision, Audio, and NLP independently from the same video. Delivery confidence combines only valid vocal-delivery and visual-behavioral scores; technical correctness remains separate.
- Structural alignment is strong at interview/question/segment/reference-document level, but shared temporal/entity alignment across Vision, ASR, and claims is not implemented.
- Report and History read persisted candidate-path data and must not trigger model reruns.
- The NLP reference corpus is a static 250-document JSON. Candidate questions require an explicit `nlp_reference_id` mapping; missing mappings yield a typed unavailable state.

## Verified milestones

### CP-020 — Authentication input icon alignment fixed (PASS; frontend only)

- Browser diagnosis proved `.input-field { padding: 12px 16px; }` overrode the existing component `pl-10`, leaving only 16px computed left padding and causing a measured 14px overlap with each 16px icon.
- The two Sign In inputs and four Create Account inputs now use authoritative 44px left padding, producing a 14px clear gap after each icon. The icon size, color, position, and vertical-centering classes are byte-for-text unchanged.
- Placeholder and entered-value measurements confirm the same spacing on all six inputs; icon and input vertical centers differ by less than 0.01px; both auth routes have zero console errors.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). Final SHA-256 values: `Login.jsx` `28526B0778890EDCBE01C063D59B8E561172521589075700ACDC59334FA6336C`; `Register.jsx` `0129E1C59A5574BE51C4485E0F0F697FC1CCF01177655F55D9935B67143AAFB9`.
- Net product change is exactly six class-token substitutions in `frontend/src/pages/Login.jsx` and `frontend/src/pages/Register.jsx`. Authentication logic, backend, APIs, routes, theme styling, and CP-010/KI-001 are unchanged.

### CP-019 — Landing CTA behavior updated (PASS; frontend only)

- The guest navbar CTA reads `Sign Up` in desktop and mobile navigation while retaining the existing `/register` account-creation route.
- The guest hero primary CTA reads `Direct Assessment` and routes to the existing standalone `/fusion-test` assessment page. Authenticated dashboard routing and the lower account-creation CTA are unchanged.
- Focused source assertions, live link-click navigation, destination-content checks, zero browser console errors, and the production Vite build all pass.
- Final SHA-256 values: `Navbar.jsx` `380FF9A92B6A3443AC69106A6D53F5552418B478900A7A84E6B850C573ED2AC2`; `Landing.jsx` `1CE32D7D0BAA7D845F8E9D9E5B601B5C333CA8DF4975F39931466F204B86E02A`.
- Net product change is limited to `frontend/src/components/Navbar.jsx` and `frontend/src/pages/Landing.jsx`. Authentication, backend, APIs, assessment logic, report logic, and CP-010/KI-001 are unchanged.

### CP-018 — Landing Score Dimensions statistic removed (PASS; frontend only)

- The landing statistics section now contains exactly three unchanged items: `3 AI Modules`, `30+ Questions Bank`, and `6 Interview Tracks`. `10+ Score Dimensions` was removed with no replacement.
- The section uses a centered three-column `max-w-3xl` grid with responsive gaps. Browser measurement at 1280×720 confirms equal 264px center spacing and visual review confirms balanced alignment.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only), browser console errors are empty, and the final `Landing.jsx` SHA-256 is `5EE7A763C500BDB06029ADAE74CF76CB981454AF228781801A4BAD7997DB4EE2`.
- Net product change is limited to `frontend/src/pages/Landing.jsx`. Backend/API/database/model/scoring behavior is unchanged. CP-010/KI-001 remains preserved.

### CP-017 — THEQA frontend branding rename complete (PASS; frontend only)

- The official user-facing product identity is now `THEQA` with subtitle `AI Interview Assessment Platform`.
- The global navbar, landing hero/copy/footer, loading screen, and browser title use the new identity. Dashboard and report routes inherit it through the unchanged global navbar.
- Source and built-bundle audits find no remaining case-insensitive `InterviewIQ` branding in frontend UI source or `frontend/dist`. The only frontend-source occurrences are the intentionally preserved internal package names in `package.json` and `package-lock.json`.
- Browser QA confirms the landing and `/fusion-test` report route show the new product name and exact subtitle; the document title is updated and console errors are empty.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). Net product change is limited to `frontend/index.html`, `frontend/src/components/Navbar.jsx`, `frontend/src/pages/Landing.jsx`, and `frontend/src/routes/guards.jsx`. Backend/API/database/scoring/NLP/Audio/Vision behavior is unchanged. CP-010/KI-001 remains preserved.

### CP-016 — Collapsible Evaluation Notes complete (PASS; frontend only)

- The former dynamic `Warnings and limitations` block is now a native `<details>` section titled `Evaluation Notes`, collapsed by default with a rotating chevron.
- The collapsed view exposes only the label and indicator. Expansion shows the unchanged dynamic `result.warnings`; a second activation hides them again.
- Styling is intentionally quieter than the main report: subtle neutral glass surface, smaller type, gray note text, and restrained bullets.
- Browser validation proves closed → open → closed state transitions, dynamic note visibility, and zero console errors. The final clean route retains the analyze control and no validation fixture.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). Net product change is limited to `frontend/src/pages/FusionTest.jsx`. Backend/API/scoring/NLP/Audio/Vision behavior is unchanged. CP-010/KI-001 remains preserved.

### CP-015 — Fusion evaluation status text colors complete (PASS; frontend only)

- Only status text colors inside the three detailed cards changed; titles, labels, narratives, recommendations, thresholds, result handling, icons, and card styling remain unchanged.
- A dimension-and-level presentation function avoids title/position matching. Content Strong/Moderate use green/amber; Content Developing or Limited Evidence uses rose/critical. Communication Moderate uses amber. Visual Limited Evidence uses blue to represent evidence limitation rather than candidate failure.
- Dynamic SSR validates Content Developing/Limited/Moderate/Strong, Communication Moderate, and Visual Limited Evidence. Icon-color assertions prove the override affects only status text.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). Net product change is limited to `frontend/src/components/AIReportSummary.jsx`. CP-010/KI-001 remains preserved.

### CP-014 — Fusion report card terminology update complete (PASS; frontend only)

- `Technical Answer` was renamed to `Content Answer` in the detailed evaluation grid.
- Content Answer, Communication, and Visual Evidence Analysis now share the exact lower label `DEVELOPMENT FOCUS`; the prior `Suggested focus` and visual-only `Evidence note` labels are removed.
- Dynamic assessment helpers, generated narratives/recommendations, thresholds, result handling, sections, and backend/API/model behavior are unchanged.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). SSR confirms the three card titles and exactly three `DEVELOPMENT FOCUS` labels.
- Net product change is limited to `frontend/src/components/AIReportSummary.jsx`. CP-010/KI-001 remains preserved.

### CP-013 — Final Fusion report UX refinement complete (PASS; frontend only)

- The report hero now contains only the large `AI Interview Evaluation Report` title and the immediate overall performance badge. The duplicated candidate-summary kicker, generic verdict paragraph, and hero footnote are removed.
- Presentation logic is explicit and dynamic: `getOverallAssessment`, `getTechnicalAssessment`, `getCommunicationAssessment`, `getVisualEvidenceAssessment`, and `getDevelopmentRecommendations` each return `level`, `color`, `summary`, and `recommendation` from the unchanged result object.
- Semantic colors are green for Strong, amber for Moderate/focused development, blue for Developing, and slate for Limited Evidence. Ordinary development is never presented as a critical red failure. Detailed-card level text follows the same semantic color.
- Candidate Strengths and Development Areas remain evidence-dependent; communication uses pace, pause, volume, and continuity signals; short/insufficient visual inputs remain neutral evidence limitations. Raw scores, model classifications, emotion labels, and internal pipeline language remain absent.
- Live DA-004 validation reused the existing ten-second video (SHA-256 `091EE35B8FACC49062422970B926F1EC95FDF426EF1EC2ECC8D94A11E73B1A9A`) through the unchanged endpoint: HTTP 200 in 199.86 seconds, `status=success`, valid alignment, transcript, warnings, and all contract sections. The report renders amber `Moderate Performance`, Technical `Moderate`, Communication `Strong`, and Visual `Limited Evidence`.
- Controlled Strong/Moderate/Developing SSR profiles produce green/amber/blue verdicts and three distinct recommendation sets. Projector QA at 1440×900 measures a 48px title and 30px verdict and shows verdict, strengths, and development priorities in the report-first viewport.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). The `/fusion-test` question/upload/record/analyze route remains intact with zero browser console errors. Validation-only preview code and the endpoint-created duplicate upload were removed.
- Net CP-013 product change is limited to `frontend/src/components/AIReportSummary.jsx`; `FusionTest.jsx` retains the verified CP-012 flow. Backend/API/database/model/NLP/Audio/Vision/scoring/threshold/retrieval/Fusion behavior is unchanged. CP-010/KI-001 remains preserved.

### CP-012 — Advanced Fusion Analysis report refinement complete (PASS; frontend only)

- The report identity is now `AI Interview Evaluation Report`. Its first viewport communicates the candidate-level interpretation, a dominant overall assessment, candidate strengths, and evidence-backed development areas.
- Overall presentation labels are `Strong Performance`, `Moderate Performance`, and `Developing`; visual insufficiency remains the neutral `Limited Evidence` state. This is presentation interpretation only and does not change backend scoring or thresholds.
- `AIReportSummary.jsx` now uses separate technical, communication, visual, recommendation, and overall narrative functions. Technical branches use the existing technical result plus hidden precision/coverage inputs; communication branches use speaking rate, pause control, volume stability, and speech continuity; visual branches distinguish short samples, face visibility, frame coverage/reliability, and supported visual evidence.
- Candidate Strengths no longer contains system statements such as successful speech capture or pipeline completion. Development Areas no longer contains unconditional camera, lighting, or generic advice; each rendered item is selected from an observed technical, vocal, or sufficiently supported visual gap.
- The preserved real DA-017 response now renders: overall `Developing`; strengths = balanced speaking pace and effective pauses; development = clearer technical definition/structure and smoother transitions; Technical Answer `Developing`; Communication `Moderate`; Visual Evidence Analysis `Limited Evidence` because the short response yielded three temporal windows.
- Controlled strong, fast-delivery, and unstable-delivery fixtures produce distinct outputs. Strong produces `Strong Performance` and no priority development area; fast produces `Moderate Performance` plus pace-specific advice; unstable delivery produces flow-specific advice. No fixed recommendation appears in all profiles.
- Final Vite build PASS (2,534 modules; existing large-chunk advisory only). In-app browser QA confirms projector-readable hierarchy, correct alternate narratives, intact `/fusion-test` upload/record/analyze controls, and zero browser console errors.
- Product scope remains exactly `frontend/src/components/AIReportSummary.jsx` and `frontend/src/pages/FusionTest.jsx`. Backend/API/database/model/NLP/scoring/threshold/retrieval/Fusion behavior is unchanged. CP-010/KI-001 remains preserved.

### CP-011 — Fusion Analysis report UI redesign complete (PASS; frontend only)

- The standalone `/fusion-test` report is now an interviewer-facing assessment rather than a debugging dashboard. `AIReportSummary` receives the unchanged payload through `<AIReportSummary result={result} />` and maps existing technical, vocal, and visual evidence into plain-language presentation labels.
- The first viewport prioritizes the large `Interview Assessment` heading and overall verdict (`Strong Performance`, `Moderate Performance`, or `Needs Improvement`). The remaining summary is limited to Candidate Strengths, Areas To Improve, and exactly three detailed cards: Technical Answer, Communication, and Visual Evidence.
- Visual insufficiency is reported as `Limited Evidence`. No raw numeric score is substituted for an unavailable or unreliable modality, and the report keeps a clear human-review/not-a-hiring-decision limitation.
- `FusionTest` retains its existing question selection, upload/record/analyze flow, warnings and limitations, invalid-answer message, transcript, and API call. It no longer renders engineering status, raw Audio/Vision model cards, model classifications, detailed modality metrics, or the numeric confidence score wall.
- Verification PASS: production Vite build completed with 2,534 modules; the only warning is the existing bundle-size advisory. The existing `Video_—_Strong_Baseline_Visu.mp4` plus `DA-017` completed through the unchanged endpoint with HTTP 200 in `180.46s`, `status=success`, transcript, warnings, and the same response sections.
- In-app browser QA PASS on the real response: the overall verdict dominates the initial viewport, official section headers are large, exactly three detail cards render, and forbidden debug/raw labels plus `/100` strings are absent.
- Scope stayed frontend-only: product changes are `frontend/src/pages/FusionTest.jsx` and `frontend/src/components/AIReportSummary.jsx`. No backend source, API contract, model, NLP pipeline, database schema, scoring, threshold, retrieval, or Fusion behavior changed.
- CP-010 and KI-001 remain preserved. If work returns to NLI, the CP-009 adapter is still rejected/evaluation-only and Phase 2E design still requires explicit authorization.

### CP-010 — LoRA Failure Diagnosis Complete (PASS; diagnosis only)

- Phase 2D was artifact-only. It loaded no model, ran no inference/training, created no data, changed no dataset/adapter, and did not modify production NLI, scoring, thresholds, retrieval, or Fusion. CP-009 remains evaluation-only and rejected for promotion.
- Frozen dependencies remain intact: CP-005 SHA `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`, training corpus SHA `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`, and split SHA `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`. Training/evaluation question overlap is zero and label distributions are exactly balanced, so label imbalance and exact CP-005 leakage do not explain the gap.
- Root cause is a train/dev authoring-template generalization gap. All 50 questions share the same deterministic 12-case schedule and authoring helpers. Label-correlated markers cover `170/200` entailments, `150/200` contradictions, and `180/200` neutrals with nearly identical train/dev rates, while `semantic_family_ids` track question families but not template/transformation families.
- The corpus is too easy for the intended claim despite correct structure and external label review: `153/180` paraphrase entailments contain the full normalized premise; all 90 direct contradictions have an explicit negation marker; 180/200 neutrals announce an independent fact. Mean token-Jaccard is E `0.766`, C `0.671`, N `0.011`, exposing strong surface shortcuts.
- All-case transition audit: fixes `NLI-EVAL-007/035`; new failures `037/041`; unchanged failures `009/018/023/042/043/045`; 35 unchanged correct. Predicted E/N/C shifts `15/18/12 -> 11/20/14`; mean E probability falls `0.076967`; entailment recall falls `13/15 -> 11/15`; false contradictions worsen `2 -> 3`.
- DA-017 falls `2/5 -> 1/5`: `041` newly becomes E→C at `0.988097 C`; `042` and `045` remain high-confidence false contradictions; `043` moves false E→false N; only unrelated neutral `044` passes. The training corpus contains zero JOIN-term records and does not teach LEFT/INNER cardinality or unmatched-row semantics.
- Root-cause ranking: (1) shared authoring-template shortcuts, (2) natural-reasoning mismatch, (3) contradiction mutations over-broaden non-entailment, (4) absent JOIN/natural dialectal paraphrase coverage, all high confidence; base-family capacity/calibration is a medium-confidence contributor. Label imbalance, exact leakage, and optimizer failure are rejected.
- Perfect internal dev therefore demonstrates mastery of the shared generator distribution, not general InterviewIQ NLI reasoning. Human label review can validate semantics without making authoring styles independent.
- Current adapter remains **REJECTED_FOR_PROMOTION_EVALUATION_ONLY**. LoRA is **PAUSE_CONDITIONAL_NOT_ABANDONED**: never repeat the same corpus/config. Before future training, require template-family isolation, independent natural formulations, unmarked relational contrasts, a separate model-selection diagnostic, and preserved CP-005 final-only acceptance.
- Primary report: `results/nli_phase2d_diagnosis_cp010/lora_failure_diagnosis_v1.md`; machine evidence: `lora_failure_diagnosis_v1.json`. Exact next step, only if authorized, is Phase 2E design-only specification of a template-independent protocol and a pre-registered revised-LoRA versus semantic-verifier/cascade comparison. No data authoring or training is implied.

### CP-009 — LoRA Training and Evaluation Complete (execution PASS; acceptance FAIL; do not promote)

- Phase 2C recorded the user's explicit external-review attestation for the unchanged CP-008 corpus, passed fail-closed preflight, trained exactly one adapter, and evaluated it once on frozen CP-005. No production NLI, inference, scoring, threshold, retrieval, Fusion, or deployment configuration changed.
- Frozen inputs remained intact: corpus SHA `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`, 480/120 split SHA `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`, and CP-005 SHA `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`. Exact leakage and train/dev overlap counts remain zero.
- The single adapter used the pinned baseline revision, r16/alpha32 query/value LoRA, dropout 0.1, bias none, SEQ_CLS, lr 2e-4, five epochs, seed 42, max length 256, and effective batch 16 on CPU/fp32. It completed 150 steps with train loss `0.178817`; 592,131 parameters were trainable; best internal-dev macro F1 reached `1.0`.
- Final adapter weights SHA is `E5972EF2A75D29FE2FBFACE9B9F0F6F1502006A3C7DD167049969D759BB8AC6A`. Training wall time was `862.211s`; sampled training peak RSS was `2.878GB`.
- CP-005 held-out result is not a remediation improvement: accuracy remains `37/45 = 0.822222`; macro F1 is `0.820639`; E/N/C F1 is `0.846154/0.857143/0.758621`; confusion is `[[11,1,3],[0,15,0],[0,4,11]]`; false contradictions worsen `2→3`; false entailments improve `1→0`; neutral improves `14/15→15/15`; DA-017 worsens `2/5→1/5`.
- The adapter fixes `NLI-EVAL-007` and `035`, newly regresses baseline-correct `037` and `041`, and changes `043` from false entailment to false neutral. Language accuracy is code-switch 75%, MSA 90%, transliteration 100%, Egyptian 88.89%, English diagnostic 66.67%; direct contradiction is 40% and natural-paraphrase entailment 57.14%.
- Runtime constraints pass: `82.386ms/case` and evaluation peak working set `2.221GB`. Semantic gates fail: overall score, macro/minimum-class F1, zero false contradiction, DA-017 5/5, zero regressions, and minimum supported slice.
- Independent audit validates all 45 predictions/probabilities, confusion matrix, five epoch logs, 150 steps, LoRA config, adapter attachment, hashes, acceptance=false, no second adapter, no promotion, and empty staged diff. CP-009 decision is **FAIL_DO_NOT_PROMOTE**.
- Perfect internal dev versus failed frozen held-out evidence suggests a generalization/data-authoring-template gap rather than optimizer failure. Exact next step, only if separately authorized, is analysis/design of CP-005 coverage and cross-question template shortcuts; no second training run or production change is authorized.

### CP-008 — Phase 2B Training Corpus Created (PARTIAL PASS; human review required)

- Phase 2B data authoring created a deterministic 600-record candidate corpus from 50 independent, non-protected reference-document question families. It did not load a model, run inference or training, create an adapter checkpoint, or modify production behavior.
- Composition exactly matches CP-007: 200 entailment / 200 contradiction / 200 neutral; MSA 150, Egyptian 150, Arabic/English code-switch 180, transliteration 60, English diagnostic 60; difficulties 180 paraphrase entailment, 20 preservation entailment, 110 near-neighbor contradiction, 90 direct contradiction, 120 technical neutral, and 80 adjacent neutral. All 600 are technical-domain cases.
- The split is by complete question ID: 480 records from 40 train question IDs and 120 records from 10 dev question IDs. No question ID, semantic family, or pair group crosses the split.
- Facts and provenance come from `reference_docs_250_FINAL_v1.json` questions, canonical chunks, and key points, frozen at SHA-256 `BA062768EB02C6DBE16D90024C30B075AF98F85D08B9E946BB26862AAB250F07`. The separately configured `data/questions/questions_250.json` is absent and was not represented as a source.
- Automated leakage/provenance checks pass: no protected CP-005 or DS-014 question ID, evaluation premise, hypothesis, or normalized pair occurs; no case reaches token-Jaccard 0.8 against CP-005 (maximum observed `0.346154`); no duplicate ID/pair or unresolved canonical provenance exists.
- Frozen artifacts: corpus SHA-256 `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`; review ledger `676B20BBA54D7D7DAF3A1DE7386871324137CB28BBAAFFDF93A6B0792828FDA3`; split manifest `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`; preflight `3FFCAA422B135F2390F23A1450EC8D54237D68DDC30B438CAB15C8924C3A790B`; quality report `F1E0A8F3C3F1E5D41C01EAAE5EAF591EAD273E4F8880F142D2CFB37C8D2E268F`.
- The checkpoint is a deliberate `PARTIAL PASS`, not a claim of reviewed labels: 0/600 have human approval, 600/600 await two independent reviewers, 190 are ambiguity-flagged, and 0/600 are accepted for training. `training_ready=false` remains fail-closed.
- Exact next step is human review and adjudication followed by minimal correction/exclusion, renewed leakage/distribution preflight, and new frozen hashes. LoRA training requires separate explicit authorization after this gate; resuming CP-008 does not authorize model loading or training.
- Phase 2C authorization later supplied an explicit external-review attestation: all 600 unchanged cases completed manual two-pass review and adjudication and were approved for training; no corpus, label, split, ledger, or project file changed during that external review. The repository therefore preserves the original CP-008 ledger and hashes and records the user attestation separately at `results/nli_phase2c_training_cp009/external_human_review_attestation_v1.json`. Reviewer identities and per-case comments were not supplied and are not claimed.

### CP-007 — Phase 2B Preparation Complete (PASS; data authoring pending)

- CP-007 is preparation only: it defines a corpus, leakage boundary, one-run LoRA contract, acceptance gates, future artifacts, and rollback. It created zero training examples, loaded no model, ran no training/evaluation, created no adapter, and changed no production path.
- The target corpus is 600 independently reviewed examples from at least 40 non-protected questions, approximately 480 train / 120 dev by complete question ID. Labels are balanced 200/200/200; primary styles are MSA 150, Egyptian 150, Arabic/English code-switch 180, transliteration 60, and English diagnostic 60; at least 360 cases carry technical terminology.
- Difficulty targets are 180 paraphrase entailments, 20 domain-entailment-preservation cases, 110 near-neighbor contradictions, 90 direct contradictions, 120 technical neutrals, and 80 semantically adjacent neutrals. Two independent reviewers plus adjudication are mandatory; AI-only labels are rejected.
- Leakage policy loads the frozen CP-005 dataset only as an exclusion source after verifying SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18` and `do_not_train=true`. It rejects all evaluation cases, ten source question IDs, five DA-017 anchors, normalized premises/hypotheses/pairs, duplicates, train/dev source overlap, paired-group splitting, mutable sources, and semantic derivatives that require human review.
- Existing hooks are compatible: `evaluate_answer(adapter_path)`, `load_adapter` using `PeftModel.from_pretrained`, `run_finetune`, and `run_nli_eval --adapter-path`. Supported LoRA shape is r 16, alpha 32, query/value projections, dropout 0.1, no bias, `SEQ_CLS`.
- The legacy training flow is not ready unchanged: configured pilot files are absent; exclusions cover DS-014 only; the new schema/review boundary is unenforced; base loading is mutable; training tokenization defaults to 128; and focused LoRA preflight tests are absent.
- Predeclared primary gates are CP-005 at least 39/45, macro F1 ≥0.85, each class F1 ≥0.80, false contradiction 0/15, false entailment ≤1/15, neutral ≥14/15, DA-017 5/5, zero new regressions, supported slices ≥70%, CPU latency ≤1.15x, peak working set ≤1.10x, and a separate Coverage/scoring regression PASS. Passing cannot automatically authorize promotion.
- Validation PASS confirms all distribution sums, required fields, protected IDs/anchors, existing hooks, authorization boundaries, zero examples/checkpoints, and empty staged diff. Exact next step requires explicit Phase 2B Data Authoring authorization and must stop again before model loading or training.

### CP-006 — Phase 2A checkpoint-control evaluation (PASS; no remediation winner)

- Phase 2A created an isolated, reproducible evaluator without modifying production NLI, scoring, thresholds, retrieval, or Fusion. The manifest freezes CP-005 SHA-256 `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`, exact model/tokenizer snapshots, E/N/C mapping, premise/hypothesis direction, CPU/fp32/eval/no-adapter, batch 8, max length 256, seed 42, deterministic algorithms, and resource methodology.
- Baseline revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` exactly reproduces CP-005: accuracy `37/45 = 0.822222`, macro F1 `0.818631`, false contradiction `2/15`, false entailment `1/15`, DA-017 `2/5`, and zero rounded-probability delta.
- Candidate `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` revision `b5113eb38ab63efdd7f280f8c144ea8b13f978ce` reaches accuracy `39/45 = 0.866667` and macro F1 `0.866270`; E/N/C F1 is `0.857143 / 0.875000 / 0.866667`; confusion rows E/N/C are `[[12,1,2],[1,14,0],[0,2,13]]`.
- Candidate improvements are three fixed failures (`NLI-EVAL-023`, `035`, `043`), false entailment `1/15 -> 0/15`, English-diagnostic accuracy `55.56% -> 88.89%`, and near-neighbor contradiction `60% -> 100%`.
- The candidate does not repair KI-001: false contradiction remains `2/15 = 13.33%`, both LEFT JOIN entailments remain false contradictions, DA-017 remains `2/5`, and `NLI-EVAL-041` regresses from entailment to neutral. Arabic/English code-switch falls `83.33% -> 75%`; natural-paraphrase entailment falls `85.71% -> 71.43%`.
- Both checkpoints have the same serving shape: `DebertaV2ForSequenceClassification`, `DebertaV2TokenizerFast`, identical vocabulary fingerprint, equal `278,811,651` parameters, strict E/N/C mapping, CPU/fp32, and approximately `2.093GB` process peak working set. Candidate timed inference is `3.6769s` versus `3.6240s` for 45 cases (`+1.5%`). Model-load timing is not decision evidence because OS file-cache order can bias it.
- The candidate passes overall accuracy, macro F1, minimum class F1, and false-entailment gates but fails false contradiction, `5/5` DA-017, and minimum supported-slice gates. Engineering decision: **no remediation winner; keep production unchanged**. The candidate is retained only as a verified control.
- Leakage controls protect all ten CP-005 question IDs and reject normalized pair, premise, hypothesis, and duplicate-training-pair overlap. No training manifest currently exists; the recorded result is `NO_TRAINING_MANIFEST_PRESENT`, not a claim about future data.
- Verification: 16 focused tests, 25/25 complete current NLP tests, offline preflight PASS, and completed-artifact audit PASS. No adapter was trained or loaded.
- Exact next experiment remains one targeted LoRA adapter on the pinned current production base using separately reviewed training/dev data with strict CP-005 exclusion, plus CP-005 A/B and a separate Coverage/scoring regression gate. This requires explicit Phase 2B authorization.

### CP-005 — Current-model NLI baseline (PASS; remediation pending)

- Phase 1 created and froze `interviewiq-nli-ar-codeswitch-heldout-v1`: 45 reviewed scored cases = 40 newly authored discovery cases plus 5 explicit DA-017 regression anchors, exactly balanced 15 entailment/15 neutral/15 contradiction across ten source questions. Dataset SHA-256 is `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`; the predeclared metrics-contract SHA-256 is `01F2B3F6A5F8EFEE019C08972854E6D92D8DC53D999957C7B60AC45DB5D2A655`.
- Structural and semantic validation passed: 45 unique case IDs and normalized pairs, 45 canonical source matches, no ambiguous scored case, explicit anchor/discovery separation, required Arabic/Egyptian/code-switched and difficulty coverage, no production/config case reference, and no current configured-training-data leakage. Evaluation data is `do_not_train=true`.
- The unchanged current model `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` resolved to revision `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c` and ran with `DebertaV2TokenizerFast`, CPU/fp32/eval, batch 8, max length 256, production direction/mapping, and no adapter or threshold/config/code change.
- Overall accuracy is `37/45 = 0.822222`; macro F1 `0.818631`; entailment/neutral/contradiction F1 is `0.866667 / 0.848485 / 0.740741`. The confusion matrix rows expected/columns predicted E,N,C is `[[13,0,2],[1,14,0],[1,4,10]]`.
- False contradiction on true entailments is `2/15 = 13.3333%`; false entailment on true contradictions is `1/15 = 6.6667%`. Discovery-only accuracy is `35/40 = 87.5%`; DA-017 anchor accuracy is `2/5 = 40%`.
- DA-017 anchor outcomes are: `NLI-EVAL-041 PASS`, `042 FAIL E→C`, `043 FAIL C→E`, `044 PASS`, `045 FAIL E→C`. The exact CP-003 E→C signature did not occur outside DA-017 among the 40 discovery cases, so it is localized to JOIN phrasing in this first set; broader cross-language/direct and near-neighbor contradiction weakness across four non-DA-017 concepts is systemic.
- The current model fails every proposed remediation gate except the false-entailment ceiling. No remediation was selected or started. Evidence ranks a separate-data, exactly-one-adapter LoRA A/B experiment through the existing optional hook first, subject to explicit Phase-2 authorization and exclusion of all ten evaluation question IDs from training.
- Reuse the frozen CP-005 artifacts. Do not recreate/relabel the dataset or rerun the unchanged baseline unless its dataset, model/tokenizer revision, preprocessing, direction, label mapping, max length, adapter state, or relevant runtime dependency changes.

### CP-003 — DA-017 NLI forensic diagnosis (PASS; fix pending)

- The forensic phase was read-only with respect to product code, config, models, thresholds, scoring, retrieval, and reference data. Nothing was staged, committed, or tagged.
- Canonical DA017-C01/C02 and preserved claims are valid UTF-8 in correct logical/codepoint order. Apparent reversed Arabic in terminal output is Unicode bidi display behavior, not stored-text corruption.
- Production NLI direction and mapping are correct: reference evidence is the premise, candidate claim is the hypothesis, and the current config is `0=entailment, 1=neutral, 2=contradiction` with softmax on the logits dimension.
- Exact target pairs retain INNER/LEFT/JOIN, contain no unknown tokens, and are far below production `max_length=256`; truncation/token loss is not involved.
- The current local `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` snapshot on CPU/fp32 exactly reproduces the after LEFT false contradiction (`0.998316 C`) and reproduces the preserved earlier correctly recognized LEFT claim as `0.981175 C`.
- Correcting `Lift→LEFT`, removing the leading article, symmetrically normalizing the reference, lowercasing SQL tokens, and reversing the pair do not repair polarity. Exact/near-exact Arabic plus monolingual English E/C/N controls show the engine and labels work; behavior is brittle on the semantic Arabic/code-switched paraphrase.
- Primary root-cause class is **D: NLI model multilingual capability / model behavior**. `Lift` is a contributing upstream input error but not the primary cause; thresholds cannot correct raw semantic inversion.
- At CP-003, KI-001 remained open as `ROOT_CAUSE_VERIFIED_FIX_PENDING`; CP-005 later superseded that workflow status with `BASELINE_MEASURED_REMEDIATION_PENDING`. The adapter idea was only a proposal, not an authorized fix or architecture decision.
- Do not repeat CP-003 string/Unicode/tokenizer/label/direction/model diagnostics unless reference text, claim preprocessing, tokenizer/model revision, NLI engine, or runtime configuration changes.

### CP-002 — External memory/checkpoint bootstrap (PASS)

- The authoritative root files now separate rules, specification, durable knowledge, decisions, current task, exact execution state, evidence, and known issues.
- `AGENTS.md` is a discovery pointer only; `AGENT_RULES.md` is the canonical rulebook.
- `EXECUTION_STATE.json` passed both PowerShell and Python JSON parsing.
- Required-file, pointer-target, and Git preservation checks passed.
- TASK-MEM-001 added only the nine memory/governance files. No product/config/model/data file was changed, and nothing was staged or committed.
- No implementation task is active. The next session must resume from `EXECUTION_STATE.json.next_step` after the user supplies a task.

### CP-001 — DA-017 BGE relevance/evidence-selection correction (PARTIAL PASS)

- Current working-tree code separates BGE relevance from NLI relationship classification.
- Small documents are BGE-ranked even when all chunks remain available to NLI; `k=10` remains a compute cap for larger documents.
- Entailment, neutral, and contradiction are read from the same BGE-selected NLI cell, preserving the D110 same-evidence invariant.
- Focused and broader automated suites were reported passing in the immediately preceding execution, but no authoritative stdout log is stored on disk. Do not infer exact results from pytest caches; see `EVIDENCE_LEDGER.md`.
- A real same-video run selected the correct DA017-C01 and DA017-C02 chunks, proving the retrieval defect was corrected.
- The result is only partially verified because the zero-shot NLI classified the correct LEFT JOIN evidence as strongly contradictory; score changed from `1.5817904` to `-49.9158`.
- The full-run artifact predates the latest small hardening edits by about five minutes, so a future task that changes or releases this fix may require dependency-aware re-verification of only the affected layers.

## Repository baseline at memory bootstrap

- Branch: `main`
- HEAD: `e0da106534bac20fed7f0ce39185b0194f8557f4`
- Upstream delta: `+5 / -0` relative to `origin/main`
- Initial dirty state before memory files: 12 unstaged modified entries, 14 untracked entries, 0 staged entries
- The dirty tree contains protected NLP changes, generated databases/media/artifacts, frontend work, backups, and an untracked historical audit. Preserve them.
- Nothing was staged or committed during the DA-017 fix or memory bootstrap.

## Documentation provenance

- `PROJECT_STATUS_AUDIT_2026-08-04.md` is an untracked dated historical audit whose headline architecture predates Phases 3A–3D. It is not current state.
- `PHASE_3A_REAL_AUDIO_IMPLEMENTATION_REPORT.md` is valid historical Phase 3A evidence but its deferred-work section is not the current roadmap.
- `README_LOCAL_SETUP.md` is an operational runbook with accumulated phase notes and known internal staleness; it is not checkpoint authority.
- The NLP `README.md` and `docs/fusion_handoff_manifest.md` are duplicate historical handoffs and cite a missing `decisions.md`. Legacy D-number references must not be reconstructed as original decisions without primary evidence.

## No-repeat guidance

- Do not redo the BGE relevance fix or rerun the expensive DA-017 full pipeline merely to rediscover CP-001.
- Re-run affected tests or the full video only if relevant code/config/model inputs changed, CP-001 evidence is invalidated, a release/final regression requires it, or the user asks.
- If the next task targets the DA-017 outcome, start at the NLI/ASR-normalization diagnostic boundary, not at retrieval selection.
