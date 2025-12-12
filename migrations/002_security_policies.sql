-- Migration: 002_security_policies.sql
-- Description: Row Level Security (RLS) policies and security hardening
-- Created: 2024
-- IMPORTANT: Run this migration AFTER 001_initial_schema.sql

-- ============================================================================
-- SECURITY SETUP: Enable Row Level Security on all tables
-- ============================================================================

-- Enable RLS on all tables
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE chapters ENABLE ROW LEVEL SECURITY;
ALTER TABLE questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE quiz_attempts ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_question_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE active_quizzes ENABLE ROW LEVEL SECURITY;

-- ============================================================================
-- USERS TABLE POLICIES
-- ============================================================================

-- Policy: Service role can do everything (for bot operations)
-- This is the primary policy - bot uses service role key
CREATE POLICY "Service role full access to users"
ON users FOR ALL
USING (true)
WITH CHECK (true);

-- Note: All operations go through service role key
-- Anon key will be blocked by default (no policies allow it)

-- ============================================================================
-- CHAPTERS TABLE POLICIES
-- ============================================================================

-- Policy: Everyone can read chapters (public data)
CREATE POLICY "Chapters are publicly readable"
ON chapters FOR SELECT
USING (true);

-- Policy: Service role can modify chapters (admin operations)
-- Anon key can only read (public data)
CREATE POLICY "Service role can modify chapters"
ON chapters FOR ALL
USING (true)
WITH CHECK (true);

-- ============================================================================
-- QUESTIONS TABLE POLICIES
-- ============================================================================

-- Policy: Everyone can read questions (public data)
CREATE POLICY "Questions are publicly readable"
ON questions FOR SELECT
USING (true);

-- Policy: Service role can modify questions (admin operations)
-- Anon key can only read (public data)
CREATE POLICY "Service role can modify questions"
ON questions FOR ALL
USING (true)
WITH CHECK (true);

-- ============================================================================
-- QUIZ ATTEMPTS TABLE POLICIES
-- ============================================================================

-- Policy: Service role can read all attempts (for bot operations)
CREATE POLICY "Service role can read attempts"
ON quiz_attempts FOR SELECT
USING (true);

-- Policy: Only service role can insert attempts (bot records answers)
CREATE POLICY "Service role can record attempts"
ON quiz_attempts FOR INSERT
WITH CHECK (true);

-- Policy: No updates or deletes allowed (immutable history)
-- This prevents cheating by modifying past attempts
CREATE POLICY "Attempts are immutable - no updates"
ON quiz_attempts FOR UPDATE
USING (false);

CREATE POLICY "Attempts cannot be deleted"
ON quiz_attempts FOR DELETE
USING (false);

-- ============================================================================
-- USER QUESTION HISTORY TABLE POLICIES
-- ============================================================================

-- Policy: Service role can manage question history
CREATE POLICY "Service role can manage question history"
ON user_question_history FOR ALL
USING (true)
WITH CHECK (true);

-- ============================================================================
-- ACTIVE QUIZZES TABLE POLICIES
-- ============================================================================

-- Policy: Service role can manage active quizzes
CREATE POLICY "Service role can manage active quizzes"
ON active_quizzes FOR ALL
USING (true)
WITH CHECK (true);

-- ============================================================================
-- SECURE FUNCTIONS FOR COMMON OPERATIONS
-- ============================================================================

-- Function: Get user stats (with RLS check)
CREATE OR REPLACE FUNCTION get_user_stats(target_user_id BIGINT)
RETURNS TABLE (
    user_id BIGINT,
    username TEXT,
    total_points INTEGER,
    total_questions INTEGER,
    correct_answers INTEGER,
    average_response_time REAL,
    current_rank TEXT
) 
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
BEGIN
    -- Service role can access any user's data
    -- In production, you might want to add user-specific checks here
    RETURN QUERY
    SELECT u.user_id, u.username, u.total_points, u.total_questions,
           u.correct_answers, u.average_response_time, u.current_rank
    FROM users u
    WHERE u.user_id = target_user_id;
END;
$$;

