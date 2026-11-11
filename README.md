# Event-Driven Conversational AI & Telemetry Analytics Engine
### Production-Grade SQL Analytics, Event Stream Modeling & Automated Pipeline

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![SQL Engine](https://img.shields.io/badge/SQL-PostgreSQL%20%7C%20SQLite%20%7C%20DuckDB-orange.svg)]()
[![Domain](https://img.shields.io/badge/Domain-AI%20Telemetry%20%7C%20Event%20Streams%20%7C%20Fintech%20%7C%20SaaS-green.svg)]()

---

## 📌 Executive Summary

Modern AI systems (voicebots, chatbots, LLM agents) generate massive streams of semi-structured turn-by-turn telemetry events. Extracting operational intelligence, detecting failure loops, and monitoring customer satisfaction requires robust data engineering and advanced analytical SQL.

This project delivers an end-to-end data analytics framework that ingests conversational event streams, models user interaction paths, and executes production SQL analytics covering:
- **Session-level rollups and containment modeling** (self-service vs escalation).
- **Sequential loop detection** using SQL window functions (`LAG`).
- **Conversational funnel drop-off analysis** using SQL window functions (`LEAD`).
- **Telemetry latency profiling and SLA tracking** correlated with customer CSAT scores.
- **Uncertainty clustering** to harvest real-world edge cases for model retraining.

Applicable across multiple industries including **Fintech, Customer Support SaaS, Telecom, Healthcare, and E-Commerce**.

---

## 🏗️ System Architecture & Event Data Schema

```
[Customer Interaction] 
        │ (Audio / Text Streams)
        ▼
[Conversational AI Engine] (VAD -> ASR -> NLU/LLM -> TTS)
        │
        ▼ (Turn-by-turn Telemetry Events)
[Data Ingestion Layer (Python / SQLite / PostgreSQL)]
        │
        ├── conversation_turns (Event stream table: session_id, turn_number, intent, latency_ms...)
        └── customer_surveys   (Outcome table: csat_score, fcr_flag, feedback)
        │
        ▼
[Advanced Analytical SQL Transformation & Window Modeling]
        ├── Pattern 1: Intent Volume, Confidence & Fallback Rates
        ├── Pattern 2: Containment vs Escalation Rate (CTE Rollups)
        ├── Pattern 3: Sequential Repeat Error Loops (LAG)
        ├── Pattern 4: Step-by-Step Funnel Abandonment (LEAD)
        ├── Pattern 5: Model Uncertainty Slicing (COUNT OVER)
        └── Pattern 6: End-to-End Latency vs User Satisfaction (JOINs)
```

---

## 📊 Core Analytical Patterns & SQL Highlights

### 1. Intent Distribution & Conditional Fallback Rate
Calculates volume and error frequency using conditional aggregation (`CASE WHEN`):
```sql
SELECT 
    intent_detected,
    COUNT(DISTINCT session_id) AS total_sessions,
    COUNT(*) AS total_turns,
    ROUND(AVG(confidence_score), 3) AS avg_confidence,
    ROUND(100.0 * SUM(CASE WHEN is_fallback = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS fallback_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN confidence_score < 0.60 THEN 1 ELSE 0 END) / COUNT(*), 2) AS low_conf_rate_pct
FROM conversation_turns
WHERE created_at >= date('now', '-30 days')
  AND speaker = 'user'
GROUP BY intent_detected
ORDER BY total_sessions DESC;
```

### 2. Containment Rate vs Escalation (Session-Level Rollup)
Uses Common Table Expressions (CTEs) to resolve the grain mismatch between turn-level events and call-level outcomes:
```sql
WITH session_outcomes AS (
    SELECT 
        session_id,
        MAX(turn_number) AS total_turns,
        MAX(CASE WHEN is_transferred = 1 THEN 1 ELSE 0 END) AS was_escalated
    FROM conversation_turns
    WHERE created_at >= date('now', '-30 days')
    GROUP BY session_id
)
SELECT 
    COUNT(*) AS total_calls,
    SUM(CASE WHEN was_escalated = 0 THEN 1 ELSE 0 END) AS contained_calls,
    SUM(CASE WHEN was_escalated = 1 THEN 1 ELSE 0 END) AS escalated_calls,
    ROUND(100.0 * SUM(CASE WHEN was_escalated = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS containment_rate_pct,
    ROUND(100.0 * SUM(CASE WHEN was_escalated = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS escalation_rate_pct,
    ROUND(AVG(total_turns), 1) AS avg_turns_per_call
FROM session_outcomes;
```

### 3. Sequential Failure Loop Detection (`LAG`)
Identifies severe customer frustration traps where the AI failed twice in consecutive turns:
```sql
WITH turn_sequence AS (
    SELECT 
        session_id,
        turn_number,
        user_utterance,
        intent_detected,
        confidence_score,
        is_fallback,
        LAG(is_fallback, 1) OVER (
            PARTITION BY session_id 
            ORDER BY turn_number
        ) AS prev_turn_was_fallback
    FROM conversation_turns
    WHERE created_at >= date('now', '-30 days')
      AND speaker = 'user'
)
SELECT session_id, turn_number, user_utterance, intent_detected, confidence_score
FROM turn_sequence
WHERE is_fallback = 1 AND prev_turn_was_fallback = 1
ORDER BY session_id, turn_number;
```

### 4. Conversational Funnel Drop-Off (`LEAD`)
Tracks navigation path friction and identifies the exact step where users abandon the interaction:
```sql
WITH step_transitions AS (
    SELECT 
        session_id,
        step_name,
        LEAD(step_name, 1) OVER (
            PARTITION BY session_id 
            ORDER BY turn_number
        ) AS next_step_name
    FROM conversation_turns
    WHERE created_at >= date('now', '-30 days')
)
SELECT 
    step_name AS exit_step,
    COUNT(*) AS total_encounters,
    SUM(CASE WHEN next_step_name IS NULL THEN 1 ELSE 0 END) AS drop_off_count,
    ROUND(100.0 * SUM(CASE WHEN next_step_name IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS drop_off_rate_pct
FROM step_transitions
GROUP BY step_name
ORDER BY drop_off_count DESC;
```

---

## 🚀 Quickstart & Reproduction

### 1. Clone & Setup
```bash
git clone https://github.com/nidhijain16/conversational-ai-sql-analytics.git
cd conversational-ai-sql-analytics
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Generate Synthetic Telemetry & Run Analysis
```bash
# Seed the database and execute Pattern 1
python run_analytics.py 1

# Execute all 6 patterns
python run_analytics.py all

# Open the interactive SQL shell to run custom queries
python run_analytics.py --interactive
```

---

## 🛠️ Tech Stack & Skills Demonstrated

- **Languages:** Python (Pandas, SQLite3, Datetime, Object Generators), SQL.
- **SQL Competencies:** Window Functions (`LAG`, `LEAD`, `OVER`, `PARTITION BY`), CTEs, Conditional Aggregation (`CASE WHEN`), Date/Time Arithmetic, Multi-table `JOIN`s, Schema Design.
- **Data Engineering Concepts:** Event stream modeling, stateful turn tracking, telemetry latency profiling, data quality validation, idempotency.
- **Data Visualization & Metrics:** Containment Rate, First Contact Resolution (FCR), Fallback Rate, CSAT impact analysis.

---

## 👤 Author
**Nidhi Jain**  
- M.Sc. Data Science | AI & Data Systems Engineer  
- Portfolio: [nidhijain16.github.io](https://nidhijain16.github.io)  
- LinkedIn: [linkedin.com/in/nidhi-jain-1607](https://www.linkedin.com/in/nidhi-jain-1607)  
- GitHub: [github.com/nidhijain16](https://github.com/nidhijain16)

