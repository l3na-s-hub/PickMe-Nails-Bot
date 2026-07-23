from datetime import date as date_type
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(255))
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    phone_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")

    def __repr__(self) -> str:
        return f"<User id={self.id} telegram_id={self.telegram_id} name={self.full_name!r}>"


class Service(Base):
    __tablename__ = "services"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    price: Mapped[int] = mapped_column(Integer)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60)

    bookings: Mapped[list["Booking"]] = relationship(back_populates="service")

    def __repr__(self) -> str:
        return f"<Service id={self.id} title={self.title!r} price={self.price}>"


class Booking(Base):
    __tablename__ = "bookings"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    service_id: Mapped[int] = mapped_column(ForeignKey("services.id"))
    booking_date: Mapped[date_type] = mapped_column(Date)
    booking_time: Mapped[str] = mapped_column(String(5))
    status: Mapped[str] = mapped_column(String(20), default="confirmed")
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped["User"] = relationship(back_populates="bookings")
    service: Mapped["Service"] = relationship(back_populates="bookings")

    def __repr__(self) -> str:
        return (
            f"<Booking id={self.id} user_id={self.user_id} service_id={self.service_id} "
            f"date={self.booking_date} time={self.booking_time} status={self.status!r}>"
        )


class AvailableSlot(Base):
    """
    Слоты, которые мастер САМ открыл для записи.

    По умолчанию в базе нет ни одного слота - клиенты не видят вообще никаких
    дат/времени, пока мастер не откроет их через админ-панель (по одному дню
    или сразу на весь месяц).
    """

    __tablename__ = "available_slots"
    __table_args__ = (UniqueConstraint("slot_date", "slot_time", name="uq_available_slot_date_time"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    slot_date: Mapped[date_type] = mapped_column(Date, index=True)
    slot_time: Mapped[str] = mapped_column(String(5))

    def __repr__(self) -> str:
        return f"<AvailableSlot date={self.slot_date} time={self.slot_time!r}>"
