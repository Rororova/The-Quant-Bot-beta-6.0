import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from supabase import create_client, Client
from postgrest.exceptions import APIError


class DatabaseManager:
    """Supabase database manager for Quiz Bot"""
    
    def __init__(self, supabase_url: str, supabase_key: str):
        self.supabase: Client = create_client(supabase_url, supabase_key)
    
    async def initialize_database(self):
        """Initialize the database - tables should be created via migrations"""
        # Verify connection by checking if tables exist
        try:
            # Try to query users table to verify connection
            result = self.supabase.table('users').select('user_id').limit(1).execute()
            print("✅ Successfully connected to Supabase database")
        except Exception as e:
            print(f"⚠️ Warning: Could not verify database connection: {e}")
            print("Make sure you have run the migrations to create the tables.")
    
    async def add_user(self, user_id: int, username: str):
        """Add a new user to the database"""
        try:
            self.supabase.table('users').upsert({
                'user_id': user_id,
                'username': username
            }).execute()
        except APIError as e:
            print(f"Error adding user: {e}")
            raise
    
    async def add_chapter(self, name: str, description: str, created_by: int) -> int:
        """Add a new chapter"""
        try:
            result = self.supabase.table('chapters').insert({
                'name': name,
                'description': description,
                'created_by': created_by
            }).execute()
            return result.data[0]['chapter_id']
        except APIError as e:
            print(f"Error adding chapter: {e}")
            raise
    
    async def add_question(self, chapter_id: int, question_text: str, option_a: str,
                           option_b: str, option_c: str, option_d: str,
                           correct_option: str, difficulty: int, explanation: str = None) -> int:
        """Add a new question to a chapter"""
        try:
            result = self.supabase.table('questions').insert({
                'chapter_id': chapter_id,
                'question_text': question_text,
                'option_a': option_a,
                'option_b': option_b,
                'option_c': option_c,
                'option_d': option_d,
                'correct_option': correct_option.upper(),
                'difficulty': difficulty,
                'explanation': explanation or ''
            }).execute()
            return result.data[0]['question_id']
        except APIError as e:
            print(f"Error adding question: {e}")
            raise
    
    async def get_chapters(self) -> List[Dict]:
        """Get all chapters"""
        try:
            result = self.supabase.table('chapters').select('*').order('name').execute()
            return result.data
        except APIError as e:
            print(f"Error getting chapters: {e}")
            return []
    
    async def get_next_question(self, user_id: int, chapter_id: int, difficulty: int = None) -> Optional[Dict]:
        """Get next question for user, avoiding recently attempted questions"""
        try:
            # First, get questions that haven't been attempted recently
            # This is a simplified version - Supabase doesn't support RANDOM() directly
            # We'll use a different approach
            
            query = self.supabase.table('questions').select('*').eq('chapter_id', chapter_id)
            
            if difficulty:
                query = query.eq('difficulty', difficulty)
            
            # Get all matching questions
            result = query.execute()
            questions = result.data
            
            if not questions:
                return None
            
            # Get user's question history
            history_result = self.supabase.table('user_question_history').select('question_id, last_attempted').eq('user_id', user_id).execute()
            attempted_questions = {row['question_id']: row['last_attempted'] for row in history_result.data}
            
            # Sort questions: unattempted first, then by last_attempted
            import random
            def sort_key(q):
                qid = q['question_id']
                if qid not in attempted_questions:
                    return (0, random.random())  # Unattempted questions first, random order
                return (1, attempted_questions[qid])
            
            questions.sort(key=sort_key)
            
            # Return the first question (least recently attempted or never attempted)
            return questions[0] if questions else None
            
        except APIError as e:
            print(f"Error getting next question: {e}")
            return None
    
    async def record_quiz_attempt(self, user_id: int, chapter_id: int, question_id: int,
                                  user_answer: str, is_correct: bool, response_time: float,
                                  difficulty: int, points_earned: int):
        """Record a quiz attempt"""
        try:
            # Record the attempt
            self.supabase.table('quiz_attempts').insert({
                'user_id': user_id,
                'chapter_id': chapter_id,
                'question_id': question_id,
                'user_answer': user_answer,
                'is_correct': is_correct,
                'response_time': response_time,
                'difficulty': difficulty,
                'points_earned': points_earned
            }).execute()
            
            # Update user question history
            self.supabase.table('user_question_history').upsert({
                'user_id': user_id,
                'question_id': question_id,
                'last_attempted': datetime.now().isoformat()
            }).execute()
            
            # Get current user stats
            user_result = self.supabase.table('users').select('*').eq('user_id', user_id).execute()
            if user_result.data:
                user = user_result.data[0]
                total_questions = user.get('total_questions', 0) + 1
                correct_answers = user.get('correct_answers', 0) + (1 if is_correct else 0)
                total_points = user.get('total_points', 0) + points_earned
                
                # Calculate new average response time
                old_avg = user.get('average_response_time', 0.0) or 0.0
                new_avg = ((old_avg * (total_questions - 1)) + response_time) / total_questions
                
                # Update user stats
                self.supabase.table('users').update({
                    'total_points': total_points,
                    'total_questions': total_questions,
                    'correct_answers': correct_answers,
                    'average_response_time': new_avg
                }).eq('user_id', user_id).execute()
            else:
                # User doesn't exist, create with initial stats
                self.supabase.table('users').upsert({
                    'user_id': user_id,
                    'total_points': points_earned,
                    'total_questions': 1,
                    'correct_answers': 1 if is_correct else 0,
                    'average_response_time': response_time
                }).execute()
                
        except APIError as e:
            print(f"Error recording quiz attempt: {e}")
            raise
    
    async def get_user_stats(self, user_id: int) -> Optional[Dict]:
        """Get comprehensive user statistics"""
        try:
            result = self.supabase.table('users').select('*').eq('user_id', user_id).execute()
            return result.data[0] if result.data else None
        except APIError as e:
            print(f"Error getting user stats: {e}")
            return None
    
    async def get_leaderboard(self, timeframe: str = 'all_time', limit: int = 10) -> List[Dict]:
        """Get leaderboard for specified timeframe"""
        try:
            if timeframe == 'daily':
                today = datetime.now().date().isoformat()
                # Use RPC function or raw SQL for complex queries
                # For now, we'll fetch all and filter (not ideal for large datasets)
                result = self.supabase.table('quiz_attempts').select(
                    'user_id, points_earned, users!inner(username)'
                ).gte('attempted_at', today).execute()
                
                # Group by user and sum points
                user_points = {}
                for row in result.data:
                    uid = row['user_id']
                    if uid not in user_points:
                        user_points[uid] = {'user_id': uid, 'username': row['users']['username'], 'points': 0, 'questions_answered': 0}
                    user_points[uid]['points'] += row.get('points_earned', 0)
                    user_points[uid]['questions_answered'] += 1
                
                leaderboard = sorted(user_points.values(), key=lambda x: x['points'], reverse=True)[:limit]
                return leaderboard
                
            elif timeframe == 'monthly':
                month_start = datetime.now().replace(day=1).date().isoformat()
                result = self.supabase.table('quiz_attempts').select(
                    'user_id, points_earned, users!inner(username)'
                ).gte('attempted_at', month_start).execute()
                
                user_points = {}
                for row in result.data:
                    uid = row['user_id']
                    if uid not in user_points:
                        user_points[uid] = {'user_id': uid, 'username': row['users']['username'], 'points': 0, 'questions_answered': 0}
                    user_points[uid]['points'] += row.get('points_earned', 0)
                    user_points[uid]['questions_answered'] += 1
                
                leaderboard = sorted(user_points.values(), key=lambda x: x['points'], reverse=True)[:limit]
                return leaderboard
                
            else:  # all_time
                result = self.supabase.table('users').select(
                    'username, total_points, total_questions, correct_answers'
                ).order('total_points', desc=True).limit(limit).execute()
                
                leaderboard = []
                for user in result.data:
                    total_q = user.get('total_questions', 0)
                    correct = user.get('correct_answers', 0)
                    accuracy = round((correct / total_q * 100), 2) if total_q > 0 else 0
                    leaderboard.append({
                        'username': user['username'],
                        'points': user.get('total_points', 0),
                        'questions_answered': total_q,
                        'accuracy': accuracy
                    })
                
                return leaderboard
                
        except APIError as e:
            print(f"Error getting leaderboard: {e}")
            return []
    
    async def get_user_chapter_performance(self, user_id: int) -> List[Dict]:
        """Get user performance by chapter for SWOT analysis"""
        try:
            # This requires a more complex query - using RPC or multiple queries
            attempts_result = self.supabase.table('quiz_attempts').select(
                'chapter_id, is_correct, response_time, chapters!inner(name)'
            ).eq('user_id', user_id).execute()
            
            # Group by chapter
            chapter_stats = {}
            for attempt in attempts_result.data:
                chapter_id = attempt['chapter_id']
                chapter_name = attempt['chapters']['name']
                
                if chapter_id not in chapter_stats:
                    chapter_stats[chapter_id] = {
                        'chapter_name': chapter_name,
                        'total_attempts': 0,
                        'correct_answers': 0,
                        'response_times': []
                    }
                
                chapter_stats[chapter_id]['total_attempts'] += 1
                if attempt['is_correct']:
                    chapter_stats[chapter_id]['correct_answers'] += 1
                if attempt.get('response_time'):
                    chapter_stats[chapter_id]['response_times'].append(attempt['response_time'])
            
            # Calculate statistics
            performance = []
            for chapter_id, stats in chapter_stats.items():
                if stats['total_attempts'] >= 3:
                    avg_time = sum(stats['response_times']) / len(stats['response_times']) if stats['response_times'] else 0
                    accuracy = (stats['correct_answers'] / stats['total_attempts']) * 100
                    performance.append({
                        'chapter_name': stats['chapter_name'],
                        'total_attempts': stats['total_attempts'],
                        'correct_answers': stats['correct_answers'],
                        'avg_response_time': avg_time,
                        'accuracy': accuracy
                    })
            
            # Sort by accuracy ascending, then by avg_response_time descending
            performance.sort(key=lambda x: (x['accuracy'], -x['avg_response_time']))
            return performance
            
        except APIError as e:
            print(f"Error getting user chapter performance: {e}")
            return []
    
    async def cleanup_old_sessions(self):
        """Clean up old quiz sessions (older than 30 minutes)"""
        try:
            cutoff_time = (datetime.now() - timedelta(minutes=30)).isoformat()
            self.supabase.table('active_quizzes').delete().lt('started_at', cutoff_time).execute()
        except APIError as e:
            print(f"Error cleaning up old sessions: {e}")

