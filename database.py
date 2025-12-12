import aiosqlite
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple


class DatabaseManager:
    def __init__(self, db_path: str):
        self.db_path = db_path

    async def initialize_database(self):
        """Initialize the database with all required tables"""
        async with aiosqlite.connect(self.db_path) as db:
            # Users table
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS users
                             (
                                 user_id
                                 INTEGER
                                 PRIMARY
                                 KEY,
                                 username
                                 TEXT
                                 NOT
                                 NULL,
                                 total_points
                                 INTEGER
                                 DEFAULT
                                 0,
                                 total_questions
                                 INTEGER
                                 DEFAULT
                                 0,
                                 correct_answers
                                 INTEGER
                                 DEFAULT
                                 0,
                                 average_response_time
                                 REAL
                                 DEFAULT
                                 0.0,
                                 current_rank
                                 TEXT
                                 DEFAULT
                                 'QA Pleasant',
                                 created_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP
                             )
                             """)

            # Chapters table
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS chapters
                             (
                                 chapter_id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 name
                                 TEXT
                                 NOT
                                 NULL
                                 UNIQUE,
                                 description
                                 TEXT,
                                 created_by
                                 INTEGER,
                                 created_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 FOREIGN
                                 KEY
                             (
                                 created_by
                             ) REFERENCES users
                             (
                                 user_id
                             )
                                 )
                             """)

            # Questions table
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS questions
                             (
                                 question_id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 chapter_id
                                 INTEGER,
                                 question_text
                                 TEXT
                                 NOT
                                 NULL,
                                 option_a
                                 TEXT
                                 NOT
                                 NULL,
                                 option_b
                                 TEXT
                                 NOT
                                 NULL,
                                 option_c
                                 TEXT
                                 NOT
                                 NULL,
                                 option_d
                                 TEXT
                                 NOT
                                 NULL,
                                 correct_option
                                 TEXT
                                 NOT
                                 NULL,
                                 difficulty
                                 INTEGER
                                 NOT
                                 NULL
                                 CHECK (
                                 difficulty
                                 IN
                             (
                                 1,
                                 2,
                                 3
                             )),
                                 explanation TEXT,
                                 created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                                 FOREIGN KEY
                             (
                                 chapter_id
                             ) REFERENCES chapters
                             (
                                 chapter_id
                             )
                                 )
                             """)

            # Quiz attempts table
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS quiz_attempts
                             (
                                 attempt_id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 user_id
                                 INTEGER,
                                 chapter_id
                                 INTEGER,
                                 question_id
                                 INTEGER,
                                 user_answer
                                 TEXT,
                                 is_correct
                                 BOOLEAN,
                                 response_time
                                 REAL,
                                 difficulty
                                 INTEGER,
                                 points_earned
                                 INTEGER,
                                 attempted_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 FOREIGN
                                 KEY
                             (
                                 user_id
                             ) REFERENCES users
                             (
                                 user_id
                             ),
                                 FOREIGN KEY
                             (
                                 chapter_id
                             ) REFERENCES chapters
                             (
                                 chapter_id
                             ),
                                 FOREIGN KEY
                             (
                                 question_id
                             ) REFERENCES questions
                             (
                                 question_id
                             )
                                 )
                             """)

            # User question history for anti-redundancy
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS user_question_history
                             (
                                 user_id
                                 INTEGER,
                                 question_id
                                 INTEGER,
                                 last_attempted
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 PRIMARY
                                 KEY
                             (
                                 user_id,
                                 question_id
                             ),
                                 FOREIGN KEY
                             (
                                 user_id
                             ) REFERENCES users
                             (
                                 user_id
                             ),
                                 FOREIGN KEY
                             (
                                 question_id
                             ) REFERENCES questions
                             (
                                 question_id
                             )
                                 )
                             """)

            # Active quiz sessions
            await db.execute("""
                             CREATE TABLE IF NOT EXISTS active_quizzes
                             (
                                 session_id
                                 TEXT
                                 PRIMARY
                                 KEY,
                                 user_id
                                 INTEGER,
                                 chapter_id
                                 INTEGER,
                                 current_question
                                 INTEGER
                                 DEFAULT
                                 0,
                                 current_difficulty
                                 INTEGER
                                 DEFAULT
                                 1,
                                 total_questions
                                 INTEGER
                                 DEFAULT
                                 10,
                                 score
                                 INTEGER
                                 DEFAULT
                                 0,
                                 correct_streak
                                 INTEGER
                                 DEFAULT
                                 0,
                                 started_at
                                 TIMESTAMP
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 FOREIGN
                                 KEY
                             (
                                 user_id
                             ) REFERENCES users
                             (
                                 user_id
                             ),
                                 FOREIGN KEY
                             (
                                 chapter_id
                             ) REFERENCES chapters
                             (
                                 chapter_id
                             )
                                 )
                             """)

            await db.commit()

    async def add_user(self, user_id: int, username: str):
        """Add a new user to the database"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username)
            )
            await db.commit()

    async def add_chapter(self, name: str, description: str, created_by: int) -> int:
        """Add a new chapter"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                "INSERT INTO chapters (name, description, created_by) VALUES (?, ?, ?)",
                (name, description, created_by)
            )
            await db.commit()
            return cursor.lastrowid

    async def add_question(self, chapter_id: int, question_text: str, option_a: str,
                           option_b: str, option_c: str, option_d: str,
                           correct_option: str, difficulty: int, explanation: str = None) -> int:
        """Add a new question to a chapter"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute("""
                                      INSERT INTO questions
                                      (chapter_id, question_text, option_a, option_b, option_c, option_d,
                                       correct_option, difficulty, explanation)
                                      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                                      """, (chapter_id, question_text, option_a, option_b, option_c, option_d,
                                            correct_option, difficulty, explanation))
            await db.commit()
            return cursor.lastrowid

    async def get_chapters(self) -> List[Dict]:
        """Get all chapters"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM chapters ORDER BY name")
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_next_question(self, user_id: int, chapter_id: int, difficulty: int = None) -> Optional[Dict]:
        """Get next question for user, avoiding recently attempted questions"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            query = """
                    SELECT q.* \
                    FROM questions q \
                             LEFT JOIN user_question_history uqh ON q.question_id = uqh.question_id AND uqh.user_id = ?
                    WHERE q.chapter_id = ? \
                    """
            params = [user_id, chapter_id]

            if difficulty:
                query += " AND q.difficulty = ?"
                params.append(difficulty)

            query += """
                ORDER BY 
                    CASE WHEN uqh.last_attempted IS NULL THEN 0 ELSE 1 END,
                    uqh.last_attempted ASC,
                    RANDOM()
                LIMIT 1
            """

            cursor = await db.execute(query, params)
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def record_quiz_attempt(self, user_id: int, chapter_id: int, question_id: int,
                                  user_answer: str, is_correct: bool, response_time: float,
                                  difficulty: int, points_earned: int):
        """Record a quiz attempt"""
        async with aiosqlite.connect(self.db_path) as db:
            # Record the attempt
            await db.execute("""
                             INSERT INTO quiz_attempts
                             (user_id, chapter_id, question_id, user_answer, is_correct, response_time, difficulty,
                              points_earned)
                             VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                             """, (user_id, chapter_id, question_id, user_answer, is_correct, response_time, difficulty,
                                   points_earned))

            # Update user question history
            await db.execute("""
                INSERT OR REPLACE INTO user_question_history (user_id, question_id)
                VALUES (?, ?)
            """, (user_id, question_id))

            # Update user stats
            await db.execute("""
                             UPDATE users
                             SET total_points          = total_points + ?,
                                 total_questions       = total_questions + 1,
                                 correct_answers       = correct_answers + ?,
                                 average_response_time = (average_response_time * (total_questions - 1) + ?) / total_questions
                             WHERE user_id = ?
                             """, (points_earned, 1 if is_correct else 0, response_time, user_id))

            await db.commit()

    async def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Get comprehensive user statistics"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def get_leaderboard(self, timeframe: str = 'all_time', limit: int = 10) -> List[Dict]:
        """Get leaderboard for specified timeframe"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if timeframe == 'daily':
                date_filter = datetime.now().date()
                query = """
                        SELECT u.username, SUM(qa.points_earned) as points, COUNT(*) as questions_answered
                        FROM users u
                                 JOIN quiz_attempts qa ON u.user_id = qa.user_id
                        WHERE DATE (qa.attempted_at) = ?
                        GROUP BY u.user_id, u.username
                        ORDER BY points DESC, questions_answered DESC
                            LIMIT ? \
                        """
                cursor = await db.execute(query, (date_filter, limit))
            elif timeframe == 'monthly':
                date_filter = datetime.now().replace(day=1).date()
                query = """
                        SELECT u.username, SUM(qa.points_earned) as points, COUNT(*) as questions_answered
                        FROM users u
                                 JOIN quiz_attempts qa ON u.user_id = qa.user_id
                        WHERE DATE (qa.attempted_at) >= ?
                        GROUP BY u.user_id, u.username
                        ORDER BY points DESC, questions_answered DESC
                            LIMIT ? \
                        """
                cursor = await db.execute(query, (date_filter, limit))
            else:  # all_time
                query = """
                        SELECT username, \
                               total_points                                                     as points, \
                               total_questions                                                  as questions_answered,
                               ROUND(CAST(correct_answers AS FLOAT) / total_questions * 100, 2) as accuracy
                        FROM users
                        WHERE total_questions > 0
                        ORDER BY total_points DESC, accuracy DESC LIMIT ? \
                        """
                cursor = await db.execute(query, (limit,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_user_chapter_performance(self, user_id: int) -> List[Dict]:
        """Get user performance by chapter for SWOT analysis"""
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute("""
                                      SELECT c.name                                             as chapter_name,
                                             COUNT(*)                                           as total_attempts,
                                             SUM(CASE WHEN qa.is_correct THEN 1 ELSE 0 END)     as correct_answers,
                                             AVG(qa.response_time)                              as avg_response_time,
                                             AVG(CASE WHEN qa.is_correct THEN 1.0 ELSE 0.0 END) as accuracy
                                      FROM quiz_attempts qa
                                               JOIN chapters c ON qa.chapter_id = c.chapter_id
                                      WHERE qa.user_id = ?
                                      GROUP BY qa.chapter_id, c.name
                                      HAVING total_attempts >= 3
                                      ORDER BY accuracy ASC, avg_response_time DESC
                                      """, (user_id,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def cleanup_old_sessions(self):
        """Clean up old quiz sessions (older than 30 minutes)"""
        async with aiosqlite.connect(self.db_path) as db:
            cutoff_time = datetime.now() - timedelta(minutes=30)
            await db.execute(
                "DELETE FROM active_quizzes WHERE started_at < ?",
                (cutoff_time,)
            )

            await db.commit()
