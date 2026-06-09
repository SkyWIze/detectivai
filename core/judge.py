"""Финал: судья обвинения + театральная развязка (вызов E из КОНЦЕПТ.md)."""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)


async def judge_accusation(case: dict, accused_id: str, justification: str) -> dict:
    """Оценивает обвинение.

    Возвращает {correct: bool, quality: int(0..100), reveal: str}.
    reveal — театральное разоблачение для показа игроку.
    """
    correct = accused_id == case["murderer_id"]

    if not config.llm_enabled:
        truth = next(s for s in case["suspects"] if s["id"] == case["murderer_id"])
        reveal = (f"Убийца — {truth['name']}. Мотив: {case['motive']}. Орудие: {case['weapon']}.\n"
                  f"Логика: {case['solution_chain']}")
        return {"correct": correct, "quality": 60 if correct else 0, "reveal": reveal}

    result = await llm.ask_json(
        system=load("judge"),
        user=(f"Дело: {case}\n"
              f"Игрок обвиняет: {accused_id}. Настоящий убийца: {case['murderer_id']}.\n"
              f"Обоснование игрока: «{justification}»\n"
              f"Оцени качество обоснования (0..100) и напиши театральное разоблачение."),
        temperature=0.7,
    )
    result["correct"] = correct
    result.setdefault("quality", 50 if correct else 0)
    result.setdefault("reveal", case["solution_chain"])
    return result
