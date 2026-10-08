# Rule: Code Standards & Practices

## 1. Python 3.11+ Standards
- Use modern type hinting: `list[str]`, `dict[str, int]`, `tuple[int, ...]`, `int | None`.
- Do NOT import `List`, `Dict`, `Tuple`, `Optional`, `Union` from `typing` unless dealing with legacy third-party library constraints.
- Use explicit Pydantic v2 patterns: `model_dump()`, `model_validate()`, `Field(default=...)`.

## 2. SQLite / Database Access (`app/data/db.py`)
- Database access MUST be centralized in `app/data/db.py`.
- Schema migrations and initialization must be idempotent (`CREATE TABLE IF NOT EXISTS`).
- Always use parameterized queries: `cursor.execute("SELECT * FROM problems WHERE contest_id = ?", (contest_id,))`.
- Provide typed helper functions for all queries (e.g., `get_user_submissions(handle: str) -> list[dict]`, `get_reference_solution(contest_id: int, idx: str) -> str | None`).

## 3. Codeforces API Client (`app/data/cf_client.py`)
- Rate Limit: Maximum 1 request per 2 seconds (using `time.sleep` or token bucket).
- Disk Caching: Cache raw responses in a local SQLite table or `.cache/` folder with sensible TTLs (e.g., problem set cached for 24h, user info cached for 5m).
- Error Handling: Handle network timeouts, HTTP 400 (handle not found), 429 (rate limit), 503 (CF maintenance) with descriptive custom exceptions (`CFAPIError`, `CFUserNotFoundError`).

## 4. LangGraph Best Practices
- Nodes must be pure functions taking state and returning a partial state dictionary: `def my_node(state: CoachState) -> dict[str, Any]:`.
- Use conditional edges for branching logic: `builder.add_conditional_edges("keeper", should_continue_or_wait)`.
- Use LangGraph interrupts or checkpointer snapshots for user interaction checkpoints (`wait_for_user`).
