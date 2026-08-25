# CP-005 Current-Model NLI Baseline Summary

- Decision state: `PASS` for the evaluation task; the current model does **not** meet the proposed remediation target.
- Dataset: `data/nli/evaluation/heldout_ar_codeswitch_v1.json`
- Metrics contract: `data/nli/evaluation/baseline_metrics_contract_v1.json` (`PREDECLARED_BEFORE_INFERENCE`)
- Full per-case report: `results/nli_baseline_cp005/current_model_baseline_v1.json`
- Failure detail: `results/nli_baseline_cp005/failure_analysis_v1.json`
- Independent validation: `results/nli_baseline_cp005/baseline_validation_v1.json`

## Dataset

- 45 scored, reviewed, unambiguous cases: 40 newly authored held-out discovery cases plus 5 pre-known DA-017 regression anchors.
- Exactly balanced labels: 15 entailment, 15 neutral, 15 contradiction.
- Ten source questions across Data Analysis, Data Science, Cybersecurity, and Software Engineering.
- Language styles: Arabic MSA 10; Egyptian Arabic 9; Arabic/English code-switch 12; Arabic transliteration variants 5; English diagnostics 9.
- All ten required difficulty types are present.
- All 45 premise strings are byte-equal to their canonical reference chunks; no duplicate normalized pair/hypothesis, unresolved source, ambiguous scored label, tokenizer UNK, or truncation exists. Maximum untruncated pair length is 78 against max length 256.
- Evaluation-only: `do_not_train=true`. The five known DA-017 cases are marked `regression_anchor=true` and reported separately.
- No `NLI-EVAL-*` case ID, evaluation dataset ID, or evaluation path occurs in production source or config, so no scored case depends on a production case-specific hard-code. The evaluation path is absent from fine-tuning source/config, and both configured pilot training files are absent; no current configured training dataset contains these held-out pairs.
- Frozen dataset SHA-256: `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`; predeclared metrics-contract SHA-256: `01F2B3F6A5F8EFEE019C08972854E6D92D8DC53D999957C7B60AC45DB5D2A655`.

## Current unchanged runtime

