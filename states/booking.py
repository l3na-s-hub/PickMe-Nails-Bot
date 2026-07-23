from aiogram.fsm.state import State, StatesGroup


class BookingStates(StatesGroup):
    waiting_service = State()
    waiting_date = State()
    waiting_time = State()
    waiting_phone = State()
    confirm = State()
