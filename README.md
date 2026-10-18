# Son of Aviral: Multi-Agent Competitive Programming Coach

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.2+-orange.svg)](https://github.com/langchain-ai/langgraph)
[![Pydantic v2](https://img.shields.io/badge/Pydantic%20v2-green.svg)](https://docs.pydantic.dev/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.35+-red.svg)](https://streamlit.io/)
[![Docker](https://img.shields.io/badge/Docker-Production--Hardened-2496ED.svg)](https://www.docker.com/)

A multi-agent coaching system that connects to your **Codeforces** history, calculates your weak algorithmic topics using exponential decay and empirical Bayes shrinkage, picks a tailored practice problem, and coaches you with **graded, 3-tier hints that strictly never leak the solution**.

Named in homage to Gilfoyle’s sentient creation **Son of Anton** from *Silicon Valley*, **Son of Aviral** was built out of deep contempt for inefficiency and manual editorial lookups. It exists to automate your algorithmic progression and ensure you stop submitting O(N^3) brute-force solutions on Test 2.

---

## 1. Core Architecture & Multi-Agent Justification

Standard LLMs and editorial walkthroughs spoil competitive programming problems by immediately revealing the key observation or full algorithm. Once spoiled, active recall and problem-solving growth is lost.

CP Coach solves this through **Multi-Agent Information Asymmetry**:
- **Tutor Agent**: Sees *only* the problem statement and user chat history. It drafts hints at the requested tier (Level 1: Nudge, Level 2: Approach, Level 3: Pseudocode) without ever seeing the reference solution.
- **Keeper Agent**: An independent auditor that loads the reference solution privately from database storage and verifies that the Tutor's draft does not leak algorithms, variable names, or solutions.
- **Judge Agent**: Executes code submissions locally in an isolated sandbox (C++17, Python 3, Java) or via remote Judge0 CE with CPU timeout/memory limits and differential stress fuzzing against ground-truth reference code.
- **Analyst Agent**: Evaluates submission history, computes weak topics using deterministic math, and selects an optimal problem.

---

## 2. Production Hardening Features

This system includes enterprise-grade security and reliability enhancements:
- **Sandbox Isolation & Environment Sanitization**: Subprocess execution environments are completely stripped of system credentials and LLM API keys. Dynamic Python introspection (`__subclasses__`, `__builtins__`) and C++ file system operations are blocked by multi-layer static guards.
- **Unprivileged Container Execution**: Docker container runs as a dedicated non-root `appuser` (UID 1001) with dropped Linux capabilities (`cap_drop: [ALL]`) and `no-new-privileges: true`.
- **Nginx Reverse Proxy**: Includes rate-limiting zones, WebSocket upgrade handling for Streamlit, and security headers (`X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`).
- **Database Concurrency & SQLite WAL Mode**: Eliminates database lock contention via `PRAGMA journal_mode = WAL;`, `synchronous = NORMAL;`, and a 5000ms busy timeout. Redundant DDL execution across query loops is eliminated with one-time execution caching.
- **Persistent LangGraph Checkpointer**: Thread states and human-in-the-loop pauses persist across container restarts using `SqliteSaver`.
- **Token-Bucket Rate Limiter**: User-tier limits protect against denial-of-service and LLM credit exhaustion.
- **Fail-Fast Production LLM Guard**: Replaces silent mock fallbacks with explicit alerting in production mode.
- **Health Checks & Telemetry**: Dual health monitoring script (`healthcheck.py`) testing HTTP web availability and SQLite schema integrity.
- **LangSmith Distributed Tracing**: Native full-lifecycle execution tracing, latency/cost attribution, and human-in-the-loop feedback logging.

---

## 3. Configuration

```bash
cp .env.example .env
```

| Key | Default | Description |
| :--- | :--- | :--- |
| `OPENROUTER_API_KEY` | — | Primary LLM key (or `GOOGLE_API_KEY`) |
| `TUTOR_MODEL_NAME` | `openrouter/free` | Hint generator model |
| `KEEPER_MODEL_NAME` | `openrouter/free` | Safety auditor model |
| `ANALYST_MODEL_NAME` | `openrouter/free` | Diagnostics model |
| `JUDGE_BACKEND` | `isolated_subprocess` | Code execution engine |
| `DATABASE_PATH` | `cp_coach.db` | SQLite storage path |

---

## 4. Running & Deployment

### Local Setup
```bash
pip install -r requirements.txt
streamlit run app/ui/streamlit_app.py
```

### Docker (Production + Nginx)
```bash
docker compose up --build -d
# Accessible at http://localhost
```

### Streamlit Community Cloud (Free)
1. Deploy from [share.streamlit.io](https://share.streamlit.io/) with file path `app/ui/streamlit_app.py`.
2. In **Advanced settings → Secrets**, paste:
   ```toml
   OPENROUTER_API_KEY = "sk-or-v1-..."
   TUTOR_MODEL_NAME = "openrouter/free"
   KEEPER_MODEL_NAME = "openrouter/free"
   ANALYST_MODEL_NAME = "openrouter/free"
   ```

---

## 5. Automated Tests

```bash
pytest tests/ -v
```
Runs 107 deterministic offline tests covering multi-agent loops, sandbox security, and rating statistics with zero API quota usage.
