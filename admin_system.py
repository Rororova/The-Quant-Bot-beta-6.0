import asyncio
import csv
import json
from typing import List, Dict, Optional
from datetime import datetime, timedelta
import config


class AdminSystem:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.admin_sessions = {}

    async def import_questions_from_csv(self, csv_content: str, chapter_id: int) -> Dict:
        """Import questions from CSV format"""
        try:
            lines = csv_content.strip().split('\n')
            reader = csv.DictReader(lines)

            imported_count = 0
            errors = []

            for row_num, row in enumerate(reader, start=2):
                try:
                    # Validate required fields
                    required_fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                                       'correct_option', 'difficulty']
                    for field in required_fields:
                        if field not in row or not row[field].strip():
                            raise ValueError(f"Missing or empty field: {field}")

                    # Validate difficulty
                    difficulty = int(row['difficulty'])
                    if difficulty not in [1, 2, 3]:
                        raise ValueError("Difficulty must be 1, 2, or 3")

                    # Validate correct option
                    correct_option = row['correct_option'].upper()
                    if correct_option not in ['A', 'B', 'C', 'D']:
                        raise ValueError("Correct option must be A, B, C, or D")

                    # Add question
                    await self.db.add_question(
                        chapter_id=chapter_id,
                        question_text=row['question_text'].strip(),
                        option_a=row['option_a'].strip(),
                        option_b=row['option_b'].strip(),
                        option_c=row['option_c'].strip(),
                        option_d=row['option_d'].strip(),
                        correct_option=correct_option,
                        difficulty=difficulty,
                        explanation=row.get('explanation', '').strip()
                    )

                    imported_count += 1

                except Exception as e:
                    errors.append(f"Row {row_num}: {str(e)}")

            return {
                'success': True,
                'imported_count': imported_count,
                'errors': errors
            }

        except Exception as e:
            return {
                'success': False,
                'error': f"CSV parsing error: {str(e)}"
            }

    async def import_questions_from_json(self, json_content: str, chapter_id: int) -> Dict:
        """Import questions from JSON format"""
        try:
            data = json.loads(json_content)

            if not isinstance(data, list):
                return {'success': False, 'error': 'JSON must contain an array of questions'}

            imported_count = 0
            errors = []

            for i, question_data in enumerate(data):
                try:
                    # Validate required fields
                    required_fields = ['question_text', 'option_a', 'option_b', 'option_c', 'option_d',
                                       'correct_option', 'difficulty']
                    for field in required_fields:
                        if field not in question_data:
                            raise ValueError(f"Missing field: {field}")

                    # Validate difficulty
                    difficulty = int(question_data['difficulty'])
                    if difficulty not in [1, 2, 3]:
                        raise ValueError("Difficulty must be 1, 2, or 3")

                    # Validate correct option
                    correct_option = question_data['correct_option'].upper()
                    if correct_option not in ['A', 'B', 'C', 'D']:
                        raise ValueError("Correct option must be A, B, C, or D")

                    # Add question
                    await self.db.add_question(
                        chapter_id=chapter_id,
                        question_text=question_data['question_text'],
                        option_a=question_data['option_a'],
                        option_b=question_data['option_b'],
                        option_c=question_data['option_c'],
                        option_d=question_data['option_d'],
                        correct_option=correct_option,
                        difficulty=difficulty,
                        explanation=question_data.get('explanation', '')
                    )

                    imported_count += 1

                except Exception as e:
                    errors.append(f"Question {i + 1}: {str(e)}")

            return {
                'success': True,
                'imported_count': imported_count,
                'errors': errors
            }

        except json.JSONDecodeError as e:
            return {
                'success': False,
                'error': f"Invalid JSON format: {str(e)}"
            }
        except Exception as e:
            return {
                'success': False,
                'error': f"Import error: {str(e)}"
            }

    async def get_system_stats(self) -> Dict:
        """Get comprehensive system statistics"""
        stats = {}
        
        if config.DATABASE_TYPE == 'supabase':
            # Use Supabase client
            try:
                # User statistics
                users_result = self.db.supabase.table('users').select('user_id', count='exact').execute()
                stats['total_users'] = users_result.count if hasattr(users_result, 'count') else len(users_result.data) if users_result.data else 0

                # Chapter statistics
                chapters_result = self.db.supabase.table('chapters').select('chapter_id', count='exact').execute()
                stats['total_chapters'] = chapters_result.count if hasattr(chapters_result, 'count') else len(chapters_result.data) if chapters_result.data else 0

                # Question statistics
                questions_result = self.db.supabase.table('questions').select('question_id', count='exact').execute()
                stats['total_questions'] = questions_result.count if hasattr(questions_result, 'count') else len(questions_result.data) if questions_result.data else 0

                # Questions by difficulty
                all_questions = self.db.supabase.table('questions').select('difficulty').execute()
                difficulty_counts = {}
                for q in all_questions.data:
                    diff = str(q.get('difficulty', '0'))
                    difficulty_counts[diff] = difficulty_counts.get(diff, 0) + 1
                stats['questions_by_difficulty'] = difficulty_counts

                # Quiz attempt statistics
                attempts_result = self.db.supabase.table('quiz_attempts').select('attempt_id', count='exact').execute()
                stats['total_attempts'] = attempts_result.count if hasattr(attempts_result, 'count') else len(attempts_result.data) if attempts_result.data else 0

                # Recent activity (last 24 hours)
                yesterday = (datetime.now() - timedelta(hours=24)).isoformat()
                recent_attempts = self.db.supabase.table('quiz_attempts').select('attempt_id', count='exact').gte('attempted_at', yesterday).execute()
                stats['attempts_last_24h'] = recent_attempts.count if hasattr(recent_attempts, 'count') else len(recent_attempts.data) if recent_attempts.data else 0

                # Active users (last 7 days)
                week_ago = (datetime.now() - timedelta(days=7)).isoformat()
                active_users_result = self.db.supabase.table('quiz_attempts').select('user_id').gte('attempted_at', week_ago).execute()
                unique_users = set(row['user_id'] for row in active_users_result.data) if active_users_result.data else set()
                stats['active_users_week'] = len(unique_users)

            except Exception as e:
                print(f"Error getting system stats: {e}")
                # Return empty stats on error
                stats = {
                    'total_users': 0,
                    'total_chapters': 0,
                    'total_questions': 0,
                    'questions_by_difficulty': {},
                    'total_attempts': 0,
                    'attempts_last_24h': 0,
                    'active_users_week': 0
                }
        else:
            # Use SQLite (original code)
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                # User statistics
                cursor = await db.execute("SELECT COUNT(*) FROM users")
                stats['total_users'] = (await cursor.fetchone())[0]

                # Chapter statistics
                cursor = await db.execute("SELECT COUNT(*) FROM chapters")
                stats['total_chapters'] = (await cursor.fetchone())[0]

                # Question statistics
                cursor = await db.execute("SELECT COUNT(*) FROM questions")
                stats['total_questions'] = (await cursor.fetchone())[0]

                # Questions by difficulty
                cursor = await db.execute("""
                                          SELECT difficulty, COUNT(*) as count
                                          FROM questions
                                          GROUP BY difficulty
                                          ORDER BY difficulty
                                          """)
                difficulty_counts = await cursor.fetchall()
                stats['questions_by_difficulty'] = {str(row[0]): row[1] for row in difficulty_counts}

                # Quiz attempt statistics
                cursor = await db.execute("SELECT COUNT(*) FROM quiz_attempts")
                stats['total_attempts'] = (await cursor.fetchone())[0]

                # Recent activity (last 24 hours)
                cursor = await db.execute("""
                                          SELECT COUNT(*)
                                          FROM quiz_attempts
                                          WHERE attempted_at > datetime('now', '-24 hours')
                                          """)
                stats['attempts_last_24h'] = (await cursor.fetchone())[0]

                # Active users (users who attempted questions in last 7 days)
                cursor = await db.execute("""
                                          SELECT COUNT(DISTINCT user_id)
                                          FROM quiz_attempts
                                          WHERE attempted_at > datetime('now', '-7 days')
                                          """)
                stats['active_users_week'] = (await cursor.fetchone())[0]

        return stats

    async def get_detailed_user_report(self, user_id: int) -> Dict:
        """Get detailed report for a specific user"""
        user_stats = await self.db.get_user_stats(user_id)
        if not user_stats:
            return {'error': 'User not found'}

        if config.DATABASE_TYPE == 'supabase':
            try:
                # Recent activity
                attempts_result = self.db.supabase.table('quiz_attempts').select(
                    '*, chapters(name), questions(question_text, difficulty)'
                ).eq('user_id', user_id).order('attempted_at', desc=True).limit(50).execute()
                
                recent_attempts = []
                for attempt in attempts_result.data:
                    attempt_dict = dict(attempt)
                    if attempt.get('chapters'):
                        attempt_dict['chapter_name'] = attempt['chapters'].get('name') if isinstance(attempt['chapters'], dict) else attempt['chapters']
                    if attempt.get('questions'):
                        q_data = attempt['questions'] if isinstance(attempt['questions'], dict) else attempt['questions']
                        attempt_dict['question_text'] = q_data.get('question_text', '')
                        attempt_dict['difficulty'] = q_data.get('difficulty', 0)
                    recent_attempts.append(attempt_dict)

                # Performance by difficulty
                all_attempts = self.db.supabase.table('quiz_attempts').select('*').eq('user_id', user_id).execute()
                difficulty_stats = {}
                for attempt in all_attempts.data:
                    diff = attempt.get('difficulty', 0)
                    if diff not in difficulty_stats:
                        difficulty_stats[diff] = {
                            'difficulty': diff,
                            'total_attempts': 0,
                            'correct_attempts': 0,
                            'response_times': [],
                            'total_points': 0
                        }
                    difficulty_stats[diff]['total_attempts'] += 1
                    if attempt.get('is_correct'):
                        difficulty_stats[diff]['correct_attempts'] += 1
                    if attempt.get('response_time'):
                        difficulty_stats[diff]['response_times'].append(attempt['response_time'])
                    difficulty_stats[diff]['total_points'] += attempt.get('points_earned', 0)
                
                difficulty_performance = []
                for diff, stats in sorted(difficulty_stats.items()):
                    avg_time = sum(stats['response_times']) / len(stats['response_times']) if stats['response_times'] else 0
                    difficulty_performance.append({
                        'difficulty': diff,
                        'total_attempts': stats['total_attempts'],
                        'correct_attempts': stats['correct_attempts'],
                        'avg_response_time': avg_time,
                        'total_points': stats['total_points']
                    })

                return {
                    'user_info': user_stats,
                    'recent_attempts': recent_attempts,
                    'difficulty_performance': difficulty_performance
                }
            except Exception as e:
                print(f"Error getting detailed user report: {e}")
                return {'error': f'Error generating report: {str(e)}'}
        else:
            # Use SQLite (original code)
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = aiosqlite.Row

                # Recent activity
                cursor = await db.execute("""
                                          SELECT qa.*, c.name as chapter_name, q.question_text, q.difficulty
                                          FROM quiz_attempts qa
                                                   JOIN chapters c ON qa.chapter_id = c.chapter_id
                                                   JOIN questions q ON qa.question_id = q.question_id
                                          WHERE qa.user_id = ?
                                          ORDER BY qa.attempted_at DESC LIMIT 50
                                          """, (user_id,))
                recent_attempts = [dict(row) for row in await cursor.fetchall()]

                # Performance by difficulty
                cursor = await db.execute("""
                                          SELECT difficulty,
                                                 COUNT(*)                                    as total_attempts,
                                                 SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) as correct_attempts,
                                                 AVG(response_time)                          as avg_response_time,
                                                 SUM(points_earned)                          as total_points
                                          FROM quiz_attempts
                                          WHERE user_id = ?
                                          GROUP BY difficulty
                                          ORDER BY difficulty
                                          """, (user_id,))
                difficulty_performance = [dict(row) for row in await cursor.fetchall()]

                return {
                    'user_info': user_stats,
                    'recent_attempts': recent_attempts,
                    'difficulty_performance': difficulty_performance
                }

    async def bulk_manage_questions(self, chapter_id: int, action: str, question_ids: List[int] = None) -> Dict:
        """Bulk manage questions (delete, move, etc.)"""
        try:
            if config.DATABASE_TYPE == 'supabase':
                if action == 'delete' and question_ids:
                    # Delete specified questions
                    deleted_count = 0
                    for qid in question_ids:
                        result = self.db.supabase.table('questions').delete().eq('question_id', qid).eq('chapter_id', chapter_id).execute()
                        if result.data:
                            deleted_count += 1
                    
                    return {
                        'success': True,
                        'message': f'Deleted {deleted_count} questions',
                        'affected_count': deleted_count
                    }

                elif action == 'delete_all':
                    # Delete all questions in chapter
                    result = self.db.supabase.table('questions').delete().eq('chapter_id', chapter_id).execute()
                    deleted_count = len(result.data) if result.data else 0
                    
                    return {
                        'success': True,
                        'message': f'Deleted all {deleted_count} questions from chapter',
                        'affected_count': deleted_count
                    }

                else:
                    return {'success': False, 'error': 'Invalid action or missing question IDs'}
            else:
                # Use SQLite (original code)
                import aiosqlite
                async with aiosqlite.connect(self.db.db_path) as db:
                    if action == 'delete' and question_ids:
                        # Delete specified questions
                        placeholders = ','.join(['?' for _ in question_ids])
                        await db.execute(
                            f"DELETE FROM questions WHERE question_id IN ({placeholders}) AND chapter_id = ?",
                            question_ids + [chapter_id]
                        )
                        affected_rows = db.total_changes
                        await db.commit()

                        return {
                            'success': True,
                            'message': f'Deleted {affected_rows} questions',
                            'affected_count': affected_rows
                        }

                    elif action == 'delete_all':
                        # Delete all questions in chapter
                        cursor = await db.execute(
                            "DELETE FROM questions WHERE chapter_id = ?",
                            (chapter_id,)
                        )
                        affected_rows = db.total_changes
                        await db.commit()

                        return {
                            'success': True,
                            'message': f'Deleted all {affected_rows} questions from chapter',
                            'affected_count': affected_rows
                        }

                    else:
                        return {'success': False, 'error': 'Invalid action or missing question IDs'}

        except Exception as e:
            return {'success': False, 'error': f'Database error: {str(e)}'}

    async def export_chapter_data(self, chapter_id: int) -> Dict:
        """Export all questions from a chapter"""
        if config.DATABASE_TYPE == 'supabase':
            try:
                # Get chapter info
                chapter_result = self.db.supabase.table('chapters').select('*').eq('chapter_id', chapter_id).execute()
                if not chapter_result.data:
                    return {'error': 'Chapter not found'}
                chapter = chapter_result.data[0]

                # Get all questions
                questions_result = self.db.supabase.table('questions').select('*').eq('chapter_id', chapter_id).order('difficulty').order('question_id').execute()
                questions = questions_result.data if questions_result.data else []

                return {
                    'chapter_info': chapter,
                    'questions': questions,
                    'total_questions': len(questions)
                }
            except Exception as e:
                return {'error': f'Error exporting chapter data: {str(e)}'}
        else:
            # Use SQLite (original code)
            import aiosqlite
            async with aiosqlite.connect(self.db.db_path) as db:
                db.row_factory = aiosqlite.Row

                # Get chapter info
                cursor = await db.execute("SELECT * FROM chapters WHERE chapter_id = ?", (chapter_id,))
                chapter = await cursor.fetchone()

                if not chapter:
                    return {'error': 'Chapter not found'}

                # Get all questions
                cursor = await db.execute("""
                                          SELECT *
                                          FROM questions
                                          WHERE chapter_id = ?
                                          ORDER BY difficulty, question_id
                                          """, (chapter_id,))
                questions = [dict(row) for row in await cursor.fetchall()]

                return {
                    'chapter_info': dict(chapter),
                    'questions': questions,
                    'total_questions': len(questions)
                }