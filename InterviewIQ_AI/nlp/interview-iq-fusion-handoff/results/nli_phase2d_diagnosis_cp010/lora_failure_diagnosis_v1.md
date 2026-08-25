# CP-010 — Phase 2D LoRA Failure Diagnosis

- Status: `VERIFIED_DIAGNOSIS_COMPLETE_NO_REMEDIATION`.
- Decision: **DIAGNOSIS COMPLETE**.
- Scope: artifact-only forensic analysis. No model was loaded, no inference/training ran, no dataset or adapter changed, and production/scoring/thresholds/retrieval/Fusion remain untouched.
- CP-009 adapter remains evaluation-only and must not be promoted.

## Executive conclusion

The `1.0` internal-dev Macro F1 is not evidence that the adapter learned general InterviewIQ NLI reasoning. The train/dev split separated source question IDs but retained the same deterministic 12-case authoring grammar, label-specific wrappers, lexical mutation operators, and donor-neutral construction on both sides. The adapter learned that generated distribution extremely well, then failed to transfer to the natural, unmarked, relational paraphrases in frozen CP-005.

The adapter did not simply stay neutral. It shifted the decision boundary away from entailment: predicted E/N/C counts changed `15/18/12 -> 11/20/14`; entailment recall fell `13/15 -> 11/15`; false contradictions rose `2/15 -> 3/15`. It fixed two cases and regressed two previously correct cases, leaving accuracy `37/45` unchanged. This is a data/validation-design generalization failure with a localized high-confidence contradiction problem, not a failed optimizer run.

## 1. Generalization-gap evidence

| Dimension | Training corpus | Frozen CP-005 | Diagnosis |
|---|---|---|---|
| Label balance | 200 E / 200 N / 200 C | 15 E / 15 N / 15 C | No count mismatch; imbalance is rejected as a cause. |
| Language style | MSA 150; Egyptian 150; code-switch 180; transliteration 60; English 60 | MSA 10; Egyptian 9; code-switch 12; transliteration 5; English 9 | Categories overlap, but English is 10% vs 20%, and the training dialect/code-switch forms are mostly fixed wrappers rather than independently worded language. |
| Difficulty | 180 paraphrase E; 20 preservation E; 110 near-neighbor C; 90 direct C; 120 technical N; 80 adjacent N | Ten natural evaluation categories | Names imply coverage, but mechanics do not: copy-plus-prefix entailments, explicit negations, and donor facts differ from CP-005's unmarked semantic decisions. |
| Concepts | 50 non-protected questions; JOIN term records: 0 | 10 held-out questions; five DA-017 JOIN anchors | Exact exclusion is correct, but no independent relational/JOIN reasoning coverage exists. |
| Split logic | 40 train questions / 10 dev questions | Fully frozen external evaluation | Question IDs are independent; authoring grammar and transformation families are not. |

There is zero training/evaluation question overlap and the CP-005 leakage controls remain valid. The failure is therefore not record leakage. It is distribution leakage between train and internal dev: both were produced by the same generator.

## 2. Training-corpus forensic analysis

- Exactly 50 questions contribute exactly 12 cases each: four per label. The same helper functions and slot schedule generate every train and dev question.
- Exclusive label-correlated opening markers occur in `170/200` entailments, `150/200` contradictions, and `180/200` neutrals. Wrong-label marker count is zero.
- The train/dev marker rates are nearly identical: E `85.0%/85.0%`, C `75.0%/75.0%`, N `89.4%/92.5%`.
- `153/180` records labelled `paraphrase_entailment` contain the entire normalized premise inside the hypothesis. Across all entailments, this is `173/200`.
- All `90` direct contradictions carry an explicit negation marker; `180/200` neutrals explicitly announce that the claim is separate/independent.
- Mean premise/hypothesis token-Jaccard is E `0.766`, C `0.671`, N `0.011`. This makes lexical overlap and wrapper vocabulary strong class shortcuts.
- `semantic_family_ids` encode only question IDs (and neutral donor question IDs). They do not encode generator, transformation, prefix, or mutation family, so the split validator cannot detect cross-split template reuse.
- Training consumed only premise, hypothesis, and label. Rationales/review metadata were not model inputs, so the problem is visible surface construction, not rationale leakage.

Assessment: the corpus is structurally valid, balanced, hash-frozen, externally reviewed, and leakage-controlled, but it is too easy and too template-like for the intended generalization claim. Human review can validate labels without making the generation distribution natural or independent.

## 3. Every-case prediction transition

- Fixed: `NLI-EVAL-007, NLI-EVAL-035`.
- Regressed/new failures: `NLI-EVAL-037, NLI-EVAL-041`.
- Unchanged failures: `NLI-EVAL-009, NLI-EVAL-018, NLI-EVAL-023, NLI-EVAL-042, NLI-EVAL-043, NLI-EVAL-045`. `NLI-EVAL-043` changes wrong class E->N but remains wrong.
- Unchanged correct: `35` cases.

