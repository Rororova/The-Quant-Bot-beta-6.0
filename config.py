import os
from dotenv import load_dotenv

load_dotenv()

# Bot Configuration
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID', 0))
ADMIN_ROLE = os.getenv('ADMIN_ROLE', 'Admin')
CREATOR_ID = int(os.getenv('CREATOR_ID', 0))

# Database Configuration
# Choose database type: 'sqlite' or 'supabase'
DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'supabase')

# SQLite Configuration (if using SQLite)
DATABASE_PATH = os.getenv('DATABASE_PATH', 'quiz_bot.db')

# Supabase Configuration (if using Supabase)
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')  # DEPRECATED: Use SERVICE_ROLE_KEY for bot
SUPABASE_SERVICE_ROLE_KEY = os.getenv('SUPABASE_SERVICE_ROLE_KEY')  # REQUIRED: Service role key for bot operations
# Note: For security, bot should use SERVICE_ROLE_KEY, not anon key
# The service role key bypasses RLS but should only be used server-side

# Quiz Configuration
POINTS_EASY = 1
POINTS_MEDIUM = 2
POINTS_HARD = 3

# Difficulty thresholds for auto-adjustment
DIFFICULTY_THRESHOLD_UP = 0.8    # Move to harder difficulty if accuracy > 80%
DIFFICULTY_THRESHOLD_DOWN = 0.4  # Move to easier difficulty if accuracy < 40%

# Ranking Configuration
RANKING_ROLES = {
    'QA Pleasant': {'min_points': 0, 'color': 0xCD7F32},
    'QA Baron': {'min_points': 100, 'color': 0xC0C0C0},
    'QA Viscount': {'min_points': 300, 'color': 0xFFD700},
    'QA Marquis': {'min_points': 600, 'color': 0xE5E4E2},
    'QA Earl': {'min_points': 1000, 'color': 0xB9F2FF},
    'Quiz Duke': {'min_points': 2000, 'color': 0x9932CC},
    'QA Grand Duke' : {'min_points' : 5000,'color' : 0x6a5acd},

}

#guild authorization

ALLOWED_GUILDS = [1400423664440049725,1414849698052968480]
