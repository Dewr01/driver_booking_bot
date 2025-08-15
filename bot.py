import asyncio
import logging
from datetime import datetime, timedelta
from aiogram import F, types, Router
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import dp, bot, ADMIN_ID, INVITE_CODE
from database import db
from keyboards import main_menu_kb, generate_dates_kb, generate_time_slots_kb, back_kb, get_calendar_kb
from admin import admin_router

logging.basicConfig(level=logging.INFO)

main_router = Router()


class BookingStates(StatesGroup):
    WAITING_INVITE = State()
    CHOOSING_DATE = State()
    CHOOSING_TIME = State()
    CHOOSING_END_TIME = State()
    ADDING_NOTES = State()
    CONFIRMATION = State()
    EDITING_BOOKING = State()


# Старт — отдельной командой, чтобы не перехватывать все сообщения
@main_router.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    user = db.get_user(message.from_user.id)
    if not user:
        await state.set_state(BookingStates.WAITING_INVITE)
        return await message.answer(
            "🔒 Только по приглашению.\n"
            "Введите код приглашения:",
            reply_markup=types.ReplyKeyboardRemove()
        )

    await message.answer(
        "Бронируйте моё время для Ваших поездок!\n"
        "Выберите действие в меню ниже:",
        reply_markup=main_menu_kb()
    )


# Обработчик инвайт-кода
@main_router.message(BookingStates.WAITING_INVITE)
async def process_invite_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if db.check_invite(code):
        db.use_invite(code)
        db.add_user(
            tg_id=message.from_user.id,
            name=message.from_user.full_name,
            username=message.from_user.username
        )
        await message.answer(
            "✅ Код приглашения принят!\n"
            "Теперь можно меня использовать.",
            reply_markup=main_menu_kb()
        )
        await state.clear()
    else:
        await message.answer("❌ Неверный код приглашения. Попробуйте ещё раз.")


# Главное меню
@main_router.message(F.text == '📅 Календарь бронирований')
async def show_calendar_menu(message: types.Message):
    await message.answer("Выберите действие:", reply_markup=get_calendar_kb())


@main_router.message(F.text == '📅 Показать календарь')
async def show_calendar(message: types.Message):
    await message.answer("Выберите дату:", reply_markup=generate_dates_kb())


@main_router.message(F.text == '📝 Мои бронирования')
async def show_user_bookings(message: types.Message):
    user = db.get_user(message.from_user.id)
    if not user:
        return await message.answer("Ошибка: пользователь не найден. Нажмите /start")

    bookings = db.get_user_bookings(user.id)
    if not bookings:
        return await message.answer("У вас нет активных бронирований", reply_markup=main_menu_kb())

    text = "📝 Ваши бронирования:\n\n"
    for booking in bookings:
        driver = db.get_driver(booking.driver_id)
        text += (
            f"📅 {booking.booking_time.strftime('%d.%m.%Y %H:%M')} - {booking.end_time.strftime('%H:%M')}\n"
            f"🚗 Водитель: {driver.name if driver else 'Кто-то из семьи'}\n"
            f"📝 Заметки: {booking.notes if booking.notes else 'нет'}\n"
            f"🆔 ID: {booking.id}\n\n"
        )

    await message.answer(text, reply_markup=main_menu_kb())


# Выбор даты (кнопки «Пн 12.08» и т.д.)
@main_router.message(F.text.regexp(r'^[А-Яа-я]{2} \d{2}\.\d{2}$'))
async def choose_date(message: types.Message, state: FSMContext):
    try:
        date_str = message.text.split()[1]
        date = datetime.strptime(date_str, "%d.%m").date()
        date = date.replace(year=datetime.now().year)
        if date < datetime.now().date():
            date = date.replace(year=datetime.now().year + 1)
    except ValueError:
        return await message.answer("Неверный формат даты. Выберите дату из списка.")

    user = db.get_user(message.from_user.id)
    if not user:
        return await message.answer("Ошибка: пользователь не найден. Нажмите /start")

    drivers = db.get_all_drivers()
    if not drivers:
        return await message.answer("Нет доступных водителей")

    driver_id = drivers[0].id
    await state.update_data(selected_date=date, driver_id=driver_id)
    await message.answer(
        f"Вы выбрали дату: {date.strftime('%d.%m.%Y')}\n"
        "Выберите время начала:",
        reply_markup=generate_time_slots_kb(date, driver_id, user.id)
    )
    await state.set_state(BookingStates.CHOOSING_TIME)


# Время начала
@main_router.message(BookingStates.CHOOSING_TIME, F.text.regexp(r'^🟡 \d{2}:\d{2}'))
async def choose_start_time(message: types.Message, state: FSMContext):
    time_str = message.text.split()[1]
    try:
        time_obj = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return await message.answer("Неверный формат времени. Выберите из списка.")

    data = await state.get_data()
    date = data["selected_date"]
    start_dt = datetime.combine(date, time_obj)

    if start_dt < datetime.now():
        return await message.answer("Нельзя выбрать прошедшее время. Выберите другое.")

    await state.update_data(start_time=start_dt)
    await message.answer(
        "Теперь выберите время окончания:",
        reply_markup=generate_time_slots_kb(date, data["driver_id"], message.from_user.id)
    )
    await state.set_state(BookingStates.CHOOSING_END_TIME)


