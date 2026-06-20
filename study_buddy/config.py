"""Configuration loader for AI Study Buddy.

Loads configuration from environment variables and .env files.
"""

import os
from pathlib import Path

from dotenv import load_dotenv


def _find_env_file() -> str:
    """Search for a .env file in the current directory or parent directories."""
    current = Path.cwd()
    for _ in range(3):  # Search up to 3 levels up
        env_path = current / ".env"
        if env_path.exists():
            return str(env_path)
        parent = current.parent
        if parent == current:
            break
        current = parent
    return ""


class Config:
    """Application configuration loaded from environment variables / .env file.

    Attributes:
        deepseek_api_key: API key for DeepSeek or OpenAI-compatible service.
        deepseek_base_url: Base URL for the API endpoint.
        model_name: The model identifier to use for API calls.
        wechat_bot_token: Token for WeChat bot integration.
        database_path: Path to the SQLite database file.
    """

    def __init__(self) -> None:
        env_file = _find_env_file()
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()  # Try loading from CWD

        self.deepseek_api_key: str = os.getenv(
            "DEEPSEEK_API_KEY", ""
        )
        self.deepseek_base_url: str = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
        self.model_name: str = os.getenv(
            "MODEL_NAME", "deepseek-chat"
        )
        self.wechat_bot_token: str = os.getenv(
            "WECHAT_BOT_TOKEN", ""
        )
        self.database_path: str = os.getenv(
            "DATABASE_PATH", str(Path.cwd() / "study_buddy.db")
        )

    @property
    def is_ready(self) -> bool:
        """Check if the minimum required configuration is present."""
        return bool(self.deepseek_api_key)


# Global singleton
config = Config()
