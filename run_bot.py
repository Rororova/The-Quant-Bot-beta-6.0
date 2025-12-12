#!/usr/bin/env python3
"""
Simple script to run the Discord Quiz Bot
This handles basic error checking and restart functionality
"""

import os
import sys
import asyncio
import logging
from bot import bot
import config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def check_config():
    """Check if all required configuration is present"""
    if not config.DISCORD_TOKEN:
        logger.error("DISCORD_TOKEN not found in environment variables!")
        logger.error("Please set up your .env file with the Discord bot token.")
        return False

    if not config.GUILD_ID:
        logger.warning("GUILD_ID not set. Bot will work in all servers.")

    if not config.CREATOR_ID:
        logger.warning("CREATOR_ID not set. Some admin features may not work.")

    return True


async def main():
    """Main function to run the bot with error handling"""
    logger.info("Starting Discord Quiz Bot...")

    # Check configuration
    if not check_config():
        logger.error("Configuration check failed!")
        return

    try:
        # Start the bot
        await bot.start(config.DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Bot crashed with error: {e}")
        raise
    finally:
        if not bot.is_closed():
            await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
