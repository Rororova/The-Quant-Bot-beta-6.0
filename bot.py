import discord
from discord.ext import commands, tasks
import asyncio
import aiosqlite
from datetime import datetime, timedelta
import config
from quiz_system import QuizSystem
from analytics import AnalyticsSystem, RankingSystem
from admin_system import AdminSystem
import webserver

# Import database manager based on config
if config.DATABASE_TYPE == 'supabase':
    from database_supabase_secure import DatabaseManager
    if not config.SUPABASE_URL:
        raise ValueError("SUPABASE_URL must be set in .env when using Supabase")
    if not config.SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError("SUPABASE_SERVICE_ROLE_KEY must be set in .env for secure operations")
        print("⚠️  WARNING: Using anon key is not secure. Use SERVICE_ROLE_KEY for bot operations.")
else:
    from database import DatabaseManager
# Set up intents
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True


class QuizBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None)

        # Initialize systems
        if config.DATABASE_TYPE == 'supabase':
            # Use service role key for secure operations
            service_key = config.SUPABASE_SERVICE_ROLE_KEY or config.SUPABASE_KEY
            if not service_key:
                raise ValueError("SUPABASE_SERVICE_ROLE_KEY must be set in .env for secure database operations")
            self.db = DatabaseManager(config.SUPABASE_URL, service_key)
        else:
            self.db = DatabaseManager(config.DATABASE_PATH)
        self.quiz_system = QuizSystem(self.db)
        self.analytics = AnalyticsSystem(self.db)
        self.ranking = RankingSystem(self.db)
        self.admin_system = AdminSystem(self.db)

        # Active quiz sessions for reaction handling
        self.active_quiz_messages = {}

    async def setup_hook(self):
        """Initialize database and start background tasks"""
        await self.db.initialize_database()
        self.cleanup_sessions.start()
        print("Quiz Bot is ready!")

    async def on_ready(self):
        print(f'{self.user} has connected to Discord!')
        print(f'Bot is in {len(self.guilds)} guilds')

    async def on_command_error(self, ctx, error):
        """Handle command errors"""
        if isinstance(error, commands.CommandNotFound):
            return  # Ignore command not found errors
        
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"❌ Missing required argument: {error.param.name}")
            return
        
        if isinstance(error, commands.BadArgument):
            await ctx.send(f"❌ Invalid argument: {str(error)}")
            return
        
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(f"❌ Command is on cooldown. Try again in {error.retry_after:.2f} seconds.")
            return
        
        if isinstance(error, commands.CheckFailure):
            return  # Already handled by global_access_check
        
        # Log unexpected errors
        print(f"Error in command {ctx.command}: {error}")
        print(f"Error type: {type(error)}")
        import traceback
        traceback.print_exception(type(error), error, error.__traceback__)
        
        # Send user-friendly error message
        try:
            await ctx.send("❌ An error occurred while executing this command. Please try again later.")
        except:
            pass  # If we can't send a message, just ignore it

    async def on_member_join(self, member):
        """Add new members to database"""
        await self.db.add_user(member.id, str(member))

    @tasks.loop(minutes=30)
    async def cleanup_sessions(self):
        """Clean up old quiz sessions periodically"""
        await self.db.cleanup_old_sessions()

    async def is_admin(self, user) -> bool:
        """Check if user has admin privileges"""
        if user.id == config.CREATOR_ID:
            return True

        for role in user.roles:
            if role.name == config.ADMIN_ROLE:
                return True
        return False

    async def is_creator(self, user) -> bool:
        """Check if user is the bot creator"""
        return user.id == config.CREATOR_ID


bot = QuizBot()

@bot.check
async def global_access_check(ctx):
    """Global check for all commands"""
    try:
        # Block DMs
        if ctx.guild is None:
            await ctx.send("❌ This bot cannot be used in Direct Messages.")
            return False
        # Block unauthorized guilds
        allowed_guilds = getattr(config, "ALLOWED_GUILDS", [])
        if allowed_guilds and ctx.guild.id not in allowed_guilds:
            await ctx.send("❌ This bot is not authorized for this server.")
            return False
        return True
    except Exception as e:
        print(f"Error in global_access_check: {e}")
        return False

