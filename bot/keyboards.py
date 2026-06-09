"""Клавиатуры бота."""
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
)

BTN_INTERROGATE = "👤 Допросить"
BTN_SEARCH = "🔍 Осмотреть"
BTN_EVIDENCE = "🎴 Улики"
BTN_CROSS = "🗣 Очная ставка"
BTN_NOTEBOOK = "📋 Блокнот"
BTN_HINT = "💡 Подсказка"
BTN_ACCUSE = "⚖️ Обвинить"
BTN_LEAVE = "🚪 В меню"


def _short(text: str, limit: int = 64) -> str:
    """Подпись для кнопки: схлопывает переносы/пробелы и аккуратно укорачивает с «…»."""
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def hide_kb() -> ReplyKeyboardRemove:
    return ReplyKeyboardRemove()


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔎 Новое дело", callback_data="new_case")],
        [InlineKeyboardButton(text="▶️ Продолжить", callback_data="continue")],
        [InlineKeyboardButton(text="🎓 Обучение", callback_data="tutorial")],
        [InlineKeyboardButton(text="📊 Профиль", callback_data="profile")],
    ])


def settings_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎩 Классика", callback_data="set:classic")],
        [InlineKeyboardButton(text="🌃 Нуар", callback_data="set:noir")],
        [InlineKeyboardButton(text="🤡 Абсурд", callback_data="set:absurd")],
    ])


def game_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_INTERROGATE), KeyboardButton(text=BTN_SEARCH)],
            [KeyboardButton(text=BTN_EVIDENCE), KeyboardButton(text=BTN_CROSS)],
            [KeyboardButton(text=BTN_NOTEBOOK), KeyboardButton(text=BTN_HINT)],
            [KeyboardButton(text=BTN_ACCUSE), KeyboardButton(text=BTN_LEAVE)],
        ],
        resize_keyboard=True,
    )


def suspects_kb(case: dict, prefix: str) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=s["name"], callback_data=f"{prefix}:{s['id']}")]
            for s in case["suspects"]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def locations_kb(case: dict) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(text=loc["name"], callback_data=f"loc:{loc['id']}")]
            for loc in case["locations"]]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def present_evidence_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎴 Предъявить улику", callback_data="evidence_menu")],
    ])


def clues_kb(case: dict, found_ids: list[str]) -> InlineKeyboardMarkup:
    rows = []
    for cid in found_ids:
        clue = next((c for c in case["clues"] if c["id"] == cid), None)
        if clue:
            rows.append([InlineKeyboardButton(text=f"🎴 {_short(clue['text'])}", callback_data=f"evid:{cid}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def found_clues_kb(case: dict, found_ids: list[str], *, can_present: bool) -> InlineKeyboardMarkup:
    rows = []
    for cid in found_ids:
        clue = next((c for c in case["clues"] if c["id"] == cid), None)
        if clue:
            rows.append([InlineKeyboardButton(text=f"📄 {_short(clue['text'])}", callback_data=f"clue:{cid}")])
    if can_present:
        rows.append([InlineKeyboardButton(text="🎴 Предъявить улику", callback_data="evidence_menu")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cross_suspects_kb(case: dict, available_ids: list[str]) -> InlineKeyboardMarkup:
    rows = [[InlineKeyboardButton(
        text=next(s["name"] for s in case["suspects"] if s["id"] == sid),
        callback_data=f"xref:{sid}")] for sid in available_ids]
    return InlineKeyboardMarkup(inline_keyboard=rows)


def cross_quotes_kb(statements: list[dict], cited_id: str) -> InlineKeyboardMarkup:
    rows = []
    for idx, st in enumerate(statements):
        rows.append([InlineKeyboardButton(text=f"🗣 {idx + 1}. {_short(st['a'])}",
                                          callback_data=f"xq:{cited_id}:{idx}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
