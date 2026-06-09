"""Интерактивный «сбор в гостиной» перед вердиктом.

Детектив обращается к собранным подозреваемым своими словами, а зал реагирует в
моменте. Реакция модулируется тем, виновен ли обвиняемый (для драматургии финала),
но настоящего убийцу сцена не называет — вердикт выносит судья (core/judge.py).
Реплики игрока копятся в state['gathering'] и идут судье как обоснование.
"""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)


def _accused(case: dict, accused_id: str) -> dict:
    return next(s for s in case["suspects"] if s["id"] == accused_id)


def _fallback(accused: dict, guilty: bool) -> str:
    if guilty:
        return (f"{accused['name']} бледнеет и отводит взгляд: «Это… это какая-то ошибка!» — "
                f"но голос предательски дрожит. По гостиной проходит напряжённый шёпот.")
    return (f"{accused['name']} вспыхивает от негодования: «Да как вы смеете! У вас нет ни единого "
            f"доказательства!» Кто-то из присутствующих недоверчиво качает головой.")


async def react(case: dict, state: dict, accused_id: str, player_speech: str) -> str:
    """Реакция зала на реплику детектива. Копит ход сцены в state['gathering']."""
    history = state.setdefault("gathering", [])
    accused = _accused(case, accused_id)
    guilty = accused_id == case["murderer_id"]

    if not config.llm_enabled:
        reaction = _fallback(accused, guilty)
        history.append({"speech": player_speech, "reaction": reaction})
        return reaction

    suspects = "; ".join(
        f"{s['name']} ({s['persona']}, алиби: {s.get('alibi', '?')})" for s in case["suspects"]
    )
    transcript = "\n".join(
        f"Детектив: {h['speech']}\nЗал: {h['reaction']}" for h in history
    ) or "(сцена только началась)"
    user = (
        f"Подозреваемые в гостиной: {suspects}.\n"
        f"Детектив указывает на: {accused['name']}.\n"
        f"Обвиняемый на самом деле {'ВИНОВЕН' if guilty else 'НЕВИНОВЕН'} "
        f"(только для твоей режиссуры реакции).\n"
        f"Ход сцены до этого:\n{transcript}\n\n"
        f"Новая реплика детектива: «{player_speech}»\n"
        f"Опиши реакцию зала на эту реплику."
    )
    try:
        reaction = await llm.ask(load("gathering"), user, temperature=0.9,
                                 model=config.llm_model_fast)
    except Exception as e:  # noqa: BLE001
        log.exception("Ошибка сцены в гостиной: %s", e)
        reaction = _fallback(accused, guilty)

    history.append({"speech": player_speech, "reaction": reaction})
    return reaction
