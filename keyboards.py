from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from datetime import datetime, timedelta


def main_menu_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='📅 Календарь бронирований')],
            [KeyboardButton(text='📝 Мои бронирования')
                # , KeyboardButton(text='⚙️ Настройки')
             ]
        ],
        resize_keyboard=True
    )


def get_calendar_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text='📅 Показать календарь')],
            [KeyboardButton(text='🔙 Назад')]
        ],
        resize_keyboard=True
    )


def generate_dates_kb():
    today = datetime.now().date()
    dates = [today + timedelta(days=i) for i in range(0, 60)]

    buttons = []
    for d in dates:
        day_name = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"][d.weekday()]
        buttons.append(KeyboardButton(text=f"{day_name} {d.strftime('%d.%m')}"))

    rows = [buttons[i:i + 4] for i in range(0, len(buttons), 4)]
    rows.append([KeyboardButton(text='🔙 Назад')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def generate_time_slots_kb(date, driver_id, user_id=None):
    from database import db
    from datetime import datetime, time as dtime

    bookings = db.get_driver_bookings_on_date(driver_id, date)  # уже с joinedload(user)
    # Составим интервалы, заранее вытащив имя пользователя (без ленивой подгрузки)
    intervals = []
    for b in bookings:
        booked_by_name = b.user.name if getattr(b, "user", None) else "Неизвестно"
        intervals.append((b.booking_time, b.end_time, b.user_id, booked_by_name))

    free_buttons = []
    for hour in range(8, 22):
        for minute in (0, 30):
            slot_start = datetime.combine(date, dtime(hour=hour, minute=minute))
            slot_end = slot_start + timedelta(minutes=30)

            # пересечение интервалов
            taken = False
            for b_start, b_end, b_uid, _ in intervals:
                if (slot_start < b_end) and (slot_end > b_start):
                    taken = True
                    break

            if not taken:
                free_buttons.append(KeyboardButton(text=f"🟡 {hour:02d}:{minute:02d}"))

    rows = [free_buttons[i:i + 4] for i in range(0, len(free_buttons), 4)]
    rows.append([KeyboardButton(text='🔙 Назад')])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def booking_actions_kb(booking_id):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✏️ Редактировать", callback_data=f"edit_{booking_id}")],
        [InlineKeyboardButton(text="❌ Отменить", callback_data=f"cancel_{booking_id}")]
    ])
    return kb


def back_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text='🔙 Назад')]], resize_keyboard=True)
