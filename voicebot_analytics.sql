-- ==============================================================================
-- VOICEBOT & CONVERSATIONAL AI ANALYTICS SQL MASTER GUIDE
-- Target Role: Data Analyst - Chatbot & Voicebot (w/m/d) | ING Deutschland
-- Candidate: Nidhi Jain
-- ==============================================================================
-- Table Schema Definitions (Assumed Industry Standard for Telephony Voicebots):
--
-- TABLE conversation_turns (
--     session_id        VARCHAR(64),   -- Unique identifier for the customer phone call
--     turn_number       INT,           -- Sequence of turn (1, 2, 3...)
--     speaker           VARCHAR(10),   -- 'user' or 'bot'
--     user_utterance    TEXT,          -- Transcribed customer speech
--     bot_response      TEXT,          -- Spoken response from voicebot
--     intent_detected   VARCHAR(64),   -- Classified intent (e.g., 'check_balance', 'fallback')
--     confidence_score  NUMERIC(4,3),  -- Model confidence between 0.000 and 1.000
--     step_name         VARCHAR(64),   -- Step in dialog flow ('welcome', 'collect_iban', 'confirm')
--     is_fallback       BOOLEAN,       -- TRUE if intent confidence fell below threshold
--     is_transferred    BOOLEAN,       -- TRUE if turn initiated escalation to human agent
--     latency_ms        INT,           -- End-to-end turnaround latency for this turn (ms)
--     created_at        TIMESTAMP      -- Timestamp of the event
-- );
--
-- TABLE customer_surveys (
--     session_id        VARCHAR(64),   -- Foreign key to conversation_turns
--     csat_score        INT,           -- Customer Satisfaction (1 = Very Unsatisfied, 5 = Very Satisfied)
--     fcr_flag          BOOLEAN,       -- First Contact Resolution (TRUE = Resolved on first call)
--     feedback_text     TEXT,          -- Optional transcribed feedback
--     survey_timestamp  TIMESTAMP
-- );
-- ==============================================================================


-- ==============================================================================
-- PATTERN 1: INTENT VOLUME, AVERAGE CONFIDENCE & FALLBACK RATE
-- Business Goal: Identify top customer intents and where the AI model is struggling.
-- Key Skills: Filtering (WHERE), Aggregation (COUNT, COUNT DISTINCT, AVG), CASE WHEN.
-- ==============================================================================

SELECT 
    intent_detected,
    -- Count distinct calls (call volume)
    COUNT(DISTINCT session_id) AS total_calls,
    -- Count total utterances (turns)
    COUNT(*) AS total_turns,
    -- Average model confidence for this specific intent
    ROUND(AVG(confidence_score), 3) AS avg_confidence,
    -- Count how many turns triggered fallback
    SUM(CASE WHEN is_fallback = TRUE THEN 1 ELSE 0 END) AS fallback_count,
    -- Fallback rate percentage (using 100.0 for decimal division)
    ROUND(100.0 * SUM(CASE WHEN is_fallback = TRUE THEN 1 ELSE 0 END) / COUNT(*), 2) AS fallback_rate_pct,
    -- Low confidence rate (< 0.60 threshold)
    ROUND(100.0 * SUM(CASE WHEN confidence_score < 0.60 THEN 1 ELSE 0 END) / COUNT(*), 2) AS low_confidence_rate_pct
FROM conversation_turns
WHERE created_at >= CURRENT_DATE - INTERVAL '30 days'
  AND speaker = 'user'
GROUP BY intent_detected
ORDER BY total_calls DESC;


-- ==============================================================================
-- PATTERN 2: CONTAINMENT RATE VS HUMAN ESCALATION RATE
-- Business Goal: What % of callers were fully resolved by self-service vs escalated?
-- Key Skills: Common Table Expression (CTE), Session-level aggregation with MAX().
-- ==============================================================================

WITH session_outcomes AS (
    -- Collapse multiple turns into one row per session
    SELECT 
        session_id,
        MIN(created_at) AS call_start_time,
        MAX(turn_number) AS total_turns_in_call,
        -- If any turn had is_transferred = TRUE, the call was escalated
        MAX(CASE WHEN is_transferred = TRUE THEN 1 ELSE 0 END) AS was_escalated
    FROM conversation_turns
    WHERE created_at >= CURRENT_DATE - INTERVAL '7 days'
    GROUP BY session_id
)
SELECT 
    COUNT(*) AS total_calls,
    -- Self-service contained calls (never transferred to human)
    SUM(CASE WHEN was_escalated = 0 THEN 1 ELSE 0 END) AS contained_calls,
    -- Escalated calls (transferred to human advisor)
    SUM(CASE WHEN was_escalated = 1 THEN 1 ELSE 0 END) AS escalated_calls,
    -- Containment Rate (%)
    ROUND(100.0 * SUM(CASE WHEN was_escalated = 0 THEN 1 ELSE 0 END) / COUNT(*), 2) AS containment_rate_pct,
    -- Escalation Rate (%)
    ROUND(100.0 * SUM(CASE WHEN was_escalated = 1 THEN 1 ELSE 0 END) / COUNT(*), 2) AS escalation_rate_pct,
    -- Average turns per call
    ROUND(AVG(total_turns_in_call), 1) AS avg_turns_per_call
FROM session_outcomes;


