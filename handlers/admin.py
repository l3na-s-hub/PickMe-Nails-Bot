from datetime import date as date_type
from datetime import datetime

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import config
from database import requests as db
from keyboards import admin_kb, client_kb
from states.admin import AdminStates

router = Router()
router.message.filter(F.from_user.id.in_(config.admin_ids))
router.callback_query.filter(F.from_user.id.in_(config.admin_ids))


def parse_date_input(text: str) -> date_type | None:
    """Парсит дату из текста в формате ДД.ММ.ГГГГ, возвращает None при ошибке."""
    try:
        return datetime.strptime(text.strip(), "%d.%m.%Y").date()
    except ValueError:
        return None


def client_display_name(user) -> str:
    """Формирует строку с именем и username клиента для карточек записи."""
    username_part = f"@{user.username}" if getattr(user, "username", None) else "нет username"
    return f"{user.full_name} ({username_part})"


@router.message(Command("admin"))
async def cmd_admin(message: Message) -> None:
    await message.answer("🔧 <b>Панель администратора</b>", reply_markup=admin_kb.admin_menu_kb())


# ---------------------------------------------------------------------------
# Записи на сегодня
# ---------------------------------------------------------------------------

@router.message(F.text == "📅 Записи на сегодня")
async def bookings_today(message: Message) -> None:
    today = date_type.today()
    bookings = await db.get_bookings_by_date(today)
    if not bookings:
        await message.answer("На сегодня записей нет.")
        return
    await message.answer(f"<b>📅 Записи на {today.strftime('%d.%m.%Y')}:</b>")
    for b in bookings:
        text = (
            f"👤 {client_display_name(b.user)}\n"
            f"📱 {b.user.phone_number or 'нет телефона'}\n"
            f"💅 {b.service.title}\n"
            f"🕐 {b.booking_time}"
        )
        await message.answer(text, reply_markup=admin_kb.admin_cancel_booking_kb(b.id))


@router.callback_query(F.data.startswith("admin_cancel_booking:"))
async def admin_cancel_booking(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[1])
    booking = await db.cancel_booking(booking_id)
    if booking is None:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ Запись клиента {client_display_name(booking.user)} на {booking.booking_date.strftime('%d.%m.%Y')} "
        f"в {booking.booking_time} отменена."
    )
    await callback.answer("Отменено")
    try:
        await callback.bot.send_message(
            booking.user.telegram_id,
            "⚠️ <b>Ваша запись отменена мастером.</b>\n\n"
            f"Услуга: {booking.service.title}\n"
            f"Дата: {booking.booking_date.strftime('%d.%m.%Y')}\n"
            f"Время: {booking.booking_time}\n\n"
            "Пожалуйста, свяжитесь со мной или запишитесь на другое время.",
        )
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Записи за месяц
# ---------------------------------------------------------------------------

@router.message(F.text == "🗓 Записи за месяц")
async def bookings_month_start(message: Message) -> None:
    await message.answer("Выберите месяц:", reply_markup=admin_kb.month_picker_kb(callback_prefix="month"))


@router.callback_query(F.data.startswith("month:"))
async def bookings_month_show(callback: CallbackQuery) -> None:
    year_str, month_str = callback.data.split(":")[1].split("-")
    year, month = int(year_str), int(month_str)
    bookings = await db.get_bookings_by_month(year, month)

    if not bookings:
        await callback.message.edit_text(f"На {admin_kb.RU_MONTHS[month]} {year} записей нет.")
        await callback.answer()
        return

    await callback.message.edit_text(f"<b>🗓 Записи за {admin_kb.RU_MONTHS[month]} {year}:</b>")
    current_day: date_type | None = None
    for b in bookings:
        if b.booking_date != current_day:
            current_day = b.booking_date
            await callback.message.answer(f"<b>📅 {current_day.strftime('%d.%m.%Y')}</b>")
        text = (
            f"👤 {client_display_name(b.user)}\n"
            f"📱 {b.user.phone_number or 'нет телефона'}\n"
            f"💅 {b.service.title}\n"
            f"🕐 {b.booking_time}"
        )
        await callback.message.answer(text, reply_markup=admin_kb.admin_cancel_booking_kb(b.id))
    await callback.answer()


