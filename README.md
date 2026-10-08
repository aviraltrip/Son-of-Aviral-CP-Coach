# 🏆 CP Coach: Multi-Agent Competitive Programming Coach

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/orchestration-LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic v2](https://img.shields.io/badge/validation-Pydantic%20v2-green.svg)](https://docs.pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/ui-Streamlit-red.svg)](https://streamlit.io/)

A multi-agent coaching system that connects to your **Codeforces** history, calculates your weak algorithmic topics using exponential decay and empirical Bayes shrinkage, picks a tailored practice problem, and coaches you with **graded, 3-tier hints that strictly never leak the solution**.

---

## 🎯 The Core Problem & Multi-Agent Justification

Standard LLMs and editorial walkthroughs spoil competitive programming problems by immediately revealing the key observation or full algorithm. Once spoiled, the active recall and problem-solving growth is lost.

CP Coach solves this through **Multi-Agent Information Asymmetry**:
- **Tutor Agent**: Sees *only* the problem statement and user chat history. It drafts hints at the requested tier (Level 1: Nudge, Level 2: Approach, Level 3: Pseudocode) without ever seeing the reference solution.
- **Keeper Agent**: An independent auditor that sees the reference solution (loaded privately from database storage) and verifies that the Tutor's draft does not leak algorithms, variable names, or solutions.
- **Analyst Agent**: Evaluates submission history, computes weak topics using deterministic math, and selects an optimal problem.

---

## 🏗️ Architecture & State Machine

```mermaid
flowchart TD
    START([START]) --> Analyst[Analyst Agent]
    Analyst --> WaitForUser1{wait_for_user interrupt}
    
    WaitForUser1 -- "request_hint" --> Tutor[Tutor Agent]
    WaitForUser1 -- "skip" --> Analyst
    WaitForUser1 -- "submitted" --> CheckSub[Check Submission]
    WaitForUser1 -- "done" --> END([END])
    
    Tutor --> Keeper[Keeper Agent]
    Keeper -- "rejected (revisions < 3)" --> Tutor
    Keeper -- "approved OR revisions == 3" --> WaitForUser2{wait_for_user interrupt}
    
    WaitForUser2 -- "request_hint" --> Tutor
    WaitForUser2 -- "submitted" --> CheckSub
    WaitForUser2 -- "skip" --> Analyst
    WaitForUser2 -- "done" --> END
    
    CheckSub -- "Verdict: AC" --> UpdateStats[Update Stats in DB] --> Analyst
    CheckSub -- "Verdict: WA / TLE" --> Tutor
```
