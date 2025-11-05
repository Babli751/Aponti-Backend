from datetime import datetime, timedelta, date, time
from typing import List
from sqlalchemy.orm import Session

from app.models.models import Booking, Service, WorkingHours
from app.models.schemas import AvailableSlots

def get_bookings(db: Session, barber_id: int, skip: int = 0, limit: int = 100):
    return db.query(Booking).filter(Booking.barber_id == barber_id).offset(skip).limit(limit).all()

def get_customer_bookings(db: Session, customer_email: str):
    return db.query(Booking).filter(Booking.customer_email == customer_email).all()

def create_booking(db: Session, booking_data: dict):
    # Servis süresini al
    service = db.query(Service).filter(Service.id == booking_data["service_id"]).first()
    if not service:
        raise ValueError("Service not found")

    # start_time datetime formatında mı kontrol et
    start_time = booking_data["start_time"]
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))

    # end_time hesapla ve booking_data dict'ine ekle
    end_time = start_time + timedelta(minutes=service.duration)
    booking_data["end_time"] = end_time
    booking_data["status"] = "confirmed"

    # Aynı zaman diliminde başka randevu var mı kontrol et
    existing_booking = db.query(Booking).filter(
        Booking.barber_id == booking_data["barber_id"],
        Booking.start_time < end_time,
        Booking.end_time > start_time,
        Booking.status == "confirmed"
    ).first()

    if existing_booking:
        raise ValueError("This time slot is already booked")

    # Booking nesnesini oluştur
    db_booking = Booking(**booking_data)
    db.add(db_booking)
    db.commit()
    db.refresh(db_booking)
    return db_booking

def cancel_booking(db: Session, booking_id: int):
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        return None

    booking.status = "cancelled"
    db.commit()
    db.refresh(booking)
    return booking

def get_available_slots(db: Session, barber_id: int, service_id: int, selected_date: date):
    # Servis süresi
    service = db.query(Service).filter(Service.id == service_id).first()
    if not service:
        return None

    # Berberin o günkü çalışma saatleri
    day_of_week = selected_date.weekday()
    working_hours = db.query(WorkingHours).filter(
        WorkingHours.barber_id == barber_id,
        WorkingHours.day_of_week == day_of_week,
        WorkingHours.is_working == True
    ).first()

    if not working_hours:
        return AvailableSlots(date=selected_date, available_times=[])

    # O günkü tüm randevular
    start_of_day = datetime.combine(selected_date, time.min)
    end_of_day = datetime.combine(selected_date, time.max)

    bookings = db.query(Booking).filter(
        Booking.barber_id == barber_id,
        Booking.start_time >= start_of_day,
        Booking.start_time <= end_of_day,
        Booking.status == "confirmed"
    ).all()

    # Zaman slotları üret
    slot_duration = timedelta(minutes=service.duration)
    current_time = datetime.combine(selected_date, working_hours.start_time)
    end_time = datetime.combine(selected_date, working_hours.end_time)

    available_slots = []
    while current_time + slot_duration <= end_time:
        slot_available = True
        for booking in bookings:
            if (current_time < booking.end_time) and (current_time + slot_duration > booking.start_time):
                slot_available = False
                break
        if slot_available:
            available_slots.append(current_time)
        current_time += timedelta(minutes=15)  # 15 dakikalık aralıklarla

    return AvailableSlots(date=selected_date, available_times=available_slots)
