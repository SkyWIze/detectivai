"""Конфигурация из переменных окружения (.env)."""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    bot_token: str = os.getenv("BOT_TOKEN", "")

    # LLM (OpenAI-совместимый клиент: Groq / OpenAI / Gemini-compat)
    llm_provider: str = os.getenv("LLM_PROVIDER", "polza")
    llm_api_key: str = os.getenv("LLM_API_KEY", "")
    # тяжёлая модель — генерация дела и финальный судья (качество)
    llm_model: str = os.getenv("LLM_MODEL", "deepseek/deepseek-v4-flash")
    # лёгкая модель — частые дешёвые вызовы (допрос, осмотр, подсказки); отдельный лимит
    llm_model_fast: str = os.getenv("LLM_MODEL_FAST", "z-ai/glm-4.7-flash")
    llm_base_url: str = os.getenv("LLM_BASE_URL", "https://polza.ai/api/v1")

    # Игра
    db_path: str = os.getenv("DB_PATH", "detective.db")
    start_moves: int = int(os.getenv("START_MOVES", "12"))

    @property
    def llm_enabled(self) -> bool:
        return bool(self.llm_api_key)


config = Config()