- Model: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli`
- Resolved model commit: `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`
- `DebertaV2ForSequenceClassification` + `DebertaV2TokenizerFast`
- CPU/fp32/eval; no adapter; batch size 8; max length 256.
- Direction and mapping unchanged: canonical reference premise, candidate claim hypothesis; `0=entailment, 1=neutral, 2=contradiction`; argmax raw logits; softmax reporting only.

## Aggregate metrics

- Accuracy: `37/45 = 0.822222`
- Macro F1: `0.818631`
- Entailment: precision `0.866667`, recall `0.866667`, F1 `0.866667`, support 15.
- Neutral: precision `0.777778`, recall `0.933333`, F1 `0.848485`, support 15.
- Contradiction: precision `0.833333`, recall `0.666667`, F1 `0.740741`, support 15.

Confusion matrix (rows=expected, columns=predicted):

| Expected \\ Predicted | Entailment | Neutral | Contradiction |
|---|---:|---:|---:|
| Entailment | 13 | 0 | 2 |
| Neutral | 1 | 14 | 0 |
| Contradiction | 1 | 4 | 10 |

- False contradiction rate on true entailments: `2/15 = 13.3333%`.
- False entailment rate on contradictions: `1/15 = 6.6667%`.

## Held-out discovery versus regression anchors

- Newly authored held-out discovery only: accuracy `35/40 = 87.5%`, macro F1 `0.877348`.
- Discovery E→C: `0/12 = 0%`; discovery C→E: `0/14 = 0%`.
- DA-017 anchors: accuracy `2/5 = 40%`, macro F1 `0.466667`.
- DA-017 anchor E→C: `2/3 = 66.6667%`; anchor C→E: `1/1 = 100%`.

Anchor results (full premise/hypothesis text is intentionally retained for auditability):

| Case | Premise | Hypothesis | Expected | Predicted | P(E) | P(N) | P(C) | Result |
|---|---|---|---|---|---:|---:|---:|---|
| NLI-EVAL-041 | INNER JOIN يعيد الصفوف التي تحقق شرط الربط في كلا الجدولين فقط. | ال Inner Join يعيد الصفوف المتطابقة بين الجدولين. | entailment | entailment | 0.679402 | 0.024493 | 0.296105 | PASS |
| NLI-EVAL-042 | LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL. | ال left join يعيد كل الصفوف من الجدول الايسر حتى اذا لم يكن هناك تطابق. | entailment | contradiction | 0.007968 | 0.010857 | 0.981175 | FAIL |
| NLI-EVAL-043 | LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL. | LEFT JOIN returns only matching rows and removes unmatched left rows. | contradiction | entailment | 0.446733 | 0.392953 | 0.160314 | FAIL |
| NLI-EVAL-044 | LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL. | Python is commonly used for data analysis. | neutral | neutral | 0.007348 | 0.972105 | 0.020547 | PASS |
| NLI-EVAL-045 | LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL. | ال LEFT JOIN يعيد كل الصفوف من الجدول الشمال حتى لو لا يوجد تطابق. | entailment | contradiction | 0.002671 | 0.001515 | 0.995815 | FAIL |

## Failure analysis

Eight failures:

- `entailment→contradiction`: 2, both DA-017 LEFT anchors.
- `contradiction→entailment`: 1, the required English LEFT contradiction anchor.
- `contradiction→neutral`: 4 across unsupervised learning, CIA Triad, symmetric encryption, and Queue/LIFO.
- `neutral→entailment`: 1, a semantically adjacent supervised-learning statement.

Language accuracy:

- Arabic transliteration variants: `100%` (5 cases).
- Arabic MSA: `90%` (10).
- Egyptian Arabic: `88.89%` (9).
- Arabic/English code-switch: `83.33%` (12).
- English diagnostic hypotheses against Arabic premises: `55.56%` (9), the weakest slice.

Difficulty accuracy:

| Difficulty type | Correct / support | Accuracy |
|---|---:|---:|
| Exact or near-exact entailment | 1/1 | 100% |
| Natural paraphrase entailment | 6/7 | 85.71% |
| Partial entailment | 2/2 | 100% |
| Direct contradiction | 2/5 | 40% |
| Negation contradiction | 5/5 | 100% |
| Near-neighbor concept contradiction | 3/5 | 60% |
| Unrelated technical neutral | 3/3 | 100% |
| Semantically adjacent non-entailing | 11/12 | 91.67% |
| Code-switched technical terminology | 2/2 | 100% |
| ASR-like lexical variation | 2/3 | 66.67% |

Interpretation: the exact CP-003 `entailment→contradiction` signature was not reproduced outside DA-017 in the 40 new cases, so it is localized to the JOIN semantic formulation in this first small set rather than universal across Arabic entailments. It is not an isolated transient string failure: two distinct realistic LEFT formulations fail with 98.12% and 99.58% contradiction, and the inverse false LEFT statement is also misclassified. Broader model weakness is systemic in cross-language/direct and near-neighbor contradiction recognition across four non-DA-017 concepts.

## Existing hooks and missing prerequisites

- Production already accepts an optional `adapter_path` and attaches it with `PeftModel.from_pretrained`.
- Evaluation already supports zero-shot versus `--adapter-path` and per-pair probabilities.
- Fine-tuning tooling already defines LoRA target modules `query_proj` and `value_proj`, question-level splits, excluded evaluation question IDs, and twin-integrity checks.
- The configured pilot training files and `checkpoints/nli-lora-v1` do not exist in the current workspace. No adapter was trained or loaded.
- Existing `gold_set_48.json` was not reused: it is DRAFT, DS-014-only, AI-drafted/not expert-verified, has stale corrected labels P37/P48, and 15/48 premises differ from current canonical chunks. Pure metric/inference functions were reused instead.

## Candidate remediation experiments

1. **Separate-data LoRA A/B experiment through the existing adapter hook** — highest expected value with the smallest production integration blast radius. First author/review training-only Arabic/code-switched hard-negative and paraphrase cases from question IDs excluded from this frozen evaluation set; then train one adapter and compare against this unchanged baseline. Do not use these 45 pairs for training.
2. **Evaluation-only multilingual checkpoint bake-off** — low experiment blast radius and no production switch during evaluation, but a selected replacement would have broader runtime/deployment/regression impact than an adapter.
3. **Secondary semantic verifier for high-risk/disagreement cases** — potentially useful if a single adapted model remains weak, but highest latency, calibration, logic, and audit blast radius.

Threshold tuning, label remapping, JOIN-specific rules, and using the held-out set as training data are rejected.

## Proposed target result

The predeclared target remains `PROPOSED_NOT_YET_APPROVED`: accuracy ≥0.85, macro F1 ≥0.85, each class F1 ≥0.80, false contradiction ≤5%, false entailment ≤10%, all five DA-017 anchors correct, and supported slices ≥70% accuracy. The current model fails every gate except the false-entailment ceiling.

## Exact next step

Await explicit Phase-2 authorization. If granted, freeze this dataset/hash and create a separate training-only corpus excluding all ten evaluation question IDs; emphasize cross-language direct/near-neighbor contradictions and Arabic/code-switched paraphrase entailments; then train exactly one LoRA adapter through the existing hook and A/B-evaluate it against this unchanged baseline before considering any production change.
