"""Дымовой тест LLM: генерация дела + один ответ подозреваемого.

Запуск из корня проекта:  python scripts/test_llm.py
Проверяет ключ/модель/промпты БЕЗ запуска Telegram-бота.
"""
import asyncio
import sys
from pathlib import Path

# Консоль Windows бывает в cp1251 - принудительно UTF-8, иначе падает на эмодзи/стрелках.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

# Чтобы импорты core/config работали при запуске из подпапки.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import config  # noqa: E402
from core import case_gen, interrogate  # noqa: E402


async def main() -> None:
    print(f"Провайдер: {config.llm_provider}")
    print(f"Основная модель: {config.llm_model}")
    print(f"Быстрая модель: {config.llm_model_fast}")
    print(f"LLM включён: {config.llm_enabled}\n")
    if not config.llm_enabled:
        print("❌ LLM_API_KEY пуст — заполни .env. Тест бессмыслен.")
        return

    print("→ Генерирую дело (вселенная: noir)…")
    case = await case_gen.generate_case("noir")
    print(f"✅ Дело: {case['title']}")
    print(f"   Жертва: {case['victim']['name']}")
    print(f"   Подозреваемые: {', '.join(s['name'] for s in case['suspects'])}")
    print(f"   Локаций: {len(case['locations'])}, улик: {len(case['clues'])}")
    print(f"   (секрет: убийца = {case['murderer_id']})\n")

    suspect = case["suspects"][0]
    print(f"→ Допрашиваю «{suspect['name']}»: 'Где вы были в момент убийства?'")
    state = {"interrogated": [], "suspect_dialogs": {}}
    answer = await interrogate.respond(case, state, suspect["id"], "Где вы были в момент убийства?")
    print(f"💬 {answer}\n")

    print("✅ Всё работает. Можно гонять бота.")


if __name__ == "__main__":
    asyncio.run(main())
