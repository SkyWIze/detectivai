"""Осмысленная подсказка: мягкий нудж по текущему состоянию, без спойлера убийцы."""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)


async def give_hint(case: dict, state: dict) -> str:
    """Возвращает подсказку, куда копать дальше. Не раскрывает разгадку."""
    found_ids = set(state.get("found_clues", []))
    found = [c["text"] for c in case["clues"] if c["id"] in found_ids]
    missing_count = sum(1 for c in case["clues"] if c["id"] not in found_ids)
    interrogated = [s["name"] for s in case["suspects"] if s["id"] in state.get("interrogated", [])]
    not_interrogated = [s["name"] for s in case["suspects"] if s["id"] not in state.get("interrogated", [])]

    if not config.llm_enabled:
        if not_interrogated:
            return f"💡 Ты ещё не говорил с: {', '.join(not_interrogated)}. Сопоставь их алиби."
        return "💡 Сравни, кто где был в момент убийства — чьё алиби не сходится с уликами?"

    user = (
        f"Разгадка (НЕ раскрывать игроку): {case['solution_chain']}\n"
        f"Найденные улики: {found or '—'}\n"
        f"Ещё не найдено улик: {missing_count}\n"
        f"Допрошены: {', '.join(interrogated) or '—'}\n"
        f"Не допрошены: {', '.join(not_interrogated) or '—'}\n"
        f"Дай одну подсказку, куда копать дальше."
    )
    try:
        text = await llm.ask(load("hint"), user, temperature=0.6, model=config.llm_model_fast)
        return f"💡 {text}"
    except Exception as e:  # noqa: BLE001
        log.exception("Ошибка генерации подсказки: %s", e)
        return "💡 Сопоставь алиби подозреваемых с найденными уликами — кто-то лжёт."
