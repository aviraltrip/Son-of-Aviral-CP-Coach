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

---

## 📂 Project Structure

```text
cp-coach/
├── app/
│   ├── state.py            # Pydantic schemas (Diagnosis, ProblemChoice, HintDraft, HintVerdict, CoachState)
│   ├── graph.py            # Parent LangGraph StateGraph, conditional edges, routing & interrupt
│   ├── agents/
│   │   ├── analyst.py      # Computes weak topics, problem selector, diagnosis generator
│   │   ├── tutor.py        # Solution-blind hint drafting node
│   │   ├── keeper.py       # Solution-aware hint validation & grading node
│   │   └── judge.py        # (Phase 8) Sandbox code execution node
│   ├── data/
│   │   ├── cf_client.py    # Codeforces API client with rate limiting & caching
│   │   ├── db.py           # SQLite database schema, CRUD methods, private reference store
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
│   └── dataset.json        # Benchmark dataset (20-30 problems)
├── tests/
│   ├── test_stats.py       # Unit tests for scoring & decay formulas
│   ├── test_db.py          # Unit tests for SQLite DB operations
│   ├── test_graph_flow.py  # LangGraph state machine flow tests
│   └── test_tutor_keeper.py# Verification loop & revision capping tests
├── .agents/
│   └── rules/              # Antigravity & AI assistant rule definitions
├── CONTEXT.md              # In-depth context & mathematical formulas
├── ARCHITECTURE.md         # Detailed technical design & ER diagrams
├── CONTRACTS.md            # Pydantic schemas, TypedDicts & DDL
├── PHASES.md               # Phased roadmap (Phases 0 - 8)
├── EVALS.md                # Evaluation framework & metric definitions
├── requirements.txt        # Pinned python dependencies
└── .env.example            # Environment variables template
```

---

## 🚀 Quickstart Guide

### 1. Clone & Setup Environment
```bash
git clone https://github.com/your-username/Son-of-Aviral-CP-Coach.git
cd Son-of-Aviral-CP-Coach

python -m venv venv
# On Windows:
.\venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Configure API Keys
Copy `.env.example` to `.env` and set your preferred model API key (e.g. Gemini, OpenAI, or Anthropic):
```bash
cp .env.example .env
```

### 3. Run Tests
```bash
pytest tests/ -v
```

### 4. Run the Streamlit UI
```bash
streamlit run app/ui/streamlit_app.py
```

---

## 📊 Evaluation & Verification

To evaluate leakage rates against a single-agent baseline:
```bash
python -m evals.leakage_eval
```

Results compare:
- **Leakage Rate (%)**: Rate at which forbidden algorithms/code leak to the user.
- **Rejection Rate (%)**: Frequency of Keeper catching over-revealing hints.
- **Revision Counts**: Turns required to produce safe pedagogical hints.
