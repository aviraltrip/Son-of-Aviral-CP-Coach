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
