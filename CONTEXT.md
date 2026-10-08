# Project Context: CP Coach (Multi-Agent Competitive Programming Coach)

## 1. Project Overview & Vision

**CP Coach** is an intelligent, multi-agent coaching system built with **Python 3.11+**, **LangGraph**, **Pydantic**, **SQLite**, and **Streamlit**. It connects to a user's Codeforces profile, analyzes their past contest and submission history to identify weak algorithm topics, recommends suitably challenging practice problems (rating target: solved level +100 to +200), and guides them through solving the problem using **progressive, graded hints that strictly avoid leaking the solution**.

### The Core Problem Solved
Traditional AI tutors and editorial solutions spoil competitive programming problems by immediately revealing the key observation or full algorithm. Once spoiled, the pedagogical value of solving the problem is lost. 

CP Coach uses **multi-agent information asymmetry** to guarantee pedagogical integrity:
- The **Tutor Agent** communicates with the user and drafts hints *without ever seeing the reference solution*.
- The **Keeper Agent** inspects the reference solution privately and *audits the Tutor's hint drafts*, rejecting any hint that leaks algorithms, code, or key insights ahead of the requested hint tier.

---

## 2. Multi-Agent Topology & Information Asymmetry

| Agent | What it Sees | What it Does | Why Separate (Boundary) |
| :--- | :--- | :--- | :--- |
| **Analyst** | Submissions, problem tags, ratings | Computes weak topics deterministically, selects next problem, drafts short diagnosis | Owns data parsing, scoring formulas, and DB sync. Heavy logic is pure deterministic code. |
| **Tutor** | Problem statement, user chat messages, previous accepted hints | Talks to user, drafts hints at levels 1, 2, or 3 | **Cannot leak what it does not know.** Structurally blind to reference solution. |
| **Keeper** | Problem statement + Reference solution (read privately from DB) | Evaluates and approves/rejects Tutor hint drafts with constructive feedback | **Core multi-agent justification.** Enforces hint safety and rubric compliance. |
| **Judge** *(Phase 8)* | User code submission, test suite | Runs code in sandbox, reports execution verdicts (AC, WA, TLE, MLE) | Isolated execution environment with time/memory resource limits. |

---
