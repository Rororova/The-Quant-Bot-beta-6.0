import aiosqlite
import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
from typing import List, Dict
import config
from database import DatabaseManager


class AnalyticsSystem:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def generate_swot_analysis(self, user_id: int) -> BytesIO:
        """Generate SWOT analysis infographic for user"""
        # Get user chapter performance
        performance_data = await self.db.get_user_chapter_performance(user_id)

        if not performance_data:
            return self._create_no_data_image()

        # Sort to get weakest chapters (lowest accuracy, highest response time)
        weakest_chapters = sorted(
            performance_data,
            key=lambda x: (x['accuracy'], -x['avg_response_time'])
        )[:5]

        # Create the visualization
        plt.style.use('seaborn-v0_8')
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('SWOT Analysis - Performance Overview', fontsize=20, fontweight='bold')

        # Strengths (top performing chapters)
        if len(performance_data) > 0:
            strengths = sorted(performance_data, key=lambda x: x['accuracy'], reverse=True)[:3]
            ax1.set_title('STRENGTHS - Top Performing Chapters', fontsize=14, fontweight='bold', color='green')

            chapters = [s['chapter_name'] for s in strengths]
            accuracies = [s['accuracy'] * 100 for s in strengths]

            bars1 = ax1.barh(chapters, accuracies, color=['#2E8B57', '#32CD32', '#90EE90'])
            ax1.set_xlabel('Accuracy (%)')
            ax1.set_xlim(0, 100)

            # Add value labels on bars
            for i, bar in enumerate(bars1):
                width = bar.get_width()
                ax1.text(width + 1, bar.get_y() + bar.get_height() / 2,
                         f'{width:.1f}%', ha='left', va='center')

        # Weaknesses (lowest performing chapters)
        ax2.set_title('WEAKNESSES - Areas for Improvement', fontsize=14, fontweight='bold', color='red')

        weak_chapters = [w['chapter_name'] for w in weakest_chapters]
        weak_accuracies = [w['accuracy'] * 100 for w in weakest_chapters]

        bars2 = ax2.barh(weak_chapters, weak_accuracies, color=['#DC143C', '#FF6347', '#FFA07A', '#FFB6C1', '#FFC0CB'])
        ax2.set_xlabel('Accuracy (%)')
        ax2.set_xlim(0, 100)

        # Add value labels on bars
        for i, bar in enumerate(bars2):
            width = bar.get_width()
            ax2.text(width + 1, bar.get_y() + bar.get_height() / 2,
                     f'{width:.1f}%', ha='left', va='center')

        # Opportunities (response time analysis)
        ax3.set_title('OPPORTUNITIES - Response Time Analysis', fontsize=14, fontweight='bold', color='blue')

        response_times = [w['avg_response_time'] for w in weakest_chapters]

        bars3 = ax3.barh(weak_chapters, response_times, color=['#4169E1', '#6495ED', '#87CEEB', '#B0E0E6', '#E0F6FF'])
        ax3.set_xlabel('Average Response Time (seconds)')

        # Add value labels on bars
        for i, bar in enumerate(bars3):
            width = bar.get_width()
            ax3.text(width + 0.1, bar.get_y() + bar.get_height() / 2,
                     f'{width:.1f}s', ha='left', va='center')

        # Threats (consistency analysis)
        ax4.set_title('THREATS - Consistency Issues', fontsize=14, fontweight='bold', color='orange')

        # Calculate consistency score (lower is worse)
        consistency_scores = []
        for chapter in weakest_chapters:
            # Simple consistency metric: inverse of response time variance
            consistency_score = max(0, 100 - (chapter['avg_response_time'] * 10))
            consistency_scores.append(consistency_score)

        bars4 = ax4.barh(weak_chapters, consistency_scores,
                         color=['#FF8C00', '#FFA500', '#FFB347', '#FFCC5C', '#FFD700'])
        ax4.set_xlabel('Consistency Score')
        ax4.set_xlim(0, 100)

        # Add value labels on bars
        for i, bar in enumerate(bars4):
            width = bar.get_width()
            ax4.text(width + 1, bar.get_y() + bar.get_height() / 2,
                     f'{width:.0f}', ha='left', va='center')

        plt.tight_layout()

        # Save to BytesIO
        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='PNG', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    def _create_no_data_image(self) -> BytesIO:
        """Create a placeholder image when no data is available"""
        fig, ax = plt.subplots(1, 1, figsize=(10, 6))
        ax.text(0.5, 0.5,
                'No Quiz Data Available\nComplete at least 3 questions\nin different chapters to see your SWOT analysis',
                ha='center', va='center', fontsize=16,
                bbox=dict(boxstyle="round,pad=0.3", facecolor="lightgray"))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.axis('off')

        img_buffer = BytesIO()
        plt.savefig(img_buffer, format='PNG', dpi=300, bbox_inches='tight')
        img_buffer.seek(0)
        plt.close()

        return img_buffer

    async def generate_performance_report(self, user_id: int) -> Dict:
        """Generate comprehensive performance report"""
        user_stats = await self.db.get_user_stats(user_id)
        if not user_stats:
            return {'error': 'User not found'}

        # Get detailed performance by chapter
        chapter_performance = await self.db.get_user_chapter_performance(user_id)

        # Calculate various metrics
        overall_accuracy = (user_stats['correct_answers'] / user_stats['total_questions'] * 100) if user_stats[
                                                                                                        'total_questions'] > 0 else 0

        # Performance trends (simplified - would need time series data for full implementation)
        report = {
            'user_id': user_id,
            'username': user_stats['username'],
            'overall_stats': {
                'total_points': user_stats['total_points'],
                'total_questions': user_stats['total_questions'],
                'overall_accuracy': round(overall_accuracy, 2),
                'average_response_time': round(user_stats['average_response_time'], 2),
                'current_rank': user_stats['current_rank']
            },
            'chapter_breakdown': chapter_performance,
            'improvement_suggestions': self._generate_suggestions(chapter_performance, overall_accuracy)
        }

        return report

    def _generate_suggestions(self, chapter_performance: List[Dict], overall_accuracy: float) -> List[str]:
        """Generate improvement suggestions based on performance"""
        suggestions = []

        if overall_accuracy < 60:
            suggestions.append("Focus on understanding fundamental concepts before attempting quizzes")

        if chapter_performance:
            # Find chapters with low accuracy
            weak_chapters = [ch for ch in chapter_performance if ch['accuracy'] < 0.5]
            if weak_chapters:
                suggestions.append(
                    f"Review these challenging chapters: {', '.join([ch['chapter_name'] for ch in weak_chapters[:3]])}")

            # Find chapters with slow response times
            slow_chapters = [ch for ch in chapter_performance if ch['avg_response_time'] > 20]
            if slow_chapters:
                suggestions.append("Practice quick recall for better response times")

        if not suggestions:
            suggestions.append("Great job! Keep practicing to maintain your performance")

        return suggestions


