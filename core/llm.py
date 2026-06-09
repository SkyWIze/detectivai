"""Тонкая свапаемая обёртка над LLM (OpenAI-совместимый клиент).

Меняешь провайдера через .env (Groq / OpenAI / Gemini-compat) — код не трогаешь.
"""
import json
import logging
import re

from openai import AsyncOpenAI

from config import config

log = logging.getLogger(__name__)

_client: AsyncOpenAI | None = None

# Разрешённые символы: кириллица, базовая латиница/ASCII, типографика и пробелы.
# Всё прочее (иероглифы CJK, арабица и пр. — частый артефакт Llama) — вырезаем.
_ALLOWED = re.compile(
    r"[^Ѐ-ӿԀ-ԯ -~ «»"
    r"‐-—‘’“”…€\n\r\t]"
)


def sanitize(text: str) -> str:
    """Убирает иностранные символы/иероглифы, схлопывает двойные пробелы."""
    cleaned = _ALLOWED.sub("", text)
    return re.sub(r"[ \t]{2,}", " ", cleaned)


def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=config.llm_api_key, base_url=config.llm_base_url)
    return _client


async def ask(
    system: str,
    user: str,
    *,
    json_mode: bool = False,
    temperature: float = 0.8,
    model: str | None = None,
) -> str:
    """Один запрос к модели. Возвращает текст ответа.

    model=None -> тяжёлая модель (config.llm_model). Для частых вызовов передавай
    config.llm_model_fast.
    """
    kwargs: dict = {}
    if json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    resp = await _get_client().chat.completions.create(
        model=model or config.llm_model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=temperature,
        **kwargs,
    )
    # sanitize чистит иероглифы/чужие символы; для JSON-режима безопасно
    # (структурные символы JSON — ASCII, они в списке разрешённых).
    return sanitize((resp.choices[0].message.content or "").strip())


async def ask_json(system: str, user: str, *, temperature: float = 0.7,
                   model: str | None = None) -> dict:
    """Запрос с гарантией JSON. Возвращает распарсенный объект."""
    raw = await ask(system, user, json_mode=True, temperature=temperature, model=model)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # некоторые модели оборачивают JSON в ```json ... ```
        cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        return json.loads(cleaned)
