from datetime import datetime, date
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_active_user
from app.crud.crud_booking import (
    get_bookings,
    get_customer_bookings,
    create_booking,
    cancel_booking,
    get_available_slots
)
from app.models.models import User, Booking as BookingModel, Service
from app.models.schemas import BookingSchema, BookingCreate, AvailableSlots

router = APIRouter(tags=["Bookings"])


@router.post("/", response_model=BookingSchema, status_code=status.HTTP_201_CREATED)
async def create_new_booking(
    booking: BookingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # ✅ Barber kontrolü
    barber = db.query(User).filter(User.id == booking.barber_id, User.is_barber == True).first()
    if not barber:
        raise HTTPException(status_code=404, detail="Barber not found")

    # ✅ Service kontrolü (barber'a ait mi?)
    service = db.query(Service).filter(
        Service.id == booking.service_id,
        Service.barber_id == booking.barber_id
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found for this barber")

    # ✅ Tarih kontrolü (aware datetime)
    start_time = booking.start_time
    print(f"📅 Booking request - Barber: {booking.barber_id}, Service: {booking.service_id}, Start: {start_time}")

    if start_time.tzinfo is None:
        from datetime import timezone
        start_time = start_time.replace(tzinfo=timezone.utc)

    if start_time < datetime.now(tz=start_time.tzinfo):
        raise HTTPException(status_code=400, detail="Booking time must be in the future")

    # Booking verilerini oluştur
    booking_data = booking.dict()
    # Build customer name from first_name and last_name
    customer_name = "Anonymous"
    if current_user.first_name or current_user.last_name:
        customer_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()

    booking_data.update({
        "user_id": current_user.id,
        "barber_id": booking.barber_id,
        "service_id": booking.service_id,
        "customer_email": current_user.email,
        "customer_name": customer_name,
        "customer_phone": current_user.phone_number or booking.customer_phone,
    })

    # ✅ Booking oluşturma
    try:
        new_booking: BookingModel = create_booking(db=db, booking_data=booking_data)
        return BookingSchema.from_orm(new_booking)  # SQLAlchemy objesini Pydantic'e çevir
    except ValueError as e:
        print(f"❌ Booking validation error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        print(f"❌ Booking creation error: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/customer", response_model=List[BookingSchema])
async def get_my_bookings(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    bookings = get_customer_bookings(db=db, customer_email=current_user.email)
    return [BookingSchema.from_orm(b) for b in bookings]


@router.get("/available-slots")
async def get_available_time_slots(
    barber_id: int,
    service_id: int,
    date: date,
    db: Session = Depends(get_db)
):
    slots = get_available_slots(db=db, barber_id=barber_id, service_id=service_id, selected_date=date)
    if not slots:
        raise HTTPException(status_code=404, detail="No available slots found")
    return slots


@router.post("/{booking_id}/cancel", response_model=BookingSchema)
async def cancel_my_booking(
    booking_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    booking = db.query(BookingModel).filter(
        BookingModel.id == booking_id,
        BookingModel.customer_email == current_user.email
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    cancelled_booking = cancel_booking(db=db, booking_id=booking_id)
    if not cancelled_booking:
        raise HTTPException(status_code=400, detail="Could not cancel booking")

    return BookingSchema.from_orm(cancelled_booking)

@router.get("/barber/{barber_id}", response_model=List[BookingSchema])
async def get_bookings_by_barber(
    barber_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # Sadece berber kendi randevularını görebilir
    if not current_user.is_barber or current_user.id != barber_id:
        raise HTTPException(status_code=403, detail="Not authorized to view these bookings")

    bookings = db.query(BookingModel).filter(BookingModel.barber_id == barber_id).all()
    return [BookingSchema.from_orm(b) for b in bookings]


@router.get("/barber-appointments/{barber_id}")
async def get_barber_appointments(
    barber_id: int,
    db: Session = Depends(get_db)
):
    """Get appointments for a specific barber (public endpoint)"""
    bookings = db.query(BookingModel).filter(BookingModel.barber_id == barber_id).all()

    return [
        {
            "id": b.id,
            "customer_name": b.customer_name,
            "customer_phone": b.customer_phone,
            "service": {
                "name": b.service.name if b.service else "Unknown Service",
                "price": b.service.price if b.service else 0,
                "duration": b.service.duration if b.service else 0
            },
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "status": b.status
        }
        for b in bookings
    ]

@router.get("/worker/{worker_id}/date/{date}")
async def get_worker_bookings_by_date(
    worker_id: int,
    date: str,
    db: Session = Depends(get_db)
):
    """Get bookings for a specific worker on a specific date"""
    from datetime import datetime, timedelta

    # Parse the date string (YYYY-MM-DD)
    try:
        target_date = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Get start and end of day
    start_of_day = datetime.combine(target_date, datetime.min.time())
    end_of_day = datetime.combine(target_date, datetime.max.time())

    # Query bookings for this worker on this date
    bookings = db.query(BookingModel).filter(
        BookingModel.barber_id == worker_id,
        BookingModel.start_time >= start_of_day,
        BookingModel.start_time <= end_of_day,
        BookingModel.status != "cancelled"
    ).all()

    return [
        {
            "id": b.id,
            "start_time": b.start_time.isoformat() if b.start_time else None,
            "end_time": b.end_time.isoformat() if b.end_time else None,
            "status": b.status
        }
        for b in bookings
    ]