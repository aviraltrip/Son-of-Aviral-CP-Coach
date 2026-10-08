"""State definitions and Pydantic schemas for CP Coach."""
from typing import Literal, TypedDict, Any
from pydantic import BaseModel, Field

class TopicStat(BaseModel):
    tag: str = Field(..., description="Codeforces algorithm/topic tag (e.g. dp, graphs, binary search)")
    solved_ratio: float = Field(..., ge=0.0, le=1.0, description="Accepted count / total attempts")
    avg_rating: float | None = Field(None, description="Average rating of solved problems with this tag")
    n_attempts: int = Field(..., ge=0, description="Total submission attempts for this tag")
    weighted_failure_score: float = Field(0.0, description="Computed failure score factoring decay & difficulty")

class Diagnosis(BaseModel):
    weak_topics: list[TopicStat] = Field(default_factory=list, description="Ranked list of user's weakest topics")
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
    leak_severity: Literal["none", "minor", "major"] = Field("none", description="Severity of any detected leakage")

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