# Quiz Commands
@bot.command(name='start_quiz')
async def start_quiz(ctx, chapter_name: str = None, difficulty: str = "mix", questions: int = 10):
    """Start a new quiz session"""
    if not chapter_name:
        embed = discord.Embed(
            title="Available Chapters",
            description="Use `!start_quiz <chapter_name>` to begin a quiz",
            color=discord.Color.blue()
        )

        chapters = await bot.db.get_chapters()
        if chapters:
            chapter_list = "\n".join([f"• {chapter['name']}" for chapter in chapters])
            embed.add_field(name="Chapters", value=chapter_list, inline=False)
        else:
            embed.add_field(name="No Chapters", value="No chapters available yet!", inline=False)

        await ctx.send(embed=embed)
        return

    # Add user to database if not exists
    await bot.db.add_user(ctx.author.id, str(ctx.author))

    # Find chapter
    chapters = await bot.db.get_chapters()
    chapter = next((ch for ch in chapters if ch['name'].lower() == chapter_name.lower()), None)

    if not chapter:
        await ctx.send(f"Chapter '{chapter_name}' not found. Use `!start_quiz` to see available chapters.")
        return

    # Validate difficulty
    if difficulty not in ['1', '2', '3', 'mix']:
        await ctx.send("Difficulty must be 1 (easy), 2 (medium), 3 (hard), or 'mix'")
        return

    # Validate question count
    if questions < 1 or questions > 50:
        await ctx.send("Number of questions must be between 1 and 50")
        return

    # Start quiz session
    session_id = await bot.quiz_system.start_quiz(
        ctx.author.id, chapter['chapter_id'], difficulty, questions
    )

    # Get first question
    question = await bot.quiz_system.get_next_question(session_id)
    if not question:
        await ctx.send("No questions available for this chapter!")
        return

    # Create quiz embed
    embed = discord.Embed(
        title=f"Quiz: {chapter['name']}",
        description=question['question_text'],
        color=discord.Color.green()
    )

    embed.add_field(name="A", value=question['option_a'], inline=False)
    embed.add_field(name="B", value=question['option_b'], inline=False)
    embed.add_field(name="C", value=question['option_c'], inline=False)
    embed.add_field(name="D", value=question['option_d'], inline=False)

    embed.set_footer(
        text=f"Question {question['question_number']}/{question['total_questions']} | "
             f"Difficulty: {question['current_difficulty']} | React with 🇦, 🇧, 🇨, or 🇩"
    )

    message = await ctx.send(embed=embed)

    # Add reaction options
    reactions = ['🇦', '🇧', '🇨', '🇩']
    for reaction in reactions:
        await message.add_reaction(reaction)

    # Store message info for reaction handling
    bot.active_quiz_messages[message.id] = {
        'session_id': session_id,
        'question_id': question['question_id'],
        'user_id': ctx.author.id,
        'start_time': datetime.now()
    }


