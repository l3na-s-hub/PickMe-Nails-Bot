from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from config import config
from database import requests as db
from keyboards.client_kb import main_menu_kb

router = Router()

WELCOME_TEXT = (
    "👋 Привет! Я — мастер маникюра <b>PickMe Nails</b> 💅\n\n"
    "Здесь вы можете:\n"
    "💅 Записаться ко мне на маникюр\n"
    "📋 Посмотреть свои записи\n"
    "💰 Узнать мои цены на услуги\n"
    "📞 Найти мои контакты\n\n"
    "Выберите пункт меню ниже 👇"
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await db.get_or_create_user(
        message.from_user.id,
        message.from_user.full_name or "Без имени",
        message.from_user.username,
    )
    if config.welcome_photo_url:
        await message.answer_photo(
            photo=config.welcome_photo_url,
            caption=WELCOME_TEXT,
            reply_markup=main_menu_kb(),
        )
    else:
        await message.answer(WELCOME_TEXT, reply_markup=main_menu_kb())


@router.message(Command("cancel"))
@router.message(F.text.in_({"🚫 Отмена", "🔙 Выйти из админки"}))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    current_state = await state.get_state()
    if current_state is None and message.text not in {"🔙 Выйти из админки"}:
        await message.answer("Нечего отменять 🙂", reply_markup=main_menu_kb())
        return
    await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb())