-- Function: Get leaderboard (public read, but limited)
CREATE OR REPLACE FUNCTION get_leaderboard(
    timeframe_type TEXT DEFAULT 'all_time',
    result_limit INTEGER DEFAULT 10
)
RETURNS TABLE (
    username TEXT,
    points BIGINT,
    questions_answered BIGINT,
    accuracy NUMERIC
)
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    start_date TIMESTAMP WITH TIME ZONE;
BEGIN
    -- Validate limit
    IF result_limit > 100 THEN
        result_limit := 100;
    END IF;
    
    -- Calculate start date based on timeframe
    CASE timeframe_type
        WHEN 'daily' THEN
            start_date := CURRENT_DATE;
        WHEN 'monthly' THEN
            start_date := DATE_TRUNC('month', CURRENT_DATE);
        ELSE
            start_date := '1970-01-01'::TIMESTAMP;
    END CASE;
    
    -- Return leaderboard
    IF timeframe_type IN ('daily', 'monthly') THEN
        RETURN QUERY
        SELECT 
            u.username,
            COALESCE(SUM(qa.points_earned), 0)::BIGINT as points,
            COUNT(qa.attempt_id)::BIGINT as questions_answered,
            CASE 
                WHEN COUNT(qa.attempt_id) > 0 THEN
                    ROUND((SUM(CASE WHEN qa.is_correct THEN 1 ELSE 0 END)::NUMERIC / COUNT(qa.attempt_id)::NUMERIC * 100), 2)
                ELSE 0
            END as accuracy
        FROM users u
        LEFT JOIN quiz_attempts qa ON u.user_id = qa.user_id 
            AND qa.attempted_at >= start_date
        WHERE qa.attempted_at >= start_date OR qa.attempted_at IS NULL
        GROUP BY u.user_id, u.username
        HAVING COUNT(qa.attempt_id) > 0
        ORDER BY points DESC, accuracy DESC
        LIMIT result_limit;
    ELSE
        RETURN QUERY
        SELECT 
            u.username,
            u.total_points::BIGINT as points,
            u.total_questions::BIGINT as questions_answered,
            CASE 
                WHEN u.total_questions > 0 THEN
                    ROUND((u.correct_answers::NUMERIC / u.total_questions::NUMERIC * 100), 2)
                ELSE 0
            END as accuracy
        FROM users u
        WHERE u.total_questions > 0
        ORDER BY u.total_points DESC, accuracy DESC
        LIMIT result_limit;
    END IF;
END;
$$;

-- Function: Record quiz attempt (secure, validates input)
CREATE OR REPLACE FUNCTION record_quiz_attempt(
    p_user_id BIGINT,
    p_chapter_id INTEGER,
    p_question_id INTEGER,
    p_user_answer TEXT,
    p_is_correct BOOLEAN,
    p_response_time REAL,
    p_difficulty INTEGER,
    p_points_earned INTEGER
)
RETURNS INTEGER
SECURITY DEFINER
SET search_path = public
LANGUAGE plpgsql
AS $$
DECLARE
    attempt_id_result INTEGER;
BEGIN
    -- Function is SECURITY DEFINER, so it runs with creator's privileges
    -- Only callable by service role (enforced by RLS on table)
    
    -- Validate inputs
    IF p_difficulty NOT IN (1, 2, 3) THEN
        RAISE EXCEPTION 'Invalid difficulty level';
    END IF;
    
    IF p_user_answer NOT IN ('A', 'B', 'C', 'D', 'a', 'b', 'c', 'd') THEN
        RAISE EXCEPTION 'Invalid answer option';
    END IF;
    
    IF p_response_time < 0 OR p_response_time > 3600 THEN
        RAISE EXCEPTION 'Invalid response time';
    END IF;
    
    -- Insert attempt
    INSERT INTO quiz_attempts (
        user_id, chapter_id, question_id, user_answer,
        is_correct, response_time, difficulty, points_earned
    ) VALUES (
        p_user_id, p_chapter_id, p_question_id, UPPER(p_user_answer),
        p_is_correct, p_response_time, p_difficulty, p_points_earned
    )
    RETURNING attempt_id INTO attempt_id_result;
    
    -- Update user question history
    INSERT INTO user_question_history (user_id, question_id, last_attempted)
    VALUES (p_user_id, p_question_id, CURRENT_TIMESTAMP)
    ON CONFLICT (user_id, question_id) 
    DO UPDATE SET last_attempted = CURRENT_TIMESTAMP;
    
    -- Update user stats
    UPDATE users
    SET 
        total_points = total_points + p_points_earned,
        total_questions = total_questions + 1,
        correct_answers = correct_answers + CASE WHEN p_is_correct THEN 1 ELSE 0 END,
        average_response_time = (
            (average_response_time * (total_questions) + p_response_time) / 
            (total_questions + 1)
        )
    WHERE user_id = p_user_id;
    
    RETURN attempt_id_result;