-- ==============================================================================
-- PATTERN 3: REPEAT FALLBACK LOOPS (CUSTOMER FRUSTRATION DETECTION)
-- Business Goal: Detect when the bot fails twice in a row, trapping the caller in a loop.
-- Key Skills: Window Function LAG(), PARTITION BY session_id, ORDER BY turn_number.
-- ==============================================================================

WITH turn_sequence AS (
    SELECT 
        session_id,
        turn_number,
        user_utterance,
        bot_response,
        intent_detected,
        confidence_score,
        is_fallback,
        -- Look at previous turn's fallback status within the same phone call
        LAG(is_fallback, 1) OVER (
            PARTITION BY session_id 
            ORDER BY turn_number
        ) AS prev_turn_was_fallback
    FROM conversation_turns
    WHERE created_at >= CURRENT_DATE - INTERVAL '1 day'
      AND speaker = 'user'
)
SELECT 
    session_id,
    turn_number,
    user_utterance,
    intent_detected,
    confidence_score
FROM turn_sequence
-- Both current turn and preceding turn were fallbacks
WHERE is_fallback = TRUE 
  AND prev_turn_was_fallback = TRUE
ORDER BY session_id, turn_number;


-- ==============================================================================
-- PATTERN 4: CONVERSATIONAL FUNNEL DROP-OFF ANALYSIS
-- Business Goal: Identify the exact dialog step where callers abandon the call.
-- Key Skills: Window Function LEAD(), PARTITION BY, identifying NULL next_step.
-- ==============================================================================

WITH step_transitions AS (
    SELECT 
        session_id,
        turn_number,
        step_name,
        intent_detected,
        is_fallback,
        -- Look ahead to the next step
        LEAD(step_name, 1) OVER (
            PARTITION BY session_id 
            ORDER BY turn_number
        ) AS next_step_name
    FROM conversation_turns
    WHERE created_at >= CURRENT_DATE - INTERVAL '14 days'
)
SELECT 
    step_name AS exit_step,
    COUNT(*) AS total_encounters,
    -- If next_step_name IS NULL, this was the caller's final turn before hanging up
    SUM(CASE WHEN next_step_name IS NULL THEN 1 ELSE 0 END) AS drop_off_count,
    -- Drop-off rate percentage
    ROUND(100.0 * SUM(CASE WHEN next_step_name IS NULL THEN 1 ELSE 0 END) / COUNT(*), 2) AS drop_off_rate_pct,
    -- Fallbacks at this step
    SUM(CASE WHEN is_fallback = TRUE THEN 1 ELSE 0 END) AS fallback_count_at_step
FROM step_transitions
GROUP BY step_name
HAVING COUNT(*) >= 50
ORDER BY drop_off_rate_pct DESC;


-- ==============================================================================
-- PATTERN 5: LOW-CONFIDENCE CLUSTERING FOR RETRAINING DATA
-- Business Goal: Extract uncertain utterances (0.40 - 0.65 confidence) to expand training data.
-- Key Skills: Window Function COUNT(*) OVER (PARTITION BY ...), Filtering.
-- ==============================================================================

SELECT 
    intent_detected,
    user_utterance,
    confidence_score,
    -- Window function: count how many uncertain utterances exist for this intent
    COUNT(*) OVER (PARTITION BY intent_detected) AS total_uncertain_utterances_for_intent
FROM conversation_turns
WHERE confidence_score BETWEEN 0.40 AND 0.65
  AND is_fallback = FALSE
  AND speaker = 'user'
  AND created_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY total_uncertain_utterances_for_intent DESC, confidence_score ASC
LIMIT 100;


-- ==============================================================================
-- PATTERN 6: IMPACT OF BOT LATENCY ON CUSTOMER SATISFACTION (CSAT)
-- Business Goal: Correlate turnaround latency and fallback count with CSAT survey scores.
-- Key Skills: INNER JOIN, Multi-table aggregation, CASE WHEN categorization.
-- ==============================================================================

WITH call_metrics AS (
    SELECT 
        session_id,
        AVG(latency_ms) AS avg_call_latency_ms,
        SUM(CASE WHEN is_fallback = TRUE THEN 1 ELSE 0 END) AS total_fallbacks
    FROM conversation_turns
    WHERE speaker = 'user'
    GROUP BY session_id
)
SELECT 
    -- Segment calls by latency
    CASE 
        WHEN c.avg_call_latency_ms <= 200 THEN 'Fast (<= 200ms)'
        WHEN c.avg_call_latency_ms <= 500 THEN 'Acceptable (201-500ms)'
        ELSE 'Slow (> 500ms)'
    END AS latency_bracket,
    COUNT(s.session_id) AS total_surveyed_calls,
    ROUND(AVG(s.csat_score), 2) AS avg_csat_score,
    ROUND(100.0 * SUM(CASE WHEN s.fcr_flag = TRUE THEN 1 ELSE 0 END) / COUNT(s.session_id), 2) AS fcr_rate_pct,
    ROUND(AVG(c.total_fallbacks), 2) AS avg_fallbacks_per_call
FROM call_metrics c
INNER JOIN customer_surveys s ON c.session_id = s.session_id
GROUP BY 
    CASE 
        WHEN c.avg_call_latency_ms <= 200 THEN 'Fast (<= 200ms)'
        WHEN c.avg_call_latency_ms <= 500 THEN 'Acceptable (201-500ms)'
        ELSE 'Slow (> 500ms)'
    END
ORDER BY avg_csat_score DESC;

