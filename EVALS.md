# Evaluation Framework (`EVALS.md`)

This document outlines the evaluation methodology, metrics, and experimental design to validate the effectiveness and safety of CP Coach.

---

## 1. Experimental Hypothesis

> **Hypothesis**: A multi-agent architecture with structural information asymmetry (Tutor ⇄ Keeper) significantly reduces algorithmic spoiler leakage at Hint Levels 1 and 2 compared to a single-agent baseline, while maintaining high pedagogical utility.

---

## 2. Benchmark Dataset (`evals/dataset.json`)

- **Size**: 20–30 Codeforces problems spanning ratings 800 to 1800.
- **Topic Distribution**:
  - Dynamic Programming (DP)
  - Graph Theory (BFS, DFS, Dijkstra, Trees)
  - Data Structures (Segment Trees, DSU, Heaps)
  - Greedy & Two Pointers
  - Number Theory & Combinatorics
- **Data Points per Problem**:
  - Contest ID & Index
  - Problem Name & Rating
  - Clean Problem Statement (text + constraints)
  - Ground-Truth Official Solution / Reference Code
  - Editorial Key Insight Summary

---

## 3. Evaluated Architectures

1. **System Under Test (Multi-Agent CP Coach)**:
   - Tutor (Solution-Blind) + Keeper (Solution-Aware Auditor) with up to 3 revisions.
2. **Baseline (Single-Agent Direct Chain)**:
   - Single LLM prompt instructed with the problem statement and requested hint level, without an adversarial Keeper.

---

## 4. Key Metrics

| Metric | Calculation | Target |
| :--- | :--- | :--- |
| **Leakage Rate (%)** | Fraction of generated hints flagged by independent LLM Judge as containing forbidden algorithm/code spoilers. | $< 5\%$ for Multi-Agent vs $> 25\%$ for Single-Agent |
| **Keeper Rejection Rate (%)** | Percentage of initial Tutor drafts rejected by the Keeper on Turn 1. | Tracks how often the Keeper saves the user from spoilers |
| **Mean Revisions per Hint** | Average number of revisions needed before approval ($1.0 \le \bar{R} \le 3.0$). | $1.2 - 1.5$ |
| **Fallback Rate (%)** | Percentage of hints that reached 3 rejections and required fallback. | $< 2\%$ |
| **Latency & Cost** | P50 / P95 response latency (seconds) and average token consumption per hint. | Monitored trade-off |
| **Pedagogical Utility (1-5)** | Human or LLM-evaluated score on clarity, relevance, and constructive guidance. | $\ge 4.2 / 5.0$ |

---

## 5. Independent LLM Judge Rubric (`evals/leakage_eval.py`)

The independent judge receives:
1. Problem statement
2. Reference solution
3. Requested hint level (1, 2, or 3)
4. Generated hint text

### Prompt Rubric for Judge:
- **Score 0 (No Leakage)**: Follows rules perfectly for the given hint level.
- **Score 1 (Minor Leakage)**: Mentions a slightly too specific property or intermediate state name that narrows down options excessively.
- **Score 2 (Major Leakage / Spoiled)**: Outright names the exact specific algorithm (for Level 1), provides copyable code (for Level 1/2), or reveals the critical mathematical formula.
