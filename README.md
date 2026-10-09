# CP Coach: Multi-Agent Competitive Programming Coach

[![Python](https://img.shields.io/badge/Python-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic v2](https://img.shields.io/badge/Pydantic%20v2-green.svg)](https://docs.pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-red.svg)](https://streamlit.io/)

A multi-agent coaching system that connects to your **Codeforces** history, calculates your weak algorithmic topics using exponential decay and empirical Bayes shrinkage, picks a tailored practice problem, and coaches you with **graded, 3-tier hints that strictly never leak the solution**.

Named in homage to Gilfoyle’s sentient creation **Son of Anton** from *Silicon Valley*, **Son of Aviral** was built out of deep contempt for inefficiency and manual editorial lookups. It exists to automate your algorithmic progression and ensure you stop submitting O(N^3) brute-force solutions on Test 2.

---

## The Core Problem & Multi-Agent Justification

Standard LLMs and editorial walkthroughs spoil competitive programming problems by immediately revealing the key observation or full algorithm. Once spoiled, the active recall and problem-solving growth is lost.

CP Coach solves this through **Multi-Agent Information Asymmetry**:
- **Tutor Agent**: Sees *only* the problem statement and user chat history. It drafts hints at the requested tier (Level 1: Nudge, Level 2: Approach, Level 3: Pseudocode) without ever seeing the reference solution.
- **Keeper Agent**: An independent auditor that sees the reference solution (loaded privately from database storage) and verifies that the Tutor's draft does not leak algorithms, variable names, or solutions.
- **Judge Agent**: Executes code submissions locally in an isolated sandbox (C++17, Python 3, Java) with CPU timeout/memory limits and differential stress fuzzing against ground-truth reference code.
- **Analyst Agent**: Evaluates submission history, computes weak topics using deterministic math, and selects an optimal problem.

---

## Architecture & State Machine

```mermaid
flowchart TD
    START([Start]) --> Analyst[Analyst: Select Problem]
    Analyst --> UserAction{User Action}

    subgraph HintLoop ["Hint Safety Loop"]
        Tutor[Tutor: Draft Hint] --> Keeper{Keeper: Audit Draft}
        Keeper -- "Leak detected (rev < 3)" --> Tutor
    end

    UserAction -- "Request Hint" --> Tutor
    Keeper -- "Approved" --> UserAction

    UserAction -- "Submit Sandbox / Remote" --> Judge{Judge & Submission Node}
    Judge -- "Accepted (AC)" --> Analyst
    Judge -- "WA / TLE / CE" --> Tutor

    UserAction -- "Skip" --> Analyst
    UserAction -- "Exit" --> END([End Session])
```

---

## Running with Docker

You can run CP Coach using Docker and Docker Compose:

```bash
# 1. Build and run container
docker compose up --build -d

# 2. Access the Streamlit dashboard
# Open http://localhost:8501 in your browser

# 3. View logs
docker compose logs -f
```