# Время окончания
@main_router.message(BookingStates.CHOOSING_END_TIME, F.text.regexp(r'^🟡 \d{2}:\d{2}'))
async def choose_end_time(message: types.Message, state: FSMContext):
    time_str = message.text.split()[1]
    try:
        time_obj = datetime.strptime(time_str, "%H:%M").time()
    except ValueError:
        return await message.answer("Неверный формат времени. Выберите из списка.")

    data = await state.get_data()
    date = data["selected_date"]
    start_dt = data["start_time"]
    end_dt = datetime.combine(date, time_obj)

    if end_dt <= start_dt:
        return await message.answer("Время окончания должно быть позже времени начала. Выберите снова.")

    await state.update_data(end_time=end_dt)
    await message.answer(
        "Хотите добавить заметку к бронированию? (например, адрес или особые пожелания)\n"
        "Если нет, отправьте '-'",
        reply_markup=back_kb()
    )
    await state.set_state(BookingStates.ADDING_NOTES)


# Заметка
@main_router.message(BookingStates.ADDING_NOTES)
async def add_notes(message: types.Message, state: FSMContext):
    notes = message.text if message.text != '-' else None
    data = await state.get_data()

    confirm_text = (
        "Подтвердите бронирование:\n"
        f"📅 Дата: {data['selected_date'].strftime('%d.%m.%Y')}\n"
        f"⏰ Время: {data['start_time'].strftime('%H:%M')} - {data['end_time'].strftime('%H:%M')}\n"
        f"📝 Заметки: {notes if notes else 'нет'}"
    )

    confirm_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm_booking")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data="cancel_booking")]
    ])

    await state.update_data(notes=notes)
    await message.answer(confirm_text, reply_markup=confirm_kb)
    await state.set_state(BookingStates.CONFIRMATION)


# Подтверждение
@main_router.callback_query(BookingStates.CONFIRMATION, F.data == "confirm_booking")
async def confirm_booking(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("Ошибка: пользователь не найден")
        await state.clear()
        return

    booking_id = db.add_booking(
        driver_id=data['driver_id'],
        user_id=user.id,
        booking_time=data['start_time'] - timedelta(minutes=30),
        end_time=data['end_time'] + timedelta(minutes=30),
        notes=data.get('notes')
    )

    if booking_id is None:
        # Слот успели занять
        await callback.message.edit_text(
            "⚠️ К сожалению, выбранный интервал уже занят. Пожалуйста, выберите другое время."
        )
        await state.clear()
        return

    if ADMIN_ID:
        try:
            driver = db.get_driver(data['driver_id'])
            await bot.send_message(
                ADMIN_ID,
                f"Новое бронирование #{booking_id}:\n"
                f"👤 Пользователь: {user.name} (@{user.username})\n"
                f"🚗 Водитель: {driver.name if driver else 'Неизвестен'}\n"
                f"📅 Дата: {data['selected_date'].strftime('%d.%m.%Y')}\n"
                f"⏰ Время: {data['start_time'].strftime('%H:%M')} - {data['end_time'].strftime('%H:%M')}\n"
                f"📝 Заметки: {data.get('notes', 'нет')}"
            )
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления админу: {e}")

    await callback.message.edit_text(
        f"✅ Бронирование #{booking_id} подтверждено!\n"
        f"Водитель будет ожидать вас {data['selected_date'].strftime('%d.%m.%Y')} "
        f"с {data['start_time'].strftime('%H:%M')} до {data['end_time'].strftime('%H:%M')}."
    )
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())


# Отмена
@main_router.callback_query(BookingStates.CONFIRMATION, F.data == "cancel_booking")
async def cancel_booking(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.edit_text("❌ Бронирование отменено")
    await state.clear()
    await callback.message.answer("Главное меню:", reply_markup=main_menu_kb())


# Назад
@main_router.message(F.text == '🔙 Назад')
async def back_to_menu(message: types.Message, state: FSMContext):
    if await state.get_state():
        await state.clear()
    await message.answer("Главное меню:", reply_markup=main_menu_kb())


# Простейшие настройки (заглушка)
# @main_router.message(F.text == '⚙️ Настройки')
# async def settings_stub(message: types.Message):
#     await message.answer("Раздел настроек в разработке. Нажмите /start для возвращения в меню.")


async def on_startup():
    # Добавляем тестового водителя при первом запуске
    if not db.get_all_drivers():
        db.add_driver("Персональный водитель")

    # Добавляем инвайт-код по умолчанию
    if not db.check_invite(INVITE_CODE):
        db.add_invite(INVITE_CODE)

    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, "Бот запущен")
        except Exception as e:
            logging.error(f"Ошибка отправки уведомления админу: {e}")


async def on_shutdown():
    if ADMIN_ID:
        try:
            await bot.send_message(ADMIN_ID, "Бот остановлен")
        except Exception:
            pass


if __name__ == "__main__":
    dp.include_router(admin_router)
    dp.include_router(main_router)

    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    asyncio.run(dp.start_polling(bot))
