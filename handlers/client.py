from datetime import date as date_type, datetime

from aiogram import F, Router
from aiogram.enums import ContentType
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import config
from database import requests as db
from keyboards import client_kb
from states.booking import BookingStates

router = Router()


def client_display_name(user) -> str:
    """Формирует строку с именем и username клиента для уведомлений мастеру."""
    username_part = f"@{user.username}" if getattr(user, "username", None) else "нет username"
    return f"{user.full_name} ({username_part})"


# ---------------------------------------------------------------------------
# Цены и контакты
# ---------------------------------------------------------------------------

@router.message(F.text == "💰 Цены и услуги")
async def show_services_list(message: Message) -> None:
    services = await db.get_all_services()
    if not services:
        await message.answer("Пока нет доступных услуг. Загляните позже 🙏")
        return
    lines = ["<b>💅 Мои услуги:</b>\n"]
    for s in services:
        lines.append(
            f"• <b>{s.title}</b>\n"
            f"  {s.description}\n"
            f"  Цена: <b>{s.price}₽</b> | Время: {s.duration_minutes} мин\n"
        )
    text = "\n".join(lines)
    if config.services_photo_url:
        await message.answer_photo(photo=config.services_photo_url, caption=text)
    else:
        await message.answer(text)


@router.message(F.text == "📞 Контакты")
async def show_contacts(message: Message) -> None:
    await message.answer(
        "<b>📍 Мои контакты:</b>\n\n"
        "Адрес: г. Екатеринбург, ул. Куйбышева, д. 139\n"
        "Телефон: +7 (992) 331-99-36\n"
        "Telegram: @mc_yzbek\n\n"
        "Пилим ногти, а не мужиков💅"
    )


# ---------------------------------------------------------------------------
# Запись на услугу (FSM)
# ---------------------------------------------------------------------------

@router.message(F.text == "💅 Записаться")
async def start_booking(message: Message, state: FSMContext) -> None:
    services = await db.get_all_services()
    if not services:
        await message.answer("К сожалению, сейчас нет доступных услуг для записи.")
        return
    await state.set_state(BookingStates.waiting_service)
    await message.answer(
        "Выберите услугу, на которую хотите записаться:",
        reply_markup=client_kb.services_inline_kb(services),
    )


@router.callback_query(BookingStates.waiting_service, F.data.startswith("service:"))
async def choose_service(callback: CallbackQuery, state: FSMContext) -> None:
    service_id = int(callback.data.split(":")[1])
    service = await db.get_service_by_id(service_id)
    if service is None:
        await callback.answer("Услуга не найдена", show_alert=True)
        return

    available_dates = await db.get_available_dates_with_free_slot(date_type.today(), limit=7)
    if not available_dates:
        await callback.message.edit_text(
            "😔 Пока нет открытых дат для записи. Загляните чуть позже — я скоро открою новые слоты!"
        )
        await callback.message.answer("Главное меню:", reply_markup=client_kb.main_menu_kb())
        await state.clear()
        await callback.answer()
        return

    await state.update_data(service_id=service.id, service_title=service.title, service_price=service.price)
    await state.set_state(BookingStates.waiting_date)
    await callback.message.edit_text(
        f"Услуга: <b>{service.title}</b>\n\nТеперь выберите удобную дату:",
        reply_markup=client_kb.dates_inline_kb(available_dates),
    )
    await callback.answer()


