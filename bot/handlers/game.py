"""Игровой цикл: новое дело, допрос, осмотр, блокнот, обвинение, финал.

Скелет: основной флоу проходим от начала до конца (на демо-деле — без LLM-ключа).
Точки для наполнения по дням помечены TODO.
"""
import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot import keyboards as kb
from bot.states import Game
from core import case_gen, hint, interrogate, judge, scoring, search, watson
from core.models import empty_state
from core.sample_case import get_sample_case
from config import config
from db import database

router = Router()
log = logging.getLogger(__name__)


# ──────────────────────────── helpers ────────────────────────────

async def _load(user_id: int) -> tuple[dict, dict] | tuple[None, None]:
    """Возвращает (case, session_row) активной игры или (None, None)."""
    sess = await database.get_session(user_id)
    if not sess or sess["status"] != "active":
        return None, None
    case = await database.get_case(sess["case_id"])
    return case, sess


async def _charge_move(user_id: int, sess: dict) -> bool:
    """Списать 1 ход за крупное действие (раунд допроса / осмотр локации).

    Возвращает False, если ходов не осталось (действие не должно состояться).
    """
    if sess["moves_left"] <= 0:
        return False
    sess["moves_left"] -= 1
    await database.save_session(user_id, sess["case_id"], "active",
                                sess["moves_left"], sess["state"])
    return True


_OUT_OF_MOVES = "⏳ Ходы кончились. Пора предъявить обвинение — жми «⚖️ Обвинить»."

_CLUE_KIND_LABELS = {
    "document": "документ",
    "trace": "след",
    "object": "предмет",
    "forensic": "экспертиза",
}


def _briefing(case: dict, moves: int) -> str:
    names = "\n".join(f"• {s['name']} — {s['persona']}" for s in case["suspects"])
    v = case["victim"]
    return (f"📁 <b>{case['title']}</b>\n\n"
            f"💀 Жертва: {v['name']} ({v['found']}).\n\n"
            f"<b>Подозреваемые:</b>\n{names}\n\n"
            f"⏳ У тебя <b>{moves}</b> ходов. Действуй кнопками снизу.")


def _location_scene(location: dict) -> str:
    """Описание локации при входе: атмосфера + что можно осмотреть."""
    objects = ", ".join(s["desc"] for s in location["searchables"])
    first = location["searchables"][0]["desc"] if location["searchables"] else "стол"
    lines = [f"🔍 <b>{location['name']}</b>"]
    if location.get("desc"):
        lines.append(location["desc"])
    lines.append(f"\nВзгляд цепляется за: <i>{objects}</i>.")
    lines.append(f"Напиши, что осмотреть внимательнее — например, «осмотреть {first}».")
    return "\n".join(lines)


def _notebook(case: dict, sess: dict) -> str:
    st = sess["state"]
    by_id = {s["id"]: s["name"] for s in case["suspects"]}
    interrogated = ", ".join(by_id.get(i, i) for i in st["interrogated"]) or "—"
    found_clues = [c for c in case["clues"] if c["id"] in st["found_clues"]]
    found_ids = {c["id"] for c in found_clues}
    clues = "\n".join(
        f"• [{_CLUE_KIND_LABELS.get(c.get('kind', 'object'), 'улика')}] {c['text']}"
        for c in found_clues
    ) or "—"
    documents = "\n".join(
        f"• {c['text']}"
        for c in found_clues if c.get("read_text")
    ) or "—"
    notes = "\n".join(
        f"• {c['notebook_note']}"
        for c in found_clues if c.get("notebook_note")
    ) or "—"
    leads = []
    for clue in found_clues:
        if clue.get("is_false_lead"):
            if any(ref in found_ids for ref in clue.get("refuted_by", [])):
                leads.append(f"Опровергнута версия: {clue['text']}")
            else:
                leads.append(f"Сомнительная версия: {clue['text']}")
        if clue.get("refutes"):
            for target_id in clue["refutes"]:
                target = next((c for c in case["clues"] if c["id"] == target_id), None)
                if target:
                    leads.append(f"Улика «{clue['text']}» ломает версию по улике «{target['text']}».")
    false_leads = "\n".join(f"• {line}" for line in leads) or "—"
    contradictions = "\n".join(f"• {c['note']}" for c in st["noted_contradictions"]) or "—"
    return (f"📋 <b>Блокнот сыщика</b>\n\n"
            f"⏳ Ходов осталось: {sess['moves_left']}\n\n"
            f"<b>Допрошены:</b> {interrogated}\n\n"
            f"<b>Улики:</b>\n{clues}\n\n"
            f"<b>Документы и тексты:</b>\n{documents}\n\n"
            f"<b>Рабочие выводы:</b>\n{notes}\n\n"
            f"<b>Версии и опровержения:</b>\n{false_leads}\n\n"
            f"<b>Противоречия:</b>\n{contradictions}\n\n"
            f"<i>Полные тексты документов смотри через «{kb.BTN_EVIDENCE}».</i>")


