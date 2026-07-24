import calendar
from datetime import date as date_type
from datetime import datetime, timedelta

from sqlalchemy import and_, not_, select, delete 
from sqlalchemy.orm import selectinload

from database.db_main import async_session
from database.models import AvailableSlot, Booking, Service, User


# ---------------------------------------------------------------------------
# Пользователи
# ---------------------------------------------------------------------------

async def get_or_create_user(telegram_id: int, full_name: str, username: str | None = None) -> User:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is None:
            user = User(telegram_id=telegram_id, full_name=full_name, username=username)
            session.add(user)
            await session.commit()
        elif username is not None and user.username != username:
            user.username = username
            await session.commit()
        return user


async def get_user_by_telegram_id(telegram_id: int) -> User | None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


async def update_user_phone(telegram_id: int, phone_number: str) -> None:
    async with async_session() as session:
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.phone_number = phone_number
            await session.commit()


# ---------------------------------------------------------------------------
# Услуги
# ---------------------------------------------------------------------------

async def get_all_services() -> list[Service]:
    async with async_session() as session:
        result = await session.execute(select(Service).order_by(Service.id))
        return list(result.scalars().all())


async def get_service_by_id(service_id: int) -> Service | None:
    async with async_session() as session:
        result = await session.execute(select(Service).where(Service.id == service_id))
        return result.scalar_one_or_none()


async def add_service(title: str, description: str, price: int, duration_minutes: int) -> Service:
    async with async_session() as session:
        service = Service(
            title=title,
            description=description,
            price=price,
            duration_minutes=duration_minutes,
        )
        session.add(service)
        await session.commit()
        return service


async def update_service(
    service_id: int,
    *,
    title: str | None = None,
    description: str | None = None,
    price: int | None = None,
    duration_minutes: int | None = None,
) -> Service | None:
    """Обновляет только переданные поля услуги, остальные остаются без изменений."""
    async with async_session() as session:
        result = await session.execute(select(Service).where(Service.id == service_id))
        service = result.scalar_one_or_none()
        if service is None:
            return None
        if title is not None:
            service.title = title
        if description is not None:
            service.description = description
        if price is not None:
            service.price = price
        if duration_minutes is not None:
            service.duration_minutes = duration_minutes
        await session.commit()
        return service


async def delete_service(service_id: int) -> bool:
    async with async_session() as session:
        result = await session.execute(select(Service).where(Service.id == service_id))
        service = result.scalar_one_or_none()
        if service is None:
            return False
        await session.delete(service)
        await session.commit()
        return True


# ---------------------------------------------------------------------------
# Записи (Booking)
# ---------------------------------------------------------------------------


async def get_free_slots_for_month(target_year: int, target_month: int) -> dict[date_type, list[str]]:
    """
    Возвращает словарь со свободными окнами в указанном месяце.
    Формат: {datetime.date(2026, 7, 21): ['12:30', '14:00', '16:00'], ...}
    """
    async with async_session() as session:
        # Подзапрос: ищем подтвержденные брони для конкретной даты и времени
        booked_exists = select(Booking).where(
            and_(
                Booking.booking_date == AvailableSlot.slot_date,
                Booking.booking_time == AvailableSlot.slot_time,
                Booking.status == "confirmed" # учитываем только активные записи
            )
        ).exists()

        # Основной запрос: берем слоты, которых нет в подтвержденных бронях
        # и которые больше или равны сегодняшнему дню
        query = select(AvailableSlot).where(
            and_(
                AvailableSlot.slot_date >= date_type.today(),
                not_(booked_exists)
            )
        ).order_by(AvailableSlot.slot_date, AvailableSlot.slot_time)

        result = await session.execute(query)
        slots = result.scalars().all()

        # Группируем по датам, отфильтровывая нужный месяц и год
        schedule = {}
        for slot in slots:
            if slot.slot_date.year == target_year and slot.slot_date.month == target_month:
                if slot.slot_date not in schedule:
                    schedule[slot.slot_date] = []
                schedule[slot.slot_date].append(slot.slot_time)

        return schedule
    

