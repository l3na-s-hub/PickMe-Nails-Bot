from datetime import date
from typing import Sequence

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database.models import Service

RU_WEEKDAYS = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]

# Стандартный набор времени, который мастер может открыть для записи.
# Используется как пресет в админ-панели при открытии дня/месяца.
AVAILABLE_TIMES = ["10:00", "13:00", "16:00", "19:00"]


def main_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="💅 Записаться")
    builder.button(text="📋 Мои записи")
    builder.button(text="💰 Цены и услуги")
    builder.button(text="📞 Контакты")
    builder.adjust(2, 2)
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="🚫 Отмена")
    return builder.as_markup(resize_keyboard=True)


def services_inline_kb(services: Sequence[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"{s.title} — {s.price}₽", callback_data=f"service:{s.id}")
    builder.button(text="🚫 Отмена", callback_data="cancel_booking_flow")
    builder.adjust(1)
    return builder.as_markup()


def dates_inline_kb(available_dates: Sequence[date]) -> InlineKeyboardMarkup:
    """Показывает даты, которые мастер открыл для записи и на которых остались свободные слоты."""
    builder = InlineKeyboardBuilder()
    for d in available_dates:
        label = f"{d.strftime('%d.%m')} ({RU_WEEKDAYS[d.weekday()]})"
        builder.button(text=label, callback_data=f"date:{d.isoformat()}")
    builder.button(text="🚫 Отмена", callback_data="cancel_booking_flow")
    builder.adjust(2)
    return builder.as_markup()


def times_inline_kb(open_times: Sequence[str], busy_times: Sequence[str]) -> InlineKeyboardMarkup:
    """Показывает время, открытое мастером на конкретную дату, за вычетом уже занятого."""
    builder = InlineKeyboardBuilder()
    for t in open_times:
        if t in busy_times:
            continue
        builder.button(text=t, callback_data=f"time:{t}")
    builder.button(text="🚫 Отмена", callback_data="cancel_booking_flow")
    builder.adjust(2)
    return builder.as_markup()


def phone_request_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📱 Отправить номер телефона", request_contact=True)
    builder.button(text="🚫 Отмена")
    builder.adjust(1)
    return builder.as_markup(resize_keyboard=True)


def confirm_booking_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Записаться", callback_data="confirm_booking")
    builder.button(text="🚫 Отмена", callback_data="cancel_booking_flow")
    builder.adjust(1)
    return builder.as_markup()


def my_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить запись", callback_data=f"cancel_my_booking:{booking_id}")
    builder.adjust(1)
    return builder.as_markup()