| Case | Expected | Baseline | LoRA | Category | Δ gold probability |
|---|---:|---:|---:|---|---:|
| NLI-EVAL-001 | E | E | E | unchanged_correct | -0.001986 |
| NLI-EVAL-002 | N | N | N | unchanged_correct | -0.000916 |
| NLI-EVAL-003 | C | C | C | unchanged_correct | -0.000492 |
| NLI-EVAL-004 | E | E | E | unchanged_correct | -0.002538 |
| NLI-EVAL-005 | C | C | C | unchanged_correct | -0.059756 |
| NLI-EVAL-006 | E | E | E | unchanged_correct | -0.069781 |
| NLI-EVAL-007 | N | E | N | fixed | +0.925770 |
| NLI-EVAL-008 | C | C | C | unchanged_correct | +0.000803 |
| NLI-EVAL-009 | C | N | N | unchanged_failure | -0.002760 |
| NLI-EVAL-010 | N | N | N | unchanged_correct | -0.000482 |
| NLI-EVAL-011 | E | E | E | unchanged_correct | -0.004727 |
| NLI-EVAL-012 | N | N | N | unchanged_correct | -0.002806 |
| NLI-EVAL-013 | C | C | C | unchanged_correct | -0.038147 |
| NLI-EVAL-014 | E | E | E | unchanged_correct | -0.125847 |
| NLI-EVAL-015 | N | N | N | unchanged_correct | +0.000035 |
| NLI-EVAL-016 | E | E | E | unchanged_correct | -0.058230 |
| NLI-EVAL-017 | N | N | N | unchanged_correct | -0.000697 |
| NLI-EVAL-018 | C | N | N | unchanged_failure | +0.222943 |
| NLI-EVAL-019 | N | N | N | unchanged_correct | -0.000239 |
| NLI-EVAL-020 | C | C | C | unchanged_correct | -0.000386 |
| NLI-EVAL-021 | E | E | E | unchanged_correct | -0.049821 |
| NLI-EVAL-022 | N | N | N | unchanged_correct | -0.000176 |
| NLI-EVAL-023 | C | N | N | unchanged_failure | +0.062756 |
| NLI-EVAL-024 | C | C | C | unchanged_correct | -0.001554 |
| NLI-EVAL-025 | E | E | E | unchanged_correct | -0.155124 |
| NLI-EVAL-026 | N | N | N | unchanged_correct | +0.002015 |
| NLI-EVAL-027 | C | C | C | unchanged_correct | -0.005869 |
| NLI-EVAL-028 | N | N | N | unchanged_correct | -0.000707 |
| NLI-EVAL-029 | E | E | E | unchanged_correct | -0.126980 |
| NLI-EVAL-030 | C | C | C | unchanged_correct | -0.108804 |
| NLI-EVAL-031 | C | C | C | unchanged_correct | -0.216068 |
| NLI-EVAL-032 | N | N | N | unchanged_correct | +0.003324 |
| NLI-EVAL-033 | E | E | E | unchanged_correct | -0.347153 |
| NLI-EVAL-034 | N | N | N | unchanged_correct | -0.001140 |
| NLI-EVAL-035 | C | N | C | fixed | +0.490994 |
| NLI-EVAL-036 | N | N | N | unchanged_correct | -0.012295 |
| NLI-EVAL-037 | E | E | N | regressed_new_failure | -0.681430 |
| NLI-EVAL-038 | E | E | E | unchanged_correct | -0.010820 |
| NLI-EVAL-039 | N | N | N | unchanged_correct | -0.000466 |
| NLI-EVAL-040 | C | C | C | unchanged_correct | -0.164954 |
| NLI-EVAL-041 | E | E | C | regressed_new_failure | -0.674962 |
| NLI-EVAL-042 | E | C | C | unchanged_failure | -0.005169 |
| NLI-EVAL-043 | C | E | N | unchanged_failure | +0.039844 |
| NLI-EVAL-044 | N | N | N | unchanged_correct | +0.006692 |
| NLI-EVAL-045 | E | C | C | unchanged_failure | -0.001886 |

## 4. LoRA behavior

| Boundary | Baseline | LoRA | Interpretation |
|---|---|---|---|
| Entailment | precision/recall/F1 0.8667/0.8667/0.8667 | 1.0000/0.7333/0.8462 | More conservative E boundary; four fewer E predictions and two true-E regressions. |
| Neutral | 0.7778/0.9333/0.8485 | 0.7500/1.0000/0.8571 | Full recall, but broader N boundary and lower precision. |
| Contradiction | 0.8333/0.6667/0.7407 | 0.7857/0.7333/0.7586 | Better recall but worse precision; boundary expands into true entailments. |