async def get_busy_times(service_id: int, booking_date: date_type) -> list[str]:
    """Возвращает список уже занятых временных слотов на указанную дату."""
    async with async_session() as session:
        result = await session.execute(
            select(Booking.booking_time).where(
                Booking.booking_date == booking_date,
                Booking.status != "cancelled",
            )
        )
        return [row[0] for row in result.all()]


async def create_booking(user_id: int, service_id: int, booking_date: date_type, booking_time: str) -> Booking:
    async with async_session() as session:
        booking = Booking(
            user_id=user_id,
            service_id=service_id,
            booking_date=booking_date,
            booking_time=booking_time,
            status="confirmed",
        )
        session.add(booking)
        await session.commit()

        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(Booking.id == booking.id)
        )
        return result.scalar_one()


async def get_booking_by_id(booking_id: int) -> Booking | None:
    async with async_session() as session:
        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(Booking.id == booking_id)
        )
        return result.scalar_one_or_none()


async def get_user_active_bookings(telegram_id: int) -> list[Booking]:
    """Активные (подтверждённые, ещё не прошедшие) записи конкретного пользователя."""
    async with async_session() as session:
        result = await session.execute(
            select(Booking)
            .join(User)
            .options(selectinload(Booking.service))
            .where(
                User.telegram_id == telegram_id,
                Booking.status == "confirmed",
                Booking.booking_date >= date_type.today(),
            )
            .order_by(Booking.booking_date, Booking.booking_time)
        )
        return list(result.scalars().all())


async def cancel_booking(booking_id: int) -> Booking | None:
    async with async_session() as session:
        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(Booking.id == booking_id)
        )
        booking = result.scalar_one_or_none()
        if booking is None:
            return None
        booking.status = "cancelled"
        await session.commit()
        return booking


async def get_bookings_by_date(booking_date: date_type) -> list[Booking]:
    """Все подтверждённые записи на указанную дату (для админ-панели)."""
    async with async_session() as session:
        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(
                Booking.booking_date == booking_date,
                Booking.status == "confirmed",
            )
            .order_by(Booking.booking_time)
        )
        return list(result.scalars().all())


async def is_slot_booked(check_date: date_type, check_time: str) -> bool:
    async with async_session() as session:
        result = await session.execute(
            select(Booking).where(
                Booking.booking_date == check_date,
                Booking.booking_time == check_time,
                Booking.status != "cancelled",
            )
        )
        return result.scalar_one_or_none() is not None


# ---------------------------------------------------------------------------
# Просмотр записей за месяц и статистика (для админ-панели)
# ---------------------------------------------------------------------------

async def get_bookings_by_month(year: int, month: int) -> list[Booking]:
    """Все подтверждённые записи за указанный месяц, отсортированные по дате/времени."""
    first_day = date_type(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date_type(year, month, last_day_num)

    async with async_session() as session:
        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(
                Booking.booking_date >= first_day,
                Booking.booking_date <= last_day,
                Booking.status == "confirmed",
            )
            .order_by(Booking.booking_date, Booking.booking_time)
        )
        return list(result.scalars().all())


async def get_monthly_stats(year: int, month: int) -> dict:
    """Количество подтверждённых записей и суммарная выручка за месяц."""
    bookings = await get_bookings_by_month(year, month)
    total_bookings = len(bookings)
    total_revenue = sum(b.service.price for b in bookings)
    return {"total_bookings": total_bookings, "total_revenue": total_revenue}


async def get_free_dates_set(target_year: int, target_month: int) -> set[date_type]:
    """
    Возвращает множество дат (set[date]), на которые есть хотя бы один свободный слот в указанном месяце.
    """
    async with async_session() as session:
        booked_exists = select(Booking).where(
            and_(
                Booking.booking_date == AvailableSlot.slot_date,
                Booking.booking_time == AvailableSlot.slot_time,
                Booking.status == "confirmed"
            )
        ).exists()

        query = select(AvailableSlot.slot_date).where(
            and_(
                AvailableSlot.slot_date >= date_type.today(),
                not_(booked_exists)
            )
        ).distinct()

        result = await session.execute(query)
        all_free_dates = result.scalars().all()

        # Фильтруем только нужный месяц и год и возвращаем как set для быстрого поиска
        return {
            d for d in all_free_dates 
            if d.year == target_year and d.month == target_month
        }


