from aiogram.fsm.state import State, StatesGroup


class AdminStates(StatesGroup):
    # Добавление новой услуги
    adding_title = State()
    adding_description = State()
    adding_price = State()
    adding_duration = State()

    # Редактирование существующей услуги (ожидание нового значения выбранного поля)
    editing_value = State()

    # Открытие одного дня для записи: ждём дату текстом, затем ждём переключения времени
    opening_day_input = State()
    opening_day_toggle = State()

    # Открытие целого месяца для записи: после выбора месяца ждём переключения времени
    opening_month_toggle = State()
