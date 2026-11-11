# -*- coding: utf-8 -*-
"""
run_voicebot_sql.py
Interactive SQL Playground for ING Voicebot Data Analyst Preparation.
Creates a local SQLite database with realistic mock banking voicebot calls and runs queries.
"""

import sqlite3
import os
import sys
import pandas as pd
from datetime import datetime, timedelta
import random

DB_FILE = os.path.join(os.path.dirname(__file__), "voicebot_practice.db")

def init_mock_database():
    """Seeds the SQLite database with realistic German banking voicebot data."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Create tables
    cursor.execute("DROP TABLE IF EXISTS conversation_turns;")
    cursor.execute("DROP TABLE IF EXISTS customer_surveys;")

    cursor.execute("""
    CREATE TABLE conversation_turns (
        session_id        VARCHAR(64),
        turn_number       INT,
        speaker           VARCHAR(10),
        user_utterance    TEXT,
        bot_response      TEXT,
        intent_detected   VARCHAR(64),
        confidence_score  REAL,
        step_name         VARCHAR(64),
        is_fallback       INT,
        is_transferred    INT,
        latency_ms        INT,
        created_at        TIMESTAMP
    );
    """)

    cursor.execute("""
    CREATE TABLE customer_surveys (
        session_id        VARCHAR(64),
        csat_score        INT,
        fcr_flag          INT,
        feedback_text     TEXT,
        survey_timestamp  TIMESTAMP
    );
    """)

    # Seed mock banking calls
    mock_scenarios = [
        # (intents, utterances, steps, will_escalate, csat, fcr)
        (
            [("check_balance", "Guten Tag, ich möchte meinen Kontostand abfragen.", 0.94, "welcome", 0, 110),
             ("check_balance", "Ja, für mein Girokonto bitte.", 0.96, "confirm_account", 0, 125)],
            False, 5, 1
        ),
        (
            [("block_card", "Hilfe, meine Girokarte wurde gestohlen!", 0.92, "welcome", 0, 130),
             ("block_card", "Ja, bitte sofort sperren.", 0.95, "confirm_block", 0, 115)],
            False, 5, 1
        ),
        (
            [("transfer_limit", "Ich muss mein Überweisungslimit erhöhen.", 0.88, "welcome", 0, 145),
             ("transfer_limit", "Auf dreitausend Euro.", 0.82, "collect_amount", 0, 160)],
            False, 4, 1
        ),
        (
            [("fallback", "Ähm ja also wegen dem Ding da letzte Woche...", 0.42, "welcome", 1, 180),
             ("fallback", "Ich verstehe die Abrechnung einfach gar nicht!", 0.38, "repeat_prompt", 1, 195),
             ("talk_to_agent", "Verbinden Sie mich bitte mit einem Menschen!", 0.97, "escalation", 0, 140)],
            True, 2, 0
        ),
        (
            [("fallback", "Hallo? Hören Sie mich? Der Empfang ist schlecht.", 0.35, "welcome", 1, 210),
             ("check_balance", "Ich wollte nur wissen wie viel Geld auf dem Konto ist.", 0.79, "welcome", 0, 135)],
            False, 3, 1
        ),
        (
            [("freistellungsauftrag", "Guten Tag, wie kann ich meinen Freistellungsauftrag anpassen?", 0.89, "welcome", 0, 140),
             ("freistellungsauftrag", "Für mein Einzeldepot.", 0.91, "confirm_product", 0, 130)],
            False, 5, 1
        ),
        (
            [("dispute_charge", "Auf meinem Auszug ist eine Abbuchung die ich nicht kenne.", 0.86, "welcome", 0, 150),
             ("dispute_charge", "Vom siebzehnten Oktober über achtzig Euro.", 0.74, "collect_details", 0, 165),
             ("talk_to_agent", "Bitte leiten Sie mich an die Fachabteilung weiter.", 0.95, "escalation", 0, 140)],
            True, 3, 0
        ),
        (
            [("open_depot", "Ich interessiere mich für ein Wertpapierdepot.", 0.91, "welcome", 0, 120),
             ("open_depot", "Welche Unterlagen brauche ich dafür?", 0.88, "faq_info", 0, 135)],
            False, 4, 1
        ),
    ]

    now = datetime.now()
    turns_data = []
    surveys_data = []

    # Generate 60 distinct sessions
    for i in range(1, 61):
        session_id = f"ING_CALL_{i:04d}"
        scenario = mock_scenarios[i % len(mock_scenarios)]
        turn_list, will_escalate, csat, fcr = scenario

        session_time = now - timedelta(days=random.randint(0, 20), minutes=random.randint(10, 500))

        for turn_idx, (intent, utt, base_conf, step, is_fb, base_lat) in enumerate(turn_list, 1):
            conf = min(0.99, max(0.20, base_conf + random.uniform(-0.04, 0.04)))
            lat = int(base_lat + random.uniform(-15, 60))
            is_trans = 1 if (will_escalate and turn_idx == len(turn_list)) else 0
            turn_time = session_time + timedelta(seconds=turn_idx * 15)

            turns_data.append((
                session_id,
                turn_idx,
                "user",
                utt,
                "Bot response audio stream",
                intent,
                round(conf, 3),
                step,
                is_fb,
                is_trans,
                lat,
                turn_time.strftime("%Y-%m-%d %H:%M:%S")
            ))

        # Add survey for each session
        surveys_data.append((
            session_id,
            csat,
            fcr,
            "Service war hilfreich." if csat >= 4 else "Musste leider weitergeleitet werden.",
            (session_time + timedelta(minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
        ))

    cursor.executemany("""
    INSERT INTO conversation_turns VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
    """, turns_data)

    cursor.executemany("""
    INSERT INTO customer_surveys VALUES (?, ?, ?, ?, ?);
    """, surveys_data)

    conn.commit()
    conn.close()
    print(f"-> Successfully seeded database '{DB_FILE}' with {len(turns_data)} conversation turns across 60 calls.")


QUERIES = {
    "1": (
        "Pattern 1: Intent Volume, Average Confidence & Fallback Rate",
        """
        SELECT 
            intent_detected,
            COUNT(DISTINCT session_id) AS total_calls,
            COUNT(*) AS total_turns,
            ROUND(AVG(confidence_score), 3) AS avg_confidence,
            SUM(CASE WHEN is_fallback = 1 THEN 1 ELSE 0 END) AS fallback_count,
            ROUND(100.0 * SUM(CASE WHEN is_fallback = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS fallback_rate_pct,
            ROUND(100.0 * SUM(CASE WHEN confidence_score < 0.60 THEN 1 ELSE 0 END) / COUNT(*), 2) AS low_conf_rate_pct
        FROM conversation_turns
        WHERE created_at >= date('now', '-30 days')
          AND speaker = 'user'
        GROUP BY intent_detected
        ORDER BY total_calls DESC;
        """
    ),
    "2": (
        "Pattern 2: Containment Rate vs Human Escalation Rate",
        """
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
        """
    ),
    "3": (
        "Pattern 3: Repeat Fallback Loops (Window LAG)",
        """
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
        SELECT 
            session_id,
            turn_number,
            user_utterance,
            intent_detected,
            confidence_score
        FROM turn_sequence
        WHERE is_fallback = 1 AND prev_turn_was_fallback = 1
        ORDER BY session_id, turn_number
        LIMIT 10;
        """
    ),
    "4": (
        "Pattern 4: Drop-Off Funnel by Step (Window LEAD)",
        """
        WITH step_transitions AS (
            SELECT 
                session_id,
                turn_number,
                step_name,
                is_fallback,
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
        """
    ),
    "5": (
        "Pattern 5: Low-Confidence Utterances for Training (Window COUNT OVER)",
        """
        SELECT 
            intent_detected,
            user_utterance,
            confidence_score,
            COUNT(*) OVER (PARTITION BY intent_detected) AS total_uncertain_in_category
        FROM conversation_turns
        WHERE confidence_score BETWEEN 0.40 AND 0.85
          AND speaker = 'user'
        ORDER BY total_uncertain_in_category DESC, confidence_score ASC
        LIMIT 10;
        """
    ),
    "6": (
        "Pattern 6: Impact of Turnaround Latency on CSAT and FCR (JOIN)",
        """
        WITH call_metrics AS (
            SELECT 
                session_id,
                AVG(latency_ms) AS avg_call_latency_ms,
                SUM(CASE WHEN is_fallback = 1 THEN 1 ELSE 0 END) AS total_fallbacks
            FROM conversation_turns
            WHERE speaker = 'user'
            GROUP BY session_id
        )
        SELECT 
            CASE 
                WHEN c.avg_call_latency_ms <= 140 THEN 'Ultra-Low (<= 140ms)'
                WHEN c.avg_call_latency_ms <= 180 THEN 'Normal (141-180ms)'
                ELSE 'Slow (> 180ms)'
            END AS latency_bracket,
            COUNT(s.session_id) AS total_surveyed_calls,
            ROUND(AVG(s.csat_score), 2) AS avg_csat_score,
            ROUND(100.0 * SUM(CASE WHEN s.fcr_flag = 1 THEN 1 ELSE 0 END) / COUNT(s.session_id), 2) AS fcr_rate_pct,
            ROUND(AVG(c.total_fallbacks), 2) AS avg_fallbacks_per_call
        FROM call_metrics c
        INNER JOIN customer_surveys s ON c.session_id = s.session_id
        GROUP BY 
            CASE 
                WHEN c.avg_call_latency_ms <= 140 THEN 'Ultra-Low (<= 140ms)'
                WHEN c.avg_call_latency_ms <= 180 THEN 'Normal (141-180ms)'
                ELSE 'Slow (> 180ms)'
            END
        ORDER BY avg_csat_score DESC;
        """
    )
}

def run_pattern(pattern_num):
    if pattern_num not in QUERIES:
        print(f"Invalid pattern '{pattern_num}'. Available patterns: 1, 2, 3, 4, 5, 6, all")
        return

    title, sql = QUERIES[pattern_num]
    print("\n" + "=" * 80)
    print(f"📊 EXECUTING: {title}")
    print("=" * 80)
    print("SQL Query:\n" + sql.strip())
    print("\nResults:")
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query(sql, conn)
    conn.close()
    pd.set_option("display.max_columns", None)
    pd.set_option("display.width", 1000)
    print(df.to_string(index=False))
    print("=" * 80)

def interactive_mode():
    print("\n=== Interactive SQL Shell (Type 'exit' to quit) ===")
    conn = sqlite3.connect(DB_FILE)
    while True:
        try:
            query = input("\nSQL> ")
            if query.strip().lower() in ("exit", "quit"):
                break
            if not query.strip():
                continue
            df = pd.read_sql_query(query, conn)
            print(df.to_string(index=False))
        except Exception as e:
            print(f"Error: {e}")
    conn.close()

if __name__ == "__main__":
    if not os.path.exists(DB_FILE):
        print("Database not found. Initializing mock banking database...")
        init_mock_database()

    arg = sys.argv[1] if len(sys.argv) > 1 else "1"

    if arg == "--init":
        init_mock_database()
    elif arg == "--interactive" or arg == "-i":
        interactive_mode()
    elif arg == "all":
        for p in sorted(QUERIES.keys()):
            run_pattern(p)
    else:
        run_pattern(arg)

