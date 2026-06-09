"""Напарник-компаньон: живой ИИ-спутник, реагирует на ход расследования.

Видит ТОЛЬКО то, что уже известно игроку (улики, кто допрошен, замеченные
нестыковки) — НЕ видит разгадки. Поэтому он не спойлит убийцу и не выдаёт решение,
а лишь рассуждает вслух, подмечает всплывшие нестыковки и подбадривает. Напарник
зависит от вселенной — это добавляет колорита и разнообразия.
"""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)

# (label с эмодзи, описание характера) по сеттингу.
_PARTNERS: dict[str, tuple[str, str]] = {
    "classic": ("🎩 Ватсон", "преданный, восторженный помощник в духе доктора Ватсона: "
                "восхищается дедукцией шефа, рассуждает вслух, бывает наивен"),
    "noir": ("🚬 Сэл", "усталый циничный напарник-детектив: говорит коротко и хлёстко, "
             "всё повидал, но цепкий и внимательный к деталям"),
    "absurd": ("🤹 Бубнин", "нелепый чудаковатый помощник: постоянно отвлекается и фантазирует, "
               "но иногда случайно роняет дельную мысль"),
}

# Канонические реплики для демо-режима без LLM (чтобы фича была видна и без ключа).
_FALLBACK: dict[str, str] = {
    "briefing": "Ну что, шеф, картина пока туманная. С кого начнём?",
    "clue": "Любопытная находка. Подошьём в дело — вдруг выстрелит.",
    "contradiction": "Ого, вы видели, как он дёрнулся? Тут что-то нечисто, шеф.",
    "verdict_win": "Мы сделали это, шеф! Я ни секунды в вас не сомневался!",
    "verdict_lose": "Не вышло в этот раз, шеф… Но какое было расследование!",
}


def _partner(setting: str) -> tuple[str, str]:
    return _PARTNERS.get(setting, _PARTNERS["classic"])


def _known(case: dict, state: dict) -> str:
    """Сводка того, что известно игроку (без разгадки) — контекст для напарника."""
    found_ids = set(state.get("found_clues", []))
    clues = [c["text"] for c in case["clues"] if c["id"] in found_ids] or ["пока ничего"]
    interrogated = [s["name"] for s in case["suspects"]
                    if s["id"] in state.get("interrogated", [])] or ["пока никого"]
    contradictions = [c.get("note", "") for c in state.get("noted_contradictions", [])]
    suspects = ", ".join(s["name"] for s in case["suspects"])
    return (f"Жертва: {case['victim']['name']}. Подозреваемые: {suspects}.\n"
            f"Уже допрошены: {', '.join(interrogated)}.\n"
            f"Найденные улики: {'; '.join(clues)}.\n"
            f"Замеченные нестыковки: {'; '.join(c for c in contradictions if c) or 'нет'}.")


async def comment(case: dict, state: dict, event: str, *, detail: str = "") -> str | None:
    """Короткая реплика напарника на событие.

    event: briefing | clue | contradiction.
    Возвращает готовую к показу строку «label: <i>текст</i>» или None.
    """
    label, style = _partner(case.get("setting", "classic"))

    if not config.llm_enabled:
        line = _FALLBACK.get(event)
        return f"{label}: <i>{line}</i>" if line else None

    events = {
        "briefing": "Дело только что началось — задай тон, подметь общее впечатление, подбодри шефа.",
        "clue": f"Детектив только что нашёл улику: «{detail}». Живо отреагируй на находку.",
        "contradiction": f"Подозреваемый дрогнул, когда ему предъявили улику: «{detail}». "
                         f"Отреагируй на пойманную нестыковку.",
        "verdict_win": f"Детектив верно изобличил убийцу — это {detail}. Дело раскрыто! "
                       f"Ликуй и от души поздравь шефа.",
        "verdict_lose": f"Детектив обвинил не того, настоящим убийцей оказался {detail}. "
                        f"Поддержи шефа и посочувствуй — без злорадства, тепло.",
    }
    try:
        text = await llm.ask(
            load("watson", name=label, style=style),
            f"{_known(case, state)}\n\nСобытие: {events.get(event, '')}\n"
            f"Ответь одной короткой репликой (1-2 предложения).",
            temperature=0.9,
            model=config.llm_model_fast,
        )
        return f"{label}: <i>{text}</i>"
    except Exception as e:  # noqa: BLE001
        log.exception("Ошибка реплики напарника: %s", e)
        return None
