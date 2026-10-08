# System Architecture: CP Coach

## 1. Overview
CP Coach is designed as an agentic state machine orchestrated by **LangGraph**. The primary design driver is **pedagogical integrity through information asymmetry**.

---

## 2. LangGraph State Machine Architecture

```mermaid
flowchart TD
    subgraph Initialization
        START([START]) --> analyst_node[Analyst Node]
    end

    subgraph UserInteraction ["User Checkpoint (wait_for_user)"]
        analyst_node --> wait_user[wait_for_user Interrupt / Checkpoint]
        wait_user --> route_action{Route User Action}
    end

    subgraph TutoringLoop ["Tutor ⇄ Keeper Verification Loop"]
        route_action -- action == 'request_hint' --> tutor_node[Tutor Node\n(Solution-Blind Draft)]
        tutor_node --> keeper_node[Keeper Node\n(Private Solution Audit)]
        keeper_node --> keeper_verdict{Approved or Revisions >= 3?}
        keeper_verdict -- "No (Reject & Revisions < 3)" --> tutor_node
        keeper_verdict -- "Yes (Approve OR Fallback)" --> wait_user
    end

    subgraph SubmissionHandling ["Submission & Progress Tracking"]
        route_action -- action == 'submitted' --> check_submission_node[Check Submission Node]
        check_submission_node --> sub_verdict{Verdict == AC?}
        sub_verdict -- "Yes (AC)" --> update_stats_node[Update DB Stats]
        update_stats_node --> analyst_node
        sub_verdict -- "No (WA / TLE)" --> tutor_targeted_node[Tutor Targeted Hint]