# ---------------------------------------------------------------------------
# Статистика за месяц
# ---------------------------------------------------------------------------

@router.message(F.text == "📊 Статистика за месяц")
async def stats_month_start(message: Message) -> None:
    await message.answer(
        "Выберите месяц для статистики:",
        reply_markup=admin_kb.month_picker_kb(callback_prefix="stats"),
    )


@router.callback_query(F.data.startswith("stats:"))
async def stats_month_show(callback: CallbackQuery) -> None:
    year_str, month_str = callback.data.split(":")[1].split("-")
    year, month = int(year_str), int(month_str)
    stats = await db.get_monthly_stats(year, month)
    await callback.message.edit_text(
        f"<b>📊 Статистика за {admin_kb.RU_MONTHS[month]} {year}:</b>\n\n"
        f"Всего записей: <b>{stats['total_bookings']}</b>\n"
        f"Выручка: <b>{stats['total_revenue']}₽</b>"
    )
    await callback.answer()


# ---------------------------------------------------------------------------
# Добавление услуги (FSM)
# ---------------------------------------------------------------------------

@router.message(F.text == "➕ Добавить услугу")
async def add_service_start(message: Message, state: FSMContext) -> None:
    await state.set_state(AdminStates.adding_title)
    await message.answer("Введите название новой услуги:")


@router.message(AdminStates.adding_title, F.text)
async def add_service_title(message: Message, state: FSMContext) -> None:
    await state.update_data(title=message.text.strip())
    await state.set_state(AdminStates.adding_description)
    await message.answer("Введите описание услуги:")


@router.message(AdminStates.adding_description, F.text)
async def add_service_description(message: Message, state: FSMContext) -> None:
    await state.update_data(description=message.text.strip())
    await state.set_state(AdminStates.adding_price)
    await message.answer("Введите цену услуги (только число, в рублях):")