@bot.event
async def on_reaction_add(reaction, user):
    """Handle quiz answers via reactions"""
    try:
        if user.bot or reaction.message.id not in bot.active_quiz_messages:
            return

        quiz_info = bot.active_quiz_messages[reaction.message.id]

        # Check if this is the right user
        if user.id != quiz_info['user_id']:
            try:
                await reaction.remove(user)
            except:
                pass  # Ignore if we can't remove reaction
            return

        # Map reaction to answer
        reaction_map = {'🇦': 'A', '🇧': 'B', '🇨': 'C', '🇩': 'D'}
        if str(reaction.emoji) not in reaction_map:
            return

        user_answer = reaction_map[str(reaction.emoji)]
        response_time = (datetime.now() - quiz_info['start_time']).total_seconds()

        # Submit answer
        result = await bot.quiz_system.submit_answer(
            quiz_info['session_id'],
            quiz_info['question_id'],
            user_answer,
            response_time
        )

        # Check for errors in result
        if 'error' in result:
            await reaction.message.channel.send(f"❌ Error: {result['error']}")
            if reaction.message.id in bot.active_quiz_messages:
                del bot.active_quiz_messages[reaction.message.id]
            return

        # Remove the quiz message from active tracking (we have quiz_info stored locally)
        if reaction.message.id in bot.active_quiz_messages:
            del bot.active_quiz_messages[reaction.message.id]

        # Create result embed
        if result['is_correct']:
            embed = discord.Embed(
                title="✅ Correct!",
                description=f"You earned {result['points_earned']} points!",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="❌ Incorrect",
                description=f"The correct answer was {result['correct_answer']}",
                color=discord.Color.red()
            )

        embed.add_field(
            name="Score",
            value=f"{result['current_score']} points",
            inline=True
        )
        embed.add_field(
            name="Streak",
            value=f"{result['streak']} correct in a row",
            inline=True
        )

        if result.get('explanation'):
            embed.add_field(name="Explanation", value=result['explanation'], inline=False)

        await reaction.message.edit(embed=embed)
        await reaction.message.clear_reactions()

        # Check if quiz is complete
        if result.get('quiz_complete'):
            stats = result['final_stats']

            final_embed = discord.Embed(
                title="🏆 Quiz Complete!",
                description=f"Great job, {user.mention}!",
                color=discord.Color.gold()
            )

            final_embed.add_field(
                name="Final Score",
                value=f"{stats['final_score']} points",
                inline=True
            )
            final_embed.add_field(
                name="Accuracy",
                value=f"{stats['accuracy']}%",
                inline=True
            )
            final_embed.add_field(
                name="Average Time",
                value=f"{stats['avg_response_time']}s",
                inline=True
            )

            if stats['time_bonus'] > 0:
                final_embed.add_field(
                    name="Time Bonus",
                    value=f"+{stats['time_bonus']} points",
                    inline=True
                )

            # Update user rank
            new_rank = await bot.ranking.calculate_user_rank(user.id)
            rank_info = await bot.ranking.get_rank_info(user.id)

            final_embed.add_field(
                name="Current Rank",
                value=new_rank,
                inline=True
            )

            await reaction.message.channel.send(embed=final_embed)

        else:
            # Get next question
            await asyncio.sleep(2)  # Brief pause

            question = await bot.quiz_system.get_next_question(quiz_info['session_id'])
            if question:
                # Create next question embed
                embed = discord.Embed(
                    title="Next Question",
                    description=question['question_text'],
                    color=discord.Color.blue()
                )

                embed.add_field(name="A", value=question['option_a'], inline=False)
                embed.add_field(name="B", value=question['option_b'], inline=False)
                embed.add_field(name="C", value=question['option_c'], inline=False)
                embed.add_field(name="D", value=question['option_d'], inline=False)

                embed.set_footer(
                    text=f"Question {question['question_number']}/{question['total_questions']} | "
                         f"Difficulty: {question['current_difficulty']} | Current Score: {result['current_score']}"
                )

                message = await reaction.message.channel.send(embed=embed)

                # Add reactions
                reactions = ['🇦', '🇧', '🇨', '🇩']
                for r in reactions:
                    await message.add_reaction(r)

                # Update tracking
                bot.active_quiz_messages[message.id] = {
                    'session_id': quiz_info['session_id'],
                    'question_id': question['question_id'],
                    'user_id': user.id,
                    'start_time': datetime.now()
                }

    except Exception as e:
        print(f"Error in on_reaction_add: {e}")
        import traceback
        traceback.print_exception(type(e), e, e.__traceback__)
        # Try to clean up if possible
        try:
            if reaction.message.id in bot.active_quiz_messages:
                del bot.active_quiz_messages[reaction.message.id]
        except:
            pass


# Leaderboard Commands
@bot.command(name='leaderboard')
async def leaderboard(ctx, timeframe: str = 'all_time'):
    """Show leaderboard (daily, monthly, all_time)"""
    valid_timeframes = ['daily', 'monthly', 'all_time']
    if timeframe not in valid_timeframes:
        await ctx.send(f"Invalid timeframe. Use: {', '.join(valid_timeframes)}")
        return

    leaderboard_data = await bot.db.get_leaderboard(timeframe, 10)

    if not leaderboard_data:
        await ctx.send("No leaderboard data available yet!")
        return

    embed = discord.Embed(
        title=f"🏆 {timeframe.replace('_', ' ').title()} Leaderboard",
        color=discord.Color.gold()
    )

    leaderboard_text = ""
    for i, entry in enumerate(leaderboard_data, 1):
        medal = ["🥇", "🥈", "🥉"][i - 1] if i <= 3 else f"{i}."
        leaderboard_text += f"{medal} **{entry['username']}** - {entry['points']} points"

        if 'accuracy' in entry:
            leaderboard_text += f" ({entry['accuracy']}% accuracy)"

        leaderboard_text += "\n"

    embed.description = leaderboard_text
    await ctx.send(embed=embed)


