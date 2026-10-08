# Rule: Agent Contracts & Interfaces

## 1. Schema Validation
All agent inputs and outputs MUST be validated using Pydantic v2 schemas defined in `app/state.py`.

## 2. Agent Specifications

### Analyst Agent (`app/agents/analyst.py`)
- **Input**: User Codeforces handle (`str`).
- **Processing**:
  1. Calls `cf_client.py` to sync user submissions into `db.py`.
  2. Calls `stats.py` to compute `list[TopicStat]` and pick next `ProblemChoice`.
  3. LLM call formats a 2-3 sentence diagnostic summary explaining *why* this problem was chosen.
- **Output**: `{"diagnosis": Diagnosis, "problem": ProblemChoice, "problem_statement": str, "revisions": 0}`

### Tutor Agent (`app/agents/tutor.py`)
- **Input**: `problem_statement`, `hint_level` (1, 2, or 3), `history` (compact past turns), `verdict` (if revising after keeper feedback).
- **Processing**:
  - LLM drafts hint matching requested level.
  - If `verdict` is present with rejection feedback, tutor must adjust tone/content away from flagged leak.
- **Output**: `{"draft": HintDraft(level=..., text=...)}`

### Keeper Agent (`app/agents/keeper.py`)
- **Input**: `problem_statement`, `draft` (from Tutor), `hint_level`, private `reference_solution` (loaded from SQLite `references` table).
- **Processing**:
  - LLM compares the draft against the reference solution and grading rubric for `hint_level`.
  - Determines if the draft leaks the algorithm, data structures, or code.
- **Output**: `{"verdict": HintVerdict(approved=..., reason=..., leak_severity=...)}`

### Submission Checker (`app/graph.py` / `check_submission`)
- **Input**: `handle`, `problem`
- **Processing**:
  - Checks Codeforces API for latest submission on `problem.contest_id + problem.index`.
  - If verdict is `OK` (Accepted): Updates DB stats, clears active problem, routes to `analyst`.
  - If verdict is `WRONG_ANSWER`, `TIME_LIMIT_EXCEEDED`, etc.: Routes to `tutor` with targeted hint context.
