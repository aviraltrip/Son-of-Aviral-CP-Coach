# Implementation Roadmap & Phases (`PHASES.md`)

This document tracks the phased implementation plan, milestones, deliverables, and definition of done (DoD) for each phase of the **CP Coach** project.

---

## Phase Summary

```
Phase 0: LangGraph Fundamentals & Environment Setup (1-2 days)
Phase 1: Contracts, Schemas & Stubbed State Machine (2 days)
Phase 2: Real Analyst, CF API Client & Deterministic Stats (3-4 days)
Phase 3: Real Tutor & Keeper Agents with Information Asymmetry (5-6 days)
Phase 4: Real-time Submission Checking & Progress Loop (2-3 days)
Phase 5: Single-Chain Baseline Implementation (3-4 days)
Phase 6: Comprehensive Evaluations & Leakage Benchmarking (3-4 days)
Phase 7: Streamlit UI, Visualizations & Agent Trace (3-4 days)
Phase 8: [Optional] Sandbox Code Judge Execution (1 week)
```

---

## Phase Details & Deliverables

### Phase 0: Environment & Core Setup
- **Goal**: Establish project structure, dependencies, LangGraph runtime, and local virtual environment.
- **Tasks**:
  1. Configure `requirements.txt`, `.env.example`, `.gitignore`.
  2. Validate LangGraph checkpointer and interrupt capabilities in Python 3.11.
- **Definition of Done (DoD)**: Environment installs without dependency conflicts; basic `langgraph` test passes.

---

### Phase 1: Contracts, Schemas & Stubbed Graph
- **Goal**: Wire the full end-to-end state machine with stubbed data before writing complex logic.
- **Tasks**:
  1. Implement `app/state.py` with all Pydantic models (`Diagnosis`, `ProblemChoice`, `HintDraft`, `HintVerdict`, `CoachState`).
  2. Implement stubbed agent nodes returning dummy data (`app/agents/analyst.py`, `app/agents/tutor.py`, `app/agents/keeper.py`).
  3. Wire the parent graph in `app/graph.py` with conditional edges and interrupt at `wait_for_user`.
- **Definition of Done (DoD)**: The state machine executes end-to-end via CLI (`python -m app.graph`), simulating hints, keeper verification loop (up to 3 revisions), and interrupts.

---

### Phase 2: Real Analyst, CF Client & Stats Engine ✅ [COMPLETED]
- **Goal**: Connect to Codeforces API, calculate actual user topic statistics, and recommend appropriate problems.
- **Tasks**:
  1. Build `app/data/cf_client.py` with polite rate limiting (1 req / 2s), disk caching, and error resilience.
  2. Build `app/data/db.py` SQLite tables for `users`, `problems`, `submissions`, `topic_stats`.
  3. Implement deterministic scoring formulas in `app/data/stats.py` (exponential decay with 30-day half-life, difficulty weighting, empirical Bayes shrinkage).
  4. Implement problem filtering (+100 to +200 rating window, unattempted problems).
- **Definition of Done (DoD)**: CLI accepts a Codeforces handle, fetches recent submissions, populates SQLite, prints ranked weak topics with stats, and recommends a valid problem.

---

### Phase 3: Real Tutor & Keeper Verification Engine
- **Goal**: Implement the core multi-agent information asymmetry loop with LLM prompts.
- **Tasks**:
  1. Create private reference storage table and ingestion pipeline for reference solutions.
  2. Implement `app/prompts/tutor_prompt.py` with strict Level 1, Level 2, Level 3 guidelines.
  3. Implement `app/prompts/keeper_prompt.py` with adversarial safety and spoiler auditing.
  4. Connect LLMs: Strong model for Tutor (e.g., Claude 3.5 Sonnet / GPT-4o / Gemini Pro), efficient model for Keeper (e.g., GPT-4o-mini / Gemini Flash).
  5. Add SQLite checkpointer (`SqliteSaver`) for session persistence across interrupts.
- **Definition of Done (DoD)**: End-to-end hint session runs; Keeper actively detects and rejects over-revealing hints; revision loop terminates safely within 3 turns.

---

### Phase 4: Submission Checking & Feedback Loop
- **Goal**: Automatically check user submissions and adapt coaching dynamically.
- **Tasks**:
  1. Implement `check_submission` node in `app/graph.py` to poll CF API for active problem verdict.
  2. If Accepted (AC): Update stats in SQLite, log session outcome, and route back to Analyst.
  3. If WA/TLE/MLE: Route to Tutor with targeted hint prompt highlighting potential pitfalls without revealing the answer.
- **Definition of Done (DoD)**: Graph responds dynamically to real submissions, distinguishing AC from WA.

---

### Phase 5: Single-Chain Baseline
- **Goal**: Build a single-agent baseline without a Keeper to serve as an experimental control.
- **Tasks**:
  1. Implement `evals/baseline_single.py` where a single prompt generates hints directly.
- **Definition of Done (DoD)**: Baseline produces reproducible hint outputs on test problem sets.

---

### Phase 6: Evals & Leakage Benchmarking
- **Goal**: Scientifically prove that the multi-agent system prevents leakage compared to single-agent baselines.
- **Tasks**:
  1. Build evaluation dataset in `evals/dataset.json` (20-30 diverse Codeforces problems across DP, Graphs, Greedy, Math).
  2. Build `evals/leakage_eval.py` utilizing an independent LLM judge with full solution access.
  3. Calculate metrics: Leakage Rate, Keeper Rejection Rate, Revision Count, Token Cost, Latency.
- **Definition of Done (DoD)**: Complete comparative evaluation table generated and documented in `README.md`.

---

### Phase 7: Streamlit UI & Visual Dashboard
- **Goal**: Deliver a polished, interactive web interface for competitive programmers.
- **Tasks**:
  1. Implement `app/ui/streamlit_app.py`.
  2. UI features: CF Handle input, Radar/Bar chart of weak topics, Problem statement viewer, 3-Tier Hint Buttons, Real-time multi-agent reasoning trace.
- **Definition of Done (DoD)**: User can complete a full coaching session in the browser with live agent feedback.

---

### Phase 8 (Optional): Sandbox Code Judge
- **Goal**: Local code execution against test cases.
- **Tasks**:
  1. Docker or Judge0 integration with memory and CPU cgroups.
  2. Brute-force test generator for automated verification.