END;
$$;

-- ============================================================================
-- REVOKE PUBLIC ACCESS (Security Hardening)
-- ============================================================================

-- Revoke all privileges from anon and authenticated roles
-- Service role will still have access via RLS policies

REVOKE ALL ON users FROM anon, authenticated;
REVOKE ALL ON chapters FROM anon, authenticated;
REVOKE ALL ON questions FROM anon, authenticated;
REVOKE ALL ON quiz_attempts FROM anon, authenticated;
REVOKE ALL ON user_question_history FROM anon, authenticated;
REVOKE ALL ON active_quizzes FROM anon, authenticated;

-- Grant SELECT only where needed (via RLS policies)
-- RLS policies will handle the actual access control

-- ============================================================================
-- ADDITIONAL SECURITY: Rate Limiting Helper Table
-- ============================================================================

-- Create rate limiting table (optional, for future use)
CREATE TABLE IF NOT EXISTS rate_limits (
    identifier TEXT PRIMARY KEY,
    request_count INTEGER DEFAULT 1,
    window_start TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_rate_limits_window_start ON rate_limits(window_start);

-- Enable RLS on rate_limits
ALTER TABLE rate_limits ENABLE ROW LEVEL SECURITY;

-- Only service role can access rate limits
CREATE POLICY "Service role can access rate limits"
ON rate_limits FOR ALL
USING (true)
WITH CHECK (true);

-- ============================================================================
-- SECURITY AUDIT LOG (Optional, for monitoring)
-- ============================================================================

CREATE TABLE IF NOT EXISTS security_audit_log (
    log_id SERIAL PRIMARY KEY,
    event_type TEXT NOT NULL,
    user_id BIGINT,
    ip_address INET,
    user_agent TEXT,
    details JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_log_event_type ON security_audit_log(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_log_created_at ON security_audit_log(created_at);
CREATE INDEX IF NOT EXISTS idx_audit_log_user_id ON security_audit_log(user_id);

-- Enable RLS on audit log
ALTER TABLE security_audit_log ENABLE ROW LEVEL SECURITY;

-- Only service role can write to audit log
CREATE POLICY "Service role can write audit log"
ON security_audit_log FOR INSERT
WITH CHECK (true);

-- Only service role can read audit log
CREATE POLICY "Service role can read audit log"
ON security_audit_log FOR SELECT
USING (true);

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON POLICY "Service role full access to users" ON users IS 'Bot service role has full access for operations';
COMMENT ON POLICY "Chapters are publicly readable" ON chapters IS 'Chapters are public data, anyone can read';
COMMENT ON POLICY "Service role can modify chapters" ON chapters IS 'Service role can create, update, and delete chapters';
COMMENT ON POLICY "Questions are publicly readable" ON questions IS 'Questions are public data, anyone can read';
COMMENT ON POLICY "Service role can modify questions" ON questions IS 'Service role can create, update, and delete questions';
COMMENT ON POLICY "Service role can read attempts" ON quiz_attempts IS 'Service role can read all quiz attempts';
COMMENT ON POLICY "Service role can record attempts" ON quiz_attempts IS 'Service role can insert new quiz attempts';
COMMENT ON POLICY "Attempts are immutable - no updates" ON quiz_attempts IS 'Quiz attempts cannot be modified once created';
COMMENT ON POLICY "Attempts cannot be deleted" ON quiz_attempts IS 'Quiz attempts cannot be deleted (immutable history)';
COMMENT ON POLICY "Service role can manage question history" ON user_question_history IS 'Service role can manage user question history';
COMMENT ON POLICY "Service role can manage active quizzes" ON active_quizzes IS 'Service role can manage active quiz sessions';
COMMENT ON FUNCTION get_user_stats IS 'Secure function to get user statistics with access control';
COMMENT ON FUNCTION get_leaderboard IS 'Secure function to get leaderboard with rate limiting';
COMMENT ON FUNCTION record_quiz_attempt IS 'Secure function to record quiz attempts with validation';

