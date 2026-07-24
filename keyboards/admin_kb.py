import calendar
from datetime import date, datetime, timedelta
from typing import Sequence

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.filters.callback_data import CallbackData
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


class ToggleSlotCallback(CallbackData, prefix="ts", sep="#"):
    action: str        # 'open' или 'close'
    date_str: str      # 'YYYY-MM-DD'
    slot_time: str     # 'HH:MM'
    

def admin_menu_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.button(text="📅 Записи на сегодня")
    builder.button(text="🗓 Записи за месяц")
    builder.button(text="📊 Статистика за месяц")
    builder.button(text="📅 Расписание на месяц")
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


def generate_working_hours() -> list[str]:
    """
    Генерирует список времени с 08:00 до 22:00 с шагом 30 минут.
    Выдаст: ['08:00', '08:30', '09:00', ..., '22:00']
    """
    start_time = datetime.strptime("08:00", "%H:%M")
    end_time = datetime.strptime("22:00", "%H:%M")
    current = start_time
    
    hours = []
    while current <= end_time:
        hours.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
        
    return hours


def admin_edit_slots_kb(chosen_date_str: str, open_slots: list[str]) -> InlineKeyboardMarkup:
    """
    Строит сетку кнопок-переключателей (по 4 в ряд).
    open_slots — это список строк времени, которые СЕЙЧАС ОТКРЫТЫ в базе (из requests.py)
    """
    builder = InlineKeyboardBuilder()
    all_hours = generate_working_hours()
    
    for slot_time in all_hours:
        # Проверяем, открыт ли этот слот в базе данных
        if slot_time in open_slots:
            # Слот открыт -> горит зеленым. Нажатие должно его ЗАКРЫТЬ (close)
            text = f"🟢 {slot_time}"
            action = "close"
        else:
            # Слот закрыт -> горит красным. Нажатие должно его ОТКРЫТЬ (open)
            text = f"🔴 {slot_time}"
            action = "open"
            
        # Формируем callback_data. 
        # Передаем действие (open/close), дату и само время, чтобы хэндлер понял, что менять.
        # Пример: "ts:open:2026-07-24:08:30" (ts - toggle slot)
        callback_data = ToggleSlotCallback(action=action, date_str=chosen_date_str, slot_time=slot_time).pack()        
        builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
        
    # Размещаем кнопки по 4 штуки в ряд для компактности
    builder.adjust(4)
    
    # Добавим кнопку "Назад" в самый конец, чтобы админ мог вернуться к выбору дат
    builder.row(InlineKeyboardButton(text="⬅️ Назад к датам", callback_data=f"back_to_dates:{chosen_date_str}"))
    
    return builder.as_markup()

def get_monthly_calendar_kb(year: int, month: int, free_dates: set[date]) -> InlineKeyboardMarkup:
    """
    Генерирует инлайн-календарь в виде сетки дней недели.
    """
    builder = InlineKeyboardBuilder()
    
    # Шапка: дни недели (Пн - Вс)
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    for day in weekdays:
        builder.add(InlineKeyboardButton(text=day, callback_data="ignore"))
    
    # Матрица месяца (недели от Пн до Вс)
    cal = calendar.monthcalendar(year, month)
    
    for week in cal:
        for day in week:
            if day == 0:
                builder.add(InlineKeyboardButton(text=" ", callback_data="ignore"))
            else:
                current_date = date(year, month, day)
                
                # Если на этот день есть свободные окна — подсвечиваем зелёным
                if current_date in free_dates:
                    text = f"🟢 {day}"
                    callback_data = f"admin_date_{current_date.isoformat()}"
                else:
                    text = str(day)
                    callback_data = "ignore"
                    
                builder.add(InlineKeyboardButton(text=text, callback_data=callback_data))
                
    # Ровно 7 колонок для сетки недели
    builder.adjust(7, repeat=True)
    return builder.as_markup()