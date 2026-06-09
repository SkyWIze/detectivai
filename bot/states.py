"""FSM-состояния игры (см. КОНЦЕПТ.md, раздел 7)."""
from aiogram.fsm.state import State, StatesGroup


class Game(StatesGroup):
    menu = State()
    choosing_setting = State()
    playing = State()          # игровой экран с постоянной клавиатурой
    interrogating = State()    # внутри допроса конкретного подозреваемого
    searching = State()        # внутри осмотра конкретной локации
    accusing = State()         # ввод обвинения + обоснование
