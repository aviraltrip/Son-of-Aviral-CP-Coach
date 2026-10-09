"""State definitions and Pydantic schemas for CP Coach."""
import time
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

class TestCase(BaseModel):
    contest_id: int = Field(..., description="Codeforces contest ID")
    idx: str = Field(..., description="Problem index")
    test_index: int = Field(1, description="1-indexed test case number")
    input_data: str = Field(..., description="Test case standard input")
    expected_output: str = Field(..., description="Expected standard output")
    is_sample: bool = Field(False, description="Whether this is an official sample test case")

class CodeSubmission(BaseModel):
    language: str = Field("cpp", description="Language: cpp, python3, java")
    source_code: str = Field(..., description="Submitted program source code")
    timestamp: float = Field(default_factory=time.time, description="Submission timestamp")

class TestCaseResult(BaseModel):
    test_index: int = Field(..., description="1-indexed test case number")
    verdict: str = Field(..., description="Test result: AC, WA, TLE, MLE, RE, CE")
    time_ms: float = Field(0.0, description="Execution time in ms")
    memory_kb: float = Field(0.0, description="Memory used in KB")
    input_snippet: str = Field("", description="Input preview snippet")
    user_output: str = Field("", description="Output produced by candidate code")
    expected_output: str = Field("", description="Expected reference output")
    error_message: str = Field("", description="Error message or diff")

class JudgeVerdict(BaseModel):
    status: Literal["AC", "WA", "TLE", "MLE", "CE", "RE", "UNKNOWN"] = Field(..., description="Overall evaluation verdict")
    passed_count: int = Field(0, description="Number of passed test cases")
    total_count: int = Field(0, description="Total number of evaluated test cases")
    time_consumed_ms: float = Field(0.0, description="Max or total execution time in ms")
    memory_consumed_bytes: int = Field(0, description="Peak memory consumed in bytes")
    compiler_output: str = Field("", description="Compiler warnings or compilation error details")
    failing_test_index: int | None = Field(None, description="1-indexed number of first failing test case")
    failing_test_result: TestCaseResult | None = Field(None, description="Detailed result of the failing test")
    detailed_results: list[TestCaseResult] = Field(default_factory=list, description="Per-test results")

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
    last_submission_verdict: str | None
    submission_code: CodeSubmission | None
    judge_verdict: JudgeVerdict | None