@router.callback_query(BookingStates.waiting_date, F.data.startswith("date:"))
async def choose_date(callback: CallbackQuery, state: FSMContext) -> None:
    date_str = callback.data.split(":")[1]
    chosen_date = date_type.fromisoformat(date_str)
    data = await state.get_data()

    open_times = await db.get_available_times_for_date(chosen_date)
    busy_times = await db.get_busy_times(data["service_id"], chosen_date)

    # Если выбранный день — это сегодня, фильтруем слоты времени, которые уже прошли
    if chosen_date == date_type.today():
        current_time_str = datetime.now().strftime("%H:%M") # Получаем текущее время сервера
        open_times = [t for t in open_times if t > current_time_str] 

    free_slots = [t for t in open_times if t not in busy_times]
    if not free_slots:
        await callback.answer("На эту дату свободных слотов не осталось, выберите другую 🙏", show_alert=True)
        return

    await state.update_data(booking_date=date_str)
    await state.set_state(BookingStates.waiting_time)
    await callback.message.edit_text(
        f"Дата: <b>{chosen_date.strftime('%d.%m.%Y')}</b>\n\nВыберите удобное время:",
        reply_markup=client_kb.times_inline_kb(open_times, busy_times),
    )
    await callback.answer()


@router.callback_query(BookingStates.waiting_time, F.data.startswith("time:"))
async def choose_time(callback: CallbackQuery, state: FSMContext) -> None:
    chosen_time = callback.data.split(":", 1)[1]
    await state.update_data(booking_time=chosen_time)

    user = await db.get_user_by_telegram_id(callback.from_user.id)
    if user and user.phone_number:
        await state.update_data(phone_number=user.phone_number)
        await state.set_state(BookingStates.confirm)
        summary = await build_summary_text(state)
        await callback.message.edit_text(summary)
        await callback.message.answer("Проверьте данные записи:", reply_markup=client_kb.confirm_booking_kb())
    else:
        await state.set_state(BookingStates.waiting_phone)
        await callback.message.edit_text("Осталось указать номер телефона для связи 📱")
        await callback.message.answer(
            "Нажмите кнопку ниже, чтобы отправить свой номер телефона:",
            reply_markup=client_kb.phone_request_kb(),
        )
    await callback.answer()


@router.message(BookingStates.waiting_phone, F.content_type == ContentType.CONTACT)
async def get_phone_contact(message: Message, state: FSMContext) -> None:
    phone_number = message.contact.phone_number
    await db.update_user_phone(message.from_user.id, phone_number)
    await state.update_data(phone_number=phone_number)
    await state.set_state(BookingStates.confirm)
    summary = await build_summary_text(state)
    await message.answer(summary, reply_markup=client_kb.cancel_kb())
    await message.answer("Проверьте данные записи:", reply_markup=client_kb.confirm_booking_kb())


@router.message(BookingStates.waiting_phone, F.text)
async def get_phone_text(message: Message, state: FSMContext) -> None:
    phone_number = message.text.strip()
    digits_only = phone_number.replace("+", "").replace(" ", "").replace("-", "")
    if not digits_only.isdigit() or len(digits_only) < 7:
        await message.answer(
            "Похоже, это не похоже на номер телефона. Попробуйте ещё раз или воспользуйтесь кнопкой ниже.",
            reply_markup=client_kb.phone_request_kb(),
        )
        return
    await db.update_user_phone(message.from_user.id, phone_number)
    await state.update_data(phone_number=phone_number)
    await state.set_state(BookingStates.confirm)
    summary = await build_summary_text(state)
    await message.answer(summary, reply_markup=client_kb.cancel_kb())
    await message.answer("Проверьте данные записи:", reply_markup=client_kb.confirm_booking_kb())


async def build_summary_text(state: FSMContext) -> str:
    data = await state.get_data()
    chosen_date = date_type.fromisoformat(data["booking_date"])
    return (
        "<b>📝 Ваша запись:</b>\n\n"
        f"Услуга: <b>{data['service_title']}</b>\n"
        f"Цена: <b>{data['service_price']}₽</b>\n"
        f"Дата: <b>{chosen_date.strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{data['booking_time']}</b>\n"
        f"Телефон: <b>{data['phone_number']}</b>\n"
    )


