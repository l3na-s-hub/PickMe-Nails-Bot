from datetime import date
from typing import Sequence

from aiogram.types import InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from database.models import Service

RU_MONTHS = [
    "", "Январь", "Февраль", "Март", "Апрель", "Май", "Июнь",
    "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь",
]

EDIT_FIELDS = [
    ("title", "Название"),
    ("description", "Описание"),
    ("price", "Цена"),
    ("duration_minutes", "Длительность"),
]


def admin_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Записи на сегодня")
    builder.button(text="🗓 Записи за месяц")
    builder.button(text="📊 Статистика за месяц")
    builder.button(text="➕ Добавить услугу")
    builder.button(text="✏️ Редактировать услугу")
    builder.button(text="❌ Удалить услугу")
    builder.button(text="🛠 Расписание записи")
    builder.button(text="🔙 Выйти из админки")
    builder.adjust(2, 2, 2, 2)
    return builder.as_markup(resize_keyboard=True)


def admin_services_delete_kb(services: Sequence[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"{s.title} — {s.price}₽", callback_data=f"admin_del_service:{s.id}")
    builder.adjust(1)
    return builder.as_markup()


def admin_services_edit_kb(services: Sequence[Service]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for s in services:
        builder.button(text=f"{s.title} — {s.price}₽", callback_data=f"edit_service:{s.id}")
    builder.adjust(1)
    return builder.as_markup()


def edit_field_choice_kb(service_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for field_key, field_label in EDIT_FIELDS:
        builder.button(text=field_label, callback_data=f"edit_field:{service_id}:{field_key}")
    builder.adjust(2)
    return builder.as_markup()


def admin_cancel_booking_kb(booking_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отменить эту запись", callback_data=f"admin_cancel_booking:{booking_id}")
    builder.adjust(1)
    return builder.as_markup()


def month_picker_kb(callback_prefix: str = "month") -> InlineKeyboardMarkup:
    """Кнопки выбора месяца: текущий и два следующих."""
    builder = InlineKeyboardBuilder()
    today = date.today()
    year, month = today.year, today.month
    for _ in range(3):
        label = f"{RU_MONTHS[month]} {year}"
        builder.button(text=label, callback_data=f"{callback_prefix}:{year}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    builder.adjust(1)
    return builder.as_markup()


# ---------------------------------------------------------------------------
# Расписание записи (мастер сам открывает дни/время)
# ---------------------------------------------------------------------------

def schedule_menu_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="➕ Открыть один день", callback_data="sched_open_day")
    builder.button(text="🗓 Открыть весь месяц", callback_data="sched_open_month")
    builder.button(text="📋 Открытые дни", callback_data="sched_view_days")
    builder.adjust(1)
    return builder.as_markup()


def toggle_times_kb(all_times: Sequence[str], selected: Sequence[str], save_callback: str) -> InlineKeyboardMarkup:
    """Клавиатура для отметки времени: выбранные помечены ✅, остальные ⬜."""
    builder = InlineKeyboardBuilder()
    for t in all_times:
        mark = "✅" if t in selected else "⬜"
        builder.button(text=f"{mark} {t}", callback_data=f"toggle_time:{t}")
    builder.button(text="💾 Сохранить", callback_data=save_callback)
    builder.adjust(2)
    return builder.as_markup()


def open_days_list_kb(dates_with_counts: Sequence[tuple]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for d, count in dates_with_counts:
        builder.button(text=f"{d.strftime('%d.%m.%Y')} ({count})", callback_data=f"view_day:{d.isoformat()}")
    builder.adjust(2)
    return builder.as_markup()


def day_slots_manage_kb(date_iso: str, times: Sequence[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for t in times:
        builder.button(text=f"🗑 {t}", callback_data=f"remove_slot:{date_iso}:{t}")
    builder.button(text="🗑 Удалить весь день", callback_data=f"remove_day:{date_iso}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()
