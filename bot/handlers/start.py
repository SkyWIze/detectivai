"""Старт, главное меню, профиль."""
import logging

from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import hide_kb, main_menu_kb
from bot.states import Game
from db import database

router = Router()
log = logging.getLogger(__name__)

WELCOME = (
    "🕵️ <b>Detective</b>\n\n"
    "Тебя ждёт дело об убийстве. Допрашивай подозреваемых своими словами, "
    "осматривай локации, лови их на лжи и назови убийцу.\n\n"
    "Каждое дело уникальное. Удачи, сыщик."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await database.get_or_create_user(message.from_user.id)
    await state.set_state(Game.menu)
    games_played, _ = await database.get_user_stats(message.from_user.id)
    text = WELCOME
    if games_played == 0:
        text += "\n\n🎓 Первый раз? Начни с «Обучение» — короткого дела с подсказками."
    await message.answer(text, reply_markup=hide_kb())
    await message.answer("Выбери действие:", reply_markup=main_menu_kb())


@router.callback_query(F.data == "profile")
async def show_profile(cb: CallbackQuery) -> None:
    await cb.answer()
    await cb.message.answer("📊 Профиль: статистика появится позже.", reply_markup=hide_kb())
    await cb.message.answer("Главное меню:", reply_markup=main_menu_kb())
