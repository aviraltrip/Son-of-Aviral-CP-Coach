# Rule: Architecture & Multi-Agent Isolation Invariants

## 1. Information Asymmetry
- **Tutor Node**: Accepts ONLY `problem_statement`, `hint_level`, `history`, and `user_action`. Must never receive or search for the reference solution.
- **Keeper Node**: Reads `reference_solution` directly from private SQLite storage (`references` table) by `(contest_id, index)`. Never writes the reference solution to `CoachState`.
- **Analyst Node**: Reads from `submissions` and `topic_stats` tables. Runs deterministic scoring formulas in `stats.py`. Uses LLM only to format a friendly 2-3 sentence diagnosis for the user.

## 2. Graph State Purity
- `CoachState` holds only compact, serializable metadata:
  ```python
  class CoachState(TypedDict):
      handle: str
      diagnosis: Diagnosis | None
      problem: ProblemChoice | None
      problem_statement: str
      hint_level: int
      draft: HintDraft | None
      verdict: HintVerdict | None
      revisions: int
      history: list[dict]
      user_action: str | None
  ```
- Any PR or code change attempting to add reference solution or raw editorial text to `CoachState` is an architectural violation.

## 3. Tutor ⇄ Keeper Bounded Revision Loop
- Maximum allowed revisions: **3**.
- State transitions:
  - If `verdict.approved == True`: Transition to `wait_for_user`.
  - If `verdict.approved == False` and `revisions < 3`: Increment `revisions += 1` and route back to `tutor_node` with `verdict.reason`.
  - If `verdict.approved == False` and `revisions >= 3`: Inject pre-defined safe fallback hint, log revision failure, and transition to `wait_for_user`.
