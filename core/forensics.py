"""Экспертиза улик: отправить найденную улику в лабораторию и получить углублённый вывод.

В отличие от подозреваемого, эксперт ВИДИТ истину дела (это объективный источник
фактов), поэтому отчёт может указать, чьи следы, подлинность, связь с алиби/временем
и признаки подброшенной улики. Но финальный вердикт «убийца — Х» эксперт не выносит.
"""
import logging

from core import llm
from core.prompt_loader import load
from config import config

log = logging.getLogger(__name__)


def _clue(case: dict, clue_id: str) -> dict | None:
    return next((c for c in case["clues"] if c["id"] == clue_id), None)


def _name(case: dict, suspect_id: str | None) -> str | None:
    if not suspect_id:
        return None
    return next((s["name"] for s in case["suspects"] if s["id"] == suspect_id), None)


def _fallback(case: dict, clue: dict) -> str:
    """Отчёт без LLM — собирается из метаданных улики (для демо-режима)."""
    parts = []
    implicates = _name(case, clue.get("implicates"))
    kind = clue.get("kind")
    if kind == "trace" or kind == "forensic":
        parts.append(f"Следы свежие, оставлены незадолго до смерти жертвы.")
    if implicates:
        parts.append(f"Находка указывает на причастность: {implicates}.")
    if clue.get("is_false_lead"):
        parts.append("Однако есть признаки, что улику подбросили или истолковали неверно, — доверять ей рано.")
    if clue.get("refutes"):
        parts.append("Эта улика опровергает одну из ранее напрашивавшихся версий.")
    return " ".join(parts) or "Экспертиза не дала однозначного результата по этому предмету."


async def analyze(case: dict, state: dict, clue_id: str) -> str | None:
    """Отчёт экспертизы по улике. Кэшируется в state['analysis'] (повторный показ бесплатен).

    Возвращает текст отчёта или None, если улики нет.
    """
    clue = _clue(case, clue_id)
    if not clue:
        return None

    cache = state.setdefault("analysis", {})
    if clue_id in cache:
        return cache[clue_id]

    if not config.llm_enabled:
        report = _fallback(case, clue)
        cache[clue_id] = report
        return report

    v = case["victim"]
    suspects = "; ".join(f"{s['name']} (алиби: {s.get('alibi', '?')})" for s in case["suspects"])
    facts = [
        f"Жертва: {v.get('name')} — {v.get('found')}.",
        f"Орудие: {case.get('weapon')}. Время убийства: {case.get('time')}.",
        f"Подозреваемые и их алиби: {suspects}.",
        f"Улика на анализ: «{clue['text']}» (тип: {clue.get('kind', 'предмет')}).",
    ]
    if clue.get("read_text"):
        facts.append(f"Текст документа: {clue['read_text']}")
    implicates = _name(case, clue.get("implicates"))
    if implicates:
        facts.append(f"Технически улика связана с: {implicates}.")
    if clue.get("is_false_lead"):
        facts.append("Эта улика — ложный след (подброшена/обманчива); экспертиза должна это вскрыть.")
    if clue.get("refutes"):
        refuted = [_clue(case, rid) for rid in clue["refutes"]]
        refuted_txt = "; ".join(c["text"] for c in refuted if c)
        if refuted_txt:
            facts.append(f"Эта улика опровергает версию по: {refuted_txt}.")

    try:
        report = await llm.ask(
            load("forensics"),
            "Данные дела (только для тебя, эксперт):\n" + "\n".join(facts) +
            "\n\nНапиши отчёт экспертизы по этой улике.",
            temperature=0.6,
            model=config.llm_model_fast,
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Ошибка экспертизы: %s", e)
        report = _fallback(case, clue)

    cache[clue_id] = report
    return report
