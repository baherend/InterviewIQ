# CP-008 Phase 2B Corpus Quality Report

- Result: `PARTIAL PASS — STRUCTURE/EXACT LEAKAGE PASS; HUMAN REVIEW REQUIRED`.
- Candidate records: `600`; train `480`; dev `120`; complete question IDs `50` (`40/10`).
- Training-ready records: `0`. All 600 records are AI-authored candidates pending two independent human reviews and adjudication where required.
- No NLI model was loaded; no inference or training ran; no adapter checkpoint or production change exists.

## Distribution

| Dimension | Counts |
|---|---|
| Labels | entailment 200; contradiction 200; neutral 200 |
| Language | MSA 150; Egyptian 150; Arabic/English code-switch 180; transliteration 60; English diagnostic 60 |
| Difficulty | paraphrase entailment 180; entailment preservation 20; near-neighbor contradiction 110; direct contradiction 90; technical neutral 120; adjacent neutral 80 |
| Technical coverage | 600 / 600 |

## Leakage and integrity

- CP-005 SHA and `do_not_train=true`: verified.
- Protected CP-005 question-ID hits: `0`; additional DS-014 evaluation exclusion: enforced.
- Normalized evaluation premise/hypothesis/pair hits: `0/0/0`.
- Duplicate case IDs/pairs: `0/0`.
- Train/dev question overlap, semantic-family overlap, and paired-group overlap: `0/0/0`.
- Maximum token-Jaccard similarity against any CP-005 premise/hypothesis: `0.346154`; hard flags at `>=0.8`: `0`.
- Canonical source/provenance failures: `0`.
- Manual semantic-family review remains `PENDING`; automated similarity is not a substitute.

## Human review gate

- Every candidate requires two independent domain-qualified human reviewers.
- Near-neighbor contradictions and adjacent neutrals are explicitly ambiguity-flagged.
- Review must confirm the label, scope, language/dialect fidelity, source independence, and absence of a CP-005 semantic derivative.
- Disagreements require adjudication. No record may set `accepted_for_training=true` before this gate closes.

## Frozen hashes

- Corpus: `3FB523040C9B2482A0FCF0AAC8FDCC13D54E32AC2D9CB75DF5CE970E2E341F33`
- Review ledger: `676B20BBA54D7D7DAF3A1DE7386871324137CB28BBAAFFDF93A6B0792828FDA3`
- Split manifest: `157BE9BD9261411A89BA60F46D86DEF56664051AA0B3A2C7F29E18257B85D3F4`
- Preflight validation: `3FFCAA422B135F2390F23A1450EC8D54237D68DDC30B438CAB15C8924C3A790B`
- Reference corpus: `BA062768EB02C6DBE16D90024C30B075AF98F85D08B9E946BB26862AAB250F07`
- CP-005 exclusion source: `5AA1278465B99B4D88AAE94871181D2A768A91AB601AD1B4E2141CF0B2A8DC18`

## Exact next step

Complete two independent human reviews for all 600 candidates, adjudicate disagreements, rerun/freeze the corpus and leakage validation, and only then request separate LoRA training authorization. Do not load a model or train while any ledger entry remains pending.