# ---------------------------------------------------------------------------
# Расписание: мастер сам открывает дни и время для записи (allow-list).
# Изначально таблица пуста - ни одной даты клиенты не видят, пока мастер
# не откроет её вручную (по одному дню или сразу на весь месяц).
# ---------------------------------------------------------------------------


async def get_slots_for_date(chosen_date_str: str) -> list[str]:
    target_date = datetime.strptime(chosen_date_str, "%Y-%m-%d").date()
    async with async_session() as session:
        query = select(AvailableSlot.slot_time).where(AvailableSlot.slot_date == target_date)
        result = await session.execute(query)
        return [row[0] for row in result.all()]

# async def add_available_slot(slot_date: date_type, slot_time: str) -> None:
#     """Открывает конкретное время в конкретный день. Дубликаты игнорируются."""
#     async with async_session() as session:
#         result = await session.execute(
#             select(AvailableSlot).where(
#                 AvailableSlot.slot_date == slot_date,
#                 AvailableSlot.slot_time == slot_time,
#             )
#         )
#         if result.scalar_one_or_none() is not None:
#             return
#         session.add(AvailableSlot(slot_date=slot_date, slot_time=slot_time))
#         await session.commit()


async def add_available_slot(chosen_date_str: str, slot_time: str) -> None:
    target_date = datetime.strptime(chosen_date_str, "%Y-%m-%d").date()
    async with async_session() as session:
        check_query = select(AvailableSlot).where(
            AvailableSlot.slot_date == target_date,
            AvailableSlot.slot_time == slot_time
        )
        exists = await session.execute(check_query)
        if exists.scalar_one_or_none() is None:
            new_slot = AvailableSlot(slot_date=target_date, slot_time=slot_time)
            session.add(new_slot)
            await session.commit()


async def open_month_bulk(year: int, month: int, times: list[str]) -> int:
    """
    Открывает переданные времена на каждый день месяца (начиная с сегодня,
    если месяц текущий). Возвращает количество затронутых дней.
    """
    first_day = date_type(year, month, 1)
    last_day_num = calendar.monthrange(year, month)[1]
    last_day = date_type(year, month, last_day_num)
    start_day = max(first_day, date_type.today())
    if start_day > last_day:
        return 0

    async with async_session() as session:
        existing_result = await session.execute(
            select(AvailableSlot.slot_date, AvailableSlot.slot_time).where(
                AvailableSlot.slot_date >= start_day,
                AvailableSlot.slot_date <= last_day,
            )
        )
        existing = set(existing_result.all())

        days_affected = 0
        current_day = start_day
        while current_day <= last_day:
            day_added = False
            for t in times:
                if (current_day, t) not in existing:
                    session.add(AvailableSlot(slot_date=current_day, slot_time=t))
                    day_added = True
            if day_added:
                days_affected += 1
            current_day += timedelta(days=1)

        await session.commit()
        return days_affected


# async def remove_available_slot(slot_date: date_type, slot_time: str) -> bool:
#     async with async_session() as session:
#         result = await session.execute(
#             select(AvailableSlot).where(
#                 AvailableSlot.slot_date == slot_date,
#                 AvailableSlot.slot_time == slot_time,
#             )
#         )
#         slot = result.scalar_one_or_none()
#         if slot is None:
#             return False
#         await session.delete(slot)
#         await session.commit()
#         return True


async def remove_available_slot(chosen_date_str: str, slot_time: str) -> None:
    target_date = datetime.strptime(chosen_date_str, "%Y-%m-%d").date()
    async with async_session() as session:
        query = delete(AvailableSlot).where(
            AvailableSlot.slot_date == target_date,
            AvailableSlot.slot_time == slot_time
        )
        await session.execute(query)
        await session.commit()


