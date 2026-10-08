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
        tutor_targeted_node --> keeper_node
    end

    subgraph GraphExit
        route_action -- action == 'skip' --> analyst_node
        route_action -- action == 'done' --> END([END])
    end
```

---

## 3. Node Responsibilities & Boundaries

```mermaid
classDiagram
    class AnalystNode {
        +sync_cf_data(handle)
        +compute_weak_topics() list~TopicStat~
        +select_problem() ProblemChoice
        +generate_diagnosis() str
    }

    class TutorNode {
        +draft_hint(problem_statement, level, history, feedback) HintDraft
        +draft_targeted_error_hint(verdict, history) HintDraft
    }

    class KeeperNode {
        -load_private_reference(contest_id, idx) str
        +audit_hint(problem_statement, draft, reference) HintVerdict
    }
