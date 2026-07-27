from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    # Добавление новой услуги
    adding_title = State()
    adding_description = State()
    adding_price = State()
    adding_duration = State()

    # Редактирование услуги
    editing_value = State()

    # Открытие расписания
    opening_day_input = State()
    opening_day_toggle = State()
    opening_month_toggle = State()

    # Редактирование контента
    editing_content = State()  # <-- НОВОЕ СОСТОЯНИЕ