def _format_clue_details(case: dict, sess: dict, clue: dict) -> str:
    found_ids = set(sess["state"].get("found_clues", []))
    kind = _CLUE_KIND_LABELS.get(clue.get("kind", "object"), "улика")
    lines = [f"🎴 <b>Улика</b>\n\n<b>Тип:</b> {kind}\n{clue['text']}"]
    read_text = clue.get("read_text")
    if read_text:
        lines.append(f"\n📄 <b>Текст документа:</b>\n<blockquote>{read_text}</blockquote>")
    if clue.get("notebook_note"):
        lines.append(f"\n🧠 <b>Заметка сыщика:</b>\n{clue['notebook_note']}")
    if clue.get("is_false_lead"):
        if any(ref in found_ids for ref in clue.get("refuted_by", [])):
            lines.append("\n⚠️ <b>Статус:</b> эта версия уже опровергнута другой уликой.")
        else:
            lines.append("\n⚠️ <b>Статус:</b> выглядит серьёзно, но эту версию ещё нужно проверить.")
    if clue.get("refutes"):
        targets = []
        for target_id in clue["refutes"]:
            target = next((c for c in case["clues"] if c["id"] == target_id), None)
            if target:
                targets.append(target["text"])
        if targets:
            lines.append("\n🧩 <b>Эта улика опровергает:</b>\n" + "\n".join(f"• {text}" for text in targets))
    return "\n".join(lines)


# ──────────────────────────── новое дело ────────────────────────────

