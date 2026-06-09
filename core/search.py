"""Осмотр локаций (вызов D из КОНЦЕПТ.md).

Игрок пишет свободным текстом, что осматривает. Сопоставляем с searchables локации:
попал в clue -> выдаём улику, иначе -> атмосферная пустышка.
"""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)


def _find_location(case: dict, location_id: str) -> dict:
    return next(loc for loc in case["locations"] if loc["id"] == location_id)


def _clue_by_id(case: dict, clue_id: str) -> dict | None:
    return next((c for c in case["clues"] if c["id"] == clue_id), None)


def _format_found_clue(clue: dict) -> str:
    text = clue["text"].strip()
    low = text.lower()
    if low.startswith("ты находишь"):
        text = text.split(":", 1)[1].strip() if ":" in text else text

    lines = [f"🔎 Ты находишь: {text}"]
    read_text = clue.get("read_text")
    if read_text:
        lines.append("\n📄 <b>Можно прочитать:</b>")
        lines.append(f"<blockquote>{read_text}</blockquote>")
    return "\n".join(lines)


async def search(case: dict, state: dict, location_id: str, query: str) -> tuple[str, str | None]:
    """Возвращает (текст ответа игроку, id найденной улики | None)."""
    location = _find_location(case, location_id)

    # Сопоставление запроса с осматриваемыми объектами.
    # Базово — через LLM (понимает синонимы). Без ключа — простое вхождение по словам.
    matched: dict | None = None
    if config.llm_enabled:
        try:
            res = await llm.ask_json(
                system=load("search"),
                user=f"Объекты локации: {location['searchables']}\nИгрок осматривает: «{query}»",
                temperature=0.3,
                model=config.llm_model_fast,
            )
            target = res.get("matched_desc")
            matched = next((s for s in location["searchables"] if s["desc"] == target), None)
        except Exception as e:  # noqa: BLE001
            log.exception("Ошибка осмотра: %s", e)

    if matched is None:
        q = query.lower()
        matched = next((s for s in location["searchables"] if any(w in q for w in s["desc"].lower().split())), None)

    if matched and matched.get("clue"):
        clue = _clue_by_id(case, matched["clue"])
        if clue:
            found = state.setdefault("found_clues", [])
            if clue["id"] not in found:
                found.append(clue["id"])
            return _format_found_clue(clue), clue["id"]

    return "🔎 Ты осматриваешь, но ничего важного не находишь.", None
