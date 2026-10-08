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