@router.callback_query(BookingStates.confirm, F.data == "confirm_booking")
async def confirm_booking(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    chosen_date = date_type.fromisoformat(data["booking_date"])

    # Повторная проверка на случай, если слот заняли/закрыли, пока клиент оформлял запись.
    open_times = await db.get_available_times_for_date(chosen_date)
    busy_times = await db.get_busy_times(data["service_id"], chosen_date)
    if data["booking_time"] not in open_times or data["booking_time"] in busy_times:
        await callback.message.edit_text(
            "😔 Это время только что стало недоступно. Пожалуйста, начните запись заново."
        )
        await callback.message.answer("Главное меню:", reply_markup=client_kb.main_menu_kb())
        await state.clear()
        await callback.answer()
        return

    user = await db.get_or_create_user(
        callback.from_user.id,
        callback.from_user.full_name or "Без имени",
        callback.from_user.username,
    )

    await db.create_booking(
        user_id=user.id,
        service_id=data["service_id"],
        booking_date=chosen_date,
        booking_time=data["booking_time"],
    )

    await callback.message.edit_text(
        "✅ <b>Вы успешно записаны!</b>\n\n"
        f"Услуга: <b>{data['service_title']}</b>\n"
        f"Дата: <b>{chosen_date.strftime('%d.%m.%Y')}</b>\n"
        f"Время: <b>{data['booking_time']}</b>\n\n"
        "Жду вас! 💅"
    )
    await callback.message.answer("Главное меню:", reply_markup=client_kb.main_menu_kb())

    admin_text = (
        "🆕 <b>Новая запись!</b>\n\n"
        f"Клиент: {client_display_name(user)}\n"
        f"Телефон: {data['phone_number']}\n"
        f"Услуга: {data['service_title']}\n"
        f"Дата: {chosen_date.strftime('%d.%m.%Y')}\n"
        f"Время: {data['booking_time']}\n"
    )
    for admin_id in config.admin_ids:
        try:
            await callback.bot.send_message(admin_id, admin_text)
        except Exception:
            pass

    await state.clear()
    await callback.answer()


@router.callback_query(F.data == "cancel_booking_flow")
async def cancel_booking_flow(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await callback.message.edit_text("Запись отменена.")
    await callback.message.answer("Главное меню:", reply_markup=client_kb.main_menu_kb())
    await callback.answer()


# ---------------------------------------------------------------------------
# Мои записи
# ---------------------------------------------------------------------------

@router.message(F.text == "📋 Мои записи")
async def show_my_bookings(message: Message) -> None:
    bookings = await db.get_user_active_bookings(message.from_user.id)
    if not bookings:
        await message.answer("У вас пока нет активных записей.")
        return
    await message.answer("<b>📋 Ваши активные записи:</b>")
    for b in bookings:
        text = (
            f"💅 {b.service.title}\n"
            f"📅 {b.booking_date.strftime('%d.%m.%Y')} в {b.booking_time}\n"
            f"💰 {b.service.price}₽"
        )
        await message.answer(text, reply_markup=client_kb.my_booking_kb(b.id))


@router.callback_query(F.data.startswith("cancel_my_booking:"))
async def cancel_my_booking(callback: CallbackQuery) -> None:
    booking_id = int(callback.data.split(":")[1])
    booking = await db.cancel_booking(booking_id)
    if booking is None:
        await callback.answer("Запись не найдена", show_alert=True)
        return
    await callback.message.edit_text(
        f"❌ Запись на {booking.booking_date.strftime('%d.%m.%Y')} в {booking.booking_time} отменена."
    )
    await callback.answer("Запись отменена")

    admin_text = (
        "⚠️ <b>Клиент отменил запись</b>\n\n"
        f"Клиент: {client_display_name(booking.user)}\n"
        f"Услуга: {booking.service.title}\n"
        f"Дата: {booking.booking_date.strftime('%d.%m.%Y')}\n"
        f"Время: {booking.booking_time}\n"
    )
    for admin_id in config.admin_ids:
        try:
            await callback.bot.send_message(admin_id, admin_text)
        except Exception:
            pass
