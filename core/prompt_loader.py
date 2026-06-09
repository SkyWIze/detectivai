"""Загрузка системных промптов из папки prompts/ с подстановкой переменных."""
from functools import lru_cache
from pathlib import Path

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


@lru_cache(maxsize=None)
def _read(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.txt").read_text(encoding="utf-8")


def load(prompt_name: str, /, **vars: str) -> str:
    """Читает prompts/<prompt_name>.txt и подставляет {placeholders}.

    Первый аргумент — позиционный-только (`/`), чтобы не конфликтовать с
    переменной шаблона `name=` (напр. имя подозреваемого в interrogate.txt).
    """
    text = _read(prompt_name)
    return text.format(**vars) if vars else text
