# CP-006 Phase 2A NLI Checkpoint-Control Comparison

- Scope: evaluation only; no training, adapter, threshold, scoring, retrieval, Fusion, or production change.
- Dataset SHA-256: `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`
- Baseline: `MoritzLaurer/mDeBERTa-v3-base-mnli-xnli` @ `8adb042d524ecd5c26d3e3ba0e3fbcf7e2d0864c`
- Candidate: `MoritzLaurer/mDeBERTa-v3-base-xnli-multilingual-nli-2mil7` @ `b5113eb38ab63efdd7f280f8c144ea8b13f978ce`
- Baseline CP-005 reproduction: `PASS`
- Automatic winner: **none**; engineering review is required.

## Aggregate comparison

| Metric | Baseline | Candidate | Delta |
|---|---:|---:|---:|
| Accuracy | 0.822222 | 0.866667 | +0.044444 |
| Macro F1 | 0.818631 | 0.866270 | +0.047639 |
| False contradiction rate | 0.133333 | 0.133333 | +0.000000 |
| False entailment rate | 0.066667 | 0.000000 | -0.066667 |

## Per-class metrics

| Class | Model | Precision | Recall | F1 | Support |
|---|---|---:|---:|---:|---:|
| entailment | baseline | 0.866667 | 0.866667 | 0.866667 | 15 |
| entailment | candidate | 0.923077 | 0.800000 | 0.857143 | 15 |
| neutral | baseline | 0.777778 | 0.933333 | 0.848485 | 15 |
| neutral | candidate | 0.823529 | 0.933333 | 0.875000 | 15 |
| contradiction | baseline | 0.833333 | 0.666667 | 0.740741 | 15 |
| contradiction | candidate | 0.866667 | 0.866667 | 0.866667 | 15 |

## Confusion matrices

### Baseline

Rows are expected labels; columns are predicted E/N/C.

| Expected | E | N | C |
|---|---:|---:|---:|
| E | 13 | 0 | 2 |
| N | 1 | 14 | 0 |
| C | 1 | 4 | 10 |

### Candidate

Rows are expected labels; columns are predicted E/N/C.

| Expected | E | N | C |
|---|---:|---:|---:|
| E | 12 | 1 | 2 |
| N | 1 | 14 | 0 |
| C | 0 | 2 | 13 |

## DA-017 anchors

| Case | Expected | Baseline prediction (E/N/C) | Candidate prediction (E/N/C) | Baseline | Candidate |
|---|---|---|---|---:|---:|
| NLI-EVAL-041 | entailment | entailment (0.679402/0.024493/0.296105) | neutral (0.422111/0.467877/0.110012) | PASS | FAIL |
| NLI-EVAL-042 | entailment | contradiction (0.007968/0.010857/0.981175) | contradiction (0.013753/0.137642/0.848605) | FAIL | FAIL |
| NLI-EVAL-043 | contradiction | entailment (0.446733/0.392953/0.160314) | contradiction (0.083939/0.413021/0.503041) | FAIL | PASS |
| NLI-EVAL-044 | neutral | neutral (0.007348/0.972105/0.020547) | neutral (0.000705/0.999076/0.000218) | PASS | PASS |
| NLI-EVAL-045 | entailment | contradiction (0.002671/0.001515/0.995815) | contradiction (0.002853/0.010693/0.986455) | FAIL | FAIL |

## Language-style breakdown

| Slice | Support | Baseline accuracy | Candidate accuracy | Delta |
|---|---:|---:|---:|---:|
| arabic_english_code_switch | 12 | 0.833333 | 0.750000 | -0.083333 |
| arabic_msa | 10 | 0.900000 | 0.900000 | +0.000000 |
| arabic_transliteration_variant | 5 | 1.000000 | 1.000000 | +0.000000 |
| egyptian_arabic | 9 | 0.888889 | 0.888889 | +0.000000 |
| english_diagnostic | 9 | 0.555556 | 0.888889 | +0.333333 |

## Difficulty breakdown

| Slice | Support | Baseline accuracy | Candidate accuracy | Delta |
|---|---:|---:|---:|---:|
| asr_like_lexical_variation | 3 | 0.666667 | 0.666667 | +0.000000 |
| code_switched_technical_terminology | 2 | 1.000000 | 1.000000 | +0.000000 |
| direct_contradiction | 5 | 0.400000 | 0.600000 | +0.200000 |
| exact_or_near_exact_entailment | 1 | 1.000000 | 1.000000 | +0.000000 |
| natural_paraphrase_entailment | 7 | 0.857143 | 0.714286 | -0.142857 |
| near_neighbor_concept_contradiction | 5 | 0.600000 | 1.000000 | +0.400000 |
| negation_contradiction | 5 | 1.000000 | 1.000000 | +0.000000 |
| partial_entailment | 2 | 1.000000 | 1.000000 | +0.000000 |
| semantically_adjacent_non_entailing | 12 | 0.916667 | 0.916667 | +0.000000 |
| unrelated_technical_neutral | 3 | 1.000000 | 1.000000 | +0.000000 |

## Case-level changes

- Fixed baseline failures: `['NLI-EVAL-023', 'NLI-EVAL-035', 'NLI-EVAL-043']`
- New regressions: `['NLI-EVAL-041']`
- Changed but still wrong: `[]`

## Resource comparison

Fresh process per model; pinned local snapshot; identical fixed-batch warm-up excluded from timed 45-case inference.

| Resource | Baseline | Candidate | Ratio |
|---|---:|---:|---:|
| Model load seconds | 2.130954 | 0.707136 | 0.332x |
| Inference seconds | 3.624001 | 3.676925 | 1.015x |
| Milliseconds/case | 80.533349 | 81.709451 | 1.015x |
| Lifecycle peak RSS bytes | 2082328576.000000 | 2090602496.000000 | 1.004x |
| Process peak working set bytes | 2092621824.000000 | 2092568576.000000 | 1.000x |

## Decision boundary

This experiment records evidence only. It does not select or deploy a winner, train an adapter, or alter production behavior.

## Engineering assessment

- **No remediation winner.** Keep the current production checkpoint unchanged.
- The candidate improves accuracy from `37/45` to `39/45`, macro F1 from `0.818631` to `0.866270`, contradiction F1 from `0.740741` to `0.866667`, and false-entailment rate from `1/15` to `0/15`.
- It fixes `NLI-EVAL-023`, `NLI-EVAL-035`, and `NLI-EVAL-043`, but introduces a new regression on `NLI-EVAL-041` (`entailment -> neutral`).
- The critical false-contradiction rate is unchanged at `2/15 = 13.33%`; the two LEFT JOIN entailments still fail, and DA-017 remains `2/5`.
- Arabic/English code-switch accuracy decreases from `83.33%` to `75%`, and natural-paraphrase entailment decreases from `85.71%` to `71.43%`.
- The candidate preserves the serving shape: same model/tokenizer classes, vocabulary, parameter count, E/N/C mapping, CPU/fp32 behavior, and effectively equal peak working set. Timed inference is `1.5%` slower in this single controlled run. Model-load timing is not used for selection because OS file-cache order can bias it.
- The candidate fails the false-contradiction, DA-017, and supported-slice gates. It is therefore retained only as a useful control result, not recommended as a production replacement.
- Targeted LoRA on the pinned current production base remains the evidence-ranked next experiment, subject to separate Phase 2B authorization and strict CP-005 leakage exclusion.
