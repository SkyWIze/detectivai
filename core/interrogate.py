"""Отыгрыш подозреваемого (вызов C из КОНЦЕПТ.md).

Ключевая идея: в модель уходит ТОЛЬКО кусок дела этого подозреваемого + короткая
память диалога. Подозреваемый не знает, кто убийца, поэтому не может его слить.
"""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)

_MAX_MEMORY = 6  # сколько последних реплик держим в контексте

# Слова-маркеры тона игрока (для оценки давления без лишних LLM-вызовов).
_AGGRO = ("убил", "убийца", "признавайся", "сознавайся", "врёшь", "врешь", "лжёшь",
          "лжешь", "виновен", "колись", "не ври", "ты это сделал", "за решётку")
_CALM = ("пожалуйста", "спасибо", "понимаю", "не волнуйтесь", "не волнуйся",
         "извините", "простите", "спокойно", "помогите")

# Поведение по уровню давления: (порог, ярлык, эмодзи, инструкция модели).
_MOODS = [
    (30, "спокоен", "🙂", "Ты держишься спокойно и отвечаешь относительно охотно."),
    (60, "насторожен", "😐", "Ты насторожён: отвечаешь короче и уклончивее обычного."),
    (85, "на взводе", "😠", "Ты на взводе: раздражён, огрызаешься, требуешь оставить тебя в покое."),
    (101, "замкнулся", "🤐", "Ты замкнулся от давления: почти не отвечаешь, требуешь прекратить "
                            "допрос. Снова разговоришься, только если детектив сменит тон на "
                            "спокойный и вежливый."),
]


def _find(case: dict, suspect_id: str) -> dict:
    return next(s for s in case["suspects"] if s["id"] == suspect_id)


def _tone_delta(text: str) -> int:
    """Насколько реплика игрока поднимает/снижает напряжение подозреваемого."""
    low = text.lower()
    delta = 4  # сам факт допроса слегка давит
    if any(w in low for w in _AGGRO):
        delta += 22
    if "!" in text:
        delta += 8
    if any(w in low for w in _CALM):
        delta -= 22
    return delta


def _mood(pressure: int) -> tuple[str, str, str]:
    """(ярлык, эмодзи, инструкция) по уровню давления."""
    for threshold, label, emoji, instruction in _MOODS:
        if pressure < threshold:
            return label, emoji, instruction
    return _MOODS[-1][1], _MOODS[-1][2], _MOODS[-1][3]


async def respond(
    case: dict,
    state: dict,
    suspect_id: str,
    player_msg: str,
    *,
    evidence_text: str | None = None,
    evidence_breaks: bool = False,
    cross_quote: str | None = None,
) -> str:
    """Ответ подозреваемого на реплику игрока.

    evidence_text   — текст предъявленной улики (механика «давить уликой»).
    evidence_breaks — улика прямо изобличает этого подозреваемого (решает код по breaks_on).
    cross_quote     — цитата другого свидетеля (перекрёстный допрос, изюминка №1).
    """
    suspect = _find(case, suspect_id)
    history = state.get("suspect_dialogs", {}).get(suspect_id, [])[-_MAX_MEMORY:]

    # динамика напряжения: тон игрока двигает «градус» подозреваемого
    pressure = state.setdefault("suspect_pressure", {}).get(suspect_id, 0)
    pressure = max(0, min(100, pressure + _tone_delta(player_msg)))
    state["suspect_pressure"][suspect_id] = pressure
    mood_label, mood_emoji, mood_instruction = _mood(pressure)
    state.setdefault("suspect_mood", {})[suspect_id] = f"{mood_emoji} {mood_label}"

    if not config.llm_enabled:
        return f"[демо] {suspect['name']} уклончиво смотрит в сторону и молчит. (LLM не настроен)"

    system = load(
        "interrogate",
        name=suspect["name"],
        persona=suspect["persona"],
        alibi=suspect["alibi"],
        secret=suspect["secret"],
        knows=", ".join(suspect.get("knows", [])),
        lies_about=suspect["lies_about"],
        mood=mood_instruction,
    )

    parts = [f"История допроса: {history}"]
    if evidence_text:
        if evidence_breaks:
            parts.append(f"Игрок предъявляет улику против тебя: «{evidence_text}». Она ПРЯМО тебя "
                         f"изобличает — ты заметно теряешься и ЧАСТИЧНО признаёшься в своём секрете. "
                         f"Но если ты не убийца — убийство на себя НЕ бери, сознайся лишь в своём грехе.")
        else:
            parts.append(f"Игрок предъявляет улику: «{evidence_text}». Тебя напрямую она не "
                         f"изобличает — отреагируй спокойно или с лёгким раздражением, причастность отрицай.")
    if cross_quote:
        parts.append(f"Игрок ссылается на показания другого: «{cross_quote}». Отреагируй на противоречие.")
    parts.append(f"Вопрос игрока: {player_msg}")

    answer = await llm.ask(system, "\n".join(parts), temperature=0.85,
                           model=config.llm_model_fast)

    history.append({"q": player_msg, "a": answer})
    state.setdefault("suspect_dialogs", {})[suspect_id] = history
    if suspect_id not in state.setdefault("interrogated", []):
        state["interrogated"].append(suspect_id)
    return answer