Mean output-probability shift is E `-0.076967`, N `+0.042667`, C `+0.034300`. Average entropy rises `0.124460 -> 0.203240`, so there is no evidence of uniform global overconfidence. However, error confidence is localized and severe: mean max-confidence on the eight errors rises `0.830853 -> 0.867238`, with high-confidence LoRA errors on `NLI-EVAL-009, NLI-EVAL-041, NLI-EVAL-042, NLI-EVAL-045`.

Conclusion: the contradiction boundary is broader, not reliably better. The adapter learned useful signals for `007` and `035`, but it suppresses entailment and remains confidently wrong on the core relation-preserving paraphrases.

## 5. DA-017 deep analysis

Probabilities are shown E/N/C.

| Case | Expected | Baseline | LoRA | Transition | Diagnosis |
|---|---:|---|---|---|---|
| NLI-EVAL-041 | E | E (0.679402/0.024493/0.296105) | C (0.004440/0.007463/0.988097) | regressed_new_failure | New severe regression: the adapter turns a previously correct INNER JOIN paraphrase into a 0.988097 contradiction. |
| NLI-EVAL-042 | E | C (0.007968/0.010857/0.981175) | C (0.002799/0.032130/0.965071) | unchanged_failure | The original LEFT JOIN false contradiction remains, at 0.965071 contradiction after adaptation. |
| NLI-EVAL-043 | C | E (0.446733/0.392953/0.160314) | N (0.127469/0.672373/0.200158) | unchanged_failure | The prediction moves from false entailment to neutral, but still misses the required contradiction. |
| NLI-EVAL-044 | N | N (0.007348/0.972105/0.020547) | N (0.007729/0.978797/0.013473) | unchanged_correct | The unrelated Python statement remains a high-confidence neutral and is the only passing post-LoRA anchor. |
| NLI-EVAL-045 | E | C (0.002671/0.001515/0.995815) | C (0.000785/0.015610/0.983605) | unchanged_failure | The Egyptian Arabic LEFT JOIN entailment remains a very high-confidence contradiction (0.983605). |

### NLI-EVAL-041

- Premise: INNER JOIN يعيد الصفوف التي تحقق شرط الربط في كلا الجدولين فقط.
- Hypothesis: ال Inner Join يعيد الصفوف المتطابقة بين الجدولين.
- Most supported cause: The synthetic near-neighbor contradiction regime broadens the contradiction boundary around technical term/relation changes, while training contains no JOIN semantics and most entailments preserve the premise wording.
- Coverage assessment: Missing genuine relation-preserving paraphrases plus over-specialization to mutation templates; not label ambiguity.

### NLI-EVAL-042

- Premise: LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL.
- Hypothesis: ال left join يعيد كل الصفوف من الجدول الايسر حتى اذا لم يكن هناك تطابق.
- Most supported cause: No training example teaches the equivalence between the canonical LEFT JOIN definition and this natural Arabic/code-switched unmatched-left-row paraphrase.
- Coverage assessment: Insufficient semantic paraphrase and concept coverage; no evidence that the expected entailment label is ambiguous.

### NLI-EVAL-043

- Premise: LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL.
- Hypothesis: LEFT JOIN returns only matching rows and removes unmatched left rows.
- Most supported cause: The adapter learns to avoid entailment for some technical mismatches, but its simple lexical-replacement/explicit-negation contradictions do not teach the relational consequence that LEFT JOIN preserves unmatched left rows.
- Coverage assessment: Partial boundary movement, insufficient relational hard-negative reasoning; not a fixed case.

### NLI-EVAL-044

- Premise: LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL.
- Hypothesis: Python is commonly used for data analysis.
- Most supported cause: This is structurally similar to donor-based neutral training and does not exercise JOIN reasoning.
- Coverage assessment: Easy neutral/template match; it does not offset the four semantic JOIN failures.

### NLI-EVAL-045

- Premise: LEFT JOIN يعيد كل صفوف الجدول الأيسر مع الصفوف المطابقة من الجدول الأيمن، وتملأ مواضع عدم التطابق بقيم NULL.
- Hypothesis: ال LEFT JOIN يعيد كل الصفوف من الجدول الشمال حتى لو لا يوجد تطابق.
- Most supported cause: Egyptian training coverage is numeric but mostly a fixed wrapper around copied canonical text, not independently worded dialectal paraphrase of relational semantics.
- Coverage assessment: Surface-style quota met, semantic/dialect realization missing; expected label remains unambiguous.

DA-017 falls from `2/5` to `1/5` solely because `041` becomes a new failure; `042`, `043`, and `045` remain failures, while only the easy unrelated neutral `044` passes. The adapter does not learn JOIN semantics from the training set because no training record contains a JOIN relation.

