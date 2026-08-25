# InterviewIQ Agent Entry Point

The authoritative repository rules are in [AGENT_RULES.md](AGENT_RULES.md).

At the start of every session, read in this order:

1. `AGENT_RULES.md`
2. `EXECUTION_STATE.json`
3. `CURRENT_TASK.md`
4. Only the relevant sections of `PROJECT_SPEC.md`, `PROJECT_MEMORY.md`, `DECISIONS.md`, `EVIDENCE_LEDGER.md`, and `KNOWN_ISSUES.md`

Resume from `EXECUTION_STATE.json.next_step`. Do not restart completed verified work.
