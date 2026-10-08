# AI Assistant & Pair Programmer Instructions (`AGENTS.md`)

This file contains binding architectural rules, code standards, and operational invariants for any AI assistant working on the **CP Coach** codebase.

---

## 1. Project Mission & Identity
CP Coach is a multi-agent LangGraph system that analyzes Codeforces history, determines weak algorithmic topics, recommends a tailored problem, and guides the user using a verified 3-tiered hint loop (Tutor ⇄ Keeper) without spoiling the answer.

---

## 2. Cardinal Invariants (DO NOT VIOLATE)

### Rule 1: Structural Information Asymmetry
- **NEVER** put reference solutions, editorial code, or full official solutions into the shared graph state (`CoachState`).
- The **Tutor Agent** MUST NOT have access to the reference solution or know the editorial algorithm.
- The **Keeper Agent** is the ONLY agent that loads reference solutions from the `references` database table.
- Shared graph state (`CoachState`) must only contain: IDs, diagnostic metadata, hint level, current hint draft, hint verdict, revision count, and compact message history.

### Rule 2: Deterministic Logic First, LLMs Second
- **DO NOT** use LLMs to calculate weak topics, parse submissions, compute statistics, or filter problems.
- All scoring (decay, difficulty weighting, shrinkage), filtering, and database operations belong in `app/data/stats.py` and `app/data/db.py`.
- LLMs are reserved strictly for:
  1. The Analyst's short textual summary/diagnosis.
  2. The Tutor's hint generation.
  3. The Keeper's hint safety verification.
  4. Targeted error explanation when WA/TLE occurs.

### Rule 3: Bounded Revision Loops & Fallback
- The `Tutor ⇄ Keeper` revision loop MUST be capped at a maximum of **3 revisions** (`revisions >= 3`).
- If rejected on the 3rd attempt, the graph MUST fall back to a predefined, safe generic hint rather than spinning or failing.

### Rule 4: Data Layer Encapsulation
- **ALL** SQLite database access MUST go through `app/data/db.py`.
- No raw SQL queries or direct `sqlite3.connect` calls outside of `db.py`. This ensures straightforward migration to PostgreSQL if needed.

### Rule 5: State & Memory Hygiene
- Keep `CoachState` lean. Never store full API payloads or megabytes of text in state. Store summaries, IDs, and compact message records.
- Use LangGraph checkpointing (`SqliteSaver` or `MemorySaver`) for human-in-the-loop pauses at `wait_for_user`.

---

## 3. Technology Stack & Dependencies

- **Language**: Python 3.11+ (modern typing: `list[str]`, `dict[str, Any]`, `X | None`, `Self`)
- **Orchestration**: `langgraph>=0.2.0`, `langchain-core>=0.3.0`
- **Schemas**: `pydantic>=2.7.0` (Use Pydantic v2 conventions: `model_dump()`, `Field()`, `field_validator`)
