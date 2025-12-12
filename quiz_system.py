import asyncio
import random
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

import aiosqlite

import config

if TYPE_CHECKING:
    # Only import for type checking, not runtime
    if config.DATABASE_TYPE == 'supabase':
        from database_supabase_secure import DatabaseManager
    else:
        from database import DatabaseManager


class QuizSystem:
    def __init__(self, db_manager: 'DatabaseManager'):
        self.db = db_manager
        self.active_sessions = {}

    async def start_quiz(self, user_id: int, chapter_id: int, difficulty: str = "mix",
                         total_questions: int = 10) -> str:
        """Start a new quiz session"""
        session_id = str(uuid.uuid4())

        # Initialize difficulty
        if difficulty == "mix":
            current_difficulty = 1  # Start with easy for mix mode
        else:
            current_difficulty = int(difficulty)

        # Store session in database
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute("""
                             INSERT INTO active_quizzes
                                 (session_id, user_id, chapter_id, current_difficulty, total_questions)
                             VALUES (?, ?, ?, ?, ?)
                             """, (session_id, user_id, chapter_id, current_difficulty, total_questions))
            await db.commit()

        # Initialize session data
        self.active_sessions[session_id] = {
            'user_id': user_id,
            'chapter_id': chapter_id,
            'current_question': 0,
            'total_questions': total_questions,
            'score': 0,
            'correct_streak': 0,
            'wrong_streak': 0,
            'difficulty_mode': difficulty,
            'current_difficulty': current_difficulty,
            'questions_by_difficulty': {1: 0, 2: 0, 3: 0},
            'correct_by_difficulty': {1: 0, 2: 0, 3: 0},
            'response_times': [],
            'started_at': datetime.now()
        }

        return session_id

    async def get_next_question(self, session_id: str) -> Optional[Dict]:
        """Get the next question for a quiz session"""
        if session_id not in self.active_sessions:
            return None

        session = self.active_sessions[session_id]

        # Check if quiz is complete
        if session['current_question'] >= session['total_questions']:
            return None

        # Get question based on current difficulty
        question = await self.db.get_next_question(
            session['user_id'],
            session['chapter_id'],
            session['current_difficulty']
        )

        if not question:
            # If no questions available at current difficulty, try any difficulty
            question = await self.db.get_next_question(
                session['user_id'],
                session['chapter_id']
            )

        if question:
            question['session_id'] = session_id
            question['question_number'] = session['current_question'] + 1
            question['total_questions'] = session['total_questions']
            question['current_difficulty'] = session['current_difficulty']

        return question

    async def submit_answer(self, session_id: str, question_id: int, user_answer: str,
                            response_time: float) -> Dict:
        """Submit an answer and get feedback"""
        if session_id not in self.active_sessions:
            return {'error': 'Invalid session'}

        session = self.active_sessions[session_id]

        # Get question details
        async with aiosqlite.connect(self.db.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                "SELECT * FROM questions WHERE question_id = ?",
                (question_id,)
            )
            question = await cursor.fetchone()

        if not question:
            return {'error': 'Question not found'}

        question = dict(question)
        is_correct = user_answer.lower() == question['correct_option'].lower()

        # Calculate points based on difficulty
        points_map = {1: config.POINTS_EASY, 2: config.POINTS_MEDIUM, 3: config.POINTS_HARD}
        points_earned = points_map[question['difficulty']] if is_correct else 0

        # Update session statistics
        session['current_question'] += 1
        session['questions_by_difficulty'][question['difficulty']] += 1
        session['response_times'].append(response_time)

        if is_correct:
            session['score'] += points_earned
            session['correct_streak'] += 1
            session['wrong_streak'] = 0
            session['correct_by_difficulty'][question['difficulty']] += 1
        else:
            session['correct_streak'] = 0
            session['wrong_streak'] += 1

        # Record in database
        await self.db.record_quiz_attempt(
            session['user_id'], session['chapter_id'], question_id,
            user_answer, is_correct, response_time,
            question['difficulty'], points_earned
        )

        # Adjust difficulty for mix mode
        if session['difficulty_mode'] == "mix":
            await self._adjust_difficulty(session_id)

        # Prepare response
        response = {
            'is_correct': is_correct,
            'correct_answer': question['correct_option'],
            'explanation': question.get('explanation', ''),
            'points_earned': points_earned,
            'current_score': session['score'],
            'question_number': session['current_question'],
            'total_questions': session['total_questions'],
            'streak': session['correct_streak']
        }

        # Check if quiz is complete
        if session['current_question'] >= session['total_questions']:
            response['quiz_complete'] = True
            response['final_stats'] = await self._calculate_final_stats(session_id)

        return response

    async def _adjust_difficulty(self, session_id: str):
        """Adjust difficulty based on recent performance (mix mode)"""
        session = self.active_sessions[session_id]
        current_diff = session['current_difficulty']

        # Calculate recent accuracy (last 3-5 questions)
        recent_window = min(5, session['current_question'])
        if recent_window < 3:
            return  # Need at least 3 questions to adjust

        recent_correct = 0
        recent_total = 0

        # Calculate accuracy for current difficulty level
        if session['questions_by_difficulty'][current_diff] >= 3:
            accuracy = session['correct_by_difficulty'][current_diff] / session['questions_by_difficulty'][current_diff]

            # Adjust based on performance
            if accuracy >= config.DIFFICULTY_THRESHOLD_UP and current_diff < 3:
                session['current_difficulty'] = min(3, current_diff + 1)
            elif accuracy <= config.DIFFICULTY_THRESHOLD_DOWN and current_diff > 1:
                session['current_difficulty'] = max(1, current_diff - 1)

    async def _calculate_final_stats(self, session_id: str) -> Dict:
        """Calculate final quiz statistics"""
        session = self.active_sessions[session_id]

        total_questions = session['current_question']
        total_correct = sum(session['correct_by_difficulty'].values())
        accuracy = (total_correct / total_questions) * 100 if total_questions > 0 else 0
        avg_response_time = sum(session['response_times']) / len(session['response_times']) if session[
            'response_times'] else 0

        # Calculate time bonus (faster responses get bonus points)
        time_bonus = 0
        if avg_response_time < 10:  # Less than 10 seconds average
            time_bonus = min(50, int((10 - avg_response_time) * 5))

        final_score = session['score'] + time_bonus

        stats = {
            'total_questions': total_questions,
            'correct_answers': total_correct,
            'accuracy': round(accuracy, 2),
            'final_score': final_score,
            'time_bonus': time_bonus,
            'avg_response_time': round(avg_response_time, 2),
            'difficulty_breakdown': session['questions_by_difficulty'].copy(),
            'quiz_duration': (datetime.now() - session['started_at']).total_seconds()
        }

        # Clean up session
        await self._cleanup_session(session_id)

        return stats

    async def _cleanup_session(self, session_id: str):
        """Clean up completed quiz session"""
        # Remove from active sessions
        if session_id in self.active_sessions:
            del self.active_sessions[session_id]

        # Remove from database
        async with aiosqlite.connect(self.db.db_path) as db:
            await db.execute(
                "DELETE FROM active_quizzes WHERE session_id = ?",
                (session_id,)
            )
            await db.commit()

    async def get_session_info(self, session_id: str) -> Optional[Dict]:
        """Get current session information"""
        return self.active_sessions.get(session_id)

    async def end_quiz(self, session_id: str) -> Dict:
        """Force end a quiz session"""
        if session_id not in self.active_sessions:
            return {'error': 'Invalid session'}

        stats = await self._calculate_final_stats(session_id)
        return {'quiz_ended': True, 'final_stats': stats}
