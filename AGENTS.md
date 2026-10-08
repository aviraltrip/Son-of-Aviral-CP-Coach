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
- **Database**: SQLite (built-in `sqlite3` wrapped in `app/data/db.py`)
- **UI**: `streamlit>=1.35.0`
- **Testing**: `pytest>=8.0.0`, `pytest-mock`
- **Evals**: Custom evaluators in `evals/` with baseline comparison

---

## 4. Directory Structure

```text
cp-coach/
├── app/
│   ├── state.py            # Pydantic schemas & CoachState TypedDict
│   ├── graph.py            # LangGraph StateGraph, conditional edges, routing
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── analyst.py      # Data-driven diagnostics & problem selection node
│   │   ├── tutor.py        # Solution-blind hint drafting node
│   │   ├── keeper.py       # Solution-aware hint validation & grading node
│   │   └── judge.py        # (Phase 8) Code execution / sandbox node
│   ├── data/
│   │   ├── __init__.py
│   │   ├── cf_client.py    # Codeforces API client with polite rate limiting & disk caching
│   │   ├── db.py           # SQLite database schema, CRUD methods, connection handling
│   │   └── stats.py        # Deterministic scoring, exponential decay, shrinkage formulas
│   ├── prompts/
│   │   ├── analyst_prompt.py
│   │   ├── tutor_prompt.py
│   │   ├── keeper_prompt.py
│   │   └── targeted_hint_prompt.py
│   └── ui/
│       └── streamlit_app.py # Streamlit UI for interaction, charts & agent trace
├── evals/
│   ├── leakage_eval.py     # Independent LLM judge for hint leakage evaluation
│   ├── baseline_single.py  # Single-agent direct baseline for comparative benchmarking
│   └── dataset.json        # Test set of (problem, reference_solution, hint_history)
├── tests/
│   ├── test_stats.py       # Unit tests for scoring, decay & Bayesian shrinkage
│   ├── test_db.py          # Unit tests for SQLite CRUD
│   ├── test_graph_flow.py  # Unit & integration tests for LangGraph state machine
│   └── test_tutor_keeper.py# Tests for verification loop & revision capping
├── .agents/
│   └── rules/              # Modular Antigravity & AI context rules
├── CONTEXT.md              # Project overview & mathematical background
├── ARCHITECTURE.md         # Detailed system architecture & Mermaid diagrams
├── CONTRACTS.md            # Pydantic schemas, typed dicts & DB tables
├── PHASES.md               # Phased implementation roadmap & deliverables
├── EVALS.md                # Evaluation strategy & benchmark metrics
├── .env.example            # Environment variables template
├── requirements.txt        # Locked dependencies
└── README.md
```

---

## 5. Coding Standards & Conventions

1. **Strict Type Annotations**: Every function and method must have explicit input types and return types.
2. **Error Handling & Resilience**:
   - CF API requests must handle HTTP 429 / 503 errors gracefully with exponential backoff and polite rate limiting (1 request per 2 seconds).
   - Database operations must use context managers and parameterized queries (no f-string SQL).
3. **Prompt Engineering**:
   - Prompts must be externalized in `app/prompts/`.
   - Tutor prompts must explicitly instruct the model to adhere strictly to the requested hint level rubric.
   - Keeper prompts must explicitly test for algorithmic leakage, variable name spoilers, and premature complexity revelations.
4. **No Hallucinated Imports**: Only use libraries listed in `requirements.txt`. Do not invent non-existent LangGraph or LangChain APIs.

---

## 6. How to Build & Test Each Phase

- Run unit tests: `pytest tests/ -v`
- Run the CLI loop: `python -m app.graph`
- Run the Streamlit UI: `streamlit run app/ui/streamlit_app.py`
- Run Leakage Evals: `python -m evals.leakage_eval`
