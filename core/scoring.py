"""Подсчёт ранга сыщика (формула, без LLM — дёшево и предсказуемо)."""

# (порог очков, имя ранга) — от высшего к низшему
_RANKS = [
    (88, "🎩 Шерлок Холмс"),
    (70, "🥸 Эркюль Пуаро"),
    (50, "🚬 Комиссар Мегрэ"),
    (30, "🔰 Инспектор Лестрейд"),
    (0, "📎 Стажёр"),
]


def compute(correct: bool, quality: int, moves_left: int, hints_used: int) -> tuple[int, str]:
    """Возвращает (очки 0..100, имя ранга)."""
    if not correct:
        return 0, "❌ Дело провалено"

    score = 45                       # база за верное обвинение
    score += quality * 0.35          # качество обоснования (0..100 -> 0..35)
    score += min(moves_left, 8) * 2.5  # бонус за эффективность (до +20)
    score -= hints_used * 12         # штраф за подсказки
    score = max(1, min(100, round(score)))

    rank = next(name for threshold, name in _RANKS if score >= threshold)
    return score, rank
