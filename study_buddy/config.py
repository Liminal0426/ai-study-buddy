"""Configuration loader for AI Study Buddy.

Loads config from .env and provides a multi-provider model registry.
"""
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv


def _find_env_file() -> str:
    current = Path.cwd()
    for _ in range(3):
        env_path = current / ".env"
        if env_path.exists():
            return str(env_path)
        parent = current.parent
        if parent == current:
            break
    return ""


# ── Provider definitions ──────────────────────────────────────────────
# Each provider: base_url, api_key env var, models with capabilities.
PROVIDERS: Dict[str, Dict[str, Any]] = {
    "deepseek": {
        "label": "DeepSeek",
        "base_url": "https://api.deepseek.com/v1",
        "api_key_var": "DEEPSEEK_API_KEY",
        "models": {
            "deepseek-chat": {"vision": True, "text": True},
            "deepseek-reasoner": {"vision": False, "text": True},
        },
        "default_model": "deepseek-chat",
    },
    "openai": {
        "label": "OpenAI",
        "base_url": "https://api.openai.com/v1",
        "api_key_var": "OPENAI_API_KEY",
        "models": {
            "gpt-4o": {"vision": True, "text": True},
            "gpt-4o-mini": {"vision": True, "text": True},
            "o1": {"vision": True, "text": True},
            "o1-mini": {"vision": False, "text": True},
        },
        "default_model": "gpt-4o",
    },
    "anthropic": {
        "label": "Anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key_var": "ANTHROPIC_API_KEY",
        "models": {
            "claude-sonnet-4-20250514": {"vision": True, "text": True},
            "claude-haiku-3-5-sonnet-20241022": {"vision": True, "text": True},
        },
        "default_model": "claude-sonnet-4-20250514",
    },
    "google": {
        "label": "Google Gemini",
        "base_url": "https://generativelanguage.googleapis.com/v1beta",
        "api_key_var": "GOOGLE_API_KEY",
        "models": {
            "gemini-2.0-flash": {"vision": True, "text": True},
            "gemini-2.0-pro-exp": {"vision": True, "text": True},
            "gemini-1.5-pro": {"vision": True, "text": True},
        },
        "default_model": "gemini-2.0-flash",
    },
    "zhipuai": {
        "label": "智谱AI (GLM)",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
        "api_key_var": "ZHIPUAI_API_KEY",
        "models": {
            "glm-5": {"vision": True, "text": True},
            "glm-4v-plus": {"vision": True, "text": False},
            "glm-4-flash": {"vision": False, "text": True},
        },
        "default_model": "glm-5",
    },
    "qwen": {
        "label": "通义千问 (Qwen)",
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "api_key_var": "QWEN_API_KEY",
        "models": {
            "qwen-vl-plus": {"vision": True, "text": True},
            "qwen-vl-max": {"vision": True, "text": True},
            "qwen-turbo": {"vision": False, "text": True},
        },
        "default_model": "qwen-vl-plus",
    },
    "moonshot": {
        "label": "Kimi (Moonshot)",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key_var": "MOONSHOT_API_KEY",
        "models": {
            "moonshot-v1-8k": {"vision": True, "text": True},
            "moonshot-v1-32k": {"vision": True, "text": True},
            "moonshot-v1-128k": {"vision": True, "text": True},
        },
        "default_model": "moonshot-v1-8k",
    },
    "mistral": {
        "label": "Mistral AI",
        "base_url": "https://api.mistral.ai/v1",
        "api_key_var": "MISTRAL_API_KEY",
        "models": {
            "mistral-large-latest": {"vision": True, "text": True},
            "mistral-small-latest": {"vision": False, "text": True},
        },
        "default_model": "mistral-large-latest",
    },
}


def _find_available_providers() -> Dict[str, Dict[str, Any]]:
    """Return only providers that have their API key set."""
    available = {}
    for name, prov in PROVIDERS.items():
        key = os.getenv(prov["api_key_var"], "").strip()
        if key:
            available[name] = {**prov, "api_key": key}
    return available


