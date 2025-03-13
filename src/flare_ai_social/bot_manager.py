import asyncio
import contextlib
import threading
import os
import time
from typing import Any

import google.generativeai as genai
import structlog
from anyio import Event
from google.api_core.exceptions import InvalidArgument, NotFound

from flare_ai_social.ai.base import BaseAIProvider
from flare_ai_social.ai.gemini import GeminiProvider
from flare_ai_social.ai.openai import OpenAIProvider
from flare_ai_social.ai.openrouter import OpenRouterProvider
from flare_ai_social.prompts.templates import FEW_SHOT_PROMPT, FEW_SHOT_LANA_PROMPT
from flare_ai_social.settings import settings
from flare_ai_social.telegram.service import TelegramBot
from flare_ai_social.twitter.service import TwitterBot, TwitterConfig

logger = structlog.get_logger(__name__)

# Error messages
ERR_AI_PROVIDER_NOT_INITIALIZED = "AI provider must be initialized"


class BotManager:
    """Manager class for handling multiple social media bots."""

    def __init__(self) -> None:
        """Initialize the BotManager."""
        self.ai_provider: BaseAIProvider | None = None
        self.telegram_bot: TelegramBot | None = None
        self.twitter_thread: threading.Thread | None = None
        self.active_bots: list[str] = []
        self.running = False
        self._telegram_polling_task: asyncio.Task | None = None

    def initialize_ai_provider(self) -> None:
        """Initialize the AI provider with either tuned model or default model."""
        # NOTE(chris): We use the openrouter provider
        genai.configure(api_key=settings.gemini_api_key)
        tuned_model_id = settings.tuned_model_name

        try:
            if settings.openai_api_key:
                logger.info("Using Gemini 2.0 Pro model")
                self.ai_provider = OpenAIProvider(
                    api_key=settings.openai_api_key,
                    model_name="gpt-4o",
                    system_instruction=FEW_SHOT_LANA_PROMPT,
                )
            else:
                self.ai_provider = GeminiProvider(
                    settings.gemini_api_key,
                    model_name=f"gemini-2.0-pro-exp-02-05",
                    system_instruction=FEW_SHOT_LANA_PROMPT,
                )
        except Exception:
            logger.exception("Error accessing tuned models")
            self._initialize_default_model()

    def _initialize_default_model(self) -> None:
        """Initialize the default model."""
        # Choose which provider to use based on available API keys
        if settings.openai_api_key:
            logger.info("Using model: Gemini-2.0-Pro")
            self.ai_provider = OpenAIProvider(
                api_key=settings.openai_api_key,
                model_name="gpt-4o",
                system_instruction=FEW_SHOT_LANA_PROMPT,
            )
        elif settings.openrouter_api_key:
            logger.info("Using OpenRouter model")
            self.ai_provider = OpenRouterProvider(
                settings.openrouter_api_key,
                model_name="openai/gpt-4o-2024-11-20",
                system_instruction=FEW_SHOT_LANA_PROMPT,
            )
        else:
            logger.info("Using default Gemini Flash model with few-shot prompting")
            self.ai_provider = GeminiProvider(
                settings.gemini_api_key,
                model_name="gemini-1.5-flash",
                system_instruction=FEW_SHOT_LANA_PROMPT,
            )

    def _check_ai_provider_initialized(self) -> BaseAIProvider:
        """Check if AI provider is initialized and raise error if not."""
        if self.ai_provider is None:
            raise RuntimeError(ERR_AI_PROVIDER_NOT_INITIALIZED)
        return self.ai_provider

    def _prompt_for_startup_tweet(self) -> str | None:
        """
        Prompt the user for a topic to generate a startup tweet about.
        
        Returns:
            The user-provided topic or None if the user declines
        """
        print("\n=== Startup Tweet Generation ===")
        print("Would you like to post a tweet when starting the bot? (y/n)")
        response = input().strip().lower()
        
        if response != "y" and response != "yes":
            print("Startup tweet declined.")
            return None
            
        print("\nWhat topic would you like the tweet to be about?")
        print("Examples: Flare Network updates, blockchain technology, DeFi innovations, etc.")
        topic = input().strip()
        
        if not topic:
            print("No topic provided. Skipping startup tweet.")
            return None
            
        print(f"\nGenerating and posting a tweet about: {topic}")
        return topic

    async def _post_startup_tweet(self, twitter_bot: TwitterBot, topic: str) -> None:
        """
        Generate and post a startup tweet.
        
        Args:
            twitter_bot: The TwitterBot instance
            topic: The topic to tweet about
        """
        tweet_id = await twitter_bot.generate_startup_tweet(topic)
        if tweet_id:
            logger.info(f"Startup tweet posted successfully with ID: {tweet_id}")
        else:
            logger.warning("Failed to post startup tweet")

    def start_twitter_bot(self) -> bool:
        """Initialize and start the Twitter bot in a separate thread."""
        if not settings.enable_twitter:
            logger.info("Twitter bot disabled in settings")
            return False

        if not all(
            [
                settings.x_api_key,
                settings.x_api_key_secret,
                settings.x_access_token,
                settings.x_access_token_secret,
            ]
        ):
            logger.error(
                "Twitter bot not started: Missing required credentials. "
                "Please configure Twitter API credentials in settings."
            )
            return False

        try:
            ai_provider = self._check_ai_provider_initialized()

            config = TwitterConfig(
                bearer_token=settings.x_bearer_token,
                api_key=settings.x_api_key,
                api_secret=settings.x_api_key_secret,
                access_token=settings.x_access_token,
                access_secret=settings.x_access_token_secret,
                rapidapi_key=settings.rapidapi_key or "",
                rapidapi_host=settings.rapidapi_host,
                accounts_to_monitor=settings.accounts_to_monitor,
                polling_interval=settings.twitter_polling_interval,
            )

            twitter_bot = TwitterBot(
                ai_provider=ai_provider,
                config=config,
            )
            
            # Ask user if they want to post a startup tweet
            if settings.tweet_generation_on_startup:
                startup_tweet_topic = self._prompt_for_startup_tweet()
                if startup_tweet_topic:
                    # Create a new thread to run the async startup tweet function
                    # This avoids the "asyncio.run() cannot be called from a running event loop" error
                    def post_startup_tweet_thread():
                        try:
                            # Use a fresh event loop in this thread
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self._post_startup_tweet(twitter_bot, startup_tweet_topic))
                            loop.close()
                        except Exception as e:
                            logger.exception(f"Error posting startup tweet: {str(e)}")
                    
                    # Run the async startup tweet posting in a separate thread
                    startup_tweet_thread = threading.Thread(
                        target=post_startup_tweet_thread,
                        daemon=True,
                        name="StartupTweetThread"
                    )
                    startup_tweet_thread.start()
                    startup_tweet_thread.join()  # Wait for the tweet to be posted before continuing

            self.twitter_thread = threading.Thread(
                target=twitter_bot.start, daemon=True, name="TwitterBotThread"
            )
            self.twitter_thread.start()
            logger.info("Twitter bot started in background thread")
            self.active_bots.append("Twitter")

        except ValueError:
            logger.exception("Failed to start Twitter bot")
            return False
        except Exception:
            logger.exception("Unexpected error starting Twitter bot")
            return False
        else:
            return True

    async def start_telegram_bot(self) -> bool:
        """Initialize and start the Telegram bot."""
        if not settings.enable_telegram:
            logger.info("Telegram bot disabled in settings")
            return False

        if not settings.telegram_api_token:
            logger.warning("Telegram bot not started: Missing API token")
            return False

        try:
            allowed_users = self._parse_allowed_users()
            ai_provider = self._check_ai_provider_initialized()

            self.telegram_bot = TelegramBot(
                ai_provider=ai_provider,
                api_token=settings.telegram_api_token,
                allowed_user_ids=allowed_users,
                polling_interval=settings.telegram_polling_interval,
            )

            await self.telegram_bot.initialize()
            self._telegram_polling_task = asyncio.create_task(
                self.telegram_bot.start_polling()
            )
            self.active_bots.append("Telegram")

        except Exception:
            logger.exception("Failed to start Telegram bot")
            if self.telegram_bot:
                await self.telegram_bot.shutdown()
            return False
        else:
            return True

    def _parse_allowed_users(self) -> list[int]:
        """Parse the allowed users from settings."""
        allowed_users: list[int] = []
        if settings.telegram_allowed_users:
            try:
                allowed_users = [
                    int(user_id.strip())
                    for user_id in settings.telegram_allowed_users.split(",")
                    if user_id.strip().isdigit()
                ]
            except ValueError:
                logger.warning("Error parsing telegram_allowed_users")
        return allowed_users

    async def _check_telegram_status(self) -> None:
        """Check and handle Telegram bot status."""
        if not (
            self.telegram_bot
            and self.telegram_bot.application
            and self.telegram_bot.application.updater
            and self.telegram_bot.application.updater.running
        ):
            logger.error("Telegram bot stopped responding")
            try:
                # Store telegram_bot in a local variable to help type checker
                telegram_bot = self.telegram_bot
                if telegram_bot is not None:  # Add explicit None check
                    await telegram_bot.shutdown()
                if await self.start_telegram_bot():
                    logger.info("Telegram bot restarted successfully")
                else:
                    logger.error("Failed to restart Telegram bot")
                    self.active_bots.remove("Telegram")
            except Exception:
                logger.exception("Error restarting Telegram bot")
                self.active_bots.remove("Telegram")

    def _check_twitter_status(self) -> None:
        """Check and handle Twitter bot status."""
        if self.twitter_thread and not self.twitter_thread.is_alive():
            logger.error("Twitter bot thread terminated unexpectedly")
            self.active_bots.remove("Twitter")
            if self.start_twitter_bot():
                logger.info("Twitter bot restarted successfully")

    async def monitor_bots(self) -> None:
        """Monitor active bots and handle unexpected terminations."""
        self.running = True

        try:
            while self.running and self.active_bots:
                if "Telegram" in self.active_bots and self.telegram_bot:
                    await self._check_telegram_status()

                if "Twitter" in self.active_bots:
                    self._check_twitter_status()

                if not self.active_bots:
                    logger.error("No active bots remaining")
                    break

                await asyncio.sleep(5)

        except Exception:
            logger.exception("Error in bot monitoring loop")
        finally:
            self.running = False

    async def shutdown(self) -> None:
        """Gracefully shutdown all active bots."""
        self.running = False

        if self.telegram_bot:
            try:
                logger.info("Shutting down Telegram bot")
                await self.telegram_bot.shutdown()
            except Exception:
                logger.exception("Error shutting down Telegram bot")

        if "Twitter" in self.active_bots:
            logger.info("Twitter bot daemon thread will terminate with main process")

        logger.info("All bots shutdown completed")


async def async_start() -> None:
    """Initialize and start all components of the application asynchronously."""
    bot_manager = BotManager()

    try:
        bot_manager.initialize_ai_provider()
        if not bot_manager.ai_provider:
            logger.error("Failed to initialize AI provider")
            return

        bot_manager.start_twitter_bot()
        await bot_manager.start_telegram_bot()

        if bot_manager.active_bots:
            logger.info("Active bots: %s", ", ".join(bot_manager.active_bots))
            monitor_task = asyncio.create_task(bot_manager.monitor_bots())

            try:
                await Event().wait()
            except asyncio.CancelledError:
                logger.info("Main task cancelled")
            finally:
                monitor_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await monitor_task
                await bot_manager.shutdown()
        else:
            logger.info(
                "No bots active. Configure Twitter and/or Telegram credentials "
                "and enable them in settings to activate social monitoring."
            )
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
        await bot_manager.shutdown()
    except Exception:
        logger.exception("Fatal error in async_start")
        await bot_manager.shutdown()


def start_bot_manager() -> None:
    """Initialize and start all components of the application."""
    try:
        asyncio.run(async_start())
    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception:
        logger.exception("Fatal error in start")
