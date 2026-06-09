"""Формы данных (для подсказок редактора). Хранятся как JSON-словари.

Подробное описание полей — в КОНЦЕПТ.md, раздел 4.
"""
try:  # NotRequired появился в typing только в Python 3.11
    from typing import NotRequired, TypedDict
except ImportError:  # Python 3.10 (напр. на сервере) — берём из typing_extensions
    from typing_extensions import NotRequired, TypedDict


class Suspect(TypedDict):
    id: str
    name: str
    persona: str
    alibi: str
    secret: str
    knows: list[str]
    lies_about: str
    breaks_on: list[str]  # id улик, на которых колется


class Searchable(TypedDict):
    desc: str
    clue: str | None  # id улики или None (пустышка)


class Location(TypedDict):
    id: str
    name: str
    desc: str  # атмосферное описание локации (1-2 предложения)
    searchables: list[Searchable]


class Clue(TypedDict):
    id: str
    text: str
    implicates: str  # id подозреваемого
    kind: NotRequired[str]  # document / trace / object / forensic
    read_text: NotRequired[str]  # полный текст записки/договора/письма, если улику можно читать
    notebook_note: NotRequired[str]  # короткий вывод для блокнота
    is_false_lead: NotRequired[bool]  # ложный след, который может повести не туда
    refuted_by: NotRequired[list[str]]  # id улик, которые опровергают этот ложный след
    refutes: NotRequired[list[str]]  # id ложных следов, которые эта улика ломает


class Case(TypedDict):
    id: str
    setting: str
    title: str
    victim: dict
    murderer_id: str  # СЕКРЕТ, не показывать игроку
    weapon: str
    motive: str
    time: str
    suspects: list[Suspect]
    locations: list[Location]
    clues: list[Clue]
    solution_chain: str


class SessionState(TypedDict):
    interrogated: list[str]
    found_clues: list[str]
    noted_contradictions: list[dict]
    hints_used: int
    suspect_dialogs: dict[str, list[dict]]


def empty_state() -> SessionState:
    return {
        "interrogated": [],
        "found_clues": [],
        "noted_contradictions": [],
        "hints_used": 0,
        "suspect_dialogs": {},
    }