@router.callback_query(F.data == "new_case")
async def new_case(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    await state.set_state(Game.choosing_setting)
    await cb.message.answer("Выбери вселенную дела:", reply_markup=kb.hide_kb())
    await cb.message.answer("Доступные варианты:", reply_markup=kb.settings_kb())


@router.callback_query(F.data.startswith("set:"))
async def setting_chosen(cb: CallbackQuery, state: FSMContext) -> None:
    setting = cb.data.split(":", 1)[1]
    await cb.answer()
    await cb.message.answer("🔮 Генерирую дело…", reply_markup=kb.hide_kb())

    case = await case_gen.generate_case(setting)
    user_id = cb.from_user.id
    await database.save_case(case, user_id)
    await database.save_session(user_id, case["id"], "active", config.start_moves, empty_state())

    await state.set_state(Game.playing)
    await cb.message.answer(_briefing(case, config.start_moves), reply_markup=kb.game_kb())
    line = await watson.comment(case, empty_state(), "briefing")
    if line:
        await cb.message.answer(line)


_TUTORIAL_INTRO = (
    "🎓 <b>Обучение</b>\n\n"
    "Простое дело, чтобы освоить механику. Как играть:\n"
    "• <b>👤 Допросить</b> — выбери подозреваемого и спрашивай своими словами.\n"
    "• <b>🔍 Осмотреть</b> — обыщи локации, пиши что осмотреть (напр. «осмотреть стол»).\n"
    "• <b>🎴 Улики</b> — предъяви найденную улику в допросе, чтобы расколоть лжеца.\n"
    "• <b>🗣 Очная ставка</b> — припри одного показаниями другого.\n"
    "• <b>📋 Блокнот</b> — что нашёл и кого допросил.\n"
    "• <b>⚖️ Обвинить</b> — назови убийцу и обоснуй. Ходы ограничены!\n\n"
    "🤝 Рядом с тобой — <b>напарник</b>: он подкинет реплику на находках и пойманных нестыковках "
    "(подсказку не выдаёт, просто думает вслух).\n\n"
    "💡 Подсказка для старта: осмотри <b>Библиотеку</b> и <b>Сад</b>, "
    "потом сравни алиби — кто-то солгал о том, где был."
)


@router.callback_query(F.data == "tutorial")
async def start_tutorial(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    case = get_sample_case()
    user_id = cb.from_user.id
    await database.save_case(case, user_id)
    await database.save_session(user_id, case["id"], "active", config.start_moves, empty_state())
    await state.set_state(Game.playing)
    await cb.message.answer(_TUTORIAL_INTRO, reply_markup=kb.game_kb())
    await cb.message.answer(_briefing(case, config.start_moves))
    line = await watson.comment(case, empty_state(), "briefing")
    if line:
        await cb.message.answer(line)


@router.callback_query(F.data == "continue")
async def continue_case(cb: CallbackQuery, state: FSMContext) -> None:
    await cb.answer()
    case, sess = await _load(cb.from_user.id)
    if not case:
        await cb.message.answer("Активного дела нет.", reply_markup=kb.hide_kb())
        await cb.message.answer("Начни новое дело.", reply_markup=kb.main_menu_kb())
        return
    await state.set_state(Game.playing)
    await cb.message.answer(_briefing(case, sess["moves_left"]), reply_markup=kb.game_kb())


# ──────────────────────────── блокнот / меню ────────────────────────────

@router.message(F.text == kb.BTN_NOTEBOOK)
async def open_notebook(message: Message) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    await message.answer(_notebook(case, sess))


@router.message(F.text == kb.BTN_EVIDENCE)
async def show_evidence(message: Message, state: FSMContext) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    found = sess["state"].get("found_clues", [])
    if not found:
        return await message.answer("Улик пока нет — сначала осмотри локации («🔍 Осмотреть»).")
    data = await state.get_data()
    suspect_id = data.get("suspect_id")
    in_interrogation = await state.get_state() == Game.interrogating.state and bool(suspect_id)
    text = "Найденные улики. Выбери, что прочитать."
    if in_interrogation:
        name = next(s["name"] for s in case["suspects"] if s["id"] == suspect_id)
        text += f"\n\nСейчас ты допрашиваешь «{name}», так что можно и перечитать улику, и потом предъявить её."
    await message.answer(text, reply_markup=kb.found_clues_kb(case, found, can_present=in_interrogation))


@router.callback_query(F.data.startswith("clue:"))
async def read_clue(cb: CallbackQuery) -> None:
    clue_id = cb.data.split(":", 1)[1]
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    clue = next((c for c in case["clues"] if c["id"] == clue_id), None)
    if not clue:
        return await cb.answer("Улика не найдена.", show_alert=True)
    await cb.answer()
    await cb.message.answer(_format_clue_details(case, sess, clue))


@router.message(F.text == kb.BTN_CROSS)
async def show_cross(message: Message, state: FSMContext) -> None:
    """Очная ставка: припереть текущего подозреваемого показаниями другого."""
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    data = await state.get_data()
    suspect_id = data.get("suspect_id")
    if await state.get_state() != Game.interrogating.state or not suspect_id:
        return await message.answer("Сначала зайди в допрос («👤 Допросить»), затем — очная ставка.")
    dialogs = sess["state"].get("suspect_dialogs", {})
    available = [sid for sid, d in dialogs.items() if sid != suspect_id and d]
    if not available:
        return await message.answer("Сначала допроси других подозреваемых — иначе нечем припереть.")
    cur_name = next(s["name"] for s in case["suspects"] if s["id"] == suspect_id)
    await message.answer(f"Чьими показаниями припереть «{cur_name}»?",
                         reply_markup=kb.cross_suspects_kb(case, available))


@router.callback_query(F.data.startswith("xref:"))
async def cross_pick_statement(cb: CallbackQuery, state: FSMContext) -> None:
    cited_id = cb.data.split(":", 1)[1]
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    await cb.answer()
    statements = sess["state"].get("suspect_dialogs", {}).get(cited_id, [])
    if not statements:
        return await cb.message.answer("У этого свидетеля нет показаний.")
    cited_name = next(s["name"] for s in case["suspects"] if s["id"] == cited_id)
    await cb.message.answer(f"Какое показание «{cited_name}» предъявить?",
                            reply_markup=kb.cross_quotes_kb(statements, cited_id))


@router.callback_query(F.data.startswith("xq:"))
async def cross_confront(cb: CallbackQuery, state: FSMContext) -> None:
    _, cited_id, idx = cb.data.split(":")
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    data = await state.get_data()
    suspect_id = data.get("suspect_id")
    if not suspect_id:
        return await cb.answer("Сначала зайди в допрос подозреваемого.", show_alert=True)
    await cb.answer()
    statements = sess["state"].get("suspect_dialogs", {}).get(cited_id, [])
    try:
        quote = statements[int(idx)]["a"]
    except (IndexError, ValueError):
        return await cb.message.answer("Показание не найдено.")
    cited_name = next(s["name"] for s in case["suspects"] if s["id"] == cited_id)

    answer = await interrogate.respond(
        case, sess["state"], suspect_id,
        "Детектив припирает тебя показаниями другого свидетеля.",
        cross_quote=f"{cited_name} утверждает: «{quote}»",
    )
    await database.save_session(cb.from_user.id, sess["case_id"], "active",
                                sess["moves_left"], sess["state"])
    await cb.message.answer(
        f"🗣 Ты ссылаешься на слова «{cited_name}»:\n<i>{quote}</i>\n\n💬 {answer}",
    )


@router.message(F.text == kb.BTN_LEAVE)
async def leave_to_menu(message: Message, state: FSMContext) -> None:
    await state.set_state(Game.menu)
    await message.answer("Дело сохранено. Вернёшься через «Продолжить».", reply_markup=kb.hide_kb())
    await message.answer("Главное меню:", reply_markup=kb.main_menu_kb())


@router.message(F.text == kb.BTN_HINT)
async def give_hint(message: Message) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    sess["state"]["hints_used"] += 1
    await database.save_session(message.from_user.id, sess["case_id"], "active",
                                sess["moves_left"], sess["state"])
    text = await hint.give_hint(case, sess["state"])
    await message.answer(f"{text}\n\n<i>(подсказка снижает итоговый ранг)</i>")


# ──────────────────────────── допрос ────────────────────────────

@router.message(F.text == kb.BTN_INTERROGATE)
async def choose_suspect(message: Message) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    if sess["moves_left"] <= 0:
        return await message.answer(_OUT_OF_MOVES)
    await message.answer("Кого допросить? <i>(новый допрос — 1 ход)</i>",
                         reply_markup=kb.suspects_kb(case, prefix="susp"))


@router.callback_query(F.data.startswith("susp:"))
async def start_interrogation(cb: CallbackQuery, state: FSMContext) -> None:
    suspect_id = cb.data.split(":", 1)[1]
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    await cb.answer()
    if not await _charge_move(cb.from_user.id, sess):
        return await cb.message.answer(_OUT_OF_MOVES)
    await state.set_state(Game.interrogating)
    await state.update_data(suspect_id=suspect_id)
    name = next(s["name"] for s in case["suspects"] if s["id"] == suspect_id)
    await cb.message.answer(
        f"🎤 Допрос: <b>{name}</b>. Задавай вопросы — в этом раунде их сколько угодно. "
        f"Снова «{kb.BTN_INTERROGATE}» — новый раунд (−1 ход).\n"
        f"⏳ Ходов осталось: {sess['moves_left']}")


@router.message(Game.interrogating, F.text & ~F.text.in_(
    {kb.BTN_INTERROGATE, kb.BTN_SEARCH, kb.BTN_EVIDENCE, kb.BTN_CROSS,
     kb.BTN_NOTEBOOK, kb.BTN_HINT, kb.BTN_ACCUSE, kb.BTN_LEAVE}))
async def interrogate_msg(message: Message, state: FSMContext) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    data = await state.get_data()
    suspect_id = data.get("suspect_id")

    answer = await interrogate.respond(case, sess["state"], suspect_id, message.text)
    await database.save_session(message.from_user.id, sess["case_id"], "active",
                                sess["moves_left"], sess["state"])
    # индикатор состояния подозреваемого (нервозность от твоего тона)
    mood = sess["state"].get("suspect_mood", {}).get(suspect_id, "")
    prefix = f"<i>{mood}</i>\n" if mood else ""
    # если у игрока уже есть улики — предложим предъявить их
    markup = kb.present_evidence_kb() if sess["state"].get("found_clues") else None
    await message.answer(f"{prefix}💬 {answer}", reply_markup=markup)


# ──────────────────────────── предъявление улики ────────────────────────────

@router.callback_query(F.data == "evidence_menu")
async def evidence_menu(cb: CallbackQuery, state: FSMContext) -> None:
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    found = sess["state"].get("found_clues", [])
    if not found:
        return await cb.answer("Улик пока нет — осмотри локации.", show_alert=True)
    await cb.answer()
    await cb.message.answer("Какую улику предъявить?", reply_markup=kb.clues_kb(case, found))


@router.callback_query(F.data.startswith("evid:"))
async def present_evidence(cb: CallbackQuery, state: FSMContext) -> None:
    clue_id = cb.data.split(":", 1)[1]
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    data = await state.get_data()
    suspect_id = data.get("suspect_id")
    if not suspect_id:
        return await cb.answer("Сначала зайди в допрос подозреваемого.", show_alert=True)
    clue = next((c for c in case["clues"] if c["id"] == clue_id), None)
    if not clue:
        return await cb.answer("Улика не найдена.", show_alert=True)
    await cb.answer()

    suspect = next(s for s in case["suspects"] if s["id"] == suspect_id)
    breaks = clue_id in suspect.get("breaks_on", [])
    answer = await interrogate.respond(
        case, sess["state"], suspect_id,
        "Детектив молча кладёт перед тобой улику и смотрит в глаза.",
        evidence_text=clue["text"], evidence_breaks=breaks,
    )
    # улика колет именно этого подозреваемого -> фиксируем противоречие в блокноте
    if breaks:
        note = f"{suspect['name']} дрогнул при улике: {clue['text']}"
        contradictions = sess["state"].setdefault("noted_contradictions", [])
        if all(n.get("note") != note for n in contradictions):
            contradictions.append({"suspect": suspect["name"], "note": note})

    await database.save_session(cb.from_user.id, sess["case_id"], "active",
                                sess["moves_left"], sess["state"])
    await cb.message.answer(
        f"🎴 Ты предъявляешь: <i>{clue['text']}</i>\n\n💬 {answer}",
        reply_markup=kb.present_evidence_kb(),
    )
    if breaks:
        line = await watson.comment(case, sess["state"], "contradiction", detail=clue["text"])
        if line:
            await cb.message.answer(line)


# ──────────────────────────── осмотр ────────────────────────────

@router.message(F.text == kb.BTN_SEARCH)
async def choose_location(message: Message, state: FSMContext) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    if sess["moves_left"] <= 0:
        return await message.answer(_OUT_OF_MOVES)
    await message.answer("Какую локацию осмотреть? <i>(осмотр — 1 ход)</i>",
                         reply_markup=kb.locations_kb(case))


@router.callback_query(F.data.startswith("loc:"))
async def start_search(cb: CallbackQuery, state: FSMContext) -> None:
    location_id = cb.data.split(":", 1)[1]
    case, sess = await _load(cb.from_user.id)
    if not case:
        return await cb.answer("Нет активного дела.", show_alert=True)
    await cb.answer()
    if not await _charge_move(cb.from_user.id, sess):
        return await cb.message.answer(_OUT_OF_MOVES)
    await state.set_state(Game.searching)
    await state.update_data(location_id=location_id)
    location = next(loc for loc in case["locations"] if loc["id"] == location_id)
    await cb.message.answer(_location_scene(location) + f"\n\n⏳ Ходов осталось: {sess['moves_left']}")


@router.message(Game.searching, F.text & ~F.text.in_(
    {kb.BTN_INTERROGATE, kb.BTN_SEARCH, kb.BTN_EVIDENCE, kb.BTN_CROSS,
     kb.BTN_NOTEBOOK, kb.BTN_HINT, kb.BTN_ACCUSE, kb.BTN_LEAVE}))
async def search_msg(message: Message, state: FSMContext) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    data = await state.get_data()
    location_id = data.get("location_id")

    before = set(sess["state"].get("found_clues", []))
    text, clue_id = await search.search(case, sess["state"], location_id, message.text)
    await database.save_session(message.from_user.id, sess["case_id"], "active",
                                sess["moves_left"], sess["state"])
    await message.answer(text)
    # напарник реагирует только на ВПЕРВЫЕ найденную улику
    if clue_id and clue_id not in before:
        clue = next((c for c in case["clues"] if c["id"] == clue_id), None)
        line = await watson.comment(case, sess["state"], "clue", detail=clue["text"]) if clue else None
        if line:
            await message.answer(line)


# ──────────────────────────── обвинение / финал ────────────────────────────

@router.message(F.text == kb.BTN_ACCUSE)
async def choose_accused(message: Message, state: FSMContext) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    await state.set_state(Game.accusing)
    await message.answer("⚖️ Кого обвиняешь? (после выбора напишешь обоснование)",
                         reply_markup=kb.suspects_kb(case, prefix="accuse"))


@router.callback_query(F.data.startswith("accuse:"))
async def accused_chosen(cb: CallbackQuery, state: FSMContext) -> None:
    accused_id = cb.data.split(":", 1)[1]
    await cb.answer()
    await state.update_data(accused_id=accused_id)
    await cb.message.answer("Напиши обоснование: кто, как и почему. Это последнее слово, сыщик.")


@router.message(Game.accusing, F.text & ~F.text.in_(
    {kb.BTN_INTERROGATE, kb.BTN_SEARCH, kb.BTN_EVIDENCE, kb.BTN_CROSS,
     kb.BTN_NOTEBOOK, kb.BTN_HINT, kb.BTN_ACCUSE, kb.BTN_LEAVE}))
async def final_accusation(message: Message, state: FSMContext) -> None:
    case, sess = await _load(message.from_user.id)
    if not case:
        return await message.answer("Нет активного дела.")
    data = await state.get_data()
    accused_id = data.get("accused_id")
    if not accused_id:
        return await message.answer("Сначала выбери подозреваемого кнопкой.")

    verdict = await judge.judge_accusation(case, accused_id, message.text)
    score, rank = scoring.compute(
        verdict["correct"], verdict.get("quality", 0),
        sess["moves_left"], sess["state"]["hints_used"],
    )

    await database.save_session(message.from_user.id, sess["case_id"], "finished",
                                sess["moves_left"], sess["state"])
    await database.add_result(message.from_user.id, sess["case_id"], score, rank)
    await state.set_state(Game.menu)

    head = "✅ <b>Верно!</b>" if verdict["correct"] else "❌ <b>Мимо.</b>"
    await message.answer(
        f"{head}\n\n🎭 {verdict['reveal']}\n\n"
        f"🏅 Очки: <b>{score}</b> · Ранг: <b>{rank}</b>",
        reply_markup=kb.hide_kb(),
    )
    # напарник закрывает дело: радуется победе или поддерживает при промахе
    truth = next(s for s in case["suspects"] if s["id"] == case["murderer_id"])
    event = "verdict_win" if verdict["correct"] else "verdict_lose"
    line = await watson.comment(case, sess["state"], event, detail=truth["name"])
    if line:
        await message.answer(line)
    await message.answer("Главное меню:", reply_markup=kb.main_menu_kb())
