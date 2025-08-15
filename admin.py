from aiogram import Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from database import db
from config import ADMIN_ID

admin_router = Router()


class AdminStates(StatesGroup):
    WAITING_BOOKING_ID = State()
    WAITING_NEW_INVITE = State()


def _admin_only(user_id: int) -> bool:
    return ADMIN_ID is not None and user_id == ADMIN_ID


@admin_router.message(Command("admin"))
async def admin_panel(message: types.Message):
    if not _admin_only(message.from_user.id):
        return await message.answer("Доступ запрещён")

    await message.answer(
        "Админ-панель:\n"
        "/bookings - Все бронирования\n"
        "/drivers - Список водителей\n"
        "/cancel_booking - Отменить бронь\n"
        "/add_invite - Создать инвайт-код\n"
        "/cleanup - Удалить не активные"
    )


@admin_router.message(Command("bookings"))
async def show_bookings(message: types.Message):
    if not _admin_only(message.from_user.id):
        return await message.answer("Доступ запрещён")

    bookings = db.get_all_bookings()
    if not bookings:
        return await message.answer("Нет активных бронирований")

    text = "Активные бронирования:\n\n"
    for b in bookings:
        driver = db.get_driver(b.driver_id)
        user = b.user  # безопасно: get_all_bookings делает joinedload(User)
        text += (
            f"🆔 ID: {b.id}\n"
            f"👤 Пользователь: {user.name if user else '—'} (@{user.username if user else '—'})\n"
            f"🚗 Водитель: {driver.name if driver else 'Неизвестен'}\n"
            f"📅 Время: {b.booking_time.strftime('%d.%m.%Y %H:%M')} - {b.end_time.strftime('%H:%M')}\n"
            f"📝 Заметки: {b.notes if b.notes else 'нет'}\n"
            f"🔹 Статус: {b.status}\n\n"
        )

    await message.answer(text[:4000])


@admin_router.message(Command("add_invite"))
async def add_invite_cmd(message: types.Message, state: FSMContext):
    if not _admin_only(message.from_user.id):
        return await message.answer("Доступ запрещён")

    await message.answer("Введите новый инвайт-код:")
    await state.set_state(AdminStates.WAITING_NEW_INVITE)


@admin_router.message(AdminStates.WAITING_NEW_INVITE)
async def process_new_invite(message: types.Message, state: FSMContext):
    if not _admin_only(message.from_user.id):
        await state.clear()
        return await message.answer("Доступ запрещён")

    code = message.text.strip()
    if db.add_invite(code):
        await message.answer(f"Инвайт-код '{code}' успешно добавлен")
    else:
        await message.answer("Ошибка: такой код уже существует")
    await state.clear()


@admin_router.message(Command("drivers"))
async def show_drivers(message: types.Message):
    if not _admin_only(message.from_user.id):
        return await message.answer("Доступ запрещён")

    drivers = db.get_all_drivers()
    if not drivers:
        return await message.answer("Активных водителей нет")

    text = "Список водителей:\n\n" + "\n".join(
        f"{d.id}. {d.name} ({d.phone})" for d in drivers
    )
    await message.answer(text)


@admin_router.message(Command("cancel_booking"))
async def cancel_booking_cmd(message: types.Message, state: FSMContext):
    if not _admin_only(message.from_user.id):
        return await message.answer("Доступ запрещён")

    await message.answer("Введите ID брони для отмены:")
    await state.set_state(AdminStates.WAITING_BOOKING_ID)


@admin_router.message(AdminStates.WAITING_BOOKING_ID)
async def process_booking_id(message: types.Message, state: FSMContext):
    if not _admin_only(message.from_user.id):
        await state.clear()
        return await message.answer("Доступ запрещён")

    try:
        booking_id = int(message.text.strip())
        if db.cancel_booking(booking_id):
            await message.answer(f"Бронирование #{booking_id} отменено")
        else:
            await message.answer("Бронирование не найдено")
    except ValueError:
        await message.answer("Введите корректный ID (число)")
    await state.clear()

    @admin_router.message(Command("cleanup"))
    async def cleanup_bookings(message: types.Message):
        if not _admin_only(message.from_user.id):
            return await message.answer("Доступ запрещён")

        deleted_count = db.delete_canceled_bookings()
        await message.answer(f"Удалено {deleted_count} отмененных бронирований")
