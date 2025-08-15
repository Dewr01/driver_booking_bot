from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    DateTime,
    Boolean,
    ForeignKey
)
from sqlalchemy.orm import declarative_base, sessionmaker, relationship, joinedload
from datetime import datetime, timedelta

Base = declarative_base()


class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    tg_id = Column(Integer, unique=True)
    name = Column(String)
    username = Column(String)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)


class Driver(Base):
    __tablename__ = 'drivers'
    id = Column(Integer, primary_key=True)
    name = Column(String)
    phone = Column(String)
    is_active = Column(Boolean, default=True)


class Booking(Base):
    __tablename__ = 'bookings'
    id = Column(Integer, primary_key=True)
    driver_id = Column(Integer)
    user_id = Column(Integer, ForeignKey('users.id'))
    booking_time = Column(DateTime)   # начало
    end_time = Column(DateTime)       # конец
    notes = Column(String, nullable=True)
    status = Column(String, default='active')  # active/canceled/completed

    # отношение к пользователю
    user = relationship("User")


class Invite(Base):
    __tablename__ = 'invites'
    id = Column(Integer, primary_key=True)
    code = Column(String, unique=True)
    is_used = Column(Boolean, default=False)


class Database:
    def __init__(self):
        self.engine = create_engine('sqlite:///bookings.db', connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        # КЛЮЧЕВОЕ: не искать объекты после commit и держать данные доступными
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)

    # ---------- Users ----------
    def add_user(self, tg_id, name, username):
        session = self.Session()
        try:
            user = session.query(User).filter_by(tg_id=tg_id).first()
            if user:
                return user.id
            user = User(tg_id=tg_id, name=name, username=username)
            session.add(user)
            session.commit()
            return user.id
        finally:
            session.close()

    def get_user(self, tg_id):
        session = self.Session()
        try:
            return session.query(User).filter_by(tg_id=tg_id).first()
        finally:
            session.close()

    # ---------- Invites ----------
    def add_invite(self, code):
        session = self.Session()
        try:
            if session.query(Invite).filter_by(code=code).first():
                return False
            session.add(Invite(code=code))
            session.commit()
            return True
        finally:
            session.close()

    def check_invite(self, code):
        session = self.Session()
        try:
            return session.query(Invite).filter_by(code=code, is_used=False).first() is not None
        finally:
            session.close()

    def use_invite(self, code):
        session = self.Session()
        try:
            invite = session.query(Invite).filter_by(code=code, is_used=False).first()
            if not invite:
                return False
            invite.is_used = True
            session.commit()
            return True
        finally:
            session.close()

    # ---------- Drivers ----------
    def add_driver(self, name):
        session = self.Session()
        try:
            driver = Driver(name=name)
            session.add(driver)
            session.commit()
            return driver.id
        finally:
            session.close()

    def get_driver(self, driver_id):
        session = self.Session()
        try:
            return session.get(Driver, driver_id)
        finally:
            session.close()

    def get_all_drivers(self):
        session = self.Session()
        try:
            return session.query(Driver).filter_by(is_active=True).all()
        finally:
            session.close()

    # ---------- Bookings ----------
    def add_booking(self, driver_id, user_id, booking_time, end_time, notes=None):
        session = self.Session()
        try:
            booking = Booking(
                driver_id=driver_id,
                user_id=user_id,
                booking_time=booking_time,
                end_time=end_time,
                notes=notes,
                status='active'
            )
            session.add(booking)
            session.commit()
            return booking.id
        finally:
            session.close()

    def get_booking(self, booking_id):
        session = self.Session()
        try:
            return session.get(Booking, booking_id)
        finally:
            session.close()

    def get_user_bookings(self, user_id):
        session = self.Session()
        try:
            return (
                session.query(Booking)
                .filter_by(user_id=user_id)
                .order_by(Booking.booking_time)
                .all()
            )
        finally:
            session.close()

    def get_all_bookings(self):
        session = self.Session()
        try:
            return (
                session.query(Booking)
                .options(joinedload(Booking.user))
                .order_by(Booking.booking_time)
                .all()
            )
        finally:
            session.close()

    def get_driver_bookings_on_date(self, driver_id, date):
        session = self.Session()
        try:
            start_dt = datetime.combine(date, datetime.min.time())
            end_dt = datetime.combine(date, datetime.max.time())
            return (
                session.query(Booking)
                .options(joinedload(Booking.user))
                .filter(
                    Booking.driver_id == driver_id,
                    Booking.status == 'active',
                    Booking.booking_time >= start_dt,
                    Booking.booking_time <= end_dt
                )
                .order_by(Booking.booking_time)
                .all()
            )
        finally:
            session.close()

    def cancel_booking(self, booking_id):
        session = self.Session()
        try:
            booking = session.get(Booking, booking_id)
            if not booking:
                return False
            booking.status = 'canceled'
            session.commit()
            return True
        finally:
            session.close()

    def delete_canceled_bookings(self):
        """Удаляет все бронирования со статусом 'canceled'"""
        session = self.Session()
        try:
            canceled_bookings = session.query(Booking).filter(Booking.status == 'canceled').all()
            for booking in canceled_bookings:
                session.delete(booking)
            session.commit()
            return len(canceled_bookings)
        except Exception as e:
            session.rollback()
            print(f"Ошибка при удалении: {e}")
            return 0
        finally:
            session.close()

    def delete_old_canceled_bookings(self, days=30):
        """Удаляет отмененные бронирования старше указанного количества дней"""
        session = self.Session()
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            old_bookings = session.query(Booking).filter(
                Booking.status == 'canceled',
                Booking.booking_time < cutoff_date
            ).all()

            for booking in old_bookings:
                session.delete(booking)

            session.commit()
            return len(old_bookings)  # Возвращаем количество удаленных записей
        finally:
            session.close()

    def update_booking(self, booking_id, new_time=None, end_time=None, notes=None):
        session = self.Session()
        try:
            booking = session.get(Booking, booking_id)
            if not booking:
                return False
            if new_time:
                booking.booking_time = new_time
            if end_time:
                booking.end_time = end_time
            if notes is not None:
                booking.notes = notes
            session.commit()
            return True
        finally:
            session.close()


db = Database()
