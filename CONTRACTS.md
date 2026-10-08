# Data Contracts & Schemas (`CONTRACTS.md`)

This document defines the definitive schemas, data models, typed dicts, SQLite DDL, and prompt rubrics for the CP Coach project.

---

## 1. Pydantic Models (`app/state.py`)

```python
from typing import Literal, TypedDict, Any
from pydantic import BaseModel, Field

class TopicStat(BaseModel):
    tag: str = Field(..., description="Codeforces algorithm/topic tag (e.g. dp, graphs, binary search)")
    solved_ratio: float = Field(..., ge=0.0, le=1.0, description="Accepted count / total attempts")
    avg_rating: float | None = Field(None, description="Average rating of solved problems with this tag")
    n_attempts: int = Field(..., ge=0, description="Total submission attempts for this tag")
    weighted_failure_score: float = Field(..., description="Computed failure score factoring decay & difficulty")

class Diagnosis(BaseModel):
    weak_topics: list[TopicStat] = Field(..., description="Ranked list of user's weakest topics")
    summary: str = Field(..., description="Natural language diagnostic explanation for the user")
    user_rating: int | None = Field(None, description="Current Codeforces user rating")

class ProblemChoice(BaseModel):
    contest_id: int = Field(..., description="Codeforces contest ID")
    index: str = Field(..., description="Problem index (e.g. A, B, C1)")
    name: str = Field(..., description="Problem name")
    rating: int | None = Field(None, description="Problem difficulty rating")
    tags: list[str] = Field(default_factory=list, description="Algorithm tags")
    reason: str = Field(..., description="Explanation of why this problem was selected")

class HintDraft(BaseModel):
    level: Literal[1, 2, 3] = Field(..., description="1 = Nudge, 2 = Approach, 3 = Pseudocode")
    text: str = Field(..., description="Drafted hint content")

class HintVerdict(BaseModel):
    approved: bool = Field(..., description="Whether the hint satisfies the safety & level rubric")
    reason: str = Field(..., description="Reason for approval or detailed feedback on why it was rejected")
    leak_severity: Literal["none", "minor", "major"] = Field(..., description="Severity of any detected leakage")

class UserMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = Field(...)
    content: str = Field(...)
    timestamp: float = Field(...)

class CoachState(TypedDict):
    handle: str
    diagnosis: Diagnosis | None
    problem: ProblemChoice | None
    problem_statement: str
    hint_level: int
    draft: HintDraft | None
    verdict: HintVerdict | None
    revisions: int
    history: list[dict[str, Any]]
    user_action: str | None
```

---

## 2. SQLite Database DDL (`app/data/db.py`)

```sql
CREATE TABLE IF NOT EXISTS users (
    handle TEXT PRIMARY KEY,
    current_rating INTEGER,
    max_rating INTEGER,
    last_synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS problems (
    contest_id INTEGER NOT NULL,
    idx TEXT NOT NULL,
    name TEXT NOT NULL,
    rating INTEGER,
    tags_json TEXT NOT NULL,
    PRIMARY KEY (contest_id, idx)
);

CREATE TABLE IF NOT EXISTS submissions (
    id INTEGER PRIMARY KEY,
    user_handle TEXT NOT NULL,
    contest_id INTEGER NOT NULL,
    idx TEXT NOT NULL,
    verdict TEXT NOT NULL,
    programming_language TEXT NOT NULL,
    pass_count INTEGER DEFAULT 0,
    time_consumed_ms INTEGER DEFAULT 0,
    memory_consumed_bytes INTEGER DEFAULT 0,
    creation_time_seconds INTEGER NOT NULL,
    FOREIGN KEY (user_handle) REFERENCES users(handle),
    FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx)
);

CREATE TABLE IF NOT EXISTS topic_stats (
    user_handle TEXT NOT NULL,
    tag TEXT NOT NULL,
    total_attempts INTEGER DEFAULT 0,
    total_accepted INTEGER DEFAULT 0,
    weighted_failure_score REAL DEFAULT 0.0,
    avg_rating_solved REAL,
    last_attempt_ts INTEGER,
    PRIMARY KEY (user_handle, tag),
    FOREIGN KEY (user_handle) REFERENCES users(handle)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    user_handle TEXT NOT NULL,
    contest_id INTEGER NOT NULL,
    idx TEXT NOT NULL,
    hints_requested INTEGER DEFAULT 0,
    keeper_rejections INTEGER DEFAULT 0,
    final_outcome TEXT, -- 'SOLVED', 'SKIPPED', 'ABANDONED'
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    FOREIGN KEY (user_handle) REFERENCES users(handle),
    FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx)
);

CREATE TABLE IF NOT EXISTS references (
    contest_id INTEGER NOT NULL,
    idx TEXT NOT NULL,
    solution_code TEXT,
    solution_editorial TEXT,
    source TEXT DEFAULT 'manual', -- 'manual', 'scraped', 'synthetic_validated'
    PRIMARY KEY (contest_id, idx),
    FOREIGN KEY (contest_id, idx) REFERENCES problems(contest_id, idx)
);
```

---

## 3. Hint Rubrics & Verification Rules

| Hint Level | Allowed Content | Strictly Forbidden Content |
| :--- | :--- | :--- |
| **Level 1: Nudge** | • Rephrasing problem constraints.<br>• Observing monotonic properties or parity.<br>• Suggesting broad concept families (e.g. "consider two pointers vs binary search"). | • Specific algorithmic names (e.g. "use Tarjan's algorithm", "use Dijkstra").<br>• Recurrence relations or formulas.<br>• Pseudo-code or variable definitions. |
| **Level 2: Approach** | • Step-by-step conceptual workflow.<br>• Data structure selection (e.g. "Maintain a Max-Heap for the top k items").<br>• Asymptotic complexity targets (e.g. "This needs to run in O(N log N)"). | • Code snippets in any programming language.<br>• Exact implementation details.<br>• Direct copy-pasteable formulas. |
| **Level 3: Pseudocode** | • Language-agnostic structured pseudocode.<br>• Explicit base cases & loop invariants.<br>• Edge-case checklist (overflow, zero-case, empty array). | • Complete runnable source code in C++, Python, Java, etc.<br>• Solution paste from competitive programming platforms. |