@router.message(AdminStates.adding_price, F.text)
async def add_service_price(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("Цена должна быть числом. Попробуйте ещё раз:")
        return
    await state.update_data(price=int(message.text.strip()))
    await state.set_state(AdminStates.adding_duration)
    await message.answer("Введите длительность процедуры в минутах (только число):")


@router.message(AdminStates.adding_duration, F.text)
async def add_service_duration(message: Message, state: FSMContext) -> None:
    if not message.text.strip().isdigit():
        await message.answer("Длительность должна быть числом. Попробуйте ещё раз:")
        return
    data = await state.get_data()
    duration = int(message.text.strip())
    service = await db.add_service(
        title=data["title"],
        description=data["description"],
        price=data["price"],
        duration_minutes=duration,
    )
    await state.clear()
    await message.answer(
        f"✅ Услуга <b>{service.title}</b> добавлена!\n"
        f"Цена: {service.price}₽, длительность: {service.duration_minutes} мин.",
        reply_markup=admin_kb.admin_menu_kb(),
    )


# ---------------------------------------------------------------------------
# Удаление услуги
# ---------------------------------------------------------------------------

@router.message(F.text == "❌ Удалить услугу")
async def delete_service_start(message: Message) -> None:
    services = await db.get_all_services()
    if not services:
        await message.answer("Список услуг пуст.")
        return
    await message.answer(
        "Выберите услугу для удаления:",
        reply_markup=admin_kb.admin_services_delete_kb(services),
    )


@router.callback_query(F.data.startswith("admin_del_service:"))
async def delete_service_confirm(callback: CallbackQuery) -> None:
    service_id = int(callback.data.split(":")[1])
    success = await db.delete_service(service_id)
    if success:
        await callback.message.edit_text("✅ Услуга удалена.")
    else:
        await callback.message.edit_text("Услуга не найдена.")
    await callback.answer()


# ---------------------------------------------------------------------------
# Редактирование существующей услуги
# ---------------------------------------------------------------------------

FIELD_LABELS = dict(admin_kb.EDIT_FIELDS)
FIELD_PROMPTS = {
    "title": "Введите новое название услуги:",
    "description": "Введите новое описание услуги:",
    "price": "Введите новую цену (только число, в рублях):",
    "duration_minutes": "Введите новую длительность в минутах (только число):",
}


@router.message(F.text == "✏️ Редактировать услугу")
async def edit_service_start(message: Message) -> None:
    services = await db.get_all_services()
    if not services:
        await message.answer("Список услуг пуст.")
        return
    await message.answer(
        "Выберите услугу для редактирования:",
        reply_markup=admin_kb.admin_services_edit_kb(services),
    )


@router.callback_query(F.data.startswith("edit_service:"))
async def edit_service_choose_field(callback: CallbackQuery) -> None:
    service_id = int(callback.data.split(":")[1])
    service = await db.get_service_by_id(service_id)
    if service is None:
        await callback.answer("Услуга не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"Услуга: <b>{service.title}</b>\n"
        f"Описание: {service.description}\n"
        f"Цена: {service.price}₽\n"
        f"Длительность: {service.duration_minutes} мин\n\n"
        "Что вы хотите изменить?",
        reply_markup=admin_kb.edit_field_choice_kb(service.id),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("edit_field:"))
async def edit_service_ask_value(callback: CallbackQuery, state: FSMContext) -> None:
    _, service_id_str, field = callback.data.split(":")
    await state.update_data(edit_service_id=int(service_id_str), edit_field=field)
    await state.set_state(AdminStates.editing_value)
    await callback.message.edit_text(FIELD_PROMPTS[field])
    await callback.answer()


@router.message(AdminStates.editing_value, F.text)
async def edit_service_save_value(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    service_id = data["edit_service_id"]
    field = data["edit_field"]
    raw_value = message.text.strip()

    if field in {"price", "duration_minutes"}:
        if not raw_value.isdigit():
            await message.answer("Значение должно быть числом. Попробуйте ещё раз:")
            return
        value: str | int = int(raw_value)
    else:
        value = raw_value

    service = await db.update_service(service_id, **{field: value})
    await state.clear()
    if service is None:
        await message.answer(
            "Не удалось найти услугу — возможно, она была удалена.",
            reply_markup=admin_kb.admin_menu_kb(),
        )
        return
    await message.answer(
        f"✅ Поле «{FIELD_LABELS[field]}» обновлено!\n\n"
        f"Услуга: <b>{service.title}</b>\n"
        f"Описание: {service.description}\n"
        f"Цена: {service.price}₽\n"
        f"Длительность: {service.duration_minutes} мин",
        reply_markup=admin_kb.admin_menu_kb(),
    )


# ---------------------------------------------------------------------------
# Расписание записи: мастер сам открывает дни/время
# ---------------------------------------------------------------------------

@router.message(F.text == "🛠 Расписание записи")
async def schedule_menu_start(message: Message) -> None:
    await message.answer(
        "Управление расписанием записи:",
        reply_markup=admin_kb.schedule_menu_kb(),
    )


# --- Открытие одного дня -----------------------------------------------------

@router.callback_query(F.data == "sched_open_day")
async def open_day_start(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(AdminStates.opening_day_input)
    await callback.message.edit_text(
        "Введите дату, которую хотите открыть для записи (формат ДД.ММ.ГГГГ):"
    )
    await callback.answer()


@router.message(AdminStates.opening_day_input, F.text)
async def open_day_pick_times(message: Message, state: FSMContext) -> None:
    parsed_date = parse_date_input(message.text)
    if parsed_date is None:
        await message.answer("Не удалось распознать дату. Введите в формате ДД.ММ.ГГГГ, например 25.12.2026:")
        return
    if parsed_date < date_type.today():
        await message.answer("Эта дата уже в прошлом. Введите будущую дату:")
        return

    await state.update_data(open_day_date=parsed_date.isoformat(), open_day_selected=[])
    await state.set_state(AdminStates.opening_day_toggle)
    await message.answer(
        f"Отметьте время, которое хотите открыть на {parsed_date.strftime('%d.%m.%Y')}, "
        "затем нажмите «Сохранить»:",
        reply_markup=admin_kb.toggle_times_kb(client_kb.AVAILABLE_TIMES, [], "save_open_day"),
    )


@router.callback_query(AdminStates.opening_day_toggle, F.data.startswith("toggle_time:"))
async def open_day_toggle_time(callback: CallbackQuery, state: FSMContext) -> None:
    chosen_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected: list[str] = data.get("open_day_selected", [])
    if chosen_time in selected:
        selected.remove(chosen_time)
    else:
        selected.append(chosen_time)
    await state.update_data(open_day_selected=selected)
    await callback.message.edit_reply_markup(
        reply_markup=admin_kb.toggle_times_kb(client_kb.AVAILABLE_TIMES, selected, "save_open_day")
    )
    await callback.answer()


@router.callback_query(AdminStates.opening_day_toggle, F.data == "save_open_day")
async def open_day_save(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list[str] = data.get("open_day_selected", [])
    if not selected:
        await callback.answer("Выберите хотя бы одно время", show_alert=True)
        return

    parsed_date = date_type.fromisoformat(data["open_day_date"])
    for t in selected:
        await db.add_available_slot(parsed_date, t)

    await state.clear()
    await callback.message.edit_text(
        f"✅ День {parsed_date.strftime('%d.%m.%Y')} открыт для записи: {', '.join(sorted(selected))}."
    )
    await callback.message.answer("Главное меню:", reply_markup=admin_kb.admin_menu_kb())
    await callback.answer()


# --- Открытие целого месяца --------------------------------------------------

@router.callback_query(F.data == "sched_open_month")
async def open_month_start(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "Выберите месяц, который хотите открыть для записи:",
        reply_markup=admin_kb.month_picker_kb(callback_prefix="sched_month"),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("sched_month:"))
async def open_month_pick_times(callback: CallbackQuery, state: FSMContext) -> None:
    year_str, month_str = callback.data.split(":")[1].split("-")
    await state.update_data(open_month_year=int(year_str), open_month_month=int(month_str), open_month_selected=[])
    await state.set_state(AdminStates.opening_month_toggle)
    label = f"{admin_kb.RU_MONTHS[int(month_str)]} {year_str}"
    await callback.message.edit_text(
        f"Отметьте время, которое хотите открыть <b>каждый день</b> в {label}, "
        "затем нажмите «Сохранить»:",
        reply_markup=admin_kb.toggle_times_kb(client_kb.AVAILABLE_TIMES, [], "save_open_month"),
    )
    await callback.answer()


@router.callback_query(AdminStates.opening_month_toggle, F.data.startswith("toggle_time:"))
async def open_month_toggle_time(callback: CallbackQuery, state: FSMContext) -> None:
    chosen_time = callback.data.split(":", 1)[1]
    data = await state.get_data()
    selected: list[str] = data.get("open_month_selected", [])
    if chosen_time in selected:
        selected.remove(chosen_time)
    else:
        selected.append(chosen_time)
    await state.update_data(open_month_selected=selected)
    await callback.message.edit_reply_markup(
        reply_markup=admin_kb.toggle_times_kb(client_kb.AVAILABLE_TIMES, selected, "save_open_month")
    )
    await callback.answer()


@router.callback_query(AdminStates.opening_month_toggle, F.data == "save_open_month")
async def open_month_save(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    selected: list[str] = data.get("open_month_selected", [])
    if not selected:
        await callback.answer("Выберите хотя бы одно время", show_alert=True)
        return

    year, month = data["open_month_year"], data["open_month_month"]
    days_affected = await db.open_month_bulk(year, month, sorted(selected))
    await state.clear()

    label = f"{admin_kb.RU_MONTHS[month]} {year}"
    if days_affected == 0:
        await callback.message.edit_text(f"В {label} не осталось дней, которые можно открыть (уже в прошлом).")
    else:
        await callback.message.edit_text(
            f"✅ Открыто {days_affected} дн. в {label} со временем: {', '.join(sorted(selected))}."
        )
    await callback.message.answer("Главное меню:", reply_markup=admin_kb.admin_menu_kb())
    await callback.answer()


# --- Просмотр и удаление открытых дней/слотов -------------------------------

@router.callback_query(F.data == "sched_view_days")
async def view_open_days(callback: CallbackQuery) -> None:
    open_dates = await db.get_open_dates_admin(from_date=date_type.today())
    if not open_dates:
        await callback.message.edit_text("Пока нет открытых дней для записи.")
        await callback.answer()
        return
    await callback.message.edit_text(
        "Открытые дни (в скобках — число слотов). Нажмите на день, чтобы управлять им:",
        reply_markup=admin_kb.open_days_list_kb(open_dates),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("view_day:"))
async def view_day_slots(callback: CallbackQuery) -> None:
    iso_date = callback.data.split(":")[1]
    parsed_date = date_type.fromisoformat(iso_date)
    times = await db.get_available_times_for_date(parsed_date)
    if not times:
        await callback.message.edit_text(f"На {parsed_date.strftime('%d.%m.%Y')} больше нет открытых слотов.")
        await callback.answer()
        return
    await callback.message.edit_text(
        f"Слоты на {parsed_date.strftime('%d.%m.%Y')}. Нажмите, чтобы закрыть конкретное время или весь день:",
        reply_markup=admin_kb.day_slots_manage_kb(iso_date, times),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_slot:"))
async def remove_slot_confirm(callback: CallbackQuery) -> None:
    _, iso_date, chosen_time = callback.data.split(":", 2)
    parsed_date = date_type.fromisoformat(iso_date)

    if await db.is_slot_booked(parsed_date, chosen_time):
        await callback.answer(
            "Нельзя закрыть: на это время уже есть запись клиента. Сначала отмените её.",
            show_alert=True,
        )
        return

    await db.remove_available_slot(parsed_date, chosen_time)
    remaining_times = await db.get_available_times_for_date(parsed_date)
    if remaining_times:
        await callback.message.edit_text(
            f"✅ Время {chosen_time} на {parsed_date.strftime('%d.%m.%Y')} закрыто.\n\n"
            f"Оставшиеся слоты на этот день:",
            reply_markup=admin_kb.day_slots_manage_kb(iso_date, remaining_times),
        )
    else:
        await callback.message.edit_text(
            f"✅ Время {chosen_time} на {parsed_date.strftime('%d.%m.%Y')} закрыто. "
            "На этот день больше нет открытых слотов."
        )
    await callback.answer()


@router.callback_query(F.data.startswith("remove_day:"))
async def remove_day_confirm(callback: CallbackQuery) -> None:
    iso_date = callback.data.split(":")[1]
    parsed_date = date_type.fromisoformat(iso_date)

    booked_today = await db.get_bookings_by_date(parsed_date)
    if booked_today:
        await callback.answer(
            "Нельзя закрыть день: на него есть активные записи. Сначала отмените их.",
            show_alert=True,
        )
        return

    removed_count = await db.remove_day_entirely(parsed_date)
    await callback.message.edit_text(
        f"✅ День {parsed_date.strftime('%d.%m.%Y')} закрыт для записи (удалено слотов: {removed_count})."
    )
    await callback.answer()