@bot.command(name='stats')
async def user_stats(ctx, member: discord.Member = None):
    """Show user statistics"""
    target = member or ctx.author
    await bot.db.add_user(target.id, str(target))

    stats = await bot.db.get_user_stats(target.id)
    if not stats:
        await ctx.send("No statistics available!")
        return

    rank_info = await bot.ranking.get_rank_info(target.id)

    embed = discord.Embed(
        title=f"📊 Statistics for {target.display_name}",
        color=discord.Color.blue()
    )

    embed.add_field(
        name="Total Points",
        value=str(stats['total_points']),
        inline=True
    )

    accuracy = (stats['correct_answers'] / stats['total_questions'] * 100) if stats['total_questions'] > 0 else 0
    embed.add_field(
        name="Accuracy",
        value=f"{accuracy:.2f}%",
        inline=True
    )

    embed.add_field(
        name="Questions Answered",
        value=str(stats['total_questions']),
        inline=True
    )

    embed.add_field(
        name="Current Rank",
        value=stats['current_rank'],
        inline=True
    )

    avg_time = stats.get('average_response_time')
    if avg_time is None:
        avg_time_str = "N/A"
    else:
        avg_time_str = f"{avg_time:.2f}s"
    embed.add_field(
        name="Avg Response Time",
        value=avg_time_str,
        inline=True
    )

    if rank_info.get('next_rank'):
        embed.add_field(
            name="Next Rank",
            value=f"{rank_info['next_rank']} ({rank_info['points_to_next_rank']} points needed)",
            inline=True
        )

    await ctx.send(embed=embed)


@bot.command(name='swot')
async def swot_analysis(ctx, member: discord.Member = None):
    """Generate SWOT analysis for user"""
    target = member or ctx.author
    await bot.db.add_user(target.id, str(target))

    # Generate SWOT analysis image
    img_buffer = await bot.analytics.generate_swot_analysis(target.id)

    file = discord.File(img_buffer, filename=f"swot_analysis_{target.id}.png")

    embed = discord.Embed(
        title=f"📈 SWOT Analysis for {target.display_name}",
        description="Your personalized performance analysis",
        color=discord.Color.purple()
    )
    embed.set_image(url=f"attachment://swot_analysis_{target.id}.png")

    await ctx.send(embed=embed, file=file)


# Admin Commands
@bot.command(name='admin')
async def admin_panel(ctx):
    """Open admin terminal (creators and admins only)"""
    if not await bot.is_admin(ctx.author):
        await ctx.send("❌ You don't have permission to use admin commands!")
        return

    embed = discord.Embed(
        title="🛠️ Admin Panel",
        description="Available admin commands:",
        color=discord.Color.orange()
    )

    commands_list = [
        "**!add_chapter** `<name>` `<description>` - Create new chapter",
        "**!add_question** `<chapter>` - Interactive question creation",
        "**!import** `<chapter>` - Import questions (CSV/JSON with file upload)",
        "**!import_csv** `<chapter>` - Import questions from CSV",
        "**!import_json** `<chapter>` - Import questions from JSON",
        "**!system_stats** - View system statistics",
        "**!user_report** `<@user>` - Detailed user report",
        "**!export_chapter** `<chapter>` - Export chapter data",
        "**!delete_chapter** `<chapter>` - Delete chapter (creator only)"
    ]

    embed.add_field(
        name="Commands",
        value="\n".join(commands_list),
        inline=False
    )

    await ctx.send(embed=embed)


@bot.command(name='add_chapter')
async def add_chapter(ctx, name: str, *, description: str):
    """Add a new chapter (admins only)"""
    if not await bot.is_admin(ctx.author):
        await ctx.send("❌ You don't have permission to use this command!")
        return

    try:
        chapter_id = await bot.db.add_chapter(name, description, ctx.author.id)

        embed = discord.Embed(
            title="✅ Chapter Created",
            description=f"Chapter '{name}' has been created successfully!",
            color=discord.Color.green()
        )
        embed.add_field(name="ID", value=str(chapter_id), inline=True)
        embed.add_field(name="Description", value=description, inline=False)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Error creating chapter: {str(e)}")


