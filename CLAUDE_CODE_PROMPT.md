# CLAUDE CODE PROMPT — ductape

Read these files in the repo before doing anything:
1. `ARCHITECTURE_FINAL_v3.md` — full specification (the source of truth for all design decisions)
2. `docs/build-phases.md` — phased build plan with acceptance criteria per phase

Follow `docs/build-phases.md` exactly. Build phase by phase. Run tests after each phase.
Do not move to the next phase until the current phase's acceptance criteria all pass.

After Phase 10, run ALL five acceptance checks. If any fail, fix and re-run from the top.

Constraints:
- Python 3.10+, only PyYAML and pytest as dependencies
- Generated C++ must compile with `g++ -std=c++17`
- Keep solutions minimal — no over-engineering

Do not stop until all acceptance criteria in Phase 10 pass.