async def remove_day_entirely(slot_date: date_type) -> int:
    """Удаляет все открытые слоты за конкретный день. Возвращает число удалённых слотов."""
    async with async_session() as session:
        result = await session.execute(select(AvailableSlot).where(AvailableSlot.slot_date == slot_date))
        slots = list(result.scalars().all())
        for slot in slots:
            await session.delete(slot)
        await session.commit()
        return len(slots)


async def get_available_times_for_date(target_date: date_type) -> list[str]:
    """Все открытые мастером времена для даты (включая уже забронированные)."""
    async with async_session() as session:
        result = await session.execute(
            select(AvailableSlot.slot_time)
            .where(AvailableSlot.slot_date == target_date)
            .order_by(AvailableSlot.slot_time)
        )
        return [row[0] for row in result.all()]


async def get_open_dates_admin(from_date: date_type | None = None) -> list[tuple[date_type, int]]:
    """Список дат, у которых есть хотя бы один открытый слот, с количеством слотов (для админа)."""
    async with async_session() as session:
        query = select(AvailableSlot.slot_date, AvailableSlot.slot_time)
        if from_date is not None:
            query = query.where(AvailableSlot.slot_date >= from_date)
        result = await session.execute(query.order_by(AvailableSlot.slot_date))
        rows = result.all()

    counts: dict[date_type, int] = {}
    for slot_date, _ in rows:
        counts[slot_date] = counts.get(slot_date, 0) + 1
    return sorted(counts.items())


async def get_available_dates_with_free_slot(from_date: date_type, limit: int = 7) -> list[date_type]:
    """
    Ближайшие даты (не более `limit`), у которых мастер открыл запись и есть
    хотя бы один ещё не забронированный слот. Используется в клиентском сценарии.
    """
    async with async_session() as session:
        slots_result = await session.execute(
            select(AvailableSlot.slot_date, AvailableSlot.slot_time)
            .where(AvailableSlot.slot_date >= from_date)
            .order_by(AvailableSlot.slot_date, AvailableSlot.slot_time)
        )
        slots = slots_result.all()
        if not slots:
            return []

        min_date = slots[0][0]
        max_date = slots[-1][0]
        bookings_result = await session.execute(
            select(Booking.booking_date, Booking.booking_time).where(
                Booking.booking_date >= min_date,
                Booking.booking_date <= max_date,
                Booking.status != "cancelled",
            )
        )
        booked = set(bookings_result.all())

    dates_with_free_slot: list[date_type] = []
    seen: set[date_type] = set()
    for slot_date, slot_time in slots:
        if slot_date in seen:
            continue
        if (slot_date, slot_time) not in booked:
            dates_with_free_slot.append(slot_date)
            seen.add(slot_date)
        if len(dates_with_free_slot) >= limit:
            break
    return dates_with_free_slot


# ---------------------------------------------------------------------------
# Автоматические напоминания клиентам о записи
# ---------------------------------------------------------------------------

async def get_bookings_needing_reminder(hours_before: int = 2) -> list[Booking]:
    """
    Подтверждённые записи, которые начнутся в ближайшие `hours_before` часов
    и по которым напоминание ещё не отправлялось.
    """
    now = datetime.now()
    window_end = now + timedelta(hours=hours_before)

    async with async_session() as session:
        result = await session.execute(
            select(Booking)
            .options(selectinload(Booking.user), selectinload(Booking.service))
            .where(
                Booking.status == "confirmed",
                Booking.reminder_sent.is_(False),
                Booking.booking_date >= now.date(),
                Booking.booking_date <= window_end.date(),
            )
        )
        bookings = list(result.scalars().all())

    due_bookings = []
    for booking in bookings:
        booking_dt = datetime.combine(
            booking.booking_date,
            datetime.strptime(booking.booking_time, "%H:%M").time(),
        )
        if now <= booking_dt <= window_end:
            due_bookings.append(booking)
    return due_bookings


async def mark_reminder_sent(booking_id: int) -> None:
    async with async_session() as session:
        result = await session.execute(select(Booking).where(Booking.id == booking_id))
        booking = result.scalar_one_or_none()
        if booking is not None:
            booking.reminder_sent = True
            await session.commit()