class RankingSystem:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    async def calculate_user_rank(self, user_id: int) -> str:
        """Calculate and update user rank based on performance"""
        user_stats = await self.db.get_user_stats(user_id)
        if not user_stats:
            return 'QA Pleasant'

        points = user_stats['total_points']

        # Find appropriate rank
        new_rank = 'QA Pleasant'
        for rank_name, requirements in config.RANKING_ROLES.items():
            if points >= requirements['min_points']:
                new_rank = rank_name

        # Update rank in database if changed
        if new_rank != user_stats['current_rank']:
            async with aiosqlite.connect(self.db.db_path) as db:
                await db.execute(
                    "UPDATE users SET current_rank = ? WHERE user_id = ?",
                    (new_rank, user_id)
                )
                await db.commit()

        return new_rank

    async def get_rank_info(self, user_id: int) -> Dict:
        """Get detailed rank information for user"""
        user_stats = await self.db.get_user_stats(user_id)
        if not user_stats:
            return {'error': 'User not found'}

        current_points = user_stats['total_points']
        current_rank = await self.calculate_user_rank(user_id)

        # Find next rank
        next_rank = None
        points_to_next = None

        rank_list = list(config.RANKING_ROLES.keys())
        current_rank_index = rank_list.index(current_rank) if current_rank in rank_list else 0

        if current_rank_index < len(rank_list) - 1:
            next_rank = rank_list[current_rank_index + 1]
            points_to_next = config.RANKING_ROLES[next_rank]['min_points'] - current_points

        return {
            'current_rank': current_rank,
            'current_points': current_points,
            'next_rank': next_rank,
            'points_to_next_rank': points_to_next,
            'rank_color': config.RANKING_ROLES[current_rank]['color']

        }