@bot.command(name='import_csv')
async def import_csv(ctx, chapter_name: str):
    """Import questions from CSV file (admins only)"""
    if not await bot.is_admin(ctx.author):
        await ctx.send("❌ You don't have permission to use this command!")
        return

    # Find chapter
    chapters = await bot.db.get_chapters()
    chapter = next((ch for ch in chapters if ch['name'].lower() == chapter_name.lower()), None)

    if not chapter:
        await ctx.send(f"Chapter '{chapter_name}' not found!")
        return

    embed = discord.Embed(
        title="📁 CSV Import Instructions",
        description="Please upload a CSV file with the following format:",
        color=discord.Color.blue()
    )

    csv_format = """```
question_text,option_a,option_b,option_c,option_d,correct_option,difficulty,explanation
"What is 2+2?","3","4","5","6","B","1","Basic arithmetic"
"Capital of France?","London","Paris","Berlin","Madrid","B","2","Geography question"
```"""

    embed.add_field(name="Required Format", value=csv_format, inline=False)
    embed.add_field(
        name="Notes",
        value="• correct_option: A, B, C, or D\n• difficulty: 1 (easy), 2 (medium), 3 (hard)\n• explanation is optional",
        inline=False
    )

    await ctx.send(embed=embed)

    # Wait for file upload
    def check(message):
        return (message.author == ctx.author and
                message.channel == ctx.channel and
                message.attachments)

    try:
        msg = await bot.wait_for('message', timeout=300.0, check=check)  # 5 minutes timeout

        if msg.attachments:
            attachment = msg.attachments[0]
            if attachment.filename.endswith('.csv'):
                content = await attachment.read()
                csv_content = content.decode('utf-8')

                # Import questions
                result = await bot.admin_system.import_questions_from_csv(csv_content, chapter['chapter_id'])

                if result['success']:
                    embed = discord.Embed(
                        title="✅ CSV Import Complete",
                        description=f"Successfully imported {result['imported_count']} questions!",
                        color=discord.Color.green()
                    )

                    if result['errors']:
                        error_text = '\n'.join(result['errors'][:5])  # Show first 5 errors
                        if len(result['errors']) > 5:
                            error_text += f"\n... and {len(result['errors']) - 5} more errors"
                        embed.add_field(name="Errors", value=f"```{error_text}```", inline=False)

                else:
                    embed = discord.Embed(
                        title="❌ Import Failed",
                        description=result['error'],
                        color=discord.Color.red()
                    )

                await ctx.send(embed=embed)
            else:
                await ctx.send("❌ Please upload a .csv file!")

    except asyncio.TimeoutError:
        await ctx.send("❌ File upload timed out!")


@bot.command(name='system_stats')
async def system_stats(ctx):
    """Show system statistics (admins only)"""
    if not await bot.is_admin(ctx.author):
        await ctx.send("❌ You don't have permission to use this command!")
        return

    stats = await bot.admin_system.get_system_stats()

    embed = discord.Embed(
        title="📊 System Statistics",
        color=discord.Color.blue()
    )

    embed.add_field(name="Total Users", value=str(stats['total_users']), inline=True)
    embed.add_field(name="Total Chapters", value=str(stats['total_chapters']), inline=True)
    embed.add_field(name="Total Questions", value=str(stats['total_questions']), inline=True)

    embed.add_field(name="Total Attempts", value=str(stats['total_attempts']), inline=True)
    embed.add_field(name="Attempts (24h)", value=str(stats['attempts_last_24h']), inline=True)
    embed.add_field(name="Active Users (7d)", value=str(stats['active_users_week']), inline=True)

    if stats['questions_by_difficulty']:
        difficulty_text = "\n".join([
            f"Level {diff}: {count} questions"
            for diff, count in stats['questions_by_difficulty'].items()
        ])
        embed.add_field(name="Questions by Difficulty", value=difficulty_text, inline=False)

    await ctx.send(embed=embed)


@bot.command(name='help')
async def help_command(ctx):
    """Show help information"""
    embed = discord.Embed(
        title="🤖 Quiz Bot Help",
        description="Your intelligent quiz companion!",
        color=discord.Color.blue()
    )

    user_commands = [
        "**!start_quiz** `[chapter] [difficulty] [questions]` - Start a quiz",
        "**!leaderboard** `[timeframe]` - View leaderboards",
        "**!stats** `[@user]` - View user statistics",
        "**!swot** `[@user]` - Generate SWOT analysis",
        "**!help** - Show this help message"
    ]

    embed.add_field(name="📝 Quiz Commands", value="\n".join(user_commands), inline=False)

    if await bot.is_admin(ctx.author):
        admin_commands = [
            "**!admin** - Open admin panel",
            "**!add_chapter** `<name> <description>` - Create chapter",
            "**!import** `<chapter>` - Import questions with file upload",
            "**!import_csv** `<chapter>` - Import from CSV",
            "**!import_json** `<chapter>` - Import from JSON",
            "**!system_stats** - System statistics"
        ]
        embed.add_field(name="🛠️ Admin Commands", value="\n".join(admin_commands), inline=False)

    embed.add_field(
        name="💡 Tips",
        value="• Use reactions to answer quiz questions\n• Mix difficulty adjusts automatically\n• Complete quizzes to rank up!",
        inline=False
    )

    await ctx.send(embed=embed)

webserver.keep_alive()
if __name__ == "__main__":

    bot.run(config.DISCORD_TOKEN)