## 6. Root-cause hypothesis ranking

| Rank | Hypothesis | Confidence | Evidence |
|---:|---|---|---|
| 1 | Cross-split authoring-template shortcut makes internal dev non-independent. | HIGH | All questions use the same 12-slot generator; label-exclusive wrappers cover 170/200 entailments, 150/200 contradictions, and 180/200 neutrals, with nearly identical train/dev rates; semantic_family_ids encode questions only, not generator/template families; dev reaches 1.0 while CP-005 does not improve. |
| 2 | Synthetic examples do not match natural semantic reasoning difficulty. | HIGH | Most purported paraphrase entailments retain the full premise; all direct contradictions have explicit negation markers; most neutrals announce independence; CP-005 errors are unmarked paraphrase, scope, and relational near-neighbor decisions. |
| 3 | Contradiction-focused mutations over-broaden the non-entailment boundary and suppress entailment. | HIGH | Predicted entailments drop 15->11; true-entailment recall drops 13/15->11/15; false contradictions rise 2->3; NLI-EVAL-041 flips from correct entailment to 0.988097 contradiction. |
| 4 | DA-017 relational concept and natural dialectal paraphrase coverage is absent. | HIGH | Zero training records contain a JOIN term; Egyptian/code-switch quotas are satisfied largely with wrappers around canonical text; DA-017 falls 2/5->1/5. |
| 5 | Base-family capacity/calibration remains a contributing limitation. | MEDIUM | Both the CP-006 checkpoint control and CP-009 adapter fail the critical false-contradiction/DA-017 gates, although they move other contradiction cases in useful directions. |
| 6 | Label imbalance, CP-005 leakage, or failed optimizer execution caused the gap. | REJECTED_BY_EVIDENCE | Labels are exactly balanced, frozen leakage checks are zero, hashes are unchanged, and training converged with validated artifacts. |

The CP-006 control strengthens this conclusion: the alternative checkpoint improved overall accuracy to `39/45` and macro F1 to `0.866270`, yet false contradictions stayed `2/15` and DA-017 stayed `2/5`. Changing weights can improve broad contradiction recognition, but neither checkpoint replacement nor the current templated LoRA resolves the critical relation-preserving paraphrase defect.

## 7. Failed assumptions

- A complete-question train/dev split was assumed to be sufficient; it did not isolate the shared generator and label wrappers.
- Difficulty labels such as paraphrase_entailment and near_neighbor_contradiction were assumed to imply natural reasoning diversity; generation mechanics show otherwise.
- Matching language/style counts was assumed to imply representative dialect/code-switch coverage; many examples are canonical text plus a fixed wrapper.
- Perfect internal dev was assumed to predict held-out gain; the dev set measured generalization to new questions under the same authoring grammar.
- Simple lexical mutations were assumed to teach technical relation boundaries; DA-017 requires compositional row-preservation/cardinality reasoning.

## 8. What must change before any future training

- Define and audit generator/template family IDs, then split them so no authoring template or transformation operator is shared between train and model-selection dev.
- Require independently worded natural Arabic, Egyptian, code-switched, and English pairs; reject copy-plus-prefix paraphrases and label-revealing wrappers.
- Add unmarked hard entailment/contradiction/neutral contrasts that vary one semantic relation, scope, direction, cardinality, or exception while preserving surface similarity.
- Cover relational technical reasoning through independent non-CP-005 concepts and examples; keep every CP-005 case/question/premise/hypothesis/pair excluded.
- Create a separate template-independent diagnostic/dev set for training selection; keep CP-005 frozen as the final acceptance set and do not tune to its 45 labels.
- Pre-register a one-variable comparison that can distinguish revised-data LoRA from a semantic-verifier/cascade alternative before authoring or training begins.

These are prerequisites, not authorization to author a new dataset or train.

## 9. LoRA versus another architecture

- Current adapter: **reject for promotion; preserve as evaluation evidence only**.
- LoRA approach: **pause, conditional—not abandoned**. A second run on the same corpus would repeat a falsified experiment. LoRA remains plausible only after a template-independent corpus and model-selection dev set exist.
- Alternative: a semantic-verifier/cascade deserves a controlled comparison if independent data cannot make a revised LoRA generalize. It has higher latency/calibration complexity, but the CP-006 and CP-009 controls show that weight changes alone have not repaired the critical false-contradiction/DA-017 objective.
- No architecture is selected for production by this diagnosis.

## 10. Exact next step

Await explicit Phase 2E design-only authorization to specify a template-independent corpus/diagnostic protocol and a pre-registered one-variable comparison between revised-data LoRA and a semantic-verifier/cascade. Do not author data, train, tune on CP-005, modify the adapter, or change production.

Stop. No data authoring, retraining, adapter modification, threshold/scoring change, or production promotion is authorized.