def _resolve_model(
    provider_name: str,
    model_name: Optional[str] = None,
) -> str:
    """Resolve a model name, defaulting to the provider's default."""
    prov = PROVIDERS.get(provider_name)
    if not prov:
        return ""
    if model_name and model_name in prov["models"]:
        return model_name
    return prov["default_model"]


def _resolve_vision_model(provider_name: str) -> str:
    """Resolve the first vision-capable model for a provider."""
    prov = PROVIDERS.get(provider_name)
    if not prov:
        return "gpt-4o"  # safe fallback
    for m_name, caps in prov["models"].items():
        if caps.get("vision"):
            return m_name
    return prov.get("default_model", "gpt-4o")


class Config:
    """Application configuration.

    Reads .env, registers all available providers, and lets the
    active provider be switched at runtime.
    """

    def __init__(self) -> None:
        env_file = _find_env_file()
        if env_file:
            load_dotenv(env_file)
        else:
            load_dotenv()

        # Original keys (backward compat)
        self.deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
        self.deepseek_base_url: str = os.getenv(
            "DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1"
        )
        self.model_name: str = os.getenv("MODEL_NAME", "deepseek-chat")
        self.wechat_bot_token: str = os.getenv("WECHAT_BOT_TOKEN", "")
        self.database_path: str = os.getenv(
            "DATABASE_PATH", str(Path.cwd() / "study_buddy.db")
        )

        # Active provider (user preference from env)
        self.active_provider: str = os.getenv("ACTIVE_PROVIDER", "deepseek")
        self.active_model: str = os.getenv(
            "ACTIVE_MODEL", _resolve_model(self.active_provider)
        )

        # Vision provider (separate — many text models don't support images)
        self.vision_provider: str = os.getenv("VISION_PROVIDER", "zhipuai")
        self.vision_model: str = os.getenv(
            "VISION_MODEL", _resolve_vision_model(self.vision_provider)
        )

        # Available providers
        self.available_providers: Dict[str, Dict[str, Any]] = _find_available_providers()

    @property
    def is_ready(self) -> bool:
        """At least one provider is configured."""
        return bool(self.available_providers)

    def get_vision_model(self) -> str:
        """Get the user-configured vision model."""
        return self.vision_model

    def get_vision_provider(self) -> str:
        """Get the user-configured vision provider name."""
        return self.vision_provider

    def get_provider(self) -> Optional[Dict[str, Any]]:
        """Get the currently active provider config, or first available."""
        if self.active_provider in self.available_providers:
            return self.available_providers[self.active_provider]
        # Fallback to first available
        for name, prov in self.available_providers.items():
            return prov
        return None

    def list_providers(self) -> List[Dict[str, Any]]:
        """List all available providers with their models."""
        result = []
        for name, prov in self.available_providers.items():
            result.append({
                "name": name,
                "label": prov["label"],
                "models": list(prov["models"].keys()),
                "default": prov["default_model"],
            })
        return result

    def switch_provider(self, provider_name: str, model_name: Optional[str] = None) -> str:
        """Switch active provider at runtime. Returns status message."""
        if provider_name not in self.available_providers:
            available = ", ".join(self.available_providers.keys())
            return f"❌ Provider '{provider_name}' not configured. Available: {available}"

        self.active_provider = provider_name
        if model_name:
            resolved = _resolve_model(provider_name, model_name)
            if resolved:
                self.active_model = resolved
            else:
                models = ", ".join(PROVIDERS[provider_name]["models"].keys())
                return f"❌ Unknown model '{model_name}'. Available: {models}"
        else:
            self.active_model = PROVIDERS[provider_name]["default_model"]

        prov = self.available_providers[provider_name]
        return f"✅ Switched to {prov['label']} / {self.active_model}"


# Global singleton
config = Config()
